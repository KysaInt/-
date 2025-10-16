"""
截图滚动区域识别与裁切工具
自动识别截图中的滚动区域边界,并进行批量裁切
支持实时调整灵敏度参数
"""

import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional
import sys

# 全局变量用于存储当前的参数和图像
g_sensitivity = 150  # 灵敏度 (50-300), 值越大越宽松
g_min_length = 20    # 最小连续长度 (5-50)
g_blur_size = 11     # 高斯模糊大小 (3-21,奇数)
g_current_boundary = None
g_sample_images = []
g_preview_img = None
g_original_img = None


def find_scroll_region_boundary(image: np.ndarray, threshold: int = 10) -> Optional[Tuple[int, int, int, int]]:
    """
    识别图片中的滚动区域边界
    
    通过分析图像的统一区域(如状态栏、标题栏)来确定内容区域
    
    Args:
        image: 输入图像
        threshold: 边缘检测阈值
    
    Returns:
        (x, y, width, height) 滚动内容区域的边界,如果识别失败则返回 None
    """
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # 计算每一行的方差,内容丰富的区域方差较大,状态栏等区域方差较小
    row_variance = np.var(gray, axis=1)
    col_variance = np.var(gray, axis=0)
    
    # 计算方差的阈值(使用中位数)
    row_threshold = np.median(row_variance) * 0.3
    col_threshold = np.median(col_variance) * 0.3
    
    # 从上边缘开始扫描,找到内容开始的位置
    top_margin = 0
    for y in range(height):
        if row_variance[y] > row_threshold:
            top_margin = y
            break
    
    # 从下边缘开始扫描
    bottom_margin = height
    for y in range(height - 1, -1, -1):
        if row_variance[y] > row_threshold:
            bottom_margin = y + 1
            break
    
    # 从左边缘开始扫描
    left_margin = 0
    for x in range(width):
        if col_variance[x] > col_threshold:
            left_margin = x
            break
    
    # 从右边缘开始扫描
    right_margin = width
    for x in range(width - 1, -1, -1):
        if col_variance[x] > col_threshold:
            right_margin = x + 1
            break
    
    # 如果识别的区域太小,可能是识别失败
    content_width = right_margin - left_margin
    content_height = bottom_margin - top_margin
    
    if content_width < width * 0.5 or content_height < height * 0.5:
        return None
    
    return (left_margin, top_margin, content_width, content_height)


def find_common_boundary(images: List[np.ndarray], sensitivity: float = 1.5, 
                         min_length: int = 20, blur_size: int = 11) -> Tuple[int, int, int, int]:
    """
    从多张图片中找到公共的滚动区域边界
    通过比较多张图片找到不变的区域(如状态栏),从而识别出内容区域
    使用更宽松的阈值来忽略状态栏图标闪烁等小变化
    
    Args:
        images: 图像列表
        sensitivity: 灵敏度系数 (0.5-3.0), 值越大越宽松,越能忽略小变化
        min_length: 连续超过阈值的最小像素数,避免误判
        blur_size: 高斯模糊核大小(奇数),越大越能忽略细节变化
    
    Returns:
        (x, y, width, height) 公共边界
    """
    if not images:
        return (0, 0, 100, 100)
    
    height, width = images[0].shape[:2]
    
    # 如果只有一张图片,使用单图识别
    if len(images) == 1:
        boundary = find_scroll_region_boundary(images[0])
        if boundary:
            return boundary
        return (0, 0, width, height)
    
    # 确保 blur_size 是奇数
    if blur_size % 2 == 0:
        blur_size += 1
    blur_size = max(3, min(21, blur_size))
    
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
    
    # 如果识别结果不合理,返回原始尺寸
    if content_width < width * 0.3 or content_height < height * 0.3:
        return (0, 0, width, height)
    
    return (left_margin, top_margin, content_width, content_height)


