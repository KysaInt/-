"""
自动截图拼接工具 (Auto Screenshot Stitch)
用于连续截取屏幕指定区域的截图,然后自动拼接成一张全景图
"""

import sys
import os
import subprocess
import importlib.util
import time
import tempfile
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
    'keyboard': '0.13.5'  # 使用 keyboard 库处理全局快捷键
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
            
            # 检查版本 - 不同模块的版本获取方式不同
            try:
                # 特殊处理某些模块
                if module_name == 'cv2':
                    import cv2
                    current_version = cv2.__version__
                elif module_name == 'PIL':
                    from PIL import Image
                    current_version = Image.__version__ if hasattr(Image, '__version__') else Image.PILLOW_VERSION
                elif module_name == 'win32clipboard':
                    # pywin32 不检查版本,只要能导入就行
                    import win32clipboard
                    current_version = required_version  # 跳过版本检查
                else:
                    module = __import__(module_name)
                    current_version = getattr(module, '__version__', None)
                
                # 如果无法获取版本,认为模块存在且版本满足
                if current_version is None:
                    continue
                
                # 版本比较
                if compare_versions(current_version, required_version) < 0:
                    outdated.append((module_name, current_version, required_version))
            except Exception as e:
                # 如果无法获取版本，认为模块存在但版本未知，不强制升级
                if DEBUG:
                    print(f"  警告: 无法获取 {module_name} 的版本: {e}")
                pass
                
        except (ImportError, ModuleNotFoundError):
            missing.append((module_name, required_version))
        except Exception as e:
            # 其他异常忽略，避免误报
            if DEBUG:
                print(f"  警告: 检查 {module_name} 时出错: {e}")
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

# 安装锁定文件 - 防止重复安装
INSTALL_LOCK_FILE = os.path.join(tempfile.gettempdir(), 'autostitch_install.lock')

def is_install_in_progress():
    """检查是否正在安装"""
    if os.path.exists(INSTALL_LOCK_FILE):
        # 检查锁文件是否过期(超过10分钟)
        try:
            mtime = os.path.getmtime(INSTALL_LOCK_FILE)
            if time.time() - mtime < 600:  # 10分钟
                return True
            else:
                # 锁文件过期,删除
                os.remove(INSTALL_LOCK_FILE)
        except:
            pass
    return False

def create_install_lock():
    """创建安装锁"""
    try:
        with open(INSTALL_LOCK_FILE, 'w') as f:
            f.write(str(os.getpid()))
    except:
        pass

def remove_install_lock():
    """删除安装锁"""
    try:
        if os.path.exists(INSTALL_LOCK_FILE):
            os.remove(INSTALL_LOCK_FILE)
    except:
        pass

if DEBUG:
    print("=" * 60)
    print("依赖检查开始...")
    print("=" * 60)

# 检查是否正在安装
if is_install_in_progress():
    if DEBUG:
        print("检测到正在安装依赖,跳过检查")
    # 正在安装中,跳过检查(可能是刚刚重启)
    missing, outdated = [], []
else:
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
        # 创建安装锁
        create_install_lock()
        
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
                    # 删除安装锁
                    remove_install_lock()
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
                        # 删除安装锁
                        remove_install_lock()
                
                def restart_program(self):
                    """重启程序"""
                    self.root.destroy()
                    
                    # 等待一会儿,让安装锁过期或者删除
                    time.sleep(1)
                    
                    # 删除安装锁(让下次启动能正常检查)
                    remove_install_lock()
                    
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

import shutil
import datetime
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
import threading


# ============================================================================
# 阶段 2.5: 管理员权限检查
# ============================================================================

def check_and_request_admin_privileges():
    """检查并请求管理员权限（确保快捷键有效）"""
    import ctypes
    import sys
    
    try:
        # 检查是否已有管理员权限
        if ctypes.windll.shell32.IsUserAnAdmin():
            print("✓ 已获得管理员权限")
            return True
        else:
            print("⚠ 未获得管理员权限，尝试重启...")
            # 重启程序并请求管理员权限
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, " ".join(sys.argv), None, 1
            )
            sys.exit(0)
    except Exception as e:
        print(f"⚠ 管理员权限检查失败: {e}")
        # 继续执行，但快捷键可能不可用
        return False


# 在主程序启动时请求管理员权限
check_and_request_admin_privileges()


# ============================================================================
# 阶段 3: 预处理与边界检测
# ============================================================================

