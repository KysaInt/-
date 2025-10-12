"""
自动图片拼接工具 v4.0
使用 OpenCV Stitcher - 成熟稳定的拼接库
"""

import sys
import os
from pathlib import Path
from datetime import datetime
from typing import List, Optional
import cv2
import numpy as np
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QLabel, QLineEdit, 
                               QFileDialog, QProgressBar, QTextEdit, QMessageBox,
                               QScrollArea, QGroupBox, QListWidget,
                               QListWidgetItem, QListView, QMenu, QInputDialog,
                               QSlider, QSizePolicy, QStyledItemDelegate, QFrame, QSplitter)
from PySide6.QtCore import Qt, QThread, Signal, QPoint, QSize, QRect, QPropertyAnimation, QEasingCurve, QUrl, QSettings
from PySide6.QtGui import QPixmap, QImage, QIcon, QAction, QPainter, QColor, QPen, QFont, QDesktopServices, QPalette

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

# 内嵌 fabric.png（Base64）
FABRIC_PNG_BASE64 = """
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
"""

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
                except Exception:
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
            try:
                hl = pal.color(pal.ColorRole.Highlight)
                htxt = pal.color(pal.ColorRole.HighlightedText)
                txt = pal.color(pal.ColorRole.ButtonText)
                mid = pal.color(pal.ColorRole.Mid)
            except Exception:
                hl = pal.highlight().color()  # type: ignore
                htxt = pal.highlightedText().color()  # type: ignore
                txt = pal.buttonText().color()  # type: ignore
                mid = pal.mid().color()  # type: ignore
            base_txt = f"rgb({txt.red()},{txt.green()},{txt.blue()})"
            h_rgb = f"rgb({hl.red()},{hl.green()},{hl.blue()})"
            h_txt = f"rgb({htxt.red()},{htxt.green()},{htxt.blue()})"
            mid_rgba = f"rgba({mid.red()},{mid.green()},{mid.blue()},120)"
            mid_hover = f"rgba({mid.red()},{mid.green()},{mid.blue()},40)"
            self.toggle_button.setStyleSheet(
                """
                QPushButton {
                    border: 1px solid %s;
                    border-radius: 4px;      /* 小圆角，更紧凑 */
                    padding: 2px 6px;        /* 仅比文字高一点 */
                    min-height: 20px;        /* 紧凑高度 */
                    background-color: transparent;
                    color: %s;
                    text-align: center;
                }
                QPushButton:hover {
                    background-color: %s;
                }
                QPushButton:checked {
                    background-color: %s;
                    border-color: %s;
                    color: %s;
                }
                """ % (mid_rgba, base_txt, mid_hover, h_rgb, h_rgb, h_txt)
            )

    # 1. 直接在顶部放置“设置”内容（扁平化，不再使用折叠面板）
    top_settings = QVBoxLayout()
    top_settings.setContentsMargins(8,8,8,0)
    top_settings.setSpacing(6)
    dir_row = QHBoxLayout()
    self.dir_edit = QLineEdit()
    self.dir_edit.setPlaceholderText("请选择包含要拼接图片的目录...")
    self.browse_btn = QPushButton("浏览...")
    self.browse_btn.setProperty("btn", "secondary")
    self.browse_btn.clicked.connect(self.browse_directory)
    dir_row.addWidget(QLabel("目录:"))
    dir_row.addWidget(self.dir_edit, 1)
    dir_row.addWidget(self.browse_btn)
    top_settings.addLayout(dir_row)
    # 同行按钮
    btn_row = QHBoxLayout()
    btn_row.setSpacing(6)
    self.start_btn = QPushButton("🚀 开始拼接")
    self.start_btn.clicked.connect(self.start_stitching)
# 紧凑：降低按钮最小高度
self.start_btn.setMinimumHeight(22)
    self.start_btn.setProperty("btn", "primary")
    self.start_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    btn_row.addWidget(self.start_btn, 1)
    top_settings.addLayout(btn_row)
    # 进度条
    self.progress_bar = QProgressBar()
    pal = self.palette()
    try:
        hl = pal.color(pal.ColorRole.Highlight)
    except Exception:
        hl = pal.highlight().color()  # type: ignore
    self.progress_bar.setStyleSheet(
        "QProgressBar { border: 1px solid palette(Mid); border-radius: 4px; text-align: center; min-height: 12px;}"
        f"QProgressBar::chunk {{ background-color: rgb({hl.red()},{hl.green()},{hl.blue()}); }}"
    )
    top_settings.addWidget(self.progress_bar)
    # 挂到主布局顶部
    layout.addLayout(top_settings)

    # 2. 图片预览与选择 / 结果预览（合并面板）
    preview_box = CollapsibleBox("预览", default_open=True, expand_flex=False)
    preview_select_layout = QVBoxLayout()
    preview_select_layout.setContentsMargins(8,8,8,8)
    preview_select_layout.setSpacing(6)

    # 顶行：统计 + 选择操作按钮（同一行）
    top_bar = QHBoxLayout()
    self.selection_summary_label = QLabel("未加载目录")
    top_bar.addWidget(self.selection_summary_label)
    top_bar.addStretch()
    self.btn_select_all = QPushButton("全选")
    self.btn_select_none = QPushButton("全不选")
    self.btn_invert = QPushButton("反选")
    for b in (self.btn_select_all, self.btn_select_none, self.btn_invert):
        b.setMinimumHeight(28)
        b.setProperty("btn", "secondary")
        top_bar.addWidget(b)
    preview_select_layout.addLayout(top_bar)

    # 第二行：缩放 + 打开输出目录
    zoom_row = QHBoxLayout()
    zoom_row.addWidget(QLabel("缩放:"))
    self.thumb_size_label = QLabel(f"{self._thumb_size}px")
    zoom_row.addWidget(self.thumb_size_label)
    self.thumb_slider = QSlider(Qt.Horizontal)
    self.thumb_slider.setMinimum(10)
    self.thumb_slider.setMaximum(300)
    self.thumb_slider.setValue(self._thumb_size)
    self.thumb_slider.setToolTip("调整预览缩略图大小 (Ctrl+滚轮 也可缩放)")
    self.thumb_slider.valueChanged.connect(self._on_thumb_size_changed)
    zoom_row.addWidget(self.thumb_slider, 1)
    self.open_output_btn = QPushButton("打开")
    self.open_output_btn.setProperty("btn", "secondary")
    self.open_output_btn.setToolTip("打开输出目录 (stitch)")
    self.open_output_btn.clicked.connect(self.open_output_dir)
    zoom_row.addWidget(self.open_output_btn)
    preview_select_layout.addLayout(zoom_row)

    # 预览：图标平铺（正方形体块）
    self.image_list = self._create_image_list()

    # 选择按钮连接
    self.btn_select_all.clicked.connect(self._select_all)
    self.btn_select_none.clicked.connect(self._select_none)
    self.btn_invert.clicked.connect(self._invert_selection)

    # 合并：结果预览区域（右侧，自动缩放，无滚动条）
    self.result_container = QWidget()
    self.result_container.setMinimumHeight(260)
    rc_layout = QVBoxLayout(self.result_container)
    rc_layout.setContentsMargins(0,0,0,0)
    rc_layout.setSpacing(0)
    self.preview_label = QLabel("拼接结果将显示在这里")
    self.preview_label.setAlignment(Qt.AlignCenter)
    # 使用当前主题的窗口背景色和中间色设置初始底色和边框，避免纯白
    pal = self.palette()
    try:
        win_col = pal.color(pal.ColorRole.Window)
        mid_col = pal.color(pal.ColorRole.Mid)
        txt_col = pal.color(pal.ColorRole.Text)
    except Exception:
        win_col = pal.window().color()  # type: ignore
        mid_col = pal.mid().color()  # type: ignore
        txt_col = pal.text().color()  # type: ignore
    self.preview_label.setStyleSheet(
        "QLabel { "
        f"background-color: rgb({win_col.red()},{win_col.green()},{win_col.blue()}); "
        f"border: 2px dashed rgb({mid_col.red()},{mid_col.green()},{mid_col.blue()}); "
        "padding: 16px; "
        f"color: rgb({txt_col.red()},{txt_col.green()},{txt_col.blue()}); "
        "font-size: 13px; }"
    )
    self.preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    rc_layout.addWidget(self.preview_label, 1)
    def _rc_resize(ev):
        QWidget.resizeEvent(self.result_container, ev)
        self._refresh_result_preview()
    self.result_container.resizeEvent = _rc_resize

    # 左右结构：左（缩略图+操作）| 分隔线 | 右（结果预览）
    content_row = QHBoxLayout()
    content_row.setSpacing(6)
    left_col = QVBoxLayout()
    left_col.addWidget(self.image_list, 1)
    content_row.addLayout(left_col, 1)
    divider = QFrame()
    divider.setFrameShape(QFrame.VLine)
    divider.setFrameShadow(QFrame.Plain)
    divider.setLineWidth(1)
    content_row.addWidget(divider)
    content_row.addWidget(self.result_container, 1)
    preview_select_layout.addLayout(content_row)

    # 双击打开：为缩略图列表启用双击打开文件
    self.image_list.itemDoubleClicked.connect(self._on_item_double_clicked)
preview_box.setContentLayout(preview_select_layout)

    # 3. 日志
    log_box = CollapsibleBox("日志", default_open=True, expand_flex=True)
    log_layout = QVBoxLayout()
    self.log_text = QTextEdit()
    self.log_text.setReadOnly(True)
    self.log_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    log_layout.addWidget(self.log_text)
log_box.setContentLayout(log_layout)

# 使用垂直分割器使预览与日志可上下拖动
self.main_splitter = QSplitter(Qt.Vertical)
self.main_splitter.addWidget(preview_box)
self.main_splitter.addWidget(log_box)
self.main_splitter.setStretchFactor(0, 1)
self.main_splitter.setStretchFactor(1, 2)
layout.addWidget(self.main_splitter, 1)

    # 首先把提示文字写入日志
    self.log("✅ 程序已启动 - 使用 OpenCV Stitcher 专业拼接引擎")
    self.log("💡 提示：")
    self.log("• Created by AYE | Version 1.0.0 | 2025-10-12")
    self.log("• OpenCV Stitcher 是业界标准的图像拼接库")
    self.log("• 自动检测特征点并精确对齐")
    self.log("• 确保相邻图片有 30% 以上的重叠区域")
    self.log("• 当前默认使用‘扫描模式’，适合截图/文档")

    # 外部底端弹簧：始终存在于所有面板之后，保证折叠时整体贴顶
    layout.addStretch(1)

# ——— 全局按钮样式（更紧凑的圆角、padding 与高度） ———
    pal = self.palette()
    try:
        bg = pal.color(pal.ColorRole.Window)
        txt = pal.color(pal.ColorRole.ButtonText)
        hi = pal.color(pal.ColorRole.Highlight)
    except Exception:
        bg = pal.window().color()  # type: ignore
        txt = pal.buttonText().color()  # type: ignore
        hi = pal.highlight().color()  # type: ignore
    base_txt = f"rgba({txt.red()},{txt.green()},{txt.blue()},255)"
    hi_rgb = f"rgb({hi.red()},{hi.green()},{hi.blue()})"
    hi_hover = f"rgba({hi.red()},{hi.green()},{hi.blue()},0.85)"
    hi_press = f"rgba({hi.red()},{hi.green()},{hi.blue()},0.7)"
    sec_bg = f"rgba({bg.red()},{bg.green()},{bg.blue()},0.6)"
    sec_bor = f"rgba({txt.red()},{txt.green()},{txt.blue()},80)"
    self.setStyleSheet(self.styleSheet() + f"""
        QPushButton[btn="primary"] {{
            color: white;
            background-color: {hi_rgb};
            border: 1px solid {hi_rgb};
            border-radius: 6px;
            padding: 3px 8px;
            min-height: 20px;
            font-weight: 600;
        }}
        QPushButton[btn="primary"]:hover {{
            background-color: {hi_hover};
            border-color: {hi_hover};
        }}
        QPushButton[btn="primary"]:pressed {{
            background-color: {hi_press};
            border-color: {hi_press};
        }}
        QPushButton[btn="primary"]:disabled {{
            background-color: rgba(180,180,180,0.5);
            border-color: rgba(160,160,160,0.4);
            color: rgba(255,255,255,0.8);
        }}

        QPushButton[btn="secondary"] {{
            color: {base_txt};
            background-color: {sec_bg};
            border: 1px solid {sec_bor};
            border-radius: 4px;
            padding: 3px 8px;
            min-height: 20px;
        }}
        QPushButton[btn="secondary"]:hover {{
            background-color: rgba(127,127,127,0.15);
        }}
        QPushButton[btn="secondary"]:pressed {{
            background-color: rgba(127,127,127,0.25);
        }}
""")

    # 恢复 UI 状态（分割器尺寸、折叠状态）
    self._restore_ui_state(preview_box, log_box)

def _restore_ui_state(self, preview_box: QWidget, log_box: QWidget):
    settings = QSettings("AYE", "AutoStitcher")
    sizes = settings.value("splitter/sizes")
    if isinstance(sizes, list) and all(isinstance(x, int) for x in sizes):
        self.main_splitter.setSizes(sizes)  # type: ignore[arg-type]
    else:
        self.main_splitter.setSizes([400, 360])

    prev_exp = settings.value("collapsible/preview", True, bool)
    log_exp = settings.value("collapsible/log", True, bool)
    # 应用折叠状态
    try:
        preview_box.toggle_button.setChecked(bool(prev_exp))
        preview_box._on_toggle(bool(prev_exp))
    except Exception:
        pass
    try:
        log_box.toggle_button.setChecked(bool(log_exp))
        log_box._on_toggle(bool(log_exp))
    except Exception:
        pass

    # 恢复缩略图大小（若存在）
    thumb = settings.value("thumb/size")
    if isinstance(thumb, int) and 10 <= thumb <= 300:
        self.thumb_slider.setValue(thumb)

def closeEvent(self, event):  # type: ignore[override]
    # 保存分割器尺寸与折叠状态、缩略图尺寸
    try:
        settings = QSettings("AYE", "AutoStitcher")
        settings.setValue("splitter/sizes", self.main_splitter.sizes())
        # 折叠状态：通过查找 splitter 中的两个 CollapsibleBox
        if self.main_splitter.count() >= 2:
            w0 = self.main_splitter.widget(0)
            w1 = self.main_splitter.widget(1)
            try:
                settings.setValue("collapsible/preview", bool(w0.toggle_button.isChecked()))
            except Exception:
                pass
            try:
                settings.setValue("collapsible/log", bool(w1.toggle_button.isChecked()))
            except Exception:
                pass
        # 缩略图尺寸
        try:
            settings.setValue("thumb/size", int(self.thumb_slider.value()))
        except Exception:
            pass
    finally:
        super().closeEvent(event)

# 底部弹簧已移至 init_ui 内部末尾，且日志面板设置了更高的伸展因子

# ============ 预览表格与缩放 ============
def _create_image_list(self) -> QListWidget:
    lw = QListWidget()
    lw.setViewMode(QListView.IconMode)
    lw.setIconSize(self._calc_icon_size())
    lw.setResizeMode(QListView.Adjust)
    lw.setMovement(QListView.Static)
    lw.setSpacing(2)
    lw.setUniformItemSizes(True)
    lw.setSelectionMode(QListWidget.MultiSelection)
    lw.setContextMenuPolicy(Qt.CustomContextMenu)
    lw.customContextMenuRequested.connect(self._on_list_context_menu)
    # Ctrl+滚轮缩放
    lw.wheelEvent = self._make_ctrl_wheel_zoom(lw.wheelEvent)
    # 选择变化时更新统计
    lw.itemSelectionChanged.connect(self._on_selection_changed)
    self._apply_list_grid(lw)
    # 自定义选中叠加序号
    lw.setItemDelegate(self.ThumbDelegate(self))
    return lw

def _calc_icon_size(self):
    # 允许最小到 10px，最大 512px
    s = max(10, min(512, self._thumb_size))
    return QSize(s, s)

def _apply_list_grid(self, lw: QListWidget):
    # 根据图标尺寸设置网格，尽量紧凑
    s = self._calc_icon_size().width()
    lw.setGridSize(QSize(s + 8, s + 8))

