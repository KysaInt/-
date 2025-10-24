# TTS 工具集 - 任务栏图标修复完整指南

## 📋 概述

本目录包含已升级的 **TTS 应用程序**，具备完整的任务栏图标显示优化。

### ✨ 新特性
- ✅ **清晰的彩色应用图标** - 蓝紫色专业设计
- ✅ **三层保险图标设置** - 确保任务栏显示正常
- ✅ **完整的缓存机制** - 防止图标丢失
- ✅ **系统托盘支持** - 任务栏通知区域图标
- ✅ **多格式图标** - PNG、ICO 双格式支持

---

## 🚀 快速开始

### 方式 1: 使用启动脚本（推荐）

**Windows (Batch)**
```bash
run_tts.bat
```

**PowerShell**
```powershell
.\run_tts.ps1
```

### 方式 2: 直接运行

```bash
python AYE_TTS_Main.pyw
```

---

## 📦 文件清单

### 核心程序
- `AYE_TTS_Main.pyw` - 主程序（已优化图标处理）✅
- `1.pyw` - TTS 模块一
- `2.pyw` - 字幕匹配模块
- `form.ui` - UI 设计文件
- `ui_form.py` - 生成的 UI 代码

### 应用图标 ⭐
```
icon.ico          ← 主应用图标（任务栏用）✅ 新生成
icon.png          ← PNG 格式图标 ✅ 新生成
icon_tb.ico       ← 任务栏专用图标 ✅ 新生成
```

### 工具脚本
- `generate_icon.py` - 图标生成脚本
- `test_icon.pyw` - 图标显示测试程序
- `check_icon_config.py` - 配置检查工具
- `run_tts.bat` - Windows 启动脚本
- `run_tts.ps1` - PowerShell 启动脚本

### 文档
- `ICON_SETUP_NOTES.md` - 技术细节文档
- `CHANGELOG_ICON_FIX.md` - 详细更新日志
- `README.md` - 本文件

---

## 🔧 工具使用

### 1. 测试图标显示

启动图标测试窗口：
```bash
python test_icon.pyw
```

此窗口会显示：
- 图标文件的找到情况
- 图标预览
- 检查清单

### 2. 检查图标配置

运行配置检查：
```bash
python check_icon_config.py
```

输出信息包括：
- ✅/❌ 各个图标文件的存在状态
- 文件大小和最后修改时间
- 环境变量和配置文件内容
- 建议和故障排除提示

### 3. 重新生成图标

如果图标显示异常，可以重新生成：
```bash
python generate_icon.py
```

**功能:**
- 生成高质量的蓝紫色应用图标
- 创建 PNG 和 ICO 两种格式
- 支持多个尺寸 (16, 32, 64, 128, 256px)
- 包含 "TTS" 文字标识

---

## ✅ 验证清单

程序启动后，请逐一检查以下项目：

### 标题栏图标
- [ ] 窗口标题栏左上角显示 TTS 图标
- [ ] 图标显示清晰，不是空白或默认图标

### 任务栏图标
- [ ] Windows 任务栏中显示 TTS 图标
- [ ] 图标颜色正确（蓝紫色）
- [ ] 非 Python 默认图标

### 窗口切换器
- [ ] 按 Alt+Tab 时显示 TTS 图标
- [ ] 图标清晰可识别

### 系统托盘
- [ ] 右下角通知区域有托盘图标
- [ ] 点击托盘图标可显示菜单

### 持久性
- [ ] 关闭程序后重启，图标仍然正确
- [ ] 将程序固定到任务栏后图标不变

---

## 🐛 故障排除

### 问题 1: 任务栏仍显示空白或 Python 图标

**原因:**
- Windows 图标缓存未更新
- 图标文件无效

**解决方案:**

**步骤 1: 清除 Windows 图标缓存**
```powershell
# 关闭文件管理器
taskkill /F /IM explorer.exe

# 等待 1-2 秒
Start-Sleep -Seconds 2

# 重启文件管理器
explorer.exe
```

**步骤 2: 验证图标文件**
```powershell
# 检查文件是否存在
Test-Path ".\icon.ico"
Test-Path ".\icon.png"

# 获取文件信息
Get-Item ".\icon.ico" | Select-Object Length
```

**步骤 3: 重新生成图标**
```bash
python generate_icon.py
```

**步骤 4: 重启程序**
```bash
python AYE_TTS_Main.pyw
```

### 问题 2: 控制台看不到调试信息

**原因:**
- 可能在后台运行
- 需要查看程序输出

**解决方案:**

使用启动脚本（会保持窗口打开）：
```bash
# Windows
run_tts.bat

# PowerShell  
.\run_tts.ps1
```

