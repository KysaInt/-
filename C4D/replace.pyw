# -*- coding: utf-8 -*-
import os
import sys
import subprocess
import importlib.util

def check_and_install_packages():
    """检查并安装所需的包"""
    required_packages = {
        'PySide6': 'PySide6',
        'Pillow': 'Pillow'
    }
    
    missing_packages = []
    
    # 检查每个包是否已安装
    for import_name, package_name in required_packages.items():
        if importlib.util.find_spec(import_name) is None:
            missing_packages.append(package_name)
    
    if missing_packages:
        try:
            print("检测到缺少以下依赖包:")
            for package in missing_packages:
                print(f"  - {package}")
            
            print("\n正在自动安装缺少的包...")
            
            for package in missing_packages:
                try:
                    print(f"正在安装 {package}...")
                    subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                    print(f"✓ {package} 安装成功")
                except subprocess.CalledProcessError as e:
                    print(f"✗ {package} 安装失败: {e}")
                    print("请手动安装此包或检查网络连接")
                    return False
            
            print("\n所有依赖包安装完成！")
        except Exception as e:
            print(f"安装包时出错: {e}")
            return False
    
    return True

# 执行依赖检查
if not check_and_install_packages():
    print("依赖安装失败，程序退出")
    sys.exit(1)

# 导入所需模块
try:
    from PySide6.QtCore import (QCoreApplication, QMetaObject, QRect, QSize, Qt)
    from PySide6.QtGui import (QFont)
    from PySide6.QtWidgets import (QApplication, QGridLayout, QHBoxLayout, QLabel,
        QLineEdit, QMainWindow, QPushButton, QSizePolicy, QStatusBar, 
        QVBoxLayout, QWidget, QLayout, QFileDialog, QMessageBox)
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保所有依赖包都已正确安装")
    sys.exit(1)

# UI类定义 - 从UI文件生成的代码直接嵌入
class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.setEnabled(True)
        MainWindow.resize(300, 159)
        sizePolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(MainWindow.sizePolicy().hasHeightForWidth())
        MainWindow.setSizePolicy(sizePolicy)
        MainWindow.setMinimumSize(QSize(300, 140))
        MainWindow.setAutoFillBackground(False)
        MainWindow.setDocumentMode(False)
        
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        sizePolicy.setHeightForWidth(self.centralwidget.sizePolicy().hasHeightForWidth())
        self.centralwidget.setSizePolicy(sizePolicy)
        self.centralwidget.setBaseSize(QSize(0, 10))
        
        self.verticalLayout = QVBoxLayout(self.centralwidget)
        self.verticalLayout.setSpacing(2)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(2, 2, 2, 2)
        self.verticalLayout.setSizeConstraint(QLayout.SetMinimumSize)
        
        self.gridLayout = QGridLayout()
        self.gridLayout.setSpacing(5)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(2, 2, 2, 2)
        
        self.label = QLabel(self.centralwidget)
        self.label.setObjectName(u"label")
        self.label.setEnabled(True)
        sizePolicy1 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.label.sizePolicy().hasHeightForWidth())
        self.label.setSizePolicy(sizePolicy1)

        self.gridLayout.addWidget(self.label, 0, 0, 1, 1)

        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setSpacing(2)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(2, 2, 2, 2)
        
        self.pathLineEdit = QLineEdit(self.centralwidget)
        self.pathLineEdit.setObjectName(u"pathLineEdit")

        self.horizontalLayout.addWidget(self.pathLineEdit)

        self.browseButton = QPushButton(self.centralwidget)
        self.browseButton.setObjectName(u"browseButton")

        self.horizontalLayout.addWidget(self.browseButton)

        self.gridLayout.addLayout(self.horizontalLayout, 0, 1, 1, 1)

        self.label_2 = QLabel(self.centralwidget)
        self.label_2.setObjectName(u"label_2")

        self.gridLayout.addWidget(self.label_2, 1, 0, 1, 1)

        self.findLineEdit = QLineEdit(self.centralwidget)
        self.findLineEdit.setObjectName(u"findLineEdit")
        sizePolicy2 = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.findLineEdit.sizePolicy().hasHeightForWidth())
        self.findLineEdit.setSizePolicy(sizePolicy2)

        self.gridLayout.addWidget(self.findLineEdit, 1, 1, 1, 1)

        self.label_3 = QLabel(self.centralwidget)
        self.label_3.setObjectName(u"label_3")

        self.gridLayout.addWidget(self.label_3, 2, 0, 1, 1)

        self.replaceLineEdit = QLineEdit(self.centralwidget)
        self.replaceLineEdit.setObjectName(u"replaceLineEdit")

        self.gridLayout.addWidget(self.replaceLineEdit, 2, 1, 1, 1)

        self.verticalLayout.addLayout(self.gridLayout)

        self.renameButton = QPushButton(self.centralwidget)
        self.renameButton.setObjectName(u"renameButton")
        sizePolicy3 = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.renameButton.sizePolicy().hasHeightForWidth())
        self.renameButton.setSizePolicy(sizePolicy3)

        self.verticalLayout.addWidget(self.renameButton)

        MainWindow.setCentralWidget(self.centralwidget)
        
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        self.statusbar.setEnabled(True)
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"rename", None))
        self.label.setText(QCoreApplication.translate("MainWindow", u"\u6267\u884c\u8def\u5f84:", None))
        self.browseButton.setText(QCoreApplication.translate("MainWindow", u"\u6d4f\u89c8...", None))
        self.label_2.setText(QCoreApplication.translate("MainWindow", u"\u67e5\u627e\u5185\u5bb9:", None))
        self.label_3.setText(QCoreApplication.translate("MainWindow", u"\u66ff\u6362\u4e3a:", None))
        self.renameButton.setText(QCoreApplication.translate("MainWindow", u"\u5f00\u59cb", None))

