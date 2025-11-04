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
        
        # ===== 调整左侧导航栏和右侧内容区域的宽度比例 =====
        from PySide6.QtWidgets import QSizePolicy
        # 设置左侧导航栏为固定的紧凑宽度
        self.ui.navigationList.setMaximumWidth(60)
        self.ui.navigationList.setMinimumWidth(60)
        self.ui.navigationList.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        
        # 设置右侧内容区域可以自由伸缩
        self.ui.stackedWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # 调整水平布局的拉伸因子，使右侧占据更多空间
        self.ui.horizontalLayout.setStretch(0, 0)  # 左侧导航栏不拉伸
        self.ui.horizontalLayout.setStretch(1, 1)  # 右侧内容区域拉伸
        
        # 导入动态依赖
        from PySide6.QtWidgets import QListWidgetItem, QWidget as _QW, QVBoxLayout as _QVL
        from PySide6.QtCore import QTimer
        
        # ===== 模块预加载系统 =====
        self.module_widgets = {}  # 存储已加载的模块 widget
        self.module_pages = {}    # 存储已创建的页面
        
        # 自动发现并加载所有 moduleX_*.pyw 模块
        modules = discover_modules()
        self.all_modules = modules  # 保存所有模块信息
        
        print(f"Discovered {len(modules)} modules: {modules}")
        
        # 初始创建导航列表项和页面占位符
        for module_num, module_name, display_name, module_file in modules:
            if module_num <= 3:
                # 前三个模块使用 UI 中预定义的页面，只更新导航
                nav_item = self.ui.navigationList.item(module_num - 1)
                if nav_item:
                    nav_item.setText(display_name)
            else:
                # 后续模块动态创建占位页面
                page = _QW()
                page.setObjectName(f"page_{module_num}")
                self.ui.stackedWidget.addWidget(page)
                self.module_pages[module_num] = page
                
                # 添加导航列表项
                QListWidgetItem(self.ui.navigationList)
                nav_item = self.ui.navigationList.item(module_num - 1)
                if nav_item:
                    nav_item.setText(display_name)
        
        # 连接导航列表的点击事件
        self.ui.navigationList.itemClicked.connect(self._on_navigation_clicked)
        
        # ===== 关键改进：在后台线程预加载所有模块 =====
        # 使用 QTimer 在后台逐个加载模块，不阻塞 UI
        self._modules_to_load = list(modules)
        self._load_index = 0
        
        print("Starting background module preloading...")
        # 所有模块都用 QTimer 异步加载，避免阻塞 UI
        if modules:
            # 第一个模块延迟 100ms 加载（给 UI 时间渲染）
            QTimer.singleShot(100, self._preload_next_module)
    
    def _preload_next_module(self):
        """在后台逐个预加载模块"""
        from PySide6.QtCore import QTimer
        
        if self._load_index >= len(self._modules_to_load):
            print("✓ All modules preloaded!")
            return
        
        module_num, module_name, display_name, module_file = self._modules_to_load[self._load_index]
        module_index = self._load_index
        
        print(f"⏳ Preloading module {module_num}: {module_name}...")
        try:
            self._load_module_blocking(module_num, module_name, display_name, module_index)
            print(f"  ✓ Module {module_num} preloaded")
        except Exception as e:
            print(f"  ✗ Failed to preload module {module_num}: {e}")
        
        self._load_index += 1
        
        # 继续加载下一个模块（FFmpeg 模块给更多时间）
        if self._load_index < len(self._modules_to_load):
            # 如果是第三个模块（FFmpeg），延迟更久，让其他操作完成
            delay = 300 if self._modules_to_load[self._load_index][0] == 3 else 150
            QTimer.singleShot(delay, self._preload_next_module)
    
    def _load_module_blocking(self, module_num, module_name, display_name, module_index):
        """直接加载模块（同步）"""
        from PySide6.QtWidgets import QListWidgetItem, QWidget as _QW, QVBoxLayout as _QVL
        
        # 动态导入模块
        widget_class = load_module_widget(module_name)
        
        if widget_class is None:
            print(f"  ⚠️  Warning: Could not find widget class in module {module_name}")
            return
        
        # 创建 widget 实例
        widget_instance = widget_class(self)
        self.module_widgets[module_num] = widget_instance
        
        # 根据模块号决定是否需要替换或新建页面
        if module_num <= 3:
            # 前三个模块使用 UI 中预定义的页面
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
                self.module_pages[module_num] = page
        else:
            # 第四个及以后的模块替换占位页面中的内容
            if module_num in self.module_pages:
                page = self.module_pages[module_num]
                # 清空页面中的所有控件
                while page.layout() and page.layout().count():
                    item = page.layout().takeAt(0)
                    w = item.widget()
                    if w is not None:
                        w.deleteLater()
                # 如果页面没有布局，创建一个
                if not page.layout():
                    page_layout = _QVL(page)
                    page_layout.setContentsMargins(0, 0, 0, 0)
                else:
                    page_layout = page.layout()
                page_layout.addWidget(widget_instance)
    
    def _on_navigation_clicked(self, item):
        """导航项被点击时的回调 - 现在只需要切换，不需要加载"""
        index = self.ui.navigationList.row(item)
        
        # 直接切换（因为所有模块都已预加载）
        self.ui.stackedWidget.setCurrentIndex(index)
        print(f"✓ Switched to module {index + 1} (instant)")


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
    
    # ===== 设置主窗口最小宽度为当前宽度的 1/3 =====
    # 当前 UI 宽度为 700，所以最小宽度约为 233
    widget.setMinimumWidth(235)
    widget.setMinimumHeight(300)
    
    widget.show()
    sys.exit(app.exec())