class ScrollBoundaryDetector:
    """
    检测滚动内容的边界
    识别不同帧之间的相同部分和不同部分,自动生成裁切边界
    
    工作原理：
    1. 比较相邻帧的差异,找到变化最大的区域（内容滚动区）
    2. 找到不变的区域（固定UI: 顶部导航栏、底部菜单等）
    3. 计算应该裁切的上下边界以移除固定UI
    """
    
    def __init__(self):
        self.overlap_threshold = 0.85  # 重叠相似度阈值
        self.debug = False  # 调试模式
    
    def detect_boundaries(self, images: List[np.ndarray]) -> Tuple[int, int]:
        """
        检测滚动内容的上下边界
        返回: (top_crop, bottom_crop) - 推荐的裁切高度（像素）
        """
        if len(images) < 2:
            print("⚠️ 图片数量不足，无法检测边界，返回默认值")
            return 0, 0
        
        print(f"\n{'='*60}")
        print(f"🔍 开始检测滚动边界，共 {len(images)} 张图片...")
        print(f"{'='*60}")
        
        h, w = images[0].shape[:2]
        print(f"📏 图片尺寸: {w}x{h}")
        
        # 方法1: 基于帧差异的边界检测
        top_crop_1, bottom_crop_1 = self._detect_by_frame_diff(images)
        
        # 方法2: 基于边缘检测的边界检测
        top_crop_2, bottom_crop_2 = self._detect_by_edge_analysis(images)
        
        # 综合两种方法的结果
        top_crop = max(top_crop_1, top_crop_2)
        bottom_crop = max(bottom_crop_1, bottom_crop_2)
        
        # 验证边界的合理性
        if top_crop + bottom_crop >= h:
            print(f"⚠️ 检测到的边界过大，调整为安全值")
            top_crop = int(h * 0.05)
            bottom_crop = int(h * 0.05)
        
        print(f"\n✅ 最终检测结果:")
        print(f"   顶部固定UI: {top_crop}px")
        print(f"   底部固定UI: {bottom_crop}px")
        print(f"   内容区域: {h - top_crop - bottom_crop}px")
        print(f"{'='*60}\n")
        
        return top_crop, bottom_crop
    
    def _detect_by_frame_diff(self, images: List[np.ndarray]) -> Tuple[int, int]:
        """基于帧差异检测边界"""
        h, w = images[0].shape[:2]
        
        # 收集所有变化行
        change_rows = set()
        total_changes = 0
        
        for i in range(len(images) - 1):
            current = images[i].astype(np.float32)
            next_frame = images[i + 1].astype(np.float32)
            
            # 确保同一高度
            if current.shape[0] != next_frame.shape[0]:
                next_frame = cv2.resize(next_frame, (current.shape[1], current.shape[0]))
            
            # 计算帧之间的差异（RGB差异）
            diff = cv2.absdiff(current, next_frame)
            
            # 按行统计差异强度（计算每一行的平均差异）
            row_diff = np.mean(diff, axis=(1, 2))  # 平均所有通道和列
            total_changes += np.mean(row_diff)
            
            # 动态阈值：使用百分比而不是固定值
            threshold = np.mean(row_diff) * 0.25  # 降低阈值以捕捉更多变化
            changed_rows = np.where(row_diff > threshold)[0]
            change_rows.update(changed_rows.tolist())
        
        if not change_rows:
            print("  📊 [方法1] 未检测到显著变化")
            return 0, 0
        
        change_rows_sorted = sorted(list(change_rows))
        print(f"  📊 [方法1] 检测到 {len(change_rows_sorted)} 行变化")
        
        # 寻找变化最密集的区间（内容区）
        h_changed = change_rows_sorted[-1] - change_rows_sorted[0]
        print(f"  📊 [方法1] 变化范围: {change_rows_sorted[0]}-{change_rows_sorted[-1]} ({h_changed}px)")
        
        # 顶部固定UI：从顶部到第一个变化行
        top_crop = change_rows_sorted[0]
        
        # 底部固定UI：从最后一个变化行到底部
        bottom_crop = h - change_rows_sorted[-1]
        
        print(f"  📊 [方法1] 结果 -> top={top_crop}, bottom={bottom_crop}")
        
        return top_crop, bottom_crop
    
    def _detect_by_edge_analysis(self, images: List[np.ndarray]) -> Tuple[int, int]:
        """基于边缘检测的边界检测（辅助方法）"""
        h, w = images[0].shape[:2]
        
        # 使用Canny边缘检测在整个序列中找到变化
        edge_rows = set()
        
        for img in images[:min(3, len(images))]:  # 只用前3张
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            
            # 找到有边缘的行
            rows_with_edges = np.where(np.sum(edges, axis=1) > 0)[0]
            edge_rows.update(rows_with_edges.tolist())
        
        if not edge_rows:
            print(f"  🔲 [方法2] 未检测到明显边缘")
            return 0, 0
        
        edge_rows_sorted = sorted(list(edge_rows))
        print(f"  🔲 [方法2] 检测到 {len(edge_rows_sorted)} 行有边缘")
        
        # 找到最大的无边缘区间
        # 理论：顶部导航栏、底部菜单等固定UI通常有很多边缘
        
        top_crop = 0
        bottom_crop = 0
        
        # 检查顶部是否有明显的无内容区域
        if edge_rows_sorted[0] > int(h * 0.15):  # 顶部有15%以上的无边缘区域
            top_crop = int(edge_rows_sorted[0] * 0.8)  # 取80%的位置
        
        # 检查底部
        if h - edge_rows_sorted[-1] > int(h * 0.15):
            bottom_crop = int((h - edge_rows_sorted[-1]) * 0.8)
        
        print(f"  🔲 [方法2] 结果 -> top={top_crop}, bottom={bottom_crop}")
        
        return top_crop, bottom_crop
    
    def crop_images(self, images: List[np.ndarray], top_crop: int, 
                   bottom_crop: int) -> List[np.ndarray]:
        """根据边界裁切所有图片"""
        if not images:
            return images
        
        h = images[0].shape[0]
        crop_start = top_crop
        crop_end = h - bottom_crop
        
        if crop_end <= crop_start:
            print(f"\n⚠️ 裁切范围无效 (crop_start={crop_start} >= crop_end={crop_end})")
            print(f"   将使用原始图片（未进行裁切）")
            return images
        
        if crop_start == 0 and bottom_crop == 0:
            print(f"\n⏭️ 边界为0，跳过裁切处理")
            return images
        
        cropped = []
        print(f"\n✂️ 开始裁切 {len(images)} 张图片...")
        print(f"   裁切范围: y={crop_start} 到 y={crop_end}")
        print(f"   新高度: {crop_end - crop_start}px")
        
        for i, img in enumerate(images):
            if i % 5 == 0 or i == len(images) - 1:  # 每5张或最后一张输出日志
                print(f"   [{i+1}/{len(images)}] 裁切中...", end='\r')
            
            cropped_img = img[crop_start:crop_end, :]
            cropped.append(cropped_img)
        
        print(f"   ✅ 裁切完成: {len(images)} 张图片从 {h}px -> {crop_end-crop_start}px\n")
        
        return cropped


