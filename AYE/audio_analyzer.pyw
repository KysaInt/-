# -*- coding: utf-8 -*-
"""
audio_analyzer.pyw
Windows 系统音频实时分析器
- 通过 soundcard 捕获 Windows WASAPI loopback（扬声器播放的音频）
- 使用 aubio 提取：音高、节拍BPM、起音、MFCC、频谱描述符、波形
- PySide6 UI，遵循 pysideui.txt 规范
"""

import sys
import os
import ctypes
import importlib
import subprocess
import numpy as np
from collections import deque

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
INSTRUMENT_LABELS = {
    "Accordion", "Banjo", "Bass guitar", "Cello", "Clarinet", "Cymbal", "Drum", "Drum kit",
    "Electric guitar", "Flute", "Glockenspiel", "Guitar", "Harp", "Hi-hat", "Keyboard (musical)",
    "Mandolin", "Marimba, xylophone", "Oboe", "Organ", "Piano", "Saxophone", "Snare drum",
    "Synthesizer", "Tambourine", "Trombone", "Trumpet", "Ukulele", "Violin, fiddle", "Wood block",
    "Acoustic guitar", "Electric piano", "Bass drum", "Musical instrument", "Plucked string instrument",
    "Bowed string instrument", "Brass instrument", "Wind instrument, woodwind instrument",
}
INSTRUMENT_LABEL_KEYWORDS = {
    "guitar", "piano", "violin", "cello", "flute", "trumpet", "sax", "drum", "instrument",
    "synth", "organ", "clarinet", "trombone", "ukulele", "mandolin", "harp", "banjo",
}
OPTIONAL_CLASSIFIER_PACKAGES = ["torch", "panns-inference"]
CLASSIFIER_METER_ITEMS = 5
CLASSIFIER_PANEL_ITEMS = 12
LIBRARY_PAGE_CONFIGS = {
    "aubio": {
        "title": "aubio",
        "subtitle": "实时基础分析",
    },
    "librosa": {
        "title": "librosa",
        "subtitle": "时频与音乐特征",
        "module": "librosa",
        "packages": ["librosa"],
        "features": [
            "STFT / Mel Spectrogram",
            "Chroma / Tempogram",
            "Onset Envelope / Beat / Tempo",
            "HPSS 与块处理式准实时分析",
        ],
    },
    "audioflux": {
        "title": "audioFlux",
        "subtitle": "高密度谱分析",
        "module": "audioflux",
        "packages": ["audioflux"],
        "features": [
            "多种谱图与变换",
            "Cepstral / MIR 特征",
            "更丰富的时频分辨率展示",
            "适合对比不同谱变换页面",
        ],
    },
    "madmom": {
        "title": "madmom",
        "subtitle": "音乐理解与节奏结构",
        "module": "madmom",
        "packages": ["madmom"],
        "features": [
            "Beats / Downbeats / Tempo",
            "Onsets / Chords / Key",
            "更偏滑动窗口与模型处理链",
            "适合作为高层音乐理解页面",
        ],
    },
}


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def midi_to_note_name(midi_value: float) -> str:
    if np.isnan(midi_value) or midi_value <= 0:
        return "--"
    midi_int = int(round(midi_value))
    octave = midi_int // 12 - 1
    return f"{NOTE_NAMES[midi_int % 12]}{octave}"


def midi_to_frequency(midi_value: float) -> float:
    if np.isnan(midi_value) or midi_value <= 0:
        return 0.0
    return 440.0 * (2.0 ** ((midi_value - 69.0) / 12.0))


def estimate_timbre_profile(metrics: dict) -> tuple[str, list[tuple[str, float]]]:
    confidence = clamp01(metrics.get("confidence", 0.0))
    zcr = clamp01(metrics.get("zcr", 0.0) * 6.0)
    flatness = clamp01(metrics.get("flatness", 0.0) * 2.5)
    centroid = clamp01(metrics.get("centroid_ratio", 0.0))
    flux = clamp01(metrics.get("flux_ratio", 0.0))

    bright = clamp01(0.7 * centroid + 0.3 * flux)
    warm = clamp01((1.0 - centroid) * 0.75 + confidence * 0.25)
    percussive = clamp01(0.55 * flux + 0.3 * zcr + 0.15 * flatness)
    tonal = clamp01(0.7 * confidence + 0.3 * (1.0 - flatness))

    scores = [
        ("明亮", bright),
        ("温暖", warm),
        ("打击感", percussive),
        ("谐和度", tonal),
    ]

    if percussive > 0.72 and bright > 0.55:
        label = "偏打击/瞬态"
    elif tonal > 0.7 and bright > 0.6:
        label = "偏明亮旋律"
    elif tonal > 0.7 and warm > 0.58:
        label = "偏温暖旋律"
    elif flatness > 0.62:
        label = "偏噪声/失真"
    else:
        label = "混合音色"
    return label, scores


def resample_linear(samples: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    samples = np.asarray(samples, dtype=np.float32)
    if len(samples) == 0 or src_sr == dst_sr:
        return samples.copy()
    dst_len = max(1, int(round(len(samples) * dst_sr / float(src_sr))))
    src_x = np.linspace(0.0, len(samples) - 1, num=len(samples), dtype=np.float32)
    dst_x = np.linspace(0.0, len(samples) - 1, num=dst_len, dtype=np.float32)
    return np.interp(dst_x, src_x, samples).astype(np.float32)


def extract_instrument_scores(label_names, clipwise_output: np.ndarray) -> tuple[str, list[tuple[str, float]]]:
    vector = np.asarray(clipwise_output, dtype=np.float32)
    matches = []
    for index, label in enumerate(label_names):
        lower_label = label.lower()
        if label in INSTRUMENT_LABELS or any(keyword in lower_label for keyword in INSTRUMENT_LABEL_KEYWORDS):
            matches.append((label, float(vector[index])))
    matches.sort(key=lambda item: item[1], reverse=True)
    top_matches = matches[:CLASSIFIER_PANEL_ITEMS]
    if not top_matches:
        return "--", []
    best_label = top_matches[0][0]
    max_score = max(top_matches[0][1], 1e-6)
    normalized = [(label, clamp01(score / max_score)) for label, score in top_matches]
    return best_label, normalized

try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AYE.AudioAnalyzer.1")
except Exception:
    pass

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSizePolicy, QGridLayout, QFrame, QComboBox,
    QSpinBox, QCheckBox, QScrollArea, QSplitter, QGroupBox,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QStackedWidget,
    QListWidget, QListWidgetItem, QTextEdit
)
from PySide6.QtCore import (
    QThread, Signal, Qt, QTimer, QPropertyAnimation, QEasingCurve,
    QSize, QPointF
)
from PySide6.QtGui import (
    QIcon, QPalette, QFontDatabase, QPainter, QColor, QPen, QBrush,
    QLinearGradient, QPainterPath, QFont
)

# ──────────────────────────────────────────────────────────────
#  颜色工具（参考 mf_pyside6.pyw）
# ──────────────────────────────────────────────────────────────
def _hex_to_rgb(hex_color: str):
    h = hex_color.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except Exception:
        return 128, 128, 128

def _luminance(rgb):
    def _c(c):
        c /= 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * _c(r) + 0.7152 * _c(g) + 0.0722 * _c(b)

def _contrast_ratio(c1, c2):
    L1, L2 = _luminance(c1), _luminance(c2)
    lighter, darker = max(L1, L2), min(L1, L2)
    return (lighter + 0.05) / (darker + 0.05)

def ensure_contrast_color(fg_hex: str, *bg_hex_candidates: str, min_ratio: float = 2.2) -> str:
    try:
        fg_rgb = _hex_to_rgb(fg_hex)
        bg_rgbs = [_hex_to_rgb(c) for c in bg_hex_candidates if c]
        if all(_contrast_ratio(fg_rgb, bg) >= min_ratio for bg in bg_rgbs):
            return fg_hex
    except Exception:
        return '#00A8FF'
    r, g, b = fg_rgb
    lum = _luminance(fg_rgb)
    if lum < 0.3:
        r = min(255, int(r * 0.6 + 80))
        g = min(255, int(g * 0.6 + 140))
        b = min(255, int(b * 0.6 + 220))
    elif lum > 0.8:
        r, g, b = int(r * 0.4), int(g * 0.7), int(b * 0.9)
    else:
        b = min(255, int(b * 1.25 + 20))
        g = min(255, int(g * 1.10 + 10))
    return f"#{r:02X}{g:02X}{b:02X}"


# ──────────────────────────────────────────────────────────────
#  CollapsibleBox（来自 pysideui.txt 规范）
# ──────────────────────────────────────────────────────────────
class CollapsibleBox(QWidget):
    def __init__(self, title="", parent=None, duration=250, expanded=False):
        super().__init__(parent)
        self._title = title
        self.toggle_button = QPushButton()
        f = self.toggle_button.font()
        f.setBold(True)
        self.toggle_button.setFont(f)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(expanded)
        self.content_area = QFrame()
        self.content_area.setFrameShape(QFrame.StyledPanel)
        self.content_area.setMaximumHeight(0)
        self.content_area.setMinimumHeight(0)
        self.anim = QPropertyAnimation(self.content_area, b"maximumHeight")
        self.anim.setDuration(duration)
        self.anim.setEasingCurve(QEasingCurve.InOutCubic)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.toggle_button)
        lay.addWidget(self.content_area)
        self.toggle_button.clicked.connect(self._on_toggled)
        self._update_arrow(expanded)

    def setContentLayout(self, layout, expanded=False):
        old = self.content_area.layout()
        if old:
            while old.count():
                it = old.takeAt(0)
                w = it.widget()
                if w:
                    w.setParent(None)
        self.content_area.setLayout(layout)
        if self.toggle_button.isChecked() or expanded:
            self.content_area.setMaximumHeight(16777215)
        else:
            self.content_area.setMaximumHeight(0)

    def _on_toggled(self, checked):
        self._update_arrow(checked)
        h = self.content_area.layout().sizeHint().height() if self.content_area.layout() else 0
        self.anim.stop()
        self.anim.setStartValue(self.content_area.maximumHeight())
        self.anim.setEndValue(h if checked else 0)
        self.anim.start()

    def _update_arrow(self, expanded):
        self.toggle_button.setText(("▼ " if expanded else "► ") + self._title)


