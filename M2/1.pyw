"""
圆形频谱可视化 - PyOpenGL 实现
可独立运行（使用 visualizer_config.json 的默认参数）
也可被主框架调用（通过 Queue 接收实时配置）
"""

import sys
import json
import colorsys
import ctypes
from pathlib import Path
import queue
import time

import numpy as np
import pyaudiowpatch as pyaudio
from scipy.fft import fft as scipy_fft
from scipy.interpolate import BSpline

from OpenGL import GL

from PySide6.QtCore import QPoint, QPointF, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPainterPath, QPen, QPolygon, QSurfaceFormat
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import QApplication, QWidget


try:
    import cupy as cp

    _HAS_GPU = True
    cp.fft.fft(cp.zeros(2048))
    print("✓ CuPy 可用 — 启用 GPU FFT")
except Exception:
    _HAS_GPU = False
    print("⚠ CuPy 不可用 — 使用 CPU FFT")


CONFIG_FILE = Path(__file__).parent / "visualizer_config.json"

_DEFAULT_CONFIG = {
    "width": 0,
    "height": 0,
    "alpha": 255,
    "ui_alpha": 180,
    "global_scale": 1.0,
    "pos_x": -1,
    "pos_y": -1,
    "drag_adjust_mode": False,
    "bg_transparent": True,
    "always_on_top": True,
    "num_bars": 64,
    "smoothing": 0.7,
    "damping": 0.85,
    "spring_strength": 0.3,
    "gravity": 0.5,
    "rotation_base": 1.0,
    "main_radius_scale": 1.0,
    "bar_height_min": 0,
    "bar_height_max": 500,
    "color_scheme": "rainbow",
    "gradient_points": [(0.0, (255, 0, 128)), (1.0, (0, 255, 255))],
    "gradient_enabled": True,
    "gradient_mode": "frequency",
    "color_dynamic": False,
    "color_cycle_speed": 1.0,
    "color_cycle_pow": 2.0,
    "color_cycle_a1": True,
    "circle_radius": 150,
    "circle_segments": 1,
    "circle_a1_rotation": True,
    "circle_a1_radius": True,
    "radius_damping": 0.92,
    "radius_spring": 0.15,
    "radius_gravity": 0.3,
    "bar_length_min": 0,
    "bar_length_max": 300,
    "freq_min": 20,
    "freq_max": 20000,
    "a1_time_window": 10,
    "k2_enabled": False,
    "k2_pow": 1.0,
    "master_visible": True,
    "c1_on": True,
    "c1_color": (100, 180, 255),
    "c1_alpha": 100,
    "c1_thick": 1,
    "c1_fill": False,
    "c1_fill_alpha": 30,
    "c1_step": 2,
    "c1_decay": 0.995,
    "c1_rot_speed": 1.0,
    "c1_rot_pow": 0.5,
    "c2_on": False,
    "c2_color": (150, 220, 255),
    "c2_alpha": 150,
    "c2_thick": 2,
    "c2_fill": False,
    "c2_fill_alpha": 50,
    "c2_step": 2,
    "c2_rot_speed": 1.0,
    "c2_rot_pow": 0.5,
    "c3_on": False,
    "c3_color": (255, 255, 255),
    "c3_alpha": 60,
    "c3_thick": 1,
    "c3_fill": False,
    "c3_fill_alpha": 20,
    "c3_rot_speed": 1.0,
    "c3_rot_pow": 0.5,
    "c4_on": True,
    "c4_color": (255, 255, 255),
    "c4_alpha": 180,
    "c4_thick": 2,
    "c4_fill": True,
    "c4_fill_alpha": 60,
    "c4_step": 2,
    "c4_rot_speed": 1.0,
    "c4_rot_pow": 0.5,
    "c5_on": True,
    "c5_color": (255, 200, 100),
    "c5_alpha": 100,
    "c5_thick": 1,
    "c5_fill": False,
    "c5_fill_alpha": 30,
    "c5_step": 2,
    "c5_decay": 0.995,
    "c5_rot_speed": 1.0,
    "c5_rot_pow": 0.5,
    "b12_on": False,
    "b12_thick": 2,
    "b12_fixed": False,
    "b12_fixed_len": 30,
    "b12_from_start": True,
    "b12_from_end": False,
    "b12_from_center": False,
    "b23_on": False,
    "b23_thick": 3,
    "b23_fixed": False,
    "b23_fixed_len": 30,
    "b23_from_start": True,
    "b23_from_end": False,
    "b23_from_center": False,
    "b34_on": True,
    "b34_thick": 3,
    "b34_fixed": False,
    "b34_fixed_len": 30,
    "b34_from_start": True,
    "b34_from_end": False,
    "b34_from_center": False,
    "b45_on": False,
    "b45_thick": 2,
    "b45_fixed": False,
    "b45_fixed_len": 30,
    "b45_from_start": True,
    "b45_from_end": False,
    "b45_from_center": False,
}


