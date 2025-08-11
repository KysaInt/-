import sys
import time
import os
import json
from datetime import datetime

def check_and_install_dependencies():
    required_packages = ['keyboard', 'mouse', 'Pillow', 'pyautogui']
    for package in required_packages:
        try:
            if package == 'Pillow':
                from PIL import Image
            else:
                __import__(package)
        except ImportError:
            print(f"正在安装 {package}...")
            try:
                import subprocess
                subprocess.check_call(['pip', 'install', package])
                print(f"{package} 安装完成!")
            except Exception as e:
                print(f"安装 {package} 失败: {str(e)}")
                print("请手动执行: pip install keyboard mouse Pillow pyautogui")
                input("按回车键退出...")
                sys.exit(1)

print("正在检查必要的库...")
check_and_install_dependencies()

# 导入必要的库
try:
    import keyboard
    import mouse
    from PIL import ImageGrab
    import pyautogui
    print("所有必要的库已就绪!")
except ImportError as e:
    print(f"导入库失败: {str(e)}")
    input("按回车键退出...")
    sys.exit(1)

class OperationRecorder:
    def __init__(self):
        # 获取当前脚本所在目录
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        # 创建带时间戳的目录名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.record_dir = os.path.join(self.base_dir, f"记录_{timestamp}")
        self.screenshot_dir = os.path.join(self.record_dir, "截图")
        self.log_file = os.path.join(self.record_dir, "操作记录.json")
        self.records = []
        self.ensure_dirs()
        print(f"\n所有记录将保存在: {self.record_dir}")
        
    def ensure_dirs(self):
        """确保必要的目录存在"""
        os.makedirs(self.screenshot_dir, exist_ok=True)
    
    def on_keyboard(self, event):
        """记录键盘事件"""
        if event.event_type == 'down':
            record = {
                'type': 'keyboard',
                'key': event.name,
                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'),
                'timestamp': time.time()
            }
            self.records.append(record)
            print(f"键盘: {event.name}")
    
    def on_click(self, x, y, button, pressed):
        """记录鼠标点击事件并截图"""
        if not pressed:
            return
            
        timestamp = time.time()
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        try:
            # 获取屏幕尺寸
            screen_width, screen_height = pyautogui.size()
            print(f"屏幕尺寸: {screen_width}x{screen_height}")
            
            # 确保截图区域在屏幕范围内
            x1 = max(0, x - 50)
            y1 = max(0, y - 50)
            x2 = min(screen_width, x + 50)
            y2 = min(screen_height, y + 50)
            print(f"截图区域: ({x1}, {y1}) -> ({x2}, {y2})")
            
            # 使用pyautogui截图
            filename = f"click_{timestamp:.3f}.png"
            filepath = os.path.join(self.screenshot_dir, filename)
            
            # 先截取全屏，然后裁剪
            screenshot = pyautogui.screenshot()
            region = screenshot.crop((x1, y1, x2, y2))
            region.save(filepath)
            print(f"截图已保存: {filepath}")
            
            record = {
                'type': 'mouse',
                'button': str(button),
                'x': x,
                'y': y,
                'time': current_time,
                'timestamp': timestamp,
                'screenshot': filename,
                'region': [x1, y1, x2, y2]
            }
            self.records.append(record)
            print(f"鼠标: {button} at ({x}, {y}) - 已保存截图: {filename}")
        except Exception as e:
            print(f"截图失败，错误信息: {str(e)}")
            print(f"错误类型: {type(e).__name__}")
            
            record = {
                'type': 'mouse',
                'button': str(button),
                'x': x,
                'y': y,
                'time': current_time,
                'timestamp': timestamp,
                'error': str(e)
            }
            self.records.append(record)
            print(f"鼠标: {button} at ({x}, {y}) - 仅记录位置信息")
    
    def save_records(self):
        """保存记录到JSON文件"""
        with open(self.log_file, 'w', encoding='utf-8') as f:
            json.dump(self.records, f, ensure_ascii=False, indent=2)
    
    def analyze_records(self):
        """分析操作记录"""
        if not self.records:
            return
        
        # 统计各个按键的使用频率
        key_counts = {}
        mouse_clicks = {}
        intervals = []
        last_time = None
        
        for record in self.records:
            current_time = record['timestamp']
            if last_time is not None:
                intervals.append(current_time - last_time)
            last_time = current_time
            
            if record['type'] == 'keyboard':
                key = record['key']
                key_counts[key] = key_counts.get(key, 0) + 1
            else:  # mouse
                button = record['button']
                mouse_clicks[button] = mouse_clicks.get(button, 0) + 1
        
        # 输出统计结果
        print("\n===== 操作统计 =====")
        print("\n键盘按键频率:")
        for key, count in sorted(key_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"{key}: {count}次")
        
        print("\n鼠标点击统计:")
        for button, count in mouse_clicks.items():
            print(f"{button}: {count}次")
        
        if intervals:
            avg_interval = sum(intervals) / len(intervals)
            print(f"\n平均操作间隔: {avg_interval:.2f}秒")
    
    def start_recording(self):
        """开始记录"""
        print("\n开始记录...")
        print(f"截图保存位置: {self.screenshot_dir}")
        print(f"记录文件位置: {self.log_file}")
        print("\n请开始操作 (按Esc退出):")
        print("- 每次点击鼠标都会自动截图")
        print("- 每次按键都会被记录")
        
        # 修改键盘事件处理方法
        def on_key_event(e):
            if e.event_type == 'down':
                self.on_keyboard(e)
        
        # 定义鼠标事件处理函数
        def on_mouse_click():
            try:
                # 获取当前鼠标位置
                x, y = mouse.get_position()
                self.on_click(x, y, "left", True)  # 简化按钮处理
            except Exception as e:
                print(f"处理鼠标事件时出错: {str(e)}")

        # 定义右键点击处理函数
        def on_mouse_right_click():
            try:
                x, y = mouse.get_position()
                self.on_click(x, y, "right", True)
            except Exception as e:
                print(f"处理鼠标事件时出错: {str(e)}")
        
        # 监听键盘和鼠标事件
        keyboard.on_press(on_key_event)
        mouse.on_right_click(on_mouse_right_click)
        mouse.on_click(on_mouse_click)
        
        # 等待Esc键退出
        keyboard.wait('esc')
        
        # 停止监听
        keyboard.unhook_all()
        mouse.unhook_all()
        
        # 保存和分析记录
        self.save_records()
        self.analyze_records()
        print("\n记录已保存到 '操作记录.json'")

if __name__ == "__main__":
    try:
        recorder = OperationRecorder()
        print("\n========== 操作记录器 ==========")
        print("功能说明:")
        print("1. 记录所有键盘按键")
        print("2. 记录鼠标点击并自动截图")
        print("3. 自动保存操作记录和统计")
        print("\n记录说明:")
        print("- 截图大小: 点击位置周围 100x100 像素")
        print("- 截图位置:", recorder.screenshot_dir)
        print("- 记录文件:", recorder.log_file)
        print("\n操作说明:")
        print("- 按回车开始记录")
        print("- 按ESC结束记录")
        print("- 结束后自动生成统计报告")
        print("==============================")
        input("\n按回车键开始记录...")
        recorder.start_recording()
    except Exception as e:
        print(f"\n程序出错: {str(e)}")
        print("按回车键退出...")
        input()
        sys.exit(1)