class ThumbDelegate(QStyledItemDelegate):
        def __init__(self, parent):
            super().__init__(parent)
            self.parent = parent
        def paint(self, painter: QPainter, option, index):
            # 自绘缩略图，保证在正方形单元内最大化适配（等比居中），并绘制选中序号
            painter.save()
            r = option.rect
            # 绘制背景（使用系统样式提供的背景，确保主题一致）
            # 不主动填充背景，交给视图样式；只绘制图片
            try:
                item = self.parent.image_list.item(index.row())
                icon = item.icon() if item is not None else QIcon()
            except Exception:
                icon = QIcon()
            # 目标边长（留出少量边距）
            side = min(r.width(), r.height()) - 8
            if side < 2:
                side = max(1, side)
            # 从图标获取较大底图，再二次等比缩放，避免锯齿
            base_pix = icon.pixmap(512, 512) if not icon.isNull() else QPixmap()
            if not base_pix.isNull():
                scaled = base_pix.scaled(side, side, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                x = r.x() + (r.width() - scaled.width()) // 2
                y = r.y() + (r.height() - scaled.height()) // 2
                painter.drawPixmap(x, y, scaled)
            painter.restore()
            # 选中项叠加大序号
            w: QListWidget = self.parent.image_list
            sel = w.selectionModel().selectedIndexes()
            if not sel:
                return
            sel_sorted = sorted(sel, key=lambda ix: ix.row())
            row_to_order = {ix.row(): i+1 for i, ix in enumerate(sel_sorted)}
            if index.row() not in row_to_order:
                return
            order = row_to_order[index.row()]
            r = option.rect
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing, True)
            d = min(r.width(), r.height())
            radius = int(d*0.35)
            cx = r.center().x()
            cy = r.top() + radius + 6
            bg = QColor(0,0,0,160)
            pen = QPen(QColor(255,255,255,220))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(bg)
            painter.drawEllipse(QPoint(cx, cy), radius, radius)
            font = painter.font()
            font.setBold(True)
            font.setPointSize(max(12, int(radius*0.9)))
            painter.setFont(font)
            painter.setPen(QPen(QColor(255,255,255)))
            text_rect = QRect(cx-radius, cy-radius, radius*2, radius*2)
            painter.drawText(text_rect, Qt.AlignCenter, str(order))
            painter.restore()

    def _make_ctrl_wheel_zoom(self, original_handler):
        def handler(event):
            if event.modifiers() & Qt.ControlModifier:
                delta = event.angleDelta().y()
                step = 10 if delta > 0 else -10
                new_val = max(10, min(300, self.thumb_slider.value() + step))
                if new_val != self.thumb_slider.value():
                    self.thumb_slider.setValue(new_val)
                event.accept()
            else:
                original_handler(event)
        return handler

    def _on_thumb_size_changed(self, value: int):
        self._thumb_size = value
        self.thumb_size_label.setText(f"{value}px")
        # 更新图标大小
        if hasattr(self, 'image_list'):
            self.image_list.setIconSize(self._calc_icon_size())
            self._apply_list_grid(self.image_list)
            self.image_list.update()

    def _style_accent_button(self, btn: QPushButton):
        # 使用当前主题的高亮色作为按钮底色，保证文字可读性
        pal = self.palette()
        try:
            highlight = pal.color(pal.ColorRole.Highlight)
            text_col = pal.color(pal.ColorRole.HighlightedText)
        except Exception:
            highlight = pal.highlight().color()  # type: ignore
            text_col = pal.highlightedText().color()  # type: ignore
        bg = f"rgb({highlight.red()},{highlight.green()},{highlight.blue()})"
        fg = f"rgb({text_col.red()},{text_col.green()},{text_col.blue()})"
        btn.setStyleSheet(
            f"QPushButton {{ font-weight: 600; border-radius: 6px; padding: 8px 12px; background-color: {bg}; color: {fg}; }}"
            "QPushButton:disabled { opacity: 0.6; }"
        )

    def _update_summary(self):
        total = self.image_list.count() if hasattr(self, 'image_list') else 0
        selected = len(self.image_list.selectedIndexes()) if hasattr(self, 'image_list') else 0
        self.selection_summary_label.setText(f"已加载: {total} 张 | 已选择: {selected} 张")
        if hasattr(self, 'image_list'):
            self.image_list.viewport().update()

    def _select_all(self):
        self.image_list.selectAll()
        self._update_summary()

    def _select_none(self):
        self.image_list.clearSelection()
        self._update_summary()

    def _invert_selection(self):
        to_select = []
        to_deselect = []
        for i in range(self.image_list.count()):
            it = self.image_list.item(i)
            if it.isSelected():
                to_deselect.append(it)
            else:
                to_select.append(it)
        for it in to_deselect:
            it.setSelected(False)
        for it in to_select:
            it.setSelected(True)
        self._update_summary()

    def _on_selection_changed(self):
        self._update_summary()

    def _on_item_double_clicked(self, item: QListWidgetItem):
        """双击缩略图：用系统默认程序打开图片文件"""
        try:
            path = item.data(self.ROLE_PATH) if item else None
            if path and os.path.exists(path):
                if sys.platform.startswith('win'):
                    os.startfile(path)  # type: ignore[attr-defined]
                else:
                    QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            else:
                QMessageBox.information(self, "提示", "未找到有效的文件路径")
        except Exception as e:
            QMessageBox.warning(self, "打开失败", f"无法打开文件:\n{path}\n\n{e}")

    def open_output_dir(self):
        """打开输出目录（所选目录下的 stitch），不存在则创建"""
        try:
            base_dir = Path(self.dir_edit.text().strip() or Path.home())
            out_dir = base_dir / "stitch"
            out_dir.mkdir(parents=True, exist_ok=True)
            p = str(out_dir)
            if sys.platform.startswith('win'):
                os.startfile(p)  # type: ignore[attr-defined]
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(p))
        except Exception as e:
            QMessageBox.warning(self, "打开失败", f"无法打开输出目录:\n{e}")

    def _auto_order_by_name(self):
        # 取已选行按文件名排序后从1开始编号
        items = []
        for i in range(self.image_list.count()):
            it = self.image_list.item(i)
            if it and it.checkState() == Qt.Checked:
                path = it.data(self.ROLE_PATH)
                items.append((i, os.path.basename(path)))
        items.sort(key=lambda x: x[1].lower())
        for order, (i, _) in enumerate(items, start=1):
            it = self.image_list.item(i)
            it.setData(self.ROLE_ORDER, order)
            self._update_item_text(it)

    def _clear_order(self):
        for i in range(self.image_list.count()):
            it = self.image_list.item(i)
            if it:
                it.setData(self.ROLE_ORDER, 0)
                self._update_item_text(it)

    def _load_images_for_preview(self, directory: str):
        # 清空并填充列表
        self.image_list.clear()
        paths = stitcher.load_images(directory)
        for path in paths:
            self._add_image_item(path)
        self._update_summary()

    def _add_image_item(self, path: str):
        pix = QPixmap(path)
        icon = QIcon(pix)
        item = QListWidgetItem(icon, "")
        item.setData(self.ROLE_PATH, path)
        item.setFlags(item.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        item.setToolTip(os.path.basename(path))
        self.image_list.addItem(item)

    def _update_item_text(self, item: QListWidgetItem):
        # 保持无文字，使用工具提示展示文件名
        item.setText("")

    def _on_list_context_menu(self, pos: QPoint):
        item = self.image_list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        act_set_order = QAction("设置序号…", self)
        act_clear_order = QAction("清除序号", self)
        act_toggle_mark = QAction("切换标记", self)
        menu.addAction(act_set_order)
        menu.addAction(act_clear_order)
        menu.addSeparator()
        menu.addAction(act_toggle_mark)

        def do_set_order():
            val, ok = QInputDialog.getInt(self, "设置序号", "序号 (>=1):", value=max(1, int(item.data(self.ROLE_ORDER) or 1)), min=1, max=9999)
            if ok:
                item.setData(self.ROLE_ORDER, int(val))
                self._update_item_text(item)

        def do_clear_order():
            item.setData(self.ROLE_ORDER, 0)
            self._update_item_text(item)

        def do_toggle_mark():
            cur = bool(item.data(self.ROLE_MARK))
            item.setData(self.ROLE_MARK, (not cur))
            self._update_item_text(item)

        act_set_order.triggered.connect(do_set_order)
        act_clear_order.triggered.connect(do_clear_order)
        act_toggle_mark.triggered.connect(do_toggle_mark)
        menu.exec(self.image_list.mapToGlobal(pos))
    
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
        
        self.preview_label.setText("⏳ 正在处理，请稍候...")
        # 使用主题色作为边框，窗口背景色作为底色
        pal = self.palette()
        try:
            win_col = pal.color(pal.ColorRole.Window)
            txt_col = pal.color(pal.ColorRole.Text)
            hi_col = pal.color(pal.ColorRole.Highlight)
        except Exception:
            win_col = pal.window().color()  # type: ignore
            txt_col = pal.text().color()    # type: ignore
            hi_col = pal.highlight().color()  # type: ignore
        self.preview_label.setStyleSheet(
            "QLabel { "
            f"background-color: rgb({win_col.red()},{win_col.green()},{win_col.blue()}); "
            f"border: 2px solid rgb({hi_col.red()},{hi_col.green()},{hi_col.blue()}); "
            "padding: 20px; "
            f"color: rgb({txt_col.red()},{txt_col.green()},{txt_col.blue()}); "
            "font-size: 14px; "
            "}"
        )
        self.result_image = None
        
        # 默认使用扫描模式
        mode = 'scans'
        mode_name = "扫描模式"
        
        # 读取用户选择（使用选中项，按行号顺序）
        selected_rows = sorted([ix.row() for ix in self.image_list.selectedIndexes()])
        selected_paths = [self.image_list.item(r).data(self.ROLE_PATH) for r in selected_rows]

        image_paths_for_job: List[str]
        if selected_paths:
            image_paths_for_job = selected_paths
        else:
            # 未选择则默认处理全部（按显示顺序）
            image_paths_for_job = []
            for i in range(self.image_list.count()):
                it = self.image_list.item(i)
                if it:
                    path = it.data(self.ROLE_PATH)
                    if path:
                        image_paths_for_job.append(path)

        if not image_paths_for_job:
            QMessageBox.warning(self, "警告", "目录中未找到可处理的图片")
            self.start_btn.setEnabled(True)
            self.browse_btn.setEnabled(True)
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
        # 自动保存结果
        try:
            base_dir = Path(self.dir_edit.text().strip() or Path.home())
            out_dir = base_dir / "stitch"
            out_dir.mkdir(parents=True, exist_ok=True)
            # 文件名：stitched_时间戳.png
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = out_dir / f"stitched_{ts}.png"
            encode_param = [int(cv2.IMWRITE_PNG_COMPRESSION), 3]
            success, encoded_img = cv2.imencode('.png', result, encode_param)
            if success:
                with open(file_path, 'wb') as f:
                    f.write(encoded_img.tobytes())
                self.log(f"💾 已自动保存结果: {file_path}")
            else:
                self.log("❌ 自动保存失败：编码失败")
        except Exception as e:
            self.log(f"❌ 自动保存异常: {e}")
        
        h, w = result.shape[:2]
        self.log(f"✅ 拼接成功！结果尺寸: {w} x {h} 像素")
        self.log("="*60)
        
        # 使用主题窗口底色 + 高亮色边框，避免硬编码白色
        pal = self.palette()
        try:
            win_col = pal.color(pal.ColorRole.Window)
            hi_col = pal.color(pal.ColorRole.Highlight)
        except Exception:
            win_col = pal.window().color()  # type: ignore
            hi_col = pal.highlight().color()  # type: ignore
        self.preview_label.setStyleSheet(
            "QLabel { "
            f"background-color: rgb({win_col.red()},{win_col.green()},{win_col.blue()}); "
            f"border: 2px solid rgb({hi_col.red()},{hi_col.green()},{hi_col.blue()}); "
            "}"
        )
        
        # 去掉强制弹窗，仅在日志中提示
        self.log("✅ 图片拼接完成，预览区已更新。结果已自动保存到输出目录 stitch。")
    
    def on_error(self, error_message: str):
        """处理错误"""
        self.log(f"❌ 错误: {error_message}")
        self.log("="*60)
        
        self.start_btn.setEnabled(True)
        self.browse_btn.setEnabled(True)
        
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
        self._set_result_pixmap_from_np(image)
        self._refresh_result_preview()

    def _set_result_pixmap_from_np(self, image: np.ndarray):
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        self._result_pixmap = QPixmap.fromImage(qt_image)

    def _refresh_result_preview(self):
        if not hasattr(self, '_result_pixmap') or self._result_pixmap.isNull():
            return
        # 根据容器尺寸自适应缩放
        avail = self.result_container.size()
        target = QSize(max(10, avail.width()-2), max(10, avail.height()-2))
        scaled = self._result_pixmap.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview_label.setPixmap(scaled)
        self.preview_label.setMinimumSize(1,1)
    
    def save_result(self):
        """保存结果"""
        if self.result_image is None:
            QMessageBox.warning(self, "警告", "没有可保存的结果")
            return
        
        # 默认保存到所选目录下的 stitch 子文件夹
        base_dir = Path(self.dir_edit.text().strip() or Path.home())
        default_dir = base_dir / "stitch"
        try:
            default_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        default_path = default_dir / "stitched_result.png"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存拼接结果", 
            str(default_path),
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
                except Exception:
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
            try:
                hl = pal.color(pal.ColorRole.Highlight)
                htxt = pal.color(pal.ColorRole.HighlightedText)
                txt = pal.color(pal.ColorRole.ButtonText)
                mid = pal.color(pal.ColorRole.Mid)
            except Exception:
                hl = pal.highlight().color()  # type: ignore
                htxt = pal.highlightedText().color()  # type: ignore
                txt = pal.buttonText().color()  # type: ignore
                mid = pal.mid().color()  # type: ignore
            base_txt = f"rgb({txt.red()},{txt.green()},{txt.blue()})"
            h_rgb = f"rgb({hl.red()},{hl.green()},{hl.blue()})"
            h_txt = f"rgb({htxt.red()},{htxt.green()},{htxt.blue()})"
            mid_rgba = f"rgba({mid.red()},{mid.green()},{mid.blue()},120)"
            mid_hover = f"rgba({mid.red()},{mid.green()},{mid.blue()},40)"
            self.toggle_button.setStyleSheet(
                """
                QPushButton {
                    border: 1px solid %s;
                    border-radius: 4px;      /* 小圆角，更紧凑 */
                    padding: 2px 6px;        /* 仅比文字高一点 */
                    min-height: 20px;        /* 紧凑高度 */
                    background-color: transparent;
                    color: %s;
                    text-align: center;
                }
                QPushButton:hover {
                    background-color: %s;
                }
                QPushButton:checked {
                    background-color: %s;
                    border-color: %s;
                    color: %s;
                }
                """ % (mid_rgba, base_txt, mid_hover, h_rgb, h_rgb, h_txt)
            )

    # 1. 直接在顶部放置“设置”内容（扁平化，不再使用折叠面板）
    top_settings = QVBoxLayout()
    top_settings.setContentsMargins(8,8,8,0)
    top_settings.setSpacing(6)
    dir_row = QHBoxLayout()
    self.dir_edit = QLineEdit()
    self.dir_edit.setPlaceholderText("请选择包含要拼接图片的目录...")
    self.browse_btn = QPushButton("浏览...")
    self.browse_btn.setProperty("btn", "secondary")
    self.browse_btn.clicked.connect(self.browse_directory)
    dir_row.addWidget(QLabel("目录:"))
    dir_row.addWidget(self.dir_edit, 1)
    dir_row.addWidget(self.browse_btn)
    top_settings.addLayout(dir_row)
    # 同行按钮
    btn_row = QHBoxLayout()
    btn_row.setSpacing(6)
    self.start_btn = QPushButton("🚀 开始拼接")
    self.start_btn.clicked.connect(self.start_stitching)
# 紧凑：降低按钮最小高度
self.start_btn.setMinimumHeight(22)
    self.start_btn.setProperty("btn", "primary")
    self.start_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    btn_row.addWidget(self.start_btn, 1)
    top_settings.addLayout(btn_row)
    # 进度条
    self.progress_bar = QProgressBar()
    pal = self.palette()
    try:
        hl = pal.color(pal.ColorRole.Highlight)
    except Exception:
        hl = pal.highlight().color()  # type: ignore
    self.progress_bar.setStyleSheet(
        "QProgressBar { border: 1px solid palette(Mid); border-radius: 4px; text-align: center; min-height: 12px;}"
        f"QProgressBar::chunk {{ background-color: rgb({hl.red()},{hl.green()},{hl.blue()}); }}"
    )
    top_settings.addWidget(self.progress_bar)
    # 挂到主布局顶部
    layout.addLayout(top_settings)

    # 2. 图片预览与选择 / 结果预览（合并面板）
    preview_box = CollapsibleBox("预览", default_open=True, expand_flex=False)
    preview_select_layout = QVBoxLayout()
    preview_select_layout.setContentsMargins(8,8,8,8)
    preview_select_layout.setSpacing(6)

    # 顶行：统计 + 选择操作按钮（同一行）
    top_bar = QHBoxLayout()
    self.selection_summary_label = QLabel("未加载目录")
    top_bar.addWidget(self.selection_summary_label)
    top_bar.addStretch()
    self.btn_select_all = QPushButton("全选")
    self.btn_select_none = QPushButton("全不选")
    self.btn_invert = QPushButton("反选")
    for b in (self.btn_select_all, self.btn_select_none, self.btn_invert):
        b.setMinimumHeight(28)
        b.setProperty("btn", "secondary")
        top_bar.addWidget(b)
    preview_select_layout.addLayout(top_bar)

    # 第二行：缩放 + 打开输出目录
    zoom_row = QHBoxLayout()
    zoom_row.addWidget(QLabel("缩放:"))
    self.thumb_size_label = QLabel(f"{self._thumb_size}px")
    zoom_row.addWidget(self.thumb_size_label)
    self.thumb_slider = QSlider(Qt.Horizontal)
    self.thumb_slider.setMinimum(10)
    self.thumb_slider.setMaximum(300)
    self.thumb_slider.setValue(self._thumb_size)
    self.thumb_slider.setToolTip("调整预览缩略图大小 (Ctrl+滚轮 也可缩放)")
    self.thumb_slider.valueChanged.connect(self._on_thumb_size_changed)
    zoom_row.addWidget(self.thumb_slider, 1)
    self.open_output_btn = QPushButton("打开")
    self.open_output_btn.setProperty("btn", "secondary")
    self.open_output_btn.setToolTip("打开输出目录 (stitch)")
    self.open_output_btn.clicked.connect(self.open_output_dir)
    zoom_row.addWidget(self.open_output_btn)
    preview_select_layout.addLayout(zoom_row)

    # 预览：图标平铺（正方形体块）
    self.image_list = self._create_image_list()

    # 选择按钮连接
    self.btn_select_all.clicked.connect(self._select_all)
    self.btn_select_none.clicked.connect(self._select_none)
    self.btn_invert.clicked.connect(self._invert_selection)

    # 合并：结果预览区域（右侧，自动缩放，无滚动条）
    self.result_container = QWidget()
    self.result_container.setMinimumHeight(260)
    rc_layout = QVBoxLayout(self.result_container)
    rc_layout.setContentsMargins(0,0,0,0)
    rc_layout.setSpacing(0)
    self.preview_label = QLabel("拼接结果将显示在这里")
    self.preview_label.setAlignment(Qt.AlignCenter)
    # 使用当前主题的窗口背景色和中间色设置初始底色和边框，避免纯白
    pal = self.palette()
    try:
        win_col = pal.color(pal.ColorRole.Window)
        mid_col = pal.color(pal.ColorRole.Mid)
        txt_col = pal.color(pal.ColorRole.Text)
    except Exception:
        win_col = pal.window().color()  # type: ignore
        mid_col = pal.mid().color()  # type: ignore
        txt_col = pal.text().color()  # type: ignore
    self.preview_label.setStyleSheet(
        "QLabel { "
        f"background-color: rgb({win_col.red()},{win_col.green()},{win_col.blue()}); "
        f"border: 2px dashed rgb({mid_col.red()},{mid_col.green()},{mid_col.blue()}); "
        "padding: 16px; "
        f"color: rgb({txt_col.red()},{txt_col.green()},{txt_col.blue()}); "
        "font-size: 13px; }"
    )
    self.preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    rc_layout.addWidget(self.preview_label, 1)
    def _rc_resize(ev):
        QWidget.resizeEvent(self.result_container, ev)
        self._refresh_result_preview()
    self.result_container.resizeEvent = _rc_resize

    # 左右结构：左（缩略图+操作）| 分隔线 | 右（结果预览）
    content_row = QHBoxLayout()
    content_row.setSpacing(6)
    left_col = QVBoxLayout()
    left_col.addWidget(self.image_list, 1)
    content_row.addLayout(left_col, 1)
    divider = QFrame()
    divider.setFrameShape(QFrame.VLine)
    divider.setFrameShadow(QFrame.Plain)
    divider.setLineWidth(1)
    content_row.addWidget(divider)
    content_row.addWidget(self.result_container, 1)
    preview_select_layout.addLayout(content_row)

    # 双击打开：为缩略图列表启用双击打开文件
    self.image_list.itemDoubleClicked.connect(self._on_item_double_clicked)
preview_box.setContentLayout(preview_select_layout)

    # 3. 日志
    log_box = CollapsibleBox("日志", default_open=True, expand_flex=True)
    log_layout = QVBoxLayout()
    self.log_text = QTextEdit()
    self.log_text.setReadOnly(True)
    self.log_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    log_layout.addWidget(self.log_text)
log_box.setContentLayout(log_layout)

# 使用垂直分割器使预览与日志可上下拖动
self.main_splitter = QSplitter(Qt.Vertical)
self.main_splitter.addWidget(preview_box)
self.main_splitter.addWidget(log_box)
self.main_splitter.setStretchFactor(0, 1)
self.main_splitter.setStretchFactor(1, 2)
layout.addWidget(self.main_splitter, 1)

    # 首先把提示文字写入日志
    self.log("✅ 程序已启动 - 使用 OpenCV Stitcher 专业拼接引擎")
    self.log("💡 提示：")
    self.log("• Created by AYE | Version 1.0.0 | 2025-10-12")
    self.log("• OpenCV Stitcher 是业界标准的图像拼接库")
    self.log("• 自动检测特征点并精确对齐")
    self.log("• 确保相邻图片有 30% 以上的重叠区域")
    self.log("• 当前默认使用‘扫描模式’，适合截图/文档")

    # 外部底端弹簧：始终存在于所有面板之后，保证折叠时整体贴顶
    layout.addStretch(1)

# ——— 全局按钮样式（更紧凑的圆角、padding 与高度） ———
    pal = self.palette()
    try:
        bg = pal.color(pal.ColorRole.Window)
        txt = pal.color(pal.ColorRole.ButtonText)
        hi = pal.color(pal.ColorRole.Highlight)
    except Exception:
        bg = pal.window().color()  # type: ignore
        txt = pal.buttonText().color()  # type: ignore
        hi = pal.highlight().color()  # type: ignore
    base_txt = f"rgba({txt.red()},{txt.green()},{txt.blue()},255)"
    hi_rgb = f"rgb({hi.red()},{hi.green()},{hi.blue()})"
    hi_hover = f"rgba({hi.red()},{hi.green()},{hi.blue()},0.85)"
    hi_press = f"rgba({hi.red()},{hi.green()},{hi.blue()},0.7)"
    sec_bg = f"rgba({bg.red()},{bg.green()},{bg.blue()},0.6)"
    sec_bor = f"rgba({txt.red()},{txt.green()},{txt.blue()},80)"
    self.setStyleSheet(self.styleSheet() + f"""
        QPushButton[btn="primary"] {{
            color: white;
            background-color: {hi_rgb};
            border: 1px solid {hi_rgb};
            border-radius: 6px;
            padding: 3px 8px;
            min-height: 20px;
            font-weight: 600;
        }}
        QPushButton[btn="primary"]:hover {{
            background-color: {hi_hover};
            border-color: {hi_hover};
        }}
        QPushButton[btn="primary"]:pressed {{
            background-color: {hi_press};
            border-color: {hi_press};
        }}
        QPushButton[btn="primary"]:disabled {{
            background-color: rgba(180,180,180,0.5);
            border-color: rgba(160,160,160,0.4);
            color: rgba(255,255,255,0.8);
        }}

        QPushButton[btn="secondary"] {{
            color: {base_txt};
            background-color: {sec_bg};
            border: 1px solid {sec_bor};
            border-radius: 4px;
            padding: 3px 8px;
            min-height: 20px;
        }}
        QPushButton[btn="secondary"]:hover {{
            background-color: rgba(127,127,127,0.15);
        }}
        QPushButton[btn="secondary"]:pressed {{
            background-color: rgba(127,127,127,0.25);
        }}
""")

    # 恢复 UI 状态（分割器尺寸、折叠状态）
    self._restore_ui_state(preview_box, log_box)

def _restore_ui_state(self, preview_box: QWidget, log_box: QWidget):
    settings = QSettings("AYE", "AutoStitcher")
    sizes = settings.value("splitter/sizes")
    if isinstance(sizes, list) and all(isinstance(x, int) for x in sizes):
        self.main_splitter.setSizes(sizes)  # type: ignore[arg-type]
    else:
        self.main_splitter.setSizes([400, 360])

    prev_exp = settings.value("collapsible/preview", True, bool)
    log_exp = settings.value("collapsible/log", True, bool)
    # 应用折叠状态
    try:
        preview_box.toggle_button.setChecked(bool(prev_exp))
        preview_box._on_toggle(bool(prev_exp))
    except Exception:
        pass
    try:
        log_box.toggle_button.setChecked(bool(log_exp))
        log_box._on_toggle(bool(log_exp))
    except Exception:
        pass

    # 恢复缩略图大小（若存在）
    thumb = settings.value("thumb/size")
    if isinstance(thumb, int) and 10 <= thumb <= 300:
        self.thumb_slider.setValue(thumb)

def closeEvent(self, event):  # type: ignore[override]
    # 保存分割器尺寸与折叠状态、缩略图尺寸
    try:
        settings = QSettings("AYE", "AutoStitcher")
        settings.setValue("splitter/sizes", self.main_splitter.sizes())
        # 折叠状态：通过查找 splitter 中的两个 CollapsibleBox
        if self.main_splitter.count() >= 2:
            w0 = self.main_splitter.widget(0)
            w1 = self.main_splitter.widget(1)
            try:
                settings.setValue("collapsible/preview", bool(w0.toggle_button.isChecked()))
            except Exception:
                pass
            try:
                settings.setValue("collapsible/log", bool(w1.toggle_button.isChecked()))
            except Exception:
                pass
        # 缩略图尺寸
        try:
            settings.setValue("thumb/size", int(self.thumb_slider.value()))
        except Exception:
            pass
    finally:
        super().closeEvent(event)

# 底部弹簧已移至 init_ui 内部末尾，且日志面板设置了更高的伸展因子

# ============ 预览表格与缩放 ============
def _create_image_list(self) -> QListWidget:
    lw = QListWidget()
    lw.setViewMode(QListView.IconMode)
    lw.setIconSize(self._calc_icon_size())
    lw.setResizeMode(QListView.Adjust)
    lw.setMovement(QListView.Static)
    lw.setSpacing(2)
    lw.setUniformItemSizes(True)
    lw.setSelectionMode(QListWidget.MultiSelection)
    lw.setContextMenuPolicy(Qt.CustomContextMenu)
    lw.customContextMenuRequested.connect(self._on_list_context_menu)
    # Ctrl+滚轮缩放
    lw.wheelEvent = self._make_ctrl_wheel_zoom(lw.wheelEvent)
    # 选择变化时更新统计
    lw.itemSelectionChanged.connect(self._on_selection_changed)
    self._apply_list_grid(lw)
    # 自定义选中叠加序号
    lw.setItemDelegate(self.ThumbDelegate(self))
    return lw

def _calc_icon_size(self):
    # 允许最小到 10px，最大 512px
    s = max(10, min(512, self._thumb_size))
    return QSize(s, s)

def _apply_list_grid(self, lw: QListWidget):
    # 根据图标尺寸设置网格，尽量紧凑
    s = self._calc_icon_size().width()
    lw.setGridSize(QSize(s + 8, s + 8))

class ThumbDelegate(QStyledItemDelegate):
        def __init__(self, parent):
            super().__init__(parent)
            self.parent = parent
        def paint(self, painter: QPainter, option, index):
            # 自绘缩略图，保证在正方形单元内最大化适配（等比居中），并绘制选中序号
            painter.save()
            r = option.rect
            # 绘制背景（使用系统样式提供的背景，确保主题一致）
            # 不主动填充背景，交给视图样式；只绘制图片
            try:
                item = self.parent.image_list.item(index.row())
                icon = item.icon() if item is not None else QIcon()
            except Exception:
                icon = QIcon()
            # 目标边长（留出少量边距）
            side = min(r.width(), r.height()) - 8
            if side < 2:
                side = max(1, side)
            # 从图标获取较大底图，再二次等比缩放，避免锯齿
            base_pix = icon.pixmap(512, 512) if not icon.isNull() else QPixmap()
            if not base_pix.isNull():
                scaled = base_pix.scaled(side, side, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                x = r.x() + (r.width() - scaled.width()) // 2
                y = r.y() + (r.height() - scaled.height()) // 2
                painter.drawPixmap(x, y, scaled)
            painter.restore()
            # 选中项叠加大序号
            w: QListWidget = self.parent.image_list
            sel = w.selectionModel().selectedIndexes()
            if not sel:
                return
            sel_sorted = sorted(sel, key=lambda ix: ix.row())
            row_to_order = {ix.row(): i+1 for i, ix in enumerate(sel_sorted)}
            if index.row() not in row_to_order:
                return
            order = row_to_order[index.row()]
            r = option.rect
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing, True)
            d = min(r.width(), r.height())
            radius = int(d*0.35)
            cx = r.center().x()
            cy = r.top() + radius + 6
            bg = QColor(0,0,0,160)
            pen = QPen(QColor(255,255,255,220))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(bg)
            painter.drawEllipse(QPoint(cx, cy), radius, radius)
            font = painter.font()
            font.setBold(True)
            font.setPointSize(max(12, int(radius*0.9)))
            painter.setFont(font)
            painter.setPen(QPen(QColor(255,255,255)))
            text_rect = QRect(cx-radius, cy-radius, radius*2, radius*2)
            painter.drawText(text_rect, Qt.AlignCenter, str(order))
            painter.restore()

    def _make_ctrl_wheel_zoom(self, original_handler):
        def handler(event):
            if event.modifiers() & Qt.ControlModifier:
                delta = event.angleDelta().y()
                step = 10 if delta > 0 else -10
                new_val = max(10, min(300, self.thumb_slider.value() + step))
                if new_val != self.thumb_slider.value():
                    self.thumb_slider.setValue(new_val)
                event.accept()
            else:
                original_handler(event)
        return handler

    def _on_thumb_size_changed(self, value: int):
        self._thumb_size = value
        self.thumb_size_label.setText(f"{value}px")
        # 更新图标大小
        if hasattr(self, 'image_list'):
            self.image_list.setIconSize(self._calc_icon_size())
            self._apply_list_grid(self.image_list)
            self.image_list.update()

    def _style_accent_button(self, btn: QPushButton):
        # 使用当前主题的高亮色作为按钮底色，保证文字可读性
        pal = self.palette()
        try:
            highlight = pal.color(pal.ColorRole.Highlight)
            text_col = pal.color(pal.ColorRole.HighlightedText)
        except Exception:
            highlight = pal.highlight().color()  # type: ignore
            text_col = pal.highlightedText().color()  # type: ignore
        bg = f"rgb({highlight.red()},{highlight.green()},{highlight.blue()})"
        fg = f"rgb({text_col.red()},{text_col.green()},{text_col.blue()})"
        btn.setStyleSheet(
            f"QPushButton {{ font-weight: 600; border-radius: 6px; padding: 8px 12px; background-color: {bg}; color: {fg}; }}"
            "QPushButton:disabled { opacity: 0.6; }"
        )

    def _update_summary(self):
        total = self.image_list.count() if hasattr(self, 'image_list') else 0
        selected = len(self.image_list.selectedIndexes()) if hasattr(self, 'image_list') else 0
        self.selection_summary_label.setText(f"已加载: {total} 张 | 已选择: {selected} 张")
        if hasattr(self, 'image_list'):
            self.image_list.viewport().update()

    def _select_all(self):
        self.image_list.selectAll()
        self._update_summary()

    def _select_none(self):
        self.image_list.clearSelection()
        self._update_summary()

    def _invert_selection(self):
        to_select = []
        to_deselect = []
        for i in range(self.image_list.count()):
            it = self.image_list.item(i)
            if it.isSelected():
                to_deselect.append(it)
            else:
                to_select.append(it)
        for it in to_deselect:
            it.setSelected(False)
        for it in to_select:
            it.setSelected(True)
        self._update_summary()

    def _on_selection_changed(self):
        self._update_summary()

    def _on_item_double_clicked(self, item: QListWidgetItem):
        """双击缩略图：用系统默认程序打开图片文件"""
        try:
            path = item.data(self.ROLE_PATH) if item else None
            if path and os.path.exists(path):
                if sys.platform.startswith('win'):
                    os.startfile(path)  # type: ignore[attr-defined]
                else:
                    QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            else:
                QMessageBox.information(self, "提示", "未找到有效的文件路径")
        except Exception as e:
            QMessageBox.warning(self, "打开失败", f"无法打开文件:\n{path}\n\n{e}")

    def open_output_dir(self):
        """打开输出目录（所选目录下的 stitch），不存在则创建"""
        try:
            base_dir = Path(self.dir_edit.text().strip() or Path.home())
            out_dir = base_dir / "stitch"
            out_dir.mkdir(parents=True, exist_ok=True)
            p = str(out_dir)
            if sys.platform.startswith('win'):
                os.startfile(p)  # type: ignore[attr-defined]
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(p))
        except Exception as e:
            QMessageBox.warning(self, "打开失败", f"无法打开输出目录:\n{e}")

    def _auto_order_by_name(self):
        # 取已选行按文件名排序后从1开始编号
        items = []
        for i in range(self.image_list.count()):
            it = self.image_list.item(i)
            if it and it.checkState() == Qt.Checked:
                path = it.data(self.ROLE_PATH)
                items.append((i, os.path.basename(path)))
        items.sort(key=lambda x: x[1].lower())
        for order, (i, _) in enumerate(items, start=1):
            it = self.image_list.item(i)
            it.setData(self.ROLE_ORDER, order)
            self._update_item_text(it)

    def _clear_order(self):
        for i in range(self.image_list.count()):
            it = self.image_list.item(i)
            if it:
                it.setData(self.ROLE_ORDER, 0)
                self._update_item_text(it)

    def _load_images_for_preview(self, directory: str):
        # 清空并填充列表
        self.image_list.clear()
        paths = stitcher.load_images(directory)
        for path in paths:
            self._add_image_item(path)
        self._update_summary()

    def _add_image_item(self, path: str):
        pix = QPixmap(path)
        icon = QIcon(pix)
        item = QListWidgetItem(icon, "")
        item.setData(self.ROLE_PATH, path)
        item.setFlags(item.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        item.setToolTip(os.path.basename(path))
        self.image_list.addItem(item)

    def _update_item_text(self, item: QListWidgetItem):
        # 保持无文字，使用工具提示展示文件名
        item.setText("")

    def _on_list_context_menu(self, pos: QPoint):
        item = self.image_list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        act_set_order = QAction("设置序号…", self)
        act_clear_order = QAction("清除序号", self)
        act_toggle_mark = QAction("切换标记", self)
        menu.addAction(act_set_order)
        menu.addAction(act_clear_order)
        menu.addSeparator()
        menu.addAction(act_toggle_mark)

        def do_set_order():
            val, ok = QInputDialog.getInt(self, "设置序号", "序号 (>=1):", value=max(1, int(item.data(self.ROLE_ORDER) or 1)), min=1, max=9999)
            if ok:
                item.setData(self.ROLE_ORDER, int(val))
                self._update_item_text(item)

        def do_clear_order():
            item.setData(self.ROLE_ORDER, 0)
            self._update_item_text(item)

        def do_toggle_mark():
            cur = bool(item.data(self.ROLE_MARK))
            item.setData(self.ROLE_MARK, (not cur))
            self._update_item_text(item)

        act_set_order.triggered.connect(do_set_order)
        act_clear_order.triggered.connect(do_clear_order)
        act_toggle_mark.triggered.connect(do_toggle_mark)
        menu.exec(self.image_list.mapToGlobal(pos))
    
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
        
        self.preview_label.setText("⏳ 正在处理，请稍候...")
        # 使用主题色作为边框，窗口背景色作为底色
        pal = self.palette()
        try:
            win_col = pal.color(pal.ColorRole.Window)
            txt_col = pal.color(pal.ColorRole.Text)
            hi_col = pal.color(pal.ColorRole.Highlight)
        except Exception:
            win_col = pal.window().color()  # type: ignore
            txt_col = pal.text().color()    # type: ignore
            hi_col = pal.highlight().color()  # type: ignore
        self.preview_label.setStyleSheet(
            "QLabel { "
            f"background-color: rgb({win_col.red()},{win_col.green()},{win_col.blue()}); "
            f"border: 2px solid rgb({hi_col.red()},{hi_col.green()},{hi_col.blue()}); "
            "padding: 20px; "
            f"color: rgb({txt_col.red()},{txt_col.green()},{txt_col.blue()}); "
            "font-size: 14px; "
            "}"
        )
        self.result_image = None
        
        # 默认使用扫描模式
        mode = 'scans'
        mode_name = "扫描模式"
        
        # 读取用户选择（使用选中项，按行号顺序）
        selected_rows = sorted([ix.row() for ix in self.image_list.selectedIndexes()])
        selected_paths = [self.image_list.item(r).data(self.ROLE_PATH) for r in selected_rows]

        image_paths_for_job: List[str]
        if selected_paths:
            image_paths_for_job = selected_paths
        else:
            # 未选择则默认处理全部（按显示顺序）
            image_paths_for_job = []
            for i in range(self.image_list.count()):
                it = self.image_list.item(i)
                if it:
                    path = it.data(self.ROLE_PATH)
                    if path:
                        image_paths_for_job.append(path)

        if not image_paths_for_job:
            QMessageBox.warning(self, "警告", "目录中未找到可处理的图片")
            self.start_btn.setEnabled(True)
            self.browse_btn.setEnabled(True)
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
        # 自动保存结果
        try:
            base_dir = Path(self.dir_edit.text().strip() or Path.home())
            out_dir = base_dir / "stitch"
            out_dir.mkdir(parents=True, exist_ok=True)
            # 文件名：stitched_时间戳.png
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = out_dir / f"stitched_{ts}.png"
            encode_param = [int(cv2.IMWRITE_PNG_COMPRESSION), 3]
            success, encoded_img = cv2.imencode('.png', result, encode_param)
            if success:
                with open(file_path, 'wb') as f:
                    f.write(encoded_img.tobytes())
                self.log(f"💾 已自动保存结果: {file_path}")
            else:
                self.log("❌ 自动保存失败：编码失败")
        except Exception as e:
            self.log(f"❌ 自动保存异常: {e}")
        
        h, w = result.shape[:2]
        self.log(f"✅ 拼接成功！结果尺寸: {w} x {h} 像素")
        self.log("="*60)
        
        # 使用主题窗口底色 + 高亮色边框，避免硬编码白色
        pal = self.palette()
        try:
            win_col = pal.color(pal.ColorRole.Window)
            hi_col = pal.color(pal.ColorRole.Highlight)
        except Exception:
            win_col = pal.window().color()  # type: ignore
            hi_col = pal.highlight().color()  # type: ignore
        self.preview_label.setStyleSheet(
            "QLabel { "
            f"background-color: rgb({win_col.red()},{win_col.green()},{win_col.blue()}); "
            f"border: 2px solid rgb({hi_col.red()},{hi_col.green()},{hi_col.blue()}); "
            "}"
        )
        
        # 去掉强制弹窗，仅在日志中提示
        self.log("✅ 图片拼接完成，预览区已更新。结果已自动保存到输出目录 stitch。")
    
    def on_error(self, error_message: str):
        """处理错误"""
        self.log(f"❌ 错误: {error_message}")
        self.log("="*60)
        
        self.start_btn.setEnabled(True)
        self.browse_btn.setEnabled(True)
        
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
        self._set_result_pixmap_from_np(image)
        self._refresh_result_preview()

    def _set_result_pixmap_from_np(self, image: np.ndarray):
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        self._result_pixmap = QPixmap.fromImage(qt_image)

    def _refresh_result_preview(self):
        if not hasattr(self, '_result_pixmap') or self._result_pixmap.isNull():
            return
        # 根据容器尺寸自适应缩放
        avail = self.result_container.size()
        target = QSize(max(10, avail.width()-2), max(10, avail.height()-2))
        scaled = self._result_pixmap.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview_label.setPixmap(scaled)
        self.preview_label.setMinimumSize(1,1)
    
    def save_result(self):
        """保存结果"""
        if self.result_image is None:
            QMessageBox.warning(self, "警告", "没有可保存的结果")
            return
        
        # 默认保存到所选目录下的 stitch 子文件夹
        base_dir = Path(self.dir_edit.text().strip() or Path.home())
        default_dir = base_dir / "stitch"
        try:
            default_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        default_path = default_dir / "stitched_result.png"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存拼接结果", 
            str(default_path),
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
    main()class ThumbDelegate(QStyledItemDelegate):
        def __init__(self, parent):
            super().__init__(parent)
            self.parent = parent
        def paint(self, painter: QPainter, option, index):
            # 自绘缩略图，保证在正方形单元内最大化适配（等比居中），并绘制选中序号
            painter.save()
            r = option.rect
            # 绘制背景（使用系统样式提供的背景，确保主题一致）
            # 不主动填充背景，交给视图样式；只绘制图片
            try:
                item = self.parent.image_list.item(index.row())
                icon = item.icon() if item is not None else QIcon()
            except Exception:
                icon = QIcon()
            # 目标边长（留出少量边距）
            side = min(r.width(), r.height()) - 8
            if side < 2:
                side = max(1, side)
            # 从图标获取较大底图，再二次等比缩放，避免锯齿
            base_pix = icon.pixmap(512, 512) if not icon.isNull() else QPixmap()
            if not base_pix.isNull():
                scaled = base_pix.scaled(side, side, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                x = r.x() + (r.width() - scaled.width()) // 2
                y = r.y() + (r.height() - scaled.height()) // 2
                painter.drawPixmap(x, y, scaled)
            painter.restore()
            # 选中项叠加大序号
            w: QListWidget = self.parent.image_list
            sel = w.selectionModel().selectedIndexes()
            if not sel:
                return
            sel_sorted = sorted(sel, key=lambda ix: ix.row())
            row_to_order = {ix.row(): i+1 for i, ix in enumerate(sel_sorted)}
            if index.row() not in row_to_order:
                return
            order = row_to_order[index.row()]
            r = option.rect
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing, True)
            d = min(r.width(), r.height())
            radius = int(d*0.35)
            cx = r.center().x()
            cy = r.top() + radius + 6
            bg = QColor(0,0,0,160)
            pen = QPen(QColor(255,255,255,220))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(bg)
            painter.drawEllipse(QPoint(cx, cy), radius, radius)
            font = painter.font()
            font.setBold(True)
            font.setPointSize(max(12, int(radius*0.9)))
            painter.setFont(font)
            painter.setPen(QPen(QColor(255,255,255)))
            text_rect = QRect(cx-radius, cy-radius, radius*2, radius*2)
            painter.drawText(text_rect, Qt.AlignCenter, str(order))
            painter.restore()

    def _make_ctrl_wheel_zoom(self, original_handler):
        def handler(event):
            if event.modifiers() & Qt.ControlModifier:
                delta = event.angleDelta().y()
                step = 10 if delta > 0 else -10
                new_val = max(10, min(300, self.thumb_slider.value() + step))
                if new_val != self.thumb_slider.value():
                    self.thumb_slider.setValue(new_val)
                event.accept()
            else:
                original_handler(event)
        return handler

    def _on_thumb_size_changed(self, value: int):
        self._thumb_size = value
        self.thumb_size_label.setText(f"{value}px")
        # 更新图标大小
        if hasattr(self, 'image_list'):
            self.image_list.setIconSize(self._calc_icon_size())
            self._apply_list_grid(self.image_list)
            self.image_list.update()

    def _style_accent_button(self, btn: QPushButton):
        # 使用当前主题的高亮色作为按钮底色，保证文字可读性
        pal = self.palette()
        try:
            highlight = pal.color(pal.ColorRole.Highlight)
            text_col = pal.color(pal.ColorRole.HighlightedText)
        except Exception:
            highlight = pal.highlight().color()  # type: ignore
            text_col = pal.highlightedText().color()  # type: ignore
        bg = f"rgb({highlight.red()},{highlight.green()},{highlight.blue()})"
        fg = f"rgb({text_col.red()},{text_col.green()},{text_col.blue()})"
        btn.setStyleSheet(
            f"QPushButton {{ font-weight: 600; border-radius: 6px; padding: 8px 12px; background-color: {bg}; color: {fg}; }}"
            "QPushButton:disabled { opacity: 0.6; }"
        )

    def _update_summary(self):
        total = self.image_list.count() if hasattr(self, 'image_list') else 0
        selected = len(self.image_list.selectedIndexes()) if hasattr(self, 'image_list') else 0
        self.selection_summary_label.setText(f"已加载: {total} 张 | 已选择: {selected} 张")
        if hasattr(self, 'image_list'):
            self.image_list.viewport().update()

    def _select_all(self):
        self.image_list.selectAll()
        self._update_summary()

    def _select_none(self):
        self.image_list.clearSelection()
        self._update_summary()

    def _invert_selection(self):
        to_select = []
        to_deselect = []
        for i in range(self.image_list.count()):
            it = self.image_list.item(i)
            if it.isSelected():
                to_deselect.append(it)
            else:
                to_select.append(it)
        for it in to_deselect:
            it.setSelected(False)
        for it in to_select:
            it.setSelected(True)
        self._update_summary()

    def _on_selection_changed(self):
        self._update_summary()

    def _on_item_double_clicked(self, item: QListWidgetItem):
        """双击缩略图：用系统默认程序打开图片文件"""
        try:
            path = item.data(self.ROLE_PATH) if item else None
            if path and os.path.exists(path):
                if sys.platform.startswith('win'):
                    os.startfile(path)  # type: ignore[attr-defined]
                else:
                    QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            else:
                QMessageBox.information(self, "提示", "未找到有效的文件路径")
        except Exception as e:
            QMessageBox.warning(self, "打开失败", f"无法打开文件:\n{path}\n\n{e}")

    def open_output_dir(self):
        """打开输出目录（所选目录下的 stitch），不存在则创建"""
        try:
            base_dir = Path(self.dir_edit.text().strip() or Path.home())
            out_dir = base_dir / "stitch"
            out_dir.mkdir(parents=True, exist_ok=True)
            p = str(out_dir)
            if sys.platform.startswith('win'):
                os.startfile(p)  # type: ignore[attr-defined]
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(p))
        except Exception as e:
            QMessageBox.warning(self, "打开失败", f"无法打开输出目录:\n{e}")

    def _auto_order_by_name(self):
        # 取已选行按文件名排序后从1开始编号
        items = []
        for i in range(self.image_list.count()):
            it = self.image_list.item(i)
            if it and it.checkState() == Qt.Checked:
                path = it.data(self.ROLE_PATH)
                items.append((i, os.path.basename(path)))
        items.sort(key=lambda x: x[1].lower())
        for order, (i, _) in enumerate(items, start=1):
            it = self.image_list.item(i)
            it.setData(self.ROLE_ORDER, order)
            self._update_item_text(it)

    def _clear_order(self):
        for i in range(self.image_list.count()):
            it = self.image_list.item(i)
            if it:
                it.setData(self.ROLE_ORDER, 0)
                self._update_item_text(it)

    def _load_images_for_preview(self, directory: str):
        # 清空并填充列表
        self.image_list.clear()
        paths = stitcher.load_images(directory)
        for path in paths:
            self._add_image_item(path)
        self._update_summary()

    def _add_image_item(self, path: str):
        pix = QPixmap(path)
        icon = QIcon(pix)
        item = QListWidgetItem(icon, "")
        item.setData(self.ROLE_PATH, path)
        item.setFlags(item.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        item.setToolTip(os.path.basename(path))
        self.image_list.addItem(item)

    def _update_item_text(self, item: QListWidgetItem):
        # 保持无文字，使用工具提示展示文件名
        item.setText("")

    def _on_list_context_menu(self, pos: QPoint):
        item = self.image_list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        act_set_order = QAction("设置序号…", self)
        act_clear_order = QAction("清除序号", self)
        act_toggle_mark = QAction("切换标记", self)
        menu.addAction(act_set_order)
        menu.addAction(act_clear_order)
        menu.addSeparator()
        menu.addAction(act_toggle_mark)

        def do_set_order():
            val, ok = QInputDialog.getInt(self, "设置序号", "序号 (>=1):", value=max(1, int(item.data(self.ROLE_ORDER) or 1)), min=1, max=9999)
            if ok:
                item.setData(self.ROLE_ORDER, int(val))
                self._update_item_text(item)

        def do_clear_order():
            item.setData(self.ROLE_ORDER, 0)
            self._update_item_text(item)

        def do_toggle_mark():
            cur = bool(item.data(self.ROLE_MARK))
            item.setData(self.ROLE_MARK, (not cur))
            self._update_item_text(item)

        act_set_order.triggered.connect(do_set_order)
        act_clear_order.triggered.connect(do_clear_order)
        act_toggle_mark.triggered.connect(do_toggle_mark)
        menu.exec(self.image_list.mapToGlobal(pos))
    
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
        
        self.preview_label.setText("⏳ 正在处理，请稍候...")
        # 使用主题色作为边框，窗口背景色作为底色
        pal = self.palette()
        try:
            win_col = pal.color(pal.ColorRole.Window)
            txt_col = pal.color(pal.ColorRole.Text)
            hi_col = pal.color(pal.ColorRole.Highlight)
        except Exception:
            win_col = pal.window().color()  # type: ignore
            txt_col = pal.text().color()    # type: ignore
            hi_col = pal.highlight().color()  # type: ignore
        self.preview_label.setStyleSheet(
            "QLabel { "
            f"background-color: rgb({win_col.red()},{win_col.green()},{win_col.blue()}); "
            f"border: 2px solid rgb({hi_col.red()},{hi_col.green()},{hi_col.blue()}); "
            "padding: 20px; "
            f"color: rgb({txt_col.red()},{txt_col.green()},{txt_col.blue()}); "
            "font-size: 14px; "
            "}"
        )
        self.result_image = None
        
        # 默认使用扫描模式
        mode = 'scans'
        mode_name = "扫描模式"
        
        # 读取用户选择（使用选中项，按行号顺序）
        selected_rows = sorted([ix.row() for ix in self.image_list.selectedIndexes()])
        selected_paths = [self.image_list.item(r).data(self.ROLE_PATH) for r in selected_rows]

        image_paths_for_job: List[str]
        if selected_paths:
            image_paths_for_job = selected_paths
        else:
            # 未选择则默认处理全部（按显示顺序）
            image_paths_for_job = []
            for i in range(self.image_list.count()):
                it = self.image_list.item(i)
                if it:
                    path = it.data(self.ROLE_PATH)
                    if path:
                        image_paths_for_job.append(path)

        if not image_paths_for_job:
            QMessageBox.warning(self, "警告", "目录中未找到可处理的图片")
            self.start_btn.setEnabled(True)
            self.browse_btn.setEnabled(True)
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
        # 自动保存结果
        try:
            base_dir = Path(self.dir_edit.text().strip() or Path.home())
            out_dir = base_dir / "stitch"
            out_dir.mkdir(parents=True, exist_ok=True)
            # 文件名：stitched_时间戳.png
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = out_dir / f"stitched_{ts}.png"
            encode_param = [int(cv2.IMWRITE_PNG_COMPRESSION), 3]
            success, encoded_img = cv2.imencode('.png', result, encode_param)
            if success:
                with open(file_path, 'wb') as f:
                    f.write(encoded_img.tobytes())
                self.log(f"💾 已自动保存结果: {file_path}")
            else:
                self.log("❌ 自动保存失败：编码失败")
        except Exception as e:
            self.log(f"❌ 自动保存异常: {e}")
        
        h, w = result.shape[:2]
        self.log(f"✅ 拼接成功！结果尺寸: {w} x {h} 像素")
        self.log("="*60)
        
        # 使用主题窗口底色 + 高亮色边框，避免硬编码白色
        pal = self.palette()
        try:
            win_col = pal.color(pal.ColorRole.Window)
            hi_col = pal.color(pal.ColorRole.Highlight)
        except Exception:
            win_col = pal.window().color()  # type: ignore
            hi_col = pal.highlight().color()  # type: ignore
        self.preview_label.setStyleSheet(
            "QLabel { "
            f"background-color: rgb({win_col.red()},{win_col.green()},{win_col.blue()}); "
            f"border: 2px solid rgb({hi_col.red()},{hi_col.green()},{hi_col.blue()}); "
            "}"
        )
        
        # 去掉强制弹窗，仅在日志中提示
        self.log("✅ 图片拼接完成，预览区已更新。结果已自动保存到输出目录 stitch。")
    
    def on_error(self, error_message: str):
        """处理错误"""
        self.log(f"❌ 错误: {error_message}")
        self.log("="*60)
        
        self.start_btn.setEnabled(True)
        self.browse_btn.setEnabled(True)
        
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
        self._set_result_pixmap_from_np(image)
        self._refresh_result_preview()

    def _set_result_pixmap_from_np(self, image: np.ndarray):
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        self._result_pixmap = QPixmap.fromImage(qt_image)

    def _refresh_result_preview(self):
        if not hasattr(self, '_result_pixmap') or self._result_pixmap.isNull():
            return
        # 根据容器尺寸自适应缩放
        avail = self.result_container.size()
        target = QSize(max(10, avail.width()-2), max(10, avail.height()-2))
        scaled = self._result_pixmap.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview_label.setPixmap(scaled)
        self.preview_label.setMinimumSize(1,1)
    
    def save_result(self):
        """保存结果"""
        if self.result_image is None:
            QMessageBox.warning(self, "警告", "没有可保存的结果")
            return
        
        # 默认保存到所选目录下的 stitch 子文件夹
        base_dir = Path(self.dir_edit.text().strip() or Path.home())
        default_dir = base_dir / "stitch"
        try:
            default_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        default_path = default_dir / "stitched_result.png"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存拼接结果", 
            str(default_path),
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
                except Exception:
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
            try:
                hl = pal.color(pal.ColorRole.Highlight)
                htxt = pal.color(pal.ColorRole.HighlightedText)
                txt = pal.color(pal.ColorRole.ButtonText)
                mid = pal.color(pal.ColorRole.Mid)
            except Exception:
                hl = pal.highlight().color()  # type: ignore
                htxt = pal.highlightedText().color()  # type: ignore
                txt = pal.buttonText().color()  # type: ignore
                mid = pal.mid().color()  # type: ignore
            base_txt = f"rgb({txt.red()},{txt.green()},{txt.blue()})"
            h_rgb = f"rgb({hl.red()},{hl.green()},{hl.blue()})"
            h_txt = f"rgb({htxt.red()},{htxt.green()},{htxt.blue()})"
            mid_rgba = f"rgba({mid.red()},{mid.green()},{mid.blue()},120)"
            mid_hover = f"rgba({mid.red()},{mid.green()},{mid.blue()},40)"
            self.toggle_button.setStyleSheet(
                """
                QPushButton {
                    border: 1px solid %s;
                    border-radius: 4px;      /* 小圆角，更紧凑 */
                    padding: 2px 6px;        /* 仅比文字高一点 */
                    min-height: 20px;        /* 紧凑高度 */
                    background-color: transparent;
                    color: %s;
                    text-align: center;
                }
                QPushButton:hover {
                    background-color: %s;
                }
                QPushButton:checked {
                    background-color: %s;
                    border-color: %s;
                    color: %s;
                }
                """ % (mid_rgba, base_txt, mid_hover, h_rgb, h_rgb, h_txt)
            )

    # 1. 直接在顶部放置“设置”内容（扁平化，不再使用折叠面板）
    top_settings = QVBoxLayout()
    top_settings.setContentsMargins(8,8,8,0)
    top_settings.setSpacing(6)
    dir_row = QHBoxLayout()
    self.dir_edit = QLineEdit()
    self.dir_edit.setPlaceholderText("请选择包含要拼接图片的目录...")
    self.browse_btn = QPushButton("浏览...")
    self.browse_btn.setProperty("btn", "secondary")
    self.browse_btn.clicked.connect(self.browse_directory)
    dir_row.addWidget(QLabel("目录:"))
    dir_row.addWidget(self.dir_edit, 1)
    dir_row.addWidget(self.browse_btn)
    top_settings.addLayout(dir_row)
    # 同行按钮
    btn_row = QHBoxLayout()
    btn_row.setSpacing(6)
    self.start_btn = QPushButton("🚀 开始拼接")
    self.start_btn.clicked.connect(self.start_stitching)
# 紧凑：降低按钮最小高度
self.start_btn.setMinimumHeight(22)
    self.start_btn.setProperty("btn", "primary")
    self.start_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    btn_row.addWidget(self.start_btn, 1)
    top_settings.addLayout(btn_row)
    # 进度条
    self.progress_bar = QProgressBar()
    pal = self.palette()
    try:
        hl = pal.color(pal.ColorRole.Highlight)
    except Exception:
        hl = pal.highlight().color()  # type: ignore
    self.progress_bar.setStyleSheet(
        "QProgressBar { border: 1px solid palette(Mid); border-radius: 4px; text-align: center; min-height: 12px;}"
        f"QProgressBar::chunk {{ background-color: rgb({hl.red()},{hl.green()},{hl.blue()}); }}"
    )
    top_settings.addWidget(self.progress_bar)
    # 挂到主布局顶部
    layout.addLayout(top_settings)

    # 2. 图片预览与选择 / 结果预览（合并面板）
    preview_box = CollapsibleBox("预览", default_open=True, expand_flex=False)
    preview_select_layout = QVBoxLayout()
    preview_select_layout.setContentsMargins(8,8,8,8)
    preview_select_layout.setSpacing(6)

    # 顶行：统计 + 选择操作按钮（同一行）
    top_bar = QHBoxLayout()
    self.selection_summary_label = QLabel("未加载目录")
    top_bar.addWidget(self.selection_summary_label)
    top_bar.addStretch()
    self.btn_select_all = QPushButton("全选")
    self.btn_select_none = QPushButton("全不选")
    self.btn_invert = QPushButton("反选")
    for b in (self.btn_select_all, self.btn_select_none, self.btn_invert):
        b.setMinimumHeight(28)
        b.setProperty("btn", "secondary")
        top_bar.addWidget(b)
    preview_select_layout.addLayout(top_bar)

    # 第二行：缩放 + 打开输出目录
    zoom_row = QHBoxLayout()
    zoom_row.addWidget(QLabel("缩放:"))
    self.thumb_size_label = QLabel(f"{self._thumb_size}px")
    zoom_row.addWidget(self.thumb_size_label)
    self.thumb_slider = QSlider(Qt.Horizontal)
    self.thumb_slider.setMinimum(10)
    self.thumb_slider.setMaximum(300)
    self.thumb_slider.setValue(self._thumb_size)
    self.thumb_slider.setToolTip("调整预览缩略图大小 (Ctrl+滚轮 也可缩放)")
    self.thumb_slider.valueChanged.connect(self._on_thumb_size_changed)
    zoom_row.addWidget(self.thumb_slider, 1)
    self.open_output_btn = QPushButton("打开")
    self.open_output_btn.setProperty("btn", "secondary")
    self.open_output_btn.setToolTip("打开输出目录 (stitch)")
    self.open_output_btn.clicked.connect(self.open_output_dir)
    zoom_row.addWidget(self.open_output_btn)
    preview_select_layout.addLayout(zoom_row)

    # 预览：图标平铺（正方形体块）
    self.image_list = self._create_image_list()

    # 选择按钮连接
    self.btn_select_all.clicked.connect(self._select_all)
    self.btn_select_none.clicked.connect(self._select_none)
    self.btn_invert.clicked.connect(self._invert_selection)

    # 合并：结果预览区域（右侧，自动缩放，无滚动条）
    self.result_container = QWidget()
    self.result_container.setMinimumHeight(260)
    rc_layout = QVBoxLayout(self.result_container)
    rc_layout.setContentsMargins(0,0,0,0)
    rc_layout.setSpacing(0)
    self.preview_label = QLabel("拼接结果将显示在这里")
    self.preview_label.setAlignment(Qt.AlignCenter)
    # 使用当前主题的窗口背景色和中间色设置初始底色和边框，避免纯白
    pal = self.palette()
    try:
        win_col = pal.color(pal.ColorRole.Window)
        mid_col = pal.color(pal.ColorRole.Mid)
        txt_col = pal.color(pal.ColorRole.Text)
    except Exception:
        win_col = pal.window().color()  # type: ignore
        mid_col = pal.mid().color()  # type: ignore
        txt_col = pal.text().color()  # type: ignore
    self.preview_label.setStyleSheet(
        "QLabel { "
        f"background-color: rgb({win_col.red()},{win_col.green()},{win_col.blue()}); "
        f"border: 2px dashed rgb({mid_col.red()},{mid_col.green()},{mid_col.blue()}); "
        "padding: 16px; "
        f"color: rgb({txt_col.red()},{txt_col.green()},{txt_col.blue()}); "
        "font-size: 13px; }"
    )
    self.preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    rc_layout.addWidget(self.preview_label, 1)
    def _rc_resize(ev):
        QWidget.resizeEvent(self.result_container, ev)
        self._refresh_result_preview()
    self.result_container.resizeEvent = _rc_resize

    # 左右结构：左（缩略图+操作）| 分隔线 | 右（结果预览）
    content_row = QHBoxLayout()
    content_row.setSpacing(6)
    left_col = QVBoxLayout()
    left_col.addWidget(self.image_list, 1)
    content_row.addLayout(left_col, 1)
    divider = QFrame()
    divider.setFrameShape(QFrame.VLine)
    divider.setFrameShadow(QFrame.Plain)
    divider.setLineWidth(1)
    content_row.addWidget(divider)
    content_row.addWidget(self.result_container, 1)
    preview_select_layout.addLayout(content_row)

    # 双击打开：为缩略图列表启用双击打开文件
    self.image_list.itemDoubleClicked.connect(self._on_item_double_clicked)
preview_box.setContentLayout(preview_select_layout)

    # 3. 日志
    log_box = CollapsibleBox("日志", default_open=True, expand_flex=True)
    log_layout = QVBoxLayout()
    self.log_text = QTextEdit()
    self.log_text.setReadOnly(True)
    self.log_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    log_layout.addWidget(self.log_text)
log_box.setContentLayout(log_layout)

# 使用垂直分割器使预览与日志可上下拖动
self.main_splitter = QSplitter(Qt.Vertical)
self.main_splitter.addWidget(preview_box)
self.main_splitter.addWidget(log_box)
self.main_splitter.setStretchFactor(0, 1)
self.main_splitter.setStretchFactor(1, 2)
layout.addWidget(self.main_splitter, 1)

    # 首先把提示文字写入日志
    self.log("✅ 程序已启动 - 使用 OpenCV Stitcher 专业拼接引擎")
    self.log("💡 提示：")
    self.log("• Created by AYE | Version 1.0.0 | 2025-10-12")
    self.log("• OpenCV Stitcher 是业界标准的图像拼接库")
    self.log("• 自动检测特征点并精确对齐")
    self.log("• 确保相邻图片有 30% 以上的重叠区域")
    self.log("• 当前默认使用‘扫描模式’，适合截图/文档")

    # 外部底端弹簧：始终存在于所有面板之后，保证折叠时整体贴顶
    layout.addStretch(1)

# ——— 全局按钮样式（更紧凑的圆角、padding 与高度） ———
    pal = self.palette()
    try:
        bg = pal.color(pal.ColorRole.Window)
        txt = pal.color(pal.ColorRole.ButtonText)
        hi = pal.color(pal.ColorRole.Highlight)
    except Exception:
        bg = pal.window().color()  # type: ignore
        txt = pal.buttonText().color()  # type: ignore
        hi = pal.highlight().color()  # type: ignore
    base_txt = f"rgba({txt.red()},{txt.green()},{txt.blue()},255)"
    hi_rgb = f"rgb({hi.red()},{hi.green()},{hi.blue()})"
    hi_hover = f"rgba({hi.red()},{hi.green()},{hi.blue()},0.85)"
    hi_press = f"rgba({hi.red()},{hi.green()},{hi.blue()},0.7)"
    sec_bg = f"rgba({bg.red()},{bg.green()},{bg.blue()},0.6)"
    sec_bor = f"rgba({txt.red()},{txt.green()},{txt.blue()},80)"
    self.setStyleSheet(self.styleSheet() + f"""
        QPushButton[btn="primary"] {{
            color: white;
            background-color: {hi_rgb};
            border: 1px solid {hi_rgb};
            border-radius: 6px;
            padding: 3px 8px;
            min-height: 20px;
            font-weight: 600;
        }}
        QPushButton[btn="primary"]:hover {{
            background-color: {hi_hover};
            border-color: {hi_hover};
        }}
        QPushButton[btn="primary"]:pressed {{
            background-color: {hi_press};
            border-color: {hi_press};
        }}
        QPushButton[btn="primary"]:disabled {{
            background-color: rgba(180,180,180,0.5);
            border-color: rgba(160,160,160,0.4);
            color: rgba(255,255,255,0.8);
        }}

        QPushButton[btn="secondary"] {{
            color: {base_txt};
            background-color: {sec_bg};
            border: 1px solid {sec_bor};
            border-radius: 4px;
            padding: 3px 8px;
            min-height: 20px;
        }}
        QPushButton[btn="secondary"]:hover {{
            background-color: rgba(127,127,127,0.15);
        }}
        QPushButton[btn="secondary"]:pressed {{
            background-color: rgba(127,127,127,0.25);
        }}
""")

    # 恢复 UI 状态（分割器尺寸、折叠状态）
    self._restore_ui_state(preview_box, log_box)

def _restore_ui_state(self, preview_box: QWidget, log_box: QWidget):
    settings = QSettings("AYE", "AutoStitcher")
    sizes = settings.value("splitter/sizes")
    if isinstance(sizes, list) and all(isinstance(x, int) for x in sizes):
        self.main_splitter.setSizes(sizes)  # type: ignore[arg-type]
    else:
        self.main_splitter.setSizes([400, 360])

    prev_exp = settings.value("collapsible/preview", True, bool)
    log_exp = settings.value("collapsible/log", True, bool)
    # 应用折叠状态
    try:
        preview_box.toggle_button.setChecked(bool(prev_exp))
        preview_box._on_toggle(bool(prev_exp))
    except Exception:
        pass
    try:
        log_box.toggle_button.setChecked(bool(log_exp))
        log_box._on_toggle(bool(log_exp))
    except Exception:
        pass

    # 恢复缩略图大小（若存在）
    thumb = settings.value("thumb/size")
    if isinstance(thumb, int) and 10 <= thumb <= 300:
        self.thumb_slider.setValue(thumb)

def closeEvent(self, event):  # type: ignore[override]
    # 保存分割器尺寸与折叠状态、缩略图尺寸
    try:
        settings = QSettings("AYE", "AutoStitcher")
        settings.setValue("splitter/sizes", self.main_splitter.sizes())
        # 折叠状态：通过查找 splitter 中的两个 CollapsibleBox
        if self.main_splitter.count() >= 2:
            w0 = self.main_splitter.widget(0)
            w1 = self.main_splitter.widget(1)
            try:
                settings.setValue("collapsible/preview", bool(w0.toggle_button.isChecked()))
            except Exception:
                pass
            try:
                settings.setValue("collapsible/log", bool(w1.toggle_button.isChecked()))
            except Exception:
                pass
        # 缩略图尺寸
        try:
            settings.setValue("thumb/size", int(self.thumb_slider.value()))
        except Exception:
            pass
    finally:
        super().closeEvent(event)

# 底部弹簧已移至 init_ui 内部末尾，且日志面板设置了更高的伸展因子

# ============ 预览表格与缩放 ============
def _create_image_list(self) -> QListWidget:
    lw = QListWidget()
    lw.setViewMode(QListView.IconMode)
    lw.setIconSize(self._calc_icon_size())
    lw.setResizeMode(QListView.Adjust)
    lw.setMovement(QListView.Static)
    lw.setSpacing(2)
    lw.setUniformItemSizes(True)
    lw.setSelectionMode(QListWidget.MultiSelection)
    lw.setContextMenuPolicy(Qt.CustomContextMenu)
    lw.customContextMenuRequested.connect(self._on_list_context_menu)
    # Ctrl+滚轮缩放
    lw.wheelEvent = self._make_ctrl_wheel_zoom(lw.wheelEvent)
    # 选择变化时更新统计
    lw.itemSelectionChanged.connect(self._on_selection_changed)
    self._apply_list_grid(lw)
    # 自定义选中叠加序号
    lw.setItemDelegate(self.ThumbDelegate(self))
    return lw

def _calc_icon_size(self):
    # 允许最小到 10px，最大 512px
    s = max(10, min(512, self._thumb_size))
    return QSize(s, s)

def _apply_list_grid(self, lw: QListWidget):
    # 根据图标尺寸设置网格，尽量紧凑
    s = self._calc_icon_size().width()
    lw.setGridSize(QSize(s + 8, s + 8))

class ThumbDelegate(QStyledItemDelegate):
        def __init__(self, parent):
            super().__init__(parent)
            self.parent = parent
        def paint(self, painter: QPainter, option, index):
            # 自绘缩略图，保证在正方形单元内最大化适配（等比居中），并绘制选中序号
            painter.save()
            r = option.rect
            # 绘制背景（使用系统样式提供的背景，确保主题一致）
            # 不主动填充背景，交给视图样式；只绘制图片
            try:
                item = self.parent.image_list.item(index.row())
                icon = item.icon() if item is not None else QIcon()
            except Exception:
                icon = QIcon()
            # 目标边长（留出少量边距）
            side = min(r.width(), r.height()) - 8
            if side < 2:
                side = max(1, side)
            # 从图标获取较大底图，再二次等比缩放，避免锯齿
            base_pix = icon.pixmap(512, 512) if not icon.isNull() else QPixmap()
            if not base_pix.isNull():
                scaled = base_pix.scaled(side, side, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                x = r.x() + (r.width() - scaled.width()) // 2
                y = r.y() + (r.height() - scaled.height()) // 2
                painter.drawPixmap(x, y, scaled)
            painter.restore()
            # 选中项叠加大序号
            w: QListWidget = self.parent.image_list
            sel = w.selectionModel().selectedIndexes()
            if not sel:
                return
            sel_sorted = sorted(sel, key=lambda ix: ix.row())
            row_to_order = {ix.row(): i+1 for i, ix in enumerate(sel_sorted)}
            if index.row() not in row_to_order:
                return
            order = row_to_order[index.row()]
            r = option.rect
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing, True)
            d = min(r.width(), r.height())
            radius = int(d*0.35)
            cx = r.center().x()
            cy = r.top() + radius + 6
            bg = QColor(0,0,0,160)
            pen = QPen(QColor(255,255,255,220))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(bg)
            painter.drawEllipse(QPoint(cx, cy), radius, radius)
            font = painter.font()
            font.setBold(True)
            font.setPointSize(max(12, int(radius*0.9)))
            painter.setFont(font)
            painter.setPen(QPen(QColor(255,255,255)))
            text_rect = QRect(cx-radius, cy-radius, radius*2, radius*2)
            painter.drawText(text_rect, Qt.AlignCenter, str(order))
            painter.restore()

    def _make_ctrl_wheel_zoom(self, original_handler):
        def handler(event):
            if event.modifiers() & Qt.ControlModifier:
                delta = event.angleDelta().y()
                step = 10 if delta > 0 else -10
                new_val = max(10, min(300, self.thumb_slider.value() + step))
                if new_val != self.thumb_slider.value():
                    self.thumb_slider.setValue(new_val)
                event.accept()
            else:
                original_handler(event)
        return handler

    def _on_thumb_size_changed(self, value: int):
        self._thumb_size = value
        self.thumb_size_label.setText(f"{value}px")
        # 更新图标大小
        if hasattr(self, 'image_list'):
            self.image_list.setIconSize(self._calc_icon_size())
            self._apply_list_grid(self.image_list)
            self.image_list.update()

    def _style_accent_button(self, btn: QPushButton):
        # 使用当前主题的高亮色作为按钮底色，保证文字可读性
        pal = self.palette()
        try:
            highlight = pal.color(pal.ColorRole.Highlight)
            text_col = pal.color(pal.ColorRole.HighlightedText)
        except Exception:
            highlight = pal.highlight().color()  # type: ignore
            text_col = pal.highlightedText().color()  # type: ignore
        bg = f"rgb({highlight.red()},{highlight.green()},{highlight.blue()})"
        fg = f"rgb({text_col.red()},{text_col.green()},{text_col.blue()})"
        btn.setStyleSheet(
            f"QPushButton {{ font-weight: 600; border-radius: 6px; padding: 8px 12px; background-color: {bg}; color: {fg}; }}"
            "QPushButton:disabled { opacity: 0.6; }"
        )

    def _update_summary(self):
        total = self.image_list.count() if hasattr(self, 'image_list') else 0
        selected = len(self.image_list.selectedIndexes()) if hasattr(self, 'image_list') else 0
        self.selection_summary_label.setText(f"已加载: {total} 张 | 已选择: {selected} 张")
        if hasattr(self, 'image_list'):
            self.image_list.viewport().update()

    def _select_all(self):
        self.image_list.selectAll()
        self._update_summary()

    def _select_none(self):
        self.image_list.clearSelection()
        self._update_summary()

    def _invert_selection(self):
        to_select = []
        to_deselect = []
        for i in range(self.image_list.count()):
            it = self.image_list.item(i)
            if it.isSelected():
                to_deselect.append(it)
            else:
                to_select.append(it)
        for it in to_deselect:
            it.setSelected(False)
        for it in to_select:
            it.setSelected(True)
        self._update_summary()

    def _on_selection_changed(self):
        self._update_summary()

    def _on_item_double_clicked(self, item: QListWidgetItem):
        """双击缩略图：用系统默认程序打开图片文件"""
        try:
            path = item.data(self.ROLE_PATH) if item else None
            if path and os.path.exists(path):
                if sys.platform.startswith('win'):
                    os.startfile(path)  # type: ignore[attr-defined]
                else:
                    QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            else:
                QMessageBox.information(self, "提示", "未找到有效的文件路径")
        except Exception as e:
            QMessageBox.warning(self, "打开失败", f"无法打开文件:\n{path}\n\n{e}")

    def open_output_dir(self):
        """打开输出目录（所选目录下的 stitch），不存在则创建"""
        try:
            base_dir = Path(self.dir_edit.text().strip() or Path.home())
            out_dir = base_dir / "stitch"
            out_dir.mkdir(parents=True, exist_ok=True)
            p = str(out_dir)
            if sys.platform.startswith('win'):
                os.startfile(p)  # type: ignore[attr-defined]
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(p))
        except Exception as e:
            QMessageBox.warning(self, "打开失败", f"无法打开输出目录:\n{e}")

    def _auto_order_by_name(self):
        # 取已选行按文件名排序后从1开始编号
        items = []
        for i in range(self.image_list.count()):
            it = self.image_list.item(i)
            if it and it.checkState() == Qt.Checked:
                path = it.data(self.ROLE_PATH)
                items.append((i, os.path.basename(path)))
        items.sort(key=lambda x: x[1].lower())
        for order, (i, _) in enumerate(items, start=1):
            it = self.image_list.item(i)
            it.setData(self.ROLE_ORDER, order)
            self._update_item_text(it)

    def _clear_order(self):
        for i in range(self.image_list.count()):
            it = self.image_list.item(i)
            if it:
                it.setData(self.ROLE_ORDER, 0)
                self._update_item_text(it)

    def _load_images_for_preview(self, directory: str):
        # 清空并填充列表
        self.image_list.clear()
        paths = stitcher.load_images(directory)
        for path in paths:
            self._add_image_item(path)
        self._update_summary()

    def _add_image_item(self, path: str):
        pix = QPixmap(path)
        icon = QIcon(pix)
        item = QListWidgetItem(icon, "")
        item.setData(self.ROLE_PATH, path)
        item.setFlags(item.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        item.setToolTip(os.path.basename(path))
        self.image_list.addItem(item)

    def _update_item_text(self, item: QListWidgetItem):
        # 保持无文字，使用工具提示展示文件名
        item.setText("")

    def _on_list_context_menu(self, pos: QPoint):
        item = self.image_list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        act_set_order = QAction("设置序号…", self)
        act_clear_order = QAction("清除序号", self)
        act_toggle_mark = QAction("切换标记", self)
        menu.addAction(act_set_order)
        menu.addAction(act_clear_order)
        menu.addSeparator()
        menu.addAction(act_toggle_mark)

        def do_set_order():
            val, ok = QInputDialog.getInt(self, "设置序号", "序号 (>=1):", value=max(1, int(item.data(self.ROLE_ORDER) or 1)), min=1, max=9999)
            if ok:
                item.setData(self.ROLE_ORDER, int(val))
                self._update_item_text(item)

        def do_clear_order():
            item.setData(self.ROLE_ORDER, 0)
            self._update_item_text(item)

        def do_toggle_mark():
            cur = bool(item.data(self.ROLE_MARK))
            item.setData(self.ROLE_MARK, (not cur))
            self._update_item_text(item)

        act_set_order.triggered.connect(do_set_order)
        act_clear_order.triggered.connect(do_clear_order)
        act_toggle_mark.triggered.connect(do_toggle_mark)
        menu.exec(self.image_list.mapToGlobal(pos))
    
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
        
        self.preview_label.setText("⏳ 正在处理，请稍候...")
        # 使用主题色作为边框，窗口背景色作为底色
        pal = self.palette()
        try:
            win_col = pal.color(pal.ColorRole.Window)
            txt_col = pal.color(pal.ColorRole.Text)
            hi_col = pal.color(pal.ColorRole.Highlight)
        except Exception:
            win_col = pal.window().color()  # type: ignore
            txt_col = pal.text().color()    # type: ignore
            hi_col = pal.highlight().color()  # type: ignore
        self.preview_label.setStyleSheet(
            "QLabel { "
            f"background-color: rgb({win_col.red()},{win_col.green()},{win_col.blue()}); "
            f"border: 2px solid rgb({hi_col.red()},{hi_col.green()},{hi_col.blue()}); "
            "padding: 20px; "
            f"color: rgb({txt_col.red()},{txt_col.green()},{txt_col.blue()}); "
            "font-size: 14px; "
            "}"
        )
        self.result_image = None
        
        # 默认使用扫描模式
        mode = 'scans'
        mode_name = "扫描模式"
        
        # 读取用户选择（使用选中项，按行号顺序）
        selected_rows = sorted([ix.row() for ix in self.image_list.selectedIndexes()])
        selected_paths = [self.image_list.item(r).data(self.ROLE_PATH) for r in selected_rows]

        image_paths_for_job: List[str]
        if selected_paths:
            image_paths_for_job = selected_paths
        else:
            # 未选择则默认处理全部（按显示顺序）
            image_paths_for_job = []
            for i in range(self.image_list.count()):
                it = self.image_list.item(i)
                if it:
                    path = it.data(self.ROLE_PATH)
                    if path:
                        image_paths_for_job.append(path)

        if not image_paths_for_job:
            QMessageBox.warning(self, "警告", "目录中未找到可处理的图片")
            self.start_btn.setEnabled(True)
            self.browse_btn.setEnabled(True)
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
        # 自动保存结果
        try:
            base_dir = Path(self.dir_edit.text().strip() or Path.home())
            out_dir = base_dir / "stitch"
            out_dir.mkdir(parents=True, exist_ok=True)
            # 文件名：stitched_时间戳.png
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = out_dir / f"stitched_{ts}.png"
            encode_param = [int(cv2.IMWRITE_PNG_COMPRESSION), 3]
            success, encoded_img = cv2.imencode('.png', result, encode_param)
            if success:
                with open(file_path, 'wb') as f:
                    f.write(encoded_img.tobytes())
                self.log(f"💾 已自动保存结果: {file_path}")
            else:
                self.log("❌ 自动保存失败：编码失败")
        except Exception as e:
            self.log(f"❌ 自动保存异常: {e}")
        
        h, w = result.shape[:2]
        self.log(f"✅ 拼接成功！结果尺寸: {w} x {h} 像素")
        self.log("="*60)
        
        # 使用主题窗口底色 + 高亮色边框，避免硬编码白色
        pal = self.palette()
        try:
            win_col = pal.color(pal.ColorRole.Window)
            hi_col = pal.color(pal.ColorRole.Highlight)
        except Exception:
            win_col = pal.window().color()  # type: ignore
            hi_col = pal.highlight().color()  # type: ignore
        self.preview_label.setStyleSheet(
            "QLabel { "
            f"background-color: rgb({win_col.red()},{win_col.green()},{win_col.blue()}); "
            f"border: 2px solid rgb({hi_col.red()},{hi_col.green()},{hi_col.blue()}); "
            "}"
        )
        
        # 去掉强制弹窗，仅在日志中提示
        self.log("✅ 图片拼接完成，预览区已更新。结果已自动保存到输出目录 stitch。")
    
    def on_error(self, error_message: str):
        """处理错误"""
        self.log(f"❌ 错误: {error_message}")
        self.log("="*60)
        
        self.start_btn.setEnabled(True)
        self.browse_btn.setEnabled(True)
        
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
        self._set_result_pixmap_from_np(image)
        self._refresh_result_preview()

    def _set_result_pixmap_from_np(self, image: np.ndarray):
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        self._result_pixmap = QPixmap.fromImage(qt_image)

    def _refresh_result_preview(self):
        if not hasattr(self, '_result_pixmap') or self._result_pixmap.isNull():
            return
        # 根据容器尺寸自适应缩放
        avail = self.result_container.size()
        target = QSize(max(10, avail.width()-2), max(10, avail.height()-2))
        scaled = self._result_pixmap.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview_label.setPixmap(scaled)
        self.preview_label.setMinimumSize(1,1)
    
    def save_result(self):
        """保存结果"""
        if self.result_image is None:
            QMessageBox.warning(self, "警告", "没有可保存的结果")
            return
        
        # 默认保存到所选目录下的 stitch 子文件夹
        base_dir = Path(self.dir_edit.text().strip() or Path.home())
        default_dir = base_dir / "stitch"
        try:
            default_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        default_path = default_dir / "stitched_result.png"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存拼接结果", 
            str(default_path),
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
    main()class ThumbDelegate(QStyledItemDelegate):
        def __init__(self, parent):
            super().__init__(parent)
            self.parent = parent
        def paint(self, painter: QPainter, option, index):
            # 自绘缩略图，保证在正方形单元内最大化适配（等比居中），并绘制选中序号
            painter.save()
            r = option.rect
            # 绘制背景（使用系统样式提供的背景，确保主题一致）
            # 不主动填充背景，交给视图样式；只绘制图片
            try:
                item = self.parent.image_list.item(index.row())
                icon = item.icon() if item is not None else QIcon()
            except Exception:
                icon = QIcon()
            # 目标边长（留出少量边距）
            side = min(r.width(), r.height()) - 8
            if side < 2:
                side = max(1, side)
            # 从图标获取较大底图，再二次等比缩放，避免锯齿
            base_pix = icon.pixmap(512, 512) if not icon.isNull() else QPixmap()
            if not base_pix.isNull():
                scaled = base_pix.scaled(side, side, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                x = r.x() + (r.width() - scaled.width()) // 2
                y = r.y() + (r.height() - scaled.height()) // 2
                painter.drawPixmap(x, y, scaled)
            painter.restore()
            # 选中项叠加大序号
            w: QListWidget = self.parent.image_list
            sel = w.selectionModel().selectedIndexes()
            if not sel:
                return
            sel_sorted = sorted(sel, key=lambda ix: ix.row())
            row_to_order = {ix.row(): i+1 for i, ix in enumerate(sel_sorted)}
            if index.row() not in row_to_order:
                return
            order = row_to_order[index.row()]
            r = option.rect
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing, True)
            d = min(r.width(), r.height())
            radius = int(d*0.35)
            cx = r.center().x()
            cy = r.top() + radius + 6
            bg = QColor(0,0,0,160)
            pen = QPen(QColor(255,255,255,220))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(bg)
            painter.drawEllipse(QPoint(cx, cy), radius, radius)
            font = painter.font()
            font.setBold(True)
            font.setPointSize(max(12, int(radius*0.9)))
            painter.setFont(font)
            painter.setPen(QPen(QColor(255,255,255)))
            text_rect = QRect(cx-radius, cy-radius, radius*2, radius*2)
            painter.drawText(text_rect, Qt.AlignCenter, str(order))
            painter.restore()

    def _make_ctrl_wheel_zoom(self, original_handler):
        def handler(event):
            if event.modifiers() & Qt.ControlModifier:
                delta = event.angleDelta().y()
                step = 10 if delta > 0 else -10
                new_val = max(10, min(300, self.thumb_slider.value() + step))
                if new_val != self.thumb_slider.value():
                    self.thumb_slider.setValue(new_val)
                event.accept()
            else:
                original_handler(event)
        return handler

    def _on_thumb_size_changed(self, value: int):
        self._thumb_size = value
        self.thumb_size_label.setText(f"{value}px")
        # 更新图标大小
        if hasattr(self, 'image_list'):
            self.image_list.setIconSize(self._calc_icon_size())
            self._apply_list_grid(self.image_list)
            self.image_list.update()

    def _style_accent_button(self, btn: QPushButton):
        # 使用当前主题的高亮色作为按钮底色，保证文字可读性
        pal = self.palette()
        try:
            highlight = pal.color(pal.ColorRole.Highlight)
            text_col = pal.color(pal.ColorRole.HighlightedText)
        except Exception:
            highlight = pal.highlight().color()  # type: ignore
            text_col = pal.highlightedText().color()  # type: ignore
        bg = f"rgb({highlight.red()},{highlight.green()},{highlight.blue()})"
        fg = f"rgb({text_col.red()},{text_col.green()},{text_col.blue()})"
        btn.setStyleSheet(
            f"QPushButton {{ font-weight: 600; border-radius: 6px; padding: 8px 12px; background-color: {bg}; color: {fg}; }}"
            "QPushButton:disabled { opacity: 0.6; }"
        )

    def _update_summary(self):
        total = self.image_list.count() if hasattr(self, 'image_list') else 0
        selected = len(self.image_list.selectedIndexes()) if hasattr(self, 'image_list') else 0
        self.selection_summary_label.setText(f"已加载: {total} 张 | 已选择: {selected} 张")
        if hasattr(self, 'image_list'):
            self.image_list.viewport().update()

    def _select_all(self):
        self.image_list.selectAll()
        self._update_summary()

    def _select_none(self):
        self.image_list.clearSelection()
        self._update_summary()

    def _invert_selection(self):
        to_select = []
        to_deselect = []
        for i in range(self.image_list.count()):
            it = self.image_list.item(i)
            if it.isSelected():
                to_deselect.append(it)
            else:
                to_select.append(it)
        for it in to_deselect:
            it.setSelected(False)
        for it in to_select:
            it.setSelected(True)
        self._update_summary()

    def _on_selection_changed(self):
        self._update_summary()

    def _on_item_double_clicked(self, item: QListWidgetItem):
        """双击缩略图：用系统默认程序打开图片文件"""
        try:
            path = item.data(self.ROLE_PATH) if item else None
            if path and os.path.exists(path):
                if sys.platform.startswith('win'):
                    os.startfile(path)  # type: ignore[attr-defined]
                else:
                    QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            else:
                QMessageBox.information(self, "提示", "未找到有效的文件路径")
        except Exception as e:
            QMessageBox.warning(self, "打开失败", f"无法打开文件:\n{path}\n\n{e}")

    def open_output_dir(self):
        """打开输出目录（所选目录下的 stitch），不存在则创建"""
        try:
            base_dir = Path(self.dir_edit.text().strip() or Path.home())
            out_dir = base_dir / "stitch"
            out_dir.mkdir(parents=True, exist_ok=True)
            p = str(out_dir)
            if sys.platform.startswith('win'):
                os.startfile(p)  # type: ignore[attr-defined]
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(p))
        except Exception as e:
            QMessageBox.warning(self, "打开失败", f"无法打开输出目录:\n{e}")

    def _auto_order_by_name(self):
        # 取已选行按文件名排序后从1开始编号
        items = []
        for i in range(self.image_list.count()):
            it = self.image_list.item(i)
            if it and it.checkState() == Qt.Checked:
                path = it.data(self.ROLE_PATH)
                items.append((i, os.path.basename(path)))
        items.sort(key=lambda x: x[1].lower())
        for order, (i, _) in enumerate(items, start=1):
            it = self.image_list.item(i)
            it.setData(self.ROLE_ORDER, order)
            self._update_item_text(it)

    def _clear_order(self):
        for i in range(self.image_list.count()):
            it = self.image_list.item(i)
            if it:
                it.setData(self.ROLE_ORDER, 0)
                self._update_item_text(it)

    def _load_images_for_preview(self, directory: str):
        # 清空并填充列表
        self.image_list.clear()
        paths = stitcher.load_images(directory)
        for path in paths:
            self._add_image_item(path)
        self._update_summary()

    def _add_image_item(self, path: str):
        pix = QPixmap(path)
        icon = QIcon(pix)
        item = QListWidgetItem(icon, "")
        item.setData(self.ROLE_PATH, path)
        item.setFlags(item.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        item.setToolTip(os.path.basename(path))
        self.image_list.addItem(item)

    def _update_item_text(self, item: QListWidgetItem):
        # 保持无文字，使用工具提示展示文件名
        item.setText("")

    def _on_list_context_menu(self, pos: QPoint):
        item = self.image_list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        act_set_order = QAction("设置序号…", self)
        act_clear_order = QAction("清除序号", self)
        act_toggle_mark = QAction("切换标记", self)
        menu.addAction(act_set_order)
        menu.addAction(act_clear_order)
        menu.addSeparator()
        menu.addAction(act_toggle_mark)

        def do_set_order():
            val, ok = QInputDialog.getInt(self, "设置序号", "序号 (>=1):", value=max(1, int(item.data(self.ROLE_ORDER) or 1)), min=1, max=9999)
            if ok:
                item.setData(self.ROLE_ORDER, int(val))
                self._update_item_text(item)

        def do_clear_order():
            item.setData(self.ROLE_ORDER, 0)
            self._update_item_text(item)

        def do_toggle_mark():
            cur = bool(item.data(self.ROLE_MARK))
            item.setData(self.ROLE_MARK, (not cur))
            self._update_item_text(item)

        act_set_order.triggered.connect(do_set_order)
        act_clear_order.triggered.connect(do_clear_order)
        act_toggle_mark.triggered.connect(do_toggle_mark)
        menu.exec(self.image_list.mapToGlobal(pos))
    
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
        
        self.preview_label.setText("⏳ 正在处理，请稍候...")
        # 使用主题色作为边框，窗口背景色作为底色
        pal = self.palette()
        try:
            win_col = pal.color(pal.ColorRole.Window)
            txt_col = pal.color(pal.ColorRole.Text)
            hi_col = pal.color(pal.ColorRole.Highlight)
        except Exception:
            win_col = pal.window().color()  # type: ignore
            txt_col = pal.text().color()    # type: ignore
            hi_col = pal.highlight().color()  # type: ignore
        self.preview_label.setStyleSheet(
            "QLabel { "
            f"background-color: rgb({win_col.red()},{win_col.green()},{win_col.blue()}); "
            f"border: 2px solid rgb({hi_col.red()},{hi_col.green()},{hi_col.blue()}); "
            "padding: 20px; "
            f"color: rgb({txt_col.red()},{txt_col.green()},{txt_col.blue()}); "
            "font-size: 14px; "
            "}"
        )
        self.result_image = None
        
        # 默认使用扫描模式
        mode = 'scans'
        mode_name = "扫描模式"
        
        # 读取用户选择（使用选中项，按行号顺序）
        selected_rows = sorted([ix.row() for ix in self.image_list.selectedIndexes()])
        selected_paths = [self.image_list.item(r).data(self.ROLE_PATH) for r in selected_rows]

        image_paths_for_job: List[str]
        if selected_paths:
            image_paths_for_job = selected_paths
        else:
            # 未选择则默认处理全部（按显示顺序）
            image_paths_for_job = []
            for i in range(self.image_list.count()):
                it = self.image_list.item(i)
                if it:
                    path = it.data(self.ROLE_PATH)
                    if path:
                        image_paths_for_job.append(path)

        if not image_paths_for_job:
            QMessageBox.warning(self, "警告", "目录中未找到可处理的图片")
            self.start_btn.setEnabled(True)
            self.browse_btn.setEnabled(True)
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
        # 自动保存结果
        try:
            base_dir = Path(self.dir_edit.text().strip() or Path.home())
            out_dir = base_dir / "stitch"
            out_dir.mkdir(parents=True, exist_ok=True)
            # 文件名：stitched_时间戳.png
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = out_dir / f"stitched_{ts}.png"
            encode_param = [int(cv2.IMWRITE_PNG_COMPRESSION), 3]
            success, encoded_img = cv2.imencode('.png', result, encode_param)
            if success:
                with open(file_path, 'wb') as f:
                    f.write(encoded_img.tobytes())
                self.log(f"💾 已自动保存结果: {file_path}")
            else:
                self.log("❌ 自动保存失败：编码失败")
        except Exception as e:
            self.log(f"❌ 自动保存异常: {e}")
        
        h, w = result.shape[:2]
        self.log(f"✅ 拼接成功！结果尺寸: {w} x {h} 像素")
        self.log("="*60)
        
        # 使用主题窗口底色 + 高亮色边框，避免硬编码白色
        pal = self.palette()
        try:
            win_col = pal.color(pal.ColorRole.Window)
            hi_col = pal.color(pal.ColorRole.Highlight)
        except Exception:
            win_col = pal.window().color()  # type: ignore
            hi_col = pal.highlight().color()  # type: ignore
        self.preview_label.setStyleSheet(
            "QLabel { "
            f"background-color: rgb({win_col.red()},{win_col.green()},{win_col.blue()}); "
            f"border: 2px solid rgb({hi_col.red()},{hi_col.green()},{hi_col.blue()}); "
            "}"
        )
        
        # 去掉强制弹窗，仅在日志中提示
        self.log("✅ 图片拼接完成，预览区已更新。结果已自动保存到输出目录 stitch。")
    
    def on_error(self, error_message: str):
        """处理错误"""
        self.log(f"❌ 错误: {error_message}")
        self.log("="*60)
        
        self.start_btn.setEnabled(True)
        self.browse_btn.setEnabled(True)
        
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
        self._set_result_pixmap_from_np(image)
        self._refresh_result_preview()

    def _set_result_pixmap_from_np(self, image: np.ndarray):
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        self._result_pixmap = QPixmap.fromImage(qt_image)

    def _refresh_result_preview(self):
        if not hasattr(self, '_result_pixmap') or self._result_pixmap.isNull():
            return
        # 根据容器尺寸自适应缩放
        avail = self.result_container.size()
        target = QSize(max(10, avail.width()-2), max(10, avail.height()-2))
        scaled = self._result_pixmap.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview_label.setPixmap(scaled)
        self.preview_label.setMinimumSize(1,1)
    
    def save_result(self):
        """保存结果"""
        if self.result_image is None:
            QMessageBox.warning(self, "警告", "没有可保存的结果")
            return
        
        # 默认保存到所选目录下的 stitch 子文件夹
        base_dir = Path(self.dir_edit.text().strip() or Path.home())
        default_dir = base_dir / "stitch"
        try:
            default_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        default_path = default_dir / "stitched_result.png"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存拼接结果", 
            str(default_path),
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
                except Exception:
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
            try:
                hl = pal.color(pal.ColorRole.Highlight)
                htxt = pal.color(pal.ColorRole.HighlightedText)
                txt = pal.color(pal.ColorRole.ButtonText)
                mid = pal.color(pal.ColorRole.Mid)
            except Exception:
                hl = pal.highlight().color()  # type: ignore
                htxt = pal.highlightedText().color()  # type: ignore
                txt = pal.buttonText().color()  # type: ignore
                mid = pal.mid().color()  # type: ignore
            base_txt = f"rgb({txt.red()},{txt.green()},{txt.blue()})"
            h_rgb = f"rgb({hl.red()},{hl.green()},{hl.blue()})"
            h_txt = f"rgb({htxt.red()},{htxt.green()},{htxt.blue()})"
            mid_rgba = f"rgba({mid.red()},{mid.green()},{mid.blue()},120)"
            mid_hover = f"rgba({mid.red()},{mid.green()},{mid.blue()},40)"
            self.toggle_button.setStyleSheet(
                """
                QPushButton {
                    border: 1px solid %s;
                    border-radius: 4px;      /* 小圆角，更紧凑 */
                    padding: 2px 6px;        /* 仅比文字高一点 */
                    min-height: 20px;        /* 紧凑高度 */
                    background-color: transparent;
                    color: %s;
                    text-align: center;
                }
                QPushButton:hover {
                    background-color: %s;
                }
                QPushButton:checked {
                    background-color: %s;
                    border-color: %s;
                    color: %s;
                }
                """ % (mid_rgba, base_txt, mid_hover, h_rgb, h_rgb, h_txt)
            )

    # 1. 直接在顶部放置“设置”内容（扁平化，不再使用折叠面板）
    top_settings = QVBoxLayout()
    top_settings.setContentsMargins(8,8,8,0)
    top_settings.setSpacing(6)
    dir_row = QHBoxLayout()
    self.dir_edit = QLineEdit()
    self.dir_edit.setPlaceholderText("请选择包含要拼接图片的目录...")
    self.browse_btn = QPushButton("浏览...")
    self.browse_btn.setProperty("btn", "secondary")
    self.browse_btn.clicked.connect(self.browse_directory)
    dir_row.addWidget(QLabel("目录:"))
    dir_row.addWidget(self.dir_edit, 1)
    dir_row.addWidget(self.browse_btn)
    top_settings.addLayout(dir_row)
    # 同行按钮
    btn_row = QHBoxLayout()
    btn_row.setSpacing(6)
    self.start_btn = QPushButton("🚀 开始拼接")
    self.start_btn.clicked.connect(self.start_stitching)
# 紧凑：降低按钮最小高度
self.start_btn.setMinimumHeight(22)
    self.start_btn.setProperty("btn", "primary")
    self.start_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    btn_row.addWidget(self.start_btn, 1)
    top_settings.addLayout(btn_row)
    # 进度条
    self.progress_bar = QProgressBar()
    pal = self.palette()
    try:
        hl = pal.color(pal.ColorRole.Highlight)
    except Exception:
        hl = pal.highlight().color()  # type: ignore
    self.progress_bar.setStyleSheet(
        "QProgressBar { border: 1px solid palette(Mid); border-radius: 4px; text-align: center; min-height: 12px;}"
        f"QProgressBar::chunk {{ background-color: rgb({hl.red()},{hl.green()},{hl.blue()}); }}"
    )
    top_settings.addWidget(self.progress_bar)
    # 挂到主布局顶部
    layout.addLayout(top_settings)

    # 2. 图片预览与选择 / 结果预览（合并面板）
    preview_box = CollapsibleBox("预览", default_open=True, expand_flex=False)
    preview_select_layout = QVBoxLayout()
    preview_select_layout.setContentsMargins(8,8,8,8)
    preview_select_layout.setSpacing(6)

    # 顶行：统计 + 选择操作按钮（同一行）
    top_bar = QHBoxLayout()
    self.selection_summary_label = QLabel("未加载目录")
    top_bar.addWidget(self.selection_summary_label)
    top_bar.addStretch()
    self.btn_select_all = QPushButton("全选")
    self.btn_select_none = QPushButton("全不选")
    self.btn_invert = QPushButton("反选")
    for b in (self.btn_select_all, self.btn_select_none, self.btn_invert):
        b.setMinimumHeight(28)
        b.setProperty("btn", "secondary")
        top_bar.addWidget(b)
    preview_select_layout.addLayout(top_bar)

    # 第二行：缩放 + 打开输出目录
    zoom_row = QHBoxLayout()
    zoom_row.addWidget(QLabel("缩放:"))
    self.thumb_size_label = QLabel(f"{self._thumb_size}px")
    zoom_row.addWidget(self.thumb_size_label)
    self.thumb_slider = QSlider(Qt.Horizontal)
    self.thumb_slider.setMinimum(10)
    self.thumb_slider.setMaximum(300)
    self.thumb_slider.setValue(self._thumb_size)
    self.thumb_slider.setToolTip("调整预览缩略图大小 (Ctrl+滚轮 也可缩放)")
    self.thumb_slider.valueChanged.connect(self._on_thumb_size_changed)
    zoom_row.addWidget(self.thumb_slider, 1)
    self.open_output_btn = QPushButton("打开")
    self.open_output_btn.setProperty("btn", "secondary")
    self.open_output_btn.setToolTip("打开输出目录 (stitch)")
    self.open_output_btn.clicked.connect(self.open_output_dir)
    zoom_row.addWidget(self.open_output_btn)
    preview_select_layout.addLayout(zoom_row)

    # 预览：图标平铺（正方形体块）
    self.image_list = self._create_image_list()

    # 选择按钮连接
    self.btn_select_all.clicked.connect(self._select_all)
    self.btn_select_none.clicked.connect(self._select_none)
    self.btn_invert.clicked.connect(self._invert_selection)

    # 合并：结果预览区域（右侧，自动缩放，无滚动条）
    self.result_container = QWidget()
    self.result_container.setMinimumHeight(260)
    rc_layout = QVBoxLayout(self.result_container)
    rc_layout.setContentsMargins(0,0,0,0)
    rc_layout.setSpacing(0)
    self.preview_label = QLabel("拼接结果将显示在这里")
    self.preview_label.setAlignment(Qt.AlignCenter)
    # 使用当前主题的窗口背景色和中间色设置初始底色和边框，避免纯白
    pal = self.palette()
    try:
        win_col = pal.color(pal.ColorRole.Window)
        mid_col = pal.color(pal.ColorRole.Mid)
        txt_col = pal.color(pal.ColorRole.Text)
    except Exception:
        win_col = pal.window().color()  # type: ignore
        mid_col = pal.mid().color()  # type: ignore
        txt_col = pal.text().color()  # type: ignore
    self.preview_label.setStyleSheet(
        "QLabel { "
        f"background-color: rgb({win_col.red()},{win_col.green()},{win_col.blue()}); "
        f"border: 2px dashed rgb({mid_col.red()},{mid_col.green()},{mid_col.blue()}); "
        "padding: 16px; "
        f"color: rgb({txt_col.red()},{txt_col.green()},{txt_col.blue()}); "
        "font-size: 13px; }"
    )
    self.preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    rc_layout.addWidget(self.preview_label, 1)
    def _rc_resize(ev):
        QWidget.resizeEvent(self.result_container, ev)
        self._refresh_result_preview()
    self.result_container.resizeEvent = _rc_resize

    # 左右结构：左（缩略图+操作）| 分隔线 | 右（结果预览）
    content_row = QHBoxLayout()
    content_row.setSpacing(6)
    left_col = QVBoxLayout()
    left_col.addWidget(self.image_list, 1)
    content_row.addLayout(left_col, 1)
    divider = QFrame()
    divider.setFrameShape(QFrame.VLine)
    divider.setFrameShadow(QFrame.Plain)
    divider.setLineWidth(1)
    content_row.addWidget(divider)
    content_row.addWidget(self.result_container, 1)
    preview_select_layout.addLayout(content_row)

    # 双击打开：为缩略图列表启用双击打开文件
    self.image_list.itemDoubleClicked.connect(self._on_item_double_clicked)
preview_box.setContentLayout(preview_select_layout)

    # 3. 日志
    log_box = CollapsibleBox("日志", default_open=True, expand_flex=True)
    log_layout = QVBoxLayout()
    self.log_text = QTextEdit()
    self.log_text.setReadOnly(True)
    self.log_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    log_layout.addWidget(self.log_text)
log_box.setContentLayout(log_layout)

# 使用垂直分割器使预览与日志可上下拖动
self.main_splitter = QSplitter(Qt.Vertical)
self.main_splitter.addWidget(preview_box)
self.main_splitter.addWidget(log_box)
self.main_splitter.setStretchFactor(0, 1)
self.main_splitter.setStretchFactor(1, 2)
layout.addWidget(self.main_splitter, 1)

    # 首先把提示文字写入日志
    self.log("✅ 程序已启动 - 使用 OpenCV Stitcher 专业拼接引擎")
    self.log("💡 提示：")
    self.log("• Created by AYE | Version 1.0.0 | 2025-10-12")
    self.log("• OpenCV Stitcher 是业界标准的图像拼接库")
    self.log("• 自动检测特征点并精确对齐")
    self.log("• 确保相邻图片有 30% 以上的重叠区域")
    self.log("• 当前默认使用‘扫描模式’，适合截图/文档")

    # 外部底端弹簧：始终存在于所有面板之后，保证折叠时整体贴顶
    layout.addStretch(1)

# ——— 全局按钮样式（更紧凑的圆角、padding 与高度） ———
    pal = self.palette()
    try:
        bg = pal.color(pal.ColorRole.Window)
        txt = pal.color(pal.ColorRole.ButtonText)
        hi = pal.color(pal.ColorRole.Highlight)
    except Exception:
        bg = pal.window().color()  # type: ignore
        txt = pal.buttonText().color()  # type: ignore
        hi = pal.highlight().color()  # type: ignore
    base_txt = f"rgba({txt.red()},{txt.green()},{txt.blue()},255)"
    hi_rgb = f"rgb({hi.red()},{hi.green()},{hi.blue()})"
    hi_hover = f"rgba({hi.red()},{hi.green()},{hi.blue()},0.85)"
    hi_press = f"rgba({hi.red()},{hi.green()},{hi.blue()},0.7)"
    sec_bg = f"rgba({bg.red()},{bg.green()},{bg.blue()},0.6)"
    sec_bor = f"rgba({txt.red()},{txt.green()},{txt.blue()},80)"
    self.setStyleSheet(self.styleSheet() + f"""
        QPushButton[btn="primary"] {{
            color: white;
            background-color: {hi_rgb};
            border: 1px solid {hi_rgb};
            border-radius: 6px;
            padding: 3px 8px;
            min-height: 20px;
            font-weight: 600;
        }}
        QPushButton[btn="primary"]:hover {{
            background-color: {hi_hover};
            border-color: {hi_hover};
        }}
        QPushButton[btn="primary"]:pressed {{
            background-color: {hi_press};
            border-color: {hi_press};
        }}
        QPushButton[btn="primary"]:disabled {{
            background-color: rgba(180,180,180,0.5);
            border-color: rgba(160,160,160,0.4);
            color: rgba(255,255,255,0.8);
        }}

        QPushButton[btn="secondary"] {{
            color: {base_txt};
            background-color: {sec_bg};
            border: 1px solid {sec_bor};
            border-radius: 4px;
            padding: 3px 8px;
            min-height: 20px;
        }}
        QPushButton[btn="secondary"]:hover {{
            background-color: rgba(127,127,127,0.15);
        }}
        QPushButton[btn="secondary"]:pressed {{
            background-color: rgba(127,127,127,0.25);
        }}
""")

    # 恢复 UI 状态（分割器尺寸、折叠状态）
    self._restore_ui_state(preview_box, log_box)

def _restore_ui_state(self, preview_box: QWidget, log_box: QWidget):
    settings = QSettings("AYE", "AutoStitcher")
    sizes = settings.value("splitter/sizes")
    if isinstance(sizes, list) and all(isinstance(x, int) for x in sizes):
        self.main_splitter.setSizes(sizes)  # type: ignore[arg-type]
    else:
        self.main_splitter.setSizes([400, 360])

    prev_exp = settings.value("collapsible/preview", True, bool)
    log_exp = settings.value("collapsible/log", True, bool)
    # 应用折叠状态
    try:
        preview_box.toggle_button.setChecked(bool(prev_exp))
        preview_box._on_toggle(bool(prev_exp))
    except Exception:
        pass
    try:
        log_box.toggle_button.setChecked(bool(log_exp))
        log_box._on_toggle(bool(log_exp))
    except Exception:
        pass

    # 恢复缩略图大小（若存在）
    thumb = settings.value("thumb/size")
    if isinstance(thumb, int) and 10 <= thumb <= 300:
        self.thumb_slider.setValue(thumb)

def closeEvent(self, event):  # type: ignore[override]
    # 保存分割器尺寸与折叠状态、缩略图尺寸
    try:
        settings = QSettings("AYE", "AutoStitcher")
        settings.setValue("splitter/sizes", self.main_splitter.sizes())
        # 折叠状态：通过查找 splitter 中的两个 CollapsibleBox
        if self.main_splitter.count() >= 2:
            w0 = self.main_splitter.widget(0)
            w1 = self.main_splitter.widget(1)
            try:
                settings.setValue("collapsible/preview", bool(w0.toggle_button.isChecked()))
            except Exception:
                pass
            try:
                settings.setValue("collapsible/log", bool(w1.toggle_button.isChecked()))
            except Exception:
                pass
        # 缩略图尺寸
        try:
            settings.setValue("thumb/size", int(self.thumb_slider.value()))
        except Exception:
            pass
    finally:
        super().closeEvent(event)

# 底部弹簧已移至 init_ui 内部末尾，且日志面板设置了更高的伸展因子

# ============ 预览表格与缩放 ============
def _create_image_list(self) -> QListWidget:
    lw = QListWidget()
    lw.setViewMode(QListView.IconMode)
    lw.setIconSize(self._calc_icon_size())
    lw.setResizeMode(QListView.Adjust)
    lw.setMovement(QListView.Static)
    lw.setSpacing(2)
    lw.setUniformItemSizes(True)
    lw.setSelectionMode(QListWidget.MultiSelection)
    lw.setContextMenuPolicy(Qt.CustomContextMenu)
    lw.customContextMenuRequested.connect(self._on_list_context_menu)
    # Ctrl+滚轮缩放
    lw.wheelEvent = self._make_ctrl_wheel_zoom(lw.wheelEvent)
    # 选择变化时更新统计
    lw.itemSelectionChanged.connect(self._on_selection_changed)
    self._apply_list_grid(lw)
    # 自定义选中叠加序号
    lw.setItemDelegate(self.ThumbDelegate(self))
    return lw

def _calc_icon_size(self):
    # 允许最小到 10px，最大 512px
    s = max(10, min(512, self._thumb_size))
    return QSize(s, s)

def _apply_list_grid(self, lw: QListWidget):
    # 根据图标尺寸设置网格，尽量紧凑
    s = self._calc_icon_size().width()
    lw.setGridSize(QSize(s + 8, s + 8))

class ThumbDelegate(QStyledItemDelegate):
        def __init__(self, parent):
            super().__init__(parent)
            self.parent = parent
        def paint(self, painter: QPainter, option, index):
            # 自绘缩略图，保证在正方形单元内最大化适配（等比居中），并绘制选中序号
            painter.save()
            r = option.rect
            # 绘制背景（使用系统样式提供的背景，确保主题一致）
            # 不主动填充背景，交给视图样式；只绘制图片
            try:
                item = self.parent.image_list.item(index.row())
                icon = item.icon() if item is not None else QIcon()
            except Exception:
                icon = QIcon()
            # 目标边长（留出少量边距）
            side = min(r.width(), r.height()) - 8
            if side < 2:
                side = max(1, side)
            # 从图标获取较大底图，再二次等比缩放，避免锯齿
            base_pix = icon.pixmap(512, 512) if not icon.isNull() else QPixmap()
            if not base_pix.isNull():
                scaled = base_pix.scaled(side, side, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                x = r.x() + (r.width() - scaled.width()) // 2
                y = r.y() + (r.height() - scaled.height()) // 2
                painter.drawPixmap(x, y, scaled)
            painter.restore()
            # 选中项叠加大序号
            w: QListWidget = self.parent.image_list
            sel = w.selectionModel().selectedIndexes()
            if not sel:
                return
            sel_sorted = sorted(sel, key=lambda ix: ix.row())
            row_to_order = {ix.row(): i+1 for i, ix in enumerate(sel_sorted)}
            if index.row() not in row_to_order:
                return
            order = row_to_order[index.row()]
            r = option.rect
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing, True)
            d = min(r.width(), r.height())
            radius = int(d*0.35)
            cx = r.center().x()
            cy = r.top() + radius + 6
            bg = QColor(0,0,0,160)
            pen = QPen(QColor(255,255,255,220))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(bg)
            painter.drawEllipse(QPoint(cx, cy), radius, radius)
            font = painter.font()
            font.setBold(True)
            font.setPointSize(max(12, int(radius*0.9)))
            painter.setFont(font)
            painter.setPen(QPen(QColor(255,255,255)))
            text_rect = QRect(cx-radius, cy-radius, radius*2, radius*2)
            painter.drawText(text_rect, Qt.AlignCenter, str(order))
            painter.restore()

    def _make_ctrl_wheel_zoom(self, original_handler):
        def handler(event):
            if event.modifiers() & Qt.ControlModifier:
                delta = event.angleDelta().y()
                step = 10 if delta > 0 else -10
                new_val = max(10, min(300, self.thumb_slider.value() + step))
                if new_val != self.thumb_slider.value():
                    self.thumb_slider.setValue(new_val)
                event.accept()
            else:
                original_handler(event)
        return handler

    def _on_thumb_size_changed(self, value: int):
        self._thumb_size = value
        self.thumb_size_label.setText(f"{value}px")
        # 更新图标大小
        if hasattr(self, 'image_list'):
            self.image_list.setIconSize(self._calc_icon_size())
            self._apply_list_grid(self.image_list)
            self.image_list.update()

    def _style_accent_button(self, btn: QPushButton):
        # 使用当前主题的高亮色作为按钮底色，保证文字可读性
        pal = self.palette()
        try:
            highlight = pal.color(pal.ColorRole.Highlight)
            text_col = pal.color(pal.ColorRole.HighlightedText)
        except Exception:
            highlight = pal.highlight().color()  # type: ignore
            text_col = pal.highlightedText().color()  # type: ignore
        bg = f"rgb({highlight.red()},{highlight.green()},{highlight.blue()})"
        fg = f"rgb({text_col.red()},{text_col.green()},{text_col.blue()})"
        btn.setStyleSheet(
            f"QPushButton {{ font-weight: 600; border-radius: 6px; padding: 8px 12px; background-color: {bg}; color: {fg}; }}"
            "QPushButton:disabled { opacity: 0.6; }"
        )

    def _update_summary(self):
        total = self.image_list.count() if hasattr(self, 'image_list') else 0
        selected = len(self.image_list.selectedIndexes()) if hasattr(self, 'image_list') else 0
        self.selection_summary_label.setText(f"已加载: {total} 张 | 已选择: {selected} 张")
        if hasattr(self, 'image_list'):
            self.image_list.viewport().update()

    def _select_all(self):
        self.image_list.selectAll()
        self._update_summary()

    def _select_none(self):
        self.image_list.clearSelection()
        self._update_summary()

    def _invert_selection(self):
        to_select = []
        to_deselect = []
        for i in range(self.image_list.count()):
            it = self.image_list.item(i)
            if it.isSelected():
                to_deselect.append(it)
            else:
                to_select.append(it)
        for it in to_deselect:
            it.setSelected(False)
        for it in to_select:
            it.setSelected(True)
        self._update_summary()

    def _on_selection_changed(self):
        self._update_summary()

    def _on_item_double_clicked(self, item: QListWidgetItem):
        """双击缩略图：用系统默认程序打开图片文件"""
        try:
            path = item.data(self.ROLE_PATH) if item else None
            if path and os.path.exists(path):
                if sys.platform.startswith('win'):
                    os.startfile(path)  # type: ignore[attr-defined]
                else:
                    QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            else:
                QMessageBox.information(self, "提示", "未找到有效的文件路径")
        except Exception as e:
            QMessageBox.warning(self, "打开失败", f"无法打开文件:\n{path}\n\n{e}")

    def open_output_dir(self):
        """打开输出目录（所选目录下的 stitch），不存在则创建"""
        try:
            base_dir = Path(self.dir_edit.text().strip() or Path.home())
            out_dir = base_dir / "stitch"
            out_dir.mkdir(parents=True, exist_ok=True)
            p = str(out_dir)
            if sys.platform.startswith('win'):
                os.startfile(p)  # type: ignore[attr-defined]
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(p))
        except Exception as e:
            QMessageBox.warning(self, "打开失败", f"无法打开输出目录:\n{e}")

    def _auto_order_by_name(self):
        # 取已选行按文件名排序后从1开始编号
        items = []
        for i in range(self.image_list.count()):
            it = self.image_list.item(i)
            if it and it.checkState() == Qt.Checked:
                path = it.data(self.ROLE_PATH)
                items.append((i, os.path.basename(path)))
        items.sort(key=lambda x: x[1].lower())
        for order, (i, _) in enumerate(items, start=1):
            it = self.image_list.item(i)
            it.setData(self.ROLE_ORDER, order)
            self._update_item_text(it)

    def _clear_order(self):
        for i in range(self.image_list.count()):
            it = self.image_list.item(i)
            if it:
                it.setData(self.ROLE_ORDER, 0)
                self._update_item_text(it)

    def _load_images_for_preview(self, directory: str):
        # 清空并填充列表
        self.image_list.clear()
        paths = stitcher.load_images(directory)
        for path in paths:
            self._add_image_item(path)
        self._update_summary()

    def _add_image_item(self, path: str):
        pix = QPixmap(path)
        icon = QIcon(pix)
        item = QListWidgetItem(icon, "")
        item.setData(self.ROLE_PATH, path)
        item.setFlags(item.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        item.setToolTip(os.path.basename(path))
        self.image_list.addItem(item)

    def _update_item_text(self, item: QListWidgetItem):
        # 保持无文字，使用工具提示展示文件名
        item.setText("")

    def _on_list_context_menu(self, pos: QPoint):
        item = self.image_list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        act_set_order = QAction("设置序号…", self)
        act_clear_order = QAction("清除序号", self)
        act_toggle_mark = QAction("切换标记", self)
        menu.addAction(act_set_order)
        menu.addAction(act_clear_order)
        menu.addSeparator()
        menu.addAction(act_toggle_mark)

        def do_set_order():
            val, ok = QInputDialog.getInt(self, "设置序号", "序号 (>=1):", value=max(1, int(item.data(self.ROLE_ORDER) or 1)), min=1, max=9999)
            if ok:
                item.setData(self.ROLE_ORDER, int(val))
                self._update_item_text(item)

        def do_clear_order():
            item.setData(self.ROLE_ORDER, 0)
            self._update_item_text(item)

        def do_toggle_mark():
            cur = bool(item.data(self.ROLE_MARK))
            item.setData(self.ROLE_MARK, (not cur))
            self._update_item_text(item)

        act_set_order.triggered.connect(do_set_order)
        act_clear_order.triggered.connect(do_clear_order)
        act_toggle_mark.triggered.connect(do_toggle_mark)
        menu.exec(self.image_list.mapToGlobal(pos))
    
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
        
        self.preview_label.setText("⏳ 正在处理，请稍候...")
        # 使用主题色作为边框，窗口背景色作为底色
        pal = self.palette()
        try:
            win_col = pal.color(pal.ColorRole.Window)
            txt_col = pal.color(pal.ColorRole.Text)
            hi_col = pal.color(pal.ColorRole.Highlight)
        except Exception:
            win_col = pal.window().color()  # type: ignore
            txt_col = pal.text().color()    # type: ignore
            hi_col = pal.highlight().color()  # type: ignore
        self.preview_label.setStyleSheet(
            "QLabel { "
            f"background-color: rgb({win_col.red()},{win_col.green()},{win_col.blue()}); "
            f"border: 2px solid rgb({hi_col.red()},{hi_col.green()},{hi_col.blue()}); "
            "padding: 20px; "
            f"color: rgb({txt_col.red()},{txt_col.green()},{txt_col.blue()}); "
            "font-size: 14px; "
            "}"
        )
        self.result_image = None
        
        # 默认使用扫描模式
        mode = 'scans'
        mode_name = "扫描模式"
        
        # 读取用户选择（使用选中项，按行号顺序）
        selected_rows = sorted([ix.row() for ix in self.image_list.selectedIndexes()])
        selected_paths = [self.image_list.item(r).data(self.ROLE_PATH) for r in selected_rows]

        image_paths_for_job: List[str]
        if selected_paths:
            image_paths_for_job = selected_paths
        else:
            # 未选择则默认处理全部（按显示顺序）
            image_paths_for_job = []
            for i in range(self.image_list.count()):
                it = self.image_list.item(i)
                if it:
                    path = it.data(self.ROLE_PATH)
                    if path:
                        image_paths_for_job.append(path)

        if not image_paths_for_job:
            QMessageBox.warning(self, "警告", "目录中未找到可处理的图片")
            self.start_btn.setEnabled(True)
            self.browse_btn.setEnabled(True)
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
        # 自动保存结果
        try:
            base_dir = Path(self.dir_edit.text().strip() or Path.home())
            out_dir = base_dir / "stitch"
            out_dir.mkdir(parents=True, exist_ok=True)
            # 文件名：stitched_时间戳.png
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = out_dir / f"stitched_{ts}.png"
            encode_param = [int(cv2.IMWRITE_PNG_COMPRESSION), 3]
            success, encoded_img = cv2.imencode('.png', result, encode_param)
            if success:
                with open(file_path, 'wb') as f:
                    f.write(encoded_img.tobytes())
                self.log(f"💾 已自动保存结果: {file_path}")
            else:
                self.log("❌ 自动保存失败：编码失败")
        except Exception as e:
            self.log(f"❌ 自动保存异常: {e}")
        
        h, w = result.shape[:2]
        self.log(f"✅ 拼接成功！结果尺寸: {w} x {h} 像素")
        self.log("="*60)
        
        # 使用主题窗口底色 + 高亮色边框，避免硬编码白色
        pal = self.palette()
        try:
            win_col = pal.color(pal.ColorRole.Window)
            hi_col = pal.color(pal.ColorRole.Highlight)
        except Exception:
            win_col = pal.window().color()  # type: ignore
            hi_col = pal.highlight().color()  # type: ignore
        self.preview_label.setStyleSheet(
            "QLabel { "
            f"background-color: rgb({win_col.red()},{win_col.green()},{win_col.blue()}); "
            f"border: 2px solid rgb({hi_col.red()},{hi_col.green()},{hi_col.blue()}); "
            "}"
        )
        
        # 去掉强制弹窗，仅在日志中提示
        self.log("✅ 图片拼接完成，预览区已更新。结果已自动保存到输出目录 stitch。")
    
    def on_error(self, error_message: str):
        """处理错误"""
        self.log(f"❌ 错误: {error_message}")
        self.log("="*60)
        
        self.start_btn.setEnabled(True)
        self.browse_btn.setEnabled(True)
        
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
        self._set_result_pixmap_from_np(image)
        self._refresh_result_preview()

    def _set_result_pixmap_from_np(self, image: np.ndarray):
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        self._result_pixmap = QPixmap.fromImage(qt_image)

    def _refresh_result_preview(self):
        if not hasattr(self, '_result_pixmap') or self._result_pixmap.isNull():
            return
        # 根据容器尺寸自适应缩放
        avail = self.result_container.size()
        target = QSize(max(10, avail.width()-2), max(10, avail.height()-2))
        scaled = self._result_pixmap.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview_label.setPixmap(scaled)
        self.preview_label.setMinimumSize(1,1)
    
    def save_result(self):
        """保存结果"""
        if self.result_image is None:
            QMessageBox.warning(self, "警告", "没有可保存的结果")
            return
        
        # 默认保存到所选目录下的 stitch 子文件夹
        base_dir = Path(self.dir_edit.text().strip() or Path.home())
        default_dir = base_dir / "stitch"
        try:
            default_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        default_path = default_dir / "stitched_result.png"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存拼接结果", 
            str(default_path),
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
    main()class ThumbDelegate(QStyledItemDelegate):
        def __init__(self, parent):
            super().__init__(parent)
            self.parent = parent
        def paint(self, painter: QPainter, option, index):
            # 自绘缩略图，保证在正方形单元内最大化适配（等比居中），并绘制选中序号
            painter.save()
            r = option.rect
            # 绘制背景（使用系统样式提供的背景，确保主题一致）
            # 不主动填充背景，交给视图样式；只绘制图片
            try:
                item = self.parent.image_list.item(index.row())
                icon = item.icon() if item is not None else QIcon()
            except Exception:
                icon = QIcon()
            # 目标边长（留出少量边距）
            side = min(r.width(), r.height()) - 8
            if side < 2:
                side = max(1, side)
            # 从图标获取较大底图，再二次等比缩放，避免锯齿
            base_pix = icon.pixmap(512, 512) if not icon.isNull() else QPixmap()
            if not base_pix.isNull():
                scaled = base_pix.scaled(side, side, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                x = r.x() + (r.width() - scaled.width()) // 2
                y = r.y() + (r.height() - scaled.height()) // 2
                painter.drawPixmap(x, y, scaled)
            painter.restore()
            # 选中项叠加大序号
            w: QListWidget = self.parent.image_list
            sel = w.selectionModel().selectedIndexes()
            if not sel:
                return
            sel_sorted = sorted(sel, key=lambda ix: ix.row())
            row_to_order = {ix.row(): i+1 for i, ix in enumerate(sel_sorted)}
            if index.row() not in row_to_order:
                return
            order = row_to_order[index.row()]
            r = option.rect
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing, True)
            d = min(r.width(), r.height())
            radius = int(d*0.35)
            cx = r.center().x()
            cy = r.top() + radius + 6
            bg = QColor(0,0,0,160)
            pen = QPen(QColor(255,255,255,220))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(bg)
            painter.drawEllipse(QPoint(cx, cy), radius, radius)
            font = painter.font()
            font.setBold(True)
            font.setPointSize(max(12, int(radius*0.9)))
            painter.setFont(font)
            painter.setPen(QPen(QColor(255,255,255)))
            text_rect = QRect(cx-radius, cy-radius, radius*2, radius*2)
            painter.drawText(text_rect, Qt.AlignCenter, str(order))
            painter.restore()

    def _make_ctrl_wheel_zoom(self, original_handler):
        def handler(event):
            if event.modifiers() & Qt.ControlModifier:
                delta = event.angleDelta().y()
                step = 10 if delta > 0 else -10
                new_val = max(10, min(300, self.thumb_slider.value() + step))
                if new_val != self.thumb_slider.value():
                    self.thumb_slider.setValue(new_val)
                event.accept()
            else:
                original_handler(event)
        return handler

    def _on_thumb_size_changed(self, value: int):
        self._thumb_size = value
        self.thumb_size_label.setText(f"{value}px")
        # 更新图标大小
        if hasattr(self, 'image_list'):
            self.image_list.setIconSize(self._calc_icon_size())
            self._apply_list_grid(self.image_list)
            self.image_list.update()

    def _style_accent_button(self, btn: QPushButton):
        # 使用当前主题的高亮色作为按钮底色，保证文字可读性
        pal = self.palette()
        try:
            highlight = pal.color(pal.ColorRole.Highlight)
            text_col = pal.color(pal.ColorRole.HighlightedText)
        except Exception:
            highlight = pal.highlight().color()  # type: ignore
            text_col = pal.highlightedText().color()  # type: ignore
        bg = f"rgb({highlight.red()},{highlight.green()},{highlight.blue()})"
        fg = f"rgb({text_col.red()},{text_col.green()},{text_col.blue()})"
        btn.setStyleSheet(
            f"QPushButton {{ font-weight: 600; border-radius: 6px; padding: 8px 12px; background-color: {bg}; color: {fg}; }}"
            "QPushButton:disabled { opacity: 0.6; }"
        )

    def _update_summary(self):
        total = self.image_list.count() if hasattr(self, 'image_list') else 0
        selected = len(self.image_list.selectedIndexes()) if hasattr(self, 'image_list') else 0
        self.selection_summary_label.setText(f"已加载: {total} 张 | 已选择: {selected} 张")
        if hasattr(self, 'image_list'):
            self.image_list.viewport().update()

    def _select_all(self):
        self.image_list.selectAll()
        self._update_summary()

    def _select_none(self):
        self.image_list.clearSelection()
        self._update_summary()

    def _invert_selection(self):
        to_select = []
        to_deselect = []
        for i in range(self.image_list.count()):
            it = self.image_list.item(i)
            if it.isSelected():
                to_deselect.append(it)
            else:
                to_select.append(it)
        for it in to_deselect:
            it.setSelected(False)
        for it in to_select:
            it.setSelected(True)
        self._update_summary()

    def _on_selection_changed(self):
        self._update_summary()

    def _on_item_double_clicked(self, item: QListWidgetItem):
        """双击缩略图：用系统默认程序打开图片文件"""
        try:
            path = item.data(self.ROLE_PATH) if item else None
            if path and os.path.exists(path):
                if sys.platform.startswith('win'):
                    os.startfile(path)  # type: ignore[attr-defined]
                else:
                    QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            else:
                QMessageBox.information(self, "提示", "未找到有效的文件路径")
        except Exception as e:
            QMessageBox.warning(self, "打开失败", f"无法打开文件:\n{path}\n\n{e}")

    def open_output_dir(self):
        """打开输出目录（所选目录下的 stitch），不存在则创建"""
        try:
            base_dir = Path(self.dir_edit.text().strip() or Path.home())
            out_dir = base_dir / "stitch"
            out_dir.mkdir(parents=True, exist_ok=True)
            p = str(out_dir)
            if sys.platform.startswith('win'):
                os.startfile(p)  # type: ignore[attr-defined]
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(p))
        except Exception as e:
            QMessageBox.warning(self, "打开失败", f"无法打开输出目录:\n{e}")

    def _auto_order_by_name(self):
        # 取已选行按文件名排序后从1开始编号
        items = []
        for i in range(self.image_list.count()):
            it = self.image_list.item(i)
            if it and it.checkState() == Qt.Checked:
                path = it.data(self.ROLE_PATH)
                items.append((i, os.path.basename(path)))
        items.sort(key=lambda x: x[1].lower())
        for order, (i, _) in enumerate(items, start=1):
            it = self.image_list.item(i)
            it.setData(self.ROLE_ORDER, order)
            self._update_item_text(it)

    def _clear_order(self):
        for i in range(self.image_list.count()):
            it = self.image_list.item(i)
            if it:
                it.setData(self.ROLE_ORDER, 0)
                self._update_item_text(it)

    def _load_images_for_preview(self, directory: str):
        # 清空并填充列表
        self.image_list.clear()
        paths = stitcher.load_images(directory)
        for path in paths:
            self._add_image_item(path)
        self._update_summary()

    def _add_image_item(self, path: str):
        pix = QPixmap(path)
        icon = QIcon(pix)
        item = QListWidgetItem(icon, "")
        item.setData(self.ROLE_PATH, path)
        item.setFlags(item.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        item.setToolTip(os.path.basename(path))
        self.image_list.addItem(item)

    def _update_item_text(self, item: QListWidgetItem):
        # 保持无文字，使用工具提示展示文件名
        item.setText("")

    def _on_list_context_menu(self, pos: QPoint):
        item = self.image_list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        act_set_order = QAction("设置序号…", self)
        act_clear_order = QAction("清除序号", self)
        act_toggle_mark = QAction("切换标记", self)
        menu.addAction(act_set_order)
        menu.addAction(act_clear_order)
        menu.addSeparator()
        menu.addAction(act_toggle_mark)

        def do_set_order():
            val, ok = QInputDialog.getInt(self, "设置序号", "序号 (>=1):", value=max(1, int(item.data(self.ROLE_ORDER) or 1)), min=1, max=9999)
            if ok:
                item.setData(self.ROLE_ORDER, int(val))
                self._update_item_text(item)

        def do_clear_order():
            item.setData(self.ROLE_ORDER, 0)
            self._update_item_text(item)

        def do_toggle_mark():
            cur = bool(item.data(self.ROLE_MARK))
            item.setData(self.ROLE_MARK, (not cur))
            self._update_item_text(item)

        act_set_order.triggered.connect(do_set_order)
        act_clear_order.triggered.connect(do_clear_order)
        act_toggle_mark.triggered.connect(do_toggle_mark)
        menu.exec(self.image_list.mapToGlobal(pos))
    
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
        
        self.preview_label.setText("⏳ 正在处理，请稍候...")
        # 使用主题色作为边框，窗口背景色作为底色
        pal = self.palette()
        try:
            win_col = pal.color(pal.ColorRole.Window)
            txt_col = pal.color(pal.ColorRole.Text)
            hi_col = pal.color(pal.ColorRole.Highlight)
        except Exception:
            win_col = pal.window().color()  # type: ignore
            txt_col = pal.text().color()    # type: ignore
            hi_col = pal.highlight().color()  # type: ignore
        self.preview_label.setStyleSheet(
            "QLabel { "
            f"background-color: rgb({win_col.red()},{win_col.green()},{win_col.blue()}); "
            f"border: 2px solid rgb({hi_col.red()},{hi_col.green()},{hi_col.blue()}); "
            "padding: 20px; "
            f"color: rgb({txt_col.red()},{txt_col.green()},{txt_col.blue()}); "
            "font-size: 14px; "
            "}"
        )
        self.result_image = None
        
        # 默认使用扫描模式
        mode = 'scans'
        mode_name = "扫描模式"
        
        # 读取用户选择（使用选中项，按行号顺序）
        selected_rows = sorted([ix.row() for ix in self.image_list.selectedIndexes()])
        selected_paths = [self.image_list.item(r).data(self.ROLE_PATH) for r in selected_rows]

        image_paths_for_job: List[str]
        if selected_paths:
            image_paths_for_job = selected_paths
        else:
            # 未选择则默认处理全部（按显示顺序）
            image_paths_for_job = []
            for i in range(self.image_list.count()):
                it = self.image_list.item(i)
                if it:
                    path = it.data(self.ROLE_PATH)
                    if path:
                        image_paths_for_job.append(path)

        if not image_paths_for_job:
            QMessageBox.warning(self, "警告", "目录中未找到可处理的图片")
            self.start_btn.setEnabled(True)
            self.browse_btn.setEnabled(True)
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
        # 自动保存结果
        try:
            base_dir = Path(self.dir_edit.text().strip() or Path.home())
            out_dir = base_dir / "stitch"
            out_dir.mkdir(parents=True, exist_ok=True)
            # 文件名：stitched_时间戳.png
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = out_dir / f"stitched_{ts}.png"
            encode_param = [int(cv2.IMWRITE_PNG_COMPRESSION), 3]
            success, encoded_img = cv2.imencode('.png', result, encode_param)
            if success:
                with open(file_path, 'wb') as f:
                    f.write(encoded_img.tobytes())
                self.log(f"💾 已自动保存结果: {file_path}")
            else:
                self.log("❌ 自动保存失败：编码失败")
        except Exception as e:
            self.log(f"❌ 自动保存异常: {e}")
        
        h, w = result.shape[:2]
        self.log(f"✅ 拼接成功！结果尺寸: {w} x {h} 像素")
        self.log("="*60)
        
        # 使用主题窗口底色 + 高亮色边框，避免硬编码白色
        pal = self.palette()
        try:
            win_col = pal.color(pal.ColorRole.Window)
            hi_col = pal.color(pal.ColorRole.Highlight)
        except Exception:
            win_col = pal.window().color()  # type: ignore
            hi_col = pal.highlight().color()  # type: ignore
        self.preview_label.setStyleSheet(
            "QLabel { "
            f"background-color: rgb({win_col.red()},{win_col.green()},{win_col.blue()}); "
            f"border: 2px solid rgb({hi_col.red()},{hi_col.green()},{hi_col.blue()}); "
            "}"
        )
        
        # 去掉强制弹窗，仅在日志中提示
        self.log("✅ 图片拼接完成，预览区已更新。结果已自动保存到输出目录 stitch。")
    
    def on_error(self, error_message: str):
        """处理错误"""
        self.log(f"❌ 错误: {error_message}")
        self.log("="*60)
        
        self.start_btn.setEnabled(True)
        self.browse_btn.setEnabled(True)
        
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
        self._set_result_pixmap_from_np(image)
        self._refresh_result_preview()

    def _set_result_pixmap_from_np(self, image: np.ndarray):
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        self._result_pixmap = QPixmap.fromImage(qt_image)

    def _refresh_result_preview(self):
        if not hasattr(self, '_result_pixmap') or self._result_pixmap.isNull():
            return
        # 根据容器尺寸自适应缩放
        avail = self.result_container.size()
        target = QSize(max(10, avail.width()-2), max(10, avail.height()-2))
        scaled = self._result_pixmap.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview_label.setPixmap(scaled)
        self.preview_label.setMinimumSize(1,1)
    
    def save_result(self):
        """保存结果"""
        if self.result_image is None:
            QMessageBox.warning(self, "警告", "没有可保存的结果")
            return
        
        # 默认保存到所选目录下的 stitch 子文件夹
        base_dir = Path(self.dir_edit.text().strip() or Path.home())
        default_dir = base_dir / "stitch"
        try:
            default_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        default_path = default_dir / "stitched_result.png"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存拼接结果", 
            str(default_path),
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
                except Exception:
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
            try:
                hl = pal.color(pal.ColorRole.Highlight)
                htxt = pal.color(pal.ColorRole.HighlightedText)
                txt = pal.color(pal.ColorRole.ButtonText)
                mid = pal.color(pal.ColorRole.Mid)
            except Exception:
                hl = pal.highlight().color()  # type: ignore
                htxt = pal.highlightedText().color()  # type: ignore
                txt = pal.buttonText().color()  # type: ignore
                mid = pal.mid().color()  # type: ignore
            base_txt = f"rgb({txt.red()},{txt.green()},{txt.blue()})"
            h_rgb = f"rgb({hl.red()},{hl.green()},{hl.blue()})"
            h_txt = f"rgb({htxt.red()},{htxt.green()},{htxt.blue()})"
            mid_rgba = f"rgba({mid.red()},{mid.green()},{mid.blue()},120)"
            mid_hover = f"rgba({mid.red()},{mid.green()},{mid.blue()},40)"
            self.toggle_button.setStyleSheet(
                """
                QPushButton {
                    border: 1px solid %s;
                    border-radius: 4px;      /* 小圆角，更紧凑 */
                    padding: 2px 6px;        /* 仅比文字高一点 */
                    min-height: 20px;        /* 紧凑高度 */
                    background-color: transparent;
                    color: %s;
                    text-align: center;
                }
                QPushButton:hover {
                    background-color: %s;
                }
                QPushButton:checked {
                    background-color: %s;
                    border-color: %s;
                    color: %s;
                }
                """ % (mid_rgba, base_txt, mid_hover, h_rgb, h_rgb, h_txt)
            )

    # 1. 直接在顶部放置“设置”内容（扁平化，不再使用折叠面板）
    top_settings = QVBoxLayout()
    top_settings.setContentsMargins(8,8,8,0)
    top_settings.setSpacing(6)
    dir_row = QHBoxLayout()
    self.dir_edit = QLineEdit()
    self.dir_edit.setPlaceholderText("请选择包含要拼接图片的目录...")
    self.browse_btn = QPushButton("浏览...")
    self.browse_btn.setProperty("btn", "secondary")
    self.browse_btn.clicked.connect(self.browse_directory)
    dir_row.addWidget(QLabel("目录:"))
    dir_row.addWidget(self.dir_edit, 1)
    dir_row.addWidget(self.browse_btn)
    top_settings.addLayout(dir_row)
    # 同行按钮
    btn_row = QHBoxLayout()
    btn_row.setSpacing(6)
    self.start_btn = QPushButton("🚀 开始拼接")
    self.start_btn.clicked.connect(self.start_stitching)
# 紧凑：降低按钮最小高度
self.start_btn.setMinimumHeight(22)
    self.start_btn.setProperty("btn", "primary")
    self.start_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    btn_row.addWidget(self.start_btn, 1)
    top_settings.addLayout(btn_row)
    # 进度条
    self.progress_bar = QProgressBar()
    pal = self.palette()
    try:
        hl = pal.color(pal.ColorRole.Highlight)
    except Exception:
        hl = pal.highlight().color()  # type: ignore
    self.progress_bar.setStyleSheet(
        "QProgressBar { border: 1px solid palette(Mid); border-radius: 4px; text-align: center; min-height: 12px;}"
        f"QProgressBar::chunk {{ background-color: rgb({hl.red()},{hl.green()},{hl.blue()}); }}"
    )
    top_settings.addWidget(self.progress_bar)
    # 挂到主布局顶部
    layout.addLayout(top_settings)

    # 2. 图片预览与选择 / 结果预览（合并面板）
    preview_box = CollapsibleBox("预览", default_open=True, expand_flex=False)
    preview_select_layout = QVBoxLayout()
    preview_select_layout.setContentsMargins(8,8,8,8)
    preview_select_layout.setSpacing(6)

    # 顶行：统计 + 选择操作按钮（同一行）
    top_bar = QHBoxLayout()
    self.selection_summary_label = QLabel("未加载目录")
    top_bar.addWidget(self.selection_summary_label)
    top_bar.addStretch()
    self.btn_select_all = QPushButton("全选")
    self.btn_select_none = QPushButton("全不选")
    self.btn_invert = QPushButton("反选")
    for b in (self.btn_select_all, self.btn_select_none, self.btn_invert):
        b.setMinimumHeight(28)
        b.setProperty("btn", "secondary")
        top_bar.addWidget(b)
    preview_select_layout.addLayout(top_bar)

    # 第二行：缩放 + 打开输出目录
    zoom_row = QHBoxLayout()
    zoom_row.addWidget(QLabel("缩放:"))
    self.thumb_size_label = QLabel(f"{self._thumb_size}px")
    zoom_row.addWidget(self.thumb_size_label)
    self.thumb_slider = QSlider(Qt.Horizontal)
    self.thumb_slider.setMinimum(10)
    self.thumb_slider.setMaximum(300)
    self.thumb_slider.setValue(self._thumb_size)
    self.thumb_slider.setToolTip("调整预览缩略图大小 (Ctrl+滚轮 也可缩放)")
    self.thumb_slider.valueChanged.connect(self._on_thumb_size_changed)
    zoom_row.addWidget(self.thumb_slider, 1)
    self.open_output_btn = QPushButton("打开")
    self.open_output_btn.setProperty("btn", "secondary")
    self.open_output_btn.setToolTip("打开输出目录 (stitch)")
    self.open_output_btn.clicked.connect(self.open_output_dir)
    zoom_row.addWidget(self.open_output_btn)
    preview_select_layout.addLayout(zoom_row)

    # 预览：图标平铺（正方形体块）
    self.image_list = self._create_image_list()

    # 选择按钮连接
    self.btn_select_all.clicked.connect(self._select_all)
    self.btn_select_none.clicked.connect(self._select_none)
    self.btn_invert.clicked.connect(self._invert_selection)

    # 合并：结果预览区域（右侧，自动缩放，无滚动条）
    self.result_container = QWidget()
    self.result_container.setMinimumHeight(260)
    rc_layout = QVBoxLayout(self.result_container)
    rc_layout.setContentsMargins(0,0,0,0)
    rc_layout.setSpacing(0)
    self.preview_label = QLabel("拼接结果将显示在这里")
    self.preview_label.setAlignment(Qt.AlignCenter)
    # 使用当前主题的窗口背景色和中间色设置初始底色和边框，避免纯白
    pal = self.palette()
    try:
        win_col = pal.color(pal.ColorRole.Window)
        mid_col = pal.color(pal.ColorRole.Mid)
        txt_col = pal.color(pal.ColorRole.Text)
    except Exception:
        win_col = pal.window().color()  # type: ignore
        mid_col = pal.mid().color()  # type: ignore
        txt_col = pal.text().color()  # type: ignore
    self.preview_label.setStyleSheet(
        "QLabel { "
        f"background-color: rgb({win_col.red()},{win_col.green()},{win_col.blue()}); "
        f"border: 2px dashed rgb({mid_col.red()},{mid_col.green()},{mid_col.blue()}); "
        "padding: 16px; "
        f"color: rgb({txt_col.red()},{txt_col.green()},{txt_col.blue()}); "
        "font-size: 13px; }"
    )
    self.preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    rc_layout.addWidget(self.preview_label, 1)
    def _rc_resize(ev):
        QWidget.resizeEvent(self.result_container, ev)
        self._refresh_result_preview()
    self.result_container.resizeEvent = _rc_resize

    # 左右结构：左（缩略图+操作）| 分隔线 | 右（结果预览）
    content_row = QHBoxLayout()
    content_row.setSpacing(6)
    left_col = QVBoxLayout()
    left_col.addWidget(self.image_list, 1)
    content_row.addLayout(left_col, 1)
    divider = QFrame()
    divider.setFrameShape(QFrame.VLine)
    divider.setFrameShadow(QFrame.Plain)
    divider.setLineWidth(1)
    content_row.addWidget(divider)
    content_row.addWidget(self.result_container, 1)
    preview_select_layout.addLayout(content_row)

    # 双击打开：为缩略图列表启用双击打开文件
    self.image_list.itemDoubleClicked.connect(self._on_item_double_clicked)
preview_box.setContentLayout(preview_select_layout)

    # 3. 日志
    log_box = CollapsibleBox("日志", default_open=True, expand_flex=True)
    log_layout = QVBoxLayout()
    self.log_text = QTextEdit()
    self.log_text.setReadOnly(True)
    self.log_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    log_layout.addWidget(self.log_text)
log_box.setContentLayout(log_layout)

# 使用垂直分割器使预览与日志可上下拖动
self.main_splitter = QSplitter(Qt.Vertical)
self.main_splitter.addWidget(preview_box)
self.main_splitter.addWidget(log_box)
self.main_splitter.setStretchFactor(0, 1)
self.main_splitter.setStretchFactor(1, 2)
layout.addWidget(self.main_splitter, 1)

    # 首先把提示文字写入日志
    self.log("✅ 程序已启动 - 使用 OpenCV Stitcher 专业拼接引擎")
    self.log("💡 提示：")
    self.log("• Created by AYE | Version 1.0.0 | 2025-10-12")
    self.log("• OpenCV Stitcher 是业界标准的图像拼接库")
    self.log("• 自动检测特征点并精确对齐")
    self.log("• 确保相邻图片有 30% 以上的重叠区域")
    self.log("• 当前默认使用‘扫描模式’，适合截图/文档")

    # 外部底端弹簧：始终存在于所有面板之后，保证折叠时整体贴顶
    layout.addStretch(1)

# ——— 全局按钮样式（更紧凑的圆角、padding 与高度） ———
    pal = self.palette()
    try:
        bg = pal.color(pal.ColorRole.Window)
        txt = pal.color(pal.ColorRole.ButtonText)
        hi = pal.color(pal.ColorRole.Highlight)
    except Exception:
        bg = pal.window().color()  # type: ignore
        txt = pal.buttonText().color()  # type: ignore
        hi = pal.highlight().color()  # type: ignore
    base_txt = f"rgba({txt.red()},{txt.green()},{txt.blue()},255)"
    hi_rgb = f"rgb({hi.red()},{hi.green()},{hi.blue()})"
    hi_hover = f"rgba({hi.red()},{hi.green()},{hi.blue()},0.85)"
    hi_press = f"rgba({hi.red()},{hi.green()},{hi.blue()},0.7)"
    sec_bg = f"rgba({bg.red()},{bg.green()},{bg.blue()},0.6)"
    sec_bor = f"rgba({txt.red()},{txt.green()},{txt.blue()},80)"
    self.setStyleSheet(self.styleSheet() + f"""
        QPushButton[btn="primary"] {{
            color: white;
            background-color: {hi_rgb};
            border: 1px solid {hi_rgb};
            border-radius: 6px;
            padding: 3px 8px;
            min-height: 20px;
            font-weight: 600;
        }}
        QPushButton[btn="primary"]:hover {{
            background-color: {hi_hover};
            border-color: {hi_hover};
        }}
        QPushButton[btn="primary"]:pressed {{
            background-color: {hi_press};
            border-color: {hi_press};
        }}
        QPushButton[btn="primary"]:disabled {{
            background-color: rgba(180,180,180,0.5);
            border-color: rgba(160,160,160,0.4);
            color: rgba(255,255,255,0.8);
        }}

        QPushButton[btn="secondary"] {{
            color: {base_txt};
            background-color: {sec_bg};
            border: 1px solid {sec_bor};
            border-radius: 4px;
            padding: 3px 8px;
            min-height: 20px;
        }}
        QPushButton[btn="secondary"]:hover {{
            background-color: rgba(127,127,127,0.15);
        }}
        QPushButton[btn="secondary"]:pressed {{
            background-color: rgba(127,127,127,0.25);
        }}
""")

    # 恢复 UI 状态（分割器尺寸、折叠状态）
    self._restore_ui_state(preview_box, log_box)

def _restore_ui_state(self, preview_box: QWidget, log_box: QWidget):
    settings = QSettings("AYE", "AutoStitcher")
    sizes = settings.value("splitter/sizes")
    if isinstance(sizes, list) and all(isinstance(x, int) for x in sizes):
        self.main_splitter.setSizes(sizes)  # type: ignore[arg-type]
    else:
        self.main_splitter.setSizes([400, 360])

    prev_exp = settings.value("collapsible/preview", True, bool)
    log_exp = settings.value("collapsible/log", True, bool)
    # 应用折叠状态
    try:
        preview_box.toggle_button.setChecked(bool(prev_exp))
        preview_box._on_toggle(bool(prev_exp))
    except Exception:
        pass
    try:
        log_box.toggle_button.setChecked(bool(log_exp))
        log_box._on_toggle(bool(log_exp))
    except Exception:
        pass

    # 恢复缩略图大小（若存在）
    thumb = settings.value("thumb/size")
    if isinstance(thumb, int) and 10 <= thumb <= 300:
        self.thumb_slider.setValue(thumb)

def closeEvent(self, event):  # type: ignore[override]
    # 保存分割器尺寸与折叠状态、缩略图尺寸
    try:
        settings = QSettings("AYE", "AutoStitcher")
        settings.setValue("splitter/sizes", self.main_splitter.sizes())
        # 折叠状态：通过查找 splitter 中的两个 CollapsibleBox
        if self.main_splitter.count() >= 2:
            w0 = self.main_splitter.widget(0)
            w1 = self.main_splitter.widget(1)
            try:
                settings.setValue("collapsible/preview", bool(w0.toggle_button.isChecked()))
            except Exception:
                pass
            try:
                settings.setValue("collapsible/log", bool(w1.toggle_button.isChecked()))
            except Exception:
                pass
        # 缩略图尺寸
        try:
            settings.setValue("thumb/size", int(self.thumb_slider.value()))
        except Exception:
            pass
    finally:
        super().closeEvent(event)

# 底部弹簧已移至 init_ui 内部末尾，且日志面板设置了更高的伸展因子

# ============ 预览表格与缩放 ============
def _create_image_list(self) -> QListWidget:
    lw = QListWidget()
    lw.setViewMode(QListView.IconMode)
    lw.setIconSize(self._calc_icon_size())
    lw.setResizeMode(QListView.Adjust)
    lw.setMovement(QListView.Static)
    lw.setSpacing(2)
    lw.setUniformItemSizes(True)
    lw.setSelectionMode(QListWidget.MultiSelection)
    lw.setContextMenuPolicy(Qt.CustomContextMenu)
    lw.customContextMenuRequested.connect(self._on_list_context_menu)
    # Ctrl+滚轮缩放
    lw.wheelEvent = self._make_ctrl_wheel_zoom(lw.wheelEvent)
    # 选择变化时更新统计
    lw.itemSelectionChanged.connect(self._on_selection_changed)
    self._apply_list_grid(lw)
    # 自定义选中叠加序号
    lw.setItemDelegate(self.ThumbDelegate(self))
    return lw

def _calc_icon_size(self):
    # 允许最小到 10px，最大 512px
    s = max(10, min(512, self._thumb_size))
    return QSize(s, s)

def _apply_list_grid(self, lw: QListWidget):
    # 根据图标尺寸设置网格，尽量紧凑
    s = self._calc_icon_size().width()
    lw.setGridSize(QSize(s + 8, s + 8))

class ThumbDelegate(QStyledItemDelegate):
        def __init__(self, parent):
            super().__init__(parent)
            self.parent = parent
        def paint(self, painter: QPainter, option, index):
            # 自绘缩略图，保证在正方形单元内最大化适配（等比居中），并绘制选中序号
            painter.save()
            r = option.rect
            # 绘制背景（使用系统样式提供的背景，确保主题一致）
            # 不主动填充背景，交给视图样式；只绘制图片
            try:
                item = self.parent.image_list.item(index.row())
                icon = item.icon() if item is not None else QIcon()
            except Exception:
                icon = QIcon()
            # 目标边长（留出少量边距）
            side = min(r.width(), r.height()) - 8
            if side < 2:
                side = max(1, side)
            # 从图标获取较大底图，再二次等比缩放，避免锯齿
            base_pix = icon.pixmap(512, 512) if not icon.isNull() else QPixmap()
            if not base_pix.isNull():
                scaled = base_pix.scaled(side, side, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                x = r.x() + (r.width() - scaled.width()) // 2
                y = r.y() + (r.height() - scaled.height()) // 2
                painter.drawPixmap(x, y, scaled)
            painter.restore()
            # 选中项叠加大序号
            w: QListWidget = self.parent.image_list
            sel = w.selectionModel().selectedIndexes()
            if not sel:
                return
            sel_sorted = sorted(sel, key=lambda ix: ix.row())
            row_to_order = {ix.row(): i+1 for i, ix in enumerate(sel_sorted)}
            if index.row() not in row_to_order:
                return
            order = row_to_order[index.row()]
            r = option.rect
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing, True)
            d = min(r.width(), r.height())
            radius = int(d*0.35)
            cx = r.center().x()
            cy = r.top() + radius + 6
            bg = QColor(0,0,0,160)
            pen = QPen(QColor(255,255,255,220))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(bg)
            painter.drawEllipse(QPoint(cx, cy), radius, radius)
            font = painter.font()
            font.setBold(True)
            font.setPointSize(max(12, int(radius*0.9)))
            painter.setFont(font)
            painter.setPen(QPen(QColor(255,255,255)))
            text_rect = QRect(cx-radius, cy-radius, radius*2, radius*2)
            painter.drawText(text_rect, Qt.AlignCenter, str(order))
            painter.restore()

    def _make_ctrl_wheel_zoom(self, original_handler):
        def handler(event):
            if event.modifiers() & Qt.ControlModifier:
                delta = event.angleDelta().y()
                step = 10 if delta > 0 else -10
                new_val = max(10, min(300, self.thumb_slider.value() + step))
                if new_val != self.thumb_slider.value():
                    self.thumb_slider.setValue(new_val)
                event.accept()
            else:
                original_handler(event)
        return handler

    def _on_thumb_size_changed(self, value: int):
        self._thumb_size = value
        self.thumb_size_label.setText(f"{value}px")
        # 更新图标大小
        if hasattr(self, 'image_list'):
            self.image_list.setIconSize(self._calc_icon_size())
            self._apply_list_grid(self.image_list)
            self.image_list.update()

    def _style_accent_button(self, btn: QPushButton):
        # 使用当前主题的高亮色作为按钮底色，保证文字可读性
        pal = self.palette()
        try:
            highlight = pal.color(pal.ColorRole.Highlight)
            text_col = pal.color(pal.ColorRole.HighlightedText)
        except Exception:
            highlight = pal.highlight().color()  # type: ignore
            text_col = pal.highlightedText().color()  # type: ignore
        bg = f"rgb({highlight.red()},{highlight.green()},{highlight.blue()})"
        fg = f"rgb({text_col.red()},{text_col.green()},{text_col.blue()})"
        btn.setStyleSheet(
            f"QPushButton {{ font-weight: 600; border-radius: 6px; padding: 8px 12px; background-color: {bg}; color: {fg}; }}"
            "QPushButton:disabled { opacity: 0.6; }"
        )

    def _update_summary(self):
        total = self.image_list.count() if hasattr(self, 'image_list') else 0
        selected = len(self.image_list.selectedIndexes()) if hasattr(self, 'image_list') else 0
        self.selection_summary_label.setText(f"已加载: {total} 张 | 已选择: {selected} 张")
        if hasattr(self, 'image_list'):
            self.image_list.viewport().update()

    def _select_all(self):
        self.image_list.selectAll()
        self._update_summary()

    def _select_none(self):
        self.image_list.clearSelection()
        self._update_summary()

    def _invert_selection(self):
        to_select = []
        to_deselect = []
        for i in range(self.image_list.count()):
            it = self.image_list.item(i)
            if it.isSelected():
                to_deselect.append(it)
            else:
                to_select.append(it)
        for it in to_deselect:
            it.setSelected(False)
        for it in to_select:
            it.setSelected(True)
        self._update_summary()

    def _on_selection_changed(self):
        self._update_summary()

    def _on_item_double_clicked(self, item: QListWidgetItem):
        """双击缩略图：用系统默认程序打开图片文件"""
        try:
            path = item.data(self.ROLE_PATH) if item else None
            if path and os.path.exists(path):
                if sys.platform.startswith('win'):
                    os.startfile(path)  # type: ignore[attr-defined]
                else:
                    QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            else:
                QMessageBox.information(self, "提示", "未找到有效的文件路径")
        except Exception as e:
            QMessageBox.warning(self, "打开失败", f"无法打开文件:\n{path}\n\n{e}")

    def open_output_dir(self):
        """打开输出目录（所选目录下的 stitch），不存在则创建"""
        try:
            base_dir = Path(self.dir_edit.text().strip() or Path.home())
            out_dir = base_dir / "stitch"
            out_dir.mkdir(parents=True, exist_ok=True)
            p = str(out_dir)
            if sys.platform.startswith('win'):
                os.startfile(p)  # type: ignore[attr-defined]
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(p))
        except Exception as e:
            QMessageBox.warning(self, "打开失败", f"无法打开输出目录:\n{e}")

    def _auto_order_by_name(self):
        # 取已选行按文件名排序后从1开始编号
        items = []
        for i in range(self.image_list.count()):
            it = self.image_list.item(i)
            if it and it.checkState() == Qt.Checked:
                path = it.data(self.ROLE_PATH)
                items.append((i, os.path.basename(path)))
        items.sort(key=lambda x: x[1].lower())
        for order, (i, _) in enumerate(items, start=1):
            it = self.image_list.item(i)
            it.setData(self.ROLE_ORDER, order)
            self._update_item_text(it)

    def _clear_order(self):
        for i in range(self.image_list.count()):
            it = self.image_list.item(i)
            if it:
                it.setData(self.ROLE_ORDER, 0)
                self._update_item_text(it)

    def _load_images_for_preview(self, directory: str):
        # 清空并填充列表
        self.image_list.clear()
        paths = stitcher.load_images(directory)
        for path in paths:
            self._add_image_item(path)
        self._update_summary()

    def _add_image_item(self, path: str):
        pix = QPixmap(path)
        icon = QIcon(pix)
        item = QListWidgetItem(icon, "")
        item.setData(self.ROLE_PATH, path)
        item.setFlags(item.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        item.setToolTip(os.path.basename(path))
        self.image_list.addItem(item)

    def _update_item_text(self, item: QListWidgetItem):
        # 保持无文字，使用工具提示展示文件名
        item.setText("")

    def _on_list_context_menu(self, pos: QPoint):
        item = self.image_list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        act_set_order = QAction("设置序号…", self)
        act_clear_order = QAction("清除序号", self)
        act_toggle_mark = QAction("切换标记", self)
        menu.addAction(act_set_order)
        menu.addAction(act_clear_order)
        menu.addSeparator()
        menu.addAction(act_toggle_mark)

        def do_set_order():
            val, ok = QInputDialog.getInt(self, "设置序号", "序号 (>=1):", value=max(1, int(item.data(self.ROLE_ORDER) or 1)), min=1, max=9999)
            if ok:
                item.setData(self.ROLE_ORDER, int(val))
                self._update_item_text(item)

        def do_clear_order():
            item.setData(self.ROLE_ORDER, 0)
            self._update_item_text(item)

        def do_toggle_mark():
            cur = bool(item.data(self.ROLE_MARK))
            item.setData(self.ROLE_MARK, (not cur))
            self._update_item_text(item)

        act_set_order.triggered.connect(do_set_order)
        act_clear_order.triggered.connect(do_clear_order)
        act_toggle_mark.triggered.connect(do_toggle_mark)
        menu.exec(self.image_list.mapToGlobal(pos))
    
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
        
        self.preview_label.setText("⏳ 正在处理，请稍候...")
        # 使用主题色作为边框，窗口背景色作为底色
        pal = self.palette()
        try:
            win_col = pal.color(pal.ColorRole.Window)
            txt_col = pal.color(pal.ColorRole.Text)
            hi_col = pal.color(pal.ColorRole.Highlight)
        except Exception:
            win_col = pal.window().color()  # type: ignore
            txt_col = pal.text().color()    # type: ignore
            hi_col = pal.highlight().color()  # type: ignore
        self.preview_label.setStyleSheet(
            "QLabel { "
            f"background-color: rgb({win_col.red()},{win_col.green()},{win_col.blue()}); "
            f"border: 2px solid rgb({hi_col.red()},{hi_col.green()},{hi_col.blue()}); "
            "padding: 20px; "
            f"color: rgb({txt_col.red()},{txt_col.green()},{txt_col.blue()}); "
            "font-size: 14px; "
            "}"
        )
        self.result_image = None
        
        # 默认使用扫描模式
        mode = 'scans'
        mode_name = "扫描模式"
        
        # 读取用户选择（使用选中项，按行号顺序）
        selected_rows = sorted([ix.row() for ix in self.image_list.selectedIndexes()])
        selected_paths = [self.image_list.item(r).data(self.ROLE_PATH) for r in selected_rows]

        image_paths_for_job: List[str]
        if selected_paths:
            image_paths_for_job = selected_paths
        else:
            # 未选择则默认处理全部（按显示顺序）
            image_paths_for_job = []
            for i in range(self.image_list.count()):
                it = self.image_list.item(i)
                if it:
                    path = it.data(self.ROLE_PATH)
                    if path:
                        image_paths_for_job.append(path)

        if not image_paths_for_job:
            QMessageBox.warning(self, "警告", "目录中未找到可处理的图片")
            self.start_btn.setEnabled(True)
            self.browse_btn.setEnabled(True)
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
        # 自动保存结果
        try:
            base_dir = Path(self.dir_edit.text().strip() or Path.home())
            out_dir = base_dir / "stitch"
            out_dir.mkdir(parents=True, exist_ok=True)
            # 文件名：stitched_时间戳.png
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = out_dir / f"stitched_{ts}.png"
            encode_param = [int(cv2.IMWRITE_PNG_COMPRESSION), 3]
            success, encoded_img = cv2.imencode('.png', result, encode_param)
            if success:
                with open(file_path, 'wb') as f:
                    f.write(encoded_img.tobytes())
                self.log(f"💾 已自动保存结果: {file_path}")
            else:
                self.log("❌ 自动保存失败：编码失败")
        except Exception as e:
            self.log(f"❌ 自动保存异常: {e}")
        
        h, w = result.shape[:2]
        self.log(f"✅ 拼接成功！结果尺寸: {w} x {h} 像素")
        self.log("="*60)
        
        # 使用主题窗口底色 + 高亮色边框，避免硬编码白色
        pal = self.palette()
        try:
            win_col = pal.color(pal.ColorRole.Window)
            hi_col = pal.color(pal.ColorRole.Highlight)
        except Exception:
            win_col = pal.window().color()  # type: ignore
            hi_col = pal.highlight().color()  # type: ignore
        self.preview_label.setStyleSheet(
            "QLabel { "
            f"background-color: rgb({win_col.red()},{win_col.green()},{win_col.blue()}); "
            f"border: 2px solid rgb({hi_col.red()},{hi_col.green()},{hi_col.blue()}); "
            "}"
        )
        
        # 去掉强制弹窗，仅在日志中提示
        self.log("✅ 图片拼接完成，预览区已更新。结果已自动保存到输出目录 stitch。")
    
    def on_error(self, error_message: str):
        """处理错误"""
        self.log(f"❌ 错误: {error_message}")
        self.log("="*60)
        
        self.start_btn.setEnabled(True)
        self.browse_btn.setEnabled(True)
        
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
        self._set_result_pixmap_from_np(image)
        self._refresh_result_preview()

    def _set_result_pixmap_from_np(self, image: np.ndarray):
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        self._result_pixmap = QPixmap.fromImage(qt_image)

    def _refresh_result_preview(self):
        if not hasattr(self, '_result_pixmap') or self._result_pixmap.isNull():
            return
        # 根据容器尺寸自适应缩放
        avail = self.result_container.size()
        target = QSize(max(10, avail.width()-2), max(10, avail.height()-2))
        scaled = self._result_pixmap.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview_label.setPixmap(scaled)
        self.preview_label.setMinimumSize(1,1)
    
    def save_result(self):
        """保存结果"""
        if self.result_image is None:
            QMessageBox.warning(self, "警告", "没有可保存的结果")
            return
        
        # 默认保存到所选目录下的 stitch 子文件夹
        base_dir = Path(self.dir_edit.text().strip() or Path.home())
        default_dir = base_dir / "stitch"
        try:
            default_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        default_path = default_dir / "stitched_result.png"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存拼接结果", 
            str(default_path),
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
