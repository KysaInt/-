# -*- coding: utf-8 -*-
import sys
import os
import subprocess
import importlib.util
import ctypes  # Windows 任务栏图标支持
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
            # 移除第3项导航并删除对应页面
            if self.ui.navigationList.count() >= 3:
                # 简易处理：将文本置空以避免误导
                self.ui.navigationList.item(2).setText("")
        except Exception:
            pass


if __name__ == "__main__":
    # --- Windows 原生方式设置任务栏/标题栏图标（增强兼容性） ---
    def _apply_win_taskbar_icon(hwnd: int, ico_path: str):
        """使用 Win32 API 为窗口句柄和窗口类设置 ICO 图标"""
        if not (sys.platform.startswith("win") and os.path.exists(ico_path) and ico_path.lower().endswith('.ico')):
            print(f"[ICON_API] Skipped: Not a valid .ico file or platform: {ico_path}")
            return
        try:
            # 常量
            WM_SETICON = 0x0080
            ICON_SMALL = 0
            ICON_BIG = 1
            IMAGE_ICON = 1
            LR_LOADFROMFILE = 0x0010
            
            # 64/32 兼容的 SetClassLongPtrW
            try:
                SetClassLongPtr = ctypes.windll.user32.SetClassLongPtrW
            except AttributeError:
                SetClassLongPtr = ctypes.windll.user32.SetClassLongW
            GCLP_HICON = -14
            GCLP_HICONSM = -34
            
            user32 = ctypes.windll.user32
            
            # 加载大图标 (任务栏、Alt+Tab)
            hicon_big = user32.LoadImageW(None, ico_path, IMAGE_ICON, 256, 256, LR_LOADFROMFILE)
            if not hicon_big:
                hicon_big = user32.LoadImageW(None, ico_path, IMAGE_ICON, 64, 64, LR_LOADFROMFILE)
            
            # 加载小图标 (标题栏)
            hicon_small = user32.LoadImageW(None, ico_path, IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
            if not hicon_small:
                hicon_small = user32.LoadImageW(None, ico_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)

            # 为窗口实例设置图标
            if hicon_big:
                user32.SendMessageW(wintypes.HWND(hwnd), WM_SETICON, ICON_BIG, hicon_big)
            if hicon_small:
                user32.SendMessageW(wintypes.HWND(hwnd), WM_SETICON, ICON_SMALL, hicon_small)
            
            # 为窗口类设置图标 (更持久)
            if hicon_big:
                SetClassLongPtr(wintypes.HWND(hwnd), GCLP_HICON, hicon_big)
            if hicon_small:
                SetClassLongPtr(wintypes.HWND(hwnd), GCLP_HICONSM, hicon_small)
            
            print(f"[ICON_API] Successfully applied {ico_path} to HWND {hwnd} and its class.")

        except Exception as e:
            print(f"[ICON_API] Error applying icon: {e}")
            pass

    def _apply_win_relaunch_properties(hwnd: int, app_id: str, ico_path: str, relaunch_cmd: str | None = None, display_name: str | None = None):
        """为窗口设置 AppUserModel Relaunch 属性，增强任务栏图标一致性。

        说明：部分环境下，仅设置 QIcon/WM_SETICON 仍可能显示 pythonw.exe 的图标；
        为窗口设置 IPropertyStore 的 RelaunchIconResource 可提高任务栏图标稳定性。
        """
        if not sys.platform.startswith("win"):
            return
        try:
            from ctypes import POINTER, Structure, Union

            class GUID(Structure):
                _fields_ = [
                    ("Data1", wintypes.DWORD),
                    ("Data2", wintypes.WORD),
                    ("Data3", wintypes.WORD),
                    ("Data4", ctypes.c_ubyte * 8),
                ]

            class PROPERTYKEY(Structure):
                _fields_ = [("fmtid", GUID), ("pid", wintypes.DWORD)]

            class PROPVARIANT_UNION(Union):
                _fields_ = [("pwszVal", wintypes.LPWSTR)]

            class PROPVARIANT(Structure):
                _fields_ = [
                    ("vt", wintypes.USHORT),
                    ("wReserved1", wintypes.USHORT),
                    ("wReserved2", wintypes.USHORT),
                    ("wReserved3", wintypes.USHORT),
                    ("u", PROPVARIANT_UNION),
                ]

            class IPropertyStore(Structure):
                pass

            IPropertyStore._fields_ = [("lpVtbl", POINTER(ctypes.c_void_p))]

            # GUID 常量
            IID_IPropertyStore = GUID(
                0x886D8EEB, 0x8CF2, 0x4446,
                (ctypes.c_ubyte * 8)(0x8D, 0x02, 0xCD, 0xBA, 0x1D, 0xBD, 0xCF, 0x99)
            )
            FMTID_AppUserModel = GUID(
                0x9F4C2855, 0x9F79, 0x4B39,
                (ctypes.c_ubyte * 8)(0xA8, 0xD0, 0xE1, 0xD4, 0x2D, 0xE1, 0xD5, 0xF3)
            )

            # PKEY_AppUserModel_ID (pid=5) 与 Relaunch 属性
            PKEY_AUMID = PROPERTYKEY(FMTID_AppUserModel, 5)
            PKEY_RelaunchIcon = PROPERTYKEY(FMTID_AppUserModel, 3)
            PKEY_RelaunchCommand = PROPERTYKEY(FMTID_AppUserModel, 2)
            PKEY_RelaunchDisplayName = PROPERTYKEY(FMTID_AppUserModel, 4)

            # 获取 IPropertyStore
            SHGetPropertyStoreForWindow = ctypes.windll.shell32.SHGetPropertyStoreForWindow
            SHGetPropertyStoreForWindow.restype = wintypes.HRESULT
            SHGetPropertyStoreForWindow.argtypes = [wintypes.HWND, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)]

            ppv = ctypes.c_void_p()
            hr = SHGetPropertyStoreForWindow(wintypes.HWND(hwnd), ctypes.byref(IID_IPropertyStore), ctypes.byref(ppv))
            if hr < 0 or not ppv.value:
                return

            propstore_ptr = ctypes.cast(ppv.value, POINTER(IPropertyStore))

            # vtbl: [0]=QI,1=AddRef,2=Release,3=GetCount,4=GetAt,5=GetValue,6=SetValue,7=Commit
            vtbl = propstore_ptr.contents.lpVtbl
            HRESULT = wintypes.HRESULT
            SetValueProto = ctypes.WINFUNCTYPE(HRESULT, POINTER(IPropertyStore), ctypes.POINTER(PROPERTYKEY), ctypes.POINTER(PROPVARIANT))
            CommitProto = ctypes.WINFUNCTYPE(HRESULT, POINTER(IPropertyStore))
            ReleaseProto = ctypes.WINFUNCTYPE(ctypes.c_ulong, POINTER(IPropertyStore))

            SetValue = SetValueProto(vtbl[6])
            Commit = CommitProto(vtbl[7])
            Release = ReleaseProto(vtbl[2])

            def _pv_from_wstr(s: str) -> PROPVARIANT:
                pv = PROPVARIANT()
                pv.vt = 31  # VT_LPWSTR
                pv.u.pwszVal = ctypes.c_wchar_p(s)
                return pv

            # 写入 AUMID
            if app_id:
                pv_id = _pv_from_wstr(app_id)
                SetValue(propstore_ptr, ctypes.byref(PKEY_AUMID), ctypes.byref(pv_id))

            # 写入 RelaunchIconResource（建议 “绝对路径,资源索引” 形式；.ico 可用 0）
            if ico_path and os.path.exists(ico_path):
                icon_res = f"{ico_path},0"
                pv_icon = _pv_from_wstr(icon_res)
                SetValue(propstore_ptr, ctypes.byref(PKEY_RelaunchIcon), ctypes.byref(pv_icon))

            # 写入 RelaunchCommand（用于任务栏固定/重启时解析正确图标与名称）
            if relaunch_cmd:
                pv_cmd = _pv_from_wstr(relaunch_cmd)
                SetValue(propstore_ptr, ctypes.byref(PKEY_RelaunchCommand), ctypes.byref(pv_cmd))

            # 写入显示名（提升展示一致性）
            if display_name:
                pv_name = _pv_from_wstr(display_name)
                SetValue(propstore_ptr, ctypes.byref(PKEY_RelaunchDisplayName), ctypes.byref(pv_name))

            Commit(propstore_ptr)
            Release(propstore_ptr)
        except Exception:
            # 忽略任意失败，尽可能保持无侵入
            pass

    # 设置 Windows AppUserModelID（与 QT/AYE/main.pyw 区分，避免两个程序在任务栏合并）
    if sys.platform.startswith("win"):
        try:
            # 为 TTS 使用独立的 AUMID
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

    # 设置应用图标（优先当前目录 icon.ico 或 icon.png，与参考实现一致）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # 覆盖优先级：
    # 1) 环境变量 AYE_TTS_ICON 指定的路径（可相对，可绝对）
    # 2) 同目录 icon.path 文件中首行指定的路径
    # 3) 本目录 icon.ico 或 icon.png（ICO 优先，确保质量）
    # 4) 兜底 QT/AYE/icon.ico 或 QT/AYE/icon.png
    icon_path = None
    icon_path_for_relaunch = None  # 用于 Relaunch 属性的 ICO 路径
    
    # 1) 环境变量
    env_icon = os.environ.get("AYE_TTS_ICON", "").strip().strip('"')
    if env_icon:
        icon_candidate = env_icon if os.path.isabs(env_icon) else os.path.join(script_dir, env_icon)
        if os.path.exists(icon_candidate):
            icon_path = os.path.abspath(icon_candidate)
            print(f"[ICON] 从环境变量加载: {icon_path}")
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
                        print(f"[ICON] 从 icon.path 加载: {icon_path}")
        except Exception:
            pass
    # 3) 本目录 icon.ico 或 icon.png（ICO 优先以获得最佳任务栏显示）
    if icon_path is None:
        ico_ico = os.path.join(script_dir, "icon.ico")
        png_ico = os.path.join(script_dir, "icon.png")
        if os.path.exists(ico_ico):
            icon_path = ico_ico
            print(f"[ICON] 从本目录加载 ICO: {icon_path}")
        elif os.path.exists(png_ico):
            icon_path = png_ico
            print(f"[ICON] 从本目录加载 PNG: {icon_path}")
    # 4) 兜底路径（QT/AYE 中的 ICO 或 PNG）
    if icon_path is None:
        alt_ico = os.path.join(os.path.dirname(script_dir), "QT", "AYE", "icon.ico")
        alt_png = os.path.join(os.path.dirname(script_dir), "QT", "AYE", "icon.png")
        if os.path.exists(alt_ico):
            icon_path = alt_ico
            print(f"[ICON] 从备选目录加载 ICO: {icon_path}")
        elif os.path.exists(alt_png):
            icon_path = alt_png
            print(f"[ICON] 从备选目录加载 PNG: {icon_path}")
    
    # 为 Relaunch 属性查找有效的 ICO 文件（备选）
    if icon_path is not None:
        # 优先使用 .ico 文件作为 Relaunch 属性的值
        if icon_path.lower().endswith('.ico'):
            icon_path_for_relaunch = icon_path
        else:
            # 如果当前 icon_path 是 PNG，寻找备选的 ICO
            ico_paths_to_try = [
                os.path.join(script_dir, "icon.ico"),
                os.path.join(script_dir, "icon_tb.ico"),
                os.path.join(os.path.dirname(script_dir), "QT", "AYE", "icon.ico"),
            ]
            for candidate_ico in ico_paths_to_try:
                if os.path.exists(candidate_ico) and candidate_ico.lower().endswith('.ico'):
                    icon_path_for_relaunch = candidate_ico
                    break
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
        # 保存到全局缓存，防止被 GC 回收
        _ICON_CACHE['app_icon'] = app_icon
        print(f"[ICON] Using icon: {icon_path}")
    else:
        print("[ICON] No icon found — using default.")

    w = MainWidget()
    if app_icon is not None:
        w.setWindowIcon(app_icon)

    # 先显示窗口以创建原生窗口句柄
    w.show()
    
    # 在显示窗口后立即设置窗口属性（确保任务栏分组按窗口 AUMID 生效）
    try:
        hwnd = int(w.winId())  # 获取原生窗口句柄
        if hwnd:
            # 组合 RelaunchCommand："pythonw.exe" "当前脚本"
            _script_path = os.path.abspath(__file__)
            _exe = sys.executable
            # PowerShell/Windows 解析时需要正确引用路径中的空格
            relaunch_cmd = f'"{_exe}" "{_script_path}"'
            _apply_win_relaunch_properties(
                hwnd,
                "AYE.TTS.App.1.0",
                icon_path_for_relaunch or icon_path or "",
                relaunch_cmd=relaunch_cmd,
                display_name="AYE TTS 工具集",
            )
    except Exception:
        pass

    # 最终强制手段：使用 Win32 API 直接加载并设置图标
    try:
        if sys.platform.startswith("win"):
            hwnd = int(w.winId())
            if icon_path_for_relaunch and os.path.exists(icon_path_for_relaunch):
                _apply_win_taskbar_icon(hwnd, icon_path_for_relaunch)
            elif icon_path and os.path.exists(icon_path):
                # 若 icon_path 是 PNG，尝试转换或使用备选
                if icon_path.lower().endswith('.png'):
                    # 尝试从 PySide6 转换 PNG -> ICO 到内存或临时位置
                    try:
                        from PySide6.QtGui import QPixmap
                        pixmap = QPixmap(icon_path)
                        # 临时存储转换后的 ICO
                        temp_ico = os.path.join(script_dir, ".icon_temp.ico")
                        pixmap.save(temp_ico, "ICO")
                        if os.path.exists(temp_ico):
                            _apply_win_taskbar_icon(hwnd, temp_ico)
                            try:
                                os.remove(temp_ico)  # 清理临时文件
                            except:
                                pass
                    except Exception:
                        pass
                else:
                    _apply_win_taskbar_icon(hwnd, icon_path)
            print(f"[ICON] Final Win32 API icon setup for HWND {hwnd}.")
    except Exception as e:
        print(f"[WARN] Failed to apply final Win32 icon setup: {e}")
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
            # 保存引用到窗口和全局缓存，避免被 GC 回收
            w._tray_icon = tray
            w._tray_menu = menu
            _ICON_CACHE['tray_icon'] = tray
            _ICON_CACHE['tray_menu'] = menu
            _ICON_CACHE['tray_actions'] = [act_show, act_quit]
            print("[ICON] System tray icon created successfully.")
    except Exception as e:
        print(f"[WARN] Failed to create system tray icon: {e}")

    sys.exit(app.exec())