def imread_unicode(file_path: str) -> Optional[np.ndarray]:
    """
    使用 numpy 读取包含 Unicode 字符的文件路径
    
    Args:
        file_path: 文件路径
    
    Returns:
        图像数据,如果读取失败则返回 None
    """
    try:
        # 使用 numpy 读取文件,然后用 cv2 解码
        with open(file_path, 'rb') as f:
            file_bytes = np.frombuffer(f.read(), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        return img
    except Exception as e:
        print(f"读取文件失败: {file_path}, 错误: {e}")
        return None


def imwrite_unicode(file_path: str, img: np.ndarray) -> bool:
    """
    保存图像到包含 Unicode 字符的文件路径
    
    Args:
        file_path: 文件路径
        img: 图像数据
    
    Returns:
        是否成功
    """
    try:
        # 编码图像并写入文件
        ext = Path(file_path).suffix
        success, encoded = cv2.imencode(ext, img)
        if success:
            with open(file_path, 'wb') as f:
                f.write(encoded)
            return True
        return False
    except Exception as e:
        print(f"保存文件失败: {file_path}, 错误: {e}")
        return False


def interactive_crop_preview(images: List[np.ndarray]) -> Optional[Tuple[int, int, int, int]]:
    """
    交互式裁切预览界面
    
    Args:
        images: 图像列表
    
    Returns:
        用户确认的边界,如果取消则返回 None
    """
    global g_sample_images, g_original_img
    
    if not images:
        return None
    
    g_sample_images = images
    g_original_img = images[0].copy()
    
    # 参数初始值
    sensitivity = 1.5
    min_length = 20
    blur_size = 11
    
    window_name = '裁切区域调整'
    
    def draw_preview(sens, min_len, blur):
        """绘制预览图"""
        boundary = find_common_boundary(g_sample_images, sens, min_len, blur)
        x, y, width, height = boundary
        
        # 创建预览图像
        preview = g_original_img.copy()
        
        # 绘制原图边框(红色)
        cv2.rectangle(preview, (0, 0), (preview.shape[1]-1, preview.shape[0]-1), (0, 0, 255), 2)
        
        # 绘制裁切区域(绿色)
        cv2.rectangle(preview, (x, y), (x + width, y + height), (0, 255, 0), 3)
        
        # 添加半透明遮罩到非裁切区域
        mask = np.zeros_like(preview)
        mask[y:y+height, x:x+width] = preview[y:y+height, x:x+width]
        preview_dark = preview.copy()
        cv2.rectangle(preview_dark, (0, 0), (preview.shape[1], preview.shape[0]), (0, 0, 0), -1)
        preview = cv2.addWeighted(preview, 0.3, preview_dark, 0.7, 0)
        preview[y:y+height, x:x+width] = mask[y:y+height, x:x+width]
        
        # 添加文字信息
        font = cv2.FONT_HERSHEY_SIMPLEX
        img_h, img_w = preview.shape[:2]
        
        # 背景框
        cv2.rectangle(preview, (5, 5), (450, 160), (0, 0, 0), -1)
        cv2.rectangle(preview, (5, 5), (450, 160), (255, 255, 255), 2)
        
        # 文字信息
        cv2.putText(preview, f"Original: {img_w}x{img_h}", (10, 30), font, 0.6, (0, 0, 255), 2)
        cv2.putText(preview, f"Cropped: {width}x{height}", (10, 60), font, 0.6, (0, 255, 0), 2)
        cv2.putText(preview, f"Top:{y} Bottom:{img_h-y-height} Left:{x} Right:{img_w-x-width}", 
                    (10, 90), font, 0.45, (255, 255, 255), 1)
        cv2.putText(preview, f"Sensitivity:{sens:.2f} MinLen:{min_len} Blur:{blur}", 
                    (10, 120), font, 0.45, (200, 200, 200), 1)
        cv2.putText(preview, "Q/W/E: Sens, A/S: MinLen, Z/X: Blur, Enter: OK, ESC: Cancel", 
                    (10, 145), font, 0.4, (100, 255, 255), 1)
        
        # 缩放预览图以适应屏幕
        preview_height = 700
        preview_scale = preview_height / preview.shape[0]
        preview_width = int(preview.shape[1] * preview_scale)
        preview_resized = cv2.resize(preview, (preview_width, preview_height))
        
        return preview_resized, boundary
    
    # 创建窗口
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 1200, 800)
    
    print("\n" + "="*60)
    print("交互式裁切区域调整")
    print("="*60)
    print("参数说明:")
    print("  - 灵敏度(Sensitivity): 值越大越宽松,越能忽略小变化")
    print("  - 最小长度(MinLen): 连续变化的最小像素数")
    print("  - 模糊度(Blur): 值越大越能忽略细节变化")
    print("\n键盘操作:")
    print("  Q/W: 降低/提高灵敏度 (步长 0.1)")
    print("  E: 大幅提高灵敏度 (步长 0.5)")
    print("  A/S: 降低/提高最小长度")
    print("  Z/X: 降低/提高模糊度")
    print("  Enter/Space: 确认并开始批量裁切")
    print("  ESC: 取消")
    print("="*60 + "\n")
    
    # 主循环
    while True:
        preview_img, boundary = draw_preview(sensitivity, min_length, blur_size)
        cv2.imshow(window_name, preview_img)
        
        key = cv2.waitKey(50) & 0xFF
        
        if key == 13 or key == 32:  # Enter 或 Space
            cv2.destroyAllWindows()
            return boundary
        elif key == 27:  # ESC
            cv2.destroyAllWindows()
            return None
        # 灵敏度调整
        elif key == ord('q') or key == ord('Q'):
            sensitivity = max(0.5, sensitivity - 0.1)
            print(f"灵敏度: {sensitivity:.2f}")
        elif key == ord('w') or key == ord('W'):
            sensitivity = min(3.0, sensitivity + 0.1)
            print(f"灵敏度: {sensitivity:.2f}")
        elif key == ord('e') or key == ord('E'):
            sensitivity = min(3.0, sensitivity + 0.5)
            print(f"灵敏度: {sensitivity:.2f}")
        # 最小长度调整
        elif key == ord('a') or key == ord('A'):
            min_length = max(5, min_length - 5)
            print(f"最小长度: {min_length}")
        elif key == ord('s') or key == ord('S'):
            min_length = min(50, min_length + 5)
            print(f"最小长度: {min_length}")
        # 模糊度调整
        elif key == ord('z') or key == ord('Z'):
            blur_size = max(1, blur_size - 2)
            print(f"模糊度: {blur_size}")
        elif key == ord('x') or key == ord('X'):
            blur_size = min(21, blur_size + 2)
            print(f"模糊度: {blur_size}")
    
    return boundary


