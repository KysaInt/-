import sys
import os
import shutil
import re
import time
import subprocess
import psutil
import json
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QTextEdit,
    QLabel, QPushButton, QHBoxLayout, QSizePolicy
)
from PySide6.QtCore import QThread, Signal, Qt, QTimer
from PySide6.QtGui import QTextCursor, QFontDatabase

class C4DRenderMonitor:
    def __init__(self):
        self.c4d_process_names = [
            'CINEMA 4D.exe',
            'Cinema 4D.exe', 
            'c4d.exe',
            'Commandline.exe',
            'TeamRender Client.exe',
            'TeamRender Server.exe'
        ]
        self.is_rendering = False
        self.last_render_status = -1
        self.last_check_time = 0
        self.cached_processes = []
        self.cache_duration = 0.5
        
    def check_c4d_processes(self):
        current_time = time.time()
        
        if current_time - self.last_check_time < self.cache_duration:
            return self.cached_processes
        
        c4d_processes = []
        
        try:
            for process in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
                process_name = process.info['name']
                if any(c4d_name.lower() in process_name.lower() for c4d_name in self.c4d_process_names):
                    c4d_processes.append({
                        'pid': process.info['pid'],
                        'name': process_name,
                        'cpu_percent': process.info['cpu_percent'],
                        'memory': process.info['memory_info'].rss if process.info['memory_info'] else 0
                    })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
        
        self.cached_processes = c4d_processes
        self.last_check_time = current_time
        
        return c4d_processes
    
    def is_rendering_active(self, processes):
        if not processes:
            return False
        
        high_cpu_processes = [p for p in processes if p['cpu_percent'] > 20.0]
        
        commandline_processes = [p for p in processes if 'commandline' in p['name'].lower()]
        
        teamrender_processes = [p for p in processes if 'teamrender' in p['name'].lower()]
        
        if commandline_processes or teamrender_processes:
            return True
        
        if high_cpu_processes:
            return True
        
        return False
    
    def check_render_queue_files(self):
        possible_files = [
            os.path.expanduser("~/AppData/Roaming/Maxon/render_queue.xml"),
            os.path.expanduser("~/AppData/Roaming/Maxon/queue.dat"),
            os.path.expanduser("~/Documents/Maxon/render_queue.xml"),
            "C:\\ProgramData\\Maxon\\render_queue.xml"
        ]
        
        for file_path in possible_files:
            try:
                if os.path.exists(file_path):
                    mtime = os.path.getmtime(file_path)
                    if time.time() - mtime < 60:
                        return True
            except Exception:
                continue
        
        return False
    
    def check_render_status(self):
        processes = self.check_c4d_processes()
        
        queue_active = self.check_render_queue_files()
        
        process_rendering = self.is_rendering_active(processes)
        current_rendering = process_rendering or queue_active
        
        return current_rendering

