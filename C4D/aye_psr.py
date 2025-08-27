# -*- coding: utf-8 -*-
"""
C4D对象变换脚本
直接输入变换指令，支持格式：
移动: x500, xy500, xyz500, mx500 (mx前缀可选)
旋转: rx50, rxy30, rxyz45 (度数)
缩放: sx2, sxy1.5, sxyz2
支持运算: x50*3, rxy45+15, sxyz2/        return operation, axes, value, is_absolute
        
    except ValueError as e:
        gui.MessageDialog(f"{str(e)}")
        return None, None, None, None
    except Exception as e:
        gui.MessageDialog(f"解析失败")
        return None, None, None, None .x50, .rx45, .sx2 (点号前缀直接设置值)
单位: 移动单位为毫米(mm)
"""

import c4d
from c4d import gui
import re
import math

def main():
    """主函数"""
    try:
        # 检查是否在C4D环境中运行
        if not hasattr(c4d, 'documents'):
            print("错误：需要在C4D中运行")
            return
        
        # 获取当前文档
        doc = c4d.documents.GetActiveDocument()
        if not doc:
            gui.MessageDialog("请先打开文档")
            return
        
        # 获取选中的对象
        selected_objects = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_CHILDREN)
        if not selected_objects:
            gui.MessageDialog("请先选择对象")
            return
        
        print(f"已选中 {len(selected_objects)} 个对象")
        
        # 直接输入变换指令
        transform_command = input_transform_command()
        if transform_command is None:
            return  # 用户取消操作
        
        # 解析变换指令
        operation, axes, value, is_absolute = parse_transform_command(transform_command)
        if operation is None or axes is None or value is None:
            return  # 解析失败
        
        # 执行变换操作
        transform_objects(doc, selected_objects, operation, axes, value, is_absolute)
        
        # 更新文档
        c4d.EventAdd()
        
        axes_str = "".join(axes)
        mode_str = "绝对" if is_absolute else "相对"
        print(f"变换完成：{operation} {mode_str} {axes_str}轴 {value * 10 if operation == '移动' else value}{'mm' if operation == '移动' else ('°' if '旋转' in operation else '')}")
        
    except Exception as e:
        error_msg = f"执行错误：{str(e)}"
        print(error_msg)
        gui.MessageDialog(error_msg)

def input_transform_command():
    """输入变换指令"""
    # 使用输入对话框获取变换指令
    command = gui.InputDialog("输入变换指令:", "")
    
    if command is None or command.strip() == "":
        return None  # 用户取消或输入为空
    
    return command.strip()

def evaluate_expression(expr):
    """安全计算数学表达式"""
    try:
        # 移除空格
        expr = expr.replace(" ", "")
        
        # 只允许数字、小数点和基本运算符
        allowed_chars = set('0123456789+-*/.() ')
        if not all(c in allowed_chars for c in expr):
            raise ValueError("不允许的字符")
        
        # 使用eval计算（仅限安全的数学表达式）
        result = eval(expr)
        return float(result)
    except Exception as e:
        raise ValueError(f"计算错误: {expr}")

