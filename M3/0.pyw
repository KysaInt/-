"""
音频可视化控制台 - 主框架
支持选择不同可视化模式（当前仅圆形频谱）
通过 multiprocessing 启动子程序并实时传递配置
"""

import os
import sys
import json
import time
import random
import re
import subprocess
import colorsys
import threading
import multiprocessing as mp
from urllib import request, parse
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QSlider,
    QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox,
    QInputDialog, QDialog, QListWidget, QLineEdit, QFileDialog,
    QFrame, QMessageBox, QScrollArea,
    QStackedWidget,
    QTreeWidget, QTreeWidgetItem,
    QMenu,
    QAbstractSpinBox,
    QProxyStyle, QStyle, QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer, Signal, QPoint, QRectF
from PySide6.QtGui import QFont, QColor, QPalette, QPainter, QPen, QCursor, QLinearGradient

from unity_exporter import (
    build_unity_export_path,
    export_unity_component,
    list_unity_shared_prerequisite_paths,
    normalize_unity_project_dir,
    sanitize_csharp_identifier,
    suggest_export_path,
)


# -- 合并自 1.pyw 的依赖 import ------------------------------------------
import ctypes
import math
import queue as _std_queue
import queue  # 兼容 CircularVisualizerWindow._update_config_from_queue 里的 queue.Empty

import numpy as np

try:
    from scipy.interpolate import BSpline
    _HAS_SCIPY_BSPLINE = True
except Exception:
    BSpline = None
    _HAS_SCIPY_BSPLINE = False

from OpenGL import GL

from PySide6.QtCore import QPointF, QRect
from PySide6.QtGui import QGuiApplication, QImage, QPainterPath, QPolygon, QSurfaceFormat
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from core.audio_runtime import AudioSignalProcessor, LoopbackAudioCapture
from core.lens_scratch_gl import LensScratchGL, _gen_procedural_scratch_mask
# -- 合并 import 结束 -------------------------------------------------------
CONFIG_FILE = Path(__file__).parent / 'visualizer_config.json'
PRESETS_DIR = Path(__file__).parent / 'presets'
SECTION_PRESETS_DIR = Path(__file__).parent / 'section_presets'

PRESET_CATEGORY_ALL = 'all'
PRESET_CATEGORY_CLASSIC = 'classic'
PRESET_CATEGORY_JELLYFISH = 'jellyfish'
PRESET_CATEGORY_LABELS = {
    PRESET_CATEGORY_ALL: '全部预设',
    PRESET_CATEGORY_CLASSIC: '原有主题',
    PRESET_CATEGORY_JELLYFISH: '柔体主题',
}
PRESET_CATEGORY_BADGES = {
    PRESET_CATEGORY_CLASSIC: '原有',
    PRESET_CATEGORY_JELLYFISH: '柔体',
}
SECTION_PRESET_LABELS = {
    'color': '颜色方案',
    'physics': '运动表现',
    'contour': '填充子主题',
    'tentacle': '柔体主题',
    'bars': '连线子主题',
    'graphics': '图元设置',
}

_DAMPED_OBJECT_KEYS = ('bar', 'c1', 'c2', 'c4', 'c5', 'b12', 'b23', 'b34', 'b45')

_THEME_PRESET_SECTIONS = (
    'theme_classic_kaleidoscope',
    'theme_kaleidoscope_fill',
    'theme_kaleidoscope_lines',
    'theme_softbody',
)

_CONTOUR_KP_KEYS = tuple(
    f'c{layer}_{suffix}'
    for layer in range(1, 6)
    for suffix in ('thick', 'alpha', 'fill_alpha', 'step', 'decay', 'rot_speed', 'rot_pow')
)
_BAR_KP_KEYS = tuple(
    f'{prefix}_{suffix}'
    for prefix in ('b12', 'b23', 'b34', 'b45')
    for suffix in ('thick', 'fixed_len')
)

_SECTION_DISPLAY_NAMES = {
    'color': '颜色方案',
    'physics': '运动表现',
    'graphics': '图元设置',
    'theme_classic_kaleidoscope': '经典主题',
    'theme_kaleidoscope_fill': '填充子主题',
    'theme_kaleidoscope_lines': '连线子主题',
    'theme_softbody': '柔体主题',
}

_DEFAULT_CONFIG = {
    'width': 0, 'height': 0, 'alpha': 255, 'ui_alpha': 180,
    'global_scale': 1.0, 'pos_x': -1, 'pos_y': -1,
    'drag_adjust_mode': False,
    'bg_transparent': True, 'always_on_top': True, 'window_layer': 'top',
    'num_bars': 64, 'smoothing': 0.7,
    'k_rise_damping': 0.1, 'k_fall_damping': 0.999,
    'bar_use_independent_damping': False,
    'bar_independent_rise_damping': 0.1, 'bar_independent_fall_damping': 0.999,
    'bar_use_independent_time_window': False, 'bar_time_window': 10.0,
    'rotation_base': 1.0, 'main_radius_scale': 1.0,
    'bar_height_min': 0, 'bar_height_max': 500,
    'bar_default_height': 0.0, 'bar_internal_min': 0.0, 'bar_internal_max': 300.0,
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
    'contours_enabled': True, 'bars_enabled': True, 'tentacles_enabled': True,
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
    # 四层条形  b12(L1-L2) b23(L2-L3) b34(L3-L4) b45(L4-L5)
    'b12_on': False, 'b12_thick': 2,
    'b12_fixed': False, 'b12_fixed_len': 30, 'b12_from_start': True, 'b12_from_end': False, 'b12_from_center': False,
    'b23_on': False, 'b23_thick': 3,
    'b23_fixed': False, 'b23_fixed_len': 30, 'b23_from_start': True, 'b23_from_end': False, 'b23_from_center': False,
    'b34_on': True,  'b34_thick': 3,
    'b34_fixed': False, 'b34_fixed_len': 30, 'b34_from_start': True, 'b34_from_end': False, 'b34_from_center': False,
    'b45_on': False, 'b45_thick': 2,
    'b45_fixed': False, 'b45_fixed_len': 30, 'b45_from_start': True, 'b45_from_end': False, 'b45_from_center': False,
    'tentacle_on': True,
    'tentacle_color': (130, 240, 220),
    'tentacle_alpha': 170,
    'tentacle_thick': 3,
    'tentacle_count': 16,
    'tentacle_length': 280,
    'tentacle_length_jitter': 80,
    'tentacle_length_jitter_speed': 0.35,
    'tentacle_length_jitter_random': False,
    'tentacle_control_points_min': 3,
    'tentacle_control_points_max': 5,
    'tentacle_tip_bias': 1.85,
    'tentacle_turbulence': 46.0,
    'tentacle_k_influence': 1.35,
    'tentacle_sway_speed': 1.1,
    'tentacle_sway_density': 2.4,
    'tentacle_tip_thickness': 0.15,
    'tentacle_water_damping': 0.84,
    'tentacle_angle_stiffness': 0.18,
    'tentacle_length_stiffness': 0.24,
    'tentacle_stretch_limit': 1.12,
    'tentacle_shader_enabled': True,
    'tentacle_shader_tip_color': (88, 170, 255),
    'tentacle_shader_alpha_start': 1.0,
    'tentacle_shader_alpha_end': 0.18,
    'tentacle_shader_bias': 1.15,
    'tentacle_core_on': True,
    'tentacle_core_color': (225, 255, 245),
    'tentacle_core_alpha': 180,
    'tentacle_core_thick': 2,
    'tentacle_core_points': 6,
    'tentacle_core_outer_radius': 26.0,
    'tentacle_core_inner_ratio': 0.42,
    'tentacle_core_base_speed': 0.75,
    'tentacle_core_k_speed': 1.2,
    'tentacle_core_p_speed': 1.35,

    # K/P 绑定（触须相关：用于替代旧的“K影响 / K角加速度 / P角加速度”独立调节）
    'kp_bind_tentacle_turbulence_k': True,
    'kp_tentacle_turbulence_k_wmin': 0.22,
    'kp_tentacle_turbulence_k_wmax': 0.683,
    'kp_bind_tentacle_core_base_speed_k': True,
    'kp_tentacle_core_base_speed_k_wmin': 0.0,
    'kp_tentacle_core_base_speed_k_wmax': 1.2,
    'kp_bind_tentacle_core_base_speed_p': True,
    'kp_tentacle_core_base_speed_p_wmin': 0.0,
    'kp_tentacle_core_base_speed_p_wmax': 1.35,
    # ── 镜头划痕眩光后处理 ──────────────────────────────────────────────────
    'lens_scratch_enabled': False,
    'lens_scratch_mask_path': '',
    'lens_scratch_normal_path': '',
    'lens_scratch_tiling_x': 1.0,
    'lens_scratch_tiling_y': 1.0,
    'lens_scratch_offset_x': 0.0,
    'lens_scratch_offset_y': 0.0,
    'lens_scratch_rotation_deg': 0.0,
    'lens_scratch_mask_power': 1.35,
    'lens_scratch_normal_influence': 1.2,
    'lens_scratch_threshold': 1.1,
    'lens_scratch_soft_knee': 0.45,
    'lens_scratch_glare_intensity': 1.15,
    'lens_scratch_count_a': 20,
    'lens_scratch_streak_count': 3,
    'lens_scratch_scratch_count': 3,
    'lens_scratch_streak_length': 3.6,
    'lens_scratch_streak_spread': 1.1,
    'lens_scratch_falloff_a': 3.8,
    'lens_scratch_falloff_b': 0.35,
    'lens_scratch_rotation_jitter_deg': 6.0,
    'lens_scratch_refraction_strength': 0.18,
    'lens_scratch_chromatic_aberration': 0.0025,
    'lens_scratch_micro_distortion': 0.55,
    'lens_scratch_tint_r': 255,
    'lens_scratch_tint_g': 255,
    'lens_scratch_tint_b': 255,
    'kp_bind_lens_scratch_glare_intensity_k': False,
    'kp_lens_scratch_glare_intensity_k_wmin': 0.0,
    'kp_lens_scratch_glare_intensity_k_wmax': 0.0,
    'kp_bind_lens_scratch_threshold_k': False,
    'kp_lens_scratch_threshold_k_wmin': 0.0,
    'kp_lens_scratch_threshold_k_wmax': 0.0,
    'kp_bind_lens_scratch_streak_length_k': False,
    'kp_lens_scratch_streak_length_k_wmin': 0.0,
    'kp_lens_scratch_streak_length_k_wmax': 0.0,
    'kp_bind_lens_scratch_refraction_strength_k': False,
    'kp_lens_scratch_refraction_strength_k_wmin': 0.0,
    'kp_lens_scratch_refraction_strength_k_wmax': 0.0,
    'kp_bind_lens_scratch_chromatic_aberration_k': False,
    'kp_lens_scratch_chromatic_aberration_k_wmin': 0.0,
    'kp_lens_scratch_chromatic_aberration_k_wmax': 0.0,
    'random_checked': [],
    'random_object_count_min': 1,
    'random_object_count_max': 10,
    'preset_order': [],
    'preset_auto_switch': False,
    'preset_switch_random_enabled': False,
    'preset_switch_infinite_random_enabled': False,
    'preset_switch_interval': 10.0,
    'preset_interval_random_enabled': False,
    'preset_switch_interval_min': 1.0,
    'preset_switch_interval_max': 10.0,
    'preset_transition_enabled': False,
    'preset_transition_duration': 2.0,
    'preset_transition_easing': 'ease_in_out',
    'last_preset': '',
}

for _prefix in _DAMPED_OBJECT_KEYS[1:]:
    _DEFAULT_CONFIG[f'{_prefix}_use_independent_damping'] = False
    _DEFAULT_CONFIG[f'{_prefix}_independent_rise_damping'] = 0.1
    _DEFAULT_CONFIG[f'{_prefix}_independent_fall_damping'] = 0.999

for _cfg_key in _CONTOUR_KP_KEYS + _BAR_KP_KEYS:
    for _sig in ('k', 'p'):
        _DEFAULT_CONFIG[f'kp_bind_{_cfg_key}_{_sig}'] = False
        _DEFAULT_CONFIG[f'kp_{_cfg_key}_{_sig}_wmin'] = 0.0
        _DEFAULT_CONFIG[f'kp_{_cfg_key}_{_sig}_wmax'] = 0.0


def _kp_binding_config_keys(cfg_keys, supports=('k', 'p')):
    keys = []
    for cfg_key in cfg_keys:
        for sig in supports:
            keys.append(f'kp_bind_{cfg_key}_{sig}')
            keys.append(f'kp_{cfg_key}_{sig}_wmin')
            keys.append(f'kp_{cfg_key}_{sig}_wmax')
    return keys


def _get_defaults():
    import copy
    return copy.deepcopy(_DEFAULT_CONFIG)


def _clamp_time_window(value, fallback=10.0):
    try:
        return max(0.01, float(value))
    except Exception:
        return max(0.01, float(fallback))


def _normalize_loaded_config(data):
    cfg = _get_defaults()
    loaded = dict(data or {})
    loaded.pop('__preset_category', None)

    legacy_rise = float(loaded.get('bar_rise_damping', loaded.get('damping', cfg['k_rise_damping'])))
    legacy_fall = float(loaded.get('bar_fall_damping', loaded.get('damping', cfg['k_fall_damping'])))
    loaded.setdefault('k_rise_damping', max(0.0, min(0.999, legacy_rise)))
    loaded.setdefault('k_fall_damping', max(0.0, min(0.999, legacy_fall)))
    loaded.setdefault('bar_use_independent_damping', False)
    loaded.setdefault('bar_independent_rise_damping', max(0.0, min(0.999, legacy_rise)))
    loaded.setdefault('bar_independent_fall_damping', max(0.0, min(0.999, legacy_fall)))
    loaded.setdefault('bar_use_independent_time_window', False)
    loaded.setdefault('bar_time_window', _clamp_time_window(loaded.get('a1_time_window', cfg['a1_time_window']), cfg['a1_time_window']))
    loaded.setdefault('window_layer', 'top' if loaded.get('always_on_top', cfg['always_on_top']) else 'normal')
    for prefix in _DAMPED_OBJECT_KEYS[1:]:
        loaded.setdefault(f'{prefix}_use_independent_damping', False)
        loaded.setdefault(f'{prefix}_independent_rise_damping', loaded['k_rise_damping'])
        loaded.setdefault(f'{prefix}_independent_fall_damping', loaded['k_fall_damping'])

    # ── 触须：旧参数迁移到新的 K/P 绑定（仅在用户未显式设置新键时）
    if 'kp_bind_tentacle_turbulence_k' not in loaded and 'tentacle_k_influence' in loaded:
        try:
            kinf = max(0.0, float(loaded.get('tentacle_k_influence', 1.35)))
            wmin = 0.22
            wmax = wmin + min(0.55, wmin + kinf * 0.18)
            loaded.setdefault('kp_bind_tentacle_turbulence_k', True)
            loaded.setdefault('kp_tentacle_turbulence_k_wmin', wmin)
            loaded.setdefault('kp_tentacle_turbulence_k_wmax', wmax)
        except Exception:
            pass

    if 'kp_bind_tentacle_core_base_speed_k' not in loaded and 'tentacle_core_k_speed' in loaded:
        try:
            loaded.setdefault('kp_bind_tentacle_core_base_speed_k', True)
            loaded.setdefault('kp_tentacle_core_base_speed_k_wmin', 0.0)
            loaded.setdefault('kp_tentacle_core_base_speed_k_wmax', float(loaded.get('tentacle_core_k_speed', 1.2)))
        except Exception:
            pass

    if 'kp_bind_tentacle_core_base_speed_p' not in loaded and 'tentacle_core_p_speed' in loaded:
        try:
            loaded.setdefault('kp_bind_tentacle_core_base_speed_p', True)
            loaded.setdefault('kp_tentacle_core_base_speed_p_wmin', 0.0)
            loaded.setdefault('kp_tentacle_core_base_speed_p_wmax', float(loaded.get('tentacle_core_p_speed', 1.35)))
        except Exception:
            pass

    cfg.update(loaded)
    cfg['a1_time_window'] = _clamp_time_window(cfg.get('a1_time_window', _DEFAULT_CONFIG['a1_time_window']), _DEFAULT_CONFIG['a1_time_window'])
    cfg['bar_time_window'] = _clamp_time_window(cfg.get('bar_time_window', cfg['a1_time_window']), cfg['a1_time_window'])
    cfg['bar_use_independent_time_window'] = bool(cfg.get('bar_use_independent_time_window', False))
    cfg.pop('freq_band_mode', None)
    cfg.pop('bar_a1_influence', None)
    cfg.pop('bar_rise_damping', None)
    cfg.pop('bar_fall_damping', None)
    cfg.pop('damping', None)
    cfg.pop('spring_strength', None)
    cfg.pop('gravity', None)
    cfg.pop('preset_category_filter', None)
    if cfg.get('window_layer') not in {'top', 'normal', 'bottom'}:
        cfg['window_layer'] = 'top' if cfg.get('always_on_top', True) else 'normal'
    cfg['always_on_top'] = (cfg.get('window_layer') == 'top')
    return cfg


def _active_palette_color(role):
    palette = QApplication.palette()
    try:
        return QColor(palette.color(QPalette.ColorGroup.Active, role))
    except TypeError:
        return QColor(palette.color(role))


def _inverse_color(color):
    return QColor(255 - int(color.red()), 255 - int(color.green()), 255 - int(color.blue()), int(color.alpha()))


def _sample_preview_color(colors, phase):
    normalized = [tuple(int(channel) for channel in color[:3]) for color in (colors or []) if len(color) >= 3]
    if not normalized:
        red, green, blue = colorsys.hsv_to_rgb(phase % 1.0, 1.0, 1.0)
        return int(red * 255), int(green * 255), int(blue * 255)
    index = int(round((phase % 1.0) * max(0, len(normalized) - 1)))
    return normalized[index % len(normalized)]


class _Collapsible(QWidget):
    """可折叠分组控件"""
    def __init__(self, title, parent=None, expanded=True):
        super().__init__(parent)
        self._title = title
        vl = QVBoxLayout(self)
        vl.setContentsMargins(0, 0, 0, 0); vl.setSpacing(0)
        self._btn = QPushButton(("▾ " if expanded else "▸ ") + title)
        self._btn.setCheckable(True); self._btn.setChecked(expanded)
        pal = QApplication.palette()
        hi = pal.color(QPalette.ColorRole.Highlight)
        base = pal.color(QPalette.ColorRole.Button)
        hi_txt = pal.color(QPalette.ColorRole.HighlightedText)
        self._btn.setStyleSheet(
            f"QPushButton{{text-align:left;padding:4px 8px;font-weight:bold;"
            f"background:{base.name()};color:{pal.color(QPalette.ColorRole.ButtonText).name()};"
            f"border:none;border-radius:2px;margin-top:1px;}}"
            f"QPushButton:checked{{background:{hi.name()};color:{hi_txt.name()};}}"
            f"QPushButton:hover{{background:{hi.lighter(130).name()};}}")
        self._body = QWidget()
        self._body_lay = QVBoxLayout(self._body)
        self._body_lay.setContentsMargins(6, 2, 2, 4); self._body_lay.setSpacing(0)
        self._body.setVisible(expanded)
        self._btn.toggled.connect(self._flip)
        vl.addWidget(self._btn); vl.addWidget(self._body)

    def set_header_visible(self, visible: bool):
        self._btn.setVisible(visible)

    def set_expanded(self, expanded: bool):
        self._btn.setChecked(expanded)
        self._body.setVisible(expanded)
        self._btn.setText(("▾ " if expanded else "▸ ") + self._title)

    def as_detail_panel(self):
        """用于右侧详情页：隐藏标题按钮并强制展开"""
        self.set_header_visible(False)
        self.set_expanded(True)
        # 详情页中减少顶部空隙
        self._body_lay.setContentsMargins(0, 0, 0, 0)

    def _flip(self, on):
        self._body.setVisible(on)
        self._btn.setText(("▾ " if on else "▸ ") + self._title)

    def add_layout(self, layout):
        self._body_lay.addLayout(layout)

    def add_widget(self, widget):
        self._body_lay.addWidget(widget)


class _YellowCheckBoxStyle(QProxyStyle):
    """复选框样式：灰色外框、透明底；勾选后黄色对勾。"""

    def drawPrimitive(self, element, option, painter, widget=None):
        if element == QStyle.PE_IndicatorCheckBox:
            rect = option.rect

            painter.save()
            painter.setRenderHint(QPainter.Antialiasing, True)

            border = QColor(140, 140, 140)
            painter.setPen(QPen(border, 1))
            painter.setBrush(Qt.NoBrush)
            r = rect.adjusted(1, 1, -1, -1)
            painter.drawRoundedRect(r, 2, 2)

            state_on = bool(option.state & QStyle.State_On)
            if state_on:
                # 黄色小勾（不填充底色）
                tick = QColor(255, 204, 0)
                painter.setPen(QPen(tick, 2))
                x1 = r.left() + int(r.width() * 0.20)
                y1 = r.top() + int(r.height() * 0.55)
                x2 = r.left() + int(r.width() * 0.42)
                y2 = r.top() + int(r.height() * 0.75)
                x3 = r.left() + int(r.width() * 0.80)
                y3 = r.top() + int(r.height() * 0.28)
                painter.drawLine(x1, y1, x2, y2)
                painter.drawLine(x2, y2, x3, y3)

            painter.restore()
            return

        super().drawPrimitive(element, option, painter, widget)


class _SoftRangeNumberMixin:
    """统一的软范围输入：右键弹出软上下限与默认值设置。"""

    def _init_soft_range(self, soft_min, soft_max, hard_min, hard_max, default_value=None):
        self._hard_min = self._coerce_value(hard_min)
        self._hard_max = self._coerce_value(hard_max)
        if self._hard_min > self._hard_max:
            self._hard_min, self._hard_max = self._hard_max, self._hard_min
        self.setRange(self._hard_min, self._hard_max)

        self._default_value = self._coerce_value(default_value if default_value is not None else self.value())
        self._soft_min = self._hard_min
        self._soft_max = self._hard_max
        self._bound_slider = None
        self._slider_scale = 1.0
        self._syncing_slider = False
        self._drag_adjust_pressed = False
        self._drag_adjust_active = False
        self._drag_adjust_start_x = 0.0
        self._drag_adjust_start_value = 0.0
        self.setKeyboardTracking(False)
        self.set_soft_range(soft_min, soft_max, sync_slider=False)

    def _clamp_hard(self, value):
        return min(self._hard_max, max(self._hard_min, self._coerce_value(value)))

    def _expand_hard_range_to_include(self, lo, hi):
        lo = self._coerce_value(lo)
        hi = self._coerce_value(hi)
        if lo > hi:
            lo, hi = hi, lo
        changed = False
        if lo < self._hard_min:
            self._hard_min = lo
            changed = True
        if hi > self._hard_max:
            self._hard_max = hi
            changed = True
        if changed:
            self.setRange(self._hard_min, self._hard_max)

    def set_default_value(self, value):
        self._default_value = self._clamp_hard(value)

    def default_value(self):
        return self._default_value

    def soft_min(self):
        return self._soft_min

    def soft_max(self):
        return self._soft_max

    def set_soft_range(self, soft_min, soft_max, sync_slider=True):
        # 用户可在右键弹窗里设置任意上下限：当超过原硬范围时自动扩展硬范围
        lo = self._coerce_value(soft_min)
        hi = self._coerce_value(soft_max)
        if lo > hi:
            lo, hi = hi, lo
        self._expand_hard_range_to_include(lo, hi)
        self._soft_min = lo
        self._soft_max = hi
        if sync_slider:
            self._apply_soft_range_to_slider()
            self._sync_slider_from_value(self.value())

    def reset_to_default_value(self):
        self.setValue(self._default_value)

    def bind_slider(self, slider, slider_scale=1.0):
        self._bound_slider = slider
        self._slider_scale = float(slider_scale) if slider_scale else 1.0
        self._apply_soft_range_to_slider()
        slider.valueChanged.connect(self._on_slider_changed)
        self.valueChanged.connect(self._sync_slider_from_value)
        self._sync_slider_from_value(self.value())

    def _slider_to_value(self, slider_value):
        return self._coerce_value(float(slider_value) / self._slider_scale)

    def _value_to_slider(self, value):
        return int(round(float(value) * self._slider_scale))

    def _apply_soft_range_to_slider(self):
        if not self._bound_slider:
            return
        slider_min = self._value_to_slider(self._soft_min)
        slider_max = self._value_to_slider(self._soft_max)
        if slider_min > slider_max:
            slider_min, slider_max = slider_max, slider_min
        self._bound_slider.setRange(slider_min, slider_max)

    def _sync_slider_from_value(self, value):
        if not self._bound_slider or self._syncing_slider:
            return
        self._syncing_slider = True
        try:
            slider_value = self._value_to_slider(value)
            slider_value = max(self._bound_slider.minimum(), min(self._bound_slider.maximum(), slider_value))
            self._bound_slider.setValue(slider_value)
        finally:
            self._syncing_slider = False

    def _on_slider_changed(self, slider_value):
        if self._syncing_slider:
            return
        self._syncing_slider = True
        try:
            self.setValue(self._slider_to_value(slider_value))
        finally:
            self._syncing_slider = False

    def _step_target(self, steps):
        current = self.value()
        step = self.singleStep() or 1
        if steps > 0:
            if current < self._soft_min:
                return self._soft_min
            return min(current + steps * step, self._soft_max)
        if current > self._soft_max:
            return self._soft_max
        return max(current + steps * step, self._soft_min)

    def stepBy(self, steps):
        if steps == 0:
            return
        self.setValue(self._coerce_value(self._step_target(steps)))

    def _create_limit_editor(self, value):
        raise NotImplementedError

    def _drag_value_delta(self, delta_x):
        raise NotImplementedError

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_adjust_pressed = True
            self._drag_adjust_active = False
            self._drag_adjust_start_x = float(event.globalPosition().x())
            self._drag_adjust_start_value = float(self.value())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_adjust_pressed:
            delta_x = float(event.globalPosition().x()) - self._drag_adjust_start_x
            if self._drag_adjust_active or abs(delta_x) >= 4.0:
                if not self._drag_adjust_active:
                    self._drag_adjust_active = True
                    self.setCursor(Qt.CursorShape.SizeHorCursor)
                    line_edit = self.lineEdit()
                    if line_edit is not None:
                        line_edit.deselect()
                self.setValue(self._clamp_hard(self._drag_adjust_start_value + self._drag_value_delta(delta_x)))
                event.accept()
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        had_drag = self._drag_adjust_active
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_adjust_pressed = False
            self._drag_adjust_active = False
            self.unsetCursor()
            if had_drag:
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        popup = _NumericAdjustPopup(self)
        popup.show_at(event.globalPos())
        event.accept()


class _SoftRangeSpinBox(_SoftRangeNumberMixin, QSpinBox):
    """整型软范围输入框：滚轮/步进限制在软范围，手动输入可超出软范围。"""

    def __init__(self, soft_min: int, soft_max: int, hard_min: int, hard_max: int, parent=None, default_value=None):
        super().__init__(parent)
        self._init_soft_range(soft_min, soft_max, hard_min, hard_max, default_value=default_value)

    def _coerce_value(self, value):
        return int(round(float(value)))

    def _create_limit_editor(self, value):
        editor = QSpinBox()
        editor.setRange(self._hard_min, self._hard_max)
        editor.setValue(self._coerce_value(value))
        return editor

    def _drag_value_delta(self, delta_x):
        step = self.singleStep() or 1
        return round(delta_x / 6.0) * step


class _SoftRangeDoubleSpinBox(_SoftRangeNumberMixin, QDoubleSpinBox):
    """浮点软范围输入框：滚轮/步进限制在软范围，手动输入可超出软范围。"""

    def __init__(self, soft_min: float, soft_max: float, hard_min: float, hard_max: float, parent=None, default_value=None):
        super().__init__(parent)
        self._init_soft_range(soft_min, soft_max, hard_min, hard_max, default_value=default_value)

    def _coerce_value(self, value):
        return float(value)

    def _create_limit_editor(self, value):
        editor = QDoubleSpinBox()
        editor.setDecimals(self.decimals())
        editor.setSingleStep(self.singleStep() or 0.01)
        editor.setRange(self._hard_min, self._hard_max)
        editor.setValue(self._coerce_value(value))
        return editor

    def _drag_value_delta(self, delta_x):
        step = self.singleStep() or 0.01
        return float(delta_x) * float(step)


class _NumericAdjustPopup(QDialog):
    """鼠标位置弹出的数值设置小窗。"""

    def __init__(self, target):
        super().__init__(target, Qt.Popup | Qt.FramelessWindowHint)
        self._target = target
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setObjectName("NumericAdjustPopup")
        self.setStyleSheet(
            "QDialog#NumericAdjustPopup{background:#1e1f23;border:1px solid #5b5d66;border-radius:8px;}"
            "QLabel{color:#d7d9de;}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        btn_reset = QPushButton("恢复默认值")
        btn_reset.clicked.connect(self._on_reset_clicked)
        root.addWidget(btn_reset)

        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(4)

        grid.addWidget(QLabel("滑块下限"), 0, 0)
        self.min_spin = self._create_unbounded_limit_editor(self._target.soft_min())
        grid.addWidget(self.min_spin, 0, 1)

        grid.addWidget(QLabel("滑块上限"), 1, 0)
        self.max_spin = self._create_unbounded_limit_editor(self._target.soft_max())
        grid.addWidget(self.max_spin, 1, 1)

        root.addLayout(grid)

        self.min_spin.valueChanged.connect(self._on_soft_range_changed)
        self.max_spin.valueChanged.connect(self._on_soft_range_changed)

    def _create_unbounded_limit_editor(self, value):
        # 右键弹窗里的上下限输入框：无按钮、超大范围、禁用滚轮避免“滑动误触”
        if isinstance(self._target, QDoubleSpinBox):
            editor = _NoWheelDoubleSpinBox()
            editor.setDecimals(self._target.decimals())
            editor.setSingleStep(self._target.singleStep() or 0.01)
            editor.setRange(-1_000_000_000.0, 1_000_000_000.0)
            editor.setValue(float(value))
        else:
            editor = _NoWheelSpinBox()
            editor.setSingleStep(self._target.singleStep() or 1)
            editor.setRange(-1_000_000_000, 1_000_000_000)
            editor.setValue(int(round(float(value))))
        editor.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        editor.setKeyboardTracking(False)
        editor.setFixedWidth(120)
        return editor

    def show_at(self, global_pos):
        self.adjustSize()
        screen = QApplication.screenAt(global_pos) or QApplication.primaryScreen()
        pos = QPoint(global_pos.x() + 12, global_pos.y() + 12)
        if screen:
            area = screen.availableGeometry()
            pos.setX(max(area.left(), min(pos.x(), area.right() - self.width() + 1)))
            pos.setY(max(area.top(), min(pos.y(), area.bottom() - self.height() + 1)))
        self.move(pos)
        self.show()

    def _on_reset_clicked(self):
        self._target.reset_to_default_value()

    def _on_soft_range_changed(self, _value):
        self._target.set_soft_range(self.min_spin.value(), self.max_spin.value())
        self._sync_from_target()

    def _sync_from_target(self):
        self.min_spin.blockSignals(True)
        self.max_spin.blockSignals(True)
        self.min_spin.setValue(self._target.soft_min())
        self.max_spin.setValue(self._target.soft_max())
        self.min_spin.blockSignals(False)
        self.max_spin.blockSignals(False)


class _NoWheelSpinBox(QSpinBox):
    def wheelEvent(self, event):
        event.ignore()


class _NoWheelDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, event):
        event.ignore()


class QuickColorPicker(QDialog):
    """鼠标位置展开的 HSL / RGB 小浮窗（实时同步）。"""
    colorSelected = Signal(tuple)

    def __init__(self, parent=None, initial=(255, 255, 255), presets=None, *, cfg_key_prefix: str | None = None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.selected_rgb = tuple(int(channel) for channel in initial)
        self._cfg_key_prefix = str(cfg_key_prefix) if cfg_key_prefix else "color_picker"
        self._mode = 'hsl'  # 'hsl' | 'rgb'
        self._host = parent
        self._kp_accent_color = _active_palette_color(QPalette.ColorRole.Highlight).name()
        self._kp_ui = {}
        self.setModal(True)
        self.setObjectName("ColorPopup")
        self.setStyleSheet(
            "QDialog#ColorPopup{background:#17181b;border:1px solid #4c4f57;border-radius:10px;}"
            "QLabel{color:#e4e6eb;}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        top = QHBoxLayout()
        self._title = QLabel("HSL")
        self._title.setStyleSheet("font-weight:bold;")
        self._title.mousePressEvent = lambda _ev: self._toggle_mode()
        top.addWidget(self._title)
        top.addStretch()
        self.preview = QFrame()
        self.preview.setFixedSize(18, 18)
        self.preview.setFrameShape(QFrame.StyledPanel)
        top.addWidget(self.preview)
        root.addLayout(top)

        # 两组控件：HSL（默认）与 RGB（点击标题切换）
        self._hsl_group = QWidget()
        self._hsl_layout = QVBoxLayout(self._hsl_group)
        self._hsl_layout.setContentsMargins(0, 0, 0, 0)
        self._hsl_layout.setSpacing(6)
        h, l, s = colorsys.rgb_to_hls(self.selected_rgb[0] / 255.0, self.selected_rgb[1] / 255.0, self.selected_rgb[2] / 255.0)
        self._hue_slider = self._make_row(self._hsl_layout, "H", 0, 359, int(round(h * 359.0)), cfg_key=self._channel_key('h'))
        self._sat_slider = self._make_row(self._hsl_layout, "S", 0, 100, int(round(s * 100.0)), cfg_key=self._channel_key('s'))
        self._light_slider = self._make_row(self._hsl_layout, "L", 0, 100, int(round(l * 100.0)), cfg_key=self._channel_key('l'))

        self._rgb_group = QWidget()
        self._rgb_layout = QVBoxLayout(self._rgb_group)
        self._rgb_layout.setContentsMargins(0, 0, 0, 0)
        self._rgb_layout.setSpacing(6)
        self._r_slider = self._make_row(self._rgb_layout, "R", 0, 255, int(self.selected_rgb[0]), cfg_key=self._channel_key('r'))
        self._g_slider = self._make_row(self._rgb_layout, "G", 0, 255, int(self.selected_rgb[1]), cfg_key=self._channel_key('g'))
        self._b_slider = self._make_row(self._rgb_layout, "B", 0, 255, int(self.selected_rgb[2]), cfg_key=self._channel_key('b'))

        root.addWidget(self._hsl_group)
        root.addWidget(self._rgb_group)
        self._rgb_group.setVisible(False)

        actions = QHBoxLayout()
        actions.addStretch()
        btn_ok = QPushButton("应用")
        btn_ok.clicked.connect(self._accept_current_color)
        actions.addWidget(btn_ok)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        actions.addWidget(btn_cancel)
        root.addLayout(actions)

        self._update_preview()
        self._update_hsl_slider_gradients()
        self._update_rgb_slider_gradients()
        self._update_all_kp_ui()

    def _channel_key(self, channel: str) -> str:
        # cfg_key 仅用于 K/P 绑定键的命名空间；“基准系数”取自当前滑块值
        return f"{self._cfg_key_prefix}__{str(channel).lower()}"

    def _cfg_get(self, key: str, default=None):
        try:
            if self._host is not None and hasattr(self._host, 'config'):
                return self._host.config.get(key, default)
        except Exception:
            pass
        return default

    def _cfg_set(self, key: str, value):
        try:
            if self._host is not None and hasattr(self._host, '_update_cfg'):
                self._host._update_cfg(key, value)
                return
            if self._host is not None and hasattr(self._host, 'config'):
                self._host.config[key] = value
                return
        except Exception:
            pass

    @staticmethod
    def _kp_enabled_key(cfg_key: str, sig: str) -> str:
        return f"kp_bind_{cfg_key}_{sig}"

    @staticmethod
    def _kp_wmin_key(cfg_key: str, sig: str) -> str:
        return f"kp_{cfg_key}_{sig}_wmin"

    @staticmethod
    def _kp_wmax_key(cfg_key: str, sig: str) -> str:
        return f"kp_{cfg_key}_{sig}_wmax"

    def _kp_is_enabled(self, cfg_key: str, sig: str) -> bool:
        return bool(self._cfg_get(self._kp_enabled_key(cfg_key, sig), False))

    def _show_kp_bind_menu(self, label: QLabel, cfg_key: str, supports=('k', 'p')):
        menu = QMenu(label)
        actions = {}
        for sig, text in [('k', '绑定 K'), ('p', '绑定 P')]:
            if sig not in supports:
                continue
            act = menu.addAction(text)
            act.setCheckable(True)
            act.setChecked(self._kp_is_enabled(cfg_key, sig))
            actions[sig] = act

        chosen = menu.exec(QCursor.pos())
        if chosen is None:
            return
        for sig, act in actions.items():
            if chosen is act:
                self._cfg_set(self._kp_enabled_key(cfg_key, sig), bool(act.isChecked()))
                self._update_kp_ui(cfg_key)
                return

    def _new_unbounded_float_input(self, *, default_value: float, decimals=3, width=72, cfg_key: str):
        box = _NoWheelDoubleSpinBox()
        box.setDecimals(int(decimals))
        box.setRange(-1_000_000_000.0, 1_000_000_000.0)
        box.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        box.setKeyboardTracking(False)
        box.setFocusPolicy(Qt.StrongFocus)
        box.setFixedWidth(int(width))
        box.setValue(float(self._cfg_get(cfg_key, default_value)))
        box.valueChanged.connect(lambda v, k=cfg_key: self._cfg_set(k, float(v)))
        return box

    def _build_kp_container(self, *, cfg_key: str, base_getter, supports=('k', 'p'), wmin_default=0.0, wmax_default=1.0, decimals=3):
        existing_label = None
        try:
            existing_label = (self._kp_ui.get(cfg_key) or {}).get('label', None)
        except Exception:
            existing_label = None
        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(18, 0, 0, 0)
        v.setSpacing(3)

        base_label = QLabel("")
        base_label.setStyleSheet("color:#888; font-size:8.5pt;")
        v.addWidget(base_label)

        rows = {}
        for sig in supports:
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(12, 0, 0, 0)
            h.setSpacing(6)
            tag = QLabel(sig.upper())
            tag.setStyleSheet(f"color:{self._kp_accent_color}; font-weight:bold;")
            h.addWidget(tag)
            h.addWidget(QLabel("权重范围"))
            wmin_spin = self._new_unbounded_float_input(
                default_value=float(wmin_default), decimals=int(decimals), width=72,
                cfg_key=self._kp_wmin_key(cfg_key, sig),
            )
            wmax_spin = self._new_unbounded_float_input(
                default_value=float(wmax_default), decimals=int(decimals), width=72,
                cfg_key=self._kp_wmax_key(cfg_key, sig),
            )
            h.addWidget(wmin_spin)
            h.addWidget(QLabel("~"))
            h.addWidget(wmax_spin)
            h.addStretch()
            v.addWidget(row)
            rows[sig] = row

        container.setVisible(False)
        self._kp_ui[cfg_key] = {
            'container': container,
            'base_label': base_label,
            'rows': rows,
            'supports': tuple(supports),
            'base_getter': base_getter,
            'label': existing_label,
        }
        return container

    def _install_kp_bindable_label(self, label: QLabel, cfg_key: str, supports=('k', 'p')):
        label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        label.customContextMenuRequested.connect(lambda _pos, w=label: self._show_kp_bind_menu(w, cfg_key, supports=supports))
        if cfg_key in self._kp_ui:
            self._kp_ui[cfg_key]['label'] = label
        else:
            self._kp_ui[cfg_key] = {
                'container': None,
                'base_label': None,
                'rows': {},
                'supports': tuple(supports),
                'base_getter': None,
                'label': label,
            }
        return label

    def _update_kp_ui(self, cfg_key: str):
        meta = self._kp_ui.get(cfg_key)
        if not meta:
            return
        supports = meta.get('supports', ('k', 'p'))
        enabled_any = any(self._kp_is_enabled(cfg_key, sig) for sig in supports)

        label = meta.get('label', None)
        if isinstance(label, QLabel):
            label.setStyleSheet(f"color:{self._kp_accent_color};" if enabled_any else "")

        container = meta.get('container', None)
        if container is not None:
            container.setVisible(bool(enabled_any))

        base_label = meta.get('base_label', None)
        base_getter = meta.get('base_getter', None)
        if isinstance(base_label, QLabel) and callable(base_getter):
            try:
                base_value = base_getter()
            except Exception:
                base_value = None
            base_label.setText(f"基准系数: {base_value}")

        for sig, row_widget in (meta.get('rows', {}) or {}).items():
            if row_widget is not None:
                row_widget.setVisible(self._kp_is_enabled(cfg_key, sig))

    def _update_all_kp_ui(self):
        for cfg_key in list(self._kp_ui.keys()):
            self._update_kp_ui(cfg_key)

    def _toggle_mode(self):
        self._mode = 'rgb' if self._mode == 'hsl' else 'hsl'
        self._title.setText('RGB' if self._mode == 'rgb' else 'HSL')
        self._hsl_group.setVisible(self._mode == 'hsl')
        self._rgb_group.setVisible(self._mode == 'rgb')
        self._update_preview()
        self._update_hsl_slider_gradients()
        self._update_rgb_slider_gradients()
        self._update_all_kp_ui()

    def _make_row(self, root_layout: QVBoxLayout, label_text, minimum, maximum, value, *, cfg_key: str):
        row_widget = QWidget()
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        lbl = QLabel(label_text)
        lbl.setFixedWidth(18)
        lbl.setAlignment(Qt.AlignCenter)
        row.addWidget(self._install_kp_bindable_label(lbl, cfg_key))
        slider = QSlider(Qt.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(value)
        slider.valueChanged.connect(self._on_any_changed)
        row.addWidget(slider)
        root_layout.addWidget(row_widget)
        container = self._build_kp_container(cfg_key=cfg_key, base_getter=lambda s=slider: s.value(), decimals=3)
        root_layout.addWidget(container)
        self._update_kp_ui(cfg_key)
        return slider

    def _on_any_changed(self, _value):
        self._update_preview()
        self._update_hsl_slider_gradients()
        self._update_rgb_slider_gradients()
        self._update_all_kp_ui()
        # 实时同步到外部（不需要点“应用”确认）
        self.colorSelected.emit(self.selected_rgb)

    def _set_slider_gradient(self, slider: QSlider, stops: list[tuple[float, tuple[int, int, int]]]):
        parts = []
        for pos, (r, g, b) in stops:
            parts.append(f"stop:{pos:.4f} rgb({int(r)},{int(g)},{int(b)})")
        grad = "qlineargradient(x1:0, y1:0, x2:1, y2:0, " + ", ".join(parts) + ")"
        slider.setStyleSheet(
            "QSlider::groove:horizontal{height:7px;border-radius:4px;" +
            "background:" + grad + ";}" +
            "QSlider::handle:horizontal{width:12px;margin:-4px 0;border-radius:6px;" +
            "background:rgba(255,255,255,210);border:1px solid rgba(0,0,0,120);}"
        )

    @staticmethod
    def _hsl_to_rgb(h_deg: float, s_pct: float, l_pct: float) -> tuple[int, int, int]:
        h = (float(h_deg) % 360.0) / 360.0
        s = max(0.0, min(1.0, float(s_pct) / 100.0))
        l = max(0.0, min(1.0, float(l_pct) / 100.0))
        rr, gg, bb = colorsys.hls_to_rgb(h, l, s)
        return (int(round(rr * 255.0)), int(round(gg * 255.0)), int(round(bb * 255.0)))

    @staticmethod
    def _rgb_to_hsl(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
        r, g, b = rgb
        h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
        return (int(round(h * 359.0)), int(round(s * 100.0)), int(round(l * 100.0)))

    def _update_hsl_slider_gradients(self):
        h = self._hue_slider.value()
        s = self._sat_slider.value()
        l = self._light_slider.value()

        # H：固定 S/L，覆盖色相环
        hue_steps = 13
        hue_stops = []
        for i in range(hue_steps):
            phase = i / (hue_steps - 1)
            rr, gg, bb = self._hsl_to_rgb(phase * 359.0, s, l)
            hue_stops.append((phase, (rr, gg, bb)))
        self._set_slider_gradient(self._hue_slider, hue_stops)

        # S：固定 H/L，0 为灰阶，1 为当前色相的全饱和版本。
        r0, g0, b0 = self._hsl_to_rgb(h, 0.0, l)
        rm, gm, bm = self._hsl_to_rgb(h, 50.0, l)
        r1, g1, b1 = self._hsl_to_rgb(h, 100.0, l)
        self._set_slider_gradient(self._sat_slider, [(0.0, (r0, g0, b0)), (0.5, (rm, gm, bm)), (1.0, (r1, g1, b1))])

        # L：HSL 亮度需要明确经过“当前色相”，否则 0/100 极值附近切换时会显得异常。
        r2, g2, b2 = self._hsl_to_rgb(h, s, 0.0)
        rmid, gmid, bmid = self._hsl_to_rgb(h, s, 50.0)
        r3, g3, b3 = self._hsl_to_rgb(h, s, 100.0)
        self._set_slider_gradient(self._light_slider, [(0.0, (r2, g2, b2)), (0.5, (rmid, gmid, bmid)), (1.0, (r3, g3, b3))])

    def _update_rgb_slider_gradients(self):
        r = int(self._r_slider.value())
        g = int(self._g_slider.value())
        b = int(self._b_slider.value())
        self._set_slider_gradient(self._r_slider, [(0.0, (0, g, b)), (1.0, (255, g, b))])
        self._set_slider_gradient(self._g_slider, [(0.0, (r, 0, b)), (1.0, (r, 255, b))])
        self._set_slider_gradient(self._b_slider, [(0.0, (r, g, 0)), (1.0, (r, g, 255))])

    def _move_to_cursor(self):
        self.adjustSize()
        global_pos = QCursor.pos() + QPoint(12, 12)
        screen = QApplication.screenAt(global_pos) or QApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            global_pos.setX(max(area.left(), min(global_pos.x(), area.right() - self.width() + 1)))
            global_pos.setY(max(area.top(), min(global_pos.y(), area.bottom() - self.height() + 1)))
        self.move(global_pos)

    def exec(self):
        self._move_to_cursor()
        return super().exec()

    def _current_rgb(self):
        if self._mode == 'rgb':
            return (int(self._r_slider.value()), int(self._g_slider.value()), int(self._b_slider.value()))
        return self._hsl_to_rgb(self._hue_slider.value(), self._sat_slider.value(), self._light_slider.value())

    def _rgb_to_hsl_preserving_context(self, rgb: tuple[int, int, int]) -> tuple[int, int, int]:
        h, s, l = self._rgb_to_hsl(rgb)
        fallback_h = self._hue_slider.value() if hasattr(self, '_hue_slider') else h
        fallback_s = self._sat_slider.value() if hasattr(self, '_sat_slider') else s

        # 黑/白/灰没有稳定色相；保留当前 H/S，避免一旦触到极值就回跳到 0° 红色。
        if s <= 0 or l <= 0 or l >= 100:
            h = fallback_h
        if l <= 0 or l >= 100:
            s = fallback_s
        return (int(h), int(s), int(l))

    def _update_preview(self):
        self.selected_rgb = self._current_rgb()
        r, g, b = self.selected_rgb
        self.preview.setStyleSheet(f"background:rgb({r},{g},{b}); border:1px solid #7f828a; border-radius:4px;")

        # 两种模式之间保持同步，避免切换时跳变
        if self._mode == 'hsl':
            self._r_slider.blockSignals(True)
            self._g_slider.blockSignals(True)
            self._b_slider.blockSignals(True)
            self._r_slider.setValue(int(r))
            self._g_slider.setValue(int(g))
            self._b_slider.setValue(int(b))
            self._r_slider.blockSignals(False)
            self._g_slider.blockSignals(False)
            self._b_slider.blockSignals(False)
        else:
            h, s, l = self._rgb_to_hsl_preserving_context(self.selected_rgb)
            self._hue_slider.blockSignals(True)
            self._sat_slider.blockSignals(True)
            self._light_slider.blockSignals(True)
            self._hue_slider.setValue(int(h))
            self._sat_slider.setValue(int(s))
            self._light_slider.setValue(int(l))
            self._hue_slider.blockSignals(False)
            self._sat_slider.blockSignals(False)
            self._light_slider.blockSignals(False)



    def _accept_current_color(self):
        self._update_preview()
        self.colorSelected.emit(self.selected_rgb)
        self.accept()


class _SignalPreviewWidget(QWidget):
    """K / P 信号预览，使用历史折线与当前水平线显示。"""

    def __init__(self, title, *, signed=False, parent=None):
        super().__init__(parent)
        self._title = title
        self._signed = signed
        self._display_value = 0.0
        self._target_value = 0.0
        self._history = []
        self._history_limit = 72
        self.setMinimumHeight(172)
        self.setMaximumHeight(196)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._advance_animation)
        self._anim_timer.start(16)

    def set_runtime_state(self, value):
        self._target_value = float(value)
        self._history.append(self._target_value)
        if len(self._history) > self._history_limit:
            self._history = self._history[-self._history_limit:]
        self.update()

    def _advance_animation(self):
        delta = self._target_value - self._display_value
        if abs(delta) < 0.02:
            if self._display_value != self._target_value:
                self._display_value = self._target_value
                self.update()
            return
        self._display_value += delta * 0.28
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        highlight = _active_palette_color(QPalette.ColorRole.Highlight)
        history_color = QColor(highlight)
        history_color.setAlpha(175)
        current_color = _inverse_color(highlight)
        current_color.setAlpha(230)

        outer = QRectF(self.rect()).adjusted(3.0, 3.0, -3.0, -3.0)
        painter.setPen(Qt.NoPen)
        painter.setBrush(Qt.NoBrush)

        painter.setPen(QColor("#e6eaf0"))
        painter.drawText(
            QRectF(outer.left(), outer.top(), outer.width(), 16.0),
            Qt.AlignLeft | Qt.AlignVCenter,
            self._title,
        )

        chart = QRectF(outer.left(), outer.top() + 24.0, outer.width(), outer.height() - 44.0)
        grid_pen = QPen(QColor(255, 255, 255, 22), 1)
        grid_pen.setStyle(Qt.DashLine)
        painter.setPen(grid_pen)
        for idx in range(5):
            y = int(round(chart.top() + chart.height() * idx / 4.0))
            painter.drawLine(int(chart.left()), y, int(chart.right()), y)

        history = self._history or [self._display_value]
        if self._signed:
            max_abs = max(1.0, max(abs(value) for value in history + [self._display_value]))
            visible_lo = -max_abs * 1.15
            visible_hi = max_abs * 1.15
        else:
            visible_lo = 0.0
            visible_hi = max(1.0, max(history + [self._display_value])) * 1.15
        display_span = max(1.0, visible_hi - visible_lo)

        if self._signed:
            zero_ratio = (0.0 - visible_lo) / display_span
            zero_y = chart.bottom() - zero_ratio * chart.height()
            painter.setPen(QPen(QColor(255, 255, 255, 48), 1))
            painter.drawLine(int(chart.left()), int(round(zero_y)), int(chart.right()), int(round(zero_y)))

        points = []
        for idx, value in enumerate(history):
            ratio = max(0.0, min(1.0, (value - visible_lo) / display_span))
            x = chart.left() + chart.width() * idx / max(1, len(history) - 1)
            y = chart.bottom() - ratio * chart.height()
            points.append(QPoint(int(round(x)), int(round(y))))
        if len(points) >= 2:
            painter.setPen(QPen(history_color, 2))
            painter.drawPolyline(points)

        current_ratio = max(0.0, min(1.0, (self._display_value - visible_lo) / display_span))
        current_y = chart.bottom() - current_ratio * chart.height()
        painter.setPen(QPen(current_color, 2))
        painter.drawLine(int(chart.left()), int(round(current_y)), int(chart.right()), int(round(current_y)))

        painter.setPen(QColor("#96a0ae"))
        painter.drawText(
            QRectF(chart.right() - 80.0, chart.top() - 6.0, 80.0, 14.0),
            Qt.AlignRight | Qt.AlignVCenter,
            f"{visible_hi:.2f}",
        )
        painter.drawText(
            QRectF(chart.right() - 80.0, chart.bottom() - 8.0, 80.0, 14.0),
            Qt.AlignRight | Qt.AlignVCenter,
            f"{visible_lo:.2f}",
        )

        painter.setPen(QColor("#d7dbe3"))
        painter.drawText(
            QRectF(outer.left(), outer.bottom() - 14.0, outer.width(), 14.0),
            Qt.AlignLeft | Qt.AlignVCenter,
            f"当前值 {self._display_value:.4f}",
        )


class _SpectrumBarsPreviewWidget(QWidget):
    """当前频率范围内的完整单段条形频谱预览。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._values = []
        self._bar_count = 64
        self._segments = 1
        self._freq_min = 20
        self._freq_max = 20000
        self._time_window = 10.0
        self._uses_independent_time_window = False
        self._uses_independent_damping = False
        self._rise_damping = 0.1
        self._fall_damping = 0.999
        self._peak_visible_hi = 1.0
        self.setMinimumHeight(172)
        self.setMaximumHeight(196)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_config_snapshot(self, *, bar_count, segments, freq_min, freq_max, time_window=10.0,
                            uses_independent_time_window=False, uses_independent_damping=False,
                            rise_damping=0.1, fall_damping=0.999):
        self._bar_count = max(1, int(bar_count))
        self._segments = max(1, int(segments))
        self._freq_min = int(min(freq_min, freq_max))
        self._freq_max = int(max(freq_min, freq_max))
        self._time_window = _clamp_time_window(time_window, 10.0)
        self._uses_independent_time_window = bool(uses_independent_time_window)
        self._uses_independent_damping = bool(uses_independent_damping)
        self._rise_damping = float(rise_damping)
        self._fall_damping = float(fall_damping)
        self.update()

    def set_runtime_state(self, values, colors=None):
        self._values = [max(0.0, float(value)) for value in (values or [])]
        if self._values:
            new_hi = max(self._values) * 1.12
            if new_hi > self._peak_visible_hi:
                self._peak_visible_hi = new_hi
        self._peak_visible_hi = max(1.0, self._peak_visible_hi * 0.999)
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        highlight = _active_palette_color(QPalette.ColorRole.Highlight)
        top_color = QColor(highlight.lighter(135))
        top_color.setAlpha(235)
        bottom_color = QColor(highlight)
        bottom_color.setAlpha(200)

        outer = QRectF(self.rect()).adjusted(3.0, 3.0, -3.0, -3.0)
        painter.setPen(QColor("#e6eaf0"))
        painter.drawText(
            QRectF(outer.left(), outer.top(), outer.width(), 16.0),
            Qt.AlignLeft | Qt.AlignVCenter,
            "完整条形频谱",
        )

        chart = QRectF(outer.left(), outer.top() + 24.0, outer.width(), outer.height() - 56.0)
        grid_pen = QPen(QColor(255, 255, 255, 22), 1)
        grid_pen.setStyle(Qt.DashLine)
        painter.setPen(grid_pen)
        for idx in range(5):
            y = int(round(chart.top() + chart.height() * idx / 4.0))
            painter.drawLine(int(chart.left()), y, int(chart.right()), y)

        painter.setPen(QPen(QColor(255, 255, 255, 48), 1))
        painter.drawLine(int(chart.left()), int(chart.bottom()), int(chart.right()), int(chart.bottom()))

        values = self._values or [0.0] * max(1, self._bar_count)
        visible_hi = max(1.0, self._peak_visible_hi)
        bar_width = max(1.0, chart.width() / max(1, len(values)))
        for idx, value in enumerate(values):
            ratio = max(0.0, min(1.0, value / visible_hi))
            height = max(1.0, ratio * chart.height())
            x = chart.left() + idx * bar_width
            rect = QRectF(x, chart.bottom() - height, max(1.0, bar_width - 1.0), height)
            gradient = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
            gradient.setColorAt(0.0, top_color)
            gradient.setColorAt(1.0, bottom_color)
            painter.fillRect(rect, gradient)

        painter.setPen(QColor("#96a0ae"))
        painter.drawText(
            QRectF(chart.right() - 70.0, chart.top() - 6.0, 70.0, 14.0),
            Qt.AlignRight | Qt.AlignVCenter,
            f"{visible_hi:.1f}",
        )

        footer = (
            f"{len(values)} 条  {self._freq_min}-{self._freq_max} Hz\n"
            f"{'独立T' if self._uses_independent_time_window else '继承T'} {self._time_window:.2f} 秒   "
            f"{'独立阻尼' if self._uses_independent_damping else '继承阻尼'}"
        )
        footer_font = QFont(painter.font())
        if footer_font.pointSizeF() > 0:
            footer_font.setPointSizeF(max(7.6, footer_font.pointSizeF() - 1.0))
        else:
            footer_font.setPointSize(8)
        painter.setFont(footer_font)
        painter.setPen(QColor("#d7dbe3"))
        painter.drawText(
            QRectF(outer.left(), outer.bottom() - 24.0, outer.width(), 22.0),
            Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap,
            footer,
        )


class _DynamicColorPreviewWidget(QWidget):
    """动态配色预览，显示运行中的颜色条、相位与变化速率。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._strip_colors = []
        self._phase = 0.0
        self._rate = 0.0
        self._dynamic_enabled = False
        self._current_color = (255, 255, 255)
        self.setMinimumHeight(104)
        self.setMaximumHeight(118)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_runtime_state(self, colors, *, phase=0.0, rate=0.0, dynamic_enabled=False, current_color=None):
        self._strip_colors = [tuple(color) for color in (colors or [])]
        self._phase = float(phase)
        self._rate = float(rate)
        self._dynamic_enabled = bool(dynamic_enabled)
        if current_color is not None:
            self._current_color = tuple(int(channel) for channel in current_color[:3])
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        outer = QRectF(self.rect()).adjusted(3.0, 3.0, -3.0, -3.0)
        painter.setPen(QColor("#e6eaf0"))
        painter.drawText(
            QRectF(outer.left(), outer.top(), outer.width(), 16.0),
            Qt.AlignLeft | Qt.AlignVCenter,
            "动态配色预览",
        )

        chart = QRectF(outer.left(), outer.top() + 24.0, outer.width(), outer.height() - 46.0)

        row_rect = QRectF(chart.left(), chart.top() + max(4.0, (chart.height() - 34.0) * 0.5), chart.width(), 34.0)
        swatch_size = 30.0
        swatch_rect = QRectF(row_rect.left(), row_rect.top() + 2.0, swatch_size, swatch_size)
        strip_rect = QRectF(swatch_rect.right() + 12.0, row_rect.center().y() - 7.0, max(24.0, row_rect.right() - swatch_rect.right() - 12.0), 14.0)

        # 色环渐变（0→红→绿→蓝→红），hue 0~1 均匀覆盖
        strip_gradient = QLinearGradient(strip_rect.left(), strip_rect.center().y(), strip_rect.right(), strip_rect.center().y())
        _hue_steps = 13
        for _i in range(_hue_steps):
            _hue = _i / (_hue_steps - 1)
            _r, _g, _b = colorsys.hsv_to_rgb(_hue, 1.0, 1.0)
            strip_gradient.setColorAt(_hue, QColor(int(_r * 255), int(_g * 255), int(_b * 255)))

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 20))
        painter.drawRoundedRect(strip_rect.adjusted(-1.0, -1.0, 1.0, 1.0), 8.0, 8.0)
        painter.setBrush(strip_gradient)
        painter.drawRoundedRect(strip_rect, 7.0, 7.0)

        current_rgb = tuple(int(channel) for channel in self._current_color[:3])
        current_color = QColor(int(current_rgb[0]), int(current_rgb[1]), int(current_rgb[2]))
        painter.setPen(QPen(QColor(255, 255, 255, 165), 1))
        painter.setBrush(current_color)
        painter.drawRoundedRect(swatch_rect, 6.0, 6.0)

        marker_x = strip_rect.left() + (self._phase % 1.0) * strip_rect.width()
        marker_pen = QPen(QColor(255, 255, 255, 230))
        marker_pen.setWidthF(1.6)
        painter.setPen(marker_pen)
        painter.drawLine(int(round(marker_x)), int(strip_rect.top()) - 4, int(round(marker_x)), int(strip_rect.bottom()) + 4)
        painter.setBrush(current_color)
        painter.drawEllipse(QRectF(marker_x - 5.0, strip_rect.center().y() - 5.0, 10.0, 10.0))

        footer_font = QFont(painter.font())
        if footer_font.pointSizeF() > 0:
            footer_font.setPointSizeF(max(7.6, footer_font.pointSizeF() - 1.0))
        else:
            footer_font.setPointSize(8)
        painter.setFont(footer_font)
        painter.setPen(QColor("#d7dbe3"))
        painter.drawText(
            QRectF(outer.left(), outer.bottom() - 20.0, outer.width(), 18.0),
            Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap,
            f"{'动态' if self._dynamic_enabled else '静态'}   {current_color.name().upper()}   速率 {self._rate:.5f}/帧",
        )


class VisualizerControlUI(QWidget):
    """音频可视化主控制台"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("音频可视化控制台")
        self.resize(880, 680)

        self.config = self._load_config()
        self.config_queue = None
        self.status_queue = None
        self.viz_process = None
        self.current_raw_a1 = 0.0
        self.current_a1 = 0.0
        self.current_p = 0.0
        self.preview_spectrum_values = []
        self.preview_dynamic_colors = []
        self.current_color_cycle_hue = 0.0
        self.current_color_cycle_rate = 0.0
        self._applying_config = False
        self._syncing_preset_combo = False
        self._last_random_apply_ts = None
        self._palette_cache = []
        self._palette_refill_running = False
        self._section_preset_combos = {}
        self._theme_nav_checks = {}
        self._color_button_registry = {}
        self._gradient_point_buttons = []
        self._latest_runtime_color_state = {}
        self._latest_gradient_point_colors = []
        self._latest_palette_preview = []
        self._latest_palette_preview_meta = []
        self._preview_sidebar_last_state = False
        self._unity_export_auto_class_name = ""
        self._unity_export_auto_path = ""

        self._kp_binding_meta = {}
        self._kp_accent_color = _active_palette_color(QPalette.ColorRole.Highlight).name()

        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status)

        self.cfg_send_timer = QTimer()
        self.cfg_send_timer.setSingleShot(True)
        self.cfg_send_timer.timeout.connect(self._send_config)

        self.cfg_save_timer = QTimer()
        self.cfg_save_timer.setSingleShot(True)
        self.cfg_save_timer.timeout.connect(self._save_config)

        self.preset_timer = QTimer()
        self.preset_timer.timeout.connect(self._auto_switch_preset)

        self._init_ui()
        self._refresh_preset_list()
        self._start_palette_refill_async()

        # 自动启动
        QTimer.singleShot(100, self._start_visualizer)

    # ═══════════════════════════════════════════════════════
    #  配置管理
    # ═══════════════════════════════════════════════════════

    def _load_config(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    raw = json.load(f)
                migrated = self._migrate_legacy_contour_fill_visibility(raw)
                normalized = _normalize_loaded_config(migrated)
                if migrated != raw:
                    self._save_config_data(normalized)
                return normalized
            except Exception as e:
                print(f"警告: 加载配置失败: {e}")
                return _get_defaults()
        cfg = _get_defaults()
        self._save_config_data(cfg)
        return cfg

    @staticmethod
    def _save_config_data(data):
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"警告: 保存配置失败: {e}")

    def _save_config(self):
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"警告: 保存配置失败: {e}")

    @staticmethod
    def _set_checkbox_silent(widget, checked):
        if widget is None or widget.isChecked() == bool(checked):
            return
        widget.blockSignals(True)
        widget.setChecked(bool(checked))
        widget.blockSignals(False)

    @staticmethod
    def _set_spin_silent(widget, value):
        if widget is None:
            return
        try:
            if abs(float(widget.value()) - float(value)) < 1e-9:
                return
        except Exception:
            pass
        widget.blockSignals(True)
        widget.setValue(value)
        widget.blockSignals(False)

    @staticmethod
    def _clamp_damping(value, fallback):
        try:
            return max(0.0, min(0.999, float(value)))
        except Exception:
            return max(0.0, min(0.999, float(fallback)))

    def _get_damping_pair(self, prefix=None):
        global_rise = self._clamp_damping(self.config.get('k_rise_damping', 0.1), 0.1)
        global_fall = self._clamp_damping(self.config.get('k_fall_damping', 0.999), 0.999)
        if not prefix or not self.config.get(f'{prefix}_use_independent_damping', False):
            return global_rise, global_fall
        rise = self._clamp_damping(self.config.get(f'{prefix}_independent_rise_damping', global_rise), global_rise)
        fall = self._clamp_damping(self.config.get(f'{prefix}_independent_fall_damping', global_fall), global_fall)
        return rise, fall

    def _sync_color_quick_widgets(self, dynamic_enabled=None):
        dynamic_enabled = bool(self.config.get('color_dynamic', False) if dynamic_enabled is None else dynamic_enabled)
        if hasattr(self, 'dyn_widget'):
            self.dyn_widget.setVisible(dynamic_enabled)
        if hasattr(self, 'color_quick_controls_widget'):
            self.color_quick_controls_widget.setEnabled(dynamic_enabled)
        if hasattr(self, 'color_cycle_a1_quick_check'):
            self.color_cycle_a1_quick_check.setEnabled(dynamic_enabled)
        self._set_checkbox_silent(getattr(self, 'dyn_check', None), dynamic_enabled)
        self._set_checkbox_silent(getattr(self, 'color_dynamic_quick_check', None), dynamic_enabled)
        self._set_checkbox_silent(getattr(self, 'cyc_a1_check', None), bool(self.config.get('color_cycle_a1', True)))
        self._set_checkbox_silent(getattr(self, 'color_cycle_a1_quick_check', None), bool(self.config.get('color_cycle_a1', True)))
        self._set_spin_silent(getattr(self, 'cyc_spd_slider', None), int(float(self.config.get('color_cycle_speed', 1.0)) * 100))
        self._set_spin_silent(getattr(self, 'cyc_spd_spin', None), float(self.config.get('color_cycle_speed', 1.0)))
        self._set_spin_silent(getattr(self, 'color_cycle_speed_quick_spin', None), float(self.config.get('color_cycle_speed', 1.0)))
        self._set_spin_silent(getattr(self, 'cyc_pow_slider', None), int(float(self.config.get('color_cycle_pow', 2.0)) * 100))
        self._set_spin_silent(getattr(self, 'cyc_pow_spin', None), float(self.config.get('color_cycle_pow', 2.0)))
        self._set_spin_silent(getattr(self, 'color_cycle_pow_quick_spin', None), float(self.config.get('color_cycle_pow', 2.0)))

    def _sync_theme_enable_widgets(self):
        classic_enabled = bool(self.config.get('contours_enabled', True) or self.config.get('bars_enabled', True))
        self._set_checkbox_silent(self._theme_nav_checks.get('theme_classic_kaleidoscope'), classic_enabled)
        self._set_checkbox_silent(self._theme_nav_checks.get('theme_kaleidoscope_fill'), bool(self.config.get('contours_enabled', True)))
        self._set_checkbox_silent(self._theme_nav_checks.get('theme_kaleidoscope_lines'), bool(self.config.get('bars_enabled', True)))
        self._set_checkbox_silent(self._theme_nav_checks.get('theme_softbody'), bool(self.config.get('tentacles_enabled', True)))

    def _set_classic_theme_enabled(self, enabled):
        enabled = bool(enabled)
        self._update_cfg('contours_enabled', enabled)
        self._update_cfg('bars_enabled', enabled)

    def _set_theme_section_enabled(self, section, enabled):
        if section == 'theme_classic_kaleidoscope':
            self._set_classic_theme_enabled(enabled)
            return
        if section == 'theme_kaleidoscope_fill':
            self._update_cfg('contours_enabled', bool(enabled))
            return
        if section == 'theme_kaleidoscope_lines':
            self._update_cfg('bars_enabled', bool(enabled))
            return
        if section == 'theme_softbody':
            self._update_cfg('tentacles_enabled', bool(enabled))
            self._update_cfg('tentacle_on', bool(enabled))

    def _create_theme_nav_check(self, section):
        checkbox = QCheckBox()
        checkbox.setToolTip('启用该主题')
        checkbox.setFixedSize(18, 18)
        checkbox.setStyleSheet('QCheckBox::indicator { width: 11px; height: 11px; }')
        checkbox.toggled.connect(lambda checked, s=section: self._set_theme_section_enabled(s, checked))
        self._theme_nav_checks[section] = checkbox

        holder = QWidget()
        holder.setStyleSheet('background: transparent;')
        layout = QHBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addStretch()
        layout.addWidget(checkbox)
        layout.addStretch()
        return holder

    def _section_display_name(self, section: str):
        return _SECTION_DISPLAY_NAMES.get(section, section)

    def _build_theme_mix_payload(self, config_data):
        payload = {}
        for section in _THEME_PRESET_SECTIONS:
            keys = self._section_keys(section)
            payload[section] = {key: config_data.get(key) for key in keys if key in config_data}
        return payload

    def _build_full_preset_payload(self):
        save_data = {key: value for key, value in self.config.items() if key not in ('pos_x', 'pos_y')}
        save_data['_preset_meta'] = {
            'format': 'theme-mix-v2',
            'theme_sections': list(_THEME_PRESET_SECTIONS),
            'contour_fill_visibility_mode': 'independent',
        }
        save_data['_theme_mix'] = self._build_theme_mix_payload(save_data)
        return save_data

    @staticmethod
    def _migrate_legacy_contour_fill_visibility(data):
        if not isinstance(data, dict):
            return data
        migrated = dict(data)
        changed = False
        for layer_index in range(1, 6):
            contour_key = f'c{layer_index}_on'
            fill_key = f'c{layer_index}_fill'
            fill_alpha_key = f'c{layer_index}_fill_alpha'
            if not bool(migrated.get(contour_key, False)) and bool(migrated.get(fill_key, False)):
                migrated[fill_key] = False
                if fill_alpha_key in migrated:
                    migrated[fill_alpha_key] = 0
                changed = True
        return migrated if changed else data

    def _inflate_loaded_preset_data(self, raw_data):
        if not isinstance(raw_data, dict):
            return {}
        preset_meta = raw_data.get('_preset_meta', {})
        use_independent_visibility = isinstance(preset_meta, dict) and preset_meta.get('contour_fill_visibility_mode') == 'independent'
        config_data = {key: value for key, value in raw_data.items() if not str(key).startswith('_')}
        if not use_independent_visibility:
            config_data = self._migrate_legacy_contour_fill_visibility(config_data)
        theme_mix = raw_data.get('_theme_mix', {})
        if isinstance(theme_mix, dict):
            for section, section_data in theme_mix.items():
                if not isinstance(section_data, dict):
                    continue
                if not use_independent_visibility:
                    section_data = self._migrate_legacy_contour_fill_visibility(section_data)
                if section in _THEME_PRESET_SECTIONS:
                    normalized_section_data = self._normalize_section_preset_payload(section, section_data)
                    if isinstance(normalized_section_data, dict):
                        config_data.update(normalized_section_data)
                        continue
                config_data.update(section_data)
        return config_data

    def _update_cfg(self, key, value):
        self.config[key] = value
        if hasattr(self, '_kp_binding_meta') and (key in self._kp_binding_meta or str(key).startswith('kp_bind_') or str(key).startswith('kp_')):
            self._maybe_update_kp_binding_ui(str(key))
        if key == 'color_dynamic':
            self._sync_color_quick_widgets(bool(value))
        elif key in {'color_cycle_speed', 'color_cycle_pow', 'color_cycle_a1'}:
            self._sync_color_quick_widgets()
        elif key in {'contours_enabled', 'bars_enabled', 'tentacles_enabled'}:
            self._sync_theme_enable_widgets()
        if key in {'color_scheme', 'gradient_enabled', 'gradient_points', 'tentacle_color', 'tentacle_shader_tip_color'} or re.match(r'^c[1-5]_color$', str(key)):
            self._update_color_preview_strip()
        if key in {
            'num_bars', 'circle_segments', 'bar_length_min', 'bar_length_max', 'freq_min', 'freq_max',
            'color_scheme', 'gradient_enabled', 'gradient_points', 'gradient_mode', 'bar_height_min', 'bar_height_max',
            'a1_time_window', 'bar_use_independent_time_window', 'bar_time_window',
            'k_rise_damping', 'k_fall_damping', 'bar_use_independent_damping',
            'bar_independent_rise_damping', 'bar_independent_fall_damping',
            'color_dynamic', 'color_cycle_speed', 'color_cycle_pow', 'color_cycle_a1',
            'tentacle_on', 'tentacle_alpha', 'tentacle_thick', 'tentacle_count', 'tentacle_length',
            'tentacle_length_jitter', 'tentacle_length_jitter_speed', 'tentacle_length_jitter_random',
            'tentacle_control_points_min', 'tentacle_control_points_max',
            'tentacle_tip_bias', 'tentacle_tip_thickness', 'tentacle_turbulence', 'tentacle_k_influence',
            'tentacle_sway_speed', 'tentacle_sway_density', 'tentacle_water_damping',
            'tentacle_angle_stiffness', 'tentacle_length_stiffness', 'tentacle_stretch_limit', 'tentacle_shader_enabled',
            'tentacle_shader_alpha_start', 'tentacle_shader_alpha_end', 'tentacle_shader_bias',
            'tentacle_core_on', 'tentacle_core_base_speed',
            'tentacle_core_k_speed', 'tentacle_core_p_speed',
        } or re.match(r'^c[1-5]_color$', str(key)) or re.match(r'^(c[1245]|b(?:12|23|34|45))_(use_independent_damping|independent_rise_damping|independent_fall_damping)$', str(key)):
            self._refresh_single_bar_preview()
        if str(key).startswith('kp_bind_tentacle_') or str(key).startswith('kp_tentacle_'):
            self._refresh_single_bar_preview()
        if self._applying_config:
            return
        self._schedule_config_commit()

    def _kp_enabled_key(self, cfg_key: str, sig: str) -> str:
        return f'kp_bind_{cfg_key}_{sig}'

    def _kp_wmin_key(self, cfg_key: str, sig: str) -> str:
        return f'kp_{cfg_key}_{sig}_wmin'

    def _kp_wmax_key(self, cfg_key: str, sig: str) -> str:
        return f'kp_{cfg_key}_{sig}_wmax'

    def _kp_is_enabled(self, cfg_key: str, sig: str) -> bool:
        return bool(self.config.get(self._kp_enabled_key(cfg_key, sig), False))

    def _show_kp_bind_menu(self, label: QLabel, cfg_key: str, supports=('k', 'p')):
        menu = QMenu(label)
        actions = {}
        for sig, text in [('k', '绑定 K'), ('p', '绑定 P')]:
            if sig not in supports:
                continue
            act = menu.addAction(text)
            act.setCheckable(True)
            act.setChecked(self._kp_is_enabled(cfg_key, sig))
            actions[sig] = act

        chosen = menu.exec(QCursor.pos())
        if chosen is None:
            return
        for sig, act in actions.items():
            if chosen is act:
                self._update_cfg(self._kp_enabled_key(cfg_key, sig), bool(act.isChecked()))
                self._update_kp_binding_ui(cfg_key)
                return

    def _attach_kp_bindable_label(self, label: QLabel, cfg_key: str, supports=('k', 'p')):
        label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        label.customContextMenuRequested.connect(lambda _pos, w=label: self._show_kp_bind_menu(w, cfg_key, supports=supports))
        return label

    def _build_kp_binding_container(
        self,
        *,
        cfg_key: str,
        supports=('k', 'p'),
        wmin_default=0.0,
        wmax_default=1.0,
        defaults_by_sig: dict | None = None,
        soft_min=-5.0,
        soft_max=5.0,
        hard_min=-100.0,
        hard_max=100.0,
        decimals=3,
    ):
        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(18, 0, 0, 0)
        v.setSpacing(3)

        base_label = QLabel("")
        base_label.setStyleSheet("color:#888; font-size:8.5pt;")
        v.addWidget(base_label)

        rows = {}
        weight_spins = {}
        for sig in supports:
            sig_defaults = (defaults_by_sig or {}).get(sig, None)
            sig_wmin_default = sig_defaults[0] if sig_defaults is not None else wmin_default
            sig_wmax_default = sig_defaults[1] if sig_defaults is not None else wmax_default
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(12, 0, 0, 0)
            h.setSpacing(6)
            tag = QLabel(sig.upper())
            tag.setStyleSheet(f"color:{self._kp_accent_color}; font-weight:bold;")
            h.addWidget(tag)
            h.addWidget(QLabel("权重范围"))
            # K/P 权重范围：用户要求“无上下按钮、无滑动/软范围、取消上下限限制”
            wmin_spin = self._new_unbounded_float_input(
                default_value=float(sig_wmin_default), decimals=int(decimals), width=72,
                cfg_key=self._kp_wmin_key(cfg_key, sig),
            )
            wmax_spin = self._new_unbounded_float_input(
                default_value=float(sig_wmax_default), decimals=int(decimals), width=72,
                cfg_key=self._kp_wmax_key(cfg_key, sig),
            )
            h.addWidget(wmin_spin)
            h.addWidget(QLabel("~"))
            h.addWidget(wmax_spin)
            h.addStretch()
            v.addWidget(row)
            rows[sig] = row
            weight_spins[sig] = (wmin_spin, wmax_spin)

        return container, base_label, rows, weight_spins

    def _register_kp_binding_ui(self, *, cfg_key: str, label: QLabel, container: QWidget, base_label: QLabel, rows: dict, supports=('k', 'p'), weight_spins: dict | None = None):
        self._kp_binding_meta[cfg_key] = {
            'label': label,
            'container': container,
            'base_label': base_label,
            'rows': rows,
            'supports': tuple(supports),
            'weight_spins': dict(weight_spins or {}),
        }
        self._update_kp_binding_ui(cfg_key)

    def _add_kp_slider_row(
        self,
        grid,
        row,
        *,
        label_text,
        cfg_key,
        default_value,
        soft_min,
        soft_max,
        hard_min,
        hard_max,
        supports=('k', 'p'),
        slider_scale=100,
        step=0.01,
        decimals=2,
        width=72,
        integer=False,
        kp_soft_min=-1.0,
        kp_soft_max=1.0,
        kp_hard_min=-100.0,
        kp_hard_max=100.0,
        kp_decimals=3,
    ):
        label = self._attach_kp_bindable_label(QLabel(label_text), cfg_key, supports=supports)
        if integer:
            slider, box = self._new_bound_int_slider(
                cfg_key=cfg_key, default_value=default_value,
                soft_min=soft_min, soft_max=soft_max,
                hard_min=hard_min, hard_max=hard_max,
                step=int(step), width=width,
            )
        else:
            slider, box = self._new_bound_float_slider(
                cfg_key=cfg_key, default_value=default_value,
                soft_min=soft_min, soft_max=soft_max,
                hard_min=hard_min, hard_max=hard_max,
                slider_scale=slider_scale, step=step, decimals=decimals, width=width,
            )
        control_row = self._make_graphics_form_row(
            label_widget=label,
            widgets=[slider, box],
            label_width=92,
            stretch=False,
        )
        grid.addWidget(control_row, row, 0, 1, 4)
        row += 1
        bind_widget, base_label, bind_rows, weight_spins = self._build_kp_binding_container(
            cfg_key=cfg_key, supports=supports,
            wmin_default=0.0, wmax_default=0.0,
            soft_min=kp_soft_min, soft_max=kp_soft_max,
            hard_min=kp_hard_min, hard_max=kp_hard_max,
            decimals=kp_decimals,
        )
        grid.addWidget(bind_widget, row, 0, 1, 4)
        row += 1
        self._register_kp_binding_ui(
            cfg_key=cfg_key, label=label,
            container=bind_widget, base_label=base_label,
            rows=bind_rows, supports=supports, weight_spins=weight_spins,
        )
        return row, label, slider, box

    def _add_kp_spin_row(
        self,
        grid,
        row,
        *,
        label_text,
        cfg_key,
        default_value,
        soft_min,
        soft_max,
        hard_min,
        hard_max,
        supports=('k', 'p'),
        step=1,
        decimals=2,
        width=72,
        integer=True,
        suffix='',
        kp_soft_min=-1.0,
        kp_soft_max=1.0,
        kp_hard_min=-100.0,
        kp_hard_max=100.0,
        kp_decimals=3,
    ):
        label = self._attach_kp_bindable_label(QLabel(label_text), cfg_key, supports=supports)
        if integer:
            box = self._new_int_box(
                default_value=default_value, soft_min=soft_min, soft_max=soft_max,
                hard_min=hard_min, hard_max=hard_max, step=int(step), width=width, suffix=suffix, cfg_key=cfg_key,
            )
        else:
            box = self._new_float_box(
                default_value=default_value, soft_min=soft_min, soft_max=soft_max,
                hard_min=hard_min, hard_max=hard_max, step=step, decimals=decimals, width=width, suffix=suffix, cfg_key=cfg_key,
            )
        control_row = self._make_graphics_form_row(
            label_widget=label,
            widgets=[box],
            label_width=92,
            stretch=False,
        )
        grid.addWidget(control_row, row, 0, 1, 4)
        row += 1
        bind_widget, base_label, bind_rows, weight_spins = self._build_kp_binding_container(
            cfg_key=cfg_key, supports=supports,
            wmin_default=0.0, wmax_default=0.0,
            soft_min=kp_soft_min, soft_max=kp_soft_max,
            hard_min=kp_hard_min, hard_max=kp_hard_max,
            decimals=kp_decimals,
        )
        grid.addWidget(bind_widget, row, 0, 1, 4)
        row += 1
        self._register_kp_binding_ui(
            cfg_key=cfg_key, label=label,
            container=bind_widget, base_label=base_label,
            rows=bind_rows, supports=supports, weight_spins=weight_spins,
        )
        return row, label, box

    def _maybe_update_kp_binding_ui(self, changed_key: str):
        if changed_key in self._kp_binding_meta:
            self._update_kp_binding_ui(changed_key)
            return
        for cfg_key in self._kp_binding_meta.keys():
            if changed_key.startswith(f'kp_bind_{cfg_key}_') or changed_key.startswith(f'kp_{cfg_key}_'):
                self._update_kp_binding_ui(cfg_key)
                return

    def _update_kp_binding_ui(self, cfg_key: str):
        meta = self._kp_binding_meta.get(cfg_key)
        if not meta:
            return
        supports = meta.get('supports', ())
        enabled_any = any(self._kp_is_enabled(cfg_key, sig) for sig in supports)
        meta['container'].setVisible(bool(enabled_any))

        base_value = self.config.get(cfg_key, None)
        meta['base_label'].setText(f"基准系数: {base_value}")

        # 参数名：当绑定启用时用主题色
        meta['label'].setStyleSheet(f"color:{self._kp_accent_color};" if enabled_any else "")

        for sig, row_widget in meta.get('rows', {}).items():
            row_widget.setVisible(self._kp_is_enabled(cfg_key, sig))

    def _schedule_config_commit(self):
        # 发送配置优先，短防抖保证交互手感
        self.cfg_send_timer.start(30)
        # 写盘使用更长防抖，避免滑块拖动高频 I/O
        self.cfg_save_timer.start(300)

    def _flush_pending_config(self):
        if self.cfg_send_timer.isActive():
            self.cfg_send_timer.stop()
            self._send_config()
        if self.cfg_save_timer.isActive():
            self.cfg_save_timer.stop()
            self._save_config()

    def _send_config(self):
        if not self.config_queue:
            return
        try:
            while True:
                try:
                    self.config_queue.get_nowait()
                except:
                    break
            try:
                self.config_queue.put_nowait(self.config)
            except:
                pass
        except:
            pass

    def _new_int_box(self, *, default_value, soft_min, soft_max, hard_min=None, hard_max=None,
                     step=1, suffix='', width=None, cfg_key=None, value=None):
        box = _SoftRangeSpinBox(
            soft_min,
            soft_max,
            hard_min if hard_min is not None else soft_min,
            hard_max if hard_max is not None else soft_max,
            default_value=default_value,
        )
        box.setSingleStep(step)
        if suffix:
            box.setSuffix(suffix)
        if width is not None:
            box.setFixedWidth(width)
        initial = self.config.get(cfg_key, default_value) if cfg_key is not None else (default_value if value is None else value)
        box.setValue(int(round(initial)))
        if cfg_key is not None:
            box.valueChanged.connect(lambda v, k=cfg_key: self._update_cfg(k, int(v)))
        return box

    def _new_float_box(self, *, default_value, soft_min, soft_max, hard_min=None, hard_max=None,
                       step=0.01, decimals=2, suffix='', width=None, cfg_key=None, value=None):
        box = _SoftRangeDoubleSpinBox(
            soft_min,
            soft_max,
            hard_min if hard_min is not None else soft_min,
            hard_max if hard_max is not None else soft_max,
            default_value=default_value,
        )
        box.setDecimals(decimals)
        box.setSingleStep(step)
        if suffix:
            box.setSuffix(suffix)
        if width is not None:
            box.setFixedWidth(width)
        initial = self.config.get(cfg_key, default_value) if cfg_key is not None else (default_value if value is None else value)
        box.setValue(float(initial))
        if cfg_key is not None:
            box.valueChanged.connect(lambda v, k=cfg_key: self._update_cfg(k, float(v)))
        return box

    def _new_unbounded_float_input(self, *, default_value, decimals=3, width=None, cfg_key=None, value=None):
        """无上下按钮、超大范围的浮点输入框（用于 K/P 权重范围等不需要软范围/滑块的场景）。"""
        box = QDoubleSpinBox()
        box.setDecimals(int(decimals))
        # 取消上下限（用超大范围近似），并去掉右侧上下按钮
        box.setRange(-1_000_000_000.0, 1_000_000_000.0)
        box.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        box.setKeyboardTracking(False)
        # 避免滚轮误触引起跳变（保留键盘输入即可）
        box.setFocusPolicy(Qt.StrongFocus)
        if width is not None:
            box.setFixedWidth(width)
        initial = self.config.get(cfg_key, default_value) if cfg_key is not None else (default_value if value is None else value)
        box.setValue(float(initial))
        if cfg_key is not None:
            box.valueChanged.connect(lambda v, k=cfg_key: self._update_cfg(k, float(v)))
        return box

    def _new_bound_int_slider(self, *, cfg_key, default_value, soft_min, soft_max, hard_min=None, hard_max=None,
                              step=1, width=62, suffix='', integer=True,
                              kp_soft_min=None, kp_soft_max=None, kp_hard_min=None, kp_hard_max=None, kp_decimals=None):
        slider = QSlider(Qt.Horizontal)
        box = self._new_int_box(
            default_value=default_value,
            soft_min=soft_min,
            soft_max=soft_max,
            hard_min=hard_min,
            hard_max=hard_max,
            step=step,
            width=width,
            suffix=suffix,
            cfg_key=cfg_key,
        )
        box.bind_slider(slider, 1)
        return slider, box

    def _new_bound_float_slider(self, *, cfg_key, default_value, soft_min, soft_max, hard_min=None, hard_max=None,
                                slider_scale=100, step=0.01, decimals=2, width=68, suffix='',
                                kp_soft_min=None, kp_soft_max=None, kp_hard_min=None, kp_hard_max=None, kp_decimals=None):
        slider = QSlider(Qt.Horizontal)
        box = self._new_float_box(
            default_value=default_value,
            soft_min=soft_min,
            soft_max=soft_max,
            hard_min=hard_min,
            hard_max=hard_max,
            step=step,
            decimals=decimals,
            width=width,
            suffix=suffix,
            cfg_key=cfg_key,
        )
        box.bind_slider(slider, slider_scale)
        return slider, box

    def _make_graphics_form_row(self, *, label_text=None, label_widget=None, widgets=None,
                                label_width=92, indent=0, stretch=True):
        row_widget = QWidget()
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(indent, 0, 0, 0)
        row.setSpacing(4)

        current_label = label_widget if label_widget is not None else (QLabel(label_text) if label_text is not None else None)
        if current_label is not None:
            current_label.setFixedWidth(label_width)
            current_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            row.addWidget(current_label)

        for widget in widgets or []:
            row.addWidget(widget)

        if stretch:
            row.addStretch()
        return row_widget

    # ═══════════════════════════════════════════════════════
    #  UI 构建
    # ═══════════════════════════════════════════════════════

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        # ── 顶部：全长横向主面板（常驻监控/调节） ─────────────────
        top = QWidget()
        top.setFont(QFont("微软雅黑", 9))
        tg = QGridLayout(top)
        tg.setContentsMargins(6, 6, 6, 6)
        tg.setHorizontalSpacing(10)
        tg.setVerticalSpacing(6)

        r = 0
        top_action_row = QHBoxLayout()
        top_action_row.setSpacing(8)
        self.master_visible_check = QCheckBox("总开关（显示全部）")
        self.master_visible_check.setChecked(self.config.get('master_visible', True))
        self.master_visible_check.toggled.connect(lambda v: self._update_cfg('master_visible', v))
        top_action_row.addWidget(self.master_visible_check)
        top_action_row.addStretch()

        self.pin_top_btn = QPushButton("置于顶层")
        self.pin_top_btn.setMinimumHeight(24)
        self.pin_top_btn.setCheckable(True)
        self.pin_top_btn.toggled.connect(lambda checked: self._handle_window_layer_toggle('top', checked))
        top_action_row.addWidget(self.pin_top_btn)

        self.pin_bottom_btn = QPushButton("置于底层")
        self.pin_bottom_btn.setMinimumHeight(24)
        self.pin_bottom_btn.setCheckable(True)
        self.pin_bottom_btn.toggled.connect(lambda checked: self._handle_window_layer_toggle('bottom', checked))
        top_action_row.addWidget(self.pin_bottom_btn)

        self.window_layer_state_lbl = QLabel("")
        self.window_layer_state_lbl.setStyleSheet("color:#8a93a1;")
        top_action_row.addWidget(self.window_layer_state_lbl)

        self.restart_program_btn = QPushButton("重启程序")
        self.restart_program_btn.setMinimumHeight(24)
        self.restart_program_btn.clicked.connect(self._restart_visualizer_process)
        top_action_row.addWidget(self.restart_program_btn)
        tg.addLayout(top_action_row, r, 0, 1, 10)

        self.a1_lbl = QLabel("0.00")
        self.k2_lbl = QLabel("0.00")
        self.a1_lbl.hide()
        self.k2_lbl.hide()
        r += 1

        tg.addWidget(QLabel("主预设:"), r, 0)
        self.preset_combo = QComboBox()
        self.preset_combo.setEditable(False)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        tg.addWidget(self.preset_combo, r, 1, 1, 2)

        b_prev = QPushButton("上一个")
        b_prev.setMinimumHeight(24)
        b_prev.clicked.connect(lambda: self._switch_preset_by_offset(-1, update_info=True))
        tg.addWidget(b_prev, r, 3)

        b_next = QPushButton("下一个")
        b_next.setMinimumHeight(24)
        b_next.clicked.connect(lambda: self._switch_preset_by_offset(1, update_info=True))
        tg.addWidget(b_next, r, 4)

        b_save = QPushButton("另存为")
        b_save.setMinimumHeight(24)
        b_save.clicked.connect(self._save_preset_as)
        tg.addWidget(b_save, r, 5)

        b_save_current = QPushButton("覆盖保存当前")
        b_save_current.setMinimumHeight(24)
        b_save_current.clicked.connect(self._save_current_preset)
        tg.addWidget(b_save_current, r, 6)

        b_reload = QPushButton("刷新")
        b_reload.setMinimumHeight(24)
        b_reload.clicked.connect(self._refresh_preset_list)
        tg.addWidget(b_reload, r, 7)

        b_delete_current = QPushButton("删除当前")
        b_delete_current.setMinimumHeight(24)
        b_delete_current.clicked.connect(self._delete_current_preset)
        tg.addWidget(b_delete_current, r, 8)

        b_rename_current = QPushButton("重命名")
        b_rename_current.setMinimumHeight(24)
        b_rename_current.clicked.connect(self._rename_current_preset)
        tg.addWidget(b_rename_current, r, 9)
        r += 1

        preset_row = QHBoxLayout(); preset_row.setSpacing(8)
        self.preset_auto_check = QCheckBox("自动切换")
        self.preset_auto_check.setChecked(self.config.get('preset_auto_switch', False))
        self.preset_auto_check.toggled.connect(self._on_preset_auto_toggled)
        preset_row.addWidget(self.preset_auto_check)

        self.preset_switch_random_check = QCheckBox("随机切换")
        self.preset_switch_random_check.setChecked(self.config.get('preset_switch_random_enabled', False))
        self.preset_switch_random_check.toggled.connect(self._on_preset_switch_random_toggled)
        preset_row.addWidget(self.preset_switch_random_check)

        self.preset_switch_infinite_random_check = QCheckBox("无限随机")
        self.preset_switch_infinite_random_check.setChecked(self.config.get('preset_switch_infinite_random_enabled', False))
        self.preset_switch_infinite_random_check.toggled.connect(self._on_preset_switch_infinite_random_toggled)
        preset_row.addWidget(self.preset_switch_infinite_random_check)

        preset_row.addWidget(QLabel("间隔"))
        self.preset_interval_spin = self._new_float_box(
            default_value=10.0, soft_min=0.01, soft_max=3600.0,
            hard_min=0.0, hard_max=86400.0, step=0.01, decimals=2,
            suffix=' 秒', value=self.config.get('preset_switch_interval', 10.0)
        )
        self.preset_interval_spin.valueChanged.connect(self._on_preset_interval_changed)
        preset_row.addWidget(self.preset_interval_spin)

        self.preset_interval_random_check = QCheckBox("随机间隔")
        self.preset_interval_random_check.setChecked(self.config.get('preset_interval_random_enabled', False))
        self.preset_interval_random_check.toggled.connect(self._on_preset_interval_random_toggled)
        preset_row.addWidget(self.preset_interval_random_check)

        preset_row.addWidget(QLabel("下限"))
        self.preset_interval_min_spin = self._new_float_box(
            default_value=1.0, soft_min=0.01, soft_max=3600.0,
            hard_min=0.0, hard_max=86400.0, step=0.01, decimals=2,
            suffix=' 秒', value=self.config.get('preset_switch_interval_min', 1.0)
        )
        self.preset_interval_min_spin.valueChanged.connect(self._on_preset_interval_min_changed)
        preset_row.addWidget(self.preset_interval_min_spin)

        preset_row.addWidget(QLabel("上限"))
        self.preset_interval_max_spin = self._new_float_box(
            default_value=10.0, soft_min=0.01, soft_max=3600.0,
            hard_min=0.0, hard_max=86400.0, step=0.01, decimals=2,
            suffix=' 秒', value=self.config.get('preset_switch_interval_max', 10.0)
        )
        self.preset_interval_max_spin.valueChanged.connect(self._on_preset_interval_max_changed)
        preset_row.addWidget(self.preset_interval_max_spin)
        preset_row.addStretch()
        tg.addLayout(preset_row, r, 0, 1, 10)
        self._update_preset_interval_mode_ui()
        r += 1

        transition_row = QHBoxLayout(); transition_row.setSpacing(6)
        self.preset_transition_check = QCheckBox("平滑过渡")
        self.preset_transition_check.setChecked(self.config.get('preset_transition_enabled', False))
        self.preset_transition_check.toggled.connect(lambda v: self._update_cfg('preset_transition_enabled', v))
        transition_row.addWidget(self.preset_transition_check)
        self.preset_transition_ctrl = QWidget()
        _tr_inner = QHBoxLayout(self.preset_transition_ctrl)
        _tr_inner.setContentsMargins(0, 0, 0, 0); _tr_inner.setSpacing(6)
        _tr_inner.addWidget(QLabel("时长:"))
        self.preset_transition_duration_spin = self._new_float_box(
            default_value=2.0, soft_min=0.1, soft_max=30.0,
            hard_min=0.05, hard_max=300.0, step=0.1, decimals=1,
            suffix=' 秒', cfg_key='preset_transition_duration'
        )
        _tr_inner.addWidget(self.preset_transition_duration_spin)
        _tr_inner.addStretch()
        self.preset_transition_ctrl.setVisible(self.config.get('preset_transition_enabled', False))
        self.preset_transition_check.toggled.connect(self.preset_transition_ctrl.setVisible)
        transition_row.addWidget(self.preset_transition_ctrl)
        transition_row.addStretch()
        tg.addLayout(transition_row, r, 0, 1, 10)
        r += 1

        tg.addWidget(QLabel("颜色方案:"), r, 0)
        self.palette_preview_cells = []
        self.palette_preview_labels = []
        palette_row = QHBoxLayout(); palette_row.setSpacing(4)
        for _ in range(8):
            cell_wrap = QWidget()
            cell_layout = QVBoxLayout(cell_wrap)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setSpacing(2)
            cell = QFrame()
            cell.setFixedSize(22, 22)
            cell.setFrameShape(QFrame.StyledPanel)
            cell.setStyleSheet("border:1px solid #666; border-radius:2px;")
            self.palette_preview_cells.append(cell)
            idx = len(self.palette_preview_cells) - 1
            cell.setCursor(Qt.PointingHandCursor)
            def _make_handler(i):
                return lambda ev: self._on_palette_cell_clicked(i)
            cell.mousePressEvent = _make_handler(idx)
            cell_layout.addWidget(cell, alignment=Qt.AlignHCenter)
            label = QLabel("")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("color:#8a93a1; font-size:7.5pt;")
            self.palette_preview_labels.append(label)
            cell_layout.addWidget(label)
            palette_row.addWidget(cell_wrap)
        palette_row.addStretch()
        tg.addLayout(palette_row, r, 1, 1, 9)
        r += 1

        brow = QHBoxLayout(); brow.setSpacing(8)
        b1 = QPushButton("📍 复位位置"); b1.setMinimumHeight(28)
        b1.clicked.connect(self._center_window); brow.addWidget(b1)
        b2 = QPushButton("🔄 复位参数"); b2.setMinimumHeight(28)
        b2.clicked.connect(self._reset_all); brow.addWidget(b2)
        brow.addStretch()
        tg.addLayout(brow, r, 0, 1, 6)

        tg.addWidget(QLabel("缩放:"), r, 6)
        self.scale_spin = self._new_float_box(
            default_value=1.0, soft_min=0.1, soft_max=10.0,
            hard_min=0.01, hard_max=100.0, step=0.1, decimals=2,
            cfg_key='global_scale'
        )
        tg.addWidget(self.scale_spin, r, 7)
        tg.addWidget(QLabel("x"), r, 8)
        r += 1

        tg.addWidget(QLabel("位置 X/Y:"), r, 0)
        h_pos = QHBoxLayout(); h_pos.setSpacing(6)
        self.pos_x_spin = self._new_int_box(
            default_value=-1, soft_min=-9999, soft_max=9999,
            hard_min=-99999, hard_max=99999, cfg_key='pos_x'
        )
        self.pos_y_spin = self._new_int_box(
            default_value=-1, soft_min=-9999, soft_max=9999,
            hard_min=-99999, hard_max=99999, cfg_key='pos_y'
        )
        h_pos.addWidget(self.pos_x_spin)
        h_pos.addWidget(self.pos_y_spin)
        tg.addLayout(h_pos, r, 1, 1, 3)

        self.drag_adjust_check = QCheckBox("拖动调整位置")
        self.drag_adjust_check.setChecked(self.config.get('drag_adjust_mode', False))
        self.drag_adjust_check.toggled.connect(lambda v: self._update_cfg('drag_adjust_mode', v))
        tg.addWidget(self.drag_adjust_check, r, 4, 1, 3)
        r += 1

        self.single_bar_panel = self._build_single_bar_preview_panel()

        self.info_bar_lbl = QLabel("")
        self.info_bar_lbl.setStyleSheet("color:#888; font-size:9pt;")
        tg.addWidget(self.info_bar_lbl, r, 0, 1, 10)
        r += 1

        root.addWidget(top)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        root.addWidget(sep)

        # ── 下方：两列（左：结构导航；右：选中项详情面板） ───────────
        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        root.addLayout(bottom, 1)

        left_column = QWidget()
        left_layout = QVBoxLayout(left_column)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)
        bottom.addWidget(left_column, 0)

        self.nav_tree = QTreeWidget()
        self.nav_tree.setColumnCount(2)
        self.nav_tree.setHeaderHidden(True)
        self.nav_tree.setMinimumWidth(220)
        self.nav_tree.setMaximumWidth(320)
        self.nav_tree.setFrameShape(QFrame.StyledPanel)
        self.nav_tree.setColumnWidth(1, 28)
        left_layout.addWidget(self.nav_tree, 1)

        self.preview_toggle_btn = QPushButton("▸ 图形预览")
        self.preview_toggle_btn.setCheckable(True)
        self.preview_toggle_btn.setChecked(False)
        self.preview_toggle_btn.toggled.connect(self._toggle_preview_sidebar)
        left_layout.addWidget(self.preview_toggle_btn)

        self.preview_sidebar = QWidget()
        preview_sidebar_layout = QVBoxLayout(self.preview_sidebar)
        preview_sidebar_layout.setContentsMargins(0, 0, 0, 0)
        preview_sidebar_layout.setSpacing(0)
        preview_sidebar_layout.addWidget(self.single_bar_panel)
        left_layout.addWidget(self.preview_sidebar)
        self._toggle_preview_sidebar(False)

        self.detail_stack = QStackedWidget()
        self.detail_scroll = QScrollArea()
        self.detail_scroll.setWidgetResizable(True)
        self.detail_scroll.setFrameShape(QFrame.NoFrame)
        self.detail_scroll.setWidget(self.detail_stack)
        bottom.addWidget(self.detail_scroll, 1)

        # 右侧详情页（使用原有 section 组件，但只显示一个）
        self._detail_pages = []
        self._nav_index = {}

        pages = [
            (("主题设置",), self._build_theme_root_section()),
            (("主题设置", "经典"), self._build_classic_theme_section()),
            (("主题设置", "经典", "填充子主题"), self._build_fill_theme_section()),
            (("主题设置", "经典", "连线子主题"), self._build_line_theme_section()),
            (("主题设置", "柔体主题"), self._build_softbody_theme_section()),
            (("控制",), self._build_control_section()),
            (("颜色方案",), self._build_color_section()),
            (("运动表现",), self._build_physics_section()),
            (("高级控制",), self._build_k1_section()),
            (("镜头划痕眩光",), self._build_lens_scratch_section()),
            (("导出到Unity",), self._build_unity_export_section()),
            (("🎲 随机",), self._build_random_section()),
        ]

        theme_toggle_sections = {
            ("主题设置", "经典"): 'theme_classic_kaleidoscope',
            ("主题设置", "经典", "填充子主题"): 'theme_kaleidoscope_fill',
            ("主题设置", "经典", "连线子主题"): 'theme_kaleidoscope_lines',
            ("主题设置", "柔体主题"): 'theme_softbody',
        }

        nav_nodes = {}
        for idx, (path_parts, w) in enumerate(pages):
            if isinstance(w, _Collapsible):
                w.as_detail_panel()
            wrap = QWidget()
            wrap.setFont(QFont("微软雅黑", 9))
            wl = QVBoxLayout(wrap)
            wl.setContentsMargins(4, 4, 4, 4)
            wl.setSpacing(2)
            wl.addWidget(w)
            wl.addStretch()
            self.detail_stack.addWidget(wrap)
            self._detail_pages.append(wrap)

            parent_item = None
            current_path = []
            for part in path_parts:
                current_path.append(part)
                path_key = tuple(current_path)
                item = nav_nodes.get(path_key)
                if item is None:
                    item = QTreeWidgetItem([part])
                    if parent_item is None:
                        self.nav_tree.addTopLevelItem(item)
                    else:
                        parent_item.addChild(item)
                    nav_nodes[path_key] = item
                parent_item = item

            parent_item.setData(0, Qt.UserRole, idx)
            self._nav_index[' / '.join(path_parts)] = idx

            section = theme_toggle_sections.get(path_parts)
            if section:
                parent_item.setText(1, ' ')
                self.nav_tree.setItemWidget(parent_item, 1, self._create_theme_nav_check(section))

        for item in nav_nodes.values():
            if item.childCount() > 0:
                item.setExpanded(True)

        self.nav_tree.currentItemChanged.connect(self._on_nav_changed)
        if self.nav_tree.topLevelItemCount() > 0:
            self.nav_tree.setCurrentItem(self.nav_tree.topLevelItem(0))

        if self.config.get('preset_auto_switch', False):
            self._schedule_next_preset_switch()

        self._update_color_preview_strip()
        self._sync_theme_enable_widgets()

    def _on_nav_changed(self, current, _previous):
        if not current:
            return
        idx = current.data(0, Qt.UserRole)
        if isinstance(idx, int) and 0 <= idx < self.detail_stack.count():
            self.detail_stack.setCurrentIndex(idx)

    def _toggle_preview_sidebar(self, expanded):
        expanded = bool(expanded)
        was_expanded = bool(self._preview_sidebar_last_state)
        preview_height = max(self.preview_sidebar.sizeHint().height(), self.single_bar_panel.sizeHint().height())
        self.preview_sidebar.setVisible(expanded)
        self.preview_toggle_btn.setText("▾ 图形预览" if expanded else "▸ 图形预览")
        self._preview_sidebar_last_state = expanded
        if self.isMaximized() or self.isFullScreen() or expanded == was_expanded:
            return
        delta = preview_height + 8
        if expanded:
            self.resize(self.width(), self.height() + delta)
            return
        self.resize(self.width(), max(self.minimumSizeHint().height(), self.height() - delta))

    def _make_preview_card(self):
        card = QFrame()
        card.setObjectName("previewCard")
        card.setStyleSheet(
            "QFrame#previewCard{border:1px solid #3b3f47;border-radius:8px;background:rgba(255,255,255,0.03);}" 
            "QLabel{color:#dce1e8;}"
            "QCheckBox{color:#dce1e8;}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        return card, layout

    def _build_damping_pair_layout(self, rise_cfg_key, fall_cfg_key, *, default_rise=0.1, default_fall=0.999,
                                   rise_label='增大阻尼:', fall_label='缩小阻尼:'):
        row = QHBoxLayout()
        row.setSpacing(4)
        row.addWidget(QLabel(rise_label))
        rise_box = self._new_float_box(
            default_value=default_rise, soft_min=0.0, soft_max=0.95,
            hard_min=0.0, hard_max=0.999, step=0.01, decimals=3,
            cfg_key=rise_cfg_key
        )
        row.addWidget(rise_box)
        row.addWidget(QLabel(fall_label))
        fall_box = self._new_float_box(
            default_value=default_fall, soft_min=0.0, soft_max=0.999,
            hard_min=0.0, hard_max=0.999, step=0.01, decimals=3,
            cfg_key=fall_cfg_key
        )
        row.addWidget(fall_box)
        row.addStretch()
        return row, rise_box, fall_box

    def _build_independent_damping_controls(self, prefix, *, label='启用独立阻尼'):
        checkbox = QCheckBox(label)
        checkbox.setChecked(self.config.get(f'{prefix}_use_independent_damping', False))
        checkbox.toggled.connect(lambda v, k=f'{prefix}_use_independent_damping': self._update_cfg(k, v))

        widget = QWidget()
        container = QHBoxLayout(widget)
        container.setContentsMargins(18, 0, 0, 0)
        container.setSpacing(0)
        row, rise_box, fall_box = self._build_damping_pair_layout(
            f'{prefix}_independent_rise_damping',
            f'{prefix}_independent_fall_damping',
        )
        container.addLayout(row)
        widget.setVisible(checkbox.isChecked())
        checkbox.toggled.connect(widget.setVisible)
        return checkbox, widget, rise_box, fall_box

    def _build_independent_time_window_controls(self, prefix, *, label='启用独立T'):
        checkbox = QCheckBox(label)
        checkbox.setChecked(self.config.get(f'{prefix}_use_independent_time_window', False))
        checkbox.toggled.connect(self._on_bar_independent_time_window_toggled)

        widget = QWidget()
        container = QHBoxLayout(widget)
        container.setContentsMargins(18, 0, 0, 0)
        container.setSpacing(4)
        container.addWidget(QLabel('频谱T:'))
        time_box = self._new_float_box(
            default_value=10.0, soft_min=0.01, soft_max=60.0,
            hard_min=0.01, hard_max=10000.0, step=0.1, decimals=2,
            suffix=' 秒', cfg_key=f'{prefix}_time_window'
        )
        container.addWidget(time_box)
        container.addStretch()
        widget.setVisible(checkbox.isChecked())
        checkbox.toggled.connect(widget.setVisible)
        return checkbox, widget, time_box

    def _on_bar_independent_time_window_toggled(self, checked):
        if checked and not self._applying_config:
            self._update_cfg('bar_time_window', _clamp_time_window(self.config.get('a1_time_window', 10.0), 10.0))
        self._update_cfg('bar_use_independent_time_window', bool(checked))

    def _build_single_bar_preview_panel(self):
        panel = QWidget()
        root = QVBoxLayout(panel)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        k_card, k_layout = self._make_preview_card()
        self.k_preview = _SignalPreviewWidget("K 预览", signed=False)
        k_layout.addWidget(self.k_preview)
        t_row = QHBoxLayout()
        t_row.setSpacing(4)
        t_row.addWidget(QLabel("T:"))
        self.a1_spin = self._new_float_box(
            default_value=10.0, soft_min=0.01, soft_max=60.0,
            hard_min=0.0, hard_max=10000.0, step=0.1, decimals=2,
            suffix=' 秒', cfg_key='a1_time_window'
        )
        t_row.addWidget(self.a1_spin)
        t_row.addStretch()
        k_layout.addLayout(t_row)
        k_damping_row, self.k_rise_damping_spin, self.k_fall_damping_spin = self._build_damping_pair_layout(
            'k_rise_damping', 'k_fall_damping'
        )
        k_layout.addLayout(k_damping_row)
        root.addWidget(k_card)

        p_card, p_layout = self._make_preview_card()
        self.p_preview = _SignalPreviewWidget("P 预览", signed=True)
        p_layout.addWidget(self.p_preview)
        p_row = QHBoxLayout()
        p_row.setSpacing(6)
        self.k2_check = QCheckBox("使用 P 替代 K")
        self.k2_check.setChecked(self.config.get('k2_enabled', False))
        self.k2_check.toggled.connect(lambda v: self._update_cfg('k2_enabled', v))
        p_row.addWidget(self.k2_check)
        p_row.addStretch()
        p_row.addWidget(QLabel("P2:"))
        self.k2_pow_spin = self._new_float_box(
            default_value=1.0, soft_min=0.01, soft_max=10.0,
            hard_min=-10000.0, hard_max=10000.0, step=0.1, decimals=2,
            cfg_key='k2_pow'
        )
        p_row.addWidget(self.k2_pow_spin)
        p_layout.addLayout(p_row)
        root.addWidget(p_card)

        spec_card, spec_layout = self._make_preview_card()
        self.spectrum_preview = _SpectrumBarsPreviewWidget()
        spec_layout.addWidget(self.spectrum_preview)

        row1 = QHBoxLayout(); row1.setSpacing(4)
        row1.addWidget(QLabel("条数:"))
        self.bars_spin = self._new_int_box(
            default_value=64, soft_min=1, soft_max=512,
            hard_min=1, hard_max=8192, step=1, cfg_key='num_bars'
        )
        row1.addWidget(self.bars_spin)
        row1.addStretch()
        spec_layout.addLayout(row1)

        row2 = QHBoxLayout(); row2.setSpacing(4)
        row2.addWidget(QLabel("Hz:"))
        self.freq_min_spin = self._new_int_box(
            default_value=20, soft_min=0, soft_max=5000,
            hard_min=0, hard_max=200000, step=1, cfg_key='freq_min'
        )
        self.freq_max_spin = self._new_int_box(
            default_value=20000, soft_min=100, soft_max=40000,
            hard_min=0, hard_max=200000, step=10, cfg_key='freq_max'
        )
        self.freq_min_spin.valueChanged.connect(self._on_freq_min_changed)
        self.freq_max_spin.valueChanged.connect(self._on_freq_max_changed)
        row2.addWidget(self.freq_min_spin)
        row2.addWidget(QLabel("~"))
        row2.addWidget(self.freq_max_spin)
        row2.addWidget(QLabel("Hz"))
        row2.addStretch()
        spec_layout.addLayout(row2)

        row3 = QHBoxLayout(); row3.setSpacing(4)
        row3.addWidget(QLabel("长度:"))
        self.bar_len_min_spin = self._new_int_box(
            default_value=0, soft_min=0, soft_max=500,
            hard_min=0, hard_max=10000, step=1, cfg_key='bar_length_min'
        )
        self.bar_len_max_spin = self._new_int_box(
            default_value=300, soft_min=1, soft_max=2000,
            hard_min=0, hard_max=10000, step=1, cfg_key='bar_length_max'
        )
        self.bar_len_min_spin.valueChanged.connect(self._on_bar_len_min_changed)
        self.bar_len_max_spin.valueChanged.connect(self._on_bar_len_max_changed)
        row3.addWidget(self.bar_len_min_spin)
        row3.addWidget(QLabel("~"))
        row3.addWidget(self.bar_len_max_spin)
        row3.addWidget(QLabel("px"))
        spec_layout.addLayout(row3)

        self.bar_independent_time_window_check, self.bar_independent_time_window_widget, self.bar_time_window_spin = self._build_independent_time_window_controls('bar')
        spec_layout.addWidget(self.bar_independent_time_window_check)
        spec_layout.addWidget(self.bar_independent_time_window_widget)

        self.bar_independent_damping_check, self.bar_independent_damping_widget, self.bar_independent_rise_damping_spin, self.bar_independent_fall_damping_spin = self._build_independent_damping_controls('bar')
        spec_layout.addWidget(self.bar_independent_damping_check)
        spec_layout.addWidget(self.bar_independent_damping_widget)

        root.addWidget(spec_card)

        color_card, color_layout = self._make_preview_card()
        self.color_preview = _DynamicColorPreviewWidget()
        color_layout.addWidget(self.color_preview)
        color_row1 = QHBoxLayout()
        color_row1.setSpacing(6)
        self.color_dynamic_quick_check = QCheckBox('动态颜色')
        self.color_dynamic_quick_check.setChecked(self.config.get('color_dynamic', False))
        self.color_dynamic_quick_check.toggled.connect(lambda v: self._update_cfg('color_dynamic', v))
        color_row1.addWidget(self.color_dynamic_quick_check)
        self.color_cycle_a1_quick_check = QCheckBox('P 突变加速')
        self.color_cycle_a1_quick_check.setChecked(self.config.get('color_cycle_a1', True))
        self.color_cycle_a1_quick_check.toggled.connect(lambda v: self._update_cfg('color_cycle_a1', v))
        color_row1.addWidget(self.color_cycle_a1_quick_check)
        color_row1.addStretch()
        color_layout.addLayout(color_row1)

        self.color_quick_controls_widget = QWidget()
        color_controls_layout = QHBoxLayout(self.color_quick_controls_widget)
        color_controls_layout.setContentsMargins(0, 0, 0, 0)
        color_controls_layout.setSpacing(4)
        color_controls_layout.addWidget(QLabel('V0:'))
        self.color_cycle_speed_quick_spin = self._new_float_box(
            default_value=1.0, soft_min=0.0, soft_max=10.0,
            hard_min=-100.0, hard_max=100.0, step=0.01, decimals=2,
            suffix='x', cfg_key='color_cycle_speed'
        )
        color_controls_layout.addWidget(self.color_cycle_speed_quick_spin)
        color_controls_layout.addWidget(QLabel('VP:'))
        self.color_cycle_pow_quick_spin = self._new_float_box(
            default_value=2.0, soft_min=0.01, soft_max=5.0,
            hard_min=-100.0, hard_max=100.0, step=0.01, decimals=2,
            cfg_key='color_cycle_pow'
        )
        color_controls_layout.addWidget(self.color_cycle_pow_quick_spin)
        color_controls_layout.addStretch()
        color_layout.addWidget(self.color_quick_controls_widget)

        root.addWidget(color_card)

        self._sync_color_quick_widgets(self.config.get('color_dynamic', False))
        self._refresh_single_bar_preview()
        return panel

    def _on_bar_len_min_changed(self, value):
        if self._applying_config:
            self._refresh_single_bar_preview()
            return
        if value > self.bar_len_max_spin.value():
            self.bar_len_max_spin.blockSignals(True)
            self.bar_len_max_spin.setValue(int(value))
            self.bar_len_max_spin.blockSignals(False)
            self._update_cfg('bar_length_max', int(value))
        self._refresh_single_bar_preview()

    def _on_bar_len_max_changed(self, value):
        if self._applying_config:
            self._refresh_single_bar_preview()
            return
        if value < self.bar_len_min_spin.value():
            self.bar_len_min_spin.blockSignals(True)
            self.bar_len_min_spin.setValue(int(value))
            self.bar_len_min_spin.blockSignals(False)
            self._update_cfg('bar_length_min', int(value))
        self._refresh_single_bar_preview()

    def _on_freq_min_changed(self, value):
        if self._applying_config:
            self._refresh_single_bar_preview()
            return
        if value > self.freq_max_spin.value():
            self.freq_max_spin.blockSignals(True)
            self.freq_max_spin.setValue(int(value))
            self.freq_max_spin.blockSignals(False)
            self._update_cfg('freq_max', int(value))
        self._refresh_single_bar_preview()

    def _on_freq_max_changed(self, value):
        if self._applying_config:
            self._refresh_single_bar_preview()
            return
        if value < self.freq_min_spin.value():
            self.freq_min_spin.blockSignals(True)
            self.freq_min_spin.setValue(int(value))
            self.freq_min_spin.blockSignals(False)
            self._update_cfg('freq_min', int(value))
        self._refresh_single_bar_preview()

    def _refresh_single_bar_preview(self):
        if not hasattr(self, 'k_preview'):
            return
        freq_min = int(self.config.get('freq_min', 20))
        freq_max = int(self.config.get('freq_max', 20000))
        if freq_min > freq_max:
            freq_min, freq_max = freq_max, freq_min
        uses_independent_time_window = bool(self.config.get('bar_use_independent_time_window', False))
        spectrum_time_window = _clamp_time_window(
            self.config.get('bar_time_window', self.config.get('a1_time_window', 10.0)),
            self.config.get('a1_time_window', 10.0),
        ) if uses_independent_time_window else _clamp_time_window(self.config.get('a1_time_window', 10.0), 10.0)
        bar_rise_damping, bar_fall_damping = self._get_damping_pair('bar')
        self.k_preview.set_runtime_state(self.current_a1)
        self.p_preview.set_runtime_state(self.current_p)
        self.spectrum_preview.set_config_snapshot(
            bar_count=int(self.config.get('num_bars', 64)),
            segments=int(self.config.get('circle_segments', 1)),
            freq_min=freq_min,
            freq_max=freq_max,
            time_window=spectrum_time_window,
            uses_independent_time_window=uses_independent_time_window,
            uses_independent_damping=bool(self.config.get('bar_use_independent_damping', False)),
            rise_damping=bar_rise_damping,
            fall_damping=bar_fall_damping,
        )
        self.spectrum_preview.set_runtime_state(self.preview_spectrum_values)
        preview_colors = self._build_spectrum_preview_colors(
            [0.0] * max(1, int(self.config.get('num_bars', 64)))
        )
        current_color = _sample_preview_color(self.preview_dynamic_colors or preview_colors, self.current_color_cycle_hue)
        self.color_preview.set_runtime_state(
            preview_colors,
            phase=self.current_color_cycle_hue,
            rate=self.current_color_cycle_rate,
            dynamic_enabled=bool(self.config.get('color_dynamic', False)),
            current_color=current_color,
        )

    @staticmethod
    def _interpolate_preview_color(ratio, points):
        if not points:
            return (255, 255, 255)
        for index in range(len(points) - 1):
            pos1, color1 = points[index]
            pos2, color2 = points[index + 1]
            if pos1 <= ratio <= pos2:
                blend = (ratio - pos1) / (pos2 - pos1) if pos2 > pos1 else 0.0
                return (
                    int(color1[0] * (1.0 - blend) + color2[0] * blend),
                    int(color1[1] * (1.0 - blend) + color2[1] * blend),
                    int(color1[2] * (1.0 - blend) + color2[2] * blend),
                )
        if ratio <= points[0][0]:
            return tuple(points[0][1])
        return tuple(points[-1][1])

    def _build_spectrum_preview_colors(self, values):
        count = len(values) if values else max(1, int(self.config.get('num_bars', 64)))
        scheme = self.config.get('color_scheme', 'rainbow')
        gradient_mode = self.config.get('gradient_mode', 'frequency')
        gradient_enabled = self.config.get('gradient_enabled', True)
        colors = []

        if scheme == 'custom':
            points = sorted(self.config.get('gradient_points', [(0.0, (255, 0, 128)), (1.0, (0, 255, 255))]), key=lambda item: item[0])
            if not gradient_enabled:
                base = tuple(points[0][1]) if points else (255, 255, 255)
                return [base] * count
            min_height = float(self.config.get('bar_height_min', 0))
            max_height = float(self.config.get('bar_height_max', 500))
            span = max(1.0, max_height - min_height)
            for index in range(count):
                if gradient_mode == 'height' and values:
                    ratio = max(0.0, min(1.0, (float(values[index]) - min_height) / span))
                else:
                    ratio = index / max(1, count - 1)
                colors.append(self._interpolate_preview_color(ratio, points))
            return colors

        for index in range(count):
            ratio = index / max(1, count - 1)
            if scheme == 'rainbow':
                rgb = colorsys.hsv_to_rgb(ratio, 1.0, 1.0)
            elif scheme == 'fire':
                rgb = (1.0, ratio * 0.8, ratio * 0.2)
            elif scheme == 'ice':
                rgb = (ratio * 0.3, ratio * 0.7, 1.0)
            elif scheme == 'neon':
                rgb = colorsys.hsv_to_rgb((ratio + 0.5) % 1.0, 1.0, 1.0)
            else:
                rgb = colorsys.hsv_to_rgb(ratio, 1.0, 1.0)
            colors.append(tuple(int(channel * 255) for channel in rgb))
        return colors

    # ── 控制（含基础设置） ──────────────────────────────

    def _build_control_section(self):
        s = _Collapsible("控制", expanded=True)
        g = QGridLayout(); g.setSpacing(3); g.setContentsMargins(0,0,0,0); r = 0

        _sh = QLabel("── 频谱布局 ──")
        _sh.setStyleSheet("color:#888; font-size:8pt; padding:3px 0 1px 0;")
        g.addWidget(_sh, r, 0, 1, 3); r += 1

        g.addWidget(QLabel("半径:"), r, 0)
        self.radius_spin = self._new_int_box(
            default_value=150, soft_min=10, soft_max=2000,
            hard_min=0, hard_max=20000, step=10, cfg_key='circle_radius'
        )
        g.addWidget(self.radius_spin, r, 1); g.addWidget(QLabel("px"), r, 2); r += 1

        g.addWidget(QLabel("段数:"), r, 0)
        self.seg_spin = self._new_int_box(
            default_value=1, soft_min=1, soft_max=11,
            hard_min=1, hard_max=360, step=1, cfg_key='circle_segments'
        )
        g.addWidget(self.seg_spin, r, 1); g.addWidget(QLabel("段"), r, 2); r += 1

        hr = QHBoxLayout(); hr.setSpacing(12)
        self.a1rot_check = QCheckBox("K 驱动旋转")
        self.a1rot_check.setChecked(self.config['circle_a1_rotation'])
        self.a1rot_check.toggled.connect(lambda v: self._update_cfg('circle_a1_rotation', v))
        self.a1rad_check = QCheckBox("K 响应半径")
        self.a1rad_check.setChecked(self.config['circle_a1_radius'])
        self.a1rad_check.toggled.connect(lambda v: self._update_cfg('circle_a1_radius', v))
        hr.addWidget(self.a1rot_check); hr.addWidget(self.a1rad_check); hr.addStretch()
        g.addLayout(hr, r, 0, 1, 3); r += 1

        _sh2 = QLabel("── 半径缓动 ──")
        _sh2.setStyleSheet("color:#888; font-size:8pt; padding:3px 0 1px 0;")
        g.addWidget(_sh2, r, 0, 1, 3); r += 1
        for lbl_t, attr, cfg_key, default, soft_min, soft_max, hard_min, hard_max in [
            ("阻尼:", "rdamp", 'radius_damping', 0.92, 0.50, 0.99, 0.0, 2.0),
            ("弹性:", "rspring", 'radius_spring', 0.15, 0.01, 1.00, 0.0, 5.0),
            ("回弹:", "rgrav", 'radius_gravity', 0.3, 0.00, 1.00, 0.0, 5.0),
        ]:
            g.addWidget(QLabel(lbl_t), r, 0)
            sl, box = self._new_bound_float_slider(
                cfg_key=cfg_key, default_value=default, soft_min=soft_min, soft_max=soft_max,
                hard_min=hard_min, hard_max=hard_max, slider_scale=100,
                step=0.01, decimals=2
            )
            g.addWidget(sl, r, 1); g.addWidget(box, r, 2)
            setattr(self, f'{attr}_slider', sl); setattr(self, f'{attr}_spin', box)
            r += 1

        hint = QLabel("顶部四联预览已承载 K / P / T / P2、默认阻尼、条形图独立阻尼，以及动态颜色预览快捷输入。图元独立阻尼已移到“主题设置”树下的对应子主题页。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#8a93a1; font-size:8.5pt; padding-top:4px;")
        g.addWidget(hint, r, 0, 1, 3)

        s.add_layout(g)
        return s

    # ── 预设管理 ──────────────────────────────────────────

    def _build_preset_section(self):
        s = _Collapsible("预设管理", expanded=True)
        v = QVBoxLayout(); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(6)

        row1 = QHBoxLayout(); row1.setSpacing(6)
        row1.addWidget(QLabel("分类:"))
        self.preset_category_combo = QComboBox()
        for category, label in PRESET_CATEGORY_LABELS.items():
            self.preset_category_combo.addItem(label, category)
        self._set_preset_category_combo_silent(PRESET_CATEGORY_ALL)
        self.preset_category_combo.currentIndexChanged.connect(self._on_preset_category_changed)
        row1.addWidget(self.preset_category_combo)

        row1.addWidget(QLabel("预设:"))
        self.preset_combo = QComboBox()
        self.preset_combo.setEditable(False)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        row1.addWidget(self.preset_combo, 1)

        b_save = QPushButton("另存为")
        b_save.setMinimumHeight(26)
        b_save.clicked.connect(self._save_preset_as)
        row1.addWidget(b_save)

        b_reload = QPushButton("刷新")
        b_reload.setMinimumHeight(26)
        b_reload.clicked.connect(self._refresh_preset_list)
        row1.addWidget(b_reload)

        b_delete_current = QPushButton("删除当前")
        b_delete_current.setMinimumHeight(26)
        b_delete_current.clicked.connect(self._delete_current_preset)
        row1.addWidget(b_delete_current)

        b_rename_current = QPushButton("重命名")
        b_rename_current.setMinimumHeight(26)
        b_rename_current.clicked.connect(self._rename_current_preset)
        row1.addWidget(b_rename_current)
        v.addLayout(row1)

        row2 = QHBoxLayout(); row2.setSpacing(10)
        self.preset_auto_check = QCheckBox("自动切换")
        self.preset_auto_check.setChecked(self.config.get('preset_auto_switch', False))
        self.preset_auto_check.toggled.connect(self._on_preset_auto_toggled)
        row2.addWidget(self.preset_auto_check)

        row2.addWidget(QLabel("间隔"))
        self.preset_interval_spin = self._new_float_box(
            default_value=10.0, soft_min=0.01, soft_max=3600.0,
            hard_min=0.0, hard_max=86400.0, step=0.01, decimals=2,
            suffix=' 秒', value=self.config.get('preset_switch_interval', 10.0)
        )
        self.preset_interval_spin.valueChanged.connect(self._on_preset_interval_changed)
        row2.addWidget(self.preset_interval_spin)
        row2.addStretch()
        v.addLayout(row2)

        row3 = QHBoxLayout(); row3.setSpacing(10)
        self.preset_interval_random_check = QCheckBox("随机间隔")
        self.preset_interval_random_check.setChecked(self.config.get('preset_interval_random_enabled', False))
        self.preset_interval_random_check.toggled.connect(self._on_preset_interval_random_toggled)
        row3.addWidget(self.preset_interval_random_check)

        row3.addWidget(QLabel("下限"))
        self.preset_interval_min_spin = self._new_float_box(
            default_value=1.0, soft_min=0.01, soft_max=3600.0,
            hard_min=0.0, hard_max=86400.0, step=0.01, decimals=2,
            suffix=' 秒', value=self.config.get('preset_switch_interval_min', 1.0)
        )
        self.preset_interval_min_spin.valueChanged.connect(self._on_preset_interval_min_changed)
        row3.addWidget(self.preset_interval_min_spin)

        row3.addWidget(QLabel("上限"))
        self.preset_interval_max_spin = self._new_float_box(
            default_value=10.0, soft_min=0.01, soft_max=3600.0,
            hard_min=0.0, hard_max=86400.0, step=0.01, decimals=2,
            suffix=' 秒', value=self.config.get('preset_switch_interval_max', 10.0)
        )
        self.preset_interval_max_spin.valueChanged.connect(self._on_preset_interval_max_changed)
        row3.addWidget(self.preset_interval_max_spin)
        row3.addStretch()
        v.addLayout(row3)

        self._update_preset_interval_mode_ui()

        s.add_layout(v)

        # 如果之前已启用，启动定时器
        if self.config.get('preset_auto_switch', False):
            self._schedule_next_preset_switch()

        return s

    def _ensure_presets_dir(self):
        PRESETS_DIR.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe_preset_name(name: str):
        invalid = '<>:"/\\|?*'
        clean = ''.join('_' if ch in invalid else ch for ch in name).strip().strip('.')
        return clean

    @staticmethod
    def _normalize_preset_category(category):
        category = str(category or PRESET_CATEGORY_ALL)
        return category if category in PRESET_CATEGORY_LABELS else PRESET_CATEGORY_ALL

    def _get_selected_preset_category(self):
        if not hasattr(self, 'preset_category_combo'):
            return PRESET_CATEGORY_ALL
        return self._normalize_preset_category(self.preset_category_combo.currentData())

    def _set_preset_category_combo_silent(self, category):
        if not hasattr(self, 'preset_category_combo'):
            return
        target = self._normalize_preset_category(category)
        for index in range(self.preset_category_combo.count()):
            if self.preset_category_combo.itemData(index) == target:
                if self.preset_category_combo.currentIndex() != index:
                    self.preset_category_combo.blockSignals(True)
                    self.preset_category_combo.setCurrentIndex(index)
                    self.preset_category_combo.blockSignals(False)
                return

    @staticmethod
    def _infer_preset_category_from_name(name: str):
        text = str(name or '')
        lower = text.lower()
        if any(token in text for token in ('水母', '柔体', '触须')):
            return PRESET_CATEGORY_JELLYFISH
        if any(token in lower for token in ('jellyfish', 'medusa', 'tentacle', 'softbody')):
            return PRESET_CATEGORY_JELLYFISH
        return PRESET_CATEGORY_CLASSIC

    def _infer_preset_category_from_config(self, data, stem=''):
        by_name = self._infer_preset_category_from_name(stem)
        if by_name != PRESET_CATEGORY_CLASSIC:
            return by_name
        cfg = dict(data or {})
        if not bool(cfg.get('tentacle_on', False)):
            return PRESET_CATEGORY_CLASSIC
        tentacle_count = float(cfg.get('tentacle_count', 0) or 0)
        tentacle_length = float(cfg.get('tentacle_length', 0) or 0)
        turbulence = float(cfg.get('tentacle_turbulence', 0) or 0)
        sway_density = float(cfg.get('tentacle_sway_density', 0) or 0)
        shader_enabled = bool(cfg.get('tentacle_shader_enabled', False))
        if tentacle_count >= 12 and tentacle_length >= 300 and turbulence >= 40 and sway_density >= 2.0 and shader_enabled:
            return PRESET_CATEGORY_JELLYFISH
        return PRESET_CATEGORY_CLASSIC

    @staticmethod
    def _read_preset_json(fp: Path):
        with open(fp, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _get_preset_category_for_file(self, fp: Path):
        try:
            raw = self._read_preset_json(fp)
        except Exception:
            return self._infer_preset_category_from_name(fp.stem)
        explicit = self._normalize_preset_category(raw.get('__preset_category'))
        if explicit != PRESET_CATEGORY_ALL:
            return explicit
        return self._infer_preset_category_from_config(raw, fp.stem)

    def _get_preset_display_name(self, fp: Path, category: str):
        if self._normalize_preset_category(category) == PRESET_CATEGORY_ALL:
            badge = PRESET_CATEGORY_BADGES.get(self._get_preset_category_for_file(fp))
            if badge:
                return f'[{badge}] {fp.stem}'
        return fp.stem

    def _select_preset_by_path(self, preset_path):
        target = str(preset_path) if preset_path else None
        if not target:
            return
        for index in range(self.preset_combo.count()):
            if str(self.preset_combo.itemData(index)) == target:
                self.preset_combo.setCurrentIndex(index)
                return

    def _get_all_ordered_preset_files(self):
        files = sorted(PRESETS_DIR.glob('*.json'), key=lambda p: p.name.lower())
        order = [str(x) for x in self.config.get('preset_order', []) if str(x).strip()]
        if not order:
            return files
        by_stem = {fp.stem: fp for fp in files}
        ordered = [by_stem[s] for s in order if s in by_stem]
        ordered.extend([fp for fp in files if fp.stem not in order])
        return ordered

    def _get_ordered_preset_files(self, category=None):
        normalized_category = self._normalize_preset_category(category)
        files = self._get_all_ordered_preset_files()
        if normalized_category == PRESET_CATEGORY_ALL:
            return files
        return [fp for fp in files if self._get_preset_category_for_file(fp) == normalized_category]

    def _save_preset_order(self, stems, category=None):
        requested = [str(s) for s in stems if str(s).strip()]
        current_all = [fp.stem for fp in self._get_all_ordered_preset_files()]
        normalized_category = self._normalize_preset_category(category)
        if normalized_category == PRESET_CATEGORY_ALL:
            new_order = requested + [stem for stem in current_all if stem not in requested]
        else:
            visible_stems = [fp.stem for fp in self._get_ordered_preset_files(normalized_category)]
            requested_visible = [stem for stem in requested if stem in visible_stems]
            visible_iter = iter(requested_visible)
            new_order = []
            for stem in current_all:
                if stem in visible_stems:
                    new_order.append(next(visible_iter, stem))
                else:
                    new_order.append(stem)
        self.config['preset_order'] = new_order
        self._schedule_config_commit()

    def _refresh_preset_list(self):
        self._ensure_presets_dir()
        current_fp = self.preset_combo.currentData()
        category = self._get_selected_preset_category()
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        invalid_files = []
        files = []
        for fp in self._get_ordered_preset_files(category):
            error = self._validate_preset_file(fp)
            if error:
                invalid_files.append((fp, error))
                continue
            files.append(fp)
        selected_idx = -1
        for fp in files:
            self.preset_combo.addItem(self._get_preset_display_name(fp, category), str(fp))
            if current_fp and str(fp) == str(current_fp):
                selected_idx = self.preset_combo.count() - 1
        # 若当前无选中，尝试恢复上次使用的预设
        if selected_idx < 0 and not current_fp:
            last_stem = self.config.get('last_preset', '')
            if last_stem:
                for i in range(self.preset_combo.count()):
                    if Path(self.preset_combo.itemData(i)).stem == last_stem:
                        selected_idx = i
                        break
        normalized_order = [fp.stem for fp in self._get_all_ordered_preset_files()]
        if normalized_order != self.config.get('preset_order', []):
            self.config['preset_order'] = normalized_order
            self._schedule_config_commit()
        if selected_idx >= 0:
            self.preset_combo.setCurrentIndex(selected_idx)
        elif self.preset_combo.count() > 0:
            self.preset_combo.setCurrentIndex(0)
        self.preset_combo.blockSignals(False)
        self._update_preset_preview()
        self._refresh_unity_export_suggestion()
        if invalid_files:
            preview_names = '、'.join(fp.stem for fp, _error in invalid_files[:3])
            if len(invalid_files) > 3:
                preview_names += ' 等'
            self._set_info_bar(f"已跳过 {len(invalid_files)} 个无效预设: {preview_names}")

    def _sync_preset_combo_from(self, source: str):
        return

    def _update_preset_preview(self):
        return

    def _load_preset_config(self, fp):
        preset_path = Path(fp)
        with open(preset_path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            raise ValueError('预设根节点必须是 JSON 对象')
        return _normalize_loaded_config(self._inflate_loaded_preset_data(raw))

    def _validate_preset_file(self, fp):
        try:
            self._load_preset_config(fp)
            return None
        except Exception as e:
            return str(e)

    def _switch_preset_by_offset(self, step, *, update_info=False):
        count = self.preset_combo.count()
        if count <= 0:
            if update_info:
                self._set_info_bar('当前没有可切换的预设')
            return False
        current = self.preset_combo.currentIndex()
        if current < 0:
            target = 0 if step >= 0 else count - 1
        else:
            target = (current + int(step)) % count
        if target == current:
            if update_info:
                self._set_info_bar(f"当前预设: {self.preset_combo.currentText()}")
            return False
        self.preset_combo.setCurrentIndex(target)
        if update_info:
            self._set_info_bar(f"已切换到预设: {self.preset_combo.currentText()}")
        return True

    def _switch_preset_random(self, *, update_info=False):
        count = self.preset_combo.count()
        if count <= 0:
            if update_info:
                self._set_info_bar('当前没有可切换的预设')
            return False
        current = self.preset_combo.currentIndex()
        if count == 1:
            if current < 0:
                self.preset_combo.setCurrentIndex(0)
                return True
            if update_info:
                self._set_info_bar(f"当前预设: {self.preset_combo.currentText()}")
            return False
        choices = [index for index in range(count) if index != current]
        if not choices:
            return False
        target = random.choice(choices)
        self.preset_combo.setCurrentIndex(target)
        if update_info:
            self._set_info_bar(f"已随机切换到预设: {self.preset_combo.currentText()}")
        return True

    def _set_info_bar(self, text: str):
        self.info_bar_lbl.setText(text)

    def _open_preset_manager(self):
        self._ensure_presets_dir()

        dlg = QDialog(self)
        dlg.setWindowTitle("预设快速管理")
        dlg.resize(420, 360)
        root = QVBoxLayout(dlg)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        lw = QListWidget()
        root.addWidget(lw, 1)

        def _reload_list(select_stem=None):
            lw.clear()
            for fp in self._get_all_ordered_preset_files():
                lw.addItem(fp.stem)
            if lw.count() == 0:
                return
            idx = 0
            if select_stem:
                for i in range(lw.count()):
                    if lw.item(i).text() == select_stem:
                        idx = i
                        break
            lw.setCurrentRow(idx)

        def _save_order_from_list():
            stems = [lw.item(i).text() for i in range(lw.count())]
            self._save_preset_order(stems)
            self._refresh_preset_list()

        def _move(delta):
            row = lw.currentRow()
            if row < 0:
                return
            target = row + delta
            if target < 0 or target >= lw.count():
                return
            item = lw.takeItem(row)
            lw.insertItem(target, item)
            lw.setCurrentRow(target)
            _save_order_from_list()

        btn_row = QHBoxLayout(); btn_row.setSpacing(6)
        b_up = QPushButton("上移")
        b_up.clicked.connect(lambda: _move(-1))
        btn_row.addWidget(b_up)
        b_down = QPushButton("下移")
        b_down.clicked.connect(lambda: _move(1))
        btn_row.addWidget(b_down)

        b_rename = QPushButton("重命名")
        def _rename():
            row = lw.currentRow()
            if row < 0:
                return
            old_stem = lw.item(row).text()
            new_name, ok = QInputDialog.getText(dlg, "重命名预设", "新名称:", text=old_stem)
            if not ok:
                return
            safe = self._safe_preset_name(new_name)
            if not safe:
                QMessageBox.warning(dlg, "无效名称", "预设名称不能为空或仅包含非法字符")
                return
            old_fp = PRESETS_DIR / f"{old_stem}.json"
            new_fp = PRESETS_DIR / f"{safe}.json"
            if not old_fp.exists():
                QMessageBox.warning(dlg, "失败", "原预设文件不存在")
                _reload_list()
                return
            if new_fp.exists() and new_fp != old_fp:
                QMessageBox.warning(dlg, "失败", "目标名称已存在")
                return
            try:
                old_fp.rename(new_fp)
                stems = [lw.item(i).text() for i in range(lw.count())]
                stems[row] = safe
                self._save_preset_order(stems)
                self._refresh_preset_list()
                _reload_list(select_stem=safe)
            except Exception as e:
                QMessageBox.critical(dlg, "错误", f"重命名失败: {e}")

        b_rename.clicked.connect(_rename)
        btn_row.addWidget(b_rename)

        b_delete = QPushButton("删除")
        def _delete():
            row = lw.currentRow()
            if row < 0:
                return
            stem = lw.item(row).text()
            if QMessageBox.question(dlg, "确认删除", f"确定删除预设 {stem} 吗？",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
                return
            fp = PRESETS_DIR / f"{stem}.json"
            try:
                if fp.exists():
                    fp.unlink()
                stems = [lw.item(i).text() for i in range(lw.count()) if i != row]
                self._save_preset_order(stems)
                self._refresh_preset_list()
                _reload_list()
            except Exception as e:
                QMessageBox.critical(dlg, "错误", f"删除失败: {e}")

        b_delete.clicked.connect(_delete)
        btn_row.addWidget(b_delete)
        btn_row.addStretch()
        root.addLayout(btn_row)

        close_row = QHBoxLayout()
        close_row.addStretch()
        b_close = QPushButton("关闭")
        b_close.clicked.connect(dlg.accept)
        close_row.addWidget(b_close)
        root.addLayout(close_row)

        _reload_list()
        dlg.exec()

    def _on_preset_changed(self, _idx):
        self._load_selected_preset(show_message=False)

    def _on_preset_category_changed(self, _idx):
        self._refresh_preset_list()

    def _on_preset_auto_toggled(self, v):
        self._update_cfg('preset_auto_switch', v)
        if v:
            self._schedule_next_preset_switch()
        else:
            self.preset_timer.stop()

    def _on_preset_switch_random_toggled(self, v):
        self._update_cfg('preset_switch_random_enabled', v)
        if v and getattr(self, 'preset_switch_infinite_random_check', None) and self.preset_switch_infinite_random_check.isChecked():
            self.preset_switch_infinite_random_check.blockSignals(True)
            self.preset_switch_infinite_random_check.setChecked(False)
            self.preset_switch_infinite_random_check.blockSignals(False)
            self._update_cfg('preset_switch_infinite_random_enabled', False)

    def _on_preset_switch_infinite_random_toggled(self, v):
        self._update_cfg('preset_switch_infinite_random_enabled', v)
        if v and getattr(self, 'preset_switch_random_check', None) and self.preset_switch_random_check.isChecked():
            self.preset_switch_random_check.blockSignals(True)
            self.preset_switch_random_check.setChecked(False)
            self.preset_switch_random_check.blockSignals(False)
            self._update_cfg('preset_switch_random_enabled', False)

    def _on_preset_interval_changed(self, v):
        self._update_cfg('preset_switch_interval', v)
        if not self.preset_interval_random_check.isChecked() and self.preset_auto_check.isChecked():
            self._schedule_next_preset_switch()

    def _on_preset_interval_random_toggled(self, v):
        self._update_cfg('preset_interval_random_enabled', v)
        self._update_preset_interval_mode_ui()
        if self.preset_auto_check.isChecked():
            self._schedule_next_preset_switch()

    def _on_preset_interval_min_changed(self, v):
        max_v = self.preset_interval_max_spin.value()
        if v > max_v:
            self.preset_interval_max_spin.blockSignals(True)
            self.preset_interval_max_spin.setValue(v)
            self.preset_interval_max_spin.blockSignals(False)
            max_v = v
            self._update_cfg('preset_switch_interval_max', max_v)
        self._update_cfg('preset_switch_interval_min', v)
        if self.preset_interval_random_check.isChecked() and self.preset_auto_check.isChecked():
            self._schedule_next_preset_switch()

    def _on_preset_interval_max_changed(self, v):
        min_v = self.preset_interval_min_spin.value()
        if v < min_v:
            self.preset_interval_min_spin.blockSignals(True)
            self.preset_interval_min_spin.setValue(v)
            self.preset_interval_min_spin.blockSignals(False)
            min_v = v
            self._update_cfg('preset_switch_interval_min', min_v)
        self._update_cfg('preset_switch_interval_max', v)
        if self.preset_interval_random_check.isChecked() and self.preset_auto_check.isChecked():
            self._schedule_next_preset_switch()

    def _update_preset_interval_mode_ui(self):
        random_mode = self.preset_interval_random_check.isChecked()
        self.preset_interval_spin.setEnabled(not random_mode)
        self.preset_interval_min_spin.setEnabled(random_mode)
        self.preset_interval_max_spin.setEnabled(random_mode)

    def _next_preset_interval_seconds(self):
        if self.preset_interval_random_check.isChecked():
            low = min(self.preset_interval_min_spin.value(), self.preset_interval_max_spin.value())
            high = max(self.preset_interval_min_spin.value(), self.preset_interval_max_spin.value())
            return random.uniform(low, high)
        return self.preset_interval_spin.value()

    def _schedule_next_preset_switch(self):
        sec = max(0.01, float(self._next_preset_interval_seconds()))
        self.preset_timer.start(int(sec * 1000))

    def _auto_switch_infinite_random(self):
        if not hasattr(self, 'random_tree'):
            return False

        checked_count = 0
        for i in range(self.random_tree.topLevelItemCount()):
            cat_item = self.random_tree.topLevelItem(i)
            for j in range(cat_item.childCount()):
                child = cat_item.child(j)
                if child.checkState(0) == Qt.Checked:
                    checked_count += 1

        if checked_count <= 0:
            self._set_info_bar('无限随机未执行：请先在随机页勾选要参与随机的项目')
            return False

        self._randomize_selected(use_transition=True)
        self._set_info_bar('已按当前随机设置生成新的随机预设状态')
        return True

    def _auto_switch_preset(self):
        if self.config.get('preset_switch_infinite_random_enabled', False):
            self._auto_switch_infinite_random()
        elif self.config.get('preset_switch_random_enabled', False):
            self._switch_preset_random()
        else:
            self._switch_preset_by_offset(1)
        if self.preset_auto_check.isChecked():
            self._schedule_next_preset_switch()

    def _save_preset_as(self):
        name, ok = QInputDialog.getText(self, "保存预设", "请输入预设名称:")
        if not ok:
            return
        safe_name = self._safe_preset_name(name)
        if not safe_name:
            QMessageBox.warning(self, "无效名称", "预设名称不能为空或仅包含非法字符")
            return

        self._ensure_presets_dir()
        fp = PRESETS_DIR / f"{safe_name}.json"
        if fp.exists():
            if QMessageBox.question(
                self,
                "覆盖确认",
                f"预设 {safe_name} 已存在，是否覆盖？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            ) != QMessageBox.Yes:
                return

        try:
            self._write_preset_file(fp)
            self._refresh_preset_list()
            self._select_preset_by_path(fp)
            QMessageBox.information(self, "成功", f"预设已保存: {safe_name}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存预设失败: {e}")

    def _save_current_preset(self):
        fp = self.preset_combo.currentData() if hasattr(self, 'preset_combo') else None
        if not fp:
            self._save_preset_as()
            return

        target = Path(fp)
        stem = target.stem
        if QMessageBox.question(
            self,
            "覆盖保存当前预设",
            f"确定用当前参数覆盖保存预设 {stem} 吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        ) != QMessageBox.Yes:
            return

        try:
            self._write_preset_file(target)
            self._refresh_preset_list()
            self._select_preset_by_path(target)
            self._set_info_bar(f"已覆盖保存当前预设: {stem}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"覆盖保存预设失败: {e}")

    def _rename_current_preset(self):
        fp = self.preset_combo.currentData()
        if not fp:
            QMessageBox.warning(self, "提示", "当前没有可重命名的预设")
            return

        old_fp = Path(fp)
        old_stem = old_fp.stem
        new_name, ok = QInputDialog.getText(self, "重命名预设", "新名称:", text=old_stem)
        if not ok:
            return

        safe_name = self._safe_preset_name(new_name)
        if not safe_name:
            QMessageBox.warning(self, "无效名称", "预设名称不能为空或仅包含非法字符")
            return
        if safe_name == old_stem:
            return

        self._ensure_presets_dir()
        new_fp = PRESETS_DIR / f"{safe_name}.json"
        if not old_fp.exists():
            QMessageBox.warning(self, "失败", "原预设文件不存在")
            self._refresh_preset_list()
            return
        if new_fp.exists() and new_fp != old_fp:
            QMessageBox.warning(self, "失败", "目标名称已存在")
            return

        try:
            old_fp.rename(new_fp)
            self.config['preset_order'] = [
                safe_name if s == old_stem else s
                for s in self.config.get('preset_order', [])
            ]
            self._schedule_config_commit()
            self._refresh_preset_list()
            self._select_preset_by_path(new_fp)
            self._set_info_bar(f"已重命名预设: {old_stem} → {safe_name}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"重命名预设失败: {e}")

    def _delete_current_preset(self):
        fp = self.preset_combo.currentData()
        if not fp:
            QMessageBox.warning(self, "提示", "当前没有可删除的预设")
            return

        stem = Path(fp).stem
        if QMessageBox.question(
            self,
            "确认删除",
            f"确定删除当前预设 {stem} 吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) != QMessageBox.Yes:
            return

        try:
            p = Path(fp)
            if p.exists():
                p.unlink()
            self.config['preset_order'] = [s for s in self.config.get('preset_order', []) if s != stem]
            self._schedule_config_commit()
            self._refresh_preset_list()
            self._set_info_bar(f"已删除预设: {stem}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"删除预设失败: {e}")

    def _load_selected_preset(self, show_message=False):
        fp = self.preset_combo.currentData()
        if not fp:
            return
        try:
            from_config = self.config.copy()
            cfg = self._load_preset_config(fp)
            # 保留运行态设置，不被预设覆盖
            runtime_keep_keys = (
                'pos_x', 'pos_y',
                'random_checked',
                'random_object_count_min',
                'random_object_count_max',
                'preset_order',
                'preset_auto_switch',
                'preset_switch_random_enabled',
                'preset_switch_infinite_random_enabled',
                'preset_switch_interval',
                'preset_interval_random_enabled',
                'preset_switch_interval_min',
                'preset_switch_interval_max',
                'preset_transition_enabled',
                'preset_transition_duration',
                'preset_transition_easing',
            )
            for key in runtime_keep_keys:
                cfg[key] = self.config.get(key, cfg.get(key))
            self._apply_config_to_ui(cfg)
            self.config['last_preset'] = Path(fp).stem
            self._schedule_config_commit()
            # 若启用平滑过渡，替换队列为过渡指令
            if self.config.get('preset_transition_enabled', False) and self.viz_process and self.viz_process.is_alive():
                self._send_transition_command(from_config)
                # 取消即将触发的 _send_config，否则它会覆盖过渡指令并中断过渡
                self.cfg_send_timer.stop()
            self._set_info_bar(f"已加载预设: {Path(fp).stem}")
            self._refresh_unity_export_suggestion()
            if show_message:
                QMessageBox.information(self, "成功", f"已加载预设: {Path(fp).stem}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载预设失败: {e}")

    def _get_current_preset_name(self):
        fp = self.preset_combo.currentData() if hasattr(self, 'preset_combo') else None
        return Path(fp).stem if fp else 'CurrentPreset'

    def _refresh_unity_export_suggestion(self):
        if not hasattr(self, 'unity_export_class_edit'):
            return
        preset_name = self._get_current_preset_name()
        last_auto_class = self._unity_export_auto_class_name
        current_class = self.unity_export_class_edit.text().strip()
        suggested_class = sanitize_csharp_identifier(preset_name, fallback='AyeExportedPresetEffect')
        if not current_class or current_class == last_auto_class:
            self.unity_export_class_edit.blockSignals(True)
            self.unity_export_class_edit.setText(suggested_class)
            self.unity_export_class_edit.blockSignals(False)
            current_class = suggested_class
        self._unity_export_auto_class_name = suggested_class

        project_dir = normalize_unity_project_dir(
            project_dir=self.config.get('unity_export_project_dir'),
            last_path=self.config.get('unity_export_last_path'),
        )
        project_dir_text = str(project_dir) if project_dir else ''
        current_path = self.unity_export_path_edit.text().strip()
        suggested_path = suggest_export_path(
            preset_name,
            current_class or suggested_class,
            project_dir=project_dir_text,
            last_path=self.config.get('unity_export_last_path'),
        )
        if not current_path or current_path == self._unity_export_auto_path:
            self.unity_export_path_edit.setText(project_dir_text)
            current_path = project_dir_text
        self._unity_export_auto_path = project_dir_text

        self.unity_export_preset_value.setText(preset_name)
        self.unity_export_tip_label.setText(
            f"输出为单个固定参数的 Unity 组件脚本，不包含 UI、预设管理或运行时调节面板。\n目标文件: {suggested_path}"
        )

    def _on_unity_export_class_changed(self, text):
        clean_name = sanitize_csharp_identifier(text or self._get_current_preset_name(), fallback='AyeExportedPresetEffect')
        previous_auto_path = self._unity_export_auto_path
        current_path = self.unity_export_path_edit.text().strip() if hasattr(self, 'unity_export_path_edit') else ''
        project_dir = normalize_unity_project_dir(
            project_dir=current_path or self.config.get('unity_export_project_dir'),
            last_path=self.config.get('unity_export_last_path'),
        )
        suggested_path = suggest_export_path(
            self._get_current_preset_name(),
            clean_name,
            project_dir=str(project_dir) if project_dir else None,
            last_path=self.config.get('unity_export_last_path'),
        )
        self._unity_export_auto_class_name = clean_name
        self._unity_export_auto_path = str(project_dir) if project_dir else ''
        if current_path == previous_auto_path or not current_path:
            self.unity_export_path_edit.setText(self._unity_export_auto_path)
        self.unity_export_tip_label.setText(
            f"输出为单个固定参数的 Unity 组件脚本，不包含 UI、预设管理或运行时调节面板。\n目标文件: {suggested_path}"
        )

    def _browse_unity_export_path(self):
        initial_dir = normalize_unity_project_dir(
            project_dir=self.unity_export_path_edit.text().strip() or self.config.get('unity_export_project_dir'),
            last_path=self.config.get('unity_export_last_path'),
        )
        selected = QFileDialog.getExistingDirectory(
            self,
            '选择 Unity 项目文件夹',
            str(initial_dir) if initial_dir else '',
        )
        if not selected:
            return
        self.unity_export_path_edit.setText(selected)
        self.config['unity_export_project_dir'] = selected
        self._schedule_config_commit()
        self._refresh_unity_export_suggestion()

    def _export_current_preset_to_unity(self):
        if QApplication.keyboardModifiers() & Qt.ControlModifier:
            self._export_all_presets_to_unity()
            return
        preset_name = self._get_current_preset_name()
        class_name = sanitize_csharp_identifier(
            self.unity_export_class_edit.text().strip() or preset_name,
            fallback='AyeExportedPresetEffect'
        )
        if self.unity_export_class_edit.text().strip() != class_name:
            self.unity_export_class_edit.blockSignals(True)
            self.unity_export_class_edit.setText(class_name)
            self.unity_export_class_edit.blockSignals(False)
        project_dir = normalize_unity_project_dir(
            project_dir=self.unity_export_path_edit.text().strip() or self.config.get('unity_export_project_dir'),
            last_path=self.config.get('unity_export_last_path'),
        )
        if not project_dir:
            QMessageBox.warning(self, '提示', '请先选择 Unity 项目文件夹')
            return
        output_path = build_unity_export_path(project_dir, class_name)
        self.unity_export_path_edit.setText(str(project_dir))

        target = Path(output_path)
        if target.exists():
            if QMessageBox.question(
                self,
                '覆盖确认',
                f'文件已存在，是否覆盖？\n{target}',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            ) != QMessageBox.Yes:
                return

        try:
            exported = export_unity_component(
                dict(self.config),
                preset_name=preset_name,
                output_path=target,
                class_name=class_name,
            )
        except Exception as e:
            QMessageBox.critical(self, '错误', f'导出 Unity 组件失败: {e}')
            return

        self.config['unity_export_last_class'] = class_name
        self.config['unity_export_project_dir'] = str(project_dir)
        self.config['unity_export_last_path'] = str(exported)
        self._schedule_config_commit()
        self._refresh_unity_export_suggestion()
        self._set_info_bar(f'Unity 组件已导出: {exported.name}')
        prerequisite_paths = list_unity_shared_prerequisite_paths(project_dir)
        prerequisite_names = '、'.join(path.name for path in prerequisite_paths) if prerequisite_paths else '无'
        QMessageBox.information(
            self,
            '导出完成',
            f'已导出当前预设为 Unity 组件脚本:\n{exported}\n\n'
            f'导出前已自动检测并按需生成共享先决组件:\n{prerequisite_names}\n\n'
            '其中会复用或生成 P01 运行时链路需要的共享脚本，例如 PyStyleVisualizer、WindowsAudioCapture、音频文件驱动和相机控制器。',
        )

    def _export_all_presets_to_unity(self):
        project_dir = normalize_unity_project_dir(
            project_dir=self.unity_export_path_edit.text().strip() or self.config.get('unity_export_project_dir'),
            last_path=self.config.get('unity_export_last_path'),
        )
        if not project_dir:
            QMessageBox.warning(self, '提示', '请先选择 Unity 项目文件夹')
            return
        preset_files = sorted(PRESETS_DIR.glob('*.json'), key=lambda p: p.name.lower())
        if not preset_files:
            QMessageBox.information(self, '提示', '没有找到预设文件')
            return
        existing = []
        for fp in preset_files:
            class_name = sanitize_csharp_identifier(fp.stem, fallback='AyeExportedPresetEffect')
            out = build_unity_export_path(project_dir, class_name)
            if out and Path(out).exists():
                existing.append(fp.stem)
        if existing:
            overlap_list = '\n'.join(existing[:10]) + ('\n...' if len(existing) > 10 else '')
            confirm_msg = (
                f'即将导出 {len(preset_files)} 个预设到:\n{project_dir}\n\n'
                f'以下 {len(existing)} 个文件已存在将被覆盖:\n{overlap_list}\n\n是否继续？'
            )
        else:
            confirm_msg = f'即将导出 {len(preset_files)} 个预设到:\n{project_dir}\n\n是否继续？'
        if QMessageBox.question(
            self, '批量导出确认', confirm_msg,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        succeeded = []
        failed = []
        base_config = dict(self.config)
        for fp in preset_files:
            try:
                preset_cfg = self._load_preset_config(fp)
                merged_cfg = {**base_config, **preset_cfg}
                preset_name = fp.stem
                class_name = sanitize_csharp_identifier(preset_name, fallback='AyeExportedPresetEffect')
                out_path = build_unity_export_path(project_dir, class_name)
                export_unity_component(
                    merged_cfg,
                    preset_name=preset_name,
                    output_path=out_path,
                    class_name=class_name,
                )
                succeeded.append(class_name)
            except Exception as e:
                failed.append(f'{fp.stem}: {e}')
        self.config['unity_export_project_dir'] = str(project_dir)
        self.unity_export_path_edit.setText(str(project_dir))
        self._schedule_config_commit()
        info = f'批量导出完成: {len(succeeded)} 成功' + (f', {len(failed)} 失败' if failed else '')
        self._set_info_bar(info)
        detail = f'已导出 {len(succeeded)} 个预设到:\n{project_dir}'
        if failed:
            detail += '\n\n以下预设导出失败:\n' + '\n'.join(failed)
        QMessageBox.information(self, '批量导出完成', detail)

    # ── 镜头划痕眩光 ──────────────────────────────────────────────────────────

    def _build_lens_scratch_section(self):
        s = _Collapsible('镜头划痕眩光', expanded=True)
        g = QGridLayout(); g.setSpacing(3); g.setContentsMargins(0, 0, 0, 0); r = 0

        # 启用开关
        en_check = QCheckBox('启用镜头划痕眩光效果')
        en_check.setChecked(bool(self.config.get('lens_scratch_enabled', False)))
        en_check.toggled.connect(lambda v: self._update_cfg('lens_scratch_enabled', bool(v)))
        self.lens_scratch_enabled_check = en_check
        g.addWidget(en_check, r, 0, 1, 4); r += 1

        note = QLabel('Windows 上使用 QPainter 模式渲染划痕叠加，非 Windows 使用 OpenGL 后处理。\n'
                      '不加载贴图时使用内置程序化划痕。')
        note.setStyleSheet('color:#888; font-size:8pt;')
        note.setWordWrap(True)
        g.addWidget(note, r, 0, 1, 4); r += 1

        # ── 划痕贴图 ──────────────────────────────────────────────────────────
        g.addWidget(self._make_section_label('划痕贴图'), r, 0, 1, 4); r += 1

        def _path_row(label_text, cfg_key, attr_name):
            nonlocal r
            row = QWidget(); hl = QHBoxLayout(row); hl.setContentsMargins(0, 0, 0, 0); hl.setSpacing(4)
            hl.addWidget(QLabel(label_text))
            edit = QLineEdit(str(self.config.get(cfg_key, '')))
            edit.setPlaceholderText('留空使用内置贴图…')
            edit.setReadOnly(True)
            edit.textChanged.connect(lambda v: self._update_cfg(cfg_key, v))
            setattr(self, attr_name, edit)
            hl.addWidget(edit, 1)
            btn = QPushButton('…')
            btn.setFixedWidth(28)
            def _pick(_=None, _cfg_key=cfg_key, _edit=edit):
                p, _ = QFileDialog.getOpenFileName(self, '选择贴图', '', '图像文件 (*.png *.jpg *.bmp *.tga *.exr *.hdr);;全部(*)')
                if p:
                    _edit.setText(p)
                    self._update_cfg(_cfg_key, p)
            btn.clicked.connect(_pick)
            clr_btn = QPushButton('✕')
            clr_btn.setFixedWidth(24)
            def _clear(_=None, _cfg_key=cfg_key, _edit=edit):
                _edit.setText('')
                self._update_cfg(_cfg_key, '')
            clr_btn.clicked.connect(_clear)
            hl.addWidget(btn); hl.addWidget(clr_btn)
            g.addWidget(row, r, 0, 1, 4); r += 1

        _path_row('遮罩贴图:', 'lens_scratch_mask_path', 'lens_scratch_mask_edit')
        _path_row('法线贴图:', 'lens_scratch_normal_path', 'lens_scratch_normal_edit')

        # 平铺 / 偏移
        def _float_row(label_text, cfg_key, default_v, s_min, s_max, h_min, h_max, dec=2):
            nonlocal r
            slider, box = self._new_bound_float_slider(
                cfg_key=cfg_key, default_value=default_v,
                soft_min=s_min, soft_max=s_max, hard_min=h_min, hard_max=h_max,
                slider_scale=100, step=0.01, decimals=dec, width=72,
            )
            g.addWidget(self._make_graphics_form_row(label_text=label_text, widgets=[slider, box], label_width=96), r, 0, 1, 4); r += 1
            return slider, box

        _float_row('平铺 X:', 'lens_scratch_tiling_x', 1.0, 0.1, 4.0, 0.01, 20.0)
        _float_row('平铺 Y:', 'lens_scratch_tiling_y', 1.0, 0.1, 4.0, 0.01, 20.0)
        _float_row('偏移 X:', 'lens_scratch_offset_x', 0.0, -1.0, 1.0, -10.0, 10.0)
        _float_row('偏移 Y:', 'lens_scratch_offset_y', 0.0, -1.0, 1.0, -10.0, 10.0)
        _float_row('旋转角度(°):', 'lens_scratch_rotation_deg', 0.0, -180.0, 180.0, -360.0, 360.0, dec=1)
        _float_row('遮罩幂次:', 'lens_scratch_mask_power', 1.35, 0.0, 4.0, 0.0, 20.0)
        _float_row('法线影响:', 'lens_scratch_normal_influence', 1.2, 0.0, 4.0, 0.0, 20.0)

        # ── 溢光 ──────────────────────────────────────────────────────────────
        g.addWidget(self._make_section_label('溢光'), r, 0, 1, 4); r += 1

        r, _, _, _ = self._add_kp_slider_row(
            g, r, label_text='高光阈值:', cfg_key='lens_scratch_threshold',
            default_value=1.1, soft_min=0.0, soft_max=4.0, hard_min=0.0, hard_max=8.0,
            supports=('k',), decimals=3, kp_soft_min=-2.0, kp_soft_max=2.0,
            kp_hard_min=-8.0, kp_hard_max=8.0, kp_decimals=3,
        )
        _float_row('柔和过渡:', 'lens_scratch_soft_knee', 0.45, 0.0, 2.0, 0.0, 5.0)

        r, _, _, _ = self._add_kp_slider_row(
            g, r, label_text='眩光强度:', cfg_key='lens_scratch_glare_intensity',
            default_value=1.15, soft_min=0.0, soft_max=4.0, hard_min=0.0, hard_max=8.0,
            supports=('k',), decimals=3, kp_soft_min=-2.0, kp_soft_max=2.0,
            kp_hard_min=-8.0, kp_hard_max=8.0, kp_decimals=3,
        )

        # 采样密度
        count_a_box = self._new_int_box(
            default_value=20, soft_min=2, soft_max=64, hard_min=2, hard_max=128, step=1,
            cfg_key='lens_scratch_count_a',
        )
        g.addWidget(self._make_graphics_form_row(label_text='采样密度:', widgets=[count_a_box], label_width=96), r, 0, 1, 4); r += 1

        scratch_count_box = self._new_int_box(
            default_value=3, soft_min=1, soft_max=16, hard_min=1, hard_max=32, step=1,
            cfg_key='lens_scratch_scratch_count',
        )
        g.addWidget(self._make_graphics_form_row(label_text='划痕层数:', widgets=[scratch_count_box], label_width=96), r, 0, 1, 4); r += 1

        streak_count_box = self._new_int_box(
            default_value=3, soft_min=1, soft_max=16, hard_min=1, hard_max=32, step=1,
            cfg_key='lens_scratch_streak_count',
        )
        g.addWidget(self._make_graphics_form_row(label_text='条纹层数:', widgets=[streak_count_box], label_width=96), r, 0, 1, 4); r += 1

        r, _, _, _ = self._add_kp_slider_row(
            g, r, label_text='条纹长度:', cfg_key='lens_scratch_streak_length',
            default_value=3.6, soft_min=0.0, soft_max=20.0, hard_min=0.0, hard_max=100.0,
            supports=('k',), slider_scale=100, decimals=2, kp_soft_min=-5.0, kp_soft_max=5.0,
            kp_hard_min=-100.0, kp_hard_max=100.0, kp_decimals=3,
        )
        _float_row('条纹扩散:', 'lens_scratch_streak_spread', 1.1, 0.0, 5.0, 0.0, 20.0)
        _float_row('衰减 A:', 'lens_scratch_falloff_a', 3.8, 0.0, 20.0, 0.0, 100.0)
        _float_row('衰减 B:', 'lens_scratch_falloff_b', 0.35, 0.0, 5.0, 0.0, 20.0)
        _float_row('角度抖动(°):', 'lens_scratch_rotation_jitter_deg', 6.0, 0.0, 90.0, 0.0, 360.0, dec=1)

        # ── 折射 ──────────────────────────────────────────────────────────────
        g.addWidget(self._make_section_label('折射'), r, 0, 1, 4); r += 1

        r, _, _, _ = self._add_kp_slider_row(
            g, r, label_text='折射强度:', cfg_key='lens_scratch_refraction_strength',
            default_value=0.18, soft_min=0.0, soft_max=2.0, hard_min=0.0, hard_max=5.0,
            supports=('k',), slider_scale=100, decimals=3, kp_soft_min=-1.0, kp_soft_max=1.0,
            kp_hard_min=-5.0, kp_hard_max=5.0, kp_decimals=4,
        )
        r, _, _, _ = self._add_kp_slider_row(
            g, r, label_text='色差:', cfg_key='lens_scratch_chromatic_aberration',
            default_value=0.0025, soft_min=0.0, soft_max=0.02, hard_min=0.0, hard_max=0.1,
            supports=('k',), slider_scale=10000, step=0.0001, decimals=4,
            kp_soft_min=-0.01, kp_soft_max=0.01, kp_hard_min=-0.1, kp_hard_max=0.1, kp_decimals=5,
        )
        _float_row('微扰动:', 'lens_scratch_micro_distortion', 0.55, 0.0, 2.0, 0.0, 5.0)

        # ── 颜色 ──────────────────────────────────────────────────────────────
        g.addWidget(self._make_section_label('眩光颜色'), r, 0, 1, 4); r += 1

        tint_btn = QPushButton()
        tint_btn.setFixedSize(22, 22)
        cur_tint = (
            int(self.config.get('lens_scratch_tint_r', 255)),
            int(self.config.get('lens_scratch_tint_g', 255)),
            int(self.config.get('lens_scratch_tint_b', 255)),
        )
        tint_btn.setStyleSheet(self._make_color_button_style(cur_tint))
        self.lens_scratch_tint_btn = tint_btn

        def _pick_tint():
            cur = (
                int(self.config.get('lens_scratch_tint_r', 255)),
                int(self.config.get('lens_scratch_tint_g', 255)),
                int(self.config.get('lens_scratch_tint_b', 255)),
            )
            picker = QuickColorPicker(self, initial=cur, presets=self._get_designer_palette(12), cfg_key_prefix='lens_scratch_tint')
            def _apply(rgb):
                self.lens_scratch_tint_btn.setStyleSheet(self._make_color_button_style(rgb))
                self._update_cfg('lens_scratch_tint_r', rgb[0])
                self._update_cfg('lens_scratch_tint_g', rgb[1])
                self._update_cfg('lens_scratch_tint_b', rgb[2])
            picker.colorSelected.connect(_apply)
            picker.exec()

        tint_btn.clicked.connect(_pick_tint)
        g.addWidget(self._make_graphics_form_row(label_text='眩光颜色:', widgets=[tint_btn], label_width=96), r, 0, 1, 4); r += 1

        s.add_layout(g)
        return s

    def _make_section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet('font-weight:bold; color:#aaa; margin-top:6px; margin-bottom:2px;')
        return lbl

    def _build_unity_export_section(self):
        s = _Collapsible('导出到Unity', expanded=True)
        v = QVBoxLayout(); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(8)

        title = QLabel('导出当前预设为独立 Unity 组件')
        title.setStyleSheet('font-size:11pt; font-weight:bold;')
        v.addWidget(title)

        desc = QLabel(
            '这里导出的是当前选中预设对应的独立 Unity 单元。\n'
            '会自动复用或生成 P01 的核心运行时脚本，只保留预设画面逻辑，不导出主程序面板和 Unity 侧 UI。'
        )
        desc.setWordWrap(True)
        desc.setStyleSheet('color:#8a93a1;')
        v.addWidget(desc)

        grid = QGridLayout(); grid.setContentsMargins(0, 4, 0, 4); grid.setHorizontalSpacing(8); grid.setVerticalSpacing(8)
        grid.addWidget(QLabel('当前预设'), 0, 0)
        self.unity_export_preset_value = QLabel('')
        self.unity_export_preset_value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        grid.addWidget(self.unity_export_preset_value, 0, 1)

        grid.addWidget(QLabel('组件类名'), 1, 0)
        self.unity_export_class_edit = QLineEdit()
        self.unity_export_class_edit.setPlaceholderText('例如 JellyfishPulseEffect')
        self.unity_export_class_edit.textChanged.connect(self._on_unity_export_class_changed)
        grid.addWidget(self.unity_export_class_edit, 1, 1)

        grid.addWidget(QLabel('Unity项目'), 2, 0)
        path_row = QHBoxLayout(); path_row.setSpacing(6)
        self.unity_export_path_edit = QLineEdit()
        self.unity_export_path_edit.setPlaceholderText('选择 Unity 项目根目录')
        path_row.addWidget(self.unity_export_path_edit, 1)
        browse_btn = QPushButton('选择项目...')
        browse_btn.clicked.connect(self._browse_unity_export_path)
        path_row.addWidget(browse_btn)
        grid.addLayout(path_row, 2, 1)
        v.addLayout(grid)

        self.unity_export_tip_label = QLabel('')
        self.unity_export_tip_label.setWordWrap(True)
        self.unity_export_tip_label.setStyleSheet('color:#8a93a1;')
        v.addWidget(self.unity_export_tip_label)

        note = QLabel(
            '导出的脚本会把当前配置直接写死在代码里，Unity 中默认不可调。\n'
            '如果场景里没有明显音频输入，它会自动回退到内置节奏驱动，方便直接预览效果。'
        )
        note.setWordWrap(True)
        note.setStyleSheet('color:#8a93a1;')
        v.addWidget(note)

        actions = QHBoxLayout(); actions.setSpacing(8)
        refresh_btn = QPushButton('刷新建议')
        refresh_btn.clicked.connect(self._refresh_unity_export_suggestion)
        actions.addWidget(refresh_btn)
        export_btn = QPushButton('导出当前预设')
        export_btn.setMinimumHeight(30)
        export_btn.clicked.connect(self._export_current_preset_to_unity)
        actions.addWidget(export_btn)
        actions.addStretch()
        v.addLayout(actions)

        s.add_layout(v)
        QTimer.singleShot(0, self._refresh_unity_export_suggestion)
        return s

    def _send_transition_command(self, from_config):
        if not self.config_queue:
            return
        cmd = {
            'command': 'preset_transition',
            'from_config': {k: v for k, v in from_config.items() if not k.startswith('_tr_')},
            'to_config': {k: v for k, v in self.config.items() if not k.startswith('_tr_')},
            'duration': float(self.config.get('preset_transition_duration', 2.0)),
            'easing': self.config.get('preset_transition_easing', 'ease_in_out'),
        }
        try:
            while True:
                try:
                    self.config_queue.get_nowait()
                except Exception:
                    break
            self.config_queue.put_nowait(cmd)
        except Exception:
            pass

    # ── 颜色 ──────────────────────────────────────────

    def _build_color_section(self):
        s = _Collapsible("颜色方案", expanded=False)
        g = QVBoxLayout(); g.setContentsMargins(0, 0, 0, 0); g.setSpacing(6)
        g.addLayout(self._build_section_action_row('color'))

        hr = QHBoxLayout()
        hr.addWidget(QLabel("方案:"))
        self.color_combo = QComboBox()
        self.color_combo.addItems(["彩虹预设", "火焰预设", "冰冻预设", "霓虹预设", "自定义"])
        schemes = ['rainbow', 'fire', 'ice', 'neon', 'custom']
        cur = self.config.get('color_scheme', 'rainbow')
        self.color_combo.setCurrentIndex(schemes.index(cur) if cur in schemes else 0)
        self.color_combo.currentIndexChanged.connect(self._on_color_scheme_changed)
        hr.addWidget(self.color_combo); hr.addStretch()
        g.addLayout(hr)

        self.color_grp = QWidget()
        cl = QVBoxLayout(self.color_grp); cl.setContentsMargins(0,0,0,0)

        self.grad_check = QCheckBox("启用渐变（关闭=单色）")
        self.grad_check.setChecked(self.config['gradient_enabled'])
        self.grad_check.toggled.connect(lambda v: self._update_cfg('gradient_enabled', v))
        cl.addWidget(self.grad_check)

        gmr = QHBoxLayout()
        gmr.addWidget(QLabel("渐变:"))
        self.grad_mode_combo = QComboBox()
        self.grad_mode_combo.addItems(["频率渐变", "高度渐变"])
        self.grad_mode_combo.setCurrentIndex(0 if self.config['gradient_mode'] == 'frequency' else 1)
        self.grad_mode_combo.currentIndexChanged.connect(lambda i: self._update_cfg('gradient_mode', 'frequency' if i == 0 else 'height'))
        gmr.addWidget(self.grad_mode_combo); gmr.addStretch()
        cl.addLayout(gmr)

        cl.addWidget(QLabel("控制点:"))
        self.gp_container = QWidget()
        self.gp_layout = QVBoxLayout(self.gp_container)
        self.gp_layout.setContentsMargins(10, 0, 0, 0)
        cl.addWidget(self.gp_container)
        self.gp_widgets = []
        self._rebuild_gradient_ui()

        add_btn = QPushButton("➕ 添加控制点")
        add_btn.clicked.connect(self._add_gradient_point)
        cl.addWidget(add_btn)

        self.dyn_check = QCheckBox("动态颜色变化")
        self.dyn_check.setChecked(self.config['color_dynamic'])
        self.dyn_check.toggled.connect(self._on_dynamic_toggled)
        cl.addWidget(self.dyn_check)

        self.dyn_widget = QWidget()
        dl = QGridLayout(self.dyn_widget); dl.setContentsMargins(10,2,0,2)
        dl.addWidget(QLabel("V0:"), 0, 0)
        self.cyc_spd_slider, self.cyc_spd_spin = self._new_bound_float_slider(
            cfg_key='color_cycle_speed', default_value=1.0,
            soft_min=0.0, soft_max=10.0, hard_min=-100.0, hard_max=100.0,
            slider_scale=100, step=0.01, decimals=2, suffix='x'
        )
        dl.addWidget(self.cyc_spd_slider, 0, 1); dl.addWidget(self.cyc_spd_spin, 0, 2)
        dl.addWidget(QLabel("VP:"), 1, 0)
        self.cyc_pow_slider, self.cyc_pow_spin = self._new_bound_float_slider(
            cfg_key='color_cycle_pow', default_value=2.0,
            soft_min=0.01, soft_max=5.0, hard_min=-100.0, hard_max=100.0,
            slider_scale=100, step=0.01, decimals=2
        )
        dl.addWidget(self.cyc_pow_slider, 1, 1); dl.addWidget(self.cyc_pow_spin, 1, 2)
        self.cyc_a1_check = QCheckBox("受P突变加速")
        self.cyc_a1_check.setChecked(self.config['color_cycle_a1'])
        self.cyc_a1_check.toggled.connect(lambda v: self._update_cfg('color_cycle_a1', v))
        dl.addWidget(self.cyc_a1_check, 2, 0, 1, 3)
        cl.addWidget(self.dyn_widget)
        self.dyn_widget.setVisible(self.config['color_dynamic'])

        g.addWidget(self.color_grp)
        self.color_grp.setVisible(cur == 'custom')
        s.add_layout(g)
        return s

    # ── 物理动画 ──────────────────────────────────────────

    def _build_physics_section(self):
        s = _Collapsible("运动表现", expanded=False)
        w = QWidget()
        v = QVBoxLayout(w); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(6)
        v.addLayout(self._build_section_action_row('physics'))

        g = QGridLayout(); g.setSpacing(3); g.setContentsMargins(0,0,0,0); r = 0

        g.addWidget(QLabel("旋转基值:"), r, 0)
        self.rotation_base_spin = self._new_float_box(
            default_value=1.0, soft_min=0.0, soft_max=10.0,
            hard_min=-100.0, hard_max=100.0, step=0.05, decimals=2,
            cfg_key='rotation_base'
        )
        g.addWidget(self.rotation_base_spin, r, 1); r += 1

        g.addWidget(QLabel("主半径缩放:"), r, 0)
        self.main_radius_scale_spin = self._new_float_box(
            default_value=1.0, soft_min=0.1, soft_max=10.0,
            hard_min=-100.0, hard_max=100.0, step=0.05, decimals=2,
            cfg_key='main_radius_scale'
        )
        g.addWidget(self.main_radius_scale_spin, r, 1); r += 1

        g.addWidget(QLabel("默认高度:"), r, 0)
        self.bar_default_height_spin = self._new_float_box(
            default_value=0.0, soft_min=0.0, soft_max=300.0,
            hard_min=-10000.0, hard_max=10000.0, step=0.1, decimals=2,
            cfg_key='bar_default_height'
        )
        g.addWidget(self.bar_default_height_spin, r, 1)
        g.addWidget(QLabel("px"), r, 2)
        r += 1

        g.addWidget(QLabel("内部高度:"), r, 0)
        hh_internal = QHBoxLayout(); hh_internal.setSpacing(4)
        self.bar_internal_min_spin = self._new_float_box(
            default_value=0.0, soft_min=0.0, soft_max=300.0,
            hard_min=-10000.0, hard_max=10000.0, step=0.1, decimals=2,
            cfg_key='bar_internal_min'
        )
        self.bar_internal_max_spin = self._new_float_box(
            default_value=300.0, soft_min=0.0, soft_max=1000.0,
            hard_min=-10000.0, hard_max=10000.0, step=0.1, decimals=2,
            cfg_key='bar_internal_max'
        )
        hh_internal.addWidget(self.bar_internal_min_spin)
        hh_internal.addWidget(QLabel("~"))
        hh_internal.addWidget(self.bar_internal_max_spin)
        hh_internal.addWidget(QLabel("px"))
        g.addLayout(hh_internal, r, 1, 1, 2)
        r += 1

        g.addWidget(QLabel("颜色映射:"), r, 0)
        hh = QHBoxLayout(); hh.setSpacing(4)
        self.hmin_spin = self._new_int_box(
            default_value=0, soft_min=0, soft_max=1000,
            hard_min=-10000, hard_max=10000, step=1, cfg_key='bar_height_min'
        )
        self.hmax_spin = self._new_int_box(
            default_value=500, soft_min=10, soft_max=2000,
            hard_min=-10000, hard_max=10000, step=1, cfg_key='bar_height_max'
        )
        hh.addWidget(self.hmin_spin); hh.addWidget(QLabel("~")); hh.addWidget(self.hmax_spin)
        hh.addWidget(QLabel("px"))
        g.addLayout(hh, r, 1, 1, 2); r += 1

        note = QLabel("K 默认增减阻尼位于顶部 K 预览卡；条形图独立阻尼位于顶部频谱卡；各图元独立阻尼位于“主题设置”树下的对应子主题页。")
        note.setWordWrap(True)
        note.setStyleSheet("color:#8a93a1; font-size:8.5pt;")
        g.addWidget(note, r, 0, 1, 3); r += 1

        v.addLayout(g)
        s.add_widget(w)
        return s

    # ── 窗口行为 ──────────────────────────────────────────

    def _build_window_section(self):
        s = _Collapsible("窗口行为", expanded=True)
        g = QVBoxLayout()
        self.trans_check = QCheckBox("背景透明")
        self.trans_check.setChecked(self.config['bg_transparent'])
        self.trans_check.toggled.connect(lambda v: self._update_cfg('bg_transparent', v))
        g.addWidget(self.trans_check)
        self.top_check = QCheckBox("窗口置顶")
        self.top_check.setChecked(self.config['always_on_top'])
        self.top_check.toggled.connect(lambda v: self._set_window_layer_mode('top' if v else 'normal'))
        g.addWidget(self.top_check)
        s.add_layout(g)
        return s

    def _build_theme_root_section(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        title = QLabel("主题设置")
        title.setStyleSheet("font-size:11pt; font-weight:bold;")
        v.addWidget(title)

        desc = QLabel(
            "当前渲染被拆成两个可混合主题：经典与柔体。\n"
            "经典下再细分为填充子主题和连线子主题，便于分别启用、单独调参，以及各自保存子预设。"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#8a93a1;")
        v.addWidget(desc)

        hint = QLabel(
            "主题启用改为在左侧“主题设置”树形图中完成。\n"
            "各主题行右侧的小复选框表示是否启用，右侧页面仅负责参数调节与子预设管理。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#8a93a1;")
        v.addWidget(hint)

        v.addStretch()
        return w

    def _build_classic_theme_section(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        v.addLayout(self._build_section_action_row('theme_classic_kaleidoscope'))
        info = QLabel('经典主题由轮廓/填充与连线两个子主题组成。轮廓与填充在图层内独立控制，子主题细节请进入下级页面。')
        info.setWordWrap(True)
        info.setStyleSheet('color:#8a93a1;')
        v.addWidget(info)
        v.addStretch()
        return w

    def _build_fill_theme_section(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        v.addLayout(self._build_section_action_row('theme_kaleidoscope_fill'))
        info = QLabel('这里保留轮廓/填充子主题的参数与子预设。每层的“轮廓”和“填充可见”互相独立，不再把“显示”当成总控。')
        info.setWordWrap(True)
        info.setStyleSheet('color:#8a93a1;')
        v.addWidget(info)
        v.addWidget(self._build_contour_section())
        v.addStretch()
        return w

    def _build_line_theme_section(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        v.addLayout(self._build_section_action_row('theme_kaleidoscope_lines'))
        info = QLabel('启用请使用左侧树行右侧的小复选框。这里保留连线子主题的参数与子预设。')
        info.setWordWrap(True)
        info.setStyleSheet('color:#8a93a1;')
        v.addWidget(info)
        v.addWidget(self._build_bars_section())
        v.addStretch()
        return w

    def _build_softbody_theme_section(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        v.addLayout(self._build_section_action_row('theme_softbody'))
        info = QLabel('启用请使用左侧树行右侧的小复选框。这里保留柔体主题的参数与子预设。')
        info.setWordWrap(True)
        info.setStyleSheet('color:#8a93a1;')
        v.addWidget(info)
        v.addWidget(self._build_tentacle_section())
        v.addStretch()
        return w

    def _build_graphics_section(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        v.addWidget(self._build_contour_section())
        v.addWidget(self._build_tentacle_section())
        v.addWidget(self._build_bars_section())
        v.addStretch()
        return w

    def _build_section_action_row(self, section: str):
        row = QHBoxLayout()
        row.setSpacing(8)
        btn_rand = QPushButton("🎲 随机")
        btn_rand.setMinimumHeight(26)
        btn_rand.clicked.connect(lambda: self._randomize_section(section))
        row.addWidget(btn_rand)
        btn_reset = QPushButton("↺ 恢复默认")
        btn_reset.setMinimumHeight(26)
        btn_reset.clicked.connect(lambda: self._reset_section_to_default(section))
        row.addWidget(btn_reset)
        section_label = SECTION_PRESET_LABELS.get(section, self._section_display_name(section))
        preset_suffix = '' if section in {'theme_classic_kaleidoscope', 'theme_kaleidoscope_fill', 'theme_kaleidoscope_lines', 'theme_softbody', 'contour', 'bars', 'tentacle'} else '子预设'
        row.addWidget(QLabel(f"{section_label}{preset_suffix}:"))
        sec_combo = QComboBox()
        sec_combo.setMinimumWidth(150)
        row.addWidget(sec_combo)
        self._section_preset_combos[section] = sec_combo
        btn_save = QPushButton("💾 保存")
        btn_save.setMinimumHeight(26)
        btn_save.clicked.connect(lambda: self._save_section_preset(section))
        row.addWidget(btn_save)
        btn_load = QPushButton("📥 读取")
        btn_load.setMinimumHeight(26)
        btn_load.clicked.connect(lambda: self._load_section_preset(section))
        row.addWidget(btn_load)
        self._refresh_section_preset_combo(section)
        row.addStretch()
        return row

    @staticmethod
    def _section_keys(section: str):
        defaults = _get_defaults()
        contour_keys = [key for key in defaults if re.match(r'^(c[1-5]_|kp_bind_c[1-5]_|kp_c[1-5]_)', key)]
        bar_keys = [key for key in defaults if re.match(r'^(b(?:12|23|34|45)_|kp_bind_b(?:12|23|34|45)_|kp_b(?:12|23|34|45)_)', key)]
        softbody_keys = [
            key for key in defaults
            if key.startswith('tentacle_') or key.startswith('kp_bind_tentacle_') or key.startswith('kp_tentacle_')
        ]
        if section == 'color':
            return [
                'color_scheme', 'gradient_enabled', 'gradient_mode', 'gradient_points',
                'color_dynamic', 'color_cycle_speed', 'color_cycle_pow', 'color_cycle_a1'
            ]
        if section == 'physics':
            return [
                'rotation_base', 'main_radius_scale',
                'circle_a1_rotation', 'circle_a1_radius',
                'radius_damping', 'radius_spring', 'radius_gravity',
                'a1_time_window', 'bar_use_independent_time_window', 'bar_time_window',
                'k_rise_damping', 'k_fall_damping',
                'bar_use_independent_damping', 'bar_independent_rise_damping', 'bar_independent_fall_damping',
                'bar_default_height', 'bar_internal_min', 'bar_internal_max',
                'bar_height_min', 'bar_height_max'
            ]
        if section == 'theme_classic_kaleidoscope':
            return ['contours_enabled', 'bars_enabled'] + contour_keys + bar_keys
        if section == 'theme_kaleidoscope_fill':
            return contour_keys
        if section == 'theme_kaleidoscope_lines':
            return bar_keys
        if section == 'theme_softbody':
            return ['tentacles_enabled'] + softbody_keys
        if section == 'contour':
            return contour_keys
        if section == 'tentacle':
            return softbody_keys
        if section == 'bars':
            return bar_keys
        if section == 'graphics':
            return ['contours_enabled', 'bars_enabled', 'tentacles_enabled'] + contour_keys + bar_keys + softbody_keys
        return []

    def _randomize_section(self, section: str):
        if section == 'theme_classic_kaleidoscope':
            self.config['contours_enabled'] = True
            self.config['bars_enabled'] = True
        elif section == 'theme_softbody':
            self.config['tentacles_enabled'] = True

        if section == 'color':
            palette = self._get_designer_palette(8)
            self.config['color_scheme'] = 'custom'
            self.config['gradient_enabled'] = True
            self.config['gradient_mode'] = random.choice(['frequency', 'height'])
            self.config['color_dynamic'] = random.choice([True, False])
            self.config['color_cycle_speed'] = round(random.uniform(0.2, 2.5), 3)
            self.config['color_cycle_pow'] = round(random.uniform(0.5, 3.5), 3)
            self.config['color_cycle_a1'] = random.choice([True, False])

            gp = []
            for i in range(4):
                pos = round(i / 3, 2)
                gp.append((pos, palette[i]))
            self.config['gradient_points'] = gp

            for li in range(1, 6):
                self.config[f'c{li}_color'] = palette[(li - 1) % len(palette)]

            self._apply_config_to_ui(self.config)
            return

        key_set = set(self._section_keys(section))
        if not key_set:
            return

        prop_map = {}
        for _cat, props in self._get_randomizable_props():
            for prop_def in props:
                prop_map[prop_def[1]] = prop_def

        color_count = 0
        for key in key_set:
            pd = prop_map.get(key)
            if pd and pd[2] == 'color':
                color_count += 1
        color_pool = self._get_designer_palette(color_count) if color_count > 0 else []

        changed = False
        for key in key_set:
            pd = prop_map.get(key)
            if not pd:
                continue
            ptype = pd[2]
            if ptype == 'bool':
                self.config[key] = random.choice([True, False])
            elif ptype == 'int':
                self.config[key] = random.randint(pd[3], pd[4])
            elif ptype == 'float':
                self.config[key] = round(random.uniform(pd[3], pd[4]), 3)
            elif ptype == 'color':
                self.config[key] = color_pool.pop(0) if color_pool else tuple(self._generate_harmony_palette(1)[0])
            elif ptype == 'choice':
                self.config[key] = random.choice(pd[3])
            changed = True

        if changed:
            if section == 'physics':
                hmin = int(self.config.get('bar_height_min', 0))
                hmax = int(self.config.get('bar_height_max', 500))
                if hmin > hmax:
                    self.config['bar_height_min'], self.config['bar_height_max'] = hmax, hmin
                imin = float(self.config.get('bar_internal_min', 0.0))
                imax = float(self.config.get('bar_internal_max', 300.0))
                if imin > imax:
                    self.config['bar_internal_min'], self.config['bar_internal_max'] = imax, imin
            if section in {'graphics', 'contour', 'bars'}:
                self._enforce_random_object_count()
            self._apply_config_to_ui(self.config)

    def _reset_section_to_default(self, section: str):
        keys = self._section_keys(section)
        if not keys:
            return
        defaults = _get_defaults()
        for key in keys:
            if key in defaults:
                self.config[key] = defaults[key]
        self._apply_config_to_ui(self.config)

    def _ensure_section_presets_dir(self):
        SECTION_PRESETS_DIR.mkdir(parents=True, exist_ok=True)

    def _section_preset_path(self, section: str):
        self._ensure_section_presets_dir()
        return SECTION_PRESETS_DIR / f"{section}.json"

    def _read_section_presets(self, section: str):
        fp = self._section_preset_path(section)
        if not fp.exists():
            return {}
        try:
            with open(fp, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _normalize_section_preset_payload(self, section: str, data):
        if not isinstance(data, dict):
            return None
        defaults = _get_defaults()
        normalized = {}
        for key in self._section_keys(section):
            if key in data:
                normalized[key] = data[key]
            elif key in defaults:
                normalized[key] = defaults[key]
        return normalized

    def _write_section_presets(self, section: str, data: dict):
        fp = self._section_preset_path(section)
        with open(fp, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _refresh_section_preset_combo(self, section: str):
        combo = self._section_preset_combos.get(section)
        if combo is None:
            return
        presets = self._read_section_presets(section)
        names = sorted(presets.keys(), key=lambda s: s.lower())
        cur = combo.currentText().strip()
        combo.blockSignals(True)
        combo.clear()
        for name in names:
            combo.addItem(name)
        if cur and cur in names:
            combo.setCurrentText(cur)
        combo.blockSignals(False)

    def _save_section_preset(self, section: str):
        keys = self._section_keys(section)
        if not keys:
            return
        combo = self._section_preset_combos.get(section)
        default_name = combo.currentText().strip() if combo else ""
        section_label = SECTION_PRESET_LABELS.get(section, self._section_display_name(section))
        preset_suffix = '' if section in {'theme_classic_kaleidoscope', 'theme_kaleidoscope_fill', 'theme_kaleidoscope_lines', 'theme_softbody', 'contour', 'bars', 'tentacle'} else '子预设'
        name, ok = QInputDialog.getText(self, f"保存{section_label}", "请输入名称:", text=default_name)
        if not ok:
            return
        safe = self._safe_preset_name(name)
        if not safe:
            QMessageBox.warning(self, "无效名称", "名称不能为空或仅包含非法字符")
            return

        presets = self._read_section_presets(section)
        defaults = _get_defaults()
        presets[safe] = {k: self.config.get(k, defaults.get(k)) for k in keys}
        try:
            self._write_section_presets(section, presets)
            self._refresh_section_preset_combo(section)
            if combo is not None:
                combo.setCurrentText(safe)
            self._set_info_bar(f"已保存{section_label}{preset_suffix}: {safe}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存{section_label}{preset_suffix}失败: {e}")

    def _load_section_preset(self, section: str):
        keys = self._section_keys(section)
        if not keys:
            return
        combo = self._section_preset_combos.get(section)
        if combo is None:
            return
        section_label = SECTION_PRESET_LABELS.get(section, self._section_display_name(section))
        preset_suffix = '' if section in {'theme_classic_kaleidoscope', 'theme_kaleidoscope_fill', 'theme_kaleidoscope_lines', 'theme_softbody', 'contour', 'bars', 'tentacle'} else '子预设'
        name = combo.currentText().strip()
        if not name:
            QMessageBox.warning(self, "提示", f"请先选择{section_label}{preset_suffix}")
            return
        presets = self._read_section_presets(section)
        data = self._normalize_section_preset_payload(section, presets.get(name))
        if not isinstance(data, dict):
            QMessageBox.warning(self, "提示", f"{section_label}{preset_suffix}不存在或已损坏")
            self._refresh_section_preset_combo(section)
            return
        for key in keys:
            self.config[key] = data[key]
        self._apply_config_to_ui(self.config)
        self._set_info_bar(f"已读取{section_label}{preset_suffix}: {name}")

    # ── 五层轮廓 ──────────────────────────────────────────

    def _build_contour_section(self):
        s = _Collapsible("五层轮廓 / 填充 (L1~L5)", expanded=False)
        g = QGridLayout(); g.setSpacing(6); g.setContentsMargins(0,0,0,0); r = 0
        g.addLayout(self._build_section_action_row('contour'), r, 0, 1, 4); r += 1
        _layers = [
            (1, "L1 内缓慢", True, True),
            (2, "L2 内快速", True, False),
            (3, "L3 基圆",   False, False),
            (4, "L4 外快速", True, False),
            (5, "L5 外缓慢", True, True),
        ]
        for li, lname, has_step, has_decay in _layers:
            hdr = QLabel(f"── 图层 {lname} ──")
            hdr.setStyleSheet("color:#888; font-size:8pt; padding:3px 0 1px 0;")
            g.addWidget(hdr, r, 0, 1, 4); r += 1

            chk = QCheckBox("轮廓")
            chk.setChecked(self.config.get(f'c{li}_on', False))
            chk.toggled.connect(lambda v, k=f'c{li}_on': self._update_cfg(k, v))
            setattr(self, f'c{li}_on_check', chk)

            cbtn = QPushButton()
            cc = self.config.get(f'c{li}_color', (255, 255, 255))
            cbtn.setFixedSize(22, 22)
            cbtn.setStyleSheet(self._make_color_button_style(cc))
            cbtn.clicked.connect(lambda _, i=li: self._pick_layer_color(i))
            setattr(self, f'c{li}_color_btn', self._register_color_button(f'c{li}_color', cbtn))

            head_row = QHBoxLayout()
            head_row.setSpacing(8)
            head_row.addWidget(chk)
            head_row.addWidget(cbtn)
            head_row.addStretch()
            g.addLayout(head_row, r, 0, 1, 4); r += 1

            r, _thick_label, sp = self._add_kp_spin_row(
                g, r,
                label_text="厚度:",
                cfg_key=f'c{li}_thick',
                default_value=2,
                soft_min=1,
                soft_max=20,
                hard_min=1,
                hard_max=1000,
                supports=('k', 'p'),
                step=1,
                integer=True,
                width=72,
                kp_soft_min=-4.0,
                kp_soft_max=4.0,
                kp_hard_min=-1000.0,
                kp_hard_max=1000.0,
                kp_decimals=3,
            )
            setattr(self, f'c{li}_thick_spin', sp)

            r, _alpha_label, sl_a, alpha_box = self._add_kp_slider_row(
                g, r,
                label_text="透明度:",
                cfg_key=f'c{li}_alpha',
                default_value=180,
                soft_min=0,
                soft_max=255,
                hard_min=0,
                hard_max=255,
                supports=('k', 'p'),
                integer=True,
                step=1,
                width=58,
                kp_soft_min=-80.0,
                kp_soft_max=80.0,
                kp_hard_min=-255.0,
                kp_hard_max=255.0,
                kp_decimals=1,
            )
            setattr(self, f'c{li}_alpha_slider', sl_a)
            setattr(self, f'c{li}_alpha_spin', alpha_box)

            fc = QCheckBox("填充可见")
            fc.setChecked(self.config.get(f'c{li}_fill', False))
            fc.toggled.connect(lambda v, k=f'c{li}_fill': self._update_cfg(k, v))
            setattr(self, f'c{li}_fill_check', fc)
            g.addWidget(fc, r, 0, 1, 4); r += 1

            r, _fill_label, fsl, fill_box = self._add_kp_slider_row(
                g, r,
                label_text="填充透明度:",
                cfg_key=f'c{li}_fill_alpha',
                default_value=50,
                soft_min=0,
                soft_max=255,
                hard_min=0,
                hard_max=255,
                supports=('k', 'p'),
                integer=True,
                step=1,
                width=58,
                kp_soft_min=-80.0,
                kp_soft_max=80.0,
                kp_hard_min=-255.0,
                kp_hard_max=255.0,
                kp_decimals=1,
            )
            setattr(self, f'c{li}_fill_alpha_slider', fsl)
            setattr(self, f'c{li}_fill_alpha_spin', fill_box)

            if has_step:
                r, _step_label, ssp = self._add_kp_spin_row(
                    g, r,
                    label_text="间隔:",
                    cfg_key=f'c{li}_step',
                    default_value=2,
                    soft_min=1,
                    soft_max=32,
                    hard_min=1,
                    hard_max=4096,
                    supports=('k', 'p'),
                    step=1,
                    integer=True,
                    width=72,
                    kp_soft_min=-8.0,
                    kp_soft_max=8.0,
                    kp_hard_min=-4096.0,
                    kp_hard_max=4096.0,
                    kp_decimals=3,
                )
                setattr(self, f'c{li}_step_spin', ssp)

            if has_decay:
                r, _decay_label, dsl, decay_box = self._add_kp_slider_row(
                    g, r,
                    label_text="衰减:",
                    cfg_key=f'c{li}_decay',
                    default_value=0.995,
                    soft_min=0.9,
                    soft_max=1.0,
                    hard_min=0.0,
                    hard_max=2.0,
                    supports=('k', 'p'),
                    slider_scale=1000,
                    step=0.001,
                    decimals=3,
                    width=72,
                    kp_soft_min=-0.2,
                    kp_soft_max=0.2,
                    kp_hard_min=-2.0,
                    kp_hard_max=2.0,
                    kp_decimals=4,
                )
                setattr(self, f'c{li}_decay_slider', dsl)
                setattr(self, f'c{li}_decay_spin', decay_box)

            if li in (1, 2, 4, 5):
                damp_check, damp_widget, rise_box, fall_box = self._build_independent_damping_controls(f'c{li}')
                setattr(self, f'c{li}_independent_damping_check', damp_check)
                setattr(self, f'c{li}_independent_damping_widget', damp_widget)
                setattr(self, f'c{li}_independent_rise_damping_spin', rise_box)
                setattr(self, f'c{li}_independent_fall_damping_spin', fall_box)
                g.addWidget(damp_check, r, 0, 1, 4); r += 1
                g.addWidget(damp_widget, r, 0, 1, 4); r += 1

            r, _speed_label, rsl, speed_box = self._add_kp_slider_row(
                g, r,
                label_text="转速:",
                cfg_key=f'c{li}_rot_speed',
                default_value=1.0,
                soft_min=-5.0,
                soft_max=5.0,
                hard_min=-100.0,
                hard_max=100.0,
                supports=('k', 'p'),
                slider_scale=100,
                step=0.01,
                decimals=2,
                width=72,
                kp_soft_min=-5.0,
                kp_soft_max=5.0,
                kp_hard_min=-100.0,
                kp_hard_max=100.0,
                kp_decimals=3,
            )
            setattr(self, f'c{li}_rot_speed_slider', rsl)
            setattr(self, f'c{li}_rot_speed_spin', speed_box)

            r, _pow_label, psl, pow_box = self._add_kp_slider_row(
                g, r,
                label_text="rot_pow:",
                cfg_key=f'c{li}_rot_pow',
                default_value=0.5,
                soft_min=-3.0,
                soft_max=3.0,
                hard_min=-100.0,
                hard_max=100.0,
                supports=('k', 'p'),
                slider_scale=100,
                step=0.01,
                decimals=2,
                width=72,
                kp_soft_min=-3.0,
                kp_soft_max=3.0,
                kp_hard_min=-100.0,
                kp_hard_max=100.0,
                kp_decimals=3,
            )
            setattr(self, f'c{li}_rot_pow_slider', psl)
            setattr(self, f'c{li}_rot_pow_spin', pow_box)

        s.add_layout(g)
        return s

    def _build_tentacle_section(self):
        section = QWidget()
        outer = QVBoxLayout(section)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        g = QGridLayout(); g.setSpacing(3); g.setContentsMargins(0, 0, 0, 0); r = 0

        cbtn = QPushButton()
        cc = self.config.get('tentacle_color', (130, 240, 220))
        cbtn.setFixedSize(22, 22)
        cbtn.setStyleSheet(self._make_color_button_style(cc))
        cbtn.clicked.connect(lambda: self._pick_special_color('tentacle_color', self.tentacle_color_btn))
        self.tentacle_color_btn = self._register_color_button('tentacle_color', cbtn)
        g.addWidget(self._make_graphics_form_row(label_text="主色:", widgets=[cbtn], stretch=False), r, 0, 1, 4)
        r += 1

        r, thick_label, sp = self._add_kp_spin_row(
            g, r,
            label_text="根部粗:",
            cfg_key='tentacle_thick',
            default_value=3,
            soft_min=1,
            soft_max=12,
            hard_min=1,
            hard_max=1000,
            supports=('k', 'p'),
            step=1,
            integer=True,
            width=72,
            kp_soft_min=-6.0,
            kp_soft_max=6.0,
            kp_hard_min=-200.0,
            kp_hard_max=200.0,
            kp_decimals=2,
        )
        self.tentacle_thick_spin = sp

        r, alpha_label, sl_a, alpha_box = self._add_kp_slider_row(
            g, r,
            label_text="透明:",
            cfg_key='tentacle_alpha',
            default_value=170,
            soft_min=0,
            soft_max=255,
            hard_min=0,
            hard_max=255,
            supports=('k', 'p'),
            integer=True,
            step=1,
            width=58,
            kp_soft_min=-80.0,
            kp_soft_max=80.0,
            kp_hard_min=-255.0,
            kp_hard_max=255.0,
            kp_decimals=1,
        )
        self.tentacle_alpha_slider = sl_a
        self.tentacle_alpha_spin = alpha_box

        r, cnt_label, cnt_slider, cnt_box = self._add_kp_slider_row(
            g, r,
            label_text="数量:",
            cfg_key='tentacle_count',
            default_value=16,
            soft_min=4,
            soft_max=32,
            hard_min=1,
            hard_max=128,
            supports=('k', 'p'),
            integer=True,
            step=1,
            width=72,
            kp_soft_min=-12.0,
            kp_soft_max=12.0,
            kp_hard_min=-256.0,
            kp_hard_max=256.0,
            kp_decimals=2,
        )
        self.tentacle_count_slider = cnt_slider
        self.tentacle_count_spin = cnt_box

        r, len_label, len_slider, len_box = self._add_kp_slider_row(
            g, r,
            label_text="长度:",
            cfg_key='tentacle_length',
            default_value=280.0,
            soft_min=40.0,
            soft_max=600.0,
            hard_min=0.0,
            hard_max=4000.0,
            supports=('k', 'p'),
            slider_scale=10,
            step=0.1,
            decimals=1,
            width=72,
            kp_soft_min=-240.0,
            kp_soft_max=240.0,
            kp_hard_min=-4000.0,
            kp_hard_max=4000.0,
            kp_decimals=2,
        )
        self.tentacle_length_slider = len_slider
        self.tentacle_length_spin = len_box

        r, jitter_label, jitter_slider, jitter_box = self._add_kp_slider_row(
            g, r,
            label_text="扰动长度:",
            cfg_key='tentacle_length_jitter',
            default_value=80.0,
            soft_min=0.0,
            soft_max=240.0,
            hard_min=0.0,
            hard_max=2000.0,
            supports=('k', 'p'),
            slider_scale=10,
            step=0.1,
            decimals=1,
            width=72,
            kp_soft_min=-240.0,
            kp_soft_max=240.0,
            kp_hard_min=-2000.0,
            kp_hard_max=2000.0,
            kp_decimals=2,
        )
        self.tentacle_length_jitter_slider = jitter_slider
        self.tentacle_length_jitter_spin = jitter_box

        r, jitter_spd_label, jitter_spd_slider, jitter_spd_box = self._add_kp_slider_row(
            g, r,
            label_text="扰动速度:",
            cfg_key='tentacle_length_jitter_speed',
            default_value=0.35,
            soft_min=0.0,
            soft_max=3.0,
            hard_min=0.0,
            hard_max=20.0,
            supports=('k', 'p'),
            slider_scale=100,
            step=0.01,
            decimals=2,
            width=72,
            kp_soft_min=-1.5,
            kp_soft_max=1.5,
            kp_hard_min=-20.0,
            kp_hard_max=20.0,
            kp_decimals=3,
        )
        self.tentacle_length_jitter_speed_slider = jitter_spd_slider
        self.tentacle_length_jitter_speed_spin = jitter_spd_box

        self.tentacle_length_jitter_random_check = QCheckBox("启用随机扰动")
        self.tentacle_length_jitter_random_check.setChecked(self.config.get('tentacle_length_jitter_random', False))
        self.tentacle_length_jitter_random_check.toggled.connect(lambda v: self._update_cfg('tentacle_length_jitter_random', bool(v)))
        g.addWidget(self.tentacle_length_jitter_random_check, r, 0, 1, 4); r += 1

        cp_min_label = self._attach_kp_bindable_label(QLabel("控制点最小:"), 'tentacle_control_points_min', supports=('k', 'p'))
        cp_min_box = self._new_int_box(
            default_value=3, soft_min=3, soft_max=9,
            hard_min=2, hard_max=24, step=1, cfg_key='tentacle_control_points_min'
        )
        self.tentacle_cp_min_spin = cp_min_box
        g.addWidget(self._make_graphics_form_row(label_widget=cp_min_label, widgets=[cp_min_box], label_width=92), r, 0, 1, 4); r += 1
        cp_min_bind, cp_min_base_lbl, cp_min_rows, cp_min_weight_spins = self._build_kp_binding_container(
            cfg_key='tentacle_control_points_min', supports=('k', 'p'),
            wmin_default=0.0, wmax_default=0.0,
            soft_min=-3.0, soft_max=3.0, hard_min=-24.0, hard_max=24.0,
            decimals=2,
        )
        g.addWidget(cp_min_bind, r, 0, 1, 4); r += 1
        self._register_kp_binding_ui(
            cfg_key='tentacle_control_points_min', label=cp_min_label,
            container=cp_min_bind, base_label=cp_min_base_lbl,
            rows=cp_min_rows, supports=('k', 'p'), weight_spins=cp_min_weight_spins,
        )

        cp_max_label = self._attach_kp_bindable_label(QLabel("控制点最大:"), 'tentacle_control_points_max', supports=('k', 'p'))
        cp_max_box = self._new_int_box(
            default_value=5, soft_min=3, soft_max=9,
            hard_min=2, hard_max=24, step=1, cfg_key='tentacle_control_points_max'
        )
        self.tentacle_cp_max_spin = cp_max_box
        g.addWidget(self._make_graphics_form_row(label_widget=cp_max_label, widgets=[cp_max_box], label_width=92), r, 0, 1, 4); r += 1
        cp_max_bind, cp_max_base_lbl, cp_max_rows, cp_max_weight_spins = self._build_kp_binding_container(
            cfg_key='tentacle_control_points_max', supports=('k', 'p'),
            wmin_default=0.0, wmax_default=0.0,
            soft_min=-3.0, soft_max=3.0, hard_min=-24.0, hard_max=24.0,
            decimals=2,
        )
        g.addWidget(cp_max_bind, r, 0, 1, 4); r += 1
        self._register_kp_binding_ui(
            cfg_key='tentacle_control_points_max', label=cp_max_label,
            container=cp_max_bind, base_label=cp_max_base_lbl,
            rows=cp_max_rows, supports=('k', 'p'), weight_spins=cp_max_weight_spins,
        )

        r, tip_bias_label, tip_slider, tip_box = self._add_kp_slider_row(
            g, r,
            label_text="末端权重:",
            cfg_key='tentacle_tip_bias',
            default_value=1.85,
            soft_min=0.5,
            soft_max=3.0,
            hard_min=0.1,
            hard_max=20.0,
            supports=('k', 'p'),
            slider_scale=100,
            step=0.01,
            decimals=2,
            width=72,
            kp_soft_min=-2.0,
            kp_soft_max=2.0,
            kp_hard_min=-20.0,
            kp_hard_max=20.0,
            kp_decimals=3,
        )
        self.tentacle_tip_bias_slider = tip_slider
        self.tentacle_tip_bias_spin = tip_box

        r, tip_thickness_label, tip_thickness_slider, tip_thickness_box = self._add_kp_slider_row(
            g, r,
            label_text="末端粗细:",
            cfg_key='tentacle_tip_thickness',
            default_value=0.15,
            soft_min=0.0,
            soft_max=1.0,
            hard_min=0.0,
            hard_max=1.0,
            supports=('k', 'p'),
            slider_scale=100,
            step=0.01,
            decimals=2,
            width=72,
            kp_soft_min=-0.5,
            kp_soft_max=0.5,
            kp_hard_min=-5.0,
            kp_hard_max=5.0,
            kp_decimals=3,
        )
        self.tentacle_tip_thickness_slider = tip_thickness_slider
        self.tentacle_tip_thickness_spin = tip_thickness_box

        soft_hdr = QLabel("── 柔体 / 水阻尼 ──")
        soft_hdr.setStyleSheet("color:#888; font-size:8pt; padding:3px 0 1px 0;")
        g.addWidget(soft_hdr, r, 0, 1, 4); r += 1

        r, turb_label, turb_slider, turb_box = self._add_kp_slider_row(
            g, r,
            label_text="紊流强度:",
            cfg_key='tentacle_turbulence',
            default_value=46.0,
            soft_min=0.0,
            soft_max=160.0,
            hard_min=0.0,
            hard_max=2000.0,
            supports=('k', 'p'),
            slider_scale=10,
            step=0.1,
            decimals=1,
            width=72,
            kp_soft_min=-2.0,
            kp_soft_max=2.0,
            kp_hard_min=-10.0,
            kp_hard_max=10.0,
            kp_decimals=3,
        )
        self.tentacle_turbulence_slider = turb_slider
        self.tentacle_turbulence_spin = turb_box
        turb_bind = self._kp_binding_meta['tentacle_turbulence']['container']
        turb_base_lbl = self._kp_binding_meta['tentacle_turbulence']['base_label']
        turb_rows = self._kp_binding_meta['tentacle_turbulence']['rows']
        turb_weight_spins = self._kp_binding_meta['tentacle_turbulence']['weight_spins']
        self.kp_tentacle_turbulence_k_wmin_spin, self.kp_tentacle_turbulence_k_wmax_spin = turb_weight_spins['k']
        self.kp_tentacle_turbulence_p_wmin_spin, self.kp_tentacle_turbulence_p_wmax_spin = turb_weight_spins['p']

        r, sway_label, sway_slider, sway_box = self._add_kp_slider_row(
            g, r,
            label_text="漂浮速度:",
            cfg_key='tentacle_sway_speed',
            default_value=1.1,
            soft_min=0.0,
            soft_max=4.0,
            hard_min=0.0,
            hard_max=20.0,
            supports=('k', 'p'),
            slider_scale=100,
            step=0.01,
            decimals=2,
            width=72,
            kp_soft_min=-2.0,
            kp_soft_max=2.0,
            kp_hard_min=-20.0,
            kp_hard_max=20.0,
            kp_decimals=3,
        )
        self.tentacle_sway_speed_slider = sway_slider
        self.tentacle_sway_speed_spin = sway_box

        r, density_label, density_slider, density_box = self._add_kp_slider_row(
            g, r,
            label_text="流场密度:",
            cfg_key='tentacle_sway_density',
            default_value=2.4,
            soft_min=0.2,
            soft_max=6.0,
            hard_min=0.0,
            hard_max=20.0,
            supports=('k', 'p'),
            slider_scale=100,
            step=0.01,
            decimals=2,
            width=72,
            kp_soft_min=-3.0,
            kp_soft_max=3.0,
            kp_hard_min=-50.0,
            kp_hard_max=50.0,
            kp_decimals=3,
        )
        self.tentacle_sway_density_slider = density_slider
        self.tentacle_sway_density_spin = density_box

        r, water_label, water_slider, water_box = self._add_kp_slider_row(
            g, r,
            label_text="水阻尼:",
            cfg_key='tentacle_water_damping',
            default_value=0.84,
            soft_min=0.0,
            soft_max=0.99,
            hard_min=0.0,
            hard_max=0.999,
            supports=('k', 'p'),
            slider_scale=1000,
            step=0.001,
            decimals=3,
            width=72,
            kp_soft_min=-0.3,
            kp_soft_max=0.3,
            kp_hard_min=-1.0,
            kp_hard_max=1.0,
            kp_decimals=4,
        )
        self.tentacle_water_damping_slider = water_slider
        self.tentacle_water_damping_spin = water_box

        r, angle_label, angle_slider, angle_box = self._add_kp_slider_row(
            g, r,
            label_text="弯曲力:",
            cfg_key='tentacle_angle_stiffness',
            default_value=0.18,
            soft_min=0.0,
            soft_max=1.0,
            hard_min=0.0,
            hard_max=5.0,
            supports=('k', 'p'),
            slider_scale=100,
            step=0.01,
            decimals=2,
            width=72,
            kp_soft_min=-0.5,
            kp_soft_max=0.5,
            kp_hard_min=-5.0,
            kp_hard_max=5.0,
            kp_decimals=3,
        )
        self.tentacle_angle_stiffness_slider = angle_slider
        self.tentacle_angle_stiffness_spin = angle_box

        r, length_hold_label, length_hold_slider, length_hold_box = self._add_kp_slider_row(
            g, r,
            label_text="拉伸力:",
            cfg_key='tentacle_length_stiffness',
            default_value=0.24,
            soft_min=0.0,
            soft_max=1.0,
            hard_min=0.0,
            hard_max=5.0,
            supports=('k', 'p'),
            slider_scale=100,
            step=0.01,
            decimals=2,
            width=72,
            kp_soft_min=-0.5,
            kp_soft_max=0.5,
            kp_hard_min=-5.0,
            kp_hard_max=5.0,
            kp_decimals=3,
        )
        self.tentacle_length_stiffness_slider = length_hold_slider
        self.tentacle_length_stiffness_spin = length_hold_box

        r, stretch_limit_label, stretch_limit_slider, stretch_limit_box = self._add_kp_slider_row(
            g, r,
            label_text="拉伸限制:",
            cfg_key='tentacle_stretch_limit',
            default_value=1.12,
            soft_min=1.0,
            soft_max=2.0,
            hard_min=1.0,
            hard_max=10.0,
            supports=('k', 'p'),
            slider_scale=100,
            step=0.01,
            decimals=2,
            width=72,
            kp_soft_min=-0.5,
            kp_soft_max=0.5,
            kp_hard_min=-10.0,
            kp_hard_max=10.0,
            kp_decimals=3,
        )
        self.tentacle_stretch_limit_slider = stretch_limit_slider
        self.tentacle_stretch_limit_spin = stretch_limit_box

        shader_hdr = QLabel("── Shader 渐变 ──")
        shader_hdr.setStyleSheet("color:#888; font-size:8pt; padding:3px 0 1px 0;")
        g.addWidget(shader_hdr, r, 0, 1, 4); r += 1

        shader_check = QCheckBox("启用渐变着色")
        shader_check.setChecked(self.config.get('tentacle_shader_enabled', True))
        shader_check.toggled.connect(lambda v: self._update_cfg('tentacle_shader_enabled', v))
        self.tentacle_shader_check = shader_check
        g.addWidget(shader_check, r, 0)

        shader_tip_btn = QPushButton()
        sc = self.config.get('tentacle_shader_tip_color', (88, 170, 255))
        shader_tip_btn.setFixedSize(22, 22)
        shader_tip_btn.setStyleSheet(self._make_color_button_style(sc))
        shader_tip_btn.clicked.connect(lambda: self._pick_special_color('tentacle_shader_tip_color', self.tentacle_shader_tip_color_btn))
        self.tentacle_shader_tip_color_btn = self._register_color_button('tentacle_shader_tip_color', shader_tip_btn)
        g.addWidget(shader_tip_btn, r, 1)
        g.addWidget(QLabel("尾色"), r, 2)
        r += 1

        r, alpha_start_label, alpha_start_slider, alpha_start_box = self._add_kp_slider_row(
            g, r,
            label_text="起始透明:",
            cfg_key='tentacle_shader_alpha_start',
            default_value=1.0,
            soft_min=0.0,
            soft_max=1.0,
            hard_min=0.0,
            hard_max=1.0,
            supports=('k', 'p'),
            slider_scale=100,
            step=0.01,
            decimals=2,
            width=72,
            kp_soft_min=-0.5,
            kp_soft_max=0.5,
            kp_hard_min=-1.0,
            kp_hard_max=1.0,
            kp_decimals=4,
        )
        self.tentacle_shader_alpha_start_slider = alpha_start_slider
        self.tentacle_shader_alpha_start_spin = alpha_start_box

        r, alpha_end_label, alpha_end_slider, alpha_end_box = self._add_kp_slider_row(
            g, r,
            label_text="末端透明:",
            cfg_key='tentacle_shader_alpha_end',
            default_value=0.18,
            soft_min=0.0,
            soft_max=1.0,
            hard_min=0.0,
            hard_max=1.0,
            supports=('k', 'p'),
            slider_scale=100,
            step=0.01,
            decimals=2,
            width=72,
            kp_soft_min=-0.5,
            kp_soft_max=0.5,
            kp_hard_min=-1.0,
            kp_hard_max=1.0,
            kp_decimals=4,
        )
        self.tentacle_shader_alpha_end_slider = alpha_end_slider
        self.tentacle_shader_alpha_end_spin = alpha_end_box

        r, shader_bias_label, shader_bias_slider, shader_bias_box = self._add_kp_slider_row(
            g, r,
            label_text="渐变偏置:",
            cfg_key='tentacle_shader_bias',
            default_value=1.15,
            soft_min=0.1,
            soft_max=3.0,
            hard_min=0.1,
            hard_max=10.0,
            supports=('k', 'p'),
            slider_scale=100,
            step=0.01,
            decimals=2,
            width=72,
            kp_soft_min=-1.0,
            kp_soft_max=1.0,
            kp_hard_min=-10.0,
            kp_hard_max=10.0,
            kp_decimals=3,
        )
        self.tentacle_shader_bias_slider = shader_bias_slider
        self.tentacle_shader_bias_spin = shader_bias_box

        core_hdr = QLabel("── 中心旋转驱动 ──")
        core_hdr.setStyleSheet("color:#888; font-size:8pt; padding:3px 0 1px 0;")
        g.addWidget(core_hdr, r, 0, 1, 4); r += 1

        note = QLabel("仅作为每根触须的根部驱动器，不额外绘制中心图形")
        note.setWordWrap(True)
        note.setStyleSheet("color:#8a93a1;")
        g.addWidget(note, r, 0, 1, 4); r += 1

        core_check = QCheckBox("启用中心驱动")
        core_check.setChecked(self.config.get('tentacle_core_on', True))
        core_check.toggled.connect(lambda v: self._update_cfg('tentacle_core_on', v))
        self.tentacle_core_on_check = core_check
        g.addWidget(core_check, r, 0, 1, 4); r += 1

        r, core_base_label, core_base_slider, core_base_box = self._add_kp_slider_row(
            g, r,
            label_text="基础角加速度:",
            cfg_key='tentacle_core_base_speed',
            default_value=0.75,
            soft_min=-5.0,
            soft_max=5.0,
            hard_min=-100.0,
            hard_max=100.0,
            supports=('k', 'p'),
            slider_scale=100,
            step=0.01,
            decimals=2,
            width=72,
            kp_soft_min=-5.0,
            kp_soft_max=5.0,
            kp_hard_min=-100.0,
            kp_hard_max=100.0,
            kp_decimals=3,
        )
        self.tentacle_core_base_speed_slider = core_base_slider
        self.tentacle_core_base_speed_spin = core_base_box
        core_bind = self._kp_binding_meta['tentacle_core_base_speed']['container']
        core_base_lbl = self._kp_binding_meta['tentacle_core_base_speed']['base_label']
        core_rows = self._kp_binding_meta['tentacle_core_base_speed']['rows']
        core_weight_spins = self._kp_binding_meta['tentacle_core_base_speed']['weight_spins']
        self.kp_tentacle_core_base_speed_k_wmin_spin, self.kp_tentacle_core_base_speed_k_wmax_spin = core_weight_spins['k']
        self.kp_tentacle_core_base_speed_p_wmin_spin, self.kp_tentacle_core_base_speed_p_wmax_spin = core_weight_spins['p']

        outer.addLayout(g)
        return section

    # ── 四层条形 ──────────────────────────────────────────

    def _build_bars_section(self):
        s = _Collapsible("四层连线 (B12~B45)", expanded=False)
        g = QGridLayout(); g.setSpacing(6); g.setContentsMargins(0,0,0,0); r = 0
        g.addLayout(self._build_section_action_row('bars'), r, 0, 1, 4); r += 1
        for key, bname in [('b12', 'L1-L2 间'), ('b23', 'L2-L3 间'),
                           ('b34', 'L3-L4 间'), ('b45', 'L4-L5 间')]:
            hdr = QLabel(f"── 连线 {bname} ──")
            hdr.setStyleSheet("color:#888; font-size:8pt; padding:3px 0 1px 0;")
            g.addWidget(hdr, r, 0, 1, 4); r += 1

            chk = QCheckBox("显示")
            chk.setChecked(self.config.get(f'{key}_on', False))
            chk.toggled.connect(lambda v, k=f'{key}_on': self._update_cfg(k, v))
            setattr(self, f'{key}_on_check', chk)
            g.addWidget(chk, r, 0, 1, 4); r += 1

            r, _thick_label, sp = self._add_kp_spin_row(
                g, r,
                label_text="厚度:",
                cfg_key=f'{key}_thick',
                default_value=3,
                soft_min=1,
                soft_max=20,
                hard_min=1,
                hard_max=1000,
                supports=('k', 'p'),
                step=1,
                integer=True,
                width=72,
                kp_soft_min=-4.0,
                kp_soft_max=4.0,
                kp_hard_min=-1000.0,
                kp_hard_max=1000.0,
                kp_decimals=3,
            )
            setattr(self, f'{key}_thick_spin', sp)

            fchk = QCheckBox("固定长度")
            fchk.setChecked(self.config.get(f'{key}_fixed', False))
            setattr(self, f'{key}_fixed_check', fchk)
            g.addWidget(fchk, r, 0, 1, 4); r += 1

            r, _fixed_label, fsp = self._add_kp_spin_row(
                g, r,
                label_text="固定长度:",
                cfg_key=f'{key}_fixed_len',
                default_value=30,
                soft_min=1,
                soft_max=500,
                hard_min=1,
                hard_max=10000,
                supports=('k', 'p'),
                step=1,
                integer=True,
                width=72,
                suffix=' px',
                kp_soft_min=-50.0,
                kp_soft_max=50.0,
                kp_hard_min=-10000.0,
                kp_hard_max=10000.0,
                kp_decimals=3,
            )
            setattr(self, f'{key}_fixed_len_spin', fsp)

            mode_w = QWidget()
            ml = QHBoxLayout(mode_w); ml.setContentsMargins(10,0,0,0); ml.setSpacing(8)
            cs = QCheckBox("首端")
            cs.setChecked(self.config.get(f'{key}_from_start', True))
            cs.toggled.connect(lambda v, k=f'{key}_from_start': self._update_cfg(k, v))
            setattr(self, f'{key}_start_check', cs)
            ce = QCheckBox("末端")
            ce.setChecked(self.config.get(f'{key}_from_end', False))
            ce.toggled.connect(lambda v, k=f'{key}_from_end': self._update_cfg(k, v))
            setattr(self, f'{key}_end_check', ce)
            cc = QCheckBox("中间")
            cc.setChecked(self.config.get(f'{key}_from_center', False))
            cc.toggled.connect(lambda v, k=f'{key}_from_center': self._update_cfg(k, v))
            setattr(self, f'{key}_center_check', cc)
            ml.addWidget(cs); ml.addWidget(ce); ml.addWidget(cc)
            mode_w.setVisible(self.config.get(f'{key}_fixed', False))
            setattr(self, f'{key}_mode_widget', mode_w)
            g.addWidget(mode_w, r, 0, 1, 4); r += 1

            fchk.toggled.connect(lambda v, k=key, w=mode_w: (self._update_cfg(f'{k}_fixed', v), w.setVisible(v)))

            damp_check, damp_widget, rise_box, fall_box = self._build_independent_damping_controls(key)
            setattr(self, f'{key}_independent_damping_check', damp_check)
            setattr(self, f'{key}_independent_damping_widget', damp_widget)
            setattr(self, f'{key}_independent_rise_damping_spin', rise_box)
            setattr(self, f'{key}_independent_fall_damping_spin', fall_box)
            g.addWidget(damp_check, r, 0, 1, 4); r += 1
            g.addWidget(damp_widget, r, 0, 1, 4); r += 1

        s.add_layout(g)
        return s

    # ── 高级控制 ──────────────────────────────────────────

    def _build_k1_section(self):
        s = _Collapsible("高级控制", expanded=True)
        v = QVBoxLayout(); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(6)
        note = QLabel("顶部四联预览区已承载 K、P、T、P2、默认阻尼、条形独立阻尼与动态颜色预览。\n右侧此页保留为说明，不再重复放置同一组控件。")
        note.setWordWrap(True)
        note.setStyleSheet("color:#9aa3af; padding:4px 0;")
        v.addWidget(note)
        s.add_layout(v)
        return s

    # ── 随机化 ──────────────────────────────────────────

    def _build_random_section(self):
        s = _Collapsible("🎲 随机", expanded=False)
        v = QVBoxLayout(); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(6)

        # 第1行：主动作按钮（全宽两列）
        row1 = QHBoxLayout(); row1.setSpacing(8)
        btn_rand = QPushButton("🎲 随机化选中项")
        btn_rand.setMinimumHeight(30)
        btn_rand.clicked.connect(self._randomize_selected)
        row1.addWidget(btn_rand, 1)

        btn_quick_save = QPushButton("💾 快速保存当前预设")
        btn_quick_save.setMinimumHeight(30)
        btn_quick_save.clicked.connect(self._on_random_quick_save_clicked)
        row1.addWidget(btn_quick_save, 1)
        v.addLayout(row1)

        # 第2行：勾选辅助按钮（独立于树面板）
        row2 = QHBoxLayout(); row2.setSpacing(8)
        btn_all = QPushButton("全选")
        btn_all.clicked.connect(lambda: self._set_all_random_checks(True))
        row2.addWidget(btn_all)
        btn_none = QPushButton("全不选")
        btn_none.clicked.connect(lambda: self._set_all_random_checks(False))
        row2.addWidget(btn_none)
        row2.addStretch()
        v.addLayout(row2)

        row3 = QHBoxLayout(); row3.setSpacing(8)
        row3.addWidget(QLabel("图元数范围"))
        self.random_obj_min_spin = self._new_int_box(
            default_value=1, soft_min=1, soft_max=9,
            hard_min=1, hard_max=99, step=1,
            value=int(self.config.get('random_object_count_min', 1))
        )
        self.random_obj_min_spin.valueChanged.connect(self._on_random_obj_min_changed)
        self.random_obj_max_spin = self._new_int_box(
            default_value=10, soft_min=1, soft_max=10,
            hard_min=1, hard_max=99, step=1,
            value=int(self.config.get('random_object_count_max', 10))
        )
        self.random_obj_max_spin.valueChanged.connect(self._on_random_obj_max_changed)
        row3.addWidget(self.random_obj_min_spin)
        row3.addWidget(QLabel("~"))
        row3.addWidget(self.random_obj_max_spin)
        row3.addWidget(QLabel("(总计 10 个图元)"))
        row3.addStretch()
        v.addLayout(row3)

        self.random_tree = QTreeWidget()
        self.random_tree.setHeaderHidden(True)
        self.random_tree.setMinimumHeight(180)

        saved_checks = set(self.config.get('random_checked', []))
        categories = self._get_randomizable_props()
        for cat_name, props in categories:
            cat_item = QTreeWidgetItem(self.random_tree, [cat_name])
            cat_item.setFlags(cat_item.flags() | Qt.ItemIsAutoTristate | Qt.ItemIsUserCheckable)
            cat_item.setCheckState(0, Qt.Unchecked)
            for prop_def in props:
                child = QTreeWidgetItem(cat_item, [prop_def[0]])
                child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                child.setCheckState(0, Qt.Checked if prop_def[1] in saved_checks else Qt.Unchecked)
                child.setData(0, Qt.UserRole, prop_def)

        self.random_tree.expandAll()
        self.random_tree.itemChanged.connect(self._on_random_tree_changed)
        v.addWidget(self.random_tree, 1)
        s.add_layout(v)
        return s

    @staticmethod
    def _get_randomizable_props():
        props = [
            ("控制 · 通用", [
                ("总开关", "master_visible", "bool"),
                ("缩放", "global_scale", "float", 0.1, 5.0),
                ("频谱条数", "num_bars", "int", 3, 12),
            ]),
            ("频谱", [
                ("半径", "circle_radius", "int", 10, 500),
                ("段数", "circle_segments", "int", 1, 11),
                ("K旋转", "circle_a1_rotation", "bool"),
                ("K半径", "circle_a1_radius", "bool"),
                ("半径阻尼", "radius_damping", "float", 0.5, 0.99),
                ("半径弹性", "radius_spring", "float", 0.01, 1.0),
                ("半径回弹", "radius_gravity", "float", 0.0, 1.0),
                ("最低频率", "freq_min", "int", 1, 5000),
                ("最高频率", "freq_max", "int", 5000, 22050),
                ("最小长度", "bar_length_min", "int", 0, 200),
                ("最大长度", "bar_length_max", "int", 50, 1000),
            ]),
            ("颜色方案", [
                ("颜色方案", "color_scheme", "choice", ["rainbow", "fire", "ice", "neon"]),
                ("渐变启用", "gradient_enabled", "bool"),
                ("渐变模式", "gradient_mode", "choice", ["frequency", "height"]),
                ("动态色相", "color_dynamic", "bool"),
                ("基础速率V0", "color_cycle_speed", "float", 0.0, 10.0),
                ("峰值速率VP", "color_cycle_pow", "float", 0.01, 5.0),
                ("P突变加速", "color_cycle_a1", "bool"),
            ]),
            ("运动表现", [
                ("旋转基值", "rotation_base", "float", 0.0, 3.0),
                ("主半径缩放", "main_radius_scale", "float", 0.1, 3.0),
                ("K增大阻尼", "k_rise_damping", "float", 0.0, 0.999),
                ("K缩小阻尼", "k_fall_damping", "float", 0.0, 0.999),
                ("条形独立阻尼", "bar_use_independent_damping", "bool"),
                ("条形增大阻尼", "bar_independent_rise_damping", "float", 0.0, 0.999),
                ("条形缩小阻尼", "bar_independent_fall_damping", "float", 0.0, 0.999),
                ("默认高度", "bar_default_height", "float", 0.0, 300.0),
                ("内部最小高度", "bar_internal_min", "float", 0.0, 300.0),
                ("内部最大高度", "bar_internal_max", "float", 0.0, 1000.0),
                ("最小高度", "bar_height_min", "int", 0, 500),
                ("最大高度", "bar_height_max", "int", 100, 2000),
            ]),
            ("窗口行为", [
                ("背景透明", "bg_transparent", "bool"),
                ("窗口置顶", "always_on_top", "bool"),
            ]),
        ]
        layer_names = {1: "内缓慢", 2: "内快速", 3: "基圆", 4: "外快速", 5: "外缓慢"}
        for li in range(1, 6):
            cat_props = [
                ("显示", f"c{li}_on", "bool"),
                ("颜色", f"c{li}_color", "color"),
                ("透明度", f"c{li}_alpha", "int", 0, 255),
                ("线宽", f"c{li}_thick", "int", 1, 20),
                ("填充", f"c{li}_fill", "bool"),
                ("填充透明度", f"c{li}_fill_alpha", "int", 0, 255),
                ("转速", f"c{li}_rot_speed", "float", -5.0, 5.0),
                ("幂次", f"c{li}_rot_pow", "float", -3.0, 3.0),
            ]
            if li in (1, 2, 4, 5):
                cat_props.append(("间隔", f"c{li}_step", "int", 1, 32))
                cat_props.extend([
                    ("独立阻尼", f"c{li}_use_independent_damping", "bool"),
                    ("增大阻尼", f"c{li}_independent_rise_damping", "float", 0.0, 0.999),
                    ("缩小阻尼", f"c{li}_independent_fall_damping", "float", 0.0, 0.999),
                ])
            if li in (1, 5):
                cat_props.append(("衰减", f"c{li}_decay", "float", 0.9, 1.0))
            props.append((f"L{li} {layer_names[li]}", cat_props))

        for key, bname in [('b12', 'L1-L2 条形'), ('b23', 'L2-L3 条形'),
                           ('b34', 'L3-L4 条形'), ('b45', 'L4-L5 条形')]:
            cat_props = [
                ("显示", f"{key}_on", "bool"),
                ("线宽", f"{key}_thick", "int", 1, 20),
                ("固定长度", f"{key}_fixed", "bool"),
                ("固定长度值", f"{key}_fixed_len", "int", 1, 500),
                ("首端", f"{key}_from_start", "bool"),
                ("末端", f"{key}_from_end", "bool"),
                ("中间", f"{key}_from_center", "bool"),
                ("独立阻尼", f"{key}_use_independent_damping", "bool"),
                ("增大阻尼", f"{key}_independent_rise_damping", "float", 0.0, 0.999),
                ("缩小阻尼", f"{key}_independent_fall_damping", "float", 0.0, 0.999),
            ]
            props.append((bname, cat_props))

        props.append(("柔体", [
            ("显示", "tentacle_on", "bool"),
            ("颜色", "tentacle_color", "color"),
            ("透明度", "tentacle_alpha", "int", 0, 255),
            ("线宽", "tentacle_thick", "int", 1, 12),
            ("数量", "tentacle_count", "int", 4, 32),
            ("长度", "tentacle_length", "float", 40.0, 700.0),
            ("扰动长度", "tentacle_length_jitter", "float", 0.0, 240.0),
            ("控制点下限", "tentacle_control_points_min", "int", 3, 9),
            ("控制点上限", "tentacle_control_points_max", "int", 3, 9),
            ("末端权重", "tentacle_tip_bias", "float", 0.5, 3.0),
            ("末端粗细", "tentacle_tip_thickness", "float", 0.0, 1.0),
            ("紊流强度", "tentacle_turbulence", "float", 0.0, 160.0),
            ("K影响", "tentacle_k_influence", "float", 0.0, 3.0),
            ("漂浮速度", "tentacle_sway_speed", "float", 0.0, 4.0),
            ("流场密度", "tentacle_sway_density", "float", 0.2, 6.0),
            ("水阻尼", "tentacle_water_damping", "float", 0.0, 0.99),
            ("弯曲力", "tentacle_angle_stiffness", "float", 0.0, 1.0),
            ("拉伸力", "tentacle_length_stiffness", "float", 0.0, 1.0),
            ("拉伸限制", "tentacle_stretch_limit", "float", 1.0, 2.0),
            ("Shader启用", "tentacle_shader_enabled", "bool"),
            ("Shader尾色", "tentacle_shader_tip_color", "color"),
            ("起始透明", "tentacle_shader_alpha_start", "float", 0.0, 1.0),
            ("末端透明", "tentacle_shader_alpha_end", "float", 0.0, 1.0),
            ("渐变偏置", "tentacle_shader_bias", "float", 0.1, 3.0),
            ("中心驱动", "tentacle_core_on", "bool"),
            ("基础角加速度", "tentacle_core_base_speed", "float", -5.0, 5.0),
            ("K角加速度", "tentacle_core_k_speed", "float", -5.0, 5.0),
            ("P角加速度", "tentacle_core_p_speed", "float", -5.0, 5.0),
        ]))

        props.append(("高级控制", [
            ("T时间窗口", "a1_time_window", "float", 0.01, 60.0),
            ("频谱独立T", "bar_use_independent_time_window", "bool"),
            ("频谱T时间窗口", "bar_time_window", "float", 0.01, 60.0),
            ("P启用", "k2_enabled", "bool"),
            ("P2幂次", "k2_pow", "float", 0.01, 10.0),
        ]))
        return props

    def _set_all_random_checks(self, checked):
        self.random_tree.blockSignals(True)
        state = Qt.Checked if checked else Qt.Unchecked
        for i in range(self.random_tree.topLevelItemCount()):
            item = self.random_tree.topLevelItem(i)
            item.setCheckState(0, state)
        self.random_tree.blockSignals(False)
        self._save_random_checks()

    def _on_random_tree_changed(self, _item, _col):
        self._save_random_checks()

    def _save_random_checks(self):
        checked = []
        for i in range(self.random_tree.topLevelItemCount()):
            cat_item = self.random_tree.topLevelItem(i)
            for j in range(cat_item.childCount()):
                child = cat_item.child(j)
                if child.checkState(0) == Qt.Checked:
                    prop_def = child.data(0, Qt.UserRole)
                    if prop_def:
                        checked.append(prop_def[1])
        self.config['random_checked'] = checked
        self._save_config()

    def _on_random_obj_min_changed(self, v):
        max_v = self.random_obj_max_spin.value()
        if v > max_v:
            self.random_obj_max_spin.blockSignals(True)
            self.random_obj_max_spin.setValue(v)
            self.random_obj_max_spin.blockSignals(False)
            max_v = v
            self._update_cfg('random_object_count_max', int(max_v))
        self._update_cfg('random_object_count_min', int(v))

    def _on_random_obj_max_changed(self, v):
        min_v = self.random_obj_min_spin.value()
        if v < min_v:
            self.random_obj_min_spin.blockSignals(True)
            self.random_obj_min_spin.setValue(v)
            self.random_obj_min_spin.blockSignals(False)
            min_v = v
            self._update_cfg('random_object_count_min', int(min_v))
        self._update_cfg('random_object_count_max', int(v))

    def _next_random_quick_preset_name(self, stay_seconds: int):
        self._ensure_presets_dir()
        pattern = re.compile(rf"^R{stay_seconds}_(\d+)$", re.IGNORECASE)
        max_seq = 0
        for fp in PRESETS_DIR.glob(f"R{stay_seconds}_*.json"):
            m = pattern.match(fp.stem)
            if m:
                max_seq = max(max_seq, int(m.group(1)))
        return f"R{stay_seconds}_{max_seq + 1:03d}"

    def _save_quick_random_preset(self, stay_seconds: int):
        if stay_seconds < 2:
            self._set_info_bar("快速保存未执行：停留时间不足 2 秒")
            return
        name = self._next_random_quick_preset_name(stay_seconds)
        fp = PRESETS_DIR / f"{name}.json"
        save_data = self._build_full_preset_payload()
        try:
            with open(fp, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
            self._refresh_preset_list()
            self._set_info_bar(f"快速保存预设: {name}")
        except Exception as e:
            print(f"警告: 快速保存预设失败: {e}")

    def _on_random_quick_save_clicked(self):
        if not self._last_random_apply_ts:
            self._set_info_bar("快速保存未执行：请先随机一次")
            return
        stay_seconds = int(time.time() - self._last_random_apply_ts)
        self._save_quick_random_preset(stay_seconds)

    @staticmethod
    def _fetch_json_url(url: str, timeout: float = 1.6):
        req = request.Request(url, headers={'User-Agent': 'AYE-Visualizer/1.0'})
        with request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8', errors='ignore'))

    @staticmethod
    def _fetch_json_post(url: str, payload: dict, timeout: float = 1.6):
        body = json.dumps(payload).encode('utf-8')
        req = request.Request(
            url,
            data=body,
            headers={'Content-Type': 'application/json', 'User-Agent': 'AYE-Visualizer/1.0'},
            method='POST'
        )
        with request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8', errors='ignore'))

    def _fetch_palette_from_thecolorapi(self, count: int):
        base = f"{random.randint(0, 0xFFFFFF):06x}"
        mode = random.choice(['analogic', 'analogic-complement', 'triad', 'quad', 'monochrome'])
        q = parse.urlencode({'hex': base, 'mode': mode, 'count': max(3, int(count))})
        data = self._fetch_json_url(f"https://www.thecolorapi.com/scheme?{q}")
        colors = data.get('colors', []) if isinstance(data, dict) else []
        out = []
        for c in colors:
            rgb = (((c or {}).get('rgb') or {}).get('r'), ((c or {}).get('rgb') or {}).get('g'), ((c or {}).get('rgb') or {}).get('b'))
            if all(isinstance(v, int) for v in rgb):
                out.append((int(rgb[0]), int(rgb[1]), int(rgb[2])))
        return out

    def _fetch_palette_from_colormind(self):
        data = self._fetch_json_post("http://colormind.io/api/", {'model': 'default'})
        result = data.get('result', []) if isinstance(data, dict) else []
        out = []
        for row in result:
            if isinstance(row, list) and len(row) >= 3:
                r, g, b = row[0], row[1], row[2]
                if all(isinstance(v, (int, float)) for v in (r, g, b)):
                    out.append((int(r), int(g), int(b)))
        return out

    def _start_palette_refill_async(self, need: int = 16):
        if self._palette_refill_running:
            return
        self._palette_refill_running = True

        def _worker():
            fetched = []
            try:
                fetched = self._fetch_palette_from_thecolorapi(max(need, 8))
            except Exception:
                fetched = []
            if not fetched:
                try:
                    fetched = self._fetch_palette_from_colormind()
                except Exception:
                    fetched = []
            if fetched:
                self._palette_cache.extend(fetched)
            self._palette_refill_running = False

        threading.Thread(target=_worker, daemon=True).start()

    @staticmethod
    def _generate_harmony_palette(count: int):
        n = max(1, int(count))
        base_h = random.random()
        sat = random.uniform(0.55, 0.9)
        val = random.uniform(0.75, 0.98)
        out = []
        for i in range(n):
            h = (base_h + (i / max(1, n)) * random.choice([0.18, 0.22, 0.28, 0.33])) % 1.0
            s = min(1.0, max(0.0, sat + random.uniform(-0.12, 0.10)))
            v = min(1.0, max(0.0, val + random.uniform(-0.10, 0.08)))
            r, g, b = colorsys.hsv_to_rgb(h, s, v)
            out.append((int(r * 255), int(g * 255), int(b * 255)))
        return out

    def _get_designer_palette(self, count: int):
        need = max(1, int(count))
        out = []

        if self._palette_cache:
            take = min(len(self._palette_cache), need)
            out.extend(self._palette_cache[:take])
            self._palette_cache = self._palette_cache[take:]

        if len(out) < need:
            out.extend(self._generate_harmony_palette(need - len(out)))

        if len(self._palette_cache) < 8:
            self._start_palette_refill_async()

        return out

    def _enforce_random_object_count(self, target_config=None):
        cfg = self.config if target_config is None else target_config
        object_keys = ['c1_on', 'c2_on', 'c3_on', 'c4_on', 'c5_on', 'b12_on', 'b23_on', 'b34_on', 'b45_on', 'tentacle_on']
        total = len(object_keys)
        min_v = int(cfg.get('random_object_count_min', 1))
        max_v = int(cfg.get('random_object_count_max', total))
        low = max(1, min(total, min(min_v, max_v)))
        high = max(1, min(total, max(min_v, max_v)))
        target = random.randint(low, high)

        chosen = set(random.sample(object_keys, k=target))
        for key in object_keys:
            cfg[key] = key in chosen

    def _randomize_selected(self, *, use_transition=False):
        """随机化所有被选中的属性"""
        now = time.time()
        working_config = dict(self.config)
        from_config = self.config.copy() if use_transition else None

        changed = False
        color_count = 0
        for i in range(self.random_tree.topLevelItemCount()):
            cat_item = self.random_tree.topLevelItem(i)
            for j in range(cat_item.childCount()):
                child = cat_item.child(j)
                if child.checkState(0) != Qt.Checked:
                    continue
                prop_def = child.data(0, Qt.UserRole)
                if prop_def and prop_def[2] == "color":
                    color_count += 1

        color_pool = self._get_designer_palette(color_count) if color_count > 0 else []

        for i in range(self.random_tree.topLevelItemCount()):
            cat_item = self.random_tree.topLevelItem(i)
            for j in range(cat_item.childCount()):
                child = cat_item.child(j)
                if child.checkState(0) != Qt.Checked:
                    continue
                prop_def = child.data(0, Qt.UserRole)
                if not prop_def:
                    continue
                cfg_key, ptype = prop_def[1], prop_def[2]
                if ptype == "bool":
                    working_config[cfg_key] = random.choice([True, False])
                elif ptype == "int":
                    working_config[cfg_key] = random.randint(prop_def[3], prop_def[4])
                elif ptype == "float":
                    working_config[cfg_key] = round(random.uniform(prop_def[3], prop_def[4]), 3)
                elif ptype == "color":
                    if color_pool:
                        working_config[cfg_key] = color_pool.pop(0)
                    else:
                        working_config[cfg_key] = tuple(self._generate_harmony_palette(1)[0])
                elif ptype == "choice":
                    working_config[cfg_key] = random.choice(prop_def[3])
                changed = True
        if changed:
            working_config['color_scheme'] = 'custom'
            self._enforce_random_object_count(working_config)
            self._apply_config_to_ui(working_config)
            self._last_random_apply_ts = now
            if use_transition and self.config.get('preset_transition_enabled', False) and self.viz_process and self.viz_process.is_alive():
                self._send_transition_command(from_config)
                self.cfg_send_timer.stop()

    def _update_color_preview_strip(self):
        if not hasattr(self, 'palette_preview_cells'):
            return
        self._set_palette_preview_colors(self._build_palette_preview_entries())

    def _on_palette_cell_clicked(self, idx: int):
        if idx < 0 or idx >= len(self.palette_preview_cells):
            return
        entry = self._latest_palette_preview_meta[idx] if idx < len(self._latest_palette_preview_meta) else None
        if not entry:
            return
        cur = entry.get('color', (255, 255, 255))
        target = entry.get('target') or {}
        target_kind = target.get('kind')

        if target_kind == 'scheme' and self.config.get('color_scheme', 'rainbow') != 'custom':
            self._set_info_bar('当前为预设配色，切到“自定义”后可直接点击色块编辑控制点')
            return

        if target_kind == 'gradient':
            cfg_prefix = f"gradient_points_{int(target.get('index', idx))}_color"
        elif target_kind == 'cfg':
            cfg_prefix = str(target.get('key') or f"palette_cell_{idx}")
        else:
            cfg_prefix = f"palette_cell_{idx}"

        picker = QuickColorPicker(self, initial=cur, presets=self._get_designer_palette(12), cfg_key_prefix=cfg_prefix)

        def _apply(new_col):
            if target_kind == 'gradient':
                pts = list(self.config.get('gradient_points', []))
                point_index = int(target.get('index', idx))
                if point_index < len(pts):
                    pts[point_index] = (pts[point_index][0], new_col)
                else:
                    pos = min(1.0, max(0.0, point_index / max(1, len(self.palette_preview_cells) - 1)))
                    pts.append((pos, new_col))
                self._update_cfg('gradient_points', pts)
            elif target_kind == 'cfg':
                key = str(target.get('key'))
                self._set_registered_color_buttons(key, new_col)
                self._update_cfg(key, new_col)
            else:
                self._set_info_bar('该色块是当前主题效果预览，不对应单独颜色参数')
                return
            self._update_color_preview_strip()

        picker.colorSelected.connect(_apply)
        picker.exec()

    # ═══════════════════════════════════════════════════════
    #  颜色控制回调
    # ═══════════════════════════════════════════════════════

    def _on_color_scheme_changed(self, idx):
        schemes = ['rainbow', 'fire', 'ice', 'neon', 'custom']
        self.color_grp.setVisible(schemes[idx] == 'custom')
        self._update_cfg('color_scheme', schemes[idx])

    def _pick_layer_color(self, layer_idx):
        key = f'c{layer_idx}_color'
        cur = self.config.get(key, (255, 255, 255))
        picker = QuickColorPicker(self, initial=cur, presets=self._get_designer_palette(12), cfg_key_prefix=key)

        def _apply(rgb):
            self._set_registered_color_buttons(key, rgb)
            self._update_cfg(key, rgb)
            self._update_color_preview_strip()

        picker.colorSelected.connect(_apply)
        picker.exec()

    def _pick_special_color(self, cfg_key: str, btn: QPushButton | None = None):
        cur = self.config.get(cfg_key, (255, 255, 255))
        picker = QuickColorPicker(self, initial=cur, presets=self._get_designer_palette(12), cfg_key_prefix=cfg_key)

        def _apply(rgb):
            if btn is not None:
                btn.setStyleSheet(self._make_color_button_style(rgb))
            self._set_registered_color_buttons(cfg_key, rgb)
            self._update_cfg(cfg_key, rgb)

        picker.colorSelected.connect(_apply)
        picker.exec()

    def _on_dynamic_toggled(self, v):
        self._update_cfg('color_dynamic', v)

    def _rebuild_gradient_ui(self):
        for w in self.gp_widgets:
            w.setParent(None); w.deleteLater()
        self.gp_widgets.clear()
        self._gradient_point_buttons.clear()

        points = sorted(self.config.get('gradient_points', [(0.0, (255, 0, 128)), (1.0, (0, 255, 255))]), key=lambda p: p[0])
        for i, (pos, color) in enumerate(points):
            row = QWidget()
            rl = QHBoxLayout(row); rl.setContentsMargins(0, 2, 0, 2)

            pos_box = self._new_float_box(
                default_value=pos, soft_min=0.0, soft_max=1.0,
                hard_min=-10.0, hard_max=10.0, step=0.01, decimals=2,
                value=pos, width=64
            )
            rl.addWidget(pos_box)
            sl = QSlider(Qt.Horizontal)
            pos_box.bind_slider(sl, 100)
            pos_box.valueChanged.connect(lambda v, idx=i: self._gp_pos_changed(idx, v))
            rl.addWidget(sl)

            btn = QPushButton(); btn.setFixedSize(26, 26)
            btn.clicked.connect(lambda _, idx=i, b=btn: self._gp_color_pick(idx, b))
            rl.addWidget(btn)
            self._gradient_point_buttons.append(btn)
            preview_color = self._latest_gradient_point_colors[i] if i < len(self._latest_gradient_point_colors) and self._latest_gradient_point_colors[i] is not None else color
            self._set_gradient_point_button_color(i, preview_color)

            if len(points) > 2:
                db = QPushButton("❌"); db.setFixedSize(25, 25)
                db.clicked.connect(lambda _, idx=i: self._gp_remove(idx))
                rl.addWidget(db)

            self.gp_layout.addWidget(row)
            self.gp_widgets.append(row)

    def _gp_pos_changed(self, idx, value):
        p = float(value)
        pts = list(self.config.get('gradient_points', []))
        if idx < len(pts):
            pts[idx] = (p, pts[idx][1])
            self._update_cfg('gradient_points', pts)

    def _gp_color_pick(self, idx, btn):
        pts = list(self.config.get('gradient_points', []))
        if idx >= len(pts):
            return
        cur = pts[idx][1]
        picker = QuickColorPicker(self, initial=cur, presets=self._get_designer_palette(12), cfg_key_prefix=f"gradient_points_{idx}_color")

        def _apply(rgb):
            btn.setStyleSheet(self._make_color_button_style(rgb))
            self._set_gradient_point_button_color(idx, rgb)
            pts2 = list(self.config.get('gradient_points', []))
            if idx < len(pts2):
                pts2[idx] = (pts2[idx][0], rgb)
                self._update_cfg('gradient_points', pts2)
                self._update_color_preview_strip()

        picker.colorSelected.connect(_apply)
        picker.exec()

    def _add_gradient_point(self):
        pts = list(self.config.get('gradient_points', []))
        pts.append((0.5, (128, 128, 255)))
        self._update_cfg('gradient_points', pts)
        self._rebuild_gradient_ui()

    def _gp_remove(self, idx):
        pts = list(self.config.get('gradient_points', []))
        if len(pts) > 2 and idx < len(pts):
            pts.pop(idx)
            self._update_cfg('gradient_points', pts)
            self._rebuild_gradient_ui()

    # ═══════════════════════════════════════════════════════
    #  进程管理
    # ═══════════════════════════════════════════════════════

    def _start_visualizer(self):
        if self.viz_process and self.viz_process.is_alive():
            return
        try:
            self.config_queue = mp.Queue(maxsize=1)
            self.status_queue = mp.Queue(maxsize=1)
            self.config_queue.put(self.config)

            self.viz_process = mp.Process(
                target=_run_circular,
                args=(self.config_queue, self.status_queue),
                daemon=True,  # 父进程退出时自动杀死子进程（无论是正常关闭还是强杀）
            )
            self.viz_process.start()

            time.sleep(0.5)
            if not self.viz_process.is_alive():
                QMessageBox.warning(self, "错误", "可视化进程启动失败")
                return

            self.status_timer.start(100)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"启动失败: {e}")

    def _stop_visualizer(self):
        self.status_timer.stop()
        if self.viz_process and self.viz_process.is_alive():
            self.viz_process.terminate()
            self.viz_process.join(timeout=2)
            if self.viz_process.is_alive():
                self.viz_process.kill()
                self.viz_process.join(timeout=1)
        self.viz_process = None
        self.config_queue = None
        self.status_queue = None

    def _center_window(self):
        # 复位位置：设为 -1 表示屏幕居中
        self.config['pos_x'] = -1
        self.config['pos_y'] = -1
        self.pos_x_spin.blockSignals(True)
        self.pos_y_spin.blockSignals(True)
        self.pos_x_spin.setValue(-1)
        self.pos_y_spin.setValue(-1)
        self.pos_x_spin.blockSignals(False)
        self.pos_y_spin.blockSignals(False)
        self._save_config()
        if self.viz_process and self.viz_process.is_alive():
            if self.config_queue and not self.config_queue.full():
                try:
                    self.config_queue.put({'command': 'center_window'})
                except:
                    pass

    def _set_window_layer_mode(self, mode):
        mode = str(mode or 'normal').lower()
        if mode not in {'top', 'normal', 'bottom'}:
            mode = 'normal'
        self.config['window_layer'] = mode
        self.config['always_on_top'] = (mode == 'top')
        self._sync_window_layer_controls(mode)
        self._schedule_config_commit()
        if self.config_queue and self.viz_process and self.viz_process.is_alive():
            try:
                self.config_queue.put_nowait({'command': 'set_window_layer', 'mode': mode})
            except Exception:
                pass
        self._set_info_bar(f"窗口层级已切换为: {'顶层' if mode == 'top' else '底层' if mode == 'bottom' else '普通'}")

    def _handle_window_layer_toggle(self, mode, checked):
        mode = str(mode or 'normal').lower()
        current = str(self.config.get('window_layer', 'normal')).lower()
        if checked:
            self._set_window_layer_mode(mode)
        elif current == mode:
            self._set_window_layer_mode('normal')

    def _sync_window_layer_controls(self, mode=None):
        mode = str(mode or self.config.get('window_layer', 'normal')).lower()
        if mode not in {'top', 'normal', 'bottom'}:
            mode = 'normal'
        if hasattr(self, 'top_check'):
            self._set_checkbox_silent(self.top_check, mode == 'top')
        if hasattr(self, 'pin_top_btn'):
            self.pin_top_btn.blockSignals(True)
            self.pin_top_btn.setChecked(mode == 'top')
            self.pin_top_btn.blockSignals(False)
        if hasattr(self, 'pin_bottom_btn'):
            self.pin_bottom_btn.blockSignals(True)
            self.pin_bottom_btn.setChecked(mode == 'bottom')
            self.pin_bottom_btn.blockSignals(False)
        if hasattr(self, 'window_layer_state_lbl'):
            mode_text = '顶层' if mode == 'top' else '底层' if mode == 'bottom' else '普通'
            self.window_layer_state_lbl.setText(f'当前层级: {mode_text}')

    def _restart_visualizer_process(self):
        self._flush_pending_config()
        self._stop_visualizer()
        try:
            target = Path(__file__).resolve()
            launcher = target.parent / '启动.bat'
            if launcher.exists() and os.name == 'nt':
                os.startfile(str(launcher))
            elif launcher.exists():
                subprocess.Popen([str(launcher)], cwd=str(target.parent))
            else:
                subprocess.Popen([sys.executable, str(target)], cwd=str(target.parent))
        except Exception as e:
            QMessageBox.critical(self, '错误', f'重启程序失败: {e}')
            self._start_visualizer()
            return
        self.close()

    @staticmethod
    def _normalize_rgb(color):
        if not isinstance(color, (list, tuple)) or len(color) < 3:
            return None
        return tuple(int(channel) for channel in color[:3])

    def _apply_color_widget_style(self, widget, color, *, border='#aaa'):
        normalized = self._normalize_rgb(color)
        if widget is None or normalized is None:
            return
        current_style_key = widget.property('_aye_rgb_style')
        target_style_key = f'{normalized[0]},{normalized[1]},{normalized[2]}|{border}'
        if current_style_key == target_style_key:
            return
        widget.setProperty('_aye_rgb_style', target_style_key)
        widget.setStyleSheet(
            f"background:rgb({normalized[0]},{normalized[1]},{normalized[2]}); border:1px solid {border}; border-radius:2px;"
        )

    def _write_preset_file(self, fp: Path):
        save_data = self._build_full_preset_payload()
        with open(fp, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)

    @staticmethod
    def _make_palette_preview_entry(color, label, *, border='#666', tooltip='', target=None):
        return {
            'color': color,
            'label': label,
            'border': border,
            'tooltip': tooltip,
            'target': target,
        }

    def _build_palette_preview_entries(self):
        section_borders = {
            '颜色': '#5e88b0',
            '经典': '#b48d59',
            '填充': '#7ea560',
            '连线': '#4f9aa3',
            '柔体': '#a36f56',
        }
        entries = []
        scheme = self.config.get('color_scheme', 'rainbow')

        if scheme == 'custom':
            points = sorted(self.config.get('gradient_points', [(0.0, (255, 0, 128)), (1.0, (0, 255, 255))]), key=lambda item: item[0])
            for index, (pos, color) in enumerate(points[:3]):
                entries.append(self._make_palette_preview_entry(
                    color,
                    '颜色',
                    border=section_borders['颜色'],
                    tooltip=f'颜色方案 / 渐变控制点 {index + 1} / 位置 {pos:.2f}',
                    target={'kind': 'gradient', 'index': index},
                ))
        else:
            scheme_colors = self._generate_harmony_palette(3)
            for index, color in enumerate(scheme_colors[:3]):
                entries.append(self._make_palette_preview_entry(
                    color,
                    '颜色',
                    border=section_borders['颜色'],
                    tooltip=f'颜色方案 / 预设颜色 {index + 1}',
                    target={'kind': 'scheme'},
                ))

        c1 = self.config.get('c1_color', (255, 255, 255))
        c5 = self.config.get('c5_color', c1)
        line_preview_colors = self._build_spectrum_preview_colors([0, 0, 0, 0, 0])
        line_preview = line_preview_colors[min(2, len(line_preview_colors) - 1)] if line_preview_colors else c1
        tentacle_base = self.config.get('tentacle_color', (130, 240, 220))
        tentacle_tip = self.config.get('tentacle_shader_tip_color', tentacle_base)

        entries.extend([
            self._make_palette_preview_entry(
                c1,
                '经典',
                border=section_borders['经典'],
                tooltip='经典主题 / 主轮廓颜色',
                target={'kind': 'cfg', 'key': 'c1_color'},
            ),
            self._make_palette_preview_entry(
                c5,
                '填充',
                border=section_borders['填充'],
                tooltip='填充子主题 / 外层填充参考色',
                target={'kind': 'cfg', 'key': 'c5_color'},
            ),
            self._make_palette_preview_entry(
                line_preview,
                '连线',
                border=section_borders['连线'],
                tooltip='连线子主题 / 颜色跟随当前颜色方案',
                target={'kind': 'scheme'},
            ),
            self._make_palette_preview_entry(
                tentacle_base,
                '柔体',
                border=section_borders['柔体'],
                tooltip='柔体主题 / 触须主色',
                target={'kind': 'cfg', 'key': 'tentacle_color'},
            ),
            self._make_palette_preview_entry(
                tentacle_tip,
                '柔体',
                border=section_borders['柔体'],
                tooltip='柔体主题 / 触须尖端颜色',
                target={'kind': 'cfg', 'key': 'tentacle_shader_tip_color'},
            ),
        ])
        return entries[:8]

    def _set_palette_preview_colors(self, colors):
        if not hasattr(self, 'palette_preview_cells'):
            return
        entries = []
        for item in (colors or []):
            if isinstance(item, dict):
                normalized = self._normalize_rgb(item.get('color'))
                if normalized is None:
                    continue
                entry = dict(item)
                entry['color'] = normalized
                entries.append(entry)
            else:
                normalized = self._normalize_rgb(item)
                if normalized is not None:
                    entries.append(self._make_palette_preview_entry(normalized, '颜色'))
        while len(entries) < len(self.palette_preview_cells):
            entries.append(self._make_palette_preview_entry((60, 60, 60), ''))
        self._latest_palette_preview = [entry['color'] for entry in entries]
        self._latest_palette_preview_meta = list(entries)
        for idx, cell in enumerate(self.palette_preview_cells):
            entry = entries[idx]
            self._apply_color_widget_style(cell, entry['color'], border=entry.get('border', '#666'))
            tooltip = entry.get('tooltip') or ''
            cell.setToolTip(tooltip)
            if idx < len(getattr(self, 'palette_preview_labels', [])):
                label = self.palette_preview_labels[idx]
                label.setText(entry.get('label', ''))
                label.setToolTip(tooltip)

    @staticmethod
    def _make_color_button_style(color):
        return f"background:rgb({int(color[0])},{int(color[1])},{int(color[2])}); border:1px solid #aaa; border-radius:2px;"

    def _register_color_button(self, cfg_key: str, button: QPushButton | None):
        if not cfg_key or button is None:
            return button
        bucket = self._color_button_registry.setdefault(str(cfg_key), [])
        if button not in bucket:
            bucket.append(button)
        color = self._latest_runtime_color_state.get(str(cfg_key), self.config.get(cfg_key))
        self._apply_color_widget_style(button, color)
        return button

    def _set_registered_color_buttons(self, cfg_key: str, color, *, from_runtime=False):
        normalized = self._normalize_rgb(color)
        if normalized is None:
            return
        cfg_key = str(cfg_key)
        if from_runtime:
            self._latest_runtime_color_state[cfg_key] = normalized
        alive_buttons = []
        for button in self._color_button_registry.get(cfg_key, []):
            if button is None:
                continue
            try:
                self._apply_color_widget_style(button, normalized)
                alive_buttons.append(button)
            except RuntimeError:
                continue
        self._color_button_registry[cfg_key] = alive_buttons

    def _set_gradient_point_button_color(self, index: int, color, *, from_runtime=False):
        normalized = self._normalize_rgb(color)
        if normalized is None:
            return
        if from_runtime:
            while len(self._latest_gradient_point_colors) <= int(index):
                self._latest_gradient_point_colors.append(None)
            self._latest_gradient_point_colors[int(index)] = normalized
        if 0 <= int(index) < len(self._gradient_point_buttons):
            button = self._gradient_point_buttons[int(index)]
            if button is not None:
                self._apply_color_widget_style(button, normalized)

    def _apply_runtime_color_snapshot(self, snapshot):
        if not isinstance(snapshot, dict):
            return
        palette_preview = snapshot.get('palette_preview')
        if isinstance(palette_preview, list):
            self._set_palette_preview_colors(palette_preview)
        for cfg_key, color in snapshot.items():
            if cfg_key == 'gradient_points':
                continue
            self._set_registered_color_buttons(cfg_key, color, from_runtime=True)
        runtime_points = snapshot.get('gradient_points')
        if isinstance(runtime_points, list):
            for idx, point in enumerate(runtime_points):
                if not (isinstance(point, (list, tuple)) and len(point) >= 2):
                    continue
                self._set_gradient_point_button_color(idx, point[1], from_runtime=True)

    def _sync_drag_position_to_config(self):
        if not self.drag_adjust_check.isChecked():
            return
        pos_x = int(self.pos_x_spin.value())
        pos_y = int(self.pos_y_spin.value())
        if self.config.get('pos_x') == pos_x and self.config.get('pos_y') == pos_y:
            return
        self.config['pos_x'] = pos_x
        self.config['pos_y'] = pos_y
        if not self._applying_config:
            self._schedule_config_commit()

    def _apply_config_to_ui(self, cfg):
        d = _normalize_loaded_config(cfg)
        # 保留随机勾选状态，不被预设/复位覆盖
        d['random_checked'] = self.config.get('random_checked', [])

        self._applying_config = True
        # 跳过正在被用户编辑（有焦点）的 spinbox，避免打断输入
        _focused = QApplication.focusWidget()
        def _ssv(w, v):
            if w is not _focused:
                w.setValue(v)

        try:
            self.config = d
            self._sync_theme_enable_widgets()
            self._sync_window_layer_controls(d.get('window_layer', 'normal'))

            # 基础 UI
            self.master_visible_check.setChecked(d.get('master_visible', True))
            _ssv(self.scale_spin, d.get('global_scale', 1.0))
            _ssv(self.pos_x_spin, d.get('pos_x', -1)); _ssv(self.pos_y_spin, d.get('pos_y', -1))
            self.drag_adjust_check.setChecked(d.get('drag_adjust_mode', False))
            _ssv(self.bars_spin, d.get('num_bars', 64))
            schemes = ['rainbow', 'fire', 'ice', 'neon', 'custom']
            scheme = d.get('color_scheme', 'rainbow')
            self.color_combo.setCurrentIndex(schemes.index(scheme) if scheme in schemes else 0)
            _ssv(self.rotation_base_spin, float(d.get('rotation_base', 1.0)))
            _ssv(self.main_radius_scale_spin, float(d.get('main_radius_scale', 1.0)))
            _ssv(self.k_rise_damping_spin, float(d.get('k_rise_damping', 0.1)))
            _ssv(self.k_fall_damping_spin, float(d.get('k_fall_damping', 0.999)))
            self.bar_independent_time_window_check.setChecked(d.get('bar_use_independent_time_window', False))
            self.bar_independent_time_window_widget.setVisible(d.get('bar_use_independent_time_window', False))
            _ssv(self.bar_time_window_spin, float(d.get('bar_time_window', d.get('a1_time_window', 10.0))))
            self.bar_independent_damping_check.setChecked(d.get('bar_use_independent_damping', False))
            self.bar_independent_damping_widget.setVisible(d.get('bar_use_independent_damping', False))
            _ssv(self.bar_independent_rise_damping_spin, float(d.get('bar_independent_rise_damping', 0.1)))
            _ssv(self.bar_independent_fall_damping_spin, float(d.get('bar_independent_fall_damping', 0.999)))
            _ssv(self.bar_default_height_spin, float(d.get('bar_default_height', 0.0)))
            _ssv(self.bar_internal_min_spin, float(d.get('bar_internal_min', 0.0)))
            _ssv(self.bar_internal_max_spin, float(d.get('bar_internal_max', 300.0)))
            _ssv(self.hmin_spin, d.get('bar_height_min', 0)); _ssv(self.hmax_spin, d.get('bar_height_max', 500))
            _ssv(self.radius_spin, d.get('circle_radius', 150)); _ssv(self.seg_spin, d.get('circle_segments', 1))
            self.a1rot_check.setChecked(d.get('circle_a1_rotation', True)); self.a1rad_check.setChecked(d.get('circle_a1_radius', True))
            self.rdamp_slider.setValue(int(d.get('radius_damping', 0.92) * 100))
            self.rspring_slider.setValue(int(d.get('radius_spring', 0.15) * 100))
            self.rgrav_slider.setValue(int(d.get('radius_gravity', 0.3) * 100))
            _ssv(self.freq_min_spin, d.get('freq_min', 20)); _ssv(self.freq_max_spin, d.get('freq_max', 20000))
            _ssv(self.bar_len_min_spin, d.get('bar_length_min', 0)); _ssv(self.bar_len_max_spin, d.get('bar_length_max', 300))
            _ssv(self.a1_spin, d.get('a1_time_window', 10.0))
            self.k2_check.setChecked(d.get('k2_enabled', False))
            _ssv(self.k2_pow_spin, d.get('k2_pow', 1.0))

            # 预设自动切换
            self.preset_auto_check.setChecked(d.get('preset_auto_switch', False))
            self.preset_switch_random_check.setChecked(d.get('preset_switch_random_enabled', False))
            self.preset_switch_infinite_random_check.setChecked(d.get('preset_switch_infinite_random_enabled', False))
            _ssv(self.preset_interval_spin, float(d.get('preset_switch_interval', 10.0)))
            self.preset_interval_random_check.setChecked(d.get('preset_interval_random_enabled', False))
            _ssv(self.preset_interval_min_spin, float(d.get('preset_switch_interval_min', 1.0)))
            _ssv(self.preset_interval_max_spin, float(d.get('preset_switch_interval_max', 10.0)))
            self._update_preset_interval_mode_ui()
            # 过渡动画
            self.preset_transition_check.setChecked(d.get('preset_transition_enabled', False))
            _ssv(self.preset_transition_duration_spin, float(d.get('preset_transition_duration', 2.0)))
            self.preset_transition_ctrl.setVisible(d.get('preset_transition_enabled', False))
            self._update_preset_preview()
            if hasattr(self, 'random_obj_min_spin'):
                _ssv(self.random_obj_min_spin, int(d.get('random_object_count_min', 1)))
            if hasattr(self, 'random_obj_max_spin'):
                _ssv(self.random_obj_max_spin, int(d.get('random_object_count_max', 10)))

            # 颜色/渐变
            self.grad_check.setChecked(d.get('gradient_enabled', True))
            self.grad_mode_combo.setCurrentIndex(0 if d.get('gradient_mode', 'frequency') == 'frequency' else 1)
            self.dyn_check.setChecked(d.get('color_dynamic', False))
            self.cyc_spd_slider.setValue(int(d.get('color_cycle_speed', 1.0) * 100))
            self.cyc_pow_slider.setValue(int(d.get('color_cycle_pow', 2.0) * 100))
            self.cyc_a1_check.setChecked(d.get('color_cycle_a1', True))
            self.color_dynamic_quick_check.setChecked(d.get('color_dynamic', False))
            _ssv(self.color_cycle_speed_quick_spin, float(d.get('color_cycle_speed', 1.0)))
            _ssv(self.color_cycle_pow_quick_spin, float(d.get('color_cycle_pow', 2.0)))
            self.color_cycle_a1_quick_check.setChecked(d.get('color_cycle_a1', True))
            self._rebuild_gradient_ui()

            # 五层轮廓
            for li in range(1, 6):
                getattr(self, f'c{li}_on_check').setChecked(d.get(f'c{li}_on', False))
                cc = d.get(f'c{li}_color', (255, 255, 255))
                getattr(self, f'c{li}_color_btn').setStyleSheet(
                    f"background:rgb({cc[0]},{cc[1]},{cc[2]}); border:1px solid #aaa; border-radius:2px;")
                _ssv(getattr(self, f'c{li}_thick_spin'), d.get(f'c{li}_thick', 2))
                getattr(self, f'c{li}_alpha_slider').setValue(d.get(f'c{li}_alpha', 180))
                getattr(self, f'c{li}_fill_check').setChecked(d.get(f'c{li}_fill', False))
                getattr(self, f'c{li}_fill_alpha_slider').setValue(d.get(f'c{li}_fill_alpha', 50))
                if hasattr(self, f'c{li}_step_spin'):
                    _ssv(getattr(self, f'c{li}_step_spin'), d.get(f'c{li}_step', 2))
                if hasattr(self, f'c{li}_decay_slider'):
                    getattr(self, f'c{li}_decay_slider').setValue(int(d.get(f'c{li}_decay', 0.995) * 1000))
                if li in (1, 2, 4, 5):
                    getattr(self, f'c{li}_independent_damping_check').setChecked(d.get(f'c{li}_use_independent_damping', False))
                    getattr(self, f'c{li}_independent_damping_widget').setVisible(d.get(f'c{li}_use_independent_damping', False))
                    _ssv(getattr(self, f'c{li}_independent_rise_damping_spin'), float(d.get(f'c{li}_independent_rise_damping', 0.1)))
                    _ssv(getattr(self, f'c{li}_independent_fall_damping_spin'), float(d.get(f'c{li}_independent_fall_damping', 0.999)))
                getattr(self, f'c{li}_rot_speed_slider').setValue(int(d.get(f'c{li}_rot_speed', 1.0) * 100))
                getattr(self, f'c{li}_rot_pow_slider').setValue(int(d.get(f'c{li}_rot_pow', 0.5) * 100))

            # 四层条形
            for key in ('b12', 'b23', 'b34', 'b45'):
                getattr(self, f'{key}_on_check').setChecked(d.get(f'{key}_on', False))
                _ssv(getattr(self, f'{key}_thick_spin'), d.get(f'{key}_thick', 3))
                getattr(self, f'{key}_fixed_check').setChecked(d.get(f'{key}_fixed', False))
                _ssv(getattr(self, f'{key}_fixed_len_spin'), d.get(f'{key}_fixed_len', 30))
                getattr(self, f'{key}_start_check').setChecked(d.get(f'{key}_from_start', True))
                getattr(self, f'{key}_end_check').setChecked(d.get(f'{key}_from_end', False))
                getattr(self, f'{key}_center_check').setChecked(d.get(f'{key}_from_center', False))
                getattr(self, f'{key}_mode_widget').setVisible(d.get(f'{key}_fixed', False))
                getattr(self, f'{key}_independent_damping_check').setChecked(d.get(f'{key}_use_independent_damping', False))
                getattr(self, f'{key}_independent_damping_widget').setVisible(d.get(f'{key}_use_independent_damping', False))
                _ssv(getattr(self, f'{key}_independent_rise_damping_spin'), float(d.get(f'{key}_independent_rise_damping', 0.1)))
                _ssv(getattr(self, f'{key}_independent_fall_damping_spin'), float(d.get(f'{key}_independent_fall_damping', 0.999)))

            tc = d.get('tentacle_color', (130, 240, 220))
            self._set_registered_color_buttons('tentacle_color', tc)
            _ssv(self.tentacle_thick_spin, d.get('tentacle_thick', 3))
            self.tentacle_alpha_slider.setValue(d.get('tentacle_alpha', 170))
            self.tentacle_count_slider.setValue(d.get('tentacle_count', 16))
            self.tentacle_length_slider.setValue(int(round(float(d.get('tentacle_length', 280.0)) * 10)))
            self.tentacle_length_jitter_slider.setValue(int(round(float(d.get('tentacle_length_jitter', 80.0)) * 10)))
            if hasattr(self, 'tentacle_length_jitter_speed_slider'):
                self.tentacle_length_jitter_speed_slider.setValue(int(round(float(d.get('tentacle_length_jitter_speed', 0.35)) * 100)))
            if hasattr(self, 'tentacle_length_jitter_random_check'):
                self.tentacle_length_jitter_random_check.setChecked(bool(d.get('tentacle_length_jitter_random', False)))
            _ssv(self.tentacle_cp_min_spin, d.get('tentacle_control_points_min', 3))
            _ssv(self.tentacle_cp_max_spin, d.get('tentacle_control_points_max', 5))
            self.tentacle_tip_bias_slider.setValue(int(round(float(d.get('tentacle_tip_bias', 1.85)) * 100)))
            self.tentacle_tip_thickness_slider.setValue(int(round(float(d.get('tentacle_tip_thickness', 0.15)) * 100)))
            self.tentacle_turbulence_slider.setValue(int(round(float(d.get('tentacle_turbulence', 46.0)) * 10)))
            if hasattr(self, 'kp_tentacle_turbulence_k_wmin_spin'):
                _ssv(self.kp_tentacle_turbulence_k_wmin_spin, float(d.get('kp_tentacle_turbulence_k_wmin', 0.22)))
            if hasattr(self, 'kp_tentacle_turbulence_k_wmax_spin'):
                _ssv(self.kp_tentacle_turbulence_k_wmax_spin, float(d.get('kp_tentacle_turbulence_k_wmax', 0.683)))
            self.tentacle_sway_speed_slider.setValue(int(round(float(d.get('tentacle_sway_speed', 1.1)) * 100)))
            self.tentacle_sway_density_slider.setValue(int(round(float(d.get('tentacle_sway_density', 2.4)) * 100)))
            self.tentacle_water_damping_slider.setValue(int(round(float(d.get('tentacle_water_damping', 0.84)) * 1000)))
            self.tentacle_angle_stiffness_slider.setValue(int(round(float(d.get('tentacle_angle_stiffness', 0.18)) * 100)))
            self.tentacle_length_stiffness_slider.setValue(int(round(float(d.get('tentacle_length_stiffness', 0.24)) * 100)))
            self.tentacle_stretch_limit_slider.setValue(int(round(float(d.get('tentacle_stretch_limit', 1.12)) * 100)))
            self.tentacle_shader_check.setChecked(d.get('tentacle_shader_enabled', True))
            tsc = d.get('tentacle_shader_tip_color', (88, 170, 255))
            self._set_registered_color_buttons('tentacle_shader_tip_color', tsc)
            self.tentacle_shader_alpha_start_slider.setValue(int(round(float(d.get('tentacle_shader_alpha_start', 1.0)) * 100)))
            self.tentacle_shader_alpha_end_slider.setValue(int(round(float(d.get('tentacle_shader_alpha_end', 0.18)) * 100)))
            self.tentacle_shader_bias_slider.setValue(int(round(float(d.get('tentacle_shader_bias', 1.15)) * 100)))
            self.tentacle_core_on_check.setChecked(d.get('tentacle_core_on', True))
            self.tentacle_core_base_speed_slider.setValue(int(round(float(d.get('tentacle_core_base_speed', 0.75)) * 100)))
            if hasattr(self, 'kp_tentacle_core_base_speed_k_wmin_spin'):
                _ssv(self.kp_tentacle_core_base_speed_k_wmin_spin, float(d.get('kp_tentacle_core_base_speed_k_wmin', 0.0)))
            if hasattr(self, 'kp_tentacle_core_base_speed_k_wmax_spin'):
                _ssv(self.kp_tentacle_core_base_speed_k_wmax_spin, float(d.get('kp_tentacle_core_base_speed_k_wmax', 1.2)))
            if hasattr(self, 'kp_tentacle_core_base_speed_p_wmin_spin'):
                _ssv(self.kp_tentacle_core_base_speed_p_wmin_spin, float(d.get('kp_tentacle_core_base_speed_p_wmin', 0.0)))
            if hasattr(self, 'kp_tentacle_core_base_speed_p_wmax_spin'):
                _ssv(self.kp_tentacle_core_base_speed_p_wmax_spin, float(d.get('kp_tentacle_core_base_speed_p_wmax', 1.35)))

            # K/P 绑定：统一回填权重范围，并刷新显隐/高亮
            if hasattr(self, '_kp_binding_meta'):
                for _cfg_key, _meta in self._kp_binding_meta.items():
                    _weight_spins = _meta.get('weight_spins') or {}
                    for _sig, (_wmin_spin, _wmax_spin) in _weight_spins.items():
                        _ssv(_wmin_spin, float(d.get(self._kp_wmin_key(_cfg_key, _sig), _wmin_spin.value())))
                        _ssv(_wmax_spin, float(d.get(self._kp_wmax_key(_cfg_key, _sig), _wmax_spin.value())))
                    if hasattr(self, '_update_kp_binding_ui'):
                        self._update_kp_binding_ui(_cfg_key)
        finally:
            self._applying_config = False

            self._sync_color_quick_widgets(d.get('color_dynamic', False))
        self._update_color_preview_strip()
        self._refresh_single_bar_preview()
        self._refresh_unity_export_suggestion()
        self._save_config()
        if self.preset_auto_check.isChecked():
            self._schedule_next_preset_switch()
        else:
            self.preset_timer.stop()
        if self.viz_process and self.viz_process.is_alive():
            self._send_config()

    def _reset_all(self):
        if QMessageBox.question(self, "确认", "确定要将所有参数复位到默认值吗？",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        self._apply_config_to_ui(_get_defaults())

    def _update_status(self):
        if not self.status_queue:
            return
        try:
            while not self.status_queue.empty():
                st = self.status_queue.get_nowait()
                if 'raw_k' in st:
                    self.current_raw_a1 = st['raw_k']
                if 'k' in st:
                    self.current_a1 = st['k']
                    self.a1_lbl.setText(f"{self.current_a1:.2f}")
                elif 'a1' in st:
                    self.current_a1 = st['a1']
                    self.a1_lbl.setText(f"{self.current_a1:.2f}")
                if 'p' in st:
                    self.current_p = st['p']
                    self.k2_lbl.setText(f"{self.current_p:.2f}")
                elif 'k2' in st:
                    self.current_p = st['k2']
                    self.k2_lbl.setText(f"{self.current_p:.2f}")
                if 'spectrum_bars' in st:
                    self.preview_spectrum_values = list(st['spectrum_bars'])
                if 'color_preview' in st:
                    self.preview_dynamic_colors = [tuple(color) for color in st['color_preview']]
                if 'runtime_color_state' in st:
                    self._apply_runtime_color_snapshot(st['runtime_color_state'])
                if 'color_cycle_hue' in st:
                    self.current_color_cycle_hue = float(st['color_cycle_hue'])
                if 'color_cycle_rate' in st:
                    self.current_color_cycle_rate = float(st['color_cycle_rate'])
                if 'drag_adjust_mode' in st and self.drag_adjust_check.isChecked() != bool(st['drag_adjust_mode']):
                    self.drag_adjust_check.setChecked(bool(st['drag_adjust_mode']))
                if 'pos_x' in st and 'pos_y' in st:
                    # 只有在用户没有聚焦pos控件时才更新显示，避免干扰用户输入
                    if not (self.pos_x_spin.hasFocus() or self.pos_y_spin.hasFocus()):
                        self.pos_x_spin.blockSignals(True)
                        self.pos_y_spin.blockSignals(True)
                        self.pos_x_spin.setValue(st['pos_x'])
                        self.pos_y_spin.setValue(st['pos_y'])
                        self.pos_x_spin.blockSignals(False)
                        self.pos_y_spin.blockSignals(False)
                        self._sync_drag_position_to_config()
                self._refresh_single_bar_preview()
        except:
            pass

    def closeEvent(self, event):
        self._sync_drag_position_to_config()
        self._flush_pending_config()
        self._stop_visualizer()
        event.accept()


# ═══════════════════════════════════════════════════════════
#  子进程入口
# ═══════════════════════════════════════════════════════════

def _run_circular(config_queue, status_queue):
    """在子进程中启动圆形频谱"""
    try:
        import importlib.util, os
        spec = importlib.util.spec_from_file_location(
            "circular_visualizer",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "1.pyw")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.run_from_main(config_queue, status_queue)
    except Exception as e:
        print(f"子进程错误: {e}")
        import traceback
        traceback.print_exc()


def main():
    mp.set_start_method('spawn', force=True)
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    # 应用自定义复选框指示器样式（灰框透明底 + 黄色勾）
    app.setStyle(_YellowCheckBoxStyle(app.style()))
    pal = app.palette()
    _hi = pal.color(QPalette.ColorRole.Highlight)
    # 仅保留尺寸设置，绘制交给 _YellowCheckBoxStyle
    app.setStyleSheet("""
        QCheckBox::indicator { width: 15px; height: 15px; }
    """)
    w = VisualizerControlUI()
    w.show()
    # show 后再居中，确保 frameGeometry 含标题栏
    fg = w.frameGeometry()
    screen_geo = QApplication.primaryScreen().availableGeometry()
    fg.moveCenter(screen_geo.center())
    w.move(fg.topLeft())
    sys.exit(app.exec())



# ============================================================================
# 以下内容由 _merge_viz.py 从 1.pyw 合并（OpenGL 渲染器类）
# ============================================================================
_ON_FIELD_ORDER = [
    "c1_on", "c2_on", "c3_on", "c4_on", "c5_on",
    "b12_on", "b23_on", "b34_on", "b45_on",
    "tentacle_on", "tentacle_core_on"
]

_NOINTERP_KEYS = frozenset({
    "color_scheme", "gradient_mode", "gradient_points",
    "num_bars",
    "contours_enabled", "bars_enabled", "tentacles_enabled",
    "c1_on", "c2_on", "c3_on", "c4_on", "c5_on",
    "b12_on", "b23_on", "b34_on", "b45_on",
    "tentacle_on", "tentacle_core_on",
    "master_visible",
    "gradient_enabled", "color_dynamic", "circle_a1_rotation", "circle_a1_radius",
    "tentacle_shader_enabled",
    "k2_enabled", "color_cycle_a1", "drag_adjust_mode", "always_on_top", "bg_transparent", "window_layer",
    "bar_use_independent_damping", "bar_use_independent_time_window",
    "c1_fill", "c2_fill", "c3_fill", "c4_fill", "c5_fill",
    "c1_use_independent_damping", "c2_use_independent_damping",
    "c4_use_independent_damping", "c5_use_independent_damping",
    "b12_use_independent_damping", "b23_use_independent_damping",
    "b34_use_independent_damping", "b45_use_independent_damping",
    "b12_fixed", "b23_fixed", "b34_fixed", "b45_fixed",
    "b12_from_start", "b12_from_end", "b12_from_center",
    "b23_from_start", "b23_from_end", "b23_from_center",
    "b34_from_start", "b34_from_end", "b34_from_center",
    "b45_from_start", "b45_from_end", "b45_from_center",
    "pos_x", "pos_y", "width", "height",
    "lens_scratch_enabled", "lens_scratch_mask_path", "lens_scratch_normal_path",
    "preset_order", "preset_auto_switch", "preset_switch_interval",
    "preset_interval_random_enabled", "preset_switch_interval_min", "preset_switch_interval_max",
    "preset_transition_enabled", "preset_transition_duration", "preset_transition_easing",
    "random_checked", "random_object_count_min", "random_object_count_max",
})


def _ease_value(t, mode):
    t = max(0.0, min(1.0, t))
    if mode == "ease_in":
        return t * t
    if mode == "ease_out":
        return 1.0 - (1.0 - t) ** 2
    if mode == "ease_in_out":
        return t * t * (3.0 - 2.0 * t)
    if mode == "cubic":
        return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)
    return t


def _sample_gradient_color(points, ratio):
    normalized = []
    for entry in (points or []):
        if not (isinstance(entry, (list, tuple)) and len(entry) >= 2):
            continue
        pos, color = entry[0], entry[1]
        if not isinstance(color, (list, tuple)) or len(color) < 3:
            continue
        try:
            normalized.append((float(pos), (int(color[0]), int(color[1]), int(color[2]))))
        except Exception:
            continue
    if not normalized:
        return (255, 255, 255)
    normalized.sort(key=lambda item: item[0])
    ratio = max(0.0, min(1.0, float(ratio)))
    for index in range(len(normalized) - 1):
        pos1, color1 = normalized[index]
        pos2, color2 = normalized[index + 1]
        if pos1 <= ratio <= pos2:
            blend = (ratio - pos1) / (pos2 - pos1) if pos2 > pos1 else 0.0
            return tuple(
                int(round(color1[channel] + (color2[channel] - color1[channel]) * blend))
                for channel in range(3)
            )
    return normalized[0][1] if ratio <= normalized[0][0] else normalized[-1][1]


def _interpolate_gradient_points(from_points, to_points, ratio, count=8):
    steps = max(2, int(count))
    blended = []
    for index in range(steps):
        pos = index / max(1, steps - 1)
        from_color = _sample_gradient_color(from_points, pos)
        to_color = _sample_gradient_color(to_points, pos)
        blended.append((
            pos,
            tuple(
                int(round(from_color[channel] + (to_color[channel] - from_color[channel]) * ratio))
                for channel in range(3)
            )
        ))
    return blended


def _load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as file_obj:
            return _normalize_loaded_config(json.load(file_obj))
    except Exception:
        return _normalize_loaded_config(None)


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
        # 镜头划痕后处理
        self._scratch_gl = LensScratchGL()
        self._scratch_fbo: int = 0
        self._scratch_tex: int = 0
        self._scratch_fbo_size: tuple[int, int] = (0, 0)

    def _framebuffer_size(self):
        dpr = max(1.0, float(self.devicePixelRatioF()))
        fb_width = max(1, int(round(self.width() * dpr)))
        fb_height = max(1, int(round(self.height() * dpr)))
        return fb_width, fb_height

    def initializeGL(self):
        GL.glClearColor(0.0, 0.0, 0.0, 0.0)
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        GL.glEnable(GL.GL_LINE_SMOOTH)
        GL.glHint(GL.GL_LINE_SMOOTH_HINT, GL.GL_NICEST)
        GL.glEnable(GL.GL_MULTISAMPLE)
        self._scratch_gl.initialize()

    def _ensure_scratch_fbo(self, fb_width: int, fb_height: int) -> None:
        """确保 FBO 和纹理的尺寸与当前帧缓冲一致。"""
        if (fb_width, fb_height) == self._scratch_fbo_size:
            return
        # 释放旧资源
        if self._scratch_fbo:
            GL.glDeleteFramebuffers(1, [self._scratch_fbo])
        if self._scratch_tex:
            GL.glDeleteTextures(1, [self._scratch_tex])
        # 创建离屏纹理（RGBA8，4 级 mip 便于 LOD 采样）
        tex = int(GL.glGenTextures(1))
        GL.glBindTexture(GL.GL_TEXTURE_2D, tex)
        GL.glTexImage2D(
            GL.GL_TEXTURE_2D, 0, GL.GL_RGBA8, fb_width, fb_height, 0,
            GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, None,
        )
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR_MIPMAP_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        # 创建 FBO
        fbo = int(GL.glGenFramebuffers(1))
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, fbo)
        GL.glFramebufferTexture2D(
            GL.GL_FRAMEBUFFER, GL.GL_COLOR_ATTACHMENT0, GL.GL_TEXTURE_2D, tex, 0,
        )
        status = GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER)
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
        if status != GL.GL_FRAMEBUFFER_COMPLETE:
            GL.glDeleteFramebuffers(1, [fbo])
            GL.glDeleteTextures(1, [tex])
            print(f"[LensScratchGL] FBO 创建失败: status=0x{status:X}")
            return
        self._scratch_fbo = fbo
        self._scratch_tex = tex
        self._scratch_fbo_size = (fb_width, fb_height)

    def resizeGL(self, width, height):
        fb_width, fb_height = self._framebuffer_size()
        GL.glViewport(0, 0, fb_width, fb_height)

    def paintGL(self):
        state = self.owner.render_state
        logical_width = max(1.0, float(self.width()))
        logical_height = max(1.0, float(self.height()))
        fb_width, fb_height = self._framebuffer_size()

        cfg = self.owner.config
        scratch_enabled = bool(cfg.get("lens_scratch_enabled", False))
        use_scratch = scratch_enabled and self._scratch_gl.ready

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        # beginNativePainting 必须在所有 raw GL 调用之前
        painter.beginNativePainting()

        # QOpenGLWidget 的默认 FBO 不一定是 0，必须在 GL 上下文激活后查询
        default_fbo = GL.glGetIntegerv(GL.GL_FRAMEBUFFER_BINDING)

        if use_scratch:
            self._ensure_scratch_fbo(fb_width, fb_height)
            if self._scratch_fbo:
                GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self._scratch_fbo)
            else:
                use_scratch = False

        GL.glViewport(0, 0, fb_width, fb_height)
        clear_alpha = 0.0 if cfg.get("bg_transparent", True) else 1.0
        GL.glClearColor(0.0, 0.0, 0.0, clear_alpha)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)

        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glLoadIdentity()
        GL.glOrtho(0.0, logical_width, logical_height, 0.0, -1.0, 1.0)

        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glLoadIdentity()

        GL.glFlush()
        if state:
            center = state.get("center", (logical_width * 0.5, logical_height * 0.5))
            for fill_item in state.get("fills", []):
                self.owner._gl_draw_radial_fill(center, fill_item["points"], fill_item["color"])
            GL.glFlush()

        if use_scratch and self._scratch_fbo:
            # 切回默认 FBO，为划痕着色器生成 mipmap，然后应用效果
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, default_fbo)
            GL.glViewport(0, 0, fb_width, fb_height)
            GL.glBindTexture(GL.GL_TEXTURE_2D, self._scratch_tex)
            GL.glGenerateMipmap(GL.GL_TEXTURE_2D)
            GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
            normalized_k = max(0.0, min(1.0, float(self.owner.a1_value)))
            scratch_params = self._build_scratch_params(cfg, fb_width, fb_height, normalized_k)
            mask_p = cfg.get("lens_scratch_mask_path", "")
            norm_p = cfg.get("lens_scratch_normal_path", "")
            if mask_p:
                self._scratch_gl.load_mask(mask_p)
            if norm_p:
                self._scratch_gl.load_normal(norm_p)
            self._scratch_gl.apply(self._scratch_tex, scratch_params)

        painter.endNativePainting()

        if state:
            for tentacle_item in state.get("tentacles", []):
                self.owner._paint_weighted_segments(painter, tentacle_item["segments"])

            for bar_item in state.get("bars", []):
                self.owner._paint_segments(painter, bar_item["segments"], bar_item["thickness"])

            for line_item in state.get("lines", []):
                self.owner._paint_line_loop(painter, line_item["points"], line_item["color"], line_item["thickness"])

        painter.end()

    def _build_scratch_params(self, cfg: dict, fb_w: int, fb_h: int, normalized_k: float) -> dict:
        """从配置中读取划痕参数，应用 KP 绑定后返回 params dict。"""
        def _kp(key: str, base: float) -> float:
            if cfg.get(f"kp_bind_{key}_k", False):
                wmin = float(cfg.get(f"kp_{key}_k_wmin", 0.0))
                wmax = float(cfg.get(f"kp_{key}_k_wmax", 0.0))
                base += wmin + (wmax - wmin) * normalized_k
            return base

        return {
            "width": fb_w,
            "height": fb_h,
            "scratch_rotation_deg": float(cfg.get("lens_scratch_rotation_deg", 0.0)),
            "scratch_tiling_x": float(cfg.get("lens_scratch_tiling_x", 1.0)),
            "scratch_tiling_y": float(cfg.get("lens_scratch_tiling_y", 1.0)),
            "scratch_offset_x": float(cfg.get("lens_scratch_offset_x", 0.0)),
            "scratch_offset_y": float(cfg.get("lens_scratch_offset_y", 0.0)),
            "scratch_mask_power": float(cfg.get("lens_scratch_mask_power", 1.35)),
            "normal_influence": float(cfg.get("lens_scratch_normal_influence", 1.2)),
            "threshold": _kp("lens_scratch_threshold", float(cfg.get("lens_scratch_threshold", 1.1))),
            "soft_knee": float(cfg.get("lens_scratch_soft_knee", 0.45)),
            "glare_intensity": _kp("lens_scratch_glare_intensity", float(cfg.get("lens_scratch_glare_intensity", 1.15))),
            "streak_length": _kp("lens_scratch_streak_length", float(cfg.get("lens_scratch_streak_length", 3.6))),
            "count_a": int(cfg.get("lens_scratch_count_a", 20)),
            "streak_spread": float(cfg.get("lens_scratch_streak_spread", 1.1)),
            "falloff_a": float(cfg.get("lens_scratch_falloff_a", 3.8)),
            "falloff_b": float(cfg.get("lens_scratch_falloff_b", 0.35)),
            "scratch_count": int(cfg.get("lens_scratch_scratch_count", 3)),
            "streak_count": int(cfg.get("lens_scratch_streak_count", 3)),
            "rotation_jitter_deg": float(cfg.get("lens_scratch_rotation_jitter_deg", 6.0)),
            "refraction_strength": _kp("lens_scratch_refraction_strength", float(cfg.get("lens_scratch_refraction_strength", 0.18))),
            "chromatic_aberration": _kp("lens_scratch_chromatic_aberration", float(cfg.get("lens_scratch_chromatic_aberration", 0.0025))),
            "micro_distortion": float(cfg.get("lens_scratch_micro_distortion", 0.55)),
            "tint_r": int(cfg.get("lens_scratch_tint_r", 255)),
            "tint_g": int(cfg.get("lens_scratch_tint_g", 255)),
            "tint_b": int(cfg.get("lens_scratch_tint_b", 255)),
            "mip_levels": 4.0,
        }


class PainterVisualizerWidget(QWidget):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)

    def paintEvent(self, _event):
        pw, ph = self.width(), self.height()
        if pw <= 0 or ph <= 0:
            return

        state = self.owner.render_state
        cfg = self.owner.config
        scratch_enabled = bool(cfg.get("lens_scratch_enabled", False))
        bg_transparent = bool(cfg.get("bg_transparent", True))

        if scratch_enabled:
            # 渲染到离屏缓冲，供后处理使用
            offscreen = QImage(pw, ph, QImage.Format.Format_RGBA8888)
            offscreen.fill(QColor(0, 0, 0, 0) if bg_transparent else QColor(0, 0, 0, 255))
            painter = QPainter(offscreen)
        else:
            painter = QPainter(self)
            if bg_transparent:
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
                painter.fillRect(self.rect(), QColor(0, 0, 0, 0))
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            else:
                painter.fillRect(self.rect(), QColor(0, 0, 0, 255))

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        if state:
            for fill_item in state.get("fills", []):
                self.owner._paint_fill(painter, fill_item["points"], fill_item["color"])
            for tentacle_item in state.get("tentacles", []):
                self.owner._paint_weighted_segments(painter, tentacle_item["segments"])
            for bar_item in state.get("bars", []):
                self.owner._paint_segments(painter, bar_item["segments"], bar_item["thickness"])
            for line_item in state.get("lines", []):
                self.owner._paint_line_loop(painter, line_item["points"], line_item["color"], line_item["thickness"])

        painter.end()

        if scratch_enabled:
            # 应用 Unity LensScratchGlareAdvanced 三段式眩光效果（预滤波→条纹→合成）
            result_img = self._apply_lens_scratch_glare(offscreen, cfg)
            final_painter = QPainter(self)
            if bg_transparent:
                final_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
                final_painter.fillRect(self.rect(), QColor(0, 0, 0, 0))
                final_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            else:
                final_painter.fillRect(self.rect(), QColor(0, 0, 0, 255))
            final_painter.drawImage(0, 0, result_img)
            final_painter.end()

    def _apply_lens_scratch_glare(self, scene_image: QImage, cfg: dict) -> QImage:
        """
        Unity LensScratchGlareAdvanced 三段式镜头划痕眩光效果的 Python 移植版本。

        Pass 0 (预滤波): 提取超过阈值的高亮像素 → 半分辨率
        Pass 1 (条纹):   两个方向的定向模糊（streak blur）
        Pass 2 (合成):   将眩光叠加回原始场景
        """
        w, h = scene_image.width(), scene_image.height()
        if w <= 0 or h <= 0:
            return scene_image

        # ── 读取参数（对应 Unity LensScratchGlareAdvanced 参数）──────────
        normalized_k = max(0.0, min(1.0, float(self.owner.a1_value)))

        base_intensity = float(cfg.get("lens_scratch_glare_intensity", 1.25))
        if cfg.get("kp_bind_lens_scratch_glare_intensity_k", False):
            wmin = float(cfg.get("kp_lens_scratch_glare_intensity_k_wmin", 0.0))
            wmax = float(cfg.get("kp_lens_scratch_glare_intensity_k_wmax", 0.0))
            base_intensity += wmin + (wmax - wmin) * normalized_k
        base_intensity = max(0.0, base_intensity)

        threshold = float(cfg.get("lens_scratch_threshold", 1.1))
        soft_knee = max(1e-4, float(cfg.get("lens_scratch_soft_knee", 0.5)))

        streak_length = float(cfg.get("lens_scratch_streak_length", 3.5))
        if cfg.get("kp_bind_lens_scratch_streak_length_k", False):
            wmin = float(cfg.get("kp_lens_scratch_streak_length_k_wmin", 0.0))
            wmax = float(cfg.get("kp_lens_scratch_streak_length_k_wmax", 0.0))
            streak_length += wmin + (wmax - wmin) * normalized_k

        spread = max(0.01, float(cfg.get("lens_scratch_streak_spread", 1.25)))
        falloff = max(0.01, float(cfg.get("lens_scratch_falloff_a", 3.5)))
        scratch1_angle = float(cfg.get("lens_scratch_rotation_deg", 90.0))
        scratch1_intensity = base_intensity
        scratch2_intensity = base_intensity * 0.64  # 副方向强度为主方向的 64%
        composite_intensity = base_intensity

        tint_r = float(cfg.get("lens_scratch_tint_r", 255)) / 255.0
        tint_g = float(cfg.get("lens_scratch_tint_g", 255)) / 255.0
        tint_b = float(cfg.get("lens_scratch_tint_b", 255)) / 255.0
        tint = np.array([tint_r, tint_g, tint_b], dtype=np.float32)

        # ── 将 QImage 转换为 numpy 数组 ───────────────────────────────────
        scene_image = scene_image.convertToFormat(QImage.Format.Format_RGBA8888)
        bpl = scene_image.bytesPerLine()
        ptr = scene_image.constBits()
        raw = np.frombuffer(ptr, dtype=np.uint8).reshape(h, bpl)
        scene_np = raw[:, : w * 4].reshape(h, w, 4).copy()

        # ── Pass 0: 预滤波（1/4 分辨率，对应 Unity frag_prefilter）──────
        sh, sw = max(1, h // 4), max(1, w // 4)
        # 2x 双步降采样（快速近似）
        small_rgb = scene_np[::4, ::4, :3][:sh, :sw].astype(np.float32)
        # 用 alpha 预乘，避免透明区域产生杂散条纹
        small_a = scene_np[::4, ::4, 3:4][:sh, :sw].astype(np.float32) / 255.0
        small_rgb = (small_rgb / 255.0) * small_a  # premultiplied [0,1]

        # 提取高亮区（soft knee，对应 Unity frag_prefilter）
        brightness = np.max(small_rgb, axis=2)  # (sh, sw)
        knee = soft_knee
        soft = np.clip((brightness - threshold + knee) / (2.0 * knee), 0.0, 1.0)
        soft = soft * soft * knee
        contrib = np.maximum(soft, brightness - threshold)
        safe_b = np.where(brightness > 1e-4, brightness, 1.0)
        scale = np.where(brightness > 1e-4, contrib / safe_b, 0.0)
        prefiltered = small_rgb * scale[:, :, np.newaxis]  # (sh, sw, 3)

        # ── Pass 1: 两个方向的条纹模糊（对应 Unity frag_streak）─────────
        def compute_glare_dir(angle_deg: float) -> tuple[float, float]:
            """对应 Unity ComputeGlareDirection：返回与划痕角度垂直的方向。"""
            rad = math.radians(angle_deg)
            dx, dy = -math.sin(rad), math.cos(rad)
            length = math.sqrt(dx * dx + dy * dy)
            if length > 0:
                dx, dy = dx / length, dy / length
            return dx, dy

        def streak_blur(src: np.ndarray, dx: float, dy: float, intensity: float) -> np.ndarray:
            """
            定向条纹模糊（对应 Unity frag_streak）:
            stepUv = direction * texelSize * streakLength * 12 * spread
            采样 -8..+8 共 17 点，权重 exp2(-|t| * falloff)
            """
            src_h, src_w = src.shape[:2]
            # 像素步长（对应 Unity 中的 texelSize * streakLength * 12 * spread）
            step_x = dx * streak_length * 12.0 * spread
            step_y = dy * streak_length * 12.0 * spread

            accum = np.zeros_like(src)
            total_w = 0.0
            for si in range(-8, 9):
                t = si / 8.0
                weight = 2.0 ** (-abs(t) * falloff)
                px = int(round(step_x * si))
                py = int(round(step_y * si))
                if px == 0 and py == 0:
                    sample = src
                else:
                    # np.roll 边缘环绕（透明背景区域值接近 0，影响可忽略）
                    sample = src
                    if px != 0:
                        sample = np.roll(sample, px, axis=1)
                    if py != 0:
                        sample = np.roll(sample, py, axis=0)
                accum += sample * weight
                total_w += weight

            return (accum / total_w) * intensity if total_w > 0.0 else accum

        dx1, dy1 = compute_glare_dir(scratch1_angle)
        dx2, dy2 = compute_glare_dir(scratch1_angle + 90.0)  # 垂直副方向

        scratch_a = streak_blur(prefiltered, dx1, dy1, scratch1_intensity)
        scratch_b = streak_blur(prefiltered, dx2, dy2, scratch2_intensity)

        # ── Pass 2: 合成（对应 Unity frag_composite）─────────────────────
        # 将 1/4 分辨率结果上采样回全分辨率（最近邻，4x repeat）
        scratch_a_full = np.repeat(np.repeat(scratch_a, 4, axis=0), 4, axis=1)[:h, :w]
        scratch_b_full = np.repeat(np.repeat(scratch_b, 4, axis=0), 4, axis=1)[:h, :w]

        # composite: result = base + (scratchA + scratchB) * tint * compositeIntensity
        glare = (scratch_a_full + scratch_b_full) * tint[np.newaxis, np.newaxis, :] * composite_intensity
        orig_rgb = scene_np[:, :, :3].astype(np.float32) / 255.0
        result_rgb = np.clip(orig_rgb + glare, 0.0, 1.0)

        result_np = scene_np.copy()
        result_np[:, :, :3] = (result_rgb * 255.0).astype(np.uint8)

        # 转回 QImage
        result_bytes = result_np.tobytes()
        result_img = QImage(result_bytes, w, h, w * 4, QImage.Format.Format_RGBA8888).copy()
        return result_img


def _should_use_painter_renderer(config):
    return sys.platform.startswith("win")


class CircularVisualizerWindow(QWidget):
    def __init__(self, config_queue=None, status_queue=None, embedded=False, parent=None):
        super().__init__(parent)
        self.config_queue = config_queue
        self.status_queue = status_queue
        self._embedded = embedded

        if config_queue and not config_queue.empty():
            self.config = config_queue.get()
        else:
            self.config = _load_config()

        screen = QGuiApplication.primaryScreen().availableGeometry()
        width = self.config.get("width", 0)
        height = self.config.get("height", 0)
        self.WIDTH = width if width > 0 else screen.width()
        self.HEIGHT = height if height > 0 else screen.height()

        self.setWindowTitle("圆形频谱 - PyOpenGL")
        if not self._embedded:
                    self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
                    self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
                    self.setAutoFillBackground(False)
                    self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
                    self.resize(self.WIDTH, self.HEIGHT)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        if _should_use_painter_renderer(self.config):
            self.gl_widget = PainterVisualizerWidget(self)
        else:
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
        self._clamp_center()

        self.CHUNK = 2048
        self.RATE = 44100
        self.channel_count = 2
        self.audio_capture = None

        self.NUM_BARS = int(self.config.get("num_bars", 64))
        self.colors = []
        self.color_cycle_hue = 0.0
        self.current_color_cycle_rate = 0.0
        self.current_color_cycle_boost = 0.0

        initial_bar_height = self._default_bar_height()
        self.bar_heights = np.full(self.NUM_BARS, initial_bar_height, dtype=float)
        self.bar_velocities = np.zeros(self.NUM_BARS, dtype=float)
        self.peak_outer_heights = np.full(self.NUM_BARS, initial_bar_height, dtype=float)
        self.peak_inner_heights = np.full(self.NUM_BARS, initial_bar_height, dtype=float)
        self.preview_spectrum_values = [0.0] * self.NUM_BARS
        self.object_length_states = {
            key: np.full(self.NUM_BARS, initial_bar_height, dtype=float) for key in _DAMPED_OBJECT_KEYS
        }
        self.spectrum_history = None
        self.spectrum_history_sum = np.zeros(self.NUM_BARS, dtype=float)
        self.smoothed_bar_values = np.zeros(self.NUM_BARS, dtype=float)

        self.smoothing_factor = float(self.config.get("smoothing", 0.7))

        self.a1_time_window = _clamp_time_window(self.config.get("a1_time_window", 10), 10)
        self.raw_a1_value = 0.0
        self.a1_value = 0.0
        self.prev_a1_value = 0.0
        self.k2_value = 0.0
        self.last_status_send = time.time()

        self.layer_rotations = {index: 0.0 for index in range(1, 6)}
        self.tentacle_core_rotation = 0.0
        self.tentacle_core_angular_velocity = 0.0
        self.tentacle_core_accel_direction = 1.0
        self.tentacle_prev_abs_p = 0.0
        self.tentacle_prev_p_rising = False
        self.tentacle_p_peak_reference = 0.0
        self.tentacle_p_peak_cooldown = 0
        self.tentacle_soft_state_signature = None
        self.tentacle_soft_states = []
        self.runtime_tentacle_base_color = tuple(int(channel) for channel in self.config.get("tentacle_color", (130, 240, 220))[:3])
        self.runtime_tentacle_tip_color = tuple(int(channel) for channel in self.config.get("tentacle_shader_tip_color", (88, 170, 255))[:3])
        self.current_radius = float(self.config.get("circle_radius", 150))
        self.radius_velocity = 0.0

        self.render_state = {"center": (self.center_x, self.center_y), "fills": [], "tentacles": [], "bars": [], "lines": []}
        self._window_ready = False

        self._update_colors()

        # 预设平滑过渡状态
        self._transition_active = False
        self._transition_start = 0.0
        self._transition_duration = 2.0
        self._transition_easing = "ease_in_out"
        self._transition_from = {}
        self._transition_target = {}
        self._transition_toggle_schedule = []  # legacy, unused
        self._transition_alpha_schedule = []     # alpha-based fade schedule
        self._transition_alpha_controlled = set()

        self.audio_processor = AudioSignalProcessor(
            self.config,
            chunk=self.CHUNK,
            rate=self.RATE,
            channel_count=self.channel_count,
        )
        self._sync_audio_processor_state()

        self._init_audio()
        self.frame_timer = QTimer(self)
        self.frame_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.frame_timer.timeout.connect(self._tick)

    def _sync_audio_processor_state(self):
        self.a1_time_window = self.audio_processor.a1_time_window
        self.raw_a1_value = self.audio_processor.raw_a1_value
        self.a1_value = self.audio_processor.a1_value
        self.k2_value = self.audio_processor.k2_value
        self.spectrum_history = self.audio_processor.spectrum_history
        self.spectrum_history_sum = self.audio_processor.spectrum_history_sum
        self.smoothed_bar_values = self.audio_processor.smoothed_bar_values

    def _runtime_kp_delta(self, cfg_key: str, sig: str, normalized: float) -> float:
        if not bool(self.config.get(f"kp_bind_{cfg_key}_{sig}", False)):
            return 0.0
        wmin = float(self.config.get(f"kp_{cfg_key}_{sig}_wmin", 0.0))
        wmax = float(self.config.get(f"kp_{cfg_key}_{sig}_wmax", 0.0))
        normalized = max(0.0, min(1.0, float(normalized)))
        return wmin + (wmax - wmin) * normalized

    def _runtime_kp_add(self, cfg_key: str, base_value: float, normalized_k: float, normalized_p: float) -> float:
        return (
            float(base_value)
            + self._runtime_kp_delta(cfg_key, 'k', normalized_k)
            + self._runtime_kp_delta(cfg_key, 'p', normalized_p)
        )

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
        if event.key() == Qt.Key.Key_Escape:
            if self.config.get("drag_adjust_mode", False):
                self.config["drag_adjust_mode"] = False
                self.dragging = False
                self.drag_handle_hover = False
                self._send_status()
                self.overlay.update()
                return
            return
        if event.key() == Qt.Key.Key_Q:
            self.close()
            return
        super().keyPressEvent(event)

    def run(self):
        if not self._embedded:
            self.show()
        self.overlay.raise_()
        self.frame_timer.start(16)
        QTimer.singleShot(0, self._finalize_window)

    def run_embedded(self):
        """在同进程中以嵌入模式启动（不弹出独立窗口）。"""
        if not self.frame_timer.isActive():
            self.frame_timer.start(16)
            QTimer.singleShot(0, self._finalize_window)

    def _finalize_window(self):
        if self._window_ready:
            return
        self._window_ready = True
        self._center_window(reset_visual_center=True)
        self._apply_window_styles(force=True)
        self._send_status()
        # 立即执行一帧 tick，填充 render_state，避免第一帧空白（首次启动 bug）
        QTimer.singleShot(0, self._tick)
        # Win32 分层窗口 HWND 可能在 singleShot(0) 时尚未完全就绪，
        # 延迟二次应用确保样式与重绘生效。
        QTimer.singleShot(150, lambda: self._apply_window_styles(force=True))

    def _init_audio(self):
        self.audio_capture = LoopbackAudioCapture(chunk=self.CHUNK)
        try:
            self.audio_capture.start()
            self.device_info = self.audio_capture.device_info
            self.RATE = self.audio_capture.rate
            self.channel_count = self.audio_capture.channel_count
            self.audio_processor.set_stream_format(rate=self.RATE, channel_count=self.channel_count)
        except Exception as exc:
            print(f"获取音频设备失败: {exc}")
            raise

    def _pull_latest_audio_frame(self):
        if not self.audio_capture:
            return None
        return self.audio_capture.pull_latest_frame()

    def _reset_length_states(self, initial_bar_height):
        self.bar_heights = np.full(self.NUM_BARS, initial_bar_height, dtype=float)
        self.bar_velocities = np.zeros(self.NUM_BARS, dtype=float)
        self.peak_outer_heights = np.full(self.NUM_BARS, initial_bar_height, dtype=float)
        self.peak_inner_heights = np.full(self.NUM_BARS, initial_bar_height, dtype=float)
        self.preview_spectrum_values = [float(initial_bar_height)] * self.NUM_BARS
        self.object_length_states = {
            key: np.full(self.NUM_BARS, initial_bar_height, dtype=float) for key in _DAMPED_OBJECT_KEYS
        }
        self.audio_processor.reset()
        self._sync_audio_processor_state()
        self.tentacle_core_angular_velocity = 0.0
        self.tentacle_core_accel_direction = 1.0
        self.tentacle_prev_abs_p = 0.0
        self.tentacle_prev_p_rising = False
        self.tentacle_p_peak_reference = 0.0
        self.tentacle_p_peak_cooldown = 0
        self.tentacle_soft_state_signature = None
        self.tentacle_soft_states = []

    def _default_bar_height(self):
        default_height = float(self.config.get("bar_default_height", 0.0))
        lower_limit = float(self.config.get("bar_internal_min", 0.0))
        upper_limit = float(self.config.get("bar_internal_max", 300.0))
        if lower_limit > upper_limit:
            lower_limit, upper_limit = upper_limit, lower_limit
        return float(np.clip(default_height, lower_limit, upper_limit))

    @staticmethod
    def _clamp_damping(value, fallback):
        try:
            return max(0.0, min(0.999, float(value)))
        except Exception:
            return max(0.0, min(0.999, float(fallback)))

    def _get_damping_pair(self, prefix=None):
        global_rise = self._clamp_damping(self.config.get("k_rise_damping", 0.1), 0.1)
        global_fall = self._clamp_damping(self.config.get("k_fall_damping", 0.999), 0.999)
        if not prefix:
            return global_rise, global_fall
        if not self.config.get(f"{prefix}_use_independent_damping", False):
            return global_rise, global_fall
        rise = self._clamp_damping(self.config.get(f"{prefix}_independent_rise_damping", global_rise), global_rise)
        fall = self._clamp_damping(self.config.get(f"{prefix}_independent_fall_damping", global_fall), global_fall)
        return rise, fall

    def _get_bar_time_window(self):
        base_time_window = _clamp_time_window(self.a1_time_window, 10.0)
        if not self.config.get("bar_use_independent_time_window", False):
            return base_time_window
        return _clamp_time_window(self.config.get("bar_time_window", base_time_window), base_time_window)

    def _prune_spectrum_history(self, now=None):
        values = self.audio_processor.prune_spectrum_history(now)
        self._sync_audio_processor_state()
        return values

    def _update_spectrum_history(self, bar_values, now=None):
        values = self.audio_processor.update_spectrum_history(bar_values, now)
        self._sync_audio_processor_state()
        return values

    @staticmethod
    def _apply_damping_step(current, target, rise_damping, fall_damping):
        return AudioSignalProcessor.apply_damping_step(current, target, rise_damping, fall_damping)

    def _build_band_edges(self, spectrum_length, freq_res):
        return self.audio_processor.build_band_edges(spectrum_length, freq_res)

    def _process_audio(self, audio_data):
        values = self.audio_processor.process_frame(audio_data)
        self._sync_audio_processor_state()
        return values

    def _update_a1(self, loudness):
        self.audio_processor.update_loudness(loudness)
        self._sync_audio_processor_state()

    @property
    def effective_a1(self):
        return self.audio_processor.effective_a1

    def _send_status(self):
        if not self.status_queue:
            return
        try:
            while not self.status_queue.empty():
                try:
                    self.status_queue.get_nowait()
                except Exception:
                    break
            self.status_queue.put(
                {
                    "raw_k": float(self.raw_a1_value),
                    "k": float(self.a1_value),
                    "p": float(self.k2_value),
                    "a1": float(self.a1_value),
                    "k2": float(self.k2_value),
                    "spectrum_bars": list(self.preview_spectrum_values),
                    "color_preview": [tuple(int(channel) for channel in color) for color in self.colors],
                    "runtime_color_state": self._build_runtime_color_state(),
                    "color_cycle_hue": float(self.color_cycle_hue),
                    "color_cycle_rate": float(self.current_color_cycle_rate),
                    "drag_adjust_mode": bool(self.config.get("drag_adjust_mode", False)),
                    "pos_x": int(round(self.center_x)),
                    "pos_y": int(round(self.center_y)),
                }
            )
        except Exception:
            pass

    def _build_runtime_color_state(self):
        state = {
            'palette_preview': [tuple(int(channel) for channel in color[:3]) for color in (self.colors[:8] or [])],
            'gradient_points': [
                (float(entry[0]), tuple(int(channel) for channel in entry[1][:3]))
                for entry in (self.config.get('gradient_points', []) or [])
                if isinstance(entry, (list, tuple)) and len(entry) >= 2 and isinstance(entry[1], (list, tuple)) and len(entry[1]) >= 3
            ],
            'tentacle_color': tuple(int(channel) for channel in getattr(self, 'runtime_tentacle_base_color', self.config.get('tentacle_color', (130, 240, 220)))[:3]),
            'tentacle_shader_tip_color': tuple(int(channel) for channel in getattr(self, 'runtime_tentacle_tip_color', self.config.get('tentacle_shader_tip_color', (88, 170, 255)))[:3]),
        }
        for layer_index in range(1, 6):
            state[f'c{layer_index}_color'] = tuple(int(channel) for channel in self.config.get(f'c{layer_index}_color', (255, 255, 255))[:3])
        return state

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
        if self._embedded:
            # 嵌入模式：位置由 Qt 布局管理，只更新视觉中心
            if reset_visual_center:
                self.center_x = max(1.0, self.width() * 0.5)
                self.center_y = max(1.0, self.height() * 0.5)
            self._clamp_center()
            return
        screen = QGuiApplication.primaryScreen().availableGeometry()
        if self.width() >= screen.width() or self.height() >= screen.height():
            self.move(screen.left(), screen.top())
        else:
            x = screen.left() + (screen.width() - self.width()) // 2
            y = screen.top() + (screen.height() - self.height()) // 2
            self.move(x, y)

        if reset_visual_center:
            self.center_x = self.width() * 0.5
            self.center_y = self.height() * 0.5
        self._clamp_center()

    def _clamp_center(self):
        width = max(1.0, float(self.width()))
        height = max(1.0, float(self.height()))
        margin_x = min(96.0, max(12.0, width * 0.03))
        margin_y = min(96.0, max(12.0, height * 0.03))
        min_x = margin_x
        max_x = max(min_x, width - margin_x)
        min_y = margin_y
        max_y = max(min_y, height - margin_y)
        self.center_x = min(max(float(self.center_x), min_x), max_x)
        self.center_y = min(max(float(self.center_y), min_y), max_y)

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
        self._clamp_center()
        self._send_status()
        self.overlay.update()

    def _apply_window_styles(self, force=False):
        if self._embedded:
            # 嵌入模式：跳过所有 Win32 层叠/置顶/透明操作
            self.gl_widget.update()
            self.overlay.update()
            return
        if not self._window_ready and not force:
            return

        hwnd = int(self.winId())
        user32 = ctypes.windll.user32
        GWL_EXSTYLE = -20
        WS_EX_LAYERED = 0x00080000
        WS_EX_TRANSPARENT = 0x00000020
        HWND_TOPMOST = -1
        HWND_NOTOPMOST = -2
        HWND_BOTTOM = 1
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

        layer = self.config.get("window_layer", "top" if self.config.get("always_on_top", True) else "normal")
        flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED
        if layer == "bottom":
            user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, flags)
            user32.SetWindowPos(hwnd, HWND_BOTTOM, 0, 0, 0, 0, flags)
        elif layer == "top":
            user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)
        else:
            user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, flags)

        opacity = max(0.05, min(1.0, self.window_alpha / 255.0))
        self.setWindowOpacity(opacity)
        self.gl_widget.update()
        self.overlay.update()

    def _build_nurbs(self, ctrl_points):
        count = len(ctrl_points)
        if count < 4:
            return None

        if not _HAS_SCIPY_BSPLINE:
            return self._densify_polyline(ctrl_points, subdivisions=8, closed=True)

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

    def _build_open_spline(self, ctrl_points):
        count = len(ctrl_points)
        if count < 2:
            return None

        if not _HAS_SCIPY_BSPLINE:
            return self._densify_polyline(ctrl_points, subdivisions=12, closed=False)

        degree = min(3, count - 1)
        ctrl = np.asarray(ctrl_points, dtype=float)
        interior_count = count - degree - 1
        if interior_count > 0:
            interior = np.linspace(0.0, 1.0, interior_count + 2, dtype=float)[1:-1]
            knots = np.concatenate([
                np.zeros(degree + 1, dtype=float),
                interior,
                np.ones(degree + 1, dtype=float),
            ])
        else:
            knots = np.concatenate([
                np.zeros(degree + 1, dtype=float),
                np.ones(degree + 1, dtype=float),
            ])

        try:
            spline_x = BSpline(knots, ctrl[:, 0], degree)
            spline_y = BSpline(knots, ctrl[:, 1], degree)
            eval_count = max(count * 12, 64)
            samples = np.linspace(0.0, 1.0, eval_count, endpoint=True)
            return list(zip(spline_x(samples), spline_y(samples)))
        except Exception:
            return None

    @staticmethod
    def _lerp_color(color_a, color_b, ratio):
        ratio = max(0.0, min(1.0, float(ratio)))
        return (
            int(round(color_a[0] + (color_b[0] - color_a[0]) * ratio)),
            int(round(color_a[1] + (color_b[1] - color_a[1]) * ratio)),
            int(round(color_a[2] + (color_b[2] - color_a[2]) * ratio)),
        )

    @staticmethod
    def _cp_count_for_tentacle(index, cp_min, cp_max):
        if cp_max <= cp_min:
            return cp_min
        return cp_min + (index % (cp_max - cp_min + 1))

    def _ensure_tentacle_soft_states(self, count, cp_min, cp_max):
        counts = tuple(self._cp_count_for_tentacle(index, cp_min, cp_max) for index in range(count))
        signature = (count, counts)
        if signature == self.tentacle_soft_state_signature:
            return

        self.tentacle_soft_states = []
        for cp_count in counts:
            outer_points = max(1, cp_count - 1)
            self.tentacle_soft_states.append({
                "offsets": np.zeros((outer_points, 2), dtype=float),
                "velocities": np.zeros((outer_points, 2), dtype=float),
                "initialized": False,
            })
        self.tentacle_soft_state_signature = signature

    @staticmethod
    def _star_points(cx, cy, outer_radius, inner_ratio, point_count, rotation):
        points = []
        point_count = max(3, int(point_count))
        inner_radius = max(1.0, float(outer_radius) * max(0.01, min(1.0, float(inner_ratio))))
        for index in range(point_count * 2):
            angle = rotation + (index / (point_count * 2)) * math.tau - math.pi / 2
            radius = outer_radius if index % 2 == 0 else inner_radius
            points.append((cx + math.cos(angle) * radius, cy + math.sin(angle) * radius))
        return points

    @staticmethod
    def _densify_polyline(points, subdivisions=12, closed=False):
        if not points:
            return []
        if len(points) == 1:
            return [points[0]]

        subdivisions = max(1, int(subdivisions))
        dense_points = []
        limit = len(points) if closed else len(points) - 1
        for index in range(limit):
            start = points[index]
            end = points[(index + 1) % len(points)]
            for step in range(subdivisions):
                ratio = step / subdivisions
                dense_points.append((
                    float(start[0]) + (float(end[0]) - float(start[0])) * ratio,
                    float(start[1]) + (float(end[1]) - float(start[1])) * ratio,
                ))
        dense_points.append(points[0] if closed else points[-1])
        return dense_points

    def _build_tentacle_segments(self, points, root_color, tip_color, alpha_scale, root_thickness, tip_thickness, alpha_start, alpha_end, bias):
        if not points or len(points) < 2:
            return []

        segment_count = len(points) - 1
        segments = []
        for index in range(segment_count):
            start = points[index]
            end = points[index + 1]
            ratio = (index + 0.5) / max(1, segment_count)
            grad_t = pow(ratio, max(0.01, float(bias)))
            color = self._lerp_color(root_color, tip_color, grad_t)
            alpha_ratio = alpha_start + (alpha_end - alpha_start) * grad_t
            alpha = max(0, min(255, int(round(alpha_scale * alpha_ratio))))
            thickness = max(0.0, float(root_thickness) + (float(tip_thickness) - float(root_thickness)) * grad_t)
            if alpha <= 0 or thickness <= 0.05:
                continue
            segments.append((start, end, (*color, alpha), thickness))
        return segments

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
        normalized_k = min(1.0, math.log1p(abs(float(self.effective_a1))) / 6.0)
        normalized_p = min(1.0, math.log1p(abs(float(self.k2_value))) / 6.0)
        fixed = self.config.get(f"{key}_fixed", False)
        fixed_len = self._runtime_kp_add(key + "_fixed_len", float(self.config.get(f"{key}_fixed_len", 30)), normalized_k, normalized_p)
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

            b_alpha = int(self.config.get(f"_tr_{key}_alpha", 255))
            len_frac = float(self.config.get(f"_tr_{key}_len_frac", 1.0))
            if not fixed:
                for index in range(self.NUM_BARS):
                    color_index = (index + segment * self.NUM_BARS // max(1, segments)) % max(1, len(self.colors))
                    color = self._get_color_for_bar(color_index, lengths[index])
                    ex = ax[index] + (bx[index] - ax[index]) * len_frac
                    ey = ay[index] + (by[index] - ay[index]) * len_frac
                    line_segments.append(((ax[index], ay[index]), (ex, ey), (*color, b_alpha)))
                continue

            eff_fixed_len = fixed_len * len_frac
            delta_x = bx - ax
            delta_y = by - ay
            full_len = np.sqrt(delta_x * delta_x + delta_y * delta_y)
            full_len = np.maximum(full_len, 1e-6)
            unit_x = delta_x / full_len
            unit_y = delta_y / full_len
            clip_len = np.minimum(eff_fixed_len, full_len)

            for index in range(self.NUM_BARS):
                color_index = (index + segment * self.NUM_BARS // max(1, segments)) % max(1, len(self.colors))
                color = self._get_color_for_bar(color_index, lengths[index])
                rgba = (*color, b_alpha)
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

    def _build_tentacle_curves(self, cx, cy, radius, scale, shared_lengths):
        self.runtime_tentacle_base_color = tuple(int(channel) for channel in self.config.get("tentacle_color", (130, 240, 220))[:3])
        self.runtime_tentacle_tip_color = tuple(int(channel) for channel in self.config.get("tentacle_shader_tip_color", (88, 170, 255))[:3])
        if not self.config.get("tentacles_enabled", True):
            return []
        if not self.config.get("tentacle_on", True):
            return []

        normalized_k = min(1.0, math.log1p(abs(float(self.effective_a1))) / 6.0)
        normalized_p = min(1.0, math.log1p(abs(float(self.k2_value))) / 6.0)

        def _lerp(a, b, t):
            return float(a) + (float(b) - float(a)) * max(0.0, min(1.0, float(t)))

        def _kp_bind_key(cfg_key: str, sig: str) -> str:
            return f"kp_bind_{cfg_key}_{sig}"

        def _kp_wmin_key(cfg_key: str, sig: str) -> str:
            return f"kp_{cfg_key}_{sig}_wmin"

        def _kp_wmax_key(cfg_key: str, sig: str) -> str:
            return f"kp_{cfg_key}_{sig}_wmax"

        def _kp_delta(cfg_key: str, sig: str, normalized: float) -> float:
            if not bool(self.config.get(_kp_bind_key(cfg_key, sig), False)):
                return 0.0
            wmin = float(self.config.get(_kp_wmin_key(cfg_key, sig), 0.0))
            wmax = float(self.config.get(_kp_wmax_key(cfg_key, sig), 0.0))
            return _lerp(wmin, wmax, normalized)

        def _kp_add(cfg_key: str, base_value: float) -> float:
            return float(base_value) + _kp_delta(cfg_key, 'k', normalized_k) + _kp_delta(cfg_key, 'p', normalized_p)

        def _any_kp_enabled_for(cfg_key: str) -> bool:
            return bool(self.config.get(_kp_bind_key(cfg_key, 'k'), False)) or bool(self.config.get(_kp_bind_key(cfg_key, 'p'), False))

        def _apply_kp_to_rgb(prefix: str, rgb: tuple[int, int, int]) -> tuple[int, int, int]:
            # 通道 cfg_key 命名规则：<prefix>__h/__s/__l 或 <prefix>__r/__g/__b
            # 若同时存在两套绑定：优先采用 HSL（因为弹窗默认 HSL 模式）。
            try:
                base_r, base_g, base_b = (int(rgb[0]), int(rgb[1]), int(rgb[2]))
            except Exception:
                base_r, base_g, base_b = (255, 255, 255)

            h_key = f"{prefix}__h"
            s_key = f"{prefix}__s"
            l_key = f"{prefix}__l"
            r_key = f"{prefix}__r"
            g_key = f"{prefix}__g"
            b_key = f"{prefix}__b"

            use_hsl = _any_kp_enabled_for(h_key) or _any_kp_enabled_for(s_key) or _any_kp_enabled_for(l_key)
            use_rgb = _any_kp_enabled_for(r_key) or _any_kp_enabled_for(g_key) or _any_kp_enabled_for(b_key)

            if use_hsl:
                hh, ll, ss = colorsys.rgb_to_hls(base_r / 255.0, base_g / 255.0, base_b / 255.0)
                h_deg = (hh % 1.0) * 360.0
                s_pct = max(0.0, min(100.0, ss * 100.0))
                l_pct = max(0.0, min(100.0, ll * 100.0))

                h_deg = (h_deg + _kp_delta(h_key, 'k', normalized_k) + _kp_delta(h_key, 'p', normalized_p)) % 360.0
                s_pct = max(0.0, min(100.0, s_pct + _kp_delta(s_key, 'k', normalized_k) + _kp_delta(s_key, 'p', normalized_p)))
                l_pct = max(0.0, min(100.0, l_pct + _kp_delta(l_key, 'k', normalized_k) + _kp_delta(l_key, 'p', normalized_p)))

                rr, gg, bb = colorsys.hls_to_rgb((h_deg % 360.0) / 360.0, l_pct / 100.0, s_pct / 100.0)
                return (int(round(rr * 255.0)), int(round(gg * 255.0)), int(round(bb * 255.0)))

            if use_rgb:
                rr = base_r + _kp_delta(r_key, 'k', normalized_k) + _kp_delta(r_key, 'p', normalized_p)
                gg = base_g + _kp_delta(g_key, 'k', normalized_k) + _kp_delta(g_key, 'p', normalized_p)
                bb = base_b + _kp_delta(b_key, 'k', normalized_k) + _kp_delta(b_key, 'p', normalized_p)
                rr = max(0.0, min(255.0, rr))
                gg = max(0.0, min(255.0, gg))
                bb = max(0.0, min(255.0, bb))
                return (int(round(rr)), int(round(gg)), int(round(bb)))

            return (base_r, base_g, base_b)

        # 触须参数（所有数值参数均支持 K/P 绑定）
        count = int(round(_kp_add('tentacle_count', float(self.config.get("tentacle_count", 16)))))
        count = max(3, min(256, count))

        base_length_unscaled = _kp_add('tentacle_length', float(self.config.get("tentacle_length", 280.0)))
        base_length = max(12.0, base_length_unscaled * scale)

        length_jitter_unscaled = _kp_add('tentacle_length_jitter', float(self.config.get("tentacle_length_jitter", 80.0)))
        length_jitter = max(0.0, length_jitter_unscaled * scale)

        length_jitter_speed = max(0.0, _kp_add('tentacle_length_jitter_speed', float(self.config.get("tentacle_length_jitter_speed", 0.35))))
        length_jitter_random = bool(self.config.get("tentacle_length_jitter_random", False))

        cp_min = int(round(_kp_add('tentacle_control_points_min', float(self.config.get("tentacle_control_points_min", 3)))))
        cp_min = max(3, min(24, cp_min))
        cp_max = int(round(_kp_add('tentacle_control_points_max', float(self.config.get("tentacle_control_points_max", 5)))))
        cp_max = max(cp_min, min(24, cp_max))

        tip_bias = max(0.1, _kp_add('tentacle_tip_bias', float(self.config.get("tentacle_tip_bias", 1.85))))

        turbulence_base = max(0.0, float(self.config.get("tentacle_turbulence", 46.0)) * scale)
        k_influence = max(0.0, float(self.config.get("tentacle_k_influence", 1.35)))

        sway_speed = max(0.0, _kp_add('tentacle_sway_speed', float(self.config.get("tentacle_sway_speed", 1.1))))
        sway_density = max(0.1, _kp_add('tentacle_sway_density', float(self.config.get("tentacle_sway_density", 2.4))))

        transition_tentacle_alpha = self.config.get("_tr_tentacle_alpha")
        if transition_tentacle_alpha is None:
            alpha_base = float(self.config.get("tentacle_alpha", 170))
            alpha = int(round(_kp_add('tentacle_alpha', alpha_base)))
        else:
            alpha = int(round(float(transition_tentacle_alpha)))
        alpha = max(0, min(255, alpha))

        length_fraction = max(0.0, float(self.config.get("_tr_tentacle_len_frac", 1.0)))

        thickness = max(0.0, _kp_add('tentacle_thick', float(self.config.get("tentacle_thick", 3))))

        tip_thickness_frac = _kp_add('tentacle_tip_thickness', float(self.config.get("tentacle_tip_thickness", 0.15)))
        tip_thickness_frac = max(0.0, min(1.0, tip_thickness_frac))
        tip_thickness = thickness * tip_thickness_frac

        water_damping = _kp_add('tentacle_water_damping', float(self.config.get("tentacle_water_damping", 0.84)))
        water_damping = max(0.0, min(0.999, water_damping))

        angle_stiffness = max(0.0, _kp_add('tentacle_angle_stiffness', float(self.config.get("tentacle_angle_stiffness", 0.18))))
        length_stiffness = max(0.0, _kp_add('tentacle_length_stiffness', float(self.config.get("tentacle_length_stiffness", 0.24))))
        stretch_limit = max(1.0, _kp_add('tentacle_stretch_limit', float(self.config.get("tentacle_stretch_limit", 1.12))))

        shader_enabled = bool(self.config.get("tentacle_shader_enabled", True))
        tip_color = tuple(self.config.get("tentacle_shader_tip_color", (88, 170, 255)))
        tip_color = _apply_kp_to_rgb('tentacle_shader_tip_color', tip_color)
        alpha_start = _kp_add('tentacle_shader_alpha_start', float(self.config.get("tentacle_shader_alpha_start", 1.0)))
        alpha_start = max(0.0, min(1.0, alpha_start))
        alpha_end = _kp_add('tentacle_shader_alpha_end', float(self.config.get("tentacle_shader_alpha_end", 0.18)))
        alpha_end = max(0.0, min(1.0, alpha_end))
        shader_bias = max(0.01, _kp_add('tentacle_shader_bias', float(self.config.get("tentacle_shader_bias", 1.15))))

        base_color = tuple(self.config.get("tentacle_color", (130, 240, 220)))
        base_color = _apply_kp_to_rgb('tentacle_color', base_color)
        self.runtime_tentacle_base_color = tuple(int(channel) for channel in base_color[:3])
        self.runtime_tentacle_tip_color = tuple(int(channel) for channel in tip_color[:3])

        # 紊流：沿用“系数乘法”语义，并扩展为可同时绑定 K/P
        turbulence_coef = 0.0
        if bool(self.config.get("kp_bind_tentacle_turbulence_k", False)):
            wmin = float(self.config.get("kp_tentacle_turbulence_k_wmin", 0.22))
            wmax = float(self.config.get("kp_tentacle_turbulence_k_wmax", 0.683))
            turbulence_coef += _lerp(wmin, wmax, normalized_k)
        if bool(self.config.get("kp_bind_tentacle_turbulence_p", False)):
            wmin = float(self.config.get("kp_tentacle_turbulence_p_wmin", 0.0))
            wmax = float(self.config.get("kp_tentacle_turbulence_p_wmax", 0.0))
            turbulence_coef += _lerp(wmin, wmax, normalized_p)
        if turbulence_coef <= 0.0 and not bool(self.config.get("kp_bind_tentacle_turbulence_k", False)) and not bool(self.config.get("kp_bind_tentacle_turbulence_p", False)):
            turbulence_coef = 0.22 + normalized_k * min(0.55, 0.22 + k_influence * 0.18)
        turbulence_coef = max(0.0, min(2.5, turbulence_coef))
        turbulence = turbulence_base * turbulence_coef
        angular_velocity = float(getattr(self, "tentacle_core_angular_velocity", 0.0))
        swirl_strength = min(1.65, abs(angular_velocity) * (7.5 + sway_speed * 2.0))
        fluid_damping = 0.86 + water_damping * 0.13
        bend_response = 0.04 + angle_stiffness * 0.18
        stretch_response = 0.04 + length_stiffness * 0.16
        follow_response = 0.06 + (angle_stiffness + length_stiffness) * 0.08
        time_now = time.time()
        flow_time = time_now * (0.18 + sway_speed * 0.18)
        jitter_time = time_now * length_jitter_speed
        curves = []
        self._ensure_tentacle_soft_states(count, cp_min, cp_max)

        for index in range(count):
            angle = self.tentacle_core_rotation + (index / count) * math.tau - math.pi / 2
            angle += 0.08 * math.sin(time_now * (0.35 + sway_speed * 0.25) + index * 0.91) * (0.2 + normalized_k * 0.8)
            direction = np.array((math.cos(angle), math.sin(angle)), dtype=float)

            normal = np.array((-direction[1], direction[0]), dtype=float)
            state = self.tentacle_soft_states[index]
            cp_count = self._cp_count_for_tentacle(index, cp_min, cp_max)
            outer_points = max(1, cp_count - 1)
            shared_index = index % max(1, len(shared_lengths))
            shared_length = float(shared_lengths[shared_index]) if len(shared_lengths) else 0.0

            # 非随机时：所有触须同步往复；随机时：每根触须相位/幅度不同
            if length_jitter_random:
                jitter_phase = (jitter_time + index * 0.17) % 1.0
            else:
                jitter_phase = jitter_time % 1.0
            jitter_tri = 1.0 - abs(2.0 * jitter_phase - 1.0)  # 0→1→0
            jitter_scale = 1.0
            if length_jitter_random:
                hashed = math.sin(index * 12.9898 + 78.233) * 43758.5453
                hashed -= math.floor(hashed)
                jitter_scale = 0.25 + 0.75 * hashed
            jitter_amount = jitter_tri * length_jitter * jitter_scale
            total_length = base_length + shared_length * 0.38 + jitter_amount * 0.45
            total_length = max(12.0, total_length * max(0.0, length_fraction))
            segment_length = total_length / max(1, outer_points)
            root_position = np.array((cx, cy), dtype=float)

            ctrl_points = [(float(root_position[0]), float(root_position[1]))]
            desired_offsets = [np.zeros(2, dtype=float)]

            for state_index in range(outer_points):
                ratio = (state_index + 1) / max(1, outer_points)
                tip_weight = pow(ratio, tip_bias)
                arc_length = segment_length * (state_index + 1)
                radial_wave = math.sin(flow_time * (0.75 + sway_density * 0.22) + index * 0.73 + ratio * (2.4 + sway_density * 0.8))
                lateral_wave = math.cos(flow_time * (0.58 + sway_density * 0.17) + index * 0.41 - ratio * 1.9)
                lateral_offset = turbulence * tip_weight * 0.16 * lateral_wave
                radial_offset = turbulence * tip_weight * 0.12 * radial_wave

                contract_amount = swirl_strength * total_length * pow(ratio, 1.35) * (0.1 + angle_stiffness * 0.22)
                contracted_arc = max(segment_length * (1.0 + 0.08 * length_stiffness), arc_length + radial_offset - contract_amount)
                swirl_drag = angular_velocity * total_length * tip_weight * (0.3 + angle_stiffness * 0.6)
                inward_pull = -direction * (swirl_strength * total_length * pow(ratio, 1.55) * (0.035 + length_stiffness * 0.08))
                desired_prev = desired_offsets[-1]
                desired_segment = direction * max(segment_length * 0.75, contracted_arc - np.linalg.norm(desired_prev))
                desired_segment += normal * (lateral_offset * 0.38 + swirl_drag * 0.72)
                segment_norm = float(np.linalg.norm(desired_segment))
                if segment_norm > 1e-6:
                    desired_segment = desired_segment / segment_norm * max(segment_length * 0.72, min(segment_norm, segment_length * 1.08))
                desired_offset = desired_prev + desired_segment + inward_pull
                desired_offsets.append(desired_offset)

                if not state["initialized"]:
                    state["offsets"][state_index] = desired_offset
                    state["velocities"][state_index] = 0.0
                else:
                    current = state["offsets"][state_index]
                    velocity = state["velocities"][state_index]
                    parent_current = state["offsets"][state_index - 1] if state_index > 0 else np.zeros(2, dtype=float)
                    parent_desired = desired_offsets[state_index]
                    radial_current = float(np.dot(current, direction))
                    tangential_current = float(np.dot(current, normal))
                    radial_target = contracted_arc
                    tangential_target = lateral_offset + swirl_drag
                    current_segment = current - parent_current
                    desired_segment = desired_offset - parent_desired
                    blended_target = current * 0.72 + desired_offset * 0.28
                    force = (blended_target - current) * (0.05 + stretch_response * 0.45)
                    force += (desired_segment - current_segment) * (0.07 + stretch_response * 0.38)
                    force += direction * (radial_target - radial_current) * stretch_response
                    force += normal * (tangential_target - tangential_current) * (bend_response + 0.04 * swirl_strength)
                    force += (parent_current - parent_desired) * follow_response
                    velocity = velocity * fluid_damping + force
                    max_velocity = max(0.6, segment_length * (0.11 + sway_speed * 0.015))
                    velocity_norm = float(np.linalg.norm(velocity))
                    if velocity_norm > max_velocity:
                        velocity = velocity * (max_velocity / velocity_norm)
                    current = current + velocity
                    max_offset_length = max(1.0, arc_length * stretch_limit)
                    current_length = float(np.linalg.norm(current))
                    if current_length > max_offset_length:
                        clamp_ratio = max_offset_length / current_length
                        current = current * clamp_ratio
                        velocity = velocity * clamp_ratio
                    state["offsets"][state_index] = current
                    state["velocities"][state_index] = velocity

                current_offset = state["offsets"][state_index]
                ctrl_points.append((
                    float(root_position[0] + current_offset[0]),
                    float(root_position[1] + current_offset[1]),
                ))

            state["initialized"] = True

            spline_points = self._build_open_spline(ctrl_points)
            if not spline_points or len(spline_points) < 2:
                continue

            color_index = index % max(1, len(self.colors))
            spectrum_color = self.colors[color_index] if self.colors else base_color
            root_color = self._lerp_color(base_color, spectrum_color, 0.35)
            shader_tip = tip_color if shader_enabled else root_color
            shader_alpha_start = alpha_start if shader_enabled else 1.0
            shader_alpha_end = alpha_end if shader_enabled else 1.0
            segments = self._build_tentacle_segments(
                spline_points,
                root_color,
                shader_tip,
                alpha,
                thickness,
                tip_thickness,
                shader_alpha_start,
                shader_alpha_end,
                shader_bias,
            )
            if segments:
                curves.append({"segments": segments})

        return curves

    def _update_visual_state(self, bar_values):
        if not self.config.get("master_visible", True):
            self.preview_spectrum_values = [0.0] * self.NUM_BARS
            self.render_state = {"center": (self.center_x, self.center_y), "fills": [], "tentacles": [], "bars": [], "lines": []}
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
        if bar_len_min > bar_len_max:
            bar_len_min, bar_len_max = bar_len_max, bar_len_min
        internal_min = float(self.config.get("bar_internal_min", 0.0))
        internal_max = float(self.config.get("bar_internal_max", 300.0))
        if internal_min > internal_max:
            internal_min, internal_max = internal_max, internal_min
        targets = self._default_bar_height() + bar_values / 200.0
        shared_rise, shared_fall = self._get_damping_pair()
        self.bar_heights = np.clip(
            self._apply_damping_step(self.bar_heights, targets, shared_rise, shared_fall),
            internal_min,
            internal_max,
        )
        shared_lengths = np.clip(self.bar_heights, bar_len_min, bar_len_max) * scale

        object_lengths = {}
        for key in _DAMPED_OBJECT_KEYS:
            if self.config.get(f"{key}_use_independent_damping", False):
                rise_damping, fall_damping = self._get_damping_pair(key)
                state = self.object_length_states.get(key)
                if state is None or len(state) != self.NUM_BARS:
                    state = np.full(self.NUM_BARS, self._default_bar_height(), dtype=float)
                state = np.clip(
                    self._apply_damping_step(state, targets, rise_damping, fall_damping),
                    internal_min,
                    internal_max,
                )
                self.object_length_states[key] = state
                object_lengths[key] = np.clip(state, bar_len_min, bar_len_max) * scale
            else:
                object_lengths[key] = shared_lengths

        self.preview_spectrum_values = [float(value) for value in object_lengths["bar"].tolist()]

        normalized_k = min(1.0, math.log1p(abs(float(self.effective_a1))) / 6.0)
        normalized_p = min(1.0, math.log1p(abs(float(self.k2_value))) / 6.0)

        decay_inner = self._runtime_kp_add("c1_decay", float(self.config.get("c1_decay", 0.995)), normalized_k, normalized_p)
        decay_outer = self._runtime_kp_add("c5_decay", float(self.config.get("c5_decay", 0.995)), normalized_k, normalized_p)
        self.peak_inner_heights = np.maximum(object_lengths["c1"], self.peak_inner_heights * decay_inner)
        self.peak_outer_heights = np.maximum(object_lengths["c5"], self.peak_outer_heights * decay_outer)

        a1_delta = abs(effective_a1 - self.prev_a1_value)
        self.prev_a1_value = effective_a1
        normalized_delta = min(a1_delta / 500.0, 1.0)
        for layer_index in range(1, 6):
            speed = self._runtime_kp_add(f"c{layer_index}_rot_speed", float(self.config.get(f"c{layer_index}_rot_speed", 1.0)), normalized_k, normalized_p)
            power = self._runtime_kp_add(f"c{layer_index}_rot_pow", float(self.config.get(f"c{layer_index}_rot_pow", 0.5)), normalized_k, normalized_p)
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
            2: np.maximum(0, radius - object_lengths["c2"]),
            3: np.full(self.NUM_BARS, radius),
            4: radius + object_lengths["c4"],
            5: radius + self.peak_outer_heights,
        }

        contours_enabled = bool(self.config.get("contours_enabled", True))
        bars_enabled = bool(self.config.get("bars_enabled", True))
        tentacles_enabled = bool(self.config.get("tentacles_enabled", True))

        contour_points = {}
        circle_points = None
        fills = []
        if contours_enabled:
            for layer_index in (1, 2, 4, 5):
                need_line = self.config.get(f"c{layer_index}_on", False)
                need_fill = self.config.get(f"c{layer_index}_fill", False)
                if not (need_line or need_fill):
                    continue
                step = max(1, int(round(self._runtime_kp_add(f"c{layer_index}_step", float(self.config.get(f"c{layer_index}_step", 2)), normalized_k, normalized_p))))
                contour_points[layer_index] = self._contour_from_radii(cx, cy, radius_map[layer_index], rot[layer_index], segments, seg_angle, step)

            circle_points = self._circle_points(cx, cy, radius, max(96, self.NUM_BARS * segments * 4), rot[3])

            for layer_index in (5, 4, 3, 2, 1):
                if not self.config.get(f"c{layer_index}_fill", False):
                    continue
                points = circle_points if layer_index == 3 else contour_points.get(layer_index)
                if points and len(points) >= 3:
                    color = tuple(self.config.get(f"c{layer_index}_color", (255, 255, 255)))
                    transition_alpha = self.config.get(f"_tr_c{layer_index}_fill_alpha")
                    if transition_alpha is None:
                        alpha = int(round(self._runtime_kp_add(f"c{layer_index}_fill_alpha", float(self.config.get(f"c{layer_index}_fill_alpha", 50)), normalized_k, normalized_p)))
                    else:
                        alpha = int(round(float(transition_alpha)))
                    alpha = max(0, min(255, alpha))
                    fills.append({"points": points, "color": (*color, alpha)})

        if tentacles_enabled and self.config.get("tentacle_core_on", True):
            normalized_k_speed = min(1.0, math.log1p(abs(float(self.a1_value))) / 6.0)
            normalized_p_speed = min(1.0, math.log1p(abs(float(self.k2_value))) / 6.0)
            abs_p = abs(float(self.k2_value))
            self.tentacle_p_peak_reference = self.tentacle_p_peak_reference * 0.94 + abs_p * 0.06
            is_rising = abs_p > self.tentacle_prev_abs_p + 1e-4
            if self.tentacle_p_peak_cooldown > 0:
                self.tentacle_p_peak_cooldown -= 1
            peak_threshold = max(0.015, self.tentacle_p_peak_reference * 1.08)
            if self.tentacle_prev_p_rising and not is_rising and self.tentacle_prev_abs_p >= peak_threshold and self.tentacle_p_peak_cooldown == 0:
                self.tentacle_core_accel_direction *= -1.0
                self.tentacle_p_peak_cooldown = 10
            self.tentacle_prev_p_rising = is_rising
            self.tentacle_prev_abs_p = abs_p
            core_acceleration = float(self.config.get("tentacle_core_base_speed", 0.75))

            def _lerp(a, b, t):
                return float(a) + (float(b) - float(a)) * max(0.0, min(1.0, float(t)))

            if bool(self.config.get("kp_bind_tentacle_core_base_speed_k", False)):
                wmin = float(self.config.get("kp_tentacle_core_base_speed_k_wmin", 0.0))
                wmax = float(self.config.get("kp_tentacle_core_base_speed_k_wmax", 1.2))
                core_acceleration += _lerp(wmin, wmax, normalized_k_speed)
            else:
                core_acceleration += normalized_k_speed * float(self.config.get("tentacle_core_k_speed", 1.2))

            if bool(self.config.get("kp_bind_tentacle_core_base_speed_p", False)):
                wmin = float(self.config.get("kp_tentacle_core_base_speed_p_wmin", 0.0))
                wmax = float(self.config.get("kp_tentacle_core_base_speed_p_wmax", 1.35))
                core_acceleration += _lerp(wmin, wmax, normalized_p_speed)
            else:
                core_acceleration += normalized_p_speed * float(self.config.get("tentacle_core_p_speed", 1.35))
            core_acceleration *= self.tentacle_core_accel_direction
            self.tentacle_core_angular_velocity *= 0.92
            self.tentacle_core_angular_velocity += core_acceleration * 0.0028 * rotation_base
            self.tentacle_core_angular_velocity = float(np.clip(self.tentacle_core_angular_velocity, -0.12, 0.12))
            self.tentacle_core_rotation = (self.tentacle_core_rotation + self.tentacle_core_angular_velocity) % math.tau
        else:
            self.tentacle_core_angular_velocity *= 0.82
        tentacles = self._build_tentacle_curves(cx, cy, radius, scale, shared_lengths)

        bars = []
        if bars_enabled:
            for layer_a, layer_b, key in ((4, 5, "b45"), (3, 4, "b34"), (2, 3, "b23"), (1, 2, "b12")):
                if not self.config.get(f"{key}_on", False):
                    continue
                thickness = int(round(self._runtime_kp_add(f"{key}_thick", float(self.config.get(f"{key}_thick", 3)), normalized_k, normalized_p)))
                thickness = max(1, thickness)
                segments_data = self._build_bar_segments(
                    cx,
                    cy,
                    radius_map[layer_a],
                    radius_map[layer_b],
                    rot[layer_a],
                    rot[layer_b],
                    segments,
                    seg_angle,
                    object_lengths[key],
                    key,
                )
                bars.append({"segments": segments_data, "thickness": thickness})

        lines = []
        if contours_enabled:
            for layer_index in (5, 4, 3, 2, 1):
                if not self.config.get(f"c{layer_index}_on", False):
                    continue
                points = circle_points if layer_index == 3 else contour_points.get(layer_index)
                if points and len(points) >= 3:
                    color = tuple(self.config.get(f"c{layer_index}_color", (255, 255, 255)))
                    transition_alpha = self.config.get(f"_tr_c{layer_index}_alpha")
                    if transition_alpha is None:
                        alpha = int(round(self._runtime_kp_add(f"c{layer_index}_alpha", float(self.config.get(f"c{layer_index}_alpha", 180)), normalized_k, normalized_p)))
                    else:
                        alpha = int(round(float(transition_alpha)))
                    alpha = max(0, min(255, alpha))
                    thickness = int(round(self._runtime_kp_add(f"c{layer_index}_thick", float(self.config.get(f"c{layer_index}_thick", 2)), normalized_k, normalized_p)))
                    thickness = max(1, thickness)
                    lines.append({"points": points, "color": (*color, alpha), "thickness": thickness})

        self.render_state = {"center": (cx, cy), "fills": fills, "tentacles": tentacles, "bars": bars, "lines": lines}

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

    def _paint_fill(self, painter, points, color):
        if not points or len(points) < 3:
            return

        path = QPainterPath()
        first_x, first_y = points[0]
        path.moveTo(QPointF(float(first_x), float(first_y)))
        for pos_x, pos_y in points[1:]:
            path.lineTo(QPointF(float(pos_x), float(pos_y)))
        path.closeSubpath()

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color[0], color[1], color[2], color[3]))
        painter.drawPath(path)

    def _paint_polyline(self, painter, points, color, thickness):
        if not points or len(points) < 2:
            return

        path = QPainterPath()
        first_x, first_y = points[0]
        path.moveTo(QPointF(float(first_x), float(first_y)))
        for pos_x, pos_y in points[1:]:
            path.lineTo(QPointF(float(pos_x), float(pos_y)))

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(self._make_round_pen(color, thickness))
        painter.drawPath(path)

    def _paint_weighted_segments(self, painter, segments):
        if not segments:
            return

        painter.setBrush(Qt.BrushStyle.NoBrush)
        last_style = None
        for start, end, color, thickness in segments:
            style = (color, round(float(thickness), 3))
            if style != last_style:
                painter.setPen(self._make_round_pen(color, thickness))
                last_style = style
            painter.drawLine(
                QPointF(float(start[0]), float(start[1])),
                QPointF(float(end[0]), float(end[1])),
            )

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
                    elif new_config["command"] == "set_window_layer":
                        mode = str(new_config.get("mode", "normal")).lower()
                        if mode not in {"top", "normal", "bottom"}:
                            mode = "normal"
                        self.config["window_layer"] = mode
                        self.config["always_on_top"] = mode == "top"
                        self._apply_window_styles(force=True)
                    elif new_config["command"] == "preset_transition":
                        self._start_transition(
                            new_config.get("from_config", {}),
                            new_config.get("to_config", {}),
                            float(new_config.get("duration", 2.0)),
                            new_config.get("easing", "ease_in_out"),
                        )
                    continue

                normalized_config = _normalize_loaded_config(new_config)
                old = self.config.copy()
                if self._transition_active:
                    self._transition_active = False   # 手动变更打断过渡
                self.config = normalized_config
                new_config = normalized_config
                self.audio_processor.update_config(new_config)
                self._sync_audio_processor_state()

                if int(new_config.get("num_bars", 64)) != self.NUM_BARS:
                    self.NUM_BARS = int(new_config.get("num_bars", 64))
                    old_heights = self.bar_heights.copy()
                    initial_bar_height = self._default_bar_height()
                    self._reset_length_states(initial_bar_height)
                    count = min(len(old_heights), self.NUM_BARS)
                    self.bar_heights[:count] = old_heights[:count]
                    for state in self.object_length_states.values():
                        state[:count] = old_heights[:count]
                    self._update_colors()

                self.smoothing_factor = float(new_config.get("smoothing", 0.7))
                self.a1_time_window = _clamp_time_window(new_config.get("a1_time_window", 10), 10)
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
                self._clamp_center()
        except queue.Empty:
            pass

    def _tick(self):
        self._update_config_from_queue()

        now = time.time()

        if self._transition_active:
            self._update_transition(now)

        if self.config.get("color_dynamic", False):
            base_speed = max(0.0, float(self.config.get("color_cycle_speed", 1.0)))
            peak_speed = max(base_speed, float(self.config.get("color_cycle_pow", 2.0)))
            if self.config.get("color_cycle_a1", True):
                reference = max(2.0, abs(self.a1_value) * 0.08 + 2.0)
                boost_target = math.tanh(abs(self.k2_value) / reference)
                self.current_color_cycle_boost = max(boost_target, self.current_color_cycle_boost * 0.88)
            else:
                self.current_color_cycle_boost *= 0.88
            # V0 直接决定基础速率（boost=0 时），VP 决定加速后的速率
            base_rate = base_speed * 0.001
            boost_extra = ((peak_speed - base_speed) * self.current_color_cycle_boost * 0.001
                           + self.current_color_cycle_boost * 0.008)
            self.current_color_cycle_rate = base_rate + boost_extra
            self.color_cycle_hue = (self.color_cycle_hue + self.current_color_cycle_rate) % 1.0
            self._update_colors()
        else:
            self.current_color_cycle_rate = 0.0
            self.current_color_cycle_boost = 0.0

        audio_frame = self._pull_latest_audio_frame()
        if audio_frame is None:
            bar_values = self._prune_spectrum_history(now)
        else:
            bar_values = self._update_spectrum_history(self._process_audio(audio_frame), now)

        self._update_visual_state(bar_values)
        self.gl_widget.update()
        self.overlay.update()

        if now - self.last_status_send >= 0.12:
            self._send_status()
            self.last_status_send = now

    # ── 预设平滑过渡（透明度淡入淡出版） ─────────────────────────

    def _start_transition(self, from_config, to_config, duration, easing):
        # 清除 from_config 中的运行时 _tr_* 键，避免中途切换带来的脏状态
        clean_from = {k: v for k, v in (from_config or {}).items() if not k.startswith('_tr_')}
        self._transition_from = _normalize_loaded_config(clean_from)
        self._transition_target = _normalize_loaded_config(to_config)
        self._transition_duration = max(0.05, float(duration))
        self._transition_easing = easing if easing else 'ease_in_out'
        self._transition_start = time.time()
        self._transition_active = True
        self._transition_toggle_schedule = []

        # 分别收集需要关闭 / 开启的图元
        turning_off = []  # (on_key, prefix)
        turning_on = []   # (on_key, prefix)
        for key in _ON_FIELD_ORDER:
            from_val = bool(self._transition_from.get(key, False))
            to_val = bool(self._transition_target.get(key, False))
            prefix = key[:-3]          # strip '_on'
            if from_val and not to_val:
                turning_off.append((key, prefix))
            elif not from_val and to_val:
                turning_on.append((key, prefix))

        # 交错排列：off0, on0, off1, on1 ...
        sequence = []
        off_i = on_i = 0
        while off_i < len(turning_off) or on_i < len(turning_on):
            if off_i < len(turning_off):
                sequence.append(('out', turning_off[off_i][0], turning_off[off_i][1]))
                off_i += 1
            if on_i < len(turning_on):
                sequence.append(('in', turning_on[on_i][0], turning_on[on_i][1]))
                on_i += 1

        n = len(sequence)
        self._transition_alpha_schedule = []
        alpha_controlled_keys = set()

        for i, (direction, on_key, prefix) in enumerate(sequence):
            slot_t_start = i / n if n > 0 else 0.0
            slot_t_end = (i + 1) / n if n > 0 else 1.0

            is_circle = prefix.startswith('c') and len(prefix) == 2 and prefix[1:].isdigit()
            is_tentacle_core = (prefix == 'tentacle_core')
            alpha_entries = []

            if is_tentacle_core:
                # tentacle_core 没有独立的透明度渲染，仅在时间槽端点切换开关（快照式）
                pass
            elif is_circle:
                if direction == 'out':
                    from_a = int(self._transition_from.get(f'{prefix}_alpha', 180))
                    alpha_entries.append((f'_tr_{prefix}_alpha', from_a, 0))
                    if self._transition_from.get(f'{prefix}_fill', False):
                        fa = int(self._transition_from.get(f'{prefix}_fill_alpha', 50))
                        alpha_entries.append((f'_tr_{prefix}_fill_alpha', fa, 0))
                else:
                    to_a = int(self._transition_target.get(f'{prefix}_alpha', 180))
                    alpha_entries.append((f'_tr_{prefix}_alpha', 0, to_a))
                    if self._transition_target.get(f'{prefix}_fill', False):
                        ta = int(self._transition_target.get(f'{prefix}_fill_alpha', 50))
                        alpha_entries.append((f'_tr_{prefix}_fill_alpha', 0, ta))
            elif prefix == 'tentacle':
                # 触须：使用 _tr_ 运行时键，起始/结束透明度从配置读取
                if direction == 'out':
                    from_a = float(self._transition_from.get('tentacle_alpha', 170))
                    alpha_entries.append(('_tr_tentacle_alpha', from_a, 0.0))
                    alpha_entries.append(('_tr_tentacle_len_frac', 1.0, 0.0))
                else:
                    to_a = float(self._transition_target.get('tentacle_alpha', 170))
                    alpha_entries.append(('_tr_tentacle_alpha', 0.0, to_a))
                    alpha_entries.append(('_tr_tentacle_len_frac', 0.0, 1.0))
            else:
                # b-层（条形图）：用 _tr_ 运行时键控制 alpha 和长度缩放，不落盘
                if direction == 'out':
                    alpha_entries.append((f'_tr_{prefix}_alpha', 255, 0))
                    alpha_entries.append((f'_tr_{prefix}_len_frac', 1.0, 0.0))
                else:
                    alpha_entries.append((f'_tr_{prefix}_alpha', 0, 255))
                    alpha_entries.append((f'_tr_{prefix}_len_frac', 0.0, 1.0))

            for ak, _, _ in alpha_entries:
                alpha_controlled_keys.add(ak)

            self._transition_alpha_schedule.append({
                'direction': direction,
                'on_key': on_key,
                'prefix': prefix,
                'is_circle': is_circle,
                'alpha_entries': alpha_entries,
                'from_fill': self._transition_from.get(f'{prefix}_fill', False) if is_circle else False,
                'slot_t_start': slot_t_start,
                'slot_t_end': slot_t_end,
            })

        self._transition_alpha_controlled = alpha_controlled_keys

    def _update_transition(self, now):
        elapsed = now - self._transition_start
        t = elapsed / self._transition_duration if self._transition_duration > 0 else 1.0

        if t >= 1.0:
            self.config = self._transition_target.copy()
            self._transition_active = False
            self._update_colors()
            return

        interp = self._transition_target.copy()
        et = _ease_value(t, self._transition_easing)

        from_gradient = self._transition_from.get('gradient_points', [])
        to_gradient = self._transition_target.get('gradient_points', [])
        interp['gradient_points'] = _interpolate_gradient_points(from_gradient, to_gradient, et, count=max(2, len(from_gradient), len(to_gradient), 8))

        # ── 数值插值（跳过透明度调度控制的键和布尔开关）────────────
        skip_interp = _NOINTERP_KEYS | getattr(self, '_transition_alpha_controlled', set())
        for key, from_val in self._transition_from.items():
            if key in skip_interp:
                continue
            to_val = self._transition_target.get(key)
            if to_val is None:
                continue
            if isinstance(from_val, (int, float)) and isinstance(to_val, (int, float)):
                interp[key] = from_val + (to_val - from_val) * et
            elif (
                isinstance(from_val, (list, tuple)) and isinstance(to_val, (list, tuple))
                and len(from_val) == 3 and len(to_val) == 3
                and all(isinstance(x, (int, float)) for x in from_val)
                and all(isinstance(x, (int, float)) for x in to_val)
            ):
                interp[key] = tuple(
                    int(round(from_val[i] + (to_val[i] - from_val[i]) * et))
                    for i in range(3)
                )

        # ── 所有 _on 字段先恢复 from 状态，由时间表覆盖 ────────────
        for key in _ON_FIELD_ORDER:
            interp[key] = self._transition_from.get(key, False)

        # ── 透明度淡入/淡出时间表 ──────────────────────────────────
        for entry in getattr(self, '_transition_alpha_schedule', []):
            direction = entry['direction']
            on_key = entry['on_key']
            prefix = entry['prefix']
            alpha_entries = entry['alpha_entries']
            is_circle = entry['is_circle']
            from_fill = entry.get('from_fill', False)
            s0 = entry['slot_t_start']
            s1 = entry['slot_t_end']

            if direction == 'in':
                if t < s0:
                    # 尚未到时间槽：元素处于隐藏状态（预透明度=0）
                    interp[on_key] = False
                    for ak, from_a, _ in alpha_entries:
                        interp[ak] = 0.0 if isinstance(from_a, float) else 0
                else:
                    # 时间槽内或之后：已开启，透明度从0渐入
                    interp[on_key] = True
                    slot_et = _ease_value(
                        min(1.0, (t - s0) / max(1e-9, s1 - s0)),
                        self._transition_easing)
                    for ak, from_a, to_a in alpha_entries:
                        _v = from_a + (to_a - from_a) * slot_et
                        interp[ak] = _v if isinstance(from_a, float) else int(round(_v))
            else:  # 'out'
                if t < s0:
                    # 时间槽前：保持原透明度和填充
                    interp[on_key] = True
                    for ak, from_a, _ in alpha_entries:
                        interp[ak] = from_a
                    if from_fill:
                        interp[f'{prefix}_fill'] = True
                elif t < s1:
                    # 时间槽内：淡出
                    interp[on_key] = True
                    slot_et = _ease_value(
                        (t - s0) / max(1e-9, s1 - s0),
                        self._transition_easing)
                    for ak, from_a, to_a in alpha_entries:
                        _v = from_a + (to_a - from_a) * slot_et
                        interp[ak] = _v if isinstance(from_a, float) else int(round(_v))
                    if from_fill:
                        interp[f'{prefix}_fill'] = True
                else:
                    # 时间槽后：关闭，透明度归零
                    interp[on_key] = False
                    for ak, _, _ in alpha_entries:
                        interp[ak] = 0.0 if isinstance(_, float) else 0

                # b-层有 _tr_ alpha，淡出结束后隐藏（on_key 已设为 False）

        self.config = interp
        self._update_colors()

    def _cleanup(self):
        if self.audio_capture is not None:
            self.audio_capture.close()
            self.audio_capture = None
        print("PyOpenGL 圆形频谱窗口已关闭")




# ============================================================================
# 嵌入模式组合控件 — 供 main.pyw 通过 MODULE_WIDGET 调用
# ============================================================================

class EmbeddedVisualizerModule(QWidget):
    """
    将 CircularVisualizerWindow（渲染）和 VisualizerControlUI（控制面板）
    合并为一个可嵌入 QWidget，供 main.pyw 的 QStackedWidget 使用。

    布局：左侧（2/3）= 渲染画布，右侧（1/3）= 控制面板。
    通讯：通过 queue.Queue（同进程），不再 mp.Process。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        import queue

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        from PySide6.QtWidgets import QSplitter
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setHandleWidth(4)
        outer.addWidget(splitter)

        self._config_q = queue.Queue(maxsize=1)
        self._status_q = queue.Queue(maxsize=1)

        self._viz = CircularVisualizerWindow(
            config_queue=self._config_q,
            status_queue=self._status_q,
            embedded=True,
            parent=splitter,
        )
        self._viz.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        splitter.addWidget(self._viz)

        self._ctrl = VisualizerControlUI()
        self._ctrl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        splitter.addWidget(self._ctrl)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)

        self._patch_ctrl()
        try:
            self._config_q.put_nowait(self._ctrl.config)
        except Exception:
            pass
        self._viz.run_embedded()

    def _patch_ctrl(self):
        """让 VisualizerControlUI 通过 queue.Queue 与嵌入渲染器通讯。"""
        ctrl  = self._ctrl
        viz   = self._viz
        cfg_q = self._config_q
        sts_q = self._status_q

        ctrl.config_queue = cfg_q
        ctrl.status_queue = sts_q

        # 用假进程对象阻止 VisualizerControlUI.__init__ 里的 QTimer.singleShot(100,
        # self._start_visualizer) 触发旧版子进程逻辑（该方法首行判断 viz_process.is_alive()）
        class _FakeAliveProcess:
            def is_alive(self):
                return True
        ctrl.viz_process = _FakeAliveProcess()

        def _start_embedded():
            try:
                cfg_q.put_nowait(ctrl.config)
            except Exception:
                pass
            viz.run_embedded()
            ctrl.status_timer.start(100)

        def _stop_embedded():
            ctrl.status_timer.stop()
            try:
                viz.frame_timer.stop()
                viz._cleanup()
            except Exception:
                pass

        ctrl._start_visualizer = _start_embedded
        ctrl._stop_visualizer  = _stop_embedded
        ctrl.status_timer.start(100)

    def _stop_visualizer(self):
        """main.pyw closeEvent 调用的清理入口。"""
        try:
            self._ctrl._stop_visualizer()
        except Exception:
            pass
        try:
            self._viz.frame_timer.stop()
            self._viz._cleanup()
        except Exception:
            pass


MODULE_WIDGET = EmbeddedVisualizerModule

if __name__ == "__main__":
    main()
