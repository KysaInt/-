import sys
import os
import shutil
import re
import time
import subprocess
import json
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QTextEdit,
    QLabel, QPushButton, QHBoxLayout, QSizePolicy, QLineEdit, QSpinBox, QSlider, QGridLayout, QFrame, QMenu, QMessageBox, QSplitter
)
from PySide6.QtCore import QThread, Signal, Qt, QTimer, QPropertyAnimation, QEasingCurve, QEvent, QSettings
from PySide6.QtGui import QTextCursor, QFontDatabase, QPalette, QAction, QPixmap


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

def generate_bar_chart_for_history(
    history_lines,
    for_log_file: bool = False,
    color: str | None = None,
    *,
    bar_width: int = 25,
    fill_char: str = '█',
    empty_char: str = '█',  # 使用相同字符由颜色区分
    global_scale: float = 1.0
):
    if not history_lines:
        return []
        
    parsed_lines = []
    valid_intervals = []
    
    # First pass: parse and find max values
    for line in history_lines:
        timestamp_part = ""
        content_part = line
        if line.startswith('[') and ']' in line:
            end_bracket_pos = line.find(']')
            if end_bracket_pos != -1:
                timestamp_part = line[:end_bracket_pos + 2]
                content_part = line[end_bracket_pos + 2:]

        if content_part.startswith('"') and '"' in content_part[1:]:
            end_quote_pos = content_part.find('"', 1)
            filename_part = content_part[:end_quote_pos + 1]
            time_part = content_part[end_quote_pos + 1:]
            
            interval = 0
            is_special = "[初始文件]" in time_part or "[不完整渲染时长]" in time_part or "[渲染暂停]" in time_part or "[00:00:00]" in time_part

            if not is_special:
                time_match = re.search(r'\[(\d{1,2}):(\d{1,2}):(\d{1,2})\]', time_part) or \
                             re.search(r'(\d{1,2}):(\d{1,2}):(\d{1,2})', time_part)
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
            parsed_lines.append({'original_line': line})
    
    max_time = max(valid_intervals) if valid_intervals else 1
    min_time = min(valid_intervals) if valid_intervals else 0
    range_time = max_time - min_time if valid_intervals and max_time > min_time else 1
    
    max_filename_length = 0
    for item in parsed_lines:
        if 'filename' in item:
            max_filename_length = max(max_filename_length, len(item['filename']))
    bar_width = max(1, bar_width)
    enhanced_lines = []
    
    # fill_char 与 empty_char 通过参数传入
    empty_color = '#555555' # Dark gray for the empty part of the bar
    
    for item in parsed_lines:
        if 'original_line' in item:
            enhanced_lines.append(item['original_line'])
            continue

        timestamp = item['timestamp']
        # Escape HTML characters for safety
        filename_html = item['filename'].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        time_part = item['time']
        interval = item['interval']
        is_special = item['is_special']
        
        # Bar generation
        bar_html = ""
        if is_special or interval == 0:
            if not for_log_file:
                bar_html = f'<span style="color: {empty_color};">{empty_char * bar_width}</span>'
            else:
                bar_html = ' ' * bar_width # Use spaces for plain text log
        else:
            base = max_time if max_time > 0 else 1
            scaled_interval = interval * (global_scale if global_scale > 0 else 1.0)
            ratio = scaled_interval / base
            raw = bar_width * ratio
            # 使用向下取整(允许显示为0长度)，保证比例真实；极小值不被强制放大
            filled_length = int(raw)
            # 若存在非零间隔但比例太小导致长度为0，为保证可见性，至少显示1格
            if interval > 0 and filled_length == 0:
                filled_length = 1
            filled_length = max(0, min(filled_length, bar_width))
            empty_length = bar_width - filled_length
            
            if not for_log_file:
                filled_part = ""
                if filled_length > 0:
                    filled_part = f'<span style="color: {color};">{fill_char * filled_length}</span>'

                empty_part = ""
                if empty_length > 0:
                    empty_part = f'<span style="color: {empty_color};">{empty_char * empty_length}</span>'

                bar_html = f"{filled_part}{empty_part}"
            else:
                bar_html = (fill_char * filled_length) + (' ' * empty_length)

        # Calculate padding
        # 使用 item['filename'] 的原始长度来计算填充
        padding_len = max(0, max_filename_length - len(item['filename']))
        
        if for_log_file:
            padding = " " * padding_len
            line_content = f"{item['filename']}{padding}|{bar_html}| {time_part}"
            enhanced_lines.append(f"{timestamp}{line_content}")
        else:
            # For rich text (HTML) in PySide
            padding = "&nbsp;" * padding_len
            
            # Color is now part of bar_html
            if color:
                colored_timestamp = f'<span style="color: {color};">{timestamp}</span>'
                line_content = f"{filename_html}{padding}|{bar_html}| {time_part}"
                enhanced_lines.append(f"{colored_timestamp}{line_content}")
            else:
                line_content = f"{filename_html}{padding}|{bar_html}| {time_part}"
                enhanced_lines.append(f"{timestamp}{line_content}")

    return enhanced_lines

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
        last_move_time = self.stats.get('last_move_time', None)
        moved_count = self.stats.get('moved_count', 0)
        program_start = self.stats.get('program_start', time.time())
        max_interval = self.stats.get('max_interval', 0)
        total_interval = self.stats.get('total_interval', 0)
        is_first_run = self.stats.get('is_first_run', True)
        is_second_run = self.stats.get('is_second_run', False)
        moved_this_round = 0
        current_time = time.time()
        
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
                        # 记录最新移动的主图像文件路径，用于预览
                        self.stats['last_moved_image'] = dst
                        now = time.time()
                        timestamp_str = datetime.fromtimestamp(now).strftime('%H:%M:%S')
                        
                        if is_first_run:
                            history.append(f'[{timestamp_str}] "{filename}"[初始文件]')
                        elif is_second_run:
                            history.append(f'[{timestamp_str}] "{filename}"[不完整渲染时长]')
                        else:
                            if last_move_time:
                                interval = now - last_move_time
                                total_interval += interval
                                if interval > max_interval: max_interval = interval
                                history.append(f'[{timestamp_str}] "{filename}" {format_seconds(interval)}')
                            else:
                                history.append(f'[{timestamp_str}] "{filename}" [00:00:00]')
                        
                        moved_count += 1
                        moved_this_round += 1
                        last_move_time = now

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

        stat_line = f"数量: {moved_count} | 最长: {format_seconds(max_interval)} | 平均: {format_seconds(avg_interval)} | 运行: {format_seconds(total_time)}"

        highlight_color = self.stats.get('highlight_color', '#FFFFFF')
        fill_char = self.stats.get('fill_char', '█')
        bar_width = self.stats.get('bar_width', 25)
        global_scale = self.stats.get('global_scale', 1.0)
        history_text = "\n".join(generate_bar_chart_for_history(
            history,
            color=highlight_color,
            bar_width=bar_width,
            fill_char=fill_char,
            empty_char=fill_char,
            global_scale=global_scale
        ))

        self.update_signal.emit(history_text, stat_line)

        self.stats.update({
            'last_move_time': last_move_time, 'max_interval': max_interval, 'total_interval': total_interval,
            'moved_count': moved_count, 'is_first_run': is_first_run,
            'is_second_run': is_second_run, 'history': history
        })

