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
    QDialog, QScrollBar, QFormLayout, QDialogButtonBox, QComboBox,
)
from PySide6.QtCore import (
    Qt, QRectF, QPointF, QPropertyAnimation, QEasingCurve,
    Signal, QLineF,
)
from PySide6.QtGui import (
    QColor, QPen, QBrush, QPainterPath, QFontDatabase, QPalette,
    QPainter, QCursor,
)

# ── 节点注册表（自动加载 node_defs/*_nodes.py）─────────────────────────
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

from node_defs import (
    NODE_DEFINITIONS,
    NODE_EVAL_FUNCS,
    NODE_CATEGORIES,
    CATEGORY_COLORS_RGB as _COLORS_RGB,
    _NODE_TO_CAT,
    register_pack,         # 供外部程序动态注册节点使用
)

CATEGORY_COLORS = {k: QColor(*v) for k, v in _COLORS_RGB.items()}

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
        self.toggle_button.setText((("▼ " if ex else "► ") + self._title))


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  DragNumberWidget — GH 风格可拖拽数值控件                           ║
# ╚══════════════════════════════════════════════════════════════════════╝

class NumSliderSettingsDialog(QDialog):
    """
    GH 风格 Slider 详细设置对话框。
    """
    _QSS = """
        QDialog { background:#252525; }
        QLabel  { color:#bbb; font-size:11px; }
        QDoubleSpinBox, QSpinBox {
            background:#1a1a1a; color:#ddd; border:1px solid #555;
            border-radius:3px; padding:2px 6px; font-size:11px;
            min-width:90px;
        }
        QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
        QSpinBox::up-button,       QSpinBox::down-button {
            width:16px; background:#333; border:1px solid #555;
        }
        QPushButton {
            background:#3a3a3a; color:#ddd; border:1px solid #555;
            border-radius:3px; padding:4px 14px; font-size:11px;
        }
        QPushButton:hover   { background:#4a4a4a; }
        QPushButton:pressed { background:#2a82da; }
        QLabel#hint {
            color:#666; font-size:9px;
        }
    """

    def __init__(self, parent, value, min_val, max_val, decimals, step):
        super().__init__(parent)
        self.setWindowTitle("Num Slider 设置")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setStyleSheet(self._QSS)
        self.setFixedWidth(300)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 10)
        lay.setSpacing(10)

        title = QLabel("<b>Num Slider 详细设置</b>")
        title.setStyleSheet("color:#2a82da;font-size:13px;")
        lay.addWidget(title)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(6)

        def _dspin(lo, hi, dec, val):
            sb = QDoubleSpinBox()
            sb.setRange(lo, hi); sb.setDecimals(dec); sb.setValue(val)
            sb.setButtonSymbols(QDoubleSpinBox.UpDownArrows)
            return sb

        self.sb_min  = _dspin(-1e9, 1e9, 6, min_val)
        self.sb_max  = _dspin(-1e9, 1e9, 6, max_val)
        self.sb_val  = _dspin(-1e9, 1e9, 6, value)
        self.sb_step = _dspin(0,    1e9, 6, step)

        self.sp_dec = QSpinBox()
        self.sp_dec.setRange(0, 10); self.sp_dec.setValue(decimals)
        self.sp_dec.setButtonSymbols(QSpinBox.UpDownArrows)

        form.addRow("最小值 (Min)",  self.sb_min)
        form.addRow("最大値 (Max)",  self.sb_max)
        form.addRow("当前値",       self.sb_val)
        form.addRow("最小步进 (Step)", self.sb_step)
        form.addRow("小数位 (Decimals)", self.sp_dec)
        lay.addLayout(form)

        # 快速输入提示
        hint = QLabel(
            "快捷输入: 在拖拽条双击后输入\n"
            "  .1 → 整数 (step=1, dec=0)　　.01 → 1位小数\n"
            "  .0···1 → N位小数 (N个零后加一个非零数字)"
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.setStyleSheet("")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def result_values(self):
        lo  = self.sb_min.value()
        hi  = self.sb_max.value()
        if lo >= hi: hi = lo + 1
        return (
            self.sb_val.value(),
            lo, hi,
            self.sp_dec.value(),
            self.sb_step.value(),
        )


class DragNumberWidget(QWidget):
    """
    Grasshopper Number Slider 风格数值控件。

    拖动操作
    ────────
    · 左右拖动          — 改变数值，每步对齐到 step
    · Ctrl  + 拖             — 精细 (×0.1)
    · Shift + 拖             — 粗调 (×10)

    键盘输入 (双击后弹出 overlay)
    ────────────────────────
    · 直接输入数字         — 设置宽定数値
    · .1                  — step=1,  dec=0 (整数)
    · .01                 — step=0.1, dec=1
    · .001                — step=0.01, dec=2  … 以此类推
    · (小数点后 N 个零尾随一个非零数字 = N 位小数精度)

    双击标题栏按鈕 — 开启详细设置对话框
    ────────────────────────
    Min / Max / 当前値 / 最小步进 / 小数位
    """
    valueChanged = Signal(float)

    # 拖动每象素对应的 scene 单位中，拖多少像素改变多少幅度
    _PIXELS_PER_UNIT = 4      # 每 4px 运动改变 1*step

    def __init__(self, value=0.0, min_val=0.0, max_val=10.0,
                 decimals=2, step=0.01, parent=None):
        super().__init__(parent)
        self._value    = float(value)
        self._min      = float(min_val)
        self._max      = float(max_val)
        self._decimals = int(decimals)     # 显示小数位
        self._step     = float(step)       # 拖动对齐单位

        self._drag_x  = None
        self._drag_v0 = 0.0
        self._editing = False              # overlay 是否显示中

        self.setCursor(Qt.SizeHorCursor)
        self.setFixedHeight(28)
        self.setMinimumWidth(160)

        # 精确输入 overlay
        self._edit = QLineEdit(self)
        self._edit.setAlignment(Qt.AlignCenter)
        self._edit.setStyleSheet(
            "background:#111;color:#eee;border:1px solid #2a82da;"
            "border-radius:3px;font-size:11px;padding:0;")
        self._edit.hide()
        self._edit.installEventFilter(self)
        self._edit.returnPressed.connect(self._commit)

    # ── 公开接口 ─────────────────────────────────────────────────────
    def value(self):    return self._value
    def minimum(self):  return self._min
    def maximum(self):  return self._max
    def decimals(self): return self._decimals
    def step(self):     return self._step

    def setValue(self, v):
        if self._step > 0:
            import math as _m
            v = round(round(v / self._step) * self._step, 12)
        v = max(self._min, min(self._max, float(v)))
        # 小数拆舍对齐
        v = round(v, self._decimals)
        changed = (v != self._value)
        self._value = v
        self.update()
        if changed:
            self.valueChanged.emit(self._value)

    def configure(self, value, min_val, max_val, decimals, step):
        """一次性设置五个参数，只发一次 valueChanged。"""
        self._min      = float(min_val)
        self._max      = float(max_val)
        self._decimals = max(0, int(decimals))
        self._step     = max(0.0, float(step))
        self.setValue(value)

    # ── 绘制 ─────────────────────────────────────────────────────────
    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect())

        bg = QPainterPath(); bg.addRoundedRect(r, 4, 4)
        p.setBrush(QColor(22, 22, 22)); p.setPen(Qt.NoPen)
        p.drawPath(bg)

        span = self._max - self._min
        ratio = (self._value - self._min) / span if span else 0.0
        ratio = max(0.0, min(1.0, ratio))
        fill_w = ratio * r.width()
        if fill_w > 0.5:
            fill_rect = QRectF(0, 0, fill_w, r.height())
            fp = QPainterPath(); fp.addRoundedRect(fill_rect, 4, 4)
            if ratio < 1.0:
                clip = QPainterPath()
                clip.addRect(QRectF(0, 0, fill_w, r.height()))
                fp = fp.intersected(clip)
            p.setBrush(QColor(36, 106, 170, 210)); p.setPen(Qt.NoPen)
            p.drawPath(fp)

        # 零点线
        if span and self._min < 0 < self._max:
            zx = (-self._min / span) * r.width()
            p.setPen(QPen(QColor(255, 255, 255, 50), 1))
            p.drawLine(QPointF(zx, 2), QPointF(zx, r.height() - 2))

        # tick 刻度（每 10% 一条小刻度）
        p.setPen(QPen(QColor(80, 80, 80, 120), 1))
        for i in range(1, 10):
            tx = r.width() * i / 10
            p.drawLine(QPointF(tx, r.height()-4), QPointF(tx, r.height()-1))

        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(65, 65, 65), 1))
        p.drawPath(bg)

        # 主数値
        fmt = f"{{:.{self._decimals}f}}"
        val_txt = fmt.format(self._value)
        font = self.font(); font.setPointSize(10); font.setBold(True)
        p.setFont(font); p.setPen(QColor(235, 235, 235))
        p.drawText(self.rect(), Qt.AlignCenter, val_txt)

        # min / max 角落小字
        font.setBold(False); font.setPointSize(7); p.setFont(font)
        p.setPen(QColor(100, 100, 100))
        mn = fmt.format(self._min); mx = fmt.format(self._max)
        p.drawText(QRectF(4, 0, 55, r.height()), Qt.AlignVCenter|Qt.AlignLeft,  mn)
        p.drawText(QRectF(r.width()-59, 0, 55, r.height()), Qt.AlignVCenter|Qt.AlignRight, mx)

        # step 小标记（右下角）
        step_txt = f"±{self._step:.{self._decimals}f}"
        font.setPointSize(6); p.setFont(font)
        p.setPen(QColor(80, 80, 80))
        p.drawText(QRectF(0, r.height()-13, r.width()-4, 13),
                   Qt.AlignVCenter|Qt.AlignRight, step_txt)

    # ── 鼠标 ─────────────────────────────────────────────────────────
    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton and not self._editing:
            self._drag_x  = ev.position().x()
            self._drag_v0 = self._value
        ev.accept()

    def mouseMoveEvent(self, ev):
        if self._drag_x is not None and not self._editing:
            dx    = ev.position().x() - self._drag_x
            step  = self._step if self._step > 0 else 0.01
            if ev.modifiers() & Qt.ControlModifier:
                step *= 0.1
            elif ev.modifiers() & Qt.ShiftModifier:
                step *= 10.0
            # dx / _PIXELS_PER_UNIT ≈ 步数
            n_steps = dx / self._PIXELS_PER_UNIT
            self.setValue(self._drag_v0 + n_steps * step)
        ev.accept()

    def mouseReleaseEvent(self, ev):
        self._drag_x = None
        ev.accept()

    def mouseDoubleClickEvent(self, ev):
        """*双击拖拽条* 开启详细设置对话框。"""
        self._open_settings_dialog()
        ev.accept()

    # ── overlay 输入框 ──────────────────────────────────────────────
    def open_inline_edit(self):
        """在拖拽条内显示输入框。"""
        self._editing = True
        self._edit.setGeometry(self.rect())
        self._edit.setText(f"{self._value:.{self._decimals}f}")
        self._edit.selectAll()
        self._edit.show(); self._edit.setFocus()

    def eventFilter(self, obj, ev):
        if obj is self._edit and ev.type() == ev.Type.KeyPress:
            if ev.key() == Qt.Key_Escape:
                self._edit.hide(); self._editing = False; return True
        return super().eventFilter(obj, ev)

    def _commit(self):
        txt = self._edit.text().strip()
        self._edit.hide(); self._editing = False

        # 快捷语法: ".XXX" — 小数点后全是零尾随一个 1（可选）
        # .1    → step=1,     dec=0
        # .01   → step=0.1,   dec=1
        # .001  → step=0.01,  dec=2
        # .0001 → step=0.001, dec=3
        import re
        m = re.fullmatch(r"\.(0*)(\d?)", txt)
        if m:
            zeros = len(m.group(1))
            # dec = zeros 个零后的一位小数→ zeros 位小数
            dec  = zeros
            step = 10 ** (-zeros)   # .1→1, .01→0.1, .001→0.01 …
            self._decimals = dec
            self._step     = step
            self.update()
            self.valueChanged.emit(self._value)
            return

        try:
            self.setValue(float(txt))
        except ValueError:
            pass

    # ── 详细设置对话框 ────────────────────────────────────────────
    def _open_settings_dialog(self):
        dlg = NumSliderSettingsDialog(
            self,
            value    = self._value,
            min_val  = self._min,
            max_val  = self._max,
            decimals = self._decimals,
            step     = self._step,
        )
        dlg.move(self.mapToGlobal(QPointF(0, self.height()).toPoint()))
        if dlg.exec() == QDialog.Accepted:
            v, lo, hi, dec, step = dlg.result_values()
            self.configure(v, lo, hi, dec, step)

    def resizeEvent(self, ev):
        self._edit.setGeometry(self.rect())




