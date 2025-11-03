# -*- coding: utf-8 -*-
"""
Module 5: 序列预览播放器 (Sequence Preview Player)
功能: PNG 序列查看器 - 支持展开/收缩、图像预览、滑块控制、自动播放

创建日期: 2025-10-30
版本: 1.1
"""
import sys
import os
import re
import subprocess
from collections import defaultdict
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QGridLayout, QFileDialog, QSlider,
    QLineEdit, QSpinBox, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QPropertyAnimation, QEasingCurve, QSize, QRect
from PySide6.QtGui import QPainter, QColor, QFont, QPalette, QPixmap, QCursor
from pathlib import Path

class ResizeHandle(QFrame):
    """可拖拽的高度调整分隔符"""
    def __init__(self, target_widget, sequence_card, parent=None):
        super().__init__(parent)
        self.target_widget = target_widget
        self.sequence_card = sequence_card
        self.setFixedHeight(5)
        self.setCursor(Qt.SizeVerCursor)
        self.setStyleSheet("ResizeHandle { background-color: #cccccc; border: 1px solid #999; }")
        self.is_dragging = False
        self.drag_start_y = 0
        self.original_height = 0

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging = True
            self.drag_start_y = event.globalPosition().y()
            self.original_height = self.target_widget.maximumHeight()

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            delta = event.globalPosition().y() - self.drag_start_y
            new_height = max(100, self.original_height + delta)  # 最小高度 100px
            self.target_widget.setMaximumHeight(new_height)

    def mouseReleaseEvent(self, event):
        if self.is_dragging:
            self.is_dragging = False
            # 释放时刷新预览
            if self.sequence_card.all_frame_files:
                self.sequence_card.display_frame(self.sequence_card.current_frame_index)

class CollapsibleBox(QWidget):
    """A collapsible box widget."""
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        
        self.toggle_button = QPushButton(title)
        font = self.toggle_button.font()
        font.setBold(True)
        self.toggle_button.setFont(font)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(False)

        self.content_area = QWidget()
        self.content_area.setMaximumHeight(0)
        self.content_area.setMinimumHeight(0)
        
        self.toggle_animation = QPropertyAnimation(self.content_area, b"maximumHeight")
        self.toggle_animation.setDuration(300)
        self.toggle_animation.setEasingCurve(QEasingCurve.InOutQuart)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.toggle_button)
        main_layout.addWidget(self.content_area)

        self.toggle_button.clicked.connect(self.toggle)
        self.update_arrow(False)

    def setContentLayout(self, layout):
        # Clear the old layout and its widgets
        if self.content_area.layout() is not None:
            old_layout = self.content_area.layout()
            while old_layout.count():
                item = old_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.setParent(None)
                    widget.deleteLater()
            del old_layout
        
        # Set the new layout
        self.content_area.setLayout(layout)

    def toggle(self, checked):
        self.update_arrow(checked)
        
        # Calculate the content height at the moment of toggling
        content_height = self.content_area.sizeHint().height()
        
        self.toggle_animation.setStartValue(self.content_area.height())
        if checked:
            self.toggle_animation.setEndValue(content_height)
        else:
            self.toggle_animation.setEndValue(0)
        
        self.toggle_animation.start()

    def update_arrow(self, checked):
        arrow = "▼" if checked else "►"
        self.toggle_button.setText(f"{arrow} 设置")

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
                        # Try to extract base name and frame number
                        # Supports formats like: name_0001.png, name.0001.png, name0001.png, 0001.png
                        match = re.match(r'(.+?)[._]?(\d+)\.png$', file, re.IGNORECASE)
                        if match:
                            base_name, frame_str = match.groups()
                            
                            # If base_name is empty or only contains digits (pure numeric filename),
                            # use the folder name as the sequence name
                            if not base_name or base_name.isdigit():
                                # Get the folder name (handle case where root == self.path)
                                folder_name = os.path.basename(root)
                                # If folder is also numeric or we're in root, use "sequence"
                                if not folder_name or folder_name.isdigit():
                                    base_name = "sequence"
                                else:
                                    base_name = folder_name
                            
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

