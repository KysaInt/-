"""
自动图片拼接工具 v4.0
使用 OpenCV Stitcher - 成熟稳定的拼接库
"""

from __future__ import annotations

# 注意：为实现“启动时依赖自检并经确认后自动安装”，需要在导入第三方库之前
# 先进行依赖检查。因此此文件的第三方导入被延后到检查完成之后。

import sys
import os
import subprocess
import re
from pathlib import Path
from datetime import datetime
from typing import List, Optional


def _parse_version_tuple(ver: str) -> tuple:
    """将版本号字符串提取为最多三段的整数元组，例如 '4.8.1.23' -> (4,8,1)。"""
    nums = re.findall(r"\d+", ver or "0")
    if not nums:
        return (0,)
    parts = [int(x) for x in nums[:3]]
    return tuple(parts)


def _version_satisfied(installed: str, minimal: str) -> bool:
    return _parse_version_tuple(installed) >= _parse_version_tuple(minimal)


def _tk_confirm(title: str, message: str) -> bool:
    """使用 Tk 弹出确认窗口；若 Tk 不可用，则返回 False（避免静默安装）。"""
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
    """通过当前 Python 解释器执行 pip 安装，返回 (成功与否, 输出/错误)。"""
    cmd = [sys.executable, "-m", "pip", "install", "-U", *packages]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            return True, proc.stdout
        # 若权限问题，尝试 --user 再来一次
        if "Permission" in (proc.stderr or "") or "permission" in (proc.stderr or ""):
            cmd_user = [sys.executable, "-m", "pip", "install", "--user", "-U", *packages]
            proc2 = subprocess.run(cmd_user, capture_output=True, text=True)
            if proc2.returncode == 0:
                return True, proc2.stdout
            return False, (proc.stderr or "") + "\n" + (proc2.stderr or "")
        return False, (proc.stderr or proc.stdout or "pip 执行失败")
    except Exception as e:
        return False, str(e)


def ensure_dependencies() -> bool:
    """
    检查并在用户确认后安装/升级依赖。
    - 需要: numpy>=1.24.0, opencv-contrib-python>=4.8.0, PySide6>=6.5.0
    - 若确认安装失败或用户拒绝，返回 False；成功或已满足返回 True。
    """
    to_install: List[str] = []
    tips: List[str] = []

    # numpy
    try:
        import importlib
        np_mod = importlib.import_module('numpy')
        if not _version_satisfied(getattr(np_mod, '__version__', '0'), '1.24.0'):
            to_install.append('numpy>=1.24.0')
            tips.append('numpy>=1.24.0（数组/图像处理）')
    except Exception:
        to_install.append('numpy>=1.24.0')
        tips.append('numpy>=1.24.0（数组/图像处理）')

    # OpenCV：统一安装 opencv-contrib-python 覆盖标准版
    need_cv = False
    try:
        import importlib
        cv2_mod = importlib.import_module('cv2')
        ver_ok = _version_satisfied(getattr(cv2_mod, '__version__', '0'), '4.8.0')
        has_stitcher = hasattr(cv2_mod, 'Stitcher_create')
        if not (ver_ok and has_stitcher):
            need_cv = True
    except Exception:
        need_cv = True
    if need_cv:
        to_install.append('opencv-contrib-python>=4.8.0')
        tips.append('opencv-contrib-python>=4.8.0（含 Stitcher/特征匹配）')

    # PySide6
    need_qt = False
    try:
        import importlib
        qt_mod = importlib.import_module('PySide6')
        ver = getattr(qt_mod, '__version__', '0')
        if not _version_satisfied(ver, '6.5.0'):
            need_qt = True
    except Exception:
        need_qt = True
    if need_qt:
        to_install.append('PySide6>=6.5.0')
        tips.append('PySide6>=6.5.0（GUI 框架）')

    if not to_install:
        return True

    # 弹窗确认
    pkg_text = "\n".join(f"- {t}" for t in tips)
    confirm_msg = (
        "检测到以下依赖缺失或版本过低：\n\n"
        f"{pkg_text}\n\n"
        "是否现在安装/升级？\n\n"
        "将执行：pip install -U " + " ".join(to_install)
    )
    if not _tk_confirm("安装依赖", confirm_msg):
        _tk_info("已取消", "已取消依赖安装，程序将退出。\n\n你也可以手动安装：\n" + "pip install -U " + " ".join(to_install))
        return False

    ok, out = _pip_install(to_install)
    if ok:
        _tk_info("安装成功", "依赖已安装/升级完成，将继续启动程序。")
        return True
    else:
        _tk_info("安装失败", "安装/升级失败。可尝试手动安装：\n\n" + out)
        return False


# 依赖检查：若失败则直接退出
if not ensure_dependencies():
    sys.exit(1)

# 通过依赖检查后，再导入第三方库
import cv2
import numpy as np
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QLabel, QLineEdit, 
                               QFileDialog, QProgressBar, QTextEdit, QMessageBox,
                               QScrollArea, QGroupBox, QListWidget,
                               QListWidgetItem, QListView, QMenu, QInputDialog,
                               QSlider, QSizePolicy, QStyledItemDelegate, QFrame, QSplitter, QStyle, QGridLayout, QDialog, QComboBox)
from PySide6.QtCore import Qt, QThread, Signal, QPoint, QSize, QRect, QPropertyAnimation, QEasingCurve, QUrl, QEvent, QSettings, QTimer, QFileSystemWatcher
from PySide6.QtGui import QPixmap, QImage, QIcon, QAction, QPainter, QColor, QPen, QFont, QDesktopServices


