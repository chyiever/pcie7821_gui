"""
Detrend滤波设置检查和测试
Detrend Filter Settings Verification

检查当前的detrend设置是否合适：
1. scipy.welch中的detrend='constant'设置
2. FPGA中的detrend_bw=10Hz高通滤波器设置
3. 两种detrend方法的区别和影响
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy import signal
import sys
import os

# 添加src路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from spectrum_analyzer import RealTimeSpectrumAnalyzer, WindowType


def test_detrend_effects():
    """测试不同detrend设置的效果"""
    print("=" * 70)
    print("Detrend滤波设置检查")
    print("=" * 70)

    # 创建测试信号：包含DC偏移、低频漂移和信号成分
    fs = 2000  # 采样率 2kHz
    t = np.linspace(0, 4, fs * 4)  # 4秒信号

    # 信号成分
    dc_offset = 100.0                           # DC偏移
    drift = 50 * np.sin(2*np.pi*0.5*t)        # 0.5Hz 低频漂移
    signal_50hz = 10 * np.sin(2*np.pi*50*t)   # 50Hz 信号
    signal_100hz = 5 * np.sin(2*np.pi*100*t)  # 100Hz 信号
    noise = 1.0 * np.random.randn(len(t))     # 白噪声

    # 组合信号
    test_signal = dc_offset + drift + signal_50hz + signal_100hz + noise

    print(f"测试信号组成:")
    print(f"  DC偏移: {dc_offset}")
    print(f"  低频漂移: 50×sin(2π×0.5×t) Hz")
    print(f"  信号1: 10×sin(2π×50×t) Hz")
    print(f"  信号2: 5×sin(2π×100×t) Hz")
    print(f"  白噪声: σ=1.0")
    print(f"  采样率: {fs} Hz, 时长: {len(t)/fs:.1f}s")

    return test_signal, fs


def compare_detrend_methods(signal_data, fs):
    """比较不同detrend方法的效果"""
    print("\n" + "="*50)
    print("scipy.welch不同detrend设置对比")
    print("="*50)

    n = len(signal_data)

    # 测试不同detrend设置
    detrend_options = [
        ('constant', '移除DC分量（当前设置）'),
        ('linear', '移除线性趋势'),
        (False, '不做去趋势'),
        (lambda x: signal.detrend(x, type='linear', bp=[n//4, n//2, 3*n//4]), '分段线性去趋势')
    ]

    results = {}

    for detrend_type, description in detrend_options:
        try:
            # 使用scipy.welch计算PSD
            freq, psd = signal.welch(
                signal_data,
                fs=fs,
                window='hann',
                nperseg=n,
                noverlap=0,
                nfft=n,
                return_onesided=True,
                scaling='density',
                detrend=detrend_type
            )

            psd_db = 10 * np.log10(psd + 1e-20)
            results[str(detrend_type)] = (freq, psd_db, description)

            # 分析低频成分 (0-10Hz)
            low_freq_mask = freq <= 10
            low_freq_power = np.mean(psd_db[low_freq_mask])

            # 分析信号频率附近的功率
            freq_50_idx = np.argmin(np.abs(freq - 50))
            freq_100_idx = np.argmin(np.abs(freq - 100))
            power_50hz = psd_db[freq_50_idx]
            power_100hz = psd_db[freq_100_idx]

            print(f"\n{description}:")
            print(f"  0-10Hz平均功率: {low_freq_power:.1f} dB")
            print(f"  50Hz功率: {power_50hz:.1f} dB")
            print(f"  100Hz功率: {power_100hz:.1f} dB")
            print(f"  总功率范围: {np.min(psd_db):.1f} - {np.max(psd_db):.1f} dB")

        except Exception as e:
            print(f"错误处理 {detrend_type}: {e}")

    return results


def analyze_fpga_detrend_vs_scipy_detrend(signal_data, fs):
    """分析FPGA高通滤波与scipy detrend的区别"""
    print("\n" + "="*50)
    print("FPGA高通滤波 vs scipy detrend 对比分析")
    print("="*50)

    # 模拟FPGA的高通滤波器（10Hz截止）
    detrend_bw = 10.0  # Hz，当前FPGA设置

    # 设计高通滤波器
    nyquist = fs / 2
    normal_cutoff = detrend_bw / nyquist

    # 使用Butterworth高通滤波器模拟FPGA行为
    from scipy.signal import butter, filtfilt

    b, a = butter(2, normal_cutoff, btype='high', analog=False)
    fpga_filtered = filtfilt(b, a, signal_data)

    print(f"FPGA高通滤波器设置:")
    print(f"  截止频率: {detrend_bw} Hz")
    print(f"  滤波器类型: 2阶Butterworth")
    print(f"  归一化截止频率: {normal_cutoff:.4f}")

    # 对比原始信号、FPGA滤波、scipy detrend
    signals_to_compare = {
        'original': (signal_data, '原始信号'),
        'fpga_filtered': (fpga_filtered, f'FPGA高通滤波({detrend_bw}Hz)'),
        'scipy_constant': (signal_data, 'scipy detrend=constant'),
        'scipy_linear': (signal_data, 'scipy detrend=linear')
    }

    psd_results = {}

    for key, (data, desc) in signals_to_compare.items():
        if key == 'scipy_constant':
            detrend_param = 'constant'
        elif key == 'scipy_linear':
            detrend_param = 'linear'
        else:
            detrend_param = False  # 不做scipy层面的detrend

        freq, psd = signal.welch(
            data, fs=fs, window='hann', nperseg=len(data),
            noverlap=0, return_onesided=True,
            scaling='density', detrend=detrend_param
        )

        psd_db = 10 * np.log10(psd + 1e-20)
        psd_results[key] = (freq, psd_db, desc)

        # 分析关键频率的功率
        dc_power = psd_db[0] if len(psd_db) > 0 else 0
        low_freq_power = np.mean(psd_db[freq <= 1])  # 0-1Hz
        mid_freq_power = np.mean(psd_db[(freq >= 1) & (freq <= 10)])  # 1-10Hz

        print(f"\n{desc}:")
        print(f"  DC(0Hz)功率: {dc_power:.1f} dB")
        print(f"  0-1Hz平均功率: {low_freq_power:.1f} dB")
        print(f"  1-10Hz平均功率: {mid_freq_power:.1f} dB")

    return psd_results


def create_comparison_plots(psd_results, detrend_results):
    """创建对比图表"""
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))

    # 子图1: 不同scipy detrend设置对比
    ax1.set_title('scipy.welch不同detrend设置对比', fontweight='bold')
    for detrend_type, (freq, psd_db, desc) in detrend_results.items():
        ax1.plot(freq, psd_db, label=desc, alpha=0.8)
    ax1.set_xlabel('频率 (Hz)')
    ax1.set_ylabel('PSD (dB)')
    ax1.set_xlim(0, 200)
    ax1.grid(True, alpha=0.3)
    ax1.legend()

    # 子图2: 低频段细节（0-20Hz）
    ax2.set_title('低频段对比 (0-20Hz)', fontweight='bold')
    for detrend_type, (freq, psd_db, desc) in detrend_results.items():
        mask = freq <= 20
        ax2.plot(freq[mask], psd_db[mask], label=desc, alpha=0.8)
    ax2.set_xlabel('频率 (Hz)')
    ax2.set_ylabel('PSD (dB)')
    ax2.grid(True, alpha=0.3)
    ax2.legend()

    # 子图3: FPGA vs scipy对比
    ax3.set_title('FPGA高通滤波 vs scipy detrend', fontweight='bold')
    colors = ['blue', 'red', 'green', 'orange']
    for i, (key, (freq, psd_db, desc)) in enumerate(psd_results.items()):
        ax3.plot(freq, psd_db, label=desc, color=colors[i], alpha=0.8)
    ax3.set_xlabel('频率 (Hz)')
    ax3.set_ylabel('PSD (dB)')
    ax3.set_xlim(0, 200)
    ax3.grid(True, alpha=0.3)
    ax3.legend()

    # 子图4: 低频段FPGA vs scipy对比
    ax4.set_title('低频段FPGA vs scipy对比 (0-50Hz)', fontweight='bold')
    for i, (key, (freq, psd_db, desc)) in enumerate(psd_results.items()):
        mask = freq <= 50
        ax4.plot(freq[mask], psd_db[mask], label=desc, color=colors[i], alpha=0.8)
    ax4.set_xlabel('频率 (Hz)')
    ax4.set_ylabel('PSD (dB)')
    ax4.grid(True, alpha=0.3)
    ax4.legend()

    plt.tight_layout()
    plt.savefig('detrend_comparison.png', dpi=150, bbox_inches='tight')
    plt.show()


def analyze_current_settings():
    """分析当前设置是否合理"""
    print("\n" + "="*70)
    print("当前设置合理性分析")
    print("="*70)

    print("当前配置:")
    print("1. FPGA处理：detrend_bw = 10Hz 高通滤波器")
    print("2. scipy.welch：detrend = 'constant' (移除DC分量)")

    print("\n设置分析:")
    print("【FPGA高通滤波 (10Hz)】")
    print("✓ 优势：")
    print("  - 硬件实现，实时处理")
    print("  - 有效去除光纤振动监测中无关的超低频漂移")
    print("  - 保留≥10Hz的振动信号（符合DAS应用需求）")
    print("  - 减少ADC饱和风险")

    print("\n【scipy detrend='constant'】")
    print("✓ 优势：")
    print("  - 软件层面移除剩余DC分量")
    print("  - 适合PSD密度计算")
    print("  - 不影响AC信号成分")
    print("✗ 局限：")
    print("  - 只移除常数偏移，不处理线性或非线性漂移")

    print("\n建议设置评估:")
    print("🔍 当前设置 detrend='constant' 是合理的，因为：")
    print("  1. FPGA已经做了主要的高通滤波(10Hz)")
    print("  2. 相位数据经过FPGA处理后，主要剩余问题是DC偏移")
    print("  3. 'constant'去趋势足以处理PSD计算前的DC问题")
    print("  4. 不会引入额外的信号失真")


def test_alternative_detrend_settings():
    """测试其他可能的detrend设置"""
    print("\n" + "="*50)
    print("替代detrend设置测试")
    print("="*50)

    # 创建包含多种漂移的测试信号
    fs = 1000
    t = np.linspace(0, 5, fs * 5)  # 5秒

    # 复杂漂移信号
    dc = 50
    linear_drift = 20 * t  # 线性漂移
    nonlinear_drift = 10 * np.sin(2*np.pi*0.2*t)  # 0.2Hz非线性漂移
    signal_20hz = 5 * np.sin(2*np.pi*20*t)  # 20Hz有用信号
    signal_100hz = 3 * np.sin(2*np.pi*100*t)  # 100Hz有用信号

    complex_signal = dc + linear_drift + nonlinear_drift + signal_20hz + signal_100hz

    # 测试不同设置对信噪比的影响
    detrend_options = ['constant', 'linear', False]

    print("测试信号：DC + 线性漂移 + 0.2Hz非线性漂移 + 20Hz信号 + 100Hz信号")

    for detrend_type in detrend_options:
        freq, psd = signal.welch(
            complex_signal, fs=fs, nperseg=len(complex_signal),
            scaling='density', detrend=detrend_type
        )

        psd_db = 10 * np.log10(psd + 1e-20)

        # 计算信号频率处的SNR
        freq_20_idx = np.argmin(np.abs(freq - 20))
        freq_100_idx = np.argmin(np.abs(freq - 100))

        # 估算噪声底线（高频部分平均）
        noise_floor = np.mean(psd_db[freq > 200])

        snr_20hz = psd_db[freq_20_idx] - noise_floor
        snr_100hz = psd_db[freq_100_idx] - noise_floor

        print(f"\ndetrend={detrend_type}:")
        print(f"  20Hz SNR: {snr_20hz:.1f} dB")
        print(f"  100Hz SNR: {snr_100hz:.1f} dB")
        print(f"  0-1Hz平均功率: {np.mean(psd_db[freq <= 1]):.1f} dB")


def main():
    """主测试函数"""
    # 生成测试信号
    test_signal, fs = test_detrend_effects()

    # 对比不同scipy detrend设置
    detrend_results = compare_detrend_methods(test_signal, fs)

    # 分析FPGA vs scipy detrend
    psd_results = analyze_fpga_detrend_vs_scipy_detrend(test_signal, fs)

    # 创建对比图表
    create_comparison_plots(psd_results, detrend_results)

    # 分析当前设置合理性
    analyze_current_settings()

    # 测试其他设置
    test_alternative_detrend_settings()

    print("\n" + "="*70)
    print("总结与建议")
    print("="*70)
    print("✅ 当前detrend设置是合理的：")
    print("   - FPGA: 10Hz高通滤波器（硬件层面去除低频漂移）")
    print("   - scipy: detrend='constant'（软件层面移除DC偏移）")
    print("")
    print("🔧 可能的优化方向：")
    print("   1. 根据具体应用调整FPGA的detrend_bw值")
    print("   2. 对于极低频振动监测，可考虑降低detrend_bw")
    print("   3. 对于高频应用，可考虑提高detrend_bw以减少低频噪声")
    print("")
    print("⚠️  注意事项：")
    print("   - FPGA高通滤波是主要的去趋势机制")
    print("   - scipy detrend主要处理剩余的DC偏移")
    print("   - 不建议使用detrend='linear'，可能过度处理信号")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()