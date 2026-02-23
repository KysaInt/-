"""
AYE Node Editor — 可执行的通用节点编辑器模板
==================================================
功能完整的节点编辑器，所有节点均可运算。
端口: 半圆贴边式，未连接空心，连接后填充。
输入节点: 内嵌 SpinBox / LineEdit / Slider / CheckBox 等可交互控件。
输出节点: 内嵌显示标签，实时显示接收到的数据。
分类: 左侧 QTabWidget 多标签页分类浏览节点。
快捷键: Space=搜索  Delete=删除  中键/Alt+左键=平移  滚轮=缩放
"""
import sys, math, random as _random, traceback, os
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QGridLayout, QTextEdit, QGraphicsView,
    QGraphicsScene, QGraphicsItem, QGraphicsPathItem, QGraphicsProxyWidget,
    QLineEdit, QSpinBox, QDoubleSpinBox, QSlider, QCheckBox,
    QSplitter, QSizePolicy, QTabWidget, QListWidget,
    QDialog, QScrollBar,
)
from PySide6.QtCore import (
    Qt, QRectF, QPointF, QPropertyAnimation, QEasingCurve,
    Signal, QLineF,
)
from PySide6.QtGui import (
    QColor, QPen, QBrush, QPainterPath, QFontDatabase, QPalette,
    QPainter, QCursor,
)

# ╔══════════════════════════════════════════════════════════════════════╗
# ║  辅助函数 — 节点求值时安全取值                                      ║
# ╚══════════════════════════════════════════════════════════════════════╝

def _n(i, k, d=0):
    """取数值，无法转换时返回默认值。"""
    v = i.get(k)
    if v is None: return d
    try: return float(v)
    except (TypeError, ValueError): return d

def _s(i, k, d=""):
    v = i.get(k)
    return str(v) if v is not None else d

def _b(i, k, d=False):
    return bool(i.get(k, d))

def _l(i, k):
    v = i.get(k)
    return list(v) if isinstance(v, (list, tuple)) else []

def _safe_eval(expr, ctx):
    allowed = {
        "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "sqrt": math.sqrt, "abs": abs, "min": min, "max": max,
        "pow": pow, "round": round, "int": int, "float": float,
        "pi": math.pi, "e": math.e, "log": math.log, "log10": math.log10,
    }
    allowed.update(ctx)
    try:
        return eval(expr, {"__builtins__": {}}, allowed)
    except Exception:
        return 0

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
# ║  节点注册表                                                         ║
# ║  格式: "名称": ([输入端口], [输出端口])                               ║
# ║  扩展: 只需在这里添加一行并在 NODE_EVAL_FUNCS 中注册求值函数          ║
# ╚══════════════════════════════════════════════════════════════════════╝

