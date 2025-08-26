# -*- coding: utf-8 -*-
"""
C4D实时尺寸编辑工具 - 常驻显示，在点线面编辑模式中修改几何体
"""

import c4d
from c4d import gui, utils

# 全局对话框实例，防止被回收
g_dialog = None

class RealtimeSizeEditor(gui.GeDialog):
    """实时尺寸编辑器，直接修改几何体而非PSR变换"""
    
    # 控件ID
    ID_WIDTH = 1001   # 宽度(X)
    ID_HEIGHT = 1002  # 高度(Y)
    ID_DEPTH = 1003   # 深度(Z)
    ID_APPLY = 1004   # 应用修改
    ID_INFO = 1005    # 信息显示
    ID_AUTO_UPDATE = 1006  # 自动更新开关
    
    def __init__(self):
        super(RealtimeSizeEditor, self).__init__()
        self.doc = c4d.documents.GetActiveDocument()
        self.selected_obj = None
        self.last_obj_id = None
        self.auto_update = True
        self.updating = False  # 防止递归更新
    
    def CreateLayout(self):
        """创建实时尺寸编辑器布局"""
        self.SetTitle("实时尺寸编辑器")
        
        # 信息显示
        self.AddStaticText(self.ID_INFO, c4d.BFH_CENTER, name="选择对象查看尺寸")
        
        # 自动更新开关
        self.AddCheckbox(self.ID_AUTO_UPDATE, c4d.BFH_LEFT, name="自动更新")
        self.SetBool(self.ID_AUTO_UPDATE, True)
        
        # 宽度 (X轴)
        self.AddStaticText(0, c4d.BFH_LEFT, name="宽度 (X):")
        self.AddEditNumber(self.ID_WIDTH, c4d.BFH_SCALEFIT)
        
        # 高度 (Y轴)
        self.AddStaticText(0, c4d.BFH_LEFT, name="高度 (Y):")
        self.AddEditNumber(self.ID_HEIGHT, c4d.BFH_SCALEFIT)
        
        # 深度 (Z轴)
        self.AddStaticText(0, c4d.BFH_LEFT, name="深度 (Z):")
        self.AddEditNumber(self.ID_DEPTH, c4d.BFH_SCALEFIT)
        
        # 应用按钮
        self.AddButton(self.ID_APPLY, c4d.BFH_CENTER, name="应用尺寸修改")
        
        # 初始值
        self.SetFloat(self.ID_WIDTH, 0.0)
        self.SetFloat(self.ID_HEIGHT, 0.0)
        self.SetFloat(self.ID_DEPTH, 0.0)
        
        print("实时尺寸编辑器创建完成")
        return True
    
    def UpdateSelection(self):
        """更新选中对象信息并显示当前尺寸"""
        if self.updating:
            return
            
        try:
            self.updating = True
            
            if not self.doc:
                self.doc = c4d.documents.GetActiveDocument()
                if not self.doc:
                    return
            
            current_obj = self.doc.GetActiveObject()
            
            # 检查是否切换了对象
            current_obj_id = current_obj.GetGUID() if current_obj else None
            
            if current_obj_id != self.last_obj_id:
                self.selected_obj = current_obj
                self.last_obj_id = current_obj_id
                
                if self.selected_obj:
                    self.DisplayObjectSize()
                else:
                    self.ClearDisplay()
                    
        except Exception as e:
            print(f"更新选择时出错: {str(e)}")
        finally:
            self.updating = False
    
    def DisplayObjectSize(self):
        """显示对象的当前尺寸"""
        if not self.selected_obj:
            return
            
        try:
            obj_name = self.selected_obj.GetName()
            
            # 获取对象的边界框尺寸
            bbox = self.GetObjectBoundingBox(self.selected_obj)
            if bbox:
                width = bbox['size'].x
                height = bbox['size'].y
                depth = bbox['size'].z
                
                # 更新输入框
                self.SetFloat(self.ID_WIDTH, width)
                self.SetFloat(self.ID_HEIGHT, height)
                self.SetFloat(self.ID_DEPTH, depth)
                
                # 显示信息
                obj_type = self.GetObjectTypeName(self.selected_obj)
                scale = self.selected_obj[c4d.ID_BASEOBJECT_REL_SCALE]
                
                info_text = f"{obj_name} ({obj_type})\n尺寸: {width:.2f} x {height:.2f} x {depth:.2f}\n缩放: {scale.x:.2f} x {scale.y:.2f} x {scale.z:.2f}"
                self.SetString(self.ID_INFO, info_text)
            else:
                self.SetString(self.ID_INFO, f"{obj_name} - 无法获取尺寸")
                
        except Exception as e:
            print(f"显示对象尺寸时出错: {str(e)}")
    
    def ClearDisplay(self):
        """清空显示"""
        self.SetFloat(self.ID_WIDTH, 0.0)
        self.SetFloat(self.ID_HEIGHT, 0.0)
        self.SetFloat(self.ID_DEPTH, 0.0)
        self.SetString(self.ID_INFO, "未选择对象")
    
    def GetObjectTypeName(self, obj):
        """获取对象类型名称"""
        obj_type = obj.GetType()
        type_names = {
            c4d.Ocube: "立方体",
            c4d.Osphere: "球体", 
            c4d.Ocylinder: "圆柱体",
            c4d.Oplane: "平面",
            c4d.Otorus: "圆环",
            c4d.Opolygon: "多边形对象",
            c4d.Ospline: "样条"
        }
        return type_names.get(obj_type, f"类型{obj_type}")
    
    def GetObjectBoundingBox(self, obj):
        """获取对象的真实边界框"""
        try:
            # 确保获取的是几何体的实际尺寸，不受PSR影响
            if obj.CheckType(c4d.Opolygon):
                # 多边形对象：直接计算所有点的边界框
                points = obj.GetAllPoints()
                if points and len(points) > 0:
                    min_point = c4d.Vector(float('inf'))
                    max_point = c4d.Vector(float('-inf'))
                    
                    for point in points:
                        min_point.x = min(min_point.x, point.x)
                        min_point.y = min(min_point.y, point.y)
                        min_point.z = min(min_point.z, point.z)
                        max_point.x = max(max_point.x, point.x)
                        max_point.y = max(max_point.y, point.y)
                        max_point.z = max(max_point.z, point.z)
                    
                    size = max_point - min_point
                    center = (min_point + max_point) * 0.5
                    
                    return {
                        'min': min_point,
                        'max': max_point,
                        'size': size,
                        'center': center
                    }
            
            # 参数化对象：读取原始参数（不受缩放影响）
            elif obj.GetType() == c4d.Ocube:
                size_x = obj[c4d.PRIM_CUBE_LEN_X]
                size_y = obj[c4d.PRIM_CUBE_LEN_Y]
                size_z = obj[c4d.PRIM_CUBE_LEN_Z]
                size = c4d.Vector(size_x, size_y, size_z)
                
            elif obj.GetType() == c4d.Osphere:
                radius = obj[c4d.PRIM_SPHERE_RAD]
                diameter = radius * 2
                size = c4d.Vector(diameter, diameter, diameter)
                
            elif obj.GetType() == c4d.Ocylinder:
                radius = obj[c4d.PRIM_CYLINDER_RADIUS]
                height = obj[c4d.PRIM_CYLINDER_HEIGHT]
                diameter = radius * 2
                size = c4d.Vector(diameter, height, diameter)
                
            elif obj.GetType() == c4d.Oplane:
                width = obj[c4d.PRIM_PLANE_WIDTH]
                height = obj[c4d.PRIM_PLANE_HEIGHT]
                size = c4d.Vector(width, 0.1, height)
                
            else:
                # 其他对象：使用边界框
                bbox = obj.GetRad() * 2  # GetRad()返回半径，所以乘2得到尺寸
                size = bbox
            
            return {
                'min': size * -0.5,
                'max': size * 0.5,
                'size': size,
                'center': c4d.Vector(0)
            }
            
        except Exception as e:
            print(f"获取边界框时出错: {str(e)}")
            return None
    
    def ApplySizeChange(self, target_width, target_height, target_depth):
        """应用尺寸变更，直接修改几何体"""
        if not self.selected_obj:
            gui.MessageDialog("请先选择一个对象!")
            return False
        
        # 开始撤销记录
        self.doc.StartUndo()
        
        try:
            obj = self.selected_obj
            self.doc.AddUndo(c4d.UNDOTYPE_CHANGE, obj)
            
            print(f"=== 开始修改几何体尺寸 ===")
            print(f"对象: {obj.GetName()}")
            print(f"目标尺寸: {target_width:.2f} x {target_height:.2f} x {target_depth:.2f}")
            
            # 确保对象是可编辑的多边形对象
            if not self.EnsureEditableObject(obj):
                gui.MessageDialog("无法将对象转换为可编辑状态!")
                return False
            
            # 获取当前尺寸
            bbox = self.GetObjectBoundingBox(obj)
            if not bbox:
                gui.MessageDialog("无法获取对象尺寸!")
                return False
            
            current_size = bbox['size']
            
            # 计算缩放比例
            if current_size.x <= 0 or current_size.y <= 0 or current_size.z <= 0:
                gui.MessageDialog("对象当前尺寸无效!")
                return False
            
            scale_x = target_width / current_size.x
            scale_y = target_height / current_size.y  
            scale_z = target_depth / current_size.z
            
            print(f"当前尺寸: {current_size.x:.2f} x {current_size.y:.2f} x {current_size.z:.2f}")
            print(f"缩放比例: {scale_x:.3f} x {scale_y:.3f} x {scale_z:.3f}")
            
            # 直接修改几何体的点坐标
            success = self.ScaleGeometry(obj, scale_x, scale_y, scale_z)
            
            if success:
                # 确保PSR缩放值保持为1
                obj[c4d.ID_BASEOBJECT_REL_SCALE] = c4d.Vector(1, 1, 1)
                
                # 更新场景
                c4d.EventAdd()
                
                print("几何体尺寸修改完成!")
                gui.MessageDialog(f"尺寸修改成功!\n新尺寸: {target_width:.2f} x {target_height:.2f} x {target_depth:.2f}")
                
                # 刷新显示
                self.DisplayObjectSize()
                
                return True
            else:
                gui.MessageDialog("几何体修改失败!")
                return False
                
        except Exception as e:
            error_msg = f"修改尺寸时出错: {str(e)}"
            print(error_msg)
            gui.MessageDialog(error_msg)
            return False
            
        finally:
            self.doc.EndUndo()
    
    def EnsureEditableObject(self, obj):
        """确保对象是可编辑的多边形对象"""
        try:
            if obj.GetType() != c4d.Opolygon:
                print("转换为可编辑对象...")
                
                # 选中对象
                obj.SetBit(c4d.BIT_ACTIVE)
                self.doc.SetActiveObject(obj)
                
                # 执行Make Editable
                c4d.CallCommand(12236)  # Make Editable
                c4d.EventAdd()
                
                # 获取转换后的对象
                new_obj = self.doc.GetActiveObject()
                if new_obj and new_obj.GetType() == c4d.Opolygon:
                    self.selected_obj = new_obj
                    print(f"对象已转换为多边形对象")
                    return True
                else:
                    print("对象转换失败")
                    return False
            
            return True
            
        except Exception as e:
            print(f"确保可编辑对象时出错: {str(e)}")
            return False
    
    def ScaleGeometry(self, obj, scale_x, scale_y, scale_z):
        """直接缩放几何体的点坐标"""
        try:
            if not obj.CheckType(c4d.Opolygon):
                print("对象不是多边形对象，无法缩放几何体")
                return False
            
            # 获取所有点
            points = obj.GetAllPoints()
            if not points:
                print("对象没有点数据")
                return False
            
            print(f"缩放 {len(points)} 个点...")
            
            # 获取几何体中心
            bbox = self.GetObjectBoundingBox(obj)
            center = bbox['center'] if bbox else c4d.Vector(0)
            
            # 缩放每个点
            new_points = []
            for point in points:
                # 相对于中心点的位置
                relative_pos = point - center
                
                # 应用缩放
                scaled_pos = c4d.Vector(
                    relative_pos.x * scale_x,
                    relative_pos.y * scale_y,
                    relative_pos.z * scale_z
                )
                
                # 新的绝对位置
                new_point = center + scaled_pos
                new_points.append(new_point)
            
            # 设置新的点坐标
            obj.SetAllPoints(new_points)
            
            # 发送更新消息
            obj.Message(c4d.MSG_UPDATE)
            
            print("几何体点坐标缩放完成")
            return True
            
        except Exception as e:
            print(f"缩放几何体时出错: {str(e)}")
            return False
    
    def Command(self, id, msg):
        """处理控件事件"""
        if id == self.ID_APPLY:
            width = self.GetFloat(self.ID_WIDTH)
            height = self.GetFloat(self.ID_HEIGHT)
            depth = self.GetFloat(self.ID_DEPTH)
            
            if width > 0 and height > 0 and depth > 0:
                self.ApplySizeChange(width, height, depth)
            else:
                gui.MessageDialog("请输入有效的尺寸值!")
            return True
            
        elif id == self.ID_AUTO_UPDATE:
            self.auto_update = self.GetBool(self.ID_AUTO_UPDATE)
            print(f"自动更新: {'开启' if self.auto_update else '关闭'}")
            return True
        
        return gui.GeDialog.Command(self, id, msg)
    
    def CoreMessage(self, id, msg):
        """监听核心消息"""
        if id == c4d.EVMSG_CHANGE:
            # 只有在自动更新开启时才更新
            if self.auto_update:
                self.UpdateSelection()
        return gui.GeDialog.CoreMessage(self, id, msg)

def main():
    """主函数"""
    global g_dialog
    
    try:
        # 如果对话框已存在，关闭它
        if g_dialog is not None:
            g_dialog.Close()
        
        # 创建新的非模态对话框
        g_dialog = RealtimeSizeEditor()
        success = g_dialog.Open(c4d.DLG_TYPE_ASYNC, defaultw=350, defaulth=300)
        
        if success:
            print("实时尺寸编辑器启动成功")
        else:
            print("对话框创建失败")
            gui.MessageDialog("无法创建实时尺寸编辑器界面")
    
    except Exception as e:
        error_msg = f"启动实时尺寸编辑器时出错: {str(e)}"
        print(error_msg)
        gui.MessageDialog(error_msg)

# 如果直接运行此脚本
if __name__ == '__main__':
    main()