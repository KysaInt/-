# -*- coding: utf-8 -*-
"""
C4D对象变换脚本
直接输入变换指令，支持格式：
移动: x500, xy500, xyz500, mx500 (mx前缀可选)
旋转: rx50, rxy30, rxyz45 (度数)
缩放: sx2, sxy1.5, sxyz2
支持运算: x50*3, rxy45+15, sxyz2/4
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
            print("错误：这个脚本必须在C4D的脚本管理器中运行")
            return
        
        # 获取当前文档
        doc = c4d.documents.GetActiveDocument()
        if not doc:
            gui.MessageDialog("错误：请先打开C4D文档")
            return
        
        # 获取选中的对象
        selected_objects = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_CHILDREN)
        if not selected_objects:
            gui.MessageDialog("错误：请先选择要移动的对象")
            return
        
        print(f"已选中 {len(selected_objects)} 个对象")
        
        # 打印坐标系统信息（首次使用时）
        print_c4d_coordinate_info()
        
        # 直接输入变换指令
        transform_command = input_transform_command()
        if transform_command is None:
            return  # 用户取消操作
        
        # 解析变换指令
        operation, axes, value = parse_transform_command(transform_command)
        if operation is None or axes is None or value is None:
            return  # 解析失败
        
        # 执行变换操作
        transform_objects(doc, selected_objects, operation, axes, value)
        
        # 更新文档
        c4d.EventAdd()
        
        axes_str = "".join(axes)
        print(f"变换完成：{operation} {axes_str}轴 {value}")
        
    except Exception as e:
        error_msg = f"执行过程中发生错误：{str(e)}"
        print(error_msg)
        gui.MessageDialog(error_msg)

def input_transform_command():
    """输入变换指令"""
    # 显示帮助信息
    help_text = """请输入变换指令，格式示例：
移动: x500, xy500, xyz500, mx500 (mx前缀可选)
旋转: rx50, rxy30, rxyz45 (绕轴旋转，度数)
相对旋转: rrx50, rrxy30, rrxyz45 (HPB相对旋转，度数)
缩放: sx2, sxy1.5, sxyz2
运算: x50*3, rxy45+15, sxyz2/4

旋转模式说明：
r前缀: 绕指定轴旋转 (数值自动取负数以符合预期方向)
- rx50: 绕X轴旋转50度 (实际使用-50度)
- ry30: 绕Y轴旋转30度 (实际使用-30度)
- rz45: 绕Z轴旋转45度 (实际使用-45度)

rr前缀: C4D原生HPB相对旋转 (数值不变)
- rrx50: X轴HPB值增加50度 (俯仰)
- rry30: Y轴HPB值增加30度 (航向)
- rrz45: Z轴HPB值增加45度 (滚转)

