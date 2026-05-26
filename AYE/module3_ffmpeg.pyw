# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
import sys
import os
import re
import shutil
import subprocess
from collections import defaultdict
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QGridLayout, QFileDialog, QSlider,
    QLineEdit, QSpinBox, QComboBox, QCheckBox, QSizePolicy
)
from PySide6.QtWidgets import QTextEdit, QProgressDialog
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPainter, QColor, QFont, QPalette
from pathlib import Path

# =============================================================================
# FFmpeg 信息缓存和异步加载
# =============================================================================
_ffmpeg_info_cache = None

class FFmpegInfoWorker(QThread):
    """在后台线程中获取 FFmpeg 信息，避免 UI 阻塞。"""
    info_ready = Signal(dict)

    def run(self):
        """执行耗时操作并发出信号。"""
        global _ffmpeg_info_cache
        info = get_ffmpeg_info()
        _ffmpeg_info_cache = info  # 缓存结果
        self.info_ready.emit(info)

# FFmpeg 可执行文件检查
def get_ffmpeg_info():
    """获取 FFmpeg 可执行文件的路径和版本信息"""
    ffmpeg_path = shutil.which('ffmpeg')
    if ffmpeg_path:
        try:
            result = subprocess.run([ffmpeg_path, '-version'], capture_output=True, text=True, timeout=15)
            version_line = result.stdout.split('\n')[0] if result.stdout else "版本未知"
            return {
                'available': True,
                'path': ffmpeg_path,
                'version': version_line
            }
        except Exception as e:
            return {
                'available': False,
                'path': ffmpeg_path,
                'error': str(e)
            }
    return {'available': False, 'path': None, 'error': 'FFmpeg 不在 PATH 中'}

class CollapsibleBox(QWidget):
    """一个可折叠面板。

    参数:
        title: 标题文本
        default_open: 初始是否展开
        expand_flex: 若为 True 且展开，则内容区域允许自由扩展(占剩余空间)
    """
    def __init__(self, title="", parent=None, default_open=False, expand_flex=False):
        super().__init__(parent)
        self.base_title = title
        self.expand_flex = expand_flex

        self.toggle_button = QPushButton()
        font = self.toggle_button.font()
        font.setBold(True)
        self.toggle_button.setFont(font)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(default_open)

        self.content_area = QWidget()
        if self.expand_flex:
            # 允许拉伸
            self.content_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        else:
            self.content_area.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        if default_open:
            if self.expand_flex:
                self.content_area.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX
            else:
                self.content_area.setMaximumHeight(self.content_area.sizeHint().height())
        else:
            self.content_area.setMaximumHeight(0)
        self.content_area.setMinimumHeight(0)

        self.toggle_animation = QPropertyAnimation(self.content_area, b"maximumHeight")
        self.toggle_animation.setDuration(250)
        self.toggle_animation.setEasingCurve(QEasingCurve.InOutQuart)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.toggle_button)
        main_layout.addWidget(self.content_area)

        self.toggle_button.clicked.connect(self.toggle)
        self.update_arrow(self.toggle_button.isChecked())
        self._apply_expand_flex_constraints(self.toggle_button.isChecked())

    def _calculate_collapsed_height(self):
        margins = self.layout().contentsMargins()
        return self.toggle_button.sizeHint().height() + margins.top() + margins.bottom()

    def _apply_expand_flex_constraints(self, expanded):
        if not self.expand_flex:
            # 非弹性面板：使用 Maximum 策略，折叠后不被 layout 拉伸
            self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
            return
        if expanded:
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.setMinimumHeight(0)
            self.setMaximumHeight(16777215)
        else:
            collapsed_height = self._calculate_collapsed_height()
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.setMinimumHeight(collapsed_height)
            self.setMaximumHeight(collapsed_height)

    def setContentLayout(self, layout):
        if self.content_area.layout() is not None:
            old_layout = self.content_area.layout()
            while old_layout.count():
                item = old_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.setParent(None)
                    widget.deleteLater()
            del old_layout
        self.content_area.setLayout(layout)
        if self.toggle_button.isChecked():
            if self.expand_flex:
                self.content_area.setMaximumHeight(16777215)
            else:
                self.content_area.setMaximumHeight(self.content_area.sizeHint().height())

    def toggle(self, checked):
        self.update_arrow(checked)
        if self.expand_flex:
            # 对可扩展面板：统一用最大高度 16777215 / 0 控制
            if checked:
                self.content_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                self.content_area.setMaximumHeight(16777215)
            else:
                self.content_area.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
                self.content_area.setMaximumHeight(0)
            
            self.content_area.updateGeometry()
            # 无需手动更新父布局，Qt会自动处理
            self._apply_expand_flex_constraints(checked)
            self.updateGeometry()
        else:
            content_height = self.content_area.sizeHint().height()
            self.toggle_animation.setStartValue(self.content_area.maximumHeight())
            self.toggle_animation.setEndValue(content_height if checked else 0)
            self.toggle_animation.start()

    def update_arrow(self, checked):
        arrow = "▼" if checked else "►"
        self.toggle_button.setText(f"{arrow} {self.base_title}")

