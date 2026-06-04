# -*- coding: utf-8 -*-
"""
hub.pyw — M3 整合主框架
左侧导航栏 + 右侧三个内嵌模块，启动时同步加载所有模块：
  1. 图形驱动  (module1_图形驱动.pyw → EmbeddedVisualizerModule  ← 启动.bat 所启动的程序)
  2. 音频分析  (ayeaa/ayeaa.pyw → MainPage)
  3. 预留模块  (占位)
"""

import importlib.util
import os
import sys
from pathlib import Path

_DIR = Path(__file__).resolve().parent


# ── venv 自举 ──────────────────────────────────────────────────────────────────
def _ensure_venv():
    """若当前环境找不到 PySide6，则用 venv313 重启。"""
    if importlib.util.find_spec("PySide6") is not None:
        return
    for candidate in [
        _DIR / "venv313" / "Scripts" / "pythonw.exe",
        _DIR / "venv313" / "Scripts" / "python.exe",
    ]:
        if candidate.exists():
            import subprocess
            subprocess.Popen([str(candidate), str(__file__)] + sys.argv[1:])
            break
    sys.exit(0)


_ensure_venv()

# ── 路径设置 ──────────────────────────────────────────────────────────────────
# M3 目录（0.pyw / module1 / core/ 等）
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))

# ayeaa 目录（让 hub_audio 模块相对导入正常工作）
_ayeaa_dir = _DIR / "ayeaa"
if str(_ayeaa_dir) not in sys.path:
    sys.path.insert(0, str(_ayeaa_dir))

# 先强制载入 venv313 的 numpy，占住 sys.modules，
# 防止后续添加 ayeaa venv 路径时被替换为冲突版本
import numpy as _np  # noqa: F401

# ayeaa 私有 venv 的 site-packages（soundcard / aubio 等）
# 追加到末尾，避免覆盖 venv313 中已有的 numpy / PySide6 等包
_ayeaa_site = _ayeaa_dir / ".venv" / "Lib" / "site-packages"
if _ayeaa_site.exists() and str(_ayeaa_site) not in sys.path:
    sys.path.append(str(_ayeaa_site))

# ── Qt imports ────────────────────────────────────────────────────────────────
from PySide6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QListWidgetItem, QStackedWidget, QLabel,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPalette, QColor, QFont, QGuiApplication


# ── 深色主题 ──────────────────────────────────────────────────────────────────
def _apply_dark_palette(app: QApplication):
    app.setStyle("Fusion")
    pal = QPalette()
    _c = QColor
    pal.setColor(QPalette.Window,          _c(30,  30,  46))
    pal.setColor(QPalette.WindowText,      _c(220, 220, 230))
    pal.setColor(QPalette.Base,            _c(22,  22,  34))
    pal.setColor(QPalette.AlternateBase,   _c(30,  30,  46))
    pal.setColor(QPalette.Text,            _c(220, 220, 230))
    pal.setColor(QPalette.BrightText,      _c(255, 255, 255))
    pal.setColor(QPalette.Button,          _c(45,  45,  65))
    pal.setColor(QPalette.ButtonText,      _c(220, 220, 230))
    pal.setColor(QPalette.Highlight,       _c(100, 120, 255))
    pal.setColor(QPalette.HighlightedText, _c(255, 255, 255))
    pal.setColor(QPalette.Mid,             _c(60,  60,  85))
    pal.setColor(QPalette.Dark,            _c(18,  18,  28))
    pal.setColor(QPalette.Shadow,          _c(10,  10,  18))
    pal.setColor(QPalette.Link,            _c(120, 140, 255))
    app.setPalette(pal)


# ── 通用工具 ──────────────────────────────────────────────────────────────────
def _load_file_as_module(mod_name: str, file_path: Path):
    """将任意 .py/.pyw 文件作为独立模块动态加载。"""
    spec = importlib.util.spec_from_file_location(mod_name, str(file_path))
    mod = importlib.util.module_from_spec(spec)
    mod.__file__ = str(file_path)
    spec.loader.exec_module(mod)
    return mod


def _error_page(msg: str) -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setAlignment(Qt.AlignCenter)
    lbl = QLabel(msg)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setWordWrap(True)
    font = QFont()
    font.setPointSize(11)
    lbl.setFont(font)
    lbl.setStyleSheet("color: #f87171; padding: 24px;")
    lay.addWidget(lbl)
    return w


def _loading_page(label: str) -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setAlignment(Qt.AlignCenter)
    lbl = QLabel(f"正在加载  {label} ...")
    lbl.setAlignment(Qt.AlignCenter)
    font = QFont()
    font.setPointSize(13)
    lbl.setFont(font)
    lbl.setStyleSheet("color: #6b7280;")
    lay.addWidget(lbl)
    return w


