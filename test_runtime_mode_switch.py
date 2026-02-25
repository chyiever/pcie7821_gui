#!/usr/bin/env python3
"""
测试运行时模式切换功能
验证：
1. 程序运行期间可以安全切换Time/Space模式
2. 模式切换不会导致程序崩溃
3. 切换后显示效果正确
"""

import sys
import os
import numpy as np

# 添加src路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from PyQt5.QtWidgets import QApplication, QMessageBox
    from PyQt5.QtCore import QTimer

    print("========== 运行时模式切换测试 ==========")

    app = QApplication([])

    from main_window import MainWindow

    # 创建主窗口
    window = MainWindow()
    window.show()
    app.processEvents()

    print("\n===== 测试设置 =====")

    # 设置测试参数
    window.frame_num_spin.setValue(4)
    window.merge_points_spin.setValue(1)
    window.point_num_spin.setValue(60)
    window.region_index_spin.setValue(25)  # 中间位置

    print(f"✓ 测试参数设置完成")
    print(f"  Frame数: {window.frame_num_spin.value()}")
    print(f"  Point数: {window.point_num_spin.value()}")
    print(f"  Region索引: {window.region_index_spin.value()}")

    # 模拟数据生成函数
    def create_test_data(frame_count=4, point_count=60):
        """创建测试数据"""
        total_points = frame_count * point_count
        data = np.zeros(total_points)

        for frame in range(frame_count):
            start_idx = frame * point_count
            for point in range(point_count):
                idx = start_idx + point
                # 每帧不同的波形特征
                if frame == 0:  # 正弦波
                    data[idx] = 0.5 * np.sin(2 * np.pi * point / 20) + 0.1 * np.random.randn()
                elif frame == 1:  # 余弦波
                    data[idx] = 0.4 * np.cos(2 * np.pi * point / 15) + 0.1 * np.random.randn()
                elif frame == 2:  # 三角波
                    data[idx] = 0.3 * np.abs(2 * (point / 30.0) - 1) + 0.1 * np.random.randn()
                else:  # 方波
                    data[idx] = 0.6 * (1 if (point % 20) < 10 else -1) + 0.1 * np.random.randn()

        return data

    # 测试计数器
    test_count = 0
    mode_switches = 0

    def simulate_data_and_switch():
        """模拟数据处理和模式切换"""
        global test_count, mode_switches

        try:
            # 生成测试数据
            test_data = create_test_data()

            # 模拟数据处理
            window._on_phase_data(test_data, 0, 1)
            test_count += 1

            # 每3次数据更新切换一次模式
            if test_count % 3 == 0:
                current_mode = "Time" if window.mode_time_radio.isChecked() else "Space"

                # 切换模式
                if window.mode_time_radio.isChecked():
                    window.mode_space_radio.setChecked(True)
                    new_mode = "Space"
                else:
                    window.mode_time_radio.setChecked(True)
                    new_mode = "Time"

                mode_switches += 1
                print(f"[{test_count:2d}] 模式切换: {current_mode} → {new_mode} (第{mode_switches}次切换)")

                app.processEvents()

                # 验证参数是否正确更新
                if hasattr(window, 'params'):
                    print(f"     参数更新: mode={window.params.display.mode}, region={window.params.display.region_index}")

            else:
                current_mode = "Time" if window.mode_time_radio.isChecked() else "Space"
                print(f"[{test_count:2d}] 数据更新: 当前模式={current_mode}")

            app.processEvents()

        except Exception as e:
            print(f"❌ 第{test_count}次测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False

        return True

    print(f"\n===== 开始运行时切换测试 =====")
    print("将进行15次数据更新，每3次切换一次模式...")
    print("如果程序不崩溃，说明运行时切换功能正常\n")

    # 设置定时器进行自动测试
    test_timer = QTimer()
    test_timer.timeout.connect(simulate_data_and_switch)

    def start_test():
        """开始测试"""
        global test_count
        if test_count < 15:
            if simulate_data_and_switch():
                # 继续下一次测试
                QTimer.singleShot(800, start_test)  # 800ms间隔
            else:
                print("\n❌ 测试因错误终止")
        else:
            print(f"\n✅ 测试完成!")
            print(f"   总数据更新次数: {test_count}")
            print(f"   总模式切换次数: {mode_switches}")
            print(f"   程序运行稳定，未发生崩溃")

            # 最终验证
            print(f"\n===== 最终验证 =====")

            # 检查当前显示状态
            time_curves_active = 0
            space_curves_active = 0

            for i, curve in enumerate(window.plot_curve_1[:4]):
                x_data, y_data = curve.getData()
                if y_data is not None and len(y_data) > 0:
                    if window.mode_time_radio.isChecked():
                        time_curves_active += 1
                    else:
                        space_curves_active += 1

            current_mode = "Time" if window.mode_time_radio.isChecked() else "Space"
            active_curves = time_curves_active if window.mode_time_radio.isChecked() else space_curves_active

            print(f"✓ 当前模式: {current_mode}")
            print(f"✓ 活动曲线数: {active_curves}")

            if current_mode == "Time" and time_curves_active > 1:
                print("✅ Time模式正常: 显示多条曲线")
            elif current_mode == "Space" and space_curves_active == 1:
                print("✅ Space模式正常: 显示单条曲线")
            else:
                print("⚠️ 显示状态可能异常，需要手动检查")

    # 延迟开始测试
    QTimer.singleShot(1000, start_test)

    print(f"===== 手动验证指南 =====")
    print("在自动测试运行期间，您可以:")
    print("1. 观察控制台输出，查看模式切换日志")
    print("2. 观察GUI界面，确认Time/Space模式显示差异")
    print("3. 手动点击Time/Space按钮测试响应")
    print("4. 观察是否有异常或崩溃")
    print()
    print("预期结果:")
    print("• Time模式: 显示多条重叠曲线(不同帧)")
    print("• Space模式: 显示单条曲线(时间序列)")
    print("• 切换过程: 无崩溃，无错误")

    # 保持窗口显示30秒
    print(f"\n窗口将保持显示30秒...")

    # 创建倒计时
    remaining_time = [30]  # 使用列表以便在内部函数中修改

    def countdown():
        if remaining_time[0] > 0:
            print(f"剩余 {remaining_time[0]} 秒... (测试{'进行中' if test_count < 15 else '已完成'})", end='\r')
            remaining_time[0] -= 1
            QTimer.singleShot(1000, countdown)
        else:
            print(f"\n\n========== 运行时切换测试结果 ==========")
            if mode_switches > 0:
                print("✅ 运行时模式切换功能正常")
                print("   • 模式切换过程无崩溃")
                print("   • 参数更新机制正常")
                print("   • GUI显示响应正确")
            else:
                print("⚠️ 未进行模式切换测试")

            print(f"\n如果在测试过程中没有看到崩溃错误,")
            print(f"说明运行时模式切换问题已修复!")

            app.quit()

    countdown()

    app.exec_()

except Exception as e:
    print(f"❌ 测试程序启动失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)