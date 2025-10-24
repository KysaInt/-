# -*- coding: utf-8 -*-
import sys
import os
import subprocess
import importlib.util
import ctypes
from ctypes import wintypes

# 全局缓存，防止图标被垃圾回收
_ICON_CACHE = {}


def check_and_regenerate_ui():
    """
    确认并根据本目录的 form.ui 生成 ui_form.py（若缺失或过期）。
    依赖 pyside6-uic，请确保其在 PATH 中。
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ui_file = os.path.join(script_dir, "form.ui")
    py_file = os.path.join(script_dir, "ui_form.py")

    if not os.path.exists(ui_file):
        print("缺少 form.ui，无法生成 ui_form.py。")
        return

    # 若 ui_form.py 不存在，或 ui 比 ui_form 新，则重新生成
    if (not os.path.exists(py_file)) or (os.path.getmtime(ui_file) > os.path.getmtime(py_file)):
        print(f"正在从 {ui_file} 生成 {py_file} …")
        try:
            subprocess.run(["pyside6-uic", ui_file, "-o", py_file], check=True)
            print("UI 生成成功。")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"生成 UI 失败: {e}")
            print("请确认已安装 PySide6，并且 pyside6-uic 可用。")
            sys.exit(1)


# 先尝试生成 ui_form.py 再导入
check_and_regenerate_ui()

from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtGui import QIcon, QGuiApplication
from PySide6.QtCore import QSize, Qt
try:
    from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QAction
except Exception:
    QSystemTrayIcon = None
from ui_form import Ui_Widget
from typing import Optional

# ------------ 图标加载与托盘封装（复用 QT/AYE/main.pyw 的做法并增强）------------
def _load_app_icon_with_fallbacks() -> Optional[QIcon]:
    """尝试按优先级加载多分辨率 ICO，返回 QIcon 或 None。
    优先使用 tts/duck.ico；若无效，降级使用 QT/AYE/icon.ico。
    """
    # 确保在 Windows 的 .pyw 环境下也能正确获取脚本目录
    if getattr(sys, 'frozen', False):
        # 如果是打包后的exe
        script_dir = os.path.dirname(sys.executable)
    else:
        # 正常的 Python 脚本
        script_dir = os.path.dirname(os.path.abspath(__file__))
    
    icon_candidates = [
        os.path.join(script_dir, "duck.ico"),
        os.path.join(os.path.dirname(script_dir), "QT", "AYE", "icon.ico"),
    ]

    for p in icon_candidates:
        # 规范化路径，确保在 Windows 下正确处理
        p = os.path.normpath(os.path.abspath(p))
        if os.path.exists(p):
            ic = QIcon(p)
            # availableSizes 在 ICO 上有时为空，不作为唯一判断标准，仍打印日志辅助排查
            try:
                sizes = ic.availableSizes()
            except Exception:
                sizes = []
            if not ic.isNull():
                print(f"[ICON] Loaded: {p} ; sizes={sizes}")
                _ICON_CACHE['app_icon'] = ic  # 防止被 GC
                return ic
            else:
                print(f"[ICON] Found but failed to load (null): {p}")
        else:
            print(f"[ICON] Candidate not found: {p}")
    print("[ICON] No valid icon loaded; will rely on Qt defaults (may show白纸)")
    return None

def _ensure_system_tray(parent_widget: QWidget, icon: Optional[QIcon]):
    """创建系统托盘图标与菜单，确保托盘图标不是白纸。
    若系统不支持或导入失败则跳过。
    """
    if QSystemTrayIcon is None or not QSystemTrayIcon.isSystemTrayAvailable():
        print("[TRAY] System tray not available; skip")
        return
    try:
        tray = QSystemTrayIcon(parent_widget)
        if icon is None or icon.isNull():
            # 尝试使用当前应用图标
            icon = parent_widget.windowIcon() or QApplication.instance().windowIcon()
        if icon is not None and not icon.isNull():
            tray.setIcon(icon)
        tray.setToolTip("AYE TTS 工具集")

        # 右键菜单
        menu = QMenu(parent_widget)
        act_show = QAction("显示窗口", parent_widget)
        act_quit = QAction("退出", parent_widget)
        menu.addAction(act_show)
        menu.addSeparator()
        menu.addAction(act_quit)
        tray.setContextMenu(menu)

        def _on_show():
            parent_widget.showNormal()
            parent_widget.activateWindow()

        act_show.triggered.connect(_on_show)
        act_quit.triggered.connect(QApplication.instance().quit)

        tray.show()
        # 缓存，避免被 GC
        parent_widget._tray_icon = tray
        parent_widget._tray_menu = menu
        print("[TRAY] System tray icon created")
    except Exception as e:
        print(f"[TRAY] Failed to create tray: {e}")


def load_class_from_file(file_path: str, module_name_alias: str, class_name: str):
    """动态从文件加载模块中的类（支持以数字命名的 .pyw 文件）"""
    spec = importlib.util.spec_from_file_location(module_name_alias, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法为 {file_path} 创建模块规范")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name_alias] = module
    spec.loader.exec_module(module)
    try:
        return getattr(module, class_name)
    except AttributeError as e:
        raise ImportError(f"{file_path} 中未找到类 {class_name}") from e


# 引入两个模块（作为子部件嵌入）
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_MOD1_PATH = os.path.join(_SCRIPT_DIR, "1.pyw")
_MOD2_PATH = os.path.join(_SCRIPT_DIR, "2.pyw")

try:
    ModuleOneWidget = load_class_from_file(_MOD1_PATH, "tts_module_1", "TTSApp")
except Exception as e:
    print(f"导入模块一失败: {e}")
    ModuleOneWidget = None

try:
    ModuleTwoWidget = load_class_from_file(_MOD2_PATH, "subtitle_module_2", "SubtitlePauseMatcherUI")
except Exception as e:
    print(f"导入模块二失败: {e}")
    ModuleTwoWidget = None


class MainWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_Widget()
        self.ui.setupUi(self)
        self.setWindowTitle("TTS 工具集")
        
        # 缓存对象，防止被 GC 回收
        self._icon_cache = {}
        self._tray_icon = None
        self._tray_menu = None

        # --- 模块一：情绪TTS ---
        page_layout_1 = self.ui.page_1.layout()
        while page_layout_1.count():
            item = page_layout_1.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        if ModuleOneWidget is not None:
            self.module1 = ModuleOneWidget()
            page_layout_1.addWidget(self.module1)
        self.ui.navigationList.item(0).setText("情绪TTS")

        # --- 模块二：字幕停顿匹配 ---
        page_layout_2 = self.ui.page_2.layout()
        while page_layout_2.count():
            item = page_layout_2.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        if ModuleTwoWidget is not None:
            self.module2 = ModuleTwoWidget()
            page_layout_2.addWidget(self.module2)
        self.ui.navigationList.item(1).setText("字幕匹配")

        # 可选：隐藏第三页占位（若不需要）
        try:
            if self.ui.navigationList.count() >= 3:
                self.ui.navigationList.item(2).setText("")
        except Exception:
            pass


if __name__ == "__main__":
    # Windows: 在创建任何窗口之前设置 AUMID，有助于任务栏分组和图标关联
    if sys.platform.startswith("win"):
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AYE.TTS.App.1.0")
        except Exception:
            pass

    # 高分屏下使用高分辨率位图，改善图标清晰度
    try:
        QGuiApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    except Exception:
        pass

    app = QApplication(sys.argv)
    
    # 设置应用信息
    app.setOrganizationName("AYE")
    app.setOrganizationDomain("local.aye")
    app.setApplicationName("AYE TTS")
    app.setApplicationDisplayName("AYE TTS 工具集")

    # 加载应用图标（带多路径回退），并设置为全局默认
    app_icon = _load_app_icon_with_fallbacks()
    if app_icon is not None and not app_icon.isNull():
        app.setWindowIcon(app_icon)

    w = MainWidget()
    # 再对主窗口显式设置一次，确保任务栏/Alt+Tab 使用
    if app_icon is not None:
        w.setWindowIcon(app_icon)

    # 创建系统托盘图标（可从任务栏最右侧看到，避免白纸）
    _ensure_system_tray(w, app_icon)

    # 显示窗口
    w.show()
    
    # Windows 特定：在窗口显示后，使用 Windows API 同时设置窗口图标与窗口类图标
    # 这样可覆盖任务栏可能读取的不同来源（窗口/类/进程）
    if sys.platform.startswith("win") and app_icon is not None:
        try:
            # 确保原生窗口已创建
            if w.windowHandle() is not None:
                _ = w.windowHandle().winId()
            hwnd = int(w.winId())

            # 解析图标路径
            if getattr(sys, 'frozen', False):
                script_dir = os.path.dirname(sys.executable)
            else:
                script_dir = os.path.dirname(os.path.abspath(__file__))
            icon_path = os.path.normpath(os.path.join(script_dir, "duck.ico"))

            if os.path.exists(icon_path):
                user32 = ctypes.windll.user32
                IMAGE_ICON = 1
                LR_LOADFROMFILE = 0x00000010
                # 加载大图标 (32x32) 与小图标 (16x16)
                hicon_large = user32.LoadImageW(0, icon_path, IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
                hicon_small = user32.LoadImageW(0, icon_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)

                WM_SETICON = 0x0080
                ICON_SMALL = 0
                ICON_BIG = 1

                # 设置窗口实例图标
                if hicon_large:
                    user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_large)
                if hicon_small:
                    user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)

                # 同时设置窗口类图标，提升任务栏采用率
                GCLP_HICON = -14
                GCLP_HICONSM = -34
                try:
                    SetClassIcon = getattr(user32, 'SetClassLongPtrW', None)
                    if SetClassIcon is None:
                        SetClassIcon = user32.SetClassLongW
                    SetClassIcon(hwnd, GCLP_HICON, hicon_large)
                    SetClassIcon(hwnd, GCLP_HICONSM, hicon_small)
                except Exception:
                    pass

                # 缓存句柄，避免被提前释放
                _ICON_CACHE['hicon_large'] = hicon_large
                _ICON_CACHE['hicon_small'] = hicon_small

                if hicon_large or hicon_small:
                    print(f"[ICON] Windows API icon set successfully (window + class): {icon_path}")
                else:
                    print(f"[ICON] Failed to load icon from: {icon_path}")
        except Exception as e:
            print(f"[ICON] Failed to set Windows icon via API: {e}")
            import traceback
            traceback.print_exc()

    sys.exit(app.exec())
