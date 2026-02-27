"""
node_defs.builtin_nodes — AYE Node Editor 内置节点
===================================================
包含所有默认节点的定义、求值函数、分类和颜色。

新增自定义节点示例
------------------
# 在 node_defs/ 目录下新建 my_nodes.py，填写：

    from ._helpers import _n

    NODE_DEFINITIONS = {
        "My Add": (["X", "Y"], ["Sum"]),
    }
    NODE_EVAL_FUNCS = {
        "My Add": lambda i, w: {"Sum": _n(i,"X") + _n(i,"Y")},
    }
    NODE_CATEGORIES = {
        "自定义": ["My Add"],
    }
    CATEGORY_COLORS_RGB = {
        "自定义": (120, 80, 160),
    }

重启编辑器后该节点自动出现在左侧面板对应分类内。
"""

import math
from ._helpers import _n, _s, _b, _l, _safe_eval

# ╔══════════════════════════════════════════════════════════════════════╗
# ║  复合求值函数                                                        ║
# ╚══════════════════════════════════════════════════════════════════════╝

def _eval_range(i, _w):
    s, e, st = int(_n(i,"Start",0)), int(_n(i,"End",10)), int(_n(i,"Step",1))
    if st == 0: st = 1
    if abs((e - s) / st) > 10000: return {"List": []}
    return {"List": list(range(s, e, st))}

def _eval_series(i, _w):
    s, st, c = _n(i,"Start",0), _n(i,"Step",1), int(_n(i,"Count",10))
    return {"List": [s + st * j for j in range(max(0, min(c, 10000)))]}

def _eval_switch(i, _w):
    idx = int(_n(i,"Index",0))
    for k in ["A","B","C","D"]:
        if idx == 0: return {"Result": i.get(k)}
        idx -= 1
    return {"Result": None}

def _eval_expression(i, w):
    expr = w if isinstance(w, str) and w.strip() else "0"
    return {"Result": _safe_eval(expr, {"x": _n(i,"x"), "y": _n(i,"y"), "z": _n(i,"z")})}

def _merge(i, _w):
    r = []
    for k in sorted(i.keys()):
        v = i.get(k)
        if v is None: continue
        if isinstance(v, (list, tuple)): r.extend(v)
        else: r.append(v)
    return {"Result": r}

# ╔══════════════════════════════════════════════════════════════════════╗
# ║  NODE_DEFINITIONS                                                   ║
# ║  格式: "名称": ([输入端口], [输出端口])                               ║
# ╚══════════════════════════════════════════════════════════════════════╝

NODE_DEFINITIONS = {
    # ── 输入 Input ──
    "Number":       ([], ["Value"]),
    "Integer":      ([], ["Value"]),
    "Boolean":      ([], ["Value"]),
    "String":       ([], ["Value"]),
    "Slider":       ([], ["Value"]),
    "Num Slider":   ([], ["Value"]),
    # ── 输出 Output ──
    "Viewer":       (["Data"], []),
    "Print":        (["Value"], []),
    # ── 数学 Math ──
    "Add":          (["A", "B"], ["Result"]),
    "Subtract":     (["A", "B"], ["Result"]),
    "Multiply":     (["A", "B"], ["Result"]),
    "Divide":       (["A", "B"], ["Result"]),
    "Power":        (["Base", "Exp"], ["Result"]),
    "Modulo":       (["A", "B"], ["Result"]),
    "Absolute":     (["Value"], ["Result"]),
    "Negate":       (["Value"], ["Result"]),
    "Sqrt":         (["Value"], ["Result"]),
    "Sin":          (["Angle"], ["Result"]),
    "Cos":          (["Angle"], ["Result"]),
    "Tan":          (["Angle"], ["Result"]),
    "Pi":           ([], ["Value"]),
    "E":            ([], ["Value"]),
    "Round":        (["Value"], ["Result"]),
    "Floor":        (["Value"], ["Result"]),
    "Ceiling":      (["Value"], ["Result"]),
    "Clamp":        (["Value", "Min", "Max"], ["Result"]),
    # ── 逻辑 Logic ──
    "And":          (["A", "B"], ["Result"]),
    "Or":           (["A", "B"], ["Result"]),
    "Not":          (["A"], ["Result"]),
    "Xor":          (["A", "B"], ["Result"]),
    "Equals":       (["A", "B"], ["Result"]),
    "Not Equals":   (["A", "B"], ["Result"]),
    "Greater":      (["A", "B"], ["Result"]),
    "Less":         (["A", "B"], ["Result"]),
    "Gate":         (["Condition", "Value"], ["Result"]),
    # ── 文本 Text ──
    "Concatenate":  (["A", "B"], ["Result"]),
    "Text Split":   (["Text", "Sep"], ["Result"]),
    "Text Replace": (["Text", "Old", "New"], ["Result"]),
    "Text Length":  (["Text"], ["Result"]),
    "To Upper":     (["Text"], ["Result"]),
    "To Lower":     (["Text"], ["Result"]),
    "Contains":     (["Text", "Search"], ["Result"]),
    "Join":         (["List", "Sep"], ["Result"]),
    # ── 列表 List ──
    "Create List":  (["Item 0", "Item 1", "Item 2"], ["List"]),
    "List Length":  (["List"], ["Result"]),
    "List Item":    (["List", "Index"], ["Result"]),
    "List Append":  (["List", "Item"], ["Result"]),
    "List Remove":  (["List", "Index"], ["Result"]),
    "List Reverse": (["List"], ["Result"]),
    "List Sort":    (["List"], ["Result"]),
    "Range":        (["Start", "End", "Step"], ["List"]),
    "Series":       (["Start", "Step", "Count"], ["List"]),
    "Merge":        (["A", "B", "C"], ["Result"]),
    # ── 控制 Control ──
    "Branch":       (["Condition", "True", "False"], ["Result"]),
    "Switch":       (["Index", "A", "B", "C"], ["Result"]),
    # ── 转换 Convert ──
    "To String":    (["Value"], ["Result"]),
    "To Integer":   (["Value"], ["Result"]),
    "To Float":     (["Value"], ["Result"]),
    "To Boolean":   (["Value"], ["Result"]),
    # ── 工具 Utility ──
    "Relay":        (["In"], ["Out"]),
    "Expression":   (["x", "y", "z"], ["Result"]),
}

