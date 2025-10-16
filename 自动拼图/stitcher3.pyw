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
# 阶段 3: 预处理与边界检测（改进版 - 使用标准差算法）
# ============================================================================

class ScrollBoundaryDetector:
    """
    滚动区域边界检测器 - 使用图像标准差分析
    
    工作原理：
    通过比较多张图片找到不变的区域(如状态栏、导航栏),识别出真正的滚动内容区域
    使用高斯模糊和灵敏度调节来忽略状态栏图标闪烁等小变化
    
    支持场景：
    - 顶部导航栏 + 内容 + 底部菜单
    - 只有顶部固定UI
    - 只有底部固定UI  
    - 无固定UI（纯内容）
    """
    
    def __init__(self, debug: bool = False):
        self.overlap_threshold = 0.85
        self.debug = debug
        self.detection_results = {}
        # 默认参数（可通过 detect_boundaries 调整）
        self.default_sensitivity = 1.5  # 灵敏度
        self.default_min_length = 20    # 最小连续长度
        self.default_blur_size = 11     # 模糊度
    
    def detect_boundaries(self, images: List[np.ndarray],
                         sensitivity: float = None,
                         min_length: int = None,
                         blur_size: int = None) -> Tuple[int, int]:
        """
        智能检测滚动区域边界 (使用标准差算法)
        
        Args:
            images: 图像列表
            sensitivity: 灵敏度系数 (0.5-3.0), 值越大越宽松,越能忽略小变化。默认1.5
            min_length: 连续超过阈值的最小像素数,避免误判。默认20
            blur_size: 高斯模糊核大小(奇数),越大越能忽略细节变化。默认11
        
        Returns: 
            (top_crop, bottom_crop) 上下边界的裁切像素数
        """
        # 使用默认值
        if sensitivity is None:
            sensitivity = self.default_sensitivity
        if min_length is None:
            min_length = self.default_min_length
        if blur_size is None:
            blur_size = self.default_blur_size
            
        if len(images) < 2:
            print("⚠️ 图片数量不足，返回默认值")
            return 0, 0
        
        h, w = images[0].shape[:2]
        print(f"\n{'='*60}")
        print(f"🧠 启动标准差边界检测 ({len(images)} 张 {w}x{h})")
        print(f"{'='*60}")
        
        # 使用标准差算法检测边界
        left, top, width, height = self._detect_by_std_analysis(
            images, sensitivity, min_length, blur_size
        )
        
        # 转换为 top_crop 和 bottom_crop 格式
        top_crop = top
        bottom_crop = h - (top + height)
        
        # 确保值在合理范围内
        top_crop = max(0, min(top_crop, h // 2))
        bottom_crop = max(0, min(bottom_crop, h // 2))
        
        # 最终验证: 确保裁切范围合理
        content_height = h - top_crop - bottom_crop
        if content_height < h * 0.1:  # 内容区至少占10%
            print(f"⚠️ 检测边界过大(内容区仅{content_height}px),使用保守安全值")
            top_crop = min(h // 10, 100)
            bottom_crop = min(h // 10, 100)
        elif top_crop + bottom_crop >= h:  # 不能裁完整个图片
            print(f"⚠️ 检测边界无效(top+bottom >= h),使用默认值")
            top_crop = 0
            bottom_crop = 0
        
        print(f"\n✅ 最终结果: top={top_crop}px, bottom={bottom_crop}px")
        print(f"   内容区: {h - top_crop - bottom_crop}px (占{100*(h-top_crop-bottom_crop)/h:.1f}%)")
        print(f"{'='*60}\n")
        
        return top_crop, bottom_crop
    
    def _detect_by_std_analysis(self, images: List[np.ndarray],
                                sensitivity: float = 1.5,
                                min_length: int = 20,
                                blur_size: int = 11) -> Tuple[int, int, int, int]:
        """
        标准差分析 - 通过比较多张图片找到变化区域
        
        Args:
            images: 图像列表
            sensitivity: 灵敏度系数,值越大越宽松
            min_length: 连续超过阈值的最小像素数
            blur_size: 高斯模糊核大小
        
        Returns:
            (left, top, width, height) 内容区域边界
        """
        if not images:
            return (0, 0, 100, 100)
        
        height, width = images[0].shape[:2]
        
        # 如果只有一张图片,返回全图
        if len(images) == 1:
            print(f"  📊 [标准差] 仅1张图片,返回全图")
            return (0, 0, width, height)
        
        # 确保 blur_size 是奇数
        if blur_size % 2 == 0:
            blur_size += 1
        blur_size = max(3, min(21, blur_size))
        
        print(f"  📊 [标准差] 参数: sensitivity={sensitivity:.2f}, min_length={min_length}, blur={blur_size}")
        
        # 将所有图片转换为灰度并使用高斯模糊减少噪声
        gray_images = []
        for img in images:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            # 应用高斯模糊来忽略小的变化(如图标闪烁)
            blurred = cv2.GaussianBlur(gray, (blur_size, blur_size), 0)
            gray_images.append(blurred)
        
        # 计算所有图片的标准差,变化大的区域是内容区域
        image_stack = np.stack(gray_images, axis=0)
        std_dev = np.std(image_stack, axis=0)
        
        # 归一化标准差
        std_dev_normalized = (std_dev - std_dev.min()) / (std_dev.max() - std_dev.min() + 1e-6)
        
        # 对每一行和每一列计算平均标准差
        row_std = np.mean(std_dev_normalized, axis=1)
        col_std = np.mean(std_dev_normalized, axis=0)
        
        # 对标准差进行平滑处理,避免因为噪声导致的误判
        def moving_average(data, window=11):
            if len(data) < window:
                return data
            cumsum = np.cumsum(np.insert(data, 0, 0))
            result = (cumsum[window:] - cumsum[:-window]) / window
            # 补齐长度
            pad_left = window // 2
            pad_right = window - pad_left - 1
            return np.pad(result, (pad_left, pad_right), mode='edge')
        
        row_std_smooth = moving_average(row_std, 11)
        col_std_smooth = moving_average(col_std, 11)
        
        # 使用可调节的灵敏度阈值
        row_threshold = np.mean(row_std_smooth) * sensitivity
        col_threshold = np.mean(col_std_smooth) * sensitivity
        
        # 找到连续超过阈值的区域(至少连续 min_length 像素),避免误判小的波动
        def find_content_region(std_data, threshold, min_len):
            above_threshold = std_data > threshold
            # 找到第一个连续超过阈值的区域
            start = 0
            for i in range(len(above_threshold) - min_len):
                if np.sum(above_threshold[i:i+min_len]) >= min_len * 0.8:  # 允许 20% 的容差
                    start = i
                    break
            
            # 找到最后一个连续超过阈值的区域
            end = len(above_threshold)
            for i in range(len(above_threshold) - min_len, -1, -1):
                if np.sum(above_threshold[i:i+min_len]) >= min_len * 0.8:
                    end = i + min_len
                    break
            
            return start, end
        
        # 找到内容区域(标准差大的区域)
        top_margin, bottom_margin = find_content_region(row_std_smooth, row_threshold, min_length)
        left_margin, right_margin = find_content_region(col_std_smooth, col_threshold, min_length)
        
        content_width = right_margin - left_margin
        content_height = bottom_margin - top_margin
        
        print(f"  📊 [标准差] 检测到: top={top_margin}, bottom={height-bottom_margin}, left={left_margin}, right={width-right_margin}")
        
        # 如果识别结果不合理,返回原始尺寸
        if content_width < width * 0.3 or content_height < height * 0.3:
            print(f"  ⚠️ [标准差] 识别区域过小,返回全图")
            return (0, 0, width, height)
        
        return (left_margin, top_margin, content_width, content_height)
    
    def crop_images(self, images: List[np.ndarray], top_crop: int, 
                   bottom_crop: int) -> List[np.ndarray]:
        """根据边界裁切所有图片"""
        if not images:
            return images
        
        h = images[0].shape[0]
        crop_start = max(0, top_crop)
        crop_end = min(h, h - bottom_crop)
        
        # 验证裁切范围
        if crop_end <= crop_start:
            print(f"\n⚠️ 裁切范围无效 (crop_start={crop_start} >= crop_end={crop_end})")
            print(f"   将使用原始图片（未进行裁切）")
            return images
        
        if crop_start == 0 and crop_end == h:
            print(f"\n⏭️ 边界为0，跳过裁切处理")
            return images
        
        cropped = []
        print(f"\n✂️ 开始裁切 {len(images)} 张图片...")
        print(f"   原始高度: {h}px")
        print(f"   裁切范围: y={crop_start} 到 y={crop_end}")
        print(f"   新高度: {crop_end - crop_start}px")
        
        for i, img in enumerate(images):
            # 验证当前图片高度
            current_h = img.shape[0]
            if current_h != h:
                print(f"\n⚠️ 图片 {i+1} 高度不一致 ({current_h}px vs {h}px)，调整裁切范围")
                current_crop_end = min(current_h, current_h - bottom_crop)
                current_crop_start = min(crop_start, current_crop_end - 1)
            else:
                current_crop_start = crop_start
                current_crop_end = crop_end
            
            if i % 5 == 0 or i == len(images) - 1:  # 每5张或最后一张输出日志
                print(f"   [{i+1}/{len(images)}] 裁切中...", end='\r')
            
            # 执行裁切
            if current_crop_end > current_crop_start:
                cropped_img = img[current_crop_start:current_crop_end, :]
                cropped.append(cropped_img)
            else:
                print(f"\n⚠️ 图片 {i+1} 裁切范围无效，跳过")
                cropped.append(img)  # 使用原图
        
        print(f"\n   ✅ 裁切完成: {len(images)} 张图片从 {h}px -> {crop_end-crop_start}px\n")
        
        return cropped


# ============================================================================
# 阶段 4: 截图工作线程
# ============================================================================

class ScreenshotThread(QThread):
    """截图线程 - 全屏截图"""
    
    screenshot_taken = Signal(int)  # 已截取的图片数量
    error_occurred = Signal(str)
    
    def __init__(self, interval: float, output_dir: str, stage1_dir: str):
        super().__init__()
        self.interval = interval
        self.output_dir = output_dir
        self.stage1_dir = stage1_dir  # 阶段1: 原始截图
        self.is_running = True
        self.screenshot_count = 0
    
    def run(self):
        """运行全屏截图"""
        try:
            print(f"开始全屏截图，输出到: {self.stage1_dir}")
            
            while self.is_running:
                try:
                    # 全屏截图
                    screenshot = ImageGrab.grab()
                    
                    # 保存截图到阶段1文件夹
                    self.screenshot_count += 1
                    filename = os.path.join(
                        self.stage1_dir,
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
    
    def __init__(self, image_dir: str, stage1_dir: str, stage2_dir: str, stage3_dir: str):
        super().__init__()
        self.image_dir = image_dir  # 主工作目录
        self.stage1_dir = stage1_dir  # 阶段1: 原始截图
        self.stage2_dir = stage2_dir  # 阶段2: 裁切后的图片
        self.stage3_dir = stage3_dir  # 阶段3: 最终拼接结果
        self.stitcher = None
        self.images = None
        self.debug = False  # 调试模式
    
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
    
    def _smart_stitch_pair(self, img1: np.ndarray, img2: np.ndarray, pair_idx: int) -> Optional[np.ndarray]:
        """智能拼接两张图片（使用特征点匹配+多种融合策略）"""
        try:
            h1, w1 = img1.shape[:2]
            h2, w2 = img2.shape[:2]
            
            # 1. 特征点匹配（ORB特征检测）
            best_offset = self._find_overlap_by_features(img1, img2)
            
            if best_offset is None:
                # 2. 备选：基于MSE的强力搜索
                best_offset = self._find_overlap_by_mse(img1, img2)
            
            if best_offset is None:
                print(f"  ⚠️ 无法找到可靠的重叠")
                # 3. 终极备选：并排拼接
                return self._concat_side_by_side(img1, img2)
            
            # 使用找到的偏移进行融合
            result = self._merge_with_blend(img1, img2, best_offset)
            return result
        
        except Exception as e:
            if self.debug:
                print(f"  智能拼接异常: {e}")
            return None
    
    def _find_overlap_by_features(self, img1: np.ndarray, img2: np.ndarray) -> Optional[int]:
        """使用ORB特征检测找到重叠区域"""
        try:
            gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
            
            # ORB特征检测
            orb = cv2.ORB_create(nfeatures=500, scaleFactor=1.2, nlevels=8)
            kp1, des1 = orb.detectAndCompute(gray1, None)
            kp2, des2 = orb.detectAndCompute(gray2, None)
            
            if des1 is None or des2 is None or len(kp1) < 10 or len(kp2) < 10:
                return None
            
            # 特征匹配
            bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
            matches = bf.knnMatch(des1, des2, k=2)
            
            # Lowe's ratio test
            good_matches = []
            for pair in matches:
                if len(pair) == 2:
                    m, n = pair
                    if m.distance < 0.75 * n.distance:
                        good_matches.append(m)
            
            if len(good_matches) < 5:
                return None
            
            # 计算重叠偏移
            src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
            
            # 估计水平偏移（对于纵向拼接，主要是水平偏移）
            offsets = (dst_pts[:, 0, 0] - src_pts[:, 0, 0]).astype(int)
            median_offset = int(np.median(offsets))
            
            return median_offset
        
        except Exception as e:
            return None
    
    def _find_overlap_by_mse(self, img1: np.ndarray, img2: np.ndarray, search_range: int = 100) -> Optional[int]:
        """基于MSE(均方误差)的精确重叠搜索"""
        h1, w1 = img1.shape[:2]
        h2, w2 = img2.shape[:2]
        
        # 搜索范围
        search_range = min(search_range, w1 // 5)
        if search_range < 10:
            return None
        
        best_offset = None
        best_score = float('inf')
        
        # 只检查合理的偏移范围
        for offset in range(0, min(search_range, w1), max(1, search_range // 20)):
            if offset >= w1 or offset >= w2:
                continue
            
            # 计算重叠区域
            overlap_w = min(w1 - offset, w2)
            if overlap_w < 20:
                continue
            
            region1 = img1[:h1, w1-overlap_w:w1]
            region2 = img2[:h2, :overlap_w]
            
            if region1.shape != region2.shape:
                continue
            
            # 计算MSE
            diff = cv2.absdiff(region1.astype(np.float32), region2.astype(np.float32))
            mse = np.mean(diff ** 2)
            
            if mse < best_score:
                best_score = mse
                best_offset = offset
        
        return best_offset if best_score < 10000 else None
    
    def _merge_with_blend(self, img1: np.ndarray, img2: np.ndarray, offset: int) -> np.ndarray:
        """使用混合模式融合重叠部分"""
        h1, w1 = img1.shape[:2]
        h2, w2 = img2.shape[:2]
        
        # 计算结果图片尺寸
        new_width = w1 + w2 - offset
        new_height = max(h1, h2)
        result = np.zeros((new_height, new_width, 3), dtype=np.uint8)
        
        # 放置第一张图片
        result[:h1, :w1] = img1
        
        # 计算融合区域
        blend_start = w1 - offset
        blend_width = offset
        
        if blend_width > 0:
            # 在重叠区使用渐变混合
            for x in range(blend_width):
                alpha = x / blend_width  # 从0到1
                src_x = w1 - blend_width + x
                dst_x = x
                
                result[:h1, src_x] = (
                    result[:h1, src_x].astype(np.float32) * (1 - alpha) +
                    img2[:h1, dst_x].astype(np.float32) * alpha
                ).astype(np.uint8)
        
        # 放置第二张图片的非重叠部分
        result[:h2, blend_start + offset:blend_start + offset + w2 - offset] = img2[:h2, offset:]
        
        return result
    
    def _concat_side_by_side(self, img1: np.ndarray, img2: np.ndarray) -> np.ndarray:
        """降级方案：并排拼接"""
        h_max = max(img1.shape[0], img2.shape[0])
        w_total = img1.shape[1] + img2.shape[1]
        
        result = np.zeros((h_max, w_total, 3), dtype=np.uint8)
        result[:img1.shape[0], :img1.shape[1]] = img1
        result[:img2.shape[0], img1.shape[1]:] = img2
        
        return result
    
    def run(self):
        """运行拼接"""
        import gc
        try:
            # 读取所有图片（从stage1目录）
            self.progress_updated.emit(10)
            
            print(f"\n📂 从stage1目录读取截图: {self.stage1_dir}")
            
            image_files = sorted([
                f for f in os.listdir(self.stage1_dir)
                if f.lower().endswith(('.png', '.jpg', '.jpeg'))
            ])
            
            if len(image_files) < 2:
                self.error_occurred.emit("至少需要 2 张图片才能拼接")
                return
            
            print(f"找到 {len(image_files)} 张图片，开始加载...\n")
            
            # 阶段1: 加载图片
            self.progress_updated.emit(15)
            images = []
            max_width = 0
            max_height = 0
            
            print(f"{'='*60}")
            print(f"📂 阶段 1: 加载图片文件")
            print(f"{'='*60}")
            
            for idx, filename in enumerate(image_files):
                filepath = os.path.join(self.stage1_dir, filename)
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
            
            print(f"\n根据检测结果进行裁切...")
            print(f"  边界参数: top_crop={top_crop}px, bottom_crop={bottom_crop}px")
            
            cropped_images = detector.crop_images(images, top_crop, bottom_crop)
            
            if not cropped_images or len(cropped_images) == 0:
                print(f"⚠️ 裁切失败，没有生成裁切图片")
                self.error_occurred.emit("裁切失败")
                return
            
            print(f"✓ 裁切成功，生成了 {len(cropped_images)} 张裁切图片")
            
            # 保存裁切后的图片到阶段2文件夹
            print(f"\n{'='*60}")
            print(f"� 阶段 3.5: 保存裁切图片到 Stage 2")
            print(f"{'='*60}")
            print(f"📁 目标目录: {self.stage2_dir}")
            print(f"📊 待保存: {len(cropped_images)} 张图片")
            
            # 确保stage2目录存在
            os.makedirs(self.stage2_dir, exist_ok=True)
            
            saved_count = 0
            for idx, cropped_img in enumerate(cropped_images, 1):
                try:
                    filename = os.path.join(self.stage2_dir, f"cropped_{idx:04d}.png")
                    
                    # 确保图片数据有效
                    if cropped_img is None or cropped_img.size == 0:
                        print(f"  [❌] 第 {idx} 张图片数据无效，跳过")
                        continue
                    
                    # 保存图片
                    success = cv2.imwrite(filename, cropped_img, [cv2.IMWRITE_PNG_COMPRESSION, 9])
                    
                    if success:
                        saved_count += 1
                        # 验证文件已保存
                        if os.path.exists(filename):
                            file_size = os.path.getsize(filename) / 1024
                            if idx % 5 == 0 or idx == 1 or idx == len(cropped_images):
                                h, w = cropped_img.shape[:2]
                                print(f"  [{idx:3d}/{len(cropped_images)}] ✓ cropped_{idx:04d}.png ({w}x{h}, {file_size:.1f} KB)")
                        else:
                            print(f"  [❌] 第 {idx} 张保存失败：文件未创建")
                    else:
                        print(f"  [❌] 第 {idx} 张保存失败：cv2.imwrite返回False")
                        
                except Exception as e:
                    print(f"  [❌] 第 {idx} 张保存异常: {e}")
            
            print(f"\n✅ 保存完成: {saved_count}/{len(cropped_images)} 张图片已保存到 stage2")
            print(f"{'='*60}\n")
            
            if saved_count == 0:
                self.error_occurred.emit("所有裁切图片保存失败")
                return
            
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
                            
                            # 智能重叠检测与融合
                            best_result = self._smart_stitch_pair(result, current_img, i)
                            if best_result is not None:
                                result = best_result
                                print(f"  拼接完成, 当前尺寸: {result.shape}")
                            else:
                                print(f"  智能拼接失败，使用降级方案")
                                # 使用默认并排拼接
                                result = self._concat_side_by_side(result, current_img)
                            
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
                # 保存结果到阶段3文件夹
                self.progress_updated.emit(90)
                output_path = os.path.join(self.stage3_dir, "stitched_result.png")
                
                try:
                    print(f"\n{'='*60}")
                    print(f"💾 准备保存拼接结果到stage3")
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
    """主窗口 - 增强版"""
    
    def __init__(self):
        super().__init__()
        
        # 配置
        self.settings = QSettings('AutoStitch', 'Config')
        
        # 状态
        self.selected_area = None  # 已弃用，仅保留兼容性
        self.temp_dir = None
        self.stage1_dir = None  # 阶段1: 原始截图
        self.stage2_dir = None  # 阶段2: 裁切图片
        self.stage3_dir = None  # 阶段3: 最终结果
        self.screenshot_thread = None
        self.stitch_thread = None
        self.overlay_window = None  # 已弃用
        
        # 全局快捷键
        self.hotkey = self.settings.value('hotkey', 'ctrl+shift+a')
        self.hotkey_listener = None
        
        # 高级参数
        self.enable_feature_matching = self.settings.value('enable_feature_matching', True, type=bool)
        self.blend_mode = self.settings.value('blend_mode', 'gradient', type=str)
        
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
            
            # 创建ss主文件夹和三个阶段的子文件夹
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            ss_dir = os.path.join(os.getcwd(), "ss")  # 当前目录的ss文件夹
            self.temp_dir = os.path.join(ss_dir, f"autostitch_{timestamp}")
            
            self.stage1_dir = os.path.join(self.temp_dir, "1_原始截图")
            self.stage2_dir = os.path.join(self.temp_dir, "2_裁切图片")
            self.stage3_dir = os.path.join(self.temp_dir, "3_最终结果")
            
            # 创建所有文件夹
            os.makedirs(self.stage1_dir, exist_ok=True)
            os.makedirs(self.stage2_dir, exist_ok=True)
            os.makedirs(self.stage3_dir, exist_ok=True)
            
            print(f"\n{'='*60}")
            print(f"📁 文件夹结构:")
            print(f"   主目录: {self.temp_dir}")
            print(f"   ├─ stage1 (原始截图): {self.stage1_dir}")
            print(f"   ├─ stage2 (裁切图片): {self.stage2_dir}")
            print(f"   └─ stage3 (最终结果): {self.stage3_dir}")
            print(f"{'='*60}\n")
            
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
                self.temp_dir,
                self.stage1_dir  # 传入stage1目录
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
            
            # 启动拼接线程（传入三个stage目录）
            self.stitch_thread = StitchThread(
                self.temp_dir,
                self.stage1_dir,
                self.stage2_dir,
                self.stage3_dir
            )
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
            
            # 不清理临时目录，保留所有输出文件供用户查看
            # 用户可以手动删除ss文件夹中的内容
            print(f"\n✅ 处理完成！")
            print(f"   📁 所有文件已保存到: {self.temp_dir}")
            print(f"   ├─ stage1 (1_原始截图): 原始全屏截图")
            print(f"   ├─ stage2 (2_裁切图片): 去除固定UI后的图片")
            print(f"   └─ stage3 (3_最终结果): stitched_result.png 长截图")
            print(f"\n")
            
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
        
        # 不删除ss文件夹，保留用户的所有输出文件
        print(f"\n👋 程序已关闭")
        if self.temp_dir:
            print(f"📁 输出文件保存在: {self.temp_dir}")
        
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
    
    # 启动欢迎信息
    print("\n" + "="*60)
    print("🚀 欢迎使用 Auto Screenshot Stitch v2.0")
    print("="*60)
    print("✨ 增强功能:")
    print("   • 4层多算法边界检测 (帧差+直方图+纹理+边缘)")
    print("   • 智能特征点匹配拼接")
    print("   • 多模式融合策略")
    print("   • 自动降级容错机制")
    print("="*60 + "\n")
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
