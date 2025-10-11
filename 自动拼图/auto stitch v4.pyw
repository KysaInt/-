"""
自动图片拼接工具 v4.0
使用 OpenCV Stitcher - 成熟稳定的拼接库
"""

import sys
import os
from pathlib import Path
from typing import List, Optional
import cv2
import numpy as np
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QLabel, QLineEdit, 
                               QFileDialog, QProgressBar, QTextEdit, QMessageBox,
                               QScrollArea, QGroupBox, QComboBox, QTableWidget,
                               QTableWidgetItem, QHeaderView, QSpinBox, QCheckBox,
                               QAbstractItemView, QToolButton)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QImage


class ImageStitcher:
    """使用 OpenCV Stitcher 进行图片拼接"""
    
    def __init__(self, mode='scans'):
        """
        mode: 'scans' 适合扫描/截图（更精确）
              'panorama' 适合全景照片
        """
        self.mode = mode
        
    def load_images(self, directory: str) -> List[str]:
        """加载目录下的所有图片"""
        supported_formats = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp']
        image_files = []
        
        for root, _, files in os.walk(directory):
            for file in sorted(files):
                if Path(file).suffix.lower() in supported_formats:
                    image_files.append(os.path.join(root, file))
        
        return image_files
    
    def stitch_images(self, image_paths: List[str], progress_callback=None) -> Optional[np.ndarray]:
        """拼接图片"""
        if not image_paths:
            return None
        
        # 加载所有图片
        images = []
        for i, path in enumerate(image_paths):
            if progress_callback:
                progress_callback(i + 1, len(image_paths), f"加载图片: {Path(path).name}")
            
            try:
                with open(path, 'rb') as f:
                    img_bytes = f.read()
                img_array = np.frombuffer(img_bytes, dtype=np.uint8)
                img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                
                if img is not None:
                    images.append(img)
                else:
                    if progress_callback:
                        progress_callback(i + 1, len(image_paths), 
                                        f"警告: 无法解码 {Path(path).name}")
            except Exception as e:
                if progress_callback:
                    progress_callback(i + 1, len(image_paths), 
                                    f"警告: 加载失败 {Path(path).name}")
        
        if not images:
            return None
        
        if len(images) == 1:
            return images[0]
        
        if progress_callback:
            progress_callback(0, 100, f"开始拼接 {len(images)} 张图片...")
        
        # 创建 Stitcher
        if self.mode == 'scans':
            # SCANS 模式：适合扫描文档、截图等
            stitcher = cv2.Stitcher_create(cv2.Stitcher_SCANS)
        else:
            # PANORAMA 模式：适合全景照片
            stitcher = cv2.Stitcher_create(cv2.Stitcher_PANORAMA)
        
        if progress_callback:
            progress_callback(50, 100, "执行拼接算法...")
        
        # 执行拼接
        try:
            status, result = stitcher.stitch(images)
            
            if status == cv2.Stitcher_OK:
                if progress_callback:
                    progress_callback(100, 100, "拼接成功！")
                return result
            else:
                error_messages = {
                    cv2.Stitcher_ERR_NEED_MORE_IMGS: "需要更多图片",
                    cv2.Stitcher_ERR_HOMOGRAPHY_EST_FAIL: "单应性估计失败 - 图片间可能没有足够重叠",
                    cv2.Stitcher_ERR_CAMERA_PARAMS_ADJUST_FAIL: "相机参数调整失败"
                }
                error_msg = error_messages.get(status, f"拼接失败，错误码: {status}")
                if progress_callback:
                    progress_callback(100, 100, error_msg)
                return None
                
        except Exception as e:
            if progress_callback:
                progress_callback(100, 100, f"拼接过程出错: {str(e)}")
            return None


