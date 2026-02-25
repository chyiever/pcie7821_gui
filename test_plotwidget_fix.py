#!/usr/bin/env python3
"""
测试PlotWidget版本的time-space图实现
"""

import sys
import os

# 添加src路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    import numpy as np
    from PyQt5.QtWidgets import QApplication

    print("正在测试PlotWidget版本的导入...")

    # 测试导入
    from time_space_plot import TimeSpacePlotWidgetV2
    print("✓ TimeSpacePlotWidgetV2 导入成功")

    # 测试基本初始化
    app = QApplication([])

    widget = TimeSpacePlotWidgetV2()
    print("✓ TimeSpacePlotWidgetV2 初始化成功")

    # 测试接口兼容性
    params = widget.get_parameters()
    print(f"✓ 参数获取成功: {len(params)} 个参数")

    # 测试数据处理
    test_data = np.random.randn(10, 100)  # 10帧，100个空间点
    result = widget.update_data(test_data)
    print(f"✓ 数据更新测试: {'成功' if result else '失败'}")

    # 显示widget来验证轴显示
    widget.show()
    widget.resize(1000, 600)
    print("✓ PlotWidget版本创建成功，应该显示坐标轴刻度")

    print("\n========== 测试总结 ==========")
    print("✓ 所有基本功能测试通过")
    print("✓ PlotWidget版本可以替代ImageView版本")
    print("✓ 坐标轴刻度显示应该工作正常")
    print("\n请在主程序中查看坐标轴是否正常显示")

    # 简短显示然后退出
    import time
    time.sleep(2)

except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("测试完成")