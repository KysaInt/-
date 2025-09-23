# -*- coding: utf-8 -*-
import sys
import os
import re
import subprocess
from collections import defaultdict
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QGridLayout, QFileDialog
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor, QFont

# -*- coding: utf-8 -*-
import sys
import os
import re
import subprocess
from collections import defaultdict
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QGridLayout, QFileDialog
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QPainter, QColor, QFont

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
        self.current_path = os.path.dirname(os.path.abspath(__file__))
        self.auto_refresh_enabled = False
        self.scan_worker = None

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
        self.path_label = QLabel(f"当前目录: {self.current_path}")
        self.path_label.setWordWrap(True)
        self.select_button = QPushButton("选择目录")
        self.select_button.clicked.connect(self.select_directory)
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self.scan_directory)
        
        toolbar_layout.addWidget(self.path_label)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.select_button)
        toolbar_layout.addWidget(self.refresh_button)
        main_layout.addWidget(toolbar)

        # Scroll Area for cards
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.card_container = QWidget()
        self.card_layout = QVBoxLayout(self.card_container)
        self.card_layout.setAlignment(Qt.AlignTop)
        
        self.scroll_area.setWidget(self.card_container)
        main_layout.addWidget(self.scroll_area)

    def select_directory(self):
        path = QFileDialog.getExistingDirectory(self, "选择目录", self.current_path)
        if path:
            self.current_path = path
            self.scan_directory()

    def scan_directory(self):
        if self.scan_worker and self.scan_worker.isRunning():
            return # Don't start a new scan if one is already running

        self.path_label.setText(f"正在扫描: {self.current_path}...")
        self.select_button.setEnabled(False)
        self.refresh_button.setEnabled(False)

        # Clear old cards before starting scan
        self.clear_cards()

        self.scan_worker = ScanWorker(self.current_path, self.channel_suffixes)
        self.scan_worker.scan_complete.connect(self.on_scan_complete)
        self.scan_worker.start()

    def on_scan_complete(self, tree_data):
        self.path_label.setText(f"当前目录: {self.current_path}")
        self.select_button.setEnabled(True)
        self.refresh_button.setEnabled(True)
        
        sorted_sequences = sorted(tree_data.items(), key=lambda item: item[0])

        for seq_name, data in sorted_sequences:
            if data['frames']: # Only show sequences with frames
                card = SequenceCard(seq_name, data)
                self.card_layout.addWidget(card)
        
        self.scan_worker = None

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

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        painter.fillRect(self.rect(), QColor("#333"))

        if self.total_frames <= 0:
            return

        if self.total_frames <= width: # Draw individual blocks
            block_width = width / self.total_frames
            for i in range(self.total_frames):
                frame_num = self.min_frame + i
                if frame_num in self.found_frames:
                    painter.fillRect(int(i * block_width), 0, int(block_width) + 1, height, QColor("#4CAF50"))
        else: # Draw segments
            for i in range(width):
                frame_start = self.min_frame + int(i * self.total_frames / width)
                frame_end = self.min_frame + int((i + 1) * self.total_frames / width)
                found = any(f in self.found_frames for f in range(frame_start, frame_end))
                if found:
                    painter.setPen(QColor("#4CAF50"))
                    painter.drawPoint(i, height // 2)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_win = QMainWindow()
    viewer_widget = SequenceViewerWidget()
    main_win.setCentralWidget(viewer_widget)
    main_win.setWindowTitle("PNG 序列查看器 (独立运行)")
    main_win.setGeometry(200, 200, 900, 700)
    main_win.show()
    sys.exit(app.exec())