# ──────────────────────────────────────────────────────────────
#  实时图表控件（纯 QPainter，不依赖 matplotlib）
# ──────────────────────────────────────────────────────────────
class WaveformWidget(QWidget):
    """滚动波形图"""
    def __init__(self, parent=None, history=200):
        super().__init__(parent)
        self._buf = deque([0.0] * history, maxlen=history)
        self.setMinimumHeight(80)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def push(self, samples: np.ndarray):
        """接收一帧音频样本（-1~1），取 RMS 推入缓冲"""
        rms = float(np.sqrt(np.mean(samples ** 2))) if len(samples) > 0 else 0.0
        self._buf.append(min(rms * 4.0, 1.0))
        self.update()

    def push_raw(self, samples: np.ndarray):
        """推入原始波形数据（每次推一段，只取部分点展示）"""
        step = max(1, len(samples) // 40)
        for i in range(0, len(samples), step):
            self._buf.append(float(np.clip(samples[i], -1.0, 1.0)))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal = self.palette()
        bg = pal.color(QPalette.Base)
        fg_col = pal.color(QPalette.Highlight)

        p.fillRect(self.rect(), bg)

        w, h = self.width(), self.height()
        mid = h / 2.0
        data = list(self._buf)
        n = len(data)
        if n < 2:
            return

        pen = QPen(fg_col, 1.5)
        p.setPen(pen)
        path = QPainterPath()
        for i, v in enumerate(data):
            x = i / (n - 1) * w
            y = mid - v * mid * 0.9
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        p.drawPath(path)


class BarChartWidget(QWidget):
    """通用条形图：用于 MFCC、频谱描述符等"""
    def __init__(self, n_bars=13, labels=None, parent=None, title=""):
        super().__init__(parent)
        self._n = n_bars
        self._values = [0.0] * n_bars
        self._labels = labels or [str(i) for i in range(n_bars)]
        self._title = title
        self._vmin = -1.0
        self._vmax = 1.0
        self.setMinimumHeight(100)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_values(self, values):
        self._values = list(values[:self._n])
        if len(self._values) < self._n:
            self._values += [0.0] * (self._n - len(self._values))
        # 自动量程（平滑）
        vmax = max(abs(v) for v in self._values) if self._values else 1.0
        if vmax > 0:
            self._vmax = max(self._vmax * 0.85 + vmax * 0.15, vmax)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal = self.palette()
        bg = pal.color(QPalette.Base)
        hi = pal.color(QPalette.Highlight)
        text_col = pal.color(QPalette.Text)
        empty_col = QColor("#555555")

        p.fillRect(self.rect(), bg)

        n = self._n
        w, h = self.width(), self.height()
        title_h = 16
        label_h = 14
        chart_h = h - title_h - label_h - 4
        if chart_h < 10:
            return

        # 标题
        if self._title:
            p.setPen(text_col)
            tf = p.font()
            tf.setPointSize(8)
            tf.setBold(True)
            p.setFont(tf)
            p.drawText(0, 0, w, title_h, Qt.AlignCenter, self._title)

        bar_w = w / n
        mid_y = title_h + chart_h / 2

        for i, v in enumerate(self._values):
            x = i * bar_w + 1
            bw = bar_w - 2
            norm = v / self._vmax if self._vmax != 0 else 0.0
            bar_h = abs(norm) * chart_h / 2

            # 空条（背景）
            p.setPen(Qt.NoPen)
            p.setBrush(empty_col)
            p.drawRect(int(x), int(title_h), int(bw), int(chart_h))

            # 实际值条
            p.setBrush(hi)
            if norm >= 0:
                p.drawRect(int(x), int(mid_y - bar_h), int(bw), int(bar_h))
            else:
                p.drawRect(int(x), int(mid_y), int(bw), int(bar_h))

        # 标签
        p.setPen(text_col)
        lf = p.font()
        lf.setPointSize(7)
        lf.setBold(False)
        p.setFont(lf)
        for i, lbl in enumerate(self._labels[:n]):
            x = i * bar_w
            p.drawText(int(x), title_h + chart_h + 2, int(bar_w), label_h,
                       Qt.AlignCenter, lbl)


class LineChartWidget(QWidget):
    """折线历史图：用于音高、BPM 等连续数据"""
    def __init__(self, history=150, parent=None, title="", ymin=0.0, ymax=1.0, unit=""):
        super().__init__(parent)
        self._history = history
        self._buf = deque([float('nan')] * history, maxlen=history)
        self._title = title
        self._ymin = ymin
        self._ymax = ymax
        self._unit = unit
        self._current = float('nan')
        self.setMinimumHeight(90)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def push(self, value: float):
        self._current = value
        self._buf.append(value)
        # 自动扩展量程
        if not np.isnan(value):
            if value > self._ymax:
                self._ymax = value * 1.1
            if value < self._ymin and value > 0:
                self._ymin = value * 0.9
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal = self.palette()
        bg = pal.color(QPalette.Base)
        hi = pal.color(QPalette.Highlight)
        text_col = pal.color(QPalette.Text)
        grid_col = pal.color(QPalette.Mid)

        p.fillRect(self.rect(), bg)
        w, h = self.width(), self.height()
        title_h = 16
        val_h = 14
        pad = 4
        chart_h = h - title_h - val_h - pad * 2

        if chart_h < 10:
            return

        # 标题
        p.setPen(text_col)
        tf = p.font()
        tf.setPointSize(8)
        tf.setBold(True)
        p.setFont(tf)
        p.drawText(0, 0, w, title_h, Qt.AlignCenter, self._title)

        # 网格线
        grid_pen = QPen(grid_col, 1, Qt.DotLine)
        p.setPen(grid_pen)
        for frac in [0.25, 0.5, 0.75]:
            y = title_h + pad + chart_h * frac
            p.drawLine(0, int(y), w, int(y))

        # 折线
        data = [v for v in self._buf]
        n = len(data)
        if n < 2:
            return

        yrange = self._ymax - self._ymin
        if yrange == 0:
            yrange = 1.0

        pen = QPen(hi, 2.0)
        p.setPen(pen)
        path = QPainterPath()
        started = False
        for i, v in enumerate(data):
            if np.isnan(v):
                started = False
                continue
            x = i / (n - 1) * w
            y = title_h + pad + chart_h * (1.0 - (v - self._ymin) / yrange)
            y = max(title_h + pad, min(y, title_h + pad + chart_h))
            if not started:
                path.moveTo(x, y)
                started = True
            else:
                path.lineTo(x, y)
        if not path.isEmpty():
            p.drawPath(path)

        # 当前值显示
        p.setPen(text_col)
        vf = p.font()
        vf.setPointSize(8)
        vf.setBold(False)
        p.setFont(vf)
        if not np.isnan(self._current):
            val_str = f"{self._current:.1f} {self._unit}"
        else:
            val_str = f"-- {self._unit}"
        p.drawText(0, h - val_h, w, val_h, Qt.AlignRight | Qt.AlignVCenter, val_str + "  ")


class SpectrogramWidget(QWidget):
    """简易频谱图（实时频谱 + 历史瀑布图）"""
    def __init__(self, n_bins=256, parent=None):
        super().__init__(parent)
        self._n_bins = n_bins
        self._spectrum = np.zeros(n_bins)
        self._waterfall = deque(maxlen=60)
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def push(self, magnitudes: np.ndarray):
        n = min(len(magnitudes), self._n_bins)
        self._spectrum[:n] = magnitudes[:n]
        if n < self._n_bins:
            self._spectrum[n:] = 0
        self._waterfall.append(self._spectrum.copy())
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal = self.palette()
        bg = pal.color(QPalette.Base)
        hi = pal.color(QPalette.Highlight)
        text_col = pal.color(QPalette.Text)

        p.fillRect(self.rect(), bg)
        w, h = self.width(), self.height()
        title_h = 16

        p.setPen(text_col)
        tf = p.font()
        tf.setPointSize(8)
        tf.setBold(True)
        p.setFont(tf)
        p.drawText(0, 0, w, title_h, Qt.AlignCenter, "频谱")

        chart_h = h - title_h
        if chart_h < 10 or len(self._spectrum) == 0:
            return

        # 分成上下两半：上半=瀑布图, 下半=实时框图
        wf_h = chart_h * 2 // 3
        sp_h = chart_h - wf_h

        # ---- 瀑布图 ----
        lines = list(self._waterfall)
        n_lines = len(lines)
        if n_lines > 0:
            peak = max(np.max(ln) for ln in lines)
            if peak == 0:
                peak = 1.0
            for row_i, line in enumerate(lines):
                y = title_h + int(row_i / n_lines * wf_h)
                row_h = max(1, int(wf_h / n_lines))
                for col_i, val in enumerate(line):
                    intensity = float(val) / peak
                    x = int(col_i / len(line) * w)
                    bw = max(1, int(w / len(line)))
                    color = QColor(hi)
                    color.setAlphaF(intensity)
                    p.fillRect(x, y, bw, row_h, color)

        # ---- 实时频谱 ----
        sp_top = title_h + wf_h
        peak = float(np.max(self._spectrum)) if np.max(self._spectrum) > 0 else 1.0
        n = self._n_bins
        bw = max(1, w // n)
        empty_col = QColor("#555555")
        for i, val in enumerate(self._spectrum):
            x = int(i / n * w)
            bar_h = int((val / peak) * sp_h)
            p.fillRect(x, sp_top, bw, sp_h, empty_col)
            p.fillRect(x, sp_top + sp_h - bar_h, bw, bar_h, hi)


class OnsetIndicator(QWidget):
    """起音闪烁指示灯 + 最近起音时间轴"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._lit = False
        self._recent = deque(maxlen=20)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._dim)
        self._scroll_timer = QTimer(self)
        self._scroll_timer.timeout.connect(self.update)
        self._scroll_timer.start(40)
        self.setMinimumHeight(90)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def flash(self):
        self._lit = True
        import time
        self._recent.append(time.time())
        self.update()
        self._timer.start(120)

    def _dim(self):
        self._lit = False
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal = self.palette()
        bg = pal.color(QPalette.Base)
        hi = pal.color(QPalette.Highlight)
        text_col = pal.color(QPalette.Text)

        p.fillRect(self.rect(), bg)
        w, h = self.width(), self.height()

        # 圆形指示灯
        radius = min(h - 10, 34) // 2
        cx, cy = radius + 8, h // 2
        if self._lit:
            p.setPen(Qt.NoPen)
            glow = QColor(hi)
            glow.setAlpha(80)
            p.setBrush(glow)
            p.drawEllipse(int(cx - radius - 4), int(cy - radius - 4),
                          int((radius + 4) * 2), int((radius + 4) * 2))
            p.setBrush(hi)
        else:
            p.setPen(QPen(hi, 2))
            p.setBrush(QColor("#555555"))
        p.drawEllipse(int(cx - radius), int(cy - radius), radius * 2, radius * 2)

        # 标签
        p.setPen(text_col)
        f = p.font()
        f.setPointSize(8)
        f.setBold(True)
        p.setFont(f)
        p.drawText(cx + radius + 10, 0, w - cx - radius - 14, h,
                   Qt.AlignLeft | Qt.AlignVCenter, "起音检测 (Onset)")

        # 近期起音时间轴（小圆点）
        import time
        now = time.time()
        timeline_x = cx + radius + 80
        timeline_w = w - timeline_x - 10
        if timeline_w > 20:
            window = 4.0  # 显示最近4秒
            p.setPen(QPen(pal.color(QPalette.Mid), 1))
            p.drawLine(int(timeline_x), cy, int(timeline_x + timeline_w), cy)
            p.setPen(Qt.NoPen)
            p.setBrush(hi)
            for t in self._recent:
                age = now - t
                if 0 <= age <= window:
                    px = timeline_x + int((1.0 - age / window) * timeline_w)
                    alpha = int(255 * (1.0 - age / window))
                    c = QColor(hi)
                    c.setAlpha(alpha)
                    p.setBrush(c)
                    p.drawEllipse(px - 4, cy - 4, 8, 8)


class BeatIndicator(QWidget):
    """节拍 BPM 仪表盘 + 心跳动画"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._bpm = 0.0
        self._pulse = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._decay)
        self._timer.start(30)
        self.setMinimumHeight(60)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def beat(self, bpm: float):
        self._bpm = bpm
        self._pulse = 1.0
        self.update()

    def _decay(self):
        if self._pulse > 0:
            self._pulse = max(0.0, self._pulse - 0.06)
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal = self.palette()
        bg = pal.color(QPalette.Base)
        hi = pal.color(QPalette.Highlight)
        text_col = pal.color(QPalette.Text)

        p.fillRect(self.rect(), bg)
        w, h = self.width(), self.height()

        # BPM 大字显示
        bpm_str = f"{self._bpm:.0f}" if self._bpm > 0 else "--"
        f = QFont()
        f.setPointSize(22)
        f.setBold(True)
        p.setFont(f)

        pulse_color = QColor(hi)
        alpha = int(80 + 175 * self._pulse)
        pulse_color.setAlpha(alpha)
        p.setPen(QPen(pulse_color))
        p.drawText(10, 0, 80, h, Qt.AlignLeft | Qt.AlignVCenter, bpm_str)

        # 标签
        p.setPen(text_col)
        f2 = QFont()
        f2.setPointSize(8)
        p.setFont(f2)
        p.drawText(10, h // 2 + 2, 80, h // 2, Qt.AlignLeft | Qt.AlignTop, "BPM")

        # 节拍进度条
        bar_x, bar_y = 100, h // 2 - 6
        bar_w, bar_h = w - 110, 12
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#555555"))
        p.drawRoundedRect(bar_x, bar_y, bar_w, bar_h, 4, 4)
        fill_w = int(bar_w * self._pulse)
        if fill_w > 0:
            grad = QLinearGradient(bar_x, 0, bar_x + bar_w, 0)
            grad.setColorAt(0, hi)
            c2 = QColor(hi)
            c2.setAlpha(60)
            grad.setColorAt(1, c2)
            p.setBrush(grad)
            p.drawRoundedRect(bar_x, bar_y, fill_w, bar_h, 4, 4)


class ValueCardWidget(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._title = title
        self._value = "--"
        self._subtitle = ""
        self.setMinimumHeight(76)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_value(self, value: str, subtitle: str = ""):
        self._value = value
        self._subtitle = subtitle
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal = self.palette()
        bg = pal.color(QPalette.Base)
        text_col = pal.color(QPalette.Text)
        hi = pal.color(QPalette.Highlight)
        mid = pal.color(QPalette.Mid)

        p.fillRect(self.rect(), bg)
        p.setPen(QPen(mid, 1))
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 6, 6)

        title_font = QFont()
        title_font.setPointSize(8)
        title_font.setBold(True)
        p.setFont(title_font)
        p.setPen(text_col)
        p.drawText(10, 8, self.width() - 20, 16, Qt.AlignLeft | Qt.AlignVCenter, self._title)

        value_font = QFont()
        value_font.setPointSize(18)
        value_font.setBold(True)
        p.setFont(value_font)
        p.setPen(hi)
        p.drawText(10, 26, self.width() - 20, 28, Qt.AlignLeft | Qt.AlignVCenter, self._value)

        p.setFont(title_font)
        p.setPen(text_col)
        p.drawText(10, self.height() - 22, self.width() - 20, 16, Qt.AlignLeft | Qt.AlignVCenter, self._subtitle)


class HorizontalMetersWidget(QWidget):
    def __init__(self, parent=None, title=""):
        super().__init__(parent)
        self._title = title
        self._items = []
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_items(self, items):
        self._items = list(items)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal = self.palette()
        bg = pal.color(QPalette.Base)
        text_col = pal.color(QPalette.Text)
        hi = pal.color(QPalette.Highlight)
        empty = QColor("#555555")

        p.fillRect(self.rect(), bg)
        w, h = self.width(), self.height()
        title_h = 18

        p.setPen(text_col)
        tf = QFont()
        tf.setPointSize(8)
        tf.setBold(True)
        p.setFont(tf)
        p.drawText(0, 0, w, title_h, Qt.AlignCenter, self._title)

        if not self._items:
            return

        row_h = max(22, (h - title_h - 8) // len(self._items))
        for index, (label, value) in enumerate(self._items):
            value = clamp01(value)
            y = title_h + 4 + index * row_h
            p.setPen(text_col)
            p.drawText(8, y, 60, row_h - 4, Qt.AlignLeft | Qt.AlignVCenter, label)
            bar_x = 72
            bar_w = max(20, w - bar_x - 52)
            bar_h = 10
            bar_y = y + (row_h - bar_h) // 2
            p.setPen(Qt.NoPen)
            p.setBrush(empty)
            p.drawRoundedRect(bar_x, bar_y, bar_w, bar_h, 4, 4)
            p.setBrush(hi)
            p.drawRoundedRect(bar_x, bar_y, int(bar_w * value), bar_h, 4, 4)
            p.setPen(text_col)
            p.drawText(bar_x + bar_w + 6, y, 40, row_h - 4, Qt.AlignRight | Qt.AlignVCenter, f"{int(value * 100):d}%")


class DataTreeWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setIndentation(18)
        self.tree.setUniformRowHeights(True)
        self.tree.setAlternatingRowColors(False)
        self.tree.setFocusPolicy(Qt.NoFocus)
        self.tree.setStyleSheet(
            "QTreeWidget::item { padding: 2px 6px; }"
            "QTreeWidget { border: 0; }"
        )
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        layout.addWidget(self.tree)

        self._items = {}

    def set_value(self, path, value=""):
        item = self._ensure_item(tuple(path))
        item.setText(1, value)
        item.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)

    def _ensure_item(self, path: tuple[str, ...]) -> QTreeWidgetItem:
        parent_item = None
        current_path = []
        for index, label in enumerate(path):
            current_path.append(label)
            key = tuple(current_path)
            item = self._items.get(key)
            if item is None:
                if parent_item is None:
                    item = QTreeWidgetItem([label, ""])
                    self.tree.addTopLevelItem(item)
                else:
                    item = QTreeWidgetItem(parent_item, [label, ""])
                    parent_font = parent_item.font(0)
                    parent_font.setBold(True)
                    parent_item.setFont(0, parent_font)
                item.setFirstColumnSpanned(False)
                item.setExpanded(True)
                item.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
                self._items[key] = item
            parent_item = item
        return parent_item


def has_optional_classifier_support() -> bool:
    if importlib.util.find_spec("panns_inference") is None:
        return False
    try:
        panns_module = importlib.import_module("panns_inference")
        return hasattr(panns_module, "AudioTagging") and hasattr(panns_module, "labels")
    except Exception:
        return False


def pip_host_python() -> str:
    base_executable = getattr(sys, "_base_executable", "")
    if base_executable and os.path.exists(base_executable):
        return os.path.abspath(base_executable)
    exe_path = os.path.abspath(sys.executable)
    if os.path.basename(exe_path).lower() == "pythonw.exe":
        console_python = os.path.join(os.path.dirname(exe_path), "python.exe")
        if os.path.exists(console_python):
            return console_python
    return exe_path


class OptionalDependencyInstaller(QThread):
    sig_done = Signal(bool, str)

    def __init__(self, packages: list[str], parent=None):
        super().__init__(parent)
        self._packages = list(packages)

    def run(self):
        command = [pip_host_python(), "-m", "pip", "install", "--user", *self._packages]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        except Exception as e:
            self.sig_done.emit(False, str(e))
            return

        output = (result.stdout or "").strip()
        error_output = (result.stderr or "").strip()
        if result.returncode != 0:
            message = error_output or output or f"pip exited with code {result.returncode}"
            self.sig_done.emit(False, message[-500:])
            return

        importlib.invalidate_caches()
        if has_optional_classifier_support():
            self.sig_done.emit(True, "乐器分类模块安装完成")
        else:
            message = output or error_output or "安装完成，但未检测到 panns_inference"
            self.sig_done.emit(False, message[-500:])


def enumerate_loopback_speakers() -> list[tuple[str, str]]:
    import soundcard as sc

    speakers = sc.all_speakers()
    return [(spk.name, spk.id) for spk in speakers]


def get_loopback_microphone(device_name: str | None):
    import soundcard as sc

    if device_name:
        return sc.get_microphone(device_name, include_loopback=True)

    speakers = sc.all_speakers()
    if not speakers:
        raise RuntimeError("未找到任何扬声器设备")
    default_spk = sc.default_speaker()
    return sc.get_microphone(default_spk.id, include_loopback=True)


# ──────────────────────────────────────────────────────────────
#  aubio 音频捕获与分析线程
# ──────────────────────────────────────────────────────────────
class AudioWorker(QThread):
    sig_waveform  = Signal(object)   # np.ndarray
    sig_spectrum  = Signal(object)   # np.ndarray (magnitudes)
    sig_pitch     = Signal(float, float)  # pitch_midi, confidence
    sig_beat      = Signal(float)    # bpm
    sig_onset     = Signal()
    sig_mfcc      = Signal(object)   # np.ndarray (13,)
    sig_specdesc  = Signal(object)   # dict {method: value}
    sig_metrics   = Signal(object)   # dict {rms, zcr, note_name, freq_hz, timbre}
    sig_classifier = Signal(object)  # dict {label, items}
    sig_status    = Signal(str)
    sig_error     = Signal(str)

    def __init__(self, device_name: str = None, samplerate: int = 44100,
                 hop_size: int = 512, win_size: int = 1024, enable_classifier: bool = False):
        super().__init__()
        self._device_name = device_name
        self._samplerate = samplerate
        self._hop_size = hop_size
        self._win_size = win_size
        self._running = False
        self._enable_classifier = enable_classifier

    def stop(self):
        self._running = False

    def run(self):
        # 延迟导入，避免启动时崩溃
        try:
            import soundcard as sc
        except ImportError:
            self.sig_error.emit("缺少 soundcard 库，请运行：pip install soundcard")
            return
        try:
            import aubio
        except ImportError:
            self.sig_error.emit("缺少 aubio 库，请先安装：pip install aubio")
            return

        panns_tagger = None
        panns_labels = None
        classifier_window = max(1, self._samplerate)
        classifier_stride = max(self._hop_size, int(self._samplerate * 0.75))
        classifier_buffer = np.zeros(classifier_window, dtype=np.float32)
        classifier_ready = 0
        classifier_since_last = 0

        if self._enable_classifier:
            try:
                panns_module = importlib.import_module("panns_inference")
                panns_tagger = panns_module.AudioTagging(device='cpu')
                panns_labels = panns_module.labels
                self.sig_status.emit("乐器分类模型已加载，正在初始化音频采集...")
            except Exception as e:
                self.sig_status.emit(f"乐器分类不可用，将继续基础分析: {e}")
                self.sig_classifier.emit({
                    "label": "不可用",
                    "subtitle": "未安装可选分类库",
                    "items": [("未加载", 0.0)],
                })

        sr = self._samplerate
        hop = self._hop_size
        win = self._win_size

        # ── 初始化 aubio 处理器 ──
        try:
            pv = aubio.pvoc(win, hop)
            pitch_o = aubio.pitch("yin", win * 4, hop, sr)
            pitch_o.set_unit("midi")
            pitch_o.set_tolerance(0.8)
            tempo_o = aubio.tempo("default", win, hop, sr)
            onset_o = aubio.onset("default", win, hop, sr)
            m = aubio.mfcc(win, 40, 13, sr)
            spec_methods = ["energy", "hfc", "centroid", "rolloff", "specflux"]
            spec_o = {method: aubio.specdesc(method, win) for method in spec_methods}
        except Exception as e:
            self.sig_error.emit(f"初始化 aubio 分析器失败: {e}")
            return

        # ── 选择 loopback 设备 ──
        try:
            mic = get_loopback_microphone(self._device_name)
        except Exception as e:
            self.sig_error.emit(f"打开音频设备失败: {e}")
            return

        self.sig_status.emit(f"正在监听: {mic.name}")
        self._running = True

        try:
            with mic.recorder(samplerate=sr, channels=1, blocksize=hop) as recorder:
                while self._running:
                    try:
                        data = recorder.record(numframes=hop)  # shape: (hop, 1)
                        samples = data[:, 0].astype(np.float32)
                        if len(samples) < hop:
                            samples = np.pad(samples, (0, hop - len(samples)))
                    except Exception as e:
                        self.sig_error.emit(f"读取音频失败: {e}")
                        break

                    # 发出波形
                    self.sig_waveform.emit(samples.copy())

                    # 更新分类缓冲
                    if len(samples) >= classifier_window:
                        classifier_buffer = samples[-classifier_window:].copy()
                        classifier_ready = classifier_window
                    else:
                        classifier_buffer = np.roll(classifier_buffer, -len(samples))
                        classifier_buffer[-len(samples):] = samples
                        classifier_ready = min(classifier_window, classifier_ready + len(samples))
                    classifier_since_last += len(samples)

                    # 频谱
                    fftgrain = pv(samples)
                    mags = fftgrain.norm.copy()
                    self.sig_spectrum.emit(mags)

                    # 音高
                    pitch_val = pitch_o(samples)[0]
                    conf = pitch_o.get_confidence()
                    self.sig_pitch.emit(float(pitch_val), float(conf))

                    # 节拍
                    is_beat = tempo_o(samples)
                    if is_beat[0]:
                        self.sig_beat.emit(float(tempo_o.get_bpm()))

                    # 起音
                    if onset_o(samples)[0]:
                        self.sig_onset.emit()

                    # MFCC
                    mfcc_out = m(fftgrain)
                    self.sig_mfcc.emit(mfcc_out.copy())

                    # 频谱描述符
                    desc = {}
                    for method, o_obj in spec_o.items():
                        desc[method] = float(o_obj(fftgrain)[0])
                    self.sig_specdesc.emit(desc)

                    rms = float(np.sqrt(np.mean(samples ** 2)))
                    zcr = float(np.mean(np.abs(np.diff(np.signbit(samples))))) if len(samples) > 1 else 0.0
                    mags_array = np.asarray(mags, dtype=np.float32)
                    eps = 1e-12
                    flatness = float(np.exp(np.mean(np.log(mags_array + eps))) / (np.mean(mags_array + eps))) if len(mags_array) else 0.0
                    centroid_ratio = float(desc.get("centroid", 0.0) / max(1.0, win / 2.0))
                    flux_ratio = clamp01(float(desc.get("specflux", 0.0)) / 150.0)
                    note_name = midi_to_note_name(float(pitch_val)) if conf >= 0.35 else "--"
                    freq_hz = midi_to_frequency(float(pitch_val)) if conf >= 0.35 else 0.0
                    timbre_label, timbre_scores = estimate_timbre_profile({
                        "confidence": float(conf),
                        "zcr": zcr,
                        "flatness": flatness,
                        "centroid_ratio": centroid_ratio,
                        "flux_ratio": flux_ratio,
                    })
                    self.sig_metrics.emit({
                        "rms": rms,
                        "zcr": zcr,
                        "note_name": note_name,
                        "freq_hz": freq_hz,
                        "timbre_label": timbre_label,
                        "timbre_scores": timbre_scores,
                    })

                    if panns_tagger is not None and panns_labels is not None:
                        if classifier_ready >= classifier_window and classifier_since_last >= classifier_stride:
                            classifier_since_last = 0
                            try:
                                model_audio = resample_linear(classifier_buffer, sr, 32000)
                                clipwise_output, _ = panns_tagger.inference(model_audio[None, :])
                                instrument_label, instrument_items = extract_instrument_scores(
                                    panns_labels, clipwise_output[0]
                                )
                                self.sig_classifier.emit({
                                    "label": instrument_label,
                                    "items": instrument_items,
                                })
                            except Exception as e:
                                self.sig_status.emit(f"乐器分类推理失败，已跳过本轮: {e}")
                                panns_tagger = None

        except Exception as e:
            self.sig_error.emit(f"音频流异常: {e}")
        finally:
            self._running = False
            self.sig_status.emit("已停止")


class LibrosaWorker(QThread):
    sig_waveform = Signal(object)
    sig_spectrum = Signal(object)
    sig_chroma = Signal(object)
    sig_metrics = Signal(object)
    sig_status = Signal(str)
    sig_error = Signal(str)

    def __init__(self, device_name: str = None, samplerate: int = 44100,
                 hop_size: int = 512, win_size: int = 2048):
        super().__init__()
        self._device_name = device_name
        self._samplerate = samplerate
        self._hop_size = hop_size
        self._win_size = win_size
        self._running = False

    def stop(self):
        self._running = False

    def run(self):
        try:
            import soundcard as sc
        except ImportError:
            self.sig_error.emit("缺少 soundcard 库，请运行：pip install soundcard")
            return
        try:
            import librosa
        except ImportError:
            self.sig_error.emit("缺少 librosa 库，请先安装：pip install librosa")
            return

        sr = self._samplerate
        hop = self._hop_size
        win = self._win_size
        analysis_buffer = np.zeros(max(win * 4, sr // 2), dtype=np.float32)

        try:
            mic = get_loopback_microphone(self._device_name)
        except Exception as e:
            self.sig_error.emit(f"打开音频设备失败: {e}")
            return

        self.sig_status.emit(f"正在监听: {mic.name}")
        self._running = True

        try:
            with mic.recorder(samplerate=sr, channels=1, blocksize=hop) as recorder:
                while self._running:
                    try:
                        data = recorder.record(numframes=hop)
                        samples = data[:, 0].astype(np.float32)
                        if len(samples) < hop:
                            samples = np.pad(samples, (0, hop - len(samples)))
                    except Exception as e:
                        self.sig_error.emit(f"读取音频失败: {e}")
                        break

                    self.sig_waveform.emit(samples.copy())

                    analysis_buffer = np.roll(analysis_buffer, -len(samples))
                    analysis_buffer[-len(samples):] = samples

                    try:
                        stft = librosa.stft(analysis_buffer, n_fft=win, hop_length=hop, center=False)
                        magnitude = np.abs(stft)
                        mel = librosa.feature.melspectrogram(S=magnitude ** 2, sr=sr, n_mels=64)
                        chroma = librosa.feature.chroma_stft(S=magnitude, sr=sr)
                        onset_env = librosa.onset.onset_strength(S=magnitude, sr=sr)
                        tempo = float(librosa.feature.tempo(onset_envelope=onset_env, sr=sr, hop_length=hop)[0]) if onset_env.size else 0.0
                        centroid = librosa.feature.spectral_centroid(S=magnitude, sr=sr)
                        rolloff = librosa.feature.spectral_rolloff(S=magnitude, sr=sr)
                        rms = librosa.feature.rms(S=magnitude)
                        zcr = librosa.feature.zero_crossing_rate(analysis_buffer, frame_length=win, hop_length=hop)
                    except Exception as e:
                        self.sig_error.emit(f"librosa 分析失败: {e}")
                        break

                    mel_column = mel[:, -1] if mel.ndim == 2 and mel.shape[1] else np.zeros(64, dtype=np.float32)
                    chroma_column = chroma[:, -1] if chroma.ndim == 2 and chroma.shape[1] else np.zeros(12, dtype=np.float32)
                    self.sig_spectrum.emit(mel_column.astype(np.float32))
                    self.sig_chroma.emit(chroma_column.astype(np.float32))
                    self.sig_metrics.emit({
                        "tempo": tempo,
                        "onset_strength": float(onset_env[-1]) if onset_env.size else 0.0,
                        "centroid": float(centroid[0, -1]) if centroid.size else 0.0,
                        "rolloff": float(rolloff[0, -1]) if rolloff.size else 0.0,
                        "rms": float(rms[0, -1]) if rms.size else 0.0,
                        "zcr": float(zcr[0, -1]) if zcr.size else 0.0,
                    })
        except Exception as e:
            self.sig_error.emit(f"音频流异常: {e}")
        finally:
            self._running = False
            self.sig_status.emit("已停止")


# ──────────────────────────────────────────────────────────────
#  设备枚举线程
# ──────────────────────────────────────────────────────────────
class DeviceEnumWorker(QThread):
    sig_devices = Signal(list)  # [(name, id), ...]
    sig_error   = Signal(str)

    def run(self):
        try:
            import soundcard as sc
            speakers = sc.all_speakers()
            result = [(spk.name, spk.id) for spk in speakers]
            self.sig_devices.emit(result)
        except ImportError:
            self.sig_error.emit("soundcard 未安装")
        except Exception as e:
            self.sig_error.emit(str(e))


# ──────────────────────────────────────────────────────────────
#  aubio 页面
# ──────────────────────────────────────────────────────────────
class AubioAnalysisPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: AudioWorker | None = None
        self._enum_worker: DeviceEnumWorker | None = None
        self._classifier_install_worker: OptionalDependencyInstaller | None = None
        self._devices = []
        self._current_bpm = 0.0
        self._pitch_conf_threshold = 0.5
        self._specdesc_methods = ["energy", "hfc", "centroid", "rolloff", "specflux"]
        self._active_device_name = ""
        self._classifier_available = has_optional_classifier_support()

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        # ── 顶部信息行 ──
        top_bar = QHBoxLayout()
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(22, 22)
        if not self.windowIcon().isNull():
            self.icon_label.setPixmap(self.windowIcon().pixmap(20, 20))
        self.status_label = QLabel("就绪 — 选择设备并点击开始")
        self.status_label.setObjectName("fixedLineLabel")
        self.status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.start_btn = QPushButton("▶ 开始")
        self.start_btn.setMinimumHeight(35)
        self.start_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.start_btn.clicked.connect(self._toggle)
        top_bar.addWidget(self.icon_label)
        top_bar.addWidget(self.status_label, 1)
        top_bar.addWidget(self.start_btn)
        root.addLayout(top_bar)

        # ── 设置面板（可折叠，默认展开）──
        self.settings_box = CollapsibleBox("设置", expanded=True)
        grid = QGridLayout()
        grid.setContentsMargins(6, 6, 6, 6)
        grid.setVerticalSpacing(6)

        grid.addWidget(QLabel("扬声器设备:"), 0, 0)
        self.device_combo = QComboBox()
        self.device_combo.addItem("正在枚举...")
        self.device_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.device_combo.currentIndexChanged.connect(self._update_runtime_snapshot)
        grid.addWidget(self.device_combo, 0, 1, 1, 2)
        refresh_btn = QPushButton("刷新")
        refresh_btn.setFixedWidth(50)
        refresh_btn.clicked.connect(self._refresh_devices)
        grid.addWidget(refresh_btn, 0, 3)

        grid.addWidget(QLabel("采样率:"), 1, 0)
        self.sr_combo = QComboBox()
        for sr in [44100, 48000, 22050]:
            self.sr_combo.addItem(str(sr), sr)
        self.sr_combo.currentIndexChanged.connect(self._update_runtime_snapshot)
        grid.addWidget(self.sr_combo, 1, 1)

        grid.addWidget(QLabel("帧大小:"), 1, 2)
        self.hop_spin = QSpinBox()
        self.hop_spin.setRange(128, 4096)
        self.hop_spin.setSingleStep(128)
        self.hop_spin.setValue(512)
        self.hop_spin.valueChanged.connect(self._update_runtime_snapshot)
        grid.addWidget(self.hop_spin, 1, 3)

        grid.addWidget(QLabel("音高置信度阈值:"), 2, 0)
        self.conf_spin = QSpinBox()
        self.conf_spin.setRange(0, 100)
        self.conf_spin.setValue(50)
        self.conf_spin.setSuffix("%")
        self.conf_spin.valueChanged.connect(lambda v: setattr(self, '_pitch_conf_threshold', v / 100.0))
        grid.addWidget(self.conf_spin, 2, 1)

        self.show_waveform_cb = QCheckBox("波形")
        self.show_waveform_cb.setChecked(True)
        self.show_spectrum_cb = QCheckBox("频谱")
        self.show_spectrum_cb.setChecked(True)
        self.show_mfcc_cb = QCheckBox("MFCC")
        self.show_mfcc_cb.setChecked(True)
        self.show_specdesc_cb = QCheckBox("频谱描述符")
        self.show_specdesc_cb.setChecked(True)
        self.show_classifier_cb = QCheckBox("乐器分类")
        self.show_classifier_cb.setChecked(self._classifier_available)
        if not self._classifier_available:
            self.show_classifier_cb.setToolTip("勾选后自动安装可选依赖 panns_inference")
        else:
            self.show_classifier_cb.setToolTip("已安装，可取消勾选以关闭乐器分类")
        self.show_classifier_cb.toggled.connect(self._on_classifier_toggled)
        cb_lay = QHBoxLayout()
        for cb in [self.show_waveform_cb, self.show_spectrum_cb,
                   self.show_mfcc_cb, self.show_specdesc_cb, self.show_classifier_cb]:
            cb_lay.addWidget(cb)
        cb_lay.addStretch(1)
        grid.addLayout(cb_lay, 2, 2, 1, 2)

        self.settings_box.setContentLayout(grid, expanded=True)
        root.addWidget(self.settings_box)

        # ── 摘要卡片 ──
        summary_row = QHBoxLayout()
        self.beat_indicator = BeatIndicator()
        self.note_card = ValueCardWidget("当前音名")
        self.note_card.set_value("--", "等待稳定音高")
        self.instrument_card = ValueCardWidget("当前乐器")
        self.instrument_card.set_value("--", "等待乐器分类")
        self.timbre_widget = HorizontalMetersWidget(title="音色画像")
        summary_row.addWidget(self.beat_indicator, 2)
        summary_row.addWidget(self.note_card, 1)
        summary_row.addWidget(self.instrument_card, 1)
        summary_row.addWidget(self.timbre_widget, 2)
        root.addLayout(summary_row)

        # ── 左列：音高 / 置信度 / 起音 对齐对照 ──
        self.pitch_chart = LineChartWidget(history=150, title="音高 (MIDI 音符号)",
                                           ymin=0, ymax=127, unit="MIDI")
        self.pitch_conf_chart = LineChartWidget(history=150, title="音高置信度",
                                                ymin=0.0, ymax=1.0, unit="")
        self.onset_indicator = OnsetIndicator()

        signal_column = QWidget()
        signal_column_layout = QVBoxLayout(signal_column)
        signal_column_layout.setContentsMargins(0, 0, 0, 0)
        signal_column_layout.setSpacing(4)
        signal_column_layout.addWidget(self._labeled("MIDI 音高", self.pitch_chart), 1)
        signal_column_layout.addWidget(self._labeled("音高置信度", self.pitch_conf_chart), 1)
        signal_column_layout.addWidget(self._labeled("起音检测", self.onset_indicator), 1)

        # ── 右列：波形 / 频谱 / 补充特征 ──
        self.waveform_widget = WaveformWidget(history=300)
        self.spectrogram_widget = SpectrogramWidget(n_bins=128)
        self.rms_chart = LineChartWidget(history=150, title="响度 RMS", ymin=0.0, ymax=0.5, unit="")
        self.zcr_chart = LineChartWidget(history=150, title="过零率 ZCR", ymin=0.0, ymax=0.4, unit="")

        right_column = QWidget()
        right_layout = QVBoxLayout(right_column)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)

        wave_spec_row = QHBoxLayout()
        wave_spec_row.addWidget(self._labeled("波形", self.waveform_widget), 1)
        wave_spec_row.addWidget(self._labeled("频谱图", self.spectrogram_widget), 1)
        right_layout.addLayout(wave_spec_row, 2)

        dynamics_row = QHBoxLayout()
        dynamics_row.addWidget(self._labeled("响度趋势", self.rms_chart), 1)
        dynamics_row.addWidget(self._labeled("过零率趋势", self.zcr_chart), 1)
        right_layout.addLayout(dynamics_row, 1)

        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.addWidget(signal_column)
        main_splitter.addWidget(right_column)
        main_splitter.setSizes([360, 690])

        # MFCC + 频谱描述符
        low_row = QHBoxLayout()
        self.mfcc_chart = BarChartWidget(
            n_bars=13,
            labels=[f"C{i}" for i in range(13)],
            title="MFCC (13 系数)"
        )
        spec_labels = self._specdesc_methods
        self.specdesc_chart = BarChartWidget(
            n_bars=len(spec_labels),
            labels=spec_labels,
            title="频谱描述符"
        )
        self.instrument_widget = HorizontalMetersWidget(title="乐器分类")
        self.instrument_widget.set_items([("等待", 0.0)])
        low_row.addWidget(self.mfcc_chart, 2)
        low_row.addWidget(self.specdesc_chart, 1)
        low_row.addWidget(self.instrument_widget, 1)

        content_panel = QWidget()
        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(4)
        content_layout.addWidget(main_splitter, 3)
        content_layout.addLayout(low_row, 1)

        self.data_box = CollapsibleBox("数据面板", expanded=True)
        self.data_box.setMinimumWidth(300)
        data_layout = QVBoxLayout()
        data_layout.setContentsMargins(6, 6, 6, 6)
        self.data_tree = DataTreeWidget()
        data_layout.addWidget(self.data_tree)
        self.data_box.setContentLayout(data_layout, expanded=True)

        body_splitter = QSplitter(Qt.Horizontal)
        body_splitter.addWidget(content_panel)
        body_splitter.addWidget(self.data_box)
        body_splitter.setSizes([900, 340])
        root.addWidget(body_splitter, 1)

        self._init_data_snapshot()

        # ── 初始化设备枚举 ──
        self._refresh_devices()

    # ──────────────────────────────────────────────────────────
    def _labeled(self, label: str, widget: QWidget) -> QWidget:
        """在 widget 外套一个带标题的 frame"""
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(2)
        lbl = QLabel(label)
        f = lbl.font()
        f.setBold(True)
        f.setPointSize(8)
        lbl.setFont(f)
        lay.addWidget(lbl)
        lay.addWidget(widget)
        return frame

    def _format_number(self, value, decimals: int = 3, suffix: str = "") -> str:
        try:
            number = float(value)
        except Exception:
            return "--"
        if np.isnan(number):
            return "--"
        text = f"{number:.{decimals}f}"
        return f"{text} {suffix}" if suffix else text

    def _set_status_text(self, text: str):
        self.status_label.setText(text)
        self.data_tree.set_value(("运行状态", "状态"), text)

    def _set_data_value(self, path, value):
        self.data_tree.set_value(path, value)

    def _init_data_snapshot(self):
        defaults = {
            ("运行状态", "状态"): "就绪 — 选择设备并点击开始",
            ("运行状态", "监听设备"): "--",
            ("运行状态", "采样率"): f"{self.sr_combo.currentData()} Hz",
            ("运行状态", "帧大小"): str(self.hop_spin.value()),
            ("音高与节拍", "MIDI 音高"): "--",
            ("音高与节拍", "音高置信度"): "0.000",
            ("音高与节拍", "当前音名"): "--",
            ("音高与节拍", "频率"): "--",
            ("音高与节拍", "BPM"): "--",
            ("时域特征", "RMS"): "0.000",
            ("时域特征", "ZCR"): "0.000",
            ("时域特征", "起音"): "等待",
            ("频谱特征", "描述符", "energy"): "0.000",
            ("频谱特征", "描述符", "hfc"): "0.000",
            ("频谱特征", "描述符", "centroid"): "0.000",
            ("频谱特征", "描述符", "rolloff"): "0.000",
            ("频谱特征", "描述符", "specflux"): "0.000",
            ("音色画像", "标签"): "--",
            ("音色画像", "评分", "明亮"): "0%",
            ("音色画像", "评分", "温暖"): "0%",
            ("音色画像", "评分", "打击感"): "0%",
            ("音色画像", "评分", "谐和度"): "0%",
            ("乐器分类", "状态"): "未启用",
            ("乐器分类", "当前乐器"): "--",
        }
        for index in range(13):
            defaults[("频谱特征", "MFCC", f"C{index}")] = "0.000"
        for index in range(CLASSIFIER_PANEL_ITEMS):
            defaults[("乐器分类", f"候选 {index + 1}")] = "--"
        for path, value in defaults.items():
            self._set_data_value(path, value)
        self._set_data_value(("乐器分类", "状态"), "已启用" if self.show_classifier_cb.isChecked() else "未启用")
        self._update_runtime_snapshot()

    def _update_runtime_snapshot(self):
        current_device = "--"
        if self.device_combo.count() > 0:
            current_device = self.device_combo.currentText() or "--"
        self._set_data_value(("运行状态", "监听设备"), current_device)
        sr_value = self.sr_combo.currentData()
        self._set_data_value(("运行状态", "采样率"), f"{sr_value} Hz" if sr_value else "--")
        self._set_data_value(("运行状态", "帧大小"), str(self.hop_spin.value()))

    def _refresh_devices(self):
        if self._enum_worker and self._enum_worker.isRunning():
            self._enum_worker.wait(1000)
        self.device_combo.clear()
        self.device_combo.addItem("正在枚举设备...")
        self.start_btn.setEnabled(False)
        self.start_btn.setText("加载中...")
        self._enum_worker = DeviceEnumWorker()
        self._enum_worker.sig_devices.connect(self._on_devices)
        self._enum_worker.sig_error.connect(self._on_enum_error)
        self._enum_worker.start()

    def _on_devices(self, devices):
        self._devices = devices
        self.device_combo.clear()
        if not devices:
            self.device_combo.addItem("未找到扬声器设备")
            self._set_status_text("未找到扬声器设备，请检查 soundcard 是否安装")
        else:
            for name, dev_id in devices:
                self.device_combo.addItem(name, dev_id)
            self._set_status_text(f"已找到 {len(devices)} 个扬声器设备，请选择后点击开始")
        self._update_runtime_snapshot()
        self.start_btn.setEnabled(True)
        self.start_btn.setText("▶ 开始")

    def _on_enum_error(self, msg: str):
        self._set_status_text(f"枚举设备失败: {msg}")
        self.start_btn.setEnabled(True)
        self.start_btn.setText("▶ 开始")

    def _toggle(self):
        if self._worker and self._worker.isRunning():
            self._stop()
        else:
            self._start()

    def _set_classifier_checked(self, checked: bool):
        self.show_classifier_cb.blockSignals(True)
        self.show_classifier_cb.setChecked(checked)
        self.show_classifier_cb.blockSignals(False)

    def _on_classifier_toggled(self, checked: bool):
        if checked and not self._classifier_available:
            if self._worker and self._worker.isRunning():
                self._set_status_text("请先停止分析，再安装乐器分类模块")
                self._set_classifier_checked(False)
                return
            if self._classifier_install_worker and self._classifier_install_worker.isRunning():
                return
            self._install_classifier_dependencies()
            return

        if checked:
            self.instrument_card.set_value("--", "等待乐器分类")
            self.instrument_widget.set_items([("等待", 0.0)])
            self._set_data_value(("乐器分类", "状态"), "已启用")
        else:
            self.instrument_card.set_value("--", "乐器分类已关闭")
            self.instrument_widget.set_items([("已关闭", 0.0)])
            self._set_data_value(("乐器分类", "状态"), "已关闭")

    def _install_classifier_dependencies(self):
        self.start_btn.setEnabled(False)
        self.show_classifier_cb.setEnabled(False)
        self._set_status_text("正在安装乐器分类模块，首次安装可能较慢...")
        self.instrument_card.set_value("安装中", "正在下载并安装依赖")
        self.instrument_widget.set_items([("安装中", 0.35)])
        self._set_data_value(("乐器分类", "状态"), "安装中")
        self._classifier_install_worker = OptionalDependencyInstaller(OPTIONAL_CLASSIFIER_PACKAGES, self)
        self._classifier_install_worker.sig_done.connect(self._on_classifier_install_finished)
        self._classifier_install_worker.finished.connect(self._on_classifier_install_thread_finished)
        self._classifier_install_worker.start()

    def _on_classifier_install_finished(self, success: bool, message: str):
        self._classifier_available = success and has_optional_classifier_support()
        self.show_classifier_cb.setEnabled(True)
        self.start_btn.setEnabled(True)

        if self._classifier_available:
            self.show_classifier_cb.setToolTip("已安装，可取消勾选以关闭乐器分类")
            self._set_classifier_checked(True)
            self.instrument_card.set_value("--", "等待乐器分类")
            self.instrument_widget.set_items([("等待", 0.0)])
            self._set_status_text(message)
            self._set_data_value(("乐器分类", "状态"), "已启用")
        else:
            self._set_classifier_checked(False)
            self.show_classifier_cb.setToolTip("安装失败，勾选后会重试安装 panns_inference")
            self.instrument_card.set_value("不可用", "乐器分类安装失败")
            self.instrument_widget.set_items([("失败", 1.0)])
            self._set_status_text(f"乐器分类安装失败: {message}")
            self._set_data_value(("乐器分类", "状态"), "安装失败")

    def _on_classifier_install_thread_finished(self):
        self._classifier_install_worker = None

    def _start(self):
        if not self._devices:
            self._set_status_text("请先刷新并选择设备")
            return

        idx = self.device_combo.currentIndex()
        if idx < 0 or idx >= len(self._devices):
            self._set_status_text("请选择有效的扬声器设备")
            return
        if self._classifier_install_worker and self._classifier_install_worker.isRunning():
            self._set_status_text("乐器分类模块正在安装，请稍候")
            return

        device_id = self._devices[idx][1]
        self._active_device_name = self._devices[idx][0]
        self._update_runtime_snapshot()
        if self.show_classifier_cb.isChecked() and not self._classifier_available:
            self.instrument_card.set_value("不可用", "未安装可选库 panns_inference")
            self.instrument_widget.set_items([("未安装", 1.0)])
            self._set_data_value(("乐器分类", "状态"), "不可用")
        sr = self.sr_combo.currentData()
        hop = self.hop_spin.value()
        win = hop * 2

        self._worker = AudioWorker(
            device_name=device_id,
            samplerate=sr,
            hop_size=hop,
            win_size=win,
            enable_classifier=self.show_classifier_cb.isChecked(),
        )
        self._worker.sig_waveform.connect(self._on_waveform)
        self._worker.sig_spectrum.connect(self._on_spectrum)
        self._worker.sig_pitch.connect(self._on_pitch)
        self._worker.sig_beat.connect(self._on_beat)
        self._worker.sig_onset.connect(self._on_onset)
        self._worker.sig_mfcc.connect(self._on_mfcc)
        self._worker.sig_specdesc.connect(self._on_specdesc)
        self._worker.sig_metrics.connect(self._on_metrics)
        self._worker.sig_classifier.connect(self._on_classifier)
        self._worker.sig_status.connect(self._set_status_text)
        self._worker.sig_error.connect(self._on_error)
        self._worker.finished.connect(self._on_worker_finished)
        self._set_status_text("正在启动音频采集与分析...")
        self._worker.start()
        self.start_btn.setText("■ 停止")

    def _stop(self):
        if self._worker:
            self._worker.stop()
            self._worker.wait(2000)
        self.start_btn.setText("▶ 开始")

    def _on_worker_finished(self):
        self.start_btn.setText("▶ 开始")

    def _on_error(self, msg: str):
        self._set_status_text(f"错误: {msg}")
        self.start_btn.setText("▶ 开始")
        self.start_btn.setEnabled(True)

    def _on_waveform(self, samples):
        if self.show_waveform_cb.isChecked():
            self.waveform_widget.push_raw(samples)

    def _on_spectrum(self, mags):
        if self.show_spectrum_cb.isChecked():
            self.spectrogram_widget.push(mags)

    def _on_pitch(self, pitch_val: float, conf: float):
        if conf >= self._pitch_conf_threshold and pitch_val > 0:
            self.pitch_chart.push(pitch_val)
        else:
            self.pitch_chart.push(float('nan'))
        self.pitch_conf_chart.push(conf)
        midi_text = self._format_number(pitch_val, 2) if pitch_val > 0 else "--"
        self._set_data_value(("音高与节拍", "MIDI 音高"), midi_text)
        self._set_data_value(("音高与节拍", "音高置信度"), self._format_number(conf, 3))

    def _on_beat(self, bpm: float):
        self._current_bpm = bpm
        self.beat_indicator.beat(bpm)
        self._set_data_value(("音高与节拍", "BPM"), self._format_number(bpm, 1))

    def _on_onset(self):
        self.onset_indicator.flash()
        self._set_data_value(("时域特征", "起音"), "检测到")

    def _on_mfcc(self, mfcc_data):
        if self.show_mfcc_cb.isChecked():
            self.mfcc_chart.set_values(mfcc_data)
        for index, value in enumerate(list(mfcc_data)[:13]):
            self._set_data_value(("频谱特征", "MFCC", f"C{index}"), self._format_number(value, 3))

    def _on_specdesc(self, desc: dict):
        if self.show_specdesc_cb.isChecked():
            vals = [desc.get(m, 0.0) for m in self._specdesc_methods]
            self.specdesc_chart.set_values(vals)
        for method in self._specdesc_methods:
            self._set_data_value(("频谱特征", "描述符", method), self._format_number(desc.get(method, 0.0), 3))

    def _on_metrics(self, metrics: dict):
        self.rms_chart.push(float(metrics.get("rms", 0.0)))
        self.zcr_chart.push(float(metrics.get("zcr", 0.0)))
        note_name = metrics.get("note_name", "--")
        freq_hz = float(metrics.get("freq_hz", 0.0))
        if note_name != "--" and freq_hz > 0:
            subtitle = f"{freq_hz:.1f} Hz"
        else:
            subtitle = "等待稳定音高"
        self.note_card.set_value(note_name, subtitle)
        self.timbre_widget.set_items(metrics.get("timbre_scores", []))
        self._set_data_value(("时域特征", "RMS"), self._format_number(metrics.get("rms", 0.0), 3))
        self._set_data_value(("时域特征", "ZCR"), self._format_number(metrics.get("zcr", 0.0), 3))
        self._set_data_value(("音高与节拍", "当前音名"), note_name)
        self._set_data_value(("音高与节拍", "频率"), self._format_number(freq_hz, 1, "Hz") if freq_hz > 0 else "--")
        self._set_data_value(("音色画像", "标签"), metrics.get("timbre_label", "--"))
        timbre_scores = dict(metrics.get("timbre_scores", []))
        for label in ["明亮", "温暖", "打击感", "谐和度"]:
            score = clamp01(timbre_scores.get(label, 0.0))
            self._set_data_value(("音色画像", "评分", label), f"{int(score * 100):d}%")

    def _on_classifier(self, payload: dict):
        items = payload.get("items", [])
        label = payload.get("label", "--")
        self.instrument_widget.set_items(items[:CLASSIFIER_METER_ITEMS])
        subtitle = payload.get("subtitle", "")
        self._set_data_value(("乐器分类", "当前乐器"), label if label else "--")
        if label and label != "--":
            if subtitle:
                self.instrument_card.set_value(label, subtitle)
                self._set_data_value(("乐器分类", "状态"), subtitle)
            else:
                detail = items[0][1] if items else 0.0
                self.instrument_card.set_value(label, f"置信度 {detail * 100:.0f}%")
                self._set_status_text(f"正在监听: {self._active_device_name} | 乐器: {label}")
                self._set_data_value(("乐器分类", "状态"), f"置信度 {detail * 100:.0f}%")
        else:
            self.instrument_card.set_value("--", "等待乐器分类")
            self._set_data_value(("乐器分类", "状态"), "等待乐器分类")

        for index in range(CLASSIFIER_PANEL_ITEMS):
            if index < len(items):
                item_label, item_score = items[index]
                text = f"{item_label} ({int(clamp01(item_score) * 100):d}%)"
            else:
                text = "--"
            self._set_data_value(("乐器分类", f"候选 {index + 1}"), text)

    def closeEvent(self, event):
        self._stop()
        if self._enum_worker and self._enum_worker.isRunning():
            self._enum_worker.wait(1000)
        super().closeEvent(event)


def is_optional_module_ready(module_name: str) -> bool:
    if not module_name:
        return False
    if importlib.util.find_spec(module_name) is None:
        return False
    try:
        importlib.import_module(module_name)
        return True
    except Exception:
        return False


class OptionalLibraryPage(QWidget):
    def __init__(self, library_key: str, parent=None):
        super().__init__(parent)
        self._library_key = library_key
        self._config = LIBRARY_PAGE_CONFIGS[library_key]
        self._installer: OptionalDependencyInstaller | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        top_bar = QHBoxLayout()
        self.status_label = QLabel("正在检查依赖状态...")
        self.status_label.setObjectName("fixedLineLabel")
        self.status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.install_btn = QPushButton("安装依赖")
        self.install_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.install_btn.clicked.connect(self._install_dependencies)
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.refresh_btn.clicked.connect(self.refresh_status)
        top_bar.addWidget(self.status_label, 1)
        top_bar.addWidget(self.install_btn)
        top_bar.addWidget(self.refresh_btn)
        root.addLayout(top_bar)

        self.settings_box = CollapsibleBox(f"{self._config['title']} 页面", expanded=True)
        grid = QGridLayout()
        grid.setContentsMargins(6, 6, 6, 6)
        grid.setVerticalSpacing(6)
        grid.addWidget(QLabel("定位:"), 0, 0)
        grid.addWidget(QLabel(self._config["subtitle"]), 0, 1)
        grid.addWidget(QLabel("目标模块:"), 1, 0)
        grid.addWidget(QLabel(self._config.get("module", "--")), 1, 1)
        grid.addWidget(QLabel("状态:"), 2, 0)
        self.ready_value = QLabel("--")
        grid.addWidget(self.ready_value, 2, 1)
        self.settings_box.setContentLayout(grid, expanded=True)
        root.addWidget(self.settings_box)

        self.features_box = CollapsibleBox("功能规划", expanded=True)
        self.feature_view = QTextEdit()
        self.feature_view.setReadOnly(True)
        self.feature_view.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.feature_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        feature_text = [
            f"库: {self._config['title']}",
            f"定位: {self._config['subtitle']}",
            "",
            "计划接入功能:",
        ]
        for item in self._config.get("features", []):
            feature_text.append(f"- {item}")
        feature_text.extend([
            "",
            "当前状态:",
            "- 已加入工作台页面架构",
            "- 依赖可由页面内单独安装",
            "- 共享实时采集与专属图表逻辑将在后续阶段接入",
        ])
        self.feature_view.setPlainText("\n".join(feature_text))
        feature_layout = QVBoxLayout()
        feature_layout.setContentsMargins(0, 0, 0, 0)
        feature_layout.addWidget(self.feature_view)
        self.features_box.setContentLayout(feature_layout, expanded=True)
        root.addWidget(self.features_box, 1)

        self.refresh_status()

    def refresh_status(self):
        module_name = self._config.get("module", "")
        ready = is_optional_module_ready(module_name)
        if ready:
            self.status_label.setText(f"{self._config['title']} 依赖已就绪，页面骨架已加载")
            self.ready_value.setText("可用")
            self.install_btn.setEnabled(False)
        else:
            self.status_label.setText(f"{self._config['title']} 尚未接入运行时分析，请先安装依赖")
            self.ready_value.setText("未安装")
            self.install_btn.setEnabled(True)

    def _install_dependencies(self):
        if self._installer and self._installer.isRunning():
            return
        packages = self._config.get("packages", [])
        if not packages:
            self.status_label.setText("当前页面没有可安装依赖")
            return
        self.install_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.status_label.setText(f"正在安装 {self._config['title']} 依赖...")
        self._installer = OptionalDependencyInstaller(packages, self)
        self._installer.sig_done.connect(self._on_install_done)
        self._installer.finished.connect(self._on_install_finished)
        self._installer.start()

    def _on_install_done(self, success: bool, message: str):
        self.status_label.setText(message if success else f"安装失败: {message}")
        self.refresh_status()

    def _on_install_finished(self):
        self.install_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self._installer = None


class LibrosaAnalysisPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: LibrosaWorker | None = None
        self._enum_worker: DeviceEnumWorker | None = None
        self._devices = []

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        top_bar = QHBoxLayout()
        self.status_label = QLabel("librosa 就绪 — 选择设备并点击开始")
        self.status_label.setObjectName("fixedLineLabel")
        self.status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.start_btn = QPushButton("▶ 开始")
        self.start_btn.setMinimumHeight(35)
        self.start_btn.clicked.connect(self._toggle)
        top_bar.addWidget(self.status_label, 1)
        top_bar.addWidget(self.start_btn)
        root.addLayout(top_bar)

        self.settings_box = CollapsibleBox("librosa 设置", expanded=True)
        grid = QGridLayout()
        grid.setContentsMargins(6, 6, 6, 6)
        grid.setVerticalSpacing(6)

        grid.addWidget(QLabel("扬声器设备:"), 0, 0)
        self.device_combo = QComboBox()
        self.device_combo.addItem("正在枚举...")
        grid.addWidget(self.device_combo, 0, 1, 1, 2)
        refresh_btn = QPushButton("刷新")
        refresh_btn.setFixedWidth(50)
        refresh_btn.clicked.connect(self._refresh_devices)
        grid.addWidget(refresh_btn, 0, 3)

        grid.addWidget(QLabel("采样率:"), 1, 0)
        self.sr_combo = QComboBox()
        for sr in [22050, 44100, 48000]:
            self.sr_combo.addItem(str(sr), sr)
        self.sr_combo.setCurrentIndex(1)
        grid.addWidget(self.sr_combo, 1, 1)

        grid.addWidget(QLabel("帧大小:"), 1, 2)
        self.hop_spin = QSpinBox()
        self.hop_spin.setRange(256, 4096)
        self.hop_spin.setSingleStep(256)
        self.hop_spin.setValue(512)
        grid.addWidget(self.hop_spin, 1, 3)

        self.settings_box.setContentLayout(grid, expanded=True)
        root.addWidget(self.settings_box)

        summary_row = QHBoxLayout()
        self.tempo_card = ValueCardWidget("Tempo")
        self.tempo_card.set_value("--", "等待节奏估计")
        self.onset_card = ValueCardWidget("Onset Strength")
        self.onset_card.set_value("--", "等待块处理")
        self.texture_card = ValueCardWidget("频谱重心")
        self.texture_card.set_value("--", "等待谱分析")
        summary_row.addWidget(self.tempo_card, 1)
        summary_row.addWidget(self.onset_card, 1)
        summary_row.addWidget(self.texture_card, 1)
        root.addLayout(summary_row)

        self.waveform_widget = WaveformWidget(history=300)
        self.mel_widget = SpectrogramWidget(n_bins=64)
        self.chroma_chart = BarChartWidget(n_bars=12, labels=[f"C{i}" for i in range(12)], title="Chroma")
        self.rms_chart = LineChartWidget(history=150, title="RMS", ymin=0.0, ymax=0.5)

        body_splitter = QSplitter(Qt.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)
        left_layout.addWidget(self._labeled("波形", self.waveform_widget), 1)
        left_layout.addWidget(self._labeled("Mel 频谱", self.mel_widget), 2)
        left_layout.addWidget(self._labeled("RMS 趋势", self.rms_chart), 1)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)
        right_layout.addWidget(self._labeled("Chroma", self.chroma_chart), 2)

        self.data_box = CollapsibleBox("数据面板", expanded=True)
        self.data_box.setMinimumWidth(300)
        data_layout = QVBoxLayout()
        data_layout.setContentsMargins(6, 6, 6, 6)
        self.data_tree = DataTreeWidget()
        data_layout.addWidget(self.data_tree)
        self.data_box.setContentLayout(data_layout, expanded=True)
        right_layout.addWidget(self.data_box, 3)

        body_splitter.addWidget(left)
        body_splitter.addWidget(right)
        body_splitter.setSizes([760, 360])
        root.addWidget(body_splitter, 1)

        self._init_data_tree()
        self._refresh_devices()

    def _labeled(self, label: str, widget: QWidget) -> QWidget:
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        title = QLabel(label)
        font = title.font()
        font.setBold(True)
        font.setPointSize(8)
        title.setFont(font)
        layout.addWidget(title)
        layout.addWidget(widget)
        return frame

    def _init_data_tree(self):
        defaults = {
            ("运行状态", "状态"): "librosa 就绪",
            ("运行状态", "监听设备"): "--",
            ("运行状态", "采样率"): f"{self.sr_combo.currentData()} Hz",
            ("运行状态", "帧大小"): str(self.hop_spin.value()),
            ("音乐特征", "Tempo"): "--",
            ("音乐特征", "Onset Strength"): "--",
            ("音乐特征", "RMS"): "--",
            ("音乐特征", "Spectral Centroid"): "--",
            ("音乐特征", "Spectral Rolloff"): "--",
        }
        for index in range(12):
            defaults[("音乐特征", "Chroma", f"Bin {index + 1}")] = "0.000"
        for path, value in defaults.items():
            self.data_tree.set_value(path, value)

    def _set_status(self, text: str):
        self.status_label.setText(text)
        self.data_tree.set_value(("运行状态", "状态"), text)

    def _refresh_devices(self):
        if self._enum_worker and self._enum_worker.isRunning():
            self._enum_worker.wait(1000)
        self.device_combo.clear()
        self.device_combo.addItem("正在枚举设备...")
        self.start_btn.setEnabled(False)
        self.start_btn.setText("加载中...")
        self._enum_worker = DeviceEnumWorker()
        self._enum_worker.sig_devices.connect(self._on_devices)
        self._enum_worker.sig_error.connect(self._on_enum_error)
        self._enum_worker.start()

    def _on_devices(self, devices):
        self._devices = devices
        self.device_combo.clear()
        if not devices:
            self.device_combo.addItem("未找到扬声器设备")
            self._set_status("未找到扬声器设备，请检查 soundcard 是否安装")
        else:
            for name, dev_id in devices:
                self.device_combo.addItem(name, dev_id)
            self._set_status(f"已找到 {len(devices)} 个扬声器设备，请选择后点击开始")
        self.start_btn.setEnabled(True)
        self.start_btn.setText("▶ 开始")

    def _on_enum_error(self, msg: str):
        self._set_status(f"枚举设备失败: {msg}")
        self.start_btn.setEnabled(True)
        self.start_btn.setText("▶ 开始")

    def _toggle(self):
        if self._worker and self._worker.isRunning():
            self._stop()
        else:
            self._start()

    def _start(self):
        if not self._devices:
            self._set_status("请先刷新并选择设备")
            return
        idx = self.device_combo.currentIndex()
        if idx < 0 or idx >= len(self._devices):
            self._set_status("请选择有效的扬声器设备")
            return

        device_id = self._devices[idx][1]
        sr = self.sr_combo.currentData()
        hop = self.hop_spin.value()
        self.data_tree.set_value(("运行状态", "监听设备"), self._devices[idx][0])
        self.data_tree.set_value(("运行状态", "采样率"), f"{sr} Hz")
        self.data_tree.set_value(("运行状态", "帧大小"), str(hop))

        self._worker = LibrosaWorker(device_name=device_id, samplerate=sr, hop_size=hop, win_size=hop * 4)
        self._worker.sig_waveform.connect(self._on_waveform)
        self._worker.sig_spectrum.connect(self._on_spectrum)
        self._worker.sig_chroma.connect(self._on_chroma)
        self._worker.sig_metrics.connect(self._on_metrics)
        self._worker.sig_status.connect(self._set_status)
        self._worker.sig_error.connect(self._on_error)
        self._worker.finished.connect(self._on_finished)
        self._set_status("正在启动 librosa 实时分析...")
        self._worker.start()
        self.start_btn.setText("■ 停止")

    def _stop(self):
        if self._worker:
            self._worker.stop()
            self._worker.wait(2000)
        self.start_btn.setText("▶ 开始")

    def _on_finished(self):
        self.start_btn.setText("▶ 开始")

    def _on_error(self, msg: str):
        self._set_status(f"错误: {msg}")
        self.start_btn.setEnabled(True)
        self.start_btn.setText("▶ 开始")

    def _on_waveform(self, samples):
        self.waveform_widget.push_raw(samples)

    def _on_spectrum(self, mel_column):
        self.mel_widget.push(np.asarray(mel_column, dtype=np.float32))

    def _on_chroma(self, chroma_column):
        self.chroma_chart.set_values(chroma_column)
        for index, value in enumerate(list(chroma_column)[:12]):
            self.data_tree.set_value(("音乐特征", "Chroma", f"Bin {index + 1}"), f"{float(value):.3f}")

    def _on_metrics(self, metrics: dict):
        tempo = float(metrics.get("tempo", 0.0))
        onset_strength = float(metrics.get("onset_strength", 0.0))
        centroid = float(metrics.get("centroid", 0.0))
        rolloff = float(metrics.get("rolloff", 0.0))
        rms = float(metrics.get("rms", 0.0))
        self.tempo_card.set_value(f"{tempo:.1f}", "BPM")
        self.onset_card.set_value(f"{onset_strength:.3f}", "当前块强度")
        self.texture_card.set_value(f"{centroid:.1f}", "Hz")
        self.rms_chart.push(rms)
        self.data_tree.set_value(("音乐特征", "Tempo"), f"{tempo:.1f}")
        self.data_tree.set_value(("音乐特征", "Onset Strength"), f"{onset_strength:.3f}")
        self.data_tree.set_value(("音乐特征", "RMS"), f"{rms:.3f}")
        self.data_tree.set_value(("音乐特征", "Spectral Centroid"), f"{centroid:.1f} Hz")
        self.data_tree.set_value(("音乐特征", "Spectral Rolloff"), f"{rolloff:.1f} Hz")

    def closeEvent(self, event):
        self._stop()
        if self._enum_worker and self._enum_worker.isRunning():
            self._enum_worker.wait(1000)
        super().closeEvent(event)


class AudioWorkbenchWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("音频分析工作台")
        self.resize(1480, 920)

        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(180)
        self.sidebar.setSpacing(2)
        self.sidebar.setAlternatingRowColors(False)
        self.sidebar.setUniformItemSizes(True)

        for key in ["aubio", "librosa", "audioflux", "madmom"]:
            cfg = LIBRARY_PAGE_CONFIGS[key]
            item = QListWidgetItem(f"{cfg['title']}\n{cfg['subtitle']}")
            item.setData(Qt.UserRole, key)
            self.sidebar.addItem(item)

        self.page_stack = QStackedWidget()
        self.aubio_page = AubioAnalysisPage(self)
        self.librosa_page = LibrosaAnalysisPage(self)
        self.audioflux_page = OptionalLibraryPage("audioflux", self)
        self.madmom_page = OptionalLibraryPage("madmom", self)

        self.page_stack.addWidget(self.aubio_page)
        self.page_stack.addWidget(self.librosa_page)
        self.page_stack.addWidget(self.audioflux_page)
        self.page_stack.addWidget(self.madmom_page)

        self.sidebar.currentRowChanged.connect(self.page_stack.setCurrentIndex)
        self.sidebar.setCurrentRow(0)

        root.addWidget(self.sidebar)
        root.addWidget(self.page_stack, 1)

    def closeEvent(self, event):
        self.aubio_page.close()
        super().closeEvent(event)


# ──────────────────────────────────────────────────────────────
#  入口
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 应用图标（Windows 任务栏）
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    win = AudioWorkbenchWindow()
    win.show()
    sys.exit(app.exec())
