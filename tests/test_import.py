"""
最小导入测试
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    print("正在测试导入...")

    # 测试导入主要模块
    print("1. 导入 PyQt5...")
    from PyQt5.QtWidgets import QApplication

    print("2. 导入 time_space_plot...")
    from time_space_plot import TimeSpacePlotWidgetV2, create_time_space_widget

    print("3. 导入 main_window...")
    from main_window import MainWindow

    print("✅ 所有导入成功！语法错误已修复")

except SyntaxError as e:
    print(f"❌ 语法错误:")
    print(f"文件: {e.filename}")
    print(f"行 {e.lineno}: {e.text}")
    print(f"错误: {e.msg}")

except Exception as e:
    print(f"❌ 导入错误: {e}")
    import traceback
    traceback.print_exc()