NODE_DEFINITIONS = {
    # ── 输入 Input ──
    "Number":       ([], ["Value"]),
    "Integer":      ([], ["Value"]),
    "Boolean":      ([], ["Value"]),
    "String":       ([], ["Value"]),
    "Slider":       ([], ["Value"]),
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

NODE_EVAL_FUNCS = {
    # Input (widget value → output)
    "Number":       lambda i, w: {"Value": w if w is not None else 0.0},
    "Integer":      lambda i, w: {"Value": int(w) if w is not None else 0},
    "Boolean":      lambda i, w: {"Value": bool(w) if w is not None else False},
    "String":       lambda i, w: {"Value": w if w is not None else ""},
    "Slider":       lambda i, w: {"Value": w if w is not None else 50},
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

NODE_CATEGORIES = {
    "输入":   ["Number", "Integer", "Boolean", "String", "Slider"],
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

CATEGORY_COLORS = {
    "输入": QColor(83, 148, 80),
    "输出": QColor(180, 80, 80),
    "数学": QColor(100, 130, 180),
    "逻辑": QColor(170, 130, 80),
    "文本": QColor(140, 110, 170),
    "列表": QColor(80, 160, 160),
    "控制": QColor(190, 180, 60),
    "转换": QColor(160, 120, 100),
    "工具": QColor(110, 110, 140),
}

_NODE_TO_CAT = {}
for _c, _ns in NODE_CATEGORIES.items():
    for _n_ in _ns:
        _NODE_TO_CAT[_n_] = _c

# 嵌入控件的节点样式
NODE_WIDGET_QSS = """
    QDoubleSpinBox, QSpinBox {
        background:#1a1a1a; color:#ddd; border:1px solid #555;
        border-radius:2px; padding:1px 3px; font-size:10px;
    }
    QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
    QSpinBox::up-button, QSpinBox::down-button {
        width:14px; background:#333; border:1px solid #555;
    }
    QLineEdit {
        background:#1a1a1a; color:#ddd; border:1px solid #555;
        border-radius:2px; padding:2px 4px; font-size:10px;
    }
    QCheckBox { color:#ddd; spacing:4px; font-size:10px; }
    QCheckBox::indicator {
        width:14px; height:14px; border:1px solid #666;
        border-radius:2px; background:#1a1a1a;
    }
    QCheckBox::indicator:checked { background:#2a82da; }
    QSlider::groove:horizontal {
        height:4px; background:#444; border-radius:2px;
    }
    QSlider::handle:horizontal {
        width:12px; height:12px; margin:-4px 0;
        background:#2a82da; border-radius:6px;
    }
    QLabel#nodeDisplay {
        color:#ccc; background:#1a1a1a; border:1px solid #444;
        border-radius:2px; padding:2px 4px; font-size:10px;
    }
    QWidget#sliderContainer { background:transparent; }
    QLabel#sliderVal {
        color:#aaa; background:transparent; border:none;
        font-size:9px; min-width:28px;
    }
"""


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  CollapsibleBox (pysideui.txt)                                      ║
# ╚══════════════════════════════════════════════════════════════════════╝

class CollapsibleBox(QWidget):
    def __init__(self, title="", parent=None, duration=250):
        super().__init__(parent)
        self._title = title
        self.toggle_button = QPushButton()
        f = self.toggle_button.font(); f.setBold(True)
        self.toggle_button.setFont(f)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(False)
        self.content_area = QFrame()
        self.content_area.setFrameShape(QFrame.StyledPanel)
        self.content_area.setMaximumHeight(0)
        self.content_area.setMinimumHeight(0)
        self.anim = QPropertyAnimation(self.content_area, b"maximumHeight")
        self.anim.setDuration(duration)
        self.anim.setEasingCurve(QEasingCurve.InOutCubic)
        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0)
        lay.addWidget(self.toggle_button); lay.addWidget(self.content_area)
        self.toggle_button.clicked.connect(self._on_toggled)
        self._update_arrow(False)

    def setContentLayout(self, layout):
        old = self.content_area.layout()
        if old:
            while old.count():
                it = old.takeAt(0); w = it.widget()
                if w: w.setParent(None)
        self.content_area.setLayout(layout)
        self.content_area.setMaximumHeight(0)

    def _on_toggled(self, checked):
        self._update_arrow(checked)
        h = self.content_area.layout().sizeHint().height() if self.content_area.layout() else 0
        self.anim.stop()
        self.anim.setStartValue(self.content_area.maximumHeight())
        self.anim.setEndValue(h if checked else 0)
        self.anim.start()

    def _update_arrow(self, ex):
        self.toggle_button.setText(("▼ " if ex else "► ") + self._title)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  NodeEdge — 贝塞尔连线                                              ║
# ╚══════════════════════════════════════════════════════════════════════╝

class NodeEdge(QGraphicsPathItem):
    def __init__(self, source_socket=None, dest_socket=None):
        super().__init__()
        self.source_socket = source_socket   # 始终为 output 端口
        self.dest_socket = dest_socket       # 始终为 input 端口
        self.source_pos = QPointF()
        self.dest_pos = QPointF()
        self.setZValue(-1)
        self._pen_default  = QPen(QColor(170,170,170,220), 2.0, cap=Qt.RoundCap)
        self._pen_selected = QPen(QColor(255,200,50,255), 2.5, cap=Qt.RoundCap)
        self._pen_drag     = QPen(QColor(255,255,255,140), 2.0, Qt.DashLine, cap=Qt.RoundCap)
        self.setFlags(QGraphicsItem.ItemIsSelectable)

    def update_positions(self):
        if self.source_socket:
            self.source_pos = self.source_socket.scenePos()
        if self.dest_socket:
            self.dest_pos = self.dest_socket.scenePos()
        self._rebuild()

    def _rebuild(self):
        p = QPainterPath(); p.moveTo(self.source_pos)
        dx = abs(self.dest_pos.x() - self.source_pos.x())
        d = max(dx * 0.5, 60)
        p.cubicTo(QPointF(self.source_pos.x()+d, self.source_pos.y()),
                  QPointF(self.dest_pos.x()-d, self.dest_pos.y()),
                  self.dest_pos)
        self.setPath(p)

    def paint(self, painter, option, widget=None):
        if self.dest_socket is None:
            self.setPen(self._pen_drag)
        elif self.isSelected():
            self.setPen(self._pen_selected)
        else:
            self.setPen(self._pen_default)
        super().paint(painter, option, widget)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  NodeSocket — 半圆贴边端口                                          ║
# ╚══════════════════════════════════════════════════════════════════════╝

class NodeSocket(QGraphicsItem):
    R = 6
    SPACING = 22
    Y0 = 34             # 第一个端口 Y 偏移

    def __init__(self, node, is_input, name, index):
        super().__init__(node)
        self.node = node
        self.is_input = is_input
        self.name = name
        self.index = index
        self.edges = []
        self.value = None       # ← 端口携带的数据

        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemSendsScenePositionChanges)
        self.setZValue(2)                # 确保 socket 始终在 proxy/node 之上
        y = self.Y0 + index * self.SPACING
        self.setPos(0 if is_input else node.width, y)

    # ── 绘制 (半圆) ─────────────────────────────────────────────────
    HIT_R = 12          # 点击检测半径 (比视觉半径 R=6 大一倍，更容易命中)

    def boundingRect(self):
        hr = self.HIT_R
        return QRectF(-hr, -hr, hr * 2, hr * 2)

    def shape(self):
        p = QPainterPath()
        p.addEllipse(QRectF(-self.HIT_R, -self.HIT_R, self.HIT_R * 2, self.HIT_R * 2))
        return p

    def paint(self, painter, option, widget=None):
        r = self.R
        hl = QApplication.palette().color(QPalette.Highlight)
        border = QColor(140,140,140)
        connected = len(self.edges) > 0

        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        rect = QRectF(-r, -r, r*2, r*2)
        if self.is_input:
            path.moveTo(0, -r); path.arcTo(rect, 90, 180); path.closeSubpath()
        else:
            path.moveTo(0, r); path.arcTo(rect, 270, 180); path.closeSubpath()

        painter.setBrush(QBrush(hl) if (connected or self.isUnderMouse()) else Qt.NoBrush)
        painter.setPen(QPen(hl if connected else border, 1.5))
        painter.drawPath(path)

    # ── edge 管理 ────────────────────────────────────────────────────
    def add_edge(self, e):  self.edges.append(e); self.update()
    def remove_edge(self, e):
        if e in self.edges: self.edges.remove(e)
        self.update()

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemScenePositionHasChanged:
            for e in self.edges: e.update_positions()
        return super().itemChange(change, value)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  NodeItem — 节点面板 + 嵌入式控件 + 求值引擎                        ║
# ╚══════════════════════════════════════════════════════════════════════╝

class NodeItem(QGraphicsItem):
    def __init__(self, title="Node", category=""):
        super().__init__()
        self.title = title
        self.category = category
        self.width = 160
        self.title_h = 26
        self.height = 60
        self.inputs  = []
        self.outputs = []
        self.title_color = CATEGORY_COLORS.get(category, QColor(70,70,70))

        self._proxy = None          # QGraphicsProxyWidget
        self._widget = None         # 嵌入的 QWidget
        self._display_label = None  # 用于 Viewer / Print 显示
        self._embedded_h = 0

        self.setFlags(
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemSendsGeometryChanges
        )

    # ── 端口 ─────────────────────────────────────────────────────────
    def add_input(self, name):
        s = NodeSocket(self, True, name, len(self.inputs))
        self.inputs.append(s); self._recalc(); return s

    def add_output(self, name):
        s = NodeSocket(self, False, name, len(self.outputs))
        self.outputs.append(s); self._recalc(); return s

    def _recalc(self):
        n = max(len(self.inputs), len(self.outputs), 1)
        self.height = self.title_h + n * NodeSocket.SPACING + 8 + self._embedded_h
        self.prepareGeometryChange()

    # ── 嵌入控件 ─────────────────────────────────────────────────────
    def setup_widget(self):
        """根据节点类型设置嵌入式控件，在添加端口之后调用。"""
        w = None
        h = 24

        if self.title == "Number":
            w = QDoubleSpinBox()
            w.setRange(-1e9, 1e9); w.setDecimals(4); w.setValue(0.0)
            w.setButtonSymbols(QDoubleSpinBox.NoButtons)
            w.valueChanged.connect(self._on_widget_changed)

        elif self.title == "Integer":
            w = QSpinBox()
            w.setRange(-999999999, 999999999); w.setValue(0)
            w.setButtonSymbols(QSpinBox.NoButtons)
            w.valueChanged.connect(self._on_widget_changed)

        elif self.title == "Boolean":
            w = QCheckBox("True / False")
            w.setChecked(False)
            w.toggled.connect(self._on_widget_changed)

        elif self.title == "String":
            w = QLineEdit(); w.setPlaceholderText("输入文本…")
            w.textChanged.connect(self._on_widget_changed)

        elif self.title == "Slider":
            container = QWidget(); container.setObjectName("sliderContainer")
            hl = QHBoxLayout(container); hl.setContentsMargins(0,0,0,0); hl.setSpacing(4)
            sl = QSlider(Qt.Horizontal); sl.setRange(0, 100); sl.setValue(50)
            lbl = QLabel("50"); lbl.setObjectName("sliderVal")
            sl.valueChanged.connect(lambda v: lbl.setText(str(v)))
            sl.valueChanged.connect(self._on_widget_changed)
            hl.addWidget(sl); hl.addWidget(lbl)
            w = container; h = 20
            self._slider_ref = sl

        elif self.title == "Expression":
            w = QLineEdit(); w.setPlaceholderText("x + y"); w.setText("x + y")
            w.textChanged.connect(self._on_widget_changed)

        elif self.title in ("Viewer", "Print"):
            w = QLabel("—"); w.setObjectName("nodeDisplay")
            w.setAlignment(Qt.AlignCenter)
            self._display_label = w
            h = 22

        if w is None:
            return

        w.setStyleSheet(NODE_WIDGET_QSS)
        w.setFixedHeight(h)
        ww = self.width - 16
        w.setFixedWidth(ww)

        proxy = QGraphicsProxyWidget(self)
        proxy.setWidget(w)
        n_sockets = max(len(self.inputs), len(self.outputs), 1)
        wy = NodeSocket.Y0 + n_sockets * NodeSocket.SPACING + 2
        proxy.setPos(8, wy)

        self._proxy = proxy
        self._widget = w
        self._embedded_h = h + 8
        self._recalc()

        # 初始求值 (输入节点发出初始值)
        self.evaluate()

    def get_widget_value(self):
        w = self._widget
        if w is None: return None
        if isinstance(w, QDoubleSpinBox): return w.value()
        if isinstance(w, QSpinBox): return w.value()
        if isinstance(w, QCheckBox): return w.isChecked()
        if isinstance(w, QLineEdit): return w.text()
        if hasattr(self, '_slider_ref'): return self._slider_ref.value()
        return None

    def _on_widget_changed(self, _=None):
        self.evaluate()

    # ── 求值引擎 ─────────────────────────────────────────────────────
    def evaluate(self, _visited=None):
        if _visited is None: _visited = set()
        if id(self) in _visited: return   # 防环
        _visited.add(id(self))

        # 收集输入
        inv = {s.name: s.value for s in self.inputs}
        wv = self.get_widget_value()

        # 求值
        func = NODE_EVAL_FUNCS.get(self.title)
        if func:
            try:
                results = func(inv, wv)
            except Exception:
                results = {}
            for s in self.outputs:
                if s.name in results:
                    s.value = results[s.name]

        # 更新显示
        if self._display_label is not None:
            if self.title == "Viewer":
                d = inv.get("Data", "—")
                txt = str(d)
                self._display_label.setText(txt[:60] if len(txt) > 60 else txt)
            elif self.title == "Print":
                d = inv.get("Value", "")
                self._display_label.setText(str(d)[:60])
                sc = self.scene()
                if sc and hasattr(sc, 'main_window') and sc.main_window:
                    sc.main_window.log(f"► {d}")

        # 传播
        for s in self.outputs:
            for e in s.edges:
                if e.dest_socket:
                    e.dest_socket.value = s.value
                    e.dest_socket.node.evaluate(_visited)

    # ── 绘制 ─────────────────────────────────────────────────────────
    def boundingRect(self):
        pad = NodeSocket.R + 2
        return QRectF(-pad, 0, self.width + pad*2, self.height)

    def paint(self, painter, option, widget=None):
        hl = QApplication.palette().color(QPalette.Highlight)
        painter.setRenderHint(QPainter.Antialiasing)

        body = QRectF(0, 0, self.width, self.height)
        bp = QPainterPath(); bp.addRoundedRect(body, 6, 6)

        painter.setBrush(QBrush(QColor(38, 38, 38, 230)))
        bc = hl if self.isSelected() else QColor(80, 80, 80, 220)
        painter.setPen(QPen(bc, 2.0 if self.isSelected() else 1.2))
        painter.drawPath(bp)

        # 标题栏
        tr = QRectF(0, 0, self.width, self.title_h)
        tp = QPainterPath(); tp.addRoundedRect(tr, 6, 6)
        tp.addRect(0, self.title_h - 6, self.width, 6)
        painter.setBrush(QBrush(self.title_color))
        painter.setPen(Qt.NoPen)
        painter.drawPath(tp)

        font = painter.font()
        font.setBold(True); font.setPointSize(9); painter.setFont(font)
        painter.setPen(QPen(QColor(240,240,240)))
        painter.drawText(tr.adjusted(8,0,-8,0), Qt.AlignVCenter|Qt.AlignLeft, self.title)

        # 端口名
        font.setBold(False); font.setPointSize(8); painter.setFont(font)
        painter.setPen(QPen(QColor(200,200,200)))
        R = NodeSocket.R
        for s in self.inputs:
            r = QRectF(R+4, s.pos().y()-10, self.width/2-R, 20)
            painter.drawText(r, Qt.AlignLeft|Qt.AlignVCenter, s.name)
        for s in self.outputs:
            r = QRectF(self.width/2, s.pos().y()-10, self.width/2-R-4, 20)
            painter.drawText(r, Qt.AlignRight|Qt.AlignVCenter, s.name)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            for s in self.inputs + self.outputs:
                for e in s.edges: e.update_positions()
        return super().itemChange(change, value)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  NodeSearchPopup — 空格键快速搜索                                    ║
# ╚══════════════════════════════════════════════════════════════════════╝

class NodeSearchPopup(QDialog):
    node_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setFixedSize(260, 320)
        self.setStyleSheet("""
            QDialog{background:#2a2a2a;border:1px solid #555;border-radius:4px;}
            QLineEdit{background:#1e1e1e;color:#eee;border:1px solid #555;
                      border-radius:3px;padding:4px 6px;margin:4px;}
            QListWidget{background:#1e1e1e;color:#ddd;border:none;margin:0 4px 4px 4px;}
            QListWidget::item:selected{background:#2a82da;}
            QListWidget::item:hover{background:#3a3a3a;}
        """)
        l = QVBoxLayout(self); l.setContentsMargins(0,0,0,0); l.setSpacing(0)
        self.sb = QLineEdit(); self.sb.setPlaceholderText("搜索节点…")
        self.sb.textChanged.connect(self._filter)
        self.lw = QListWidget()
        self.lw.itemActivated.connect(self._accept)
        l.addWidget(self.sb); l.addWidget(self.lw)

        self._items = []
        for cat, ns in NODE_CATEGORIES.items():
            for n in ns:
                self._items.append((n, cat))
        self._items.sort(key=lambda x: x[0])
        for name, cat in self._items:
            self.lw.addItem(f"{name}  [{cat}]")
        self.sb.installEventFilter(self)

    def _filter(self, t):
        t = t.lower()
        for i, (n, c) in enumerate(self._items):
            self.lw.item(i).setHidden(t not in n.lower() and t not in c.lower())

    def _accept(self, item=None):
        if not item: item = self.lw.currentItem()
        if not item:
            for i in range(self.lw.count()):
                if not self.lw.item(i).isHidden(): item = self.lw.item(i); break
        if item:
            self.node_selected.emit(item.text().split("  [")[0])
        self.close()

    def eventFilter(self, o, ev):
        if o is self.sb and ev.type() == ev.Type.KeyPress:
            k = ev.key()
            if k in (Qt.Key_Up, Qt.Key_Down):
                self.lw.setFocus()
                if self.lw.currentRow() < 0: self.lw.setCurrentRow(0)
                QApplication.sendEvent(self.lw, ev); return True
            if k in (Qt.Key_Return, Qt.Key_Enter): self._accept(); return True
            if k == Qt.Key_Escape: self.close(); return True
        return super().eventFilter(o, ev)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  NodeScene — 网格背景                                               ║
# ╚══════════════════════════════════════════════════════════════════════╝

class NodeScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSceneRect(-5000, -5000, 10000, 10000)
        self.main_window = None

    def drawBackground(self, painter, rect):
        painter.setRenderHint(QPainter.Antialiasing, False)
        sm, lg = 20, 100
        l = int(math.floor(rect.left()/sm)*sm)
        r = int(math.ceil(rect.right()/sm)*sm)
        t = int(math.floor(rect.top()/sm)*sm)
        b = int(math.ceil(rect.bottom()/sm)*sm)
        sl, dl = [], []
        for x in range(l, r+1, sm):
            ln = QLineF(x, t, x, b)
            (dl if x % lg == 0 else sl).append(ln)
        for y in range(t, b+1, sm):
            ln = QLineF(l, y, r, y)
            (dl if y % lg == 0 else sl).append(ln)
        painter.setPen(QPen(QColor(50,50,50,60), 1)); painter.drawLines(sl)
        painter.setPen(QPen(QColor(60,60,60,100), 1)); painter.drawLines(dl)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  NodeView — 画布视图                                                ║
# ╚══════════════════════════════════════════════════════════════════════╝

class NodeView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setStyleSheet("QGraphicsView{border:none;background:#1e1e1e;}")

        self._zoom = 0
        self._zoom_range = (-8, 12)
        self._zf = 1.15
        self._cur_edge = None
        self._panning = False
        self._pan_pos = QPointF()

    # ── 键盘 ─────────────────────────────────────────────────────────
    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Space and not ev.isAutoRepeat():
            self._open_search(); ev.accept(); return
        if ev.key() == Qt.Key_Delete:
            self._del_selected(); ev.accept(); return
        super().keyPressEvent(ev)

    def _open_search(self):
        p = NodeSearchPopup(self)
        p.node_selected.connect(self._add_from_popup)
        cp = QCursor.pos(); p.move(cp); p.show(); p.sb.setFocus()
        self._popup_spos = self.mapToScene(self.mapFromGlobal(cp))

    def _add_from_popup(self, name):
        sc = self.scene()
        if sc and sc.main_window:
            sc.main_window.add_node(name, self._popup_spos)

    def _del_selected(self):
        for item in list(self.scene().selectedItems()):
            if isinstance(item, NodeEdge):
                if item.source_socket: item.source_socket.remove_edge(item)
                if item.dest_socket:   item.dest_socket.remove_edge(item)
                self.scene().removeItem(item)
            elif isinstance(item, NodeItem):
                for s in item.inputs + item.outputs:
                    for e in list(s.edges):
                        oth = e.dest_socket if e.source_socket is s else e.source_socket
                        if oth: oth.remove_edge(e)
                        s.remove_edge(e)
                        self.scene().removeItem(e)
                self.scene().removeItem(item)

    # ── 缩放 ─────────────────────────────────────────────────────────
    def wheelEvent(self, ev):
        if ev.angleDelta().y() > 0 and self._zoom < self._zoom_range[1]:
            self._zoom += 1; self.scale(self._zf, self._zf)
        elif ev.angleDelta().y() < 0 and self._zoom > self._zoom_range[0]:
            self._zoom -= 1; self.scale(1/self._zf, 1/self._zf)

    # ── 辅助：查找点击处的 NodeSocket ────────────────────────────────
    def _socket_at(self, vpos):
        """在视图坐标 vpos(QPoint) 处查找 NodeSocket (带容差)。"""
        # 1) 精确点击检测
        for item in self.items(vpos):
            if isinstance(item, NodeSocket):
                return item
        # 2) 容差矩形检测 (±10px)
        tol = 10
        from PySide6.QtCore import QRect
        rect = QRect(vpos.x() - tol, vpos.y() - tol, tol * 2, tol * 2)
        candidates = []
        scene_pt = self.mapToScene(vpos)
        for item in self.items(rect):
            if isinstance(item, NodeSocket):
                d = (item.scenePos() - scene_pt)
                dist = (d.x()**2 + d.y()**2) ** 0.5
                candidates.append((dist, item))
        if candidates:
            candidates.sort(key=lambda x: x[0])
            return candidates[0][1]
        return None

    def _log_error(self, where, text):
        """将错误输出到 UI 日志和 stderr/文件 (pyw 无控制台)。"""
        msg = f"⚠ ERROR in {where}:\n{text}"
        try:
            sc = self.scene()
            if sc and hasattr(sc, 'main_window') and sc.main_window:
                sc.main_window.log(msg[:300])
        except Exception:
            pass
        try:
            print(msg, file=sys.stderr)
        except Exception:
            pass

    # ── 鼠标 ─────────────────────────────────────────────────────────
    def mousePressEvent(self, ev):
        try:
            if ev.button() == Qt.MiddleButton or (ev.button() == Qt.LeftButton and ev.modifiers() & Qt.AltModifier):
                self._panning = True; self._pan_pos = ev.position()
                self.setCursor(Qt.ClosedHandCursor); ev.accept(); return

            if ev.button() == Qt.LeftButton:
                vp = ev.position().toPoint()
                sock = self._socket_at(vp)
                if sock is not None:
                    self.setDragMode(QGraphicsView.NoDrag)   # 禁用 rubber band
                    edge = NodeEdge()
                    edge._drag_origin = sock
                    edge.source_pos = sock.scenePos()
                    edge.dest_pos = self.mapToScene(vp)
                    self.scene().addItem(edge)
                    edge._rebuild()
                    self._cur_edge = edge
                    ev.accept(); return
        except Exception:
            self._log_error("mousePressEvent", traceback.format_exc())
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        try:
            if self._panning:
                d = ev.position() - self._pan_pos
                self.horizontalScrollBar().setValue(int(self.horizontalScrollBar().value()-d.x()))
                self.verticalScrollBar().setValue(int(self.verticalScrollBar().value()-d.y()))
                self._pan_pos = ev.position(); ev.accept(); return
            if self._cur_edge:
                self._cur_edge.dest_pos = self.mapToScene(ev.position().toPoint())
                self._cur_edge._rebuild(); ev.accept(); return
        except Exception:
            self._log_error("mouseMoveEvent", traceback.format_exc())
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        try:
            if self._panning and ev.button() in (Qt.MiddleButton, Qt.LeftButton):
                self._panning = False; self.setCursor(Qt.ArrowCursor); ev.accept(); return

            if self._cur_edge:
                edge = self._cur_edge
                self._cur_edge = None
                origin = edge._drag_origin
                target = self._socket_at(ev.position().toPoint())

                if isinstance(target, NodeSocket) and target is not origin and target.is_input != origin.is_input:
                    # 规范化: source=output, dest=input
                    out_s = origin if not origin.is_input else target
                    in_s  = target if target.is_input else origin

                    edge.source_socket = out_s
                    edge.dest_socket   = in_s
                    out_s.add_edge(edge)
                    in_s.add_edge(edge)
                    edge.update_positions()

                    # 传值并求值
                    in_s.value = out_s.value
                    in_s.node.evaluate()

                    # 在 UI 日志中确认
                    sc = self.scene()
                    if sc and hasattr(sc, 'main_window') and sc.main_window:
                        sc.main_window.log(
                            f"🔗 {out_s.node.title}.{out_s.name} → {in_s.node.title}.{in_s.name}"
                        )
                else:
                    self.scene().removeItem(edge)

                self.setDragMode(QGraphicsView.RubberBandDrag)  # 恢复 rubber band
                ev.accept(); return
        except Exception:
            self._log_error("mouseReleaseEvent", traceback.format_exc())
            self.setDragMode(QGraphicsView.RubberBandDrag)
        super().mouseReleaseEvent(ev)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  NodeEditorWindow — 主窗口                                          ║
# ╚══════════════════════════════════════════════════════════════════════╝

class NodeEditorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AYE Node Editor")
        self.resize(1400, 850)

        central = QWidget(); self.setCentralWidget(central)
        root = QHBoxLayout(central); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal); root.addWidget(splitter)

        # ── 左侧面板 ────────────────────────────────────────────────
        left = QWidget()
        ll = QVBoxLayout(left); ll.setContentsMargins(4,4,4,4); ll.setSpacing(4)

        # 状态行
        hl = QHBoxLayout()
        self.infoLabel = QLabel("就绪 | Space=搜索 Del=删除")
        self.infoLabel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.execBtn = QPushButton("全部求值")
        self.execBtn.clicked.connect(self._eval_all)
        hl.addWidget(self.infoLabel, 1); hl.addWidget(self.execBtn)
        ll.addLayout(hl)

        # ── 多标签节点库 ─────────────────────────────────────────────
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.North)
        self.tabs.setDocumentMode(True)

        for cat, nodes in NODE_CATEGORIES.items():
            lw = QListWidget()
            lw.addItems(nodes)
            lw.itemDoubleClicked.connect(self._on_list_dbl)
            self.tabs.addTab(lw, cat)

        ll.addWidget(self.tabs)

        # 属性面板
        self.propsBox = CollapsibleBox("属性")
        self.propsBox.toggle_button.setChecked(True)
        pg = QGridLayout(); pg.setContentsMargins(6,6,6,6)
        self.propLabel = QLabel("选择节点以查看属性")
        pg.addWidget(self.propLabel, 0, 0)
        self.propsBox.setContentLayout(pg)
        ll.addWidget(self.propsBox)

        # 日志
        self.logView = QTextEdit(); self.logView.setReadOnly(True)
        self.logView.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.logView.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        ll.addWidget(self.logView, 1)

        # ── 右侧画布 ────────────────────────────────────────────────
        self.scene = NodeScene(); self.scene.main_window = self
        self.view = NodeView(self.scene)

        splitter.addWidget(left); splitter.addWidget(self.view)
        splitter.setSizes([320, 1080])

        self.log("节点编辑器已启动。")
        self.log(f"注册 {len(NODE_DEFINITIONS)} 个可执行节点  |  {len(NODE_CATEGORIES)} 个类别")
        self.log("Space=搜索  双击列表=添加  Delete=删除  中键=平移  滚轮=缩放")
        self.log("连线后数据自动流转，修改输入节点控件即可看到结果传播。")

    def _on_list_dbl(self, item):
        self.add_node(item.text())

    def add_node(self, title, pos=None):
        if title not in NODE_DEFINITIONS:
            self.log(f"⚠ 未知: {title}"); return
        ins, outs = NODE_DEFINITIONS[title]
        cat = _NODE_TO_CAT.get(title, "")
        node = NodeItem(title, cat)
        for n in ins:  node.add_input(n)
        for n in outs: node.add_output(n)
        node.setup_widget()

        if pos is None:
            c = self.view.viewport().rect().center()
            pos = self.view.mapToScene(c)
        node.setPos(pos)
        self.scene.addItem(node)
        self.log(f"+ {title}")

    def _eval_all(self):
        """手动触发所有无输入端口的源节点求值，刷新整个图。"""
        for item in self.scene.items():
            if isinstance(item, NodeItem) and not item.inputs:
                item.evaluate()
        self.log("✓ 全部求值完成")

    def log(self, msg):
        self.logView.append(f'<div style="white-space:pre;">{msg}</div>')


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  入口                                                               ║
# ╚══════════════════════════════════════════════════════════════════════╝

