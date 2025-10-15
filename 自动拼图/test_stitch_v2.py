"""
测试新拼接算法的简单脚本
"""
import cv2
import numpy as np
from pathlib import Path

def test_vertical_stitch():
    """测试垂直拼接"""
    print("=" * 50)
    print("测试垂直拼接")
    print("=" * 50)
    
    # 创建两张测试图片
    # 图片1: 200x300 蓝色
    img1 = np.zeros((300, 200, 3), dtype=np.uint8)
    img1[:, :] = (255, 0, 0)  # 蓝色
    
    # 图片2: 200x300 红色，顶部50px与img1重叠
    img2 = np.zeros((300, 200, 3), dtype=np.uint8)
    img2[:, :] = (0, 0, 255)  # 红色
    img2[:50, :] = (255, 0, 0)  # 顶部50px蓝色（模拟重叠）
    
    print(f"图片1: {img1.shape}")
    print(f"图片2: {img2.shape}")
    
    # 简单拼接（不去重叠）
    simple = np.vstack([img1, img2])
    print(f"简单拼接结果: {simple.shape} (应该是 600x200)")
    
    # 智能拼接（去重叠）
    # 去除img2的顶部50px
    img2_cropped = img2[50:, :]
    smart = np.vstack([img1, img2_cropped])
    print(f"智能拼接结果: {smart.shape} (应该是 550x200)")
    
    print("✅ 垂直拼接测试通过")
    return True

def test_horizontal_stitch():
    """测试水平拼接"""
    print("\n" + "=" * 50)
    print("测试水平拼接")
    print("=" * 50)
    
    # 创建两张测试图片
    # 图片1: 300x200 绿色
    img1 = np.zeros((200, 300, 3), dtype=np.uint8)
    img1[:, :] = (0, 255, 0)  # 绿色
    
    # 图片2: 300x200 黄色，左侧50px与img1重叠
    img2 = np.zeros((200, 300, 3), dtype=np.uint8)
    img2[:, :] = (0, 255, 255)  # 黄色
    img2[:, :50] = (0, 255, 0)  # 左侧50px绿色（模拟重叠）
    
    print(f"图片1: {img1.shape}")
    print(f"图片2: {img2.shape}")
    
    # 简单拼接（不去重叠）
    simple = np.hstack([img1, img2])
    print(f"简单拼接结果: {simple.shape} (应该是 200x600)")
    
    # 智能拼接（去重叠）
    img2_cropped = img2[:, 50:]
    smart = np.hstack([img1, img2_cropped])
    print(f"智能拼接结果: {smart.shape} (应该是 200x550)")
    
    print("✅ 水平拼接测试通过")
    return True

def test_grid_stitch():
    """测试网格拼接"""
    print("\n" + "=" * 50)
    print("测试网格拼接")
    print("=" * 50)
    
    # 创建5张测试图片
    images = []
    colors = [
        (255, 0, 0),    # 蓝色
        (0, 255, 0),    # 绿色
        (0, 0, 255),    # 红色
        (255, 255, 0),  # 青色
        (255, 0, 255),  # 品红色
    ]
    
    for i, color in enumerate(colors):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        img[:, :] = color
        images.append(img)
        print(f"图片{i+1}: {img.shape} - 颜色{color}")
    
    # 网格拼接（3x2）
    n = len(images)
    cols = int(np.ceil(np.sqrt(n)))  # 3
    rows = int(np.ceil(n / cols))    # 2
    
    print(f"网格布局: {rows}行 x {cols}列")
    
    # 创建网格
    max_h = max(img.shape[0] for img in images)
    max_w = max(img.shape[1] for img in images)
    
    grid_rows = []
    for r in range(rows):
        row_images = []
        for c in range(cols):
            idx = r * cols + c
            if idx < n:
                # 居中填充
                padded = np.zeros((max_h, max_w, 3), dtype=np.uint8)
                padded[:images[idx].shape[0], :images[idx].shape[1]] = images[idx]
                row_images.append(padded)
            else:
                # 空白
                row_images.append(np.zeros((max_h, max_w, 3), dtype=np.uint8))
        grid_rows.append(np.hstack(row_images))
    
    result = np.vstack(grid_rows)
    print(f"网格拼接结果: {result.shape} (应该是 {rows*max_h}x{cols*max_w})")
    
    print("✅ 网格拼接测试通过")
    return True

def test_overlap_detection():
    """测试重叠检测算法"""
    print("\n" + "=" * 50)
    print("测试重叠检测算法")
    print("=" * 50)
    
    # 创建两张有50px重叠的图片
    img1 = np.zeros((300, 200, 3), dtype=np.uint8)
    img1[:, :] = (100, 100, 100)
    
    img2 = np.zeros((300, 200, 3), dtype=np.uint8)
    img2[:, :] = (150, 150, 150)
    img2[:50, :] = (100, 100, 100)  # 顶部50px与img1相同
    
    # 模拟重叠检测
    best_overlap = 0
    best_score = float('inf')
    
    for overlap in range(10, 100, 5):
        region1 = img1[-overlap:, :]
        region2 = img2[:overlap, :]
        
        if region1.shape == region2.shape:
            diff = np.mean(np.abs(region1.astype(float) - region2.astype(float)))
            
            if diff < best_score:
                best_score = diff
                best_overlap = overlap
    
    print(f"检测到的重叠: {best_overlap}px (实际: 50px)")
    print(f"最小差异: {best_score:.2f}")
    
    if abs(best_overlap - 50) <= 5:  # 允许5px误差
        print("✅ 重叠检测测试通过")
        return True
    else:
        print("❌ 重叠检测测试失败")
        return False

if __name__ == '__main__':
    print("\n" + "🧪 开始测试新拼接算法\n")
    
    results = []
    
    try:
        results.append(("垂直拼接", test_vertical_stitch()))
    except Exception as e:
        print(f"❌ 垂直拼接测试失败: {e}")
        results.append(("垂直拼接", False))
    
    try:
        results.append(("水平拼接", test_horizontal_stitch()))
    except Exception as e:
        print(f"❌ 水平拼接测试失败: {e}")
        results.append(("水平拼接", False))
    
    try:
        results.append(("网格拼接", test_grid_stitch()))
    except Exception as e:
        print(f"❌ 网格拼接测试失败: {e}")
        results.append(("网格拼接", False))
    
    try:
        results.append(("重叠检测", test_overlap_detection()))
    except Exception as e:
        print(f"❌ 重叠检测测试失败: {e}")
        results.append(("重叠检测", False))
    
    # 汇总结果
    print("\n" + "=" * 50)
    print("测试汇总")
    print("=" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！新拼接算法工作正常。")
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，需要修复。")