class StitchThread(QThread):
    """拼接工作线程"""
    progress = Signal(int, int, str)
    finished = Signal(object)
    error = Signal(str)
    
    def __init__(self, directory: str, mode: str = 'scans', image_paths: Optional[List[str]] = None):
        super().__init__()
        self.directory = directory
        self.mode = mode
        self.stitcher = ImageStitcher(mode=mode)
        self.image_paths = image_paths or []
    
    def run(self):
        """执行拼接任务"""
        try:
            self.progress.emit(0, 100, "扫描目录...")
            image_paths = list(self.image_paths) if self.image_paths else self.stitcher.load_images(self.directory)
            
            if not image_paths:
                self.error.emit("未在目录中找到图片文件")
                return
            
            self.progress.emit(0, 100, f"找到 {len(image_paths)} 张图片")
            
            result = self.stitcher.stitch_images(
                image_paths,
                progress_callback=self.progress.emit
            )
            
            if result is not None:
                self.finished.emit(result)
            else:
                self.error.emit("拼接失败：OpenCV Stitcher 未能找到图片间的关联\n\n可能原因：\n1. 图片间重叠不足\n2. 图片质量差异过大\n3. 图片间没有共同特征\n\n建议：\n- 确保相邻图片有30%以上重叠\n- 尝试切换拼接模式\n- 减少图片数量进行测试")
                
        except Exception as e:
            self.error.emit(f"拼接过程出错: {str(e)}")


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.result_image = None
        self.stitch_thread = None
        self._thumb_size = 100
        self._image_rows = []  # list of dicts: {path, selected, order, marked, thumb}
        self.init_ui()
        
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("自动图片拼接工具 v4.0 - OpenCV Stitcher")
        self.setMinimumSize(900, 700)
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # 目录选择
        dir_group = QGroupBox("1. 选择图片目录")
        dir_layout = QHBoxLayout()
        
        self.dir_edit = QLineEdit()
        self.dir_edit.setPlaceholderText("请选择包含要拼接图片的目录...")
        dir_layout.addWidget(self.dir_edit)
        
        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.clicked.connect(self.browse_directory)
        dir_layout.addWidget(self.browse_btn)
        
        dir_group.setLayout(dir_layout)
        layout.addWidget(dir_group)
        
        # 参数设置
        param_group = QGroupBox("2. 拼接模式")
        param_layout = QHBoxLayout()
        
        param_layout.addWidget(QLabel("模式选择:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "扫描模式（截图/文档）- 推荐",
            "全景模式（照片）"
        ])
        self.mode_combo.setCurrentIndex(0)
        self.mode_combo.setToolTip(
            "扫描模式: 适合屏幕截图、扫描文档，更精确的对齐\n"
            "全景模式: 适合风景照片，允许更多的视角变化"
        )
        param_layout.addWidget(self.mode_combo)
        
        param_layout.addStretch()
        param_group.setLayout(param_layout)
        layout.addWidget(param_group)
        
        # 说明
        info_group = QGroupBox("💡 使用提示")
        info_layout = QVBoxLayout()
        info_label = QLabel(
            "• OpenCV Stitcher 是业界标准的图像拼接库\n"
            "• 自动检测特征点并精确对齐\n"
            "• 确保相邻图片有 30% 以上的重叠区域\n"
            "• 截图请选择「扫描模式」，照片请选择「全景模式」"
        )
        info_label.setWordWrap(True)
        info_layout.addWidget(info_label)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # 图片预览与选择
        preview_select_group = QGroupBox("4. 图片预览与选择")
        preview_select_layout = QVBoxLayout()

        # 缩放控制与统计
        top_bar = QHBoxLayout()
        self.selection_summary_label = QLabel("未加载目录")
        top_bar.addWidget(self.selection_summary_label)
        top_bar.addStretch()
        top_bar.addWidget(QLabel("缩放:"))
        # 比例显示 + 滑条控件
        self.thumb_size_label = QLabel("100%")
        top_bar.addWidget(self.thumb_size_label)
        from PySide6.QtWidgets import QSlider
        self.thumb_slider = QSlider(Qt.Horizontal)
        self.thumb_slider.setMinimum(50)
        self.thumb_slider.setMaximum(300)
        self.thumb_slider.setValue(self._thumb_size)
        self.thumb_slider.setToolTip("调整预览缩略图大小 (Ctrl+滚轮 也可缩放)")
        self.thumb_slider.valueChanged.connect(self._on_thumb_size_changed)
        top_bar.addWidget(self.thumb_slider)
        preview_select_layout.addLayout(top_bar)

        # 预览表格
        self.image_table = self._create_image_table()
        preview_select_layout.addWidget(self.image_table)

        # 操作按钮
        ops_bar = QHBoxLayout()
        self.btn_select_all = QPushButton("全选")
        self.btn_select_none = QPushButton("全不选")
        self.btn_invert = QPushButton("反选")
        self.btn_auto_order = QPushButton("按名称自动编号")
        self.btn_clear_order = QPushButton("清除序号")
        self.btn_select_all.clicked.connect(self._select_all)
        self.btn_select_none.clicked.connect(self._select_none)
        self.btn_invert.clicked.connect(self._invert_selection)
        self.btn_auto_order.clicked.connect(self._auto_order_by_name)
        self.btn_clear_order.clicked.connect(self._clear_order)
        for b in (self.btn_select_all, self.btn_select_none, self.btn_invert, self.btn_auto_order, self.btn_clear_order):
            ops_bar.addWidget(b)
        ops_bar.addStretch()
        preview_select_layout.addLayout(ops_bar)

        preview_select_group.setLayout(preview_select_layout)
        layout.addWidget(preview_select_group)

        # 控制按钮
        control_group = QGroupBox("3. 执行拼接")
        control_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("🚀 开始拼接")
        self.start_btn.clicked.connect(self.start_stitching)
        self.start_btn.setMinimumHeight(40)
        self.start_btn.setStyleSheet("font-size: 14px; font-weight: bold;")
        control_layout.addWidget(self.start_btn)
        
        self.save_btn = QPushButton("💾 保存结果")
        self.save_btn.clicked.connect(self.save_result)
        self.save_btn.setEnabled(False)
        self.save_btn.setMinimumHeight(40)
        self.save_btn.setStyleSheet("font-size: 14px; font-weight: bold;")
        control_layout.addWidget(self.save_btn)
        
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid grey;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # 日志
        log_group = QGroupBox("📋 处理日志")
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(120)
        log_layout.addWidget(self.log_text)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        # 预览
        preview_group = QGroupBox("🖼️ 结果预览")
        preview_layout = QVBoxLayout()
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(300)
        
        self.preview_label = QLabel("拼接结果将显示在这里")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("""
            QLabel { 
                background-color: #f5f5f5; 
                border: 2px dashed #ccc;
                padding: 20px;
                color: #666;
                font-size: 14px;
            }
        """)
        
        scroll_area.setWidget(self.preview_label)
        preview_layout.addWidget(scroll_area)
        
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)
        
        self.log("✅ 程序已启动 - 使用 OpenCV Stitcher 专业拼接引擎")
        self.log("📖 OpenCV Stitcher 是成熟稳定的图像拼接解决方案")

    # ============ 预览表格与缩放 ============
    def _create_image_table(self) -> QTableWidget:
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(["序号", "预览", "文件名", "选择", "标记"])
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setAlternatingRowColors(True)

        # Ctrl+滚轮缩放
        table.wheelEvent = self._make_ctrl_wheel_zoom(table.wheelEvent)
        return table

    def _make_ctrl_wheel_zoom(self, original_handler):
        def handler(event):
            if event.modifiers() & Qt.ControlModifier:
                delta = event.angleDelta().y()
                step = 10 if delta > 0 else -10
                new_val = max(50, min(300, self.thumb_slider.value() + step))
                if new_val != self.thumb_slider.value():
                    self.thumb_slider.setValue(new_val)
                event.accept()
            else:
                original_handler(event)
        return handler

    def _on_thumb_size_changed(self, value: int):
        self._thumb_size = value
        self.thumb_size_label.setText(f"{value}%")
        # 更新已有缩略图尺寸
        for row in range(self.image_table.rowCount()):
            label = self.image_table.cellWidget(row, 1)
            if isinstance(label, QLabel) and label.pixmap() is not None:
                orig_pix: QPixmap = label.pixmap()
                # 由于label里存的是缩略图，再放大缩小影响清晰度；这里重新生成
                path = self.image_table.item(row, 2).data(Qt.UserRole) if self.image_table.item(row, 2) else None
                if path and os.path.exists(path):
                    pix = QPixmap(path)
                    if not pix.isNull():
                        thumb = pix.scaled(self._thumb_size, self._thumb_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        label.setPixmap(thumb)
                        label.setFixedSize(self._thumb_size+8, self._thumb_size+8)
        self.image_table.resizeRowsToContents()

    def _update_summary(self):
        total = self.image_table.rowCount()
        selected = 0
        for r in range(total):
            cb = self.image_table.cellWidget(r, 3)
            if isinstance(cb, QCheckBox) and cb.isChecked():
                selected += 1
        self.selection_summary_label.setText(f"已加载: {total} 张 | 已选择: {selected} 张")

    def _select_all(self):
        for r in range(self.image_table.rowCount()):
            cb = self.image_table.cellWidget(r, 3)
            if isinstance(cb, QCheckBox):
                cb.setChecked(True)
        self._update_summary()

    def _select_none(self):
        for r in range(self.image_table.rowCount()):
            cb = self.image_table.cellWidget(r, 3)
            if isinstance(cb, QCheckBox):
                cb.setChecked(False)
        self._update_summary()

    def _invert_selection(self):
        for r in range(self.image_table.rowCount()):
            cb = self.image_table.cellWidget(r, 3)
            if isinstance(cb, QCheckBox):
                cb.setChecked(not cb.isChecked())
        self._update_summary()

    def _auto_order_by_name(self):
        # 取已选行按文件名排序后从1开始编号
        rows = []
        for r in range(self.image_table.rowCount()):
            cb = self.image_table.cellWidget(r, 3)
            name_item = self.image_table.item(r, 2)
            if isinstance(cb, QCheckBox) and cb.isChecked() and name_item:
                rows.append((r, name_item.text()))
        rows.sort(key=lambda x: x[1].lower())
        for idx, (r, _) in enumerate(rows, start=1):
            spin = self.image_table.cellWidget(r, 0)
            if isinstance(spin, QSpinBox):
                spin.setValue(idx)

    def _clear_order(self):
        for r in range(self.image_table.rowCount()):
            spin = self.image_table.cellWidget(r, 0)
            if isinstance(spin, QSpinBox):
                spin.setValue(0)

    def _load_images_for_preview(self, directory: str):
        # 清空表格
        self.image_table.setRowCount(0)
        stitcher = ImageStitcher()
        paths = stitcher.load_images(directory)
        for path in paths:
            self._add_image_row(path)
        self._update_summary()

    def _add_image_row(self, path: str):
        row = self.image_table.rowCount()
        self.image_table.insertRow(row)

        # 序号（执行顺序）
        spin = QSpinBox()
        spin.setRange(0, 9999)
        spin.setValue(0)
        spin.setToolTip("执行序号（从1开始，0表示未指定）")
        self.image_table.setCellWidget(row, 0, spin)

        # 预览
        thumb_label = QLabel()
        thumb_label.setAlignment(Qt.AlignCenter)
        pix = QPixmap(path)
        if not pix.isNull():
            thumb = pix.scaled(self._thumb_size, self._thumb_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            thumb_label.setPixmap(thumb)
            thumb_label.setFixedSize(self._thumb_size+8, self._thumb_size+8)
        self.image_table.setCellWidget(row, 1, thumb_label)

        # 文件名（存路径在UserRole）
        name_item = QTableWidgetItem(os.path.basename(path))
        name_item.setData(Qt.UserRole, path)
        self.image_table.setItem(row, 2, name_item)

        # 选择
        cb = QCheckBox()
        cb.setChecked(False)
        cb.stateChanged.connect(lambda _=None: self._update_summary())
        cb.setToolTip("选中后只处理打勾的图片；如全部未选，则默认处理全部")
        self.image_table.setCellWidget(row, 3, cb)

        # 标记（星标）
        mark_btn = QToolButton()
        mark_btn.setCheckable(True)
        mark_btn.setText("☆")
        mark_btn.setToolTip("标记/取消标记")
        def _toggle_mark(checked, btn=mark_btn):
            btn.setText("★" if checked else "☆")
        mark_btn.toggled.connect(_toggle_mark)
        self.image_table.setCellWidget(row, 4, mark_btn)

        self.image_table.resizeRowToContents(row)
    
    def log(self, message: str):
        """添加日志"""
        self.log_text.append(message)
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )
    
    def browse_directory(self):
        """浏览选择目录"""
        directory = QFileDialog.getExistingDirectory(
            self, "选择图片目录", 
            self.dir_edit.text() or str(Path.home())
        )
        if directory:
            self.dir_edit.setText(directory)
            self.log(f"📁 已选择目录: {directory}")
            self._load_images_for_preview(directory)
    
    def start_stitching(self):
        """开始拼接"""
        directory = self.dir_edit.text().strip()
        
        if not directory:
            QMessageBox.warning(self, "警告", "请先选择图片目录")
            return
        
        if not os.path.isdir(directory):
            QMessageBox.warning(self, "警告", "选择的目录不存在")
            return
        
        self.start_btn.setEnabled(False)
        self.browse_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.mode_combo.setEnabled(False)
        
        self.preview_label.setText("⏳ 正在处理，请稍候...")
        self.preview_label.setStyleSheet("""
            QLabel { 
                background-color: #fff3cd; 
                border: 2px solid #ffc107;
                padding: 20px;
                color: #856404;
                font-size: 14px;
            }
        """)
        self.result_image = None
        
        mode_index = self.mode_combo.currentIndex()
        mode = 'scans' if mode_index == 0 else 'panorama'
        mode_name = "扫描模式" if mode == 'scans' else "全景模式"
        
        # 读取用户选择
        selected_paths = []
        ordered = []  # (order, index, path)
        for r in range(self.image_table.rowCount()):
            name_item = self.image_table.item(r, 2)
            path = name_item.data(Qt.UserRole) if name_item else None
            if not path:
                continue
            cb = self.image_table.cellWidget(r, 3)
            spin = self.image_table.cellWidget(r, 0)
            order_val = spin.value() if isinstance(spin, QSpinBox) else 0
            checked = cb.isChecked() if isinstance(cb, QCheckBox) else False
            if checked:
                selected_paths.append(path)
                ordered.append((order_val if order_val > 0 else 999999, r, path))

        image_paths_for_job: List[str]
        if selected_paths:
            # 若有序号，按序号升序；未设序号的排在后面并按行号排序
            ordered.sort(key=lambda t: (t[0], t[1]))
            image_paths_for_job = [p for (_, _, p) in ordered]
        else:
            # 未选择则默认处理全部（按显示顺序）
            image_paths_for_job = []
            for r in range(self.image_table.rowCount()):
                name_item = self.image_table.item(r, 2)
                path = name_item.data(Qt.UserRole) if name_item else None
                if path:
                    image_paths_for_job.append(path)

        if not image_paths_for_job:
            QMessageBox.warning(self, "警告", "目录中未找到可处理的图片")
            self.start_btn.setEnabled(True)
            self.browse_btn.setEnabled(True)
            self.mode_combo.setEnabled(True)
            return

        self.stitch_thread = StitchThread(directory, mode, image_paths=image_paths_for_job)
        self.stitch_thread.progress.connect(self.on_progress)
        self.stitch_thread.finished.connect(self.on_finished)
        self.stitch_thread.error.connect(self.on_error)
        self.stitch_thread.start()
        
        self.log("="*60)
        self.log(f"🚀 开始拼接处理... (模式: {mode_name})")
    
    def on_progress(self, current: int, total: int, message: str):
        """更新进度"""
        if total > 0:
            progress = int((current / total) * 100)
            self.progress_bar.setValue(progress)
        self.log(message)
    
    def on_finished(self, result: np.ndarray):
        """拼接完成"""
        self.result_image = result
        self.display_result(result)
        
        self.start_btn.setEnabled(True)
        self.browse_btn.setEnabled(True)
        self.save_btn.setEnabled(True)
        self.mode_combo.setEnabled(True)
        
        h, w = result.shape[:2]
        self.log(f"✅ 拼接成功！结果尺寸: {w} x {h} 像素")
        self.log("="*60)
        
        self.preview_label.setStyleSheet("""
            QLabel { 
                background-color: #f5f5f5; 
                border: 2px solid #4CAF50;
            }
        """)
        
        QMessageBox.information(
            self, 
            "✅ 成功", 
            f"图片拼接完成！\n\n结果尺寸: {w} x {h} 像素\n\n请查看预览并保存结果。"
        )
    
    def on_error(self, error_message: str):
        """处理错误"""
        self.log(f"❌ 错误: {error_message}")
        self.log("="*60)
        
        self.start_btn.setEnabled(True)
        self.browse_btn.setEnabled(True)
        self.mode_combo.setEnabled(True)
        
        self.preview_label.setText("❌ 拼接失败")
        self.preview_label.setStyleSheet("""
            QLabel { 
                background-color: #f8d7da; 
                border: 2px solid #dc3545;
                padding: 20px;
                color: #721c24;
                font-size: 14px;
            }
        """)
        self.progress_bar.setValue(0)
        
        QMessageBox.critical(self, "❌ 错误", error_message)
    
    def display_result(self, image: np.ndarray):
        """显示结果图片"""
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        
        pixmap = QPixmap.fromImage(qt_image)
        max_width = 850
        max_height = 500
        
        if w > max_width or h > max_height:
            pixmap = pixmap.scaled(max_width, max_height, 
                                  Qt.KeepAspectRatio, 
                                  Qt.SmoothTransformation)
        
        self.preview_label.setPixmap(pixmap)
        self.preview_label.resize(pixmap.size())
    
    def save_result(self):
        """保存结果"""
        if self.result_image is None:
            QMessageBox.warning(self, "警告", "没有可保存的结果")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存拼接结果", 
            str(Path.home() / "stitched_result.png"),
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.tiff)"
        )
        
        if file_path:
            try:
                ext = Path(file_path).suffix.lower()
                if ext in ['.jpg', '.jpeg']:
                    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 95]
                    success, encoded_img = cv2.imencode('.jpg', self.result_image, encode_param)
                elif ext == '.png':
                    encode_param = [int(cv2.IMWRITE_PNG_COMPRESSION), 3]
                    success, encoded_img = cv2.imencode('.png', self.result_image, encode_param)
                elif ext == '.bmp':
                    success, encoded_img = cv2.imencode('.bmp', self.result_image)
                elif ext in ['.tiff', '.tif']:
                    success, encoded_img = cv2.imencode('.tiff', self.result_image)
                else:
                    success, encoded_img = cv2.imencode('.png', self.result_image)
                
                if success:
                    with open(file_path, 'wb') as f:
                        f.write(encoded_img.tobytes())
                    
                    self.log(f"💾 结果已保存到: {file_path}")
                    QMessageBox.information(
                        self, 
                        "✅ 成功", 
                        f"图片已成功保存到:\n\n{file_path}"
                    )
                else:
                    raise Exception("图片编码失败")
            except Exception as e:
                self.log(f"❌ 保存失败: {str(e)}")
                QMessageBox.critical(self, "错误", f"保存失败:\n{str(e)}")


def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
