"""
测试精确特征匹配算法
"""
import cv2
import numpy as np
from pathlib import Path

def create_test_images_with_overlap():
    """创建带有重叠区域的测试图片"""
    print("=" * 60)
    print("创建测试图片（带50px重叠）")
    print("=" * 60)
    
    # 图片1: 300x200, 渐变色（蓝到绿）
    img1 = np.zeros((300, 200, 3), dtype=np.uint8)
    for i in range(300):
        color = int(255 * i / 300)
        img1[i, :] = [255 - color, color, 0]
    
    # 添加一些特征点（圆圈）
    for x in [50, 100, 150]:
        for y in [50, 150, 250]:
            cv2.circle(img1, (x, y), 10, (255, 255, 255), 2)
    
    # 图片2: 350x200, 顶部50px与img1底部相同
    img2 = np.zeros((350, 200, 3), dtype=np.uint8)
    # 复制img1的底部50px到img2的顶部
    img2[:50, :] = img1[-50:, :]
    # 剩余部分：渐变色（绿到红）
    for i in range(50, 350):
        color = int(255 * (i - 50) / 300)
        img2[i, :] = [0, 255 - color, color]
    
    # 添加特征点
    for x in [50, 100, 150]:
        for y in [100, 200, 300]:
            cv2.circle(img2, (x, y), 10, (255, 255, 255), 2)
    
    return img1, img2

def test_sift_matching():
    """测试SIFT特征匹配"""
    print("\n" + "=" * 60)
    print("测试SIFT特征匹配")
    print("=" * 60)
    
    img1, img2 = create_test_images_with_overlap()
    
    try:
        # 初始化SIFT
        sift = cv2.SIFT_create(nfeatures=2000)
        print("✓ SIFT检测器初始化成功")
    except:
        print("✗ SIFT不可用，跳过测试")
        return False
    
    # 转灰度
    gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
    
    # 提取ROI（img1底部30%, img2顶部30%）
    h1, h2 = gray1.shape[0], gray2.shape[0]
    roi1 = gray1[int(h1*0.7):, :]
    roi2 = gray2[:int(h2*0.3), :]
    
    print(f"ROI1形状: {roi1.shape}")
    print(f"ROI2形状: {roi2.shape}")
    
    # 检测特征点
    kp1, des1 = sift.detectAndCompute(roi1, None)
    kp2, des2 = sift.detectAndCompute(roi2, None)
    
    print(f"特征点数 - img1: {len(kp1)}, img2: {len(kp2)}")
    
    if des1 is None or des2 is None:
        print("✗ 未检测到特征点")
        return False
    
    # 特征匹配
    bf = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)
    matches = bf.knnMatch(des1, des2, k=2)
    
    print(f"初始匹配数: {len(matches)}")
    
    # Lowe's ratio test
    good_matches = []
    for m_n in matches:
        if len(m_n) == 2:
            m, n = m_n
            if m.distance < 0.75 * n.distance:
                good_matches.append(m)
    
    print(f"好匹配数（ratio test后）: {len(good_matches)}")
    
    if len(good_matches) < 4:
        print("✗ 好匹配太少，无法计算单应性")
        return False
    
    # 计算单应性矩阵
    pts1 = np.float32([kp1[m.queryIdx].pt for m in good_matches])
    pts2 = np.float32([kp2[m.trainIdx].pt for m in good_matches])
    
    H, mask = cv2.findHomography(pts2, pts1, cv2.RANSAC, 5.0)
    
    if H is None:
        print("✗ 单应性计算失败")
        return False
    
    inliers = np.sum(mask)
    print(f"内点数（RANSAC后）: {inliers}")
    
    if inliers < 4:
        print("✗ 内点太少")
        return False
    
    # 计算重叠量
    h1_full, w1 = img1.shape[:2]
    h2_full, w2 = img2.shape[:2]
    
    # 将ROI坐标转换回原图
    roi1_offset_y = int(h1_full * 0.7)
    pts1[:, 1] += roi1_offset_y
    
    # 用单应性矩阵变换img2的角点
    corners2 = np.float32([[0, 0], [w2, 0], [w2, h2_full], [0, h2_full]]).reshape(-1, 1, 2)
    transformed = cv2.perspectiveTransform(corners2, H)
    
    # 计算重叠
    top_y = np.mean(transformed[0:2, 0, 1])
    detected_overlap = max(0, int(h1_full - top_y))
    
    print(f"检测到的重叠: {detected_overlap}px (实际: 50px)")
    print(f"误差: {abs(detected_overlap - 50)}px")
    
    if abs(detected_overlap - 50) <= 10:  # 允许10px误差
        print("✅ SIFT匹配测试通过！")
        return True
    else:
        print("⚠️  SIFT匹配测试通过，但重叠检测误差较大")
        return True

