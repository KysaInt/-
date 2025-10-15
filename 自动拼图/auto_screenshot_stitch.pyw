"""
自动截图拼接工具 (Auto Screenshot Stitch)
用于连续截取屏幕指定区域的截图,然后自动拼接成一张全景图
"""

import sys
import os
import subprocess
import importlib.util
from pathlib import Path

# ============================================================================
# 阶段 1: 依赖检查与自动安装
# ============================================================================

# 定义必需依赖及其版本要求
REQUIRED_DEPENDENCIES = {
    'PySide6': '6.5.0',
    'cv2': '4.8.0',  # opencv-contrib-python
    'numpy': '1.24.0',
    'PIL': '10.0.0',  # Pillow
    'win32clipboard': '306',  # pywin32
    'keyboard': '0.13.5'
}

# 包名映射 (import名 -> pip包名)
PACKAGE_NAMES = {
    'cv2': 'opencv-contrib-python',
    'PIL': 'Pillow',
    'win32clipboard': 'pywin32'
}


def check_missing_dependencies():
    """检查缺失的依赖包"""
    missing = []
    outdated = []
    
    for module_name, required_version in REQUIRED_DEPENDENCIES.items():
        try:
            # 尝试导入模块
            spec = importlib.util.find_spec(module_name)
            if spec is None:
                missing.append((module_name, required_version))
                continue
            
            # 检查版本
            try:
                module = __import__(module_name)
                current_version = getattr(module, '__version__', '0.0.0')
                
                # 简单版本比较
                if compare_versions(current_version, required_version) < 0:
                    outdated.append((module_name, current_version, required_version))
            except Exception:
                # 如果无法获取版本，认为模块存在但版本未知，不强制升级
                pass
                
        except (ImportError, ModuleNotFoundError):
            missing.append((module_name, required_version))
        except Exception:
            # 其他异常忽略，避免误报
            pass
    
    return missing, outdated


def compare_versions(v1, v2):
    """比较版本号 返回: -1(v1<v2), 0(v1==v2), 1(v1>v2)"""
    def normalize(v):
        # 提取版本号中的数字部分
        parts = []
        for part in str(v).split('.')[:3]:
            # 只提取数字
            import re
            num = re.findall(r'\d+', part)
            if num:
                parts.append(int(num[0]))
        return parts
    
    try:
        parts1 = normalize(v1)
        parts2 = normalize(v2)
        
        # 补齐长度
        max_len = max(len(parts1), len(parts2))
        parts1 += [0] * (max_len - len(parts1))
        parts2 += [0] * (max_len - len(parts2))
        
        for p1, p2 in zip(parts1, parts2):
            if p1 < p2:
                return -1
            elif p1 > p2:
                return 1
        return 0
    except Exception:
        # 如果比较失败，认为版本满足要求
        return 0


def get_pip_package_name(module_name):
    """获取 pip 包名"""
    return PACKAGE_NAMES.get(module_name, module_name)


# 在导入其他依赖前检查（每次都检查，但只在有问题时才提示）
# 添加调试模式：设置环境变量 DEBUG=1 可以看到详细的依赖检查信息
DEBUG = os.environ.get('DEBUG', '0') == '1'

if DEBUG:
    print("=" * 60)
    print("依赖检查开始...")
    print("=" * 60)

missing, outdated = check_missing_dependencies()

if DEBUG:
    print(f"\n检查结果:")
    print(f"  缺失: {len(missing)} 个")
    print(f"  过期: {len(outdated)} 个")
    for module_name, version in missing:
        print(f"    - 缺失: {module_name} (需要 >= {version})")
    for module_name, current, required in outdated:
        print(f"    - 过期: {module_name} ({current} -> {required})")
    print("=" * 60)

