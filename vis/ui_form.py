# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'form.ui'
##
## Created by: Qt User Interface Compiler (pyside6-uic)
##
## NOTE: This file may be regenerated from form.ui.
################################################################################

from PySide6.QtCore import (QCoreApplication, QMetaObject, QSize, Qt)
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QStackedWidget, QVBoxLayout, QWidget)


class Ui_Widget(object):
    def setupUi(self, Widget):
        if not Widget.objectName():
            Widget.setObjectName("Widget")
        Widget.resize(820, 520)
        font = QFont()
        font.setFamilies(["黑体"])
        font.setPointSize(10)
        Widget.setFont(font)

        self.horizontalLayout = QHBoxLayout(Widget)
        self.horizontalLayout.setObjectName("horizontalLayout")

        self.navigationList = QListWidget(Widget)
        QListWidgetItem(self.navigationList)
        QListWidgetItem(self.navigationList)
        self.navigationList.setObjectName("navigationList")
        self.navigationList.setMaximumSize(QSize(110, 16777215))
        font1 = QFont()
        font1.setFamilies(["微软雅黑"])
        font1.setPointSize(9)
        self.navigationList.setFont(font1)

        self.horizontalLayout.addWidget(self.navigationList)

        self.stackedWidget = QStackedWidget(Widget)
        self.stackedWidget.setObjectName("stackedWidget")
        font2 = QFont()
        font2.setFamilies(["微软雅黑"])
        font2.setPointSize(9)
        self.stackedWidget.setFont(font2)

        self.page_1 = QWidget()
        self.page_1.setObjectName("page_1")
        self.verticalLayout = QVBoxLayout(self.page_1)
        self.verticalLayout.setObjectName("verticalLayout")
        self.label_1 = QLabel(self.page_1)
        self.label_1.setObjectName("label_1")
        self.label_1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.verticalLayout.addWidget(self.label_1)
        self.stackedWidget.addWidget(self.page_1)

        self.page_2 = QWidget()
        self.page_2.setObjectName("page_2")
        self.verticalLayout_2 = QVBoxLayout(self.page_2)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.label_2 = QLabel(self.page_2)
        self.label_2.setObjectName("label_2")
        self.label_2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.verticalLayout_2.addWidget(self.label_2)
        self.stackedWidget.addWidget(self.page_2)

        self.horizontalLayout.addWidget(self.stackedWidget)

        self.retranslateUi(Widget)
        self.navigationList.currentRowChanged.connect(self.stackedWidget.setCurrentIndex)
        self.stackedWidget.setCurrentIndex(0)
        QMetaObject.connectSlotsByName(Widget)

    def retranslateUi(self, Widget):
        Widget.setWindowTitle(QCoreApplication.translate("Widget", "Vision 工具集", None))

        __sortingEnabled = self.navigationList.isSortingEnabled()
        self.navigationList.setSortingEnabled(False)
        self.navigationList.item(0).setText(QCoreApplication.translate("Widget", "图像分析", None))
        self.navigationList.item(1).setText(QCoreApplication.translate("Widget", "文字识别", None))
        self.navigationList.setSortingEnabled(__sortingEnabled)

        self.label_1.setText(QCoreApplication.translate("Widget", "这里是图像分析页", None))
        self.label_2.setText(QCoreApplication.translate("Widget", "这里是文字识别页", None))
