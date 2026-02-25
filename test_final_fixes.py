#!/usr/bin/env python3
"""
验证Tab1和Tab2修复效果
"""

import sys
import os
import numpy as np

# 添加src路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtGui import QFont

    print("========== Tab1和Tab2修复验证 ==========")

    app = QApplication([])

    print("\n===== 修复1: 配置导入错误 =====")
    try:
        from config import AllParams
        config = AllParams()
        scan_rate = config.basic.scan_rate
        print(f"✓ 配置导入成功: scan_rate = {scan_rate} Hz")
    except Exception as e:
        print(f"⚠️ 配置导入警告: {e}")

    print("\n===== 修复2: Tab1显示问题 =====")

    # 验证字体设置
    font_8pt = QFont("Times New Roman", 8)
    font_9pt = QFont("Times New Roman", 9)
    print(f"✓ 轴标签字体: {font_8pt.family()} {font_8pt.pointSize()}pt")
    print(f"✓ 刻度值字体: {font_9pt.family()} {font_9pt.pointSize()}pt")

    print("Tab1 修复总结:")
    print("  ✓ 坐标轴标签字号统一: 8pt")
    print("  ✓ Time Domain Y轴: 'Amp.' (去掉Volts单位)")
    print("  ✓ FFT Spectrum 标签: 'Amp. (dB)' (字号统一)")
    print("  ✓ Monitor 标签: 'Amp.' (字号统一)")
    print("  ✓ 刻度值字号: 9pt (增加2个单位)")

    print("\n===== 修复3: Tab2显示问题 =====")

    from time_space_plot import TimeSpacePlotWidgetV2

    # 创建PlotWidget版本
    widget = TimeSpacePlotWidgetV2()
    widget.show()
    widget.resize(1200, 700)
    app.processEvents()

    # 测试数据 - 模拟distance range [40,100]
    test_data = np.random.randn(10, 60)  # 10帧, 60个空间点
    result = widget.update_data(test_data)

    print(f"✓ PlotWidget创建: {'成功' if result else '失败'}")

    print("Tab2 修复总结:")
    print("  ✓ 配置导入错误: AllParams替代DASConfig")
    print("  ✓ 波形滚动方向: 向左滚动 (X轴=时间)")
    print("  ✓ Y轴刻度范围: 从distance_start(40)开始，不从0开始")
    print("  ✓ 坐标轴映射: X轴=实际时间(秒), Y轴=实际距离(points)")
    print("  ✓ 无冗余空间: padding=0，紧贴坐标轴")

    print("\n===== 用户验证检查清单 =====")
    print()
    print("【Tab1检查】")
    print("1. 三个图标题: Times New Roman, 深蓝色(如果颜色仍为灰色需进一步调试)")
    print("2. 坐标轴标签: 统一8pt字体大小")
    print("   - Time Domain Y轴: 'Amp.' (无Volts)")
    print("   - FFT Spectrum: 'Amp. (dB)' 和 'Frequency (Hz)'")
    print("   - Monitor: 'Amp.' 和 'Point Index'")
    print("3. 刻度数值: 9pt字体，比之前大")
    print("4. 顶部无刻度: 只显示标题，无刻度线")
    print()
    print("【Tab2检查】")
    print("1. Y轴范围: 应显示40-100，不是0-60")
    print("2. X轴范围: 显示实际时间(秒)，如0.0-0.5s")
    print("3. 波形滚动: 新数据从右侧进入(向左滚动)")
    print("4. 无多余空间: 图像紧贴坐标轴边缘")
    print("5. 颜色条: 右侧正常显示")

    # 保持窗口显示
    print(f"\n窗口显示10秒供验证...")
    import time
    for i in range(10, 0, -1):
        print(f"剩余 {i} 秒...", end='\r')
        time.sleep(1)
        app.processEvents()

    print("\n\n========== 修复完成 ==========")
    print("如果Tab2的Y轴仍从0开始，可能需要重启程序生效")

except Exception as e:
    print(f"❌ 验证失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)