# ╔══════════════════════════════════════════════════════════════════════╗
# ║  NODE_EVAL_FUNCS                                                    ║
# ╚══════════════════════════════════════════════════════════════════════╝

NODE_EVAL_FUNCS = {
    # Input (widget value → output)
    "Number":       lambda i, w: {"Value": w if w is not None else 0.0},
    "Integer":      lambda i, w: {"Value": int(w) if w is not None else 0},
    "Boolean":      lambda i, w: {"Value": bool(w) if w is not None else False},
    "String":       lambda i, w: {"Value": w if w is not None else ""},
    "Slider":       lambda i, w: {"Value": w if w is not None else 50},
    "Num Slider":   lambda i, w: {"Value": w if w is not None else 0.0},
    # Output (无输出端口，在 evaluate 中特殊处理)
    "Viewer":       lambda i, w: {},
    "Print":        lambda i, w: {},
    # Math
    "Add":          lambda i, w: {"Result": _n(i,"A") + _n(i,"B")},
    "Subtract":     lambda i, w: {"Result": _n(i,"A") - _n(i,"B")},
    "Multiply":     lambda i, w: {"Result": _n(i,"A") * _n(i,"B")},
    "Divide":       lambda i, w: {"Result": _n(i,"A") / _n(i,"B") if _n(i,"B") != 0 else 0},
    "Power":        lambda i, w: {"Result": _n(i,"Base") ** _n(i,"Exp")},
    "Modulo":       lambda i, w: {"Result": _n(i,"A") % _n(i,"B") if _n(i,"B") != 0 else 0},
    "Absolute":     lambda i, w: {"Result": abs(_n(i,"Value"))},
    "Negate":       lambda i, w: {"Result": -_n(i,"Value")},
    "Sqrt":         lambda i, w: {"Result": math.sqrt(max(0, _n(i,"Value")))},
    "Sin":          lambda i, w: {"Result": math.sin(_n(i,"Angle"))},
    "Cos":          lambda i, w: {"Result": math.cos(_n(i,"Angle"))},
    "Tan":          lambda i, w: {"Result": math.tan(_n(i,"Angle")) if math.cos(_n(i,"Angle")) != 0 else 0},
    "Pi":           lambda i, w: {"Value": math.pi},
    "E":            lambda i, w: {"Value": math.e},
    "Round":        lambda i, w: {"Result": round(_n(i,"Value"))},
    "Floor":        lambda i, w: {"Result": math.floor(_n(i,"Value"))},
    "Ceiling":      lambda i, w: {"Result": math.ceil(_n(i,"Value"))},
    "Clamp":        lambda i, w: {"Result": max(_n(i,"Min",0), min(_n(i,"Max",1), _n(i,"Value")))},
    # Logic
    "And":          lambda i, w: {"Result": _b(i,"A") and _b(i,"B")},
    "Or":           lambda i, w: {"Result": _b(i,"A") or _b(i,"B")},
    "Not":          lambda i, w: {"Result": not _b(i,"A")},
    "Xor":          lambda i, w: {"Result": _b(i,"A") ^ _b(i,"B")},
    "Equals":       lambda i, w: {"Result": i.get("A") == i.get("B")},
    "Not Equals":   lambda i, w: {"Result": i.get("A") != i.get("B")},
    "Greater":      lambda i, w: {"Result": _n(i,"A") > _n(i,"B")},
    "Less":         lambda i, w: {"Result": _n(i,"A") < _n(i,"B")},
    "Gate":         lambda i, w: {"Result": i.get("Value") if _b(i,"Condition") else None},
    # Text
    "Concatenate":  lambda i, w: {"Result": _s(i,"A") + _s(i,"B")},
    "Text Split":   lambda i, w: {"Result": _s(i,"Text").split(_s(i,"Sep") or None)},
    "Text Replace": lambda i, w: {"Result": _s(i,"Text").replace(_s(i,"Old"), _s(i,"New"))},
    "Text Length":  lambda i, w: {"Result": len(_s(i,"Text"))},
    "To Upper":     lambda i, w: {"Result": _s(i,"Text").upper()},
    "To Lower":     lambda i, w: {"Result": _s(i,"Text").lower()},
    "Contains":     lambda i, w: {"Result": _s(i,"Search") in _s(i,"Text")},
    "Join":         lambda i, w: {"Result": _s(i,"Sep"," ").join(str(x) for x in _l(i,"List"))},
    # List
    "Create List":  lambda i, w: {"List": [v for k, v in sorted(i.items()) if v is not None]},
    "List Length":  lambda i, w: {"Result": len(_l(i,"List"))},
    "List Item":    lambda i, w: {"Result": _l(i,"List")[int(_n(i,"Index"))] if 0 <= int(_n(i,"Index")) < len(_l(i,"List")) else None},
    "List Append":  lambda i, w: {"Result": _l(i,"List") + [i.get("Item")]},
    "List Remove":  lambda i, w: {"Result": [x for j,x in enumerate(_l(i,"List")) if j != int(_n(i,"Index"))]},
    "List Reverse": lambda i, w: {"Result": list(reversed(_l(i,"List")))},
    "List Sort":    lambda i, w: {"Result": sorted(_l(i,"List"), key=lambda x: (str(type(x).__name__), x))},
    "Range":        _eval_range,
    "Series":       _eval_series,
    "Merge":        _merge,
    # Control
    "Branch":       lambda i, w: {"Result": i.get("True") if _b(i,"Condition") else i.get("False")},
    "Switch":       _eval_switch,
    # Conversion
    "To String":    lambda i, w: {"Result": str(i.get("Value",""))},
    "To Integer":   lambda i, w: {"Result": int(_n(i,"Value"))},
    "To Float":     lambda i, w: {"Result": float(_n(i,"Value"))},
    "To Boolean":   lambda i, w: {"Result": bool(i.get("Value"))},
    # Utility
    "Relay":        lambda i, w: {"Out": i.get("In")},
    "Expression":   _eval_expression,
}