class ScanWorker(QThread):
    """Worker thread for scanning files to prevent UI freezing."""
    scan_complete = Signal(object)

    def __init__(self, path, channel_suffixes):
        super().__init__()
        self.path = path
        self.channel_suffixes = channel_suffixes
        self.is_running = True

    def run(self):
        tree_data = defaultdict(lambda: {'frames': set(), 'total_files': 0, 'path': ''})
        try:
            for root, _, files in os.walk(self.path):
                if not self.is_running:
                    return
                for file in files:
                    if file.lower().endswith('.png'):
                        # Simplified regex to capture base name and frame number
                        match = re.match(r'(.+?)[._]?(\d+)\.png$', file, re.IGNORECASE)
                        if match:
                            base_name, frame_str = match.groups()
                            
                            # Ignore channel images
                            is_channel = False
                            # Check if the part before the frame number ends with a channel suffix
                            # e.g., "render.zdepth.0001" -> base_name is "render.zdepth"
                            for suffix in self.channel_suffixes:
                                if base_name.lower().endswith('.' + suffix):
                                    is_channel = True
                                    break
                            if is_channel:
                                continue

                            frame = int(frame_str)
                            
                            # If a sequence name contains a channel name but is not a channel file,
                            # strip the suffix for grouping. e.g. "shot01.diffuse" and "shot01" should be grouped.
                            # This part might need refinement based on naming conventions.
                            # For now, we group by the exact base_name.
                            
                            tree_data[base_name]['frames'].add(frame)
                            tree_data[base_name]['total_files'] += 1
                            if not tree_data[base_name]['path']:
                                tree_data[base_name]['path'] = root
            if self.is_running:
                self.scan_complete.emit(tree_data)
        except Exception as e:
            print(f"Error in scan worker: {e}")
            self.scan_complete.emit({}) # Emit empty dict on error

    def stop(self):
        self.is_running = False

class SequenceViewerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 设置默认路径为上两级的 '0' 目录
        self.current_path = str(Path(os.path.abspath(__file__)).parent.parent / '0')
        os.makedirs(self.current_path, exist_ok=True) # 确保目录存在
        self.auto_refresh_enabled = False
        self.scan_worker = None
        self.min_frame_threshold = 5
        self.max_frame_threshold = 10000
        self.selected_cards_order = []  # 维护选中的顺序
        # 默认输出目录为桌面
        desktop_path = str(Path.home() / 'Desktop')
        self.unified_output_dir = desktop_path if os.path.exists(desktop_path) else str(Path.home())

        # Common channel suffixes
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

        # 标志：标记初始化是否完成
        self._initialization_complete = False
        
        self.setup_ui()
        
        # 标记 UI 已设置好，但内容还在加载
        self._initialization_complete = True
        
        # 延迟扫描目录和启动自动刷新定时器，避免初始化时卡顿
        # Defer scanning to avoid UI freezing during initialization
        QTimer.singleShot(200, self._deferred_init)

        # 简单日志缓存（同时输出到界面日志）
        self._last_message = ""
    
        # 异步获取 FFmpeg 信息
        self.ffmpeg_worker = FFmpegInfoWorker()
        self.ffmpeg_worker.info_ready.connect(self._on_ffmpeg_info_ready)

    def _on_ffmpeg_info_ready(self, ffmpeg_info):
        """处理来自后台线程的 FFmpeg 信息。"""
        if ffmpeg_info['available']:
            self.log(f"🎬 FFmpeg: {ffmpeg_info['path']}")
            self.log(f"   {ffmpeg_info['version']}")
            self.log(f"✅ FFmpeg 库已就绪")
        else:
            self.log(f"❌ FFmpeg 未找到或无法执行: {ffmpeg_info.get('error', '未知错误')}")
            if ffmpeg_info.get('path'):
                self.log(f"   路径: {ffmpeg_info['path']}")
        self.log("")

    def _deferred_init(self):
        """后台初始化：启动扫描和自动刷新"""
        # 启动第一次扫描
        self.scan_directory()
        
        # Auto-refresh timer
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(5000) # 5 seconds
        self.refresh_timer.timeout.connect(self.scan_directory)

    def log(self, msg: str):
        self._last_message = msg
        print(msg)
        # 输出到界面日志
        if hasattr(self, 'log_view'):
            try:
                self.log_view.append(msg)
            except Exception:
                pass
        # 让UI有机会刷新，避免“无响应”的感觉
        try:
            QApplication.processEvents()
        except Exception:
            pass

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        # 创建"输出设置"折叠面板（放置 ffmpeg 转视频的设置）
        self.output_settings_box = CollapsibleBox("输出设置", default_open=True, expand_flex=False)
        from PySide6.QtWidgets import QVBoxLayout as _QVBL, QHBoxLayout as _QHBL
        output_settings_layout = _QVBL()
        output_settings_layout.setContentsMargins(4, 4, 4, 4)
        output_settings_layout.setSpacing(4)

        # 行1：预览目录 + 预览按钮
        row1 = _QHBL()
        self.path_edit = QLineEdit(self.current_path)
        self.path_edit.returnPressed.connect(self.path_edited)
        self.select_button = QPushButton("预览目录")
        self.select_button.clicked.connect(self.select_directory)
        row1.addWidget(self.path_edit, 1)
        row1.addWidget(self.select_button)
        output_settings_layout.addLayout(row1)

        # 行2：输出目录 + 选择按钮
        row2 = _QHBL()
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText(f"输出目录: {self.unified_output_dir}")
        self.output_dir_edit.setReadOnly(True)
        self.unified_output_dir_btn = QPushButton("输出目录")
        self.unified_output_dir_btn.clicked.connect(self.choose_unified_output_dir)
        row2.addWidget(self.output_dir_edit, 1)
        row2.addWidget(self.unified_output_dir_btn)
        output_settings_layout.addLayout(row2)

        # 行3：视频格式
        row3 = _QHBL()
        row3.addWidget(QLabel("视频格式:"))
        self.video_format_combo = QComboBox()
        self.video_format_combo.addItems(["mp4", "mov", "avi", "mkv", "webm"])
        row3.addWidget(self.video_format_combo)
        row3.addStretch()
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self.scan_directory)
        row3.addWidget(self.refresh_button)
        output_settings_layout.addLayout(row3)

        # 行4：帧率（码率移动到码控行）
        row4 = _QHBL()
        row4.addWidget(QLabel("帧率:"))
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 120)
        self.fps_spin.setValue(30)
        row4.addWidget(self.fps_spin)
        row4.addStretch()
        output_settings_layout.addLayout(row4)

        # 行5：编码器 + 预设
        row5 = _QHBL()
        row5.addWidget(QLabel("编码器:"))
        self.encoder_combo = QComboBox()
        self.encoder_combo.addItems([
            "libx264 (H.264)",
            "libx265 (H.265/HEVC)",
            "mpeg4",
            "ffv1 (无损)"
        ])
        self.encoder_combo.currentTextChanged.connect(self._update_encoder_params)
        row5.addWidget(self.encoder_combo)
        row5.addWidget(QLabel("预设:"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"])
        self.preset_combo.setCurrentText("medium")
        row5.addWidget(self.preset_combo)
        row5.addStretch()
        output_settings_layout.addLayout(row5)

        # 行5.1：码控（CBR/CRF）+ 码率/CRF + 2-pass
        row5_1 = _QHBL()
        row5_1.addWidget(QLabel("码控:"))
        self.vrate_mode_combo = QComboBox()
        self.vrate_mode_combo.addItems(["CBR(目标码率)", "CRF(质量优先 VBR)"])
        self.vrate_mode_combo.setCurrentIndex(1)
        row5_1.addWidget(self.vrate_mode_combo)

        self.bitrate_label = QLabel("码率(Mbps):")
        row5_1.addWidget(self.bitrate_label)
        self.bitrate_spin = QSpinBox()
        self.bitrate_spin.setRange(1, 500)
        self.bitrate_spin.setValue(10)
        row5_1.addWidget(self.bitrate_spin)

        self.crf_label = QLabel("CRF:")
        row5_1.addWidget(self.crf_label)
        self.crf_spin = QSpinBox()
        self.crf_spin.setRange(0, 51)
        self.crf_spin.setValue(23)
        row5_1.addWidget(self.crf_spin)

        self.two_pass_checkbox = QCheckBox("两次编码(2-pass)")
        self.two_pass_checkbox.setChecked(False)
        row5_1.addWidget(self.two_pass_checkbox)
        row5_1.addStretch()
        output_settings_layout.addLayout(row5_1)

        # 行5.2：Alpha 通道处理
        row5_2 = _QHBL()
        row5_2.addWidget(QLabel("Alpha 处理:"))
        self.alpha_mode_combo = QComboBox()
        self.alpha_mode_combo.addItems([
            "保留原始(rgba)",
            "直通预乘(straight)",
            "预乘(premultiply)",
            "分离(separate)",
            "去除背景"
        ])
        self.alpha_mode_combo.setCurrentIndex(0)
        row5_2.addWidget(self.alpha_mode_combo)
        
        row5_2.addWidget(QLabel("像素格式:"))
        self.pix_fmt_combo = QComboBox()
        self.pix_fmt_combo.addItems([
            "rgba (带透明)",
            "yuva420p (YUV+Alpha)",
            "yuv420p (无透明)"
        ])
        self.pix_fmt_combo.setCurrentIndex(0)
        row5_2.addWidget(self.pix_fmt_combo)
        row5_2.addStretch()
        output_settings_layout.addLayout(row5_2)

        # 行6：输出文件名前缀
        row6 = _QHBL()
        row6.addWidget(QLabel("输出名前缀:"))
        self.output_prefix_edit = QLineEdit()
        self.output_prefix_edit.setPlaceholderText("视频文件名前缀")
        row6.addWidget(self.output_prefix_edit, 1)
        output_settings_layout.addLayout(row6)

        # 行7：执行按钮（全宽）
        self.execute_convert_btn = QPushButton("执行转换")
        self.execute_convert_btn.clicked.connect(self.execute_convert_to_video)
        self.execute_convert_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        output_settings_layout.addWidget(self.execute_convert_btn)

        # 行8：日志输出
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(120)
        output_settings_layout.addWidget(self.log_view)

        self.output_settings_box.setContentLayout(output_settings_layout)
        main_layout.addWidget(self.output_settings_box)

        # 样式设置折叠面板（下移）
        self.collapsible_box = CollapsibleBox("样式设置", default_open=False, expand_flex=False)
        settings_layout = QGridLayout()

        # Width Slider
        settings_layout.addWidget(QLabel("宽度:"), 1, 0)
        self.width_slider = QSlider(Qt.Horizontal)
        self.width_slider.setRange(1, 30)
        self.width_slider.setValue(2)
        self.width_slider_label = QLabel(str(self.width_slider.value()))
        self.width_slider.valueChanged.connect(self.width_slider_label.setNum)
        self.width_slider.valueChanged.connect(self.update_pixel_width)
        settings_layout.addWidget(self.width_slider, 1, 1)
        settings_layout.addWidget(self.width_slider_label, 1, 2)

        # Height Slider
        settings_layout.addWidget(QLabel("高度:"), 2, 0)
        self.height_slider = QSlider(Qt.Horizontal)
        self.height_slider.setRange(1, 30)
        self.height_slider.setValue(2)
        self.height_slider_label = QLabel(str(self.height_slider.value()))
        self.height_slider.valueChanged.connect(self.height_slider_label.setNum)
        self.height_slider.valueChanged.connect(self.update_pixel_height)
        settings_layout.addWidget(self.height_slider, 2, 1)
        settings_layout.addWidget(self.height_slider_label, 2, 2)

        # Min Frames Input
        settings_layout.addWidget(QLabel("最少帧数:"), 3, 0)
        self.min_frames_spinbox = QSpinBox()
        self.min_frames_spinbox.setRange(0, 9999)
        self.min_frames_spinbox.setValue(self.min_frame_threshold)
        self.min_frames_spinbox.valueChanged.connect(self.update_min_threshold)
        settings_layout.addWidget(self.min_frames_spinbox, 3, 1)

        # Max Frames Input
        settings_layout.addWidget(QLabel("最多帧数:"), 4, 0)
        self.max_frames_spinbox = QSpinBox()
        self.max_frames_spinbox.setRange(1, 99999)
        self.max_frames_spinbox.setValue(self.max_frame_threshold)
        self.max_frames_spinbox.valueChanged.connect(self.update_max_threshold)
        settings_layout.addWidget(self.max_frames_spinbox, 4, 1)

        self.collapsible_box.setContentLayout(settings_layout)
        main_layout.addWidget(self.collapsible_box)

        # 同步一次状态
        # self.custom_output_toggled(self.custom_output_checkbox.checkState())

        # 序列选择折叠面板 (可扩展填充)
        self.sequence_box = CollapsibleBox("序列选择", default_open=True, expand_flex=True)
        sequence_layout = QVBoxLayout()
        sequence_layout.setContentsMargins(0, 0, 0, 0)
        # Scroll Area for cards
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.card_container = QWidget()
        self.card_layout = QVBoxLayout(self.card_container)
        self.card_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.card_container)
        sequence_layout.addWidget(self.scroll_area)
        self.sequence_box.setContentLayout(sequence_layout)
        main_layout.addWidget(self.sequence_box, 100)
        main_layout.addStretch(1)

        # 根据码控模式更新控件可用状态
        self.vrate_mode_combo.currentIndexChanged.connect(self._update_vrate_controls)
        self._update_vrate_controls()

    def _update_encoder_params(self):
        """根据选中的编码器更新预设和码控参数的可用性"""
        encoder_text = self.encoder_combo.currentText()
        is_ffv1 = "ffv1" in encoder_text.lower()
        is_lossy = "x264" in encoder_text or "x265" in encoder_text or "mpeg4" in encoder_text
        
        # FFV1 是无损，不需要预设和码控
        self.preset_combo.setEnabled(is_lossy)
        self.vrate_mode_combo.setEnabled(is_lossy)
        self.crf_spin.setEnabled(is_lossy and self.vrate_mode_combo.currentIndex() == 1)
        self.bitrate_spin.setEnabled(is_lossy and self.vrate_mode_combo.currentIndex() == 0)
        self.two_pass_checkbox.setEnabled(is_lossy and self.vrate_mode_combo.currentIndex() == 0)
        
        if is_ffv1:
            self.log_view.append("💡 FFV1 无损编码：预设和码率选项已禁用")

    def _update_vrate_controls(self):
        use_crf = self.vrate_mode_combo.currentIndex() == 1
        # CRF 模式下，仅可设置 CRF；CBR 模式下，仅可设置码率和两次编码
        self.crf_label.setEnabled(use_crf)
        self.crf_spin.setEnabled(use_crf)
        self.bitrate_label.setEnabled(not use_crf)
        self.bitrate_spin.setEnabled(not use_crf)
        self.two_pass_checkbox.setEnabled(not use_crf)

    def path_edited(self):
        new_path = self.path_edit.text()
        if os.path.isdir(new_path):
            self.current_path = new_path
            self.scan_directory()
        else:
            # If path is invalid, revert to the old one
            self.path_edit.setText(self.current_path)

    def select_directory(self):
        path = QFileDialog.getExistingDirectory(self, "选择目录", self.current_path)
        if path:
            self.current_path = path
            self.path_edit.setText(self.current_path)
            self.scan_directory()

    def scan_directory(self):
        if self.scan_worker and self.scan_worker.isRunning():
            return # Don't start a new scan if one is already running

        self.path_edit.setText(self.current_path)
        self.select_button.setEnabled(False)
        self.refresh_button.setEnabled(False)

        # Don't clear cards here to avoid flickering.
        # self.clear_cards()

        self.scan_worker = ScanWorker(self.current_path, self.channel_suffixes)
        self.scan_worker.scan_complete.connect(self.on_scan_complete)
        self.scan_worker.start()

    def on_scan_complete(self, tree_data):
        # Clear old cards first, then add new ones. This reduces flicker.
        self.clear_cards()

        self.path_edit.setText(self.current_path)
        self.select_button.setEnabled(True)
        self.refresh_button.setEnabled(True)
        
        sorted_sequences = sorted(tree_data.items(), key=lambda item: item[0])

        # Store cards to update them later
        self.cards = []
        for seq_name, data in sorted_sequences:
            if data['frames']: # Only show sequences with frames
                frame_count = len(data['frames'])
                if not (self.min_frame_threshold <= frame_count <= self.max_frame_threshold):
                    continue
                card = SequenceCard(seq_name, data)
                # Apply current slider values to new cards
                card.viz_widget.set_pixel_width(self.width_slider.value())
                card.viz_widget.set_pixel_height(self.height_slider.value())
                self.card_layout.addWidget(card)
                self.cards.append(card)
        
        self.scan_worker = None

    def update_min_threshold(self, value):
        self.min_frame_threshold = value
        self.scan_directory()

    def update_max_threshold(self, value):
        self.max_frame_threshold = value
        self.scan_directory()

    def update_pixel_width(self, value):
        for card in getattr(self, 'cards', []):
            card.viz_widget.set_pixel_width(value)

    def update_pixel_height(self, value):
        for card in getattr(self, 'cards', []):
            card.viz_widget.set_pixel_height(value)

    def clear_cards(self):
        while self.card_layout.count():
            item = self.card_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.selected_cards_order.clear()

    def register_card_click(self, card):
        # 由卡片调用，维护顺序
        if card.selected:
            if card not in self.selected_cards_order:
                self.selected_cards_order.append(card)
        else:
            if card in self.selected_cards_order:
                self.selected_cards_order.remove(card)
        # 重新分配序号并刷新显示
        self.update_card_order_overlays()

    def update_card_order_overlays(self):
        # 生成 A,B,C... 超过26继续 AA,AB ? 目前简单循环字母
        def index_to_letters(i):
            letters = ''
            i0 = i
            while True:
                letters = chr(ord('A') + (i % 26)) + letters
                i = i // 26 - 1
                if i < 0:
                    break
            return letters
        for idx, card in enumerate(self.selected_cards_order):
            card.order_code = index_to_letters(idx)
            card.update()
        # 未选中的清空
        for card in getattr(self, 'cards', []):
            if card not in self.selected_cards_order:
                card.order_code = ''
                card.update()

    def choose_unified_output_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择输出目录", getattr(self, 'unified_output_dir', self.current_path))
        if path:
            self.unified_output_dir = path
            self.unified_output_dir_btn.setText(os.path.basename(path))
            if hasattr(self, 'output_dir_edit'):
                self.output_dir_edit.setText(path)

    def execute_convert_to_video(self):
        """将选中的 PNG 序列使用 ffmpeg 转换为视频"""
        self.log("=" * 60)
        self.log("🎬 PNG 序列转视频 - 开始执行")
        self.log("=" * 60)
        
        if not self.selected_cards_order:
            self.log("❌ 请先选择至少一个序列。")
            return
        
        self.log(f"📋 已选择 {len(self.selected_cards_order)} 个序列")
        
        # 确保输出目录存在（已在__init__中设置默认为桌面）
        if not self.unified_output_dir or not os.path.exists(self.unified_output_dir):
            self.log("⚠️  输出目录无效，已重置为桌面")
            desktop_path = str(Path.home() / 'Desktop')
            self.unified_output_dir = desktop_path if os.path.exists(desktop_path) else str(Path.home())
        
        os.makedirs(self.unified_output_dir, exist_ok=True)
        self.log(f"📁 输出目录: {self.unified_output_dir}")

        # 获取设置
        video_format = self.video_format_combo.currentText()
        fps = self.fps_spin.value()
        encoder_text = self.encoder_combo.currentText()
        # 从编码器文本中提取真实的编码器名称（去掉括号中的描述）
        if '(' in encoder_text:
            encoder = encoder_text.split('(')[0].strip()
        else:
            encoder = encoder_text.strip()
        
        preset = self.preset_combo.currentText()
        output_prefix = self.output_prefix_edit.text().strip() or "output"
        use_crf = self.vrate_mode_combo.currentIndex() == 1
        crf_value = self.crf_spin.value() if hasattr(self, 'crf_spin') else 23
        bitrate = self.bitrate_spin.value() if hasattr(self, 'bitrate_spin') else 10
        do_two_pass = self.two_pass_checkbox.isChecked() if hasattr(self, 'two_pass_checkbox') else False
        alpha_mode = self.alpha_mode_combo.currentText() if hasattr(self, 'alpha_mode_combo') else "保留原始(rgba)"
        pix_fmt_text = self.pix_fmt_combo.currentText() if hasattr(self, 'pix_fmt_combo') else "rgba (带透明)"

        self.log(f"⚙️  转码参数:")
        self.log(f"   - 格式: {video_format}")
        self.log(f"   - 帧率: {fps} fps")
        self.log(f"   - 编码器: {encoder} (原始文本: {encoder_text})")
        
        if encoder.lower() == "ffv1":
            self.log(f"   - 模式: FFV1 无损编码")
        elif use_crf:
            self.log(f"   - 模式: CRF")
            self.log(f"   - CRF: {crf_value}")
        else:
            self.log(f"   - 模式: CBR")
            self.log(f"   - 码率: {bitrate} Mbps")
            self.log(f"   - 两次编码: {'是' if do_two_pass else '否'}")
        
        self.log(f"   - 预设: {preset}")
        self.log(f"   - Alpha处理: {alpha_mode}")
        self.log(f"   - 像素格式: {pix_fmt_text}")
        self.log(f"   - 输出前缀: {output_prefix}")
        self.log("")

        # 逐个转换选中的序列
        success_count = 0
        fail_count = 0
        
        for idx, card in enumerate(self.selected_cards_order, 1):
            self.log(f"[{idx}/{len(self.selected_cards_order)}] 处理序列: {card.name}")
            try:
                # 禁用按钮避免重复点击
                self.execute_convert_btn.setEnabled(False)
                QApplication.processEvents()
                self._convert_sequence_to_video(
                    card, video_format, fps, bitrate, encoder, preset, output_prefix,
                    use_crf, crf_value, do_two_pass, alpha_mode, pix_fmt_text
                )
                success_count += 1
            except Exception as e:
                self.log(f"❌ 转换序列 {card.name} 失败: {e}")
                fail_count += 1
            self.log("")

        # 还原按钮
        self.execute_convert_btn.setEnabled(True)

        self.log("=" * 60)
        self.log(f"✅ 转换完成 - 成功: {success_count}, 失败: {fail_count}")
        self.log("=" * 60)

    def _convert_sequence_to_video(self, card, video_format, fps, bitrate, encoder, preset, output_prefix,
                                   use_crf: bool, crf_value: int, do_two_pass: bool, alpha_mode: str, pix_fmt_text: str):
        """使用 ffmpeg 将单个 PNG 序列转换为视频"""
        
        try:
            seq_path = card.data.get('path')
            if not seq_path or not os.path.isdir(seq_path):
                self.log(f"❌ 序列路径不存在: {seq_path}")
                return

            # 找出输入文件的命名模式
            frames = sorted(list(card.data['frames']))
            if not frames:
                self.log(f"❌ 序列 {card.name} 没有找到帧。")
                return

            min_frame = min(frames)
            max_frame = max(frames)
            
            # 查找第一个 PNG 文件以确定文件命名模式
            sample_file = None
            for fname in os.listdir(seq_path):
                if fname.lower().endswith('.png'):
                    match = re.match(r'(.+?)[._]?(\d+)\.png$', fname, re.IGNORECASE)
                    if match and int(match.group(2)) == min_frame:
                        sample_file = fname
                        break
            
            if not sample_file:
                self.log(f"❌ 无法确定序列 {card.name} 的命名模式。")
                return

            # 基于样本文件精确推断 ffmpeg 输入模式（分隔符+位数）
            sample_match = re.match(r'(.+?)([._]?)(\d+)\.png$', sample_file, re.IGNORECASE)
            if not sample_match:
                self.log(f"❌ 无法解析样本文件名: {sample_file}")
                return

            base_name = sample_match.group(1)
            sep = sample_match.group(2) or ''
            digits = len(sample_match.group(3))
            self.log(f"📝 序列基础名: {base_name}, 最小帧: {min_frame}, 最大帧: {max_frame}")

            input_pattern = f"{base_name}{sep}%0{digits}d.png"
            # 双重校验模式是否存在
            test_file = f"{base_name}{sep}{str(min_frame).zfill(digits)}.png"
            if not os.path.exists(os.path.join(seq_path, test_file)):
                # 若起始帧可能不等于 min_frame（或有缺帧），尝试用目录里第一个匹配到的样本帧
                alt_test = sample_file
                # 以样本的数字长度作为准则
                input_pattern = f"{base_name}{sep}%0{digits}d.png"
            self.log(f"✓ 识别到模式: {input_pattern}")

            input_path = os.path.join(seq_path, input_pattern)
            
            # 输出文件名
            output_filename = f"{output_prefix}_{card.name}.{video_format}"
            output_file = os.path.join(self.unified_output_dir, output_filename)

            # 根据 Alpha 模式和像素格式构建滤镜和参数
            filters = []
            pix_fmt = "rgba"  # 默认保留 Alpha
            
            if "yuva420p" in pix_fmt_text:
                pix_fmt = "yuva420p"
            elif "yuv420p" in pix_fmt_text:
                pix_fmt = "yuv420p"
            
            # 根据容器格式验证 Alpha 支持
            # mp4 对 Alpha 支持有限，应该使用 mov 或 mkv
            container_alpha_warn = False
            if video_format.lower() == "mp4" and pix_fmt in ["rgba", "yuva420p"]:
                container_alpha_warn = True
                self.log(f"⚠️  警告：MP4 容器对 Alpha 通道支持有限！")
                self.log(f"   建议使用 MOV 或 MKV 容器以保留透明度")
            
            # Alpha 处理模式
            # 注意：format=rgba 可能在某些情况下破坏 alpha 通道，所以只在必要时使用
            if alpha_mode == "保留原始(rgba)":
                # 仅设置像素格式，不添加额外滤镜
                # FFmpeg 会自动识别 PNG 的 Alpha 通道，避免 format=rgba 破坏 alpha
                pass
            elif alpha_mode == "直通预乘(straight)":
                # 直通 -> 预乘：保持原始直通 alpha
                # PNG 默认就是直通 alpha，不需要显式处理
                pass
            elif alpha_mode == "预乘(premultiply)":
                # 预乘：需要实际的预乘操作
                # 使用 split + alphaextract + alphamerge 组合
                filters.append("split=2[main][alpha];[alpha]alphaextract[a];[main][a]alphamerge")
            elif alpha_mode == "分离(separate)":
                # 分离 alpha 通道（删除 alpha，仅保留 RGB）
                filters.append("format=rgb24")
                pix_fmt = "yuv420p"
            elif alpha_mode == "去除背景":
                # 删除 alpha，纯视频
                filters.append("format=rgb24")
                pix_fmt = "yuv420p"
            
            # 构建完整滤镜链
            filter_chain = ""
            if filters:
                filter_chain = ",".join(filters)

            # 对于保留 Alpha 的模式，显式添加 format=rgba 滤镜确保 Alpha 不被破坏
            alpha_preserving_filter = ""
            if (alpha_mode == "保留原始(rgba)" or alpha_mode == "直通预乘(straight)") and pix_fmt == "rgba":
                # 显式指定 format=rgba 来保留 Alpha 通道，避免 Alpha 被破坏
                alpha_preserving_filter = "format=rgba"
                if filter_chain:
                    filter_chain = filter_chain + "," + alpha_preserving_filter
                else:
                    filter_chain = alpha_preserving_filter

            # 根据模式构建 ffmpeg 命令
            base_args = [
                'ffmpeg',
                '-y',  # 覆盖输出
                '-framerate', str(fps),
                '-start_number', str(min_frame),  # 从实际最小帧开始
                '-i', input_path,
            ]
            
            # 添加滤镜链（如果有）
            if filter_chain:
                base_args.extend(['-vf', filter_chain])
            
            base_args.extend([
                '-c:v', encoder,
                '-pix_fmt', pix_fmt,  # 指定输出像素格式
                '-r', str(fps),  # 显式指定输出帧率（重要：某些容器如 AVI 需要这个才能正确保存帧率）
            ])
            
            # 根据编码器类型添加特定参数
            rc_args = []
            if encoder.lower() == "ffv1":
                # FFV1 无损编码参数
                rc_args = ['-level', '3', '-coder', '1']  # level 3：高压缩；coder 1：算术编码
                # FFV1 通常与 mkv/avi 容器搭配更好，但如果指定 mp4 也会尝试
            else:
                # 有损编码（x264/x265/mpeg4）
                base_args.extend(['-preset', preset])
                if use_crf:
                    rc_args = ['-crf', str(crf_value)]
                else:
                    rc_args = ['-b:v', f'{bitrate}M']

            self.log(f"▶️  开始转换: {card.name}")
            if encoder.lower() == "ffv1":
                self.log(f"   格式={video_format}, fps={fps}, 编码器={encoder} (无损)")
            elif use_crf:
                self.log(f"   格式={video_format}, fps={fps}, CRF={crf_value}, 编码器={encoder}, 预设={preset}")
            else:
                self.log(f"   格式={video_format}, fps={fps}, 码率={bitrate}M, 编码器={encoder}, 预设={preset}, 两次={do_two_pass}")
            self.log(f"   输入模式: {input_pattern}")
            
            # 清晰地说明 Alpha 处理和透明度保留情况
            if alpha_mode == "保留原始(rgba)" or alpha_mode == "直通预乘(straight)":
                self.log(f"✅ Alpha处理: {alpha_mode}")
                self.log(f"   ✓ 透明度保留：使用 format=rgba 滤镜显式保留")
                if container_alpha_warn:
                    self.log(f"   ⚠️  注意：MP4 容器可能破坏透明度，建议转换为 MOV 格式")
                else:
                    self.log(f"   ✓ 容器格式支持 Alpha，透明度应正确保留")
            else:
                self.log(f"⚠️  Alpha处理: {alpha_mode}")
                if "去除" in alpha_mode or "分离" in alpha_mode:
                    self.log(f"   ✓ 已移除 Alpha 通道")
            
            self.log(f"   像素格式: {pix_fmt}")
            if filter_chain:
                self.log(f"   滤镜链: {filter_chain}")
                if alpha_preserving_filter:
                    self.log(f"   实际滤镜: {alpha_preserving_filter}")
            else:
                if alpha_preserving_filter:
                    self.log(f"   滤镜链: {alpha_preserving_filter}")
                else:
                    self.log(f"   滤镜链: (无，直接使用输入)")
            self.log(f"   输出文件: {output_file}")

            if encoder.lower() == "ffv1":
                # FFV1 无损编码：单次
                cmd = base_args + rc_args + [output_file]
                self.log(f"🔧 FFmpeg 命令行: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
                if result.returncode == 0:
                    self.log(f"✅ 转换成功: {output_filename}")
                else:
                    self.log(f"❌ 转换失败: {result.stderr if result.stderr else result.stdout}")
            elif (not use_crf) and do_two_pass:
                # 两次编码（仅在CBR下）
                passlog = os.path.join(self.unified_output_dir, f"{output_prefix}_{card.name}_pass")
                null_sink = 'NUL' if os.name == 'nt' else '/dev/null'
                cmd1 = base_args + rc_args + ['-pass', '1', '-passlogfile', passlog, '-f', video_format, null_sink]
                self.log(f"🔧 第一次编码命令: {' '.join(cmd1)}")
                res1 = subprocess.run(cmd1, capture_output=True, text=True, timeout=3600)
                if res1.returncode != 0:
                    self.log(f"❌ 第一次编码失败: {res1.stderr if res1.stderr else res1.stdout}")
                    return
                cmd2 = base_args + rc_args + ['-pass', '2', '-passlogfile', passlog, output_file]
                self.log(f"🔧 第二次编码命令: {' '.join(cmd2)}")
                res2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=3600)
                # 清理pass日志
                for ext in ('.log', '.log.mbtree'):
                    p = passlog + ext
                    try:
                        if os.path.exists(p):
                            os.remove(p)
                    except Exception:
                        pass
                if res2.returncode == 0:
                    self.log(f"✅ 转换成功: {output_filename}")
                else:
                    self.log(f"❌ 转换失败(第二次): {res2.stderr if res2.stderr else res2.stdout}")
            else:
                # 单次编码
                cmd = base_args + rc_args + [output_file]
                self.log(f"🔧 FFmpeg 命令行: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
                if result.returncode == 0:
                    self.log(f"✅ 转换成功: {output_filename}")
                else:
                    self.log(f"❌ 转换失败: {result.stderr if result.stderr else result.stdout}")
        
        except subprocess.TimeoutExpired:
            self.log(f"❌ 转换超时: {card.name}")
        except FileNotFoundError as e:
            self.log(f"❌ FFmpeg 未找到: {e}")
            self.log("   请确保已安装 FFmpeg 并添加到 PATH")
        except Exception as e:
            self.log(f"❌ 转换错误: {e}")

    def toggle_auto_refresh(self, enabled):
        self.auto_refresh_enabled = enabled
        if self.auto_refresh_enabled:
            self.refresh_timer.start()
        else:
            self.refresh_timer.stop()

    def showEvent(self, event):
        """Override showEvent to refresh when the widget is shown."""
        super().showEvent(event)
        
        # 异步获取 FFmpeg 信息（如果尚未缓存）
        global _ffmpeg_info_cache
        if _ffmpeg_info_cache is None:
            if not self.ffmpeg_worker.isRunning():
                self.ffmpeg_worker.start()
        else:
            # 如果已缓存，直接使用缓存信息
            self._on_ffmpeg_info_ready(_ffmpeg_info_cache)
        
        # We use a QTimer to delay the scan slightly, ensuring the UI is fully visible
        # and responsive before the scan starts.
        QTimer.singleShot(100, self.scan_directory)

    def closeEvent(self, event):
        if self.scan_worker and self.scan_worker.isRunning():
            self.scan_worker.stop()
            self.scan_worker.wait() # Wait for thread to finish
        super().closeEvent(event)


class SequenceCard(QFrame):
    def __init__(self, name, data, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.name = name
        self.data = data
        self.selected = False
        self.order_code = ''  # A,B,C ...

        frames = sorted(list(data['frames']))
        self.min_frame = frames[0] if frames else 0
        self.max_frame = frames[-1] if frames else 0
        self.total_frames = self.max_frame - self.min_frame + 1
        self.found_frames = len(frames)
        self.completeness = self.found_frames / self.total_frames if self.total_frames > 0 else 0

        self.setup_ui()
        self.update_style()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        name_label = QLabel(f"<b>{self.name}</b>")
        name_label.setWordWrap(True)
        completeness_label = QLabel(f"{self.completeness:.1%}")
        header_layout.addWidget(name_label)
        header_layout.addStretch()
        header_layout.addWidget(completeness_label)
        layout.addLayout(header_layout)
        
        # Info
        info_text = f"范围: {self.min_frame}-{self.max_frame}  |  总计: {self.total_frames} 帧  |  找到: {self.found_frames} 帧"
        info_label = QLabel(info_text)
        layout.addWidget(info_label)
        
        # Visualization
        self.viz_widget = FrameVizWidget(self.min_frame, self.max_frame, self.data['frames'])
        self.viz_widget.setMinimumHeight(20)
        layout.addWidget(self.viz_widget)

    def mouseDoubleClickEvent(self, event):
        """Opens the sequence folder on double-click."""
        path = self.data.get('path')
        if path and os.path.isdir(path):
            try:
                # Use os.startfile for a more platform-independent way to open the folder
                os.startfile(os.path.realpath(path))
            except Exception as e:
                print(f"Error opening folder: {e}")
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.toggle_selected()
        super().mousePressEvent(event)

    def toggle_selected(self):
        self.selected = not self.selected
        self.update_style()
        # 通知父组件维护顺序
        parent = self.parentWidget()
        # parent is the card_container; its parent is scroll area widget's parent layout container
        while parent and not isinstance(parent, SequenceViewerWidget):
            parent = parent.parentWidget()
        if parent and hasattr(parent, 'register_card_click'):
            parent.register_card_click(self)

    def set_selected(self, value: bool):
        if self.selected != value:
            self.selected = value
            self.update_style()

    def update_style(self):
        palette = self.palette()
        highlight = palette.color(QPalette.ColorRole.Highlight)
        hl_rgba = f"rgba({highlight.red()},{highlight.green()},{highlight.blue()},90)"
        border = f"rgba({highlight.red()},{highlight.green()},{highlight.blue()},170)"
        if self.selected:
            self.setStyleSheet(f"SequenceCard {{background-color: {hl_rgba}; border:2px solid {border}; border-radius:4px;}} ")
        else:
            self.setStyleSheet("SequenceCard {background-color: none; border:1px solid rgba(255,255,255,40); border-radius:4px;} ")

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.selected and self.order_code:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            palette = self.palette()
            highlight = palette.color(QPalette.ColorRole.Highlight)
            color = QColor(highlight)
            color.setAlpha(40)
            painter.setPen(Qt.NoPen)
            painter.setBrush(Qt.NoBrush)
            font = painter.font()
            font.setPointSize(int(self.height() * 0.6))
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(color)
            text = self.order_code
            rect = self.rect()
            painter.drawText(rect, Qt.AlignCenter, text)


class FrameVizWidget(QWidget):
    def __init__(self, min_frame, max_frame, found_frames, parent=None):
        super().__init__(parent)
        self.min_frame = min_frame
        self.max_frame = max_frame
        self.found_frames = found_frames
        self.total_frames = max_frame - min_frame + 1
        
        # 外观设置
        self.pixel_width = 2
        self.pixel_height = 2
        self.gap = 1
        
        palette = self.palette()
        self.exist_color = palette.color(QPalette.ColorRole.Highlight)
        self.missing_color = palette.color(QPalette.ColorRole.Mid)
        self.bg_color = palette.color(QPalette.ColorRole.Base)

        # 初始计算一次高度
        self._update_layout(self.width())

    def set_pixel_width(self, width):
        self.pixel_width = width
        self._update_layout(self.width())

    def set_pixel_height(self, height):
        self.pixel_height = height
        self._update_layout(self.width())

    def _update_layout(self, width):
        """根据宽度计算布局和所需高度"""
        if width <= 0 or self.total_frames <= 0:
            self.setFixedHeight(self.pixel_height)
            return

        block_width = self.pixel_width + self.gap
        block_height = self.pixel_height + self.gap
        pixels_per_row = max(1, (width + self.gap) // block_width)
        num_rows = (self.total_frames + pixels_per_row - 1) // pixels_per_row
        
        required_height = num_rows * block_height - self.gap
        
        # 设置固定高度，这将通知父布局进行调整
        if self.height() != required_height:
            self.setFixedHeight(required_height)
        
        # 触发重绘
        self.update()

    def resizeEvent(self, event):
        """当控件大小改变时，重新计算布局"""
        super().resizeEvent(event)
        self._update_layout(event.size().width())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        
        # 绘制背景
        painter.fillRect(self.rect(), self.bg_color)

        if self.total_frames <= 0 or width <= 0:
            return

        block_width = self.pixel_width + self.gap
        block_height = self.pixel_height + self.gap
        pixels_per_row = max(1, (width + self.gap) // block_width)

        for i in range(self.total_frames):
            frame_num = self.min_frame + i
            
            row = i // pixels_per_row
            col = i % pixels_per_row
            
            x = col * block_width
            y = row * block_height
            
            color = self.exist_color if frame_num in self.found_frames else self.missing_color
            
            painter.fillRect(x, y, self.pixel_width, self.pixel_height, color)

# --- Compatibility Alias ----------------------------------------------------
# main.pyw imports SequenceSplitWidget from this module. The original refactor
# renamed (or copied) the sequence viewer code here but did not provide the
# expected class name, causing an ImportError. To restore runtime we expose an
# alias so existing code keeps working. If later you implement real “切分”
# (splitting) logic, replace this alias with the actual implementation.
class SequenceSplitWidget(SequenceViewerWidget):
    pass

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_win = QMainWindow()
    viewer_widget = SequenceViewerWidget()
    main_win.setCentralWidget(viewer_widget)
    main_win.setWindowTitle("PNG 序列查看器 (独立运行)")
    main_win.setGeometry(200, 200, 900, 700)
    main_win.show()
    sys.exit(app.exec())