if __name__ == "__main__":
    # .pyw 无控制台，将 stderr 重定向到日志文件以便调试
    _log_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        sys.stderr = open(os.path.join(_log_dir, "_node_editor_errors.log"), "w", encoding="utf-8")
    except Exception:
        pass

    app = QApplication(sys.argv)

    p = QPalette()
    p.setColor(QPalette.Window,          QColor(45,45,45))
    p.setColor(QPalette.WindowText,      Qt.white)
    p.setColor(QPalette.Base,            QColor(30,30,30))
    p.setColor(QPalette.AlternateBase,   QColor(50,50,50))
    p.setColor(QPalette.ToolTipBase,     QColor(25,25,25))
    p.setColor(QPalette.ToolTipText,     Qt.white)
    p.setColor(QPalette.Text,            QColor(220,220,220))
    p.setColor(QPalette.Button,          QColor(53,53,53))
    p.setColor(QPalette.ButtonText,      Qt.white)
    p.setColor(QPalette.BrightText,      Qt.red)
    p.setColor(QPalette.Link,            QColor(42,130,218))
    p.setColor(QPalette.Highlight,       QColor(42,130,218))
    p.setColor(QPalette.HighlightedText, Qt.black)
    p.setColor(QPalette.Mid,             QColor(70,70,70))
    p.setColor(QPalette.Midlight,        QColor(90,90,90))
    app.setPalette(p)

    app.setStyleSheet("""
        QMainWindow{background:#2d2d2d;}
        QTabWidget::pane{border:1px solid #444;border-top:none;background:#1e1e1e;}
        QTabBar::tab{background:#2d2d2d;color:#999;padding:4px 6px;margin-right:1px;
                     border:1px solid #444;border-bottom:none;border-radius:3px 3px 0 0;font-size:11px;}
        QTabBar::tab:selected{background:#1e1e1e;color:#ddd;}
        QTabBar::tab:hover{background:#3a3a3a;color:#ccc;}
        QListWidget{background:#1e1e1e;color:#ddd;border:none;font-size:12px;}
        QListWidget::item:hover{background:#333;}
        QListWidget::item:selected{background:#2a82da;}
        QTextEdit{background:#1a1a1a;color:#bbb;border:none;font-size:11px;}
        QPushButton{background:#3a3a3a;color:#ddd;border:1px solid #555;
                    border-radius:3px;padding:4px 10px;}
        QPushButton:hover{background:#454545;}
        QPushButton:pressed{background:#2a82da;}
        QLabel{color:#aaa;font-size:11px;}
        QSplitter::handle{background:#333;width:3px;}
    """)

    win = NodeEditorWindow()
    win.show()
    sys.exit(app.exec())
