"""
切换到名为M的摄像机
该脚本会将当前视口切换到名为M的摄像机
作者: KysaInt
日期: 2025-08-19
"""

import c4d

def main():
    try:
        # 确保脚本开始执行
        print("=== 脚本开始执行 ===")
        
        # 获取活跃文档
        doc = c4d.documents.GetActiveDocument()
        if not doc:
            print("错误: 无法获取活跃文档")
            c4d.gui.MessageDialog("错误: 无法获取活跃文档")
            return False
        
        print("成功获取活跃文档")
        
        # 查找名为"M"的摄像机
        camera = None
        camera_list = []
        
        # 递归搜索所有对象
        def search_objects(obj):
            nonlocal camera, camera_list
            while obj:
                if obj.GetType() == c4d.Ocamera:
                    camera_name = obj.GetName()
                    camera_list.append(camera_name)
                    print(f"找到摄像机: {camera_name}")
                    if camera_name == "M":
                        camera = obj
                        print(f"匹配目标摄像机: {camera_name}")
                
                # 递归搜索子对象
                child = obj.GetDown()
                if child:
                    search_objects(child)
                
                obj = obj.GetNext()
        
        # 开始搜索
        first_obj = doc.GetFirstObject()
        search_objects(first_obj)
        
        print(f"场景中所有摄像机: {camera_list}")
        
        if camera:
            print(f"准备切换到摄像机: {camera.GetName()}")
            
            # 获取活跃的BaseDraw (视口)
            bd = doc.GetActiveBaseDraw()
            if bd:
                print("成功获取活跃视口")
                # 切换摄像机
                bd.SetSceneCamera(camera)
                # 强制更新文档
                c4d.EventAdd()
                c4d.DrawViews(c4d.DRAWFLAGS_ONLY_ACTIVE_VIEW | c4d.DRAWFLAGS_NO_THREAD | c4d.DRAWFLAGS_NO_ANIMATION)
                
                # 成功切换，静默执行
                print(f"成功切换到摄像机: {camera.GetName()}")
                return True
            else:
                error_msg = "错误: 无法获取活跃视口"
                print(error_msg)
                c4d.gui.MessageDialog(error_msg)
                return False
        else:
            error_msg = f"未找到名为 'M' 的摄像机\n场景中的摄像机: {', '.join(camera_list) if camera_list else '无'}"
            print(error_msg)
            c4d.gui.MessageDialog(error_msg)
            return False
            
    except Exception as e:
        error_msg = f"脚本执行出错: {str(e)}"
        print(error_msg)
        c4d.gui.MessageDialog(error_msg)
        return False

# Cinema 4D脚本的标准执行方式
if __name__ == '__main__':
    main()
