#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重复文件删除工具 - 使用 PySide6 图形界面
支持通过多种方法识别内容相同但文件名不同的文件
"""

import sys
import os
import hashlib
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Set
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QCheckBox, QComboBox, QProgressBar,
    QTreeWidget, QTreeWidgetItem, QFileDialog, QMessageBox, QHeaderView,
    QGroupBox, QTextEdit
)
from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtGui import QIcon


class ScanWorker(QObject):
    """扫描工作线程"""
    progress = Signal(int, int, str)  # current, total, message
    finished = Signal(dict)  # duplicates dict
    error = Signal(str)
    
    def __init__(self, directory: str, include_subdirs: bool, method: str):
        super().__init__()
        self.directory = directory
        self.include_subdirs = include_subdirs
        self.method = method
        self.is_cancelled = False
        
    def cancel(self):
        """取消扫描"""
        self.is_cancelled = True
        
    def _get_file_hash(self, filepath: Path, method: str = "full") -> str:
        """计算文件哈希值"""
        hash_obj = hashlib.sha256()
        
        try:
            if method == "fast":
                # 快速模式：只读取文件头部（前1MB）
                with open(filepath, 'rb') as f:
                    chunk = f.read(1024 * 1024)
                    hash_obj.update(chunk)
            elif method == "accurate" or method == "strict":
                # 准确模式和严格模式：读取整个文件
                with open(filepath, 'rb') as f:
                    while True:
                        chunk = f.read(8192)
                        if not chunk:
                            break
                        hash_obj.update(chunk)
            
            return hash_obj.hexdigest()
        except Exception as e:
            return None
            
    def _get_files(self) -> List[Path]:
        """获取所有文件列表"""
        files = []
        path = Path(self.directory)
        
        if self.include_subdirs:
            for item in path.rglob('*'):
                if item.is_file():
                    files.append(item)
        else:
            for item in path.iterdir():
                if item.is_file():
                    files.append(item)
        
        return files
        
    def run(self):
        """执行扫描"""
        try:
            # 获取所有文件
            files = self._get_files()
            total_files = len(files)
            
            if total_files == 0:
                self.finished.emit({})
                return
            
            self.progress.emit(0, total_files, "正在按大小分组...")
            
            # 第一步：按文件大小分组
            size_groups = defaultdict(list)
            for i, file_path in enumerate(files):
                if self.is_cancelled:
                    return
                    
                try:
                    size = file_path.stat().st_size
                    size_groups[size].append(file_path)
                    self.progress.emit(i + 1, total_files, f"分组中: {file_path.name}")
                except Exception:
                    continue
            
            # 过滤出大小相同的文件组（至少2个文件）
            potential_duplicates = {size: files for size, files in size_groups.items() if len(files) > 1}
            
            if not potential_duplicates:
                self.finished.emit({})
                return
            
            # 第二步：对每组按哈希值进一步分组
            self.progress.emit(0, total_files, "正在计算文件哈希...")
            
            hash_groups = defaultdict(list)
            processed = 0
            
            for size, file_list in potential_duplicates.items():
                for file_path in file_list:
                    if self.is_cancelled:
                        return
                    
                    file_hash = self._get_file_hash(file_path, self.method)
                    if file_hash:
                        # 使用大小+哈希作为键
                        key = f"{size}_{file_hash}"
                        hash_groups[key].append(file_path)
                    
                    processed += 1
                    self.progress.emit(processed, total_files, f"计算哈希: {file_path.name}")
            
            # 第三步：严格模式下进行字节对比
            if self.method == "strict":
                self.progress.emit(0, total_files, "正在进行字节对比...")
                verified_groups = {}
                
                for key, file_list in hash_groups.items():
                    if len(file_list) < 2:
                        continue
                    
                    if self.is_cancelled:
                        return
                    
                    # 逐字节比较确认完全相同
                    verified = self._verify_identical(file_list)
                    if len(verified) > 1:
                        verified_groups[key] = verified
                
                duplicates = verified_groups
            else:
                # 过滤出真正的重复文件（至少2个）
                duplicates = {k: v for k, v in hash_groups.items() if len(v) > 1}
            
            self.finished.emit(duplicates)
            
        except Exception as e:
            self.error.emit(f"扫描出错: {str(e)}")
            
    def _verify_identical(self, files: List[Path]) -> List[Path]:
        """逐字节验证文件是否完全相同"""
        if len(files) < 2:
            return files
        
        identical = [files[0]]
        reference = files[0]
        
        for file in files[1:]:
            if self._compare_files_byte_by_byte(reference, file):
                identical.append(file)
        
        return identical
        
    def _compare_files_byte_by_byte(self, file1: Path, file2: Path) -> bool:
        """逐字节比较两个文件"""
        try:
            with open(file1, 'rb') as f1, open(file2, 'rb') as f2:
                while True:
                    chunk1 = f1.read(8192)
                    chunk2 = f2.read(8192)
                    
                    if chunk1 != chunk2:
                        return False
                    
                    if not chunk1:  # 都到达文件末尾
                        return True
        except Exception:
            return False


class DuplicateFileRemover(QMainWindow):
    """重复文件删除工具主窗口"""
    
    def __init__(self):
        super().__init__()
        self.duplicates = {}
        self.scan_thread = None
        self.scan_worker = None
        self.init_ui()
        
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("重复文件删除工具")
        self.setMinimumSize(900, 600)
        
        # 中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # === 目录选择区域 ===
        dir_group = QGroupBox("扫描设置")
        dir_layout = QVBoxLayout()
        
        # 目录选择
        dir_select_layout = QHBoxLayout()
        dir_select_layout.addWidget(QLabel("扫描目录:"))
        self.dir_input = QLineEdit()
        self.dir_input.setPlaceholderText("选择要扫描的目录...")
        dir_select_layout.addWidget(self.dir_input)
        self.browse_btn = QPushButton("浏览")
        self.browse_btn.clicked.connect(self.select_directory)
        dir_select_layout.addWidget(self.browse_btn)
        dir_layout.addLayout(dir_select_layout)
        
        # 选项
        options_layout = QHBoxLayout()
        self.subdir_checkbox = QCheckBox("包含子目录")
        self.subdir_checkbox.setChecked(True)
        options_layout.addWidget(self.subdir_checkbox)
        
        options_layout.addWidget(QLabel("识别方法:"))
        self.method_combo = QComboBox()
        self.method_combo.addItem("快速 (仅头部哈希)", "fast")
        self.method_combo.addItem("准确 (完整哈希)", "accurate")
        self.method_combo.addItem("严格 (哈希+字节对比)", "strict")
        self.method_combo.setCurrentIndex(1)
        options_layout.addWidget(self.method_combo)
        options_layout.addStretch()
        dir_layout.addLayout(options_layout)
        
        dir_group.setLayout(dir_layout)
        main_layout.addWidget(dir_group)
        
        # === 控制按钮 ===
        control_layout = QHBoxLayout()
        self.scan_btn = QPushButton("开始扫描")
        self.scan_btn.clicked.connect(self.start_scan)
        control_layout.addWidget(self.scan_btn)
        
        self.stop_btn = QPushButton("停止扫描")
        self.stop_btn.clicked.connect(self.stop_scan)
        self.stop_btn.setEnabled(False)
        control_layout.addWidget(self.stop_btn)
        
        control_layout.addStretch()
        main_layout.addLayout(control_layout)
        
        # === 进度条 ===
        progress_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_bar)
        self.progress_label = QLabel("就绪")
        progress_layout.addWidget(self.progress_label)
        main_layout.addLayout(progress_layout)
        
        # === 结果树形表格 ===
        result_group = QGroupBox("重复文件")
        result_layout = QVBoxLayout()
        
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["文件路径", "大小", "修改时间", "完整路径"])
        self.tree_widget.setColumnWidth(0, 350)
        self.tree_widget.setColumnWidth(1, 100)
        self.tree_widget.setColumnWidth(2, 150)
        self.tree_widget.header().setStretchLastSection(True)
        self.tree_widget.setSelectionMode(QTreeWidget.ExtendedSelection)
        result_layout.addWidget(self.tree_widget)
        
        result_group.setLayout(result_layout)
        main_layout.addWidget(result_group)
        
        # === 操作按钮 ===
        action_layout = QHBoxLayout()
        
        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.clicked.connect(self.select_all)
        action_layout.addWidget(self.select_all_btn)
        
        self.deselect_all_btn = QPushButton("取消全选")
        self.deselect_all_btn.clicked.connect(self.deselect_all)
        action_layout.addWidget(self.deselect_all_btn)
        
        self.invert_selection_btn = QPushButton("反选")
        self.invert_selection_btn.clicked.connect(self.invert_selection)
        action_layout.addWidget(self.invert_selection_btn)
        
        self.keep_one_btn = QPushButton("每组保留一个(其余选中)")
        self.keep_one_btn.clicked.connect(self.keep_one_per_group)
        action_layout.addWidget(self.keep_one_btn)
        
        action_layout.addStretch()
        
        self.delete_btn = QPushButton("删除选中文件")
        self.delete_btn.clicked.connect(self.delete_selected)
        self.delete_btn.setStyleSheet("background-color: #ff4444; color: white; font-weight: bold;")
        action_layout.addWidget(self.delete_btn)
        
        main_layout.addLayout(action_layout)
        
        # === 状态栏 ===
        self.statusBar().showMessage("就绪")
        
    def select_directory(self):
        """选择目录"""
        directory = QFileDialog.getExistingDirectory(self, "选择要扫描的目录")
        if directory:
            self.dir_input.setText(directory)
            
    def start_scan(self):
        """开始扫描"""
        directory = self.dir_input.text().strip()
        
        if not directory:
            QMessageBox.warning(self, "警告", "请先选择要扫描的目录！")
            return
        
        if not os.path.isdir(directory):
            QMessageBox.warning(self, "警告", "选择的目录不存在！")
            return
        
        # 清空之前的结果
        self.tree_widget.clear()
        self.duplicates = {}
        
        # 禁用控制
        self.scan_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.browse_btn.setEnabled(False)
        self.method_combo.setEnabled(False)
        self.subdir_checkbox.setEnabled(False)
        
        # 创建工作线程
        self.scan_thread = QThread()
        self.scan_worker = ScanWorker(
            directory,
            self.subdir_checkbox.isChecked(),
            self.method_combo.currentData()
        )
        self.scan_worker.moveToThread(self.scan_thread)
        
        # 连接信号
        self.scan_thread.started.connect(self.scan_worker.run)
        self.scan_worker.progress.connect(self.update_progress)
        self.scan_worker.finished.connect(self.scan_finished)
        self.scan_worker.error.connect(self.scan_error)
        self.scan_worker.finished.connect(self.scan_thread.quit)
        self.scan_worker.error.connect(self.scan_thread.quit)
        self.scan_thread.finished.connect(self.scan_cleanup)
        
        # 启动线程
        self.scan_thread.start()
        self.statusBar().showMessage("正在扫描...")
        
    def stop_scan(self):
        """停止扫描"""
        if self.scan_worker:
            self.scan_worker.cancel()
            self.progress_label.setText("正在停止...")
            
    def update_progress(self, current: int, total: int, message: str):
        """更新进度"""
        if total > 0:
            percentage = int((current / total) * 100)
            self.progress_bar.setValue(percentage)
        self.progress_label.setText(message)
        
    def scan_finished(self, duplicates: Dict):
        """扫描完成"""
        self.duplicates = duplicates
        self.display_duplicates()
        
        total_groups = len(duplicates)
        total_files = sum(len(files) for files in duplicates.values())
        
        self.statusBar().showMessage(f"扫描完成！找到 {total_groups} 组重复文件，共 {total_files} 个文件")
        self.progress_label.setText(f"完成 - {total_groups} 组重复")
        self.progress_bar.setValue(100)
        
    def scan_error(self, error_msg: str):
        """扫描出错"""
        QMessageBox.critical(self, "错误", error_msg)
        self.statusBar().showMessage("扫描出错")
        self.progress_label.setText("出错")
        
    def scan_cleanup(self):
        """清理扫描资源"""
        self.scan_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.browse_btn.setEnabled(True)
        self.method_combo.setEnabled(True)
        self.subdir_checkbox.setEnabled(True)
        
    def display_duplicates(self):
        """显示重复文件"""
        self.tree_widget.clear()
        
        if not self.duplicates:
            return
        
        for group_key, files in self.duplicates.items():
            # 创建组节点
            size = files[0].stat().st_size
            size_str = self.format_size(size)
            group_item = QTreeWidgetItem(self.tree_widget)
            group_item.setText(0, f"重复组 ({len(files)} 个文件)")
            group_item.setText(1, size_str)
            group_item.setFlags(group_item.flags() | Qt.ItemIsAutoTristate)
            
            # 添加文件节点
            for file_path in sorted(files):
                file_item = QTreeWidgetItem(group_item)
                file_item.setText(0, file_path.name)
                file_item.setText(1, size_str)
                
                try:
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    file_item.setText(2, mtime.strftime("%Y-%m-%d %H:%M:%S"))
                except Exception:
                    file_item.setText(2, "N/A")
                
                file_item.setText(3, str(file_path))
                file_item.setCheckState(0, Qt.Unchecked)
                file_item.setData(0, Qt.UserRole, str(file_path))
            
            group_item.setExpanded(True)
            
    def format_size(self, size: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"
        
    def select_all(self):
        """全选"""
        self._set_all_checked(Qt.Checked)
        
    def deselect_all(self):
        """取消全选"""
        self._set_all_checked(Qt.Unchecked)
        
    def invert_selection(self):
        """反选"""
        root = self.tree_widget.invisibleRootItem()
        for i in range(root.childCount()):
            group_item = root.child(i)
            for j in range(group_item.childCount()):
                file_item = group_item.child(j)
                current_state = file_item.checkState(0)
                new_state = Qt.Unchecked if current_state == Qt.Checked else Qt.Checked
                file_item.setCheckState(0, new_state)
                
    def keep_one_per_group(self):
        """每组保留一个，其余选中"""
        root = self.tree_widget.invisibleRootItem()
        for i in range(root.childCount()):
            group_item = root.child(i)
            for j in range(group_item.childCount()):
                file_item = group_item.child(j)
                # 第一个不选，其余选中
                if j == 0:
                    file_item.setCheckState(0, Qt.Unchecked)
                else:
                    file_item.setCheckState(0, Qt.Checked)
                    
    def _set_all_checked(self, state: Qt.CheckState):
        """设置所有项目的选中状态"""
        root = self.tree_widget.invisibleRootItem()
        for i in range(root.childCount()):
            group_item = root.child(i)
            for j in range(group_item.childCount()):
                file_item = group_item.child(j)
                file_item.setCheckState(0, state)
                
    def delete_selected(self):
        """删除选中的文件"""
        # 收集要删除的文件
        files_to_delete = []
        root = self.tree_widget.invisibleRootItem()
        
        for i in range(root.childCount()):
            group_item = root.child(i)
            for j in range(group_item.childCount()):
                file_item = group_item.child(j)
                if file_item.checkState(0) == Qt.Checked:
                    file_path = file_item.data(0, Qt.UserRole)
                    files_to_delete.append(file_path)
        
        if not files_to_delete:
            QMessageBox.information(self, "提示", "没有选中任何文件！")
            return
        
        # 确认删除
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除 {len(files_to_delete)} 个文件吗？\n\n文件将被移动到回收站。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # 尝试导入 send2trash
        try:
            from send2trash import send2trash
            use_trash = True
        except ImportError:
            reply = QMessageBox.question(
                self,
                "警告",
                "未安装 send2trash 模块，无法移动到回收站。\n\n是否永久删除文件？\n\n建议安装: pip install send2trash",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
            use_trash = False
        
        # 执行删除
        deleted_count = 0
        failed_files = []
        
        for file_path in files_to_delete:
            try:
                if use_trash:
                    send2trash(file_path)
                else:
                    os.remove(file_path)
                deleted_count += 1
            except Exception as e:
                failed_files.append(f"{file_path}: {str(e)}")
        
        # 显示结果
        if failed_files:
            error_msg = f"成功删除 {deleted_count} 个文件\n\n以下文件删除失败:\n" + "\n".join(failed_files[:10])
            if len(failed_files) > 10:
                error_msg += f"\n... 以及其他 {len(failed_files) - 10} 个文件"
            QMessageBox.warning(self, "删除结果", error_msg)
        else:
            QMessageBox.information(self, "成功", f"成功删除 {deleted_count} 个文件！")
        
        # 重新扫描或清空结果
        self.tree_widget.clear()
        self.duplicates = {}
        self.statusBar().showMessage(f"已删除 {deleted_count} 个文件")


def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # 使用 Fusion 样式
    
    window = DuplicateFileRemover()
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
