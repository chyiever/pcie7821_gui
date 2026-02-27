"""
新频谱分析逻辑测试
Test New Spectrum Analysis Logic

测试修改后的频谱分析逻辑：
- Raw数据 (data_type='short'): 只计算功率谱
- Phase数据 (data_type='int'): 只计算PSD (使用scipy.welch)

New Logic Test:
- Raw data (data_type='short'): Power spectrum only
- Phase data (data_type='int'): PSD only (using scipy.welch)
"""

import numpy as np
import matplotlib.pyplot as plt
import sys
import os

# 添加src路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from spectrum_analyzer import RealTimeSpectrumAnalyzer, WindowType


def create_test_signals():
    """创建测试信号"""
    sample_rate = 2000  # 2kHz
    duration = 2.0      # 2秒
    n_samples = int(sample_rate * duration)

    t = np.linspace(0, duration, n_samples, endpoint=False)

    # 测试信号：100Hz + 300Hz + 噪声
    signal = (1.0 * np.sin(2*np.pi*100*t) +     # 100Hz
              0.5 * np.sin(2*np.pi*300*t) +     # 300Hz
              0.1 * np.random.randn(n_samples)) # 白噪声

    # 模拟raw数据 (int16)
    raw_data = (signal * 16384).astype(np.int16)

    # 模拟phase数据 (int32)
    phase_data = (signal * 32767).astype(np.int32)

    return raw_data, phase_data, sample_rate


def test_new_logic():
    """测试新的分析逻辑"""
    print("=" * 70)
    print("新频谱分析逻辑测试")
    print("=" * 70)

    # 创建分析器
    analyzer = RealTimeSpectrumAnalyzer(WindowType.HANNING, averaging_count=1)

    # 创建测试信号
    raw_data, phase_data, sample_rate = create_test_signals()

    print(f"测试信号参数:")
    print(f"  采样率: {sample_rate} Hz")
    print(f"  数据长度: {len(raw_data)} 样本")
    print(f"  信号成分: 100Hz (幅度1.0) + 300Hz (幅度0.5) + 白噪声")

    # 测试1: Raw数据 → 功率谱
    print("\n" + "="*50)
    print("测试1: Raw数据分析 (应该返回功率谱)")
    print("="*50)

    freq_raw, power_raw, df_raw = analyzer.update(
        raw_data, sample_rate, psd_mode=True, data_type='short'
    )  # 注意：psd_mode=True 会被忽略，因为raw数据只计算功率谱

    print(f"结果:")
    print(f"  数据类型: Raw (int16)")
    print(f"  分析类型: 功率谱 (忽略psd_mode参数)")
    print(f"  频率分辨率: {df_raw:.3f} Hz")
    print(f"  频率范围: 0 - {freq_raw[-1]:.1f} Hz")
    print(f"  幅值范围: {np.min(power_raw):.1f} - {np.max(power_raw):.1f} dB")

    # 找峰值
    peaks_raw = find_peaks(freq_raw, power_raw, threshold=-10)
    print(f"  峰值频率: {[f'{f:.1f}Hz({p:.1f}dB)' for f, p in peaks_raw[:3]]}")

    # 测试2: Phase数据 → PSD
    print("\n" + "="*50)
    print("测试2: Phase数据分析 (应该返回PSD)")
    print("="*50)

    freq_phase, psd_phase, df_phase = analyzer.update(
        phase_data, sample_rate, psd_mode=False, data_type='int'
    )  # 注意：psd_mode=False 会被忽略，因为phase数据只计算PSD

    print(f"结果:")
    print(f"  数据类型: Phase (int32)")
    print(f"  分析类型: PSD (使用scipy.welch，忽略psd_mode参数)")
    print(f"  频率分辨率: {df_phase:.3f} Hz")
    print(f"  频率范围: 0 - {freq_phase[-1]:.1f} Hz")
    print(f"  幅值范围: {np.min(psd_phase):.1f} - {np.max(psd_phase):.1f} dB")

    # 找峰值
    peaks_phase = find_peaks(freq_phase, psd_phase, threshold=-10)
    print(f"  峰值频率: {[f'{f:.1f}Hz({p:.1f}dB)' for f, p in peaks_phase[:3]]}")

    # 对比分析
    print("\n" + "="*50)
    print("对比分析:")
    print("="*50)
    print("主要区别:")
    print("1. Raw数据 → 功率谱 (dB)")
    print("   - 使用自定义FFT算法")
    print("   - 包含DC成分(0Hz)")
    print("   - 单位: dB")

    print("\n2. Phase数据 → PSD (dB)")
    print("   - 使用scipy.signal.welch")
    print("   - 窗口长度 = 信号长度")
    print("   - density类型，单位: dB (不是dB/Hz)")
    print("   - 自动去除DC成分")

    # 绘图对比
    create_comparison_plots(freq_raw, power_raw, freq_phase, psd_phase)

    return freq_raw, power_raw, freq_phase, psd_phase


