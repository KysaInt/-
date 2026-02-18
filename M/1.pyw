"""
圆形频谱可视化 - Pygame 实现
可独立运行（使用 default_config.py 的默认参数）
也可被主框架调用（通过 Queue 接收实时配置）
"""

import sys
import os
import json
import numpy as np
import pyaudiowpatch as pyaudio
import pygame
from scipy.fft import fft as scipy_fft
from scipy.interpolate import BSpline
import colorsys
import queue
import ctypes
from ctypes import wintypes
import time
from pathlib import Path

# GPU 加速（可选）
try:
    import cupy as cp
    _HAS_GPU = True
    # 预热 CuPy FFT
    cp.fft.fft(cp.zeros(2048))
    print("✓ CuPy 可用 — 启用 GPU 加速")
except Exception:
    _HAS_GPU = False
    print("⚠ CuPy 不可用 — 使用 CPU 计算")

CONFIG_FILE = Path(__file__).parent / 'visualizer_config.json'

_DEFAULT_CONFIG = {
    'width': 0, 'height': 0, 'alpha': 255, 'ui_alpha': 180,
    'global_scale': 1.0, 'pos_x': -1, 'pos_y': -1,
    'drag_adjust_mode': False,
    'bg_transparent': True, 'always_on_top': True,
    'num_bars': 64, 'smoothing': 0.7,
    'damping': 0.85, 'spring_strength': 0.3, 'gravity': 0.5,
    'rotation_base': 1.0, 'main_radius_scale': 1.0,
    'bar_height_min': 0, 'bar_height_max': 500,
    'color_scheme': 'rainbow',
    'gradient_points': [(0.0, (255, 0, 128)), (1.0, (0, 255, 255))],
    'gradient_enabled': True, 'gradient_mode': 'frequency',
    'color_dynamic': False, 'color_cycle_speed': 1.0,
    'color_cycle_pow': 2.0, 'color_cycle_a1': True,
    'circle_radius': 150, 'circle_segments': 1,
    'circle_a1_rotation': True, 'circle_a1_radius': True,
    'radius_damping': 0.92, 'radius_spring': 0.15, 'radius_gravity': 0.3,
    'bar_length_min': 0, 'bar_length_max': 300,
    'freq_min': 20, 'freq_max': 20000,
    'a1_time_window': 10,
    'k2_enabled': False, 'k2_pow': 1.0,
    'master_visible': True,
    # C1 内缓慢  C2 内快速  C3 基圆  C4 外快速  C5 外缓慢
    'c1_on': True,  'c1_color': (100,180,255), 'c1_alpha': 100, 'c1_thick': 1,
    'c1_fill': False, 'c1_fill_alpha': 30, 'c1_step': 2, 'c1_decay': 0.995,
    'c1_rot_speed': 1.0, 'c1_rot_pow': 0.5,
    'c2_on': False, 'c2_color': (150,220,255), 'c2_alpha': 150, 'c2_thick': 2,
    'c2_fill': False, 'c2_fill_alpha': 50, 'c2_step': 2,
    'c2_rot_speed': 1.0, 'c2_rot_pow': 0.5,
    'c3_on': False, 'c3_color': (255,255,255), 'c3_alpha': 60,  'c3_thick': 1,
    'c3_fill': False, 'c3_fill_alpha': 20,
    'c3_rot_speed': 1.0, 'c3_rot_pow': 0.5,
    'c4_on': True,  'c4_color': (255,255,255), 'c4_alpha': 180, 'c4_thick': 2,
    'c4_fill': True,  'c4_fill_alpha': 60, 'c4_step': 2,
    'c4_rot_speed': 1.0, 'c4_rot_pow': 0.5,
    'c5_on': True,  'c5_color': (255,200,100), 'c5_alpha': 100, 'c5_thick': 1,
    'c5_fill': False, 'c5_fill_alpha': 30, 'c5_step': 2, 'c5_decay': 0.995,
    'c5_rot_speed': 1.0, 'c5_rot_pow': 0.5,
    # 四层条形  b12(C1-C2) b23(C2-C3) b34(C3-C4) b45(C4-C5)
    'b12_on': False, 'b12_thick': 2,
    'b12_fixed': False, 'b12_fixed_len': 30, 'b12_from_start': True, 'b12_from_end': False, 'b12_from_center': False,
    'b23_on': False, 'b23_thick': 3,
    'b23_fixed': False, 'b23_fixed_len': 30, 'b23_from_start': True, 'b23_from_end': False, 'b23_from_center': False,
    'b34_on': True,  'b34_thick': 3,
    'b34_fixed': False, 'b34_fixed_len': 30, 'b34_from_start': True, 'b34_from_end': False, 'b34_from_center': False,
    'b45_on': False, 'b45_thick': 2,
    'b45_fixed': False, 'b45_fixed_len': 30, 'b45_from_start': True, 'b45_from_end': False, 'b45_from_center': False,
}


