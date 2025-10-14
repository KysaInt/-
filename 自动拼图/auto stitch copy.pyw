"""
自动图片拼接工具 v4.0
使用 OpenCV Stitcher - 成熟稳定的拼接库
"""

from __future__ import annotations

# 注意：为实现“启动时依赖自检并经确认后自动安装”，需要在导入第三方库之前
# 先进行依赖检查。因此此文件的第三方导入被延后到检查完成之后。

import sys
import os
import subprocess
import re
from pathlib import Path
from datetime import datetime
from typing import List, Optional


def _parse_version_tuple(ver: str) -> tuple:
    """将版本号字符串提取为最多三段的整数元组，例如 '4.8.1.23' -> (4,8,1)。"""
    nums = re.findall(r"\d+", ver or "0")
    if not nums:
        return (0,)
    parts = [int(x) for x in nums[:3]]
    return tuple(parts)


def _version_satisfied(installed: str, minimal: str) -> bool:
    return _parse_version_tuple(installed) >= _parse_version_tuple(minimal)


def _tk_confirm(title: str, message: str) -> bool:
    """使用 Tk 弹出确认窗口；若 Tk 不可用，则返回 False（避免静默安装）。"""
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        res = messagebox.askyesno(title, message)
        root.destroy()
        return bool(res)
    except Exception:
        return False


def _tk_info(title: str, message: str) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        messagebox.showinfo(title, message)
        root.destroy()
    except Exception:
        pass


def _pip_install(packages: List[str]) -> tuple[bool, str]:
    """通过当前 Python 解释器执行 pip 安装，返回 (成功与否, 输出/错误)。"""
    cmd = [sys.executable, "-m", "pip", "install", "-U", *packages]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            return True, proc.stdout
        # 若权限问题，尝试 --user 再来一次
        if "Permission" in (proc.stderr or "") or "permission" in (proc.stderr or ""):
            cmd_user = [sys.executable, "-m", "pip", "install", "--user", "-U", *packages]
            proc2 = subprocess.run(cmd_user, capture_output=True, text=True)
            if proc2.returncode == 0:
                return True, proc2.stdout
            return False, (proc.stderr or "") + "\n" + (proc2.stderr or "")
        return False, (proc.stderr or proc.stdout or "pip 执行失败")
    except Exception as e:
        return False, str(e)


def ensure_dependencies() -> bool:
    """
    检查并在用户确认后安装/升级依赖。
    - 需要: numpy>=1.24.0, opencv-contrib-python>=4.8.0, PySide6>=6.5.0
    - 若确认安装失败或用户拒绝，返回 False；成功或已满足返回 True。
    """
    to_install: List[str] = []
    tips: List[str] = []

    # numpy
    try:
        import importlib
        np_mod = importlib.import_module('numpy')
        if not _version_satisfied(getattr(np_mod, '__version__', '0'), '1.24.0'):
            to_install.append('numpy>=1.24.0')
            tips.append('numpy>=1.24.0（数组/图像处理）')
    except Exception:
        to_install.append('numpy>=1.24.0')
        tips.append('numpy>=1.24.0（数组/图像处理）')

    # OpenCV：统一安装 opencv-contrib-python 覆盖标准版
    need_cv = False
    try:
        import importlib
        cv2_mod = importlib.import_module('cv2')
        ver_ok = _version_satisfied(getattr(cv2_mod, '__version__', '0'), '4.8.0')
        has_stitcher = hasattr(cv2_mod, 'Stitcher_create')
        if not (ver_ok and has_stitcher):
            need_cv = True
    except Exception:
        need_cv = True
    if need_cv:
        to_install.append('opencv-contrib-python>=4.8.0')
        tips.append('opencv-contrib-python>=4.8.0（含 Stitcher/特征匹配）')

    # PySide6
    need_qt = False
    try:
        import importlib
        qt_mod = importlib.import_module('PySide6')
        ver = getattr(qt_mod, '__version__', '0')
        if not _version_satisfied(ver, '6.5.0'):
            need_qt = True
    except Exception:
        need_qt = True
    if need_qt:
        to_install.append('PySide6>=6.5.0')
        tips.append('PySide6>=6.5.0（GUI 框架）')

    if not to_install:
        return True

    # 弹窗确认
    pkg_text = "\n".join(f"- {t}" for t in tips)
    confirm_msg = (
        "检测到以下依赖缺失或版本过低：\n\n"
        f"{pkg_text}\n\n"
        "是否现在安装/升级？\n\n"
        "将执行：pip install -U " + " ".join(to_install)
    )
    if not _tk_confirm("安装依赖", confirm_msg):
        _tk_info("已取消", "已取消依赖安装，程序将退出。\n\n你也可以手动安装：\n" + "pip install -U " + " ".join(to_install))
        return False

    ok, out = _pip_install(to_install)
    if ok:
        _tk_info("安装成功", "依赖已安装/升级完成，将继续启动程序。")
        return True
    else:
        _tk_info("安装失败", "安装/升级失败。可尝试手动安装：\n\n" + out)
        return False


# 依赖检查：若失败则直接退出
if not ensure_dependencies():
    sys.exit(1)