# ╔══════════════════════════════════════════════════════════════════════╗
# ║  SceneSlider — 修复 QGraphicsProxyWidget 中 QSlider 位置不同步      ║
# ║  QSlider handle 位置依赖 QStyle::subControlRect，在 QGraphicsView    ║
# ║  缩放/平移时坐标计算失准。子类直接从鼠标 X 位置线性映射值，彻底修复。  ║
# ╚══════════════════════════════════════════════════════════════════════╝

class SceneSlider(QSlider):
    """直接从鼠标 X 坐标线性计算值，与视图缩放/平移无关。"""

    def _x_to_value(self, x: float) -> int:
        w = self.width()
        if w <= 0:
            return self.minimum()
        ratio = max(0.0, min(1.0, x / w))
        return round(self.minimum() + ratio * (self.maximum() - self.minimum()))

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self.setValue(self._x_to_value(ev.position().x()))
            ev.accept()
        else:
            super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if ev.buttons() & Qt.LeftButton:
            self.setValue(self._x_to_value(ev.position().x()))
            ev.accept()
        else:
            super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        ev.accept()

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
        self._pen_default  = QPen(QColor(170,170,170,220), 2.0, Qt.SolidLine, Qt.RoundCap)
        self._pen_selected = QPen(QColor(255,200,50,255), 2.5, Qt.SolidLine, Qt.RoundCap)
        self._pen_drag     = QPen(QColor(255,255,255,140), 2.0, Qt.DashLine,  Qt.RoundCap)
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
            sl = SceneSlider(Qt.Horizontal); sl.setRange(0, 100); sl.setValue(50)
            lbl = QLabel("50"); lbl.setObjectName("sliderVal")
            sl.valueChanged.connect(lambda v: lbl.setText(str(v)))
            sl.valueChanged.connect(self._on_widget_changed)
            hl.addWidget(sl); hl.addWidget(lbl)
            w = container; h = 20
            self._slider_ref = sl

        elif self.title == "Num Slider":
            # 加宽节点以便拖拽控件有足够空间
            self.width = 220
            for s in self.outputs:          # 同步 output socket x 位置
                s.setPos(self.width, s.pos().y())

            # 外包容器：拖拽条 + 设置按鈕
            container = QWidget()
            container.setObjectName("sliderContainer")
            vl = QVBoxLayout(container)
            vl.setContentsMargins(0, 0, 0, 0); vl.setSpacing(2)

            dw = DragNumberWidget(value=0.0, min_val=0.0, max_val=10.0,
                                  decimals=2, step=0.01)
            dw.valueChanged.connect(self._on_widget_changed)
            vl.addWidget(dw)

            btn = QPushButton("⚙ 设置")
            btn.setFixedHeight(18)
            btn.setStyleSheet(
                "QPushButton{background:#2a2a2a;color:#888;border:1px solid #444;"
                "border-radius:2px;font-size:9px;padding:0 4px;}"
                "QPushButton:hover{background:#3a3a3a;color:#bbb;}"
                "QPushButton:pressed{background:#2a82da;color:#fff;}")
            btn.clicked.connect(lambda: dw._open_settings_dialog())
            vl.addWidget(btn)

            self._drag_number_widget = dw
            w = container
            h = 28 + 20   # 拖拽条 + 按鈕

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

        ww = self.width - 16
        # Num Slider 容器不套用全局 QSS（内部已有独立样式）
        if self.title != "Num Slider":
            w.setStyleSheet(NODE_WIDGET_QSS)
        w.setFixedHeight(h)
        w.setFixedWidth(ww)
        # 同步内部 DragNumberWidget 宽度
        if hasattr(self, '_drag_number_widget'):
            self._drag_number_widget.setFixedWidth(ww)

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
        if isinstance(w, DragNumberWidget): return w.value()
        # Num Slider 包装在 container 里
        if hasattr(self, '_drag_number_widget'): return self._drag_number_widget.value()
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

        # 根调用完成后刷新属性面板（仅在该节点被选中时）
        if len(_visited) == 1 and self.isSelected():
            sc = self.scene()
            if sc and hasattr(sc, 'main_window') and sc.main_window:
                sc.main_window._on_selection_changed()

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

        # 标题栏 — 手动构造路径：顶部圆角，底部直角，彻底消除碎屑
        r6 = 6.0
        tp = QPainterPath()
        tp.moveTo(0, self.title_h)                                    # 左下
        tp.lineTo(0, r6)                                              # 左边
        tp.arcTo(QRectF(0, 0, r6*2, r6*2), 180, -90)                 # 左上圆角
        tp.lineTo(self.width - r6, 0)                                 # 顶边
        tp.arcTo(QRectF(self.width - r6*2, 0, r6*2, r6*2), 90, -90)  # 右上圆角
        tp.lineTo(self.width, self.title_h)                           # 右边
        tp.closeSubpath()                                             # 底边直线闭合
        painter.setBrush(QBrush(self.title_color))
        painter.setPen(Qt.NoPen)
        painter.drawPath(tp)

        tr = QRectF(0, 0, self.width, self.title_h)   # 标题文字区域
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

    def __init__(self, parent=None, title="搜索节点…", filter_names=None):
        """
        filter_names: 若给定 set/list，则只显示此范围内的节点名称。
        """
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
        self.sb = QLineEdit(); self.sb.setPlaceholderText(title)
        self.sb.textChanged.connect(self._filter)
        self.lw = QListWidget()
        self.lw.itemActivated.connect(self._accept)
        l.addWidget(self.sb); l.addWidget(self.lw)

        self._items = []
        for cat, ns in NODE_CATEGORIES.items():
            for n in ns:
                if filter_names is None or n in filter_names:
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
        self._drag_origin_for_connect = None   # 拖线到空白时记录来源 socket
        self._panning = False
        self._pan_pos = QPointF()
        self._clipboard = []                   # Ctrl+C/V 剪贴板

    # ── 键盘 ─────────────────────────────────────────────────────────
    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Space and not ev.isAutoRepeat():
            self._open_search(); ev.accept(); return
        if ev.key() == Qt.Key_Delete:
            self._del_selected(); ev.accept(); return
        if ev.modifiers() & Qt.ControlModifier:
            if ev.key() == Qt.Key_C:
                self._copy_selected(); ev.accept(); return
            if ev.key() == Qt.Key_V:
                self._paste_nodes(); ev.accept(); return
        super().keyPressEvent(ev)

    # ── 复制 / 粘贴 ──────────────────────────────────────────────────
    def _copy_selected(self):
        self._clipboard.clear()
        for item in self.scene().selectedItems():
            if isinstance(item, NodeItem):
                self._clipboard.append({
                    "title": item.title,
                    "pos":   (item.pos().x(), item.pos().y()),
                })
        sc = self.scene()
        if sc and hasattr(sc, 'main_window') and sc.main_window and self._clipboard:
            sc.main_window.log(f"📋 已复制 {len(self._clipboard)} 个节点")

    def _paste_nodes(self):
        if not self._clipboard:
            return
        sc = self.scene()
        # 清除旧选中，粘贴后选中新节点
        for item in sc.selectedItems():
            item.setSelected(False)
        offset = 40
        for info in self._clipboard:
            title = info["title"]
            if title not in NODE_DEFINITIONS:
                continue
            ox, oy = info["pos"]
            mw = sc.main_window if hasattr(sc, 'main_window') else None
            if mw:
                ins, outs = NODE_DEFINITIONS[title]
                cat = _NODE_TO_CAT.get(title, "")
                node = NodeItem(title, cat)
                for n in ins:  node.add_input(n)
                for n in outs: node.add_output(n)
                node.setup_widget()
                node.setPos(ox + offset, oy + offset)
                sc.addItem(node)
                node.setSelected(True)
        if sc and hasattr(sc, 'main_window') and sc.main_window:
            sc.main_window.log(f"📌 已粘贴 {len(self._clipboard)} 个节点")

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
    def _socket_at(self, vpos, exclude_edge=None):
        """在视图坐标 vpos(QPoint) 处查找 NodeSocket (带容差)。
        exclude_edge: 临时从场景排除的拖拽 edge，避免路径遮挡检测。
        """
        scene_pt = self.mapToScene(vpos)

        # 缩放感知容差（保证视觉像素约 14px）
        scale = self.transform().m11() if self.transform().m11() > 0 else 1.0
        tol_scene = max(NodeSocket.HIT_R, int(14 / scale))

        # 1) 精确场景坐标检测
        for item in self.scene().items(scene_pt):
            if item is exclude_edge:
                continue
            if isinstance(item, NodeSocket):
                return item

        # 2) 容差矩形检测（场景坐标）
        from PySide6.QtCore import QRectF
        tol_rect = QRectF(scene_pt.x() - tol_scene, scene_pt.y() - tol_scene,
                          tol_scene * 2, tol_scene * 2)
        candidates = []
        for item in self.scene().items(tol_rect):
            if item is exclude_edge:
                continue
            if isinstance(item, NodeSocket):
                d = item.scenePos() - scene_pt
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

                    # ── 若点击的是已连接的输入端口，拾取已有连线重新拖拽 ──
                    if sock.is_input and sock.edges:
                        old_edge = sock.edges[0]          # 取第一条线
                        out_s = old_edge.source_socket
                        # 断开输入端
                        sock.remove_edge(old_edge)
                        old_edge.dest_socket = None
                        # 以 output socket 为起点继续拖拽
                        edge = old_edge
                        edge._drag_origin = out_s
                        edge.source_pos = out_s.scenePos() if out_s else self.mapToScene(vp)
                        edge.dest_pos   = self.mapToScene(vp)
                        edge._rebuild()
                        self._cur_edge = edge
                        self._drag_origin_for_connect = out_s
                        ev.accept(); return

                    edge = NodeEdge()
                    edge._drag_origin = sock
                    edge.source_pos = sock.scenePos()
                    edge.dest_pos   = self.mapToScene(vp)
                    self.scene().addItem(edge)
                    edge._rebuild()
                    self._cur_edge = edge
                    self._drag_origin_for_connect = sock
                    ev.accept(); return
                # 未命中 socket → 交给 super 处理节点选择/移动
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

            if self._cur_edge and ev.button() == Qt.LeftButton:
                edge = self._cur_edge
                self._cur_edge = None
                origin = edge._drag_origin

                # 临时隐藏拖拽 edge，避免 bezier 路径遮挡目标 socket 检测
                edge.setVisible(False)
                target = self._socket_at(ev.position().toPoint(), exclude_edge=edge)
                edge.setVisible(True)

                connected = False
                if (isinstance(target, NodeSocket)
                        and target is not origin
                        and target.is_input != origin.is_input):
                    # 规范化: source=output, dest=input
                    out_s = origin if not origin.is_input else target
                    in_s  = target if target.is_input else origin

                    # ── 若 input 端口已有连线，先断开旧线 ──
                    for old_e in list(in_s.edges):
                        if old_e.source_socket:
                            old_e.source_socket.remove_edge(old_e)
                        in_s.remove_edge(old_e)
                        self.scene().removeItem(old_e)

                    edge.source_socket = out_s
                    edge.dest_socket   = in_s
                    out_s.add_edge(edge)
                    in_s.add_edge(edge)
                    edge.update_positions()

                    # 传值并求值
                    in_s.value = out_s.value
                    in_s.node.evaluate()
                    connected = True

                    # 在 UI 日志中确认
                    sc = self.scene()
                    if sc and hasattr(sc, 'main_window') and sc.main_window:
                        sc.main_window.log(
                            f"🔗 {out_s.node.title}.{out_s.name} → {in_s.node.title}.{in_s.name}"
                        )

                if not connected:
                    self.scene().removeItem(edge)
                    # ── 拖线到空白处：弹出兼容节点选择弹窗 ──
                    from_sock = self._drag_origin_for_connect
                    if from_sock is not None:
                        self._show_connect_popup(from_sock, ev.position().toPoint())

                self._drag_origin_for_connect = None

                self.setDragMode(QGraphicsView.RubberBandDrag)  # 恢复 rubber band
                ev.accept(); return
        except Exception:
            self._log_error("mouseReleaseEvent", traceback.format_exc())
            if self._cur_edge:
                try: self.scene().removeItem(self._cur_edge)
                except Exception: pass
                self._cur_edge = None
            self.setDragMode(QGraphicsView.RubberBandDrag)
            ev.accept(); return   # 异常后也不透传给 super，避免误触发节点移动
        super().mouseReleaseEvent(ev)

    # ── 拖线到空白处弹出兼容节点弹窗 ────────────────────────────────
    def _show_connect_popup(self, from_sock, vpos):
        """
        from_sock: 拖拽起点 socket。
        根据其方向过滤出兼容节点（output→需要input端口的节点，input→需要output端口的节点）。
        """
        # 确定哪些节点有兼容端口
        compatible = []
        for name, (ins, outs) in NODE_DEFINITIONS.items():
            if from_sock.is_input:
                # 起点是 input，目标节点需要有 output
                if outs:
                    compatible.append(name)
            else:
                # 起点是 output，目标节点需要有 input
                if ins:
                    compatible.append(name)

        if not compatible:
            return

        drop_scene = self.mapToScene(vpos)
        popup = NodeSearchPopup(
            self,
            title="连接到…",
            filter_names=set(compatible),
        )

        def _on_selected(node_name):
            sc = self.scene()
            mw = sc.main_window if hasattr(sc, 'main_window') else None
            if not mw:
                return
            # 添加新节点
            mw.add_node(node_name, drop_scene)
            # 找到刚添加的节点（最后一个同名节点）
            new_node = None
            for item in sc.items():
                if isinstance(item, NodeItem) and item.title == node_name:
                    new_node = item
                    break  # scene.items() 最后加入的排最前
            if new_node is None:
                return
            # 自动连线：找第一个方向兼容的端口
            if from_sock.is_input:
                # 起点是 input → 连接新节点第一个 output
                if new_node.outputs:
                    tgt = new_node.outputs[0]
                    out_s, in_s = tgt, from_sock
                else:
                    return
            else:
                # 起点是 output → 连接新节点第一个 input
                if new_node.inputs:
                    tgt = new_node.inputs[0]
                    out_s, in_s = from_sock, tgt
                else:
                    return
            # 断开旧连线
            for old_e in list(in_s.edges):
                if old_e.source_socket:
                    old_e.source_socket.remove_edge(old_e)
                in_s.remove_edge(old_e)
                sc.removeItem(old_e)
            new_edge = NodeEdge(out_s, in_s)
            new_edge.source_pos = out_s.scenePos()
            new_edge.dest_pos   = in_s.scenePos()
            sc.addItem(new_edge)
            out_s.add_edge(new_edge)
            in_s.add_edge(new_edge)
            new_edge.update_positions()
            in_s.value = out_s.value
            in_s.node.evaluate()
            if mw:
                mw.log(f"🔗 {out_s.node.title}.{out_s.name} → {in_s.node.title}.{in_s.name}")

        popup.node_selected.connect(_on_selected)
        popup.move(QCursor.pos())
        popup.show()
        popup.sb.setFocus()


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
        self.propsBox._update_arrow(True)
        pg = QGridLayout(); pg.setContentsMargins(6,6,6,6)
        self.propLabel = QLabel("选择节点以查看属性")
        pg.addWidget(self.propLabel, 0, 0)
        self.propsBox.setContentLayout(pg)
        # 初始展开
        self.propsBox.content_area.setMaximumHeight(60)
        ll.addWidget(self.propsBox)

        # 日志
        self.logView = QTextEdit(); self.logView.setReadOnly(True)
        self.logView.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.logView.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        ll.addWidget(self.logView, 1)

        # ── 右侧画布 ────────────────────────────────────────────────
        self.scene = NodeScene(); self.scene.main_window = self
        self.view = NodeView(self.scene)
        self.scene.selectionChanged.connect(self._on_selection_changed)

        splitter.addWidget(left); splitter.addWidget(self.view)
        splitter.setSizes([320, 1080])

        self.log("节点编辑器已启动。")
        self.log(f"注册 {len(NODE_DEFINITIONS)} 个可执行节点  |  {len(NODE_CATEGORIES)} 个类别")
        self.log("Space=搜索  双击列表=添加  Delete=删除  中键=平移  滚轮=缩放")
        self.log("连线后数据自动流转，修改输入节点控件即可看到结果传播。")

    def _on_list_dbl(self, item):
        self.add_node(item.text())

    def _on_selection_changed(self):
        """选中变化时刷新左侧属性面板。"""
        nodes = [i for i in self.scene.selectedItems() if isinstance(i, NodeItem)]
        lay = self.propsBox.content_area.layout()
        # 清空旧内容
        while lay.count():
            it = lay.takeAt(0)
            if it.widget(): it.widget().deleteLater()

        if not nodes:
            lay.addWidget(QLabel("未选中节点"), 0, 0)
            return

        if len(nodes) == 1:
            node = nodes[0]
            cat  = node.category or "未分类"
            color = CATEGORY_COLORS.get(cat, QColor(120,120,120))

            # 标题
            title_lbl = QLabel(f"<b>{node.title}</b>")
            title_lbl.setStyleSheet(f"color:{color.name()};font-size:12px;")
            lay.addWidget(title_lbl, 0, 0, 1, 2)

            lay.addWidget(QLabel(f"类别: {cat}"), 1, 0, 1, 2)

            row = 2
            if node.inputs:
                lay.addWidget(QLabel("<b>输入端口</b>"), row, 0, 1, 2); row += 1
                for s in node.inputs:
                    v = s.value
                    v_str = str(round(v, 4)) if isinstance(v, float) else str(v) if v is not None else "—"
                    lay.addWidget(QLabel(f"  {s.name}"), row, 0)
                    lay.addWidget(QLabel(v_str), row, 1)
                    row += 1
            if node.outputs:
                lay.addWidget(QLabel("<b>输出端口</b>"), row, 0, 1, 2); row += 1
                for s in node.outputs:
                    v = s.value
                    v_str = str(round(v, 4)) if isinstance(v, float) else str(v) if v is not None else "—"
                    lay.addWidget(QLabel(f"  {s.name}"), row, 0)
                    lay.addWidget(QLabel(v_str), row, 1)
                    row += 1
        else:
            lay.addWidget(QLabel(f"已选 {len(nodes)} 个节点"), 0, 0, 1, 2)
            for idx, node in enumerate(nodes):
                lay.addWidget(QLabel(f"  {node.title}"), idx + 1, 0, 1, 2)

        # 动画重算高度
        if self.propsBox.toggle_button.isChecked():
            h = lay.sizeHint().height() + 12
            self.propsBox.content_area.setMaximumHeight(h)

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
