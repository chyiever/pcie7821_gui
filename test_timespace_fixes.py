#!/usr/bin/env python3
"""
验证time-space图滚动方向和Y轴刻度修复
"""

import sys
import os
import numpy as np

# 添加src路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from PyQt5.QtWidgets import QApplication

    print("========== Time-Space图修复验证 ==========")

    app = QApplication([])

    from time_space_plot import TimeSpacePlotWidgetV2

    # 创建widget
    widget = TimeSpacePlotWidgetV2()
    widget.show()
    widget.resize(1200, 700)
    app.processEvents()

    print("\n===== 测试数据生成 =====")

    # 创建有意义的测试数据来验证滚动方向
    n_frames = 20
    n_points = 60  # 对应distance range [40, 100]

    # 创建能显示滚动效果的数据
    # 每一帧都有不同的特征，以便观察滚动方向
    test_data = np.zeros((n_frames, n_points))

    for frame in range(n_frames):
        for point in range(n_points):
            # 创建移动的波形：每一帧在不同位置有峰值
            peak_position = (point + frame * 3) % n_points
            distance_from_peak = abs(point - peak_position)
            if distance_from_peak < 5:  # 峰值宽度
                test_data[frame, point] = 0.2 * (1 - distance_from_peak / 5.0)
            else:
                test_data[frame, point] = 0.02 * np.random.randn()

    print(f"✓ 测试数据创建: {test_data.shape} (frames, points)")
    print(f"  数据范围: [{test_data.min():.3f}, {test_data.max():.3f}]")

    # 分批更新数据以模拟滚动效果
    print("\n===== 测试滚动效果 =====")

    batch_size = 5
    for i in range(0, n_frames, batch_size):
        end_idx = min(i + batch_size, n_frames)
        batch_data = test_data[i:end_idx]

        result = widget.update_data(batch_data)
        print(f"✓ 更新数据批次 {i//batch_size + 1}: {batch_data.shape}")

        app.processEvents()

        # 短暂暂停以便观察
        import time
        time.sleep(0.5)

    print("\n===== 验证检查清单 =====")
    print()
    print("请在GUI中检查以下项目:")
    print()
    print("【滚动方向验证】")
    print("1. 波形移动方向: 应该是从右侧进入，向左滚动")
    print("2. 最新数据位置: 应该在图形的右侧")
    print("3. 时间轴方向: X轴从左(过去)到右(现在)")
    print()
    print("【Y轴刻度验证】")
    print("4. Y轴起始值: 应该显示40，不是0")
    print("5. Y轴结束值: 应该显示100")
    print("6. Y轴范围: 完整显示[40, 100]")
    print("7. 无多余空间: 图像应该紧贴Y轴边缘")
    print()
    print("【技术指标】")
    print("8. X轴标签: 'Time (s, total: X.Xs)'")
    print("9. Y轴标签: 'Distance (points: 40 to 100)'")
    print("10. 颜色条: 右侧正常显示")

    # 获取当前参数进行验证
    params = widget.get_parameters()
    print(f"\n===== 当前参数 =====")
    print(f"Distance range: {params['distance_range_start']} - {params['distance_range_end']}")
    print(f"Window frames: {params['window_frames']}")
    print(f"Color range: {params['vmin']} - {params['vmax']}")

    print(f"\n窗口将保持显示15秒供详细检查...")

    for i in range(15, 0, -1):
        print(f"剩余 {i} 秒...", end='\r')
        time.sleep(1)
        app.processEvents()

    print(f"\n\n========== 修复验证总结 ==========")
    print("如果观察到:")
    print("✓ 波形从右向左滚动 - 滚动方向修复成功")
    print("✓ Y轴从40开始显示 - Y轴刻度修复成功")
    print("❌ 仍然向下滚动 - 可能需要数据翻转(fliplr)")
    print("❌ Y轴从0开始 - 可能需要更强制的轴设置")

except Exception as e:
    print(f"❌ 验证失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)