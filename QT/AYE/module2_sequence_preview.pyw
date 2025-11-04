# -*- coding: utf-8 -*-
"""
Module 2: 序列预览播放器 (Sequence Preview Player)
功能: PNG 序列查看器 - 支持展开/收缩、图像预览、滑块控制、自动播放

创建日期: 2025-10-30
版本: 1.3
修复: 移除拖动功能，保留展开/收缩状态管理
"""
import sys
import os
import re
import subprocess
from collections import defaultdict
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QGridLayout, QFileDialog, QSlider,
    QLineEdit, QSpinBox, QSizePolicy, QCheckBox, QDoubleSpinBox, QDialog
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QPropertyAnimation, QEasingCurve, QSize, QRect
from PySide6.QtGui import QPainter, QColor, QFont, QPalette, QPixmap, QCursor
from pathlib import Path



class ElidedLabel(QLabel):
    """单行省略号标签，避免自动换行为两行。"""
    def __init__(self, text="", parent=None, mode=Qt.ElideRight):
        super().__init__(text, parent)
        self._full_text = text
        self._elide_mode = mode
        self.setWordWrap(False)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        if text:
            self.setToolTip(text)

    def setText(self, text):
        # 存储完整文本并更新提示
        self._full_text = text
        if text:
            self.setToolTip(text)
        self._update_elide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_elide()

    def setElideMode(self, mode):
        self._elide_mode = mode
        self._update_elide()

    def _update_elide(self):
        # 使用当前字体度量，按控件宽度生成省略文本
        fm = self.fontMetrics()
        available = max(0, self.width())
        elided = fm.elidedText(self._full_text or "", self._elide_mode, available)
        # 调用父类 setText，避免递归
        super().setText(elided)

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
        
        # 添加标志防止在动画进行中再次触发
        self._animation_in_progress = False

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
        # 如果动画正在进行中，忽略此次点击
        if self._animation_in_progress:
            # 恢复按钮状态到之前的状态
            self.toggle_button.blockSignals(True)
            self.toggle_button.setChecked(not checked)
            self.toggle_button.blockSignals(False)
            return
        
        self._animation_in_progress = True
        self.update_arrow(checked)
        
        # Calculate the content height at the moment of toggling
        # 临时移除高度限制以获取实际内容高度
        self.content_area.setMaximumHeight(16777215)  # 16777215 是 Qt 默认的最大高度
        content_height = self.content_area.sizeHint().height()
        
        # 确保计算出有效的高度
        if content_height <= 0:
            content_height = 200  # 默认最小高度
        
        self.toggle_animation.setStartValue(self.content_area.height())
        if checked:
            self.toggle_animation.setEndValue(content_height)
        else:
            self.toggle_animation.setEndValue(0)
        
        # 连接动画完成信号以解除动画进行中的标志
        self.toggle_animation.finished.connect(self._on_animation_finished)
        self.toggle_animation.start()

    def _on_animation_finished(self):
        """动画完成时的回调"""
        self._animation_in_progress = False
        # 如果是收缩状态，确保最大高度被重置为 0
        if not self.toggle_button.isChecked():
            self.content_area.setMaximumHeight(0)
        # 断开连接以避免重复调用
        try:
            self.toggle_animation.finished.disconnect(self._on_animation_finished)
        except:
            pass

    def update_arrow(self, checked):
        arrow = "▼" if checked else "►"
        self.toggle_button.setText(f"{arrow} 设置")

    def cleanup(self):
        """清理动画和信号连接"""
        # 停止动画
        if hasattr(self, 'toggle_animation') and self.toggle_animation.state() == self.toggle_animation.Running:
            self.toggle_animation.stop()
        
        # 断开动画完成信号
        try:
            self.toggle_animation.finished.disconnect(self._on_animation_finished)
        except:
            pass
        
        # 断开按钮点击信号
        try:
            self.toggle_button.clicked.disconnect(self.toggle)
        except:
            pass

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
        
        # 实时播放相关设置
        self.realtime_playback_enabled = False
        self.realtime_target_fps = 24.0  # 目标帧率（实际播放时的FPS）
        
        # 状态保存用于模块切换时的恢复
        self._saved_state = {
            'card_states': {},  # 保存每张卡片的展开状态和高度
            'scroll_position': 0,  # 保存滚动条位置
        }
        # 首次显示标志
        self._first_show = True

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

        # Realtime Playback Settings
        # 复选框、帧率在同一行
        playback_container = QWidget()
        playback_layout = QHBoxLayout(playback_container)
        playback_layout.setContentsMargins(0, 0, 0, 0)
        playback_layout.setSpacing(10)
        
        self.realtime_playback_checkbox = QCheckBox("启用实时播放")
        self.realtime_playback_checkbox.setChecked(self.realtime_playback_enabled)
        self.realtime_playback_checkbox.stateChanged.connect(self.update_realtime_playback_enabled)
        playback_layout.addWidget(self.realtime_playback_checkbox)
        
        # 目标帧率输入
        fps_label = QLabel("目标帧率:")
        playback_layout.addWidget(fps_label)
        self.realtime_fps_spinbox = QDoubleSpinBox()
        self.realtime_fps_spinbox.setRange(0.1, 300.0)
        self.realtime_fps_spinbox.setValue(self.realtime_target_fps)
        self.realtime_fps_spinbox.setSingleStep(1.0)
        self.realtime_fps_spinbox.setDecimals(1)
        self.realtime_fps_spinbox.setSuffix(" fps")
        self.realtime_fps_spinbox.valueChanged.connect(self.update_realtime_fps)
        playback_layout.addWidget(self.realtime_fps_spinbox)
        playback_layout.addStretch()
        
        settings_layout.addWidget(QLabel("播放设置:"), 5, 0)
        settings_layout.addWidget(playback_container, 5, 1, 1, 3)  # 跨3列

        self.collapsible_box.setContentLayout(settings_layout)
        main_layout.addWidget(self.collapsible_box)

        # Scroll Area for cards
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # 低存在感滚动条样式：透明背景、细窄、仅悬停时略微可见
        self.scroll_area.setStyleSheet(
            """
            QScrollBar:vertical {
                background: transparent;
                width: 8px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,40); /* 微弱可见 */
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(255,255,255,70);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
                border: none;
            }

            QScrollBar:horizontal {
                background: transparent;
                height: 8px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: rgba(255,255,255,40);
                border-radius: 4px;
                min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover {
                background: rgba(255,255,255,70);
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: transparent;
                border: none;
            }
            """
        )
        
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

        # 先断开旧的工作线程的连接
        if self.scan_worker is not None:
            try:
                self.scan_worker.scan_complete.disconnect(self.on_scan_complete)
            except:
                pass

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
                # 传递实时播放设置并更新控制条显示
                card.realtime_playback_enabled = self.realtime_playback_enabled
                card.realtime_target_fps = self.realtime_target_fps
                card.playback_control_bar.set_realtime_enabled(self.realtime_playback_enabled)
                card.playback_control_bar.set_fps(self.realtime_target_fps)
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

    def update_realtime_playback_enabled(self, state):
        """更新实时播放启用状态 - 覆盖所有卡片设置"""
        self.realtime_playback_enabled = self.realtime_playback_checkbox.isChecked()
        # 将设置传递给所有卡片
        for card in getattr(self, 'cards', []):
            card.realtime_playback_enabled = self.realtime_playback_enabled
            # 更新卡片控制条的显示
            card.playback_control_bar.set_realtime_enabled(self.realtime_playback_enabled)

    def update_realtime_fps(self, value):
        """更新目标帧率 - 覆盖所有卡片设置"""
        self.realtime_target_fps = value
        # 将设置传递给所有卡片
        for card in getattr(self, 'cards', []):
            card.realtime_target_fps = self.realtime_target_fps
            # 更新卡片控制条的显示
            card.playback_control_bar.set_fps(self.realtime_target_fps)
            # 如果正在播放，重新启动定时器以应用新的帧率
            if card.playback_enabled and card.playback_timer.isActive():
                card.playback_timer.stop()
                card.update_playback_timer_interval()
                card.playback_timer.start()

    def update_pixel_width(self, value):
        for card in getattr(self, 'cards', []):
            card.viz_widget.set_pixel_width(value)
        # 当宽度改变时，调整展开的卡片高度一次
        self._adjust_all_card_heights_once()

    def update_pixel_height(self, value):
        for card in getattr(self, 'cards', []):
            card.viz_widget.set_pixel_height(value)
        # 当高度改变时，调整展开的卡片高度一次
        self._adjust_all_card_heights_once()

    def _adjust_all_card_heights_once(self):
        """用户改变宽度/高度时，对所有展开的卡片进行一次性高度调整"""
        if not hasattr(self, 'cards'):
            return
        
        for card in self.cards:
            if card.is_expanded and not card.toggle_animation.isRunning():
                # 计算新的高度
                new_height = card._calculate_expand_height()
                current_h = card.content_widget.height()
                
                # 如果变化超过 10px，平滑过渡
                if abs(new_height - current_h) > 10:
                    card.toggle_animation.setStartValue(current_h)
                    card.toggle_animation.setEndValue(new_height)
                    card.toggle_animation.start()

    def clear_cards(self):
        # Remove all items from layout, including stretch
        while self.card_layout.count() > 0:
            item = self.card_layout.takeAt(0)
            widget = item.widget()
            spacer = item.spacerItem()
            
            if widget:
                # 如果是 SequenceCard，先清理资源
                if isinstance(widget, SequenceCard):
                    try:
                        widget.cleanup()
                    except Exception as e:
                        print(f"Error cleaning up card: {e}")
                widget.deleteLater()
            elif spacer:
                # 删除拉伸项，不需要特殊处理
                pass

    def toggle_auto_refresh(self, enabled):
        self.auto_refresh_enabled = enabled
        if self.auto_refresh_enabled:
            self.refresh_timer.start()
        else:
            self.refresh_timer.stop()

    def showEvent(self, event):
        """Override showEvent to refresh when the widget is shown."""
        super().showEvent(event)
        
        if self._first_show:
            # 首次显示时执行扫描
            self._first_show = False
            QTimer.singleShot(100, self.scan_directory)
        else:
            # 非首次显示，只恢复之前保存的状态，不重新扫描
            self._restore_state()

    def hideEvent(self, event):
        """Override hideEvent to save state and stop resources when hidden."""
        # 保存当前状态
        self._save_state()
        # 停止刷新定时器
        if hasattr(self, 'refresh_timer') and self.refresh_timer.isActive():
            self.refresh_timer.stop()
        super().hideEvent(event)

    def _save_state(self):
        """保存当前模块的状态（展开卡片、滚动位置等）"""
        # 保存实时播放设置
        self._saved_state['realtime_playback_enabled'] = self.realtime_playback_enabled
        self._saved_state['realtime_target_fps'] = self.realtime_target_fps
        
        # 保存滚动条位置
        if hasattr(self, 'scroll_area') and self.scroll_area.verticalScrollBar():
            self._saved_state['scroll_position'] = self.scroll_area.verticalScrollBar().value()
        
        # 保存每张卡片的展开状态、配置和播放状态
        if hasattr(self, 'cards'):
            for card in self.cards:
                card_name = card.name
                self._saved_state['card_states'][card_name] = {
                    'is_expanded': card.is_expanded,
                    'max_height': card.content_widget.maximumHeight(),
                    'current_frame': card.current_frame_index if hasattr(card, 'current_frame_index') else 0,
                    'is_playing': card.playback_enabled if hasattr(card, 'playback_enabled') else False,
                    # 保存每张卡片的独立实时播放配置
                    'realtime_enabled': card.realtime_playback_enabled if hasattr(card, 'realtime_playback_enabled') else False,
                    'realtime_fps': card.realtime_target_fps if hasattr(card, 'realtime_target_fps') else 24.0,
                }
                # 停止播放
                if hasattr(card, 'playback_enabled') and card.playback_enabled:
                    card.stop_playback()
                # 停止定时器
                if hasattr(card, 'size_monitor_timer') and card.size_monitor_timer.isActive():
                    card.size_monitor_timer.stop()

    def _restore_state(self):
        """恢复之前保存的状态"""
        if not hasattr(self, 'cards'):
            return
        
        # 恢复实时播放设置
        saved_realtime_enabled = self._saved_state.get('realtime_playback_enabled', False)
        saved_realtime_fps = self._saved_state.get('realtime_target_fps', 24.0)
        
        if hasattr(self, 'realtime_playback_checkbox'):
            self.realtime_playback_checkbox.setChecked(saved_realtime_enabled)
        if hasattr(self, 'realtime_fps_spinbox'):
            self.realtime_fps_spinbox.setValue(saved_realtime_fps)
        
        self.realtime_playback_enabled = saved_realtime_enabled
        self.realtime_target_fps = saved_realtime_fps
        
        # 恢复滚动条位置
        if hasattr(self, 'scroll_area') and self.scroll_area.verticalScrollBar():
            saved_pos = self._saved_state.get('scroll_position', 0)
            # 延迟一点时间以确保 UI 完全刷新
            QTimer.singleShot(50, lambda: self.scroll_area.verticalScrollBar().setValue(saved_pos))
        
        # 恢复卡片状态（不触发动画，仅恢复数据）
        card_states = self._saved_state.get('card_states', {})
        for card in self.cards:
            card_name = card.name
            if card_name in card_states:
                state = card_states[card_name]
                was_expanded = state.get('is_expanded', False)
                saved_height = state.get('max_height', 0)
                saved_frame = state.get('current_frame', 0)
                was_playing = state.get('is_playing', False)
                # 恢复卡片的独立配置
                saved_realtime_enabled = state.get('realtime_enabled', False)
                saved_realtime_fps = state.get('realtime_fps', 24.0)
                
                # 恢复卡片的独立实时播放配置
                card.realtime_playback_enabled = saved_realtime_enabled
                card.realtime_target_fps = saved_realtime_fps
                
                # 更新控制条的显示
                card.playback_control_bar.set_realtime_enabled(saved_realtime_enabled)
                card.playback_control_bar.set_fps(saved_realtime_fps)
                
                # 直接恢复卡片的内部状态，不触发动画
                card.is_expanded = was_expanded
                
                if was_expanded:
                    # 恢复为展开状态
                    card.content_widget.setMaximumHeight(saved_height if saved_height > 0 else 16777215)
                    card.size_monitor_timer.start()
                    
                    # 恢复预览帧显示
                    if len(card.all_frame_files) > 0 and not card.preview_label.pixmap():
                        card.display_frame(saved_frame)
                    
                    # 恢复播放状态
                    if was_playing and len(card.all_frame_files) > 0:
                        card.playback_control_bar.set_playing(True)
                        card.playback_enabled = True
                        card.last_frame_time = 0.0  # 重置计时
                        if not card.playback_timer.isActive():
                            card.update_playback_timer_interval()
                            card.playback_timer.start()
                else:
                    # 保持收缩状态
                    card.content_widget.setMaximumHeight(0)
                    card.size_monitor_timer.stop()

    def closeEvent(self, event):
        # 清理折叠框
        if hasattr(self, 'collapsible_box'):
            self.collapsible_box.cleanup()
        
        # 清理所有卡片
        self.clear_cards()
        
        # 停止刷新定时器
        if hasattr(self, 'refresh_timer'):
            self.refresh_timer.stop()
        
        # 停止扫描线程
        if self.scan_worker and self.scan_worker.isRunning():
            self.scan_worker.stop()
            self.scan_worker.wait() # Wait for thread to finish
        super().closeEvent(event)