def _load_config():
    import copy

    cfg = copy.deepcopy(_DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as file_obj:
                cfg.update(json.load(file_obj))
        except Exception:
            pass
    return cfg


class OverlayControlLayer(QWidget):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

    def paintEvent(self, _event):
        if not self.owner.config.get("drag_adjust_mode", False):
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self.owner.drag_handle_rect()
        hover = self.owner.drag_handle_hover
        base_alpha = max(60, min(235, int(self.owner.ui_bg_alpha)))

        bg = QColor(70, 70, 90, min(245, base_alpha + 25)) if hover else QColor(50, 50, 60, base_alpha)
        border = QColor(180, 200, 255) if hover else QColor(120, 130, 160)
        arrow = QColor(220, 230, 255) if hover else QColor(160, 170, 200)
        label = QColor(200, 210, 240)

        painter.setPen(QPen(border, 2))
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, 12, 12)

        cx = rect.center().x()
        cy = rect.center().y()
        arm = 16
        head = 5

        painter.setPen(QPen(arrow, 2))
        painter.drawLine(QPoint(cx, cy - arm), QPoint(cx, cy - 3))
        painter.drawLine(QPoint(cx, cy + 3), QPoint(cx, cy + arm))
        painter.drawLine(QPoint(cx - arm, cy), QPoint(cx - 3, cy))
        painter.drawLine(QPoint(cx + 3, cy), QPoint(cx + arm, cy))

        painter.setBrush(arrow)
        painter.drawPolygon(QPolygon([QPoint(cx, cy - arm - head), QPoint(cx - head, cy - arm), QPoint(cx + head, cy - arm)]))
        painter.drawPolygon(QPolygon([QPoint(cx, cy + arm + head), QPoint(cx - head, cy + arm), QPoint(cx + head, cy + arm)]))
        painter.drawPolygon(QPolygon([QPoint(cx - arm - head, cy), QPoint(cx - arm, cy - head), QPoint(cx - arm, cy + head)]))
        painter.drawPolygon(QPolygon([QPoint(cx + arm + head, cy), QPoint(cx + arm, cy - head), QPoint(cx + arm, cy + head)]))
        painter.drawEllipse(QPoint(cx, cy), 2, 2)

        painter.setPen(label)
        text_rect = rect.adjusted(0, arm + head + 6, 0, 28)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, "拖动")

    def mousePressEvent(self, event):
        if not self.owner.config.get("drag_adjust_mode", False):
            event.ignore()
            return
        if event.button() == Qt.MouseButton.LeftButton and self.owner.drag_handle_rect().contains(event.position().toPoint()):
            self.owner.dragging = True
            self.owner.drag_last_global = event.globalPosition().toPoint()
            self.grabMouse()
            event.accept()
            return
        event.ignore()

    def mouseMoveEvent(self, event):
        if not self.owner.config.get("drag_adjust_mode", False):
            event.ignore()
            return

        point = event.position().toPoint()
        self.owner.drag_handle_hover = self.owner.drag_handle_rect().contains(point)
        if self.owner.dragging:
            current = event.globalPosition().toPoint()
            last = self.owner.drag_last_global or current
            delta = current - last
            self.owner.drag_last_global = current
            self.owner.move_center_by(delta.x(), delta.y())

        self.update()
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.owner.dragging:
            self.owner.dragging = False
            self.owner.drag_last_global = None
            self.releaseMouse()
            self.update()
            event.accept()
            return
        event.ignore()

    def leaveEvent(self, _event):
        if not self.owner.dragging:
            self.owner.drag_handle_hover = False
            self.update()


class OpenGLVisualizerWidget(QOpenGLWidget):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)

    def initializeGL(self):
        GL.glClearColor(0.0, 0.0, 0.0, 0.0)
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        GL.glEnable(GL.GL_LINE_SMOOTH)
        GL.glHint(GL.GL_LINE_SMOOTH_HINT, GL.GL_NICEST)
        GL.glEnable(GL.GL_MULTISAMPLE)

    def resizeGL(self, width, height):
        GL.glViewport(0, 0, width, height)

    def paintGL(self):
        state = self.owner.render_state

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.beginNativePainting()

        GL.glViewport(0, 0, self.width(), self.height())
        clear_alpha = 0.0 if self.owner.config.get("bg_transparent", True) else 1.0
        GL.glClearColor(0.0, 0.0, 0.0, clear_alpha)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)

        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glLoadIdentity()
        GL.glOrtho(0.0, float(self.width()), float(self.height()), 0.0, -1.0, 1.0)

        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glLoadIdentity()

        GL.glFlush()
        if state:
            center = state.get("center", (self.width() * 0.5, self.height() * 0.5))
            for fill_item in state.get("fills", []):
                self.owner._gl_draw_radial_fill(center, fill_item["points"], fill_item["color"])
            GL.glFlush()

        painter.endNativePainting()

        if state:
            for bar_item in state.get("bars", []):
                self.owner._paint_segments(painter, bar_item["segments"], bar_item["thickness"])

            for line_item in state.get("lines", []):
                self.owner._paint_line_loop(painter, line_item["points"], line_item["color"], line_item["thickness"])

        painter.end()