def crop_images(input_dir: Path, output_dir: Path, boundary: Tuple[int, int, int, int]) -> int:
    """
    根据边界裁切所有图片
    
    Args:
        input_dir: 输入目录
        output_dir: 输出目录
        boundary: 裁切边界 (x, y, width, height)
    
    Returns:
        处理的图片数量
    """
    x, y, width, height = boundary
    
    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 获取所有图片文件
    image_files = sorted(input_dir.glob('*.png')) + sorted(input_dir.glob('*.jpg')) + sorted(input_dir.glob('*.jpeg'))
    
    count = 0
    for img_path in image_files:
        # 读取图片(支持中文路径)
        img = imread_unicode(str(img_path))
        if img is None:
            print(f"警告: 无法读取图片 {img_path}")
            continue
        
        # 裁切
        cropped = img[y:y+height, x:x+width]
        
        # 保存到输出目录(支持中文路径)
        output_path = output_dir / img_path.name
        imwrite_unicode(str(output_path), cropped)
        
        count += 1
        print(f"已处理: {img_path.name} -> {output_path}")
    
    return count


def process_directory(input_dir: str):
    """
    处理指定目录中的所有截图
    
    Args:
        input_dir: 输入目录路径
    """
    input_path = Path(input_dir)
    
    if not input_path.exists():
        print(f"错误: 目录不存在 - {input_dir}")
        return
    
    # 创建输出目录
    output_path = input_path / "裁切后"
    
    print(f"正在处理目录: {input_path}")
    print(f"输出目录: {output_path}")
    
    # 获取所有图片文件
    image_files = sorted(input_path.glob('*.png')) + sorted(input_path.glob('*.jpg')) + sorted(input_path.glob('*.jpeg'))
    
    if not image_files:
        print("错误: 未找到任何图片文件")
        return
    
    print(f"找到 {len(image_files)} 个图片文件")
    
    # 读取所有图片用于识别边界(至少3张,最多全部)
    sample_size = min(len(image_files), max(3, len(image_files)))
    sample_images = []
    
    print(f"正在分析 {sample_size} 张图片以识别边界...")
    for img_path in image_files[:sample_size]:
        img = imread_unicode(str(img_path))
        if img is not None:
            sample_images.append(img)
    
    if not sample_images:
        print("错误: 无法读取任何图片")
        return
    
    # 使用交互式界面让用户调整参数
    boundary = interactive_crop_preview(sample_images)
    
    if boundary is None:
        print("\n已取消操作")
        return
    
    x, y, width, height = boundary
    print(f"\n最终裁切区域: x={x}, y={y}, width={width}, height={height}")
    print(f"  - 顶部边距: {y}px")
    print(f"  - 底部边距: {sample_images[0].shape[0] - y - height}px")
    print(f"  - 左侧边距: {x}px")
    print(f"  - 右侧边距: {sample_images[0].shape[1] - x - width}px")
    
    # 执行裁切
    print("\n开始裁切所有图片...")
    count = crop_images(input_path, output_path, boundary)
    
    print(f"\n完成! 共处理 {count} 张图片")
    print(f"裁切后的图片保存在: {output_path}")


def main():
    """主函数"""
    if len(sys.argv) > 1:
        input_dir = sys.argv[1]
    else:
        # 默认目录
        input_dir = r"C:\Users\94230\OneDrive\-\ss\autostitch_20251016_172540\1_原始截图"
    
    process_directory(input_dir)


if __name__ == "__main__":
    main()
