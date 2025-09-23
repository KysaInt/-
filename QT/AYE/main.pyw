# This Python file uses the following encoding: utf-8
import sys

from PySide6.QtWidgets import QApplication, QWidget

# Important:
# You need to run the following command to generate the ui_form.py file
#     pyside6-uic form.ui -o ui_form.py, or
#     pyside2-uic form.ui -o ui_form.py
from ui_form import Ui_Widget
from mf_pyside6 import C4DMonitorWidget # Import the refactored widget
from sequence_viewer import SequenceViewerWidget # 导入序列查看器小部件
from rename_tool import RenameWidget # 导入新的重命名模块

class Widget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_Widget()
        self.ui.setupUi(self)

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

        # --- Module 3: Rename Tool ---
        self.rename_tool = RenameWidget(self)
        page_3_layout = self.ui.page_3.layout()
        while page_3_layout.count():
            item = page_3_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        page_3_layout.addWidget(self.rename_tool)
        self.ui.navigationList.item(2).setText("重命名")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = Widget()
    widget.show()
    sys.exit(app.exec())