class SequencePreviewWidget(QWidget):
    """PNG序列预览播放器主窗口"""
    def __init__(self, parent=None):
        super().__init__(parent)
        # 设置默认路径为上两级的 '0' 目录
        self.current_path = str(Path(os.path.abspath(__file__)).parent.parent / '0')
        os.makedirs(self.current_path, exist_ok=True) # 确保目录存在
        self.auto_refresh_enabled = False
        self.scan_worker = None
        self.min_frame_threshold = 5
        self.max_frame_threshold = 10000

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

        self.setup_ui()
        self.scan_directory()

        # Auto-refresh timer
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(5000) # 5 seconds
        self.refresh_timer.timeout.connect(self.scan_directory)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        # 将路径选择行整合进设置折叠面板中

        # Collapsible settings box
        self.collapsible_box = CollapsibleBox("设置")
        settings_layout = QGridLayout() # Use QGridLayout for better alignment

        # Path selection row (位于顶部)
        path_label = QLabel("目录:")
        self.path_edit = QLineEdit(self.current_path)
        self.path_edit.returnPressed.connect(self.path_edited)
        self.select_button = QPushButton("选择")
        self.select_button.clicked.connect(self.select_directory)
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self.scan_directory)

        settings_layout.addWidget(path_label, 0, 0)
        settings_layout.addWidget(self.path_edit, 0, 1)
        settings_layout.addWidget(self.select_button, 0, 2)
        settings_layout.addWidget(self.refresh_button, 0, 3)

        # 调整列拉伸，让路径编辑框更宽
        settings_layout.setColumnStretch(1, 1)

        # Width Slider - 使用HBoxLayout让滑块和标签在同一行
        settings_layout.addWidget(QLabel("宽度:"), 1, 0)
        width_container = QWidget()
        width_layout = QHBoxLayout(width_container)
        width_layout.setContentsMargins(0, 0, 0, 0)
        self.width_slider = QSlider(Qt.Horizontal)
        self.width_slider.setRange(1, 30)
        self.width_slider.setValue(2)
        self.width_slider_label = QLabel(str(self.width_slider.value()))
        self.width_slider_label.setMinimumWidth(30)
        self.width_slider.valueChanged.connect(self.width_slider_label.setNum)
        self.width_slider.valueChanged.connect(self.update_pixel_width)
        width_layout.addWidget(self.width_slider)
        width_layout.addWidget(self.width_slider_label)
        settings_layout.addWidget(width_container, 1, 1, 1, 3)  # 跨3列

        # Height Slider - 使用HBoxLayout让滑块和标签在同一行
        settings_layout.addWidget(QLabel("高度:"), 2, 0)
        height_container = QWidget()
        height_layout = QHBoxLayout(height_container)
        height_layout.setContentsMargins(0, 0, 0, 0)
        self.height_slider = QSlider(Qt.Horizontal)
        self.height_slider.setRange(1, 30)
        self.height_slider.setValue(2)
        self.height_slider_label = QLabel(str(self.height_slider.value()))
        self.height_slider_label.setMinimumWidth(30)
        self.height_slider.valueChanged.connect(self.height_slider_label.setNum)
        self.height_slider.valueChanged.connect(self.update_pixel_height)
        height_layout.addWidget(self.height_slider)
        height_layout.addWidget(self.height_slider_label)
        settings_layout.addWidget(height_container, 2, 1, 1, 3)  # 跨3列

        # Min Frames Input
        settings_layout.addWidget(QLabel("最少帧数:"), 3, 0)
        self.min_frames_spinbox = QSpinBox()
        self.min_frames_spinbox.setRange(0, 9999)
        self.min_frames_spinbox.setValue(self.min_frame_threshold)
        self.min_frames_spinbox.valueChanged.connect(self.update_min_threshold)
        settings_layout.addWidget(self.min_frames_spinbox, 3, 1, 1, 3)  # 跨3列

        # Max Frames Input
        settings_layout.addWidget(QLabel("最多帧数:"), 4, 0)
        self.max_frames_spinbox = QSpinBox()
        self.max_frames_spinbox.setRange(1, 99999)
        self.max_frames_spinbox.setValue(self.max_frame_threshold)
        self.max_frames_spinbox.valueChanged.connect(self.update_max_threshold)
        settings_layout.addWidget(self.max_frames_spinbox, 4, 1, 1, 3)  # 跨3列

        self.collapsible_box.setContentLayout(settings_layout)
        main_layout.addWidget(self.collapsible_box)

        # Scroll Area for cards
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.card_container = QWidget()
        self.card_layout = QVBoxLayout(self.card_container)
        self.card_layout.setSpacing(0)  # Remove spacing between cards
        self.card_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins
        # 不要在上方添加 stretch，卡片从顶部紧贴开始排列
        # 只在最后添加 stretch 用来填充剩余空间
        
        self.scroll_area.setWidget(self.card_container)
        main_layout.addWidget(self.scroll_area)

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
        
        # 在所有卡片添加完后，在最下方添加拉伸来填充剩余空间
        self.card_layout.addStretch()
        
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
        # Remove all items from layout
        while self.card_layout.count() > 0:
            item = self.card_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def toggle_auto_refresh(self, enabled):
        self.auto_refresh_enabled = enabled
        if self.auto_refresh_enabled:
            self.refresh_timer.start()
        else:
            self.refresh_timer.stop()

    def showEvent(self, event):
        """Override showEvent to refresh when the widget is shown."""
        super().showEvent(event)
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
        # 设置尺寸策略: 水平拉伸, 垂直 Fixed (高度不变，始终紧凑)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        self.name = name
        self.data = data
        
        frames = sorted(list(data['frames']))
        self.min_frame = frames[0] if frames else 0
        self.max_frame = frames[-1] if frames else 0
        self.total_frames = self.max_frame - self.min_frame + 1
        self.found_frames = len(frames)
        self.completeness = self.found_frames / self.total_frames if self.total_frames > 0 else 0
        
        self.all_frame_files = self._collect_frame_files(frames)
        self.is_expanded = False
        self.current_frame_index = 0
        self.playback_enabled = False
        self.playback_speed = 30  # ms per frame
        self.last_preview_label_size = None  # 跟踪上次预览标签的大小
        self._cached_pixmap = None  # 缓存当前显示的原始像素图
        self._last_loaded_frame_path = None  # 跟踪上次加载的文件路径
        
        self.setup_ui()
        self.setup_animation()
        
        # Playback timer
        self.playback_timer = QTimer(self)
        self.playback_timer.timeout.connect(self.advance_frame)
        
        # 大小改变监听定时器 - 用于即时更新预览
        self.size_monitor_timer = QTimer(self)
        self.size_monitor_timer.setSingleShot(False)
        self.size_monitor_timer.setInterval(30)  # 每30ms检查一次大小，提高响应速度
        self.size_monitor_timer.timeout.connect(self.check_preview_label_size)
        self.pending_refresh = False  # 防抖标志

    def _collect_frame_files(self, frame_numbers):
        """Collect actual file paths for each frame number"""
        frame_files = {}
        path = self.data.get('path', '')
        if not path or not os.path.isdir(path):
            return frame_files
        
        try:
            # Create a set of frame numbers for quick lookup
            frame_set = set(frame_numbers)
            
            for file in os.listdir(path):
                if file.lower().endswith('.png'):
                    # Try to extract frame number from filename
                    # Supports formats like: name_0001.png, name.0001.png, name0001.png, 0001.png
                    match = re.match(r'(.+?)[._-]?(\d+)\.png$', file, re.IGNORECASE)
                    if match:
                        base_name = match.group(1)
                        frame_num_str = match.group(2)
                        
                        # Determine the sequence name to match against
                        # For numeric base names or sequence names, use folder-based matching
                        sequence_name = self.name
                        
                        # If self.name is "sequence" (default for pure numeric), 
                        # match any file with valid frame number
                        if sequence_name.lower() == "sequence":
                            # For generic "sequence" name, accept any file in this folder
                            try:
                                frame_num = int(frame_num_str)
                                if frame_num in frame_set:
                                    frame_files[frame_num] = os.path.join(path, file)
                            except ValueError:
                                pass
                        else:
                            # Check if base name matches (case-insensitive)
                            if base_name.lower() == sequence_name.lower():
                                try:
                                    frame_num = int(frame_num_str)
                                    # Check if this frame number is in our expected set
                                    if frame_num in frame_set:
                                        frame_files[frame_num] = os.path.join(path, file)
                                except ValueError:
                                    pass
        except Exception as e:
            print(f"Error collecting frame files: {e}")
        
        return frame_files

    def setup_animation(self):
        """Setup expand/collapse animation"""
        self.toggle_animation = QPropertyAnimation(self.content_widget, b"maximumHeight")
        self.toggle_animation.setDuration(300)
        self.toggle_animation.setEasingCurve(QEasingCurve.InOutQuart)
        # Connect finished signal to handle post-animation state
        self.toggle_animation.finished.connect(self.on_animation_finished)

    def on_animation_finished(self):
        """Called when animation finishes"""
        if not self.is_expanded:
            # Ensure content is completely hidden
            self.content_widget.setMaximumHeight(0)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        # 关键：不要在主布局中添加任何拉伸，让所有子元素保持其自然大小
        main_layout.setSizeConstraint(QVBoxLayout.SetMinimumSize)
        
        # Header (clickable)
        self.header_widget = QFrame()
        self.header_widget.setCursor(Qt.PointingHandCursor)
        header_layout = QHBoxLayout(self.header_widget)
        header_layout.setContentsMargins(4, 4, 4, 4)
        
        name_label = QLabel(f"<b>{self.name}</b>")
        name_label.setWordWrap(True)
        completeness_label = QLabel(f"{self.completeness:.1%}")
        header_layout.addWidget(name_label)
        header_layout.addStretch()
        header_layout.addWidget(completeness_label)
        
        main_layout.addWidget(self.header_widget)
        
        # Info line
        info_text = f"范围: {self.min_frame}-{self.max_frame}  |  总计: {self.total_frames} 帧  |  找到: {self.found_frames} 帧"
        info_label = QLabel(info_text)
        info_label.setStyleSheet("QLabel { font-size: 9pt; color: #888; }")
        main_layout.addWidget(info_label)
        
        # Visualization (这部分不会被压缩)
        self.viz_widget = FrameVizWidget(self.min_frame, self.max_frame, self.data['frames'])
        self.viz_widget.setMinimumHeight(20)
        main_layout.addWidget(self.viz_widget)
        
        # Content widget (expandable - 可伸缩)
        self.content_widget = QWidget()
        self.content_widget.setObjectName("contentWidget")
        self.content_widget.setMaximumHeight(0)
        self.content_widget.setMinimumHeight(0)
        
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 6, 0, 6)
        content_layout.setSpacing(6)
        
        # Preview label
        self.preview_label = QLabel("无预览")
        self.preview_label.setAlignment(Qt.AlignCenter | Qt.AlignTop)  # 改为从上对齐
        self.preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.preview_label.setMinimumHeight(200)
        self.preview_label.setMinimumWidth(300)
        # 移除最大高度限制，让它可以无限制增长
        self.preview_label.setStyleSheet("QLabel { background-color: #2a2a2a; border: 1px solid #555; padding: 5px; }")
        self.preview_label.setScaledContents(False)
        content_layout.addWidget(self.preview_label)
        
        # Playback controls layout
        controls_layout = QHBoxLayout()
        
        # Play button - 去掉三角标志，使用更简洁的文字
        self.play_button = QPushButton("播放")
        self.play_button.setCheckable(True)
        self.play_button.setMaximumWidth(100)
        self.play_button.clicked.connect(self.toggle_playback)
        self.play_button.setEnabled(len(self.all_frame_files) > 0)
        controls_layout.addWidget(self.play_button)
        
        # Frame slider
        self.frame_slider = QSlider(Qt.Horizontal)
        self.frame_slider.setMinimum(0)
        max_slider = max(0, len(self.all_frame_files) - 1)
        self.frame_slider.setMaximum(max_slider)
        self.frame_slider.sliderMoved.connect(self.on_slider_moved)
        self.frame_slider.setEnabled(len(self.all_frame_files) > 0)
        controls_layout.addWidget(self.frame_slider)
        
        # Frame number label
        self.frame_number_label = QLabel("0/0")
        self.frame_number_label.setMinimumWidth(60)
        self.frame_number_label.setAlignment(Qt.AlignCenter)
        self.frame_number_label.setStyleSheet("QLabel { font-size: 9pt; }")
        controls_layout.addWidget(self.frame_number_label)
        
        content_layout.addLayout(controls_layout)
        
        # 将 Content widget 添加到主布局，但不会压缩上面的区域
        main_layout.addWidget(self.content_widget)
        
        # 添加可调整高度的句柄
        self.resize_handle = ResizeHandle(self.content_widget, self)
        main_layout.addWidget(self.resize_handle)
        
        # 初始设置 content_widget 的最大高度为 0（默认关闭）
        # 展开时会自动计算所需高度
        self.content_widget.setMaximumHeight(0)
        
        # Connect header click
        self.header_widget.mousePressEvent = self.toggle_expanded

    def toggle_expanded(self, event):
        """Toggle expanded state"""
        self.is_expanded = not self.is_expanded
        if self.is_expanded and len(self.all_frame_files) > 0 and not self.preview_label.pixmap():
            # Initialize preview on first expand
            self.display_frame(0)
            # 展开时启动大小监听
            self.size_monitor_timer.start()
            # 计算所需的高度以完整显示图片
            QTimer.singleShot(10, self.auto_adjust_content_height)
        else:
            # 收缩时停止大小监听
            self.size_monitor_timer.stop()
        self.update_animation()

    def auto_adjust_content_height(self):
        """自动调整 Content 高度以完整显示图片"""
        if not self.preview_label.pixmap():
            return
        
        # 获取图片的显示高度
        pixmap = self.preview_label.pixmap()
        if pixmap and not pixmap.isNull():
            # 计算图片实际显示的高度
            img_height = pixmap.height()
            
            # 计算需要的总高度：图片高度 + 控制条高度 + padding
            # 控制条高度约 40px（播放按钮+滑块）
            # padding 约 20px
            control_height = 40
            padding = 20
            total_required_height = img_height + control_height + padding
            
            # 设置 content_widget 的最大高度为计算出的高度
            self.content_widget.setMaximumHeight(total_required_height)
            
            # 重新启动动画以应用新的高度
            self.toggle_animation.setStartValue(0)
            self.toggle_animation.setEndValue(total_required_height)
            self.toggle_animation.start()

    def check_preview_label_size(self):
        """检查预览标签大小是否改变，如果改变则刷新预览"""
        if not self.is_expanded or not self.preview_label.pixmap():
            return
        
        current_size = (self.preview_label.width(), self.preview_label.height())
        
        # 只有当大小真正改变了，且不在处理中时，才刷新
        if self.last_preview_label_size != current_size and not self.pending_refresh:
            self.last_preview_label_size = current_size
            self.pending_refresh = True
            # 使用 QTimer 延迟刷新，避免频繁重新计算
            QTimer.singleShot(0, lambda: self._do_refresh_preview())

    def _do_refresh_preview(self):
        """执行预览刷新"""
        try:
            self.display_frame(self.current_frame_index)
        finally:
            self.pending_refresh = False

    def update_animation(self):
        """Update expand/collapse animation"""
        self.toggle_animation.setStartValue(self.content_widget.height())
        if self.is_expanded:
            # 如果是手动切换展开（不是自动调整），使用默认高度
            # 自动调整会在 auto_adjust_content_height 中直接修改动画
            if self.content_widget.maximumHeight() == 16777215:  # 未设置最大高度时
                target_height = 350
                self.content_widget.setMaximumHeight(target_height)
            else:
                target_height = self.content_widget.maximumHeight()
            self.toggle_animation.setEndValue(target_height)
        else:
            self.toggle_animation.setEndValue(0)
            self.stop_playback()
        self.toggle_animation.start()

    def display_frame(self, index):
        """Display frame at given index"""
        if not self.all_frame_files:
            self.preview_label.setText("无图片文件")
            self.frame_number_label.setText("0/0")
            return
        
        sorted_frames = sorted(self.all_frame_files.keys())
        if 0 <= index < len(sorted_frames):
            frame_num = sorted_frames[index]
            file_path = self.all_frame_files[frame_num]
            
            try:
                # 第一次显示该帧时加载图片，之后使用缓存
                if not hasattr(self, '_last_loaded_frame_path') or self._last_loaded_frame_path != file_path:
                    pixmap = QPixmap(file_path)
                    if not pixmap.isNull():
                        self._cached_pixmap = pixmap
                        self._last_loaded_frame_path = file_path
                    else:
                        self.preview_label.setText(f"无法加载:\n{os.path.basename(file_path)}")
                        return
                else:
                    pixmap = self._cached_pixmap
                
                # 获取预览标签的实际可用宽度
                label_width = self.preview_label.width()
                
                # 如果标签宽度尚未确定，使用默认值
                if label_width <= 0:
                    label_width = 300
                
                # 计算缩放后的宽度 - 总是使用满宽度
                pixmap_width = pixmap.width()
                pixmap_height = pixmap.height()
                
                # 按宽度缩放，让图片填满标签宽度
                final_width = label_width - 10  # 保留padding空间
                
                # 快速缩放：使用 FastTransformation 替代 SmoothTransformation
                scaled_pixmap = pixmap.scaledToWidth(final_width, Qt.FastTransformation)
                
                self.preview_label.setPixmap(scaled_pixmap)
                self.current_frame_index = index
                self.frame_slider.blockSignals(True)
                self.frame_slider.setValue(index)
                self.frame_slider.blockSignals(False)
                total = len(sorted_frames)
                self.frame_number_label.setText(f"{frame_num} ({index+1}/{total})")
            except Exception as e:
                self.preview_label.setText(f"错误:\n{str(e)}")
        else:
            self.preview_label.setText("帧索引超出范围")

    def on_slider_moved(self, value):
        """Handle slider movement"""
        self.display_frame(value)

    def toggle_playback(self, checked):
        """Toggle playback - 首尾循环播放"""
        self.playback_enabled = checked
        if checked:
            self.play_button.setText("暂停")
            if len(self.all_frame_files) > 0 and not self.playback_timer.isActive():
                self.playback_timer.start(self.playback_speed)
        else:
            self.stop_playback()

    def stop_playback(self):
        """Stop playback"""
        self.playback_enabled = False
        self.play_button.setChecked(False)
        self.play_button.setText("播放")
        if self.playback_timer.isActive():
            self.playback_timer.stop()

    def advance_frame(self):
        """Advance to next frame"""
        if not self.playback_enabled or not self.all_frame_files:
            return
        
        sorted_frames = sorted(self.all_frame_files.keys())
        next_index = (self.current_frame_index + 1) % len(sorted_frames)
        self.display_frame(next_index)

    def closeEvent(self, event):
        """关闭时清理定时器"""
        self.size_monitor_timer.stop()
        self.playback_timer.stop()
        super().closeEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Opens the sequence folder on double-click."""
        path = self.data.get('path')
        if path and os.path.isdir(path):
            try:
                os.startfile(os.path.realpath(path))
            except Exception as e:
                print(f"Error opening folder: {e}")
        super().mouseDoubleClickEvent(event)


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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_win = QMainWindow()
    viewer_widget = SequencePreviewWidget()
    main_win.setCentralWidget(viewer_widget)
    main_win.setWindowTitle("PNG 序列预览播放器")
    main_win.setGeometry(200, 200, 900, 700)
    main_win.show()
    sys.exit(app.exec())
