"""
自动截图拼接工具
支持自定义快捷键、区域选择、连续截图和自动拼接
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Optional
import json
import subprocess
import re

# =============================================================================
# 依赖自检与自动安装模块
# =============================================================================

def _parse_version_tuple(ver: str) -> tuple:
    """将版本号字符串提取为最多三段的整数元组，例如 '4.8.1.23' -> (4,8,1)。"""
    # 修正正则表达式，移除不必要的转义
    nums = re.findall(r"\d+", ver or "0")
    if not nums:
        return (0,)
    parts = [int(x) for x in nums[:3]]
    return tuple(parts)

def _version_satisfied(installed: str, minimal: str) -> bool:
    """检查版本是否满足要求"""
    return _parse_version_tuple(installed) >= _parse_version_tuple(minimal)

def _tk_confirm(title: str, message: str) -> bool:
    """使用 Tk 弹出确认窗口；若 Tk 不可用，则返回 False。"""
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        res = messagebox.askyesno(title, message)
        root.destroy()
        return bool(res)
    except Exception:
        return False

def _tk_info(title: str, message: str) -> None:
    """使用 Tk 弹出信息窗口。"""
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        messagebox.showinfo(title, message)
        root.destroy()
    except Exception:
        pass

def _pip_install(packages: List[str]) -> tuple[bool, str]:
    """通过当前 Python 解释器执行 pip 安装。"""
    # 关键修复：确保使用 python.exe 而不是 pythonw.exe
    python_exe = sys.executable.replace("pythonw.exe", "python.exe")
    
    cmd = [python_exe, "-m", "pip", "install", "-U", *packages]
    try:
        # 在 Windows 上隐藏弹出的命令行窗口
        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', startupinfo=startupinfo)
        
        if proc.returncode == 0:
            return True, proc.stdout
            
        # 权限问题，尝试 --user
        if "Permission" in (proc.stderr or "") or "denied" in (proc.stderr or ""):
            cmd_user = [python_exe, "-m", "pip", "install", "--user", "-U", *packages]
            proc2 = subprocess.run(cmd_user, capture_output=True, text=True, encoding='utf-8', startupinfo=startupinfo)
            if proc2.returncode == 0:
                return True, proc2.stdout
            return False, (proc.stderr or "") + "\n" + (proc2.stderr or "")
            
        return False, (proc.stderr or proc.stdout or "pip 执行失败")
    except Exception as e:
        return False, str(e)

def ensure_dependencies() -> bool:
    """检查并在用户确认后安装/升级依赖。"""
    to_install: List[str] = []
    tips: List[str] = []
    
    required = {
        "PySide6": ("6.5.0", "PySide6>=6.5.0", "GUI 框架"),
        "cv2": ("4.8.0", "opencv-contrib-python>=4.8.0", "图像拼接"),
        "numpy": ("1.24.0", "numpy>=1.24.0", "图像处理"),
        "PIL": ("10.0.0", "Pillow>=10.0.0", "截图"),
        "win32clipboard": (None, "pywin32>=306", "剪贴板操作"),
        "keyboard": ("0.13.5", "keyboard>=0.13.5", "全局快捷键"),
    }

    import importlib
    for mod_name, (min_ver, pkg_name, desc) in required.items():
        try:
            if mod_name == 'win32clipboard':
                importlib.import_module('win32clipboard')
            else:
                mod = importlib.import_module(mod_name)
                if min_ver:
                    ver = getattr(mod, '__version__', '0')
                    if not _version_satisfied(ver, min_ver):
                        to_install.append(pkg_name)
                        tips.append(f"{pkg_name} ({desc})")
        except ImportError:
            to_install.append(pkg_name)
            tips.append(f"{pkg_name} ({desc})")

    if not to_install:
        return True

    pkg_text = "\n".join(f"- {t}" for t in tips)
    confirm_msg = (
        "检测到以下依赖缺失或版本过低：\n\n"
        f"{pkg_text}\n\n"
        "是否现在自动安装/升级？\n\n"
        f"将执行：pip install -U {' '.join(to_install)}"
    )
    if not _tk_confirm("依赖安装确认", confirm_msg):
        _tk_info("已取消", "已取消依赖安装，程序将退出。")
        return False

    ok, out = _pip_install(to_install)
    if ok:
        _tk_info("安装成功", "依赖已安装/升级完成，请重新启动程序。")
    else:
        _tk_info("安装失败", "自动安装失败，请手动安装：\n\n" + "pip install -U " + " ".join(to_install) + "\n\n错误信息:\n" + out)
    return False # 总是返回 False，让用户重启

# 在导入其他库之前执行依赖检查
if not ensure_dependencies():
    sys.exit(0)

# =============================================================================
# 主程序
# =============================================================================

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSpinBox, QMessageBox, QGroupBox, 
    QKeySequenceEdit, QFormLayout, QFileDialog, QCheckBox
)
from PySide6.QtCore import (
    Qt, QThread, Signal, QRect, QPoint, QSize, QTimer, QSettings
)
from PySide6.QtGui import (
    QKeySequence, QScreen, QPixmap, QImage, QPainter, QColor, QPen, QCursor
)
import cv2
import numpy as np
from PIL import ImageGrab
import win32clipboard
from io import BytesIO
import keyboard



class OverlayWindow(QWidget):
    """全屏蒙版窗口，用于选择截图区域"""
    region_selected = Signal(QRect)
    cancelled = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 150);")
        
        self.start_pos = None
        self.current_pos = None
        self.selection_rect = None
        
        # 获取主屏幕尺寸
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)
        
    def showEvent(self, event):
        super().showEvent(event)
        self.setCursor(Qt.CursorShape.CrossCursor)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_pos = event.pos()
            self.current_pos = event.pos()
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            self.cancelled.emit()
            self.close()
            
    def mouseMoveEvent(self, event):
        if self.start_pos:
            self.current_pos = event.pos()
            self.update()
            
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.start_pos:
            self.current_pos = event.pos()
            
            # 计算选择的矩形区域
            x1 = min(self.start_pos.x(), self.current_pos.x())
            y1 = min(self.start_pos.y(), self.current_pos.y())
            x2 = max(self.start_pos.x(), self.current_pos.x())
            y2 = max(self.start_pos.y(), self.current_pos.y())
            
            if abs(x2 - x1) > 10 and abs(y2 - y1) > 10:  # 最小尺寸检查
                self.selection_rect = QRect(x1, y1, x2 - x1, y2 - y1)
                self.region_selected.emit(self.selection_rect)
                self.close()
            else:
                self.cancelled.emit()
                self.close()
                
    def paintEvent(self, event):
        if self.start_pos and self.current_pos:
            painter = QPainter(self)
            
            # 绘制选择框
            x1 = min(self.start_pos.x(), self.current_pos.x())
            y1 = min(self.start_pos.y(), self.current_pos.y())
            x2 = max(self.start_pos.x(), self.current_pos.x())
            y2 = max(self.start_pos.y(), self.current_pos.y())
            
            # 使用主题高亮色
            palette = QApplication.palette()
            highlight_color = palette.highlight().color()
            
            # 绘制边框
            pen = QPen(highlight_color, 2, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.drawRect(x1, y1, x2 - x1, y2 - y1)
            
            # 绘制半透明填充
            fill_color = QColor(highlight_color)
            fill_color.setAlpha(30)
            painter.fillRect(x1, y1, x2 - x1, y2 - y1, fill_color)
            
            # 显示尺寸信息
            painter.setPen(QPen(Qt.GlobalColor.white))
            size_text = f"{x2 - x1} × {y2 - y1}"
            painter.drawText(x1 + 5, y1 + 20, size_text)


class ScreenshotThread(QThread):
    """连续截图线程"""
    progress = Signal(int)
    finished = Signal()
    
    def __init__(self, region: QRect, interval: int, output_dir: str):
        super().__init__()
        self.region = region
        self.interval = interval  # 毫秒
        self.output_dir = output_dir
        self.running = True
        self.count = 0
        
    def run(self):
        while self.running:
            try:
                # 截图
                screenshot = ImageGrab.grab(bbox=(
                    self.region.x(),
                    self.region.y(),
                    self.region.x() + self.region.width(),
                    self.region.y() + self.region.height()
                ))
                
                # 保存
                filename = os.path.join(
                    self.output_dir,
                    f"screenshot_{self.count:04d}.png"
                )
                screenshot.save(filename)
                
                self.count += 1
                self.progress.emit(self.count)
                
                # 等待
                self.msleep(self.interval)
                
            except Exception as e:
                print(f"截图错误: {e}")
                break
                
        self.finished.emit()
        
    def stop(self):
        self.running = False


class StitchThread(QThread):
    """图片拼接线程"""
    progress = Signal(str)
    finished = Signal(np.ndarray)
    error = Signal(str)
    
    def __init__(self, image_dir: str):
        super().__init__()
        self.image_dir = image_dir
        
    def run(self):
        try:
            self.progress.emit("加载图片...")
            
            # 获取所有图片文件
            image_files = sorted([
                os.path.join(self.image_dir, f)
                for f in os.listdir(self.image_dir)
                if f.lower().endswith(('.png', '.jpg', '.jpeg'))
            ])
            
            if not image_files:
                self.error.emit("未找到截图文件")
                return
                
            if len(image_files) == 1:
                # 只有一张图片，直接返回
                img = cv2.imread(image_files[0])
                if img is not None:
                    self.finished.emit(img)
                else:
                    self.error.emit("无法读取图片")
                return
                
            # 加载图片
            images = []
            for img_path in image_files:
                img = cv2.imread(img_path)
                if img is not None:
                    images.append(img)
                    
            if len(images) < 2:
                self.error.emit("可用图片数量不足")
                return
                
            self.progress.emit(f"正在拼接 {len(images)} 张图片...")
            
            # 使用 OpenCV Stitcher
            stitcher = cv2.Stitcher_create(cv2.Stitcher_SCANS)
            status, pano = stitcher.stitch(images)
            
            if status == cv2.Stitcher_OK:
                self.progress.emit("拼接完成")
                self.finished.emit(pano)
            else:
                error_messages = {
                    cv2.Stitcher_ERR_NEED_MORE_IMGS: "需要更多图片",
                    cv2.Stitcher_ERR_HOMOGRAPHY_EST_FAIL: "图片匹配失败，请确保图片有重叠区域",
                    cv2.Stitcher_ERR_CAMERA_PARAMS_ADJUST_FAIL: "相机参数调整失败"
                }
                error_msg = error_messages.get(status, f"拼接失败 (错误码: {status})")
                self.error.emit(error_msg)
                
        except Exception as e:
            self.error.emit(f"拼接异常: {str(e)}")


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("自动截图拼接工具")
        self.setMinimumSize(500, 400)
        
        # 设置
        self.settings = QSettings("AutoStitch", "Config")
        self.load_settings()
        
        # 状态变量
        self.temp_dir = None
        self.screenshot_thread = None
        self.stitch_thread = None
        self.selected_region = None
        self.is_capturing = False
        self.current_hotkey_str = "" # 用于存储当前注册的快捷键字符串
        
        # 创建UI
        self.setup_ui()
        
        # 注册全局快捷键
        self.register_hotkey()
        
    def setup_ui(self):
        """创建用户界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # 快捷键设置组
        hotkey_group = QGroupBox("快捷键设置")
        hotkey_layout = QFormLayout()
        
        self.hotkey_edit = QKeySequenceEdit()
        self.hotkey_edit.setKeySequence(self.hotkey)
        hotkey_layout.addRow("触发快捷键:", self.hotkey_edit)
        
        save_hotkey_btn = QPushButton("保存快捷键")
        save_hotkey_btn.clicked.connect(self.save_hotkey)
        hotkey_layout.addRow(save_hotkey_btn)
        
        hotkey_group.setLayout(hotkey_layout)
        layout.addWidget(hotkey_group)
        
        # 截图设置组
        screenshot_group = QGroupBox("截图设置")
        screenshot_layout = QFormLayout()
        
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(100, 10000)
        self.interval_spin.setValue(self.interval)
        self.interval_spin.setSuffix(" 毫秒")
        screenshot_layout.addRow("截图间隔:", self.interval_spin)
        
        screenshot_group.setLayout(screenshot_layout)
        layout.addWidget(screenshot_group)
        
        # 状态显示
        status_group = QGroupBox("状态")
        status_layout = QVBoxLayout()
        
        self.status_label = QLabel("就绪")
        self.status_label.setWordWrap(True)
        status_layout.addWidget(self.status_label)
        
        self.count_label = QLabel("截图数量: 0")
        status_layout.addWidget(self.count_label)
        
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        # 操作按钮
        button_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("开始选择区域")
        self.start_btn.clicked.connect(self.start_selection)
        button_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("停止并拼接")
        self.stop_btn.clicked.connect(self.stop_and_stitch)
        self.stop_btn.setEnabled(False)
        button_layout.addWidget(self.stop_btn)
        
        layout.addLayout(button_layout)
        
        # 说明
        help_label = QLabel(
            "使用说明:\n"
            "1. 设置快捷键并保存\n"
            "2. 按下快捷键,全屏出现蒙版\n"
            "3. 用鼠标拖动选择截图区域\n"
            "4. 松开鼠标后自动开始连续截图\n"
            "5. 再次按下快捷键停止并自动拼接\n"
            "6. 拼接结果自动复制到剪贴板"
        )
        help_label.setStyleSheet("color: gray; font-size: 10pt;")
        help_label.setWordWrap(True)
        layout.addWidget(help_label)
        
        layout.addStretch()
        
    def load_settings(self):
        """加载设置"""
        self.hotkey = QKeySequence(
            self.settings.value("hotkey", "Ctrl+Shift+A")
        )
        self.interval = int(self.settings.value("interval", 500))
        
    def save_settings(self):
        """保存设置"""
        self.settings.setValue("hotkey", self.hotkey.toString())
        self.settings.setValue("interval", self.interval)
        
    def save_hotkey(self):
        """保存快捷键"""
        new_hotkey = self.hotkey_edit.keySequence()
        if new_hotkey.isEmpty():
            QMessageBox.warning(self, "警告", "快捷键不能为空")
            return
            
        self.hotkey = new_hotkey
        self.settings.setValue("hotkey", self.hotkey.toString())
        self.register_hotkey()
        QMessageBox.information(self, "成功", f"快捷键已设置为: {self.hotkey.toString()}")
        
    def register_hotkey(self):
        """注册全局快捷键"""
        try:
            # 移除之前的快捷键
            if self.current_hotkey_str:
                keyboard.remove_hotkey(self.current_hotkey_str)

            hotkey_str = self.hotkey.toString().lower()
            
            # keyboard 库在 Windows 下可能需要管理员权限才能监听
            keyboard.add_hotkey(
                hotkey_str,
                lambda: QTimer.singleShot(0, self.toggle_capture)
            )
            
            self.current_hotkey_str = hotkey_str
            self.status_label.setText(f"就绪。快捷键: {self.hotkey.toString()}")

        except Exception as e:
            self.status_label.setText(f"快捷键注册失败: {e}")
            QMessageBox.warning(
                self, "快捷键错误", 
                f"无法注册全局快捷键: {e}\n\n"
                "请尝试以管理员身份运行此程序。\n"
                "你也可以更换快捷键或使用界面按钮操作。"
            )
            
    def toggle_capture(self):
        """切换截图状态"""
        # 确保窗口不在最小化状态
        if self.isMinimized():
            self.showNormal()
        self.activateWindow()

        if self.is_capturing:
            # 正在截图，停止并拼接
            self.stop_and_stitch()
        else:
            # 开始选择区域
            self.start_selection()
            
    def start_selection(self):
        """开始选择区域"""
        # 隐藏主窗口以避免干扰
        self.hide()
        # 稍作延迟以确保窗口完全隐藏
        QTimer.singleShot(150, self._show_overlay)

    def _show_overlay(self):
        """显示蒙版"""
        self.overlay = OverlayWindow()
        self.overlay.region_selected.connect(self.on_region_selected)
        self.overlay.cancelled.connect(self.on_selection_cancelled)
        self.overlay.showFullScreen()
        
    def on_region_selected(self, region: QRect):
        """区域选择完成"""
        self.show() # 恢复主窗口
        self.selected_region = region
        self.start_screenshot()
        
    def on_selection_cancelled(self):
        """区域选择取消"""
        self.show() # 恢复主窗口
        self.status_label.setText("已取消选择")
        
    def on_screenshot_progress(self, count: int):
        """截图进度更新"""
        self.count_label.setText(f"截图数量: {count}")
        
    def on_screenshot_finished(self):
        """截图完成"""
        pass
        
    def stop_and_stitch(self):
        """停止截图并开始拼接"""
        if not self.is_capturing:
            return
            
        # 停止截图
        if self.screenshot_thread:
            self.screenshot_thread.stop()
            self.screenshot_thread.wait()
            
        self.is_capturing = False
        self.stop_btn.setEnabled(False)
        self.status_label.setText("正在拼接...")
        
        # 开始拼接
        if self.temp_dir and os.path.exists(self.temp_dir):
            self.stitch_thread = StitchThread(self.temp_dir)
            self.stitch_thread.progress.connect(self.on_stitch_progress)
            self.stitch_thread.finished.connect(self.on_stitch_finished)
            self.stitch_thread.error.connect(self.on_stitch_error)
            self.stitch_thread.start()
        else:
            self.on_stitch_error("临时目录不存在")
            
    def on_stitch_progress(self, message: str):
        """拼接进度更新"""
        self.status_label.setText(message)
        
    def on_stitch_finished(self, result: np.ndarray):
        """拼接完成"""
        self.status_label.setText("拼接完成，正在复制到剪贴板...")
        
        # 保存临时文件
        temp_output = os.path.join(self.temp_dir, "stitched_result.png")
        cv2.imwrite(temp_output, result)
        
        # 复制到剪贴板
        self.copy_image_to_clipboard(temp_output)
        
        self.status_label.setText("完成！图片已复制到剪贴板")
        self.start_btn.setEnabled(True)
        
        # 清理临时文件（延迟删除）
        QTimer.singleShot(5000, lambda: self.cleanup_temp_dir())
        
        QMessageBox.information(self, "成功", "拼接完成！图片已复制到剪贴板")
        
    def on_stitch_error(self, error: str):
        """拼接错误"""
        self.status_label.setText(f"错误: {error}")
        self.start_btn.setEnabled(True)
        QMessageBox.warning(self, "拼接失败", error)
        self.cleanup_temp_dir()
        
    def copy_image_to_clipboard(self, image_path: str):
        """将图片复制到剪贴板"""
        try:
            from PIL import Image
            
            # 读取图片
            image = Image.open(image_path)
            
            # 转换为 BMP 格式（Windows 剪贴板）
            output = BytesIO()
            image.convert('RGB').save(output, 'BMP')
            data = output.getvalue()[14:]  # BMP 文件头是 14 字节
            output.close()
            
            # 复制到剪贴板
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
            win32clipboard.CloseClipboard()
            
        except Exception as e:
            print(f"复制到剪贴板失败: {e}")
            QMessageBox.warning(self, "警告", f"复制到剪贴板失败: {e}")
            
    def cleanup_temp_dir(self):
        """清理临时目录"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except Exception as e:
                print(f"清理临时目录失败: {e}")
                
    def closeEvent(self, event):
        """关闭事件"""
        # 清理所有快捷键
        keyboard.unhook_all()
            
        # 停止线程
        if self.screenshot_thread and self.screenshot_thread.isRunning():
            self.screenshot_thread.stop()
            self.screenshot_thread.wait()
            
        if self.stitch_thread and self.stitch_thread.isRunning():
            self.stitch_thread.wait()
            
        # 清理临时文件
        self.cleanup_temp_dir()
        
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("自动截图拼接工具")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