class ImageStitcher:
    """精确图片拼接器 - 基于特征匹配的高精度拼接
    
    新特性:
    1. 使用SIFT/ORB特征点精确定位重叠区域
    2. 支持任意角度和比例的图片拼接
    3. 智能裁剪，生成不规则边界
    4. 多种拼接模式：智能、垂直、水平、网格
    """

    def __init__(self, mode='smart'):
        """
        mode: 'smart'      自动检测最佳拼接方式
              'vertical'   强制垂直拼接
              'horizontal' 强制水平拼接
              'grid'       网格拼接
        """
        self.mode = mode
        # 初始化特征检测器
        try:
            # 优先使用SIFT（更准确，适合截图）
            self.detector = cv2.SIFT_create(nfeatures=2000)
            self.matcher = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)
            self.feature_type = 'SIFT'
        except:
            # 回退到ORB
            self.detector = cv2.ORB_create(nfeatures=2000)
            self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
            self.feature_type = 'ORB'

    def load_images(self, directory: str) -> List[str]:
        """加载目录下的所有图片"""
        supported_formats = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp']
        image_files = []

        for root, _, files in os.walk(directory):
            for file in sorted(files):
                if Path(file).suffix.lower() in supported_formats:
                    image_files.append(os.path.join(root, file))

        return image_files


    def _find_overlap_precise(self, img1: np.ndarray, img2: np.ndarray, direction='vertical') -> dict:
        """精确查找两张图片的重叠区域和变换矩阵
        
        Args:
            img1: 第一张图片（上方/左侧）
            img2: 第二张图片（下方/右侧）
            direction: 'vertical' 或 'horizontal'
        
        Returns:
            {
                'found': bool,           # 是否找到重叠
                'overlap': int,          # 重叠像素数
                'offset': (x, y),        # 偏移量
                'homography': np.ndarray # 单应性矩阵（如果需要）
            }
        """
        result = {
            'found': False,
            'overlap': 0,
            'offset': (0, 0),
            'homography': None
        }
        
        # 转换为灰度图
        gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY) if len(img1.shape) == 3 else img1
        gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY) if len(img2.shape) == 3 else img2
        
        # 提取感兴趣区域（减少计算量）
        h1, w1 = gray1.shape
        h2, w2 = gray2.shape
        
        if direction == 'vertical':
            # 垂直拼接：比较img1底部30%和img2顶部30%
            roi1 = gray1[int(h1*0.7):, :]
            roi2 = gray2[:int(h2*0.3), :]
            roi1_offset = (0, int(h1*0.7))
            roi2_offset = (0, 0)
        else:
            # 水平拼接：比较img1右侧30%和img2左侧30%
            roi1 = gray1[:, int(w1*0.7):]
            roi2 = gray2[:, :int(w2*0.3)]
            roi1_offset = (int(w1*0.7), 0)
            roi2_offset = (0, 0)
        
        # 检测特征点
        kp1, des1 = self.detector.detectAndCompute(roi1, None)
        kp2, des2 = self.detector.detectAndCompute(roi2, None)
        
        if des1 is None or des2 is None or len(kp1) < 4 or len(kp2) < 4:
            return result
        
        # 特征匹配
        try:
            matches = self.matcher.knnMatch(des1, des2, k=2)
        except:
            return result
        
        # Lowe's ratio test
        good_matches = []
        for m_n in matches:
            if len(m_n) == 2:
                m, n = m_n
                if m.distance < 0.75 * n.distance:
                    good_matches.append(m)
        
        # 至少需要4个好的匹配点
        if len(good_matches) < 4:
            return result
        
        # 提取匹配点坐标
        pts1 = np.float32([kp1[m.queryIdx].pt for m in good_matches])
        pts2 = np.float32([kp2[m.trainIdx].pt for m in good_matches])
        
        # 调整坐标到原图
        pts1[:, 0] += roi1_offset[0]
        pts1[:, 1] += roi1_offset[1]
        pts2[:, 0] += roi2_offset[0]
        pts2[:, 1] += roi2_offset[1]
        
        # 计算单应性矩阵（用于处理缩放、旋转）
        try:
            H, mask = cv2.findHomography(pts2, pts1, cv2.RANSAC, 5.0)
            if H is None:
                return result
            
            # 统计内点
            inliers = np.sum(mask)
            if inliers < 4:
                return result
            
            result['found'] = True
            result['homography'] = H
            
            # 计算偏移量
            if direction == 'vertical':
                # 计算img2需要向上移动多少才能对齐
                corners2 = np.float32([[0, 0], [w2, 0], [w2, h2], [0, h2]]).reshape(-1, 1, 2)
                transformed = cv2.perspectiveTransform(corners2, H)
                # 取顶部边缘的平均y坐标作为重叠位置
                top_y = np.mean(transformed[0:2, 0, 1])
                result['overlap'] = max(0, int(h1 - top_y))
                result['offset'] = (0, int(top_y))
            else:
                # 水平拼接
                corners2 = np.float32([[0, 0], [w2, 0], [w2, h2], [0, h2]]).reshape(-1, 1, 2)
                transformed = cv2.perspectiveTransform(corners2, H)
                # 取左侧边缘的平均x坐标作为重叠位置
                left_x = np.mean(transformed[[0, 3], 0, 0])
                result['overlap'] = max(0, int(w1 - left_x))
                result['offset'] = (int(left_x), 0)
            
            return result
            
        except Exception as e:
            return result

    def _stitch_two_precise(self, img1: np.ndarray, img2: np.ndarray, direction='vertical', progress_callback=None) -> np.ndarray:
        """精确拼接两张图片
        
        使用特征匹配找到精确的重叠位置，支持缩放和旋转
        """
        if progress_callback:
            progress_callback(1, 2, f"正在分析图片重叠区域...")
        
        # 查找重叠
        overlap_info = self._find_overlap_precise(img1, img2, direction)
        
        if not overlap_info['found']:
            # 如果找不到重叠，使用简单拼接
            if progress_callback:
                progress_callback(1, 2, f"未检测到重叠，使用简单拼接...")
            return self._simple_stitch_two(img1, img2, direction)
        
        if progress_callback:
            progress_callback(1, 2, f"✓ 检测到{overlap_info['overlap']}px重叠，正在精确拼接...")
        
        h1, w1 = img1.shape[:2]
        h2, w2 = img2.shape[:2]
        H = overlap_info['homography']
        
        if direction == 'vertical':
            # 垂直拼接
            offset_y = overlap_info['offset'][1]
            
            # 如果有单应性变换，先对img2进行变换
            if H is not None and not np.allclose(H, np.eye(3)):
                # 计算变换后的尺寸
                corners2 = np.float32([[0, 0], [w2, 0], [w2, h2], [0, h2]]).reshape(-1, 1, 2)
                transformed = cv2.perspectiveTransform(corners2, H)
                
                x_coords = transformed[:, 0, 0]
                y_coords = transformed[:, 0, 1]
                
                min_x, max_x = int(np.floor(x_coords.min())), int(np.ceil(x_coords.max()))
                min_y, max_y = int(np.floor(y_coords.min())), int(np.ceil(y_coords.max()))
                
                # 创建变换矩阵（加上平移）
                translation = np.array([[1, 0, -min_x], [0, 1, -min_y], [0, 0, 1]])
                H_translated = translation @ H
                
                # 变换img2
                out_w = max_x - min_x
                out_h = max_y - min_y
                img2_warped = cv2.warpPerspective(img2, H_translated, (out_w, out_h))
                
                # 调整offset
                offset_y = offset_y - min_y
            else:
                img2_warped = img2
            
            # 创建画布
            canvas_h = max(h1, offset_y + img2_warped.shape[0])
            canvas_w = max(w1, img2_warped.shape[1])
            canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
            
            # 放置img1
            canvas[:h1, :w1] = img1
            
            # 放置img2（融合重叠区域）
            y_start = max(0, offset_y)
            y_end = min(canvas_h, offset_y + img2_warped.shape[0])
            
            if y_start < h1:
                # 有重叠，使用alpha融合
                overlap_h = min(h1 - y_start, img2_warped.shape[0])
                for i in range(overlap_h):
                    alpha = i / overlap_h  # 线性融合
                    y = y_start + i
                    canvas[y, :img2_warped.shape[1]] = (
                        canvas[y, :img2_warped.shape[1]] * (1 - alpha) +
                        img2_warped[i, :] * alpha
                    ).astype(np.uint8)
                
                # 放置非重叠部分
                if offset_y + overlap_h < offset_y + img2_warped.shape[0]:
                    canvas[y_start + overlap_h:y_end, :img2_warped.shape[1]] = \
                        img2_warped[overlap_h:y_end - y_start, :]
            else:
                # 无重叠
                canvas[y_start:y_end, :img2_warped.shape[1]] = img2_warped[:y_end - y_start, :]
            
            return canvas
            
        else:
            # 水平拼接（类似逻辑）
            offset_x = overlap_info['offset'][0]
            
            if H is not None and not np.allclose(H, np.eye(3)):
                corners2 = np.float32([[0, 0], [w2, 0], [w2, h2], [0, h2]]).reshape(-1, 1, 2)
                transformed = cv2.perspectiveTransform(corners2, H)
                
                x_coords = transformed[:, 0, 0]
                y_coords = transformed[:, 0, 1]
                
                min_x, max_x = int(np.floor(x_coords.min())), int(np.ceil(x_coords.max()))
                min_y, max_y = int(np.floor(y_coords.min())), int(np.ceil(y_coords.max()))
                
                translation = np.array([[1, 0, -min_x], [0, 1, -min_y], [0, 0, 1]])
                H_translated = translation @ H
                
                out_w = max_x - min_x
                out_h = max_y - min_y
                img2_warped = cv2.warpPerspective(img2, H_translated, (out_w, out_h))
                
                offset_x = offset_x - min_x
            else:
                img2_warped = img2
            
            canvas_h = max(h1, img2_warped.shape[0])
            canvas_w = max(w1, offset_x + img2_warped.shape[1])
            canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
            
            canvas[:h1, :w1] = img1
            
            x_start = max(0, offset_x)
            x_end = min(canvas_w, offset_x + img2_warped.shape[1])
            
            if x_start < w1:
                overlap_w = min(w1 - x_start, img2_warped.shape[1])
                for i in range(overlap_w):
                    alpha = i / overlap_w
                    x = x_start + i
                    canvas[:img2_warped.shape[0], x] = (
                        canvas[:img2_warped.shape[0], x] * (1 - alpha) +
                        img2_warped[:, i] * alpha
                    ).astype(np.uint8)
                
                if offset_x + overlap_w < offset_x + img2_warped.shape[1]:
                    canvas[:img2_warped.shape[0], x_start + overlap_w:x_end] = \
                        img2_warped[:, overlap_w:x_end - x_start]
            else:
                canvas[:img2_warped.shape[0], x_start:x_end] = img2_warped[:, :x_end - x_start]
            
            return canvas

    def _simple_stitch_two(self, img1: np.ndarray, img2: np.ndarray, direction='vertical') -> np.ndarray:
        """简单拼接两张图片（无特征匹配）"""
        if direction == 'vertical':
            max_w = max(img1.shape[1], img2.shape[1])
            if img1.shape[1] < max_w:
                img1 = np.pad(img1, ((0, 0), (0, max_w - img1.shape[1]), (0, 0)), mode='constant')
            if img2.shape[1] < max_w:
                img2 = np.pad(img2, ((0, 0), (0, max_w - img2.shape[1]), (0, 0)), mode='constant')
            return np.vstack([img1, img2])
        else:
            max_h = max(img1.shape[0], img2.shape[0])
            if img1.shape[0] < max_h:
                img1 = np.pad(img1, ((0, max_h - img1.shape[0]), (0, 0), (0, 0)), mode='constant')
            if img2.shape[0] < max_h:
                img2 = np.pad(img2, ((0, max_h - img2.shape[0]), (0, 0), (0, 0)), mode='constant')
            return np.hstack([img1, img2])

    def _detect_stitch_direction(self, images: List[np.ndarray]) -> str:
        """智能检测拼接方向
        
        策略：
        1. 如果所有图片宽度相同或接近，且高度不同 -> 垂直拼接
        2. 如果所有图片高度相同或接近，且宽度不同 -> 水平拼接
        3. 如果图片尺寸差异很大 -> 网格拼接
        4. 默认 -> 垂直拼接
        """
        if len(images) <= 1:
            return 'vertical'
        
        widths = [img.shape[1] for img in images]
        heights = [img.shape[0] for img in images]
        
        # 计算尺寸变化系数
        w_var = np.std(widths) / (np.mean(widths) + 1e-6)
        h_var = np.std(heights) / (np.mean(heights) + 1e-6)
        
        # 判断逻辑
        if w_var < 0.1 and h_var > 0.2:  # 宽度相近，高度差异大
            return 'vertical'
        elif h_var < 0.1 and w_var > 0.2:  # 高度相近，宽度差异大
            return 'horizontal'
        elif w_var > 0.5 or h_var > 0.5:  # 尺寸差异很大
            return 'grid'
        else:
            # 默认垂直（最常见的截图场景）
            return 'vertical'

    def _stitch_sequence_precise(self, images: List[np.ndarray], direction: str, progress_callback=None) -> np.ndarray:
        """精确拼接多张图片序列"""
        if len(images) == 1:
            return images[0]
        
        result = images[0]
        for i, img in enumerate(images[1:], start=1):
            if progress_callback:
                progress_callback(i, len(images)-1, f"正在精确拼接第 {i}/{len(images)-1} 张...")
            result = self._stitch_two_precise(result, img, direction, progress_callback)
        
        return result

    def _grid_stitch(self, images: List[np.ndarray], progress_callback=None) -> np.ndarray:
        """网格拼接"""
        n = len(images)
        cols = int(np.ceil(np.sqrt(n)))
        rows = int(np.ceil(n / cols))
        
        # 找到最大宽高
        max_h = max(img.shape[0] for img in images)
        max_w = max(img.shape[1] for img in images)
        
        # 创建网格
        grid_rows = []
        for r in range(rows):
            if progress_callback:
                progress_callback(r+1, rows, f"正在创建网格第 {r+1}/{rows} 行...")
            
            row_images = []
            for c in range(cols):
                idx = r * cols + c
                if idx < n:
                    img = images[idx]
                    # 居中填充到统一大小
                    padded = np.zeros((max_h, max_w, 3), dtype=np.uint8)
                    y_offset = (max_h - img.shape[0]) // 2
                    x_offset = (max_w - img.shape[1]) // 2
                    padded[y_offset:y_offset+img.shape[0], x_offset:x_offset+img.shape[1]] = img
                    row_images.append(padded)
                else:
                    # 空白填充
                    row_images.append(np.zeros((max_h, max_w, 3), dtype=np.uint8))
            grid_rows.append(np.hstack(row_images))
        
        result = np.vstack(grid_rows)
        return result

    def stitch_images(self, image_paths: List[str], progress_callback=None, fallback_mode='vertical') -> Optional[np.ndarray]:
        """拼接图片 - 精确特征匹配实现
        
        Args:
            image_paths: 图片路径列表
            progress_callback: 进度回调函数
            fallback_mode: 备选拼接模式 ('vertical', 'horizontal', 'grid', None)
        """
        if not image_paths:
            return None

        # 1. 加载所有图片
        images = []
        for i, path in enumerate(image_paths):
            if progress_callback:
                progress_callback(i + 1, len(image_paths), f"加载图片: {Path(path).name}")

            try:
                with open(path, 'rb') as f:
                    img_bytes = f.read()
                img_array = np.frombuffer(img_bytes, dtype=np.uint8)
                img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

                if img is not None:
                    images.append(img)
                    if progress_callback:
                        progress_callback(i + 1, len(image_paths), f"✓ 已加载: {Path(path).name} ({img.shape[1]}x{img.shape[0]})")
                else:
                    if progress_callback:
                        progress_callback(i + 1, len(image_paths), f"⚠ 无法解码: {Path(path).name}")
            except Exception as e:
                if progress_callback:
                    progress_callback(i + 1, len(image_paths), f"⚠ 加载失败: {Path(path).name} - {e}")

        if not images:
            return None

        if len(images) == 1:
            if progress_callback:
                progress_callback(1, 1, "单张图片，无需拼接")
            return images[0]

        # 2. 确定拼接方向
        if self.mode == 'smart':
            # 使用fallback_mode作为智能模式的指导
            if fallback_mode == 'vertical':
                direction = 'vertical'
            elif fallback_mode == 'horizontal':
                direction = 'horizontal'
            elif fallback_mode == 'grid':
                direction = 'grid'
            else:
                # 真正的智能检测
                direction = self._detect_stitch_direction(images)
        else:
            direction = self.mode if self.mode in ['vertical', 'horizontal', 'grid'] else fallback_mode or 'vertical'

        if progress_callback:
            direction_name = {'vertical': '垂直', 'horizontal': '水平', 'grid': '网格'}.get(direction, direction)
            progress_callback(len(image_paths), len(image_paths), f"开始{direction_name}拼接 {len(images)} 张图片...")
            progress_callback(len(image_paths), len(image_paths), f"使用 {self.feature_type} 特征检测器进行精确匹配...")

        # 3. 执行拼接
        try:
            if direction == 'grid':
                result = self._grid_stitch(images, progress_callback)
            else:
                # 使用精确特征匹配拼接
                result = self._stitch_sequence_precise(images, direction, progress_callback)
            
            if progress_callback:
                progress_callback(len(image_paths), len(image_paths), f"✓ 拼接完成！结果尺寸: {result.shape[1]}x{result.shape[0]}")
            
            return result
            
        except Exception as e:
            import traceback
            if progress_callback:
                progress_callback(len(image_paths), len(image_paths), f"✗ 拼接失败: {e}")
                progress_callback(len(image_paths), len(image_paths), traceback.format_exc())
            return None