def _load_config():
    """加载配置（优先 JSON，回退内置默认值）"""
    import copy
    cfg = copy.deepcopy(_DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg


class CircularVisualizerWindow:
    """圆形频谱可视化窗口"""

    def __init__(self, config_queue=None, status_queue=None):
        self.config_queue = config_queue
        self.status_queue = status_queue

        # 获取初始配置
        if config_queue and not config_queue.empty():
            self.config = config_queue.get()
        else:
            self.config = _load_config()

        # 初始化 Pygame
        pygame.init()
        screen_info = pygame.display.Info()

        # 窗口尺寸（0=全屏）
        w = self.config.get('width', 0)
        h = self.config.get('height', 0)
        self.WIDTH = w if w > 0 else screen_info.current_w
        self.HEIGHT = h if h > 0 else screen_info.current_h

        # 音频设置
        self.CHUNK = 2048
        self.RATE = 44100
        self.audio_queue = queue.Queue()

        # 频谱条
        self.NUM_BARS = self.config['num_bars']
        self.bar_width = self.WIDTH // self.NUM_BARS

        # 创建窗口
        self.screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT), pygame.NOFRAME)
        pygame.display.set_caption("圆形频谱")
        self.clock = pygame.time.Clock()

        # 字体（使用系统中文字体，回退到默认字体）
        self.font_small = pygame.font.Font(None, 24)
        self._cn_font_28 = None
        self._cn_font_20 = None
        for _fn in ['msyh.ttc', 'simhei.ttf', 'simsun.ttc', 'microsoftyahei.ttf']:
            _fp = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts', _fn)
            if os.path.exists(_fp):
                try:
                    self._cn_font_28 = pygame.font.Font(_fp, 16)
                    self._cn_font_20 = pygame.font.Font(_fp, 12)
                    break
                except Exception:
                    pass

        # 可视化中心位置（使用 config 的 pos_x/pos_y，-1 表示屏幕中心）
        cx_default = self.WIDTH // 2
        cy_default = self.HEIGHT // 2
        self.center_x = self.config.get('pos_x', -1)
        self.center_y = self.config.get('pos_y', -1)
        if self.center_x < 0:
            self.center_x = cx_default
        if self.center_y < 0:
            self.center_y = cy_default

        # 透明（使用近似黑 (1,0,1) 而非纯黑 (0,0,0) 作为色键，
        # 避免用户选择纯黑色时与透明色键冲突导致内容不可见）
        self.transparent_color = (1, 0, 1)
        self.window_alpha = self.config['alpha']
        self.ui_bg_alpha = self.config['ui_alpha']

        # 窗口拖动（这里实际是拖动可视化中心点，而不是窗口本身）
        self.dragging = False
        # 记录拖动开始时的鼠标全局位置和中心点位置
        self.drag_start_cursor = None
        self.center_drag_start = None
        self.drag_handle_size = 92
        self.drag_handle_rect = pygame.Rect(
            self.WIDTH // 2 - self.drag_handle_size // 2,
            self.HEIGHT // 2 - self.drag_handle_size // 2,
            self.drag_handle_size,
            self.drag_handle_size,
        )
        self.drag_handle_hover = False

        # 设置透明置顶
        self._setup_transparent_window()

        # 颜色
        self.colors = []
        self.color_cycle_hue = 0.0
        self._update_colors()

        # 物理动画
        self.bar_heights = np.zeros(self.NUM_BARS)
        self.bar_velocities = np.zeros(self.NUM_BARS)
        self.smoothing_factor = self.config.get('smoothing', 0.7)
        self.damping = self.config.get('damping', 0.85)
        self.spring_strength = self.config.get('spring_strength', 0.3)
        self.gravity = self.config.get('gravity', 0.5)

        # A1 响度
        self.a1_time_window = self.config.get('a1_time_window', 10)
        self.loudness_history = []
        self.a1_value = 0.0
        self.prev_a1_value = 0.0  # 前一帧 A1，用于计算变化率
        self.k2_value = 0.0       # K2 = sign(delta)*|delta|^pow
        self.last_status_send = time.time()

        # 每层独立旋转状态 {1..5}
        self.layer_rotations = {i: 0.0 for i in range(1, 6)}

        # 半径物理缓动
        self.current_radius = float(self.config.get('circle_radius', 150))
        self.radius_velocity = 0.0

        # 峰值跟踪
        self.peak_outer_heights = np.zeros(self.NUM_BARS)
        self.peak_inner_heights = np.zeros(self.NUM_BARS)

        # 初始化音频
        self._init_audio()

    # ── 音频 ──────────────────────────────────────────────

    def _init_audio(self):
        """初始化 WASAPI loopback 音频捕获"""
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
            print(f"使用设备: {self.device_info['name']}")
        except Exception as e:
            print(f"获取音频设备失败: {e}")
            raise

        self.stream = self.p.open(
            format=pyaudio.paInt16,
            channels=self.device_info["maxInputChannels"],
            rate=self.RATE,
            frames_per_buffer=self.CHUNK,
            input=True,
            input_device_index=self.device_info["index"],
            stream_callback=self._audio_callback,
        )
        self.stream.start_stream()
        print("✓ 音频捕获已启动")

    def _audio_callback(self, in_data, frame_count, time_info, status):
        if in_data:
            self.audio_queue.put(np.frombuffer(in_data, dtype=np.int16))
        return (in_data, pyaudio.paContinue)

    def _process_audio(self, audio_data):
        """FFT 频谱分析（支持 GPU 加速）"""
        if len(audio_data) > self.CHUNK:
            audio_data = audio_data.reshape(-1, 2).mean(axis=1)
        if len(audio_data) >= self.CHUNK:
            audio_data = audio_data[:self.CHUNK]
        else:
            audio_data = np.pad(audio_data, (0, self.CHUNK - len(audio_data)))

        # RMS 响度
        loudness = np.sqrt(np.mean(audio_data.astype(float) ** 2))
        self._update_a1(loudness)

        windowed = audio_data * np.hamming(len(audio_data))

        # FFT：优先 GPU，回退 CPU
        if _HAS_GPU:
            try:
                w_gpu = cp.asarray(windowed)
                spectrum = cp.asnumpy(cp.abs(cp.fft.fft(w_gpu))[:self.CHUNK // 2])
            except Exception:
                spectrum = np.abs(scipy_fft(windowed))[:self.CHUNK // 2]
        else:
            spectrum = np.abs(scipy_fft(windowed))[:self.CHUNK // 2]

        # 频率区间限制
        freq_res = self.RATE / self.CHUNK
        f_lo = max(1, int(self.config.get('freq_min', 20) / freq_res))
        f_hi = min(len(spectrum), int(self.config.get('freq_max', 20000) / freq_res))
        if f_hi <= f_lo:
            f_hi = f_lo + 1
        sub = spectrum[f_lo:f_hi]
        freq_bins = np.logspace(np.log10(1), np.log10(max(2, len(sub))), self.NUM_BARS + 1, dtype=int)

        bar_values = np.zeros(self.NUM_BARS)
        for i in range(self.NUM_BARS):
            start, end = freq_bins[i], freq_bins[i + 1]
            if end > start:
                bar_values[i] = np.mean(sub[start:end])
        return bar_values

    # ── A1 / K2 ────────────────────────────────────────────

    def _update_a1(self, loudness):
        now = time.time()
        self.loudness_history.append((now, loudness))
        cutoff = now - self.a1_time_window
        self.loudness_history = [(t, l) for t, l in self.loudness_history if t >= cutoff]
        old_a1 = self.a1_value
        self.a1_value = np.mean([l for _, l in self.loudness_history]) if self.loudness_history else 0.0
        # K2: sign-preserving power of delta
        delta = self.a1_value - old_a1
        pw = self.config.get('k2_pow', 1.0)
        self.k2_value = np.sign(delta) * (abs(delta) ** pw)

    @property
    def effective_a1(self):
        """K2 启用时用 K2 替代 K1"""
        if self.config.get('k2_enabled', False):
            return self.k2_value
        return self.a1_value

    def _send_status(self):
        """向控制台汇报当前状态：K 值和可视化中心位置"""
        if not self.status_queue or self.status_queue.full():
            return
        try:
            while not self.status_queue.empty():
                try:
                    self.status_queue.get_nowait()
                except Exception:
                    break
            self.status_queue.put({
                'a1': self.a1_value,
                'k2': self.k2_value,
                # 这里的 pos_x/pos_y 表示可视化中心点，而非窗口左上角
                'pos_x': int(self.center_x),
                'pos_y': int(self.center_y),
            })
        except Exception:
            pass

    def _get_window_pos(self):
        """获取当前窗口屏幕坐标"""
        try:
            hwnd = pygame.display.get_wm_info()["window"]
            rect = wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
            return (rect.left, rect.top)
        except:
            return (-1, -1)

    # ── 颜色系统 ──────────────────────────────────────────

    def _update_colors(self):
        """根据当前配置生成颜色表"""
        scheme = self.config.get('color_scheme', 'rainbow')
        gradient_enabled = self.config.get('gradient_enabled', True)
        color_dynamic = self.config.get('color_dynamic', False)
        self.colors = []

        if scheme == 'custom':
            points = sorted(
                self.config.get('gradient_points', [(0.0, (255, 0, 128)), (1.0, (0, 255, 255))]),
                key=lambda p: p[0],
            )
            if not gradient_enabled:
                base = points[0][1]
                if color_dynamic:
                    h, s, v = colorsys.rgb_to_hsv(base[0] / 255, base[1] / 255, base[2] / 255)
                    for _ in range(self.NUM_BARS):
                        nh = (h + self.color_cycle_hue) % 1.0
                        rgb = colorsys.hsv_to_rgb(nh, s, v)
                        self.colors.append(tuple(int(c * 255) for c in rgb))
                else:
                    self.colors = [base] * self.NUM_BARS
            else:
                for i in range(self.NUM_BARS):
                    ratio = i / self.NUM_BARS
                    base = self._interpolate_color(ratio, points)
                    if color_dynamic:
                        h, s, v = colorsys.rgb_to_hsv(base[0] / 255, base[1] / 255, base[2] / 255)
                        nh = (h + self.color_cycle_hue) % 1.0
                        rgb = colorsys.hsv_to_rgb(nh, s, v)
                        self.colors.append(tuple(int(c * 255) for c in rgb))
                    else:
                        self.colors.append(base)
        else:
            for i in range(self.NUM_BARS):
                ratio = i / self.NUM_BARS
                if scheme == 'rainbow':
                    hue = (ratio + self.color_cycle_hue) % 1.0 if color_dynamic else ratio
                    rgb = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
                elif scheme == 'fire':
                    rgb = (1.0, ratio * 0.8, ratio * 0.2)
                    if color_dynamic:
                        h, s, v = colorsys.rgb_to_hsv(*rgb)
                        rgb = colorsys.hsv_to_rgb((h + self.color_cycle_hue) % 1.0, s, v)
                elif scheme == 'ice':
                    rgb = (ratio * 0.3, ratio * 0.7, 1.0)
                    if color_dynamic:
                        h, s, v = colorsys.rgb_to_hsv(*rgb)
                        rgb = colorsys.hsv_to_rgb((h + self.color_cycle_hue) % 1.0, s, v)
                elif scheme == 'neon':
                    hue = ((ratio + 0.5) % 1.0 + self.color_cycle_hue) % 1.0 if color_dynamic else (ratio + 0.5) % 1.0
                    rgb = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
                else:
                    rgb = colorsys.hsv_to_rgb(ratio, 1.0, 1.0)
                self.colors.append(tuple(int(c * 255) for c in rgb))

    @staticmethod
    def _interpolate_color(ratio, points):
        for i in range(len(points) - 1):
            pos1, c1 = points[i]
            pos2, c2 = points[i + 1]
            if pos1 <= ratio <= pos2:
                t = (ratio - pos1) / (pos2 - pos1) if (pos2 - pos1) > 0 else 0
                return (
                    int(c1[0] * (1 - t) + c2[0] * t),
                    int(c1[1] * (1 - t) + c2[1] * t),
                    int(c1[2] * (1 - t) + c2[2] * t),
                )
        return points[0][1] if ratio <= points[0][0] else points[-1][1]

    def _get_color_for_bar(self, bar_index, bar_height=None):
        scheme = self.config.get('color_scheme', 'rainbow')
        gradient_mode = self.config.get('gradient_mode', 'frequency')

        if scheme != 'custom' or gradient_mode != 'height':
            return self.colors[bar_index] if bar_index < len(self.colors) else (255, 255, 255)

        # 自定义 + 高度渐变
        if bar_height is None:
            bar_height = self.bar_heights[bar_index]
        mn = self.config.get('bar_height_min', 0)
        mx = self.config.get('bar_height_max', 500)
        ratio = max(0.0, min(1.0, (bar_height - mn) / (mx - mn))) if mx > mn else 0.0
        points = sorted(self.config.get('gradient_points', [(0.0, (255, 0, 128)), (1.0, (0, 255, 255))]), key=lambda p: p[0])
        base = self._interpolate_color(ratio, points)

        if self.config.get('color_dynamic', False):
            h, s, v = colorsys.rgb_to_hsv(base[0] / 255, base[1] / 255, base[2] / 255)
            rgb = colorsys.hsv_to_rgb((h + self.color_cycle_hue) % 1.0, s, v)
            return tuple(int(c * 255) for c in rgb)
        return base

    # ── 窗口管理 ──────────────────────────────────────────

    def _setup_transparent_window(self):
        try:
            hwnd = pygame.display.get_wm_info()["window"]
            GWL_EXSTYLE = -20
            user32 = ctypes.windll.user32
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | 0x00080000)

            self._set_click_through(not self.config.get('drag_adjust_mode', False))

            if self.config.get('bg_transparent', True):
                ck = self.transparent_color[0] | (self.transparent_color[1] << 8) | (self.transparent_color[2] << 16)
                user32.SetLayeredWindowAttributes(hwnd, ck, 0, 0x00000001)

            if self.config.get('always_on_top', True):
                user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0040)

            # 全屏/窗口位置只在创建时由系统决定或简单居中，
            # 不再使用 pos_x/pos_y 控制窗口位置，pos_* 仅表示可视化中心
            self._center_window()

            # 发送初始中心坐标状态，让控制台立即获得正确的位置
            self._send_status()
            print("✓ 透明悬浮窗口设置成功")
        except Exception as e:
            print(f"警告: 设置透明窗口失败: {e}")

    def _set_click_through(self, enabled):
        try:
            hwnd = pygame.display.get_wm_info()["window"]
            GWL_EXSTYLE = -20
            WS_EX_TRANSPARENT = 0x00000020
            user32 = ctypes.windll.user32
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if enabled:
                style |= WS_EX_TRANSPARENT
            else:
                style &= ~WS_EX_TRANSPARENT
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0020)
        except Exception as e:
            print(f"警告: 切换点击穿透失败: {e}")

    def _draw_drag_handle(self):
        if not self.config.get('drag_adjust_mode', False):
            return
        # 使用可视化中心点，而非窗口中心
        cx, cy = int(self.center_x), int(self.center_y)
        sz = self.drag_handle_size
        self.drag_handle_rect = pygame.Rect(
            cx - sz // 2, cy - sz // 2, sz, sz,
        )

        # 半透明圆角背景
        bg = pygame.Surface((sz, sz), pygame.SRCALPHA)
        radius = 12
        col_bg = (50, 50, 60, 200) if not self.drag_handle_hover else (70, 70, 90, 230)
        col_border = (180, 200, 255) if self.drag_handle_hover else (120, 130, 160)
        pygame.draw.rect(bg, col_bg, (0, 0, sz, sz), border_radius=radius)
        pygame.draw.rect(bg, (*col_border, 180), (0, 0, sz, sz), 2, border_radius=radius)
        self.screen.blit(bg, self.drag_handle_rect.topleft)

        # 绘制十字移动箭头图标（不依赖字体）
        arrow_col = (220, 230, 255) if self.drag_handle_hover else (160, 170, 200)
        arm = 16  # 箭头臂长
        head = 5  # 箭头头部大小
        lw = 2
        # 上
        pygame.draw.line(self.screen, arrow_col, (cx, cy - arm), (cx, cy - 3), lw)
        pygame.draw.polygon(self.screen, arrow_col, [
            (cx, cy - arm - head), (cx - head, cy - arm), (cx + head, cy - arm)])
        # 下
        pygame.draw.line(self.screen, arrow_col, (cx, cy + 3), (cx, cy + arm), lw)
        pygame.draw.polygon(self.screen, arrow_col, [
            (cx, cy + arm + head), (cx - head, cy + arm), (cx + head, cy + arm)])
        # 左
        pygame.draw.line(self.screen, arrow_col, (cx - arm, cy), (cx - 3, cy), lw)
        pygame.draw.polygon(self.screen, arrow_col, [
            (cx - arm - head, cy), (cx - arm, cy - head), (cx - arm, cy + head)])
        # 右
        pygame.draw.line(self.screen, arrow_col, (cx + 3, cy), (cx + arm, cy), lw)
        pygame.draw.polygon(self.screen, arrow_col, [
            (cx + arm + head, cy), (cx + arm, cy - head), (cx + arm, cy + head)])

        # 中心小点
        pygame.draw.circle(self.screen, arrow_col, (cx, cy), 2)

        # 底部提示文字
        if self._cn_font_20:
            hint = self._cn_font_20.render("拖动", True, (200, 210, 240))
        else:
            hint = pygame.font.Font(None, 16).render("DRAG", True, (200, 210, 240))
        self.screen.blit(hint, hint.get_rect(center=(cx, cy + arm + head + 12)))

    def _center_window(self):
        try:
            user32 = ctypes.windll.user32
            sw = user32.GetSystemMetrics(0)
            sh = user32.GetSystemMetrics(1)
            hwnd = pygame.display.get_wm_info()["window"]
            
            # 全屏模式：确保窗口在屏幕内
            if self.WIDTH >= sw or self.HEIGHT >= sh:
                user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0004 | 0x0001 | 0x0040)
                print(f"✓ 全屏窗口已定位到 (0,0)")
            else:
                x = (sw - self.WIDTH) // 2
                y = (sh - self.HEIGHT) // 2
                user32.SetWindowPos(hwnd, 0, x, y, 0, 0, 0x0004 | 0x0001 | 0x0040)
                print(f"✓ 窗口已居中到 ({x},{y})")
        except Exception as e:
            print(f"警告: 居中窗口失败: {e}")

    def _move_window(self, event):
        """拖动时更新可视化中心点（而不是窗口位置）"""
        # 使用鼠标相对移动量 event.rel，避免全局坐标和 DPI 问题
        dx, dy = event.rel
        if dx == 0 and dy == 0:
            return
        self.center_x += dx
        self.center_y += dy

    # ── 辅助：NURBS / 轮廓 / 条形 ──────────────────────────

    def _build_nurbs(self, ctrl_points):
        """周期性三次 B 样条，返回 [(x,y), ...] 或 None"""
        n = len(ctrl_points)
        if n < 4:
            return None
        k = 3
        ctrl = np.array(ctrl_points, dtype=float)
        ctrl_w = np.vstack([ctrl, ctrl[:k]])
        knots = np.arange(len(ctrl_w) + k + 1, dtype=float)
        try:
            bsx = BSpline(knots, ctrl_w[:, 0], k)
            bsy = BSpline(knots, ctrl_w[:, 1], k)
            ne = max(n * 8, 200)
            t = np.linspace(k, n + k, ne, endpoint=False)
            return list(zip(bsx(t).astype(int), bsy(t).astype(int)))
        except Exception:
            return None

    def _contour_from_radii(self, cx, cy, radii, rot_rad, segments, seg_angle, step):
        """从每条 bar 的绝对半径数组构建 NURBS 轮廓"""
        bar_ids = np.tile(np.arange(0, self.NUM_BARS, step), segments)
        seg_ids = np.repeat(np.arange(segments), len(range(0, self.NUM_BARS, step)))
        angles = bar_ids / self.NUM_BARS * seg_angle - np.pi / 2 + rot_rad + seg_ids * seg_angle
        px = cx + radii[bar_ids] * np.cos(angles)
        py = cy + radii[bar_ids] * np.sin(angles)
        return self._build_nurbs(list(zip(px, py)))

    def _draw_bars_between(self, cx, cy, radii_a, radii_b, rot_a, rot_b,
                           segments, seg_angle, thick, lengths, key):
        """在两层轮廓之间绘制条形（支持固定长度 + 首/尾/中间模式）"""
        fixed = self.config.get(f'{key}_fixed', False)
        fixed_len = self.config.get(f'{key}_fixed_len', 30)
        from_start = self.config.get(f'{key}_from_start', True)
        from_end = self.config.get(f'{key}_from_end', False)
        from_center = self.config.get(f'{key}_from_center', False)

        indices = np.arange(self.NUM_BARS)
        for seg in range(segments):
            seg_off = seg * seg_angle
            ang_a = indices / self.NUM_BARS * seg_angle - np.pi / 2 + rot_a + seg_off
            ang_b = indices / self.NUM_BARS * seg_angle - np.pi / 2 + rot_b + seg_off
            ax = cx + radii_a * np.cos(ang_a)
            ay = cy + radii_a * np.sin(ang_a)
            bx = cx + radii_b * np.cos(ang_b)
            by = cy + radii_b * np.sin(ang_b)

            if not fixed:
                # 全长模式
                for i in range(self.NUM_BARS):
                    ci = (i + seg * self.NUM_BARS // segments) % len(self.colors)
                    color = self._get_color_for_bar(ci, lengths[i])
                    pygame.draw.line(self.screen, color,
                                     (int(ax[i]), int(ay[i])),
                                     (int(bx[i]), int(by[i])), thick)
            else:
                # 固定长度模式
                dx = bx - ax; dy = by - ay
                full_len = np.sqrt(dx * dx + dy * dy)
                full_len = np.maximum(full_len, 1e-6)
                ux = dx / full_len; uy = dy / full_len  # 单位方向
                clip_len = np.minimum(fixed_len, full_len)

                for i in range(self.NUM_BARS):
                    ci = (i + seg * self.NUM_BARS // segments) % len(self.colors)
                    color = self._get_color_for_bar(ci, lengths[i])
                    if from_start:
                        s = (int(ax[i]), int(ay[i]))
                        e = (int(ax[i] + ux[i] * clip_len[i]), int(ay[i] + uy[i] * clip_len[i]))
                        pygame.draw.line(self.screen, color, s, e, thick)
                    if from_end:
                        s = (int(bx[i]), int(by[i]))
                        e = (int(bx[i] - ux[i] * clip_len[i]), int(by[i] - uy[i] * clip_len[i]))
                        pygame.draw.line(self.screen, color, s, e, thick)
                    if from_center:
                        mx = (ax[i] + bx[i]) * 0.5
                        my = (ay[i] + by[i]) * 0.5
                        half = clip_len[i] * 0.5
                        s = (int(mx - ux[i] * half), int(my - uy[i] * half))
                        e = (int(mx + ux[i] * half), int(my + uy[i] * half))
                        pygame.draw.line(self.screen, color, s, e, thick)

    # ── 圆形频谱绘制（五层轮廓 + 四层条形）──────────────

    def _draw_circular_spectrum(self, bar_values):
        if not self.config.get('master_visible', True):
            return

        # 使用可视化中心点作为轴心，而不是窗口中心
        cx = int(getattr(self, 'center_x', self.WIDTH // 2))
        cy = int(getattr(self, 'center_y', self.HEIGHT // 2))
        scale = self.config.get('global_scale', 1.0)
        main_radius_scale = float(self.config.get('main_radius_scale', 1.0))
        rotation_base = float(self.config.get('rotation_base', 1.0))
        base_radius = self.config.get('circle_radius', 150) * scale * main_radius_scale
        segments = self.config.get('circle_segments', 1)
        seg_angle = 2 * np.pi / segments

        # ── A1 驱动半径（弹性缓动）──
        target_radius = base_radius
        ea1 = self.effective_a1
        if self.config.get('circle_a1_radius', True) and ea1 > 0:
            target_radius = base_radius + (ea1 / 1000.0) * 100 * scale
        r_damping = self.config.get('radius_damping', 0.92)
        r_spring  = self.config.get('radius_spring', 0.15)
        r_gravity = self.config.get('radius_gravity', 0.3)
        spring_f  = (target_radius - self.current_radius) * r_spring
        gravity_f = -(self.current_radius - base_radius) * r_gravity * 0.01
        self.radius_velocity *= r_damping
        self.radius_velocity += spring_f + gravity_f
        self.current_radius += self.radius_velocity
        self.current_radius = max(10, self.current_radius)
        radius = self.current_radius

        # ── 向量化物理模拟 ──
        bar_len_min = self.config.get('bar_length_min', 0)
        bar_len_max = self.config.get('bar_length_max', 300)
        targets = bar_values / 200.0
        spring_forces = (targets - self.bar_heights) * self.spring_strength
        self.bar_velocities *= self.damping
        self.bar_velocities += spring_forces - self.gravity * 0.1
        self.bar_heights = np.clip(self.bar_heights + self.bar_velocities, 0, 300)
        lengths = np.clip(self.bar_heights, bar_len_min, bar_len_max) * scale

        # ── 峰值跟踪 ──
        decay_1 = self.config.get('c1_decay', 0.995)
        decay_5 = self.config.get('c5_decay', 0.995)
        self.peak_inner_heights = np.maximum(lengths, self.peak_inner_heights * decay_1)
        self.peak_outer_heights = np.maximum(lengths, self.peak_outer_heights * decay_5)

        # ── 每层独立旋转 ──
        a1_delta = abs(ea1 - self.prev_a1_value)
        self.prev_a1_value = ea1
        norm_delta = min(a1_delta / 500.0, 1.0)
        for li in range(1, 6):
            spd = self.config.get(f'c{li}_rot_speed', 1.0)
            pw  = self.config.get(f'c{li}_rot_pow', 0.5)
            if self.config.get('circle_a1_rotation', True) and norm_delta > 1e-4:
                if pw >= 0:
                    factor = pow(norm_delta + 0.001, pw)
                else:
                    factor = max(0.0, 1.0 - pow(norm_delta, abs(pw)))
                self.layer_rotations[li] += spd * factor * 2.0 * rotation_base
            else:
                self.layer_rotations[li] += spd * 0.1 * rotation_base
            self.layer_rotations[li] %= 360
        rot = {i: self.layer_rotations[i] * np.pi / 180 for i in range(1, 6)}

        # ── 每层绝对半径数组 ──
        # c1 内缓慢  c2 内快速  c3 基圆  c4 外快速  c5 外缓慢
        r1 = np.maximum(0, radius - self.peak_inner_heights)
        r2 = np.maximum(0, radius - lengths)
        r3 = np.full(self.NUM_BARS, radius)
        r4 = radius + lengths
        r5 = radius + self.peak_outer_heights
        layer_r = {1: r1, 2: r2, 3: r3, 4: r4, 5: r5}

        # ── 构建 NURBS 轮廓点（c1,c2,c4,c5）──
        contour_pts = {}
        for li in (1, 2, 4, 5):
            need_line = self.config.get(f'c{li}_on', False)
            need_fill = self.config.get(f'c{li}_fill', False)
            if not (need_line or need_fill):
                continue
            step = max(1, self.config.get(f'c{li}_step', 2))
            contour_pts[li] = self._contour_from_radii(
                cx, cy, layer_r[li], rot[li], segments, seg_angle, step)

        # ── 绘制填充（外→内，内层覆盖外层形成环效果）──
        _surf = pygame.Surface((self.WIDTH, self.HEIGHT), pygame.SRCALPHA)
        for li in (5, 4, 3, 2, 1):
            if not self.config.get(f'c{li}_fill', False):
                continue
            f_alpha = self.config.get(f'c{li}_fill_alpha', 50)
            f_color = tuple(self.config.get(f'c{li}_color', (255, 255, 255)))
            _surf.fill((0, 0, 0, 0))
            if li == 3:
                pygame.draw.circle(_surf, (*f_color, f_alpha), (cx, cy), int(radius))
            else:
                pts = contour_pts.get(li)
                if pts and len(pts) >= 3:
                    pygame.draw.polygon(_surf, (*f_color, f_alpha), pts)
                else:
                    continue
            self.screen.blit(_surf, (0, 0))

        # ── 绘制条形层（外→内，内层在上）──
        bar_pairs = [(4, 5, 'b45'), (3, 4, 'b34'), (2, 3, 'b23'), (1, 2, 'b12')]
        for li_a, li_b, key in bar_pairs:
            if not self.config.get(f'{key}_on', False):
                continue
            thick = self.config.get(f'{key}_thick', 3)
            self._draw_bars_between(cx, cy, layer_r[li_a], layer_r[li_b],
                                    rot[li_a], rot[li_b],
                                    segments, seg_angle, thick, lengths, key)

        # ── 绘制轮廓线（外→内，内层在上）──
        for li in (5, 4, 3, 2, 1):
            if not self.config.get(f'c{li}_on', False):
                continue
            c_color = tuple(self.config.get(f'c{li}_color', (255, 255, 255)))
            c_alpha = self.config.get(f'c{li}_alpha', 180)
            c_thick = self.config.get(f'c{li}_thick', 2)
            if li == 3:
                _surf.fill((0, 0, 0, 0))
                pygame.draw.circle(_surf, (*c_color, c_alpha), (cx, cy), int(radius), c_thick)
                self.screen.blit(_surf, (0, 0))
            else:
                pts = contour_pts.get(li)
                if pts and len(pts) >= 3:
                    _surf.fill((0, 0, 0, 0))
                    pygame.draw.lines(_surf, (*c_color, c_alpha), True, pts, c_thick)
                    self.screen.blit(_surf, (0, 0))

    # ── 实时配置更新 ──────────────────────────────────────

    def _update_config_from_queue(self):
        if not self.config_queue:
            return
        try:
            while True:
                new = self.config_queue.get_nowait()

                # 特殊命令
                if 'command' in new:
                    if new['command'] == 'center_window':
                        self._center_window()
                    continue

                old = self.config.copy()
                self.config = new

                # 频谱条数量变化
                if new.get('num_bars', 64) != self.NUM_BARS:
                    self.NUM_BARS = new['num_bars']
                    self.bar_width = self.WIDTH // self.NUM_BARS
                    old_h = self.bar_heights
                    self.bar_heights = np.zeros(self.NUM_BARS)
                    self.bar_velocities = np.zeros(self.NUM_BARS)
                    self.peak_outer_heights = np.zeros(self.NUM_BARS)
                    self.peak_inner_heights = np.zeros(self.NUM_BARS)
                    n = min(len(old_h), self.NUM_BARS)
                    self.bar_heights[:n] = old_h[:n]
                    self._update_colors()

                # 实时参数
                self.smoothing_factor = new.get('smoothing', 0.7)
                self.damping = new.get('damping', 0.85)
                self.spring_strength = new.get('spring_strength', 0.3)
                self.gravity = new.get('gravity', 0.5)
                self.a1_time_window = new.get('a1_time_window', 10)

                self.ui_bg_alpha = new.get('ui_alpha', 180)

                # 点击穿透 / 拖动调整模式
                if new.get('drag_adjust_mode', False) != old.get('drag_adjust_mode', False):
                    self._set_click_through(not new.get('drag_adjust_mode', False))
                    self.dragging = False

                # 颜色变化（分区预设读取时也需要立即生效）
                if (
                    new.get('color_scheme') != old.get('color_scheme') or
                    new.get('gradient_points') != old.get('gradient_points') or
                    new.get('gradient_enabled') != old.get('gradient_enabled') or
                    new.get('gradient_mode') != old.get('gradient_mode') or
                    new.get('color_dynamic') != old.get('color_dynamic') or
                    new.get('color_cycle_speed') != old.get('color_cycle_speed') or
                    new.get('color_cycle_pow') != old.get('color_cycle_pow') or
                    new.get('color_cycle_a1') != old.get('color_cycle_a1')
                ):
                    self._update_colors()

                # 位置同步（来自控制台手动设置，可视化中心点）
                new_cx = new.get('pos_x', -1)
                new_cy = new.get('pos_y', -1)
                old_cx = old.get('pos_x', -1)
                old_cy = old.get('pos_y', -1)
                if (new_cx, new_cy) != (old_cx, old_cy):
                    if new_cx >= 0:
                        self.center_x = new_cx
                    if new_cy >= 0:
                        self.center_y = new_cy
        except queue.Empty:
            pass

    # ── 主循环 ────────────────────────────────────────────

    def run(self):
        print("圆形频谱 - 进入主循环")
        running = True

        while running:
            self._update_config_from_queue()

            # 定期发送状态（降低频率减少UI干扰）
            now = time.time()
            if now - self.last_status_send >= 2.0:  # 2秒发送一次
                self._send_status()
                self.last_status_send = now

            # 事件
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_q):
                        running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.config.get('drag_adjust_mode', False):
                        if self.drag_handle_rect.collidepoint(event.pos):
                            # 开始拖动：记录当前全局鼠标位置和当前中心点
                            self.dragging = True
                            try:
                                user32 = ctypes.windll.user32
                                pt = wintypes.POINT()
                                user32.GetCursorPos(ctypes.byref(pt))
                                self.drag_start_cursor = (pt.x, pt.y)
                                self.center_drag_start = (self.center_x, self.center_y)
                            except Exception:
                                self.drag_start_cursor = None
                                self.center_drag_start = None
                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    self.dragging = False
                    self.drag_start_cursor = None
                    self.center_drag_start = None
                elif event.type == pygame.MOUSEMOTION:
                    if self.config.get('drag_adjust_mode', False):
                        self.drag_handle_hover = self.drag_handle_rect.collidepoint(event.pos)
                    if self.dragging and self.config.get('drag_adjust_mode', False):
                        # 使用相对位移来移动可视化中心，避免 DPI / 全局坐标问题
                        self._move_window(event)

            # 清屏
            self.screen.fill(self.transparent_color)

            # 动态颜色循环
            ea1 = self.effective_a1
            if self.config.get('color_dynamic', False):
                base_hue_speed = 0.001
                if self.config.get('color_cycle_a1', True) and ea1 > 0:
                    base_hue_speed *= 1.0 + (ea1 / 1000.0) * 2.0
                spd = self.config.get('color_cycle_speed', 1.0)
                pw = self.config.get('color_cycle_pow', 2.0)
                self.color_cycle_hue = (self.color_cycle_hue + base_hue_speed * pow(spd, pw)) % 1.0
                self._update_colors()

            # 获取音频数据
            if not self.audio_queue.empty():
                try:
                    bar_values = self._process_audio(self.audio_queue.get_nowait())
                except queue.Empty:
                    bar_values = np.zeros(self.NUM_BARS)
            else:
                bar_values = np.zeros(self.NUM_BARS)

            # 绘制圆形频谱
            self._draw_circular_spectrum(bar_values)

            # 拖动区域提示
            self._draw_drag_handle()

            pygame.display.flip()
            self.clock.tick(60)

        self._cleanup()

    def _cleanup(self):
        if hasattr(self, 'stream'):
            self.stream.stop_stream()
            self.stream.close()
        if hasattr(self, 'p'):
            self.p.terminate()
        pygame.quit()
        print("圆形频谱窗口已关闭")


# ── 独立运行入口 ──────────────────────────────────────────

def run_standalone():
    """独立运行（使用默认配置）"""
    print("========== 圆形频谱独立运行 ==========")
    viz = CircularVisualizerWindow()
    viz.run()


def run_from_main(config_queue, status_queue):
    """被主框架调用"""
    print("========== 圆形频谱（主框架模式） ==========")
    try:
        viz = CircularVisualizerWindow(config_queue, status_queue)
        viz.run()
    except Exception as e:
        print(f"圆形频谱进程错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_standalone()