### 问题 3: 依赖库缺失错误

**错误信息:**
```
ModuleNotFoundError: No module named 'PIL'
```

**解决方案:**

安装 Pillow 库（用于图标生成）：
```bash
pip install Pillow
```

### 问题 4: 图标仍为白纸

**原因:**
- 使用的 PNG 图标无效
- ICO 文件格式错误

**解决方案:**

重新生成图标并确保成功：
```bash
python generate_icon.py
```

检查输出是否显示：
```
✅ 已生成 PNG 图标
✅ 已生成 ICO 图标
✅ 已生成任务栏 ICO 图标
```

---

## 🔍 调试步骤

### 查看程序启动日志

运行程序时观察控制台输出中的 `[ICON]` 标签：

```
[ICON] 从本目录加载 ICO: C:\...\icon.ico
[ICON] Using icon: C:\...\icon.ico
[ICON] Successfully applied icon.ico to HWND 1234567 and its class.
[ICON] Final Win32 API icon setup for HWND 1234567.
[ICON] System tray icon created successfully.
```

### 查看系统事件日志

在 Windows 事件查看器中检查 (可选)：
- 应用程序和服务日志 → Windows → Application

### 查看进程信息

使用 Process Explorer 检查程序的窗口属性：
- 下载: https://docs.microsoft.com/en-us/sysinternals/downloads/process-explorer
- 搜索 `pythonw.exe` 进程
- 查看其窗口属性

---

## 🎨 自定义图标

### 使用自己的图标

**方法 1: 替换文件**
```bash
# 替换 icon.png (建议 256x256 或更大)
# 替换 icon.ico (可选)

# 重启程序
python AYE_TTS_Main.pyw
```

**方法 2: 使用环境变量**
```powershell
# 设置环境变量指向自定义图标
$env:AYE_TTS_ICON = "C:\path\to\your\icon.ico"

# 启动程序
python AYE_TTS_Main.pyw
```

**方法 3: 使用配置文件**
```bash
# 创建 icon.path 文件
echo "C:\path\to\your\icon.ico" > icon.path

# 程序启动时会读取此文件
```

### 生成自定义图标

编辑 `generate_icon.py` 中的颜色方案：

```python
colors = {
    "bg": (YOUR_R, YOUR_G, YOUR_B),      # 背景颜色
    "accent": (YOUR_R, YOUR_G, YOUR_B),  # 强调颜色
    "text": (255, 255, 255),              # 文字颜色 (保持白色)
    "shadow": (YOUR_R, YOUR_G, YOUR_B),   # 阴影颜色
}
```

然后运行：
```bash
python generate_icon.py
```

---

## 📊 技术细节

### 应用 ID (AUMID)
```
AYE.TTS.App.1.0
```
- 用于 Windows 任务栏分组
- 与其他 AYE 应用程序分离
- 支持应用固定和跳转列表

### 图标设置方法

程序使用三层保险确保图标显示：

1. **SetClassLongPtr** (最持久)
   ```
   为窗口类设置图标，对所有实例生效
   ```

2. **WM_SETICON** (实时更新)
   ```
   为特定窗口实例设置图标
   ```

3. **IPropertyStore** (任务栏属性)
   ```
   设置 RelaunchCommand 和 RelaunchIcon
   用于任务栏固定和重启
   ```

### 支持的平台
- ✅ Windows 7 及以上
- ✅ x86 和 x64 架构
- ✅ 高 DPI 显示屏支持

---

## 🔗 相关资源

### 官方文档
- [PySide6 QIcon](https://doc.qt.io/qtforpython-6/PySide6/QtGui/QIcon.html)
- [Windows AppUserModelID](https://docs.microsoft.com/en-us/windows/win32/shell/appids)
- [WM_SETICON Message](https://docs.microsoft.com/en-us/windows/win32/winmsg/wm-seticon)

### 相关工具
- [IconFX](http://www.nongnu.org/iconfx/) - 图标编辑
- [ImageMagick](https://imagemagick.org/) - 图像处理
- [Process Explorer](https://docs.microsoft.com/en-us/sysinternals/downloads/process-explorer) - 进程查看

---

## 📞 支持与反馈

如遇问题，请：

1. ✅ 运行 `check_icon_config.py` 检查配置
2. ✅ 查看 `CHANGELOG_ICON_FIX.md` 了解更新内容
3. ✅ 运行 `test_icon.pyw` 测试图标显示
4. ✅ 检查控制台输出中的 `[ICON]` 日志

---

**版本**: 1.0  
**更新日期**: 2025-10-24  
**状态**: ✅ 生产就绪