class CircularVisualizerWindow(QWidget):
    def __init__(self, config_queue=None, status_queue=None):
        super().__init__(None)
        self.config_queue = config_queue
        self.status_queue = status_queue

        if config_queue and not config_queue.empty():
            self.config = config_queue.get()
        else:
            self.config = _load_config()

        screen = QGuiApplication.primaryScreen().geometry()
        width = self.config.get("width", 0)
        height = self.config.get("height", 0)
        self.WIDTH = width if width > 0 else screen.width()
        self.HEIGHT = height if height > 0 else screen.height()

        self.setWindowTitle("圆形频谱 - PyOpenGL")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.resize(self.WIDTH, self.HEIGHT)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.gl_widget = OpenGLVisualizerWidget(self)
        self.overlay = OverlayControlLayer(self)

        self.window_alpha = int(self.config.get("alpha", 255))
        self.ui_bg_alpha = int(self.config.get("ui_alpha", 180))

        self.dragging = False
        self.drag_last_global = None
        self.drag_handle_hover = False

        self.center_x = self.config.get("pos_x", -1)
        self.center_y = self.config.get("pos_y", -1)
        if self.center_x < 0:
            self.center_x = self.WIDTH * 0.5
        if self.center_y < 0:
            self.center_y = self.HEIGHT * 0.5

        self.CHUNK = 2048
        self.RATE = 44100
        self.audio_queue = queue.Queue()
        self.channel_count = 2

        self.NUM_BARS = int(self.config.get("num_bars", 64))
        self.colors = []
        self.color_cycle_hue = 0.0

        self.bar_heights = np.zeros(self.NUM_BARS, dtype=float)
        self.bar_velocities = np.zeros(self.NUM_BARS, dtype=float)
        self.peak_outer_heights = np.zeros(self.NUM_BARS, dtype=float)
        self.peak_inner_heights = np.zeros(self.NUM_BARS, dtype=float)

        self.smoothing_factor = float(self.config.get("smoothing", 0.7))
        self.damping = float(self.config.get("damping", 0.85))
        self.spring_strength = float(self.config.get("spring_strength", 0.3))
        self.gravity = float(self.config.get("gravity", 0.5))

        self.a1_time_window = float(self.config.get("a1_time_window", 10))
        self.loudness_history = []
        self.a1_value = 0.0
        self.prev_a1_value = 0.0
        self.k2_value = 0.0
        self.last_status_send = time.time()

        self.layer_rotations = {index: 0.0 for index in range(1, 6)}
        self.current_radius = float(self.config.get("circle_radius", 150))
        self.radius_velocity = 0.0

        self.render_state = {"center": (self.center_x, self.center_y), "fills": [], "bars": [], "lines": []}
        self._window_ready = False

        self._update_colors()
        self._init_audio()

        self.frame_timer = QTimer(self)
        self.frame_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.frame_timer.timeout.connect(self._tick)

    def resizeEvent(self, event):
        self.gl_widget.setGeometry(0, 0, self.width(), self.height())
        self.overlay.setGeometry(0, 0, self.width(), self.height())
        self.overlay.raise_()
        super().resizeEvent(event)

    def closeEvent(self, event):
        self.frame_timer.stop()
        self._cleanup()
        event.accept()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Q):
            self.close()
            return
        super().keyPressEvent(event)

    def run(self):
        self.show()
        self.overlay.raise_()
        self.frame_timer.start(16)
        QTimer.singleShot(0, self._finalize_window)

    def _finalize_window(self):
        if self._window_ready:
            return
        self._window_ready = True
        self._center_window(reset_visual_center=True)
        self._apply_window_styles(force=True)
        self._send_status()

    def _init_audio(self):
        print("正在初始化音频设备...")
        self.p = pyaudio.PyAudio()
        try:
            wasapi_info = self.p.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_speakers = self.p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
            if not default_speakers["isLoopbackDevice"]:
                for loopback in self.p.get_loopback_device_info_generator():
                    if default_speakers["name"] in loopback["name"]:
                        default_speakers = loopback
                        break
            self.device_info = default_speakers
            self.RATE = int(self.device_info["defaultSampleRate"])
            self.channel_count = max(1, int(self.device_info.get("maxInputChannels", 2) or 2))
            print(f"使用设备: {self.device_info['name']}")
        except Exception as exc:
            print(f"获取音频设备失败: {exc}")
            raise

        self.stream = self.p.open(
            format=pyaudio.paInt16,
            channels=self.channel_count,
            rate=self.RATE,
            frames_per_buffer=self.CHUNK,
            input=True,
            input_device_index=self.device_info["index"],
            stream_callback=self._audio_callback,
        )
        self.stream.start_stream()
        print("✓ 音频捕获已启动")

    def _audio_callback(self, in_data, _frame_count, _time_info, _status):
        if in_data:
            self.audio_queue.put(np.frombuffer(in_data, dtype=np.int16))
        return (in_data, pyaudio.paContinue)

    def _pull_latest_audio_frame(self):
        if self.audio_queue.empty():
            return None
        try:
            return self.audio_queue.get_nowait()
        except queue.Empty:
            return None

    def _process_audio(self, audio_data):
        if self.channel_count > 1 and len(audio_data) % self.channel_count == 0:
            audio_data = audio_data.reshape(-1, self.channel_count).mean(axis=1)
        if len(audio_data) >= self.CHUNK:
            audio_data = audio_data[: self.CHUNK]
        else:
            audio_data = np.pad(audio_data, (0, self.CHUNK - len(audio_data)))

        loudness = np.sqrt(np.mean(audio_data.astype(float) ** 2))
        self._update_a1(loudness)

        windowed = audio_data * np.hamming(len(audio_data))
        if _HAS_GPU:
            try:
                gpu_window = cp.asarray(windowed)
                spectrum = cp.asnumpy(cp.abs(cp.fft.fft(gpu_window))[: self.CHUNK // 2])
            except Exception:
                spectrum = np.abs(scipy_fft(windowed))[: self.CHUNK // 2]
        else:
            spectrum = np.abs(scipy_fft(windowed))[: self.CHUNK // 2]

        freq_res = self.RATE / self.CHUNK
        f_lo = max(1, int(self.config.get("freq_min", 20) / freq_res))
        f_hi = min(len(spectrum), int(self.config.get("freq_max", 20000) / freq_res))
        if f_hi <= f_lo:
            f_hi = f_lo + 1

        sub = spectrum[f_lo:f_hi]
        bins = np.logspace(np.log10(1), np.log10(max(2, len(sub))), self.NUM_BARS + 1, dtype=int)

        bar_values = np.zeros(self.NUM_BARS, dtype=float)
        for index in range(self.NUM_BARS):
            start = bins[index]
            end = bins[index + 1]
            if end > start:
                bar_values[index] = np.mean(sub[start:end])
        return bar_values

    def _update_a1(self, loudness):
        now = time.time()
        self.loudness_history.append((now, loudness))
        cutoff = now - self.a1_time_window
        self.loudness_history = [(stamp, value) for stamp, value in self.loudness_history if stamp >= cutoff]

        previous = self.a1_value
        self.a1_value = np.mean([value for _, value in self.loudness_history]) if self.loudness_history else 0.0
        delta = self.a1_value - previous
        power = float(self.config.get("k2_pow", 1.0))
        self.k2_value = np.sign(delta) * (abs(delta) ** power)

    @property
    def effective_a1(self):
        if self.config.get("k2_enabled", False):
            return self.k2_value
        return self.a1_value

    def _send_status(self):
        if not self.status_queue or self.status_queue.full():
            return
        try:
            while not self.status_queue.empty():
                try:
                    self.status_queue.get_nowait()
                except Exception:
                    break
            self.status_queue.put(
                {
                    "a1": float(self.a1_value),
                    "k2": float(self.k2_value),
                    "pos_x": int(round(self.center_x)),
                    "pos_y": int(round(self.center_y)),
                }
            )
        except Exception:
            pass

    def _update_colors(self):
        scheme = self.config.get("color_scheme", "rainbow")
        gradient_enabled = self.config.get("gradient_enabled", True)
        color_dynamic = self.config.get("color_dynamic", False)
        self.colors = []

        if scheme == "custom":
            points = sorted(
                self.config.get("gradient_points", [(0.0, (255, 0, 128)), (1.0, (0, 255, 255))]),
                key=lambda item: item[0],
            )
            if not gradient_enabled:
                base = tuple(points[0][1])
                if color_dynamic:
                    hue, sat, val = colorsys.rgb_to_hsv(base[0] / 255, base[1] / 255, base[2] / 255)
                    for _ in range(self.NUM_BARS):
                        next_hue = (hue + self.color_cycle_hue) % 1.0
                        rgb = colorsys.hsv_to_rgb(next_hue, sat, val)
                        self.colors.append(tuple(int(channel * 255) for channel in rgb))
                else:
                    self.colors = [base] * self.NUM_BARS
            else:
                for index in range(self.NUM_BARS):
                    ratio = index / max(1, self.NUM_BARS)
                    base = self._interpolate_color(ratio, points)
                    if color_dynamic:
                        hue, sat, val = colorsys.rgb_to_hsv(base[0] / 255, base[1] / 255, base[2] / 255)
                        next_hue = (hue + self.color_cycle_hue) % 1.0
                        rgb = colorsys.hsv_to_rgb(next_hue, sat, val)
                        self.colors.append(tuple(int(channel * 255) for channel in rgb))
                    else:
                        self.colors.append(base)
            return

        for index in range(self.NUM_BARS):
            ratio = index / max(1, self.NUM_BARS)
            if scheme == "rainbow":
                hue = (ratio + self.color_cycle_hue) % 1.0 if color_dynamic else ratio
                rgb = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
            elif scheme == "fire":
                rgb = (1.0, ratio * 0.8, ratio * 0.2)
                if color_dynamic:
                    hue, sat, val = colorsys.rgb_to_hsv(*rgb)
                    rgb = colorsys.hsv_to_rgb((hue + self.color_cycle_hue) % 1.0, sat, val)
            elif scheme == "ice":
                rgb = (ratio * 0.3, ratio * 0.7, 1.0)
                if color_dynamic:
                    hue, sat, val = colorsys.rgb_to_hsv(*rgb)
                    rgb = colorsys.hsv_to_rgb((hue + self.color_cycle_hue) % 1.0, sat, val)
            elif scheme == "neon":
                hue = ((ratio + 0.5) % 1.0 + self.color_cycle_hue) % 1.0 if color_dynamic else (ratio + 0.5) % 1.0
                rgb = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
            else:
                rgb = colorsys.hsv_to_rgb(ratio, 1.0, 1.0)
            self.colors.append(tuple(int(channel * 255) for channel in rgb))

    @staticmethod
    def _interpolate_color(ratio, points):
        for index in range(len(points) - 1):
            pos1, color1 = points[index]
            pos2, color2 = points[index + 1]
            if pos1 <= ratio <= pos2:
                blend = (ratio - pos1) / (pos2 - pos1) if (pos2 - pos1) > 0 else 0.0
                return (
                    int(color1[0] * (1 - blend) + color2[0] * blend),
                    int(color1[1] * (1 - blend) + color2[1] * blend),
                    int(color1[2] * (1 - blend) + color2[2] * blend),
                )
        return tuple(points[0][1]) if ratio <= points[0][0] else tuple(points[-1][1])

    def _get_color_for_bar(self, bar_index, bar_height=None):
        scheme = self.config.get("color_scheme", "rainbow")
        gradient_mode = self.config.get("gradient_mode", "frequency")

        if scheme != "custom" or gradient_mode != "height":
            return self.colors[bar_index] if bar_index < len(self.colors) else (255, 255, 255)

        if bar_height is None:
            bar_height = self.bar_heights[bar_index]
        min_height = self.config.get("bar_height_min", 0)
        max_height = self.config.get("bar_height_max", 500)
        ratio = max(0.0, min(1.0, (bar_height - min_height) / (max_height - min_height))) if max_height > min_height else 0.0

        points = sorted(
            self.config.get("gradient_points", [(0.0, (255, 0, 128)), (1.0, (0, 255, 255))]),
            key=lambda item: item[0],
        )
        base = self._interpolate_color(ratio, points)

        if self.config.get("color_dynamic", False):
            hue, sat, val = colorsys.rgb_to_hsv(base[0] / 255, base[1] / 255, base[2] / 255)
            rgb = colorsys.hsv_to_rgb((hue + self.color_cycle_hue) % 1.0, sat, val)
            return tuple(int(channel * 255) for channel in rgb)
        return base

    def _center_window(self, reset_visual_center=False):
        screen = QGuiApplication.primaryScreen().geometry()
        if self.width() >= screen.width() or self.height() >= screen.height():
            self.move(screen.left(), screen.top())
        else:
            x = screen.left() + (screen.width() - self.width()) // 2
            y = screen.top() + (screen.height() - self.height()) // 2
            self.move(x, y)

        if reset_visual_center:
            self.center_x = self.width() * 0.5
            self.center_y = self.height() * 0.5

    def drag_handle_rect(self):
        size = 92
        cx = int(round(self.center_x))
        cy = int(round(self.center_y))
        return QRect(cx - size // 2, cy - size // 2, size, size)

    def move_center_by(self, dx, dy):
        if dx == 0 and dy == 0:
            return
        self.center_x += dx
        self.center_y += dy
        self._send_status()
        self.overlay.update()

    def _apply_window_styles(self, force=False):
        if not self._window_ready and not force:
            return

        hwnd = int(self.winId())
        user32 = ctypes.windll.user32
        GWL_EXSTYLE = -20
        WS_EX_LAYERED = 0x00080000
        WS_EX_TRANSPARENT = 0x00000020
        HWND_TOPMOST = -1
        HWND_NOTOPMOST = -2
        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        SWP_NOACTIVATE = 0x0010
        SWP_FRAMECHANGED = 0x0020

        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style |= WS_EX_LAYERED
        if self.config.get("drag_adjust_mode", False):
            style &= ~WS_EX_TRANSPARENT
        else:
            style |= WS_EX_TRANSPARENT
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

        z_order = HWND_TOPMOST if self.config.get("always_on_top", True) else HWND_NOTOPMOST
        user32.SetWindowPos(hwnd, z_order, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED)

        opacity = max(0.05, min(1.0, self.window_alpha / 255.0))
        self.setWindowOpacity(opacity)
        self.overlay.update()

    def _build_nurbs(self, ctrl_points):
        count = len(ctrl_points)
        if count < 4:
            return None

        degree = 3
        ctrl = np.asarray(ctrl_points, dtype=float)
        ctrl_wrap = np.vstack([ctrl, ctrl[:degree]])
        knots = np.arange(len(ctrl_wrap) + degree + 1, dtype=float)
        try:
            spline_x = BSpline(knots, ctrl_wrap[:, 0], degree)
            spline_y = BSpline(knots, ctrl_wrap[:, 1], degree)
            eval_count = max(count * 8, 200)
            samples = np.linspace(degree, count + degree, eval_count, endpoint=False)
            return list(zip(spline_x(samples), spline_y(samples)))
        except Exception:
            return None

    def _contour_from_radii(self, cx, cy, radii, rot_rad, segments, seg_angle, step):
        sample_ids = np.arange(0, self.NUM_BARS, step)
        bar_ids = np.tile(sample_ids, segments)
        seg_ids = np.repeat(np.arange(segments), len(sample_ids))
        angles = bar_ids / self.NUM_BARS * seg_angle - np.pi / 2 + rot_rad + seg_ids * seg_angle
        pos_x = cx + radii[bar_ids] * np.cos(angles)
        pos_y = cy + radii[bar_ids] * np.sin(angles)
        return self._build_nurbs(list(zip(pos_x, pos_y)))

    @staticmethod
    def _circle_points(cx, cy, radius, segments=256, rotation=0.0):
        angles = np.linspace(0.0, np.pi * 2.0, max(32, segments), endpoint=False) + rotation - np.pi / 2
        pos_x = cx + radius * np.cos(angles)
        pos_y = cy + radius * np.sin(angles)
        return list(zip(pos_x, pos_y))

    def _build_bar_segments(self, cx, cy, radii_a, radii_b, rot_a, rot_b, segments, seg_angle, lengths, key):
        fixed = self.config.get(f"{key}_fixed", False)
        fixed_len = float(self.config.get(f"{key}_fixed_len", 30))
        from_start = self.config.get(f"{key}_from_start", True)
        from_end = self.config.get(f"{key}_from_end", False)
        from_center = self.config.get(f"{key}_from_center", False)

        indices = np.arange(self.NUM_BARS)
        line_segments = []
        for segment in range(segments):
            seg_off = segment * seg_angle
            angle_a = indices / self.NUM_BARS * seg_angle - np.pi / 2 + rot_a + seg_off
            angle_b = indices / self.NUM_BARS * seg_angle - np.pi / 2 + rot_b + seg_off
            ax = cx + radii_a * np.cos(angle_a)
            ay = cy + radii_a * np.sin(angle_a)
            bx = cx + radii_b * np.cos(angle_b)
            by = cy + radii_b * np.sin(angle_b)

            if not fixed:
                for index in range(self.NUM_BARS):
                    color_index = (index + segment * self.NUM_BARS // max(1, segments)) % max(1, len(self.colors))
                    color = self._get_color_for_bar(color_index, lengths[index])
                    line_segments.append(((ax[index], ay[index]), (bx[index], by[index]), (*color, 255)))
                continue

            delta_x = bx - ax
            delta_y = by - ay
            full_len = np.sqrt(delta_x * delta_x + delta_y * delta_y)
            full_len = np.maximum(full_len, 1e-6)
            unit_x = delta_x / full_len
            unit_y = delta_y / full_len
            clip_len = np.minimum(fixed_len, full_len)

            for index in range(self.NUM_BARS):
                color_index = (index + segment * self.NUM_BARS // max(1, segments)) % max(1, len(self.colors))
                color = self._get_color_for_bar(color_index, lengths[index])
                rgba = (*color, 255)
                if from_start:
                    line_segments.append(
                        (
                            (ax[index], ay[index]),
                            (ax[index] + unit_x[index] * clip_len[index], ay[index] + unit_y[index] * clip_len[index]),
                            rgba,
                        )
                    )
                if from_end:
                    line_segments.append(
                        (
                            (bx[index], by[index]),
                            (bx[index] - unit_x[index] * clip_len[index], by[index] - unit_y[index] * clip_len[index]),
                            rgba,
                        )
                    )
                if from_center:
                    mid_x = (ax[index] + bx[index]) * 0.5
                    mid_y = (ay[index] + by[index]) * 0.5
                    half = clip_len[index] * 0.5
                    line_segments.append(
                        (
                            (mid_x - unit_x[index] * half, mid_y - unit_y[index] * half),
                            (mid_x + unit_x[index] * half, mid_y + unit_y[index] * half),
                            rgba,
                        )
                    )
        return line_segments

    def _update_visual_state(self, bar_values):
        if not self.config.get("master_visible", True):
            self.render_state = {"center": (self.center_x, self.center_y), "fills": [], "bars": [], "lines": []}
            return

        cx = float(self.center_x)
        cy = float(self.center_y)
        scale = float(self.config.get("global_scale", 1.0))
        main_radius_scale = float(self.config.get("main_radius_scale", 1.0))
        rotation_base = float(self.config.get("rotation_base", 1.0))
        base_radius = float(self.config.get("circle_radius", 150)) * scale * main_radius_scale
        segments = max(1, int(self.config.get("circle_segments", 1)))
        seg_angle = 2 * np.pi / segments

        target_radius = base_radius
        effective_a1 = self.effective_a1
        if self.config.get("circle_a1_radius", True) and effective_a1 > 0:
            target_radius = base_radius + (effective_a1 / 1000.0) * 100.0 * scale

        radius_damping = float(self.config.get("radius_damping", 0.92))
        radius_spring = float(self.config.get("radius_spring", 0.15))
        radius_gravity = float(self.config.get("radius_gravity", 0.3))

        spring_force = (target_radius - self.current_radius) * radius_spring
        gravity_force = -(self.current_radius - base_radius) * radius_gravity * 0.01
        self.radius_velocity *= radius_damping
        self.radius_velocity += spring_force + gravity_force
        self.current_radius = max(10.0, self.current_radius + self.radius_velocity)
        radius = self.current_radius

        bar_len_min = float(self.config.get("bar_length_min", 0))
        bar_len_max = float(self.config.get("bar_length_max", 300))
        targets = bar_values / 200.0
        spring_forces = (targets - self.bar_heights) * self.spring_strength
        self.bar_velocities *= self.damping
        self.bar_velocities += spring_forces - self.gravity * 0.1
        self.bar_heights = np.clip(self.bar_heights + self.bar_velocities, 0, 300)
        lengths = np.clip(self.bar_heights, bar_len_min, bar_len_max) * scale

        decay_inner = float(self.config.get("c1_decay", 0.995))
        decay_outer = float(self.config.get("c5_decay", 0.995))
        self.peak_inner_heights = np.maximum(lengths, self.peak_inner_heights * decay_inner)
        self.peak_outer_heights = np.maximum(lengths, self.peak_outer_heights * decay_outer)

        a1_delta = abs(effective_a1 - self.prev_a1_value)
        self.prev_a1_value = effective_a1
        normalized_delta = min(a1_delta / 500.0, 1.0)
        for layer_index in range(1, 6):
            speed = float(self.config.get(f"c{layer_index}_rot_speed", 1.0))
            power = float(self.config.get(f"c{layer_index}_rot_pow", 0.5))
            if self.config.get("circle_a1_rotation", True) and normalized_delta > 1e-4:
                if power >= 0:
                    factor = pow(normalized_delta + 0.001, power)
                else:
                    factor = max(0.0, 1.0 - pow(normalized_delta, abs(power)))
                self.layer_rotations[layer_index] += speed * factor * 2.0 * rotation_base
            else:
                self.layer_rotations[layer_index] += speed * 0.1 * rotation_base
            self.layer_rotations[layer_index] %= 360.0
        rot = {index: np.deg2rad(self.layer_rotations[index]) for index in range(1, 6)}

        radius_map = {
            1: np.maximum(0, radius - self.peak_inner_heights),
            2: np.maximum(0, radius - lengths),
            3: np.full(self.NUM_BARS, radius),
            4: radius + lengths,
            5: radius + self.peak_outer_heights,
        }

        contour_points = {}
        for layer_index in (1, 2, 4, 5):
            need_line = self.config.get(f"c{layer_index}_on", False)
            need_fill = self.config.get(f"c{layer_index}_fill", False)
            if not (need_line or need_fill):
                continue
            step = max(1, int(self.config.get(f"c{layer_index}_step", 2)))
            contour_points[layer_index] = self._contour_from_radii(cx, cy, radius_map[layer_index], rot[layer_index], segments, seg_angle, step)

        circle_points = self._circle_points(cx, cy, radius, max(96, self.NUM_BARS * segments * 4), rot[3])

        fills = []
        for layer_index in (5, 4, 3, 2, 1):
            if not self.config.get(f"c{layer_index}_fill", False):
                continue
            points = circle_points if layer_index == 3 else contour_points.get(layer_index)
            if points and len(points) >= 3:
                color = tuple(self.config.get(f"c{layer_index}_color", (255, 255, 255)))
                alpha = int(self.config.get(f"c{layer_index}_fill_alpha", 50))
                fills.append({"points": points, "color": (*color, alpha)})

        bars = []
        for layer_a, layer_b, key in ((4, 5, "b45"), (3, 4, "b34"), (2, 3, "b23"), (1, 2, "b12")):
            if not self.config.get(f"{key}_on", False):
                continue
            thickness = int(self.config.get(f"{key}_thick", 3))
            segments_data = self._build_bar_segments(
                cx,
                cy,
                radius_map[layer_a],
                radius_map[layer_b],
                rot[layer_a],
                rot[layer_b],
                segments,
                seg_angle,
                lengths,
                key,
            )
            bars.append({"segments": segments_data, "thickness": thickness})

        lines = []
        for layer_index in (5, 4, 3, 2, 1):
            if not self.config.get(f"c{layer_index}_on", False):
                continue
            points = circle_points if layer_index == 3 else contour_points.get(layer_index)
            if points and len(points) >= 3:
                color = tuple(self.config.get(f"c{layer_index}_color", (255, 255, 255)))
                alpha = int(self.config.get(f"c{layer_index}_alpha", 180))
                thickness = int(self.config.get(f"c{layer_index}_thick", 2))
                lines.append({"points": points, "color": (*color, alpha), "thickness": thickness})

        self.render_state = {"center": (cx, cy), "fills": fills, "bars": bars, "lines": lines}

    @staticmethod
    def _gl_set_color(color):
        GL.glColor4f(color[0] / 255.0, color[1] / 255.0, color[2] / 255.0, color[3] / 255.0)

    def _gl_draw_radial_fill(self, center, points, color):
        if not points or len(points) < 3:
            return
        self._gl_set_color(color)
        GL.glBegin(GL.GL_TRIANGLE_FAN)
        GL.glVertex2f(float(center[0]), float(center[1]))
        for pos_x, pos_y in points:
            GL.glVertex2f(float(pos_x), float(pos_y))
        GL.glVertex2f(float(points[0][0]), float(points[0][1]))
        GL.glEnd()

    def _gl_draw_line_loop(self, points, color, thickness):
        if not points or len(points) < 2:
            return
        GL.glLineWidth(max(1.0, float(thickness)))
        self._gl_set_color(color)
        GL.glBegin(GL.GL_LINE_LOOP)
        for pos_x, pos_y in points:
            GL.glVertex2f(float(pos_x), float(pos_y))
        GL.glEnd()

    def _gl_draw_segments(self, segments, thickness):
        if not segments:
            return
        GL.glLineWidth(max(1.0, float(thickness)))
        GL.glBegin(GL.GL_LINES)
        for start, end, color in segments:
            self._gl_set_color(color)
            GL.glVertex2f(float(start[0]), float(start[1]))
            GL.glVertex2f(float(end[0]), float(end[1]))
        GL.glEnd()

    @staticmethod
    def _make_round_pen(color, thickness):
        pen = QPen(QColor(color[0], color[1], color[2], color[3]))
        pen.setWidthF(max(1.0, float(thickness)))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        return pen

    def _paint_line_loop(self, painter, points, color, thickness):
        if not points or len(points) < 2:
            return

        path = QPainterPath()
        first_x, first_y = points[0]
        path.moveTo(QPointF(float(first_x), float(first_y)))
        for pos_x, pos_y in points[1:]:
            path.lineTo(QPointF(float(pos_x), float(pos_y)))
        path.closeSubpath()

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(self._make_round_pen(color, thickness))
        painter.drawPath(path)

    def _paint_segments(self, painter, segments, thickness):
        if not segments:
            return

        painter.setBrush(Qt.BrushStyle.NoBrush)
        last_color = None
        for start, end, color in segments:
            if color != last_color:
                painter.setPen(self._make_round_pen(color, thickness))
                last_color = color
            painter.drawLine(
                QPointF(float(start[0]), float(start[1])),
                QPointF(float(end[0]), float(end[1])),
            )

    def _update_config_from_queue(self):
        if not self.config_queue:
            return

        try:
            while True:
                new_config = self.config_queue.get_nowait()

                if "command" in new_config:
                    if new_config["command"] == "center_window":
                        self._center_window(reset_visual_center=True)
                        self._send_status()
                    continue

                old = self.config.copy()
                self.config = new_config

                if int(new_config.get("num_bars", 64)) != self.NUM_BARS:
                    self.NUM_BARS = int(new_config.get("num_bars", 64))
                    old_heights = self.bar_heights.copy()
                    self.bar_heights = np.zeros(self.NUM_BARS, dtype=float)
                    self.bar_velocities = np.zeros(self.NUM_BARS, dtype=float)
                    self.peak_outer_heights = np.zeros(self.NUM_BARS, dtype=float)
                    self.peak_inner_heights = np.zeros(self.NUM_BARS, dtype=float)
                    count = min(len(old_heights), self.NUM_BARS)
                    self.bar_heights[:count] = old_heights[:count]
                    self._update_colors()

                self.smoothing_factor = float(new_config.get("smoothing", 0.7))
                self.damping = float(new_config.get("damping", 0.85))
                self.spring_strength = float(new_config.get("spring_strength", 0.3))
                self.gravity = float(new_config.get("gravity", 0.5))
                self.a1_time_window = float(new_config.get("a1_time_window", 10))
                self.ui_bg_alpha = int(new_config.get("ui_alpha", 180))
                self.window_alpha = int(new_config.get("alpha", 255))

                if (
                    new_config.get("color_scheme") != old.get("color_scheme")
                    or new_config.get("gradient_points") != old.get("gradient_points")
                    or new_config.get("gradient_enabled") != old.get("gradient_enabled")
                    or new_config.get("gradient_mode") != old.get("gradient_mode")
                    or new_config.get("color_dynamic") != old.get("color_dynamic")
                    or new_config.get("color_cycle_speed") != old.get("color_cycle_speed")
                    or new_config.get("color_cycle_pow") != old.get("color_cycle_pow")
                    or new_config.get("color_cycle_a1") != old.get("color_cycle_a1")
                ):
                    self._update_colors()

                if (
                    new_config.get("drag_adjust_mode", False) != old.get("drag_adjust_mode", False)
                    or new_config.get("always_on_top", True) != old.get("always_on_top", True)
                    or new_config.get("bg_transparent", True) != old.get("bg_transparent", True)
                    or new_config.get("alpha", 255) != old.get("alpha", 255)
                ):
                    self._apply_window_styles(force=True)

                new_x = new_config.get("pos_x", -1)
                new_y = new_config.get("pos_y", -1)
                if new_x < 0:
                    self.center_x = self.width() * 0.5
                else:
                    self.center_x = float(new_x)
                if new_y < 0:
                    self.center_y = self.height() * 0.5
                else:
                    self.center_y = float(new_y)
        except queue.Empty:
            pass

    def _tick(self):
        self._update_config_from_queue()

        now = time.time()
        if now - self.last_status_send >= 2.0:
            self._send_status()
            self.last_status_send = now

        effective_a1 = self.effective_a1
        if self.config.get("color_dynamic", False):
            base_speed = 0.001
            if self.config.get("color_cycle_a1", True) and effective_a1 > 0:
                base_speed *= 1.0 + (effective_a1 / 1000.0) * 2.0
            speed = float(self.config.get("color_cycle_speed", 1.0))
            power = float(self.config.get("color_cycle_pow", 2.0))
            self.color_cycle_hue = (self.color_cycle_hue + base_speed * pow(speed, power)) % 1.0
            self._update_colors()

        audio_frame = self._pull_latest_audio_frame()
        if audio_frame is None:
            bar_values = np.zeros(self.NUM_BARS, dtype=float)
        else:
            bar_values = self._process_audio(audio_frame)

        self._update_visual_state(bar_values)
        self.gl_widget.update()
        self.overlay.update()

    def _cleanup(self):
        if hasattr(self, "stream"):
            self.stream.stop_stream()
            self.stream.close()
        if hasattr(self, "p"):
            self.p.terminate()
        print("PyOpenGL 圆形频谱窗口已关闭")


def _create_app():
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseDesktopOpenGL, True)
    fmt = QSurfaceFormat()
    fmt.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
    fmt.setVersion(2, 1)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CompatibilityProfile)
    fmt.setAlphaBufferSize(8)
    fmt.setSamples(4)
    QSurfaceFormat.setDefaultFormat(fmt)
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def run_standalone():
    print("========== 圆形频谱独立运行（PyOpenGL） ==========")
    app = _create_app()
    window = CircularVisualizerWindow()
    window.run()
    sys.exit(app.exec())


def run_from_main(config_queue, status_queue):
    print("========== 圆形频谱（主框架模式 / PyOpenGL） ==========")
    try:
        app = _create_app()
        window = CircularVisualizerWindow(config_queue, status_queue)
        window.run()
        sys.exit(app.exec())
    except Exception as exc:
        print(f"圆形频谱进程错误: {exc}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    run_standalone()