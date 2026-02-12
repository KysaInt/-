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
    'bg_transparent': True, 'always_on_top': True,
    'num_bars': 64, 'smoothing': 0.7,
    'damping': 0.85, 'spring_strength': 0.3, 'gravity': 0.5,
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

        # 字体
        self.font_small = pygame.font.Font(None, 24)

        # 透明
        self.transparent_color = (0, 0, 0)
        self.window_alpha = self.config['alpha']
        self.ui_bg_alpha = self.config['ui_alpha']

        # 锁定按钮
        self.lock_button_size = 50
        self.lock_button_rect = pygame.Rect(
            self.WIDTH - self.lock_button_size - 10, 10,
            self.lock_button_size, self.lock_button_size
        )
        self.lock_button_visible = True
        self.lock_button_hover = False
        self.is_locked = False
        self.hover_timer = time.time()
        self.hide_delay = 2.0

        # 窗口拖动
        self.dragging = False
        self.drag_offset = (0, 0)

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

    # ── A1 ────────────────────────────────────────────────

    def _update_a1(self, loudness):
        now = time.time()
        self.loudness_history.append((now, loudness))
        cutoff = now - self.a1_time_window
        self.loudness_history = [(t, l) for t, l in self.loudness_history if t >= cutoff]
        self.a1_value = np.mean([l for _, l in self.loudness_history]) if self.loudness_history else 0.0

    def _send_status(self):
        if not self.status_queue or self.status_queue.full():
            return
        try:
            while not self.status_queue.empty():
                try:
                    self.status_queue.get_nowait()
                except:
                    break
            self.status_queue.put({'a1': self.a1_value})
        except:
            pass

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
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | 0x00080000 | 0x00000008)

            if self.config.get('bg_transparent', True):
                ck = self.transparent_color[0] | (self.transparent_color[1] << 8) | (self.transparent_color[2] << 16)
                user32.SetLayeredWindowAttributes(hwnd, ck, 0, 0x00000001)

            if self.config.get('always_on_top', True):
                user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0040)

            self._center_window()
            print("✓ 透明悬浮窗口设置成功")
        except Exception as e:
            print(f"警告: 设置透明窗口失败: {e}")

    def _center_window(self):
        try:
            user32 = ctypes.windll.user32
            sw = user32.GetSystemMetrics(0)
            sh = user32.GetSystemMetrics(1)
            if self.WIDTH >= sw or self.HEIGHT >= sh:
                return
            hwnd = pygame.display.get_wm_info()["window"]
            x = (sw - self.WIDTH) // 2
            y = (sh - self.HEIGHT) // 2
            user32.SetWindowPos(hwnd, 0, x, y, 0, 0, 0x0004 | 0x0001 | 0x0040)
        except Exception as e:
            print(f"警告: 居中窗口失败: {e}")

    def _move_window(self, mouse_pos):
        try:
            hwnd = pygame.display.get_wm_info()["window"]
            user32 = ctypes.windll.user32
            pt = wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            user32.SetWindowPos(hwnd, -1, pt.x - self.drag_offset[0], pt.y - self.drag_offset[1], 0, 0, 0x0001 | 0x0040)
        except:
            pass

    # ── 锁定按钮 ─────────────────────────────────────────

    def _draw_lock_button(self):
        if not self.lock_button_visible:
            return
        bg = pygame.Surface((self.lock_button_size, self.lock_button_size), pygame.SRCALPHA)
        bg.fill((120, 120, 120, 240) if self.lock_button_hover else (60, 60, 60, 200))
        self.screen.blit(bg, self.lock_button_rect.topleft)
        pygame.draw.rect(
            self.screen,
            (200, 200, 200) if self.lock_button_hover else (100, 100, 100),
            self.lock_button_rect, 2,
        )
        icon = pygame.font.Font(None, 32).render("🔒" if self.is_locked else "🔓", True, (255, 255, 255))
        self.screen.blit(icon, icon.get_rect(center=self.lock_button_rect.center))

        if self.lock_button_hover:
            txt = "锁定" if self.is_locked else "解锁-可拖动"
            surf = pygame.font.Font(None, 20).render(txt, True, (255, 255, 255))
            r = surf.get_rect(centerx=self.lock_button_rect.centerx, top=self.lock_button_rect.bottom + 8)
            hint_bg = pygame.Surface((r.width + 12, r.height + 6), pygame.SRCALPHA)
            hint_bg.fill((30, 30, 30, 220))
            self.screen.blit(hint_bg, (r.left - 6, r.top - 3))
            self.screen.blit(surf, r)

    def _check_lock_hover(self, pos):
        hover_area = pygame.Rect(self.WIDTH - 120, 0, 120, 100)
        if hover_area.collidepoint(pos):
            self.lock_button_visible = True
            self.hover_timer = time.time()
            self.lock_button_hover = self.lock_button_rect.collidepoint(pos)
        elif time.time() - self.hover_timer > self.hide_delay:
            self.lock_button_visible = False
            self.lock_button_hover = False

    def _handle_lock_click(self, pos):
        if self.lock_button_rect.collidepoint(pos):
            self.is_locked = not self.is_locked
            return True
        return False

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

        cx, cy = self.WIDTH // 2, self.HEIGHT // 2
        base_radius = self.config.get('circle_radius', 150)
        segments = self.config.get('circle_segments', 1)
        seg_angle = 2 * np.pi / segments

        # ── A1 驱动半径（弹性缓动）──
        target_radius = base_radius
        if self.config.get('circle_a1_radius', True) and self.a1_value > 0:
            target_radius = base_radius + (self.a1_value / 1000.0) * 100
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
        lengths = np.clip(self.bar_heights, bar_len_min, bar_len_max)

        # ── 峰值跟踪 ──
        decay_1 = self.config.get('c1_decay', 0.995)
        decay_5 = self.config.get('c5_decay', 0.995)
        self.peak_inner_heights = np.maximum(lengths, self.peak_inner_heights * decay_1)
        self.peak_outer_heights = np.maximum(lengths, self.peak_outer_heights * decay_5)

        # ── 每层独立旋转 ──
        a1_delta = abs(self.a1_value - self.prev_a1_value)
        self.prev_a1_value = self.a1_value
        norm_delta = min(a1_delta / 500.0, 1.0)
        for li in range(1, 6):
            spd = self.config.get(f'c{li}_rot_speed', 1.0)
            pw  = self.config.get(f'c{li}_rot_pow', 0.5)
            if self.config.get('circle_a1_rotation', True) and norm_delta > 1e-4:
                if pw >= 0:
                    factor = pow(norm_delta + 0.001, pw)
                else:
                    factor = max(0.0, 1.0 - pow(norm_delta, abs(pw)))
                self.layer_rotations[li] += spd * factor * 2.0
            else:
                self.layer_rotations[li] += spd * 0.1
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
            while not self.config_queue.empty():
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

                # 实时参数
                self.smoothing_factor = new.get('smoothing', 0.7)
                self.damping = new.get('damping', 0.85)
                self.spring_strength = new.get('spring_strength', 0.3)
                self.gravity = new.get('gravity', 0.5)
                self.a1_time_window = new.get('a1_time_window', 10)

                self.ui_bg_alpha = new.get('ui_alpha', 180)

                # 颜色变化
                if (new.get('color_scheme') != old.get('color_scheme') or
                        new.get('gradient_points') != old.get('gradient_points')):
                    self._update_colors()

                self.lock_button_rect = pygame.Rect(
                    self.WIDTH - self.lock_button_size - 10, 10,
                    self.lock_button_size, self.lock_button_size,
                )
        except queue.Empty:
            pass

    # ── 主循环 ────────────────────────────────────────────

    def run(self):
        print("圆形频谱 - 进入主循环")
        running = True

        while running:
            self._update_config_from_queue()

            # 定期发送状态
            now = time.time()
            if now - self.last_status_send >= 1.0:
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
                    if self._handle_lock_click(event.pos):
                        continue
                    if not self.is_locked:
                        self.dragging = True
                        self.drag_offset = event.pos
                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    self.dragging = False
                elif event.type == pygame.MOUSEMOTION:
                    self._check_lock_hover(event.pos)
                    if self.dragging and not self.is_locked:
                        self._move_window(event.pos)

            # 清屏
            self.screen.fill(self.transparent_color)

            # 动态颜色循环
            if self.config.get('color_dynamic', False):
                base_hue_speed = 0.001
                if self.config.get('color_cycle_a1', True) and self.a1_value > 0:
                    base_hue_speed *= 1.0 + (self.a1_value / 1000.0) * 2.0
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

            # 锁定按钮
            self._draw_lock_button()

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