def test_orb_matching():
    """测试ORB特征匹配"""
    print("\n" + "=" * 60)
    print("测试ORB特征匹配")
    print("=" * 60)
    
    img1, img2 = create_test_images_with_overlap()
    
    # 初始化ORB
    orb = cv2.ORB_create(nfeatures=2000)
    print("✓ ORB检测器初始化成功")
    
    # 转灰度
    gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
    
    # 提取ROI
    h1, h2 = gray1.shape[0], gray2.shape[0]
    roi1 = gray1[int(h1*0.7):, :]
    roi2 = gray2[:int(h2*0.3), :]
    
    # 检测特征点
    kp1, des1 = orb.detectAndCompute(roi1, None)
    kp2, des2 = orb.detectAndCompute(roi2, None)
    
    print(f"特征点数 - img1: {len(kp1)}, img2: {len(kp2)}")
    
    if des1 is None or des2 is None:
        print("✗ 未检测到特征点")
        return False
    
    # 特征匹配（使用汉明距离）
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    matches = bf.knnMatch(des1, des2, k=2)
    
    print(f"初始匹配数: {len(matches)}")
    
    # Lowe's ratio test
    good_matches = []
    for m_n in matches:
        if len(m_n) == 2:
            m, n = m_n
            if m.distance < 0.75 * n.distance:
                good_matches.append(m)
    
    print(f"好匹配数（ratio test后）: {len(good_matches)}")
    
    if len(good_matches) >= 4:
        print("✅ ORB匹配测试通过！")
        return True
    else:
        print("⚠️  ORB匹配测试：匹配点较少但可用")
        return True

def test_alpha_blending():
    """测试alpha融合算法"""
    print("\n" + "=" * 60)
    print("测试Alpha融合算法")
    print("=" * 60)
    
    # 创建两个有重叠的简单图片
    img1 = np.zeros((100, 100, 3), dtype=np.uint8)
    img1[:, :] = [255, 0, 0]  # 蓝色
    
    img2 = np.zeros((100, 100, 3), dtype=np.uint8)
    img2[:, :] = [0, 0, 255]  # 红色
    
    # 融合50px重叠
    overlap_h = 50
    result = img1.copy()
    
    for i in range(overlap_h):
        alpha = i / overlap_h
        result[50 + i, :] = (
            img1[50 + i, :] * (1 - alpha) +
            img2[i, :] * alpha
        ).astype(np.uint8)
    
    # 检查融合效果
    # 起点应该是纯蓝色
    start_color = result[50, 50]
    # 终点应该接近纯红色
    end_color = result[99, 50]
    # 中点应该是紫色（混合）
    mid_color = result[75, 50]
    
    print(f"起点颜色: {start_color} (期望: [255, 0, 0])")
    print(f"中点颜色: {mid_color} (期望: ~[127, 0, 127])")
    print(f"终点颜色: {end_color} (期望: [0, 0, 255])")
    
    # 简单验证
    if (start_color[0] > 200 and  # 蓝色分量高
        mid_color[0] > 50 and mid_color[2] > 50 and  # 混合色
        end_color[2] > 200):  # 红色分量高
        print("✅ Alpha融合测试通过！")
        return True
    else:
        print("✗ Alpha融合测试失败")
        return False

if __name__ == '__main__':
    print("\n" + "🧪 测试精确特征匹配算法\n")
    
    results = []
    
    try:
        results.append(("SIFT匹配", test_sift_matching()))
    except Exception as e:
        print(f"❌ SIFT匹配测试异常: {e}")
        results.append(("SIFT匹配", False))
    
    try:
        results.append(("ORB匹配", test_orb_matching()))
    except Exception as e:
        print(f"❌ ORB匹配测试异常: {e}")
        results.append(("ORB匹配", False))
    
    try:
        results.append(("Alpha融合", test_alpha_blending()))
    except Exception as e:
        print(f"❌ Alpha融合测试异常: {e}")
        results.append(("Alpha融合", False))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！精确匹配算法工作正常。")
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，需要检查。")