# ╔══════════════════════════════════════════════════════════════════════╗
# ║  NODE_CATEGORIES  &  CATEGORY_COLORS_RGB                            ║
# ╚══════════════════════════════════════════════════════════════════════╝

NODE_CATEGORIES = {
    "输入":   ["Number", "Integer", "Boolean", "String", "Slider", "Num Slider"],
    "输出":   ["Viewer", "Print"],
    "数学":   ["Add", "Subtract", "Multiply", "Divide", "Power", "Modulo",
               "Absolute", "Negate", "Sqrt", "Sin", "Cos", "Tan",
               "Pi", "E", "Round", "Floor", "Ceiling", "Clamp"],
    "逻辑":   ["And", "Or", "Not", "Xor", "Equals", "Not Equals",
               "Greater", "Less", "Gate"],
    "文本":   ["Concatenate", "Text Split", "Text Replace", "Text Length",
               "To Upper", "To Lower", "Contains", "Join"],
    "列表":   ["Create List", "List Length", "List Item", "List Append",
               "List Remove", "List Reverse", "List Sort",
               "Range", "Series", "Merge"],
    "控制":   ["Branch", "Switch"],
    "转换":   ["To String", "To Integer", "To Float", "To Boolean"],
    "工具":   ["Relay", "Expression"],
}

# 颜色用 (R, G, B) 元组，避免在定义文件中依赖 Qt
CATEGORY_COLORS_RGB = {
    "输入": (83,  148,  80),
    "输出": (180,  80,  80),
    "数学": (100, 130, 180),
    "逻辑": (170, 130,  80),
    "文本": (140, 110, 170),
    "列表": ( 80, 160, 160),
    "控制": (190, 180,  60),
    "转换": (160, 120, 100),
    "工具": (110, 110, 140),
}
