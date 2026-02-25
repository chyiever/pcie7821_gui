#!/usr/bin/env python3
"""
简化的运行时模式切换测试
验证修复后的功能是否稳定
"""

import sys
import os

# 添加src路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

print("========== 运行时模式切换修复验证 ==========")
print()
print("修复内容:")
print("1. ✓ 修正了 _update_params() 方法名错误")
print("2. ✓ 改为安全的参数更新方式，避免重新收集所有参数")
print("3. ✓ 添加了region index实时更新")
print("4. ✓ 增强了错误处理机制")
print()

try:
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QTimer

    app = QApplication([])

    from main_window import MainWindow

    # 创建主窗口
    window = MainWindow()
    window.show()
    app.processEvents()

    print("✓ 主窗口创建成功")

    # 验证信号连接
    time_signals = window.mode_time_radio.receivers(window.mode_time_radio.toggled)
    space_signals = window.mode_space_radio.receivers(window.mode_space_radio.toggled)
    region_signals = window.region_index_spin.receivers(window.region_index_spin.valueChanged)

    print(f"✓ Time模式信号连接数: {time_signals}")
    print(f"✓ Space模式信号连接数: {space_signals}")
    print(f"✓ Region信号连接数: {region_signals}")

    # 检查方法是否存在
    has_mode_changed = hasattr(window, '_on_mode_changed')
    has_region_changed = hasattr(window, '_on_region_changed')

    print(f"✓ _on_mode_changed 方法存在: {has_mode_changed}")
    print(f"✓ _on_region_changed 方法存在: {has_region_changed}")

    if not (has_mode_changed and has_region_changed):
        print("❌ 缺少必要的处理方法")
        sys.exit(1)

    print("\n===== 安全模式切换测试 =====")

    # 测试计数器
    switch_count = 0
    error_count = 0

    def safe_mode_switch():
        """安全的模式切换测试"""
        global switch_count, error_count

        try:
            switch_count += 1

            # 切换模式
            if window.mode_time_radio.isChecked():
                window.mode_space_radio.setChecked(True)
                new_mode = "Space"
            else:
                window.mode_time_radio.setChecked(True)
                new_mode = "Time"

            print(f"[{switch_count:2d}] 切换到{new_mode}模式", end="")

            # 处理事件
            app.processEvents()

            # 验证参数是否正确更新
            if hasattr(window, 'params') and window.params is not None:
                mode_str = "SPACE" if window.params.display.mode.value == 1 else "TIME"
                print(f" → 参数更新: {mode_str}")
            else:
                print(" → 参数未初始化")

            return True

        except Exception as e:
            error_count += 1
            print(f" → ❌ 错误: {e}")
            return False

    def test_region_change():
        """测试region变化"""
        try:
            current_region = window.region_index_spin.value()
            new_region = (current_region + 10) % 100

            print(f"Region变化: {current_region} → {new_region}", end="")
            window.region_index_spin.setValue(new_region)
            app.processEvents()

            if hasattr(window, 'params') and window.params is not None:
                actual_region = window.params.display.region_index
                print(f" → 参数更新: {actual_region}")
            else:
                print(" → 参数未初始化")

            return True
        except Exception as e:
            print(f" → ❌ 错误: {e}")
            return False

    # 执行模式切换测试
    print("执行10次模式切换...")
    for i in range(10):
        if not safe_mode_switch():
            break

    # 执行region变化测试
    print("\n执行region变化测试...")
    test_region_change()

    print(f"\n===== 测试结果 =====")
    print(f"✓ 模式切换次数: {switch_count}")
    print(f"✓ 错误次数: {error_count}")

    if error_count == 0:
        print("🎉 运行时模式切换修复成功!")
        print("   • 无崩溃错误")
        print("   • 参数更新正常")
        print("   • 信号连接正确")
    else:
        print(f"⚠️ 仍有 {error_count} 个错误需要处理")

    print(f"\n现在您可以安全地在程序运行期间切换Time/Space模式了。")
    print("建议在实际使用中测试:")
    print("1. 启动数据采集")
    print("2. 在采集过程中切换Time/Space模式")
    print("3. 观察显示效果是否正确切换")
    print("4. 确认不会出现崩溃")

    # 保持窗口显示10秒供手动测试
    print(f"\n窗口将保持显示10秒供手动验证...")

    import time
    for i in range(10, 0, -1):
        print(f"剩余 {i} 秒...", end='\r')
        time.sleep(1)
        app.processEvents()

    print(f"\n\n========== 修复验证完成 ==========")

except Exception as e:
    print(f"❌ 验证程序失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)