# 通过依赖检查后，再导入第三方库
import cv2
import numpy as np
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QLabel, QLineEdit, 
                               QFileDialog, QProgressBar, QTextEdit, QMessageBox,
                               QScrollArea, QGroupBox, QListWidget,
                               QListWidgetItem, QListView, QMenu, QInputDialog,
                               QSlider, QSizePolicy, QStyledItemDelegate, QFrame, QSplitter, QStyle, QGridLayout, QDialog)
from PySide6.QtCore import Qt, QThread, Signal, QPoint, QSize, QRect, QPropertyAnimation, QEasingCurve, QUrl, QEvent, QSettings, QTimer
from PySide6.QtGui import QPixmap, QImage, QIcon, QAction, QPainter, QColor, QPen, QFont, QDesktopServices

def build_themed_icon(palette=None) -> QIcon:
    """从脚本同目录加载 fabric.png 作为图标；若不存在则返回空图标。

    参数 palette 仅为兼容旧调用保留，不再使用。
    """
    try:
        icon_path = Path(__file__).resolve().parent / 'fabric.png'
        if icon_path.exists():
            return QIcon(str(icon_path))
    except Exception:
        pass
    return QIcon()


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

    def _make_transparent(self, pano: np.ndarray) -> np.ndarray:
        """将拼接结果的纯黑背景转为透明（BGRA）。
        注意：此方法以接近黑色(0~1)作为空白的判定阈值，可能会把真实黑色像素也当作透明。
        如有需要，可根据素材调整阈值或更换空白检测逻辑。
        """
        if pano is None:
            return pano
        if pano.ndim != 3:
            return pano
        h, w = pano.shape[:2]
        # 确保是 BGR
        if pano.shape[2] == 4:
            bgr = pano[:, :, :3]
        else:
            bgr = pano
        # 阈值：非常接近纯黑
        mask = cv2.inRange(bgr, (0, 0, 0), (1, 1, 1))
        # 构建 BGRA
        bgra = cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA)
        # 默认不透明
        bgra[:, :, 3] = 255
        # 空白处设为透明
        bgra[mask > 0, 3] = 0
        return bgra

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
                        progress_callback(i + 1, len(image_paths), f"警告: 无法解码 {Path(path).name}")
            except Exception:
                if progress_callback:
                    progress_callback(i + 1, len(image_paths), f"警告: 加载失败 {Path(path).name}")

        if not images:
            return None

        if len(images) == 1:
            # 单张图也做一次透明化处理，保持输出一致
            return self._make_transparent(images[0])

        if self.mode == 'scans':
            stitcher = cv2.Stitcher_create(cv2.Stitcher_SCANS)
        else:
            stitcher = cv2.Stitcher_create(cv2.Stitcher_PANORAMA)

        status, pano = stitcher.stitch(images)
        if progress_callback:
            progress_callback(len(image_paths), len(image_paths), "拼接完成")
        if status == cv2.Stitcher_OK and pano is not None:
            return self._make_transparent(pano)
        return None

class ProgressDialog(QDialog):
    """下载/处理进度弹窗：显示当前进度、状态信息与耗时。

    使用 update_progress(current,total,message) 更新；
    finish() 结束并自动关闭。
    """
    def __init__(self, parent=None, title: str = "正在处理"):
        super().__init__(parent)
        self.setWindowTitle(title)
        # 改为非模态，避免阻塞父窗口交互
        self.setModal(False)
        self.resize(420, 160)
        self._start_dt = datetime.now()
        self._last_message = ""
        layout = QVBoxLayout(self)
        self.label_status = QLabel("准备中…")
        self.label_status.setWordWrap(True)
        layout.addWidget(self.label_status)
        self.bar = QProgressBar(); self.bar.setRange(0, 100); self.bar.setValue(0)
        layout.addWidget(self.bar)
        self.label_elapsed = QLabel("耗时: 0s")
        layout.addWidget(self.label_elapsed)
        # 取消按钮
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self._on_cancel_clicked)
        layout.addWidget(self.btn_cancel)
        self._cancelled = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(1000)
        # 顶置
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        # 样式自适应主题
        pal = self.palette()
        try:
            hi = pal.color(pal.ColorRole.Highlight)
        except Exception:
            hi = pal.highlight().color()  # type: ignore
        self.bar.setStyleSheet(
            "QProgressBar { border: 1px solid palette(Mid); border-radius: 4px; height: 14px; text-align: center;}"
            f"QProgressBar::chunk {{ background-color: rgb({hi.red()},{hi.green()},{hi.blue()}); border-radius: 4px; }}"
        )
    def _on_tick(self):
        delta = datetime.now() - self._start_dt
        secs = int(delta.total_seconds())
        if secs < 60:
            txt = f"耗时: {secs}s"
        else:
            m, s = divmod(secs, 60)
            if m < 60:
                txt = f"耗时: {m}m{s:02d}s"
            else:
                h, rem = divmod(m, 60)
                m2, s2 = divmod(rem, 60)
                txt = f"耗时: {h}h{m2:02d}m{s2:02d}s"
        self.label_elapsed.setText(txt)
    def update_progress(self, current: int, total: int, message: str):
        # 归一化为百分比
        pct = 0
        if total > 0:
            pct = max(0, min(100, int((current / total) * 100)))
        self.bar.setValue(pct)
        self._last_message = message or ""
        self.label_status.setText(f"{message}\n进度: {pct}% ({current}/{total})")
        if self._cancelled:
            self.label_status.setText(f"已请求取消… 当前进度 {pct}%")
    def finish(self, success: bool = True, final_message: str = ""):
        self._timer.stop()
        if final_message:
            self.label_status.setText(final_message)
        else:
            self.label_status.setText("处理完成" if success else "处理失败")
        QTimer.singleShot(800, self.accept)
    def _on_cancel_clicked(self):
        self._cancelled = True
        self.btn_cancel.setEnabled(False)
        self.label_status.setText("已发出取消请求，等待当前步骤完成…")

