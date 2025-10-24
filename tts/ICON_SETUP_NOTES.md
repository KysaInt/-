# TTS 程序任务栏图标显示优化说明

## 问题描述
程序运行时任务栏图标可能显示不正常或显示为默认 Python 图标。

## 改进方案

### 1. **窗口句柄创建时序修复**
- **原问题**: 在 `w.show()` 之前尝试获取 HWND 可能会失败
- **解决方案**: 移动所有 Win32 API 调用到 `w.show()` 之后
- **效果**: 确保原生窗口句柄已正确创建

### 2. **全局图标缓存机制**
- **原问题**: QIcon 和托盘图标对象可能被垃圾回收
- **解决方案**: 添加全局 `_ICON_CACHE` 字典保存所有图标相关对象
- **效果**: 防止图标在内存中被释放，任务栏图标保持稳定显示

### 3. **增强的 Win32 API 图标设置**
- **方法一**: 使用 `WM_SETICON` 消息直接设置 HICON
- **方法二**: 使用 `SetClassLongPtrW` 为窗口类设置图标（更持久）
- **方法三**: 通过 IPropertyStore 设置 RelaunchIconResource

### 4. **PNG 到 ICO 转换处理**
- **原问题**: `_apply_win_taskbar_icon()` 只支持 .ico 文件
- **解决方案**: 自动将 PNG 图标临时转换为 ICO 格式用于 Win32 API 调用
- **效果**: 支持 PNG 图标，避免仅有 PNG 时无法显示的问题

### 5. **多级图标加载策略**
依次查找图标文件：
1. 环境变量 `AYE_TTS_ICON` 指定的路径
2. `icon.path` 配置文件中的路径
3. 本目录的 `icon.png` 或 `icon.ico`
4. 备选: `QT/AYE/` 目录中的图标

### 6. **系统托盘图标缓存**
- 保存托盘对象和菜单到全局缓存
- 保存菜单中的 QAction 对象
- 确保托盘图标始终可用

## 配置文件

### icon.path (可选)
在 `tts/` 目录下创建 `icon.path` 文件，第一行指定图标路径：
```
../QT/AYE/icon.ico
```

### 环境变量 (可选)
设置 `AYE_TTS_ICON` 环境变量指定图标路径：
```powershell
$env:AYE_TTS_ICON = "C:\path\to\icon.ico"
```

## 当前图标状态

已检测到以下图标文件：
- ✅ `icon.png` - PNG 格式图标
- ✅ `icon_tb.ico` - 任务栏 ICO 图标

## 验证步骤

1. 运行程序: `python AYE_TTS_Main.pyw`
2. 观察控制台输出中的 `[ICON]` 标签，确认图标是否正确加载
3. 查看 Windows 任务栏，确认图标显示正常
4. 检查 Alt+Tab 窗口切换器中的图标
5. 将程序固定到任务栏，检查固定后的图标是否正常

## 故障排除

### 任务栏仍显示 Python 图标
- 确认 `icon.png` 或 `icon.ico` 存在
- 检查 `ICON_API` 日志输出
- 尝试重启程序
- 清除 Windows 图标缓存: `taskkill /F /IM explorer.exe`

### 系统托盘图标不显示
- 确认系统托盘功能可用
- 检查 PySide6 版本是否支持 QSystemTrayIcon

## 技术细节

### AUMID (AppUserModelID)
- 设置为 `AYE.TTS.App.1.0`
- 用于区分不同的 AYE 应用程序
- 决定任务栏中的分组方式

### RelaunchCommand
自动设置为:
```
"C:\path\to\pythonw.exe" "C:\path\to\AYE_TTS_Main.pyw"
```
用于任务栏固定后的重启命令

### 兼容性支持
- Windows 7+ (已测试)
- 支持 x86 和 x64 架构
- 自动检测 SetClassLongPtr(W) 可用性
