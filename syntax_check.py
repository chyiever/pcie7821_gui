#!/usr/bin/env python3
"""
语法检查脚本
"""

import ast
import sys
import os

def check_syntax(file_path):
    """检查Python文件语法"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()

        # 尝试解析语法
        ast.parse(source)
        print(f"✓ {file_path} 语法正确")
        return True
    except SyntaxError as e:
        print(f"❌ {file_path} 语法错误:")
        print(f"   行 {e.lineno}: {e.text}")
        print(f"   错误: {e.msg}")
        return False
    except Exception as e:
        print(f"❌ {file_path} 检查失败: {e}")
        return False

if __name__ == "__main__":
    # 检查关键文件
    files_to_check = [
        'src/main_window.py',
        'src/time_space_plot.py'
    ]

    all_good = True
    for file_path in files_to_check:
        if os.path.exists(file_path):
            if not check_syntax(file_path):
                all_good = False
        else:
            print(f"⚠️ 文件不存在: {file_path}")

    if all_good:
        print("\n✅ 所有文件语法检查通过")
    else:
        print("\n❌ 发现语法错误，请修复后再试")
        sys.exit(1)