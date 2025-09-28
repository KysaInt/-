import os
import time
import sys
from pathlib import Path

# 检查必要的库是否已安装
try:
    import win32com.client
except ImportError:
    print("检测到缺少必要的库：pywin32")
    print("正在尝试自动安装...")
    
    try:
        # 检查是否安装了pip
        import pip
    except ImportError:
        print("未检测到pip，无法自动安装依赖库。")
        print("请手动安装pywin32：pip install pywin32")
        input("按Enter键退出...")
        sys.exit(1)
        
    try:
        # 使用subprocess调用pip来安装pywin32
        import subprocess
        print("正在下载并安装pywin32库，请稍候...")
        print("这可能需要几分钟时间，取决于您的网络速度...")
        
        # 在Windows上，我们需要使用不同的方式调用pip
        if sys.platform.startswith('win'):
            import ctypes
            if ctypes.windll.shell32.IsUserAnAdmin() == 0:
                print("注意：您可能需要管理员权限来安装此库。")
                print("如果安装失败，请尝试以管理员身份运行此程序。")
            
        # 使用subprocess并等待安装完成
        process = subprocess.Popen(
            [sys.executable, "-m", "pip", "install", "--user", "pywin32"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        # 显示一些进度指示
        while process.poll() is None:
            print(".", end="", flush=True)
            time.sleep(1)
        
        stdout, stderr = process.communicate()
        
        # 检查安装是否成功
        if process.returncode == 0:
            print("\npywin32库安装成功！")
            print("为确保模块正确加载，程序将自动重启...")
            time.sleep(2)  # 给用户一些时间看到消息
            
            # 使用Python的内置机制重启程序
            python = sys.executable
            os.execl(python, python, *sys.argv)
        else:
            print(f"\n安装失败: {stderr}")
            raise Exception("安装过程返回错误")
    except Exception as e:
        print(f"自动安装失败：{e}")
        print("请手动安装pywin32：pip install pywin32")
        input("按Enter键退出...")
        sys.exit(1)

def list_available_voices():
    """列出系统中所有可用的语音"""
    try:
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        voices = speaker.GetVoices()
        
        print("可用的语音列表:")
        for i in range(voices.Count):
            voice = voices.Item(i)
            print(f"{i+1}. {voice.GetDescription()}")
        
        return voices
    except Exception as e:
        print(f"获取语音列表失败: {e}")
        return None

def select_voice():
    """让用户选择语音"""
    voices = list_available_voices()
    if not voices or voices.Count == 0:
        print("没有找到可用的语音，将使用默认语音。")
        return None
    
    try:
        choice = int(input("\n请选择语音序号 (输入0使用默认语音): "))
        if choice == 0:
            return None
        if 1 <= choice <= voices.Count:
            return voices.Item(choice-1)
        else:
            print("无效选择，将使用默认语音。")
            return None
    except ValueError:
        print("输入无效，将使用默认语音。")
        return None

def select_rate():
    """让用户选择语速"""
    try:
        rate = int(input("请选择语速 (-10最慢 到 10最快，0为正常速度): "))
        if -10 <= rate <= 10:
            return rate
        else:
            print("无效选择，将使用正常语速。")
            return 0
    except ValueError:
        print("输入无效，将使用正常语速。")
        return 0

def text_to_speech(text, output_file, selected_voice=None, rate=0):
    """
    使用Windows TTS API将文本转换为语音
    :param text: 需要转换的文本
    :param output_file: 输出的wav文件路径
    :param selected_voice: 选定的语音
    :param rate: 语速 (-10 到 10)，0为正常速度
    """
    try:
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        
        # 设置语音
        if selected_voice:
            speaker.Voice = selected_voice
        
        # 设置语速
        speaker.Rate = rate
        
        # 创建音频流
        stream = win32com.client.Dispatch("SAPI.SpFileStream")
        stream.Open(output_file, 3, False)
        speaker.AudioOutputStream = stream
        
        # 转换文本到语音
        speaker.Speak(text)
        stream.Close()
        
        print(f"语音文件已保存到: {output_file}")
        return True
    except Exception as e:
        print(f"转换失败: {e}")
        return False

def process_txt_files(selected_voice=None, rate=0):
    """处理当前目录下的所有txt文件"""
    current_dir = Path(__file__).parent
    txt_files = list(current_dir.glob("*.txt"))
    
    if not txt_files:
        print("当前目录下没有找到txt文件。")
        return
    
    print(f"找到{len(txt_files)}个txt文件，开始处理...")
    
    for txt_path in txt_files:
        # 创建同名的wav文件
        wav_path = txt_path.with_suffix(".wav")
        
        # 如果wav文件已存在，添加时间戳避免覆盖
        if wav_path.exists():
            timestamp = int(time.time())
            wav_path = txt_path.with_stem(f"{txt_path.stem}_{timestamp}").with_suffix(".wav")
        
        # 读取txt文件内容
        try:
            with open(txt_path, 'r', encoding='utf-8') as f:
                text_content = f.read().strip()
                
            if text_content:
                print(f"正在处理: {txt_path.name}")
                if text_to_speech(text_content, str(wav_path), selected_voice, rate):
                    print(f"成功将 {txt_path.name} 转换为 {wav_path.name}")
                else:
                    print(f"转换 {txt_path.name} 失败")
            else:
                print(f"文件 {txt_path.name} 内容为空，已跳过")
        except UnicodeDecodeError:
            # 尝试不同编码
            try:
                with open(txt_path, 'r', encoding='gbk') as f:
                    text_content = f.read().strip()
                
                if text_content:
                    print(f"正在处理: {txt_path.name} (GBK编码)")
                    if text_to_speech(text_content, str(wav_path), selected_voice, rate):
                        print(f"成功将 {txt_path.name} 转换为 {wav_path.name}")
                    else:
                        print(f"转换 {txt_path.name} 失败")
                else:
                    print(f"文件 {txt_path.name} 内容为空，已跳过")
            except Exception as e:
                print(f"无法读取文件 {txt_path.name}: {e}")

if __name__ == "__main__":
    print("=" * 50)
    print("Windows 文字转语音程序")
    print("=" * 50)
    print("该程序将同目录下的所有TXT文件转换为WAV语音文件")
    print("=" * 50)
    
    # 选择语音
    print("\n【1】选择语音:")
    selected_voice = select_voice()
    
    # 选择语速
    print("\n【2】选择语速:")
    rate = select_rate()
    
    print("\n【3】开始转换:")
    process_txt_files(selected_voice, rate)
    
    print("\n处理完成!")
    input("按Enter键退出...")