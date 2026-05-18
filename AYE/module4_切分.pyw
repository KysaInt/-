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

        # 简单日志缓存（未来可替换为QTextEdit显示）
        self._last_message = ""

    def log(self, msg: str):
        self._last_message = msg
        print(msg)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        # 先创建“切分设置”折叠面板（放置路径行）
        self.split_box = CollapsibleBox("切分设置", default_open=True, expand_flex=False)
        from PySide6.QtWidgets import QVBoxLayout as _QVBL, QHBoxLayout as _QHBL
        split_layout = _QVBL()
        split_layout.setContentsMargins(4, 4, 4, 4)
        split_layout.setSpacing(4)

        # 行1：预览目录 + 预览按钮
        row1 = _QHBL()
        self.path_edit = QLineEdit(self.current_path)
        self.path_edit.returnPressed.connect(self.path_edited)
        self.select_button = QPushButton("预览目录")
        self.select_button.clicked.connect(self.select_directory)
        row1.addWidget(self.path_edit, 1)
        row1.addWidget(self.select_button)
        split_layout.addLayout(row1)

        # 行2：输出目录 + 选择按钮
        row2 = _QHBL()
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText("输出目录（未选择）")
        self.output_dir_edit.setReadOnly(True)
        self.unified_output_dir_btn = QPushButton("输出目录")
        self.unified_output_dir_btn.clicked.connect(self.choose_unified_output_dir)
        row2.addWidget(self.output_dir_edit, 1)
        row2.addWidget(self.unified_output_dir_btn)
        split_layout.addLayout(row2)

        # 行3：切分方法 + 片段数 + 刷新按钮（右侧）
        row3 = _QHBL()
        row3.addWidget(QLabel("切分方法:"))
        self.split_method_combo = QComboBox()
        self.split_method_combo.addItems(["默认切分模式", "字幕时间切分", "音频响度切分"])
        self.split_method_combo.currentIndexChanged.connect(self.split_method_changed)
        row3.addWidget(self.split_method_combo)
        self.segment_count_label = QLabel("片段数:")
        self.segment_count_spin = QSpinBox()
        self.segment_count_spin.setRange(2, 1000)
        self.segment_count_spin.setValue(3)
        row3.addWidget(self.segment_count_label)
        row3.addWidget(self.segment_count_spin)
        row3.addStretch()
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self.scan_directory)
        row3.addWidget(self.refresh_button)
        split_layout.addLayout(row3)

        # 行4：输出类型复选框
        row4 = _QHBL()
        self.segment_output_checkbox = QCheckBox("片段输出")
        self.segment_output_checkbox.setChecked(True)
        self.segment_output_checkbox.stateChanged.connect(self.output_mode_changed)
        self.custom_output_checkbox = QCheckBox("组合输出")
        self.custom_output_checkbox.stateChanged.connect(self.custom_output_toggled)
        row4.addWidget(self.segment_output_checkbox)
        row4.addWidget(self.custom_output_checkbox)
        row4.addStretch()
        split_layout.addLayout(row4)

        # 行5：组合模式
        row5 = _QHBL()
        self.custom_pattern_label = QLabel("组合:")
        self.custom_pattern_edit = QLineEdit()
        self.custom_pattern_edit.setPlaceholderText("例如: ABAB 或 ACBA ...")
        row5.addWidget(self.custom_pattern_label)
        row5.addWidget(self.custom_pattern_edit, 1)
        split_layout.addLayout(row5)

        # 行6：前缀
        row6 = _QHBL()
        self.custom_prefix_label = QLabel("前缀:")
        self.custom_prefix_edit = QLineEdit()
        row6.addWidget(self.custom_prefix_label)
        row6.addWidget(self.custom_prefix_edit, 1)
        split_layout.addLayout(row6)

        # 行7：执行按钮（全宽）
        self.execute_output_btn = QPushButton("执行")
        self.execute_output_btn.clicked.connect(self.execute_outputs)
        self.execute_output_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        split_layout.addWidget(self.execute_output_btn)

        # 组合输出复用统一输出目录
        self.custom_output_dir = ''

        # 初始禁用自定义输出子控件
        for w in [self.custom_pattern_label, self.custom_pattern_edit,
                  self.custom_prefix_label, self.custom_prefix_edit]:
            w.setEnabled(False)

        self.split_box.setContentLayout(split_layout)
        main_layout.addWidget(self.split_box)

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
        self.custom_output_toggled(self.custom_output_checkbox.checkState())

        # 主序列折叠面板 (可扩展填充)
        self.sequence_box = CollapsibleBox("主序列", default_open=True, expand_flex=True)
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

    def split_method_changed(self, index):
        method = self.split_method_combo.currentText()
        enable_equal = (method == "默认切分模式")
        # 仅控制片段数相关控件使能，不隐藏其它按钮
        self.segment_count_label.setEnabled(enable_equal)
        self.segment_count_spin.setEnabled(enable_equal)
        # 组合输入启用仍只由“组合输出”复选框决定，不受模式影响
        self.custom_output_toggled(self.custom_output_checkbox.checkState())
        self.update_execute_button_state()
        self.log(f"[切分模式切换] 当前模式: {method}, 片段数启用={enable_equal}")

    def compute_equal_splits(self):
        """基于当前选择卡片和片段数，返回 {card: [(code, [frame_numbers])...]}
        使用实际存在的帧号列表来分块，避免用缺失帧填充。"""
        result = {}
        if not self.selected_cards_order:
            return result
        segs = self.segment_count_spin.value()
        for seq_idx, card in enumerate(self.selected_cards_order):
            frames = sorted(list(card.data['frames']))
            if not frames:
                continue
            # 均分算法基于帧列表长度
            total = len(frames)
            base = total // segs
            remainder = total % segs
            segments = []
            start_index = 0
            for i in range(segs):
                length = base + (1 if i < remainder else 0)
                part_frames = frames[start_index:start_index+length]
                start_index += length
                code = f"{card.order_code}{i+1}" if card.order_code else f"{seq_idx+1}-{i+1}"
                segments.append((code, part_frames))
            result[card] = segments
        return result

    def choose_equal_split_output_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择切分输出目录", self.current_path)
        if path:
            self.equal_split_output_dir = path
            self.equal_split_output_dir_btn.setText(os.path.basename(path))
    
    # ===== 统一输出目录相关新增方法 =====
    def choose_unified_output_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择输出目录", getattr(self, 'unified_output_dir', self.current_path))
        if path:
            self.unified_output_dir = path
            self.unified_output_dir_btn.setText(os.path.basename(path))
            if hasattr(self, 'output_dir_edit'):
                self.output_dir_edit.setText(path)
        self.update_execute_button_state()

    def open_unified_output_dir(self):
        if hasattr(self, 'unified_output_dir') and self.unified_output_dir and os.path.isdir(self.unified_output_dir):
            try:
                os.startfile(self.unified_output_dir)
            except Exception as e:
                self.log(f"打开目录失败: {e}")
        else:
            self.log("尚未选择有效的输出目录。")

    def update_execute_button_state(self):
        has_dir = hasattr(self, 'unified_output_dir') and bool(self.unified_output_dir)
        any_mode = self.segment_output_checkbox.isChecked() or self.custom_output_checkbox.isChecked()
        self.execute_output_btn.setEnabled(has_dir and any_mode)

    def perform_equal_split(self):
        # 检查模式
        if self.split_method_combo.currentText() != "默认切分模式":
            self.log("请先选择 '默认切分模式' 并设置片段数。")
            return
        splits = self.compute_equal_splits()
        if not splits:
            self.log("没有可用的切分结果，请先选择序列。")
            return
        output_dir = getattr(self, 'unified_output_dir', None)
        if not output_dir:
            self.log("请选择输出目录。")
            return
        # 构建帧文件索引函数（与自定义输出类似）
        def build_frame_index(card):
            index = {}
            base_dir = card.data.get('path')
            if not base_dir or not os.path.isdir(base_dir):
                return index
            for fname in os.listdir(base_dir):
                if not fname.lower().endswith('.png'):
                    continue
                m = re.match(r'(.+?)[._]?(\d+)\.png$', fname, re.IGNORECASE)
                if not m:
                    continue
                frame_num = int(m.group(2))
                if frame_num in card.data['frames']:
                    index[frame_num] = os.path.join(base_dir, fname)
            return index

        # 统计总帧数用于进度
        total_frames_to_copy = sum(len(frame_list) for segs in splits.values() for _, frame_list in segs)
        dlg = QProgressDialog("正在执行切分...", "取消", 0, total_frames_to_copy, self)
        dlg.setWindowTitle("切分进度")
        dlg.setAutoClose(True)
        dlg.setAutoReset(True)
        copied = 0
        for card, segs in splits.items():
            frame_index = build_frame_index(card)
            for (code, frame_list) in segs:
                target_dir = os.path.join(self.equal_split_output_dir, code)
                target_dir = os.path.join(output_dir, code)
                os.makedirs(target_dir, exist_ok=True)
                for frame_num in frame_list:
                    if dlg.wasCanceled():
                        self.log("切分已取消。")
                        return
                    src = frame_index.get(frame_num)
                    if not src:
                        self.log(f"警告: 缺失帧 {frame_num} (序列 {card.name})")
                        continue
                    out_name = f"{code}_{frame_num:04d}.png"
                    dst = os.path.join(target_dir, out_name)
                    try:
                        with open(src, 'rb') as fsrc, open(dst, 'wb') as fdst:
                            fdst.write(fsrc.read())
                    except Exception as e:
                        self.log(f"复制帧失败 {src} -> {dst}: {e}")
                    copied += 1
                    if copied % 10 == 0 or copied == total_frames_to_copy:
                        dlg.setValue(copied)
                        dlg.setLabelText(f"复制中... {copied}/{total_frames_to_copy}")
                        QApplication.processEvents()
        dlg.setValue(total_frames_to_copy)
        self.log("默认切分模式执行完成。")

    def custom_output_toggled(self, state):
        widgets = [
            self.custom_pattern_label, self.custom_pattern_edit,
            self.custom_prefix_label, self.custom_prefix_edit
        ]
        enabled = (state == Qt.Checked)
        for w in widgets:
            if w:
                w.setEnabled(enabled)
        self.log(f"[组合输出UI] 勾选状态={state}, 已启用={enabled}")
        self.update_execute_button_state()

    def output_mode_changed(self, state):
        # 片段输出复选框变更，仅需要刷新执行按钮可用状态
        self.update_execute_button_state()

    def choose_custom_output_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择输出目录", self.current_path)
        if path:
            self.custom_output_dir = path
            self.custom_output_dir_btn.setText(os.path.basename(path))

    def perform_custom_output(self):
        if not self.custom_output_checkbox.isChecked():
            return
        pattern = self.custom_pattern_edit.text().strip().upper()
        prefix = self.custom_prefix_edit.text().strip()
        if not pattern:
            self.log("请输入组合文本模式 (例如 ABAB)")
            return
        if not prefix:
            self.log("请输入前缀。")
            return
        if self.split_method_combo.currentText() != "默认切分模式":
            self.log("组合输出仅支持 '默认切分模式'")
            return
        splits = self.compute_equal_splits()
        if not splits:
            self.log("没有可用的切分数据。")
            return
        output_dir = getattr(self, 'unified_output_dir', None)
        if not output_dir:
            self.log("请选择输出目录。")
            return
        def build_frame_index(card):
            index = {}
            base_dir = card.data.get('path')
            if not base_dir or not os.path.isdir(base_dir):
                return index
            for fname in os.listdir(base_dir):
                if not fname.lower().endswith('.png'): continue
                m = re.match(r'(.+?)[._]?(\d+)\.png$', fname, re.IGNORECASE)
                if not m: continue
                frame_num = int(m.group(2))
                if frame_num in card.data['frames']:
                    index[frame_num] = os.path.join(base_dir, fname)
            return index
        letter_map = {}
        for card, segs in splits.items():
            for idx, (code, frame_list) in enumerate(segs):
                if not card.order_code:
                    continue
                letter = card.order_code
                letter_map.setdefault(letter, []).append((idx, frame_list, card))
        for k in letter_map:
            letter_map[k].sort(key=lambda x: x[0])
        combined_frames = []
        letter_occurrence = {}
        for pos, ch in enumerate(pattern):
            if ch not in letter_map:
                self.log(f"模式字母 {ch} 不在已选序列中，跳过。")
                continue
            occ = letter_occurrence.get(ch, 0)
            letter_occurrence[ch] = occ + 1
            candidates = letter_map[ch]
            if occ >= len(candidates):
                self.log(f"字母 {ch} 的第 {occ+1} 次片段不存在，跳过。")
                continue
            _, frame_list, card = candidates[occ]
            frame_index = build_frame_index(card)
            for frame_num in frame_list:
                src = frame_index.get(frame_num)
                if src:
                    combined_frames.append(src)
        if not combined_frames:
            self.log("组合结果为空。")
            return
        pattern_tag = pattern
        target_folder = os.path.join(output_dir, f"{prefix}_{pattern_tag}")
        os.makedirs(target_folder, exist_ok=True)
        dlg = QProgressDialog("正在执行组合输出...", "取消", 0, len(combined_frames), self)
        dlg.setWindowTitle("组合输出进度")
        dlg.setAutoClose(True)
        dlg.setAutoReset(True)
        for i, src in enumerate(combined_frames, start=1):
            if dlg.wasCanceled():
                self.log("组合输出已取消。")
                return
            ext = os.path.splitext(src)[1]
            dst_name = f"{prefix}_{pattern_tag}_{i:04d}{ext}"
            dst = os.path.join(target_folder, dst_name)
            try:
                shutil.copy2(src, dst)
            except Exception as e:
                self.log(f"复制失败 {src} -> {dst}: {e}")
            dlg.setValue(i)
        self.log("组合输出完成。")

    def execute_outputs(self):
        if not hasattr(self, 'unified_output_dir'):
            self.log("请先选择输出目录。")
            return
        ran_any = False
        if self.segment_output_checkbox.isChecked():
            self.perform_equal_split()
            ran_any = True
        if self.custom_output_checkbox.isChecked():
            self.perform_custom_output()
            ran_any = True
        if not ran_any:
            self.log("请勾选至少一种输出类型。")
        self.update_execute_button_state()
        # 验证前置条件（允许只要已选卡片并能计算切分即可，不再强制模式）
        splits = self.compute_equal_splits()
        if not splits:
            self.log("没有可用的切分结果，请先选择序列并设置片段数。")
            return
        pattern = self.custom_pattern_edit.text().strip().upper()
        if not pattern or not pattern.isalpha():
            self.log("组合文本需为字母，例如 ABAB。")
            return
        if not self.custom_output_dir:
            self.log("请选择输出目录。")
            return
        prefix = self.custom_prefix_edit.text().strip()
        # 建立字母 -> card 映射
        letter_map = {}
        for card in self.selected_cards_order:
            if not card.order_code:
                continue
            letter_map[card.order_code] = card
        # 检查 pattern 用到的字母是否存在
        for ch in pattern:
            if ch not in letter_map:
                print(f"模式字母 {ch} 不在当前选中序列中。")
                return
        # 生成输出根文件夹: 前缀_组合  (若无前缀则仅组合)
        folder_name = f"{prefix}_{pattern}" if prefix else f"{pattern}"
        target_root = os.path.join(self.custom_output_dir, folder_name)
        os.makedirs(target_root, exist_ok=True)

        # 收集卡片原始帧 -> 实际文件路径映射（逐目录扫描）
        # 为减少压力，仅当需要时针对每个卡片目录建立缓存
        def build_frame_index(card):
            index = {}
            base_dir = card.data.get('path')
            if not base_dir or not os.path.isdir(base_dir):
                return index
            for fname in os.listdir(base_dir):
                if not fname.lower().endswith('.png'):
                    continue
                m = re.match(r'(.+?)[._]?(\d+)\.png$', fname, re.IGNORECASE)
                if not m:
                    continue
                frame_num = int(m.group(2))
                if frame_num in card.data['frames']:
                    index[frame_num] = os.path.join(base_dir, fname)
            return index

        card_frame_index_cache = {}
        # 新规则：位置 -> 片段号
        # 例：A300帧, B30帧, 分成3段 (A1 A2 A3 / B1 B2 B3)
        # pattern = ABA (长度3) => A1 + B2 + A3
        # pattern = ABAB (长度4) 且分段数>=4 => A1 + B2 + A3 + B4
        # 因此要求: 分段数 >= pattern长度，否则无法满足位置映射
        segment_count = self.segment_count_spin.value()
        if segment_count < len(pattern):
            self.log(f"片段数({segment_count}) 小于组合长度({len(pattern)})，无法按位置映射。")
            return
        all_segments = self.compute_equal_splits()  # {card: [(code, [frames])...]}
        output_sequence_counter = 0
        for pos, ch in enumerate(pattern, start=1):
            card = letter_map[ch]
            seg_list = all_segments.get(card, [])
            if pos > len(seg_list):
                self.log(f"字母 {ch} 需要第 {pos} 段，但只有 {len(seg_list)} 段，跳过。")
                continue
            code, frame_list = seg_list[pos-1]
            if card not in card_frame_index_cache:
                card_frame_index_cache[card] = build_frame_index(card)
            frame_index = card_frame_index_cache[card]
            frames_range = [f for f in frame_list if f in frame_index]
            for fnum in frames_range:
                src = frame_index[fnum]
                output_sequence_counter += 1
                # 文件命名: 前缀_组合_帧号(4位) ；若无前缀则 组合_帧号
                base_prefix = f"{prefix}_{pattern}" if prefix else f"{pattern}"
                new_name = f"{base_prefix}_{output_sequence_counter:04d}.png"
                dst = os.path.join(target_root, new_name)
                try:
                    with open(src, 'rb') as rf, open(dst, 'wb') as wf:
                        wf.write(rf.read())
                except Exception as e:
                    self.log(f"复制 {src} 失败: {e}")
        self.log(f"自定义输出完成: {output_sequence_counter} 帧 写入 {target_root}")

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