class ProgressDialog(QDialog):
    """下载/处理进度弹窗：显示当前进度、状态信息与耗时。

    使用 update_progress(current,total,message) 更新；
    finish() 结束并自动关闭。
    """
    def __init__(self, parent=None, title: str = "正在处理"):
        super().__init__(parent)
        self.setWindowTitle(title)
        # 改为非模态，避免阻塞父窗口交互
        self.setModal(False)
        self.resize(420, 160)
        self._start_dt = datetime.now()
        self._last_message = ""
        layout = QVBoxLayout(self)
        self.label_status = QLabel("准备中…")
        self.label_status.setWordWrap(True)
        layout.addWidget(self.label_status)
        self.bar = QProgressBar(); self.bar.setRange(0, 100); self.bar.setValue(0)
        layout.addWidget(self.bar)
        self.label_elapsed = QLabel("耗时: 0s")
        layout.addWidget(self.label_elapsed)
        # 取消按钮
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self._on_cancel_clicked)
        layout.addWidget(self.btn_cancel)
        self._cancelled = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(1000)
        # 顶置
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        # 样式自适应主题
        pal = self.palette()
        try:
            hi = pal.color(pal.ColorRole.Highlight)
        except Exception:
            hi = pal.highlight().color()  # type: ignore
        self.bar.setStyleSheet(
            "QProgressBar { border: 1px solid palette(Mid); border-radius: 4px; height: 14px; text-align: center;}"
            f"QProgressBar::chunk {{ background-color: rgb({hi.red()},{hi.green()},{hi.blue()}); border-radius: 4px; }}"
        )
    def _on_tick(self):
        delta = datetime.now() - self._start_dt
        secs = int(delta.total_seconds())
        if secs < 60:
            txt = f"耗时: {secs}s"
        else:
            m, s = divmod(secs, 60)
            if m < 60:
                txt = f"耗时: {m}m{s:02d}s"
            else:
                h, rem = divmod(m, 60)
                m2, s2 = divmod(rem, 60)
                txt = f"耗时: {h}h{m2:02d}m{s2:02d}s"
        self.label_elapsed.setText(txt)
    def update_progress(self, current: int, total: int, message: str):
        # 归一化为百分比
        pct = 0
        if total > 0:
            pct = max(0, min(100, int((current / total) * 100)))
        self.bar.setValue(pct)
        self._last_message = message or ""
        self.label_status.setText(f"{message}\n进度: {pct}% ({current}/{total})")
        if self._cancelled:
            self.label_status.setText(f"已请求取消… 当前进度 {pct}%")
    def finish(self, success: bool = True, final_message: str = ""):
        self._timer.stop()
        if final_message:
            self.label_status.setText(final_message)
        else:
            self.label_status.setText("处理完成" if success else "处理失败")
        QTimer.singleShot(800, self.accept)
    def _on_cancel_clicked(self):
        self._cancelled = True
        self.btn_cancel.setEnabled(False)
        self.label_status.setText("已发出取消请求，等待当前步骤完成…")

