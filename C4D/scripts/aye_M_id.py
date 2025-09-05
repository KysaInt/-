#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
材质ID一键设置脚本 - 增强版
功能：
-  一键为所有材质启用材质ID
-  自动按顺序分配ID序号（从1开始）
-  生成鲜艳不重复的随机颜色
-  显示详细的处理结果
-  支持重置所有材质ID设置
-  自动保存撤销历史
-  支持所有类型的材质（VRay、标准、节点材质等）

作者：AYE
版本：3.0
日期：2025-09-03
"""

import c4d
import random
import math
from c4d import documents, gui

# VRay材质相关常量
VRAY_MATERIAL_ID = 1036219  # VRay材质类型ID
VRAY_MTLWRAPPER_ID = 1034636  # VRay材质包装器ID

# VRay材质ID相关参数
VRAY_MATERIAL_OPTION_MATTEID = 1004  # 材质ID启用选项
VRAY_MATERIAL_MATTEID = 1005  # 材质ID值
VRAY_MATERIAL_MATTEID_COLOR = 1006  # 材质ID颜色

# 颜色生成配置
COLOR_BRIGHTNESS_MIN = 0.4  # 最小亮度
COLOR_SATURATION_MIN = 0.6  # 最小饱和度
COLOR_SIMILARITY_THRESHOLD = 0.25  # 颜色相似度阈值

def generate_vibrant_colors(count):
    """生成鲜艳不重复的随机颜色"""
    colors = []
    used_colors = set()

    # 预定义的基础色相组合，确保颜色分布均匀
    base_hues = []
    for i in range(count):
        hue = (360.0 / max(count, 8)) * i
        base_hues.append(hue)

    # 打乱顺序增加随机性
    random.shuffle(base_hues)

    for i in range(count):
        attempts = 0
        max_attempts = 50

        while attempts < max_attempts:
            if i < len(base_hues):
                # 使用预定义色相，添加随机变化
                hue = base_hues[i] + random.uniform(-30, 30)
                hue = hue % 360
            else:
                # 完全随机色相
                hue = random.uniform(0, 360)

            # 确保高饱和度和亮度
            saturation = random.uniform(0.7, 1.0)
            value = random.uniform(0.7, 0.95)

            # 转换HSV到RGB
            rgb = hsv_to_rgb(hue, saturation, value)

            # 检查颜色相似度
            is_similar = False
            for used_color in used_colors:
                if color_distance(rgb, used_color) < COLOR_SIMILARITY_THRESHOLD:
                    is_similar = True
                    break

            if not is_similar:
                colors.append(rgb)
                used_colors.add((round(rgb.x, 2), round(rgb.y, 2), round(rgb.z, 2)))
                break

            attempts += 1

        # 如果无法找到足够不同的颜色，使用备用方案
        if len(colors) <= i:
            hue = (360.0 / count) * i
            rgb = hsv_to_rgb(hue, 0.8, 0.9)
            colors.append(rgb)

    return colors

def hsv_to_rgb(h, s, v):
    """将HSV颜色转换为RGB颜色"""
    h = h / 60.0
    i = int(h)
    f = h - i
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))

    if i == 0:
        r, g, b = v, t, p
    elif i == 1:
        r, g, b = q, v, p
    elif i == 2:
        r, g, b = p, v, t
    elif i == 3:
        r, g, b = p, q, v
    elif i == 4:
        r, g, b = t, p, v
    else:
        r, g, b = v, p, q

    return c4d.Vector(r, g, b)

def color_distance(color1, color2):
    """计算两个颜色之间的欧几里得距离"""
    if isinstance(color2, tuple):
        color2 = c4d.Vector(color2[0], color2[1], color2[2])

    return math.sqrt(
        (color1.x - color2.x) ** 2 +
        (color1.y - color2.y) ** 2 +
        (color1.z - color2.z) ** 2
    )

def find_vray_materials(doc):
    """查找场景中的所有材质（不再限制为VRay材质）"""
    all_materials = doc.GetMaterials()

    print(f" 检测到场景中共有 {len(all_materials)} 个材质")

    # 直接返回所有材质，不做任何过滤
    for mat in all_materials:
        mat_type = mat.GetType()
        mat_name = mat.GetName()
        mat_typename = mat.GetTypeName()

        print(f" ✅ 识别材质: '{mat_name}' | TypeID: {mat_type} | TypeName: {mat_typename}")

    print(f"  将处理所有 {len(all_materials)} 个材质")
    return all_materials

def set_material_id_properties(material, mat_id, color):
    """为材质设置ID和颜色属性"""
    try:
        print(f" 正在设置材质: '{material.GetName()}' -> ID: {mat_id}")

        # 1. 启用 Material ID
        success_enable = False

        # 方法1: 使用 Cinema4D 常量
        try:
            if hasattr(c4d, 'MTLMATERIALID_MATERIAL_ID_ENABLED'):
                material[c4d.MTLMATERIALID_MATERIAL_ID_ENABLED] = True
                success_enable = True
                print(f"   ✅ 使用 C4D 常量启用 Material ID")
        except Exception as e:
            print(f"   ❌ C4D 常量启用失败: {e}")

        # 方法2: 通过关键词查找参数
        if not success_enable:
            enable_keys = ['material id', 'matte id', 'matteid', 'enable id', 'id enable']
            enable_param = find_param_by_keywords(material, enable_keys)
            if enable_param is not None:
                try:
                    material[enable_param] = True
                    success_enable = True
                    print(f"   ✅ 通过关键词启用 Material ID: {enable_param}")
                except Exception as e:
                    print(f"   ❌ 关键词启用失败: {e}")

        # 方法3: 使用预定义常量作为备用
        if not success_enable:
            try:
                material[VRAY_MATERIAL_OPTION_MATTEID] = True
                success_enable = True
                print(f"   ✅ 使用备用常量启用 Material ID")
            except Exception as e:
                print(f"   ❌ 备用常量启用失败: {e}")

        # 2. 设置 Material ID 数值
        success_id = False

        # 方法1: 使用 MTLMATERIALID_MATERIAL_ID_NUMBER (这是正确的ID字段)
        try:
            if hasattr(c4d, 'MTLMATERIALID_MATERIAL_ID_NUMBER'):
                material[c4d.MTLMATERIALID_MATERIAL_ID_NUMBER] = mat_id
                success_id = True
                print(f"   ✅ 使用 MATERIAL_ID_NUMBER 设置ID: {mat_id}")
        except Exception as e:
            print(f"   ❌ MATERIAL_ID_NUMBER 设置失败: {e}")

        # 方法2: 使用 MTLMATERIALID_MATERIAL_ID
        if not success_id:
            try:
                if hasattr(c4d, 'MTLMATERIALID_MATERIAL_ID'):
                    material[c4d.MTLMATERIALID_MATERIAL_ID] = mat_id
                    success_id = True
                    print(f"   ✅ 使用 MATERIAL_ID 设置ID: {mat_id}")
            except Exception as e:
                print(f"   ❌ MATERIAL_ID 设置失败: {e}")

        # 方法3: 通过关键词查找ID参数
        if not success_id:
            id_keys = ['material id', 'matte id', 'matteid', 'id number', 'id value']
            id_param = find_param_by_keywords(material, id_keys)
            if id_param is not None:
                try:
                    material[id_param] = mat_id
                    success_id = True
                    print(f"   ✅ 通过关键词设置ID: {mat_id}")
                except Exception as e:
                    print(f"   ❌ 关键词ID设置失败: {e}")

        # 方法4: 使用备用常量
        if not success_id:
            try:
                material[VRAY_MATERIAL_MATTEID] = mat_id
                success_id = True
                print(f"   ✅ 使用备用常量设置ID: {mat_id}")
            except Exception as e:
                print(f"   ❌ 备用常量ID设置失败: {e}")

        # 3. 设置 Material ID 颜色
        success_color = False

        # 方法1: 使用 MTLMATERIALID_MATERIAL_ID_COLOR_VALUE
        try:
            if hasattr(c4d, 'MTLMATERIALID_MATERIAL_ID_COLOR_VALUE'):
                material[c4d.MTLMATERIALID_MATERIAL_ID_COLOR_VALUE] = color
                success_color = True
                print(f"   ✅ 使用 COLOR_VALUE 设置颜色")
        except Exception as e:
            print(f"   ❌ COLOR_VALUE 设置失败: {e}")

        # 方法2: 使用 MTLMATERIALID_MATERIAL_ID_COLOR
        if not success_color:
            try:
                if hasattr(c4d, 'MTLMATERIALID_MATERIAL_ID_COLOR'):
                    material[c4d.MTLMATERIALID_MATERIAL_ID_COLOR] = color
                    success_color = True
                    print(f"   ✅ 使用 MATERIAL_ID_COLOR 设置颜色")
            except Exception as e:
                print(f"   ❌ MATERIAL_ID_COLOR 设置失败: {e}")

        # 方法3: 通过关键词查找颜色参数
        if not success_color:
            color_keys = ['material id color', 'matte id color', 'matteid color', 'id color']
            color_param = find_param_by_keywords(material, color_keys)
            if color_param is not None:
                try:
                    material[color_param] = color
                    success_color = True
                    print(f"   ✅ 通过关键词设置颜色")
                except Exception as e:
                    print(f"   ❌ 关键词颜色设置失败: {e}")

        # 方法4: 使用备用常量
        if not success_color:
            try:
                material[VRAY_MATERIAL_MATTEID_COLOR] = color
                success_color = True
                print(f"   ✅ 使用备用常量设置颜色")
            except Exception as e:
                print(f"   ❌ 备用常量颜色设置失败: {e}")

        # 4. 设置其他相关参数
        try:
            # 设置颜色倍增器为1（如果存在）
            if hasattr(c4d, 'MTLMATERIALID_MATERIAL_ID_COLOR_MULTIPLIER'):
                material[c4d.MTLMATERIALID_MATERIAL_ID_COLOR_MULTIPLIER] = 1.0
                print(f"   ✅ 设置颜色倍增器为1.0")
        except Exception:
            pass

        # 5. 刷新材质
        try:
            material.Message(c4d.MSG_UPDATE)
            material.Update(True, c4d.UPDATEMESSAGE_DESCRIPTION)
            print(f"   ✅ 材质刷新完成")
        except Exception as e:
            print(f"   ❌ 材质刷新失败: {e}")

        # 检查设置结果
        if success_enable and success_id:
            print(f"    材质 '{material.GetName()}' 设置成功 - ID: {mat_id}")
            return True
        else:
            print(f"   ❌ 材质 '{material.GetName()}' 设置不完整 - Enable: {success_enable}, ID: {success_id}")
            return False

    except Exception as e:
        print(f"❌ 设置材质 '{material.GetName()}' 时发生错误: {str(e)}")
        return False


def find_param_by_keywords(material, keywords):
    """在材质的描述中查找包含任一关键词的参数ID，返回第一个匹配的参数ID（或None）。

    该函数用于适配不同VRay版本的参数命名差异。
    """
    try:
        desc = material.GetDescription(c4d.DESCFLAGS_GET_0)
    except Exception:
        return None

    matches = []

    for d in desc:
        # 有些描述项可能是字典或元组，使用 DESC_NAME 和 DESC_ID 提取
        try:
            name = d[c4d.DESC_NAME]
            did = d[c4d.DESC_ID]
        except Exception:
            continue

        if not isinstance(name, str):
            continue

        lname = name.lower()
        for k in keywords:
            if k.lower() in lname:
                # 记录匹配项，优先返回完全匹配或最相关的
                score = 0
                if lname == k.lower():
                    score = 100  # 完全匹配
                elif lname.startswith(k.lower()):
                    score = 50   # 开头匹配
                elif k.lower() in lname:
                    score = 10   # 包含匹配

                matches.append((score, did, name))

    # 按评分排序，返回最佳匹配
    if matches:
        matches.sort(key=lambda x: x[0], reverse=True)
        best_match = matches[0]
        print(f"   找到参数匹配: '{best_match[2]}' (score: {best_match[0]})")
        return best_match[1]

    return None

def show_detailed_results(materials, success_count, colors):
    """显示详细的处理结果"""
    print("\n" + "=" * 70)
    print(" 材质ID设置完成 - 详细报告")
    print("=" * 70)

    for i, material in enumerate(materials):
        if i < success_count:
            color = colors[i]
            print(f"✅ {i+1:2d}. {material.GetName():<25} | ID: {i+1:2d} | RGB: ({color.x:.2f}, {color.y:.2f}, {color.z:.2f})")
        else:
            print(f"❌ {i+1:2d}. {material.GetName():<25} | 设置失败")

    print("=" * 70)
    print(f" 统计信息:")
    print(f"   • 总材质数量: {len(materials)}")
    print(f"   • 成功设置: {success_count}")
    print(f"   • 失败数量: {len(materials) - success_count}")
    print(f"   • 成功率: {(success_count/len(materials)*100):.1f}%")
    print("=" * 70)

def list_all_materials(doc):
    """列出当前文档中所有材质的名称和 Type ID，便于诊断"""
    mats = doc.GetMaterials()
    print("\n 场景中所有材质列表：")
    type_counts = {}
    for i, m in enumerate(mats):
        t = m.GetType()
        name = m.GetName()
        tname = m.GetTypeName()
        print(f"{i+1:3d}. Name: '{name}' | TypeID: {t} | TypeName: {tname}")
        type_counts[t] = type_counts.get(t, 0) + 1

    print("\n TypeID 统计：")
    for t, cnt in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"TypeID: {t}  —  Count: {cnt}")

def detect_possible_vray_types(doc):
    """基于材质名称等线索侦测可能的VRay材质Type ID"""
    mats = doc.GetMaterials()
    candidates = {}
    for m in mats:
        name = m.GetName().lower()
        t = m.GetType()
        # 名称中出现 vray 或 v-ray 的视为候选
        if 'vray' in name or 'v-ray' in name or 'v_ray' in name:
            candidates.setdefault(t, []).append(m.GetName())

    if not candidates:
        print("⚠️ 未通过名称匹配到明显的VRay材质。建议使用 'list' 模式查看所有 TypeID。")
        return

    print("✅ 通过名称匹配到以下可能的 VRay TypeID：")
    for t, names in candidates.items():
        print(f"TypeID: {t} — Count: {len(names)}")
        for n in names:
            print(f"    • {n}")

def dump_material_info(mat):
    """打印单个材质的详细信息：名称、Type、TypeName、描述项及当前值"""
    print("\n" + "-" * 80)
    print(f"Material: '{mat.GetName()}'")
    print(f"  TypeID: {mat.GetType()}")
    try:
        print(f"  TypeName: {mat.GetTypeName()}")
    except Exception:
        pass
    print("  Description fields:")
    try:
        desc = mat.GetDescription(c4d.DESCFLAGS_GET_0)
    except Exception as e:
        print(f"   (无法获取描述：{e})")
        desc = None

    if desc:
        for d in desc:
            try:
                name = d.get(c4d.DESC_NAME, '<noname>')
                did = d.get(c4d.DESC_ID, None)
            except Exception:
                continue

            # 打印描述项名和ID
            print(f"   - Field: {name}")
            print(f"       DESC_ID: {did}")
            # 尝试读取当前值
            try:
                if did is not None:
                    val = mat[did]
                else:
                    val = '<no id>'
            except Exception as e:
                val = f'<read error: {e}>'
            print(f"       Current Value: {val}")
    print("-" * 80 + "\n")

def main():
    """主函数 - 一键设置材质ID"""
    print(" 启动材质ID一键设置工具...")

    # 获取当前文档
    doc = documents.GetActiveDocument()
    if not doc:
        gui.MessageDialog("❌ 错误：没有活动的文档")
        return

    # 添加调试：列出所有材质
    list_all_materials(doc)

    print(" 正在扫描场景中的所有材质...")

    # 查找所有材质（不再限制为VRay材质）
    materials = find_vray_materials(doc)

    if not materials:
        message = "⚠️ 场景中没有找到任何材质\n\n"
        message += "请确保场景中包含材质后再运行脚本。"
        gui.MessageDialog(message)
        return

    print(f"✅ 找到 {len(materials)} 个材质")
    print(" 正在生成随机颜色...")

    # 生成鲜艳的随机颜色
    colors = generate_vibrant_colors(len(materials))

    print(" 开始应用材质ID设置...")

    # 开始撤销记录
    doc.StartUndo()

    success_count = 0

    # 为每个材质设置ID和颜色
    for i, material in enumerate(materials):
        doc.AddUndo(c4d.UNDOTYPE_CHANGE, material)

        mat_id = i + 1  # 从1开始编号
        color = colors[i]

        if set_material_id_properties(material, mat_id, color):
            success_count += 1

    # 结束撤销记录
    doc.EndUndo()

    # 刷新场景显示
    c4d.EventAdd()

    # 显示详细结果
    show_detailed_results(materials, success_count, colors)

    # 显示简要对话框
    if success_count == len(materials):
        icon = ""
        status = "完美完成"
    elif success_count > 0:
        icon = "⚠️"
        status = "部分完成"
    else:
        icon = "❌"
        status = "设置失败"

    message = f"{icon} 材质ID设置{status}！\n\n"
    message += f" 处理统计：\n"
    message += f"   • 找到材质：{len(materials)} 个\n"
    message += f"   • 成功设置：{success_count} 个\n"
    message += f"   • ID范围：1 - {len(materials)}\n\n"

    if success_count > 0:
        message += f"✨ 功能说明：\n"
        message += f"   • 已启用所有材质的Material ID\n"
        message += f"   • 自动分配了连续的ID序号\n"
        message += f"   • 生成了鲜艳不重复的随机颜色\n"
        message += f"   • 可使用Ctrl+Z撤销操作"

    gui.MessageDialog(message)

def reset_all_material_ids():
    """重置所有VRay材质的ID设置"""
    print(" 启动VRay材质ID重置工具...")

    doc = documents.GetActiveDocument()
    if not doc:
        gui.MessageDialog("❌ 错误：没有活动的文档")
        return

    vray_materials = find_vray_materials(doc)

    if not vray_materials:
        gui.MessageDialog("⚠️ 场景中没有找到VRay材质")
        return

    # 确认对话框
    result = gui.QuestionDialog(
        f" 确定要重置所有VRay材质的ID设置吗？\n\n"
        f"将会重置 {len(vray_materials)} 个材质的：\n"
        f"• 禁用Material ID选项\n"
        f"• 重置ID值为0\n"
        f"• 重置颜色为白色\n\n"
        f"此操作可以撤销。"
    )

    if not result:
        print("❌ 用户取消了重置操作")
        return

    print(f" 正在重置 {len(vray_materials)} 个材质的ID设置...")

    doc.StartUndo()

    reset_count = 0
    for material in vray_materials:
        doc.AddUndo(c4d.UNDOTYPE_CHANGE, material)
        try:
            # 优先使用 Cinema4D 常量重置
            try:
                if hasattr(c4d, 'MTLMATERIALID_MATERIAL_ID_ENABLED'):
                    material[c4d.MTLMATERIALID_MATERIAL_ID_ENABLED] = False
            except Exception:
                pass

            # 重置ID值
            try:
                if hasattr(c4d, 'MTLMATERIALID_MATERIAL_ID'):
                    material[c4d.MTLMATERIALID_MATERIAL_ID] = 0
                else:
                    material[VRAY_MATERIAL_MATTEID] = 0
            except Exception:
                material[VRAY_MATERIAL_MATTEID] = 0

            # 重置颜色
            try:
                if hasattr(c4d, 'MTLMATERIALID_MATERIAL_ID_COLOR'):
                    material[c4d.MTLMATERIALID_MATERIAL_ID_COLOR] = c4d.Vector(1, 1, 1)
                else:
                    material[VRAY_MATERIAL_MATTEID_COLOR] = c4d.Vector(1, 1, 1)
            except Exception:
                material[VRAY_MATERIAL_MATTEID_COLOR] = c4d.Vector(1, 1, 1)
            reset_count += 1
            print(f"✅ 重置材质: {material.GetName()}")
        except Exception as e:
            print(f"❌ 重置材质 {material.GetName()} 时出错: {str(e)}")

    doc.EndUndo()
    c4d.EventAdd()

    print(f"✅ 重置完成，共处理 {reset_count} 个材质")
    gui.MessageDialog(f"✅ 重置完成！\n\n已重置 {reset_count} 个材质的ID设置")

# 脚本入口点
if __name__ == '__main__':
    # 检查是否有Shift键按下来执行重置功能
    import sys

    # 支持命令行参数：reset, list, detect
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        doc = documents.GetActiveDocument()
        if cmd == 'reset':
            reset_all_material_ids()
        elif cmd == 'list':
            if not doc:
                gui.MessageDialog('没有活动的文档')
            else:
                list_all_materials(doc)
        elif cmd == 'detect':
            if not doc:
                gui.MessageDialog('没有活动的文档')
            else:
                detect_possible_vray_types(doc)
        else:
            # 未知参数则执行主流程
            main()
    else:
        main()

    print("\n 提示：")
    print("   • 使用参数 'list' 可以在控制台列出所有材质及其 TypeID，例如：python script.py list")
    print("   • 使用参数 'detect' 可以基于名称尝试检测可能的 VRay TypeID")
    print("   • 使用参数 'reset' 可以重置所有材质ID")