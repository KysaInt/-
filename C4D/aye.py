# -*- coding: utf-8 -*-
"""
C4D脚本管理器按钮 - 启动mf.py (简单可靠版)
最简单但最可靠的启动方式，支持自动创建mf.py文件
"""

import c4d
import os



def main():
    try:
        # 检查是否在C4D环境中运行
        if not hasattr(c4d, 'documents'):
            print("错误：这个脚本必须在C4D的脚本管理器中运行")
            print("请确保：")
            print("1. 已打开Cinema 4D软件")
            print("2. 在C4D的脚本管理器中执行此脚本")
            print("3. 不要直接在Python环境中运行")
            return

        print("开始执行脚本...")
        # 获取文档
        doc = c4d.documents.GetActiveDocument()
        if not doc:
            print("错误：请先打开C4D文档")
            print("请确保：")
            print("1. 已创建或打开一个C4D文档")
            print("2. 文档窗口处于活动状态")
            return
        print("成功获取C4D文档")
        
        # 获取文档路径
        doc_path = doc.GetDocumentPath()
        if not doc_path:
            print("错误：请先保存文档")
            print("请执行以下步骤：")
            print("1. 点击'文件' > '保存'")
            print("2. 选择保存位置并确认")
            print("3. 然后再次运行此脚本")
            return
        print(f"文档路径：{doc_path}")
    except ImportError:
        print("错误：无法导入C4D模块")
        print("请确保在C4D的脚本管理器中运行此脚本")
        return
    except Exception as e:
        print(f"执行过程中发生错误：{str(e)}")
        print("请检查：")
        print("1. C4D软件是否正常运行")
        print("2. 是否有足够的系统权限")
        print("3. 系统资源是否充足")
        return
    # 目标路径
    target_folder = os.path.join(doc_path, "0")
    mf_path = os.path.join(target_folder, "mf.py")
    # 检查并下载文件
    if not os.path.exists(mf_path):
        try:
            # 创建0文件夹（如果不存在）
            if not os.path.exists(target_folder):
                os.makedirs(target_folder)
                print(f"已创建文件夹: {target_folder}")
            # 从GitHub下载mf.py，带进度条
            import urllib.request
            url = "https://raw.githubusercontent.com/KysaInt/-/main/C4D/mf.py"
            print(f"正在从GitHub下载mf.py: {url}")
            def show_progress(block_num, block_size, total_size):
                downloaded = block_num * block_size
                percent = min(100, downloaded * 100 // total_size) if total_size > 0 else 0
                bar_len = 30
                filled_len = int(bar_len * percent // 100)
                bar = '█' * filled_len + '-' * (bar_len - filled_len)
                print(f'\r[下载进度] |{bar}| {percent}% ', end='')
                if downloaded >= total_size:
                    print()
            urllib.request.urlretrieve(url, mf_path, show_progress)
            print(f"已自动下载mf.py文件: {mf_path}")
        except Exception as e:
            print(f"下载文件失败: {e}")
            return
    # 启动 - 使用更可靠的方式
    work_dir = os.path.dirname(mf_path)
    print(f"工作目录: {work_dir}")
    
    try:
        # 检查Python是否可用
        python_check = os.system('python --version')
        if python_check != 0:
            print("错误: 未找到Python，请确保Python已正确安装并添加到系统环境变量")
            return
            
        # 直接使用subprocess启动，不创建bat文件
        import subprocess
        
        try:
            # 使用Python直接启动mf.py，在新的命令行窗口中运行
            print("正在启动脚本...")
            
            # 构建启动命令 - 修复引号嵌套问题
            cmd = f'start "C4D监控" cmd /k "cd /d "{work_dir}" && python mf.py"'
            
            # 启动新窗口
            process = subprocess.Popen(cmd, 
                                    shell=True,
                                    cwd=work_dir)
            print("脚本已启动")
            print("监控程序正在新窗口中运行")
                
        except Exception as e:
            print(f"启动脚本失败: {e}")
            print("尝试备用启动方法...")
            
            # 备用方法1：简化命令
            try:
                simple_cmd = f'start cmd /k "cd /d "{work_dir}" && python mf.py"'
                os.system(simple_cmd)
                print("已使用备用方法1启动")
            except Exception as backup_error1:
                print(f"备用方法1失败: {backup_error1}")
                
                # 备用方法2：最简单的启动方式
                try:
                    os.chdir(work_dir)
                    os.system('start cmd /k python mf.py')
                    print("已使用备用方法2启动")
                except Exception as backup_error2:
                    print(f"所有启动方法都失败: {backup_error2}")
        
    except Exception as e:
        print(f"启动失败，错误信息: {e}")
        print("请检查以下几点：")
        print("1. Python是否正确安装")
        print("2. 是否有权限访问目标文件夹")
        print("3. 路径中是否包含特殊字符")

if __name__=='__main__':
    main()
