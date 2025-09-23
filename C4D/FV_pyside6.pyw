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
import ctypes
from datetime import datetime
import time
import threading
import json
from pathlib import Path

# 尝试导入 PySide6
try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QFrame, QScrollArea, QFileDialog, QMessageBox,
        QTextEdit, QMenuBar, QSizePolicy, QStackedWidget
    )
    from PySide6.QtGui import (
        QAction, QFont, QColor, QPainter, QPalette, QIcon, QTextCursor
    )
    from PySide6.QtCore import (
        Qt, QThread, Signal, QObject, QSize, QTimer
    )
except ImportError:
    print("错误：缺少 PySide6 模块。")
    print("请先安装 PySide6: pip install PySide6")
    sys.exit(1)


def check_and_install_packages():
    """检查并安装所需的包 (使用 PySide6 显示提示)"""
    required_packages = {
        'pywinstyles': 'pywinstyles',
        'PIL': 'Pillow',
        'psutil': 'psutil'
    }

    missing_packages = []
    for import_name, package_name in required_packages.items():
        if importlib.util.find_spec(import_name) is None:
            missing_packages.append(package_name)

    if missing_packages:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        packages_str = '\n'.join([f"  • {pkg}" for pkg in missing_packages])
        message = f"检测到缺少以下依赖包:\n\n{packages_str}\n\n是否现在自动安装这些包？"

        reply = QMessageBox.question(None, "缺少依赖包", message,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.Yes)

        if reply == QMessageBox.StandardButton.Yes:
            progress_dialog = QMessageBox(QMessageBox.Icon.Information, "安装依赖包", "正在安装，请稍候...", QMessageBox.StandardButton.NoButton)
            progress_dialog.setStandardButtons(QMessageBox.StandardButton.NoButton) # 隐藏按钮
            progress_dialog.show()
            QApplication.processEvents()

            success = True
            for package in missing_packages:
                try:
                    progress_dialog.setInformativeText(f"正在安装 {package}...")
                    QApplication.processEvents()
                    subprocess.check_call([sys.executable, "-m", "pip", "install", package],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except subprocess.CalledProcessError:
                    success = False
                    QMessageBox.critical(None, "安装失败", f"安装 {package} 失败！\n请检查网络连接或手动安装。")
                    break
            
            progress_dialog.close()

            if success:
                QMessageBox.information(None, "安装完成", "所有依赖包安装成功！\n程序将继续启动。")
                return True
            else:
                return False
        else:
            return False
    return True

# 执行依赖检查
if not check_and_install_packages():
    sys.exit(1)

# 导入其他模块
try:
    import pywinstyles
    import winreg
    from PIL import Image, ImageDraw
    import psutil
    import shutil
except ImportError as e:
    QMessageBox.critical(None, "导入错误", f"导入模块失败: {e}\n请确保所有依赖包都已正确安装。")
    sys.exit(1)


# --- 后端逻辑 (从 FV.pyw 移植) ---

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
                    c4d_processes.append(process.info)
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
        # ... (此部分逻辑不变)
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
    # ... (此部分逻辑不变)
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


def main_logic(stats):
    # ... (此部分逻辑基本不变, 除了移除 os.system('cls') 和 print)
    folder_path = os.path.dirname(os.path.abspath(__file__))
    if 'history' not in stats: stats['history'] = []
    if 'render_monitor' not in stats: stats['render_monitor'] = C4DRenderMonitor()
    
    history = stats['history']
    render_monitor = stats['render_monitor']
    
    try:
        is_rendering = render_monitor.check_render_status()
        
        last_move_time = stats.get('last_move_time', None)
        moved_count = stats.get('moved_count', 0)
        program_start = stats.get('program_start', time.time())
        dot_count = stats.get('dot_count', 1)
        max_interval = stats.get('max_interval', 0)
        total_interval = stats.get('total_interval', 0)
        total_render_time = stats.get('total_render_time', 0)
        last_render_check = stats.get('last_render_check', time.time())
        is_first_run = stats.get('is_first_run', True)
        is_second_run = stats.get('is_second_run', False)
        moved_this_round = 0
        
        current_time = time.time()
        if stats.get('was_rendering', False) and is_rendering:
            total_render_time += current_time - last_render_check
        
        stats['was_rendering'] = is_rendering
        stats['last_render_check'] = current_time
        
        base_dir = folder_path
        sequences = defaultdict(list)
        
        for filename in os.listdir(base_dir):
            if filename.lower().endswith('.png'):
                name, ext = os.path.splitext(filename)
                match = re.search(r'(.+?)\.(.+?)\.(\d{4})$', name) or re.search(r'(.+?)(\d{4})$', name)
                if not match: continue
                
                groups = match.groups()
                basename = groups[0]
                channel_suffix = groups[1] if len(groups) == 3 else None
                num = groups[-1]
                
                sequences[basename].append((filename, channel_suffix))

        time.sleep(0.1)
        
        for seq, file_info_list in sequences.items():
            main_folder = os.path.join(base_dir, seq)
            os.makedirs(main_folder, exist_ok=True)
            stats['last_target_folder'] = main_folder
            
            for filename, channel_suffix in file_info_list:
                src = os.path.join(base_dir, filename)
                if not os.path.exists(src): continue

                if channel_suffix:
                    target_folder = os.path.join(main_folder, channel_suffix)
                else:
                    target_folder = os.path.join(main_folder, "RGB")
                
                os.makedirs(target_folder, exist_ok=True)
                dst = os.path.join(target_folder, filename)
                
                try:
                    shutil.move(src, dst)
                    if not channel_suffix: # 只记录主图像
                        now = time.time()
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        if is_first_run:
                            history.append(f"[{timestamp}] \"{filename}\"[初始文件]")
                        elif is_second_run:
                            history.append(f"[{timestamp}] \"{filename}\"[不完整渲染时长]")
                        else:
                            if last_move_time and is_rendering:
                                interval = now - last_move_time
                                total_interval += interval
                                if interval > max_interval: max_interval = interval
                                history.append(f"[{timestamp}] \"{filename}\"{format_seconds(interval)}")
                            elif last_move_time and not is_rendering:
                                history.append(f"[{timestamp}] \"{filename}\"[渲染暂停]")
                            else:
                                history.append(f"[{timestamp}] \"{filename}\"[00:00:00]")
                        
                        moved_count += 1
                        moved_this_round += 1
                        if is_rendering: last_move_time = now
                except Exception:
                    pass

        if is_first_run and moved_this_round > 0:
            stats['first_run_moved'] = stats.get('first_run_moved', 0) + moved_this_round
            is_first_run = False
            is_second_run = True
        elif is_second_run and moved_this_round > 0:
            stats['second_run_moved'] = stats.get('second_run_moved', 0) + moved_this_round
            is_second_run = False
            
        total_time = time.time() - program_start
        first_run_moved = stats.get('first_run_moved', 0)
        second_run_moved = stats.get('second_run_moved', 0)
        effective_moved_count = moved_count - first_run_moved - second_run_moved
        avg_interval = total_interval / effective_moved_count if effective_moved_count > 0 else 0
        dots = '.' * dot_count + ' ' * (3 - dot_count)
        render_indicator = "🔴渲染中" if is_rendering else "⚪暂停中"
        
        stat_line = f"数量: {moved_count} | 最长: {format_seconds(max_interval)} | 平均: {format_seconds(avg_interval)} | 总渲染时间: {format_seconds(total_render_time)} | 程序运行时间: {format_seconds(total_time)} | {render_indicator} {dots}"
        
        enhanced_history = generate_bar_chart_for_history(history, for_log_file=False)
        output_lines = enhanced_history + [stat_line]
        
        # 更新状态
        stats.update({
            'last_move_time': last_move_time, 'max_interval': max_interval, 'total_interval': total_interval,
            'total_render_time': total_render_time, 'moved_count': moved_count, 'program_start': program_start,
            'dot_count': (dot_count + 1) % 4, 'is_first_run': is_first_run, 'is_second_run': is_second_run,
            'history': history
        })
        return '\n'.join(output_lines)
    except Exception as e:
        return f"main_logic发生异常: {e}"


# --- PySide6 UI ---

class MonitorWorker(QObject):
    """渲染监控工作线程"""
    output_ready = Signal(str)
    
    def __init__(self):
        super().__init__()
        self.running = False
        self.stats = {
            'last_move_time': None, 'moved_count': 0, 'program_start': time.time(), 
            'should_exit': False, 'render_monitor': C4DRenderMonitor()
        }

    def run(self):
        self.running = True
        while self.running:
            output = main_logic(self.stats)
            self.output_ready.emit(output)
            time.sleep(1)

    def stop(self):
        self.running = False

class FrameVizWidget(QWidget):
    """帧分布可视化小组件"""
    def __init__(self, frames, total_frames, color, parent=None):
        super().__init__(parent)
        self.frames = frames
        self.total_frames = total_frames
        self.color = QColor(color)
        self.setMinimumHeight(12)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        # 背景
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#333"))
        painter.drawRect(0, 0, width, height)
        
        if not self.frames or self.total_frames == 0:
            return
            
        # 绘制存在的帧
        painter.setBrush(self.color)
        for frame_num in self.frames:
            start_pos = (frame_num / self.total_frames) * width
            end_pos = ((frame_num + 1) / self.total_frames) * width
            rect_width = max(1, end_pos - start_pos)
            painter.drawRect(int(start_pos), 0, int(rect_width), height)

class SequenceCard(QFrame):
    """单个序列的卡片UI"""
    def __init__(self, seq_name, seq_data, parent=None):
        super().__init__(parent)
        self.seq_name = seq_name
        self.seq_data = seq_data
        
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("SequenceCard")
        self.setStyleSheet("""
            #SequenceCard {
                background-color: #2d2d2d;
                border-radius: 5px;
                border: 1px solid #404040;
            }
            #SequenceCard:hover {
                border: 1px solid #555;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        
        # 头部
        header_layout = QHBoxLayout()
        self.name_label = QLabel(f"<b>{self.seq_name}</b>")
        self.name_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        header_layout.addWidget(self.name_label)
        header_layout.addStretch()
        
        total_frames = seq_data.get('total_frames', 0)
        completed_frames = seq_data.get('completed_frames', 0)
        completion_rate = seq_data.get('completion_rate', 0)
        
        self.count_label = QLabel(f"{completed_frames} / {total_frames} 帧")
        self.percent_label = QLabel(f"<b>{completion_rate:.1f}%</b>")
        
        header_layout.addWidget(self.count_label)
        header_layout.addWidget(self.percent_label, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(header_layout)
        
        # 帧分布可视化
        if 'frames' in seq_data and total_frames > 0:
            color = "#00a0e9" # 蓝色
            viz_widget = FrameVizWidget(seq_data['frames'], total_frames, color)
            layout.addWidget(viz_widget)
            
        # 详细信息
        details_layout = QHBoxLayout()
        frame_range_str = f"范围: {seq_data.get('min_frame', 'N/A')} - {seq_data.get('max_frame', 'N/A')}"
        self.range_label = QLabel(frame_range_str)
        
        missing_count = seq_data.get('missing_count', 0)
        self.missing_label = QLabel(f"缺失: {missing_count}")
        
        details_layout.addWidget(self.range_label)
        details_layout.addStretch()
        details_layout.addWidget(self.missing_label)
        layout.addLayout(details_layout)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_path = os.path.dirname(os.path.abspath(__file__))
        self.tree_data = {}
        self.monitor_worker = None
        self.monitor_thread = None

        self.setup_ui()
        self.apply_theme()
        self.scan_directory()
        self.start_monitor_thread()

    def setup_ui(self):
        self.setWindowTitle("文件查看管理器")
        self.setGeometry(100, 100, 900, 650)
        
        self.create_menu()
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)
        
        # 面板1: 文件管理器
        fm_panel = QWidget()
        self.setup_file_manager_panel(fm_panel)
        self.stacked_widget.addWidget(fm_panel)
        
        # 面板2: 渲染监控
        monitor_panel = QWidget()
        self.setup_monitor_panel(monitor_panel)
        self.stacked_widget.addWidget(monitor_panel)
        
        self.stacked_widget.setCurrentIndex(1) # 默认显示监控面板
        self.setWindowTitle("C4D 渲染监控")

    def setup_file_manager_panel(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 工具栏
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0,0,0,0)
        self.path_label = QLabel(f"当前目录: {self.current_path}")
        self.path_label.setWordWrap(True)
        select_btn = QPushButton("选择...")
        select_btn.clicked.connect(self.select_directory)
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.scan_directory)
        toolbar_layout.addWidget(self.path_label, stretch=1)
        toolbar_layout.addWidget(select_btn)
        toolbar_layout.addWidget(refresh_btn)
        layout.addWidget(toolbar)
        
        # 滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("QScrollArea { border: none; background-color: #202020; }")
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_layout.setSpacing(6)
        scroll_area.setWidget(self.scroll_content)
        layout.addWidget(scroll_area)

    def setup_monitor_panel(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(5, 5, 5, 5)
        
        title_layout = QHBoxLayout()
        title_label = QLabel("🎬 C4D 渲染监控")
        title_label.setStyleSheet("font-size: 12pt; font-weight: bold;")
        switch_label = QLabel("按 M 键切换面板")
        switch_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        switch_label.setStyleSheet("color: #aaa;")
        title_layout.addWidget(title_label)
        title_layout.addWidget(switch_label)
        layout.addLayout(title_layout)
        
        self.monitor_text = QTextEdit()
        self.monitor_text.setReadOnly(True)
        self.monitor_text.setFont(QFont("Consolas", 9))
        self.monitor_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #404040;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.monitor_text)

    def create_menu(self):
        menubar = self.menuBar()
        
        file_menu = menubar.addMenu("文件")
        select_action = QAction("选择目录", self)
        select_action.triggered.connect(self.select_directory)
        refresh_action = QAction("刷新", self)
        refresh_action.triggered.connect(self.scan_directory)
        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(select_action)
        file_menu.addAction(refresh_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)
        
        view_menu = menubar.addMenu("视图")
        sort_name_action = QAction("按名称排序", self)
        sort_name_action.triggered.connect(lambda: self.sort_sequences("name"))
        sort_comp_action = QAction("按完成率排序", self)
        sort_comp_action.triggered.connect(lambda: self.sort_sequences("completion"))
        view_menu.addAction(sort_name_action)
        view_menu.addAction(sort_comp_action)

    def apply_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #252525;
                color: #e0e0e0;
            }
            QMenuBar {
                background-color: #2d2d2d;
            }
            QMenuBar::item:selected {
                background-color: #404040;
            }
            QMenu {
                background-color: #2d2d2d;
                border: 1px solid #404040;
            }
            QMenu::item:selected {
                background-color: #404040;
            }
            QPushButton {
                background-color: #3a3a3a;
                border: 1px solid #505050;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton:pressed {
                background-color: #5a5a5a;
            }
        """)
        try:
            pywinstyles.apply_style(self, "dark")
        except Exception:
            pass # pywinstyles may fail on some systems

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_M:
            self.switch_panel()
        else:
            super().keyPressEvent(event)

    def switch_panel(self):
        current_index = self.stacked_widget.currentIndex()
        next_index = 1 - current_index
        self.stacked_widget.setCurrentIndex(next_index)
        if next_index == 0:
            self.setWindowTitle("文件查看管理器")
        else:
            self.setWindowTitle("C4D 渲染监控")

    def start_monitor_thread(self):
        self.monitor_thread = QThread()
        self.monitor_worker = MonitorWorker()
        self.monitor_worker.moveToThread(self.monitor_thread)
        
        self.monitor_thread.started.connect(self.monitor_worker.run)
        self.monitor_worker.output_ready.connect(self.update_monitor_text)
        
        self.monitor_thread.start()

    def update_monitor_text(self, text):
        self.monitor_text.setPlainText(text)
        self.monitor_text.moveCursor(QTextCursor.MoveOperation.End)

    def select_directory(self):
        path = QFileDialog.getExistingDirectory(self, "选择目录", self.current_path)
        if path:
            self.current_path = path
            self.path_label.setText(f"当前目录: {self.current_path}")
            self.scan_directory()

    def scan_directory(self):
        self.tree_data = {}
        sequences = defaultdict(list)
        
        # 常见的通道后缀列表，用于识别和忽略通道文件
        channel_suffixes = [
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
        channel_suffixes_set = set(channel_suffixes)

        try:
            # 我们只扫描当前目录，不再递归扫描子目录，以匹配原版逻辑
            for filename in os.listdir(self.current_path):
                if not filename.lower().endswith(('.png', '.exr', '.tif')):
                    continue

                name, ext = os.path.splitext(filename)
                
                # 尝试匹配 'basename.channel.framenumber'
                match_channel = re.search(r'(.+?)\.([^.]+)\.(\d+)$', name)
                if match_channel:
                    basename, channel, frame_num_str = match_channel.groups()
                    # 如果点后面的部分是已知的通道名，则忽略此文件
                    if channel.lower() in channel_suffixes_set:
                        continue
                    # 否则，它可能是一个有效的序列名，如 'project.v1.0001'
                    seq_name = f"{basename}.{channel}"
                    frame_num = int(frame_num_str)
                    sequences[seq_name].append(frame_num)
                    continue

                # 尝试匹配 'basename.framenumber' 或 'basename_framenumber'
                match_main = re.search(r'(.+?)[._](\d+)$', name)
                if match_main:
                    seq_name, frame_num_str = match_main.groups()
                    frame_num = int(frame_num_str)
                    sequences[seq_name].append(frame_num)

        except Exception as e:
            QMessageBox.warning(self, "扫描错误", f"扫描目录时出错: {e}")
            return

        for name, frames_list in sequences.items():
            if not frames_list: continue
            
            frames = sorted(list(set(frames_list)))
            min_f, max_f = frames[0], frames[-1]
            total_frames = max_f - min_f + 1
            completed_frames = len(frames)
            
            self.tree_data[name] = {
                'name': name,
                'min_frame': min_f,
                'max_frame': max_f,
                'total_frames': total_frames,
                'completed_frames': completed_frames,
                'completion_rate': (completed_frames / total_frames) * 100 if total_frames > 0 else 0,
                'missing_count': total_frames - completed_frames,
                'frames': set(frames)
            }
        
        self.sort_sequences("name") # 默认按名称排序

    def sort_sequences(self, by):
        if by == "completion":
            sorted_items = sorted(self.tree_data.values(), key=lambda x: x['completion_rate'], reverse=True)
        else: # name
            sorted_items = sorted(self.tree_data.values(), key=lambda x: x['name'])
        
        self.display_sequences(sorted_items)

    def display_sequences(self, sorted_items):
        # 清空现有卡片
        while self.scroll_layout.count():
            child = self.scroll_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # 添加新卡片
        for item in sorted_items:
            card = SequenceCard(item['name'], item)
            self.scroll_layout.addWidget(card)

    def closeEvent(self, event):
        if self.monitor_worker:
            self.monitor_worker.stop()
        if self.monitor_thread:
            self.monitor_thread.quit()
            self.monitor_thread.wait()
        super().closeEvent(event)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
