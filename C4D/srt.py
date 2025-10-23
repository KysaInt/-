# -*- coding: utf-8 -*-
"""
SRT字幕同步到C4D文本对象
支持C4D Python解释器运行
选择SRT文件后,将字幕内容、入点、出点同步到选中的文本对象
"""

import c4d
import os
import re
from c4d import gui, storage

class SrtSubtitle:
    """SRT字幕类"""
    def __init__(self, index, start_time, end_time, text):
        self.index = index
        self.start_time = start_time  # 帧数
        self.end_time = end_time      # 帧数
        self.text = text

def parse_srt_time(time_str, fps=25):
    """
    解析SRT时间格式 (HH:MM:SS,mmm) 转换为帧数
    time_str: 时间字符串,格式为 "00:00:01,500"
    fps: 帧率,默认25fps
    """
    # 匹配时间格式: 00:00:01,500
    match = re.match(r'(\d+):(\d+):(\d+),(\d+)', time_str)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2))
        seconds = int(match.group(3))
        milliseconds = int(match.group(4))
        
        # 转换为总秒数
        total_seconds = hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0
        
        # 转换为帧数
        frame = int(total_seconds * fps)
        return frame
    return 0

def parse_srt_file(file_path, fps=25):
    """
    解析SRT字幕文件
    返回字幕列表
    """
    print("[DEBUG] 解析SRT文件: {}".format(file_path))
    subtitles = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        print("[DEBUG] 成功以UTF-8编码读取文件")
    except:
        try:
            with open(file_path, 'r', encoding='gbk') as f:
                content = f.read()
            print("[DEBUG] 成功以GBK编码读取文件")
        except Exception as e:
            print("[DEBUG] 文件读取失败: {}".format(e))
            return None
    
    print("[DEBUG] 文件内容长度: {} 字符".format(len(content)))
    
    # 分割每个字幕块
    blocks = content.strip().split('\n\n')
    print("[DEBUG] 分割后的字幕块数: {}".format(len(blocks)))
    
    for block_idx, block in enumerate(blocks):
        lines = block.strip().split('\n')
        print("[DEBUG] 处理块 {}: {} 行".format(block_idx, len(lines)))
        if len(lines) < 3:
            print("[DEBUG] 块 {} 行数不足，跳过".format(block_idx))
            continue
        
        # 第一行是序号
        try:
            index = int(lines[0].strip())
            print("[DEBUG] 字幕索引: {}".format(index))
        except:
            print("[DEBUG] 块 {} 序号解析失败: {}".format(block_idx, lines[0]))
            continue
        
        # 第二行是时间范围
        time_line = lines[1].strip()
        print("[DEBUG] 时间行: {}".format(time_line))
        time_match = re.match(r'(.+?)\s*-->\s*(.+)', time_line)
        if not time_match:
            print("[DEBUG] 块 {} 时间行不匹配".format(block_idx))
            continue
        
        start_time_str = time_match.group(1).strip()
        end_time_str = time_match.group(2).strip()
        
        print("[DEBUG] 开始时间: {}, 结束时间: {}".format(start_time_str, end_time_str))
        
        start_frame = parse_srt_time(start_time_str, fps)
        end_frame = parse_srt_time(end_time_str, fps)
        
        print("[DEBUG] 开始帧: {}, 结束帧: {}".format(start_frame, end_frame))
        
        # 剩余行是字幕文本
        text = '\n'.join(lines[2:])
        print("[DEBUG] 字幕文本: {}".format(text[:50]))
        
        subtitle = SrtSubtitle(index, start_frame, end_frame, text)
        subtitles.append(subtitle)
    
    print("[DEBUG] 成功解析 {} 条字幕".format(len(subtitles)))
    return subtitles