def parse_transform_command(command):
    """解析变换指令"""
    try:
        # 移除所有空格并转换为小写
        command = command.replace(" ", "").lower()
        
        # 更精确的正则表达式匹配
        # 分别匹配不同的前缀模式，支持点号前缀的绝对设置
        patterns = [
            r'^(\.)?(rr)([xyz]+)(.+)$',      # .rr前缀：.rrx45, rrx45
            r'^(\.)?(r)([xyz]+)(.+)$',       # .r前缀：.rx45, rx45
            r'^(\.)?(s)([xyz]+)(.+)$',       # .s前缀：.sx2, sx2
            r'^(\.)?(m)([xyz]+)(.+)$',       # .m前缀：.mx500, mx500
            r'^(\.)([xyz]+)(.+)$',           # .无前缀：.x500
            r'^([xyz]+)(.+)$',               # 无前缀：x500, xy300
        ]
        
        match = None
        is_absolute = False  # 是否为绝对设置模式
        prefix = ''
        axes_str = ''
        value_expr = ''
        
        # 尝试匹配每个模式
        for pattern in patterns:
            match = re.match(pattern, command)
            if match:
                groups = match.groups()
                
                if len(groups) == 4 and groups[0] == '.':
                    # 有点号前缀的情况：.rx45, .rrx45, .sx2, .mx500
                    is_absolute = True
                    prefix = groups[1]
                    axes_str = groups[2]
                    value_expr = groups[3]
                elif len(groups) == 4:
                    # 无点号前缀的情况：rx45, rrx45, sx2, mx500
                    is_absolute = False
                    prefix = groups[1]
                    axes_str = groups[2]
                    value_expr = groups[3]
                elif len(groups) == 3 and groups[0] == '.':
                    # 点号+无操作前缀：.x500
                    is_absolute = True
                    prefix = ''
                    axes_str = groups[1]
                    value_expr = groups[2]
                else:
                    # 无前缀的情况：x500, xy300
                    is_absolute = False
                    prefix = ''
                    axes_str = groups[0]
                    value_expr = groups[1]
                break
        
        if not match:
            gui.MessageDialog("格式错误")
            return None, None, None
        
        # 验证轴向组合
        valid_axes = set('xyz')
        if not all(axis in valid_axes for axis in axes_str):
            gui.MessageDialog("轴向错误")
            return None, None, None
        
        # 转换为轴向列表并去重保持顺序
        axes = []
        for axis in axes_str:
            if axis.upper() not in axes:
                axes.append(axis.upper())
        
        # 确定操作类型
        if prefix == 'rr':
            operation = "相对旋转"  # HPB相对旋转
        elif prefix == 'r':
            operation = "绕轴旋转"  # 绕指定轴旋转
        elif prefix == 's':
            operation = "缩放"
        else:
            operation = "移动"  # 包括 'm' 前缀和无前缀
        
        # 计算数值表达式
        value = evaluate_expression(value_expr)
        
        # 如果是移动操作，将cm转换为mm（C4D内部单位是cm，但我们用mm显示）
        if operation == "移动":
            value = value / 10.0  # mm转换为cm
        
        axes_str = "".join(axes)
        mode_str = "绝对" if is_absolute else "相对"
        print(f"解析结果：操作={operation}, 模式={mode_str}, 轴向={axes_str}, 数值={value}")
        return operation, axes, value, is_absolute
        
    except ValueError as e:
        gui.MessageDialog(f"{str(e)}")
        return None, None, None
    except Exception as e:
        gui.MessageDialog(f"解析失败")
        return None, None, None

def transform_objects(doc, objects, operation, axes, value, is_absolute):
    """变换对象"""
    # 开始撤销记录
    doc.StartUndo()
    
    try:
        for obj in objects:
            # 记录撤销状态
            doc.AddUndo(c4d.UNDOTYPE_CHANGE, obj)
            
            if operation == "移动":
                move_object(obj, axes, value, is_absolute)
            elif operation == "绕轴旋转":
                rotate_around_axis(obj, axes, value, is_absolute)
            elif operation == "相对旋转":
                rotate_relative(obj, axes, value, is_absolute)
            elif operation == "缩放":
                scale_object(obj, axes, value, is_absolute)
            
            axes_str = "".join(axes)
            mode_str = "绝对" if is_absolute else "相对"
            display_value = value * 10 if operation == "移动" else value
            unit = "mm" if operation == "移动" else ("°" if "旋转" in operation else "")
            print(f"对象 '{obj.GetName()}' 已执行 {operation} {mode_str} {axes_str}轴 {display_value}{unit}")
    
    finally:
        # 结束撤销记录
        doc.EndUndo()

def move_object(obj, axes, value, is_absolute):
    """移动对象"""
    if is_absolute:
        # 绝对设置：直接设置位置为指定值
        pos = obj.GetRelPos()
        
        for axis in axes:
            if axis == "X":
                pos.x = value
            elif axis == "Y":
                pos.y = value
            elif axis == "Z":
                pos.z = value
    else:
        # 相对移动：在当前位置基础上增加
        pos = obj.GetRelPos()
        
        for axis in axes:
            if axis == "X":
                pos.x += value
            elif axis == "Y":
                pos.y += value
            elif axis == "Z":
                pos.z += value
    
    obj.SetRelPos(pos)

