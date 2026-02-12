# TTS 工具集 UI 视觉风格设计指南

## 📋 目录
- [整体架构](#整体架构)
- [布局设计](#布局设计)
- [字体系统](#字体系统)
- [色彩与样式](#色彩与样式)
- [控件规范](#控件规范)
- [窗口行为](#窗口行为)
- [图标系统](#图标系统)
- [交互模式](#交互模式)
- [代码实现模式](#代码实现模式)

---

## 整体架构

### 主框架结构
程序采用**左侧导航栏 + 右侧内容区**的经典双栏布局模式，使用 PySide6 (Qt) 框架构建。

```
┌─────────────────────────────────────┐
│  [导航栏]  │  [内容展示区域]        │
│   80px     │      可变宽度           │
│            │                         │
│  ► 模块一  │  ╔═══════════════════╗ │
│  ► 模块二  │  ║   当前模块内容    ║ │
│  ► 模块三  │  ║                   ║ │
│            │  ║                   ║ │
│            │  ╚═══════════════════╝ │
└─────────────────────────────────────┘
```

### 技术实现
- **主容器**: `QWidget` + `QHBoxLayout` 水平布局
- **左侧导航**: `QListWidget`（固定宽度 80px）
- **右侧内容**: `QStackedWidget`（页面切换容器）
- **信号连接**: `navigationList.currentRowChanged(int)` → `stackedWidget.setCurrentIndex(int)`

---

## 布局设计

### 1. 主窗口布局
```xml
<layout class="QHBoxLayout" name="horizontalLayout">
    <item>导航列表 (QListWidget)</item>
    <item>堆叠窗口 (QStackedWidget)</item>
</layout>
```

### 2. 导航列表规格
- **宽度**: 固定 80px
- **高度**: 自适应（maximumSize: width=80, height=16777215）
- **字体**: 微软雅黑 9pt
- **项目文本**: 简短标签（2-4 个汉字，如"情绪TTS"、"字幕匹配"）

### 3. 内容页面布局
每个 `QStackedWidget` 的子页面（page_1, page_2, page_3...）都使用 `QVBoxLayout` 垂直布局：

```python
# 页面结构
page_1 = QWidget()
layout = QVBoxLayout(page_1)
# 动态添加子模块组件
layout.addWidget(module_widget)
```

### 4. 表单布局模式

#### A. 表单参数区（QGridLayout）
用于左对齐的标签-输入对控件：
```python
form_layout = QGridLayout()
form_layout.addWidget(QLabel("参数名:"), row, 0)    # 左列：标签
form_layout.addWidget(input_widget, row, 1)         # 右列：输入控件
```

**典型用途**:
- 文件路径选择（标签 + QLineEdit + QPushButton）
- 数值参数（标签 + QSpinBox / QDoubleSpinBox）
- 下拉选项（标签 + QComboBox）

#### B. 横向参数组（QHBoxLayout）
将多个相关参数水平排列：
```python
row_layout = QHBoxLayout()
row_layout.addWidget(QLabel("语速:"))
row_layout.addWidget(rate_input)       # QLineEdit
row_layout.addWidget(QLabel("%"))      # 单位后缀
row_layout.addStretch()                # 弹性空间
```

**典型模式**:
```
[标签] [输入] [单位] | [标签] [输入] [单位] | [标签] [输入]
```

#### C. 按钮操作栏（QHBoxLayout）
功能按钮水平排列：
```python
action_layout = QHBoxLayout()
action_layout.addWidget(analyze_btn)
action_layout.addWidget(match_btn)
action_layout.addWidget(export_btn)
action_layout.addStretch()
action_layout.addWidget(reset_btn)      # 右对齐
```

---

## 字体系统

### 字体优先级

#### 1. 主窗口默认字体
```python
<property name="font">
    <family>黑体</family>
    <pointsize>10</pointsize>
</property>
```
- **应用场景**: 窗口级别默认字体
- **字体**: 黑体 10pt

#### 2. 内容区标准字体
```python
<property name="font">
    <family>微软雅黑</family>
    <pointsize>9</pointsize>
</property>
```
- **应用场景**: 导航列表、内容区标签、按钮、输入框
- **字体**: 微软雅黑 9pt
- **特性**: 清晰、易读、适合中文界面

#### 3. 强调文本
```python
label.setStyleSheet("QLabel { font-weight: bold; padding: 3px; }")
# 或
f = label.font()
f.setBold(True)
label.setFont(f)
```
- **应用场景**: 
  - 分组标题（如"SSML 扩展"）
  - 状态提示（如"已选择: 0 个模型"）
  - 折叠面板标题

#### 4. 等宽字体（日志/代码）
```python
font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
font.setPointSize(9)
log_text.setFont(font)
```
- **应用场景**: 
  - 日志输出框（QTextEdit）
  - 技术信息展示
  - 代码片段

---

## 色彩与样式

### 1. 基础样式规范

#### 状态标签样式
```python
# 加粗 + 内边距
"QLabel { font-weight: bold; padding: 3px; }"
```

#### 分组标题
```python
# HTML 加粗标签
QLabel("<b>分组标题</b>")
```

### 2. 框架样式

#### QFrame 内容容器
```python
content_area = QFrame()
content_area.setFrameShape(QFrame.StyledPanel)
```
- **用途**: 可折叠区域的内容包裹
- **样式**: 带边框的面板

### 3. 按钮图标
使用 Unicode Emoji 作为视觉辅助：
```
🔍 - 分析/搜索
📂 - 打开文件夹
💾 - 保存/导出
🔄 - 重置/刷新
🔗 - 连接/匹配
📋 - 日志/列表
```

**按钮文本格式**: `[Emoji] 功能名称`
```python
QPushButton("🔍 分析音频")
QPushButton("💾 导出字幕")
```

---

## 控件规范

### 1. QListWidget (导航列表)
```python
navigation_list = QListWidget()
navigation_list.setMaximumSize(QSize(80, 16777215))
navigation_list.setFont(QFont("微软雅黑", 9))

# 添加项目
navigation_list.addItem("模块一")  # 2-4 字简短标签
```

### 2. QComboBox (下拉选择)
```python
combo = QComboBox()
combo.addItems(["选项一", "选项二", "选项三"])
combo.setCurrentIndex(0)  # 默认选择
```

**应用场景**:
- 情绪选择
- 音调/音量选择
- 语音模型切换

### 3. QLineEdit (单行输入)
```python
input_field = QLineEdit()
input_field.setText("默认值")
input_field.setPlaceholderText("提示文本")
```

**典型输入类型**:
- 数字参数（语速: "0"，延时: "300"）
- 文本参数（行字数: "28"）
- 文件路径（通过 QFileDialog 辅助）

### 4. QSpinBox / QDoubleSpinBox (数值输入)
```python
spin = QSpinBox()
spin.setRange(-100, 100)
spin.setSingleStep(1)
spin.setValue(0)

double_spin = QDoubleSpinBox()
double_spin.setRange(0.0, 10.0)
double_spin.setSingleStep(0.1)
double_spin.setDecimals(2)
```

### 5. QTextEdit (多行文本/日志)
```python
log_view = QTextEdit()
log_view.setReadOnly(True)  # 日志框只读
log_view.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
```

### 6. QPushButton (按钮)
```python
button = QPushButton("🔍 开始分析")
button.setEnabled(True)  # 初始状态
button.clicked.connect(on_click_handler)
```

### 7. QLabel (标签)
```python
# 普通标签
label = QLabel("参数名:")

# 加粗标签
bold_label = QLabel("<b>分组标题</b>")

# 状态标签
status = QLabel("就绪")
status.setStyleSheet("QLabel { font-weight: bold; padding: 3px; }")

# 居中对齐
center_label = QLabel("内容")
center_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
```

### 8. QProgressBar (进度条)
```python
progress = QProgressBar()
progress.setRange(0, 100)
progress.setValue(0)
progress.setTextVisible(True)
```

### 9. QCheckBox (复选框)
```python
checkbox = QCheckBox("启用功能")
checkbox.setChecked(False)
```

---

## 窗口行为

### 1. 初始尺寸
**在 .ui 文件中定义**:
```xml
<property name="geometry">
    <rect>
        <x>0</x> <y>0</y>
        <width>700</width>
        <height>400</height>
    </rect>
</property>
```

### 2. 运行时调整
**在主程序中动态设置**:
```python
# 目标高度: 1000px（或屏幕可用高度）
screen = QGuiApplication.primaryScreen()
geo = screen.availableGeometry()

new_h = min(1000, geo.height())
new_w = max(600, min(current_width, int(geo.width() * 0.95)))

# 居中显示
x = geo.x() + (geo.width() - new_w) // 2
y = geo.y() + (geo.height() - new_h) // 2
window.setGeometry(x, y, new_w, new_h)
```

**尺寸策略**:
- 最小宽度: 600px
- 最大宽度: 屏幕宽度的 95%
- 首选高度: 1000px（不超过屏幕可用高度）
- 启动位置: 屏幕中心

### 3. 窗口标题
```python
window.setWindowTitle("TTS 工具集")
```

---

## 图标系统

### 1. 图标加载优先级
```python
icon_candidates = [
    "tts/duck.ico",                    # 优先：模块专用图标
    "QT/AYE/icon.ico",                 # 备用：通用图标
]
```

### 2. 图标规格
- **格式**: ICO（支持多分辨率）
- **尺寸**: 16×16、32×32（标准 Windows 图标）
- **应用位置**:
  - 窗口标题栏图标 (`window.setWindowIcon()`)
  - 任务栏图标（通过 Windows API 设置）
  - 系统托盘图标 (`QSystemTrayIcon`)

### 3. 高 DPI 支持
```python
# 启用高分辨率位图
QGuiApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
```

### 4. Windows 任务栏图标设置
```python
# AppUserModelID（任务栏分组）
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("aye.tts.main.v1")

# 通过 Windows API 设置窗口图标
user32 = ctypes.windll.user32
hicon_large = user32.LoadImageW(0, icon_path, IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
hicon_small = user32.LoadImageW(0, icon_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_large)
user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
```

### 5. 系统托盘
```python
tray = QSystemTrayIcon(parent_widget)
tray.setIcon(app_icon)
tray.setToolTip("AYE TTS 工具集")

# 右键菜单
menu = QMenu()
menu.addAction("显示窗口", on_show)
menu.addSeparator()
menu.addAction("退出", app.quit)
tray.setContextMenu(menu)
tray.show()
```

---

## 交互模式

### 1. 可折叠面板 (CollapsibleBox)

#### 视觉设计
```
╔═══════════════════════════════╗
║ ▼ 高级参数                    ║  ← 标题按钮（可点击）
╠═══════════════════════════════╣
║ [参数控件区域]                ║  ← 内容区（可展开/收起）
║ ...                           ║
╚═══════════════════════════════╝
```

#### 实现特性
```python
class CollapsibleBox(QWidget):
    toggled = Signal(bool)
    
    def __init__(self, title: str, expanded: bool = True):
        # 标题按钮
        self.toggle_button = QPushButton()
        self.toggle_button.setCheckable(True)
        f = self.toggle_button.font()
        f.setBold(True)
        self.toggle_button.setFont(f)
        
        # 内容区
        self.content_area = QWidget()
        self.content_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
```

**标题格式**:
- 展开: `"▼ 面板标题"`
- 收起: `"► 面板标题"`

**折叠行为**:
- 展开: `content_area.setVisible(True)`, `maxHeight = 16777215`
- 收起: `content_area.setVisible(False)`, `maxHeight = 0`

### 2. 按钮状态管理
```python
# 初始状态
analyze_btn.setEnabled(True)
match_btn.setEnabled(False)    # 依赖分析完成
export_btn.setEnabled(False)   # 依赖匹配完成

# 状态切换
def on_analysis_complete():
    match_btn.setEnabled(True)
    status_label.setText("分析完成")
```

### 3. 实时状态反馈
```python
# 状态标签
status_label = QLabel("就绪")
status_label.setStyleSheet("QLabel { font-weight: bold; padding: 3px; }")

# 信息统计
info_labels = {
    "检测到的停顿数": QLabel("0"),
    "总停顿时长": QLabel("0.0s"),
    "字幕条数": QLabel("0"),
}
```

### 4. 日志输出
```python
log_view = QTextEdit()
log_view.setReadOnly(True)
log_view.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))

def log(message: str):
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_view.append(f"[{timestamp}] {message}")
```

---

## 代码实现模式

### 1. UI 自动生成流程
```python
def check_and_regenerate_ui():
    """根据 form.ui 生成 ui_form.py"""
    if not os.path.exists(py_file) or \
       os.path.getmtime(ui_file) > os.path.getmtime(py_file):
        subprocess.run(["pyside6-uic", ui_file, "-o", py_file], check=True)

check_and_regenerate_ui()
from ui_form import Ui_Widget
```

### 2. 主窗口类结构
```python
class MainWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_Widget()
        self.ui.setupUi(self)
        self.setWindowTitle("应用标题")
        
        # 清理占位内容
        self._clear_page_layout(self.ui.page_1)
        
        # 加载子模块
        self.module1 = ModuleWidget()
        self.ui.page_1.layout().addWidget(self.module1)
        
        # 更新导航标签
        self.ui.navigationList.item(0).setText("模块名称")
```

### 3. 动态模块加载
```python
def load_class_from_file(file_path: str, module_name: str, class_name: str):
    """动态导入模块类（支持数字命名的 .pyw 文件）"""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return getattr(module, class_name)

ModuleClass = load_class_from_file("1.pyw", "module_1", "TTSApp")
```

### 4. 子模块嵌入模式
```python
# 清理现有布局
page_layout = self.ui.page_1.layout()
while page_layout.count():
    item = page_layout.takeAt(0)
    w = item.widget()
    if w:
        w.deleteLater()

# 添加新模块
module = SubModuleWidget()
page_layout.addWidget(module)
```

### 5. 应用入口配置
```python
if __name__ == "__main__":
    # Windows AppUserModelID（任务栏分组）
    if sys.platform.startswith("win"):
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "aye.tts.main.v1"
        )
    
    # 高 DPI 支持
    QGuiApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    
    # 应用元数据
    app.setOrganizationName("AYE")
    app.setOrganizationDomain("local.aye")
    app.setApplicationName("AYE TTS")
    app.setApplicationDisplayName("AYE TTS 工具集")
    
    # 全局图标
    app_icon = _load_app_icon_with_fallbacks()
    app.setWindowIcon(app_icon)
    
    # 创建主窗口
    w = MainWidget()
    w.setWindowIcon(app_icon)
    
    # 调整窗口尺寸和位置
    _adjust_window_geometry(w)
    
    # 系统托盘
    _ensure_system_tray(w, app_icon)
    
    # 显示
    w.show()
    
    sys.exit(app.exec())
```

---

## 最佳实践总结

### 1. 布局原则
- ✅ 使用 `QHBoxLayout` 实现左右分栏
- ✅ 使用 `QVBoxLayout` 实现垂直堆叠
- ✅ 使用 `QGridLayout` 实现表单对齐
- ✅ 使用 `addStretch()` 实现弹性空间
- ✅ 使用 `QSplitter` 实现可调整分栏

### 2. 样式统一
- ✅ 窗口默认字体：黑体 10pt
- ✅ 内容标准字体：微软雅黑 9pt
- ✅ 日志等宽字体：系统 FixedFont 9pt
- ✅ 按钮加 Emoji 图标：`🔍 💾 🔄 📂`

### 3. 控件规范
- ✅ 导航栏固定 80px 宽度
- ✅ 标签使用 `setStyleSheet()` 加粗
- ✅ 日志框使用 `setReadOnly(True)`
- ✅ 按钮根据状态启用/禁用

### 4. 交互设计
- ✅ 可折叠面板使用 `CollapsibleBox`
- ✅ 长时任务使用 `QThread` 异步
- ✅ 实时反馈使用状态标签
- ✅ 操作日志实时输出

### 5. 图标管理
- ✅ 多路径回退加载机制
- ✅ 支持多分辨率 ICO 文件
- ✅ Windows API 级别设置
- ✅ 防止 GC 回收（缓存句柄）

---

## 快速还原清单

需要的核心文件：

1. **form.ui** - Qt Designer 界面文件（定义主框架）
2. **TTS_Main.pyw** - 主程序入口（窗口配置、模块加载、图标设置）
3. **1.pyw, 2.pyw...** - 子模块文件（独立功能组件）
4. **duck.ico / icon.ico** - 应用图标（16×16 + 32×32）

关键代码区块：

- `check_and_regenerate_ui()` - UI 自动生成
- `_load_app_icon_with_fallbacks()` - 图标加载
- `_ensure_system_tray()` - 系统托盘
- `MainWidget.__init__()` - 主窗口初始化
- `CollapsibleBox` - 可折叠面板组件

---

## 版本信息
- **框架**: PySide6 (Qt for Python)
- **Python**: 3.9+
- **平台**: Windows（优化）、跨平台支持
- **设计语言**: 简洁实用、功能优先
- **创建者**: AYE

---

**使用说明**: 参考本文档可快速搭建具有相同视觉风格的应用框架。核心思路是：左侧固定导航 + 右侧堆叠页面 + 模块化子组件 + 统一字体系统 + Emoji 图标辅助。