def apply_subtitles_to_objects(doc, objects, subtitles):
    """
    将字幕应用到文本对象：正确方式是先设置对象参数值，再用 CTrack.FillKey 将值写入关键帧。
    若字符串轨道无法返回曲线，回退到 SetTime + Record 方法。
    """
    if not objects or not subtitles:
        print("[DEBUG] 错误: objects={}, subtitles={}".format(bool(objects), bool(subtitles)))
        return False

    fps = doc.GetFps()
    print("[DEBUG] 文档FPS: {}".format(fps))
    original_time = doc.GetTime()
    print("[DEBUG] 原始时间: {}".format(original_time))
    doc.StartUndo()

    applied_count = 0

    # 单对象模式：将所有字幕写到同一个文本对象上（最常见的需求）
    if len(objects) == 1:
        obj = objects[0]
        print("[DEBUG] 单对象模式: 对象名称={}, 对象类型={}".format(obj.GetName(), obj.GetType()))

        try:
            doc.AddUndo(c4d.UNDOTYPE_CHANGE, obj)

            # 检查对象是否支持文本参数
            test_desc_id = c4d.DescID(c4d.DescLevel(c4d.PRIM_TEXT_TEXT, c4d.DTYPE_STRING, 0))
            current_text = obj.GetParameter(test_desc_id, c4d.DESCFLAGS_GET_0)
            print("[DEBUG] 对象当前文本内容: {} (类型: {})".format(current_text, type(current_text)))
            
            # 使用带类型的 DescID（字符串），确保轨道/关键帧正确关联
            text_desc_id = c4d.DescID(c4d.DescLevel(c4d.PRIM_TEXT_TEXT, c4d.DTYPE_STRING, 0))
            print("[DEBUG] 尝试找到或创建文本轨道...")
            text_track = obj.FindCTrack(text_desc_id)
            if not text_track:
                print("[DEBUG] 文本轨道不存在，创建新轨道...")
                text_track = c4d.CTrack(obj, text_desc_id)
                obj.InsertTrackSorted(text_track)
                doc.AddUndo(c4d.UNDOTYPE_NEW, text_track)
            else:
                print("[DEBUG] 找到现有文本轨道")

            curve = text_track.GetCurve()
            print("[DEBUG] 曲线对象: {}".format(curve))
            if curve:
                while curve.GetKeyCount() > 0:
                    curve.DelKey(0)
                print("[DEBUG] 已清除旧关键帧，清除后的关键帧数: {}".format(curve.GetKeyCount()))

            def write_key_at_frame(frame, value):
                """在指定帧写入文本值"""
                t = c4d.BaseTime(frame, fps)
                previous_time = doc.GetTime()
                try:
                    doc.SetTime(t)
                    # 先设置参数值
                    obj.SetParameter(text_desc_id, value, c4d.DESCFLAGS_SET_0)
                    print("[DEBUG] 在帧 {} 设置参数值为: '{}'".format(frame, value[:30] if value else '(空)'))
                    
                    if curve:
                        # 使用曲线添加关键帧
                        kd = curve.AddKey(t)
                        if not kd:
                            print("[DEBUG] 在帧 {} 创建关键帧对象失败".format(frame))
                            return False
                        
                        key = kd["key"]
                        print("[DEBUG] 成功创建关键帧对象，正在填充数据...")
                        
                        # 使用 FillKey 将当前参数值写入关键帧
                        text_track.FillKey(doc, obj, key)
                        print("[DEBUG] FillKey 完成")
                        
                        # 设置为阶跃插值
                        try:
                            key.SetInterpolation(curve, c4d.KEYINTERPOLATION_STEP)
                            print("[DEBUG] 设置关键帧插值为阶跃")
                        except Exception as e:
                            print("[DEBUG] 设置插值失败: {}".format(e))
                        
                        print("[DEBUG] 在帧 {} 成功写入文本: '{}'".format(frame, value[:30] if value else '(空)'))
                        return True
                    else:
                        # 没有曲线时，使用 Record 方法记录当前值
                        obj.Record(text_desc_id)
                        print("[DEBUG] 使用 Record 方法在帧 {} 写入文本".format(frame))
                        return True
                except Exception as e:
                    print("[DEBUG] write_key_at_frame 错误 (帧{}, 值'{}'): {}".format(frame, value[:30] if value else '(空)', e))
                    import traceback
                    print(traceback.format_exc())
                    return False
                finally:
                    doc.SetTime(previous_time)

            for sub_idx, sub in enumerate(subtitles):
                print("[DEBUG] 处理字幕: 开始帧={}, 结束帧={}, 文本='{}'".format(sub.start_time, sub.end_time, sub.text[:30]))
                wrote = False
                
                # 正确的关键帧结构：
                # 1. 开始前一帧置空（start-1: ""）
                if sub.start_time > 0:
                    result1 = write_key_at_frame(sub.start_time - 1, "")
                    wrote = wrote or result1
                    print("[DEBUG]   帧{}: 返回{}".format(sub.start_time - 1, result1))
                
                # 2. 开始帧写入字幕（start: text）
                result2 = write_key_at_frame(sub.start_time, sub.text)
                wrote = wrote or result2
                print("[DEBUG]   帧{}: 返回{}".format(sub.start_time, result2))
                
                # 3. 结束帧保持字幕（end: text）
                result3 = write_key_at_frame(sub.end_time, sub.text)
                wrote = wrote or result3
                print("[DEBUG]   帧{}: 返回{}".format(sub.end_time, result3))
                
                # 4. 结束后一帧置空（end+1: ""）
                # 但需要检查是否有下一个字幕，如果下一个字幕紧接着开始，则只在最后一个字幕后置空
                is_last_subtitle = (sub_idx == len(subtitles) - 1)
                next_subtitle = subtitles[sub_idx + 1] if not is_last_subtitle else None
                
                # 只有在没有下一个字幕，或下一个字幕不是紧接着开始时，才在end+1置空
                if is_last_subtitle or (next_subtitle and next_subtitle.start_time > sub.end_time + 1):
                    result4 = write_key_at_frame(sub.end_time + 1, "")
                    wrote = wrote or result4
                    print("[DEBUG]   帧{}: 返回{}".format(sub.end_time + 1, result4))
                
                print("[DEBUG]   字幕综合结果: wrote={}".format(wrote))
                if wrote:
                    applied_count += 1
                    print("[DEBUG]   applied_count 增加到: {}".format(applied_count))

        except Exception as e:
            print("处理对象 '{}' 时出错: {}".format(obj.GetName(), e))
            import traceback
            print(traceback.format_exc())
        finally:
            doc.SetTime(original_time)

        doc.EndUndo()
        c4d.EventAdd()
        return applied_count > 0

    # 多对象模式：按最小数量一一对应
    count = min(len(objects), len(subtitles))
    print("[DEBUG] 多对象模式: 对象数={}, 字幕数={}".format(len(objects), len(subtitles)))
    for i in range(count):
        obj = objects[i]
        subtitle = subtitles[i]
        print("[DEBUG] 处理对象 {} - 名称: {}, 字幕: {}".format(i, obj.GetName(), subtitle.text[:30]))

        try:
            doc.AddUndo(c4d.UNDOTYPE_CHANGE, obj)

            # 文本参数描述ID
            text_desc_id = c4d.DescID(c4d.DescLevel(c4d.PRIM_TEXT_TEXT, c4d.DTYPE_STRING, 0))

            # 获取/创建轨道
            text_track = obj.FindCTrack(text_desc_id)
            if not text_track:
                text_track = c4d.CTrack(obj, text_desc_id)
                obj.InsertTrackSorted(text_track)
                doc.AddUndo(c4d.UNDOTYPE_NEW, text_track)

            curve = text_track.GetCurve()

            # 清除旧关键帧（如果能获取到曲线）
            if curve:
                while curve.GetKeyCount() > 0:
                    curve.DelKey(0)

            # 定义一个帮助函数：在某帧写入某文本值
            def write_key_at_frame(frame, value):
                """在指定帧写入文本值"""
                t = c4d.BaseTime(frame, fps)
                previous_time = doc.GetTime()
                try:
                    doc.SetTime(t)
                    # 先设置参数值
                    obj.SetParameter(text_desc_id, value, c4d.DESCFLAGS_SET_0)
                    
                    if curve:
                        # 使用曲线添加关键帧
                        kd = curve.AddKey(t)
                        if not kd:
                            print("[DEBUG] 在帧 {} 创建关键帧对象失败".format(frame))
                            return False
                        
                        key = kd["key"]
                        # 使用 FillKey 将当前参数值写入关键帧
                        text_track.FillKey(doc, obj, key)
                        
                        # 设置为阶跃插值
                        try:
                            key.SetInterpolation(curve, c4d.KEYINTERPOLATION_STEP)
                        except Exception:
                            pass
                        return True
                    else:
                        # 没有曲线时，使用 Record 方法记录当前值
                        obj.Record(text_desc_id)
                        return True
                except Exception as e:
                    print("[DEBUG] write_key_at_frame 错误 (多对象, 帧{}, 值'{}'): {}".format(frame, value[:30] if value else '(空)', e))
                    import traceback
                    print(traceback.format_exc())
                    return False
                finally:
                    doc.SetTime(previous_time)

            created_any = False

            # 检查是否是最后一个字幕
            is_last_subtitle = (i == len(subtitles) - 1)
            next_subtitle = subtitles[i + 1] if not is_last_subtitle else None

            # 1. 开始前一帧置空
            if subtitle.start_time > 0:
                result1 = write_key_at_frame(subtitle.start_time - 1, "")
                created_any = created_any or result1
                print("[DEBUG]   帧{}: 返回{}".format(subtitle.start_time - 1, result1))
            
            # 2. 开始帧写入字幕
            result2 = write_key_at_frame(subtitle.start_time, subtitle.text)
            created_any = created_any or result2
            print("[DEBUG]   帧{}: 返回{}".format(subtitle.start_time, result2))
            
            # 3. 结束帧保持字幕
            result3 = write_key_at_frame(subtitle.end_time, subtitle.text)
            created_any = created_any or result3
            print("[DEBUG]   帧{}: 返回{}".format(subtitle.end_time, result3))
            
            # 4. 结束后一帧置空
            # 只有在没有下一个字幕，或下一个字幕不是紧接着开始时，才在end+1置空
            if is_last_subtitle or (next_subtitle and next_subtitle.start_time > subtitle.end_time + 1):
                result4 = write_key_at_frame(subtitle.end_time + 1, "")
                created_any = created_any or result4
                print("[DEBUG]   帧{}: 返回{}".format(subtitle.end_time + 1, result4))

            print("[DEBUG]   字幕综合结果: created_any={}".format(created_any))
            if created_any:
                applied_count += 1
                print("[DEBUG]   applied_count 增加到: {}".format(applied_count))

        except Exception as e:
            print("处理对象 '{}' 时出错: {}".format(obj.GetName(), e))
            import traceback
            print(traceback.format_exc())
            continue
        finally:
            # 恢复时间
            doc.SetTime(original_time)

    doc.EndUndo()
    c4d.EventAdd()
    return applied_count > 0

