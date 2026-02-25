#!/usr/bin/env python3
"""
测试HistogramLUTWidget颜色条功能
验证：
1. 垂直方向的颜色渐变条
2. 数据直方图分布显示
3. 亮度/对比度交互式调整
4. 颜色映射与主图同步
"""

import sys
import os
import numpy as np

# 添加src路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QTimer

    print("========== HistogramLUTWidget颜色条测试 ==========")

    app = QApplication([])

    from time_space_plot import TimeSpacePlotWidgetV2

    # 创建widget
    widget = TimeSpacePlotWidgetV2()
    widget.show()
    widget.resize(1400, 700)  # 增加宽度以容纳新的histogram widget
    app.processEvents()

    print("\n===== 新颜色条功能验证 =====")

    # 创建测试数据 - 具有明显的数据分布特征
    n_frames = 50
    n_points = 60

    # 创建具有不同数据分布的测试数据
    test_data = np.zeros((n_frames, n_points))

    # 第一部分：高斯分布数据（中心区域）
    for frame in range(n_frames//3):
        center = n_points // 2
        for point in range(n_points):
            distance = abs(point - center)
            if distance < 15:
                test_data[frame, point] = 0.3 * np.exp(-(distance/5.0)**2) + 0.05*np.random.randn()

    # 第二部分：双峰分布数据
    for frame in range(n_frames//3, 2*n_frames//3):
        for point in range(n_points):
            # 两个峰值位置
            peak1_dist = abs(point - 15)
            peak2_dist = abs(point - 45)
            if peak1_dist < 8:
                test_data[frame, point] = 0.5 * (1 - peak1_dist/8.0)
            elif peak2_dist < 8:
                test_data[frame, point] = -0.4 * (1 - peak2_dist/8.0)
            else:
                test_data[frame, point] = 0.02 * np.random.randn()

    # 第三部分：均匀分布 + 噪声
    for frame in range(2*n_frames//3, n_frames):
        test_data[frame, :] = np.random.uniform(-0.2, 0.2, n_points)

    print(f"✓ 创建测试数据: {test_data.shape}")
    print(f"  数据范围: [{test_data.min():.3f}, {test_data.max():.3f}]")
    print(f"  数据分布特征:")
    print(f"    - 高斯分布区域: frames 0-{n_frames//3}")
    print(f"    - 双峰分布区域: frames {n_frames//3}-{2*n_frames//3}")
    print(f"    - 均匀分布区域: frames {2*n_frames//3}-{n_frames}")

    # 更新数据到widget
    result = widget.update_data(test_data)
    print(f"✓ 数据更新: {'成功' if result else '失败'}")

    print(f"\n===== HistogramLUTWidget功能验证 =====")
    print("请在GUI中验证以下功能:")
    print()
    print("【颜色条改进验证】")
    print("1. ✅ 颜色渐变条: 垂直方向显示，不是水平方向")
    print("2. ✅ 直方图分布: 右侧显示数据的直方图分布曲线")
    print("3. ✅ 交互式调整: 可以拖动上下边界来调整亮度/对比度")
    print("4. ✅ 实时更新: 调整时主图颜色映射同步更新")
    print()
    print("【具体操作验证】")
    print("5. 拖动histogram上边界 → 调整最大显示值")
    print("6. 拖动histogram下边界 → 调整最小显示值")
    print("7. 观察直方图分布 → 应显示三种不同的数据分布特征")
    print("8. 切换颜色映射 → jet/viridis等应同步到histogram")
    print()
    print("【技术指标】")
    print("9. 宽度适当: histogram widget不会占用过多空间")
    print("10. 响应性好: 颜色调整无明显延迟")
    print("11. 背景协调: histogram背景为白色，与整体UI一致")

    # 测试不同颜色映射
    def test_colormaps():
        print(f"\n--- 测试不同颜色映射 ---")
        colormaps = ['jet', 'viridis', 'plasma', 'hot', 'gray']

        for i, cmap in enumerate(colormaps):
            print(f"切换到颜色映射: {cmap}")
            # 这里应该通过控制面板切换，暂时用参数更新
            widget._colormap = cmap
            widget._apply_colormap_v2()
            app.processEvents()

            # 短暂停顿观察
            import time
            time.sleep(1.5)

        print("✓ 颜色映射测试完成")

    # 延迟执行颜色映射测试
    def delayed_test():
        test_colormaps()

    QTimer.singleShot(3000, delayed_test)  # 3秒后开始测试

    print(f"\n===== 显示保持时间 =====")
    print(f"窗口将保持显示30秒供详细验证...")
    print(f"3秒后将自动测试不同颜色映射...")

    # 保持窗口显示
    import time
    for i in range(30, 0, -1):
        print(f"剩余 {i} 秒...", end='\r')
        time.sleep(1)
        app.processEvents()

    print(f"\n\n========== HistogramLUTWidget测试完成 ==========")
    print("如果观察到:")
    print("✅ 垂直颜色渐变条 - 颜色条方向修复成功")
    print("✅ 直方图分布显示 - 数据分布可视化增强")
    print("✅ 交互式亮度/对比度 - 用户体验显著改善")
    print("✅ 实时颜色映射同步 - 功能集成良好")
    print()
    print("新的HistogramLUTWidget提供了:")
    print("• 专业的科学可视化颜色控制")
    print("• 直观的数据分布理解")
    print("• 灵活的显示参数调整")

except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)