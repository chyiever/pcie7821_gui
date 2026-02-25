#!/usr/bin/env python3
"""
测试PlotWidget版本的time-space图修复
验证颜色条、坐标轴、定位等问题的修复效果
"""

import sys
import os
import numpy as np

# 添加src路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from PyQt5.QtWidgets import QApplication
    from time_space_plot import TimeSpacePlotWidgetV2

    print("========== PlotWidget版本修复测试 ==========")

    # 测试导入
    print("✓ TimeSpacePlotWidgetV2 导入成功")

    # 测试基本初始化
    app = QApplication([])

    widget = TimeSpacePlotWidgetV2()
    print("✓ TimeSpacePlotWidgetV2 初始化成功")

    # 显示widget
    widget.show()
    widget.resize(1200, 700)  # 更大尺寸以便看到颜色条

    # 等待UI完全初始化
    app.processEvents()

    # 测试参数获取
    params = widget.get_parameters()
    print(f"✓ 参数获取成功: {len(params)} 个参数")
    print(f"  - Distance range: {params['distance_range_start']} - {params['distance_range_end']}")
    print(f"  - Color range: {params['vmin']} - {params['vmax']}")

    # 生成测试数据模拟真实场景
    print("\n========== 测试数据处理 ==========")
    # 模拟100个空间点，10个时间帧的相位数据
    n_points = 100
    n_frames = 10

    # 创建有意义的测试数据：沿空间有渐变，沿时间有变化
    test_data = np.zeros((n_frames, n_points))
    for t in range(n_frames):
        for x in range(n_points):
            # 空间渐变 + 时间变化 + 一些噪声
            test_data[t, x] = 0.1 * np.sin(x/10.0) * np.cos(t/2.0) + 0.01 * np.random.randn()

    print(f"生成测试数据: {test_data.shape}, 范围: [{test_data.min():.3f}, {test_data.max():.3f}]")

    # 更新数据
    result = widget.update_data(test_data)
    print(f"✓ 数据更新: {'成功' if result else '失败'}")

    # 处理UI事件以确保显示更新
    app.processEvents()

    print("\n========== 修复验证检查 ==========")

    # 检查1: 颜色条是否存在
    if hasattr(widget, 'colorbar_widget'):
        print("✓ 颜色条组件存在")
        print(f"  颜色条尺寸: {widget.colorbar_widget.size()}")
    else:
        print("❌ 颜色条组件缺失")

    # 检查2: 主图形是否正确设置
    if hasattr(widget, 'plot_widget'):
        print("✓ 主图形组件存在")
        view_box = widget.plot_widget.getViewBox()
        if view_box:
            x_range = view_box.viewRange()[0]
            y_range = view_box.viewRange()[1]
            print(f"  X轴范围: {x_range}")
            print(f"  Y轴范围: {y_range}")

            # 验证X轴起始是否为0（修复问题4）
            if abs(x_range[0]) < 0.1:
                print("✓ X轴起始位置修复成功 (从0开始)")
            else:
                print(f"⚠️ X轴起始位置: {x_range[0]} (应该接近0)")
    else:
        print("❌ 主图形组件缺失")

    # 检查3: 图像项是否正确设置
    if hasattr(widget, 'image_item'):
        print("✓ 图像项存在")
        # 获取图像边界
        rect = widget.image_item.boundingRect()
        print(f"  图像边界: {rect}")
    else:
        print("❌ 图像项缺失")

    print("\n========== 用户界面检查指南 ==========")
    print("请在弹出的窗口中检查以下项目：")
    print("")
    print("1. 颜色条显示:")
    print("   ✓ 窗口右侧应显示垂直颜色条")
    print("   ✓ 颜色条右侧应有数值刻度")
    print("   ✓ 颜色条应显示从-0.1到0.1的范围")
    print("")
    print("2. 坐标轴显示:")
    print("   ✓ X轴应显示距离范围 (40-100)")
    print("   ✓ Y轴应显示时间采样点 (0-时间点数)")
    print("   ✓ 坐标轴刻度应清晰可见")
    print("")
    print("3. 图像定位:")
    print("   ✓ 彩色图像应紧贴坐标轴，无多余空白")
    print("   ✓ X轴起始应对应距离起始值40")
    print("   ✓ 图像左边缘应在X=0位置")
    print("")
    print("4. 控制面板:")
    print("   ✓ 顶部应显示 '✓ Using PlotWidget for reliable axis display'")
    print("   ✓ 所有参数控件应正常工作")
    print("")

    # 保持窗口显示一段时间
    print("窗口将保持显示10秒以便检查...")
    import time

    for i in range(10, 0, -1):
        print(f"  剩余 {i} 秒...", end='\r')
        time.sleep(1)
        app.processEvents()  # 保持界面响应

    print("\n\n========== 测试完成 ==========")
    print("如果以上所有检查项目都正常，说明修复成功！")

except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)