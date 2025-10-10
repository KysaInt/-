"""
测试设置面板布局 - 验证情绪控制是否显示
"""
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                               QLabel, QCheckBox, QComboBox, QFrame, QPushButton)
from PySide6.QtCore import Qt
import sys

def create_test_window():
    app = QApplication(sys.argv)
    
    window = QWidget()
    window.setWindowTitle("设置面板测试")
    window.setGeometry(100, 100, 600, 800)
    
    main_layout = QVBoxLayout(window)
    
    # 模拟设置面板
    settings_layout = QVBoxLayout()
    settings_layout.setSpacing(3)
    
    # 1. 热键
    settings_layout.addWidget(QLabel("热键:"))
    settings_layout.addWidget(QPushButton("点击录制快捷键"))
    
    # 2. 音频设备
    settings_layout.addWidget(QLabel("音频设备:"))
    audio_combo = QComboBox()
    audio_combo.addItems(["设备1", "设备2"])
    settings_layout.addWidget(audio_combo)
    
    # 3. 输出目录
    settings_layout.addWidget(QLabel("输出目录:"))
    output_check = QCheckBox("启用自定义输出目录")
    settings_layout.addWidget(output_check)
    
    # 4. 基础参数
    settings_layout.addWidget(QLabel("基础参数:"))
    basic_frame = QFrame()
    basic_layout = QHBoxLayout(basic_frame)
    basic_layout.addWidget(QLabel("语速:"))
    basic_layout.addWidget(QComboBox())
    basic_layout.addWidget(QLabel("音调:"))
    basic_layout.addWidget(QComboBox())
    settings_layout.addWidget(basic_frame)
    
    # 5. 情绪控制标题
    emotion_title = QLabel("<b>情绪控制 (SSML):</b>")
    settings_layout.addWidget(emotion_title)
    
    # 6. 启用情绪控制复选框
    enable_emotion = QCheckBox("启用情绪控制 (SSML)")
    enable_emotion.setChecked(False)
    settings_layout.addWidget(enable_emotion)
    
    # 7. 情绪选项
    emotion_frame = QFrame()
    emotion_layout = QHBoxLayout(emotion_frame)
    emotion_layout.addWidget(QLabel("情绪:"))
    emotion_combo = QComboBox()
    emotion_combo.addItems(["普通", "高兴", "悲伤", "生气"])
    emotion_layout.addWidget(emotion_combo, 1)
    emotion_layout.addWidget(QLabel("强度:"))
    intensity_combo = QComboBox()
    intensity_combo.addItems(["正常", "较强", "很强"])
    emotion_layout.addWidget(intensity_combo)
    settings_layout.addWidget(emotion_frame)
    
    # 8. 角色选项
    role_frame = QFrame()
    role_layout = QHBoxLayout(role_frame)
    role_layout.addWidget(QLabel("角色:"))
    role_combo = QComboBox()
    role_combo.addItems(["无", "女孩", "男孩"])
    role_layout.addWidget(role_combo)
    role_layout.addStretch()
    settings_layout.addWidget(role_frame)
    
    # 9. 分隔线
    separator = QFrame()
    separator.setFrameShape(QFrame.HLine)
    separator.setFrameShadow(QFrame.Sunken)
    settings_layout.addWidget(separator)
    
    # 10. 其他说明
    settings_layout.addWidget(QLabel("↑ 以上是完整的设置面板内容"))
    settings_layout.addStretch()
    
    main_layout.addLayout(settings_layout)
    
    # 统计信息
    count_label = QLabel(f"总控件数: {settings_layout.count()}")
    count_label.setStyleSheet("background: yellow; padding: 5px;")
    main_layout.addWidget(count_label)
    
    window.show()
    
    print(f"设置面板控件数: {settings_layout.count()}")
    print("情绪控制相关控件:")
    print(f"  - 标题: {emotion_title is not None}")
    print(f"  - 复选框: {enable_emotion is not None}")
    print(f"  - 情绪框: {emotion_frame is not None}")
    print(f"  - 角色框: {role_frame is not None}")
    
    return app.exec()

if __name__ == "__main__":
    sys.exit(create_test_window())
