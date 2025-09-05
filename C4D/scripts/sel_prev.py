"""
切换到上一个摄像机
该脚本会循环切换到场景中的上一个摄像机
作者: KysaInt
日期: 2025-08-19
"""

import c4d

def main():
    try:
        # 获取活跃文档
        doc = c4d.documents.GetActiveDocument()
        if not doc:
            print("错误: 无法获取活跃文档")
            c4d.gui.MessageDialog("错误: 无法获取活跃文档")
            return False
        
        # 获取当前活跃视口
        bd = doc.GetActiveBaseDraw()
        if not bd:
            print("错误: 无法获取活跃视口")
            c4d.gui.MessageDialog("错误: 无法获取活跃视口")
            return False
        
        # 获取当前摄像机
        current_camera = bd.GetSceneCamera(doc)
        
        # 收集所有摄像机
        cameras = []
        
        def search_objects(obj):
            while obj:
                if obj.GetType() == c4d.Ocamera:
                    cameras.append(obj)
                
                # 递归搜索子对象
                child = obj.GetDown()
                if child:
                    search_objects(child)
                
                obj = obj.GetNext()
        
        # 开始搜索所有摄像机
        first_obj = doc.GetFirstObject()
        search_objects(first_obj)
        
        if not cameras:
            error_msg = "场景中没有找到摄像机"
            print(error_msg)
            c4d.gui.MessageDialog(error_msg)
            return False
        
        # 按名称排序摄像机列表（保持与next脚本一致的顺序）
        cameras.sort(key=lambda x: x.GetName())
        
        print(f"找到 {len(cameras)} 个摄像机:")
        for i, cam in enumerate(cameras):
            print(f"  {i}: {cam.GetName()}")
        
        # 找到当前摄像机在列表中的位置
        current_index = -1
        if current_camera:
            for i, cam in enumerate(cameras):
                if cam == current_camera:
                    current_index = i
                    print(f"当前摄像机: {cam.GetName()} (索引: {i})")
                    break
        
        # 计算上一个摄像机的索引
        if current_index == -1:
            # 如果没有找到当前摄像机，切换到最后一个
            prev_index = len(cameras) - 1
            print("未找到当前摄像机，切换到最后一个摄像机")
        else:
            # 循环到上一个摄像机
            prev_index = (current_index - 1) % len(cameras)
            print(f"切换到上一个摄像机，索引: {prev_index}")
        
        # 切换到上一个摄像机
        prev_camera = cameras[prev_index]
        bd.SetSceneCamera(prev_camera)
        
        # 强制更新视图
        c4d.EventAdd()
        c4d.DrawViews(c4d.DRAWFLAGS_ONLY_ACTIVE_VIEW | c4d.DRAWFLAGS_NO_THREAD | c4d.DRAWFLAGS_NO_ANIMATION)
        
        print(f"已切换到摄像机: {prev_camera.GetName()}")
        return True
        
    except Exception as e:
        error_msg = f"脚本执行出错: {str(e)}"
        print(error_msg)
        c4d.gui.MessageDialog(error_msg)
        return False

# Cinema 4D脚本的标准执行方式
if __name__ == '__main__':
    main()
