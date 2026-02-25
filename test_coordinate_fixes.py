#!/usr/bin/env python3
"""
验证坐标轴修复：
1. 滚动方向：向左滚动（X轴=时间）
2. Y轴起始：从distance_start开始，不从0开始
3. 时间轴：不受time DS影响
"""

import sys
import os
import numpy as np

# 添加src路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from PyQt5.QtWidgets import QApplication

    print("========== 坐标轴修复综合验证 ==========")

    app = QApplication([])

    from time_space_plot import TimeSpacePlotWidgetV2

    # 创建widget
    widget = TimeSpacePlotWidgetV2()
    widget.show()
    widget.resize(1200, 700)
    app.processEvents()

    print("\n===== 修复验证设置 =====")

    # 设置测试参数
    params = widget.get_parameters()
    print(f"初始参数:")
    print(f"  Distance range: {params['distance_range_start']} - {params['distance_range_end']}")
    print(f"  Scan rate: {params.get('scan_rate', 'Unknown')} Hz")
    print(f"  Time DS: {params.get('time_downsample', 1)}")
    print(f"  Space DS: {params.get('space_downsample', 1)}")

    # 测试不同Time DS设置对时间轴的影响
    print("\n===== 测试Time DS对时间轴影响 =====")

    test_configs = [
        {"time_ds": 1, "description": "无降采样"},
        {"time_ds": 2, "description": "2倍时间降采样"},
        {"time_ds": 4, "description": "4倍时间降采样"}
    ]

    # 创建测试数据：20帧，60个空间点 (对应distance range [40, 100])
    n_frames = 20
    n_points = 60

    # 创建滚动波形测试数据
    test_data = np.zeros((n_frames, n_points))
    for frame in range(n_frames):
        for point in range(n_points):
            # 创建向左移动的波形：每一帧波峰向左移动
            peak_position = (point - frame * 2) % n_points  # 向左移动
            distance_from_peak = abs(point - peak_position)
            if distance_from_peak < 4:
                test_data[frame, point] = 0.3 * (1 - distance_from_peak / 4.0)
            else:
                test_data[frame, point] = 0.01 * np.random.randn()

    for i, config in enumerate(test_configs):
        print(f"\n--- 测试配置 {i+1}: {config['description']} ---")

        # 设置time DS参数
        if hasattr(widget, '_time_downsample'):
            widget._time_downsample = config['time_ds']

        # 更新数据
        result = widget.update_data(test_data)
        print(f"✓ 数据更新: {'成功' if result else '失败'}")

        # 获取当前显示参数
        params = widget.get_parameters()
        print(f"  Time DS设置: {config['time_ds']}")

        app.processEvents()
        import time
        time.sleep(1.0)  # 暂停观察

    print(f"\n===== 关键验证点 =====")
    print("请在GUI中观察以下项目:")
    print()
    print("【修复1: 滚动方向】")
    print("✓ 波形应该从右侧进入，向左滚动")
    print("✓ X轴代表时间（水平方向）")
    print("✓ 最新数据在右侧，历史数据在左侧")
    print()
    print("【修复2: Y轴刻度】")
    print("✓ Y轴起始值应该显示40，不是0")
    print("✓ Y轴结束值应该显示100")
    print("✓ Y轴代表距离（垂直方向）")
    print("✓ 无多余空间：图像紧贴Y轴边缘")
    print()
    print("【修复3: 时间轴独立性】")
    print("✓ X轴时间范围不应随Time DS变化")
    print("✓ X轴标签：'Time (s, total: X.Xs)'")
    print("✓ 总时间长度 = 帧数 / 采样率，不受降采样影响")
    print()
    print("【技术指标】")
    print("✓ Y轴标签：'Distance (points: 40 to 100)'")
    print("✓ 颜色条：右侧正常显示")
    print("✓ 坐标轴字体：Times New Roman")

    # 最终测试：验证坐标映射
    print(f"\n===== 坐标映射验证 =====")

    # 创建特殊标记数据来验证坐标
    marker_data = np.zeros((10, n_points))

    # 在特定位置放置标记
    marker_data[0, 0] = 1.0      # 第1帧，第1个空间点 -> 应显示在 (t=0, d=40)
    marker_data[0, -1] = 1.0     # 第1帧，最后空间点 -> 应显示在 (t=0, d=100)
    marker_data[-1, 0] = 1.0     # 最后帧，第1个空间点 -> 应显示在 (t=max, d=40)
    marker_data[-1, -1] = 1.0    # 最后帧，最后空间点 -> 应显示在 (t=max, d=100)

    widget.update_data(marker_data)
    print("✓ 已添加坐标标记点")
    print("  四个白色亮点应分别位于:")
    print("  - 左下角: (t=0, distance=40)")
    print("  - 左上角: (t=0, distance=100)")
    print("  - 右下角: (t=最大, distance=40)")
    print("  - 右上角: (t=最大, distance=100)")

    print(f"\n窗口将保持显示20秒供详细验证...")

    for i in range(20, 0, -1):
        print(f"剩余 {i} 秒... 请仔细检查上述验证点", end='\r')
        import time
        time.sleep(1)
        app.processEvents()

    print(f"\n\n========== 修复验证结果 ==========")
    print("如果观察到:")
    print("✅ 波形从右向左滚动 - 坐标轴方向修复成功")
    print("✅ Y轴从40开始显示 - Y轴起始点修复成功")
    print("✅ X轴时间不受Time DS影响 - 时间轴独立性修复成功")
    print("✅ 标记点位置正确 - 坐标映射修复成功")
    print()
    print("如果仍有问题:")
    print("❌ 向下滚动 - 数据transpose可能有问题")
    print("❌ Y轴从0开始 - setRect坐标映射可能失效")
    print("❌ X轴时间变化 - 时间计算仍受降采样影响")

except Exception as e:
    print(f"❌ 验证失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)