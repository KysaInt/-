# This Python file uses the following encoding: utf-8
import sys
import os
import subprocess
import ctypes  # For setting Windows AppUserModelID so taskbar/icon works properly
import re
import importlib
from pathlib import Path

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

def discover_modules():
    """
    自动发现同目录下的 moduleX_*.pyw 文件，并返回按序号排序的模块信息列表。
    返回格式: [(module_num, module_name, display_name, module_file), ...]
    其中 display_name 是文件名中 '_' 后面的部分（不含扩展名）
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    modules = []
    
    # 查找所有 moduleX_*.pyw 文件
    pattern = re.compile(r'module(\d+)_(.+)\.(pyw|py)$')
    
    for file in Path(script_dir).glob('module*_*.py*'):
        match = pattern.match(file.name)
        if match:
            module_num = int(match.group(1))
            display_name = match.group(2)
            module_name = file.stem  # 不含扩展名的文件名
            modules.append((module_num, module_name, display_name, str(file)))
    
    # 按序号排序
    modules.sort(key=lambda x: x[0])
    return modules

def load_module_widget(module_name):
    """
    动态导入模块并获取主窗口类。
    优先选择最具体的类（排除通用辅助类如 CollapsibleBox, FrameVizWidget, PlaybackControlBar 等）
    """
    try:
        module = importlib.import_module(module_name)
        
        # 通用辅助类的名称模式（通常不是主窗口）
        generic_class_patterns = [
            'CollapsibleBox', 'FrameVizWidget', 'PlaybackControlBar', 
            'ScanWorker', 'Worker', 'ResizableHandle', 'ResizableCollapsibleBox',
            'ElidedLabel', 'FpsInputDialog', 'SequenceCard'
        ]
        
        main_widget_candidates = []
        
        # 收集所有继承自 QWidget 的类
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, QWidget) and attr != QWidget:
                # 排除通用辅助类
                if attr_name not in generic_class_patterns:
                    main_widget_candidates.append((attr_name, attr))
        
        # 优先选择名字中包含 'Widget' 的类（最可能是主窗口）
        for class_name, class_obj in main_widget_candidates:
            if 'Widget' in class_name:
                return class_obj
        
        # 如果没有找到，返回第一个候选类
        if main_widget_candidates:
            return main_widget_candidates[0][1]
        
        # 如果仍没有找到，返回 None
        return None
    except Exception as e:
        print(f"Failed to load module {module_name}: {e}")
        import traceback
        traceback.print_exc()
        return None

class Widget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_Widget()
        self.ui.setupUi(self)
        self.setWindowTitle(" ")
        
        # 导入动态依赖
        from PySide6.QtWidgets import QListWidgetItem, QWidget as _QW, QVBoxLayout as _QVL
        
        # 自动发现并加载所有 moduleX_*.pyw 模块
        modules = discover_modules()
        self.module_widgets = {}  # 存储已加载的模块 widget
        
        print(f"Discovered {len(modules)} modules: {modules}")
        
        for module_num, module_name, display_name, module_file in modules:
            print(f"Loading module {module_num}: {module_name} (display as '{display_name}')")
            
            try:
                # 动态导入模块
                widget_class = load_module_widget(module_name)
                
                if widget_class is None:
                    print(f"  ⚠️  Warning: Could not find widget class in module {module_name}")
                    continue
                
                # 创建 widget 实例
                widget_instance = widget_class(self)
                self.module_widgets[module_num] = widget_instance
                
                # 根据是否是第一个模块来决定是否需要替换或新建页面
                if module_num <= 3:
                    # 前三个模块使用 UI 中预定义的页面 (page_1, page_2, page_3)
                    page_attr = f"page_{module_num}"
                    if hasattr(self.ui, page_attr):
                        page = getattr(self.ui, page_attr)
                        page_layout = page.layout()
                        while page_layout.count():
                            item = page_layout.takeAt(0)
                            w = item.widget()
                            if w is not None:
                                w.deleteLater()
                        page_layout.addWidget(widget_instance)
                        
                        # 更新导航列表项
                        nav_item = self.ui.navigationList.item(module_num - 1)
                        if nav_item:
                            nav_item.setText(display_name)
                else:
                    # 第四个及以后的模块动态创建页面
                    page = _QW()
                    page.setObjectName(f"page_{module_num}")
                    page_layout = _QVL(page)
                    page_layout.setContentsMargins(0, 0, 0, 0)
                    page_layout.addWidget(widget_instance)
                    self.ui.stackedWidget.addWidget(page)
                    
                    # 添加导航列表项
                    QListWidgetItem(self.ui.navigationList)
                    nav_item = self.ui.navigationList.item(module_num - 1)
                    if nav_item:
                        nav_item.setText(display_name)
                
                print(f"  ✓ Module {module_num} loaded successfully")
            
            except Exception as e:
                print(f"  ✗ Failed to load module {module_num}: {e}")
                import traceback
                traceback.print_exc()


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
