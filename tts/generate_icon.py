#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成 TTS 应用图标
创建一个彩色的、带有 "TTS" 文字的应用图标
"""

import os
from PIL import Image, ImageDraw, ImageFont

def create_tts_icon():
    """创建 TTS 应用图标"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 创建 PNG 图标
    icon_sizes = [
        (16, 16),
        (32, 32),
        (64, 64),
        (128, 128),
        (256, 256),
    ]
    
    # 使用渐变色方案 - 蓝紫色 (专业感)
    colors = {
        "bg": (41, 128, 185),      # 蓝色背景
        "accent": (155, 89, 182),  # 紫色强调
        "text": (255, 255, 255),   # 白色文字
        "shadow": (25, 75, 110),   # 深蓝阴影
    }
    
    print("生成 TTS 应用图标...")
    
    # 生成最大尺寸的图标用于 PNG
    size = 256
    img = Image.new('RGB', (size, size), colors["bg"])
    draw = ImageDraw.Draw(img)
    
    # 添加渐变背景 (从深蓝到浅蓝)
    for y in range(size):
        ratio = y / size
        r = int(colors["shadow"][0] + (colors["bg"][0] - colors["shadow"][0]) * ratio)
        g = int(colors["shadow"][1] + (colors["bg"][1] - colors["shadow"][1]) * ratio)
        b = int(colors["shadow"][2] + (colors["bg"][2] - colors["shadow"][2]) * ratio)
        draw.line([(0, y), (size, y)], fill=(r, g, b))
    
    # 添加紫色强调边框
    border_width = 8
    draw.rectangle(
        [(border_width, border_width), (size - border_width, size - border_width)],
        outline=colors["accent"],
        width=3
    )
    
    # 添加音频波形图案 (象征"语音")
    wave_color = colors["accent"]
    wave_y = size // 2
    wave_height = size // 6
    
    # 绘制三条波形线
    for i in range(3):
        x_offset = size // 4 + i * (size // 6)
        # 左半边
        draw.arc(
            [(x_offset - wave_height // 2, wave_y - wave_height // 2),
             (x_offset + wave_height // 2, wave_y + wave_height // 2)],
            0, 180,
            fill=wave_color,
            width=3
        )
    
    # 添加 "TTS" 文字 (使用系统字体)
    try:
        # 尝试找系统字体
        font_size = 80
        font = ImageFont.truetype("C:\\Windows\\Fonts\\Arial.ttf", font_size)
    except:
        # 如果找不到，使用默认字体
        font = ImageFont.load_default()
    
    text = "TTS"
    # 计算文字位置（居中）
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (size - text_width) // 2
    y = size // 2 - text_height // 2 + 20
    
    # 绘制文字阴影
    draw.text((x + 2, y + 2), text, font=font, fill=colors["shadow"])
    # 绘制文字
    draw.text((x, y), text, font=font, fill=colors["text"])
    
    # 保存 PNG 格式
    png_path = os.path.join(script_dir, "icon.png")
    img.save(png_path, "PNG")
    print(f"✅ 已生成 PNG 图标: {png_path}")
    
    # 转换为 ICO 格式 (用于任务栏)
    ico_path = os.path.join(script_dir, "icon.ico")
    
    # 创建多尺寸 ICO
    ico_images = []
    for size in icon_sizes:
        img_resized = img.resize(size, Image.Resampling.LANCZOS)
        ico_images.append(img_resized)
    
    # 保存 ICO (使用最大的作为主图标)
    ico_images[0].save(ico_path, "ICO", sizes=icon_sizes)
    print(f"✅ 已生成 ICO 图标: {ico_path}")
    
    # 创建任务栏专用 ICO (icon_tb.ico)
    ico_tb_path = os.path.join(script_dir, "icon_tb.ico")
    ico_images[0].save(ico_tb_path, "ICO", sizes=icon_sizes)
    print(f"✅ 已生成任务栏 ICO 图标: {ico_tb_path}")
    
    print("\n图标生成完成！")
    return True

if __name__ == "__main__":
    try:
        create_tts_icon()
    except ImportError:
        print("❌ 需要安装 Pillow 库")
        print("运行: pip install Pillow")
    except Exception as e:
        print(f"❌ 生成图标失败: {e}")
