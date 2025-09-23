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

class Widget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_Widget()
        self.ui.setupUi(self)

        # Create an instance of the monitor widget
        self.c4d_monitor = C4DMonitorWidget(self)

        # Clear the placeholder layout from the target page (e.g., page_1)
        # and add the monitor widget.
        # First, get the layout of page_1
        page_layout = self.ui.page_1.layout()
        # Remove any existing widgets from the layout
        while page_layout.count():
            item = page_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        
        # Add the new monitor widget to the layout
        page_layout.addWidget(self.c4d_monitor)

        # Optionally, change the navigation list text
        self.ui.navigationList.item(0).setText("C4D 监控")

        # --- Module 2: Sequence Viewer ---
        # Create an instance of the sequence viewer widget
        self.sequence_viewer = SequenceViewerWidget(self)

        # Get the layout of page_2 and clear it
        page_2_layout = self.ui.page_2.layout()
        while page_2_layout.count():
            item = page_2_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        
        # Add the new sequence viewer widget to the layout
        page_2_layout.addWidget(self.sequence_viewer)

        # Change the navigation list text for the second item
        self.ui.navigationList.item(1).setText("序列查看器")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = Widget()
    widget.show()
    sys.exit(app.exec())
