# -*- coding: utf-8 -*-
import os
import sys
import subprocess
import importlib.util

def check_and_install_packages():
    """检查并安装所需的包"""
    required_packages = {
        'pywinstyles': 'pywinstyles',
        'PIL': 'Pillow',
        'nonexistent_package': 'nonexistent_package'  # 添加一个不存在的包来测试
    }
    
    missing_packages = []
    
    # 检查每个包是否已安装
    for import_name, package_name in required_packages.items():
        if importlib.util.find_spec(import_name) is None:
            missing_packages.append(package_name)
    
    if missing_packages:
        # 如果有缺失的包，显示GUI提示
        try:
            import tkinter as tk
            from tkinter import messagebox
            
            root = tk.Tk()
            root.withdraw()  # 隐藏主窗口
            
            packages_str = '\n'.join([f"  • {pkg}" for pkg in missing_packages])
            message = f"检测到缺少以下依赖包:\n\n{packages_str}\n\n是否现在自动安装这些包？"
            
            print(f"缺少依赖包: {missing_packages}")
            return False  # 测试版本直接返回，不实际安装
            
        except ImportError:
            print("检测到缺少以下依赖包:")
            for package in missing_packages:
                print(f"  - {package}")
            return False
    
    print("所有依赖包已安装")
    return True

# 执行依赖检查
if check_and_install_packages():
    print("程序正常启动")
else:
    print("依赖检查发现问题")