def format_seconds(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def open_last_folder(folder_path):
    try:
        subprocess.Popen(['explorer', folder_path])
    except Exception as e:
        print(f"打开文件夹失败: {e}")

def generate_bar_chart_for_history(history_lines, for_log_file=False):
    if not history_lines:
        return ""
        
    parsed_lines = []
    valid_intervals = []
    
    # 定义高亮颜色
    highlight_color = "#00A0E9"

    for line in history_lines:
        # 检查并分离时间戳
        timestamp_part = ""
        content_part = line
        if line.startswith('[') and ']' in line:
            end_bracket_pos = line.find(']')
            if end_bracket_pos != -1:
                timestamp_part = line[:end_bracket_pos + 2] # 包括]和后面的空格
                content_part = line[end_bracket_pos + 2:]

        if content_part.startswith('"') and '"' in content_part[1:]:
            end_quote_pos = content_part.find('"', 1)
            filename_part = content_part[:end_quote_pos + 1]
            time_part = content_part[end_quote_pos + 1:]
            
            interval = 0
            is_special = False
            
            if "[初始文件]" in time_part or "[不完整渲染时长]" in time_part or "[渲染暂停]" in time_part:
                is_special = True
            elif "[00:00:00]" in time_part:
                is_special = True
            else:
                time_match = re.search(r'\[(\d{1,2}):(\d{1,2}):(\d{1,2})\]', time_part)
                if time_match:
                    try:
                        h, m, s = map(int, time_match.groups())
                        interval = h * 3600 + m * 60 + s
                        if interval > 0:
                            valid_intervals.append(interval)
                    except:
                        pass
                else:
                    time_match = re.search(r'(\d{1,2}):(\d{1,2}):(\d{1,2})', time_part)
                    if time_match:
                        try:
                            h, m, s = map(int, time_match.groups())
                            interval = h * 3600 + m * 60 + s
                            if interval > 0:
                                valid_intervals.append(interval)
                        except:
                            pass
            
            parsed_lines.append({
                'timestamp': timestamp_part,
                'filename': filename_part,
                'time': time_part,
                'interval': interval,
                'is_special': is_special
            })
        else:
            # 对于非标准行，进行HTML转义以避免解析错误
            escaped_line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            parsed_lines.append({'original_line': escaped_line})
    
    if valid_intervals:
        max_time = max(valid_intervals)
    else:
        max_time = 0
    
    max_filename_length = 0
    for item in parsed_lines:
        if 'filename' in item:
            # HTML转义文件名中的特殊字符
            item['filename'] = item['filename'].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            max_filename_length = max(max_filename_length, len(item['filename']))
    
    enhanced_lines = []
    bar_width = 20
    
    fill_char = '█'
    empty_char = ' '
    
    for item in parsed_lines:
        if 'original_line' in item:
            enhanced_lines.append(item['original_line'])
        else:
            timestamp = item['timestamp']
            filename = item['filename']
            time_part = item['time']
            interval = item['interval']
            is_special = item['is_special']
            
            # HTML转义
            timestamp = timestamp.replace("<", "&lt;").replace(">", "&gt;")
            time_part = time_part.replace("<", "&lt;").replace(">", "&gt;")

            padding = "&nbsp;" * (max_filename_length - len(filename))
            
            if is_special or interval == 0:
                bar = empty_char * bar_width
            else:
                ratio = interval / max_time if max_time > 0 else 0.0
                ratio = max(0.0, min(1.0, ratio))
                filled_length = int(bar_width * ratio) if interval > 0 else 0
                bar = fill_char * filled_length + empty_char * (bar_width - filled_length)
            
            # 添加颜色
            colored_timestamp = f'<font color="{highlight_color}">{timestamp}</font>'
            colored_bar = f'<font color="{highlight_color}">{bar}</font>'
            
            enhanced_lines.append(f"{colored_timestamp}{filename}{padding}|{colored_bar}|{time_part}")
    
    return "<br>".join(enhanced_lines)

class Worker(QThread):
    update_signal = Signal(str, str)
    log_signal = Signal(str)

    def __init__(self, stats):
        super().__init__()
        self.stats = stats
        self.running = True
        # 常见的通道后缀
        self.channel_suffixes = [
            'alpha', 'zdepth', 'normal', 'roughness', 'metallic', 'specular',
            'emission', 'ao', 'displacement', 'bump', 'diffuse', 'reflection', 'refraction',
            'atmospheric_effects', 'background', 'bump_normals', 'caustics', 'coat',
            'coat_filter', 'coat_glossiness', 'coat_reflection', 'coverage', 'cryptomatte',
            'cryptomatte00', 'cryptomatte01', 'cryptomatte02', 'denoiser', 'dl1', 'dl2', 'dl3',
            'dr_bucket', 'environment', 'extra_tex', 'global_illumination', 'lighting',
            'material_id', 'material_select', 'matte_shadow', 'metalness', 'multi_matte',
            'multi_matte_id', 'normals', 'object_id', 'object_select', 'object_select_alpha',
            'object_select_filter', 'raw_coat_filter', 'raw_coat_reflection', 'raw_gi',
            'raw_lighting', 'raw_reflection', 'raw_refraction', 'raw_shadow', 'raw_sheen_filter',
            'raw_sheen_reflection', 'raw_total_light', 'reflection_filter', 'reflection_glossiness',
            'reflection_highlight_glossiness', 'reflection_ior', 'refraction_filter',
            'refraction_glossiness', 'render_id', 'sampler_info', 'sample_rate',
            'self_illumination', 'shadow', 'sheen', 'sheen_filter', 'sheen_glossiness',
            'sheen_reflection', 'sss', 'toon', 'toon_lighting', 'toon_specular',
            'total_light', 'velocity', 'effectsresult'
        ]

    def run(self):
        while self.running:
            try:
                self.main_logic()
                time.sleep(1)
            except Exception as e:
                self.log_signal.emit(f"Worker 线程异常: {e}")

    def stop(self):
        self.running = False
        self.wait()

    def main_logic(self):
        # 目标目录现在是脚本所在目录的上两级的'0'目录
        folder_path = str(Path(os.path.abspath(__file__)).parent.parent / '0')
        # 确保目标目录存在
        os.makedirs(folder_path, exist_ok=True)
        history = self.stats['history']
        render_monitor = self.stats['render_monitor']
        
        is_rendering = render_monitor.check_render_status()
        
        last_move_time = self.stats.get('last_move_time', None)
        moved_count = self.stats.get('moved_count', 0)
        program_start = self.stats.get('program_start', time.time())
        max_interval = self.stats.get('max_interval', 0)
        total_interval = self.stats.get('total_interval', 0)
        total_render_time = self.stats.get('total_render_time', 0)
        last_render_check = self.stats.get('last_render_check', time.time())
        is_first_run = self.stats.get('is_first_run', True)
        is_second_run = self.stats.get('is_second_run', False)
        moved_this_round = 0
        
        current_time = time.time()
        if self.stats.get('was_rendering', False) and is_rendering:
            total_render_time += current_time - last_render_check
        
        self.stats['was_rendering'] = is_rendering
        self.stats['last_render_check'] = current_time
        
        base_dir = folder_path
        sequences = {}
        
        for filename in os.listdir(base_dir):
            if filename.lower().endswith('.png'):
                name, ext = os.path.splitext(filename)
                
                basename, num, channel_suffix = None, None, None
                
                match = re.search(r'(.+?)\.(.+?)\.(\d{4})$', name)
                if match:
                    basename, channel_suffix, num = match.groups()
                else:
                    match = re.search(r'(.+?)(\d{4})$', name)
                    if match:
                        basename, num = match.groups()
                        channel_suffix = None
                    else:
                        continue
                
                if basename and num:
                    sequences.setdefault(basename, []).append((filename, channel_suffix))

        time.sleep(0.1)
        
        for seq, file_info_list in sequences.items():
            main_folder = os.path.join(base_dir, seq)
            os.makedirs(main_folder, exist_ok=True)
            
            self.stats['last_target_folder'] = main_folder
            
            for filename, channel_suffix in file_info_list:
                src = os.path.join(base_dir, filename)
                if not os.path.exists(src): continue

                dst_folder = main_folder
                if channel_suffix:
                    dst_folder = os.path.join(main_folder, channel_suffix)
                else:
                    dst_folder = os.path.join(main_folder, "RGB")
                
                os.makedirs(dst_folder, exist_ok=True)
                dst = os.path.join(dst_folder, filename)
                
                try:
                    shutil.move(src, dst)
                    
                    # 只对主RGB文件进行统计和记录
                    if not channel_suffix:
                        now = time.time()
                        timestamp_str = datetime.fromtimestamp(now).strftime('%H:%M:%S')
                        
                        if is_first_run:
                            history.append(f'[{timestamp_str}] "{filename}"[初始文件]')
                        elif is_second_run:
                            history.append(f'[{timestamp_str}] "{filename}"[不完整渲染时长]')
                        else:
                            if last_move_time and is_rendering:
                                interval = now - last_move_time
                                total_interval += interval
                                if interval > max_interval: max_interval = interval
                                history.append(f'[{timestamp_str}] "{filename}" {format_seconds(interval)}')
                            elif last_move_time and not is_rendering:
                                history.append(f'[{timestamp_str}] "{filename}" [渲染暂停]')
                            else:
                                history.append(f'[{timestamp_str}] "{filename}" [00:00:00]')
                        
                        moved_count += 1
                        moved_this_round += 1
                        if is_rendering: last_move_time = now

                except Exception as e:
                    self.log_signal.emit(f"移动文件失败: {e}")

        if moved_this_round > 0:
            timestamp = datetime.now().strftime('%H:%M:%S')
            self.log_signal.emit(f"[{timestamp}] 处理了 {moved_this_round} 个文件。")
            if is_first_run:
                is_first_run = False
                is_second_run = True
            elif is_second_run:
                is_second_run = False
            
        total_time = time.time() - program_start
        first_run_moved = self.stats.get('first_run_moved', 0)
        second_run_moved = self.stats.get('second_run_moved', 0)
        effective_moved_count = moved_count - first_run_moved - second_run_moved
        avg_interval = total_interval / effective_moved_count if effective_moved_count > 0 else 0
        
        render_indicator = "🔴渲染中" if is_rendering else "⚪暂停中"
        
        stat_line = f"数量: {moved_count} | 最长: {format_seconds(max_interval)} | 平均: {format_seconds(avg_interval)} | 总渲染: {format_seconds(total_render_time)} | 运行: {format_seconds(total_time)} | {render_indicator}"
        
        history_text = generate_bar_chart_for_history(history)

        self.update_signal.emit(history_text, stat_line)

        self.stats.update({
            'last_move_time': last_move_time, 'max_interval': max_interval, 'total_interval': total_interval,
            'total_render_time': total_render_time, 'moved_count': moved_count, 'is_first_run': is_first_run,
            'is_second_run': is_second_run, 'history': history
        })

class C4DMonitorWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.stats = {
            'history': [],
            'render_monitor': C4DRenderMonitor(),
            'program_start': time.time(),
            'should_exit': False
        }

        self.init_ui()
        self.start_worker()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.history_view = QTextEdit()
        self.history_view.setReadOnly(True)
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        self.history_view.setFont(font)
        layout.addWidget(self.history_view)

        self.status_label = QLabel("正在初始化...")
        self.status_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.status_label)

        button_layout = QHBoxLayout()
        self.open_folder_button = QPushButton("打开渲染目录")
        self.open_folder_button.clicked.connect(self.open_folder)
        button_layout.addWidget(self.open_folder_button)
        
        layout.addLayout(button_layout)

    def start_worker(self):
        self.worker = Worker(self.stats)
        self.worker.update_signal.connect(self.update_ui)
        self.worker.log_signal.connect(self.log_message)
        self.worker.start()

    def update_ui(self, history_text, status_text):
        self.history_view.setHtml(history_text)
        self.history_view.moveCursor(QTextCursor.MoveOperation.End)
        self.status_label.setText(status_text)

    def log_message(self, message):
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.history_view.append(f"[{timestamp}] {message}")
        self.history_view.moveCursor(QTextCursor.MoveOperation.End)

    def open_folder(self):
        last_folder = self.stats.get('last_target_folder')
        if last_folder and os.path.exists(last_folder):
            open_last_folder(last_folder)
        else:
            self.log_message("没有可打开的文件夹记录")

    def close_app(self):
        # If running standalone, this will close the app. If embedded, it does nothing.
        if self.parent() is None or isinstance(self.window(), QMainWindow):
             QApplication.instance().quit()
        else:
            # If embedded, maybe just stop the worker
            self.worker.stop()

    def closeEvent(self, event):
        self.worker.stop()
        # Here you would also save the final log, similar to the original script
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Create a main window to host the widget for standalone execution
    main_win = QMainWindow()
    monitor_widget = C4DMonitorWidget()
    main_win.setCentralWidget(monitor_widget)
    main_win.setWindowTitle("C4D 文件管理器 (独立运行)")
    main_win.setGeometry(100, 100, 800, 600)
    main_win.show()
    sys.exit(app.exec())
