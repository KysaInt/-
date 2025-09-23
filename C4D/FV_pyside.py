# -*- coding: utf-8 -*-
"""
跨文件夹PNG序列查看管理器 (PySide6 版本)
递归扫描整个目录，自动识别序列名，统计渲染完整度
支持分组渲染的帧分布查看，忽略通道图只统计RGB主文件
"""

import os
import sys
import re
import subprocess
import importlib.util
from collections import defaultdict
import math
from datetime import datetime
import time
import threading
import json
from pathlib import Path
import shutil
import logging
import traceback

# Setup logging to a file at the very beginning
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'FV_pyside_debug.log')
# Use filemode='w' to overwrite the log on each run, making it easier to read
logging.basicConfig(filename=log_file, level=logging.DEBUG, 
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    filemode='w')

logging.info("Script execution started.")

# 尝试导入 PySide6 和其他必要的库
def check_and_install_packages():
    """检查并安装所需的包"""
    required_packages = {
        'PySide6': 'PySide6',
        'Pillow': 'Pillow',
        'psutil': 'psutil',
    }

    missing_packages = []
    for import_name, package_name in required_packages.items():
        if importlib.util.find_spec(import_name) is None:
            missing_packages.append(package_name)

    if missing_packages:
        print("检测到缺少以下依赖包:")
        for package in missing_packages:
            print(f"  - {package}")
        
        reply = input("是否现在自动安装这些包? (y/n): ").lower()
        if reply == 'y':
            for package in missing_packages:
                try:
                    print(f"正在安装 {package}...")
                    subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                    print(f"✓ {package} 安装成功")
                except subprocess.CalledProcessError as e:
                    print(f"✗ {package} 安装失败: {e}")
                    return False
            print("\n所有依赖包安装完成！")
            return True
        else:
            return False
    return True

if not check_and_install_packages():
    print("依赖安装失败或用户取消，程序退出。")
    sys.exit(1)

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QScrollArea, QFrame, QStackedWidget, QTextEdit,
    QMenuBar, QMessageBox, QSizePolicy, QDialog, QSpinBox, QColorDialog
)
from PySide6.QtGui import (
    QPixmap, QImage, QPainter, QColor, QFont, QAction, QIcon
)
from PySide6.QtCore import (
    Qt, QSize, QThread, Signal, QObject, QTimer
)
import psutil
from PIL import Image, ImageDraw, ImageQt

# --- 从 FV.pyw 迁移过来的非 UI 核心逻辑 ---

