"""PySide6 GUI 应用：两个页面（爬虫与 OCR），可调用模块函数并显示结果。

运行: python main.py
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit,
    QLineEdit, QLabel, QFileDialog, QStackedWidget, QMessageBox, QProgressBar
)
from PySide6.QtCore import Qt, QThread, Signal, Slot

from crawler_module import fetch_url
from ocr_module import ocr_image


class WorkerThread(QThread):
    finished_sig = Signal(object, object)  # (result, error)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            res = self.func(*self.args, **self.kwargs)
            self.finished_sig.emit(res, None)
        except Exception as e:
            tb = traceback.format_exc()
            self.finished_sig.emit(None, (e, tb))


class CrawlerPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        h = QHBoxLayout()
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText('https://example.com')
        self.fetch_btn = QPushButton('抓取')
        h.addWidget(QLabel('URL:'))
        h.addWidget(self.url_edit)
        h.addWidget(self.fetch_btn)
        layout.addLayout(h)
        self.save_btn = QPushButton('选择保存路径 (可选)')
        layout.addWidget(self.save_btn)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        self.result = QTextEdit()
        layout.addWidget(self.result)
        self.setLayout(layout)

        self.save_path: Path | None = None
        self.save_btn.clicked.connect(self.choose_save)
        self.fetch_btn.clicked.connect(self.on_fetch)

    def choose_save(self):
        p, _ = QFileDialog.getSaveFileName(self, '选择保存路径', filter='HTML Files (*.html);;All Files (*)')
        if p:
            self.save_path = Path(p)
            self.save_btn.setText(f'保存为: {self.save_path.name}')

    def on_fetch(self):
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, '错误', '请输入 URL')
            return
        self.result.clear()
        self.progress.setVisible(True)
        self.thread = WorkerThread(fetch_url, url, str(self.save_path) if self.save_path else None)
        self.thread.finished_sig.connect(self.on_finished)
        self.thread.start()

    @Slot(object, object)
    def on_finished(self, res, err):
        self.progress.setVisible(False)
        if err:
            e, tb = err
            self.result.setPlainText(f'错误: {e}\n\n{tb}')
        else:
            self.result.setPlainText(res[:10000])


class OCRPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        h = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.browse_btn = QPushButton('浏览')
        self.run_btn = QPushButton('识别')
        h.addWidget(self.path_edit)
        h.addWidget(self.browse_btn)
        h.addWidget(self.run_btn)
        layout.addLayout(h)
        self.lang_edit = QLineEdit()
        self.lang_edit.setPlaceholderText('可选语言，例如 chi_sim 或 eng')
        layout.addWidget(self.lang_edit)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        self.result = QTextEdit()
        layout.addWidget(self.result)
        self.setLayout(layout)

        self.browse_btn.clicked.connect(self.on_browse)
        self.run_btn.clicked.connect(self.on_run)

    def on_browse(self):
        p, _ = QFileDialog.getOpenFileName(self, '选择图片', filter='Images (*.png *.jpg *.jpeg *.bmp);;All Files (*)')
        if p:
            self.path_edit.setText(p)

    def on_run(self):
        path = self.path_edit.text().strip()
        if not path:
            QMessageBox.warning(self, '错误', '请选择图片路径')
            return
        lang = self.lang_edit.text().strip() or None
        self.result.clear()
        self.progress.setVisible(True)
        self.thread = WorkerThread(ocr_image, path, lang)
        self.thread.finished_sig.connect(self.on_finished)
        self.thread.start()

    @Slot(object, object)
    def on_finished(self, res, err):
        self.progress.setVisible(False)
        if err:
            e, tb = err
            self.result.setPlainText(f'错误: {e}\n\n{tb}')
        else:
            self.result.setPlainText(res)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Mini App - 爬虫 & OCR')
        self.resize(900, 600)
        layout = QVBoxLayout()
        btn_layout = QHBoxLayout()
        self.crawler_btn = QPushButton('爬虫')
        self.ocr_btn = QPushButton('OCR')
        btn_layout.addWidget(self.crawler_btn)
        btn_layout.addWidget(self.ocr_btn)
        layout.addLayout(btn_layout)
        self.stack = QStackedWidget()
        self.crawler_page = CrawlerPage()
        self.ocr_page = OCRPage()
        self.stack.addWidget(self.crawler_page)
        self.stack.addWidget(self.ocr_page)
        layout.addWidget(self.stack)
        self.setLayout(layout)

        self.crawler_btn.clicked.connect(lambda: self.stack.setCurrentWidget(self.crawler_page))
        self.ocr_btn.clicked.connect(lambda: self.stack.setCurrentWidget(self.ocr_page))


def main():
    app = QApplication([])
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
