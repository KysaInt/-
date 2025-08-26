import c4d

def iter_siblings(doc, parent):
    """按对象管理器顺序遍历某个父对象的直系子对象；parent=None 表示根层级"""
    if parent is None:
        o = doc.GetFirstObject()
        while o:
            yield o
            o = o.GetNext()
    else:
        o = parent.GetDown()
        while o:
            yield o
            o = o.GetNext()

def main():
    # 选中的对象
    selection = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_SELECTIONORDER)
    if not selection:
        return

    doc.StartUndo()

    # 按父对象分组
    groups = {}
    for obj in selection:
        parent = obj.GetUp()  # 立即父对象
        groups.setdefault(parent, []).append(obj)

    # 对每个父对象一组，按对象管理器的兄弟顺序重命名
    for parent, objs in groups.items():
        # 取该父对象的直系子对象顺序，并筛选出本次选中的那些
        chosen = set(objs)
        ordered = [o for o in iter_siblings(doc, parent) if o in chosen]

        prefix = parent.GetName() if parent else "NoParent"
        for i, obj in enumerate(ordered):
            new_name = f"{prefix}_{i}"
            doc.AddUndo(c4d.UNDOTYPE_CHANGE, obj)
            obj.SetName(new_name)

    doc.EndUndo()
    c4d.EventAdd()

if __name__ == '__main__':
    main()
