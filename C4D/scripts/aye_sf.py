#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
设置当前帧脚本
功能：
- 弹出输入界面，显示当前帧作为默认值
- 输入框激活状态，支持回车确认
- 设置时间线到指定帧数

作者：AYE
版本：1.0
日期：2025-09-03
"""

import c4d
from c4d import gui, documents

class FrameInputDialog(gui.GeDialog):
    """设置帧数的输入对话框"""
    
    # 控件ID
    ID_FRAME_INPUT = 1000
    ID_OK_BUTTON = 1001
    ID_CANCEL_BUTTON = 1002
    
    def __init__(self, current_frame):
        self.current_frame = current_frame
        self.result_frame = None
    
    def CreateLayout(self):
        """创建对话框布局"""
        self.SetTitle("设置当前帧")
        
        # 添加说明文本
        self.AddStaticText(0, c4d.BFH_LEFT, name="设置时间线到指定帧:")
        
        # 添加间距
        self.AddSeparatorV(5)
        
        # 添加输入框，并设置默认值为当前帧
        self.AddEditNumber(self.ID_FRAME_INPUT, c4d.BFH_SCALEFIT)
        self.SetInt32(self.ID_FRAME_INPUT, int(self.current_frame))
        
        # 添加间距
        self.AddSeparatorV(10)
        
        # 添加按钮组
        self.GroupBegin(0, c4d.BFH_CENTER, 2, 1)
        self.AddButton(self.ID_OK_BUTTON, c4d.BFH_LEFT, name="确定")
        self.AddButton(self.ID_CANCEL_BUTTON, c4d.BFH_LEFT, name="取消")
        self.GroupEnd()
        
        return True
    
    def InitValues(self):
        """初始化值"""
        # 设置输入框为激活状态并选中所有文本
        self.Activate(self.ID_FRAME_INPUT)
        return True
    
    def Command(self, id, msg):
        """处理按钮点击事件"""
        if id == self.ID_OK_BUTTON:
            # 获取输入的帧数
            frame = self.GetInt32(self.ID_FRAME_INPUT)
            self.result_frame = frame
            self.Close()
            return True
        elif id == self.ID_CANCEL_BUTTON:
            # 取消操作
            self.result_frame = None
            self.Close()
            return True
        elif id == self.ID_FRAME_INPUT:
            # 检查是否按下回车键
            if msg.GetLong(c4d.BFM_INPUT_QUALIFIER) & c4d.QSHIFT == 0:
                # 如果是回车键，执行确定操作
                frame = self.GetInt32(self.ID_FRAME_INPUT)
                self.result_frame = frame
                self.Close()
                return True
        
        return gui.GeDialog.Command(self, id, msg)
    
    def CoreMessage(self, id, msg):
        """处理核心消息，包括键盘事件"""
        if id == c4d.EVMSG_CHANGE:
            return True
        return gui.GeDialog.CoreMessage(self, id, msg)

def main():
    """主函数"""
    # 获取当前文档
    doc = documents.GetActiveDocument()
    if not doc:
        gui.MessageDialog("❌ 错误：没有活动的文档")
        return
    
    # 获取当前帧
    current_frame = doc.GetTime().GetFrame(doc.GetFps())
    
    # 创建并显示输入对话框
    dialog = FrameInputDialog(current_frame)
    dialog.Open(c4d.DLG_TYPE_MODAL, defaultw=250, defaulth=120)
    
    # 检查用户是否确认了输入
    if dialog.result_frame is not None:
        # 设置新的帧数
        new_frame = dialog.result_frame
        
        # 计算新的时间
        fps = doc.GetFps()
        new_time = c4d.BaseTime(new_frame, fps)
        
        # 设置文档时间
        doc.SetTime(new_time)
        
        # 更新视口
        c4d.EventAdd()

if __name__ == '__main__':
    main()