def find_peaks(freq, spectrum, threshold=-10):
    """简单的峰值检测"""
    peaks = []
    for i in range(1, len(spectrum)-1):
        if (spectrum[i] > threshold and
            spectrum[i] > spectrum[i-1] and
            spectrum[i] > spectrum[i+1]):
            peaks.append((freq[i], spectrum[i]))

    return sorted(peaks, key=lambda x: x[1], reverse=True)


def create_comparison_plots(freq_raw, power_raw, freq_phase, psd_phase):
    """创建对比图"""
    plt.figure(figsize=(12, 8))

    # 子图1: Raw数据功率谱
    plt.subplot(2, 1, 1)
    plt.plot(freq_raw, power_raw, 'b-', linewidth=1)
    plt.title('Raw数据功率谱 (Power Spectrum)', fontsize=12, fontweight='bold')
    plt.xlabel('频率 (Hz)')
    plt.ylabel('功率 (dB)')
    plt.grid(True, alpha=0.3)
    plt.xlim(0, 1000)

    # 子图2: Phase数据PSD
    plt.subplot(2, 1, 2)
    plt.plot(freq_phase, psd_phase, 'r-', linewidth=1)
    plt.title('Phase数据PSD (使用scipy.welch)', fontsize=12, fontweight='bold')
    plt.xlabel('频率 (Hz)')
    plt.ylabel('PSD (dB)')
    plt.grid(True, alpha=0.3)
    plt.xlim(0, 1000)

    plt.tight_layout()
    plt.savefig('spectrum_analysis_comparison.png', dpi=150, bbox_inches='tight')
    plt.show()


def test_data_type_detection():
    """测试数据类型自动检测"""
    print("\n" + "="*70)
    print("数据类型自动检测测试")
    print("="*70)

    analyzer = RealTimeSpectrumAnalyzer()
    raw_data, phase_data, sample_rate = create_test_signals()

    # 测试dtype检测
    print("1. 通过numpy dtype检测:")
    print(f"   raw_data.dtype = {raw_data.dtype} → 应该识别为raw数据")
    print(f"   phase_data.dtype = {phase_data.dtype} → 应该识别为phase数据")

    # 不指定data_type，让其自动检测
    freq1, spec1, df1 = analyzer.update(raw_data, sample_rate)
    freq2, spec2, df2 = analyzer.update(phase_data, sample_rate)

    print("\n2. 自动检测结果:")
    print(f"   int16数据 → 功率谱，幅值范围: {np.min(spec1):.1f} - {np.max(spec1):.1f} dB")
    print(f"   int32数据 → PSD，幅值范围: {np.min(spec2):.1f} - {np.max(spec2):.1f} dB")


def test_welch_parameters():
    """测试scipy.welch参数设置"""
    print("\n" + "="*70)
    print("scipy.welch参数验证")
    print("="*70)

    from scipy import signal

    # 创建简单测试信号
    fs = 1000
    t = np.arange(0, 2, 1/fs)
    x = np.sin(2*np.pi*50*t) + 0.1*np.random.randn(len(t))

    print(f"测试信号: 50Hz正弦波 + 噪声")
    print(f"采样率: {fs} Hz")
    print(f"信号长度: {len(x)} 样本")

    # 使用不同参数调用welch
    print("\n参数设置验证:")

    # 1. 窗口长度 = 信号长度（我们的设置）
    freq1, psd1 = signal.welch(
        x, fs=fs,
        window='hann',
        nperseg=len(x),  # 窗口长度 = 信号长度
        noverlap=0,      # 无重叠
        nfft=len(x),     # FFT长度 = 信号长度
        return_onesided=True,
        scaling='density',
        detrend='constant'
    )

    print(f"1. 我们的设置 (nperseg={len(x)}):")
    print(f"   频率分辨率: {freq1[1] - freq1[0]:.3f} Hz")
    print(f"   频率点数: {len(freq1)}")
    print(f"   PSD范围: {np.min(10*np.log10(psd1)):.1f} - {np.max(10*np.log10(psd1)):.1f} dB")

    # 2. 默认设置（作对比）
    freq2, psd2 = signal.welch(x, fs=fs, scaling='density')

    print(f"\n2. 默认设置:")
    print(f"   频率分辨率: {freq2[1] - freq2[0]:.3f} Hz")
    print(f"   频率点数: {len(freq2)}")
    print(f"   PSD范围: {np.min(10*np.log10(psd2)):.1f} - {np.max(10*np.log10(psd2)):.1f} dB")

    print("\n结论: 我们的设置提供最大频率分辨率")


if __name__ == "__main__":
    # 运行所有测试
    try:
        test_new_logic()
        test_data_type_detection()
        test_welch_parameters()

        print("\n" + "="*70)
        print("测试完成！")
        print("="*70)
        print("修改总结:")
        print("1. Raw数据 (data_type='short') → 只计算功率谱")
        print("2. Phase数据 (data_type='int') → 只计算PSD (scipy.welch)")
        print("3. psd_mode参数已废弃，分析类型由data_type自动决定")
        print("4. 保持了数据类型自动检测功能")
        print("5. scipy.welch使用窗口长度=信号长度，获得最大频率分辨率")

    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()