# This Python file uses the following encoding: utf-8
import sys
import os
import subprocess

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
from mf_pyside6 import C4DMonitorWidget # Import the refactored widget
from sequence_viewer import SequenceViewerWidget # 导入序列查看器小部件
from rename_tool import ReplaceWidget # 导入新的重命名模块

class Widget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_Widget()
        self.ui.setupUi(self)
        self.setWindowTitle("AYE🔧")

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


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 设置应用程序图标
    script_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(script_dir, "icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    widget = Widget()
    widget.show()
    sys.exit(app.exec())
