import c4d

def is_geometry(obj):
    """判断是否为几何体对象"""
    return obj.CheckType(c4d.Opolygon) or obj.GetType() in [
        c4d.Ocube, c4d.Osphere, c4d.Oplane, c4d.Odisc, c4d.Ospline
    ]

def iter_all_objects(obj):
    while obj:
        yield obj
        child = obj.GetDown()
        if child:
            yield from iter_all_objects(child)
        obj = obj.GetNext()

def iter_children(obj):
    children = []
    child = obj.GetDown()
    while child:
        children.append(child)
        child = child.GetNext()
    return children

def rename_geometry_by_parent(doc, root):
    """先重命名多边形对象，按父对象名 + 序号"""
    all_objs = list(iter_all_objects(root))
    mapping = []

    for obj in all_objs:
        if is_geometry(obj):
            parent = obj.GetUp()
            parent_name = parent.GetName() if parent else "NoParent"
            mapping.append((obj, parent_name))

    # 按父对象分组，生成序号
    groups = {}
    for obj, parent_name in mapping:
        groups.setdefault(parent_name, []).append(obj)

    for parent_name, objs in groups.items():
        for i, obj in enumerate(objs):
            new_name = f"{parent_name}_{i}"
            doc.AddUndo(c4d.UNDOTYPE_CHANGE, obj)
            obj.SetName(new_name)

def collapse_single_geo_null(doc, obj):
    """折叠空对象，仅当空对象下唯一多边形对象时删除空对象"""
    children = iter_children(obj)
    geo_children = [c for c in children if is_geometry(c)]
    null_children = [c for c in children if not is_geometry(c)]

    # 先递归处理子空对象
    for n in null_children:
        collapse_single_geo_null(doc, n)

    # 当前空对象处理逻辑
    if len(geo_children) == 1 and not null_children:
        geo = geo_children[0]
        parent = obj.GetUp()
        if parent:
            geo.InsertAfter(obj)
        else:
            doc.InsertObject(geo, None, None)
        doc.AddUndo(c4d.UNDOTYPE_DELETE, obj)
        obj.Remove()
    # 其他情况保持空对象，不做删除

def main():
    doc.StartUndo()
    root = doc.GetFirstObject()
    if not root:
        doc.EndUndo()
        return

    # 1. 先重命名多边形对象
    rename_geometry_by_parent(doc, root)

    # 2. 收集空对象列表，自底向上处理
    nulls = [obj for obj in iter_all_objects(root) if not is_geometry(obj)]
    for obj in reversed(nulls):
        collapse_single_geo_null(doc, obj)

    doc.EndUndo()
    c4d.EventAdd()

if __name__ == "__main__":
    main()
