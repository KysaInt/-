项目说明
=========

这个小项目包含三个可独立运行的脚本：

- `main.py`：基于 PySide6 的 GUI，包含两页（爬虫与 OCR），可以从界面调用两个模块。
- `crawler_module.py`：简单的爬虫模块，可通过命令行独立运行，下载指定 URL 并保存为 HTML 文件。
- `ocr_module.py`：基于 pytesseract 的 OCR 模块，可通过命令行独立运行，读取图片并输出识别文本。

依赖
------

在 Windows 上建议先安装 Tesseract OCR 可执行文件（https://github.com/UB-Mannheim/tesseract/wiki），然后将其路径加入系统 PATH。随后在虚拟环境中安装 Python 依赖：

```
pip install -r mini_app/requirements.txt
```

运行
------

1. 运行 GUI：

```
python mini_app/main.py
```

2. 单独运行爬虫模块：

```
python mini_app/crawler_module.py https://example.com
```

3. 单独运行 OCR 模块：

```
python mini_app/ocr_module.py path/to/image.png
```

注意
-----

- OCR 模块依赖本机安装的 Tesseract 可执行文件（pytesseract 只是 Python 包的封装）。
- GUI 程序已尽量使用后台线程来避免阻塞，但在不同系统或不同图片上运行时，性能和识别准确率会有差异。
