# -*- coding: utf-8 -*-
import os
import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt

def batch_replace(root_dir, find_str, replace_str):
    """批量替换文件和文件夹名称"""
    replaced_count = 0
    # 使用 os.walk 从底层向上遍历，以先替换文件/子文件夹，再替换父文件夹
    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=False):
        # 替换文件
        for filename in filenames:
            if find_str in filename:
                old_path = os.path.join(dirpath, filename)
                new_filename = filename.replace(find_str, replace_str)
                new_path = os.path.join(dirpath, new_filename)
                try:
                    os.rename(old_path, new_path)
                    replaced_count += 1
                except OSError:
                    # 忽略错误，例如当目标文件已存在时
                    pass

        # 替换文件夹
        for dirname in dirnames:
            if find_str in dirname:
                old_dir = os.path.join(dirpath, dirname)
                new_dir_name = dirname.replace(find_str, replace_str)
                new_dir = os.path.join(dirpath, new_dir_name)
                try:
                    os.rename(old_dir, new_dir)
                    replaced_count += 1
                except OSError:
                    # 忽略错误
                    pass
    return replaced_count

class ReplaceWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # 表单布局
        grid_layout = QGridLayout()
        grid_layout.setSpacing(8)

        # 路径行
        self.path_label = QLabel("执行路径:")
        self.path_line_edit = QLineEdit()
        self.browse_button = QPushButton("浏览...")
        grid_layout.addWidget(self.path_label, 0, 0)
        
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.path_line_edit)
        path_layout.addWidget(self.browse_button)
        grid_layout.addLayout(path_layout, 0, 1)

        # 查找内容行
        self.find_label = QLabel("查找内容:")
        self.find_line_edit = QLineEdit()
        grid_layout.addWidget(self.find_label, 1, 0)
        grid_layout.addWidget(self.find_line_edit, 1, 1)

        # 替换为行
        self.replace_label = QLabel("替换为:")
        self.replace_line_edit = QLineEdit()
        grid_layout.addWidget(self.replace_label, 2, 0)
        grid_layout.addWidget(self.replace_line_edit, 2, 1)

        main_layout.addLayout(grid_layout)

        # 执行按钮
        self.replace_button = QPushButton("开始替换")
        self.replace_button.setMinimumHeight(35)
        main_layout.addWidget(self.replace_button)

        main_layout.addStretch() # 添加伸缩，使控件集中在顶部

        # 设置初始路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        default_path = os.path.join(os.path.dirname(current_dir), '0')
        self.path_line_edit.setText(default_path)

    def connect_signals(self):
        self.browse_button.clicked.connect(self.browse_directory)
        self.replace_button.clicked.connect(self.execute_replace)

    def browse_directory(self):
        current_path = self.path_line_edit.text()
        directory = QFileDialog.getExistingDirectory(
            self, "选择要替换的根文件夹", current_path
        )
        if directory:
            self.path_line_edit.setText(directory)

    def execute_replace(self):
        root_dir = self.path_line_edit.text()
        find_str = self.find_line_edit.text()
        replace_str = self.replace_line_edit.text()

        if not find_str:
            QMessageBox.warning(self, "警告", "“查找内容”不能为空！")
            return

        if not os.path.isdir(root_dir):
            QMessageBox.critical(self, "错误", "指定的路径不是一个有效的文件夹！")
            return

        try:
            replaced_count = batch_replace(root_dir, find_str, replace_str)
            QMessageBox.information(
                self, "完成", f"批量替换完成！\n共处理了 {replaced_count} 个文件和文件夹。"
            )
        except Exception as e:
            QMessageBox.critical(self, "错误", f"替换过程中发生错误：\n{e}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    widget = ReplaceWidget()
    widget.setWindowTitle("批量替换工具")
    widget.setGeometry(300, 300, 450, 200)
    widget.show()
    sys.exit(app.exec())
