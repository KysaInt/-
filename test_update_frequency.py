#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试🗂️.py的更新频率
"""

import os
import shutil
import time
import subprocess

def create_test_files():
    """创建测试PNG文件"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 创建一些测试PNG文件
    test_files = [
        "test0001.png",
        "test0002.png", 
        "test0003.png"
    ]
    
    for filename in test_files:
        file_path = os.path.join(base_dir, filename)
        if not os.path.exists(file_path):
            # 创建空的PNG文件
            with open(file_path, 'wb') as f:
                # 写入最小的PNG文件头
                f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82')
            print(f"创建测试文件: {filename}")
            time.sleep(2)  # 间隔2秒创建文件，测试程序响应

if __name__ == "__main__":
    print("开始创建测试文件来验证🗂️.py的更新频率...")
    print("请在另一个终端运行🗂️.py程序")
    print("观察程序是否每秒更新一次")
    input("按回车键开始创建测试文件...")
    
    create_test_files()
    print("测试文件创建完成")