支持的操作：移动(x/y/z/xy/xz/yz/xyz或mx), 旋转(rx/ry/rz/rxy/rxz/ryz/rxyz), 相对旋转(rrx/rry/rrz/rrxy/rrxz/rryz/rrxyz), 缩放(sx/sy/sz/sxy/sxz/syz/sxyz)
支持的运算符：+, -, *, /"""
    
    print(help_text)
    
    # 使用输入对话框获取变换指令
    command = gui.InputDialog("输入变换指令 (如: rx50, rrx30, sxy2):", "")
    
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
            raise ValueError("包含不允许的字符")
        
        # 使用eval计算（仅限安全的数学表达式）
        result = eval(expr)
        return float(result)
    except Exception as e:
        raise ValueError(f"表达式计算错误: {expr}")

def parse_transform_command(command):
    """解析变换指令"""
    try:
        # 移除所有空格并转换为小写
        command = command.replace(" ", "").lower()
        
        # 更精确的正则表达式匹配
        # 分别匹配不同的前缀模式
        patterns = [
            r'^(rr)([xyz]+)(.+)$',      # rr前缀：rrx45, rrxy30
            r'^(r)([xyz]+)(.+)$',       # r前缀：rx45, rxy30
            r'^(s)([xyz]+)(.+)$',       # s前缀：sx2, sxy1.5
            r'^(m)([xyz]+)(.+)$',       # m前缀：mx500, mxy300
            r'^([xyz]+)(.+)$',          # 无前缀：x500, xy300
        ]
        
        match = None
        prefix = ''
        axes_str = ''
        value_expr = ''
        
        # 尝试匹配每个模式
        for pattern in patterns:
            match = re.match(pattern, command)
            if match:
                if len(match.groups()) == 3:
                    prefix = match.group(1)
                    axes_str = match.group(2)
                    value_expr = match.group(3)
                else:  # 无前缀的情况
                    prefix = ''
                    axes_str = match.group(1)
                    value_expr = match.group(2)
                break
        
        if not match:
            gui.MessageDialog("错误：输入格式不正确！\n\n正确格式示例：\nx500 (单轴移动)\nxy500 (双轴移动)\nrx45 (绕轴旋转)\nrrx45 (HPB相对旋转)\nsx2 (单轴缩放)")
            return None, None, None
        
        # 验证轴向组合
        valid_axes = set('xyz')
        if not all(axis in valid_axes for axis in axes_str):
            gui.MessageDialog("错误：轴向只能包含 x, y, z")
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
        
        axes_str = "".join(axes)
        print(f"解析结果：操作={operation}, 轴向={axes_str}, 数值={value}")
        return operation, axes, value
        
    except ValueError as e:
        gui.MessageDialog(f"错误：{str(e)}")
        return None, None, None
    except Exception as e:
        gui.MessageDialog(f"错误：指令解析失败！\n{str(e)}")
        return None, None, None

def transform_objects(doc, objects, operation, axes, value):
    """变换对象"""
    # 开始撤销记录
    doc.StartUndo()
    
    try:
        for obj in objects:
            # 记录撤销状态
            doc.AddUndo(c4d.UNDOTYPE_CHANGE, obj)
            
            if operation == "移动":
                move_object(obj, axes, value)
            elif operation == "绕轴旋转":
                rotate_around_axis(obj, axes, value)
            elif operation == "相对旋转":
                rotate_relative(obj, axes, value)
            elif operation == "缩放":
                scale_object(obj, axes, value)
            
            axes_str = "".join(axes)
            print(f"对象 '{obj.GetName()}' 已执行 {operation} {axes_str}轴 {value}")
    
    finally:
        # 结束撤销记录
        doc.EndUndo()

def move_object(obj, axes, value):
    """移动对象"""
    # 使用相对位置而不是绝对位置
    pos = obj.GetRelPos()
    
    for axis in axes:
        if axis == "X":
            pos.x += value
        elif axis == "Y":
            pos.y += value
        elif axis == "Z":
            pos.z += value
    
    obj.SetRelPos(pos)

def rotate_around_axis(obj, axes, value):
    """绕指定轴旋转对象
    
    新的旋转逻辑：
    - rx50: 绕X轴旋转50度 (数值自动取负数以符合预期方向)
    - ry30: 绕Y轴旋转30度  
    - rz45: 绕Z轴旋转45度
    使用矩阵变换实现真正的绕轴旋转
    """
    # 将度数转换为弧度，并自动取负数以符合预期的旋转方向
    radians = math.radians(-value)  # 注意：这里自动取负数
    
    # 获取对象当前的相对变换矩阵
    ml = obj.GetRelMl()
    
    for axis in axes:
        # 创建旋转矩阵
        if axis == "X":
            # 绕X轴旋转矩阵
            rotation_matrix = c4d.Matrix()
            rotation_matrix.v1 = c4d.Vector(1, 0, 0)
            rotation_matrix.v2 = c4d.Vector(0, math.cos(radians), -math.sin(radians))
            rotation_matrix.v3 = c4d.Vector(0, math.sin(radians), math.cos(radians))
            rotation_matrix.off = c4d.Vector(0, 0, 0)  # 确保位移为0
        elif axis == "Y":
            # 绕Y轴旋转矩阵
            rotation_matrix = c4d.Matrix()
            rotation_matrix.v1 = c4d.Vector(math.cos(radians), 0, math.sin(radians))
            rotation_matrix.v2 = c4d.Vector(0, 1, 0)
            rotation_matrix.v3 = c4d.Vector(-math.sin(radians), 0, math.cos(radians))
            rotation_matrix.off = c4d.Vector(0, 0, 0)  # 确保位移为0
        elif axis == "Z":
            # 绕Z轴旋转矩阵
            rotation_matrix = c4d.Matrix()
            rotation_matrix.v1 = c4d.Vector(math.cos(radians), -math.sin(radians), 0)
            rotation_matrix.v2 = c4d.Vector(math.sin(radians), math.cos(radians), 0)
            rotation_matrix.v3 = c4d.Vector(0, 0, 1)
            rotation_matrix.off = c4d.Vector(0, 0, 0)  # 确保位移为0
        
        # 应用旋转：新矩阵 = 当前矩阵 * 旋转矩阵
        ml = ml * rotation_matrix
    
    # 设置新的相对变换矩阵
    obj.SetRelMl(ml)

def rotate_relative(obj, axes, value):
    """相对旋转对象 (原C4D HPB方式)
    
    C4D原生旋转逻辑 (HPB):
    - rrx: X轴HPB值增加 (俯仰 Pitch) - 物体前后倾斜
    - rry: Y轴HPB值增加 (航向 Heading) - 物体左右转向
    - rrz: Z轴HPB值增加 (滚转 Bank) - 物体左右滚动
    """
    # 使用相对旋转而不是绝对旋转
    rot = obj.GetRelRot()
    
    # 将度数转换为弧度
    radians = math.radians(value)
    
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
    info = """
=== C4D坐标系统说明 ===
坐标系：左手坐标系
X轴：红色，向右
Y轴：绿色，向上  
Z轴：蓝色，向前

旋转模式：
1. 绕轴旋转 (r前缀):
   - rx45: 绕X轴旋转45度 (数值自动取负数以符合预期方向)
   - ry30: 绕Y轴旋转30度 (实际使用-30度)
   - rz60: 绕Z轴旋转60度 (实际使用-60度)

2. 相对旋转 (rr前缀):
   - rrx45: X轴HPB值增加45度 (俯仰 Pitch，数值不变)
   - rry30: Y轴HPB值增加30度 (航向 Heading，数值不变)
   - rrz60: Z轴HPB值增加60度 (滚转 Bank，数值不变)

推荐使用：
- 需要精确绕轴旋转时用 r前缀
- 需要C4D原生旋转行为时用 rr前缀
========================
"""
    print(info)

def scale_object(obj, axes, value):
    """缩放对象"""
    # 使用相对缩放而不是绝对缩放
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
