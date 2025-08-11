#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件整理脚本
功能：将当前目录下的各种文件按类型移动到指定文件夹，并删除临时文件
"""

import os
import shutil
import glob
from pathlib import Path

def create_target_directory():
    """创建目标文件夹"""
    target_dir = r"C:\Z\整理\待整理文件夹"
    try:
        os.makedirs(target_dir, exist_ok=True)
        print(f"创建目标文件夹: {target_dir}")
        return target_dir
    except Exception as e:
        print(f"创建文件夹失败: {e}")
        return None

def move_files_by_extension(target_dir):
    """根据文件扩展名移动文件"""
    # 需要移动的文件扩展名列表
    extensions_to_move = [
        # 图片文件
        "*.jpg", "*.jpeg", "*.png", "*.gif", "*.tif", "*.psd", "*.WEBP",
        # CAD文件
        "*.dwg", "*.dwf", "*.dxf", "*.dwl2",
        # 文档文件
        "*.txt", "*.pdf", "*.xlsx", "*.pptx", "*.xls",
        # 压缩文件
        "*.zip", "*.7z", "*.rar", "*.iso",
        # 3D模型文件
        "*.obj", "*.3ds", "*.vrmesh", "*.fbx", "*.skp", "*.3dm", "*.blend",
        "*.MAX", "*.C4D", "*.dae", "*.mtl", "*.abc",
        # 音视频文件
        "*.mp4", "*.m4a", "*.mid", "*.rmvb", "*.mkv", "*.AVI", "*.MP3", "*.WAV",
        # 其他文件
        "*.swf", "*.torrent", "*.cdr", "*.exe", "*.hdr", "*.ai", "*.skb",
        "*.fas", "*.vlx", "*.exr", "*.dat", "*.stpbak", "*.stp", "*.ini",
        "*.GH", "*.HTM", "*.aep",
        # Guitar Pro文件
        "*.gp5", "*.gp4", "*.gp3", "*.gpx",
        # 其他专业文件
        "*.kbdx", "*.xmind"
    ]
    
    moved_count = 0
    
    for pattern in extensions_to_move:
        files = glob.glob(pattern)
        for file in files:
            try:
                if os.path.isfile(file):
                    destination = os.path.join(target_dir, os.path.basename(file))
                    # 如果目标文件已存在，添加数字后缀
                    counter = 1
                    base_name, ext = os.path.splitext(os.path.basename(file))
                    while os.path.exists(destination):
                        new_name = f"{base_name}_{counter}{ext}"
                        destination = os.path.join(target_dir, new_name)
                        counter += 1
                    
                    shutil.move(file, destination)
                    print(f"移动文件: {file} -> {destination}")
                    moved_count += 1
            except Exception as e:
                print(f"移动文件失败 {file}: {e}")
    
    print(f"总共移动了 {moved_count} 个文件")

def delete_temp_files():
    """删除临时文件"""
    # 需要删除的文件扩展名列表
    extensions_to_delete = [
        "*.dwl", "*.bak", "*.log", "*.downloading", 
        "*.ipa", "*.PART", "*.php", "*.3dmbak", "*.rhl"
    ]
    
    deleted_count = 0
    
    for pattern in extensions_to_delete:
        files = glob.glob(pattern)
        for file in files:
            try:
                if os.path.isfile(file):
                    os.remove(file)
                    print(f"删除临时文件: {file}")
                    deleted_count += 1
            except Exception as e:
                print(f"删除文件失败 {file}: {e}")
    
    print(f"总共删除了 {deleted_count} 个临时文件")

def main():
    """主函数"""
    print("=" * 50)
    print("文件整理脚本开始执行")
    print("=" * 50)
    
    # 获取当前工作目录
    current_dir = os.getcwd()
    print(f"当前工作目录: {current_dir}")
    
    # 创建目标文件夹
    target_dir = create_target_directory()
    if not target_dir:
        print("无法创建目标文件夹，脚本退出")
        return
    
    print("\n1. 开始移动文件...")
    move_files_by_extension(target_dir)
    
    print("\n2. 开始删除临时文件...")
    delete_temp_files()
    
    print("\n" + "=" * 50)
    print("文件整理完成！")
    print("=" * 50)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n用户中断操作")
    except Exception as e:
        print(f"脚本执行出错: {e}")
    finally:
        input("按回车键退出...")
