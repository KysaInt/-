# -*- coding: utf-8 -*-
"""
C4D脚本管理器按钮 - 下载并启动mf.py
从GitHub下载mf.py到工程目录的0/文件夹并自动执行
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
    c4d_print("AYE脚本启动 - 下载并执行mf.py")
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
        mf_path = os.path.join(target_folder, "mf.py")

        # 确保目标文件夹存在
        if not os.path.exists(target_folder):
            os.makedirs(target_folder)
            c4d_print(f"✓ 已创建文件夹: {target_folder}")

        c4d_print(f"目标文件路径: {mf_path}")

        # 下载mf.py文件
        c4d_print("步骤5: 下载mf.py文件...")
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
            url = "https://raw.githubusercontent.com/KysaInt/-/main/C4D/mf.py"
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

                with open(mf_path, 'wb') as f:
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
            if os.path.exists(mf_path) and os.path.getsize(mf_path) > 100:
                download_success = True
                c4d_print(f"✓ 成功下载mf.py文件: {mf_path}")
                c4d_print(f"文件大小: {os.path.getsize(mf_path)} 字节")
            else:
                c4d_print("✗ 下载的文件无效或为空")

        except Exception as e:
            c4d_print(f"✗ 下载失败: {e}")
            c4d_print("无法获取mf.py文件，脚本终止")
            return

        if not download_success:
            c4d_print("无法获取mf.py文件，脚本终止")
            return

        # 启动mf.py脚本
        c4d_print("步骤6: 启动mf.py脚本...")
        work_dir = os.path.dirname(mf_path)

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

            # 验证mf.py文件
            if not os.path.exists(mf_path):
                c4d_print("✗ mf.py文件不存在")
                return

            # 读取文件内容验证
            try:
                with open(mf_path, 'r', encoding='utf-8') as f:
                    content = f.read(200)
                c4d_print("✓ mf.py文件验证通过")
            except Exception as e:
                c4d_print(f"✗ mf.py文件读取失败: {e}")
                return

            # 多种启动方式
            launch_success = False

            # 方法1: 直接启动
            if not launch_success:
                try:
                    c4d_print("尝试方法1: 直接启动...")
                    cmd = f'start "MF监控脚本" cmd /k "cd /d "{work_dir}" && {python_cmd} mf.py"'
                    os.system(cmd)
                    launch_success = True
                    c4d_print("✓ mf.py脚本已启动")
                except Exception as e:
                    c4d_print(f"方法1失败: {e}")

            # 方法2: 使用subprocess
            if not launch_success:
                try:
                    c4d_print("尝试方法2: subprocess启动...")
                    process = subprocess.Popen(
                        ['cmd', '/c', 'start', '"MF监控脚本"', 'cmd', '/k',
                         f'cd /d "{work_dir}" && {python_cmd} mf.py'],
                        shell=True,
                        cwd=work_dir
                    )
                    launch_success = True
                    c4d_print("✓ mf.py脚本已启动")
                except Exception as e:
                    c4d_print(f"方法2失败: {e}")

            if not launch_success:
                c4d_print("所有启动方法都失败")
                c4d_print("请手动执行以下命令:")
                c4d_print(f'cd /d "{work_dir}"')
                c4d_print(f'{python_cmd} mf.py')

        except Exception as e:
            c4d_print(f"启动过程出错: {e}")

        c4d_print("=" * 60)
        c4d_print("AYE脚本执行完成")
        c4d_print("=" * 60)

    except Exception as e:
        c4d_print(f"脚本执行出错: {e}")

if __name__ == '__main__':
    main()