class C4DMonitorWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.stats = {
            'history': [],
            'program_start': time.time(),
            'should_exit': False
        }
        # 日志相关变量
        self.log_file_path = Path(os.path.abspath(__file__)).with_name('render_history.log')
        self._loaded_history_count = 0  # 已载入的历史行数量

        # 设置持久化存储
        self.settings = QSettings('AYE', 'C4DMonitor')

        # 周期性保存日志（防止异常退出丢失）
        self._periodic_save_timer = QTimer(self)
        self._periodic_save_timer.timeout.connect(self.save_history)
        self._periodic_save_timer.start(30000)  # 30 秒保存一次

        self.init_ui()
        # 需要在 init_ui 之后才有 highlight_color，所以此处再加载历史
        self.load_history()
        self.start_worker()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(2)  # 设置较小的间距，让折叠框更紧凑
        # ---- 固定文本行 + 右侧按钮（同一行） ----
        header_layout = QHBoxLayout()
        self.fixed_line_label = QLabel("正在初始化...")
        self.fixed_line_label.setObjectName("fixedLineLabel")
        self.fixed_line_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        header_layout.addWidget(self.fixed_line_label, 1)
        self.open_folder_button = QPushButton("打开")
        self.open_folder_button.setToolTip("打开最近目标渲染目录")
        self.open_folder_button.clicked.connect(self.open_folder)
        self.open_folder_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        header_layout.addWidget(self.open_folder_button)
        layout.addLayout(header_layout)

        # ---- 设置折叠框 ----
        # 需要先创建 history_view 供设置面板读取字体大小，但暂不添加到布局
        self.history_view = QTextEdit()
        self.history_view.setReadOnly(True)
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        self.history_view.setFont(font)
        # 主题高亮色作为条形颜色
        highlight_color = self._ensure_visible_color(
            self.palette().color(QPalette.ColorRole.Highlight).name()
        )
        self.stats['highlight_color'] = highlight_color
        # Ctrl+滚轮缩放字号
        self.history_view.wheelEvent = self.history_view_wheel_event
        # 设置右键菜单策略
        self.history_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.history_view.customContextMenuRequested.connect(self._show_context_menu)

        self._init_settings_panel(layout)

        # ---- 预览折叠框（位于设置栏下方）使用可调整大小的容器 ----
        self.preview_box = ResizableCollapsibleBox("预览", self.settings)
        # 设置预览框的 content_area 为透明背景
        self.preview_box.content_area.setStyleSheet("QFrame { background-color: transparent; border: none; }")
        preview_layout = QVBoxLayout()
        preview_layout.setContentsMargins(6, 6, 6, 6)
        preview_layout.setAlignment(Qt.AlignTop)
        self.preview_label = QLabel("无预览")
        self.preview_label.setAlignment(Qt.AlignCenter | Qt.AlignTop)
        self.preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.preview_label.setMinimumHeight(100)
        self.preview_label.setObjectName("previewLabel")
        # 设置透明背景
        self.preview_label.setStyleSheet("QLabel#previewLabel { background-color: transparent; }")
        preview_layout.addWidget(self.preview_label)
        self.preview_box.setContentLayout(preview_layout)
        self.preview_box.expanded.connect(self._force_update_preview)
        layout.addWidget(self.preview_box)

        # 预览内部状态
        self._last_preview_path = None
        self._original_preview_pixmap = None
        # 监听 label 尺寸变化以保持等比缩放
        self.preview_label.installEventFilter(self)

        # ---- 主文本窗口置于最底部并可伸展 ----
        self.history_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.history_view, 1)

        # 自动滚动相关状态（放在创建后）
        self.auto_scroll_enabled = True
        self._suppress_scroll_signal = False
        self._auto_scroll_reenable_timer = QTimer(self)
        self._auto_scroll_reenable_timer.setSingleShot(True)
        self._auto_scroll_reenable_timer.timeout.connect(self._reenable_auto_scroll)
        self.history_view.verticalScrollBar().valueChanged.connect(self._on_user_scroll)

    def eventFilter(self, obj, event):
        if obj is self.preview_label and event.type() == QEvent.Resize:
            self._apply_scaled_preview()
        return super().eventFilter(obj, event)

    # ---------------- 设置面板实现 ----------------
    def _init_settings_panel(self, parent_layout: QVBoxLayout):
        self.settings_box = CollapsibleBox("设置")
        grid = QGridLayout()
        grid.setContentsMargins(6, 6, 6, 6)
        row = 0
        # 单一字符（用于填充和空白，通过颜色区分）
        grid.addWidget(QLabel("条形字符:"), row, 0)
        self.fill_char_edit = QLineEdit('█')
        self.fill_char_edit.setMaxLength(2)
        grid.addWidget(self.fill_char_edit, row, 1)
        row += 1

        # 总宽度
        grid.addWidget(QLabel("总宽度:"), row, 0)
        self.bar_width_spin = QSpinBox()
        self.bar_width_spin.setRange(5, 200)
        self.bar_width_spin.setValue(25)
        grid.addWidget(self.bar_width_spin, row, 1)
        row += 1

        # 全局缩放
        grid.addWidget(QLabel("全局缩放:"), row, 0)
        self.scale_slider = QSlider(Qt.Horizontal)
        self.scale_slider.setRange(10, 300)  # 表示 0.1 - 3.0
        self.scale_slider.setValue(100)
        grid.addWidget(self.scale_slider, row, 1)
        self.scale_label = QLabel("1.0x")
        grid.addWidget(self.scale_label, row, 2)
        row += 1

        # 字号缩放（影响 QTextEdit 字体）
        grid.addWidget(QLabel("文字缩放:"), row, 0)
        self.font_scale_slider = QSlider(Qt.Horizontal)
        self.font_scale_slider.setRange(5, 40)
        # 记当前字号
        self._base_font_point_size = self.history_view.font().pointSize()
        self.font_scale_slider.setValue(self._base_font_point_size)
        grid.addWidget(self.font_scale_slider, row, 1)
        self.font_scale_label = QLabel(str(self._base_font_point_size))
        grid.addWidget(self.font_scale_label, row, 2)
        row += 1


        self.settings_box.setContentLayout(grid)
        parent_layout.addWidget(self.settings_box)

        # 初始写入 stats
        self.stats['fill_char'] = (self.fill_char_edit.text() or '█')[0]
        self.stats['bar_width'] = self.bar_width_spin.value()
        self.stats['global_scale'] = self.scale_slider.value() / 100.0

        # 信号连接
        self.fill_char_edit.textChanged.connect(self._settings_changed)
        self.bar_width_spin.valueChanged.connect(self._settings_changed)
        self.scale_slider.valueChanged.connect(self._scale_changed)
        self.font_scale_slider.valueChanged.connect(self._font_scale_changed)
    # 已移除最小非零块设置，保留其余信号

    def _font_scale_changed(self, val):
        self.font_scale_label.setText(str(val))
        font = self.history_view.font()
        font.setPointSize(val)
        self.history_view.setFont(font)

    def _scale_changed(self, val):
        scale = val / 100.0
        self.scale_label.setText(f"{scale:.2f}x")
        self._settings_changed()

    def _settings_changed(self, *args):
        # 重新渲染当前 history
        history = self.stats.get('history', [])
        highlight_color = self._ensure_visible_color(self.stats.get('highlight_color', '#FFFFFF'))
        self.stats['highlight_color'] = highlight_color
        fill_char = (self.fill_char_edit.text() or '█')[0]
        bar_width = self.bar_width_spin.value()
        scale = self.scale_slider.value() / 100.0
        # 写入 stats 供线程使用
        self.stats['fill_char'] = fill_char
        self.stats['bar_width'] = bar_width
        self.stats['global_scale'] = scale
        history_text = "\n".join(generate_bar_chart_for_history(
            history,
            color=highlight_color,
            bar_width=bar_width,
            fill_char=fill_char,
            empty_char=fill_char,  # 同字符不同颜色
            global_scale=scale
        ))
        # 保持滚动位置逻辑
        sb = self.history_view.verticalScrollBar()
        at_bottom = sb.value() == sb.maximum()
        self._suppress_scroll_signal = True
        self._set_history_html(history_text)
        if at_bottom:
            self.history_view.moveCursor(QTextCursor.End)
        self._suppress_scroll_signal = False

    def _history_html_from_text(self, history_text: str) -> str:
        lines = history_text.split('\n') if history_text else []
        if not lines:
            lines = ['']
        html_lines = []
        for line in lines:
            content = line if line else '&nbsp;'
            html_lines.append(f'<div style="white-space: pre;">{content}</div>')

        font = self.history_view.font()
        font_size = font.pointSizeF()
        if font_size <= 0:
            font_size = getattr(self, '_base_font_point_size', 10)
        palette = self.history_view.palette()
        fg_color = palette.color(QPalette.Text).name()
        bg_color = palette.color(QPalette.Base).name()

        return (
            "<html><head><meta charset='utf-8'></head>"
            f"<body style=\"margin:0;font-family:'{font.family()}';font-size:{font_size}pt;"
            f"color:{fg_color};background-color:{bg_color};\">"
            f"{''.join(html_lines)}"
            "</body></html>"
        )

    def _set_history_html(self, history_text: str):
        self.history_view.setHtml(self._history_html_from_text(history_text))

    def _ensure_visible_color(self, color: str) -> str:
        fallback = '#4caf50'
        if not color:
            return fallback
        hex_value = color[1:] if color.startswith('#') else color
        if len(hex_value) == 3:
            hex_value = ''.join(ch * 2 for ch in hex_value)
        if len(hex_value) != 6:
            return fallback
        try:
            r, g, b = [int(hex_value[i:i+2], 16) for i in range(0, 6, 2)]
        except ValueError:
            return fallback

        bg = self.history_view.palette().color(QPalette.Base)
        contrast = abs(r - bg.red()) + abs(g - bg.green()) + abs(b - bg.blue())
        if contrast < 120:
            return fallback
        return f"#{hex_value.lower()}"

    # ---------------- 视图与线程逻辑（原误放在 CollapsibleBox 内） ----------------
    def history_view_wheel_event(self, event):
        """支持 Ctrl+滚轮 调整字体大小。"""
        if QApplication.keyboardModifiers() == Qt.ControlModifier:
            delta = event.angleDelta().y()
            font = self.history_view.font()
            current_size = font.pointSize()
            if delta > 0:
                font.setPointSize(current_size + 1)
            else:
                if current_size > 1:
                    font.setPointSize(current_size - 1)
            self.history_view.setFont(font)
            event.accept()
        else:
            QTextEdit.wheelEvent(self.history_view, event)

    def start_worker(self):
        self.worker = Worker(self.stats)
        self.worker.update_signal.connect(self.update_ui)
        self.worker.log_signal.connect(self.log_message)
        self.worker.start()

    def update_ui(self, history_text, status_text):
        sb = self.history_view.verticalScrollBar()
        # 当用户手动滚动后（auto_scroll_enabled=False），在刷新期间保持原始滚动值，
        # 避免因内容增加而按照“距底部距离”推进，导致阅读位置被不断向下顶。
        preserve_value = sb.value() if not self.auto_scroll_enabled else None

        self._suppress_scroll_signal = True
        self._set_history_html(history_text)
        if self.auto_scroll_enabled:
            self.history_view.moveCursor(QTextCursor.MoveOperation.End)
        else:
            new_max = sb.maximum()
            # 保持刷新前的位置，若超出新范围则夹紧
            target = min(preserve_value if preserve_value is not None else 0, new_max)
            sb.setValue(max(0, target))
        self._suppress_scroll_signal = False
        # 更新固定行文本内容（虽然名为固定行，但可显示动态统计）
        self.fixed_line_label.setText(status_text)
        # 如有新文件则更新预览
        self.update_preview_if_needed()

    # ---------------- 预览逻辑 ----------------
    def update_preview_if_needed(self):
        """常规更新：只在路径变化时才更新"""
        path = self.stats.get('last_moved_image')
        if path and path != self._last_preview_path and os.path.exists(path):
            self._set_preview_image(path)
            self._last_preview_path = path
    
    def _force_update_preview(self):
        """强制更新：展开预览框时调用，重新加载最新图片"""
        path = self.stats.get('last_moved_image')
        if path and os.path.exists(path):
            # 强制重新加载，即使路径相同
            self._last_preview_path = None
            self._set_preview_image(path)
            self._last_preview_path = path
        elif not path:
            self.preview_label.setText("暂无图片")
            self.preview_label.setPixmap(QPixmap())
        else:
            self.preview_label.setText("图片文件不存在")
            self.preview_label.setPixmap(QPixmap())

    def _set_preview_image(self, path: str):
        try:
            # 使用 QPixmap 加载图片，它会自动保留 PNG 的 alpha 通道
            pix = QPixmap(path)
            if pix.isNull():
                self._original_preview_pixmap = None
                self.preview_label.setText("预览加载失败")
                self.preview_label.setPixmap(QPixmap())
                return
            self._original_preview_pixmap = pix
            self.preview_label.setText("")
            self._apply_scaled_preview()
        except Exception as e:
            self.preview_label.setText(f"预览加载失败: {e}")
            self.preview_label.setPixmap(QPixmap())

    def _apply_scaled_preview(self):
        """应用缩放后的预览图，保持透明通道"""
        if not self._original_preview_pixmap:
            return
        label_size = self.preview_label.size()
        if label_size.width() <= 0 or label_size.height() <= 0:
            return
        # 使用 SmoothTransformation 并保持宽高比缩放
        scaled = self._original_preview_pixmap.scaled(
            label_size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.preview_label.setPixmap(scaled)

    def log_message(self, message):
        timestamp = datetime.now().strftime('%H:%M:%S')
        sb = self.history_view.verticalScrollBar()
        # 在手动滚动暂停自动滚动期间，记录原始滚动值，刷新后保持不变。
        preserve_value = sb.value() if not self.auto_scroll_enabled else None

        self._suppress_scroll_signal = True
        self.history_view.append(f"[{timestamp}] {message}")
        if self.auto_scroll_enabled:
            self.history_view.moveCursor(QTextCursor.MoveOperation.End)
        else:
            new_max = sb.maximum()
            target = min(preserve_value if preserve_value is not None else 0, new_max)
            sb.setValue(max(0, target))
        self._suppress_scroll_signal = False

    def open_folder(self):
        last_folder = self.stats.get('last_target_folder')
        if last_folder and os.path.exists(last_folder):
            open_last_folder(last_folder)
        else:
            self.log_message("没有可打开的文件夹记录")

    def close_app(self):
        if self.parent() is None or isinstance(self.window(), QMainWindow):
             QApplication.instance().quit()
        else:
            self.worker.stop()

    def closeEvent(self, event):
        if hasattr(self, 'worker'):
            self.worker.stop()
        self.save_history()
        super().closeEvent(event)

    # -------------------- 日志持久化 --------------------
    def load_history(self):
        if self.log_file_path.exists():
            try:
                with open(self.log_file_path, 'r', encoding='utf-8') as f:
                    lines = [line.rstrip('\n') for line in f if line.strip()]
                if lines:
                    self.stats['history'].extend(lines)
                    self._loaded_history_count = len(self.stats['history'])
                    history_text = "\n".join(generate_bar_chart_for_history(
                        self.stats['history'],
                        color=self.stats.get('highlight_color','#FFFFFF'),
                        bar_width=self.stats.get('bar_width',25),
                        fill_char=self.stats.get('fill_char','█'),
                        empty_char=self.stats.get('fill_char','█'),
                        global_scale=self.stats.get('global_scale',1.0)
                    ))
                    self._suppress_scroll_signal = True
                    self._set_history_html(history_text)
                    self.history_view.moveCursor(QTextCursor.MoveOperation.End)
                    self._suppress_scroll_signal = False
            except Exception as e:
                print(f"读取历史日志失败: {e}")

    def save_history(self):
        try:
            new_lines = self.stats['history'][self._loaded_history_count:]
            if not new_lines:
                return
            with open(self.log_file_path, 'a', encoding='utf-8') as f:
                for line in new_lines:
                    f.write(line + '\n')
            self._loaded_history_count = len(self.stats['history'])
        except Exception as e:
            print(f"保存日志失败: {e}")

    # -------------------- 自动滚动逻辑 --------------------
    def _on_user_scroll(self):
        if self._suppress_scroll_signal:
            return
        self.auto_scroll_enabled = False
        self._auto_scroll_reenable_timer.start(10000)

    def _reenable_auto_scroll(self):
        self.auto_scroll_enabled = True
        self.scroll_to_bottom()

    def scroll_to_bottom(self):
        self._suppress_scroll_signal = True
        self.history_view.moveCursor(QTextCursor.MoveOperation.End)
        self._suppress_scroll_signal = False

    # -------------------- 右键菜单功能 --------------------
    def _show_context_menu(self, position):
        """显示右键上下文菜单"""
        menu = QMenu(self.history_view)
        
        # 创建清空日志动作
        clear_action = QAction("清空日志文件", self.history_view)
        clear_action.triggered.connect(self._clear_log_file)
        menu.addAction(clear_action)
        
        # 显示菜单
        menu.exec_(self.history_view.mapToGlobal(position))
    
    def _clear_log_file(self):
        """清空日志文件"""
        # 弹出确认对话框
        reply = QMessageBox.question(
            self,
            '确认清空',
            '确定要清空当前的日志文件吗?\n此操作将永久删除所有历史记录,无法恢复!',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # 清空内存中的历史记录
                self.stats['history'].clear()
                self._loaded_history_count = 0
                
                # 清空日志文件
                if self.log_file_path.exists():
                    self.log_file_path.unlink()
                
                # 清空显示
                self._suppress_scroll_signal = True
                self.history_view.clear()
                self._suppress_scroll_signal = False
                
                # 重置统计数据
                self.stats['moved_count'] = 0
                self.stats['max_interval'] = 0
                self.stats['total_interval'] = 0
                self.stats['first_run_moved'] = 0
                self.stats['second_run_moved'] = 0
                
                timestamp = datetime.now().strftime('%H:%M:%S')
                self.log_message(f"日志已清空")
                
            except Exception as e:
                QMessageBox.warning(self, '错误', f'清空日志失败: {e}')
                print(f"清空日志失败: {e}")

class ResizableHandle(QWidget):
    """可拖动的调整大小手柄"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(8)
        self.setCursor(Qt.SizeVerCursor)
        self.setStyleSheet("""
            QWidget {
                background-color: transparent;
            }
            QWidget:hover {
                background-color: rgba(100, 100, 100, 100);
            }
        """)
        self._dragging = False
        self._start_pos = None
        self._start_height = 0

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._start_pos = event.globalPosition().toPoint()
            if self.parent():
                self._start_height = self.parent().content_area.height()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging and self.parent():
            delta = event.globalPosition().toPoint().y() - self._start_pos.y()
            new_height = max(100, self._start_height + delta)
            self.parent().setContentHeight(new_height)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False
            if self.parent():
                self.parent().saveHeight()
            event.accept()

class ResizableCollapsibleBox(QWidget):
    """支持调整大小的可折叠框"""
    expanded = Signal()
    
    def __init__(self, title="", settings=None, parent=None):
        super().__init__(parent)
        self._base_title = title
        self._settings = settings
        self._settings_key = f"CollapsibleBox_{title}_height"
        
        self.toggle_button = QPushButton(title)
        font = self.toggle_button.font()
        font.setBold(True)
        self.toggle_button.setFont(font)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(False)

        self.content_area = QFrame()
        self.content_area.setFrameShape(QFrame.StyledPanel)
        self.content_area.setMaximumHeight(0)
        self.content_area.setMinimumHeight(0)
        
        # 可拖动的调整大小手柄
        self.resize_handle = ResizableHandle(self)

        self.toggle_animation = QPropertyAnimation(self.content_area, b"maximumHeight")
        self.toggle_animation.setDuration(250)
        self.toggle_animation.setEasingCurve(QEasingCurve.InOutCubic)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.toggle_button)
        lay.addWidget(self.content_area)
        lay.addWidget(self.resize_handle)

        self.toggle_button.clicked.connect(self._on_toggled)
        self._update_arrow(False)
        
        # 加载保存的高度
        self._saved_height = self._load_height()

    def setContentLayout(self, layout):
        old = self.content_area.layout()
        if old is not None:
            while old.count():
                it = old.takeAt(0)
                w = it.widget()
                if w:
                    w.setParent(None)
        self.content_area.setLayout(layout)
        self.content_area.setMaximumHeight(0)

    def _on_toggled(self, checked: bool):
        self._update_arrow(checked)
        # 使用保存的高度或默认高度
        content_height = self._saved_height if checked else 0
        self.toggle_animation.stop()
        self.toggle_animation.setStartValue(self.content_area.maximumHeight())
        self.toggle_animation.setEndValue(content_height)
        
        # 关闭时需要同时设置 minimumHeight 为 0
        if not checked:
            self.content_area.setMinimumHeight(0)
        else:
            self.content_area.setMinimumHeight(content_height)
        
        self.toggle_animation.start()
        
        # 显示/隐藏调整手柄
        self.resize_handle.setVisible(checked)
        
        if checked:
            self.expanded.emit()

    def _update_arrow(self, expanded: bool):
        arrow = '▼' if expanded else '►'
        base = self._base_title if getattr(self, '_base_title', None) else ""
        self.toggle_button.setText(f"{arrow} {base}")

    def setContentHeight(self, height: int):
        """设置内容区域高度"""
        height = max(100, min(height, 1000))  # 限制在 100-1000 之间
        self.content_area.setMaximumHeight(height)
        self.content_area.setMinimumHeight(height)
        self._saved_height = height

    def saveHeight(self):
        """保存当前高度到设置"""
        if self._settings:
            self._settings.setValue(self._settings_key, self._saved_height)

    def _load_height(self):
        """从设置加载高度"""
        if self._settings:
            return self._settings.value(self._settings_key, 300, type=int)
        return 300

class CollapsibleBox(QWidget):
    expanded = Signal()
    def __init__(self, title="", fixed_content_height=None, parent=None):
        super().__init__(parent)
        self._base_title = title
        self._fixed_content_height = fixed_content_height
        self.toggle_button = QPushButton(title)
        font = self.toggle_button.font()
        font.setBold(True)
        self.toggle_button.setFont(font)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(False)

        self.content_area = QFrame()
        self.content_area.setFrameShape(QFrame.StyledPanel)
        self.content_area.setMaximumHeight(0)
        self.content_area.setMinimumHeight(0)

        self.toggle_animation = QPropertyAnimation(self.content_area, b"maximumHeight")
        self.toggle_animation.setDuration(250)
        self.toggle_animation.setEasingCurve(QEasingCurve.InOutCubic)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0,0,0,0)
        lay.addWidget(self.toggle_button)
        lay.addWidget(self.content_area)

        self.toggle_button.clicked.connect(self._on_toggled)
        self._update_arrow(False)

    def setContentLayout(self, layout):
        # 清除旧 layout
        old = self.content_area.layout()
        if old is not None:
            while old.count():
                it = old.takeAt(0)
                w = it.widget()
                if w:
                    w.setParent(None)
        self.content_area.setLayout(layout)
        self.content_area.setMaximumHeight(0)

    def _on_toggled(self, checked: bool):
        self._update_arrow(checked)
        # 如果指定了固定高度，使用固定高度；否则使用 layout 的 sizeHint
        if self._fixed_content_height:
            content_height = self._fixed_content_height
        else:
            content_height = self.content_area.layout().sizeHint().height() if self.content_area.layout() else 0
        self.toggle_animation.stop()
        self.toggle_animation.setStartValue(self.content_area.maximumHeight())
        self.toggle_animation.setEndValue(content_height if checked else 0)
        self.toggle_animation.start()
        if checked:
            self.expanded.emit()

    def _update_arrow(self, expanded: bool):
        arrow = '▼' if expanded else '►'
        base = self._base_title if getattr(self, '_base_title', None) else ""
        self.toggle_button.setText(f"{arrow} {base}")

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
