"""OCR 模块

依赖：pytesseract, Pillow。需要系统安装 tesseract 可执行文件并在 PATH 中。

提供 ocr_image(image_path) 函数，返回识别文本。
支持命令行独立运行。
"""
from __future__ import annotations

import sys
from typing import Optional
from PIL import Image
import pytesseract


def ocr_image(image_path: str, lang: Optional[str] = None) -> str:
    """对图片执行 OCR，返回识别到的文本。

    lang: 可选 tesseract 语言代码，例如 'chi_sim' 或 'eng'
    """
    img = Image.open(image_path)
    kwargs = {}
    if lang:
        kwargs['lang'] = lang
    text = pytesseract.image_to_string(img, **kwargs)
    return text


def main(argv=None):
    argv = argv or sys.argv[1:]
    if not argv:
        print("用法: python ocr_module.py <image_path> [lang]")
        return 1
    path = argv[0]
    lang = argv[1] if len(argv) > 1 else None
    try:
        text = ocr_image(path, lang)
        print("识别结果:\n")
        print(text)
        return 0
    except Exception as e:
        print(f"OCR 失败: {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
