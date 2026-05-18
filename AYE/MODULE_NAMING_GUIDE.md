# 模块命名与加载指南

## 概述

`main.pyw` 现在实现了 **自动模块发现与加载** 系统。您可以随意命名和修改模块文件，只要遵循命名规则，程序就能自动识别并加载它们。

## 命名规则

### 文件命名格式
```
moduleX_显示名称.pyw
```

其中：
- **X** 是序号（1, 2, 3, ...）- 决定模块在导航列表中的顺序
- **显示名称** 是任意文本 - 显示在主窗口左侧导航列表中
- **.pyw** 是文件扩展名

### 示例
| 文件名 | 显示名称 | 加载顺序 |
|--------|---------|---------|
| `module1_渲染.pyw` | 渲染 | 第1个 |
| `module2_预览.pyw` | 预览 | 第2个 |
| `module3_ffmpeg.pyw` | ffmpeg | 第3个 |
| `module4_切分.pyw` | 切分 | 第4个 |
| `module5_命名.pyw` | 命名 | 第5个 |

## 模块类要求

每个模块文件必须包含 **至少一个继承自 `QWidget` 的主类**。

### 自动选择逻辑
系统会自动：
1. **排除** 通用辅助类：`CollapsibleBox`, `FrameVizWidget`, `PlaybackControlBar`, `ScanWorker`, `Worker` 等
2. **优先选择** 名字中包含 `Widget` 的类（如 `C4DMonitorWidget`, `SequencePreviewWidget` 等）
3. **回退** 到第一个非辅助类

### 当前模块映射

| 模块文件 | 主类名 | 显示名称 |
|---------|--------|---------|
| `module1_渲染.pyw` | `C4DMonitorWidget` | 渲染 |
| `module2_预览.pyw` | `SequencePreviewWidget` | 预览 |
| `module3_ffmpeg.pyw` | `SequenceViewerWidget` | ffmpeg |
| `module4_切分.pyw` | `SequenceViewerWidget` | 切分 |
| `module5_命名.pyw` | `ReplaceWidget` | 命名 |

## 修改模块名称

### 场景：修改显示名称
只需修改文件名中 `_` 后面的部分：

```bash
# 将 module3_ffmpeg.pyw 改为 module3_视频转换.pyw
# 导航列表中自动显示为 "视频转换"
```

### 场景：调整模块顺序
只需修改序号：

```bash
# 将 module3_ffmpeg.pyw 改为 module5_ffmpeg.pyw
# 该模块会移到第5个位置
```

### 场景：完全重命名
例如重命名整个系统：

```bash
module1_主要.pyw
module2_工具1.pyw
module3_工具2.pyw
module4_工具3.pyw
module5_工具4.pyw
```

**无需修改 `main.pyw`，一切自动适配！**

## 内部工作原理

### `discover_modules()` 函数
- 扫描同目录下所有 `moduleX_*.pyw` 文件
- 按序号 X 从小到大排序
- 返回 `[(序号, 模块名, 显示名, 文件路径), ...]`

### `load_module_widget()` 函数
- 动态导入模块
- 自动识别主类（排除通用辅助类）
- 返回可用的主类

### 页面管理
- **前3个模块**（module1-3）：使用 UI 中预定义的页面 `page_1`, `page_2`, `page_3`
- **后续模块**（module4+）：动态创建新页面

## 故障排除

### 问题：模块没有被加载
**检查清单：**
1. ✓ 文件名是否遵循 `moduleX_名称.pyw` 格式？
2. ✓ 是否在同一目录（`QT/AYE/`）？
3. ✓ 模块中是否有继承自 `QWidget` 的类？
4. ✓ 查看控制台输出的加载日志

### 问题：加载了错误的类
**解决方案：**
- 将主类改名为 `*Widget` 格式（如 `MyFeatureWidget`）
- 或检查是否有通用辅助类名称冲突

### 问题：序号乱序
**确保：**
- 文件名中的序号格式正确：`module1_`, `module2_`, 等等（不能是 `moduleA_` 或 `module10a_`）

## 最佳实践

✅ **推荐做法：**
- 主类名使用 `*Widget` 后缀
- 显示名称简洁明了（中英文都可以）
- 保持序号连续（1, 2, 3, 4, 5...）
- 在模块文件开头写明功能说明

❌ **避免做法：**
- 在一个模块中放置多个名字相似的主类（可能选错）
- 使用过长或包含特殊字符的显示名称
- 跳跃序号（如 module1, module3, module5）

## 添加新模块

### 步骤
1. 创建新文件 `moduleX_显示名.pyw`（X 是下一个序号）
2. 实现 `class YourFeatureWidget(QWidget):`
3. 在 `__init__` 中调用 `self.setup_ui()` 设置界面
4. 重启应用 - 新模块会自动加载！

### 最小示例
```python
# module6_新功能.pyw
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QApplication
import sys

class NewFeatureWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        label = QLabel("这是新模块！")
        layout.addWidget(label)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = NewFeatureWidget()
    widget.show()
    sys.exit(app.exec())
```

---

**祝您使用愉快！** 🎉
