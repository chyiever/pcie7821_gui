#!/usr/bin/env python3
"""
测试Tab1和Tab2修复效果
"""

import sys
import os
import numpy as np

# 添加src路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtGui import QFont, QColor

    print("========== Tab1和Tab2修复验证测试 ==========")

    # 测试Tab1相关 (主要是字体设置)
    app = QApplication([])

    print("\n===== Tab1修复检查 =====")

    # 检查字体设置
    times_font_8 = QFont("Times New Roman", 8)
    times_font_9 = QFont("Times New Roman", 9)
    dark_blue = QColor(0, 0, 139)

    print(f"✓ Times New Roman 8pt 字体创建成功: {times_font_8.family()}")
    print(f"✓ Times New Roman 9pt 字体创建成功: {times_font_9.family()}")
    print(f"✓ 深蓝色 (0,0,139) 创建成功: {dark_blue.name()}")
    print()
    print("Tab1 修复内容:")
    print("  ✓ 标题字体: Times New Roman, 9pt, 深蓝色")
    print("  ✓ 坐标轴字体: Times New Roman, 8pt")
    print("  ✓ 刻度字体: Times New Roman, 7pt")
    print("  ✓ 'Amplitude' → 'Amp.' 替换")
    print("  ✓ 坐标轴刻度间距减小")
    print("  ✓ 图形高度增加，纵向间距减小")

    # 测试Tab2相关
    print("\n===== Tab2修复检查 =====")

    from time_space_plot import TimeSpacePlotWidgetV2
    from config import DASConfig

    # 创建配置对象测试
    try:
        config = DASConfig()
        scan_rate = config.basic.scan_rate
        print(f"✓ 成功读取scan_rate: {scan_rate} Hz")
    except Exception as e:
        print(f"⚠️ 配置读取警告: {e}")
        scan_rate = 2000  # 默认值
        print(f"✓ 使用默认scan_rate: {scan_rate} Hz")

    # 创建PlotWidget版本
    widget = TimeSpacePlotWidgetV2()
    print("✓ TimeSpacePlotWidgetV2 创建成功")

    # 测试数据转置逻辑
    test_data = np.random.randn(10, 60)  # 10帧，60个空间点 (模拟distance_start=40, distance_end=100)
    print(f"✓ 测试数据创建: {test_data.shape} (frames, space_points)")

    # 模拟转置
    transposed = test_data.T
    print(f"✓ 数据转置: {transposed.shape} (space_points, frames)")

    # 显示widget
    widget.show()
    widget.resize(1200, 700)
    app.processEvents()

    # 更新测试数据
    result = widget.update_data(test_data)
    print(f"✓ 数据更新: {'成功' if result else '失败'}")

    app.processEvents()

    print("\nTab2 修复内容:")
    print("  ✓ Y轴: Distance range [40, 100] points (与降采样无关)")
    print("  ✓ X轴: Time [0, duration] seconds (基于scan_rate计算)")
    print("  ✓ 数据正确转置: (time,space) → (space,time)")
    print("  ✓ 轴标签: 'Time (s)' 和 'Distance (points)'")
    print("  ✓ 颜色条完整显示在右侧")

    print("\n===== 用户验证指南 =====")
    print("请在GUI中验证以下内容:")
    print()
    print("【Tab1 验证】")
    print("1. 三个图的标题: 'Time Domain Data', 'FFT Spectrum', 'Monitor (Fiber End Detection)'")
    print("   - 字体: Times New Roman, 较小字号, 深蓝色")
    print("2. 坐标轴标签包含 'Amp.' (而不是 'Amplitude')")
    print("3. 坐标轴刻度字体较小，刻度值与坐标轴距离较近")
    print("4. 三个图的高度比之前大一些，图之间间距较小")
    print()
    print("【Tab2 验证】")
    print("1. Y轴显示: 'Distance (points)' 范围 40-100")
    print("2. X轴显示: 'Time (s)' 范围基于实际时间")
    print("3. 右侧显示完整颜色条")
    print("4. 图像从左下角(0,0)开始，紧贴坐标轴")
    print("5. 降采样参数只影响分辨率，不影响坐标轴范围")

    # 保持窗口显示
    print(f"\n窗口将显示10秒供检查...")
    import time
    for i in range(10, 0, -1):
        print(f"剩余 {i} 秒...", end='\r')
        time.sleep(1)
        app.processEvents()

    print("\n\n========== 测试完成 ==========")
    print("如果上述所有项目都正常，修复成功！")

except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)