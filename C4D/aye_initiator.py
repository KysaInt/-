# -*- coding: utf-8 -*-
"""
C4D脚本管理器按钮 - 下载并启动AYE
从GitHub下载FV2文件夹到工程目录并自动执行main.pyw
"""

import c4d
import os
import sys
import urllib.request
import zipfile
import io

def main():
    # 添加强制输出到C4D控制台的函数
    def c4d_print(msg):
        print(msg)
        try:
            # 尝试使用C4D的消息系统
            if hasattr(c4d, 'gui') and hasattr(c4d.gui, 'MessageDialog'):
                # 不使用对话框，因为会中断脚本流程
                pass
        except:
            pass

    c4d_print("=" * 60)
    c4d_print("AYE脚本启动 - 下载并执行AYE")
    c4d_print("=" * 60)

    try:
        # 检查C4D环境
        c4d_print("步骤1: 检查C4D环境...")
        if not hasattr(c4d, 'documents'):
            c4d_print("错误：这个脚本必须在C4D的脚本管理器中运行")
            return

        # 获取活动文档
        c4d_print("步骤2: 获取活动文档...")
        doc = c4d.documents.GetActiveDocument()
        if not doc:
            c4d_print("错误：请先打开C4D文档")
            return

        # 获取文档路径
        c4d_print("步骤3: 检查文档保存状态...")
        doc_path = doc.GetDocumentPath()
        if not doc_path:
            c4d_print("错误：请先保存文档")
            return
        c4d_print(f"文档路径：{doc_path}")

        # 创建目标路径
        c4d_print("步骤4: 准备目标路径...")
        # 目标是工程目录下的 "AYE" 文件夹
        target_folder = os.path.join(doc_path, "AYE")
        script_path = os.path.join(target_folder, "main.pyw")

        # 确保目标文件夹存在
        if not os.path.exists(target_folder):
            os.makedirs(target_folder)
            c4d_print(f"✓ 已创建文件夹: {target_folder}")

        c4d_print(f"目标文件夹路径: {target_folder}")

        # 下载并解压FV2文件夹
        c4d_print("步骤5: 下载并解压AYE文件夹...")
        download_success = False

        try:
            import socket
            import ssl

            # 设置超时和SSL上下文
            socket.setdefaulttimeout(60)
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            # GitHub仓库zip下载地址
            zip_url = "https://github.com/KysaInt/-/archive/refs/heads/main.zip"
            c4d_print(f"下载地址: {zip_url}")

            # 创建请求对象
            req = urllib.request.Request(zip_url)
            req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

            # 下载zip文件到内存
            with urllib.request.urlopen(req, context=ssl_context, timeout=120) as response:
                c4d_print("连接成功，正在下载...")
                zip_content = response.read()
                c4d_print(f"✓ 下载完成，大小: {len(zip_content) / 1024:.2f} KB")

            # 从内存中解压zip
            with zipfile.ZipFile(io.BytesIO(zip_content)) as z:
                c4d_print("正在解压AYE文件夹...")
                # 确定zip文件内的源文件夹路径
                # 通常是 <repo_name>-<branch_name>/path/to/folder
                source_folder_in_zip = "--main/QT/AYE/"
                
                files_to_extract = [f for f in z.namelist() if f.startswith(source_folder_in_zip) and not f.endswith('/')]
                if not files_to_extract:
                    c4d_print(f"✗ 在zip文件中找不到 {source_folder_in_zip} 文件夹")
                    return

                for file_path_in_zip in files_to_extract:
                    # 计算解压后的相对路径
                    relative_path = file_path_in_zip.replace(source_folder_in_zip, '', 1)
                    target_file_path = os.path.join(target_folder, relative_path)
                    
                    # 创建子目录
                    target_file_dir = os.path.dirname(target_file_path)
                    if not os.path.exists(target_file_dir):
                        os.makedirs(target_file_dir)
                        
                    # 提取文件
                    with z.open(file_path_in_zip) as source_file, open(target_file_path, 'wb') as target_file:
                        target_file.write(source_file.read())
                
                c4d_print(f"✓ 成功解压 {len(files_to_extract)} 个文件到 {target_folder}")

            # 验证主脚本文件是否存在
            if os.path.exists(script_path) and os.path.getsize(script_path) > 100:
                download_success = True
                c4d_print(f"✓ 成功获取AYE文件夹，主脚本: {script_path}")
            else:
                c4d_print("✗ 下载或解压后，主脚本文件无效或为空")

        except Exception as e:
            c4d_print(f"✗ 下载或解压失败: {e}")
            c4d_print("无法获取AYE文件夹，脚本终止")
            return

        if not download_success:
            c4d_print("无法获取AYE文件夹，脚本终止")
            return

        # 启动main.pyw脚本
        c4d_print("步骤6: 启动main.pyw脚本...")
        work_dir = target_folder # 工作目录是AYE文件夹

        try:
            import subprocess

            # 检查Python环境
            python_cmd = "python"
            try:
                result = subprocess.run(['python', '--version'],
                                      capture_output=True,
                                      text=True,
                                      timeout=5)
                if result.returncode != 0:
                    python_cmd = "py"
                    c4d_print("使用py命令")
                else:
                    c4d_print(f"Python版本: {result.stdout.strip()}")
            except:
                python_cmd = "py"
                c4d_print("使用py命令")

            # 验证main.pyw文件
            if not os.path.exists(script_path):
                c4d_print("✗ main.pyw文件不存在")
                return

            # 读取文件内容验证
            try:
                with open(script_path, 'r', encoding='utf-8') as f:
                    content = f.read(200)
                c4d_print("✓ main.pyw文件验证通过")
            except Exception as e:
                c4d_print(f"✗ main.pyw文件读取失败: {e}")
                return

            # 使用pythonw无窗口启动
            launch_success = False
            
            try:
                c4d_print("尝试使用 sys.executable 启动...")
                
                # 获取当前C4D环境的python解释器路径
                python_exe_path = sys.executable
                c4d_print(f"当前Python解释器: {python_exe_path}")

                # 构造pythonw.exe的路径
                pythonw_exe_path = python_exe_path.replace("python.exe", "pythonw.exe")
                if 'pythonw.exe' not in pythonw_exe_path:
                     # 如果是 py.exe 或其他情况，尝试直接用 pyw
                    pythonw_exe_path = "pyw"
                
                c4d_print(f"尝试使用: {pythonw_exe_path}")

                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                
                # 使用绝对路径启动
                process = subprocess.Popen(
                    [pythonw_exe_path, "main.pyw"],
                    shell=False,
                    cwd=work_dir,
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                launch_success = True
                c4d_print("✓ main.pyw脚本已启动（无窗口模式）")
            except Exception as e:
                c4d_print(f"启动失败: {e}")

            if not launch_success:
                c4d_print("所有启动方法都失败")
                c4d_print("请手动执行以下命令:")
                c4d_print(f'cd /d "{work_dir}"')
                c4d_print(f'py main.pyw')

        except Exception as e:
            c4d_print(f"启动过程出错: {e}")

        c4d_print("=" * 60)
        c4d_print("AYE脚本执行完成")
        c4d_print("=" * 60)

    except Exception as e:
        c4d_print(f"脚本执行出错: {e}")

if __name__ == '__main__':
    main()
