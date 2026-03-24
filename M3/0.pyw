"""
音频可视化控制台 - 主框架
支持选择不同可视化模式（当前仅圆形频谱）
通过 multiprocessing 启动子程序并实时传递配置
"""

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
    QInputDialog, QDialog, QListWidget, QLineEdit,
    QFrame, QMessageBox, QScrollArea,
    QStackedWidget,
    QTreeWidget, QTreeWidgetItem,
    QMenu,
    QAbstractSpinBox,
    QProxyStyle, QStyle, QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer, Signal, QPoint, QRectF
from PySide6.QtGui import QFont, QColor, QPalette, QPainter, QPen, QCursor, QLinearGradient

CONFIG_FILE = Path(__file__).parent / 'visualizer_config.json'
PRESETS_DIR = Path(__file__).parent / 'presets'
SECTION_PRESETS_DIR = Path(__file__).parent / 'section_presets'

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
    'random_checked': [],
    'random_object_count_min': 1,
    'random_object_count_max': 10,
    'preset_order': [],
    'preset_auto_switch': False,
    'preset_switch_interval': 10.0,
    'preset_interval_random_enabled': False,
    'preset_switch_interval_min': 1.0,
    'preset_switch_interval_max': 10.0,
    'preset_transition_enabled': False,
    'preset_transition_duration': 2.0,
    'preset_transition_easing': 'ease_in_out',
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
        lbl.setFixedWidth(12)
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

        # S：固定 H/L，0→1
        r0, g0, b0 = self._hsl_to_rgb(h, 0.0, l)
        r1, g1, b1 = self._hsl_to_rgb(h, 100.0, l)
        self._set_slider_gradient(self._sat_slider, [(0.0, (r0, g0, b0)), (1.0, (r1, g1, b1))])

        # L：固定 H/S，0→1
        r2, g2, b2 = self._hsl_to_rgb(h, s, 0.0)
        r3, g3, b3 = self._hsl_to_rgb(h, s, 100.0)
        self._set_slider_gradient(self._light_slider, [(0.0, (r2, g2, b2)), (1.0, (r3, g3, b3))])

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
            h, s, l = self._rgb_to_hsl(self.selected_rgb)
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
                    return _normalize_loaded_config(json.load(f))
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
        }
        save_data['_theme_mix'] = self._build_theme_mix_payload(save_data)
        return save_data

    def _inflate_loaded_preset_data(self, raw_data):
        if not isinstance(raw_data, dict):
            return {}
        config_data = {key: value for key, value in raw_data.items() if not str(key).startswith('_')}
        theme_mix = raw_data.get('_theme_mix', {})
        if isinstance(theme_mix, dict):
            for section_data in theme_mix.values():
                if isinstance(section_data, dict):
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
            'tentacle_core_k_speed', 'tentacle_core_p_speed'
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
        grid.addWidget(label, row, 0)
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
        grid.addWidget(slider, row, 1, 1, 2)
        grid.addWidget(box, row, 3)
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
        grid.addWidget(label, row, 0)
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
        grid.addWidget(box, row, 3)
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
                              step=1, width=62, suffix=''):
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
                                slider_scale=100, step=0.01, decimals=2, width=68, suffix=''):
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
        self.pin_top_btn.clicked.connect(lambda: self._set_window_layer_mode('top'))
        top_action_row.addWidget(self.pin_top_btn)

        self.pin_bottom_btn = QPushButton("置于底层")
        self.pin_bottom_btn.setMinimumHeight(24)
        self.pin_bottom_btn.clicked.connect(lambda: self._set_window_layer_mode('bottom'))
        top_action_row.addWidget(self.pin_bottom_btn)

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

        tg.addWidget(QLabel("预设管理:"), r, 0)
        self.preset_combo = QComboBox()
        self.preset_combo.setEditable(False)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        tg.addWidget(self.preset_combo, r, 1, 1, 3)

        b_prev = QPushButton("上一个")
        b_prev.setMinimumHeight(24)
        b_prev.clicked.connect(lambda: self._switch_preset_by_offset(-1, update_info=True))
        tg.addWidget(b_prev, r, 4)

        b_next = QPushButton("下一个")
        b_next.setMinimumHeight(24)
        b_next.clicked.connect(lambda: self._switch_preset_by_offset(1, update_info=True))
        tg.addWidget(b_next, r, 5)

        b_save = QPushButton("另存为")
        b_save.setMinimumHeight(24)
        b_save.clicked.connect(self._save_preset_as)
        tg.addWidget(b_save, r, 6)

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

        preset_row.addWidget(QLabel("间隔"))
        self.preset_interval_spin = self._new_float_box(
            default_value=10.0, soft_min=0.01, soft_max=3600.0,
            hard_min=0.0, hard_max=86400.0, step=0.01, decimals=2,
            suffix=' 秒', value=self.config.get('preset_switch_interval', 10.0)
        )
        self.preset_interval_spin.valueChanged.connect(self._on_preset_interval_changed)
        preset_row.addWidget(self.preset_interval_spin)

        self.preset_interval_random_check = QCheckBox("随机间隔随机")
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
        palette_row = QHBoxLayout(); palette_row.setSpacing(4)
        for _ in range(8):
            cell = QFrame()
            cell.setFixedSize(22, 22)
            cell.setFrameShape(QFrame.StyledPanel)
            cell.setStyleSheet("border:1px solid #666; border-radius:2px;")
            self.palette_preview_cells.append(cell)
            idx = len(self.palette_preview_cells) - 1
            # allow clicking the small preview cell to edit color
            cell.setCursor(Qt.PointingHandCursor)
            def _make_handler(i):
                return lambda ev: self._on_palette_cell_clicked(i)
            cell.mousePressEvent = _make_handler(idx)
            palette_row.addWidget(cell)
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

        self.preview_toggle_btn = QPushButton("▾ 图形预览")
        self.preview_toggle_btn.setCheckable(True)
        self.preview_toggle_btn.setChecked(True)
        self.preview_toggle_btn.toggled.connect(self._toggle_preview_sidebar)
        left_layout.addWidget(self.preview_toggle_btn)

        self.preview_sidebar = QWidget()
        preview_sidebar_layout = QVBoxLayout(self.preview_sidebar)
        preview_sidebar_layout.setContentsMargins(0, 0, 0, 0)
        preview_sidebar_layout.setSpacing(0)
        preview_sidebar_layout.addWidget(self.single_bar_panel)
        left_layout.addWidget(self.preview_sidebar)

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
            (("主题设置", "经典", "填充主题"), self._build_fill_theme_section()),
            (("主题设置", "经典", "连线主题"), self._build_line_theme_section()),
            (("主题设置", "柔体主题"), self._build_softbody_theme_section()),
            (("控制",), self._build_control_section()),
            (("颜色方案",), self._build_color_section()),
            (("运动表现",), self._build_physics_section()),
            (("高级控制",), self._build_k1_section()),
            (("🎲 随机",), self._build_random_section()),
        ]

        theme_toggle_sections = {
            ("主题设置", "经典"): 'theme_classic_kaleidoscope',
            ("主题设置", "经典", "填充主题"): 'theme_kaleidoscope_fill',
            ("主题设置", "经典", "连线主题"): 'theme_kaleidoscope_lines',
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
        self.preview_sidebar.setVisible(bool(expanded))
        self.preview_toggle_btn.setText("▾ 图形预览" if expanded else "▸ 图形预览")

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
        self.preset_interval_random_check = QCheckBox("随机间隔随机")
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

    def _get_ordered_preset_files(self):
        files = sorted(PRESETS_DIR.glob('*.json'), key=lambda p: p.name.lower())
        order = [str(x) for x in self.config.get('preset_order', []) if str(x).strip()]
        if not order:
            return files
        by_stem = {fp.stem: fp for fp in files}
        ordered = [by_stem[s] for s in order if s in by_stem]
        ordered.extend([fp for fp in files if fp.stem not in order])
        return ordered

    def _save_preset_order(self, stems):
        self.config['preset_order'] = [str(s) for s in stems if str(s).strip()]
        self._schedule_config_commit()

    def _refresh_preset_list(self):
        self._ensure_presets_dir()
        current_fp = self.preset_combo.currentData()
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        valid_files = []
        invalid_files = []
        for fp in self._get_ordered_preset_files():
            error = self._validate_preset_file(fp)
            if error:
                invalid_files.append((fp, error))
                continue
            valid_files.append(fp)
        selected_idx = -1
        for fp in valid_files:
            self.preset_combo.addItem(fp.stem, str(fp))
            if current_fp and str(fp) == str(current_fp):
                selected_idx = self.preset_combo.count() - 1
        # 清理不存在的排序项
        normalized_order = [Path(self.preset_combo.itemData(i)).stem for i in range(self.preset_combo.count())]
        if normalized_order != self.config.get('preset_order', []):
            self.config['preset_order'] = normalized_order
            self._schedule_config_commit()
        if selected_idx >= 0:
            self.preset_combo.setCurrentIndex(selected_idx)
        elif self.preset_combo.count() > 0:
            self.preset_combo.setCurrentIndex(0)
        self.preset_combo.blockSignals(False)
        self._update_preset_preview()
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
            for fp in self._get_ordered_preset_files():
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

    def _on_preset_auto_toggled(self, v):
        self._update_cfg('preset_auto_switch', v)
        if v:
            self._schedule_next_preset_switch()
        else:
            self.preset_timer.stop()

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

    def _auto_switch_preset(self):
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
            save_data = self._build_full_preset_payload()
            with open(fp, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
            self._refresh_preset_list()
            idx = self.preset_combo.findText(safe_name)
            if idx >= 0:
                self.preset_combo.setCurrentIndex(idx)
            QMessageBox.information(self, "成功", f"预设已保存: {safe_name}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存预设失败: {e}")

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
            idx = self.preset_combo.findText(safe_name)
            if idx >= 0:
                self.preset_combo.setCurrentIndex(idx)
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
                'preset_switch_interval',
                'preset_interval_random_enabled',
                'preset_switch_interval_min',
                'preset_switch_interval_max',
                'preset_transition_enabled',
                'preset_transition_duration',
                'preset_transition_easing',
                'window_layer',
            )
            for key in runtime_keep_keys:
                cfg[key] = self.config.get(key, cfg.get(key))
            self._apply_config_to_ui(cfg)
            # 若启用平滑过渡，替换队列为过渡指令
            if self.config.get('preset_transition_enabled', False) and self.viz_process and self.viz_process.is_alive():
                self._send_transition_command(from_config)
            self._set_info_bar(f"已加载预设: {Path(fp).stem}")
            if show_message:
                QMessageBox.information(self, "成功", f"已加载预设: {Path(fp).stem}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载预设失败: {e}")

    def _send_transition_command(self, from_config):
        if not self.config_queue:
            return
        cmd = {
            'command': 'preset_transition',
            'from_config': {k: v for k, v in from_config.items()},
            'to_config': {k: v for k, v in self.config.items()},
            'duration': float(self.config.get('preset_transition_duration', 2.0)),
            'easing': 'cubic',
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
        info = QLabel('经典主题由填充与连线两个子主题组成。启用请使用左侧树行右侧的小复选框，子主题细节请进入下级页面。')
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
        info = QLabel('启用请使用左侧树行右侧的小复选框。这里保留填充子主题的参数与子预设。')
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
        v.addLayout(self._build_section_action_row('graphics'))
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
        contour_keys = []
        for li in range(1, 6):
            contour_keys.extend([
                f'c{li}_on', f'c{li}_color', f'c{li}_alpha', f'c{li}_thick',
                f'c{li}_fill', f'c{li}_fill_alpha', f'c{li}_rot_speed', f'c{li}_rot_pow'
            ])
            if li in (1, 2, 4, 5):
                contour_keys.append(f'c{li}_step')
                contour_keys.extend([
                    f'c{li}_use_independent_damping',
                    f'c{li}_independent_rise_damping',
                    f'c{li}_independent_fall_damping',
                ])
            if li in (1, 5):
                contour_keys.append(f'c{li}_decay')
        contour_keys.extend(_kp_binding_config_keys(_CONTOUR_KP_KEYS))

        bar_keys = []
        for key in ('b12', 'b23', 'b34', 'b45'):
            bar_keys.extend([
                f'{key}_on', f'{key}_thick', f'{key}_fixed', f'{key}_fixed_len',
                f'{key}_from_start', f'{key}_from_end', f'{key}_from_center',
                f'{key}_use_independent_damping', f'{key}_independent_rise_damping', f'{key}_independent_fall_damping'
            ])
            bar_keys.extend(_kp_binding_config_keys(_BAR_KP_KEYS))

        softbody_keys = [
            'tentacles_enabled', 'tentacle_on', 'tentacle_color', 'tentacle_alpha', 'tentacle_thick',
            'tentacle_count', 'tentacle_length', 'tentacle_length_jitter', 'tentacle_length_jitter_speed',
            'tentacle_length_jitter_random', 'tentacle_control_points_min', 'tentacle_control_points_max',
            'tentacle_tip_bias', 'tentacle_turbulence', 'tentacle_k_influence', 'tentacle_sway_speed',
            'tentacle_sway_density', 'tentacle_tip_thickness', 'tentacle_water_damping',
            'tentacle_angle_stiffness', 'tentacle_length_stiffness', 'tentacle_stretch_limit',
            'tentacle_shader_enabled', 'tentacle_shader_tip_color', 'tentacle_shader_alpha_start',
            'tentacle_shader_alpha_end', 'tentacle_shader_bias', 'tentacle_core_on',
            'tentacle_core_base_speed', 'tentacle_core_k_speed', 'tentacle_core_p_speed',
            'kp_bind_tentacle_turbulence_k', 'kp_tentacle_turbulence_k_wmin', 'kp_tentacle_turbulence_k_wmax',
            'kp_bind_tentacle_core_base_speed_k', 'kp_tentacle_core_base_speed_k_wmin', 'kp_tentacle_core_base_speed_k_wmax',
            'kp_bind_tentacle_core_base_speed_p', 'kp_tentacle_core_base_speed_p_wmin', 'kp_tentacle_core_base_speed_p_wmax',
        ]

        if section == 'color':
            return [
                'color_scheme', 'gradient_enabled', 'gradient_mode', 'gradient_points',
                'color_dynamic', 'color_cycle_speed', 'color_cycle_pow', 'color_cycle_a1'
            ]
        if section == 'physics':
            return [
                'rotation_base', 'main_radius_scale',
                'a1_time_window', 'bar_use_independent_time_window', 'bar_time_window',
                'k_rise_damping', 'k_fall_damping',
                'bar_use_independent_damping', 'bar_independent_rise_damping', 'bar_independent_fall_damping',
                'bar_default_height', 'bar_internal_min', 'bar_internal_max',
                'bar_height_min', 'bar_height_max'
            ]
        if section == 'theme_classic_kaleidoscope':
            return ['contours_enabled', 'bars_enabled'] + contour_keys + bar_keys
        if section == 'theme_kaleidoscope_fill':
            return ['contours_enabled'] + contour_keys
        if section == 'theme_kaleidoscope_lines':
            return ['bars_enabled'] + bar_keys
        if section == 'theme_softbody':
            return softbody_keys
        if section == 'graphics':
            return ['contours_enabled', 'bars_enabled'] + contour_keys + bar_keys + softbody_keys
        return []

    def _randomize_section(self, section: str):
        if section == 'theme_classic_kaleidoscope':
            self.config['contours_enabled'] = True
            self.config['bars_enabled'] = True
        elif section == 'theme_kaleidoscope_fill':
            self.config['contours_enabled'] = True
        elif section == 'theme_kaleidoscope_lines':
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
            if section == 'graphics':
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
        title = self._section_display_name(section)
        name, ok = QInputDialog.getText(self, f"保存{title}", "请输入名称:", text=default_name)
        if not ok:
            return
        safe = self._safe_preset_name(name)
        if not safe:
            QMessageBox.warning(self, "无效名称", "名称不能为空或仅包含非法字符")
            return

        presets = self._read_section_presets(section)
        presets[safe] = {k: self.config.get(k) for k in keys}
        try:
            self._write_section_presets(section, presets)
            self._refresh_section_preset_combo(section)
            if combo is not None:
                combo.setCurrentText(safe)
            self._set_info_bar(f"已保存{title}: {safe}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存{title}失败: {e}")

    def _load_section_preset(self, section: str):
        keys = self._section_keys(section)
        if not keys:
            return
        combo = self._section_preset_combos.get(section)
        if combo is None:
            return
        title = self._section_display_name(section)
        name = combo.currentText().strip()
        if not name:
            QMessageBox.warning(self, "提示", f"请先选择{title}")
            return
        presets = self._read_section_presets(section)
        data = presets.get(name)
        if not isinstance(data, dict):
            QMessageBox.warning(self, "提示", f"{title}不存在或已损坏")
            self._refresh_section_preset_combo(section)
            return
        for key in keys:
            if key in data:
                self.config[key] = data[key]
        self._apply_config_to_ui(self.config)
        self._set_info_bar(f"已读取{title}: {name}")

    # ── 五层轮廓 ──────────────────────────────────────────

    def _build_contour_section(self):
        s = _Collapsible("五层轮廓 (L1~L5)", expanded=False)
        g = QGridLayout(); g.setSpacing(3); g.setContentsMargins(0,0,0,0); r = 0
        _layers = [
            (1, "L1 内缓慢", True, True),
            (2, "L2 内快速", True, False),
            (3, "L3 基圆",   False, False),
            (4, "L4 外快速", True, False),
            (5, "L5 外缓慢", True, True),
        ]
        for li, lname, has_step, has_decay in _layers:
            hdr = QLabel(f"── {lname} ──")
            hdr.setStyleSheet("color:#888; font-size:8pt; padding:3px 0 1px 0;")
            g.addWidget(hdr, r, 0, 1, 4); r += 1

            chk = QCheckBox("显示")
            chk.setChecked(self.config.get(f'c{li}_on', False))
            chk.toggled.connect(lambda v, k=f'c{li}_on': self._update_cfg(k, v))
            setattr(self, f'c{li}_on_check', chk)
            g.addWidget(chk, r, 0)

            cbtn = QPushButton()
            cc = self.config.get(f'c{li}_color', (255, 255, 255))
            cbtn.setFixedSize(22, 22)
            cbtn.setStyleSheet(f"background:rgb({cc[0]},{cc[1]},{cc[2]}); border:1px solid #aaa; border-radius:2px;")
            cbtn.clicked.connect(lambda _, i=li: self._pick_layer_color(i))
            setattr(self, f'c{li}_color_btn', cbtn)
            g.addWidget(cbtn, r, 1)

            sp = self._new_int_box(
                default_value=2, soft_min=1, soft_max=20,
                hard_min=1, hard_max=1000, step=1, cfg_key=f'c{li}_thick'
            )
            setattr(self, f'c{li}_thick_spin', sp)
            ht = QHBoxLayout()
            thick_label = self._attach_kp_bindable_label(QLabel("粗:"), f'c{li}_thick', supports=('k', 'p'))
            ht.addWidget(thick_label); ht.addWidget(sp)
            g.addLayout(ht, r, 2, 1, 2); r += 1
            thick_bind, thick_base_lbl, thick_rows, thick_weight_spins = self._build_kp_binding_container(
                cfg_key=f'c{li}_thick', supports=('k', 'p'),
                wmin_default=0.0, wmax_default=0.0,
                soft_min=-6.0, soft_max=6.0, hard_min=-100.0, hard_max=100.0,
                decimals=2,
            )
            g.addWidget(thick_bind, r, 0, 1, 4); r += 1
            self._register_kp_binding_ui(
                cfg_key=f'c{li}_thick', label=thick_label,
                container=thick_bind, base_label=thick_base_lbl,
                rows=thick_rows, supports=('k', 'p'), weight_spins=thick_weight_spins,
            )

            r, _alpha_label, sl_a, alpha_box = self._add_kp_slider_row(
                g, r,
                label_text='透明:', cfg_key=f'c{li}_alpha',
                default_value=180,
                soft_min=0, soft_max=255, hard_min=0, hard_max=255,
                integer=True, step=1, width=58,
                kp_soft_min=-80.0, kp_soft_max=80.0, kp_hard_min=-255.0, kp_hard_max=255.0, kp_decimals=1,
            )
            setattr(self, f'c{li}_alpha_slider', sl_a)
            setattr(self, f'c{li}_alpha_spin', alpha_box)

            fc = QCheckBox("填充")
            fc.setChecked(self.config.get(f'c{li}_fill', False))
            fc.toggled.connect(lambda v, k=f'c{li}_fill': self._update_cfg(k, v))
            setattr(self, f'c{li}_fill_check', fc)
            g.addWidget(fc, r, 0)
            r += 1
            r, _fill_alpha_label, fsl, fill_box = self._add_kp_slider_row(
                g, r,
                label_text='填充透明:', cfg_key=f'c{li}_fill_alpha',
                default_value=50,
                soft_min=0, soft_max=255, hard_min=0, hard_max=255,
                integer=True, step=1, width=58,
                kp_soft_min=-80.0, kp_soft_max=80.0, kp_hard_min=-255.0, kp_hard_max=255.0, kp_decimals=1,
            )
            setattr(self, f'c{li}_fill_alpha_slider', fsl)
            setattr(self, f'c{li}_fill_alpha_spin', fill_box)

            if has_step:
                r, _step_label, ssp = self._add_kp_spin_row(
                    g, r,
                    label_text='间隔:', cfg_key=f'c{li}_step',
                    default_value=2,
                    soft_min=1, soft_max=32, hard_min=1, hard_max=4096,
                    integer=True, step=1,
                    kp_soft_min=-8.0, kp_soft_max=8.0, kp_hard_min=-256.0, kp_hard_max=256.0, kp_decimals=2,
                )
                setattr(self, f'c{li}_step_spin', ssp)

            if has_decay:
                r, _decay_label, dsl, decay_box = self._add_kp_slider_row(
                    g, r,
                    label_text='衰减:', cfg_key=f'c{li}_decay',
                    default_value=0.995,
                    soft_min=0.9, soft_max=1.0, hard_min=0.0, hard_max=2.0,
                    slider_scale=1000, step=0.001, decimals=3, width=72,
                    kp_soft_min=-0.2, kp_soft_max=0.2, kp_hard_min=-2.0, kp_hard_max=2.0, kp_decimals=4,
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
                label_text='转速:', cfg_key=f'c{li}_rot_speed',
                default_value=1.0,
                soft_min=-5.0, soft_max=5.0, hard_min=-100.0, hard_max=100.0,
                slider_scale=100, step=0.01, decimals=2, width=72,
                kp_soft_min=-5.0, kp_soft_max=5.0, kp_hard_min=-100.0, kp_hard_max=100.0, kp_decimals=3,
            )
            setattr(self, f'c{li}_rot_speed_slider', rsl)
            setattr(self, f'c{li}_rot_speed_spin', speed_box)

            r, _pow_label, psl, pow_box = self._add_kp_slider_row(
                g, r,
                label_text='pow:', cfg_key=f'c{li}_rot_pow',
                default_value=0.5,
                soft_min=-3.0, soft_max=3.0, hard_min=-100.0, hard_max=100.0,
                slider_scale=100, step=0.01, decimals=2, width=72,
                kp_soft_min=-3.0, kp_soft_max=3.0, kp_hard_min=-100.0, kp_hard_max=100.0, kp_decimals=3,
            )
            setattr(self, f'c{li}_rot_pow_slider', psl)
            setattr(self, f'c{li}_rot_pow_spin', pow_box)

        s.add_layout(g)
        return s

    def _build_tentacle_section(self):
        s = _Collapsible("水母", expanded=True)
        g = QGridLayout(); g.setSpacing(3); g.setContentsMargins(0, 0, 0, 0); r = 0

        chk = QCheckBox("显示")
        chk.setChecked(self.config.get('tentacle_on', True))
        chk.toggled.connect(lambda v: self._update_cfg('tentacle_on', v))
        self.tentacle_on_check = chk
        g.addWidget(chk, r, 0)

        cbtn = QPushButton()
        cc = self.config.get('tentacle_color', (130, 240, 220))
        cbtn.setFixedSize(22, 22)
        cbtn.setStyleSheet(f"background:rgb({cc[0]},{cc[1]},{cc[2]}); border:1px solid #aaa; border-radius:2px;")
        cbtn.clicked.connect(lambda: self._pick_special_color('tentacle_color', self.tentacle_color_btn))
        self.tentacle_color_btn = cbtn
        g.addWidget(cbtn, r, 1)

        sp = self._new_int_box(
            default_value=3, soft_min=1, soft_max=12,
            hard_min=1, hard_max=1000, step=1, cfg_key='tentacle_thick'
        )
        self.tentacle_thick_spin = sp
        thick_label = self._attach_kp_bindable_label(QLabel("根部粗:"), 'tentacle_thick', supports=('k', 'p'))
        ht = QHBoxLayout(); ht.setSpacing(6)
        ht.addWidget(thick_label); ht.addWidget(sp)
        g.addLayout(ht, r, 2, 1, 2); r += 1

        thick_bind, thick_base_lbl, thick_rows, thick_weight_spins = self._build_kp_binding_container(
            cfg_key='tentacle_thick', supports=('k', 'p'),
            wmin_default=0.0, wmax_default=0.0,
            soft_min=-6.0, soft_max=6.0, hard_min=-200.0, hard_max=200.0,
            decimals=2,
        )
        g.addWidget(thick_bind, r, 0, 1, 4); r += 1
        self._register_kp_binding_ui(
            cfg_key='tentacle_thick', label=thick_label,
            container=thick_bind, base_label=thick_base_lbl,
            rows=thick_rows, supports=('k', 'p'), weight_spins=thick_weight_spins,
        )

        alpha_label = self._attach_kp_bindable_label(QLabel("透明:"), 'tentacle_alpha', supports=('k', 'p'))
        g.addWidget(alpha_label, r, 0)
        sl_a, alpha_box = self._new_bound_int_slider(
            cfg_key='tentacle_alpha', default_value=170,
            soft_min=0, soft_max=255, hard_min=0, hard_max=255,
            step=1, width=58
        )
        self.tentacle_alpha_slider = sl_a
        self.tentacle_alpha_spin = alpha_box
        g.addWidget(sl_a, r, 1, 1, 2); g.addWidget(alpha_box, r, 3); r += 1

        alpha_bind, alpha_base_lbl, alpha_rows, alpha_weight_spins = self._build_kp_binding_container(
            cfg_key='tentacle_alpha', supports=('k', 'p'),
            wmin_default=0.0, wmax_default=0.0,
            soft_min=-80.0, soft_max=80.0, hard_min=-255.0, hard_max=255.0,
            decimals=1,
        )
        g.addWidget(alpha_bind, r, 0, 1, 4); r += 1
        self._register_kp_binding_ui(
            cfg_key='tentacle_alpha', label=alpha_label,
            container=alpha_bind, base_label=alpha_base_lbl,
            rows=alpha_rows, supports=('k', 'p'), weight_spins=alpha_weight_spins,
        )

        cnt_label = self._attach_kp_bindable_label(QLabel("数量:"), 'tentacle_count', supports=('k', 'p'))
        g.addWidget(cnt_label, r, 0)
        cnt_slider, cnt_box = self._new_bound_int_slider(
            cfg_key='tentacle_count', default_value=16,
            soft_min=4, soft_max=32, hard_min=1, hard_max=128,
            step=1, width=72
        )
        self.tentacle_count_slider = cnt_slider
        self.tentacle_count_spin = cnt_box
        g.addWidget(cnt_slider, r, 1, 1, 2); g.addWidget(cnt_box, r, 3); r += 1

        cnt_bind, cnt_base_lbl, cnt_rows, cnt_weight_spins = self._build_kp_binding_container(
            cfg_key='tentacle_count', supports=('k', 'p'),
            wmin_default=0.0, wmax_default=0.0,
            soft_min=-12.0, soft_max=12.0, hard_min=-256.0, hard_max=256.0,
            decimals=2,
        )
        g.addWidget(cnt_bind, r, 0, 1, 4); r += 1
        self._register_kp_binding_ui(
            cfg_key='tentacle_count', label=cnt_label,
            container=cnt_bind, base_label=cnt_base_lbl,
            rows=cnt_rows, supports=('k', 'p'), weight_spins=cnt_weight_spins,
        )

        len_label = self._attach_kp_bindable_label(QLabel("长度:"), 'tentacle_length', supports=('k', 'p'))
        g.addWidget(len_label, r, 0)
        len_slider, len_box = self._new_bound_float_slider(
            cfg_key='tentacle_length', default_value=280.0,
            soft_min=40.0, soft_max=600.0, hard_min=0.0, hard_max=4000.0,
            slider_scale=10, step=0.1, decimals=1, width=72
        )
        self.tentacle_length_slider = len_slider
        self.tentacle_length_spin = len_box
        g.addWidget(len_slider, r, 1, 1, 2); g.addWidget(len_box, r, 3); r += 1

        len_bind, len_base_lbl, len_rows, len_weight_spins = self._build_kp_binding_container(
            cfg_key='tentacle_length', supports=('k', 'p'),
            wmin_default=0.0, wmax_default=0.0,
            soft_min=-240.0, soft_max=240.0, hard_min=-4000.0, hard_max=4000.0,
            decimals=2,
        )
        g.addWidget(len_bind, r, 0, 1, 4); r += 1
        self._register_kp_binding_ui(
            cfg_key='tentacle_length', label=len_label,
            container=len_bind, base_label=len_base_lbl,
            rows=len_rows, supports=('k', 'p'), weight_spins=len_weight_spins,
        )

        jitter_label = self._attach_kp_bindable_label(QLabel("扰动长度:"), 'tentacle_length_jitter', supports=('k', 'p'))
        g.addWidget(jitter_label, r, 0)
        jitter_slider, jitter_box = self._new_bound_float_slider(
            cfg_key='tentacle_length_jitter', default_value=80.0,
            soft_min=0.0, soft_max=240.0, hard_min=0.0, hard_max=2000.0,
            slider_scale=10, step=0.1, decimals=1, width=72
        )
        self.tentacle_length_jitter_slider = jitter_slider
        self.tentacle_length_jitter_spin = jitter_box
        g.addWidget(jitter_slider, r, 1, 1, 2); g.addWidget(jitter_box, r, 3); r += 1

        jitter_bind, jitter_base_lbl, jitter_rows, jitter_weight_spins = self._build_kp_binding_container(
            cfg_key='tentacle_length_jitter', supports=('k', 'p'),
            wmin_default=0.0, wmax_default=0.0,
            soft_min=-240.0, soft_max=240.0, hard_min=-2000.0, hard_max=2000.0,
            decimals=2,
        )
        g.addWidget(jitter_bind, r, 0, 1, 4); r += 1
        self._register_kp_binding_ui(
            cfg_key='tentacle_length_jitter', label=jitter_label,
            container=jitter_bind, base_label=jitter_base_lbl,
            rows=jitter_rows, supports=('k', 'p'), weight_spins=jitter_weight_spins,
        )

        jitter_spd_label = self._attach_kp_bindable_label(QLabel("扰动速度:"), 'tentacle_length_jitter_speed', supports=('k', 'p'))
        g.addWidget(jitter_spd_label, r, 0)
        jitter_spd_slider, jitter_spd_box = self._new_bound_float_slider(
            cfg_key='tentacle_length_jitter_speed', default_value=0.35,
            soft_min=0.0, soft_max=3.0, hard_min=0.0, hard_max=20.0,
            slider_scale=100, step=0.01, decimals=2, width=72
        )
        self.tentacle_length_jitter_speed_slider = jitter_spd_slider
        self.tentacle_length_jitter_speed_spin = jitter_spd_box
        g.addWidget(jitter_spd_slider, r, 1, 1, 2); g.addWidget(jitter_spd_box, r, 3); r += 1

        jitter_spd_bind, jitter_spd_base_lbl, jitter_spd_rows, jitter_spd_weight_spins = self._build_kp_binding_container(
            cfg_key='tentacle_length_jitter_speed', supports=('k', 'p'),
            wmin_default=0.0, wmax_default=0.0,
            soft_min=-1.5, soft_max=1.5, hard_min=-20.0, hard_max=20.0,
            decimals=3,
        )
        g.addWidget(jitter_spd_bind, r, 0, 1, 4); r += 1
        self._register_kp_binding_ui(
            cfg_key='tentacle_length_jitter_speed', label=jitter_spd_label,
            container=jitter_spd_bind, base_label=jitter_spd_base_lbl,
            rows=jitter_spd_rows, supports=('k', 'p'), weight_spins=jitter_spd_weight_spins,
        )

        self.tentacle_length_jitter_random_check = QCheckBox("启用随机扰动")
        self.tentacle_length_jitter_random_check.setChecked(self.config.get('tentacle_length_jitter_random', False))
        self.tentacle_length_jitter_random_check.toggled.connect(lambda v: self._update_cfg('tentacle_length_jitter_random', bool(v)))
        g.addWidget(self.tentacle_length_jitter_random_check, r, 0, 1, 4); r += 1

        cp_min_label = self._attach_kp_bindable_label(QLabel("控制点最小:"), 'tentacle_control_points_min', supports=('k', 'p'))
        g.addWidget(cp_min_label, r, 0)
        cp_min_box = self._new_int_box(
            default_value=3, soft_min=3, soft_max=9,
            hard_min=2, hard_max=24, step=1, cfg_key='tentacle_control_points_min'
        )
        self.tentacle_cp_min_spin = cp_min_box
        g.addWidget(cp_min_box, r, 3); r += 1
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
        g.addWidget(cp_max_label, r, 0)
        cp_max_box = self._new_int_box(
            default_value=5, soft_min=3, soft_max=9,
            hard_min=2, hard_max=24, step=1, cfg_key='tentacle_control_points_max'
        )
        self.tentacle_cp_max_spin = cp_max_box
        g.addWidget(cp_max_box, r, 3); r += 1
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

        tip_bias_label = self._attach_kp_bindable_label(QLabel("末端权重:"), 'tentacle_tip_bias', supports=('k', 'p'))
        g.addWidget(tip_bias_label, r, 0)
        tip_slider, tip_box = self._new_bound_float_slider(
            cfg_key='tentacle_tip_bias', default_value=1.85,
            soft_min=0.5, soft_max=3.0, hard_min=0.1, hard_max=20.0,
            slider_scale=100, step=0.01, decimals=2, width=72
        )
        self.tentacle_tip_bias_slider = tip_slider
        self.tentacle_tip_bias_spin = tip_box
        g.addWidget(tip_slider, r, 1, 1, 2); g.addWidget(tip_box, r, 3); r += 1
        tip_bias_bind, tip_bias_base_lbl, tip_bias_rows, tip_bias_weight_spins = self._build_kp_binding_container(
            cfg_key='tentacle_tip_bias', supports=('k', 'p'),
            wmin_default=0.0, wmax_default=0.0,
            soft_min=-2.0, soft_max=2.0, hard_min=-20.0, hard_max=20.0,
            decimals=3,
        )
        g.addWidget(tip_bias_bind, r, 0, 1, 4); r += 1
        self._register_kp_binding_ui(
            cfg_key='tentacle_tip_bias', label=tip_bias_label,
            container=tip_bias_bind, base_label=tip_bias_base_lbl,
            rows=tip_bias_rows, supports=('k', 'p'), weight_spins=tip_bias_weight_spins,
        )

        tip_thickness_label = self._attach_kp_bindable_label(QLabel("末端粗细:"), 'tentacle_tip_thickness', supports=('k', 'p'))
        g.addWidget(tip_thickness_label, r, 0)
        tip_thickness_slider, tip_thickness_box = self._new_bound_float_slider(
            cfg_key='tentacle_tip_thickness', default_value=0.15,
            soft_min=0.0, soft_max=1.0, hard_min=0.0, hard_max=1.0,
            slider_scale=100, step=0.01, decimals=2, width=72
        )
        self.tentacle_tip_thickness_slider = tip_thickness_slider
        self.tentacle_tip_thickness_spin = tip_thickness_box
        g.addWidget(tip_thickness_slider, r, 1, 1, 2); g.addWidget(tip_thickness_box, r, 3); r += 1
        tip_thickness_bind, tip_thickness_base_lbl, tip_thickness_rows, tip_thickness_weight_spins = self._build_kp_binding_container(
            cfg_key='tentacle_tip_thickness', supports=('k', 'p'),
            wmin_default=0.0, wmax_default=0.0,
            soft_min=-0.5, soft_max=0.5, hard_min=-5.0, hard_max=5.0,
            decimals=3,
        )
        g.addWidget(tip_thickness_bind, r, 0, 1, 4); r += 1
        self._register_kp_binding_ui(
            cfg_key='tentacle_tip_thickness', label=tip_thickness_label,
            container=tip_thickness_bind, base_label=tip_thickness_base_lbl,
            rows=tip_thickness_rows, supports=('k', 'p'), weight_spins=tip_thickness_weight_spins,
        )

        soft_hdr = QLabel("── 柔体 / 水阻尼 ──")
        soft_hdr.setStyleSheet("color:#888; font-size:8pt; padding:3px 0 1px 0;")
        g.addWidget(soft_hdr, r, 0, 1, 4); r += 1

        turb_label = self._attach_kp_bindable_label(QLabel("紊流强度:"), 'tentacle_turbulence', supports=('k', 'p'))
        g.addWidget(turb_label, r, 0)
        turb_slider, turb_box = self._new_bound_float_slider(
            cfg_key='tentacle_turbulence', default_value=46.0,
            soft_min=0.0, soft_max=160.0, hard_min=0.0, hard_max=2000.0,
            slider_scale=10, step=0.1, decimals=1, width=72
        )
        self.tentacle_turbulence_slider = turb_slider
        self.tentacle_turbulence_spin = turb_box
        g.addWidget(turb_slider, r, 1, 1, 2); g.addWidget(turb_box, r, 3); r += 1

        turb_bind, turb_base_lbl, turb_rows, turb_weight_spins = self._build_kp_binding_container(
            cfg_key='tentacle_turbulence', supports=('k', 'p'),
            defaults_by_sig={'k': (0.22, 0.683), 'p': (0.0, 0.0)},
            soft_min=-2.0, soft_max=2.0, hard_min=-10.0, hard_max=10.0,
            decimals=3,
        )
        self.kp_tentacle_turbulence_k_wmin_spin, self.kp_tentacle_turbulence_k_wmax_spin = turb_weight_spins['k']
        self.kp_tentacle_turbulence_p_wmin_spin, self.kp_tentacle_turbulence_p_wmax_spin = turb_weight_spins['p']
        g.addWidget(turb_bind, r, 0, 1, 4); r += 1
        self._register_kp_binding_ui(
            cfg_key='tentacle_turbulence',
            label=turb_label,
            container=turb_bind,
            base_label=turb_base_lbl,
            rows=turb_rows,
            supports=('k', 'p'),
            weight_spins=turb_weight_spins,
        )

        sway_label = self._attach_kp_bindable_label(QLabel("漂浮速度:"), 'tentacle_sway_speed', supports=('k', 'p'))
        g.addWidget(sway_label, r, 0)
        sway_slider, sway_box = self._new_bound_float_slider(
            cfg_key='tentacle_sway_speed', default_value=1.1,
            soft_min=0.0, soft_max=4.0, hard_min=0.0, hard_max=20.0,
            slider_scale=100, step=0.01, decimals=2, width=72
        )
        self.tentacle_sway_speed_slider = sway_slider
        self.tentacle_sway_speed_spin = sway_box
        g.addWidget(sway_slider, r, 1, 1, 2); g.addWidget(sway_box, r, 3); r += 1
        sway_bind, sway_base_lbl, sway_rows, sway_weight_spins = self._build_kp_binding_container(
            cfg_key='tentacle_sway_speed', supports=('k', 'p'),
            wmin_default=0.0, wmax_default=0.0,
            soft_min=-2.0, soft_max=2.0, hard_min=-20.0, hard_max=20.0,
            decimals=3,
        )
        g.addWidget(sway_bind, r, 0, 1, 4); r += 1
        self._register_kp_binding_ui(
            cfg_key='tentacle_sway_speed', label=sway_label,
            container=sway_bind, base_label=sway_base_lbl,
            rows=sway_rows, supports=('k', 'p'), weight_spins=sway_weight_spins,
        )

        density_label = self._attach_kp_bindable_label(QLabel("流场密度:"), 'tentacle_sway_density', supports=('k', 'p'))
        g.addWidget(density_label, r, 0)
        density_slider, density_box = self._new_bound_float_slider(
            cfg_key='tentacle_sway_density', default_value=2.4,
            soft_min=0.2, soft_max=6.0, hard_min=0.0, hard_max=20.0,
            slider_scale=100, step=0.01, decimals=2, width=72
        )
        self.tentacle_sway_density_slider = density_slider
        self.tentacle_sway_density_spin = density_box
        g.addWidget(density_slider, r, 1, 1, 2); g.addWidget(density_box, r, 3); r += 1
        density_bind, density_base_lbl, density_rows, density_weight_spins = self._build_kp_binding_container(
            cfg_key='tentacle_sway_density', supports=('k', 'p'),
            wmin_default=0.0, wmax_default=0.0,
            soft_min=-3.0, soft_max=3.0, hard_min=-50.0, hard_max=50.0,
            decimals=3,
        )
        g.addWidget(density_bind, r, 0, 1, 4); r += 1
        self._register_kp_binding_ui(
            cfg_key='tentacle_sway_density', label=density_label,
            container=density_bind, base_label=density_base_lbl,
            rows=density_rows, supports=('k', 'p'), weight_spins=density_weight_spins,
        )

        water_label = self._attach_kp_bindable_label(QLabel("水阻尼:"), 'tentacle_water_damping', supports=('k', 'p'))
        g.addWidget(water_label, r, 0)
        water_slider, water_box = self._new_bound_float_slider(
            cfg_key='tentacle_water_damping', default_value=0.84,
            soft_min=0.0, soft_max=0.99, hard_min=0.0, hard_max=0.999,
            slider_scale=1000, step=0.001, decimals=3, width=72
        )
        self.tentacle_water_damping_slider = water_slider
        self.tentacle_water_damping_spin = water_box
        g.addWidget(water_slider, r, 1, 1, 2); g.addWidget(water_box, r, 3); r += 1
        water_bind, water_base_lbl, water_rows, water_weight_spins = self._build_kp_binding_container(
            cfg_key='tentacle_water_damping', supports=('k', 'p'),
            wmin_default=0.0, wmax_default=0.0,
            soft_min=-0.3, soft_max=0.3, hard_min=-1.0, hard_max=1.0,
            decimals=4,
        )
        g.addWidget(water_bind, r, 0, 1, 4); r += 1
        self._register_kp_binding_ui(
            cfg_key='tentacle_water_damping', label=water_label,
            container=water_bind, base_label=water_base_lbl,
            rows=water_rows, supports=('k', 'p'), weight_spins=water_weight_spins,
        )

        angle_label = self._attach_kp_bindable_label(QLabel("弯曲力:"), 'tentacle_angle_stiffness', supports=('k', 'p'))
        g.addWidget(angle_label, r, 0)
        angle_slider, angle_box = self._new_bound_float_slider(
            cfg_key='tentacle_angle_stiffness', default_value=0.18,
            soft_min=0.0, soft_max=1.0, hard_min=0.0, hard_max=5.0,
            slider_scale=100, step=0.01, decimals=2, width=72
        )
        self.tentacle_angle_stiffness_slider = angle_slider
        self.tentacle_angle_stiffness_spin = angle_box
        g.addWidget(angle_slider, r, 1, 1, 2); g.addWidget(angle_box, r, 3); r += 1
        angle_bind, angle_base_lbl, angle_rows, angle_weight_spins = self._build_kp_binding_container(
            cfg_key='tentacle_angle_stiffness', supports=('k', 'p'),
            wmin_default=0.0, wmax_default=0.0,
            soft_min=-0.5, soft_max=0.5, hard_min=-5.0, hard_max=5.0,
            decimals=3,
        )
        g.addWidget(angle_bind, r, 0, 1, 4); r += 1
        self._register_kp_binding_ui(
            cfg_key='tentacle_angle_stiffness', label=angle_label,
            container=angle_bind, base_label=angle_base_lbl,
            rows=angle_rows, supports=('k', 'p'), weight_spins=angle_weight_spins,
        )

        length_hold_label = self._attach_kp_bindable_label(QLabel("拉伸力:"), 'tentacle_length_stiffness', supports=('k', 'p'))
        g.addWidget(length_hold_label, r, 0)
        length_hold_slider, length_hold_box = self._new_bound_float_slider(
            cfg_key='tentacle_length_stiffness', default_value=0.24,
            soft_min=0.0, soft_max=1.0, hard_min=0.0, hard_max=5.0,
            slider_scale=100, step=0.01, decimals=2, width=72
        )
        self.tentacle_length_stiffness_slider = length_hold_slider
        self.tentacle_length_stiffness_spin = length_hold_box
        g.addWidget(length_hold_slider, r, 1, 1, 2); g.addWidget(length_hold_box, r, 3); r += 1
        length_hold_bind, length_hold_base_lbl, length_hold_rows, length_hold_weight_spins = self._build_kp_binding_container(
            cfg_key='tentacle_length_stiffness', supports=('k', 'p'),
            wmin_default=0.0, wmax_default=0.0,
            soft_min=-0.5, soft_max=0.5, hard_min=-5.0, hard_max=5.0,
            decimals=3,
        )
        g.addWidget(length_hold_bind, r, 0, 1, 4); r += 1
        self._register_kp_binding_ui(
            cfg_key='tentacle_length_stiffness', label=length_hold_label,
            container=length_hold_bind, base_label=length_hold_base_lbl,
            rows=length_hold_rows, supports=('k', 'p'), weight_spins=length_hold_weight_spins,
        )

        stretch_limit_label = self._attach_kp_bindable_label(QLabel("拉伸限制:"), 'tentacle_stretch_limit', supports=('k', 'p'))
        g.addWidget(stretch_limit_label, r, 0)
        stretch_limit_slider, stretch_limit_box = self._new_bound_float_slider(
            cfg_key='tentacle_stretch_limit', default_value=1.12,
            soft_min=1.0, soft_max=2.0, hard_min=1.0, hard_max=10.0,
            slider_scale=100, step=0.01, decimals=2, width=72
        )
        self.tentacle_stretch_limit_slider = stretch_limit_slider
        self.tentacle_stretch_limit_spin = stretch_limit_box
        g.addWidget(stretch_limit_slider, r, 1, 1, 2); g.addWidget(stretch_limit_box, r, 3); r += 1
        stretch_bind, stretch_base_lbl, stretch_rows, stretch_weight_spins = self._build_kp_binding_container(
            cfg_key='tentacle_stretch_limit', supports=('k', 'p'),
            wmin_default=0.0, wmax_default=0.0,
            soft_min=-0.5, soft_max=0.5, hard_min=-10.0, hard_max=10.0,
            decimals=3,
        )
        g.addWidget(stretch_bind, r, 0, 1, 4); r += 1
        self._register_kp_binding_ui(
            cfg_key='tentacle_stretch_limit', label=stretch_limit_label,
            container=stretch_bind, base_label=stretch_base_lbl,
            rows=stretch_rows, supports=('k', 'p'), weight_spins=stretch_weight_spins,
        )

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
        shader_tip_btn.setStyleSheet(f"background:rgb({sc[0]},{sc[1]},{sc[2]}); border:1px solid #aaa; border-radius:2px;")
        shader_tip_btn.clicked.connect(lambda: self._pick_special_color('tentacle_shader_tip_color', self.tentacle_shader_tip_color_btn))
        self.tentacle_shader_tip_color_btn = shader_tip_btn
        g.addWidget(shader_tip_btn, r, 1)
        g.addWidget(QLabel("尾色"), r, 2)
        r += 1

        alpha_start_label = self._attach_kp_bindable_label(QLabel("起始透明:"), 'tentacle_shader_alpha_start', supports=('k', 'p'))
        g.addWidget(alpha_start_label, r, 0)
        alpha_start_slider, alpha_start_box = self._new_bound_float_slider(
            cfg_key='tentacle_shader_alpha_start', default_value=1.0,
            soft_min=0.0, soft_max=1.0, hard_min=0.0, hard_max=1.0,
            slider_scale=100, step=0.01, decimals=2, width=72
        )
        self.tentacle_shader_alpha_start_slider = alpha_start_slider
        self.tentacle_shader_alpha_start_spin = alpha_start_box
        g.addWidget(alpha_start_slider, r, 1, 1, 2); g.addWidget(alpha_start_box, r, 3); r += 1
        alpha_start_bind, alpha_start_base_lbl, alpha_start_rows, alpha_start_weight_spins = self._build_kp_binding_container(
            cfg_key='tentacle_shader_alpha_start', supports=('k', 'p'),
            wmin_default=0.0, wmax_default=0.0,
            soft_min=-0.5, soft_max=0.5, hard_min=-1.0, hard_max=1.0,
            decimals=4,
        )
        g.addWidget(alpha_start_bind, r, 0, 1, 4); r += 1
        self._register_kp_binding_ui(
            cfg_key='tentacle_shader_alpha_start', label=alpha_start_label,
            container=alpha_start_bind, base_label=alpha_start_base_lbl,
            rows=alpha_start_rows, supports=('k', 'p'), weight_spins=alpha_start_weight_spins,
        )

        alpha_end_label = self._attach_kp_bindable_label(QLabel("末端透明:"), 'tentacle_shader_alpha_end', supports=('k', 'p'))
        g.addWidget(alpha_end_label, r, 0)
        alpha_end_slider, alpha_end_box = self._new_bound_float_slider(
            cfg_key='tentacle_shader_alpha_end', default_value=0.18,
            soft_min=0.0, soft_max=1.0, hard_min=0.0, hard_max=1.0,
            slider_scale=100, step=0.01, decimals=2, width=72
        )
        self.tentacle_shader_alpha_end_slider = alpha_end_slider
        self.tentacle_shader_alpha_end_spin = alpha_end_box
        g.addWidget(alpha_end_slider, r, 1, 1, 2); g.addWidget(alpha_end_box, r, 3); r += 1
        alpha_end_bind, alpha_end_base_lbl, alpha_end_rows, alpha_end_weight_spins = self._build_kp_binding_container(
            cfg_key='tentacle_shader_alpha_end', supports=('k', 'p'),
            wmin_default=0.0, wmax_default=0.0,
            soft_min=-0.5, soft_max=0.5, hard_min=-1.0, hard_max=1.0,
            decimals=4,
        )
        g.addWidget(alpha_end_bind, r, 0, 1, 4); r += 1
        self._register_kp_binding_ui(
            cfg_key='tentacle_shader_alpha_end', label=alpha_end_label,
            container=alpha_end_bind, base_label=alpha_end_base_lbl,
            rows=alpha_end_rows, supports=('k', 'p'), weight_spins=alpha_end_weight_spins,
        )

        shader_bias_label = self._attach_kp_bindable_label(QLabel("渐变偏置:"), 'tentacle_shader_bias', supports=('k', 'p'))
        g.addWidget(shader_bias_label, r, 0)
        shader_bias_slider, shader_bias_box = self._new_bound_float_slider(
            cfg_key='tentacle_shader_bias', default_value=1.15,
            soft_min=0.1, soft_max=3.0, hard_min=0.1, hard_max=10.0,
            slider_scale=100, step=0.01, decimals=2, width=72
        )
        self.tentacle_shader_bias_slider = shader_bias_slider
        self.tentacle_shader_bias_spin = shader_bias_box
        g.addWidget(shader_bias_slider, r, 1, 1, 2); g.addWidget(shader_bias_box, r, 3); r += 1
        shader_bias_bind, shader_bias_base_lbl, shader_bias_rows, shader_bias_weight_spins = self._build_kp_binding_container(
            cfg_key='tentacle_shader_bias', supports=('k', 'p'),
            wmin_default=0.0, wmax_default=0.0,
            soft_min=-1.0, soft_max=1.0, hard_min=-10.0, hard_max=10.0,
            decimals=3,
        )
        g.addWidget(shader_bias_bind, r, 0, 1, 4); r += 1
        self._register_kp_binding_ui(
            cfg_key='tentacle_shader_bias', label=shader_bias_label,
            container=shader_bias_bind, base_label=shader_bias_base_lbl,
            rows=shader_bias_rows, supports=('k', 'p'), weight_spins=shader_bias_weight_spins,
        )

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

        core_base_label = self._attach_kp_bindable_label(QLabel("基础角加速度:"), 'tentacle_core_base_speed', supports=('k', 'p'))
        g.addWidget(core_base_label, r, 0)
        core_base_slider, core_base_box = self._new_bound_float_slider(
            cfg_key='tentacle_core_base_speed', default_value=0.75,
            soft_min=-5.0, soft_max=5.0, hard_min=-100.0, hard_max=100.0,
            slider_scale=100, step=0.01, decimals=2, width=72
        )
        self.tentacle_core_base_speed_slider = core_base_slider
        self.tentacle_core_base_speed_spin = core_base_box
        g.addWidget(core_base_slider, r, 1, 1, 2); g.addWidget(core_base_box, r, 3); r += 1

        core_bind, core_base_lbl, core_rows, core_weight_spins = self._build_kp_binding_container(
            cfg_key='tentacle_core_base_speed', supports=('k', 'p'),
            defaults_by_sig={'k': (0.0, 1.2), 'p': (0.0, 1.35)},
            soft_min=-5.0, soft_max=5.0, hard_min=-100.0, hard_max=100.0,
            decimals=3,
        )
        self.kp_tentacle_core_base_speed_k_wmin_spin, self.kp_tentacle_core_base_speed_k_wmax_spin = core_weight_spins['k']
        self.kp_tentacle_core_base_speed_p_wmin_spin, self.kp_tentacle_core_base_speed_p_wmax_spin = core_weight_spins['p']
        g.addWidget(core_bind, r, 0, 1, 4); r += 1
        self._register_kp_binding_ui(
            cfg_key='tentacle_core_base_speed',
            label=core_base_label,
            container=core_bind,
            base_label=core_base_lbl,
            rows=core_rows,
            supports=('k', 'p'),
            weight_spins=core_weight_spins,
        )

        s.add_layout(g)
        return s

    # ── 四层条形 ──────────────────────────────────────────

    def _build_bars_section(self):
        s = _Collapsible("四层条形 (B12~B45)", expanded=False)
        g = QGridLayout(); g.setSpacing(3); g.setContentsMargins(0,0,0,0); r = 0
        for key, bname in [('b12', 'L1-L2 间'), ('b23', 'L2-L3 间'),
                           ('b34', 'L3-L4 间'), ('b45', 'L4-L5 间')]:
            hdr = QLabel(f"── {bname} ──")
            hdr.setStyleSheet("color:#888; font-size:8pt; padding:3px 0 1px 0;")
            g.addWidget(hdr, r, 0, 1, 3); r += 1

            chk = QCheckBox("显示")
            chk.setChecked(self.config.get(f'{key}_on', False))
            chk.toggled.connect(lambda v, k=f'{key}_on': self._update_cfg(k, v))
            setattr(self, f'{key}_on_check', chk)
            g.addWidget(chk, r, 0)
            sp = self._new_int_box(
                default_value=3, soft_min=1, soft_max=20,
                hard_min=1, hard_max=1000, step=1, cfg_key=f'{key}_thick'
            )
            setattr(self, f'{key}_thick_spin', sp)
            ht = QHBoxLayout()
            thick_label = self._attach_kp_bindable_label(QLabel("粗:"), f'{key}_thick', supports=('k', 'p'))
            ht.addWidget(thick_label); ht.addWidget(sp)
            g.addLayout(ht, r, 1, 1, 2); r += 1
            thick_bind, thick_base_lbl, thick_rows, thick_weight_spins = self._build_kp_binding_container(
                cfg_key=f'{key}_thick', supports=('k', 'p'),
                wmin_default=0.0, wmax_default=0.0,
                soft_min=-6.0, soft_max=6.0, hard_min=-100.0, hard_max=100.0,
                decimals=2,
            )
            g.addWidget(thick_bind, r, 0, 1, 3); r += 1
            self._register_kp_binding_ui(
                cfg_key=f'{key}_thick', label=thick_label,
                container=thick_bind, base_label=thick_base_lbl,
                rows=thick_rows, supports=('k', 'p'), weight_spins=thick_weight_spins,
            )

            fchk = QCheckBox("固定长度")
            fchk.setChecked(self.config.get(f'{key}_fixed', False))
            setattr(self, f'{key}_fixed_check', fchk)
            g.addWidget(fchk, r, 0)
            r += 1
            r, _fixed_len_label, fsp = self._add_kp_spin_row(
                g, r,
                label_text='固定长度:', cfg_key=f'{key}_fixed_len',
                default_value=30,
                soft_min=1, soft_max=500, hard_min=1, hard_max=10000,
                integer=True, step=1, suffix=' px',
                kp_soft_min=-120.0, kp_soft_max=120.0, kp_hard_min=-10000.0, kp_hard_max=10000.0, kp_decimals=2,
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
            g.addWidget(mode_w, r, 0, 1, 3); r += 1

            fchk.toggled.connect(lambda v, k=key, w=mode_w: (self._update_cfg(f'{k}_fixed', v), w.setVisible(v)))

            damp_check, damp_widget, rise_box, fall_box = self._build_independent_damping_controls(key)
            setattr(self, f'{key}_independent_damping_check', damp_check)
            setattr(self, f'{key}_independent_damping_widget', damp_widget)
            setattr(self, f'{key}_independent_rise_damping_spin', rise_box)
            setattr(self, f'{key}_independent_fall_damping_spin', fall_box)
            g.addWidget(damp_check, r, 0, 1, 3); r += 1
            g.addWidget(damp_widget, r, 0, 1, 3); r += 1

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

        props.append(("水母", [
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

    def _enforce_random_object_count(self):
        object_keys = ['c1_on', 'c2_on', 'c3_on', 'c4_on', 'c5_on', 'b12_on', 'b23_on', 'b34_on', 'b45_on', 'tentacle_on']
        total = len(object_keys)
        min_v = int(self.config.get('random_object_count_min', 1))
        max_v = int(self.config.get('random_object_count_max', total))
        low = max(1, min(total, min(min_v, max_v)))
        high = max(1, min(total, max(min_v, max_v)))
        target = random.randint(low, high)

        chosen = set(random.sample(object_keys, k=target))
        for key in object_keys:
            self.config[key] = key in chosen

    def _randomize_selected(self):
        """随机化所有被选中的属性"""
        now = time.time()

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
                    self.config[cfg_key] = random.choice([True, False])
                elif ptype == "int":
                    self.config[cfg_key] = random.randint(prop_def[3], prop_def[4])
                elif ptype == "float":
                    self.config[cfg_key] = round(random.uniform(prop_def[3], prop_def[4]), 3)
                elif ptype == "color":
                    if color_pool:
                        self.config[cfg_key] = color_pool.pop(0)
                    else:
                        self.config[cfg_key] = tuple(self._generate_harmony_palette(1)[0])
                elif ptype == "choice":
                    self.config[cfg_key] = random.choice(prop_def[3])
                changed = True
        if changed:
            self.config['color_scheme'] = 'custom'
            self._enforce_random_object_count()
            self._apply_config_to_ui(self.config)
            self._last_random_apply_ts = now

    def _update_color_preview_strip(self):
        if not hasattr(self, 'palette_preview_cells'):
            return
        previews = []
        if self.config.get('color_scheme', 'rainbow') == 'custom':
            if self.config.get('gradient_enabled', True):
                pts = self.config.get('gradient_points', []) or []
                for p in pts[:8]:
                    c = p[1] if isinstance(p, (list, tuple)) and len(p) >= 2 else None
                    if isinstance(c, (list, tuple)) and len(c) >= 3:
                        previews.append((int(c[0]), int(c[1]), int(c[2])))
            if len(previews) < 8:
                for i in range(1, 6):
                    c = self.config.get(f'c{i}_color', (255, 255, 255))
                    previews.append((int(c[0]), int(c[1]), int(c[2])))
                    if len(previews) >= 8:
                        break
        else:
            previews = self._generate_harmony_palette(8)

        while len(previews) < 8:
            previews.append((60, 60, 60))
        self._set_palette_preview_colors(previews[:8])

    def _on_palette_cell_clicked(self, idx: int):
        # 点击主色带上的小色块以快速编辑颜色
        if idx < 0 or idx >= len(self.palette_preview_cells):
            return
        # 读取当前 displayed color
        style = self.palette_preview_cells[idx].styleSheet()
        m = re.search(r'rgb\((\d+),(\d+),(\d+)\)', style)
        if m:
            cur = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        else:
            cur = (255, 255, 255)

        cfg_prefix = f"palette_cell_{idx}"
        if self.config.get('color_scheme', 'rainbow') == 'custom' and self.config.get('gradient_enabled', True):
            pts = list(self.config.get('gradient_points', []))
            if idx < len(pts):
                cfg_prefix = f"gradient_points_{idx}_color"
        else:
            li = (idx % 5) + 1
            cfg_prefix = f"c{li}_color"

        picker = QuickColorPicker(self, initial=cur, presets=self._get_designer_palette(12), cfg_key_prefix=cfg_prefix)

        def _apply(new_col):
            # 如果当前为自定义渐变并且存在对应控制点，则更新控制点
            if self.config.get('color_scheme', 'rainbow') == 'custom' and self.config.get('gradient_enabled', True):
                pts = list(self.config.get('gradient_points', []))
                if idx < len(pts):
                    pts[idx] = (pts[idx][0], new_col)
                else:
                    pos = min(1.0, max(0.0, idx / max(1, len(self.palette_preview_cells) - 1)))
                    pts.append((pos, new_col))
                self._update_cfg('gradient_points', pts)
            else:
                li = (idx % 5) + 1
                key = f'c{li}_color'
                self._update_cfg(key, new_col)
                if hasattr(self, f'c{li}_color_btn'):
                    getattr(self, f'c{li}_color_btn').setStyleSheet(
                        f"background:rgb({new_col[0]},{new_col[1]},{new_col[2]}); border:1px solid #aaa; border-radius:2px;"
                    )
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
            btn = getattr(self, f'c{layer_idx}_color_btn')
            btn.setStyleSheet(f"background:rgb({rgb[0]},{rgb[1]},{rgb[2]}); border:1px solid #aaa; border-radius:2px;")
            self._update_cfg(key, rgb)
            self._update_color_preview_strip()

        picker.colorSelected.connect(_apply)
        picker.exec()

    def _pick_special_color(self, cfg_key: str, btn: QPushButton | None = None):
        cur = self.config.get(cfg_key, (255, 255, 255))
        picker = QuickColorPicker(self, initial=cur, presets=self._get_designer_palette(12), cfg_key_prefix=cfg_key)

        def _apply(rgb):
            if btn is not None:
                btn.setStyleSheet(f"background:rgb({rgb[0]},{rgb[1]},{rgb[2]}); border:1px solid #aaa; border-radius:2px;")
            self._update_cfg(cfg_key, rgb)

        picker.colorSelected.connect(_apply)
        picker.exec()

    def _on_dynamic_toggled(self, v):
        self._update_cfg('color_dynamic', v)

    def _rebuild_gradient_ui(self):
        for w in self.gp_widgets:
            w.setParent(None); w.deleteLater()
        self.gp_widgets.clear()

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
            btn.setStyleSheet(f"background:rgb({color[0]},{color[1]},{color[2]}); border:1px solid #aaa; border-radius:2px;")
            btn.clicked.connect(lambda _, idx=i, b=btn: self._gp_color_pick(idx, b))
            rl.addWidget(btn)

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
            btn.setStyleSheet(f"background:rgb({rgb[0]},{rgb[1]},{rgb[2]}); border:1px solid #aaa; border-radius:2px;")
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

    def _sync_window_layer_controls(self, mode=None):
        mode = str(mode or self.config.get('window_layer', 'normal')).lower()
        if mode not in {'top', 'normal', 'bottom'}:
            mode = 'normal'
        if hasattr(self, 'top_check'):
            self._set_checkbox_silent(self.top_check, mode == 'top')
        if hasattr(self, 'pin_top_btn'):
            self.pin_top_btn.setEnabled(mode != 'top')
        if hasattr(self, 'pin_bottom_btn'):
            self.pin_bottom_btn.setEnabled(mode != 'bottom')

    def _restart_visualizer_process(self):
        self._flush_pending_config()
        self._stop_visualizer()
        try:
            target = Path(__file__).resolve()
            subprocess.Popen([sys.executable, str(target)], cwd=str(target.parent))
        except Exception as e:
            QMessageBox.critical(self, '错误', f'重启程序失败: {e}')
            self._start_visualizer()
            return
        self.close()

    def _set_palette_preview_colors(self, colors):
        if not hasattr(self, 'palette_preview_cells'):
            return
        preview_colors = [tuple(int(channel) for channel in color[:3]) for color in (colors or []) if len(color) >= 3]
        while len(preview_colors) < len(self.palette_preview_cells):
            preview_colors.append((60, 60, 60))
        for idx, cell in enumerate(self.palette_preview_cells):
            color = preview_colors[idx]
            cell.setStyleSheet(
                f"background:rgb({color[0]},{color[1]},{color[2]}); border:1px solid #666; border-radius:2px;"
            )

    def _apply_runtime_color_snapshot(self, snapshot):
        if not isinstance(snapshot, dict):
            return
        palette_preview = snapshot.get('palette_preview')
        if isinstance(palette_preview, list):
            self._set_palette_preview_colors(palette_preview)
        for layer_index in range(1, 6):
            color = snapshot.get(f'c{layer_index}_color')
            btn = getattr(self, f'c{layer_index}_color_btn', None)
            if btn is not None and isinstance(color, (list, tuple)) and len(color) >= 3:
                btn.setStyleSheet(
                    f"background:rgb({int(color[0])},{int(color[1])},{int(color[2])}); border:1px solid #aaa; border-radius:2px;"
                )
        tentacle_color = snapshot.get('tentacle_color')
        if hasattr(self, 'tentacle_color_btn') and isinstance(tentacle_color, (list, tuple)) and len(tentacle_color) >= 3:
            self.tentacle_color_btn.setStyleSheet(
                f"background:rgb({int(tentacle_color[0])},{int(tentacle_color[1])},{int(tentacle_color[2])}); border:1px solid #aaa; border-radius:2px;"
            )
        shader_tip_color = snapshot.get('tentacle_shader_tip_color')
        if hasattr(self, 'tentacle_shader_tip_color_btn') and isinstance(shader_tip_color, (list, tuple)) and len(shader_tip_color) >= 3:
            self.tentacle_shader_tip_color_btn.setStyleSheet(
                f"background:rgb({int(shader_tip_color[0])},{int(shader_tip_color[1])},{int(shader_tip_color[2])}); border:1px solid #aaa; border-radius:2px;"
            )
        runtime_points = snapshot.get('gradient_points')
        if isinstance(runtime_points, list):
            for idx, row in enumerate(getattr(self, 'gp_widgets', [])):
                if idx >= len(runtime_points):
                    break
                point = runtime_points[idx]
                if not (isinstance(point, (list, tuple)) and len(point) >= 2):
                    continue
                color = point[1]
                if not (isinstance(color, (list, tuple)) and len(color) >= 3):
                    continue
                buttons = row.findChildren(QPushButton)
                if buttons:
                    buttons[0].setStyleSheet(
                        f"background:rgb({int(color[0])},{int(color[1])},{int(color[2])}); border:1px solid #aaa; border-radius:2px;"
                    )

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

            self.tentacle_on_check.setChecked(d.get('tentacle_on', True))
            tc = d.get('tentacle_color', (130, 240, 220))
            self.tentacle_color_btn.setStyleSheet(
                f"background:rgb({tc[0]},{tc[1]},{tc[2]}); border:1px solid #aaa; border-radius:2px;")
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
            self.tentacle_shader_tip_color_btn.setStyleSheet(
                f"background:rgb({tsc[0]},{tsc[1]},{tsc[2]}); border:1px solid #aaa; border-radius:2px;")
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


if __name__ == "__main__":
    main()
