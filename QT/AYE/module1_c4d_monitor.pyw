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
    QLabel, QPushButton, QHBoxLayout, QSizePolicy, QLineEdit, QSpinBox, QSlider, QGridLayout, QFrame, QMenu, QMessageBox, QCheckBox, QFileDialog
)
from PySide6.QtCore import QThread, Signal, Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QTextCursor, QFontDatabase, QPalette, QAction


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
        # 检查是否使用指定目录
        use_custom_dir = self.stats.get('use_custom_dir', False)
        custom_dir = self.stats.get('custom_dir', '')
        
        if use_custom_dir and custom_dir and os.path.isdir(custom_dir):
            # 使用指定目录下的0文件夹
            folder_path = os.path.join(custom_dir, '0')
        else:
            # 默认:脚本所在目录的上一级目录中的'0'文件夹
            # 例如: QT\AYE\module1_c4d_monitor.pyw -> QT\0
            folder_path = str(Path(os.path.abspath(__file__)).parent.parent / '0')
        
        # 确保目标目录存在
        os.makedirs(folder_path, exist_ok=True)
        # 记录当前目标目录，便于“打开”按钮使用
        self.stats['last_target_folder'] = folder_path
        
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

        # 指定目录复选框和选择按钮
        grid.addWidget(QLabel("指定目录:"), row, 0)
        self.custom_dir_checkbox = QCheckBox()
        self.custom_dir_checkbox.setChecked(False)
        grid.addWidget(self.custom_dir_checkbox, row, 1)
        self.custom_dir_button = QPushButton("选择...")
        self.custom_dir_button.setEnabled(False)  # 默认禁用
        grid.addWidget(self.custom_dir_button, row, 2)
        row += 1
        
        # 显示当前选择的目录路径
        grid.addWidget(QLabel("目录路径:"), row, 0)
        self.custom_dir_label = QLabel("未选择")
        self.custom_dir_label.setWordWrap(True)
        self.custom_dir_label.setStyleSheet("color: gray;")
        grid.addWidget(self.custom_dir_label, row, 1, 1, 2)
        row += 1


        self.settings_box.setContentLayout(grid)
        parent_layout.addWidget(self.settings_box)

        # 初始写入 stats
        self.stats['fill_char'] = (self.fill_char_edit.text() or '█')[0]
        self.stats['bar_width'] = self.bar_width_spin.value()
        self.stats['global_scale'] = self.scale_slider.value() / 100.0
        self.stats['use_custom_dir'] = False
        self.stats['custom_dir'] = ''

        # 信号连接
        self.fill_char_edit.textChanged.connect(self._settings_changed)
        self.bar_width_spin.valueChanged.connect(self._settings_changed)
        self.scale_slider.valueChanged.connect(self._scale_changed)
        self.font_scale_slider.valueChanged.connect(self._font_scale_changed)
        self.custom_dir_checkbox.stateChanged.connect(self._on_custom_dir_checkbox_changed)
        self.custom_dir_button.clicked.connect(self._select_custom_directory)
    # 已移除最小非零块设置,保留其余信号

    def _on_custom_dir_checkbox_changed(self, state):
        """处理指定目录复选框状态变化"""
        # stateChanged 传入的是 int，这里与枚举的 .value 比较更稳妥
        is_checked = (state == Qt.CheckState.Checked.value)
        self.custom_dir_button.setEnabled(is_checked)
        self.stats['use_custom_dir'] = bool(is_checked)

        # 勾选但未选择目录时，立即弹出选择框；取消时恢复显示
        if is_checked:
            if not self.stats.get('custom_dir') or not os.path.isdir(self.stats.get('custom_dir')):
                self._select_custom_directory()
                # 若用户取消选择，则回退勾选状态
                if not self.stats.get('custom_dir'):
                    self.custom_dir_checkbox.blockSignals(True)
                    self.custom_dir_checkbox.setChecked(False)
                    self.custom_dir_checkbox.blockSignals(False)
                    self.custom_dir_button.setEnabled(False)
                    self.stats['use_custom_dir'] = False
                    return
            # 到这里表示有有效目录，创建 0 并提示
            zero_dir = os.path.join(self.stats['custom_dir'], '0')
            try:
                os.makedirs(zero_dir, exist_ok=True)
                # 让“打开”按钮可立即打开此目录
                self.stats['last_target_folder'] = zero_dir
                self.log_message(f"已切换监控目录到: {zero_dir}")
            except Exception as e:
                self.log_message(f"创建目录失败: {e}")
        else:
            # 如果取消勾选,重置目录显示
            self.custom_dir_label.setText("未选择")
            self.custom_dir_label.setStyleSheet("color: gray;")
    
    def _select_custom_directory(self):
        """选择自定义目录"""
        # 获取当前目录(如果已设置)或使用默认路径
        current_dir = self.stats.get('custom_dir', str(Path.home()))
        self.log_message("打开目录选择对话框…")
        
        directory = QFileDialog.getExistingDirectory(
            self,
            "选择目标目录",
            current_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if directory:
            self.stats['custom_dir'] = directory
            # 显示选择的路径(缩短显示)
            display_path = directory
            if len(display_path) > 40:
                display_path = "..." + display_path[-37:]
            self.custom_dir_label.setText(display_path)
            self.custom_dir_label.setStyleSheet("color: white;")
            self.custom_dir_label.setToolTip(directory)  # 完整路径在工具提示中显示
            # 若复选框未勾选，此处也启用
            if not self.custom_dir_checkbox.isChecked():
                self.custom_dir_checkbox.blockSignals(True)
                self.custom_dir_checkbox.setChecked(True)
                self.custom_dir_checkbox.blockSignals(False)
                self.stats['use_custom_dir'] = True
            # 立即创建 0 并更新“打开”按钮指向
            zero_dir = os.path.join(directory, '0')
            try:
                os.makedirs(zero_dir, exist_ok=True)
                self.stats['last_target_folder'] = zero_dir
                self.log_message(f"指定目录已设置: {directory} (监控子目录: {zero_dir})")
            except Exception as e:
                self.log_message(f"创建目录失败: {e}")

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

class CollapsibleBox(QWidget):
    def __init__(self, title="", parent=None):
        super().__init__(parent)
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
        content_height = self.content_area.layout().sizeHint().height() if self.content_area.layout() else 0
        self.toggle_animation.stop()
        self.toggle_animation.setStartValue(self.content_area.maximumHeight())
        self.toggle_animation.setEndValue(content_height if checked else 0)
        self.toggle_animation.start()

    def _update_arrow(self, expanded: bool):
        arrow = '▼' if expanded else '►'
        self.toggle_button.setText(f"{arrow} 设置")

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
