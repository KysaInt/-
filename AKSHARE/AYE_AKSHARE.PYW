
# -*- coding: utf-8 -*-
import sys
import os
import subprocess
import importlib.util
import ctypes

from typing import Optional


_ICON_CACHE = {}


def check_and_regenerate_ui():
	"""确认并根据本目录的 form.ui 生成 ui_form.py（若缺失或过期）。

	风格参考 tts/TTS_Main.pyw，但更稳健：
	- 若缺少 pyside6-uic，但已存在 ui_form.py，则继续运行；
	- 若两者都缺失，则退出。
	"""

	script_dir = os.path.dirname(os.path.abspath(__file__))
	ui_file = os.path.join(script_dir, "form.ui")
	py_file = os.path.join(script_dir, "ui_form.py")

	if not os.path.exists(ui_file):
		print("缺少 form.ui。")
		if os.path.exists(py_file):
			return
		print("同时缺少 ui_form.py，无法启动。")
		sys.exit(1)

	need_regen = (not os.path.exists(py_file)) or (os.path.getmtime(ui_file) > os.path.getmtime(py_file))
	if not need_regen:
		return

	print(f"正在从 {ui_file} 生成 {py_file} …")
	try:
		subprocess.run(["pyside6-uic", ui_file, "-o", py_file], check=True)
		print("UI 生成成功。")
	except (subprocess.CalledProcessError, FileNotFoundError) as e:
		if os.path.exists(py_file):
			print(f"生成 UI 失败，但已存在 ui_form.py，将继续运行：{e}")
			return
		print(f"生成 UI 失败: {e}")
		print("请确认已安装 PySide6，并且 pyside6-uic 可用。")
		sys.exit(1)


check_and_regenerate_ui()

from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtGui import QIcon, QGuiApplication
from PySide6.QtCore import Qt

try:
	from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QAction
except Exception:
	QSystemTrayIcon = None

from ui_form import Ui_Widget


def _load_app_icon_with_fallbacks() -> Optional[QIcon]:
	"""按优先级加载图标。优先 AKSHARE/icon.ico，回退 QT/AYE/icon.ico。"""
	script_dir = os.path.dirname(os.path.abspath(__file__))
	root_dir = os.path.dirname(script_dir)

	icon_candidates = [
		os.path.join(script_dir, "icon.ico"),
		os.path.join(root_dir, "QT", "AYE", "icon.ico"),
	]

	for p in icon_candidates:
		p = os.path.normpath(os.path.abspath(p))
		if not os.path.exists(p):
			continue
		ic = QIcon(p)
		if not ic.isNull():
			_ICON_CACHE["app_icon"] = ic
			return ic
	return None


def _ensure_system_tray(parent_widget: QWidget, icon: Optional[QIcon]):
	if QSystemTrayIcon is None or not QSystemTrayIcon.isSystemTrayAvailable():
		return
	try:
		tray = QSystemTrayIcon(parent_widget)
		if icon is None or icon.isNull():
			icon = parent_widget.windowIcon() or QApplication.instance().windowIcon()
		if icon is not None and not icon.isNull():
			tray.setIcon(icon)
		tray.setToolTip("AYE AKShare 工具集")

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
		parent_widget._tray_icon = tray
		parent_widget._tray_menu = menu
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


_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_MOD1_PATH = os.path.join(_SCRIPT_DIR, "1.pyw")

try:
	ModuleOneWidget = load_class_from_file(_MOD1_PATH, "akshare_module_1", "AKShareApp")
except Exception as e:
	print(f"导入模块一失败: {e}")
	ModuleOneWidget = None


class MainWidget(QWidget):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.ui = Ui_Widget()
		self.ui.setupUi(self)
		self.setWindowTitle("AKShare 工具集")

		self._tray_icon = None
		self._tray_menu = None

		# --- 模块一：基础 ---
		page_layout_1 = self.ui.page_1.layout()
		while page_layout_1.count():
			item = page_layout_1.takeAt(0)
			w = item.widget()
			if w is not None:
				w.deleteLater()
		if ModuleOneWidget is not None:
			self.module1 = ModuleOneWidget()
			page_layout_1.addWidget(self.module1)

		# 重命名导航
		try:
			self.ui.navigationList.item(0).setText("AKShare")
		except Exception:
			pass
		# 隐藏其余模块占位
		try:
			if self.ui.navigationList.count() >= 2:
				self.ui.navigationList.item(1).setText("")
			if self.ui.navigationList.count() >= 3:
				self.ui.navigationList.item(2).setText("")
		except Exception:
			pass


if __name__ == "__main__":
	if sys.platform.startswith("win"):
		try:
			ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AYE.AKSHARE.App.1.0")
		except Exception:
			pass

	try:
		QGuiApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
	except Exception:
		pass

	app = QApplication(sys.argv)
	app.setOrganizationName("AYE")
	app.setOrganizationDomain("local.aye")
	app.setApplicationName("AYE AKShare")
	app.setApplicationDisplayName("AYE AKShare 工具集")

	app_icon = _load_app_icon_with_fallbacks()
	if app_icon is not None and not app_icon.isNull():
		app.setWindowIcon(app_icon)

	w = MainWidget()
	if app_icon is not None:
		w.setWindowIcon(app_icon)

	# 默认启动高度：1000px（不超过屏幕可用高度），并居中
	try:
		screen = QGuiApplication.primaryScreen()
		geo = screen.availableGeometry() if screen is not None else None
		if geo is not None:
			cur = w.geometry()
			new_h = min(1000, geo.height())
			new_w = max(600, min(cur.width(), int(geo.width() * 0.95)))
			x = geo.x() + max(0, int((geo.width() - new_w) / 2))
			y = geo.y() + max(0, int((geo.height() - new_h) / 2))
			w.setGeometry(x, y, new_w, new_h)
	except Exception:
		pass

	_ensure_system_tray(w, app_icon)
	w.show()
	sys.exit(app.exec())