class FpsInputDialog(QDialog):
    """FPS 输入对话框"""
    def __init__(self, current_fps=24.0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置目标帧率")
        self.setModal(True)
        self.setMinimumWidth(300)
        
        layout = QVBoxLayout(self)
        
        # 标签
        label = QLabel("输入目标帧率 (0.1 - 300.0):")
        layout.addWidget(label)
        
        # FPS输入框
        self.fps_input = QDoubleSpinBox()
        self.fps_input.setRange(0.1, 300.0)
        self.fps_input.setValue(current_fps)
        self.fps_input.setSingleStep(1.0)
        self.fps_input.setDecimals(1)
        self.fps_input.setSuffix(" fps")
        layout.addWidget(self.fps_input)
        
        # 按钮
        button_layout = QHBoxLayout()
        ok_button = QPushButton("确定")
        cancel_button = QPushButton("取消")
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
    
    def get_fps(self):
        return self.fps_input.value()


class PlaybackControlBar(QWidget):
    """自定义播放控制条：包括播放按钮、实时播放按钮、FPS输入框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 播放控制相关属性
        self.is_playing = False
        self.realtime_enabled = False
        self.target_fps = 24.0
        
        # 创建主布局
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 左部分：播放/暂停按钮（只显示符号，更窄）
        self.play_button = QPushButton("▶")
        self.play_button.setCheckable(True)
        self.play_button.setMaximumWidth(32)
        self.play_button.setMinimumHeight(24)
        self.play_button.setFlat(False)  # 确保有正常的按钮外观
        self.play_button.toggled.connect(self._on_play_toggled)  # 使用 toggled 信号
        self.play_button.clicked.connect(self._on_play_clicked)
        self.play_button.setToolTip("播放/暂停")
        main_layout.addWidget(self.play_button)
        
        # 中间部分：实时播放按钮（R）
        self.realtime_button = QPushButton("R")
        self.realtime_button.setCheckable(True)
        self.realtime_button.setMaximumWidth(32)
        self.realtime_button.setMinimumHeight(24)
        self.realtime_button.clicked.connect(self._on_realtime_clicked)
        self.realtime_button.setToolTip("启用实时播放模式")
        main_layout.addWidget(self.realtime_button)
        
        # 右侧部分：FPS输入框（直接编辑，无弹窗）
        self.fps_edit = QLineEdit(f"{self.target_fps:.1f}")
        self.fps_edit.setMaximumWidth(50)
        self.fps_edit.setMinimumHeight(24)
        self.fps_edit.setAlignment(Qt.AlignCenter)
        self.fps_edit.setEnabled(False)  # 默认禁用
        self.fps_edit.returnPressed.connect(self._on_fps_edited)
        self.fps_edit.setToolTip("输入目标帧率（仅在启用实时播放时可用）")
        main_layout.addWidget(self.fps_edit)
    
    def _on_play_clicked(self):
        """播放按钮点击事件"""
        self.is_playing = self.play_button.isChecked()
    
    def _on_play_toggled(self, checked):
        """播放按钮状态切换事件 - 负责更新显示文本"""
        self.is_playing = checked
        if checked:
            self.play_button.setText("‖")  # 暂停符号 - 单竖线
        else:
            self.play_button.setText("▶")  # 播放符号
    
    def _on_realtime_clicked(self):
        """实时播放按钮点击事件"""
        self.realtime_enabled = self.realtime_button.isChecked()
        self.fps_edit.setEnabled(self.realtime_enabled)
    
    def _on_fps_edited(self):
        """FPS输入框回车事件 - 直接在框内编辑"""
        try:
            fps = float(self.fps_edit.text())
            self.target_fps = max(0.1, min(300.0, fps))
            self.fps_edit.setText(f"{self.target_fps:.1f}")
        except ValueError:
            # 如果输入无效，恢复之前的值
            self.fps_edit.setText(f"{self.target_fps:.1f}")
    
    def set_fps(self, fps):
        """设置FPS值"""
        self.target_fps = max(0.1, min(300.0, fps))
        self.fps_edit.setText(f"{self.target_fps:.1f}")
    
    def set_realtime_enabled(self, enabled):
        """设置实时播放启用状态"""
        self.realtime_enabled = enabled
        self.realtime_button.setChecked(enabled)
        self.fps_edit.setEnabled(enabled)
    
    def get_realtime_enabled(self):
        """获取实时播放启用状态"""
        return self.realtime_enabled
    
    def get_fps(self):
        """获取FPS值"""
        return self.target_fps
    
    def set_playing(self, playing):
        """设置播放状态"""
        self.is_playing = playing
        self.play_button.setChecked(playing)
        if playing:
            self.play_button.setText("‖")  # 暂停符号
        else:
            self.play_button.setText("▶")  # 播放符号
    
    def is_playing_state(self):
        """获取播放状态"""
        return self.is_playing


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
        
        # 实时播放相关设置
        self.realtime_playback_enabled = False
        self.realtime_target_fps = 24.0
        self.last_frame_time = 0.0  # 用于计算跳帧
        
        self.setup_ui()
        self.setup_animation()
        
        # Playback timer
        self.playback_timer = QTimer(self)
        self.playback_timer.timeout.connect(self.advance_frame)
        
        # 大小改变监听定时器 - 用于即时更新预览
        self.size_monitor_timer = QTimer(self)
        self.size_monitor_timer.setSingleShot(False)
        self.size_monitor_timer.setInterval(200)  # 改为 200ms（原为 30ms），减少频率防止抖动
        self.size_monitor_timer.timeout.connect(self.check_preview_label_size)
        self.pending_refresh = False  # 防抖标志
        
        # 防止重复切换的标志
        self._toggle_in_progress = False

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
        self._toggle_in_progress = False
        if not self.is_expanded:
            # 收缩时重置最大高度为 0
            self.content_widget.setMaximumHeight(0)
        else:
            # 展开完成后，移除最大高度限制以允许拖拽
            self.content_widget.setMaximumHeight(16777215)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        # 关键：不要设置 SetMinimumSize，让卡片正常伸展
        # main_layout.setSizeConstraint(QVBoxLayout.SetMinimumSize)  # 注释掉
        
        # Header (clickable)
        self.header_widget = QFrame()
        self.header_widget.setCursor(Qt.PointingHandCursor)
        header_layout = QHBoxLayout(self.header_widget)
        header_layout.setContentsMargins(4, 4, 4, 4)

        name_label = ElidedLabel(self.name)
        # 使用粗体以替代富文本 <b>，避免影响省略计算
        f = name_label.font()
        f.setBold(True)
        name_label.setFont(f)
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
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(4)
        
        # 使用新的自定义播放控制条
        self.playback_control_bar = PlaybackControlBar()
        self.playback_control_bar.play_button.clicked.connect(self.toggle_playback)
        self.playback_control_bar.realtime_button.clicked.connect(self.on_realtime_button_clicked)
        self.playback_control_bar.fps_edit.returnPressed.connect(self.on_fps_edited)
        self.playback_control_bar.play_button.setEnabled(len(self.all_frame_files) > 0)
        
        # 播放控制条不拉伸，始终靠左
        controls_layout.addWidget(self.playback_control_bar, 0)
        
        # Frame slider - 占用所有剩余空间
        self.frame_slider = QSlider(Qt.Horizontal)
        self.frame_slider.setMinimum(0)
        max_slider = max(0, len(self.all_frame_files) - 1)
        self.frame_slider.setMaximum(max_slider)
        self.frame_slider.sliderMoved.connect(self.on_slider_moved)
        self.frame_slider.setEnabled(len(self.all_frame_files) > 0)
        controls_layout.addWidget(self.frame_slider, 1)
        
        # Frame number label - 固定宽度，靠右
        self.frame_number_label = QLabel("0/0")
        self.frame_number_label.setMinimumWidth(60)
        self.frame_number_label.setAlignment(Qt.AlignCenter)
        self.frame_number_label.setStyleSheet("QLabel { font-size: 9pt; }")
        controls_layout.addWidget(self.frame_number_label, 0)
        
        content_layout.addLayout(controls_layout)
        
        # 将 Content widget 添加到主布局，但不会压缩上面的区域
        main_layout.addWidget(self.content_widget)
        
        # 初始设置 content_widget 的最大高度为 0（默认关闭）
        # 展开时会自动计算所需高度
        self.content_widget.setMaximumHeight(0)
        
        # Connect header click
        self.header_widget.mousePressEvent = self.toggle_expanded

    def toggle_expanded(self, event):
        """Toggle expanded state"""
        # 如果正在进行切换动画，忽略本次点击
        if self._toggle_in_progress:
            return
        
        self._toggle_in_progress = True
        self.is_expanded = not self.is_expanded
        if self.is_expanded:
            # 首次展开需要初始化预览；再次展开保持当前帧
            if len(self.all_frame_files) > 0 and not self.preview_label.pixmap():
                self.display_frame(0)
            # 展开时启动大小监听
            self.size_monitor_timer.start()
        else:
            # 收缩时停止大小监听和自动调整
            self.size_monitor_timer.stop()
            self.stop_playback()
        self.update_animation()

    def _calculate_expand_height(self):
        """计算合理的展开高度"""
        # 获取预览标签的当前宽度，用于计算缩放高度
        label_width = self.preview_label.width()
        if label_width <= 0:
            label_width = 300  # 默认宽度
        
        # 如果有缓存的图片，根据其显示高度计算
        if hasattr(self, '_cached_pixmap') and self._cached_pixmap and not self._cached_pixmap.isNull():
            pixmap = self._cached_pixmap
            pixmap_width = pixmap.width()
            pixmap_height = pixmap.height()
            
            if pixmap_width > 0:
                # 按实际显示宽度计算缩放后的高度
                scale_ratio = label_width / pixmap_width
                img_display_height = pixmap_height * scale_ratio
            else:
                img_display_height = 200
        else:
            img_display_height = 200
        
        # 控制条高度约 60px（播放按钮+滑块+间距+padding）
        control_height = 60
        # 内容区域的上下 padding
        padding = 20
        
        total_height = img_display_height + control_height + padding
        # 范围：最小 300px，最大窗口高度的 80%，给设置栏和其他留空间
        min_h = 300
        max_h = 800  # 限制最大高度防止过大
        return max(min_h, min(max_h, total_height))

    def check_preview_label_size(self):
        """检查预览标签大小是否改变，刷新预览但不调整高度"""
        if not self.is_expanded or not self.preview_label.pixmap():
            return
        
        current_size = (self.preview_label.width(), self.preview_label.height())
        
        # 只有当大小真正改变了，且不在处理中时，才刷新预览（但不调整高度）
        if self.last_preview_label_size != current_size and not self.pending_refresh:
            self.last_preview_label_size = current_size
            self.pending_refresh = True
            # 标签尺寸改变时，重新渲染预览（缩放图片以适应新宽度）
            QTimer.singleShot(100, self._refresh_preview_for_size_change)

    def _refresh_preview_for_size_change(self):
        """标签尺寸改变时重新渲染预览"""
        if not self.is_expanded or not self.preview_label.pixmap():
            self.pending_refresh = False
            return
        
        # 仅刷新预览显示，不改变卡片高度（防止抖动）
        try:
            self.display_frame(self.current_frame_index)
        finally:
            self.pending_refresh = False

    def update_animation(self):
        """Update expand/collapse animation"""
        # 若有正在运行的动画，先停止，避免状态错乱
        if self.toggle_animation.state() == QPropertyAnimation.Running:
            self.toggle_animation.stop()

        self.toggle_animation.setStartValue(self.content_widget.height())
        if self.is_expanded:
            # 计算合理的展开高度
            target_height = self._calculate_expand_height()
            # 立即移除高度限制，允许拖拽自由调整
            # 不要再次设置最大高度限制，让其保持之前拖拽的值或最大值
            if self.content_widget.maximumHeight() < target_height:
                self.content_widget.setMaximumHeight(16777215)
            self.toggle_animation.setEndValue(target_height)
        else:
            # 收缩时不需要改最大高度，动画会自然结束
            self.toggle_animation.setEndValue(0)
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
        # 从控制条中获取状态
        self.playback_enabled = self.playback_control_bar.is_playing
        
        if self.playback_enabled:
            if len(self.all_frame_files) > 0 and not self.playback_timer.isActive():
                self.last_frame_time = 0.0  # 重置计时
                self.update_playback_timer_interval()
                self.playback_timer.start()
        else:
            self.stop_playback()

    def on_realtime_button_clicked(self):
        """实时播放按钮点击事件"""
        self.realtime_playback_enabled = self.playback_control_bar.get_realtime_enabled()
        # 如果正在播放，更新定时器间隔
        if self.playback_enabled and self.playback_timer.isActive():
            self.playback_timer.stop()
            self.last_frame_time = 0.0
            self.update_playback_timer_interval()
            self.playback_timer.start()

    def on_fps_edited(self):
        """FPS输入框编辑事件"""
        # 更新本卡片的FPS设置
        self.realtime_target_fps = self.playback_control_bar.get_fps()
        # 如果正在播放，更新定时器间隔
        if self.playback_enabled and self.playback_timer.isActive():
            self.playback_timer.stop()
            self.last_frame_time = 0.0
            self.update_playback_timer_interval()
            self.playback_timer.start()

    def update_playback_timer_interval(self):
        """根据实时播放设置更新定时器间隔"""
        if self.realtime_playback_enabled and self.realtime_target_fps > 0:
            # 实时播放模式：每帧的时间间隔（毫秒）
            interval = int(1000.0 / self.realtime_target_fps)
        else:
            # 普通播放模式
            interval = self.playback_speed
        self.playback_timer.setInterval(interval)

    def stop_playback(self):
        """Stop playback"""
        self.playback_enabled = False
        self.playback_control_bar.set_playing(False)
        if self.playback_timer.isActive():
            self.playback_timer.stop()

    def advance_frame(self):
        """Advance to next frame"""
        if not self.playback_enabled or not self.all_frame_files:
            return
        
        sorted_frames = sorted(self.all_frame_files.keys())
        
        if self.realtime_playback_enabled and self.realtime_target_fps > 0:
            # 实时播放模式：根据目标FPS计算跳帧
            import time
            current_time = time.time()
            
            if self.last_frame_time == 0.0:
                # 首次调用
                self.last_frame_time = current_time
                elapsed = 0.0
            else:
                elapsed = current_time - self.last_frame_time
                self.last_frame_time = current_time
            
            # 根据实际间隔计算应该跳过多少帧
            # 例如：目标24fps，实际过了50ms，那应该前进2帧
            frame_duration = 1.0 / self.realtime_target_fps
            frames_to_advance = max(1, int(round(elapsed / frame_duration)))
            
            next_index = (self.current_frame_index + frames_to_advance) % len(sorted_frames)
            self.display_frame(next_index)
        else:
            # 普通播放模式：每次前进一帧
            next_index = (self.current_frame_index + 1) % len(sorted_frames)
            self.display_frame(next_index)

    def cleanup(self):
        """清理所有资源和定时器"""
        # 停止所有定时器
        if hasattr(self, 'size_monitor_timer') and self.size_monitor_timer.isActive():
            self.size_monitor_timer.stop()
        if hasattr(self, 'playback_timer') and self.playback_timer.isActive():
            self.playback_timer.stop()
        
        # 停止所有动画
        if hasattr(self, 'toggle_animation') and self.toggle_animation.state() == self.toggle_animation.Running:
            self.toggle_animation.stop()
        
        # 断开所有信号连接
        try:
            if hasattr(self, 'size_monitor_timer'):
                self.size_monitor_timer.timeout.disconnect()
        except:
            pass
        try:
            if hasattr(self, 'playback_timer'):
                self.playback_timer.timeout.disconnect()
        except:
            pass
        try:
            if hasattr(self, 'toggle_animation'):
                self.toggle_animation.finished.disconnect()
        except:
            pass
        
        # 清理缓存的像素图
        self._cached_pixmap = None

    def closeEvent(self, event):
        """关闭时清理定时器"""
        self.cleanup()
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
