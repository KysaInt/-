# -*- coding: utf-8 -*-
"""
C4D脚本管理器按钮 - 下载并启动FV.pyw
从GitHub下载FV.pyw到工程目录的0/文件夹并自动执行
"""

import c4d
import os
import sys

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
    c4d_print("AYE脚本启动 - 下载并执行FV.pyw")
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
        target_folder = os.path.join(doc_path, "0")
        script_path = os.path.join(target_folder, "FV.pyw")

        # 确保目标文件夹存在
        if not os.path.exists(target_folder):
            os.makedirs(target_folder)
            c4d_print(f"✓ 已创建文件夹: {target_folder}")

        c4d_print(f"目标文件路径: {script_path}")

        # 下载FV.pyw文件
        c4d_print("步骤5: 下载FV.pyw文件...")
        download_success = False

        # 尝试下载
        try:
            import urllib.request
            import socket
            import ssl

            # 设置超时和SSL上下文
            socket.setdefaulttimeout(60)  # 增加等待时间到60秒
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            # 使用正确的GitHub raw URL
            url = "https://raw.githubusercontent.com/KysaInt/-/main/C4D/FV.pyw"
            c4d_print(f"下载地址: {url}")

            def show_progress(block_num, block_size, total_size):
                if total_size > 0:
                    downloaded = block_num * block_size
                    percent = min(100, downloaded * 100 // total_size)
                    if block_num % 5 == 0:
                        c4d_print(f"下载进度: {percent}%")

            # 创建请求对象
            req = urllib.request.Request(url)
            req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

            # 下载文件
            with urllib.request.urlopen(req, context=ssl_context, timeout=60) as response:  # 增加超时到60秒
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                block_size = 8192

                with open(script_path, 'wb') as f:
                    while True:
                        data = response.read(block_size)
                        if not data:
                            break
                        f.write(data)
                        downloaded += len(data)

                        if total_size > 0 and downloaded % (block_size * 5) == 0:
                            percent = min(100, downloaded * 100 // total_size)
                            c4d_print(f"下载进度: {percent}%")

            # 验证下载的文件
            if os.path.exists(script_path) and os.path.getsize(script_path) > 100:
                download_success = True
                c4d_print(f"✓ 成功下载FV.pyw文件: {script_path}")
                c4d_print(f"文件大小: {os.path.getsize(script_path)} 字节")
            else:
                c4d_print("✗ 下载的文件无效或为空")

        except Exception as e:
            c4d_print(f"✗ 下载失败: {e}")
            c4d_print("无法获取FV.pyw文件，脚本终止")
            return

        if not download_success:
            c4d_print("无法获取FV.pyw文件，脚本终止")
            return

        # 启动FV.pyw脚本
        c4d_print("步骤6: 启动FV.pyw脚本...")
        work_dir = os.path.dirname(script_path)

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

            # 验证FV.pyw文件
            if not os.path.exists(script_path):
                c4d_print("✗ FV.pyw文件不存在")
                return

            # 读取文件内容验证
            try:
                with open(script_path, 'r', encoding='utf-8') as f:
                    content = f.read(200)
                c4d_print("✓ FV.pyw文件验证通过")
            except Exception as e:
                c4d_print(f"✗ FV.pyw文件读取失败: {e}")
                return

            # 使用pythonw无窗口启动
            launch_success = False
            
            try:
                c4d_print("尝试启动...")
                # 使用pythonw来执行pyw文件
                pythonw_cmd = python_cmd.replace('python', 'pythonw')
                if not pythonw_cmd.endswith('w'):
                    pythonw_cmd += 'w'
                
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                
                process = subprocess.Popen(
                    [pythonw_cmd, "FV.pyw"],
                    shell=False,
                    cwd=work_dir,
                    startupinfo=startupinfo
                )
                launch_success = True
                c4d_print("✓ FV.pyw脚本已启动（无窗口模式）")
            except Exception as e:
                c4d_print(f"启动失败: {e}")

            if not launch_success:
                c4d_print("所有启动方法都失败")
                c4d_print("请手动执行以下命令:")
                c4d_print(f'cd /d "{work_dir}"')
                c4d_print(f'{python_cmd} FV.pyw')

        except Exception as e:
            c4d_print(f"启动过程出错: {e}")

        c4d_print("=" * 60)
        c4d_print("AYE脚本执行完成")
        c4d_print("=" * 60)

    except Exception as e:
        c4d_print(f"脚本执行出错: {e}")

if __name__ == '__main__':
    main()
