"""
快速测试情绪控制UI是否可见
"""
import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QCheckBox, QComboBox, QScrollArea, QFrame
from PySide6.QtCore import Qt

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("情绪控制测试")
        self.setGeometry(100, 100, 500, 700)
        
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # 创建滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scroll.setMinimumHeight(520)
        scroll.setMaximumHeight(600)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(5)
        
        # 添加一些内容
        content_layout.addWidget(QLabel("热键设置"))
        content_layout.addWidget(QLabel("音频设备"))
        content_layout.addWidget(QLabel("输出目录"))
        content_layout.addWidget(QLabel("基础参数"))
        
        # 情绪控制部分
        content_layout.addWidget(QLabel("<b>情绪控制 (SSML):</b>"))
        
        enable_cb = QCheckBox("启用情绪控制 (SSML)")
        enable_cb.setChecked(False)
        content_layout.addWidget(enable_cb)
        
        # 情绪选择
        emotion_frame = QFrame()
        emotion_layout = QVBoxLayout(emotion_frame)
        emotion_layout.addWidget(QLabel("情绪:"))
        emotion_combo = QComboBox()
        emotion_combo.addItems(["普通", "高兴", "悲伤", "生气", "兴奋"])
        emotion_layout.addWidget(emotion_combo)
        content_layout.addWidget(emotion_frame)
        
        # 强度选择
        intensity_frame = QFrame()
        intensity_layout = QVBoxLayout(intensity_frame)
        intensity_layout.addWidget(QLabel("强度:"))
        intensity_combo = QComboBox()
        intensity_combo.addItems(["很轻微", "较轻", "正常", "较强", "很强"])
        intensity_layout.addWidget(intensity_combo)
        content_layout.addWidget(intensity_frame)
        
        # 角色选择
        role_frame = QFrame()
        role_layout = QVBoxLayout(role_frame)
        role_layout.addWidget(QLabel("角色:"))
        role_combo = QComboBox()
        role_combo.addItems(["无", "女孩", "男孩", "年轻女性"])
        role_layout.addWidget(role_combo)
        content_layout.addWidget(role_frame)
        
        # 分隔线
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        content_layout.addWidget(sep)
        
        content_layout.addWidget(QLabel("其他设置..."))
        content_layout.addStretch()
        
        scroll.setWidget(content)
        layout.addWidget(scroll)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())
