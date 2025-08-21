# 音频切分工具依赖安装脚本
# 运行此脚本安装所需的依赖库

import subprocess
import sys

def install_requirements():
    """安装所需的依赖库"""
    requirements = [
        'pydub',
        'numpy',
        'librosa',
        'mido'
    ]
    
    print("正在安装音频处理工具所需的依赖库...")
    print("包括音频切分和MIDI转换功能所需的库...")
    
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
        print("\n现在可以运行以下程序：")
        print("- '切分.py' 启动音频切分工具")
        print("- 'to midi.py' 启动音频转MIDI工具")
    else:
        print("\n依赖安装失败，请检查网络连接或手动安装依赖。")
    
    input("\n按回车键退出...")
