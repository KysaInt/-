# -*- coding: utf-8 -*-
import sys
import os
import re
import subprocess
from collections import defaultdict
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QGridLayout, QFileDialog, QSlider,
    QLineEdit, QSpinBox
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPainter, QColor, QFont
from pathlib import Path

class CollapsibleBox(QWidget):
    """A collapsible box widget."""
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        
        self.toggle_button = QPushButton(title)
        self.toggle_button.setStyleSheet("text-align: left; font-weight: bold;")
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
        # 设置默认路径为父级的 '0' 目录
        self.current_path = str(Path(os.path.abspath(__file__)).parent / '0')
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

        # Toolbar
        toolbar = QFrame()
        toolbar_layout = QHBoxLayout(toolbar)
        
        self.path_edit = QLineEdit(self.current_path)
        self.path_edit.returnPressed.connect(self.path_edited)
        
        self.select_button = QPushButton("选择目录")
        self.select_button.clicked.connect(self.select_directory)
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self.scan_directory)
        
        toolbar_layout.addWidget(QLabel("当前目录:"))
        toolbar_layout.addWidget(self.path_edit)
        toolbar_layout.addWidget(self.select_button)
        toolbar_layout.addWidget(self.refresh_button)
        main_layout.addWidget(toolbar)

        # Collapsible settings box
        self.collapsible_box = CollapsibleBox("设置")
        settings_layout = QGridLayout() # Use QGridLayout for better alignment

        # Width Slider
        settings_layout.addWidget(QLabel("宽度:"), 0, 0)
        self.width_slider = QSlider(Qt.Horizontal)
        self.width_slider.setRange(1, 30)
        self.width_slider.setValue(4)
        self.width_slider_label = QLabel(str(self.width_slider.value()))
        self.width_slider.valueChanged.connect(self.width_slider_label.setNum)
        self.width_slider.valueChanged.connect(self.update_pixel_width)
        settings_layout.addWidget(self.width_slider, 0, 1)
        settings_layout.addWidget(self.width_slider_label, 0, 2)

        # Height Slider
        settings_layout.addWidget(QLabel("高度:"), 1, 0)
        self.height_slider = QSlider(Qt.Horizontal)
        self.height_slider.setRange(1, 30)
        self.height_slider.setValue(4)
        self.height_slider_label = QLabel(str(self.height_slider.value()))
        self.height_slider.valueChanged.connect(self.height_slider_label.setNum)
        self.height_slider.valueChanged.connect(self.update_pixel_height)
        settings_layout.addWidget(self.height_slider, 1, 1)
        settings_layout.addWidget(self.height_slider_label, 1, 2)

        # Min Frames Input
        settings_layout.addWidget(QLabel("最少帧数:"), 2, 0)
        self.min_frames_spinbox = QSpinBox()
        self.min_frames_spinbox.setRange(0, 9999)
        self.min_frames_spinbox.setValue(self.min_frame_threshold)
        self.min_frames_spinbox.valueChanged.connect(self.update_min_threshold)
        settings_layout.addWidget(self.min_frames_spinbox, 2, 1)

        # Max Frames Input
        settings_layout.addWidget(QLabel("最多帧数:"), 3, 0)
        self.max_frames_spinbox = QSpinBox()
        self.max_frames_spinbox.setRange(1, 99999)
        self.max_frames_spinbox.setValue(self.max_frame_threshold)
        self.max_frames_spinbox.valueChanged.connect(self.update_max_threshold)
        settings_layout.addWidget(self.max_frames_spinbox, 3, 1)

        self.collapsible_box.setContentLayout(settings_layout)
        main_layout.addWidget(self.collapsible_box)

        # Scroll Area for cards
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.card_container = QWidget()
        self.card_layout = QVBoxLayout(self.card_container)
        self.card_layout.setAlignment(Qt.AlignTop)
        
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

        self.path_edit.setText(f"正在扫描: {self.current_path}...")
        self.select_button.setEnabled(False)
        self.refresh_button.setEnabled(False)

        # Clear old cards before starting scan
        self.clear_cards()

        self.scan_worker = ScanWorker(self.current_path, self.channel_suffixes)
        self.scan_worker.scan_complete.connect(self.on_scan_complete)
        self.scan_worker.start()

    def on_scan_complete(self, tree_data):
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
        
        self.name = name
        self.data = data
        
        frames = sorted(list(data['frames']))
        self.min_frame = frames[0] if frames else 0
        self.max_frame = frames[-1] if frames else 0
        self.total_frames = self.max_frame - self.min_frame + 1
        self.found_frames = len(frames)
        self.completeness = self.found_frames / self.total_frames if self.total_frames > 0 else 0
        
        self.setup_ui()

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

        # Path
        path_label = QLabel(f"<i>{self.data['path']}</i>")
        path_label.setWordWrap(True)
        layout.addWidget(path_label)

class FrameVizWidget(QWidget):
    def __init__(self, min_frame, max_frame, found_frames, parent=None):
        super().__init__(parent)
        self.min_frame = min_frame
        self.max_frame = max_frame
        self.found_frames = found_frames
        self.total_frames = max_frame - min_frame + 1
        
        # 外观设置
        self.pixel_width = 4
        self.pixel_height = 4
        self.gap = 2
        self.exist_color = self.palette().color(QPalette.Highlight)
        self.missing_color = QColor("#555555")
        self.bg_color = self.palette().color(QPalette.Base)

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
    viewer_widget = SequenceViewerWidget()
    main_win.setCentralWidget(viewer_widget)
    main_win.setWindowTitle("PNG 序列查看器 (独立运行)")
    main_win.setGeometry(200, 200, 900, 700)
    main_win.show()
    sys.exit(app.exec())