def rotate_around_axis(obj, axes, value, is_absolute):
    """绕指定轴旋转对象
    
    新的旋转逻辑：
    - rx50: 绕X轴旋转50度 (数值自动取负数以符合预期方向)
    - ry30: 绕Y轴旋转30度  
    - rz45: 绕Z轴旋转45度
    使用矩阵变换实现真正的绕轴旋转
    """
    if is_absolute:
        # 绝对旋转：只修改指定轴的 HPB 角度分量，保留未指定轴的值，避免被清零
        # 采用 HPB（GetRelRot / SetRelRot）方式直接修改对应分量
        rot = obj.GetRelRot()
        radians = math.radians(-value)
        for axis in axes:
            if axis == "X":
                rot.x = radians
            elif axis == "Y":
                rot.y = radians
            elif axis == "Z":
                rot.z = radians
        obj.SetRelRot(rot)
    else:
        # 相对旋转：在当前旋转基础上增加
        radians = math.radians(-value)
        ml = obj.GetRelMl()
        
        for axis in axes:
            if axis == "X":
                rotation_matrix = c4d.Matrix()
                rotation_matrix.v1 = c4d.Vector(1, 0, 0)
                rotation_matrix.v2 = c4d.Vector(0, math.cos(radians), -math.sin(radians))
                rotation_matrix.v3 = c4d.Vector(0, math.sin(radians), math.cos(radians))
                rotation_matrix.off = c4d.Vector(0, 0, 0)
            elif axis == "Y":
                rotation_matrix = c4d.Matrix()
                rotation_matrix.v1 = c4d.Vector(math.cos(radians), 0, math.sin(radians))
                rotation_matrix.v2 = c4d.Vector(0, 1, 0)
                rotation_matrix.v3 = c4d.Vector(-math.sin(radians), 0, math.cos(radians))
                rotation_matrix.off = c4d.Vector(0, 0, 0)
            elif axis == "Z":
                rotation_matrix = c4d.Matrix()
                rotation_matrix.v1 = c4d.Vector(math.cos(radians), -math.sin(radians), 0)
                rotation_matrix.v2 = c4d.Vector(math.sin(radians), math.cos(radians), 0)
                rotation_matrix.v3 = c4d.Vector(0, 0, 1)
                rotation_matrix.off = c4d.Vector(0, 0, 0)
            
            ml = ml * rotation_matrix
        
        obj.SetRelMl(ml)

def rotate_relative(obj, axes, value, is_absolute):
    """相对旋转对象 (原C4D HPB方式)
    
    C4D原生旋转逻辑 (HPB):
    - rrx: X轴HPB值增加 (俯仰 Pitch) - 物体前后倾斜
    - rry: Y轴HPB值增加 (航向 Heading) - 物体左右转向
    - rrz: Z轴HPB值增加 (滚转 Bank) - 物体左右滚动
    """
    # 将度数转换为弧度
    radians = math.radians(value)
    
    if is_absolute:
        # 绝对设置：只替换指定轴的 HPB 分量，保留未指定轴的原始值
        rot = obj.GetRelRot()
        for axis in axes:
            if axis == "X":
                rot.x = radians  # 俯仰 (Pitch)
            elif axis == "Y":
                rot.y = radians  # 航向 (Heading)
            elif axis == "Z":
                rot.z = radians  # 滚转 (Bank)
    else:
        # 相对旋转：在当前旋转基础上增加
        rot = obj.GetRelRot()
        
        for axis in axes:
            if axis == "X":
                rot.x += radians  # 俯仰 (Pitch)
            elif axis == "Y":
                rot.y += radians  # 航向 (Heading)
            elif axis == "Z":
                rot.z += radians  # 滚转 (Bank)
    
    obj.SetRelRot(rot)

def print_c4d_coordinate_info():
    """打印C4D坐标系统信息"""
    pass  # 已移除详细说明

def scale_object(obj, axes, value, is_absolute):
    """缩放对象"""
    if is_absolute:
        # 绝对设置：只替换指定轴的缩放分量，保留未指定轴的缩放值
        scale = obj.GetRelScale()
        for axis in axes:
            if axis == "X":
                scale.x = value
            elif axis == "Y":
                scale.y = value
            elif axis == "Z":
                scale.z = value
    else:
        # 相对缩放：在当前缩放基础上乘以
        scale = obj.GetRelScale()
        
        for axis in axes:
            if axis == "X":
                scale.x *= value
            elif axis == "Y":
                scale.y *= value
            elif axis == "Z":
                scale.z *= value
    
    obj.SetRelScale(scale)

# 如果直接运行此脚本
if __name__ == '__main__':
    main()
