#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TTS 程序图标配置检查工具
用于诊断任务栏图标显示问题
"""

import os
import sys

def check_icon_config():
    """检查 TTS 程序的图标配置"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    print("=" * 60)
    print("TTS 程序图标配置检查")
    print("=" * 60)
    print()
    
    # 检查 icon 文件
    print("📁 本目录图标文件:")
    icon_files = {
        "icon.png": "PNG 图标",
        "icon.ico": "ICO 图标",
        "icon_tb.ico": "任务栏 ICO 图标",
        "icon.path": "图标路径配置文件",
    }
    
    found_icons = []
    for filename, description in icon_files.items():
        file_path = os.path.join(script_dir, filename)
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            print(f"  ✅ {filename} ({description}) - {size} bytes")
            found_icons.append(filename)
        else:
            print(f"  ❌ {filename} ({description}) - 未找到")
    
    print()
    
    # 检查备选图标目录
    print("📁 备选图标目录 (QT/AYE):")
    qt_aye_path = os.path.join(script_dir, "..", "QT", "AYE")
    alt_icons = {
        "icon.ico": "ICO 图标",
        "icon.png": "PNG 图标",
    }
    
    if os.path.exists(qt_aye_path):
        for filename, description in alt_icons.items():
            file_path = os.path.join(qt_aye_path, filename)
            if os.path.exists(file_path):
                size = os.path.getsize(file_path)
                rel_path = os.path.relpath(file_path, script_dir)
                print(f"  ✅ {rel_path} ({description}) - {size} bytes")
            else:
                print(f"  ❌ {filename} ({description}) - 未找到")
    else:
        print(f"  ❌ 备选目录不存在: {qt_aye_path}")
    
    print()
    
    # 检查环境变量
    print("🔧 环境变量:")
    aye_tts_icon = os.environ.get("AYE_TTS_ICON", "").strip().strip('"')
    if aye_tts_icon:
        if os.path.exists(aye_tts_icon):
            print(f"  ✅ AYE_TTS_ICON 已设置 → {aye_tts_icon}")
        else:
            print(f"  ⚠️  AYE_TTS_ICON 已设置但文件不存在 → {aye_tts_icon}")
    else:
        print("  ❌ AYE_TTS_ICON 未设置")
    
    print()
    
    # 检查 icon.path 配置文件内容
    icon_path_file = os.path.join(script_dir, "icon.path")
    print("📄 icon.path 配置文件:")
    if os.path.exists(icon_path_file):
        try:
            with open(icon_path_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if content:
                print(f"  ✅ 内容: {content}")
                # 验证路径是否存在
                test_path = content if os.path.isabs(content) else os.path.join(script_dir, content)
                if os.path.exists(test_path):
                    print(f"  ✅ 指定的图标文件存在")
                else:
                    print(f"  ⚠️  指定的图标文件不存在: {test_path}")
            else:
                print("  ⚠️  文件为空")
        except Exception as e:
            print(f"  ❌ 读取失败: {e}")
    else:
        print("  ❌ 文件不存在 (可选)")
    
    print()
    
    # 建议
    print("💡 建议:")
    if "icon.png" in found_icons and "icon_tb.ico" not in found_icons:
        print("  • icon.png 存在，icon_tb.ico 不存在")
        print("    → 程序会自动转换 PNG 为 ICO")
    elif "icon_tb.ico" in found_icons:
        print("  • ✅ 已有 icon_tb.ico，任务栏图标优先使用此文件")
    elif "icon.ico" in found_icons:
        print("  • ✅ 已有 icon.ico，可用作备选")
    
    print()
    print("=" * 60)
    print("配置检查完成")
    print("=" * 60)

if __name__ == "__main__":
    check_icon_config()