class StitchThread(QThread):
    """拼接工作线程"""
    progress = Signal(int, int, str)
    finished = Signal(object)
    error = Signal(str)
    
    def __init__(self, directory: str, mode: str = 'scans', image_paths: Optional[List[str]] = None, fallback_mode: str = 'vertical'):
        super().__init__()
        self.directory = directory
        self.mode = mode
        self.stitcher = ImageStitcher(mode=mode)
        self.image_paths = image_paths or []
        self.fallback_mode = fallback_mode
    
    def run(self):
        """执行拼接任务 - 简化版本，直接拼接所有图片"""
        try:
            self.progress.emit(0, 100, "准备拼接...")
            image_paths = list(self.image_paths) if self.image_paths else self.stitcher.load_images(self.directory)
            
            if not image_paths:
                self.error.emit("未在目录中找到图片文件")
                return
            
            if len(image_paths) < 1:
                self.error.emit("需要至少1张图片")
                return

            self.progress.emit(0, 100, f"将拼接 {len(image_paths)} 张图片...")
            self.progress.emit(0, 100, f"图片列表: {[os.path.basename(p) for p in image_paths[:5]]}" + ("..." if len(image_paths) > 5 else ""))
            
            # 直接尝试拼接所有图片
            pano = self.stitcher.stitch_images(
                image_paths, 
                progress_callback=self.progress.emit,
                fallback_mode=self.fallback_mode
            )
            
            self.progress.emit(100, 100, f"拼接方法返回: type={type(pano)}, is None={pano is None}")
            if pano is not None and hasattr(pano, 'shape'):
                self.progress.emit(100, 100, f"返回图像信息: shape={pano.shape}, dtype={pano.dtype}")
            
            if pano is not None:
                self.progress.emit(100, 100, "拼接完成，准备发送结果...")
                # 返回格式: [(paths, image)]
                result_data = [([str(p) for p in image_paths], pano)]
                self.progress.emit(100, 100, f"发送finished信号: len={len(result_data)}, 第一项类型={type(result_data[0])}")
                self.finished.emit(result_data)
            else:
                self.progress.emit(100, 100, "拼接返回None，发送错误...")
                self.error.emit("拼接失败。请尝试选择其他拼接模式或确保图片有重叠区域。")

        except Exception as e:
            import traceback
            err_msg = f"拼接过程出错: {str(e)}\n{traceback.format_exc()}"
            self.progress.emit(100, 100, f"发生异常: {str(e)}")
            self.error.emit(err_msg)


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        # 结果图像（用于单结果保存等）
        self.result_image = None
        # 后台线程
        self.stitch_thread = None
        # 缩略图初始尺寸
        self._thumb_size = 60
        # 选择顺序跟踪列表
        self.selection_order = []
        # QListWidget item roles
        self.ROLE_PATH = Qt.UserRole
        self.ROLE_ORDER = Qt.UserRole + 1
        self.ROLE_MARK = Qt.UserRole + 2
        # 进度弹窗实例（运行时创建/销毁）
        self._progress_dialog = None
        # 文件系统监控器
        self.file_watcher = QFileSystemWatcher()
        self.file_watcher.directoryChanged.connect(self._on_directory_changed)
        # 初始化界面
        self.init_ui()
        
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("OpenCV Stitcher")
        self.setMinimumSize(900, 700)
        # 主题变化监听，用于实时刷新样式
        self.installEventFilter(self)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # 1. 直接在顶部放置“设置”内容
        top_settings = QVBoxLayout()
        top_settings.setContentsMargins(8,8,8,0)
        top_settings.setSpacing(6)
        dir_row = QHBoxLayout()
        self.dir_edit = QLineEdit()
        self.dir_edit.setPlaceholderText("请选择包含要拼接图片的目录...")
        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.setProperty("btn", "secondary")
        self.browse_btn.clicked.connect(self.browse_directory)
        dir_row.addWidget(QLabel("目录:"))
        dir_row.addWidget(self.dir_edit, 1)
        dir_row.addWidget(self.browse_btn)
        top_settings.addLayout(dir_row)

        # 输出格式选择
        format_row = QHBoxLayout()
        format_row.addWidget(QLabel("输出格式:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["PNG", "JPEG", "WebP (无损)"])
        format_row.addWidget(self.format_combo)
        format_row.addStretch()
        
        # 拼接模式选择
        format_row.addWidget(QLabel("失败时备选:"))
        self.fallback_combo = QComboBox()
        self.fallback_combo.addItems(["垂直拼接", "水平拼接", "网格拼接", "不使用备选"])
        self.fallback_combo.setCurrentIndex(0)
        self.fallback_combo.setToolTip("当OpenCV智能拼接失败时使用的备选方案")
        format_row.addWidget(self.fallback_combo)
        format_row.addStretch(1)
        top_settings.addLayout(format_row)

        # 顶部同排：打开 + 选择按钮
        top_bar = QHBoxLayout()
        top_bar.setSpacing(6)
        self.selection_summary_label = QLabel("未加载目录")
        top_bar.addWidget(self.selection_summary_label)
        # 先放置“打开”按钮
        self.open_output_btn = QPushButton("打开")
        self.open_output_btn.setProperty("btn", "secondary")
        self.open_output_btn.setToolTip("打开输出目录 (stitch)")
        self.open_output_btn.clicked.connect(self.open_output_dir)
        top_bar.addWidget(self.open_output_btn)
        # 中部：选择相关按钮
        self.btn_select_all = QPushButton("全选")
        self.btn_select_all.setMinimumHeight(28)
        self.btn_select_all.setProperty("btn", "secondary")
        top_bar.addWidget(self.btn_select_all)
        # 中部：全不选、反选
        self.btn_select_none = QPushButton("全不选")
        self.btn_select_none.setMinimumHeight(28)
        self.btn_select_none.setProperty("btn", "secondary")
        top_bar.addWidget(self.btn_select_none)
        self.btn_invert = QPushButton("反选")
        self.btn_invert.setMinimumHeight(28)
        self.btn_invert.setProperty("btn", "secondary")
        top_bar.addWidget(self.btn_invert)
        # 右侧：开始拼接（动态占据余下宽度并贴右侧）
        self.start_btn = QPushButton("🚀 开始拼接")
        self.start_btn.clicked.connect(self.start_stitching)
        self.start_btn.setMinimumHeight(32)
        self.start_btn.setProperty("btn", "primary")
        self.start_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        top_bar.addWidget(self.start_btn, 1)
        top_settings.addLayout(top_bar)
        # 挂到主布局顶部
        layout.addLayout(top_settings)

        # 2. 图片预览与选择 / 结果预览（合并面板）
        preview_select_container = QWidget()
        preview_select_layout = QVBoxLayout(preview_select_container)
        # 更紧凑的上下边距与行间距
        preview_select_layout.setContentsMargins(6,6,6,6)
        preview_select_layout.setSpacing(4)

        # 第二行：缩放
        zoom_row = QHBoxLayout()
        zoom_row.addWidget(QLabel("缩放:"))
        self.thumb_size_label = QLabel(f"{self._thumb_size}px")
        zoom_row.addWidget(self.thumb_size_label)
        self.thumb_slider = QSlider(Qt.Horizontal)
        self.thumb_slider.setMinimum(10)
        self.thumb_slider.setMaximum(300)
        self.thumb_slider.setValue(self._thumb_size)
        self.thumb_slider.setToolTip("调整预览缩略图大小 (Ctrl+滚轮 也可缩放)")
        self.thumb_slider.valueChanged.connect(self._on_thumb_size_changed)
        zoom_row.addWidget(self.thumb_slider, 1)
        preview_select_layout.addLayout(zoom_row)
        # 更细的进度条：紧贴缩放行下方
        self.progress_bar = QProgressBar()
        pal = self.palette()
        try:
            hl = pal.color(pal.ColorRole.Highlight)
        except Exception:
            hl = pal.highlight().color()  # type: ignore
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setStyleSheet(
            "QProgressBar { border: 1px solid palette(Mid); border-radius: 3px; min-height: 6px; }"
            f"QProgressBar::chunk {{ background-color: rgb({hl.red()},{hl.green()},{hl.blue()}); border-radius: 3px; }}"
        )
        preview_select_layout.addWidget(self.progress_bar)

        # 预览：图标平铺（正方形体块）
        self.image_list = self._create_image_list()

        # 选择按钮连接
        self.btn_select_all.clicked.connect(self._select_all)
        self.btn_select_none.clicked.connect(self._select_none)
        self.btn_invert.clicked.connect(self._invert_selection)

        # 合并：结果预览区域（右侧，自动缩放；支持单图和多图网格）
        self.result_container = QWidget()
        self.result_container.setMinimumHeight(260)
        rc_layout = QVBoxLayout(self.result_container)
        rc_layout.setContentsMargins(0,0,0,0)
        rc_layout.setSpacing(0)
        # 单结果占位/显示
        self.preview_label = QLabel("拼接结果将显示在这里")
        self.preview_label.setAlignment(Qt.AlignCenter)
        # 使用当前主题的窗口背景色和中间色设置初始底色和边框，避免纯白
        pal = self.palette()
        try:
            win_col = pal.color(pal.ColorRole.Window)
            mid_col = pal.color(pal.ColorRole.Mid)
            txt_col = pal.color(pal.ColorRole.Text)
        except Exception:
            win_col = pal.window().color()  # type: ignore
            mid_col = pal.mid().color()  # type: ignore
            txt_col = pal.text().color()  # type: ignore
        self.preview_label.setStyleSheet(
            "QLabel { "
            f"background-color: rgb({win_col.red()},{win_col.green()},{win_col.blue()}); "
            f"border: 2px dashed rgb({mid_col.red()},{mid_col.green()},{mid_col.blue()}); "
            "padding: 16px; "
            f"color: rgb({txt_col.red()},{txt_col.green()},{txt_col.blue()}); "
            "font-size: 13px; }"
        )
        self.preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        rc_layout.addWidget(self.preview_label, 1)
        # 多结果滚动网格
        self.result_scroll = QScrollArea()
        self.result_scroll.setWidgetResizable(True)
        self.result_grid_widget = QWidget()
        self.result_grid = QGridLayout(self.result_grid_widget)
        self.result_grid.setContentsMargins(8,8,8,8)
        self.result_grid.setSpacing(8)
        self.result_scroll.setWidget(self.result_grid_widget)
        self.result_scroll.setVisible(False)  # 初始隐藏，默认单图显示
        rc_layout.addWidget(self.result_scroll, 1)
        def _rc_resize(ev):
            QWidget.resizeEvent(self.result_container, ev)
            self._refresh_results_preview()
        self.result_container.resizeEvent = _rc_resize

        # 左右结构：左（缩略图+操作）| 分隔线 | 右（结果预览）
        self.h_splitter = QSplitter(Qt.Horizontal)
        self.h_splitter.setChildrenCollapsible(False)

        left_widget = QWidget()
        left_col = QVBoxLayout(left_widget)
        left_col.setContentsMargins(0,0,0,0)
        left_col.addWidget(self.image_list, 1)

        self.h_splitter.addWidget(left_widget)
        self.h_splitter.addWidget(self.result_container)
        self.h_splitter.setStretchFactor(0, 1)
        self.h_splitter.setStretchFactor(1, 1)
        preview_select_layout.addWidget(self.h_splitter)

        # 双击打开：为缩略图列表启用双击打开文件
        self.image_list.itemDoubleClicked.connect(self._on_item_double_clicked)

        # 日志面板
        log_container = QWidget()
        log_layout = QVBoxLayout(log_container)
        log_layout.setContentsMargins(0,6,0,0)
        log_layout.addWidget(QLabel("日志:"))
        self.log_text = QTextEdit(); self.log_text.setReadOnly(True)
        self.log_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        log_layout.addWidget(self.log_text)

        self.vsplitter = QSplitter(Qt.Vertical)
        self.vsplitter.setChildrenCollapsible(False)
        self.vsplitter.addWidget(preview_select_container)
        self.vsplitter.addWidget(log_container)
        self.vsplitter.setStretchFactor(0, 70)
        self.vsplitter.setStretchFactor(1, 30)
        layout.addWidget(self.vsplitter, 1)

        # 首次提示
        self.log("✅ 程序已启动 - 使用 OpenCV Stitcher 专业拼接引擎")
        self.log("💡 提示：")
        self.log("• Created by AYE | Version 1.0.0 | 2025-10-12")
        self.log("• OpenCV Stitcher 是业界标准的图像拼接库")
        self.log("• 自动检测特征点并精确对齐")
        self.log("• 确保相邻图片有 30% 以上的重叠区域")
        self.log("• 当前默认使用‘扫描模式’，适合截图/文档")

        # 应用全局按钮样式 + 恢复设置
        self._apply_global_styles()
        self._restore_settings()

    # ============ 预览表格与缩放 ============
    def _create_image_list(self) -> QListWidget:
        lw = QListWidget()
        lw.setViewMode(QListView.IconMode)
        lw.setIconSize(self._calc_icon_size())
        lw.setResizeMode(QListView.Adjust)
        lw.setMovement(QListView.Static)
        lw.setSpacing(1)
        lw.setUniformItemSizes(True)
        lw.setSelectionMode(QListWidget.MultiSelection)
        lw.setContextMenuPolicy(Qt.CustomContextMenu)
        lw.customContextMenuRequested.connect(self._on_list_context_menu)
        # 去掉额外留白，进一步紧凑
        lw.setStyleSheet("QListView{padding:0px; margin:0px;} QListView::item{margin:0px; padding:0px;}")
        # Ctrl+滚轮缩放
        lw.wheelEvent = self._make_ctrl_wheel_zoom(lw.wheelEvent)
        # 点击时更新选择顺序
        lw.itemClicked.connect(self._on_item_clicked_for_ordering)
        # 选择变化时更新统计
        lw.itemSelectionChanged.connect(self._on_selection_changed)
        self._apply_list_grid(lw)
        # 自定义选中叠加序号
        lw.setItemDelegate(self.ThumbDelegate(self))
        return lw

    def _calc_icon_size(self):
        # 允许最小到 10px，最大 512px
        s = max(10, min(512, self._thumb_size))
        return QSize(s, s)

    def _apply_list_grid(self, lw: QListWidget):
        # 根据图标尺寸设置网格，尽量紧凑
        s = self._calc_icon_size().width()
        # 为描边和序号留出额外边距，避免被裁切
        pad = 8
        lw.setGridSize(QSize(s + pad, s + pad))
        # 刷新几何以立即生效
        try:
            lw.updateGeometries()
        except Exception:
            pass
        lw.viewport().update()

    class ThumbDelegate(QStyledItemDelegate):
        def __init__(self, parent):
            super().__init__(parent)
            self.parent = parent
        def sizeHint(self, option, index):
            # 返回与当前缩略图设置相匹配的单元格尺寸
            s = self.parent._calc_icon_size().width()
            pad = 8
            return QSize(s + pad, s + pad)
        def paint(self, painter: QPainter, option, index):
            # 自绘缩略图：先绘制正方形边框，再绘制图片，最后绘制选中序号
            r = option.rect
            # 1) 正方形方框
            painter.save()
            # 让方框尽量占满单元格，仅为描边留出 1px 余量
            side_frame = max(2, min(r.width(), r.height()) - 1)
            fx = r.x() + (r.width() - side_frame) // 2
            fy = r.y() + (r.height() - side_frame) // 2
            frame_rect = QRect(fx, fy, side_frame, side_frame)
            pal = self.parent.palette()
            try:
                mid_col = pal.color(pal.ColorRole.Mid)
                hi_col = pal.color(pal.ColorRole.Highlight)
            except Exception:
                mid_col = pal.mid().color()  # type: ignore
                hi_col = pal.highlight().color()  # type: ignore
            # 未选中使用浅灰（mid），选中使用主题高亮色，选中时线条稍粗
            pen = QPen(hi_col if (option.state & QStyle.State_Selected) else mid_col)
            pen.setWidth(2 if (option.state & QStyle.State_Selected) else 1)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(frame_rect)
            painter.restore()

            # 2) 图片
            painter.save()
            try:
                item = self.parent.image_list.item(index.row())
                icon = item.icon() if item is not None else QIcon()
            except Exception:
                icon = QIcon()
            # 目标边长（为描边留出 1-2px 余量）
            side = min(r.width(), r.height()) - 2
            if side < 2:
                side = max(1, side)
            # 从图标获取较大底图，再二次等比缩放，避免锯齿
            base_pix = icon.pixmap(512, 512) if not icon.isNull() else QPixmap()
            if not base_pix.isNull():
                scaled = base_pix.scaled(side, side, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                x = r.x() + (r.width() - scaled.width()) // 2
                y = r.y() + (r.height() - scaled.height()) // 2
                painter.drawPixmap(x, y, scaled)
            painter.restore()
            # 选中项叠加序号：居中于正方形方框中央，主题色文字
            if not (option.state & QStyle.State_Selected):
                return

            try:
                item = self.parent.image_list.item(index.row())
                order = self.parent.selection_order.index(item) + 1
            except (ValueError, AttributeError):
                return # 如果 item 不在选择顺序列表中，则不绘制序号

            painter.save()
            painter.setRenderHint(QPainter.Antialiasing, True)
            try:
                hi_col = pal.color(pal.ColorRole.Highlight)
            except Exception:
                hi_col = pal.highlight().color()  # type: ignore
            painter.setPen(QPen(hi_col))
            font = painter.font()
            font.setBold(True)
            # 字号按方框尺寸自适应
            font.setPointSize(max(9, int(min(frame_rect.width(), frame_rect.height()) * 0.35)))
            painter.setFont(font)
            painter.drawText(frame_rect, Qt.AlignCenter, str(order))
            painter.restore()

    def _make_ctrl_wheel_zoom(self, original_handler):
        def handler(event):
            if event.modifiers() & Qt.ControlModifier:
                delta = event.angleDelta().y()
                step = 10 if delta > 0 else -10
                new_val = max(10, min(300, self.thumb_slider.value() + step))
                if new_val != self.thumb_slider.value():
                    self.thumb_slider.setValue(new_val)
                event.accept()
            else:
                original_handler(event)
        return handler

    def _on_thumb_size_changed(self, value: int):
        self._thumb_size = value
        self.thumb_size_label.setText(f"{value}px")
        # 更新图标大小
        if hasattr(self, 'image_list'):
            self.image_list.setIconSize(self._calc_icon_size())
            self._apply_list_grid(self.image_list)
            # 强制刷新几何和重绘
            try:
                self.image_list.updateGeometries()
            except Exception:
                pass
            self.image_list.viewport().update()

    def _style_accent_button(self, btn: QPushButton):
        # 使用当前主题的高亮色作为按钮底色，保证文字可读性
        pal = self.palette()
        try:
            highlight = pal.color(pal.ColorRole.Highlight)
            text_col = pal.color(pal.ColorRole.HighlightedText)
        except Exception:
            highlight = pal.highlight().color()  # type: ignore
            text_col = pal.highlightedText().color()  # type: ignore
        bg = f"rgb({highlight.red()},{highlight.green()},{highlight.blue()})"
        fg = f"rgb({text_col.red()},{text_col.green()},{text_col.blue()})"
        btn.setStyleSheet(
            f"QPushButton {{ font-weight: 600; border-radius: 6px; padding: 8px 12px; background-color: {bg}; color: {fg}; }}"
            "QPushButton:disabled { opacity: 0.6; }"
        )

    def _update_summary(self):
        total = self.image_list.count() if hasattr(self, 'image_list') else 0
        selected = len(self.image_list.selectedIndexes()) if hasattr(self, 'image_list') else 0
        self.selection_summary_label.setText(f"已加载: {total} 张 | 已选择: {selected} 张")
        if hasattr(self, 'image_list'):
            self.image_list.viewport().update()

    def _select_all(self):
        self.image_list.selectAll()
        # 更新选择顺序列表
        self.selection_order = [self.image_list.item(i) for i in range(self.image_list.count())]
        self._update_summary()

    def _select_none(self):
        self.image_list.clearSelection()
        # 更新选择顺序列表
        self.selection_order = []
        self._update_summary()

    def _invert_selection(self):
        current_selection = set(self.image_list.selectedItems())
        all_items = [self.image_list.item(i) for i in range(self.image_list.count())]
        
        # 清空当前选择和顺序
        self.image_list.clearSelection()
        self.selection_order = []

        # 重新选择并构建顺序
        for item in all_items:
            if item not in current_selection:
                item.setSelected(True) # 这会自动触发 itemSelectionChanged
                if item not in self.selection_order:
                     self.selection_order.append(item) # 手动维护顺序

        self._update_summary()

    def _on_item_clicked_for_ordering(self, item: QListWidgetItem):
        """根据点击更新 selection_order 列表"""
        if item.isSelected():
            if item not in self.selection_order:
                self.selection_order.append(item)
        else:
            if item in self.selection_order:
                self.selection_order.remove(item)
        
        # 强制重绘所有可见项以更新序号
        self.image_list.viewport().update()

    def _on_selection_changed(self):
        self._update_summary()

    def _on_directory_changed(self, path):
        """目录内容发生变化时自动刷新"""
        self.log(f"🔄 检测到目录变化，自动刷新图片列表...")
        QTimer.singleShot(500, lambda: self._load_images_for_preview(path))  # 延迟500ms避免频繁刷新

    def _on_item_double_clicked(self, item: QListWidgetItem):
        """双击缩略图：用系统默认程序打开图片文件"""
        try:
            path = item.data(self.ROLE_PATH) if item else None
            if path and os.path.exists(path):
                if sys.platform.startswith('win'):
                    os.startfile(path)  # type: ignore[attr-defined]
                else:
                    QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            else:
                QMessageBox.information(self, "提示", "未找到有效的文件路径")
        except Exception as e:
            QMessageBox.warning(self, "打开失败", f"无法打开文件:\n{path}\n\n{e}")

    def open_output_dir(self):
        """打开输出目录（所选目录下的 stitch），不存在则创建"""
        try:
            base_dir = Path(self.dir_edit.text().strip() or Path.home())
            out_dir = base_dir / "stitch"
            out_dir.mkdir(parents=True, exist_ok=True)
            p = str(out_dir)
            if sys.platform.startswith('win'):
                os.startfile(p)  # type: ignore
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(p))
        except Exception as e:
            QMessageBox.warning(self, "打开失败", f"无法打开输出目录:\n{e}")

    def _auto_order_by_name(self):
        # 取已选行按文件名排序后从1开始编号
        items = []
        for i in range(self.image_list.count()):
            it = self.image_list.item(i)
            if it and it.checkState() == Qt.Checked:
                path = it.data(self.ROLE_PATH)
                items.append((i, os.path.basename(path)))
        items.sort(key=lambda x: x[1].lower())
        for order, (i, _) in enumerate(items, start=1):
            it = self.image_list.item(i)
            it.setData(self.ROLE_ORDER, order)
            self._update_item_text(it)

    def _clear_order(self):
        for i in range(self.image_list.count()):
            it = self.image_list.item(i)
            if it:
                it.setData(self.ROLE_ORDER, 0)
                self._update_item_text(it)

    def _load_images_for_preview(self, directory: str):
        # 清空并填充列表
        self.image_list.clear()
        stitcher = ImageStitcher()
        paths = stitcher.load_images(directory)
        for path in paths:
            self._add_image_item(path)
        self._update_summary()
        # 清空旧的选择
        self.selection_order = []
        self.image_list.clearSelection()

    def _add_image_item(self, path: str):
        pix = QPixmap(path)
        icon = QIcon(pix)
        item = QListWidgetItem(icon, "")
        item.setData(self.ROLE_PATH, path)
        item.setFlags(item.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        item.setToolTip(os.path.basename(path))
        self.image_list.addItem(item)

    def _update_item_text(self, item: QListWidgetItem):
        # 保持无文字，使用工具提示展示文件名
        item.setText("")

    def _on_list_context_menu(self, pos: QPoint):
        item = self.image_list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        act_set_order = QAction("设置序号…", self)
        act_clear_order = QAction("清除序号", self)
        act_toggle_mark = QAction("切换标记", self)
        menu.addAction(act_set_order)
        menu.addAction(act_clear_order)
        menu.addSeparator()
        menu.addAction(act_toggle_mark)

        def do_set_order():
            val, ok = QInputDialog.getInt(self, "设置序号", "序号 (>=1):", value=max(1, int(item.data(self.ROLE_ORDER) or 1)), min=1, max=9999)
            if ok:
                item.setData(self.ROLE_ORDER, int(val))
                self._update_item_text(item)

        def do_clear_order():
            item.setData(self.ROLE_ORDER, 0)
            self._update_item_text(item)

        def do_toggle_mark():
            cur = bool(item.data(self.ROLE_MARK))
            item.setData(self.ROLE_MARK, (not cur))
            self._update_item_text(item)

        act_set_order.triggered.connect(do_set_order)
        act_clear_order.triggered.connect(do_clear_order)
        act_toggle_mark.triggered.connect(do_toggle_mark)
        menu.exec(self.image_list.mapToGlobal(pos))
    
    def log(self, message: str):
        """添加日志（始终自动滚动到底部）"""
        self.log_text.append(message)
        # 方式1：滚动条拉到最底
        sb = self.log_text.verticalScrollBar()
        sb.setValue(sb.maximum())
        # 方式2：移动光标确保可见（双保险）
        try:
            cursor = self.log_text.textCursor()
            cursor.movePosition(cursor.End)
            self.log_text.setTextCursor(cursor)
            self.log_text.ensureCursorVisible()
        except Exception:
            pass
    
    def _apply_global_styles(self):
        """应用全局样式（占位方法）"""
        pass
    
    def browse_directory(self):
        """浏览选择目录"""
        directory = QFileDialog.getExistingDirectory(
            self, "选择图片目录", 
            self.dir_edit.text() or str(Path.home())
        )
        if directory:
            # 移除旧的监控
            old_dirs = self.file_watcher.directories()
            if old_dirs:
                self.file_watcher.removePaths(old_dirs)
            
            # 添加新的监控
            self.file_watcher.addPath(directory)
            
            self.dir_edit.setText(directory)
            self.log(f"📁 已选择目录: {directory}")
            self.log("👁️ 已启用实时监控，目录变化将自动刷新")
            self.selection_order = [] # 清空旧目录的选择顺序
            self._load_images_for_preview(directory)
    
    def start_stitching(self):
        """开始拼接"""
        directory = self.dir_edit.text().strip()
        if not directory:
            QMessageBox.warning(self, "警告", "请先选择图片目录")
            return
        if not os.path.isdir(directory):
            QMessageBox.warning(self, "警告", "选择的目录不存在")
            return
        self.start_btn.setEnabled(False)
        self.browse_btn.setEnabled(False)
        # 视觉反馈
        pal = self.palette()
        try:
            win_col = pal.color(pal.ColorRole.Window); txt_col = pal.color(pal.ColorRole.Text); hi_col = pal.color(pal.ColorRole.Highlight)
        except Exception:
            win_col = pal.window().color(); txt_col = pal.text().color(); hi_col = pal.highlight().color()  # type: ignore
        self.preview_label.setText("⏳ 正在处理，请稍候...")
        self.preview_label.setStyleSheet(
            "QLabel { "
            f"background-color: rgb({win_col.red()},{win_col.green()},{win_col.blue()}); "
            f"border: 2px solid rgb({hi_col.red()},{hi_col.green()},{hi_col.blue()}); padding: 20px; font-size: 14px; "
            "}"
        )
        # 模式
        mode = 'scans'; mode_name = '扫描模式'
        # 需要处理的文件列表
        if self.selection_order:
            image_paths_for_job = [it.data(self.ROLE_PATH) for it in self.selection_order if it]
        else:
            image_paths_for_job = [self.image_list.item(i).data(self.ROLE_PATH) for i in range(self.image_list.count()) if self.image_list.item(i)]
        image_paths_for_job = [p for p in image_paths_for_job if p]
        if not image_paths_for_job:
            QMessageBox.warning(self, "警告", "没有要处理的图片。请选择图片或确保目录不为空。")
            self.start_btn.setEnabled(True); self.browse_btn.setEnabled(True); return
        
        # 获取备选模式
        fallback_map = {
            "垂直拼接": "vertical",
            "水平拼接": "horizontal", 
            "网格拼接": "grid",
            "不使用备选": None
        }
        fallback_mode = fallback_map.get(self.fallback_combo.currentText(), "vertical")
        fallback_name = self.fallback_combo.currentText()
        
        # 直接开始，不再弹出确认对话框
        self.log(f"🚀 开始拼接 {len(image_paths_for_job)} 张图片")
        self.log(f"  模式: {mode_name}")
        self.log(f"  备选方案: {fallback_name}")
        
        # 启动线程
        self.stitch_thread = StitchThread(directory, mode, image_paths=image_paths_for_job, fallback_mode=fallback_mode)
        self.stitch_thread.progress.connect(self.update_progress)
        self.stitch_thread.finished.connect(self.on_stitch_finished)
        self.stitch_thread.error.connect(self.on_stitch_error)
        
        # 不再显示进度弹窗
        # self._progress_dialog = ProgressDialog(self, title="正在拼接")
        # self._progress_dialog.show()
        # self.stitch_thread.progress.connect(self._progress_dialog.update_progress)
        # self.stitch_thread.finished.connect(lambda: self._progress_dialog.finish(True))
        # self.stitch_thread.error.connect(lambda msg: self._progress_dialog.finish(False, msg))

        self.stitch_thread.start()
        self.start_btn.setEnabled(False)
        self.start_btn.setText("拼接中...")

    def update_progress(self, current, total, message):
        """更新主窗口的进度条和日志"""
        if total > 0:
            self.progress_bar.setValue(int((current / total) * 100))
        else:
            self.progress_bar.setValue(0)
        self.log(f"进度: {message}")

    def on_stitch_finished(self, results):
        """拼接完成后的处理"""
        self.progress_bar.setValue(100)
        
        self.log(f"📊 收到拼接结果，类型: {type(results)}, 长度: {len(results) if isinstance(results, list) else 'N/A'}")
        
        # 从results(列表的[(paths, image)])中提取纯图像列表
        image_list = []
        if isinstance(results, list) and len(results) > 0:
            for idx, item in enumerate(results):
                self.log(f"  结果 {idx+1}: 类型={type(item)}, 是元组={isinstance(item, tuple)}, len={len(item) if isinstance(item, (list, tuple)) else 'N/A'}")
                # item 是 (paths, img) 元组
                if isinstance(item, tuple) and len(item) == 2:
                    paths, img = item
                    self.log(f"  - 路径数: {len(paths) if isinstance(paths, list) else 'N/A'}")
                    self.log(f"  - 图像: {type(img)}, shape: {img.shape if img is not None and hasattr(img, 'shape') else 'None'}")
                    if img is not None and hasattr(img, 'shape'):
                        image_list.append(img)
                    else:
                        self.log(f"  - 警告: 图像为空或无效")
                elif isinstance(item, np.ndarray):  # 如果直接是图像数组
                    self.log(f"  - 直接图像数组: shape={item.shape}")
                    image_list.append(item)
                else:
                    self.log(f"  - 警告: 无法识别的结果类型")
        else:
            self.log(f"  警告: results 不是列表或为空")
        
        if not image_list:
            self.log("❌ 拼接完成但没有生成任何结果图像")
            self.log("   请检查图片是否有足够的重叠区域，或尝试使用备选拼接模式")
            QMessageBox.warning(self, "拼接失败", "没有生成任何拼接结果\n\n请检查：\n1. 图片是否有重叠区域\n2. 尝试选择备选拼接模式（垂直/水平/网格）")
            self.start_btn.setEnabled(True)
            self.start_btn.setText("🚀 开始拼接")
            return
        
        self.log(f"✅ 拼接完成！共生成 {len(image_list)} 张图片。")
        
        self.result_images = image_list  # 保存纯图像列表
        self._refresh_results_preview() # 刷新多结果网格

        # 保存所有结果到文件
        self.save_all_results()

        self.start_btn.setEnabled(True)
        self.start_btn.setText("🚀 开始拼接")
        
        # 清理临时文件
        temp_dir = Path(self.dir_edit.text().strip()) / "stitch_temp"
        if temp_dir.exists():
            try:
                import shutil
                shutil.rmtree(temp_dir)
                self.log("🧹 清理了临时文件。")
            except Exception as e:
                self.log(f"⚠️ 清理临时文件失败: {e}")

    def on_stitch_error(self, message):
        """拼接出错的处理"""
        self.progress_bar.setValue(0)
        self.log(f"❌ 错误: {message}")
        QMessageBox.warning(self, "拼接失败", message)
        self.start_btn.setEnabled(True)
        self.start_btn.setText("🚀 开始拼接")
        
        # 清理临时文件
        temp_dir = Path(self.dir_edit.text().strip()) / "stitch_temp"
        if temp_dir.exists():
            try:
                import shutil
                shutil.rmtree(temp_dir)
                self.log("清理了临时文件。")
            except Exception as e:
                self.log(f"清理临时文件失败: {e}")

    def _refresh_results_preview(self):
        """根据结果数量，决定显示单图还是多图网格"""
        if not hasattr(self, 'result_images') or not self.result_images:
            self.preview_label.setVisible(True)
            self.result_scroll.setVisible(False)
            return

        if len(self.result_images) == 1:
            self.preview_label.setVisible(True)
            self.result_scroll.setVisible(False)
            pano = self.result_images[0]  # 直接获取图像
            self.display_image(pano)
        else:
            self.preview_label.setVisible(False)
            self.result_scroll.setVisible(True)
            self._populate_result_grid()

    def _populate_result_grid(self):
        """用拼接结果填充网格"""
        # 清空旧网格
        for i in reversed(range(self.result_grid.count())): 
            widget = self.result_grid.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()

        cols = max(1, self.result_scroll.width() // 200) # 每列约200px
        
        for i, pano in enumerate(self.result_images):  # 直接遍历图像列表
            row, col = divmod(i, cols)
            
            # 创建一个容器来显示图片和信息
            container = QWidget()
            layout = QVBoxLayout(container)
            
            label = QLabel()
            label.setAlignment(Qt.AlignCenter)
            
            # 将OpenCV图像转为QPixmap
            if pano is None: 
                continue
            
            # 确保图像是连续的内存布局
            pano = np.ascontiguousarray(pano)
            h, w = pano.shape[:2]
            
            if pano.ndim == 3:
                if pano.shape[2] == 4: # BGRA
                    q_img = QImage(pano.data, w, h, pano.strides[0], QImage.Format_BGRA8888)
                elif pano.shape[2] == 3: # BGR
                    q_img = QImage(pano.data, w, h, pano.strides[0], QImage.Format_BGR888).rgbSwapped()
                else:
                    continue
            elif pano.ndim == 2: # Grayscale
                q_img = QImage(pano.data, w, h, pano.strides[0], QImage.Format_Grayscale8)
            else:
                continue

            pixmap = QPixmap.fromImage(q_img)
            label.setPixmap(pixmap.scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            
            info_label = QLabel(f"结果 {i+1}")
            info_label.setAlignment(Qt.AlignCenter)
            
            layout.addWidget(label)
            layout.addWidget(info_label)
            
            self.result_grid.addWidget(container, row, col)

    def save_all_results(self):
        """保存所有拼接结果"""
        if not hasattr(self, 'result_images') or not self.result_images:
            self.log("⚠️ 没有可保存的结果。")
            return

        base_dir = self.dir_edit.text().strip()
        if not base_dir:
            self.log("⚠️ 保存失败：未设置目录。")
            return
        
        output_dir = Path(base_dir) / "stitch"
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            self.log(f"📁 输出目录: {output_dir}")
            self.log(f"📁 输出目录(绝对路径): {output_dir.absolute()}")
        except Exception as e:
            self.log(f"❌ 无法创建输出目录: {e}")
            QMessageBox.critical(self, "错误", f"无法创建输出目录:\n{e}")
            return

        # 获取选择的格式
        output_format = self.format_combo.currentText().split(" ")[0].lower()
        ext = ".jpg" if output_format == "jpeg" else f".{output_format}"

        params = []
        if output_format == "jpeg":
            params = [cv2.IMWRITE_JPEG_QUALITY, 100]
        elif output_format == "png":
            params = [cv2.IMWRITE_PNG_COMPRESSION, 0] # 0=无压缩，质量最高
        elif output_format == "webp":
            params = [cv2.IMWRITE_WEBP_QUALITY, 101] # 101=无损

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved_count = 0
        
        # 直接遍历图像列表
        for i, pano in enumerate(self.result_images, start=1):
            if pano is None: 
                self.log(f"⚠️ 跳过空结果 {i}")
                continue
            
            filename = output_dir / f"stitched_{timestamp}_{i}{ext}"
            self.log(f"💾 正在保存 {i}/{len(self.result_images)}: {filename.name}")
            self.log(f"   图像信息: shape={pano.shape}, dtype={pano.dtype}")
            
            try:
                # 检查图像维度
                if len(pano.shape) < 2:
                    self.log(f"❌ 图像 {i} 维度错误: {pano.shape}")
                    continue
                
                # 确保图像是连续的内存布局
                pano = np.ascontiguousarray(pano)
                
                # 根据格式和通道数选择保存方式
                save_img = None
                if output_format in ['png', 'webp']:
                    # PNG和WebP支持透明通道
                    if len(pano.shape) == 3 and pano.shape[2] == 4:
                        # BGRA格式，直接保存
                        save_img = pano
                        self.log(f"   使用BGRA格式保存")
                    elif len(pano.shape) == 3 and pano.shape[2] == 3:
                        # BGR格式，直接保存
                        save_img = pano
                        self.log(f"   使用BGR格式保存")
                    else:
                        # 灰度图
                        save_img = pano
                        self.log(f"   使用灰度格式保存")
                else:
                    # JPEG不支持透明通道
                    if len(pano.shape) == 3 and pano.shape[2] == 4:
                        # BGRA转BGR
                        save_img = cv2.cvtColor(pano, cv2.COLOR_BGRA2BGR)
                        self.log(f"   BGRA转BGR后保存")
                    elif len(pano.shape) == 3 and pano.shape[2] == 3:
                        save_img = pano
                        self.log(f"   使用BGR格式保存")
                    else:
                        save_img = pano
                        self.log(f"   使用灰度格式保存")
                
                # 保存文件
                self.log(f"   调用cv2.imwrite: {filename.absolute()}")
                success = cv2.imwrite(str(filename.absolute()), save_img, params)
                
                if success:
                    # 验证文件是否真的被创建
                    if filename.exists():
                        file_size = filename.stat().st_size
                        saved_count += 1
                        self.log(f"✅ 成功保存: {filename.name} ({file_size / 1024:.1f} KB)")
                    else:
                        self.log(f"❌ cv2.imwrite返回True但文件不存在: {filename}")
                        self.log(f"   请检查磁盘空间和文件权限")
                else:
                    self.log(f"❌ cv2.imwrite返回False: {filename}")
                    
            except Exception as e:
                import traceback
                self.log(f"❌ 保存异常 {filename.name}: {e}")
                self.log(f"   详细错误:\n{traceback.format_exc()}")
        
        if saved_count > 0:
            self.log(f"🎉 保存完成！共保存 {saved_count}/{len(self.result_images)} 个文件")
            self.log(f"📂 文件位置: {output_dir.absolute()}")
            QMessageBox.information(self, "保存成功", f"成功保存 {saved_count} 张拼接图片到:\n{output_dir.absolute()}")
        else:
            self.log(f"❌ 没有成功保存任何文件，请检查上述错误信息")
            QMessageBox.warning(self, "保存失败", "没有成功保存任何文件，请查看日志了解详情")

    def display_image(self, cv_img):
        """在预览标签中显示OpenCV图像"""
        if cv_img is None:
            self.preview_label.setText("拼接失败或没有结果")
            self.preview_label.setPixmap(QPixmap())
            return

        # 确保图像是连续的内存布局
        cv_img = np.ascontiguousarray(cv_img)
        self.result_image = cv_img.copy()
        
        h, w = cv_img.shape[:2]
        
        # 根据维度和通道数确定格式
        if cv_img.ndim == 3:
            if cv_img.shape[2] == 4: # BGRA
                q_img = QImage(cv_img.data, w, h, cv_img.strides[0], QImage.Format_BGRA8888)
            elif cv_img.shape[2] == 3: # BGR
                q_img = QImage(cv_img.data, w, h, cv_img.strides[0], QImage.Format_BGR888).rgbSwapped()
            else:
                # 不支持的通道数，转换为BGR
                cv_img_bgr = cv2.cvtColor(cv_img, cv2.COLOR_GRAY2BGR)
                q_img = QImage(cv_img_bgr.data, w, h, cv_img_bgr.strides[0], QImage.Format_BGR888).rgbSwapped()
        elif cv_img.ndim == 2: # Grayscale
            q_img = QImage(cv_img.data, w, h, cv_img.strides[0], QImage.Format_Grayscale8)
        else:
            self.preview_label.setText(f"不支持的图像格式: {cv_img.shape}")
            return

        pixmap = QPixmap.fromImage(q_img)
        
        # 缩放以适应标签大小
        self.preview_label.setPixmap(pixmap.scaled(
            self.preview_label.size(), 
            Qt.KeepAspectRatio, 
            Qt.SmoothTransformation
        ))

    def save_result(self):
        """保存单个拼接结果（此功能在多图输出模式下可能需要调整）"""
        if self.result_image is None:
            QMessageBox.information(self, "提示", "没有可保存的拼接结果")
            return

        base_dir = self.dir_edit.text().strip()
        if not base_dir:
            QMessageBox.warning(self, "错误", "请先选择一个目录")
            return
        
        output_dir = Path(base_dir) / "stitch"
        output_dir.mkdir(exist_ok=True)
        
        # 使用时间戳命名
        filename = f"stitched_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        save_path = str(output_dir / filename)
        
        try:
            # PNG 支持透明通道，直接保存
            cv2.imwrite(save_path, self.result_image, [cv2.IMWRITE_PNG_COMPRESSION, 0])
            self.log(f"💾 结果已保存到: {save_path}")
            QMessageBox.information(self, "保存成功", f"结果已保存到:\n{save_path}")
        except Exception as e:
            self.log(f"❌ 保存失败: {e}")
            QMessageBox.critical(self, "保存失败", f"无法保存文件:\n{e}")

    def _restore_settings(self):
        """恢复上次关闭时的设置"""
        settings = QSettings("AYE", "OpenCVStitcher")
        self.restoreGeometry(settings.value("geometry"))
        last_dir = settings.value("last_dir", "")
        self.dir_edit.setText(last_dir)
        if last_dir and os.path.isdir(last_dir):
            # 添加文件监控
            self.file_watcher.addPath(last_dir)
            self.log(f"👁️ 已启用实时监控: {last_dir}")
            self._load_images_for_preview(last_dir)
        self.h_splitter.restoreState(settings.value("hsplitter_state"))
        self.vsplitter.restoreState(settings.value("vsplitter_state"))
        self.thumb_slider.setValue(int(settings.value("thumb_size", self._thumb_size)))
        self.format_combo.setCurrentText(settings.value("output_format", "PNG"))
        self.fallback_combo.setCurrentText(settings.value("fallback_mode", "垂直拼接"))

    def closeEvent(self, event):
        """关闭窗口时保存设置"""
        settings = QSettings("AYE", "OpenCVStitcher")
        settings.setValue("last_dir", self.dir_edit.text())
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("hsplitter_state", self.h_splitter.saveState())
        settings.setValue("vsplitter_state", self.vsplitter.saveState())
        settings.setValue("thumb_size", self.thumb_slider.value())
        settings.setValue("output_format", self.format_combo.currentText())
        settings.setValue("fallback_mode", self.fallback_combo.currentText())
        super().closeEvent(event)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())