import sys
print("Python version:", sys.version)
try:
    from PySide6.QtWidgets import QApplication, QWidget
    print("PySide6 imported successfully")
    app = QApplication(sys.argv)
    print("QApplication created")
    window = QWidget()
    print("QWidget created")
    window.show()
    print("Window shown")
    app.exec()
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()