# ── 主窗口 ────────────────────────────────────────────────────────────────────
class HubWindow(QWidget):
    _NAV_W = 74                          # 左侧导航栏宽度（px）
    _MODULES = [                         # (导航显示名, 内部标识)
        ("图形\n驱动",    "viz"),
        ("音频\n分析",    "audio"),
        ("模块\n三",      "placeholder"),
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("M3 Hub")
        self._page_widgets: list[QWidget | None] = [None] * len(self._MODULES)
        self._build_ui()
        # 窗口显示后立刻同步加载全部模块
        QTimer.singleShot(0, self._load_all)

    # ── 布局 ──────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 侧边栏导航
        self._nav = QListWidget()
        self._nav.setFixedWidth(self._NAV_W)
        self._nav.setFrameShape(QListWidget.NoFrame)
        self._nav.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._nav.setStyleSheet("""
            QListWidget {
                background: #13131f;
                border: none;
                border-right: 1px solid #252538;
                outline: none;
            }
            QListWidget::item {
                padding: 16px 2px;
                color: #9ca3af;
                border-bottom: 1px solid #1d1d2e;
                font-size: 11px;
            }
            QListWidget::item:selected {
                background: #1e1e38;
                color: #ffffff;
                border-left: 3px solid #6479ff;
            }
            QListWidget::item:hover:!selected {
                background: #191928;
                color: #d1d5db;
            }
        """)
        for title, _ in self._MODULES:
            item = QListWidgetItem(title)
            item.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            self._nav.addItem(item)
        self._nav.setCurrentRow(0)
        self._nav.itemClicked.connect(self._on_nav_click)

        # 内容堆叠页
        self._stack = QStackedWidget()
        for i, (title, _) in enumerate(self._MODULES):
            page = QWidget()
            page_lay = QVBoxLayout(page)
            page_lay.setContentsMargins(0, 0, 0, 0)
            page_lay.addWidget(_loading_page(title.replace("\n", "")))
            self._stack.addWidget(page)

        root.addWidget(self._nav)
        root.addWidget(self._stack, 1)

    def _on_nav_click(self, item: QListWidgetItem):
        self._stack.setCurrentIndex(self._nav.row(item))

    # ── 页面替换 ──────────────────────────────────────────────────────────────
    def _set_page_content(self, index: int, widget: QWidget):
        """将第 index 个页面的内容替换为 widget。"""
        page = self._stack.widget(index)
        lay = page.layout()
        while lay.count():
            item = lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        lay.addWidget(widget)
        self._page_widgets[index] = widget

    # ── 模块加载 ──────────────────────────────────────────────────────────────
    def _load_all(self):
        self._load_viz()
        self._load_audio()
        self._load_placeholder()

    def _load_viz(self):
        """模块 1：图形驱动（启动.bat 所启动的 0.pyw 可视化器，嵌入版）"""
        try:
            mod = _load_file_as_module("hub_viz", _DIR / "module1_图形驱动.pyw")
            widget = mod.MODULE_WIDGET()
            self._set_page_content(0, widget)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            self._set_page_content(0, _error_page(f"图形驱动加载失败\n\n{exc}"))

    def _load_audio(self):
        """模块 2：音频分析（ayeaa/ayeaa.pyw → MainPage）"""
        try:
            mod = _load_file_as_module("hub_audio", _ayeaa_dir / "ayeaa.pyw")
            widget = mod.MainPage()
            self._set_page_content(1, widget)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            self._set_page_content(1, _error_page(f"音频分析加载失败\n\n{exc}"))

    def _load_placeholder(self):
        """模块 3：预留"""
        ph = QWidget()
        lay = QVBoxLayout(ph)
        lay.setAlignment(Qt.AlignCenter)
        lbl = QLabel("待接入")
        lbl.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(20)
        lbl.setFont(font)
        lbl.setStyleSheet("color: #374151;")
        lay.addWidget(lbl)
        self._set_page_content(2, ph)

    # ── 关闭清理 ──────────────────────────────────────────────────────────────
    def closeEvent(self, event):
        # 停止音频线程
        audio = self._page_widgets[1]
        if audio is not None and hasattr(audio, "stop_runtime"):
            try:
                audio.stop_runtime()
            except Exception:
                pass
        # 停止图形渲染
        viz = self._page_widgets[0]
        if viz is not None and hasattr(viz, "_stop_visualizer"):
            try:
                viz._stop_visualizer()
            except Exception:
                pass
        super().closeEvent(event)


# ── 入口 ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import ctypes
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AYE.M3Hub.1")
    except Exception:
        pass

    os.chdir(str(_DIR))

    app = QApplication(sys.argv)
    _apply_dark_palette(app)

    win = HubWindow()
    win.resize(1600, 920)
    win.setMinimumSize(900, 500)

    # 居中屏幕
    screen = QGuiApplication.primaryScreen()
    if screen:
        geo = screen.availableGeometry()
        win.move(
            geo.x() + (geo.width()  - win.width())  // 2,
            geo.y() + (geo.height() - win.height()) // 2,
        )

    win.show()
    sys.exit(app.exec())
