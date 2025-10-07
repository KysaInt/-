# AYE OCR Tool - 升级说明

## 🎉 重大更新：集成 PaddleOCR

### ✨ 新功能

#### 1. **双OCR引擎支持**
- **PaddleOCR** (推荐)：百度开源的OCR引擎，中文识别准确率极高
- **Tesseract**：通用OCR引擎，支持多语言

#### 2. **智能引擎切换**
- 在设置中可以选择OCR引擎
- 如果PaddleOCR失败，会自动降级使用Tesseract
- 默认使用PaddleOCR获得最佳中文识别效果

#### 3. **图像预处理增强**
- 图像放大2倍提高识别精度
- 降噪处理
- 自适应二值化
- 形态学优化
- 锐化处理

### 📦 依赖安装

程序会自动检测并安装以下依赖：
- PySide6
- Pillow
- pytesseract
- keyboard
- pyperclip
- numpy
- opencv-python
- **paddleocr** (新增)

首次运行时，PaddleOCR会自动下载模型文件（约几十MB），请耐心等待。

### 🎯 使用方法

1. **启动程序**
   ```
   python aye_ocr.pyw
   ```

2. **设置OCR引擎**
   - 点击"设置"按钮
   - 在"OCR引擎"下拉框中选择：
     - "PaddleOCR (推荐-中文)" - 中文识别最佳
     - "Tesseract" - 通用引擎

3. **开始识别**
   - 按快捷键 `Ctrl+Shift+A`（可自定义）
   - 框选要识别的区域
   - 释放鼠标自动识别并复制到剪贴板

### 🔧 配置文件

配置保存在 `ocr_settings.json`：
```json
{
    "hotkey": "ctrl+shift+a",
    "tesseract_path": "",
    "ocr_lang": "chi_sim+eng",
    "enhance_image": true,
    "ocr_engine": "paddleocr"
}
```

### 📊 性能对比

| 特性 | PaddleOCR | Tesseract |
|------|-----------|-----------|
| 中文识别 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| 英文识别 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 符号识别 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| 速度 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 安装复杂度 | 简单(pip) | 需手动安装 |

### 💡 使用建议

1. **中文文本**：推荐使用 PaddleOCR
2. **英文文本**：两者都可以，PaddleOCR稍好
3. **手写文字**：PaddleOCR 效果更好
4. **表格/复杂布局**：PaddleOCR 布局识别更准确

### 🐛 故障排除

**Q: PaddleOCR安装失败？**
A: 尝试手动安装：`pip install paddleocr`

**Q: 首次运行很慢？**
A: 正常现象，PaddleOCR首次运行会下载模型文件

**Q: 识别结果不理想？**
A: 
- 确保截图区域文字清晰
- 尝试调整截图大小
- 尝试切换到另一个OCR引擎

**Q: 想禁用图像预处理？**
A: 在配置文件中设置 `"enhance_image": false`

### 📝 更新日志

**v2.0** (2025-10-06)
- ✅ 集成PaddleOCR中文识别引擎
- ✅ 添加OCR引擎选择功能
- ✅ 修复截图尺寸数字被识别的问题
- ✅ 优化图像预处理流程
- ✅ 提升中文识别准确率

**v1.0**
- 基础Tesseract OCR功能
- 全局快捷键截图
- 自动复制到剪贴板