class C4DRenderMonitor:
    def __init__(self):
        self.c4d_process_names = [
            'CINEMA 4D.exe', 'Cinema 4D.exe', 'c4d.exe',
            'Commandline.exe', 'TeamRender Client.exe', 'TeamRender Server.exe'
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
                if any(c4d_name.lower() in process.info['name'].lower() for c4d_name in self.c4d_process_names):
                    c4d_processes.append({
                        'pid': process.info['pid'],
                        'name': process.info['name'],
                        'cpu_percent': process.info['cpu_percent'],
                        'memory': process.info['memory_info'].rss if process.info['memory_info'] else 0
                    })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
        
        self.cached_processes = c4d_processes
        self.last_check_time = current_time
        return c4d_processes
    
    def is_rendering_active(self, processes):
        if not processes: return False
        if any(p['cpu_percent'] > 20.0 for p in processes): return True
        if any('commandline' in p['name'].lower() for p in processes): return True
        if any('teamrender' in p['name'].lower() for p in processes): return True
        return False
    
    def check_render_queue_files(self):
        possible_files = [
            os.path.expanduser("~/AppData/Roaming/Maxon/render_queue.xml"),
            os.path.expanduser("~/AppData/Roaming/Maxon/queue.dat"),
        ]
        for file_path in possible_files:
            if os.path.exists(file_path) and (time.time() - os.path.getmtime(file_path) < 60):
                return True
        return False
    
    def check_render_status(self):
        processes = self.check_c4d_processes()
        queue_active = self.check_render_queue_files()
        process_rendering = self.is_rendering_active(processes)
        return process_rendering or queue_active

def format_seconds(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def generate_bar_chart_for_history(history_lines, for_log_file=False):
    if not history_lines: return []
    parsed_lines, valid_intervals = [], []
    for line in history_lines:
        timestamp_end = line.find(']') + 1 if line.startswith('[') and ']' in line else 0
        timestamp = line[:timestamp_end]
        line_to_parse = line[timestamp_end:].strip()
        
        end_quote_pos = line_to_parse.find('"', 1) if line_to_parse.startswith('"') else -1
        if end_quote_pos != -1:
            filename_part = line_to_parse[:end_quote_pos + 1]
            time_part = line_to_parse[end_quote_pos + 1:]
            interval, is_special = 0, False
            
            if any(s in time_part for s in ["[初始文件]", "[不完整渲染时长]", "[渲染暂停]", "[00:00:00]"]):
                is_special = True
            else:
                time_match = re.search(r'\[(\d{1,2}):(\d{1,2}):(\d{1,2})\]', time_part)
                if time_match:
                    h, m, s = map(int, time_match.groups())
                    interval = h * 3600 + m * 60 + s
                    if interval > 0: valid_intervals.append(interval)
            
            parsed_lines.append({'filename': filename_part, 'time': time_part, 'interval': interval, 'is_special': is_special, 'timestamp': timestamp})
        else:
            parsed_lines.append({'original_line': line})

    max_time = max(valid_intervals) if valid_intervals else 0
    max_filename_length = max((len(item['filename']) for item in parsed_lines if 'filename' in item), default=0)
    
    enhanced_lines = []
    bar_width = 20
    fill_char, empty_char = ('|', ' ') if for_log_file else ('█', ' ')
    
    for item in parsed_lines:
        if 'original_line' in item:
            enhanced_lines.append(item['original_line'])
        else:
            padding = " " * (max_filename_length - len(item['filename']))
            if item['is_special'] or item['interval'] == 0:
                bar = empty_char * bar_width
            else:
                ratio = item['interval'] / max_time if max_time > 0 else 0.0
                filled_length = int(bar_width * max(0.0, min(1.0, ratio)))
                bar = fill_char * filled_length + empty_char * (bar_width - filled_length)
            enhanced_lines.append(f"{item['timestamp']}{item['filename']}{padding}|{bar}|{item['time']}")
    return enhanced_lines

class MonitorWorker(QObject):
    finished = Signal()
    update_signal = Signal(str)

    def __init__(self, folder_path):
        super().__init__()
        self.folder_path = folder_path
        self.running = True
        self.stats = {
            'history': [],
            'render_monitor': C4DRenderMonitor(),
            'last_log_save': 0,
            'last_move_time': None,
            'moved_count': 0,
            'program_start': time.time(),
            'dot_count': 1,
            'max_interval': 0,
            'total_interval': 0,
            'total_render_time': 0,
            'last_render_check': time.time(),
            'is_first_run': True,
            'is_second_run': False,
            'was_rendering': False,
        }

    def run(self):
        while self.running:
            try:
                output = self.main_logic()
                self.update_signal.emit(output)
            except Exception as e:
                self.update_signal.emit(f"监控逻辑异常: {e}")
                logging.error("监控逻辑异常", exc_info=True)
            time.sleep(1)
        self.finished.emit()

    def stop(self):
        self.running = False

    def main_logic(self):
        stats = self.stats
        render_monitor = stats['render_monitor']
        
        is_rendering = render_monitor.check_render_status()
        current_time = time.time()
        if stats['was_rendering'] and is_rendering:
            stats['total_render_time'] += current_time - stats['last_render_check']
        stats['was_rendering'] = is_rendering
        stats['last_render_check'] = current_time

        base_dir = self.folder_path
        sequences = defaultdict(list)
        
        for filename in os.listdir(base_dir):
            if filename.lower().endswith('.png'):
                name, ext = os.path.splitext(filename)
                match = re.search(r'(.+?)\.(.+?)\.(\d{4})$', name) or re.search(r'(.+?)(\d{4})$', name)
                if match:
                    groups = match.groups()
                    basename = groups[0]
                    channel_suffix = groups[1] if len(groups) == 3 else None
                    num = groups[-1]
                    sequences[basename].append((filename, channel_suffix))

        moved_this_round = 0
        for seq, file_info_list in sequences.items():
            main_folder = os.path.join(base_dir, seq)
            os.makedirs(main_folder, exist_ok=True)
            stats['last_target_folder'] = main_folder
            
            for filename, channel_suffix in file_info_list:
                src = os.path.join(base_dir, filename)
                if not os.path.exists(src): continue

                target_folder = os.path.join(main_folder, channel_suffix or "RGB")
                os.makedirs(target_folder, exist_ok=True)
                dst = os.path.join(target_folder, filename)
                
                try:
                    shutil.move(src, dst)
                    now = time.time()
                    moved_this_round += 1
                    stats['moved_count'] += 1
                    
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    if stats['is_first_run']:
                        stats['history'].append(f"[{timestamp}] \"{filename}\"[初始文件]")
                    elif stats['is_second_run']:
                        stats['history'].append(f"[{timestamp}] \"{filename}\"[不完整渲染时长]")
                    else:
                        if stats['last_move_time'] and is_rendering:
                            interval = now - stats['last_move_time']
                            stats['total_interval'] += interval
                            stats['max_interval'] = max(stats['max_interval'], interval)
                            stats['history'].append(f"[{timestamp}] \"{filename}\"{format_seconds(interval)}")
                        else:
                            stats['history'].append(f"[{timestamp}] \"{filename}\"[{'渲染暂停' if not is_rendering else '00:00:00'}]")
                    
                    if is_rendering:
                        stats['last_move_time'] = now
                except Exception:
                    logging.error("文件移动异常", exc_info=True)
                    pass

        if stats['is_first_run'] and moved_this_round > 0:
            stats['is_first_run'] = False
            stats['is_second_run'] = True
        elif stats['is_second_run'] and moved_this_round > 0:
            stats['is_second_run'] = False

        total_time = time.time() - stats['program_start']
        effective_moved_count = stats['moved_count'] - (stats.get('first_run_moved', 0) + stats.get('second_run_moved', 0))
        avg_interval = stats['total_interval'] / effective_moved_count if effective_moved_count > 0 else 0
        dots = '.' * stats['dot_count'] + ' ' * (3 - stats['dot_count'])
        stats['dot_count'] = (stats['dot_count'] % 3) + 1
        
        render_indicator = "🔴渲染中" if is_rendering else "⚪暂停中"
        stat_line = f"数量: {stats['moved_count']} | 最长: {format_seconds(stats['max_interval'])} | 平均: {format_seconds(avg_interval)} | 总渲染时间: {format_seconds(stats['total_render_time'])} | 程序运行时间: {format_seconds(total_time)} | {render_indicator} {dots}"
        
        enhanced_history = generate_bar_chart_for_history(stats['history'])
        return '\n'.join(enhanced_history + [stat_line])

# --- PySide6 UI and Application Logic ---

class SequenceCard(QFrame):
    def __init__(self, name, data, parent=None):
        super().__init__(parent)
        self.name = name
        self.data = data
        self.setObjectName("SequenceCard")
        self.setFrameShape(QFrame.StyledPanel)

        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(4)
        self.layout.setContentsMargins(5, 5, 5, 5)

        title_text = f"{name} ({data.get('found_frames', 0)}/{data.get('total_frames', 0)})"
        self.title_label = QLabel(title_text)
        self.title_label.setObjectName("CardTitle")
        self.layout.addWidget(self.title_label)

        self.progress_bar = QLabel()
        self.progress_bar.setMinimumHeight(20)
        self.layout.addWidget(self.progress_bar)
        
        info_text = f"范围: {data.get('min_frame', 'N/A')} - {data.get('max_frame', 'N/A')}"
        self.info_label = QLabel(info_text)
        self.layout.addWidget(self.info_label)

        # Use a timer to ensure the widget has been sized before the first draw.
        QTimer.singleShot(50, self.update_visualization)

    def update_visualization(self):
        completion = self.data.get('completion', 0)
        
        # Use the progress_bar's width for the pixmap
        width = self.progress_bar.width()
        if width <= 1:
            # If the widget is not yet visible/sized, try again shortly.
            QTimer.singleShot(100, self.update_visualization)
            return
            
        height = 18
        pixmap = QPixmap(width, height)
        pixmap.fill(QColor("#404040"))
        
        painter = QPainter(pixmap)
        
        # Draw completion bar
        painter.setBrush(QColor("#6E9FD1"))
        painter.setPen(Qt.NoPen)
        painter.drawRect(0, 0, int(width * completion), height)
        
        # Draw missing frames gaps
        painter.setBrush(QColor("#A14E4E"))
        total_frames = self.data.get('total_frames')
        if total_frames and total_frames > 1:
            frame_ranges = self.data.get('frame_ranges', [])
            min_frame = self.data.get('min_frame', 0)
            
            last_end = min_frame - 1
            for start, end in frame_ranges:
                if start > last_end + 1:
                    # There is a gap
                    gap_start_frame = last_end + 1
                    gap_end_frame = start - 1
                    
                    start_pos = ((gap_start_frame - min_frame) / total_frames) * width
                    end_pos = ((gap_end_frame - min_frame) / total_frames) * width
                    
                    rect_width = max(1.0, end_pos - start_pos)
                    painter.drawRect(int(start_pos), 0, int(rect_width), height)
                last_end = end

        painter.end()
        
        self.progress_bar.setPixmap(pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Debounce resize updates to avoid excessive redraws
        if not hasattr(self, 'resize_timer'):
            self.resize_timer = QTimer()
            self.resize_timer.setSingleShot(True)
            self.resize_timer.timeout.connect(self.update_visualization)
        self.resize_timer.start(50)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_path = os.path.dirname(os.path.abspath(__file__))
        self.tree_data = {}
        self.auto_refresh_timer = QTimer(self)
        self.auto_refresh_timer.setInterval(5000)
        self.auto_refresh_timer.timeout.connect(self.scan_directory)
        
        self.monitor_thread = None
        self.monitor_worker = None

        self.init_ui()
        self.apply_stylesheet()
        self.scan_directory()
        
    def init_ui(self):
        self.setWindowTitle("文件查看管理器")
        self.setGeometry(100, 100, 900, 650)
        self.setMinimumSize(400, 300)

        self.create_menu()

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        self.stacked_widget = QStackedWidget()
        self.main_layout.addWidget(self.stacked_widget)

        # Panel 1: File Manager
        self.file_manager_panel = QWidget()
        self.setup_file_manager_panel(self.file_manager_panel)
        self.stacked_widget.addWidget(self.file_manager_panel)

        # Panel 2: Render Monitor
        self.monitor_panel = QWidget()
        self.setup_monitor_panel(self.monitor_panel)
        self.stacked_widget.addWidget(self.monitor_panel)

        self.stacked_widget.setCurrentWidget(self.monitor_panel)
        self.setWindowTitle("C4D 渲染监控")
        self.start_monitor_thread()

    def create_menu(self):
        menubar = self.menuBar()
        
        # File Menu
        file_menu = menubar.addMenu("文件")
        select_dir_action = QAction("选择目录", self)
        select_dir_action.triggered.connect(self.select_directory)
        file_menu.addAction(select_dir_action)

        refresh_action = QAction("刷新", self)
        refresh_action.triggered.connect(self.scan_directory)
        file_menu.addAction(refresh_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View Menu
        view_menu = menubar.addMenu("视图")
        self.auto_refresh_action = QAction("启用自动刷新 (5秒)", self, checkable=True)
        self.auto_refresh_action.triggered.connect(self.toggle_auto_refresh)
        view_menu.addAction(self.auto_refresh_action)

        # Panel Switch Action
        switch_panel_action = QAction("切换面板 (M)", self)
        switch_panel_action.setShortcut("M")
        switch_panel_action.triggered.connect(self.switch_panel)
        menubar.addAction(switch_panel_action)

    def setup_file_manager_panel(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Toolbar
        toolbar = QFrame()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        self.path_label = QLabel(f"当前目录: {self.current_path}")
        self.path_label.setWordWrap(True)
        select_button = QPushButton("选择...")
        select_button.clicked.connect(self.select_directory)
        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(self.scan_directory)
        toolbar_layout.addWidget(self.path_label, 1)
        toolbar_layout.addWidget(select_button)
        toolbar_layout.addWidget(refresh_button)
        layout.addWidget(toolbar)

        # Overall Stats
        self.stats_label = QLabel("总计: 0 序列, 0 文件")
        layout.addWidget(self.stats_label)

        # Scroll Area for cards
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_content = QWidget()
        self.card_layout = QVBoxLayout(self.scroll_content)
        self.card_layout.setSpacing(8)
        self.card_layout.addStretch() # Pushes cards to the top
        self.scroll_area.setWidget(self.scroll_content)
        layout.addWidget(self.scroll_area)

    def setup_monitor_panel(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(5, 5, 5, 5)
        
        title_label = QLabel("🎬 C4D 渲染监控")
        title_label.setObjectName("MonitorTitle")
        layout.addWidget(title_label)
        
        self.monitor_text_edit = QTextEdit()
        self.monitor_text_edit.setReadOnly(True)
        self.monitor_text_edit.setFont(QFont("Consolas", 9))
        layout.addWidget(self.monitor_text_edit)

    def switch_panel(self):
        current_index = self.stacked_widget.currentIndex()
        next_index = 1 - current_index
        self.stacked_widget.setCurrentIndex(next_index)
        
        if next_index == 0: # File Manager
            self.setWindowTitle("文件查看管理器")
            self.stop_monitor_thread()
        else: # Render Monitor
            self.setWindowTitle("C4D 渲染监控")
            self.start_monitor_thread()

    def start_monitor_thread(self):
        if self.monitor_thread is None:
            self.monitor_thread = QThread()
            self.monitor_worker = MonitorWorker(self.current_path)
            self.monitor_worker.moveToThread(self.monitor_thread)
            
            self.monitor_worker.update_signal.connect(self.update_monitor_text)
            self.monitor_thread.started.connect(self.monitor_worker.run)
            self.monitor_worker.finished.connect(self.monitor_thread.quit)
            self.monitor_worker.finished.connect(self.monitor_worker.deleteLater)
            self.monitor_thread.finished.connect(self.monitor_thread.deleteLater)
            
            self.monitor_thread.start()

    def stop_monitor_thread(self):
        if self.monitor_worker:
            self.monitor_worker.stop()
        if self.monitor_thread:
            self.monitor_thread.quit()
            self.monitor_thread.wait()
        self.monitor_thread = None
        self.monitor_worker = None

    def update_monitor_text(self, text):
        self.monitor_text_edit.setPlainText(text)
        self.monitor_text_edit.verticalScrollBar().setValue(self.monitor_text_edit.verticalScrollBar().maximum())

    def select_directory(self):
        path = QFileDialog.getExistingDirectory(self, "选择目录", self.current_path)
        if path:
            self.current_path = path
            self.path_label.setText(f"当前目录: {self.current_path}")
            self.scan_directory()

    def scan_directory(self):
        # Clear existing cards
        while self.card_layout.count() > 1: # Keep the stretch
            item = self.card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.tree_data = self.parse_directory(self.current_path)
        
        total_sequences = len(self.tree_data)
        total_files = sum(len(data['files']) for data in self.tree_data.values())
        self.stats_label.setText(f"总计: {total_sequences} 序列, {total_files} 文件")

        # Sort sequences by name for consistent order
        sorted_sequences = sorted(self.tree_data.items(), key=lambda item: item[0])

        for seq_name, data in sorted_sequences:
            card = SequenceCard(seq_name, data, self)
            self.card_layout.insertWidget(self.card_layout.count() - 1, card)

    def parse_directory(self, path):
        sequences = defaultdict(lambda: {
            'files': [], 
            'channels': defaultdict(list),
            'min_frame': None,
            'max_frame': None
        })
        
        # Regex to capture base name, frame number, and extension. Handles . and _ as separators.
        # Example: "MyRender_v01.1001.exr" -> ("MyRender_v01", "1001", ".exr")
        # Example: "MyRender.AO.1001.exr" -> ("MyRender.AO", "1001", ".exr")
        file_pattern = re.compile(r'(.+?)[._](\d+)\.(.+)', re.IGNORECASE)
        
        # Common channel names to help distinguish them from the main sequence name
        channel_suffixes = {
            'alpha', 'zdepth', 'normal', 'roughness', 'metallic', 'specular', 'emission', 'ao', 
            'displacement', 'bump', 'diffuse', 'reflection', 'refraction', 'effectsresult',
            'rgb', 'beauty', 'main'
        }

        for root, _, files in os.walk(path):
            for filename in files:
                match = file_pattern.match(filename)
                if not match:
                    continue

                base_name, frame_str, ext = match.groups()
                frame = int(frame_str)

                # Determine sequence name and channel
                parts = base_name.split('.')
                channel = "RGB" # Default channel
                seq_name = base_name

                if len(parts) > 1 and parts[-1].lower() in channel_suffixes:
                    channel = parts[-1]
                    seq_name = ".".join(parts[:-1])

                # Store file info
                sequences[seq_name]['files'].append({
                    'path': os.path.join(root, filename),
                    'frame': frame,
                    'channel': channel
                })
                
                # Update min/max frames for the main sequence
                if sequences[seq_name]['min_frame'] is None or frame < sequences[seq_name]['min_frame']:
                    sequences[seq_name]['min_frame'] = frame
                if sequences[seq_name]['max_frame'] is None or frame > sequences[seq_name]['max_frame']:
                    sequences[seq_name]['max_frame'] = frame


        # Post-process to calculate completion etc.
        for name, data in sequences.items():
            if not data['files']: continue
            
            # Use RGB channel for completion calculation if available, otherwise any channel
            rgb_frames = {f['frame'] for f in data['files'] if f['channel'].lower() in ('rgb', 'beauty', 'main')}
            if not rgb_frames:
                rgb_frames = {f['frame'] for f in data['files']} # Fallback

            if data['min_frame'] is not None and data['max_frame'] is not None:
                data['total_frames'] = data['max_frame'] - data['min_frame'] + 1
                data['found_frames'] = len(rgb_frames)
                data['completion'] = data['found_frames'] / data['total_frames'] if data['total_frames'] > 0 else 0
                data['frame_ranges'] = self.get_frame_ranges(sorted(list(rgb_frames)))
            else: # No frames found
                data['total_frames'] = 0
                data['found_frames'] = 0
                data['completion'] = 0
                data['frame_ranges'] = []

        return sequences

    def get_frame_ranges(self, frames):
        if not frames:
            return []
        ranges = []
        start_frame = frames[0]
        for i in range(1, len(frames)):
            if frames[i] != frames[i-1] + 1:
                ranges.append((start_frame, frames[i-1]))
                start_frame = frames[i]
        ranges.append((start_frame, frames[-1]))
        return ranges


    def toggle_auto_refresh(self):
        if self.auto_refresh_action.isChecked():
            self.auto_refresh_timer.start()
        else:
            self.auto_refresh_timer.stop()

    def apply_stylesheet(self):
        qss = """
            QMainWindow, QDialog {
                background-color: #2d2d2d;
            }
            QWidget {
                color: #cccccc;
                font-family: 'Segoe UI', 'Microsoft YaHei';
                font-size: 9pt;
            }
            QMenuBar {
                background-color: #3c3c3c;
                color: #cccccc;
            }
            QMenuBar::item:selected {
                background-color: #505050;
            }
            QMenu {
                background-color: #3c3c3c;
                border: 1px solid #505050;
            }
            QMenu::item:selected {
                background-color: #505050;
            }
            QPushButton {
                background-color: #505050;
                border: 1px solid #606060;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #606060;
            }
            QPushButton:pressed {
                background-color: #404040;
            }
            QLabel {
                color: #cccccc;
            }
            QLabel#MonitorTitle {
                font-size: 12pt;
                font-weight: bold;
                color: #ffffff;
            }
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                font-family: 'Consolas', 'Courier New', monospace;
            }
            QScrollArea {
                background-color: #252526;
                border: none;
            }
            QScrollBar:vertical {
                border: none;
                background: #252526;
                width: 10px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: #505050;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
            QFrame#SequenceCard {
                background-color: #3c3c3c;
                border: 1px solid #505050;
                border-radius: 4px;
                padding: 5px;
            }
            QLabel#CardTitle {
                font-weight: bold;
                font-size: 10pt;
            }
        """
        self.setStyleSheet(qss)

    def closeEvent(self, event):
        self.stop_monitor_thread()
        event.accept()

def main():
    logging.info("Main function entered.")
    # Add a global exception hook to catch unhandled errors
    def exception_hook(exctype, value, traceback_obj):
        # Log the full exception and traceback
        logging.error("Unhandled exception caught by hook.", exc_info=(exctype, value, traceback_obj))
        
        # Format the traceback for the message box
        tback_list = traceback.format_exception(exctype, value, traceback_obj)
        tback_str = "".join(tback_list)
        
        error_message = f"""<b>An unexpected error occurred:</b><br><br>
                          <b style='color:red;'>{exctype.__name__}: {value}</b><br><br>
                          <b>Traceback:</b><br>
                          <pre>{tback_str}</pre><br>
                          A detailed log has been created at:<br><i>{log_file}</i>"""

        try:
            # Ensure an application instance exists to show the message box
            app = QApplication.instance() or QApplication(sys.argv)
            
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle("Application Error")
            msg_box.setTextFormat(Qt.RichText)
            msg_box.setText(error_message)
            # Make the message box wider to show more info
            msg_box.setStyleSheet("QMessageBox { min-width: 700px; } pre { font-family: Consolas, Courier New; }")
            msg_box.exec()
        except Exception as e:
            logging.error(f"Failed to show exception dialog: {e}")
        finally:
            # The default hook prints to stderr, which is useful in console mode.
            sys.__excepthook__(exctype, value, traceback_obj)
            sys.exit(1)

    sys.excepthook = exception_hook

    logging.info("Starting QApplication.")
    app = QApplication(sys.argv)
    logging.info("Creating MainWindow.")
    window = MainWindow()
    logging.info("Showing MainWindow.")
    window.show()
    logging.info("Entering app.exec().")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
