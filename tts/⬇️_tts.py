#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub TTS目录下载器
运行此程序会自动下载 https://github.com/KysaInt/-/tree/main/tts 到同级目录
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path


def check_git_installed():
    """检查Git是否安装"""
    try:
        subprocess.run(['git', '--version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def check_git_lfs_installed():
    """检查Git LFS是否安装"""
    try:
        subprocess.run(['git', 'lfs', '--version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def download_with_git(repo_url, branch, target_folder, output_dir):
    """使用Git稀疏检出下载特定目录"""
    print(f"准备下载 {repo_url} 的 {target_folder} 分支...")
    
    # 创建临时目录用于git操作
    temp_dir = os.path.join(output_dir, '.git_temp')
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        print("初始化Git仓库（稀疏检出）...")
        # 初始化git仓库
        subprocess.run(['git', 'init'], cwd=temp_dir, check=True, capture_output=True)
        
        # 配置远程仓库
        subprocess.run(
            ['git', 'remote', 'add', 'origin', repo_url],
            cwd=temp_dir, check=True, capture_output=True
        )
        
        # 启用稀疏检出
        subprocess.run(
            ['git', 'config', 'core.sparseCheckout', 'true'],
            cwd=temp_dir, check=True, capture_output=True
        )
        
        # 配置要检出的路径
        sparse_checkout_file = os.path.join(temp_dir, '.git', 'info', 'sparse-checkout')
        os.makedirs(os.path.dirname(sparse_checkout_file), exist_ok=True)
        with open(sparse_checkout_file, 'w', encoding='utf-8') as f:
            f.write(f"{target_folder}/\n")
        
        print(f"拉取 {branch} 分支（仅包含 {target_folder} 目录）...")
        # 拉取指定分支
        subprocess.run(
            ['git', 'pull', 'origin', branch],
            cwd=temp_dir, check=True, capture_output=True
        )
        
        # 移动下载的目录到目标位置
        src = os.path.join(temp_dir, target_folder)
        dst = os.path.join(output_dir, target_folder)
        
        if os.path.exists(src):
            if os.path.exists(dst):
                print(f"目标目录 {target_folder} 已存在，删除旧目录...")
                shutil.rmtree(dst)
            
            shutil.move(src, dst)
            print(f"✓ 成功下载到 {dst}")
            return True
        else:
            print(f"✗ 下载失败：在仓库中找不到 {target_folder} 目录")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"✗ Git操作失败: {e}")
        return False
    finally:
        # 清理临时目录
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def download_with_github_cli(repo_url, branch, target_folder, output_dir):
    """使用GitHub CLI下载特定目录"""
    print(f"准备下载 {repo_url} 的 {target_folder} 分支...")
    
    try:
        print(f"使用 gh 克隆仓库...")
        temp_dir = os.path.join(output_dir, '.gh_temp')
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        
        # 使用gh克隆仓库
        repo_name = repo_url.split('/')[-1]
        repo_owner = repo_url.split('/')[-2]
        
        subprocess.run(
            ['gh', 'repo', 'clone', f'{repo_owner}/{repo_name}', temp_dir],
            check=True, capture_output=True
        )
        
        # 检出指定分支
        subprocess.run(
            ['git', 'checkout', branch],
            cwd=temp_dir, check=True, capture_output=True
        )
        
        # 移动下载的目录
        src = os.path.join(temp_dir, target_folder)
        dst = os.path.join(output_dir, target_folder)
        
        if os.path.exists(src):
            if os.path.exists(dst):
                print(f"目标目录 {target_folder} 已存在，删除旧目录...")
                shutil.rmtree(dst)
            
            shutil.move(src, dst)
            print(f"✓ 成功下载到 {dst}")
            return True
        else:
            print(f"✗ 下载失败：在仓库中找不到 {target_folder} 目录")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"✗ GitHub CLI操作失败: {e}")
        return False
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def main():
    """主函数"""
    print("=" * 60)
    print("GitHub TTS目录下载器")
    print("=" * 60)
    
    # 配置
    repo_url = "https://github.com/KysaInt/-"
    branch = "main"
    target_folder = "tts"
    
    # 获取当前脚本所在目录的父目录作为输出目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.dirname(script_dir)  # 上一级目录
    
    print(f"\n配置信息:")
    print(f"  仓库地址: {repo_url}")
    print(f"  分支: {branch}")
    print(f"  目录: {target_folder}")
    print(f"  输出目录: {output_dir}\n")
    
    # 检查Git是否安装
    if not check_git_installed():
        print("✗ 错误: 未检测到Git")
        print("\n请先安装Git:")
        print("  Windows: https://git-scm.com/download/win")
        print("  或使用包管理器: choco install git")
        sys.exit(1)
    
    print("✓ Git已安装")
    
    # 尝试用Git下载
    print("\n开始下载...\n")
    success = download_with_git(repo_url, branch, target_folder, output_dir)
    
    if success:
        print("\n" + "=" * 60)
        print("✓ 下载完成！")
        print("=" * 60)
        print(f"\n下载的目录位置: {os.path.join(output_dir, target_folder)}")
    else:
        print("\n" + "=" * 60)
        print("✗ 下载失败")
        print("=" * 60)
        sys.exit(1)


if __name__ == '__main__':
    main()
