# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'form.ui'
##
## Created by: Qt User Interface Compiler version 6.9.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QSizePolicy, QStackedWidget, QVBoxLayout,
    QWidget)

class Ui_Widget(object):
    def setupUi(self, Widget):
        if not Widget.objectName():
            Widget.setObjectName(u"Widget")
        Widget.resize(820, 520)
        font = QFont()
        font.setFamilies([u"\u9ed1\u4f53"])
        font.setPointSize(10)
        Widget.setFont(font)
        self.horizontalLayout = QHBoxLayout(Widget)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.navigationList = QListWidget(Widget)
        QListWidgetItem(self.navigationList)
        QListWidgetItem(self.navigationList)
        self.navigationList.setObjectName(u"navigationList")
        self.navigationList.setMaximumSize(QSize(110, 16777215))
        font1 = QFont()
        font1.setFamilies([u"\u5fae\u8f6f\u96c5\u9ed1"])
        font1.setPointSize(9)
        font1.setBold(False)
        font1.setItalic(False)
        font1.setUnderline(False)
        self.navigationList.setFont(font1)

        self.horizontalLayout.addWidget(self.navigationList)

        self.stackedWidget = QStackedWidget(Widget)
        self.stackedWidget.setObjectName(u"stackedWidget")
        font2 = QFont()
        font2.setFamilies([u"\u5fae\u8f6f\u96c5\u9ed1"])
        font2.setPointSize(9)
        self.stackedWidget.setFont(font2)
        self.page_1 = QWidget()
        self.page_1.setObjectName(u"page_1")
        self.verticalLayout = QVBoxLayout(self.page_1)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.label_1 = QLabel(self.page_1)
        self.label_1.setObjectName(u"label_1")
        self.label_1.setAlignment(Qt.AlignCenter)

        self.verticalLayout.addWidget(self.label_1)

        self.stackedWidget.addWidget(self.page_1)
        self.page_2 = QWidget()
        self.page_2.setObjectName(u"page_2")
        self.verticalLayout_2 = QVBoxLayout(self.page_2)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.label_2 = QLabel(self.page_2)
        self.label_2.setObjectName(u"label_2")
        self.label_2.setAlignment(Qt.AlignCenter)

        self.verticalLayout_2.addWidget(self.label_2)

        self.stackedWidget.addWidget(self.page_2)

        self.horizontalLayout.addWidget(self.stackedWidget)


        self.retranslateUi(Widget)
        self.navigationList.currentRowChanged.connect(self.stackedWidget.setCurrentIndex)

        QMetaObject.connectSlotsByName(Widget)
    # setupUi

    def retranslateUi(self, Widget):
        Widget.setWindowTitle(QCoreApplication.translate("Widget", u"Vision \u5de5\u5177\u96c6", None))

        __sortingEnabled = self.navigationList.isSortingEnabled()
        self.navigationList.setSortingEnabled(False)
        ___qlistwidgetitem = self.navigationList.item(0)
        ___qlistwidgetitem.setText(QCoreApplication.translate("Widget", u"\u56fe\u50cf\u5206\u6790", None));
        ___qlistwidgetitem1 = self.navigationList.item(1)
        ___qlistwidgetitem1.setText(QCoreApplication.translate("Widget", u"\u6587\u5b57\u8bc6\u522b", None));
        self.navigationList.setSortingEnabled(__sortingEnabled)

        self.label_1.setText(QCoreApplication.translate("Widget", u"\u8fd9\u91cc\u662f\u56fe\u50cf\u5206\u6790\u9875", None))
        self.label_2.setText(QCoreApplication.translate("Widget", u"\u8fd9\u91cc\u662f\u6587\u5b57\u8bc6\u522b\u9875", None))
    # retranslateUi

