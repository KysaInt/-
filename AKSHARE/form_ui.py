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
        Widget.resize(700, 400)
        font = QFont()
        font.setFamilies([u"\u9ed1\u4f53"])
        font.setPointSize(10)
        Widget.setFont(font)
        self.horizontalLayout = QHBoxLayout(Widget)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.navigationList = QListWidget(Widget)
        QListWidgetItem(self.navigationList)
        QListWidgetItem(self.navigationList)
        QListWidgetItem(self.navigationList)
        self.navigationList.setObjectName(u"navigationList")
        self.navigationList.setMaximumSize(QSize(80, 16777215))
        font1 = QFont()
        font1.setFamilies([u"\u5fae\u8f6f\u96c5\u9ed1"])
        font1.setPointSize(9)
        font1.setBold(False)
        font1.setItalic(False)
        font1.setUnderline(False)
        font1.setKerning(True)
        font1.setStyleStrategy(QFont.PreferDefault)
        font1.setHintingPreference(QFont.PreferDefaultHinting)
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
        self.label_1.setEnabled(True)
        font3 = QFont()
        font3.setFamilies([u"\u5fae\u8f6f\u96c5\u9ed1"])
        font3.setPointSize(9)
        font3.setBold(False)
        self.label_1.setFont(font3)
        self.label_1.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.verticalLayout.addWidget(self.label_1)

        self.stackedWidget.addWidget(self.page_1)
        self.page_2 = QWidget()
        self.page_2.setObjectName(u"page_2")
        self.verticalLayout_2 = QVBoxLayout(self.page_2)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.label_2 = QLabel(self.page_2)
        self.label_2.setObjectName(u"label_2")
        self.label_2.setFont(font2)
        self.label_2.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.verticalLayout_2.addWidget(self.label_2)

        self.stackedWidget.addWidget(self.page_2)
        self.page_3 = QWidget()
        self.page_3.setObjectName(u"page_3")
        self.verticalLayout_3 = QVBoxLayout(self.page_3)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.label_3 = QLabel(self.page_3)
        self.label_3.setObjectName(u"label_3")
        self.label_3.setFont(font2)
        self.label_3.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.verticalLayout_3.addWidget(self.label_3)

        self.stackedWidget.addWidget(self.page_3)

        self.horizontalLayout.addWidget(self.stackedWidget)


        self.retranslateUi(Widget)

        self.stackedWidget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(Widget)
    # setupUi

    def retranslateUi(self, Widget):
        Widget.setWindowTitle(QCoreApplication.translate("Widget", u"\u4e3b\u754c\u9762", None))

        __sortingEnabled = self.navigationList.isSortingEnabled()
        self.navigationList.setSortingEnabled(False)
        ___qlistwidgetitem = self.navigationList.item(0)
        ___qlistwidgetitem.setText(QCoreApplication.translate("Widget", u"\u6a21\u5757\u4e00", None));
        ___qlistwidgetitem1 = self.navigationList.item(1)
        ___qlistwidgetitem1.setText(QCoreApplication.translate("Widget", u"\u6a21\u5757\u4e8c", None));
        ___qlistwidgetitem2 = self.navigationList.item(2)
        ___qlistwidgetitem2.setText(QCoreApplication.translate("Widget", u"\u6a21\u5757\u4e09", None));
        self.navigationList.setSortingEnabled(__sortingEnabled)

        self.label_1.setText(QCoreApplication.translate("Widget", u"\u8fd9\u91cc\u662f\u6a21\u5757\u4e00\u7684\u5185\u5bb9", None))
        self.label_2.setText(QCoreApplication.translate("Widget", u"\u8fd9\u91cc\u662f\u6a21\u5757\u4e8c\u7684\u5185\u5bb9", None))
        self.label_3.setText(QCoreApplication.translate("Widget", u"\u8fd9\u91cc\u662f\u6a21\u5757\u4e09\u7684\u5185\u5bb9", None))
    # retranslateUi

