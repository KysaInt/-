# This Python file uses the following encoding: utf-8
import sys
import os
import subprocess
import ctypes  # For setting Windows AppUserModelID so taskbar/icon works properly
import re
import importlib
from pathlib import Path
import json

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

def _read_modules_config(script_dir: str):
    """读取可选的 modules.json（若存在）定义模块顺序与显示名。
    格式示例：
    {
      "modules": [
        {"name": "module1_渲染", "title": "渲染"},
        {"name": "module2_预览"}
      ]
    }
    """
    cfg_path = os.path.join(script_dir, "modules.json")
    if not os.path.exists(cfg_path):
        return None
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Failed to read modules.json: {e}")
        return None

def discover_plugins():
    """
    发现同目录下可作为插件的模块文件，并根据 modules.json 或约定进行排序。
    返回列表，每项为 dict：
      {
        'name': 模块导入名（文件名不含扩展名）, 
        'title': 显示名称,
        'file': 绝对路径,
        'order': 用于排序的整数或 None
      }
    说明：
      - 首先尝试读取 modules.json 按指定顺序加载；
      - 若无配置，则按文件名自动发现并尽量从 "moduleX_*" 中提取序号排序；
      - 显示名优先取 MODULE_META.title 或文件名中的中文部分。
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config = _read_modules_config(script_dir)

    # 扫描所有候选 py/pyw 文件（排除以下划线开头的临时/库）
    all_files = [p for p in Path(script_dir).glob("*.py*") if not p.name.startswith("_")]

    # 建立索引：module_name -> path
    name_to_path = {p.stem: str(p) for p in all_files}

    plugins = []

    def make_entry(name: str, path: str):
        # 从文件名提取候选顺序与标题
        m = re.match(r"module(\d+)_([^\\/.]+)", name)
        order = int(m.group(1)) if m else None
        display = m.group(2) if (m and len(m.groups()) >= 2) else name
        return {"name": name, "title": display, "file": path, "order": order}

    if config and isinstance(config, dict) and isinstance(config.get("modules"), list):
        # 先按配置中的顺序加入
        for item in config["modules"]:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not name:
                continue
            path = name_to_path.get(name)
            if not path:
                print(f"Warning: module '{name}' listed in modules.json not found on disk")
                continue
            entry = make_entry(name, path)
            # 配置中可覆盖标题或顺序
            if "title" in item:
                entry["title"] = item["title"]
            if "order" in item:
                entry["order"] = item["order"]
            plugins.append(entry)

        # 再把未在配置中的其余模块追加到末尾
        configured = {p["name"] for p in plugins}
        for name, path in name_to_path.items():
            if name not in configured and name not in {"main", "ui_form", "form_ui", "form", "mf_pyside6"}:
                plugins.append(make_entry(name, path))
    else:
        # 无配置：仅自动发现以 module*_*.py* 命名或包含 QWidget 的模块
        for p in all_files:
            name = p.stem
            if name in {"main", "ui_form", "form_ui", "form", "mf_pyside6"}:
                continue
            # 以 moduleX_* 优先
            if re.match(r"module\d+_", name):
                plugins.append(make_entry(name, str(p)))
        # 若没有任何符合 moduleX_* 的，也允许全部按字母加入以保证可用
        if not plugins:
            for p in all_files:
                name = p.stem
                if name in {"main", "ui_form", "form_ui", "form", "mf_pyside6"}:
                    continue
                plugins.append(make_entry(name, str(p)))

    # 排序：优先使用 order，其次按标题/名称
    plugins.sort(key=lambda e: (e["order"] is None, e["order"] if e["order"] is not None else 0, e["title"]))
    return plugins

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
        
        # ===== 插件化：完全解除与“fixed 5 模块/固定顺序”的耦合 =====
        # 清空 UI 原本在 .ui 里放置的占位页与导航项
        try:
            self.ui.navigationList.clear()
        except Exception:
            pass
        try:
            while self.ui.stackedWidget.count() > 0:
                w = self.ui.stackedWidget.widget(0)
                self.ui.stackedWidget.removeWidget(w)
                w.deleteLater()
        except Exception:
            pass

        # ===== 模块预加载系统（插件） =====
        self.module_widgets = {}   # key: index -> widget instance
        self.module_pages = {}     # key: index -> page QWidget
        self.plugins = discover_plugins()  # [{'name','title','file','order'}]

        print(f"Discovered {len(self.plugins)} plugin modules:")
        for i, p in enumerate(self.plugins, 1):
            print(f"  {i}. {p['name']} (title={p['title']}, order={p['order']})")

        # 为每个插件创建导航和页面占位
        for idx, plugin in enumerate(self.plugins):
            # 导航项
            QListWidgetItem(plugin["title"], self.ui.navigationList)
            # 页面占位
            page = _QW()
            page.setObjectName(f"page_{idx}")
            self.ui.stackedWidget.addWidget(page)
            self.module_pages[idx] = page

        # 连接导航列表的点击事件
        self.ui.navigationList.itemClicked.connect(self._on_navigation_clicked)

        # 默认选中并显示第一个插件（若存在）
        if self.plugins:
            self.ui.navigationList.setCurrentRow(0)
            self.ui.stackedWidget.setCurrentIndex(0)

        # 使用 QTimer 在后台逐个加载模块，不阻塞 UI
        self._load_index = 0
        print("Starting background plugin preloading...")
        if self.plugins:
            QTimer.singleShot(100, self._preload_next_module)
    
    def _preload_next_module(self):
        """在后台逐个预加载模块"""
        from PySide6.QtCore import QTimer
        
        if self._load_index >= len(self.plugins):
            print("✓ All modules preloaded!")
            return
        
        plugin = self.plugins[self._load_index]
        module_name = plugin["name"]
        display_name = plugin["title"]
        module_index = self._load_index
        
        print(f"⏳ Preloading module {module_index+1}: {module_name}...")
        try:
            self._load_module_blocking(module_index, module_name, display_name)
            print(f"  ✓ Module {module_index+1} preloaded")
        except Exception as e:
            print(f"  ✗ Failed to preload module {module_index+1}: {e}")
        
        self._load_index += 1
        
        # 继续加载下一个模块（FFmpeg 模块给更多时间）
        if self._load_index < len(self.plugins):
            # 简单启发：名字含 ffmpeg 的插件稍微延迟
            next_name = self.plugins[self._load_index]["name"].lower()
            delay = 300 if ("ffmpeg" in next_name or "video" in next_name) else 150
            QTimer.singleShot(delay, self._preload_next_module)
    
    def _load_module_blocking(self, module_index, module_name, display_name):
        """直接加载模块（同步）"""
        from PySide6.QtWidgets import QListWidgetItem, QWidget as _QW, QVBoxLayout as _QVL
        
        # 动态导入模块并优先使用模块工厂函数 create_widget(parent)
        try:
            module = importlib.import_module(module_name)
        except Exception as e:
            print(f"  ✗ Import failed for {module_name}: {e}")
            return

        if hasattr(module, "create_widget") and callable(getattr(module, "create_widget")):
            try:
                widget_instance = module.create_widget(self)
            except Exception as e:
                print(f"  ✗ create_widget() failed in {module_name}: {e}")
                return
        else:
            widget_class = load_module_widget(module_name)
            if widget_class is None:
                print(f"  ⚠️  Warning: Could not find widget class in module {module_name}")
                return
            widget_instance = widget_class(self)

        self.module_widgets[module_index] = widget_instance

        # 使用统一的动态页面逻辑：无论第几个都相同处理
        if module_index in self.module_pages:
            page = self.module_pages[module_index]
            # 清空页面中的所有控件
            if page.layout():
                while page.layout().count():
                    item = page.layout().takeAt(0)
                    w = item.widget()
                    if w is not None:
                        w.deleteLater()
                page_layout = page.layout()
            else:
                page_layout = _QVL(page)
                page_layout.setContentsMargins(0, 0, 0, 0)
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

    # ===== 根据当前屏幕可用高度的百分比设置默认高度 =====
    # 例如占用 80% 的可用高度，可自行调整 ratio
    from PySide6.QtGui import QGuiApplication

    screen = QGuiApplication.primaryScreen()
    if screen is not None:
        available_geometry = screen.availableGeometry()
        screen_height = available_geometry.height()
        ratio = 0.8  # 使用 80% 的屏幕可用高度
        target_height = int(screen_height * ratio)
        # 保证不小于最小高度
        target_height = max(target_height, widget.minimumHeight())
        widget.resize(widget.width() or 700, target_height)
    
    widget.show()
    sys.exit(app.exec())
