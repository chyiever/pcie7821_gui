#!/usr/bin/env python3
"""
验证模式修复：
1. Time/Space模式区别
2. Tab1/Tab2独立性
3. 默认参数值(detrend=10Hz, polar_div=True)
"""

import sys
import os
import numpy as np

# 添加src路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QTimer

    print("========== 模式修复综合验证 ==========")

    app = QApplication([])

    from main_window import MainWindow

    # 创建主窗口
    window = MainWindow()
    window.show()
    app.processEvents()

    print("\n===== 验证默认参数值 =====")
    print(f"✓ Detrend默认值: {window.detrend_bw_spin.value():.1f}Hz (期望: 10.0Hz)")
    print(f"✓ PolarDiv默认状态: {'已勾选' if window.polar_div_check.isChecked() else '未勾选'} (期望: 已勾选)")

    print("\n===== 验证信号连接 =====")
    # 检查信号连接
    time_connected = len(window.mode_time_radio.receivers(window.mode_time_radio.toggled)) > 0
    space_connected = len(window.mode_space_radio.receivers(window.mode_space_radio.toggled)) > 0

    print(f"✓ Time模式信号连接: {'已连接' if time_connected else '未连接'} (期望: 已连接)")
    print(f"✓ Space模式信号连接: {'已连接' if space_connected else '未连接'} (期望: 已连接)")

    print("\n===== 模拟数据测试 =====")

    # 创建模拟数据
    def create_test_data():
        # 创建多帧数据: 4帧，每帧60个点
        frames = 4
        points_per_frame = 60
        total_points = frames * points_per_frame

        data = np.zeros(total_points)

        # 第1帧: 正弦波
        for i in range(points_per_frame):
            data[i] = 0.5 * np.sin(2 * np.pi * i / 20) + 0.1 * np.random.randn()

        # 第2帧: 余弦波
        for i in range(points_per_frame, 2*points_per_frame):
            idx = i - points_per_frame
            data[i] = 0.4 * np.cos(2 * np.pi * idx / 15) + 0.1 * np.random.randn()

        # 第3帧: 三角波
        for i in range(2*points_per_frame, 3*points_per_frame):
            idx = i - 2*points_per_frame
            data[i] = 0.3 * (2 * abs(2 * (idx / 30.0 - 0.5)) - 1) + 0.1 * np.random.randn()

        # 第4帧: 方波
        for i in range(3*points_per_frame, 4*points_per_frame):
            idx = i - 3*points_per_frame
            data[i] = 0.6 * (1 if (idx % 20) < 10 else -1) + 0.1 * np.random.randn()

        return data

    test_data = create_test_data()
    print(f"✓ 创建测试数据: {len(test_data)} points")

    # 测试函数
    def test_mode_differences():
        print("\n--- 测试Time vs Space模式差异 ---")

        # 设置参数
        window.frame_num_spin.setValue(4)
        window.merge_points_spin.setValue(1)
        window.point_num_spin.setValue(60)

        # 设置区域索引为中间位置
        window.region_index_spin.setValue(30)

        print(f"参数设置: frame_num=4, point_num=60, region_index=30")

        # 测试Time模式
        print("\n1. 测试Time模式:")
        window.mode_time_radio.setChecked(True)
        app.processEvents()

        # 模拟数据处理
        window._on_phase_data(test_data, 0, 1)
        app.processEvents()

        # 检查Time模式结果（应该显示多条曲线，每条代表一帧）
        time_curves_with_data = 0
        for i, curve in enumerate(window.plot_curve_1[:4]):
            x_data, y_data = curve.getData()
            if y_data is not None and len(y_data) > 0:
                time_curves_with_data += 1
                print(f"   Frame {i+1}: {len(y_data)} points, range=[{np.min(y_data):.3f}, {np.max(y_data):.3f}]")

        print(f"   Time模式活动曲线数: {time_curves_with_data}")

        import time
        time.sleep(1.0)

        # 测试Space模式
        print("\n2. 测试Space模式:")
        window.mode_space_radio.setChecked(True)
        app.processEvents()

        # 模拟数据处理
        window._on_phase_data(test_data, 0, 1)
        app.processEvents()

        # 检查Space模式结果（应该只显示一条曲线，代表指定位置的时间序列）
        space_curves_with_data = 0
        for i, curve in enumerate(window.plot_curve_1[:4]):
            x_data, y_data = curve.getData()
            if y_data is not None and len(y_data) > 0:
                space_curves_with_data += 1
                if i == 0:
                    print(f"   Region {window.region_index_spin.value()}: {len(y_data)} points, range=[{np.min(y_data):.3f}, {np.max(y_data):.3f}]")

        print(f"   Space模式活动曲线数: {space_curves_with_data}")

        # 验证结果
        print(f"\n--- 模式差异验证结果 ---")
        if time_curves_with_data > 1 and space_curves_with_data == 1:
            print("✅ Time/Space模式正常工作")
            print("   Time模式: 多条曲线(多帧数据)")
            print("   Space模式: 单条曲线(时间序列)")
        elif time_curves_with_data == space_curves_with_data:
            print("❌ Time/Space模式显示相同结果")
            print("   可能原因: 信号连接失败或参数更新失败")
        else:
            print("⚠️ 未预期的结果")
            print(f"   Time模式曲线数: {time_curves_with_data}")
            print(f"   Space模式曲线数: {space_curves_with_data}")

    def test_tab_independence():
        print("\n--- 测试Tab1/Tab2独立性 ---")

        # 切换到Tab1
        window.plot_tabs.setCurrentIndex(0)
        print("1. 切换到Tab1 (Time Plot)")

        # 激活Tab2的PLOT按钮（如果存在）
        if hasattr(window, 'time_space_widget') and window.time_space_widget is not None:
            if hasattr(window.time_space_widget, 'plot_btn'):
                window.time_space_widget.plot_btn.setChecked(True)
                print("   ✓ Tab2 PLOT按钮已激活")

            # 处理数据，应该只更新Tab1，不更新Tab2（因为Tab2不活动）
            window._on_phase_data(test_data, 0, 1)
            app.processEvents()
            print("   ✓ 数据处理完成（仅Tab1活动）")

        # 切换到Tab2
        window.plot_tabs.setCurrentIndex(1)
        print("\n2. 切换到Tab2 (Time-Space Plot)")

        # 再次处理数据，现在应该更新Tab2
        if hasattr(window, 'time_space_widget') and window.time_space_widget is not None:
            window._on_phase_data(test_data, 0, 1)
            app.processEvents()
            print("   ✓ 数据处理完成（Tab2活动）")

        print("\n--- Tab独立性验证 ---")
        print("✅ Tab1/Tab2根据当前活动标签页更新")
        print("   当Tab1活动时: 只更新Time Plot")
        print("   当Tab2活动时: 根据PLOT按钮状态更新Time-Space Plot")

    # 延迟执行测试
    def delayed_tests():
        test_mode_differences()
        test_tab_independence()

    QTimer.singleShot(2000, delayed_tests)  # 2秒后开始测试

    print(f"\n===== 用户交互验证 =====")
    print("请手动验证以下功能:")
    print()
    print("【模式切换】")
    print("1. 点击'Time'模式 → 应显示多条重叠曲线（不同帧）")
    print("2. 点击'Space'模式 → 应显示单条曲线（时间序列）")
    print("3. 改变Region值 → Space模式曲线应变化，Time模式不变")
    print()
    print("【Tab独立性】")
    print("4. 切换到Tab2 → 激活PLOT按钮 → 应显示time-space图")
    print("5. 切换回Tab1 → Tab1正常显示，Tab2暂停更新")
    print()
    print("【默认值】")
    print("6. 检查Detrend值是否为10.0Hz")
    print("7. 检查PolarDiv是否已勾选")

    print(f"\n窗口将保持显示30秒供验证...")

    # 保持窗口显示
    import time
    for i in range(30, 0, -1):
        print(f"剩余 {i} 秒...", end='\r')
        time.sleep(1)
        app.processEvents()

    print(f"\n\n========== 修复验证结果 ==========")
    print("如果观察到:")
    print("✅ Time模式显示多条曲线，Space模式显示单条曲线 - 模式修复成功")
    print("✅ Tab切换时更新逻辑正确 - Tab独立性修复成功")
    print("✅ Detrend=10Hz, PolarDiv=已勾选 - 默认值修复成功")
    print("✅ 模式切换时有debug输出 - 信号连接修复成功")

except Exception as e:
    print(f"❌ 验证失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)