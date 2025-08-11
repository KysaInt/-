# C4D渲染队列监听程序使用说明

## 功能说明
这个程序可以监听Cinema 4D的渲染队列状态：
- 当检测到C4D正在渲染时，输出 `1`
- 当没有渲染活动时，输出 `0`

## 文件说明
- `c4dvray.py` - 主监听程序
- `c4d_monitor.bat` - 启动脚本（双击运行）
- `c4d_render_log.txt` - 日志文件（自动生成）
- `c4d_render_status.json` - 状态文件（自动生成）

## 使用方法

### 方法1：直接双击批处理文件
1. 双击 `c4d_monitor.bat` 文件
2. 程序将开始监听C4D渲染状态
3. 按 `Ctrl+C` 停止监听

### 方法2：命令行运行
```powershell
cd "c:\Users\94230\OneDrive\-"
& "C:/Users/94230/AppData/Local/Programs/Python/Python313/python.exe" "c4dvray.py"
```

### 方法3：在其他程序中调用
可以在其他程序中调用此监听程序，通过读取输出来获取渲染状态。

## 监听原理
程序通过以下方式检测C4D渲染状态：

1. **进程监听**：检测以下C4D相关进程
   - CINEMA 4D.exe
   - Cinema 4D.exe
   - c4d.exe
   - Commandline.exe（命令行渲染）
   - TeamRender Client.exe（团队渲染客户端）
   - TeamRender Server.exe（团队渲染服务器）

2. **CPU使用率检测**：当C4D进程CPU使用率超过20%时，认为可能在渲染

3. **渲染队列文件检测**：监听Maxon文件夹中的渲染队列相关文件

## 输出格式
- `1` - 正在渲染
- `0` - 未渲染

## 日志功能
程序会自动记录：
- 状态变化时间
- 检测到的C4D进程信息
- 错误信息

## 注意事项
1. 需要安装Python 3.x和psutil库
2. 程序每2秒检查一次状态
3. 只有状态发生变化时才会输出新的值
4. 程序会自动创建日志文件用于调试

## 故障排除
如果程序无法正常工作：
1. 确保C4D正在运行
2. 检查 `c4d_render_log.txt` 日志文件
3. 确认Python环境配置正确
4. 检查是否有权限访问C4D进程信息

## 自定义配置
如需修改监听频率或其他参数，可编辑 `c4dvray.py` 文件中的相关设置。