def batch_rename(root_dir, find_str, replace_str):
    """批量重命名文件和文件夹"""
    renamed_count = 0
    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=False):
        # 重命名文件
        for filename in filenames:
            if find_str in filename:
                old_path = os.path.join(dirpath, filename)
                new_filename = filename.replace(find_str, replace_str)
                new_path = os.path.join(dirpath, new_filename)
                try:
                    os.rename(old_path, new_path)
                    renamed_count += 1
                except Exception:
                    pass  # 静默异常
        
        # 重命名文件夹
        for dirname in dirnames:
            if find_str in dirname:
                old_dir = os.path.join(dirpath, dirname)
                new_dir = os.path.join(dirpath, dirname.replace(find_str, replace_str))
                try:
                    os.rename(old_dir, new_dir)
                    renamed_count += 1
                except Exception:
                    pass  # 静默异常
    
    return renamed_count

class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        
        # 初始化界面
        self.init_ui()
        
        # 连接信号和槽
        self.connect_signals()
    
    def init_ui(self):
        """初始化界面"""
        # 设置初始路径为当前目录
        self.ui.pathLineEdit.setText(os.path.dirname(os.path.abspath(__file__)))
    
    def connect_signals(self):
        """连接信号和槽"""
        self.ui.browseButton.clicked.connect(self.on_browse)
        self.ui.renameButton.clicked.connect(self.on_rename)
    
    def on_browse(self):
        """选择执行路径"""
        current_path = self.ui.pathLineEdit.text()
        directory = QFileDialog.getExistingDirectory(
            self,
            "选择要重命名的文件夹",
            current_path or os.path.dirname(os.path.abspath(__file__))
        )
        if directory:
            self.ui.pathLineEdit.setText(directory)
    
    def on_rename(self):
        """执行批量重命名"""
        find_str = self.ui.findLineEdit.text()
        replace_str = self.ui.replaceLineEdit.text()
        
        if not find_str:
            self.statusBar().showMessage("查找内容不能为空！", 3000)
            return
        
        root_dir = self.ui.pathLineEdit.text() or os.path.dirname(os.path.abspath(__file__))
        
        if not os.path.exists(root_dir):
            QMessageBox.critical(self, "错误", "指定的路径不存在！")
            return
        
        try:
            renamed_count = batch_rename(root_dir, find_str, replace_str)
            self.statusBar().showMessage(f"批量重命名完成！共处理 {renamed_count} 个文件/文件夹。路径: {root_dir}", 5000)
        except Exception as e:
            self.statusBar().showMessage(f"重命名失败: {str(e)}", 5000)
            QMessageBox.critical(self, "错误", f"重命名过程中发生错误：\n{str(e)}")

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()