if missing or outdated:
        # 需要安装依赖,使用 tkinter 显示安装对话框(tkinter 是 Python 内置的)
        try:
            import tkinter as tk
            from tkinter import ttk, scrolledtext
            import threading
            
            class DependencyInstallDialog:
                """依赖安装对话框"""
                def __init__(self, missing, outdated):
                    self.missing = missing
                    self.outdated = outdated
                    self.root = tk.Tk()
                    self.root.title("依赖检查 - Auto Screenshot Stitch")
                    self.root.geometry("600x400")
                    self.root.resizable(False, False)
                    
                    self.setup_ui()
                    
                def setup_ui(self):
                    """设置界面"""
                    # 标题
                    title_frame = tk.Frame(self.root, bg='#2196F3', height=60)
                    title_frame.pack(fill='x')
                    title_frame.pack_propagate(False)
                    
                    title_label = tk.Label(
                        title_frame,
                        text="⚠️ 正在自动安装依赖",
                        font=('Microsoft YaHei', 14, 'bold'),
                        bg='#2196F3',
                        fg='white'
                    )
                    title_label.pack(pady=15)
                    
                    # 信息区域
                    info_frame = tk.Frame(self.root, padx=20, pady=10)
                    info_frame.pack(fill='both', expand=True)
                    
                    info_text = "程序需要以下依赖才能正常运行，正在自动安装:\n\n"
                    
                    if self.missing:
                        info_text += "❌ 缺失的依赖:\n"
                        for module_name, version in self.missing:
                            pkg_name = get_pip_package_name(module_name)
                            info_text += f"   • {pkg_name} >= {version}\n"
                        info_text += "\n"
                    
                    if self.outdated:
                        info_text += "⚠️ 版本过低的依赖:\n"
                        for module_name, current, required in self.outdated:
                            pkg_name = get_pip_package_name(module_name)
                            info_text += f"   • {pkg_name}: {current} -> {required}\n"
                        info_text += "\n"
                    
                    info_text += "⏳ 请稍候，正在后台安装..."
                    
                    info_label = tk.Label(
                        info_frame,
                        text=info_text,
                        font=('Microsoft YaHei', 10),
                        justify='left',
                        anchor='w'
                    )
                    info_label.pack(fill='x')
                    
                    # 日志区域
                    log_label = tk.Label(
                        info_frame,
                        text="安装日志:",
                        font=('Microsoft YaHei', 10, 'bold')
                    )
                    log_label.pack(anchor='w', pady=(10, 5))
                    
                    self.log_text = scrolledtext.ScrolledText(
                        info_frame,
                        height=8,
                        font=('Consolas', 9),
                        state='disabled'
                    )
                    self.log_text.pack(fill='both', expand=True)
                    
                    # 按钮区域
                    button_frame = tk.Frame(self.root, padx=20, pady=15)
                    button_frame.pack(fill='x')
                    
                    self.cancel_btn = tk.Button(
                        button_frame,
                        text="取消安装",
                        command=self.cancel_install,
                        font=('Microsoft YaHei', 10),
                        padx=20,
                        pady=5
                    )
                    self.cancel_btn.pack(side='left', padx=5)
                    
                    self.status_label = tk.Label(
                        button_frame,
                        text="正在准备安装...",
                        font=('Microsoft YaHei', 9),
                        fg='#FF9800'
                    )
                    self.status_label.pack(side='right', padx=5)
                    
                    # 自动开始安装
                    self.root.after(500, self.start_install)
                
                def log(self, message):
                    """添加日志"""
                    self.log_text.config(state='normal')
                    self.log_text.insert('end', message + '\n')
                    self.log_text.see('end')
                    self.log_text.config(state='disabled')
                    self.root.update()
                
                def cancel_install(self):
                    """取消安装"""
                    self.root.quit()
                    sys.exit(1)
                
                def start_install(self):
                    """开始安装"""
                    self.cancel_btn.config(state='disabled')
                    self.status_label.config(text="正在安装...", fg='#FF9800')
                    
                    # 在新线程中安装
                    thread = threading.Thread(target=self.install_dependencies)
                    thread.daemon = True
                    thread.start()
                
                def install_dependencies(self):
                    """安装依赖"""
                    try:
                        # 收集所有需要安装的包
                        packages = []
                        
                        for module_name, version in self.missing:
                            pkg_name = get_pip_package_name(module_name)
                            packages.append(f"{pkg_name}>={version}")
                        
                        for module_name, current, required in self.outdated:
                            pkg_name = get_pip_package_name(module_name)
                            packages.append(f"{pkg_name}>={required}")
                        
                        if not packages:
                            self.log("没有需要安装的包")
                            return
                        
                        self.log(f"准备安装 {len(packages)} 个包...\n")
                        
                        # 使用 pip 安装
                        for package in packages:
                            self.log(f"正在安装 {package}...")
                            
                            try:
                                result = subprocess.run(
                                    [sys.executable, '-m', 'pip', 'install', package],
                                    capture_output=True,
                                    text=True,
                                    timeout=300
                                )
                                
                                if result.returncode == 0:
                                    self.log(f"✓ {package} 安装成功")
                                else:
                                    self.log(f"✗ {package} 安装失败: {result.stderr}")
                                    raise Exception(f"安装失败: {result.stderr}")
                            except subprocess.TimeoutExpired:
                                self.log(f"✗ {package} 安装超时")
                                raise Exception("安装超时")
                        
                        self.log("\n✅ 所有依赖安装完成! 程序将在 2 秒后自动重启...")
                        self.status_label.config(text="✅ 安装完成", fg='#4CAF50')
                        
                        # 等待 2 秒后重启程序
                        self.root.after(2000, self.restart_program)
                        
                    except Exception as e:
                        self.log(f"\n❌ 安装失败: {str(e)}")
                        self.status_label.config(text="❌ 安装失败", fg='#F44336')
                        self.cancel_btn.config(state='normal', text="关闭")
                
                def restart_program(self):
                    """重启程序"""
                    self.root.destroy()
                    
                    # 直接重启，不需要特殊参数（依赖已安装，下次启动会自动跳过）
                    args = [sys.executable, sys.argv[0]]
                    
                    if sys.platform == 'win32':
                        # Windows: 使用 pythonw.exe 运行 .pyw 文件
                        pythonw = sys.executable.replace('python.exe', 'pythonw.exe')
                        if os.path.exists(pythonw):
                            args[0] = pythonw
                    
                    subprocess.Popen(args)
                    sys.exit(0)
                
                def run(self):
                    """运行对话框"""
                    self.root.mainloop()
            
            # 显示安装对话框
            dialog = DependencyInstallDialog(missing, outdated)
            dialog.run()
            sys.exit(0)
            
        except Exception as e:
            print(f"依赖检查失败: {e}")
            sys.exit(1)


