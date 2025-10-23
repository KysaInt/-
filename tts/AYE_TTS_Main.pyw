# -*- coding: utf-8 -*-
import sys
import os
import subprocess
import importlib.util
import ctypes  # Windows 任务栏图标支持
from ctypes import wintypes


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
from PySide6.QtGui import QIcon
from PySide6.QtCore import QSize
try:
    # 可选：用于创建系统托盘图标（Windows 通知区域）
    from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QAction
except Exception:
    QSystemTrayIcon = None
from ui_form import Ui_Widget

# 动态从文件加载模块中的类（支持以数字命名的 .pyw 文件）
def load_class_from_file(file_path: str, module_name_alias: str, class_name: str):
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
# 现按要求文件更名为 1.pyw 与 2.pyw，使用动态加载方式
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
            # 移除第3项导航并删除对应页面
            if self.ui.navigationList.count() >= 3:
                # 简易处理：将文本置空以避免误导
                self.ui.navigationList.item(2).setText("")
        except Exception:
            pass


if __name__ == "__main__":
    # --- Windows 原生方式设置任务栏/标题栏图标（增强兼容性） ---
    def _apply_win_taskbar_icon(hwnd: int, ico_path: str):
        if not (sys.platform.startswith("win") and os.path.exists(ico_path)):
            return
        try:
            # 常量
            WM_SETICON = 0x0080
            ICON_SMALL = 0
            ICON_BIG = 1
            IMAGE_ICON = 1
            LR_LOADFROMFILE = 0x0010
            # 64/32 兼容的 SetClassLongPtrW 选择
            try:
                SetClassLongPtr = ctypes.windll.user32.SetClassLongPtrW
            except AttributeError:
                SetClassLongPtr = ctypes.windll.user32.SetClassLongW
            GCLP_HICON = -14
            GCLP_HICONSM = -34

            user32 = ctypes.windll.user32
            # 加载不同尺寸图标
            hicon_big = user32.LoadImageW(None, ico_path, IMAGE_ICON, 256, 256, LR_LOADFROMFILE)
            if not hicon_big:
                hicon_big = user32.LoadImageW(None, ico_path, IMAGE_ICON, 64, 64, LR_LOADFROMFILE)
            hicon_small = user32.LoadImageW(None, ico_path, IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
            if not hicon_small:
                hicon_small = user32.LoadImageW(None, ico_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)

            if hicon_big:
                user32.SendMessageW(wintypes.HWND(hwnd), WM_SETICON, ICON_BIG, hicon_big)
                SetClassLongPtr(wintypes.HWND(hwnd), GCLP_HICON, hicon_big)
            if hicon_small:
                user32.SendMessageW(wintypes.HWND(hwnd), WM_SETICON, ICON_SMALL, hicon_small)
                SetClassLongPtr(wintypes.HWND(hwnd), GCLP_HICONSM, hicon_small)
        except Exception:
            pass

    # 设置 Windows AppUserModelID（让任务栏图标更稳定）
    if sys.platform.startswith("win"):
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AYE.TTS.App.1.0")
        except Exception:
            pass

    app = QApplication(sys.argv)

    # 建议设置应用信息，有助于 Windows 分组与配置保存
    try:
        app.setOrganizationName("AYE")
        app.setOrganizationDomain("local.aye")
        app.setApplicationName("AYE TTS")
        app.setApplicationDisplayName("AYE TTS 工具集")
    except Exception:
        pass

    # 设置应用图标（可选）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # 覆盖优先级：
    # 1) 环境变量 AYE_TTS_ICON 指定的路径（可相对，可绝对）
    # 2) 同目录 icon.path 文件中首行指定的路径
    # 3) 本目录 icon.ico
    # 4) 兜底 QT/AYE/icon.ico
    icon_path = None
    # 1) 环境变量
    env_icon = os.environ.get("AYE_TTS_ICON", "").strip().strip('"')
    if env_icon:
        icon_candidate = env_icon if os.path.isabs(env_icon) else os.path.join(script_dir, env_icon)
        if os.path.exists(icon_candidate):
            icon_path = os.path.abspath(icon_candidate)
    # 2) icon.path 文件
    if icon_path is None:
        try:
            icon_path_cfg = os.path.join(script_dir, "icon.path")
            if os.path.exists(icon_path_cfg):
                with open(icon_path_cfg, "r", encoding="utf-8") as f:
                    first_line = f.readline().strip().strip('"')
                if first_line:
                    icon_candidate = first_line if os.path.isabs(first_line) else os.path.join(script_dir, first_line)
                    if os.path.exists(icon_candidate):
                        icon_path = os.path.abspath(icon_candidate)
        except Exception:
            pass
    # 3) 本目录 icon.ico
    if icon_path is None:
        default_ico = os.path.join(script_dir, "icon.ico")
        if os.path.exists(default_ico):
            icon_path = default_ico
    # 4) 兜底路径
    if icon_path is None:
        alt_path = os.path.join(os.path.dirname(script_dir), "QT", "AYE", "icon.ico")
        if os.path.exists(alt_path):
            icon_path = alt_path
    app_icon = None
    if icon_path and os.path.exists(icon_path):
        app_icon = QIcon(icon_path)
        # 可选：显式注册常用尺寸，提升不同缩放比下的清晰度
        try:
            for sz in (16, 24, 32, 48, 64, 128, 256):
                app_icon.addFile(icon_path, QSize(sz, sz))
        except Exception:
            pass
        app.setWindowIcon(app_icon)
        print(f"[ICON] Using icon: {icon_path}")
    else:
        print("[ICON] No icon found — using default.")

    w = MainWidget()
    if app_icon is not None:
        w.setWindowIcon(app_icon)
    w.show()
    # 使用 Win32 API 进一步强制设置任务栏与窗口类图标
    try:
        hwnd = int(w.winId())
        # 仅当是 .ico 时，使用 Win32 API 强制设置（PNG/JPG 无法直接加载为 HICON）
        if icon_path and os.path.exists(icon_path) and icon_path.lower().endswith('.ico'):
            _apply_win_taskbar_icon(hwnd, icon_path)
    except Exception:
        pass

    # Windows 通知区域图标（如需在状态区域显示图标）
    try:
        if QSystemTrayIcon is not None and QSystemTrayIcon.isSystemTrayAvailable() and app_icon is not None:
            tray = QSystemTrayIcon(app_icon, w)
            # 简易菜单：还原窗口 / 退出
            menu = QMenu()
            act_show = QAction("显示窗口", menu)
            act_quit = QAction("退出", menu)
            act_show.triggered.connect(lambda: (w.showNormal(), w.activateWindow()))
            act_quit.triggered.connect(app.quit)
            menu.addAction(act_show)
            menu.addSeparator()
            menu.addAction(act_quit)
            tray.setContextMenu(menu)
            tray.setToolTip("AYE TTS 工具集")
            tray.show()
            # 保存引用，避免被 GC 回收
            w._tray_icon = tray
            w._tray_menu = menu
    except Exception:
        pass

    sys.exit(app.exec())