def main():
    """主函数"""
    # 启动提示
    print("SRT字幕同步脚本已启动...")
    
    try:
        doc = c4d.documents.GetActiveDocument()
        
        if not doc:
            gui.MessageDialog("无法获取当前文档!")
            return
        
        # 获取选中的对象
        objects = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_CHILDREN | c4d.GETACTIVEOBJECTFLAGS_SELECTIONORDER)
        if not objects:
            gui.MessageDialog("请先在对象管理器中选择至少一个对象后再运行脚本。")
            return
    except Exception as e:
        gui.MessageDialog("初始化错误: " + str(e))
        return

    # 先选择SRT文件（把选择文件的步骤提前，避免因对象类型识别失败而没有弹窗）
    file_path = storage.LoadDialog(
        type=c4d.FILESELECTTYPE_ANYTHING,
        title="选择SRT字幕文件",
        flags=c4d.FILESELECT_LOAD
    )
    
    if not file_path:
        gui.MessageDialog("未选择文件！")
        return
    
    # 检查文件是否存在
    if not os.path.exists(file_path):
        gui.MessageDialog("文件不存在！")
        return
    
    # 检查文件扩展名
    if not file_path.lower().endswith('.srt'):
        result = gui.MessageDialog("选择的文件不是SRT格式,是否继续?", c4d.GEMB_YESNO)
        if result != c4d.GEMB_R_YES:
            return

    # 获取项目帧率
    fps = doc.GetFps()
    
    # 解析SRT文件
    subtitles = parse_srt_file(file_path, fps)
    
    if not subtitles:
        gui.MessageDialog("无法解析SRT文件或文件为空!\n文件: " + file_path)
        return
    
    # 不再在此处严格筛选对象，直接在应用阶段按对象逐个尝试写入文本参数，更加稳妥
    text_objects = list(objects)
    gui.MessageDialog("成功解析 {} 条字幕，将在已选的 {} 个对象上尝试写入文本。".format(len(subtitles), len(text_objects)))
    
    gui.MessageDialog("开始同步...")
    
    # 应用字幕到对象
    success = apply_subtitles_to_objects(doc, text_objects, subtitles)
    
    print("[DEBUG] 脚本执行完成!")
    print("[DEBUG] 应用字幕到对象成功返回: {}".format(success))
    
    if success:
        c4d.EventAdd()
        gui.MessageDialog(
            "字幕同步完成!\n\n" +
            "共处理 {} 个字幕和 {} 个文本对象".format(
                len(subtitles) if len(text_objects) == 1 else min(len(text_objects), len(subtitles)),
                len(text_objects)
            )
        )
    else:
        gui.MessageDialog("字幕同步失败!")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        c4d.gui.MessageDialog("脚本执行错误:\n" + str(e))
        import traceback
        print("详细错误信息:")
        print(traceback.format_exc())
