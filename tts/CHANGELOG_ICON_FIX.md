# TTS 任务栏图标修复 - 更新日志

## 问题诊断与解决方案

### 问题描述
程序运行时任务栏显示空白图标（白纸）而非应用图标。

### 根本原因
1. **原有的 `icon.png` 文件损坏或无效** - 可能导致图标加载失败
2. **图标优先级错误** - 原代码优先 PNG，但 PNG 无效时没有妥善降级
3. **图标缓存机制不完整** - 图标对象可能被垃圾回收
4. **窗口句柄时序问题** - 在窗口完全创建前设置图标属性

---

## 实施的改进方案

### 1️⃣ **生成新的有效图标** 
- ✅ 创建 `generate_icon.py` 脚本生成高质量图标
- ✅ 图标特点：
  - 蓝紫色专业配色
  - 包含 "TTS" 文字标识
  - 多尺寸支持 (16, 32, 64, 128, 256px)
  - PNG 和 ICO 两种格式

#### 文件生成情况：
```
✅ icon.ico       - 新生成 (470 bytes) 
✅ icon.png       - 新生成 (5073 bytes)
✅ icon_tb.ico    - 新生成 (用于任务栏)
```

### 2️⃣ **图标加载优先级优化**

修改 `AYE_TTS_Main.pyw` 中的图标加载顺序：

```
1. 环境变量 AYE_TTS_ICON
   ↓
2. icon.path 配置文件
   ↓
3. 本目录文件（⭐ ICO 优先 > PNG）
   └─ icon.ico ✅
   └─ icon.png
   ↓
4. 备选目录 QT/AYE/
```

**关键改变**: ICO 格式优先于 PNG，确保最佳的任务栏显示质量

### 3️⃣ **完整的图标缓存机制**

添加全局缓存对象，防止被垃圾回收：
```python
_ICON_CACHE = {}  # 全局缓存

# 缓存应用图标
_ICON_CACHE['app_icon'] = app_icon

# 缓存系统托盘
_ICON_CACHE['tray_icon'] = tray
_ICON_CACHE['tray_menu'] = menu
_ICON_CACHE['tray_actions'] = [act_show, act_quit]

# 窗口内部缓存
w._icon_cache = {}
w._tray_icon = tray
```

### 4️⃣ **窗口句柄时序修复**

正确的图标设置流程：
```
1. w = MainWidget()        # 创建窗口对象
   ↓
2. w.show()                # 显示窗口，创建原生句柄 ⭐
   ↓
3. hwnd = w.winId()        # 获取窗口句柄
   ↓
4. SetClassLongPtr()       # 为窗口类设置图标
5. WM_SETICON 消息         # 为窗口实例设置图标
6. IPropertyStore 属性     # 设置任务栏分组属性
```

### 5️⃣ **增强的 Win32 API 处理**

三层保险确保图标显示：

**第一层**: SetClassLongPtr (最持久)
```python
SetClassLongPtr(hwnd, GCLP_HICON, hicon_big)      # 大图标
SetClassLongPtr(hwnd, GCLP_HICONSM, hicon_small)  # 小图标
```

**第二层**: WM_SETICON 消息
```python
SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_big)
SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
```

**第三层**: IPropertyStore RelaunchIcon
```python
PKEY_RelaunchIcon = "icon.ico,0"  # 任务栏重启时使用
```

---

## 使用新工具

### 1. 生成图标
```bash
python tts/generate_icon.py
```

### 2. 测试图标显示
```bash
python tts/test_icon.pyw
```

### 3. 检查配置
```bash
python tts/check_icon_config.py
```

### 4. 运行主程序
```bash
python tts/AYE_TTS_Main.pyw
```

---

## 验证清单

运行程序后检查以下几项：

- [ ] **标题栏图标** - 窗口标题栏左上角显示 TTS 图标
- [ ] **任务栏图标** - 任务栏中显示 TTS 图标（非 Python 图标）
- [ ] **Alt+Tab 图标** - 切换窗口时显示 TTS 图标
- [ ] **系统托盘** - 右下角通知区域有托盘图标
- [ ] **图标固定** - 固定到任务栏后图标保持正确

---

## 故障排除

### 症状: 任务栏仍显示空白或 Python 图标

**解决方案:**

1. **清除 Windows 图标缓存**
```powershell
taskkill /F /IM explorer.exe
Start-Sleep -Seconds 1
explorer.exe
```

2. **验证图标文件**
```powershell
Test-Path "C:\Users\94230\OneDrive\-\tts\icon.ico"
Test-Path "C:\Users\94230\OneDrive\-\tts\icon.png"
```

3. **重新生成图标**
```bash
python tts/generate_icon.py
```

4. **查看调试输出**
程序启动时应在控制台看到类似输出：
```
[ICON] 从本目录加载 ICO: C:\Users\...\icon.ico
[ICON] Successfully applied ... to HWND ...
[ICON] Final Win32 API icon setup for HWND ...
[ICON] System tray icon created successfully.
```

---

## 文件清单

### 新增文件
- ✅ `generate_icon.py` - 图标生成脚本
- ✅ `test_icon.pyw` - 图标测试窗口
- ✅ `check_icon_config.py` - 配置检查工具
- ✅ `ICON_SETUP_NOTES.md` - 技术文档

### 修改文件
- ✅ `AYE_TTS_Main.pyw` - 主程序（优化图标加载和缓存）

### 更新的资源
- ✅ `icon.ico` - 新生成 ⭐
- ✅ `icon.png` - 新生成 ⭐
- ✅ `icon_tb.ico` - 新生成 ⭐

---

## 技术参考

### 相关 Windows API
- `WM_SETICON` (0x0080) - 设置窗口图标
- `SetClassLongPtrW` - 为窗口类设置属性
- `LoadImageW` - 从文件加载图像
- `SendMessageW` - 发送窗口消息
- `SHGetPropertyStoreForWindow` - 获取窗口属性存储
- `SetCurrentProcessExplicitAppUserModelID` - 设置应用 AUMID

### AppUserModelID (AUMID)
- 当前值: `AYE.TTS.App.1.0`
- 用途: Windows 任务栏分组与应用识别
- 优点: 与 QT/AYE 程序分离，避免合并

---

## 下一步建议

1. **验证其他 AYE 程序的图标显示** - 检查 C4D, QT 等模块
2. **创建统一的图标管理系统** - 为所有 AYE 程序提供统一的图标
3. **添加配置 UI** - 允许用户自定义应用图标
4. **性能优化** - 监控图标缓存对内存的影响

---

**最后更新**: 2025-10-24 09:35
**状态**: ✅ 完成