class ImageGrouper:
    """基于特征匹配的图片分组器：将可拼合的图片划为同一连通分量"""
    def __init__(self, feature: str = 'ORB'):
        self.feature = feature.upper()
        if self.feature == 'SIFT' and hasattr(cv2, 'SIFT_create'):
            self.detector = cv2.SIFT_create()
            self.norm = cv2.NORM_L2
        else:
            # 默认 ORB
            self.detector = cv2.ORB_create(nfeatures=4000)
            self.norm = cv2.NORM_HAMMING

    def _compute_desc(self, img_gray: np.ndarray):
        kp, des = self.detector.detectAndCompute(img_gray, None)
        return kp, des

    def _good_pair(self, des1, des2) -> bool:
        if des1 is None or des2 is None:
            return False
        bf = cv2.BFMatcher(self.norm, crossCheck=False)
        try:
            matches = bf.knnMatch(des1, des2, k=2)
        except cv2.error:
            return False
        # Lowe ratio test
        good = []
        for m in matches:
            if len(m) != 2:
                continue
            m1, m2 = m
            if m1.distance < 0.75 * m2.distance:
                good.append(m1)
        if len(good) < 12:
            return False
        return True

    def group_images(self, paths: List[str], progress=None):
        """将图片分组为若干可拼合的连通分量。返回 (groups: List[List[str]], discarded: List[str])"""
        n = len(paths)
        if n <= 1:
            return ([], paths)
        # 读取灰度并计算描述符
        grays = []
        descs = []
        for i, p in enumerate(paths):
            if progress:
                progress(i+1, max(1, n), f"分组: 读取与特征提取 {Path(p).name}")
            try:
                data = np.fromfile(p, dtype=np.uint8)
                img = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
            except Exception:
                img = None
            if img is None:
                grays.append(None)
                descs.append(None)
                continue
            _, des = self._compute_desc(img)
            grays.append(img)
            descs.append(des)
        # 构建邻接
        adj = {i: set() for i in range(n)}
        total_pairs = n*(n-1)//2
        pair_idx = 0
        for i in range(n):
            for j in range(i+1, n):
                pair_idx += 1
                if progress:
                    progress(pair_idx, max(1, total_pairs), f"分组: 匹配 {Path(paths[i]).name} ↔ {Path(paths[j]).name}")
                if grays[i] is None or grays[j] is None:
                    continue
                if self._good_pair(descs[i], descs[j]):
                    adj[i].add(j)
                    adj[j].add(i)
        # 连通分量
        visited = [False]*n
        groups_idx = []
        for i in range(n):
            if visited[i]:
                continue
            stack = [i]
            comp = []
            while stack:
                u = stack.pop()
                if visited[u]:
                    continue
                visited[u] = True
                comp.append(u)
                for v in adj[u]:
                    if not visited[v]:
                        stack.append(v)
            groups_idx.append(comp)
        # 过滤掉孤立点（不可拼合）
        groups = []
        discarded = []
        for comp in groups_idx:
            if len(comp) >= 2:
                groups.append([paths[k] for k in comp])
            else:
                discarded.append(paths[comp[0]])
        return groups, discarded


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
        self.grouper = ImageGrouper(feature='ORB')
        self.image_paths = image_paths or []
    
    def run(self):
        """执行拼接任务"""
        try:
            self.progress.emit(0, 100, "扫描目录...")
            image_paths = list(self.image_paths) if self.image_paths else self.stitcher.load_images(self.directory)
            
            if not image_paths:
                self.error.emit("未在目录中找到图片文件")
                return
            
            self.progress.emit(0, 100, f"找到 {len(image_paths)} 张图片，开始自动分组…")
            groups, discarded = self.grouper.group_images(image_paths, progress=self.progress.emit)

            if not groups:
                self.error.emit("未能找到可拼合的图片组。\n\n建议：\n- 确保相邻图片有30%以上重叠\n- 尝试切换拼接模式\n- 减少图片数量进行测试")
                return

            results = []
            total = len(groups)
            for idx, grp in enumerate(groups, start=1):
                self.progress.emit(idx-1, total, f"拼接分组 {idx}/{total}（{len(grp)} 张）…")
                pano = self.stitcher.stitch_images(grp, progress_callback=None)
                if pano is not None:
                    results.append((grp, pano))
                else:
                    discarded.extend(grp)
            if results:
                self.finished.emit(results)
            else:
                self.error.emit("分组拼接均失败，未生成结果。")
                
        except Exception as e:
            self.error.emit(f"拼接过程出错: {str(e)}")


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        # 结果图像（用于单结果保存等）
        self.result_image = None
        # 后台线程
        self.stitch_thread = None
        # 缩略图初始尺寸
        self._thumb_size = 60
        # 选择顺序跟踪列表
        self.selection_order = []
        # QListWidget item roles
        self.ROLE_PATH = Qt.UserRole
        self.ROLE_ORDER = Qt.UserRole + 1
        self.ROLE_MARK = Qt.UserRole + 2
        # 进度弹窗实例（运行时创建/销毁）
        self._progress_dialog = None
        # 初始化界面
        self.init_ui()
        
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("OpenCV Stitcher")
        self.setMinimumSize(900, 700)
        # 主题变化监听，用于实时刷新样式
        self.installEventFilter(self)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # 1. 直接在顶部放置“设置”内容
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
        # 顶部同排：打开 + 选择按钮
        top_bar = QHBoxLayout()
        top_bar.setSpacing(6)
        self.selection_summary_label = QLabel("未加载目录")
        top_bar.addWidget(self.selection_summary_label)
        # 先放置“打开”按钮
        self.open_output_btn = QPushButton("打开")
        self.open_output_btn.setProperty("btn", "secondary")
        self.open_output_btn.setToolTip("打开输出目录 (stitch)")
        self.open_output_btn.clicked.connect(self.open_output_dir)
        top_bar.addWidget(self.open_output_btn)
        # 中部：选择相关按钮
        self.btn_select_all = QPushButton("全选")
        self.btn_select_all.setMinimumHeight(28)
        self.btn_select_all.setProperty("btn", "secondary")
        top_bar.addWidget(self.btn_select_all)
        # 中部：全不选、反选
        self.btn_select_none = QPushButton("全不选")
        self.btn_select_none.setMinimumHeight(28)
        self.btn_select_none.setProperty("btn", "secondary")
        top_bar.addWidget(self.btn_select_none)
        self.btn_invert = QPushButton("反选")
        self.btn_invert.setMinimumHeight(28)
        self.btn_invert.setProperty("btn", "secondary")
        top_bar.addWidget(self.btn_invert)
        # 右侧：开始拼接（动态占据余下宽度并贴右侧）
        self.start_btn = QPushButton("🚀 开始拼接")
        self.start_btn.clicked.connect(self.start_stitching)
        self.start_btn.setMinimumHeight(32)
        self.start_btn.setProperty("btn", "primary")
        self.start_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        top_bar.addWidget(self.start_btn, 1)
        top_settings.addLayout(top_bar)
        # 挂到主布局顶部
        layout.addLayout(top_settings)

        # 2. 图片预览与选择 / 结果预览（合并面板）
        preview_select_container = QWidget()
        preview_select_layout = QVBoxLayout(preview_select_container)
        # 更紧凑的上下边距与行间距
        preview_select_layout.setContentsMargins(6,6,6,6)
        preview_select_layout.setSpacing(4)

        # 第二行：缩放
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
        preview_select_layout.addLayout(zoom_row)
        # 更细的进度条：紧贴缩放行下方
        self.progress_bar = QProgressBar()
        pal = self.palette()
        try:
            hl = pal.color(pal.ColorRole.Highlight)
        except Exception:
            hl = pal.highlight().color()  # type: ignore
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setStyleSheet(
            "QProgressBar { border: 1px solid palette(Mid); border-radius: 3px; min-height: 6px; }"
            f"QProgressBar::chunk {{ background-color: rgb({hl.red()},{hl.green()},{hl.blue()}); border-radius: 3px; }}"
        )
        preview_select_layout.addWidget(self.progress_bar)

        # 预览：图标平铺（正方形体块）
        self.image_list = self._create_image_list()

        # 选择按钮连接
        self.btn_select_all.clicked.connect(self._select_all)
        self.btn_select_none.clicked.connect(self._select_none)
        self.btn_invert.clicked.connect(self._invert_selection)

        # 合并：结果预览区域（右侧，自动缩放；支持单图和多图网格）
        self.result_container = QWidget()
        self.result_container.setMinimumHeight(260)
        rc_layout = QVBoxLayout(self.result_container)
        rc_layout.setContentsMargins(0,0,0,0)
        rc_layout.setSpacing(0)
        # 单结果占位/显示
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
        # 多结果滚动网格
        self.result_scroll = QScrollArea()
        self.result_scroll.setWidgetResizable(True)
        self.result_grid_widget = QWidget()
        self.result_grid = QGridLayout(self.result_grid_widget)
        self.result_grid.setContentsMargins(8,8,8,8)
        self.result_grid.setSpacing(8)
        self.result_scroll.setWidget(self.result_grid_widget)
        self.result_scroll.setVisible(False)  # 初始隐藏，默认单图显示
        rc_layout.addWidget(self.result_scroll, 1)
        def _rc_resize(ev):
            QWidget.resizeEvent(self.result_container, ev)
            self._refresh_results_preview()
        self.result_container.resizeEvent = _rc_resize

        # 左右结构：左（缩略图+操作）| 分隔线 | 右（结果预览）
        h_splitter = QSplitter(Qt.Horizontal)
        h_splitter.setChildrenCollapsible(False)
        
        left_widget = QWidget()
        left_col = QVBoxLayout(left_widget)
        left_col.setContentsMargins(0,0,0,0)
        left_col.addWidget(self.image_list, 1)
        
        h_splitter.addWidget(left_widget)
        h_splitter.addWidget(self.result_container)
        h_splitter.setStretchFactor(0, 1)
        h_splitter.setStretchFactor(1, 1)
        
        preview_select_layout.addWidget(h_splitter)

        # 双击打开：为缩略图列表启用双击打开文件
        self.image_list.itemDoubleClicked.connect(self._on_item_double_clicked)

        # 日志面板
        log_container = QWidget()
        log_layout = QVBoxLayout(log_container)
        log_layout.setContentsMargins(0,6,0,0)
        log_layout.addWidget(QLabel("日志:"))
        self.log_text = QTextEdit(); self.log_text.setReadOnly(True)
        self.log_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        log_layout.addWidget(self.log_text)

        self.vsplitter = QSplitter(Qt.Vertical)
        self.vsplitter.setChildrenCollapsible(False)
        self.vsplitter.addWidget(preview_select_container)
        self.vsplitter.addWidget(log_container)
        self.vsplitter.setStretchFactor(0, 70)
        self.vsplitter.setStretchFactor(1, 30)
        layout.addWidget(self.vsplitter, 1)

        # 首次提示
        self.log("✅ 程序已启动 - 使用 OpenCV Stitcher 专业拼接引擎")
        self.log("💡 提示：")
        self.log("• Created by AYE | Version 1.0.0 | 2025-10-12")
        self.log("• OpenCV Stitcher 是业界标准的图像拼接库")
        self.log("• 自动检测特征点并精确对齐")
        self.log("• 确保相邻图片有 30% 以上的重叠区域")
        self.log("• 当前默认使用‘扫描模式’，适合截图/文档")

        # 应用全局按钮样式 + 恢复设置
        self._apply_global_styles()
        self._restore_settings()

    # ============ 预览表格与缩放 ============
    def _create_image_list(self) -> QListWidget:
        lw = QListWidget()
        lw.setViewMode(QListView.IconMode)
        lw.setIconSize(self._calc_icon_size())
        lw.setResizeMode(QListView.Adjust)
        lw.setMovement(QListView.Static)
        lw.setSpacing(1)
        lw.setUniformItemSizes(True)
        lw.setSelectionMode(QListWidget.MultiSelection)
        lw.setContextMenuPolicy(Qt.CustomContextMenu)
        lw.customContextMenuRequested.connect(self._on_list_context_menu)
        # 去掉额外留白，进一步紧凑
        lw.setStyleSheet("QListView{padding:0px; margin:0px;} QListView::item{margin:0px; padding:0px;}")
        # Ctrl+滚轮缩放
        lw.wheelEvent = self._make_ctrl_wheel_zoom(lw.wheelEvent)
        # 点击时更新选择顺序
        lw.itemClicked.connect(self._on_item_clicked_for_ordering)
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
        # 为描边和序号留出额外边距，避免被裁切
        pad = 8
        lw.setGridSize(QSize(s + pad, s + pad))
        # 刷新几何以立即生效
        try:
            lw.updateGeometries()
        except Exception:
            pass
        lw.viewport().update()

    class ThumbDelegate(QStyledItemDelegate):
        def __init__(self, parent):
            super().__init__(parent)
            self.parent = parent
        def sizeHint(self, option, index):
            # 返回与当前缩略图设置相匹配的单元格尺寸
            s = self.parent._calc_icon_size().width()
            pad = 8
            return QSize(s + pad, s + pad)
        def paint(self, painter: QPainter, option, index):
            # 自绘缩略图：先绘制正方形边框，再绘制图片，最后绘制选中序号
            r = option.rect
            # 1) 正方形方框
            painter.save()
            # 让方框尽量占满单元格，仅为描边留出 1px 余量
            side_frame = max(2, min(r.width(), r.height()) - 1)
            fx = r.x() + (r.width() - side_frame) // 2
            fy = r.y() + (r.height() - side_frame) // 2
            frame_rect = QRect(fx, fy, side_frame, side_frame)
            pal = self.parent.palette()
            try:
                mid_col = pal.color(pal.ColorRole.Mid)
                hi_col = pal.color(pal.ColorRole.Highlight)
            except Exception:
                mid_col = pal.mid().color()  # type: ignore
                hi_col = pal.highlight().color()  # type: ignore
            # 未选中使用浅灰（mid），选中使用主题高亮色，选中时线条稍粗
            pen = QPen(hi_col if (option.state & QStyle.State_Selected) else mid_col)
            pen.setWidth(2 if (option.state & QStyle.State_Selected) else 1)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(frame_rect)
            painter.restore()

            # 2) 图片
            painter.save()
            try:
                item = self.parent.image_list.item(index.row())
                icon = item.icon() if item is not None else QIcon()
            except Exception:
                icon = QIcon()
            # 目标边长（为描边留出 1-2px 余量）
            side = min(r.width(), r.height()) - 2
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
            # 选中项叠加序号：居中于正方形方框中央，主题色文字
            if not (option.state & QStyle.State_Selected):
                return

            try:
                item = self.parent.image_list.item(index.row())
                order = self.parent.selection_order.index(item) + 1
            except (ValueError, AttributeError):
                return # 如果 item 不在选择顺序列表中，则不绘制序号

            painter.save()
            painter.setRenderHint(QPainter.Antialiasing, True)
            try:
                hi_col = pal.color(pal.ColorRole.Highlight)
            except Exception:
                hi_col = pal.highlight().color()  # type: ignore
            painter.setPen(QPen(hi_col))
            font = painter.font()
            font.setBold(True)
            # 字号按方框尺寸自适应
            font.setPointSize(max(9, int(min(frame_rect.width(), frame_rect.height()) * 0.35)))
            painter.setFont(font)
            painter.drawText(frame_rect, Qt.AlignCenter, str(order))
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
            # 强制刷新几何和重绘
            try:
                self.image_list.updateGeometries()
            except Exception:
                pass
            self.image_list.viewport().update()

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
        # 更新选择顺序列表
        self.selection_order = [self.image_list.item(i) for i in range(self.image_list.count())]
        self._update_summary()

    def _select_none(self):
        self.image_list.clearSelection()
        # 更新选择顺序列表
        self.selection_order = []
        self._update_summary()

    def _invert_selection(self):
        current_selection = set(self.image_list.selectedItems())
        all_items = [self.image_list.item(i) for i in range(self.image_list.count())]
        
        # 清空当前选择和顺序
        self.image_list.clearSelection()
        self.selection_order = []

        # 重新选择并构建顺序
        for item in all_items:
            if item not in current_selection:
                item.setSelected(True) # 这会自动触发 itemSelectionChanged
                if item not in self.selection_order:
                     self.selection_order.append(item) # 手动维护顺序

        self._update_summary()

    def _on_item_clicked_for_ordering(self, item: QListWidgetItem):
        """根据点击更新 selection_order 列表"""
        if item.isSelected():
            if item not in self.selection_order:
                self.selection_order.append(item)
        else:
            if item in self.selection_order:
                self.selection_order.remove(item)
        
        # 强制重绘所有可见项以更新序号
        self.image_list.viewport().update()

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
        stitcher = ImageStitcher()
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
        """添加日志（始终自动滚动到底部）"""
        self.log_text.append(message)
        # 方式1：滚动条拉到最底
        sb = self.log_text.verticalScrollBar()
        sb.setValue(sb.maximum())
        # 方式2：移动光标确保可见（双保险）
        try:
            cursor = self.log_text.textCursor()
            cursor.movePosition(cursor.End)
            self.log_text.setTextCursor(cursor)
            self.log_text.ensureCursorVisible()
        except Exception:
            pass
    
    def browse_directory(self):
        """浏览选择目录"""
        directory = QFileDialog.getExistingDirectory(
            self, "选择图片目录", 
            self.dir_edit.text() or str(Path.home())
        )
        if directory:
            self.dir_edit.setText(directory)
            self.log(f"📁 已选择目录: {directory}")
            self.selection_order = [] # 清空旧目录的选择顺序
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
        # 视觉反馈
        pal = self.palette()
        try:
            win_col = pal.color(pal.ColorRole.Window); txt_col = pal.color(pal.ColorRole.Text); hi_col = pal.color(pal.ColorRole.Highlight)
        except Exception:
            win_col = pal.window().color(); txt_col = pal.text().color(); hi_col = pal.highlight().color()  # type: ignore
        self.preview_label.setText("⏳ 正在处理，请稍候...")
        self.preview_label.setStyleSheet(
            "QLabel { "
            f"background-color: rgb({win_col.red()},{win_col.green()},{win_col.blue()}); "
            f"border: 2px solid rgb({hi_col.red()},{hi_col.green()},{hi_col.blue()}); padding: 20px; font-size: 14px; "
            "}"
        )
        # 模式
        mode = 'scans'; mode_name = '扫描模式'
        # 需要处理的文件列表
        if self.selection_order:
            image_paths_for_job = [it.data(self.ROLE_PATH) for it in self.selection_order if it]
        else:
            image_paths_for_job = [self.image_list.item(i).data(self.ROLE_PATH) for i in range(self.image_list.count()) if self.image_list.item(i)]
        image_paths_for_job = [p for p in image_paths_for_job if p]
        if not image_paths_for_job:
            QMessageBox.warning(self, "警告", "没有要处理的图片。请选择图片或确保目录不为空。")
            self.start_btn.setEnabled(True); self.browse_btn.setEnabled(True); return
        # 确认
        est = "取决于图片数量与分辨率"
        reply = QMessageBox.question(self, "确认开始", f"即将开始拼接处理\n\n模式: {mode_name}\n图片数量: {len(image_paths_for_job)} 张\n预计耗时: {est}\n\n是否继续?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if reply != QMessageBox.Yes:
            self.start_btn.setEnabled(True); self.browse_btn.setEnabled(True); self.preview_label.setText("操作已取消"); return
        # 进度弹窗
        self._progress_dialog = ProgressDialog(self, title="拼接进度")
        self._progress_dialog.update_progress(0, len(image_paths_for_job), "准备启动线程…")
        self._progress_dialog.show(); QApplication.processEvents()
        # 启动线程
        self.stitch_thread = StitchThread(directory, mode, image_paths=image_paths_for_job)
        self.stitch_thread.progress.connect(self.on_progress)
        self.stitch_thread.finished.connect(self.on_finished)
        self.stitch_thread.error.connect(self.on_error)
        self.stitch_thread.start()
        self.log("="*60); self.log(f"🚀 开始拼接处理... (模式: {mode_name})")
    
    def on_progress(self, current: int, total: int, message: str):
        """更新进度"""
        if total > 0:
            progress = int((current / total) * 100)
            self.progress_bar.setValue(progress)
        self.log(message)
        if self._progress_dialog:
            self._progress_dialog.update_progress(current, total, message)
            QApplication.processEvents()
    
    def on_finished(self, result_obj):
        """拼接完成：兼容单结果与多结果"""
        results: List[np.ndarray] = []
        if isinstance(result_obj, list):
            for grp, img in result_obj:
                results.append(img)
        elif isinstance(result_obj, np.ndarray):
            results = [result_obj]
        else:
            results = []
        # 用第一张作为当前结果以兼容保存等逻辑
        self.result_image = None if not results else results[0]
        self.display_results(results)
        
        self.start_btn.setEnabled(True)
        self.browse_btn.setEnabled(True)
        # 自动保存所有结果（PNG，无压缩，保留透明）
        try:
            base_dir = Path(self.dir_edit.text().strip() or Path.home())
            out_dir = base_dir / "stitch"
            out_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            for i, img in enumerate(results, start=1):
                file_path = out_dir / f"stitched_{ts}_g{i}.png"
                encode_param = [int(cv2.IMWRITE_PNG_COMPRESSION), 0]
                success, encoded_img = cv2.imencode('.png', img, encode_param)
                if success:
                    with open(file_path, 'wb') as f:
                        f.write(encoded_img.tobytes())
                    self.log(f"💾 已自动保存结果(无压缩PNG): {file_path}")
                else:
                    self.log(f"❌ 自动保存失败：编码失败 (第{i}组)")
        except Exception as e:
            self.log(f"❌ 自动保存异常: {e}")
        
        for i, img in enumerate(results, start=1):
            h, w = img.shape[:2]
            self.log(f"✅ 结果 {i}: {w} x {h} 像素")
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
        
        self.log("✅ 图片拼接完成，预览区已更新。所有结果已自动保存到输出目录 stitch。")
        if self._progress_dialog:
            self._progress_dialog.finish(success=True, final_message="拼接完成，结果已保存。")
            self._progress_dialog = None
    
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
        if self._progress_dialog:
            self._progress_dialog.finish(success=False, final_message=error_message)
            self._progress_dialog = None
    
    def display_results(self, images: List[np.ndarray]):
        """显示多个结果（1张=单图，>1张=网格）"""
        if len(images) <= 1:
            # 单图逻辑
            self.result_scroll.setVisible(False)
            self.preview_label.setVisible(True)
            if images:
                self._set_result_pixmaps_from_np(images)
                # 取第一张
                if self._result_pixmaps:
                    pix = self._result_pixmaps[0]
                    avail = self.result_container.size()
                    target = QSize(max(10, avail.width()-2), max(10, avail.height()-2))
                    self.preview_label.setPixmap(pix.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.preview_label.setText("拼接结果将显示在这里")
        else:
            # 多图网格
            self.preview_label.setVisible(False)
            self.result_scroll.setVisible(True)
            self._set_result_pixmaps_from_np(images)
            self._refresh_results_preview()

    def _set_result_pixmaps_from_np(self, images: List[np.ndarray]):
        self._result_pixmaps = []
        for image in images:
            if image.ndim == 3 and image.shape[2] == 4:
                rgba = cv2.cvtColor(image, cv2.COLOR_BGRA2RGBA)
                h, w, ch = rgba.shape
                bytes_per_line = ch * w
                qt_image = QImage(rgba.data, w, h, bytes_per_line, QImage.Format_RGBA8888)
                self._result_pixmaps.append(QPixmap.fromImage(qt_image))
            else:
                rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_image.shape
                bytes_per_line = ch * w
                qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
                self._result_pixmaps.append(QPixmap.fromImage(qt_image))

    def _refresh_results_preview(self):
        if not hasattr(self, '_result_pixmaps'):
            return
        # 清空旧格子
        for i in reversed(range(self.result_grid.count())):
            item = self.result_grid.itemAt(i)
            w = item.widget() if item else None
            if w:
                w.setParent(None)
        count = len(self._result_pixmaps)
        if count == 0:
            self.preview_label.setVisible(True)
            self.result_scroll.setVisible(False)
            self.preview_label.setText("拼接结果将显示在这里")
            return
        # 均分为接近方阵的网格
        import math
        cols = max(1, math.ceil(math.sqrt(count)))
        rows = math.ceil(count / cols)
        area = self.result_scroll.viewport().size()
        cell_w = max(50, area.width() // cols)
        cell_h = max(50, area.height() // rows)
        idx = 0
        for r in range(rows):
            for c in range(cols):
                if idx >= count:
                    break
                lbl = QLabel()
                lbl.setAlignment(Qt.AlignCenter)
                pix = self._result_pixmaps[idx]
                scaled = pix.scaled(cell_w-8, cell_h-8, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                lbl.setPixmap(scaled)
                self.result_grid.addWidget(lbl, r, c)
                idx += 1
    
    def save_result(self):
        """保存结果（仅PNG，无压缩）"""
        if self.result_image is None:
            QMessageBox.warning(self, "警告", "没有可保存的结果")
            return
        base_dir = Path(self.dir_edit.text().strip() or Path.home())
        default_dir = base_dir / "stitch"
        try:
            default_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        default_path = default_dir / "stitched_result.png"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存拼接结果为PNG", 
            str(default_path),
            "PNG 图片 (*.png)"
        )
        if file_path:
            # 强制 .png 后缀
            if not str(file_path).lower().endswith('.png'):
                file_path = str(file_path) + '.png'
            try:
                encode_param = [int(cv2.IMWRITE_PNG_COMPRESSION), 0]
                success, encoded_img = cv2.imencode('.png', self.result_image, encode_param)
                if success:
                    with open(file_path, 'wb') as f:
                        f.write(encoded_img.tobytes())
                    self.log(f"💾 结果已保存到(无压缩PNG): {file_path}")
                    QMessageBox.information(self, "✅ 成功", f"图片已成功保存到:\n\n{file_path}")
                else:
                    raise Exception("图片编码失败")
            except Exception as e:
                self.log(f"❌ 保存失败: {str(e)}")
                QMessageBox.critical(self, "错误", f"保存失败:\n{str(e)}")

    def _apply_global_styles(self):
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
        radius = 10
        self.setStyleSheet(
            f"QPushButton[btn='primary'] {{ color: white; background-color: {hi_rgb}; border: 1px solid {hi_rgb}; border-radius: {radius}px; padding: 6px 14px; font-weight: 600; }}"
            f"QPushButton[btn='primary']:hover {{ background-color: {hi_hover}; border-color: {hi_hover}; }}"
            f"QPushButton[btn='primary']:pressed {{ background-color: {hi_press}; border-color: {hi_press}; }}"
            f"QPushButton[btn='primary']:disabled {{ background-color: rgba(180,180,180,0.5); border-color: rgba(160,160,160,0.4); color: rgba(255,255,255,0.8); }}"
            f"QPushButton[btn='secondary'] {{ color: {base_txt}; background-color: {sec_bg}; border: 1px solid {sec_bor}; border-radius: {radius}px; padding: 5px 12px; }}"
            "QPushButton[btn='secondary']:hover { background-color: rgba(127,127,127,0.15); }"
            "QPushButton[btn='secondary']:pressed { background-color: rgba(127,127,127,0.25); }"
        )

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.ApplicationPaletteChange, QEvent.PaletteChange, QEvent.StyleChange):
            try:
                self._apply_global_styles()
                # 进度条颜色刷新
                pal = self.palette()
                try:
                    hi = pal.color(pal.ColorRole.Highlight)
                except Exception:
                    hi = pal.highlight().color()  # type: ignore
                self.progress_bar.setStyleSheet(
                    "QProgressBar { border: 1px solid palette(Mid); border-radius: 3px; min-height: 6px; }"
                    f"QProgressBar::chunk {{ background-color: rgb({hi.red()},{hi.green()},{hi.blue()}); border-radius: 3px; }}"
                )
            except Exception:
                pass
        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        try:
            self._save_settings()
        except Exception:
            pass
        return super().closeEvent(event)

    def _restore_settings(self):
        self._settings = QSettings('AYE', 'AutoStitchV4')
        last_dir = self._settings.value('last_dir', '', type=str)
        if last_dir:
            self.dir_edit.setText(last_dir)
        try:
            self._thumb_size = int(self._settings.value('thumb', self._thumb_size))
            self.thumb_slider.setValue(self._thumb_size)
        except Exception:
            pass
        try:
            w = int(self._settings.value('win_w', self.width()))
            h = int(self._settings.value('win_h', self.height()))
            self.resize(max(600, w), max(400, h))
        except Exception:
            pass
        try:
            sizes = self._settings.value('vsplitter', None)
            if isinstance(sizes, list) and len(sizes) == 2:
                self.vsplitter.setSizes([int(sizes[0]), int(sizes[1])])
        except Exception:
            pass

    def _save_settings(self):
        if not hasattr(self, '_settings'):
            self._settings = QSettings('AYE', 'AutoStitchV4')
        self._settings.setValue('last_dir', self.dir_edit.text().strip())
        self._settings.setValue('thumb', self._thumb_size)
        self._settings.setValue('win_w', self.width())
        self._settings.setValue('win_h', self.height())
        if hasattr(self, 'vsplitter'):
            self._settings.setValue('vsplitter', self.vsplitter.sizes())


def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    # 不设置标题栏图标（按需可从磁盘加载，但这里隐藏图标）
    themed_icon = QIcon()
    window = MainWindow()
    # 保持窗口图标为空，避免标题栏显示图标
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