# ============================================================================
# 阶段 4: 截图工作线程
# ============================================================================

class ScreenshotThread(QThread):
    """截图线程 - 全屏截图"""
    
    screenshot_taken = Signal(int)  # 已截取的图片数量
    error_occurred = Signal(str)
    
    def __init__(self, interval: float, output_dir: str):
        super().__init__()
        self.interval = interval
        self.output_dir = output_dir
        self.is_running = True
        self.screenshot_count = 0
    
    def run(self):
        """运行全屏截图"""
        try:
            print("开始全屏截图...")
            
            while self.is_running:
                try:
                    # 全屏截图
                    screenshot = ImageGrab.grab()
                    
                    # 保存截图
                    self.screenshot_count += 1
                    filename = os.path.join(
                        self.output_dir,
                        f"screenshot_{self.screenshot_count:04d}.png"
                    )
                    screenshot.save(filename)
                    
                    print(f"已截图 {self.screenshot_count}: {screenshot.size}")
                    
                    # 发送信号
                    self.screenshot_taken.emit(self.screenshot_count)
                    
                    # 等待间隔时间
                    time.sleep(self.interval)
                    
                except Exception as e:
                    print(f"单次截图失败: {e}")
                    # 继续下一次截图,不中断整个流程
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
    """图像拼接线程 - 带有预处理和边界检测"""
    
    progress_updated = Signal(int)  # 进度百分比
    stitch_completed = Signal(str)  # 拼接完成,返回结果图片路径
    error_occurred = Signal(str)
    
    def __init__(self, image_dir: str):
        super().__init__()
        self.image_dir = image_dir
        self.stitcher = None
        self.images = None
    
    def cleanup(self):
        """清理资源"""
        try:
            if self.images:
                self.images.clear()
                self.images = None
            self.stitcher = None
            # 强制垃圾回收
            import gc
            gc.collect()
        except Exception as e:
            print(f"清理资源失败: {e}")
    
    def run(self):
        """运行拼接"""
        import gc
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
            
            print(f"找到 {len(image_files)} 张图片，开始加载...")
            
            # 阶段1: 加载图片
            self.progress_updated.emit(15)
            images = []
            max_width = 0
            max_height = 0
            
            print(f"\n{'='*60}")
            print(f"📂 阶段 1: 加载图片文件")
            print(f"{'='*60}")
            
            for idx, filename in enumerate(image_files):
                filepath = os.path.join(self.image_dir, filename)
                try:
                    # 使用 IMREAD_COLOR 确保读取的是 3 通道 BGR 图像
                    # 使用 IMREAD_UNCHANGED 会保留图像的原始格式（包括 alpha 通道）
                    # 但为了保险起见，用 IMREAD_COLOR 确保 BGR 格式
                    img = cv2.imread(filepath, cv2.IMREAD_COLOR)
                    
                    if img is not None:
                        h, w = img.shape[:2]
                        max_width = max(max_width, w)
                        max_height = max(max_height, h)
                        images.append(img)
                        
                        if (idx + 1) % 5 == 0 or idx == 0 or idx == len(image_files) - 1:
                            print(f"  [{idx+1:3d}/{len(image_files)}] ✓ {filename:30s} - {w}x{h}")
                    else:
                        print(f"  [❌] 无法读取: {filename}")
                except Exception as e:
                    print(f"  [❌] 加载失败 {filename}: {e}")
            
            if len(images) < 2:
                self.error_occurred.emit(f"❌ 没有足够的有效图片 (仅 {len(images)} 张)")
                return
            
            print(f"\n✅ 成功加载 {len(images)} 张有效图片")
            print(f"   原始尺寸范围: {max_width}x{max_height}")
            print(f"{'='*60}\n")
            
            # 阶段2: 优化图片大小
            self.progress_updated.emit(25)
            max_dimension = 1200
            
            print(f"\n{'='*60}")
            print(f"🔍 阶段 2: 优化图片大小")
            print(f"{'='*60}")
            
            if max_width > max_dimension or max_height > max_dimension:
                scale = min(max_dimension / max_width, max_dimension / max_height)
                print(f"  需要缩放: {scale:.3f} ({max_width}x{max_height} -> ~{int(max_width*scale)}x{int(max_height*scale)})")
                
                optimized_images = []
                for i, img in enumerate(images):
                    h, w = img.shape[:2]
                    new_w = int(w * scale)
                    new_h = int(h * scale)
                    
                    # 使用 INTER_AREA 进行高质量缩小
                    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
                    optimized_images.append(resized)
                    
                    if (i + 1) % 5 == 0 or i == 0 or i == len(images) - 1:
                        print(f"  [{i+1:3d}/{len(images)}] {w}x{h} -> {new_w}x{new_h}")
                    
                    del img
                    gc.collect()
                
                images = optimized_images
                del optimized_images
                print(f"✅ 图片优化完成")
            else:
                print(f"  ✓ 图片尺寸合理，无需缩放")
            
            gc.collect()
            print(f"{'='*60}\n")
            
            # 阶段3: 预处理 - 检测滚动边界
            self.progress_updated.emit(35)
            print("🔧 阶段 3: 预处理 - 检测滚动边界...")
            
            detector = ScrollBoundaryDetector()
            top_crop, bottom_crop = detector.detect_boundaries(images)
            
            print(f"根据检测结果进行裁切...")
            cropped_images = detector.crop_images(images, top_crop, bottom_crop)
            
            # 释放原始图片内存
            images.clear()
            gc.collect()
            images = cropped_images
            
            if len(images) < 2:
                self.error_occurred.emit("❌ 裁切后没有足够的图片")
                return
            
            print(f"\n✅ 裁切完成，准备拼接 {len(images)} 张图片...")
            
            # 阶段4: 拼接
            self.progress_updated.emit(50)
            
            print(f"\n{'='*60}")
            print(f"🧩 阶段 4: 执行图像拼接")
            print(f"{'='*60}")
            
            try:
                # 使用 SCANS 模式(适合有序截图)
                stitcher = cv2.Stitcher.create(cv2.Stitcher_SCANS)
                print("✓ 拼接器创建成功 (SCANS 模式)")
            except Exception as e:
                print(f"⚠️ SCANS 模式失败: {e}，尝试默认模式...")
                try:
                    stitcher = cv2.Stitcher.create()
                    print("✓ 拼接器创建成功 (默认模式)")
                except Exception as e2:
                    print(f"❌ 默认模式也失败: {e2}")
                    self.error_occurred.emit(f"❌ 无法创建拼接器: {str(e2)}")
                    return
            
            # 执行拼接
            self.progress_updated.emit(65)
            print(f"📊 处理 {len(images)} 张图片...")
            
            stitched = None
            try:
                print(f"处理 {len(images)} 张图片...")
                
                if len(images) == 0:
                    raise ValueError("没有图片可拼接")
                
                if len(images) == 1:
                    stitched = images[0]
                    print("只有一张图片,直接使用")
                else:
                    # 逐张拼接
                    result = images[0].copy()
                    print(f"初始图片: {result.shape}")
                    
                    for i in range(1, len(images)):
                        current_img = images[i]
                        print(f"正在与第 {i+1} 张图片进行拼接 (形状: {current_img.shape})...")
                        
                        try:
                            h_result, w_result = result.shape[:2]
                            h_current, w_current = current_img.shape[:2]
                            
                            # 统一高度
                            if h_current != h_result:
                                scale = h_result / h_current
                                w_current_scaled = int(w_current * scale)
                                current_img = cv2.resize(current_img, (w_current_scaled, h_result), 
                                                        interpolation=cv2.INTER_AREA)
                                print(f"  调整第 {i+1} 张高度: {h_current} -> {h_result}")
                            
                            # 计算最佳重叠
                            overlap_width = int(w_result * 0.15)
                            right_region = result[:, max(0, w_result - overlap_width):]
                            left_region = current_img[:, :min(overlap_width, w_current)]
                            
                            if left_region.shape[1] < overlap_width:
                                overlap_width = left_region.shape[1]
                            
                            # 寻找最佳对齐点
                            best_offset = 0
                            best_score = float('inf')
                            
                            for offset in range(0, overlap_width, max(1, overlap_width // 5)):
                                if offset < w_result and offset < w_current:
                                    end_x = min(w_result - offset, w_current)
                                    if end_x > 0:
                                        region1 = result[:, w_result - end_x:]
                                        region2 = current_img[:, :end_x]
                                        
                                        diff = cv2.absdiff(region1, region2).astype(float)
                                        mse = np.mean(diff ** 2)
                                        
                                        if mse < best_score:
                                            best_score = mse
                                            best_offset = offset
                            
                            print(f"  最佳重叠偏移: {best_offset}, 相似度分数: {best_score:.2f}")
                            
                            # 创建拼接结果
                            new_width = w_result + w_current - best_offset
                            new_height = max(h_result, h_current)
                            stitched_pair = np.zeros((new_height, new_width, 3), dtype=np.uint8)
                            
                            stitched_pair[:result.shape[0], :w_result] = result
                            start_x = w_result - best_offset
                            stitched_pair[:current_img.shape[0], start_x:start_x + w_current] = current_img
                            
                            result = stitched_pair
                            print(f"  拼接完成, 当前尺寸: {result.shape}")
                            
                            gc.collect()
                            
                        except Exception as e:
                            print(f"  拼接第 {i+1} 张出错: {e}")
                            try:
                                max_h = max(result.shape[0], current_img.shape[0])
                                fallback = np.zeros((max_h, result.shape[1] + current_img.shape[1], 3), 
                                                   dtype=np.uint8)
                                fallback[:result.shape[0], :result.shape[1]] = result
                                fallback[:current_img.shape[0], result.shape[1]:] = current_img
                                result = fallback
                                print(f"  使用降级方案(并排放置): {result.shape}")
                            except:
                                print(f"  降级方案也失败了,继续使用当前结果")
                                continue
                    
                    stitched = result
                    print(f"最终拼接完成: {stitched.shape}")
                    
            except Exception as e:
                print(f"拼接执行异常: {e}")
                import traceback
                traceback.print_exc()
                self.error_occurred.emit(f"拼接执行异常: {str(e)}")
                return
            
            if stitched is not None:
                # 保存结果
                self.progress_updated.emit(90)
                output_path = os.path.join(self.image_dir, "stitched_result.png")
                
                try:
                    print(f"\n{'='*60}")
                    print(f"💾 准备保存拼接结果")
                    print(f"   尺寸: {stitched.shape}")
                    print(f"   输出路径: {output_path}")
                    print(f"{'='*60}")
                    
                    # 确保图像数据类型正确（必须是uint8）
                    if stitched.dtype != np.uint8:
                        print(f"⚠️ 转换数据类型: {stitched.dtype} -> uint8")
                        if stitched.dtype == np.float32 or stitched.dtype == np.float64:
                            # 浮点数转整数
                            stitched = np.clip(stitched * 255, 0, 255).astype(np.uint8)
                        else:
                            stitched = stitched.astype(np.uint8)
                    
                    # 使用高质量 PNG 压缩（压缩等级 9，无损质量）
                    # PNG 压缩等级: 0-9，值越大压缩率越高，但都是无损压缩
                    # 9 是最大压缩，但保证图像质量不损失
                    success = cv2.imwrite(
                        output_path, 
                        stitched, 
                        [cv2.IMWRITE_PNG_COMPRESSION, 9]
                    )
                    
                    if not success:
                        self.error_occurred.emit("❌ 无法保存拼接结果（cv2.imwrite 返回 False）")
                        return
                    
                    # 验证文件已保存
                    if not os.path.exists(output_path):
                        self.error_occurred.emit("❌ 保存的文件不存在")
                        return
                    
                    file_size = os.path.getsize(output_path)
                    file_size_mb = file_size / 1024 / 1024
                    
                    print(f"\n✅ 拼接结果已保存")
                    print(f"   文件路径: {output_path}")
                    print(f"   文件大小: {file_size_mb:.2f} MB ({file_size:,} bytes)")
                    print(f"   图像尺寸: {stitched.shape[1]}x{stitched.shape[0]} (宽x高)")
                    print(f"   压缩方式: PNG (无损压缩，质量 9/9)")
                    print(f"{'='*60}\n")
                        
                except Exception as e:
                    print(f"\n❌ 保存拼接结果失败: {e}")
                    import traceback
                    traceback.print_exc()
                    self.error_occurred.emit(f"保存拼接结果失败: {str(e)}")
                    return
                
                self.progress_updated.emit(100)
                self.stitch_completed.emit(output_path)
            else:
                print(f"拼接失败: 结果为空")
                self.error_occurred.emit("拼接失败：结果为空")
        
        except MemoryError as e:
            print(f"线程内存错误: {e}")
            import traceback
            traceback.print_exc()
            self.error_occurred.emit(f"内存不足: {str(e)}")
        except Exception as e:
            print(f"拼接过程中发生异常: {e}")
            import traceback
            traceback.print_exc()
            self.error_occurred.emit(f"拼接过程出错: {str(e)}")
        finally:
            # 清理资源
            self.cleanup()


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
        self.selected_area = None  # 已弃用，仅保留兼容性
        self.temp_dir = None
        self.screenshot_thread = None
        self.stitch_thread = None
        self.overlay_window = None  # 已弃用
        
        # 全局快捷键
        self.hotkey = self.settings.value('hotkey', 'ctrl+shift+a')
        self.hotkey_listener = None
        
        self.setup_ui()
        self.load_settings()
        self.setup_hotkey()
    
    def setup_ui(self):
        """设置界面"""
        self.setWindowTitle("全屏截图拼接")
        self.setMinimumSize(380, 280)
        self.setMaximumSize(420, 320)
        
        # 中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(12, 12, 12, 12)
        
        # 设置组
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
        self.interval_spinbox.setValue(0.2)
        self.interval_spinbox.setSuffix(" 秒")
        self.interval_spinbox.setFont(QFont("Microsoft YaHei", 9))
        self.interval_spinbox.setMaximumWidth(80)
        interval_layout.addWidget(self.interval_spinbox)
        
        self.auto_copy_checkbox = QCheckBox("自动复制")
        self.auto_copy_checkbox.setChecked(True)
        self.auto_copy_checkbox.setFont(QFont("Microsoft YaHei", 9))
        interval_layout.addWidget(self.auto_copy_checkbox)
        
        self.top_most_checkbox = QCheckBox("置顶")
        self.top_most_checkbox.setChecked(False)
        self.top_most_checkbox.setFont(QFont("Microsoft YaHei", 9))
        self.top_most_checkbox.stateChanged.connect(self.toggle_top_most)
        interval_layout.addWidget(self.top_most_checkbox)
        
        interval_layout.addStretch()
        
        settings_layout.addRow("间隔:", interval_widget)
        
        # 快捷键
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
        
        # 开始按钮
        self.start_btn = QPushButton("开始全屏截图")
        self.start_btn.setFont(QFont("Microsoft YaHei", 10))
        self.start_btn.setMinimumHeight(40)
        self.start_btn.setStyleSheet("""
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
        self.start_btn.clicked.connect(self.start_screenshot)
        main_layout.addWidget(self.start_btn)
        
        # 停止按钮
        self.stop_btn = QPushButton("停止并拼接")
        self.stop_btn.setFont(QFont("Microsoft YaHei", 10))
        self.stop_btn.setMinimumHeight(40)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
            }
        """)
        self.stop_btn.clicked.connect(self.stop_and_stitch)
        main_layout.addWidget(self.stop_btn)
        
        # 隐藏的按钮（保留兼容性）
        self.select_area_btn = QPushButton()
        self.select_area_btn.setVisible(False)
        self.start_screenshot_btn = QPushButton()
        self.start_screenshot_btn.setVisible(False)
        self.stop_and_stitch_btn = QPushButton()
        self.stop_and_stitch_btn.setVisible(False)
        
        # 状态组
        status_group = QGroupBox("状态")
        status_group.setFont(QFont("Microsoft YaHei", 9, QFont.Bold))
        status_layout = QVBoxLayout()
        status_layout.setSpacing(6)
        status_layout.setContentsMargins(8, 8, 8, 8)
        
        # 截图计数
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
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFont(QFont("Microsoft YaHei", 8))
        self.progress_bar.setMaximumHeight(16)
        status_layout.addWidget(self.progress_bar)
        
        status_group.setLayout(status_layout)
        main_layout.addWidget(status_group)
        
        # 提示信息
        hint_label = QLabel(f"按 {self.hotkey} 快速开始/停止 | 点击按钮直接开始")
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
        
        top_most = self.settings.value('top_most', False, type=bool)
        self.top_most_checkbox.setChecked(top_most)
        self.toggle_top_most()
    
    def save_settings(self):
        """保存设置"""
        self.settings.setValue('interval', self.interval_spinbox.value())
        self.settings.setValue('auto_copy', self.auto_copy_checkbox.isChecked())
        self.settings.setValue('hotkey', self.hotkey)
        self.settings.setValue('top_most', self.top_most_checkbox.isChecked())
    
    def setup_hotkey(self):
        """设置全局快捷键 - 使用 keyboard 库（需要管理员权限）"""
        try:
            # 移除旧的热键监听
            if self.hotkey_listener is not None:
                try:
                    keyboard.remove_hotkey(self.hotkey)
                    print(f"✓ 已移除旧快捷键: {self.hotkey}")
                except:
                    pass
            
            # 验证快捷键格式
            if not self.hotkey or '+' not in self.hotkey:
                print(f"❌ 无效的快捷键格式: {self.hotkey}")
                QMessageBox.warning(self, "错误", f"无效的快捷键格式: {self.hotkey}\n\n格式示例: ctrl+shift+a")
                return
            
            # 注册新的快捷键
            try:
                keyboard.add_hotkey(self.hotkey, self._hotkey_callback, suppress=False)
                self.hotkey_listener = True  # 标记已设置
                print(f"✓ 快捷键已激活: {self.hotkey}")
                QMessageBox.information(self, "成功", f"快捷键已激活: {self.hotkey}\n\n现在可以按此快捷键开始/停止")
            except ValueError as e:
                print(f"❌ 快捷键格式错误: {e}")
                QMessageBox.warning(self, "错误", f"快捷键格式错误: {e}\n\n请检查快捷键格式")
                return
            except PermissionError:
                print(f"❌ 需要管理员权限才能使用快捷键")
                QMessageBox.critical(self, "权限错误", "需要管理员权限才能使用快捷键\n\n程序已以管理员身份启动，但快捷键仍不可用。\n请尝试重启程序。")
                print(f"   请以管理员身份运行程序")
                self.hotkey_listener = False
                return
            except Exception as e:
                print(f"❌ 快捷键设置失败: {e}")
                self.hotkey_listener = False
                return
            
        except Exception as e:
            print(f"❌ 快捷键初始化失败: {e}")
            import traceback
            traceback.print_exc()
            self.hotkey_listener = False
    
    def _parse_hotkey(self, hotkey_str: str) -> list:
        """
        快捷键格式验证
        keyboard 库格式: "ctrl+shift+a", "alt+f9" 等
        无需解析，直接传给 keyboard.add_hotkey()
        """
        try:
            keys = hotkey_str.lower().split('+')
            
            # 验证格式
            for key in keys:
                key = key.strip()
                if not key:
                    print(f"快捷键格式错误: 空键值")
                    return None
                # 允许的修饰键和字母数字键
                if key not in ['ctrl', 'shift', 'alt', 'win'] and len(key) != 1:
                    if key not in ['f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 
                                  'f10', 'f11', 'f12', 'enter', 'space', 'tab', 'esc']:
                        print(f"未识别的键: {key}")
                        return None
            
            return keys
        except Exception as e:
            print(f"解析快捷键失败: {e}")
            return None
    
    def _start_listener(self):
        """已弃用 - keyboard 库自动后台监听"""
        pass
    
    def _hotkey_callback(self):
        """快捷键回调（由 keyboard 库在后台线程调用）"""
        try:
            print(f"[快捷键触发] {self.hotkey} - 触发时间: {datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
            # 使用QTimer在主线程中执行
            QTimer.singleShot(0, self.hotkey_triggered)
        except Exception as e:
            print(f"❌ 快捷键回调异常: {e}")
            import traceback
            traceback.print_exc()
    
    def update_hotkey(self):
        """更新快捷键"""
        new_hotkey = self.hotkey_edit.text().strip().lower()
        
        if not new_hotkey:
            QMessageBox.warning(self, "提示", "快捷键不能为空")
            return
        
        # 验证格式
        if '+' not in new_hotkey:
            QMessageBox.warning(self, "格式错误", "快捷键格式错误\n\n格式示例:\n• ctrl+shift+a\n• alt+f9\n• shift+f12")
            return
        
        self.hotkey = new_hotkey
        self.save_settings()
        self.setup_hotkey()
        self.hint_label.setText(f"按 {self.hotkey} 快速开始/停止 | 点击按钮直接开始")
    
    def toggle_top_most(self):
        """切换窗口置顶状态"""
        if self.top_most_checkbox.isChecked():
            # 设置窗口始终在最前端
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
            self.show()
            print("✓ 窗口已置顶")
        else:
            # 取消窗口置顶
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
            self.show()
            print("✓ 窗口已取消置顶")
        
        self.save_settings()
    
    def hotkey_triggered(self):
        """快捷键触发 - 必须在主线程中执行"""
        try:
            print("[热键事件] hotkey_triggered 被调用")
            # 根据当前状态执行不同操作
            if self.screenshot_thread and self.screenshot_thread.isRunning():
                # 正在截图 -> 停止并拼接
                print("→ 当前状态: 截图中，执行停止并拼接")
                self.stop_and_stitch()
            else:
                # 未截图 -> 直接开始截图
                print("→ 当前状态: 未截图，执行开始截图")
                self.start_screenshot()
        except Exception as e:
            print(f"❌ 快捷键处理失败: {e}")
            import traceback
            traceback.print_exc()
    
    def select_area(self):
        """已弃用 - 保留以兼容旧代码"""
        self.start_screenshot()
    
    def show_overlay(self):
        """已弃用 - 保留以兼容旧代码"""
        pass
    
    def on_overlay_closed(self):
        """已弃用 - 保留以兼容旧代码"""
        pass
    
    def on_area_selected(self, area):
        """已弃用 - 保留以兼容旧代码"""
        self.start_screenshot()
    
    def start_screenshot(self):
        """开始全屏自动截图"""
        try:
            # 如果已经在截图,先停止
            if self.screenshot_thread and self.screenshot_thread.isRunning():
                self.screenshot_thread.stop()
                if not self.screenshot_thread.wait(2000):
                    self.screenshot_thread.terminate()
                    self.screenshot_thread.wait()
            
            # 保存设置
            self.save_settings()
            
            # 创建临时目录
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            self.temp_dir = os.path.join(
                tempfile.gettempdir(),
                f"autostitch_{timestamp}"
            )
            os.makedirs(self.temp_dir, exist_ok=True)
            
            print(f"临时目录: {self.temp_dir}")
            
            # 更新界面
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.screenshot_count_label.setText("0 张")
            self.status_label.setText("截图中...")
            self.progress_bar.setVisible(False)
            
            # 启动截图线程
            interval = self.interval_spinbox.value()
            self.screenshot_thread = ScreenshotThread(
                interval,
                self.temp_dir
            )
            self.screenshot_thread.screenshot_taken.connect(self.on_screenshot_taken)
            self.screenshot_thread.error_occurred.connect(self.on_screenshot_error)
            self.screenshot_thread.start()
            
            print(f"全屏截图线程已启动，间隔: {interval} 秒")
        
        except Exception as e:
            print(f"启动截图异常: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "错误", f"启动截图失败: {str(e)}")
            self.reset_ui()
    
    def on_screenshot_taken(self, count):
        """截图完成"""
        self.screenshot_count_label.setText(f"{count} 张")
    
    def on_screenshot_error(self, error):
        """截图错误"""
        try:
            print(f"截图错误: {error}")
            QMessageBox.critical(self, "截图错误", error)
        except Exception as e:
            print(f"显示错误对话框异常: {e}")
        finally:
            self.reset_ui()
    
    def stop_and_stitch(self):
        """停止截图并拼接"""
        try:
            print("停止截图...")
            
            # 停止截图线程
            if self.screenshot_thread and self.screenshot_thread.isRunning():
                self.screenshot_thread.stop()
                # 等待线程正常退出
                if not self.screenshot_thread.wait(3000):
                    print("截图线程未能正常退出，强制终止...")
                    self.screenshot_thread.terminate()
                    self.screenshot_thread.wait(1000)
            
            print(f"截图完成，共 {self.screenshot_thread.screenshot_count if self.screenshot_thread else 0} 张")
            
            # 检查截图数量
            if not self.screenshot_thread or self.screenshot_thread.screenshot_count < 2:
                QMessageBox.warning(self, "提示", "至少需要 2 张截图才能拼接")
                self.reset_ui()
                return
            
            # 更新界面
            self.stop_and_stitch_btn.setEnabled(False)
            self.status_label.setText("拼接中...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            print(f"开始拼接 {self.screenshot_thread.screenshot_count} 张图片...")
            
            # 启动拼接线程
            self.stitch_thread = StitchThread(self.temp_dir)
            self.stitch_thread.progress_updated.connect(self.on_stitch_progress)
            self.stitch_thread.stitch_completed.connect(self.on_stitch_completed)
            self.stitch_thread.error_occurred.connect(self.on_stitch_error)
            self.stitch_thread.start()
        
        except Exception as e:
            print(f"停止和拼接过程异常: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "错误", f"处理过程出错: {str(e)}")
            self.reset_ui()
    
    def on_stitch_progress(self, progress):
        """拼接进度"""
        try:
            self.progress_bar.setValue(progress)
        except Exception as e:
            print(f"更新拼接进度异常: {e}")
    
    def on_stitch_completed(self, result_path):
        """拼接完成"""
        try:
            self.progress_bar.setVisible(False)
            self.status_label.setText("完成")
            
            print(f"拼接完成，结果路径: {result_path}")
            
            # 检查文件是否存在
            if not os.path.exists(result_path):
                QMessageBox.critical(self, "错误", "拼接结果文件不存在")
                self.reset_ui()
                return
            
            # 验证文件大小
            file_size = os.path.getsize(result_path)
            print(f"文件大小: {file_size / 1024 / 1024:.2f} MB")
            
            if file_size == 0:
                QMessageBox.critical(self, "错误", "拼接结果文件为空")
                self.reset_ui()
                return
            
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
            
            # 清理拼接线程
            if self.stitch_thread:
                self.stitch_thread.cleanup()
            
            self.reset_ui()
        except Exception as e:
            print(f"拼接完成处理异常: {e}")
            import traceback
            traceback.print_exc()
            self.reset_ui()
    
    def on_stitch_error(self, error):
        """拼接错误"""
        try:
            self.progress_bar.setVisible(False)
            
            print(f"拼接错误: {error}")
            
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
        except Exception as e:
            print(f"错误处理异常: {e}")
            self.reset_ui()
    
    def reset_ui(self):
        """重置界面"""
        try:
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
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
                            except Exception as e:
                                print(f"删除文件失败 {filepath}: {e}")
                except Exception as e:
                    print(f"清理临时文件失败: {e}")
        except Exception as e:
            print(f"重置UI异常: {e}")
    
    def closeEvent(self, event):
        """关闭事件"""
        # 停止线程
        if self.screenshot_thread and self.screenshot_thread.isRunning():
            self.screenshot_thread.stop()
            self.screenshot_thread.wait(2000)
            if self.screenshot_thread.isRunning():
                self.screenshot_thread.terminate()
                self.screenshot_thread.wait()
        
        if self.stitch_thread and self.stitch_thread.isRunning():
            self.stitch_thread.wait(2000)
            if self.stitch_thread.isRunning():
                self.stitch_thread.terminate()
                self.stitch_thread.wait()
        
        # 清理拼接线程资源
        if self.stitch_thread:
            try:
                self.stitch_thread.cleanup()
            except:
                pass
        
        # 移除快捷键（keyboard 库）
        try:
            if self.hotkey:
                keyboard.remove_hotkey(self.hotkey)
                print(f"✓ 快捷键已移除: {self.hotkey}")
        except Exception as e:
            print(f"移除快捷键失败: {e}")
        
        # 清理临时目录
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            except Exception as e:
                print(f"清理临时目录失败: {e}")
        
        # 强制垃圾回收
        try:
            import gc
            gc.collect()
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
