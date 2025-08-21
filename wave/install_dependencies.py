# 音频切分工具依赖安装脚本
# 运行此脚本安装所需的依赖库

import subprocess
import sys

def install_requirements():
    """安装所需的依赖库"""
    requirements = [
        'pydub',
        'numpy'
    ]
    
    print("正在安装音频切分工具所需的依赖库...")
    print("需要安装的库:", requirements)
    
    for package in requirements:
        try:
            print(f"\n正在安装 {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            print(f"✓ {package} 安装成功")
        except subprocess.CalledProcessError as e:
            print(f"✗ {package} 安装失败: {e}")
            return False
    
    print("\n所有依赖库安装完成！")
    print("\n注意：如果要处理 MP3 文件，还需要安装 FFmpeg:")
    print("1. 从 https://ffmpeg.org/download.html 下载 FFmpeg")
    print("2. 将 FFmpeg 添加到系统 PATH 环境变量中")
    print("3. 或者将 ffmpeg.exe 放在程序同一目录下")
    
    return True

if __name__ == "__main__":
    success = install_requirements()
    if success:
        print("\n现在可以运行 '切分.py' 来启动音频切分工具！")
    else:
        print("\n依赖安装失败，请检查网络连接或手动安装依赖。")
    
    input("\n按回车键退出...")