# ============================================================================
# 阶段 2: 导入所有依赖
# ============================================================================

import tempfile
import shutil
import datetime
import time
from typing import List, Tuple, Optional

from PySide6.QtCore import (
    Qt, QThread, Signal, QSettings, QSize, QRect, QPoint, QTimer
)
from PySide6.QtGui import (
    QPainter, QColor, QPen, QFont, QPixmap, QImage, QKeySequence, QIcon
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSpinBox, QDoubleSpinBox, QLineEdit, QMessageBox, QProgressBar,
    QGroupBox, QFormLayout, QCheckBox
)

import cv2
import numpy as np
from PIL import ImageGrab, Image
import win32clipboard
import keyboard


# ============================================================================
# 阶段 3: 区域选择蒙版窗口
# ============================================================================

class OverlayWindow(QWidget):
    """全屏半透明蒙版窗口,用于选择截图区域"""
    
    area_selected = Signal(tuple)  # (x, y, width, height)
    
    def __init__(self):
        super().__init__()
        self.start_pos = None
        self.end_pos = None
        self.is_selecting = False
        
        self.setup_ui()
    
    def setup_ui(self):
        """设置窗口"""
        # 设置为全屏无边框窗口
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.Tool
        )
        
        # 获取所有屏幕的总尺寸
        screen = QApplication.primaryScreen().virtualGeometry()
        self.setGeometry(screen)
        
        # 设置窗口为半透明
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowOpacity(0.3)
        
        # 设置鼠标光标
        self.setCursor(Qt.CrossCursor)
    
    def paintEvent(self, event):
        """绘制事件"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制半透明黑色背景
        painter.fillRect(self.rect(), QColor(0, 0, 0, 150))
        
        # 如果正在选择,绘制选择区域
        if self.start_pos and self.end_pos:
            # 选择区域矩形
            rect = QRect(self.start_pos, self.end_pos).normalized()
            
            # 清除选择区域的蒙版(显示原始屏幕)
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(rect, Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            
            # 绘制边框
            pen = QPen(QColor(0, 255, 0), 2, Qt.SolidLine)
            painter.setPen(pen)
            painter.drawRect(rect)
            
            # 绘制尺寸信息
            text = f"{rect.width()} × {rect.height()}"
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Arial", 12, QFont.Bold))
            
            # 计算文本位置(在矩形上方居中)
            text_rect = painter.fontMetrics().boundingRect(text)
            text_x = rect.x() + (rect.width() - text_rect.width()) // 2
            text_y = rect.y() - 10
            
            # 绘制文本背景
            bg_rect = QRect(
                text_x - 5,
                text_y - text_rect.height() - 5,
                text_rect.width() + 10,
                text_rect.height() + 10
            )
            painter.fillRect(bg_rect, QColor(0, 0, 0, 180))
            
            # 绘制文本
            painter.drawText(text_x, text_y, text)
        
        # 绘制提示信息
        if not self.is_selecting:
            hint_text = "拖拽鼠标选择截图区域 | 按 ESC 取消"
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
            
            text_rect = painter.fontMetrics().boundingRect(hint_text)
            text_x = (self.width() - text_rect.width()) // 2
            text_y = 50
            
            # 绘制文本背景
            bg_rect = QRect(
                text_x - 10,
                text_y - text_rect.height() - 10,
                text_rect.width() + 20,
                text_rect.height() + 20
            )
            painter.fillRect(bg_rect, QColor(0, 0, 0, 200))
            
            # 绘制文本
            painter.drawText(text_x, text_y, hint_text)
    
    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.LeftButton:
            self.start_pos = event.pos()
            self.end_pos = event.pos()
            self.is_selecting = True
            self.update()
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        if self.is_selecting:
            self.end_pos = event.pos()
            self.update()
    
    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        if event.button() == Qt.LeftButton and self.is_selecting:
            self.end_pos = event.pos()
            self.is_selecting = False
            
            # 计算选择区域
            rect = QRect(self.start_pos, self.end_pos).normalized()
            
            # 检查区域大小
            if rect.width() > 10 and rect.height() > 10:
                self.area_selected.emit((
                    rect.x(),
                    rect.y(),
                    rect.width(),
                    rect.height()
                ))
                self.close()
            else:
                QMessageBox.warning(self, "提示", "选择区域太小,请重新选择")
                self.start_pos = None
                self.end_pos = None
                self.update()
    
    def keyPressEvent(self, event):
        """键盘事件"""
        if event.key() == Qt.Key_Escape:
            self.close()


# ============================================================================
# 阶段 4: 截图工作线程
# ============================================================================

class ScreenshotThread(QThread):
    """截图线程"""
    
    screenshot_taken = Signal(int)  # 已截取的图片数量
    error_occurred = Signal(str)
    
    def __init__(self, area: Tuple[int, int, int, int], interval: float, output_dir: str):
        super().__init__()
        self.area = area  # (x, y, width, height)
        self.interval = interval
        self.output_dir = output_dir
        self.is_running = True
        self.screenshot_count = 0
    
    def run(self):
        """运行截图"""
        try:
            x, y, width, height = self.area
            
            while self.is_running:
                # 截取屏幕区域
                screenshot = ImageGrab.grab(bbox=(x, y, x + width, y + height))
                
                # 保存截图
                self.screenshot_count += 1
                filename = os.path.join(
                    self.output_dir,
                    f"screenshot_{self.screenshot_count:04d}.png"
                )
                screenshot.save(filename)
                
                # 发送信号
                self.screenshot_taken.emit(self.screenshot_count)
                
                # 等待间隔时间
                time.sleep(self.interval)
        
        except Exception as e:
            self.error_occurred.emit(f"截图失败: {str(e)}")
    
    def stop(self):
        """停止截图"""
        self.is_running = False


# ============================================================================
# 阶段 5: 图像拼接线程
# ============================================================================

class StitchThread(QThread):
    """图像拼接线程"""
    
    progress_updated = Signal(int)  # 进度百分比
    stitch_completed = Signal(str)  # 拼接完成,返回结果图片路径
    error_occurred = Signal(str)
    
    def __init__(self, image_dir: str):
        super().__init__()
        self.image_dir = image_dir
    
    def run(self):
        """运行拼接"""
        try:
            # 读取所有图片
            self.progress_updated.emit(10)
            
            image_files = sorted([
                f for f in os.listdir(self.image_dir)
                if f.lower().endswith(('.png', '.jpg', '.jpeg'))
            ])
            
            if len(image_files) < 2:
                self.error_occurred.emit("至少需要 2 张图片才能拼接")
                return
            
            # 加载图片
            self.progress_updated.emit(30)
            images = []
            
            for idx, filename in enumerate(image_files):
                filepath = os.path.join(self.image_dir, filename)
                img = cv2.imread(filepath)
                
                if img is not None:
                    images.append(img)
            
            if len(images) < 2:
                self.error_occurred.emit("没有足够的有效图片")
                return
            
            # 创建拼接器
            self.progress_updated.emit(50)
            
            # 使用 SCANS 模式(扫描模式,适合有序截图)
            stitcher = cv2.Stitcher.create(cv2.Stitcher_SCANS)
            
            # 执行拼接
            self.progress_updated.emit(70)
            status, stitched = stitcher.stitch(images)
            
            if status == cv2.Stitcher_OK:
                # 保存结果
                self.progress_updated.emit(90)
                output_path = os.path.join(self.image_dir, "stitched_result.png")
                cv2.imwrite(output_path, stitched)
                
                self.progress_updated.emit(100)
                self.stitch_completed.emit(output_path)
            else:
                error_messages = {
                    cv2.Stitcher_ERR_NEED_MORE_IMGS: "需要更多图片",
                    cv2.Stitcher_ERR_HOMOGRAPHY_EST_FAIL: "特征匹配失败(图片重叠不足)",
                    cv2.Stitcher_ERR_CAMERA_PARAMS_ADJUST_FAIL: "相机参数调整失败"
                }
                error_msg = error_messages.get(status, f"拼接失败(错误码: {status})")
                self.error_occurred.emit(error_msg)
        
        except Exception as e:
            self.error_occurred.emit(f"拼接过程出错: {str(e)}")


# ============================================================================
# 阶段 6: 剪贴板工具
# ============================================================================

def copy_image_to_clipboard(image_path: str) -> bool:
    """将图片复制到 Windows 剪贴板"""
    try:
        # 读取图片
        image = Image.open(image_path)
        
        # 转换为 BMP 格式(剪贴板需要)
        output = io.BytesIO()
        image.convert('RGB').save(output, 'BMP')
        data = output.getvalue()[14:]  # BMP 文件头是 14 字节,剪贴板不需要
        output.close()
        
        # 复制到剪贴板
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
        win32clipboard.CloseClipboard()
        
        return True
    except Exception as e:
        print(f"复制到剪贴板失败: {e}")
        return False


# 需要导入 io
import io


# ============================================================================
# 阶段 7: 主窗口
# ============================================================================

class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        
        # 配置
        self.settings = QSettings('AutoStitch', 'Config')
        
        # 状态
        self.selected_area = None
        self.temp_dir = None
        self.screenshot_thread = None
        self.stitch_thread = None
        self.overlay_window = None
        
        # 全局快捷键
        self.hotkey = self.settings.value('hotkey', 'ctrl+shift+a')
        
        self.setup_ui()
        self.load_settings()
        self.setup_hotkey()
    
    def setup_ui(self):
        """设置界面"""
        self.setWindowTitle("截图拼接")
        self.setMinimumSize(380, 360)
        self.setMaximumSize(420, 400)
        
        # 中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(12, 12, 12, 12)
        
        # 设置组 - 紧凑布局
        settings_group = QGroupBox("设置")
        settings_group.setFont(QFont("Microsoft YaHei", 9, QFont.Bold))
        settings_layout = QFormLayout()
        settings_layout.setSpacing(6)
        settings_layout.setContentsMargins(8, 8, 8, 8)
        
        # 截图间隔
        interval_widget = QWidget()
        interval_layout = QHBoxLayout(interval_widget)
        interval_layout.setContentsMargins(0, 0, 0, 0)
        interval_layout.setSpacing(4)
        
        self.interval_spinbox = QDoubleSpinBox()
        self.interval_spinbox.setRange(0.1, 10.0)
        self.interval_spinbox.setDecimals(1)
        self.interval_spinbox.setSingleStep(0.1)
        self.interval_spinbox.setValue(0.2)  # 默认0.2秒
        self.interval_spinbox.setSuffix(" 秒")
        self.interval_spinbox.setFont(QFont("Microsoft YaHei", 9))
        self.interval_spinbox.setMaximumWidth(80)
        interval_layout.addWidget(self.interval_spinbox)
        
        self.auto_copy_checkbox = QCheckBox("自动复制")
        self.auto_copy_checkbox.setChecked(True)
        self.auto_copy_checkbox.setFont(QFont("Microsoft YaHei", 9))
        interval_layout.addWidget(self.auto_copy_checkbox)
        interval_layout.addStretch()
        
        settings_layout.addRow("间隔:", interval_widget)
        
        # 快捷键 - 更紧凑
        hotkey_layout = QHBoxLayout()
        hotkey_layout.setSpacing(4)
        self.hotkey_edit = QLineEdit(self.hotkey)
        self.hotkey_edit.setFont(QFont("Microsoft YaHei", 9))
        self.hotkey_edit.setPlaceholderText("ctrl+shift+a")
        hotkey_layout.addWidget(self.hotkey_edit)
        
        update_hotkey_btn = QPushButton("更新")
        update_hotkey_btn.setFont(QFont("Microsoft YaHei", 8))
        update_hotkey_btn.setMaximumWidth(50)
        update_hotkey_btn.clicked.connect(self.update_hotkey)
        hotkey_layout.addWidget(update_hotkey_btn)
        
        settings_layout.addRow("快捷键:", hotkey_layout)
        
        settings_group.setLayout(settings_layout)
        main_layout.addWidget(settings_group)
        
        # 选择区域按钮
        self.select_area_btn = QPushButton("选择区域")
        self.select_area_btn.setFont(QFont("Microsoft YaHei", 10))
        self.select_area_btn.setMinimumHeight(40)
        self.select_area_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
            }
        """)
        self.select_area_btn.clicked.connect(self.select_area)
        main_layout.addWidget(self.select_area_btn)
        
        # 区域信息 - 更紧凑
        self.area_label = QLabel("未选择")
        self.area_label.setFont(QFont("Microsoft YaHei", 8))
        self.area_label.setStyleSheet("color: #666; padding: 2px;")
        self.area_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.area_label)
        
        # 隐藏的开始和停止按钮（保留逻辑，但不显示）
        self.start_screenshot_btn = QPushButton()
        self.start_screenshot_btn.setVisible(False)
        self.start_screenshot_btn.clicked.connect(self.start_screenshot)
        
        self.stop_and_stitch_btn = QPushButton()
        self.stop_and_stitch_btn.setVisible(False)
        self.stop_and_stitch_btn.clicked.connect(self.stop_and_stitch)
        
        # 状态组 - 紧凑
        status_group = QGroupBox("状态")
        status_group.setFont(QFont("Microsoft YaHei", 9, QFont.Bold))
        status_layout = QVBoxLayout()
        status_layout.setSpacing(6)
        status_layout.setContentsMargins(8, 8, 8, 8)
        
        # 截图计数和状态合并到一行
        status_row = QHBoxLayout()
        self.screenshot_count_label = QLabel("0 张")
        self.screenshot_count_label.setFont(QFont("Microsoft YaHei", 9))
        status_row.addWidget(QLabel("已截:"))
        status_row.addWidget(self.screenshot_count_label)
        status_row.addStretch()
        
        self.status_label = QLabel("就绪")
        self.status_label.setFont(QFont("Microsoft YaHei", 9))
        self.status_label.setStyleSheet("color: #666;")
        status_row.addWidget(self.status_label)
        
        status_layout.addLayout(status_row)
        
        # 进度条 - 更细
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFont(QFont("Microsoft YaHei", 8))
        self.progress_bar.setMaximumHeight(16)
        status_layout.addWidget(self.progress_bar)
        
        status_group.setLayout(status_layout)
        main_layout.addWidget(status_group)
        
        # 底部提示 - 更紧凑
        hint_label = QLabel(f"按 {self.hotkey} 启动/停止")
        hint_label.setFont(QFont("Microsoft YaHei", 8))
        hint_label.setStyleSheet("color: #999; padding: 4px;")
        hint_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(hint_label)
        self.hint_label = hint_label
        
        main_layout.addStretch()
    
    def load_settings(self):
        """加载设置"""
        interval = self.settings.value('interval', 0.2, type=float)
        self.interval_spinbox.setValue(interval)
        
        auto_copy = self.settings.value('auto_copy', True, type=bool)
        self.auto_copy_checkbox.setChecked(auto_copy)
    
    def save_settings(self):
        """保存设置"""
        self.settings.setValue('interval', self.interval_spinbox.value())
        self.settings.setValue('auto_copy', self.auto_copy_checkbox.isChecked())
        self.settings.setValue('hotkey', self.hotkey)
    
    def setup_hotkey(self):
        """设置全局快捷键"""
        try:
            # 移除旧的快捷键
            keyboard.unhook_all()
            
            # 添加新的快捷键
            keyboard.add_hotkey(self.hotkey, self.hotkey_triggered)
            
        except Exception as e:
            QMessageBox.warning(
                self,
                "快捷键设置失败",
                f"无法设置全局快捷键: {str(e)}\n\n"
                "请尝试以管理员权限运行程序,或更改快捷键。"
            )
    
    def update_hotkey(self):
        """更新快捷键"""
        new_hotkey = self.hotkey_edit.text().strip().lower()
        
        if not new_hotkey:
            QMessageBox.warning(self, "提示", "快捷键不能为空")
            return
        
        self.hotkey = new_hotkey
        self.save_settings()
        self.setup_hotkey()
        self.hint_label.setText(f"按 {self.hotkey} 启动/停止")
        
        QMessageBox.information(self, "成功", f"快捷键已更新为: {self.hotkey}")
    
    def hotkey_triggered(self):
        """快捷键触发"""
        # 根据当前状态执行不同操作
        if self.screenshot_thread and self.screenshot_thread.isRunning():
            # 正在截图 -> 停止并拼接
            self.stop_and_stitch()
        elif self.selected_area:
            # 已选择区域 -> 开始截图
            self.start_screenshot()
        else:
            # 未选择区域 -> 选择区域
            self.select_area()
    
    def select_area(self):
        """选择截图区域"""
        self.status_label.setText("选择区域...")
        
        # 隐藏主窗口
        self.hide()
        
        # 延迟显示蒙版窗口
        QTimer.singleShot(200, self.show_overlay)
    
    def show_overlay(self):
        """显示蒙版窗口"""
        self.overlay_window = OverlayWindow()
        self.overlay_window.area_selected.connect(self.on_area_selected)
        self.overlay_window.show()
    
    def on_area_selected(self, area):
        """区域选择完成"""
        self.selected_area = area
        x, y, width, height = area
        
        self.area_label.setText(f"{width} × {height}")
        self.start_screenshot_btn.setEnabled(True)
        self.status_label.setText("已选择")
        
        # 显示主窗口
        self.show()
        self.activateWindow()
    
    def start_screenshot(self):
        """开始自动截图"""
        if not self.selected_area:
            QMessageBox.warning(self, "提示", "请先选择截图区域")
            return
        
        # 保存设置
        self.save_settings()
        
        # 创建临时目录
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.temp_dir = os.path.join(
            tempfile.gettempdir(),
            f"autostitch_{timestamp}"
        )
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # 更新界面
        self.select_area_btn.setEnabled(False)
        self.start_screenshot_btn.setEnabled(False)
        self.stop_and_stitch_btn.setEnabled(True)
        self.screenshot_count_label.setText("0 张")
        self.status_label.setText("截图中...")
        
        # 启动截图线程
        interval = self.interval_spinbox.value()
        self.screenshot_thread = ScreenshotThread(
            self.selected_area,
            interval,
            self.temp_dir
        )
        self.screenshot_thread.screenshot_taken.connect(self.on_screenshot_taken)
        self.screenshot_thread.error_occurred.connect(self.on_screenshot_error)
        self.screenshot_thread.start()
    
    def on_screenshot_taken(self, count):
        """截图完成"""
        self.screenshot_count_label.setText(f"{count} 张")
    
    def on_screenshot_error(self, error):
        """截图错误"""
        QMessageBox.critical(self, "错误", error)
        self.reset_ui()
    
    def stop_and_stitch(self):
        """停止截图并拼接"""
        # 停止截图线程
        if self.screenshot_thread and self.screenshot_thread.isRunning():
            self.screenshot_thread.stop()
            self.screenshot_thread.wait()
        
        # 检查截图数量
        if self.screenshot_thread.screenshot_count < 2:
            QMessageBox.warning(self, "提示", "至少需要 2 张截图才能拼接")
            self.reset_ui()
            return
        
        # 更新界面
        self.stop_and_stitch_btn.setEnabled(False)
        self.status_label.setText("拼接中...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # 启动拼接线程
        self.stitch_thread = StitchThread(self.temp_dir)
        self.stitch_thread.progress_updated.connect(self.on_stitch_progress)
        self.stitch_thread.stitch_completed.connect(self.on_stitch_completed)
        self.stitch_thread.error_occurred.connect(self.on_stitch_error)
        self.stitch_thread.start()
    
    def on_stitch_progress(self, progress):
        """拼接进度"""
        self.progress_bar.setValue(progress)
    
    def on_stitch_completed(self, result_path):
        """拼接完成"""
        self.progress_bar.setVisible(False)
        self.status_label.setText("完成")
        
        # 复制到剪贴板
        if self.auto_copy_checkbox.isChecked():
            if copy_image_to_clipboard(result_path):
                self.status_label.setText("完成 (已复制)")
                
                QMessageBox.information(
                    self,
                    "完成",
                    f"拼接完成!\n\n"
                    f"已复制到剪贴板,可直接粘贴。\n\n"
                    f"保存位置:\n{result_path}"
                )
            else:
                QMessageBox.information(
                    self,
                    "完成",
                    f"拼接完成!\n\n"
                    f"保存位置:\n{result_path}"
                )
        else:
            QMessageBox.information(
                self,
                "完成",
                f"拼接完成!\n\n"
                f"保存位置:\n{result_path}"
            )
        
        self.reset_ui()
    
    def on_stitch_error(self, error):
        """拼接错误"""
        self.progress_bar.setVisible(False)
        
        QMessageBox.critical(
            self,
            "拼接失败",
            f"{error}\n\n"
            "可能原因:\n"
            "• 图片重叠不足\n"
            "• 间隔过长\n"
            "• 数量不足\n\n"
            "建议:\n"
            "• 减小截图间隔\n"
            "• 确保30%以上重叠"
        )
        
        self.reset_ui()
    
    def reset_ui(self):
        """重置界面"""
        self.select_area_btn.setEnabled(True)
        self.start_screenshot_btn.setEnabled(bool(self.selected_area))
        self.stop_and_stitch_btn.setEnabled(False)
        self.status_label.setText("就绪")
        self.progress_bar.setVisible(False)
        
        # 清理临时目录
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                # 保留拼接结果,删除其他文件
                for file in os.listdir(self.temp_dir):
                    if file != "stitched_result.png":
                        filepath = os.path.join(self.temp_dir, file)
                        try:
                            os.remove(filepath)
                        except:
                            pass
            except Exception as e:
                print(f"清理临时文件失败: {e}")
    
    def closeEvent(self, event):
        """关闭事件"""
        # 停止线程
        if self.screenshot_thread and self.screenshot_thread.isRunning():
            self.screenshot_thread.stop()
            self.screenshot_thread.wait()
        
        if self.stitch_thread and self.stitch_thread.isRunning():
            self.stitch_thread.wait()
        
        # 移除快捷键
        try:
            keyboard.unhook_all()
        except:
            pass
        
        # 清理临时目录
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            except:
                pass
        
        event.accept()


# ============================================================================
# 主程序入口
# ============================================================================

def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 设置应用信息
    app.setApplicationName("Auto Screenshot Stitch")
    app.setOrganizationName("AutoStitch")
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
