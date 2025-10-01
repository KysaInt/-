# This Python file uses the following encoding: utf-8
import sys
import os
import subprocess
import ctypes  # For setting Windows AppUserModelID so taskbar/icon works properly

def check_and_regenerate_ui():
    """
    Checks if the UI file needs to be regenerated from the .ui file and does so.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ui_file = os.path.join(script_dir, "form.ui")
    py_file = os.path.join(script_dir, "ui_form.py")

    # Regenerate if the .py file doesn't exist or the .ui file is newer
    if not os.path.exists(py_file) or os.path.getmtime(ui_file) > os.path.getmtime(py_file):
        print(f"Regenerating {py_file} from {ui_file}...")
        try:
            subprocess.run(["pyside6-uic", ui_file, "-o", py_file], check=True)
            print("UI file regenerated successfully.")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"Error regenerating UI file: {e}")
            print("Please ensure 'pyside6-uic' is in your system's PATH.")
            sys.exit(1) # Exit if UI generation fails

# Run the check before importing the UI module
check_and_regenerate_ui()

from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtGui import QIcon

# Important:
# You need to run the following command to generate the ui_form.py file
#     pyside6-uic form.ui -o ui_form.py, or
#     pyside2-uic form.ui -o ui_form.py
from ui_form import Ui_Widget
"""
更新说明:
1. 现在主程序改为导入已加序号的模块文件 (module1_*, module2_* 等)。
2. 如需再次使用未加序号旧文件名, 只需把下方 import 改回去即可。
"""
from module1_c4d_monitor import C4DMonitorWidget  # 渲染监控（原 mf_pyside6 / c4d monitor）
from module2_sequence_viewer import SequenceViewerWidget  # 序列查看器
from module3_rename_tool import ReplaceWidget  # 批量替换工具
from module4_sequence_splitter import SequenceSplitWidget  # 序列切分

class Widget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_Widget()
        self.ui.setupUi(self)
        self.setWindowTitle(" ")

        # --- Module 1: C4D Monitor ---
        self.c4d_monitor = C4DMonitorWidget(self)
        page_layout = self.ui.page_1.layout()
        while page_layout.count():
            item = page_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        page_layout.addWidget(self.c4d_monitor)
        self.ui.navigationList.item(0).setText("渲染")

        # --- Module 2: Sequence Viewer ---
        self.sequence_viewer = SequenceViewerWidget(self)
        page_2_layout = self.ui.page_2.layout()
        while page_2_layout.count():
            item = page_2_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        page_2_layout.addWidget(self.sequence_viewer)
        self.ui.navigationList.item(1).setText("序列")

        # --- Module 3: Replace Tool ---
        self.rename_tool = ReplaceWidget(self)
        page_3_layout = self.ui.page_3.layout()
        while page_3_layout.count():
            item = page_3_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        page_3_layout.addWidget(self.rename_tool)
        self.ui.navigationList.item(2).setText("替换")
        # --- Module 4: Sequence Splitter ---
        # 动态添加一个新的页面与导航项，避免修改 .ui 源文件
        from PySide6.QtWidgets import QListWidgetItem, QWidget as _QW, QVBoxLayout as _QVL
        self.sequence_splitter = SequenceSplitWidget(self)
        page_4 = _QW()
        page_4.setObjectName("page_4")
        page_4_layout = _QVL(page_4)
        page_4_layout.setContentsMargins(0,0,0,0)
        page_4_layout.addWidget(self.sequence_splitter)
        self.ui.stackedWidget.addWidget(page_4)
        QListWidgetItem(self.ui.navigationList)  # 新增列表项
        self.ui.navigationList.item(3).setText("切分")


if __name__ == "__main__":
    # --- Windows 任务栏图标支持：设置 AppUserModelID（必须在窗口创建前执行）---
    if sys.platform.startswith('win'):
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AYE.App.1.0")
        except Exception:
            # 静默失败即可（在部分旧系统或受限环境可能失败）
            pass

    app = QApplication(sys.argv)

    # 设置应用程序图标（作为全局默认）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(script_dir, "icon.ico")
    app_icon = None
    if os.path.exists(icon_path):
        app_icon = QIcon(icon_path)
        app.setWindowIcon(app_icon)

    widget = Widget()
    # 再对主窗口显式设置一次，确保任务栏/Alt+Tab 使用
    if app_icon is not None:
        widget.setWindowIcon(app_icon)
    widget.show()
    sys.exit(app.exec())
