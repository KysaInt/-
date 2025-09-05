import c4d

def find_or_create_layer(doc, path):
    """
    根据路径创建图层层级
    path: list[str] 从顶层到当前层的名字
    """
    layer_root = doc.GetLayerObjectRoot()
    parent_layer = layer_root
    for name in path:
        # 在当前层级下查找是否已有该图层
        child = parent_layer.GetDown()
        target = None
        while child:
            if child.GetName() == name:
                target = child
                break
            child = child.GetNext()
        # 如果没有则新建
        if target is None:
            target = c4d.documents.LayerObject()
            target.SetName(name)
            target.InsertUnderLast(parent_layer)
        parent_layer = target
    return parent_layer

def process_object(doc, obj, parent_path=None):
    """
    遍历对象管理器并生成对应图层结构
    """
    if parent_path is None:
        parent_path = []

    # 当前对象在层级中的路径
    current_path = parent_path + [obj.GetName()]
    
    # 查找或创建对应图层
    layer = find_or_create_layer(doc, current_path)
    
    # 绑定对象到图层
    obj.SetLayerObject(layer)

    # 递归子对象
    child = obj.GetDown()
    while child:
        process_object(doc, child, current_path)
        child = child.GetNext()

def main():
    doc.StartUndo()
    obj = doc.GetFirstObject()
    while obj:
        process_object(doc, obj)
        obj = obj.GetNext()
    doc.EndUndo()
    c4d.EventAdd()

if __name__ == '__main__':
    main()
