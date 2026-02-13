"""
音频可视化控制台 - 主框架
支持选择不同可视化模式（当前仅圆形频谱）
通过 multiprocessing 启动子程序并实时传递配置
"""

import sys
import os
import json
import time
import random
import multiprocessing as mp
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QSlider,
    QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox,
    QInputDialog,
    QFrame, QMessageBox, QColorDialog, QScrollArea,
    QTreeWidget, QTreeWidgetItem,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor, QPalette

CONFIG_FILE = Path(__file__).parent / 'visualizer_config.json'
PRESETS_DIR = Path(__file__).parent / 'presets'

_DEFAULT_CONFIG = {
    'width': 0, 'height': 0, 'alpha': 255, 'ui_alpha': 180,
    'global_scale': 1.0, 'pos_x': -1, 'pos_y': -1,
    'drag_adjust_mode': False,
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
    # 四层条形  b12(L1-L2) b23(L2-L3) b34(L3-L4) b45(L4-L5)
    'b12_on': False, 'b12_thick': 2,
    'b12_fixed': False, 'b12_fixed_len': 30, 'b12_from_start': True, 'b12_from_end': False, 'b12_from_center': False,
    'b23_on': False, 'b23_thick': 3,
    'b23_fixed': False, 'b23_fixed_len': 30, 'b23_from_start': True, 'b23_from_end': False, 'b23_from_center': False,
    'b34_on': True,  'b34_thick': 3,
    'b34_fixed': False, 'b34_fixed_len': 30, 'b34_from_start': True, 'b34_from_end': False, 'b34_from_center': False,
    'b45_on': False, 'b45_thick': 2,
    'b45_fixed': False, 'b45_fixed_len': 30, 'b45_from_start': True, 'b45_from_end': False, 'b45_from_center': False,
    'random_checked': [],
    'preset_auto_switch': False,
    'preset_switch_interval': 10,
}


def _get_defaults():
    import copy
    return copy.deepcopy(_DEFAULT_CONFIG)


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

    def _flip(self, on):
        self._body.setVisible(on)
        self._btn.setText(("▾ " if on else "▸ ") + self._title)

    def add_layout(self, layout):
        self._body_lay.addLayout(layout)

    def add_widget(self, widget):
        self._body_lay.addWidget(widget)


class VisualizerControlUI(QWidget):
    """音频可视化主控制台"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("音频可视化控制台")
        self.resize(780, 620)

        self.config = self._load_config()
        self.config_queue = None
        self.status_queue = None
        self.viz_process = None
        self.current_a1 = 0.0
        self._applying_config = False

        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status)

        self.preset_timer = QTimer()
        self.preset_timer.timeout.connect(self._auto_switch_preset)

        self._init_ui()
        self._refresh_preset_list()

        # 自动启动
        QTimer.singleShot(100, self._start_visualizer)

    # ═══════════════════════════════════════════════════════
    #  配置管理
    # ═══════════════════════════════════════════════════════

    def _load_config(self):
        cfg = _get_defaults()
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    cfg.update(json.load(f))
            except Exception as e:
                print(f"警告: 加载配置失败: {e}")
        else:
            # 首次运行，用默认值创建 JSON
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

    def _update_cfg(self, key, value):
        self.config[key] = value
        if self._applying_config:
            return
        self._send_config()
        self._save_config()

    def _send_config(self):
        if not self.config_queue:
            return
        try:
            while not self.config_queue.empty():
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

    # ═══════════════════════════════════════════════════════
    #  UI 构建
    # ═══════════════════════════════════════════════════════

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(5, 5, 5, 5)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        inner.setFont(QFont("微软雅黑", 9))
        vlay = QVBoxLayout(inner)
        vlay.setSpacing(2); vlay.setContentsMargins(4, 4, 4, 4)

        self._build_control_section(vlay)
        self._build_preset_section(vlay)
        self._build_color_section(vlay)
        self._build_physics_section(vlay)
        self._build_window_section(vlay)
        self._build_contour_section(vlay)
        self._build_bars_section(vlay)
        self._build_k1_section(vlay)
        self._build_random_section(vlay)

        vlay.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll)

    # ── 控制（含基础设置） ──────────────────────────────

    def _build_control_section(self, vlay):
        s = _Collapsible("控制")
        g = QGridLayout(); g.setSpacing(3); g.setContentsMargins(0,0,0,0); r = 0

        # ■ 总开关（最顶部）
        self.master_visible_check = QCheckBox("总开关（显示全部）")
        self.master_visible_check.setChecked(self.config.get('master_visible', True))
        self.master_visible_check.toggled.connect(lambda v: self._update_cfg('master_visible', v))
        g.addWidget(self.master_visible_check, r, 0, 1, 3); r += 1

        # 模式
        mrow = QHBoxLayout()
        mrow.addWidget(QLabel("模式:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["圆形频谱"])
        mrow.addWidget(self.mode_combo); mrow.addStretch()
        g.addLayout(mrow, r, 0, 1, 3); r += 1

        # 复位
        rrow = QHBoxLayout()
        b1 = QPushButton("📍 复位位置"); b1.setMinimumHeight(30)
        b1.clicked.connect(self._center_window); rrow.addWidget(b1)
        b2 = QPushButton("🔄 复位参数"); b2.setMinimumHeight(30)
        b2.clicked.connect(self._reset_all); rrow.addWidget(b2)
        g.addLayout(rrow, r, 0, 1, 3); r += 1

        # 整体缩放
        g.addWidget(QLabel("缩放:"), r, 0)
        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.1, 10.0); self.scale_spin.setSingleStep(0.1); self.scale_spin.setDecimals(2)
        self.scale_spin.setValue(self.config.get('global_scale', 1.0))
        self.scale_spin.valueChanged.connect(lambda v: self._update_cfg('global_scale', v))
        g.addWidget(self.scale_spin, r, 1); g.addWidget(QLabel("x"), r, 2); r += 1

        # 位置 XY
        g.addWidget(QLabel("位置:"), r, 0)
        h_pos = QHBoxLayout(); h_pos.setSpacing(4)
        self.pos_x_spin = QSpinBox(); self.pos_x_spin.setRange(-9999, 9999)
        self.pos_x_spin.setValue(self.config.get('pos_x', -1))
        self.pos_x_spin.valueChanged.connect(lambda v: self._update_cfg('pos_x', v))
        self.pos_y_spin = QSpinBox(); self.pos_y_spin.setRange(-9999, 9999)
        self.pos_y_spin.setValue(self.config.get('pos_y', -1))
        self.pos_y_spin.valueChanged.connect(lambda v: self._update_cfg('pos_y', v))
        h_pos.addWidget(QLabel("X")); h_pos.addWidget(self.pos_x_spin)
        h_pos.addWidget(QLabel("Y")); h_pos.addWidget(self.pos_y_spin)
        g.addLayout(h_pos, r, 1, 1, 2); r += 1

        self.drag_adjust_check = QCheckBox("拖动调整位置（开启后可在频谱窗口直接拖动）")
        self.drag_adjust_check.setChecked(self.config.get('drag_adjust_mode', False))
        self.drag_adjust_check.toggled.connect(lambda v: self._update_cfg('drag_adjust_mode', v))
        g.addWidget(self.drag_adjust_check, r, 0, 1, 3); r += 1

        # ── 通用 ──
        _sh0 = QLabel("── 通用 ──")
        _sh0.setStyleSheet("color:#888; font-size:8pt; padding:3px 0 1px 0;")
        g.addWidget(_sh0, r, 0, 1, 3); r += 1

        g.addWidget(QLabel("宽度:"), r, 0)
        self.width_spin = QSpinBox(); self.width_spin.setRange(0, 7680); self.width_spin.setSingleStep(100)
        self.width_spin.setValue(self.config['width'])
        self.width_spin.valueChanged.connect(lambda v: self._update_cfg('width', v))
        g.addWidget(self.width_spin, r, 1); g.addWidget(QLabel("px(0=全屏)"), r, 2); r += 1

        g.addWidget(QLabel("高度:"), r, 0)
        self.height_spin = QSpinBox(); self.height_spin.setRange(0, 4320); self.height_spin.setSingleStep(100)
        self.height_spin.setValue(self.config['height'])
        self.height_spin.valueChanged.connect(lambda v: self._update_cfg('height', v))
        g.addWidget(self.height_spin, r, 1); g.addWidget(QLabel("px"), r, 2); r += 1

        g.addWidget(QLabel("背景透明:"), r, 0)
        self.alpha_slider = QSlider(Qt.Horizontal); self.alpha_slider.setRange(0, 255)
        self.alpha_slider.setValue(self.config['alpha'])
        self.alpha_lbl = QLabel(str(self.config['alpha'])); self.alpha_lbl.setFixedWidth(30)
        self.alpha_slider.valueChanged.connect(lambda v: (self.alpha_lbl.setText(str(v)), self._update_cfg('alpha', v)))
        g.addWidget(self.alpha_slider, r, 1); g.addWidget(self.alpha_lbl, r, 2); r += 1

        g.addWidget(QLabel("UI透明:"), r, 0)
        self.ui_alpha_slider = QSlider(Qt.Horizontal); self.ui_alpha_slider.setRange(0, 255)
        self.ui_alpha_slider.setValue(self.config['ui_alpha'])
        self.ui_alpha_lbl = QLabel(str(self.config['ui_alpha'])); self.ui_alpha_lbl.setFixedWidth(30)
        self.ui_alpha_slider.valueChanged.connect(lambda v: (self.ui_alpha_lbl.setText(str(v)), self._update_cfg('ui_alpha', v)))
        g.addWidget(self.ui_alpha_slider, r, 1); g.addWidget(self.ui_alpha_lbl, r, 2); r += 1

        g.addWidget(QLabel("平滑度:"), r, 0)
        self.smooth_slider = QSlider(Qt.Horizontal); self.smooth_slider.setRange(0, 100)
        self.smooth_slider.setValue(int(self.config['smoothing'] * 100))
        self.smooth_lbl = QLabel(f"{self.config['smoothing']:.2f}"); self.smooth_lbl.setFixedWidth(30)
        self.smooth_slider.valueChanged.connect(lambda v: (self.smooth_lbl.setText(f"{v/100:.2f}"), self._update_cfg('smoothing', v / 100)))
        g.addWidget(self.smooth_slider, r, 1); g.addWidget(self.smooth_lbl, r, 2); r += 1

        g.addWidget(QLabel("频谱条:"), r, 0)
        self.bars_spin = QSpinBox(); self.bars_spin.setRange(4, 1024); self.bars_spin.setSingleStep(8)
        self.bars_spin.setValue(self.config['num_bars'])
        self.bars_spin.valueChanged.connect(lambda v: self._update_cfg('num_bars', v))
        g.addWidget(self.bars_spin, r, 1); r += 1

        # ── 频谱 ──
        _sh = QLabel("── 频谱 ──")
        _sh.setStyleSheet("color:#888; font-size:8pt; padding:3px 0 1px 0;")
        g.addWidget(_sh, r, 0, 1, 3); r += 1

        g.addWidget(QLabel("半径:"), r, 0)
        self.radius_spin = QSpinBox(); self.radius_spin.setRange(10, 2000); self.radius_spin.setSingleStep(10)
        self.radius_spin.setValue(self.config['circle_radius'])
        self.radius_spin.valueChanged.connect(lambda v: self._update_cfg('circle_radius', v))
        g.addWidget(self.radius_spin, r, 1); g.addWidget(QLabel("px"), r, 2); r += 1

        g.addWidget(QLabel("段数:"), r, 0)
        self.seg_spin = QSpinBox(); self.seg_spin.setRange(1, 16)
        self.seg_spin.setValue(self.config['circle_segments'])
        self.seg_spin.valueChanged.connect(lambda v: self._update_cfg('circle_segments', v))
        g.addWidget(self.seg_spin, r, 1); r += 1

        hr = QHBoxLayout(); hr.setSpacing(12)
        self.a1rot_check = QCheckBox("K1 驱动旋转")
        self.a1rot_check.setChecked(self.config['circle_a1_rotation'])
        self.a1rot_check.toggled.connect(lambda v: self._update_cfg('circle_a1_rotation', v))
        self.a1rad_check = QCheckBox("K1 响应半径")
        self.a1rad_check.setChecked(self.config['circle_a1_radius'])
        self.a1rad_check.toggled.connect(lambda v: self._update_cfg('circle_a1_radius', v))
        hr.addWidget(self.a1rot_check); hr.addWidget(self.a1rad_check); hr.addStretch()
        g.addLayout(hr, r, 0, 1, 3); r += 1

        _sh2 = QLabel("── 半径缓动 ──")
        _sh2.setStyleSheet("color:#888; font-size:8pt; padding:3px 0 1px 0;")
        g.addWidget(_sh2, r, 0, 1, 3); r += 1
        for lbl_t, attr, sl_range, cfg_key, default in [
            ("阻尼:", "rdamp", (50, 99), 'radius_damping', 0.92),
            ("弹性:", "rspring", (1, 100), 'radius_spring', 0.15),
            ("回弹:", "rgrav", (0, 100), 'radius_gravity', 0.3),
        ]:
            g.addWidget(QLabel(lbl_t), r, 0)
            sl = QSlider(Qt.Horizontal); sl.setRange(*sl_range)
            val = self.config.get(cfg_key, default)
            sl.setValue(int(val * 100))
            lb = QLabel(f"{val:.2f}"); lb.setFixedWidth(42)
            sl.valueChanged.connect(lambda v, k=cfg_key, l=lb: (l.setText(f"{v/100:.2f}"), self._update_cfg(k, v / 100)))
            g.addWidget(sl, r, 1); g.addWidget(lb, r, 2)
            setattr(self, f'{attr}_slider', sl); setattr(self, f'{attr}_lbl', lb)
            r += 1

        _sh3 = QLabel("── 频率 · 条形长度 ──")
        _sh3.setStyleSheet("color:#888; font-size:8pt; padding:3px 0 1px 0;")
        g.addWidget(_sh3, r, 0, 1, 3); r += 1

        g.addWidget(QLabel("频率:"), r, 0)
        h_freq = QHBoxLayout(); h_freq.setSpacing(4)
        self.freq_min_spin = QSpinBox(); self.freq_min_spin.setRange(1, 20000); self.freq_min_spin.setSingleStep(10)
        self.freq_min_spin.setValue(self.config.get('freq_min', 20))
        self.freq_min_spin.valueChanged.connect(lambda v: self._update_cfg('freq_min', v))
        self.freq_max_spin = QSpinBox(); self.freq_max_spin.setRange(100, 22050); self.freq_max_spin.setSingleStep(100)
        self.freq_max_spin.setValue(self.config.get('freq_max', 20000))
        self.freq_max_spin.valueChanged.connect(lambda v: self._update_cfg('freq_max', v))
        h_freq.addWidget(self.freq_min_spin); h_freq.addWidget(QLabel("~")); h_freq.addWidget(self.freq_max_spin)
        h_freq.addWidget(QLabel("Hz"))
        g.addLayout(h_freq, r, 1, 1, 2); r += 1

        g.addWidget(QLabel("长度:"), r, 0)
        h_len = QHBoxLayout(); h_len.setSpacing(4)
        self.bar_len_min_spin = QSpinBox(); self.bar_len_min_spin.setRange(0, 500)
        self.bar_len_min_spin.setValue(self.config.get('bar_length_min', 0))
        self.bar_len_min_spin.valueChanged.connect(lambda v: self._update_cfg('bar_length_min', v))
        self.bar_len_max_spin = QSpinBox(); self.bar_len_max_spin.setRange(1, 2000)
        self.bar_len_max_spin.setValue(self.config.get('bar_length_max', 300))
        self.bar_len_max_spin.valueChanged.connect(lambda v: self._update_cfg('bar_length_max', v))
        h_len.addWidget(self.bar_len_min_spin); h_len.addWidget(QLabel("~")); h_len.addWidget(self.bar_len_max_spin)
        h_len.addWidget(QLabel("px"))
        g.addLayout(h_len, r, 1, 1, 2); r += 1

        s.add_layout(g)
        vlay.addWidget(s)

    # ── 预设管理 ──────────────────────────────────────────

    def _build_preset_section(self, vlay):
        s = _Collapsible("预设管理", expanded=False)
        g = QGridLayout(); g.setSpacing(4); g.setContentsMargins(0, 0, 0, 0)

        g.addWidget(QLabel("预设:"), 0, 0)
        self.preset_combo = QComboBox()
        self.preset_combo.setEditable(False)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        g.addWidget(self.preset_combo, 0, 1, 1, 3)

        b_save = QPushButton("💾 另存为")
        b_save.clicked.connect(self._save_preset_as)
        g.addWidget(b_save, 1, 0)

        b_reload = QPushButton("🔄 刷新列表")
        b_reload.clicked.connect(self._refresh_preset_list)
        g.addWidget(b_reload, 1, 1)

        # 自动随机切换预设
        self.preset_auto_check = QCheckBox("🔀 自动随机切换")
        self.preset_auto_check.setChecked(self.config.get('preset_auto_switch', False))
        self.preset_auto_check.toggled.connect(self._on_preset_auto_toggled)
        g.addWidget(self.preset_auto_check, 2, 0, 1, 2)

        h_interval = QHBoxLayout(); h_interval.setSpacing(4)
        h_interval.addWidget(QLabel("间隔:"))
        self.preset_interval_spin = QSpinBox()
        self.preset_interval_spin.setRange(1, 3600)
        self.preset_interval_spin.setSuffix(" 秒")
        self.preset_interval_spin.setValue(self.config.get('preset_switch_interval', 10))
        self.preset_interval_spin.valueChanged.connect(self._on_preset_interval_changed)
        h_interval.addWidget(self.preset_interval_spin)
        g.addLayout(h_interval, 2, 2, 1, 2)

        s.add_layout(g)
        vlay.addWidget(s)

        # 如果之前已启用，启动定时器
        if self.config.get('preset_auto_switch', False):
            self.preset_timer.start(self.config.get('preset_switch_interval', 10) * 1000)

    def _ensure_presets_dir(self):
        PRESETS_DIR.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe_preset_name(name: str):
        invalid = '<>:"/\\|?*'
        clean = ''.join('_' if ch in invalid else ch for ch in name).strip().strip('.')
        return clean

    def _refresh_preset_list(self):
        self._ensure_presets_dir()
        current_fp = self.preset_combo.currentData()
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        files = sorted(PRESETS_DIR.glob('*.json'), key=lambda p: p.name.lower())
        selected_idx = -1
        for fp in files:
            self.preset_combo.addItem(fp.stem, str(fp))
            if current_fp and str(fp) == str(current_fp):
                selected_idx = self.preset_combo.count() - 1
        if selected_idx >= 0:
            self.preset_combo.setCurrentIndex(selected_idx)
        self.preset_combo.blockSignals(False)

    def _on_preset_changed(self, _idx):
        self._load_selected_preset(show_message=False)

    def _on_preset_auto_toggled(self, v):
        self._update_cfg('preset_auto_switch', v)
        if v:
            interval = self.preset_interval_spin.value()
            self.preset_timer.start(interval * 1000)
        else:
            self.preset_timer.stop()

    def _on_preset_interval_changed(self, v):
        self._update_cfg('preset_switch_interval', v)
        if self.preset_auto_check.isChecked():
            self.preset_timer.start(v * 1000)

    def _auto_switch_preset(self):
        count = self.preset_combo.count()
        if count < 2:
            return
        current = self.preset_combo.currentIndex()
        candidates = [i for i in range(count) if i != current]
        idx = random.choice(candidates)
        self.preset_combo.setCurrentIndex(idx)

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
            save_data = {k: v for k, v in self.config.items() if k not in ('pos_x', 'pos_y')}
            with open(fp, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
            self._refresh_preset_list()
            idx = self.preset_combo.findText(safe_name)
            if idx >= 0:
                self.preset_combo.setCurrentIndex(idx)
            QMessageBox.information(self, "成功", f"预设已保存: {safe_name}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存预设失败: {e}")

    def _load_selected_preset(self, show_message=False):
        fp = self.preset_combo.currentData()
        if not fp:
            return
        try:
            with open(fp, 'r', encoding='utf-8') as f:
                data = json.load(f)
            cfg = _get_defaults()
            cfg.update(data)
            # 保留当前位置，不用预设中的
            cfg['pos_x'] = self.config.get('pos_x', -1)
            cfg['pos_y'] = self.config.get('pos_y', -1)
            self._apply_config_to_ui(cfg)
            if show_message:
                QMessageBox.information(self, "成功", f"已加载预设: {Path(fp).stem}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载预设失败: {e}")

    # ── 颜色 ──────────────────────────────────────────

    def _build_color_section(self, vlay):
        s = _Collapsible("颜色方案", expanded=False)
        g = QVBoxLayout()

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

        self.dyn_check = QCheckBox("动态色相循环")
        self.dyn_check.setChecked(self.config['color_dynamic'])
        self.dyn_check.toggled.connect(self._on_dynamic_toggled)
        cl.addWidget(self.dyn_check)

        self.dyn_widget = QWidget()
        dl = QGridLayout(self.dyn_widget); dl.setContentsMargins(10,2,0,2)
        dl.addWidget(QLabel("速度:"), 0, 0)
        self.cyc_spd_slider = QSlider(Qt.Horizontal); self.cyc_spd_slider.setRange(0, 1000)
        self.cyc_spd_slider.setValue(int(self.config['color_cycle_speed'] * 100))
        self.cyc_spd_lbl = QLabel(f"{self.config['color_cycle_speed']:.2f}x"); self.cyc_spd_lbl.setFixedWidth(42)
        self.cyc_spd_slider.valueChanged.connect(lambda v: (self.cyc_spd_lbl.setText(f"{v/100:.2f}x"), self._update_cfg('color_cycle_speed', v / 100)))
        dl.addWidget(self.cyc_spd_slider, 0, 1); dl.addWidget(self.cyc_spd_lbl, 0, 2)
        dl.addWidget(QLabel("指数:"), 1, 0)
        self.cyc_pow_slider = QSlider(Qt.Horizontal); self.cyc_pow_slider.setRange(1, 500)
        self.cyc_pow_slider.setValue(int(self.config['color_cycle_pow'] * 100))
        self.cyc_pow_lbl = QLabel(f"{self.config['color_cycle_pow']:.2f}"); self.cyc_pow_lbl.setFixedWidth(42)
        self.cyc_pow_slider.valueChanged.connect(lambda v: (self.cyc_pow_lbl.setText(f"{v/100:.2f}"), self._update_cfg('color_cycle_pow', v / 100)))
        dl.addWidget(self.cyc_pow_slider, 1, 1); dl.addWidget(self.cyc_pow_lbl, 1, 2)
        self.cyc_a1_check = QCheckBox("受K1响度控制")
        self.cyc_a1_check.setChecked(self.config['color_cycle_a1'])
        self.cyc_a1_check.toggled.connect(lambda v: self._update_cfg('color_cycle_a1', v))
        dl.addWidget(self.cyc_a1_check, 2, 0, 1, 3)
        cl.addWidget(self.dyn_widget)
        self.dyn_widget.setVisible(self.config['color_dynamic'])

        g.addWidget(self.color_grp)
        self.color_grp.setVisible(cur == 'custom')
        s.add_layout(g)
        vlay.addWidget(s)

    # ── 物理动画 ──────────────────────────────────────────

    def _build_physics_section(self, vlay):
        s = _Collapsible("物理动画", expanded=False)
        g = QGridLayout(); g.setSpacing(3); g.setContentsMargins(0,0,0,0); r = 0

        for lbl_t, attr, sl_range, cfg_key, default in [
            ("阻尼:", "damp", (0, 200), 'damping', 0.85),
            ("弹性:", "spring", (0, 300), 'spring_strength', 0.3),
            ("重力:", "grav", (0, 200), 'gravity', 0.5),
        ]:
            g.addWidget(QLabel(lbl_t), r, 0)
            sl = QSlider(Qt.Horizontal); sl.setRange(*sl_range)
            val = self.config.get(cfg_key, default)
            sl.setValue(int(val * 100))
            lb = QLabel(f"{val:.2f}"); lb.setFixedWidth(42)
            sl.valueChanged.connect(lambda v, k=cfg_key, l=lb: (l.setText(f"{v/100:.2f}"), self._update_cfg(k, v / 100)))
            g.addWidget(sl, r, 1); g.addWidget(lb, r, 2)
            setattr(self, f'{attr}_slider', sl); setattr(self, f'{attr}_lbl', lb)
            r += 1

        g.addWidget(QLabel("高度:"), r, 0)
        hh = QHBoxLayout(); hh.setSpacing(4)
        self.hmin_spin = QSpinBox(); self.hmin_spin.setRange(0, 1000)
        self.hmin_spin.setValue(self.config['bar_height_min'])
        self.hmin_spin.valueChanged.connect(lambda v: self._update_cfg('bar_height_min', v))
        self.hmax_spin = QSpinBox(); self.hmax_spin.setRange(10, 2000)
        self.hmax_spin.setValue(self.config['bar_height_max'])
        self.hmax_spin.valueChanged.connect(lambda v: self._update_cfg('bar_height_max', v))
        hh.addWidget(self.hmin_spin); hh.addWidget(QLabel("~")); hh.addWidget(self.hmax_spin)
        hh.addWidget(QLabel("px"))
        g.addLayout(hh, r, 1, 1, 2); r += 1

        s.add_layout(g)
        vlay.addWidget(s)

    # ── 窗口行为 ──────────────────────────────────────────

    def _build_window_section(self, vlay):
        s = _Collapsible("窗口行为", expanded=False)
        g = QVBoxLayout()
        self.trans_check = QCheckBox("背景透明")
        self.trans_check.setChecked(self.config['bg_transparent'])
        self.trans_check.toggled.connect(lambda v: self._update_cfg('bg_transparent', v))
        g.addWidget(self.trans_check)
        self.top_check = QCheckBox("窗口置顶")
        self.top_check.setChecked(self.config['always_on_top'])
        self.top_check.toggled.connect(lambda v: self._update_cfg('always_on_top', v))
        g.addWidget(self.top_check)
        s.add_layout(g)
        vlay.addWidget(s)

    # ── 五层轮廓 ──────────────────────────────────────────

    def _build_contour_section(self, vlay):
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
            cbtn.setFixedSize(40, 18)
            cbtn.setStyleSheet(f"background:rgb({cc[0]},{cc[1]},{cc[2]}); border:1px solid #aaa; border-radius:2px;")
            cbtn.clicked.connect(lambda _, i=li: self._pick_layer_color(i))
            setattr(self, f'c{li}_color_btn', cbtn)
            g.addWidget(cbtn, r, 1)

            sp = QSpinBox(); sp.setRange(1, 20)
            sp.setValue(self.config.get(f'c{li}_thick', 2))
            sp.valueChanged.connect(lambda v, k=f'c{li}_thick': self._update_cfg(k, v))
            setattr(self, f'c{li}_thick_spin', sp)
            ht = QHBoxLayout()
            ht.addWidget(QLabel("粗:")); ht.addWidget(sp)
            g.addLayout(ht, r, 2, 1, 2); r += 1

            g.addWidget(QLabel("透明:"), r, 0)
            sl_a = QSlider(Qt.Horizontal); sl_a.setRange(0, 255)
            av = self.config.get(f'c{li}_alpha', 180)
            sl_a.setValue(av)
            lb_a = QLabel(str(av)); lb_a.setFixedWidth(30)
            sl_a.valueChanged.connect(lambda v, k=f'c{li}_alpha', l=lb_a: (l.setText(str(v)), self._update_cfg(k, v)))
            setattr(self, f'c{li}_alpha_slider', sl_a)
            g.addWidget(sl_a, r, 1, 1, 2); g.addWidget(lb_a, r, 3); r += 1

            fc = QCheckBox("填充")
            fc.setChecked(self.config.get(f'c{li}_fill', False))
            fc.toggled.connect(lambda v, k=f'c{li}_fill': self._update_cfg(k, v))
            setattr(self, f'c{li}_fill_check', fc)
            g.addWidget(fc, r, 0)
            fsl = QSlider(Qt.Horizontal); fsl.setRange(0, 255)
            fv = self.config.get(f'c{li}_fill_alpha', 50)
            fsl.setValue(fv)
            flb = QLabel(str(fv)); flb.setFixedWidth(30)
            fsl.valueChanged.connect(lambda v, k=f'c{li}_fill_alpha', l=flb: (l.setText(str(v)), self._update_cfg(k, v)))
            setattr(self, f'c{li}_fill_alpha_slider', fsl)
            g.addWidget(fsl, r, 1, 1, 2); g.addWidget(flb, r, 3); r += 1

            if has_step:
                g.addWidget(QLabel("间隔:"), r, 0)
                ssp = QSpinBox(); ssp.setRange(1, 32)
                ssp.setValue(self.config.get(f'c{li}_step', 2))
                ssp.valueChanged.connect(lambda v, k=f'c{li}_step': self._update_cfg(k, v))
                setattr(self, f'c{li}_step_spin', ssp)
                g.addWidget(ssp, r, 1); r += 1

            if has_decay:
                g.addWidget(QLabel("衰减:"), r, 0)
                dsl = QSlider(Qt.Horizontal); dsl.setRange(900, 1000)
                dv = self.config.get(f'c{li}_decay', 0.995)
                dsl.setValue(int(dv * 1000))
                dlb = QLabel(f"{dv:.3f}"); dlb.setFixedWidth(42)
                dsl.valueChanged.connect(lambda v, k=f'c{li}_decay', l=dlb: (l.setText(f"{v/1000:.3f}"), self._update_cfg(k, v / 1000)))
                setattr(self, f'c{li}_decay_slider', dsl)
                g.addWidget(dsl, r, 1, 1, 2); g.addWidget(dlb, r, 3); r += 1

            g.addWidget(QLabel("转速:"), r, 0)
            rsl = QSlider(Qt.Horizontal); rsl.setRange(-500, 500)
            rv = self.config.get(f'c{li}_rot_speed', 1.0)
            rsl.setValue(int(rv * 100))
            rlb = QLabel(f"{rv:.2f}"); rlb.setFixedWidth(42)
            rsl.valueChanged.connect(lambda v, k=f'c{li}_rot_speed', l=rlb: (l.setText(f"{v/100:.2f}"), self._update_cfg(k, v / 100)))
            setattr(self, f'c{li}_rot_speed_slider', rsl)
            g.addWidget(rsl, r, 1, 1, 2); g.addWidget(rlb, r, 3); r += 1

            g.addWidget(QLabel("pow:"), r, 0)
            psl = QSlider(Qt.Horizontal); psl.setRange(-300, 300)
            pv = self.config.get(f'c{li}_rot_pow', 0.5)
            psl.setValue(int(pv * 100))
            plb = QLabel(f"{pv:.2f}"); plb.setFixedWidth(42)
            psl.valueChanged.connect(lambda v, k=f'c{li}_rot_pow', l=plb: (l.setText(f"{v/100:.2f}"), self._update_cfg(k, v / 100)))
            setattr(self, f'c{li}_rot_pow_slider', psl)
            g.addWidget(psl, r, 1, 1, 2); g.addWidget(plb, r, 3); r += 1

        s.add_layout(g)
        vlay.addWidget(s)

    # ── 四层条形 ──────────────────────────────────────────

    def _build_bars_section(self, vlay):
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
            sp = QSpinBox(); sp.setRange(1, 20)
            sp.setValue(self.config.get(f'{key}_thick', 3))
            sp.valueChanged.connect(lambda v, k=f'{key}_thick': self._update_cfg(k, v))
            setattr(self, f'{key}_thick_spin', sp)
            ht = QHBoxLayout()
            ht.addWidget(QLabel("粗:")); ht.addWidget(sp)
            g.addLayout(ht, r, 1, 1, 2); r += 1

            fchk = QCheckBox("固定长度")
            fchk.setChecked(self.config.get(f'{key}_fixed', False))
            setattr(self, f'{key}_fixed_check', fchk)
            g.addWidget(fchk, r, 0)
            fsp = QSpinBox(); fsp.setRange(1, 500)
            fsp.setValue(self.config.get(f'{key}_fixed_len', 30))
            fsp.valueChanged.connect(lambda v, k=f'{key}_fixed_len': self._update_cfg(k, v))
            setattr(self, f'{key}_fixed_len_spin', fsp)
            fh = QHBoxLayout()
            fh.addWidget(fsp); fh.addWidget(QLabel("px"))
            g.addLayout(fh, r, 1, 1, 2); r += 1

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

        s.add_layout(g)
        vlay.addWidget(s)

    # ── 高级控制 ──────────────────────────────────────────

    def _build_k1_section(self, vlay):
        s = _Collapsible("高级控制", expanded=False)
        g = QGridLayout(); g.setSpacing(3); g.setContentsMargins(0,0,0,0); r = 0

        # K1 当前值 + 时间窗口
        g.addWidget(QLabel("K1:"), r, 0)
        self.a1_lbl = QLabel("0.00")
        g.addWidget(self.a1_lbl, r, 1)
        g.addWidget(QLabel("窗口:"), r, 2)
        self.a1_spin = QDoubleSpinBox()
        self.a1_spin.setRange(0.01, 60.0); self.a1_spin.setSingleStep(0.1); self.a1_spin.setDecimals(2)
        self.a1_spin.setValue(self.config['a1_time_window']); self.a1_spin.setSuffix(" 秒")
        self.a1_spin.valueChanged.connect(lambda v: self._update_cfg('a1_time_window', v))
        g.addWidget(self.a1_spin, r, 3); r += 1

        # K2 启用
        _sh_k2 = QLabel("── K2 (差分幂) ──")
        _sh_k2.setStyleSheet("color:#888; font-size:8pt; padding:3px 0 1px 0;")
        g.addWidget(_sh_k2, r, 0, 1, 4); r += 1

        self.k2_check = QCheckBox("启用 K2 替代 K1")
        self.k2_check.setChecked(self.config.get('k2_enabled', False))
        self.k2_check.toggled.connect(lambda v: self._update_cfg('k2_enabled', v))
        g.addWidget(self.k2_check, r, 0, 1, 2)
        g.addWidget(QLabel("K2:"), r, 2)
        self.k2_lbl = QLabel("0.00")
        g.addWidget(self.k2_lbl, r, 3); r += 1

        g.addWidget(QLabel("幂次:"), r, 0)
        self.k2_pow_spin = QDoubleSpinBox()
        self.k2_pow_spin.setRange(0.01, 10.0); self.k2_pow_spin.setSingleStep(0.1); self.k2_pow_spin.setDecimals(2)
        self.k2_pow_spin.setValue(self.config.get('k2_pow', 1.0))
        self.k2_pow_spin.valueChanged.connect(lambda v: self._update_cfg('k2_pow', v))
        g.addWidget(self.k2_pow_spin, r, 1); r += 1

        s.add_layout(g)
        vlay.addWidget(s)

    # ── 随机化 ──────────────────────────────────────────

    def _build_random_section(self, vlay):
        s = _Collapsible("🎲 随机", expanded=False)
        v = QVBoxLayout()

        btn_row = QHBoxLayout()
        btn_rand = QPushButton("🎲 随机化选中项")
        btn_rand.setMinimumHeight(30)
        btn_rand.clicked.connect(self._randomize_selected)
        btn_row.addWidget(btn_rand)
        btn_all = QPushButton("全选")
        btn_all.clicked.connect(lambda: self._set_all_random_checks(True))
        btn_row.addWidget(btn_all)
        btn_none = QPushButton("全不选")
        btn_none.clicked.connect(lambda: self._set_all_random_checks(False))
        btn_row.addWidget(btn_none)
        v.addLayout(btn_row)

        self.random_tree = QTreeWidget()
        self.random_tree.setHeaderHidden(True)
        self.random_tree.setMinimumHeight(300)

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
        v.addWidget(self.random_tree)
        s.add_layout(v)
        vlay.addWidget(s)

    @staticmethod
    def _get_randomizable_props():
        props = [
            ("控制 · 通用", [
                ("总开关", "master_visible", "bool"),
                ("缩放", "global_scale", "float", 0.1, 5.0),
                ("背景透明度", "alpha", "int", 0, 255),
                ("UI透明度", "ui_alpha", "int", 0, 255),
                ("平滑度", "smoothing", "float", 0.0, 1.0),
                ("频谱条数", "num_bars", "int", 4, 256),
            ]),
            ("频谱", [
                ("半径", "circle_radius", "int", 10, 500),
                ("段数", "circle_segments", "int", 1, 8),
                ("K1旋转", "circle_a1_rotation", "bool"),
                ("K1半径", "circle_a1_radius", "bool"),
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
                ("循环速度", "color_cycle_speed", "float", 0.0, 10.0),
                ("循环指数", "color_cycle_pow", "float", 0.01, 5.0),
                ("K1色相控制", "color_cycle_a1", "bool"),
            ]),
            ("物理动画", [
                ("阻尼", "damping", "float", 0.0, 2.0),
                ("弹性", "spring_strength", "float", 0.0, 3.0),
                ("重力", "gravity", "float", 0.0, 2.0),
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
            ]
            props.append((bname, cat_props))

        props.append(("高级控制", [
            ("K1时间窗口", "a1_time_window", "float", 0.01, 60.0),
            ("K2启用", "k2_enabled", "bool"),
            ("K2幂次", "k2_pow", "float", 0.01, 10.0),
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

    def _randomize_selected(self):
        """随机化所有被选中的属性"""
        changed = False
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
                    self.config[cfg_key] = (
                        random.randint(0, 255),
                        random.randint(0, 255),
                        random.randint(0, 255),
                    )
                elif ptype == "choice":
                    self.config[cfg_key] = random.choice(prop_def[3])
                changed = True
        if changed:
            self._apply_config_to_ui(self.config)

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
        c = QColorDialog.getColor(QColor(*cur), self, f"L{layer_idx} 颜色")
        if c.isValid():
            rgb = (c.red(), c.green(), c.blue())
            btn = getattr(self, f'c{layer_idx}_color_btn')
            btn.setStyleSheet(f"background:rgb({rgb[0]},{rgb[1]},{rgb[2]}); border:1px solid #aaa; border-radius:2px;")
            self._update_cfg(key, rgb)

    def _on_dynamic_toggled(self, v):
        self.dyn_widget.setVisible(v)
        self._update_cfg('color_dynamic', v)

    def _rebuild_gradient_ui(self):
        for w in self.gp_widgets:
            w.setParent(None); w.deleteLater()
        self.gp_widgets.clear()

        points = sorted(self.config.get('gradient_points', [(0.0, (255, 0, 128)), (1.0, (0, 255, 255))]), key=lambda p: p[0])
        for i, (pos, color) in enumerate(points):
            row = QWidget()
            rl = QHBoxLayout(row); rl.setContentsMargins(0, 2, 0, 2)

            lbl = QLabel(f"{pos:.2f}"); lbl.setFixedWidth(35)
            rl.addWidget(lbl)
            sl = QSlider(Qt.Horizontal); sl.setRange(0, 100); sl.setValue(int(pos * 100))
            sl.valueChanged.connect(lambda v, idx=i, lb=lbl: self._gp_pos_changed(idx, v, lb))
            rl.addWidget(sl)

            btn = QPushButton(); btn.setFixedSize(40, 25)
            btn.setStyleSheet(f"background:rgb({color[0]},{color[1]},{color[2]}); border:1px solid #aaa; border-radius:2px;")
            btn.clicked.connect(lambda _, idx=i, b=btn: self._gp_color_pick(idx, b))
            rl.addWidget(btn)

            if len(points) > 2:
                db = QPushButton("❌"); db.setFixedSize(25, 25)
                db.clicked.connect(lambda _, idx=i: self._gp_remove(idx))
                rl.addWidget(db)

            self.gp_layout.addWidget(row)
            self.gp_widgets.append(row)

    def _gp_pos_changed(self, idx, val, lbl):
        p = val / 100.0; lbl.setText(f"{p:.2f}")
        pts = list(self.config.get('gradient_points', []))
        if idx < len(pts):
            pts[idx] = (p, pts[idx][1])
            self._update_cfg('gradient_points', pts)

    def _gp_color_pick(self, idx, btn):
        pts = list(self.config.get('gradient_points', []))
        if idx >= len(pts):
            return
        cur = pts[idx][1]
        c = QColorDialog.getColor(QColor(*cur), self, "选择颜色")
        if c.isValid():
            rgb = (c.red(), c.green(), c.blue())
            btn.setStyleSheet(f"background:rgb({rgb[0]},{rgb[1]},{rgb[2]}); border:1px solid #aaa; border-radius:2px;")
            pts[idx] = (pts[idx][0], rgb)
            self._update_cfg('gradient_points', pts)

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

            self.status_timer.start(1000)  # 降低到1秒，减少对用户输入的干扰
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

    def _apply_config_to_ui(self, cfg):
        d = _get_defaults()
        d.update(cfg)
        # 保留随机勾选状态，不被预设/复位覆盖
        d['random_checked'] = self.config.get('random_checked', [])

        self._applying_config = True
        try:
            self.config = d

            # 基础 UI
            self.master_visible_check.setChecked(d.get('master_visible', True))
            self.scale_spin.setValue(d.get('global_scale', 1.0))
            self.pos_x_spin.setValue(d.get('pos_x', -1)); self.pos_y_spin.setValue(d.get('pos_y', -1))
            self.drag_adjust_check.setChecked(d.get('drag_adjust_mode', False))
            self.width_spin.setValue(d.get('width', 0)); self.height_spin.setValue(d.get('height', 0))
            self.bars_spin.setValue(d.get('num_bars', 64)); self.smooth_slider.setValue(int(d.get('smoothing', 0.7) * 100))
            self.alpha_slider.setValue(d.get('alpha', 255)); self.ui_alpha_slider.setValue(d.get('ui_alpha', 180))
            schemes = ['rainbow', 'fire', 'ice', 'neon', 'custom']
            scheme = d.get('color_scheme', 'rainbow')
            self.color_combo.setCurrentIndex(schemes.index(scheme) if scheme in schemes else 0)
            self.damp_slider.setValue(int(d.get('damping', 0.85) * 100))
            self.spring_slider.setValue(int(d.get('spring_strength', 0.3) * 100))
            self.grav_slider.setValue(int(d.get('gravity', 0.5) * 100))
            self.hmin_spin.setValue(d.get('bar_height_min', 0)); self.hmax_spin.setValue(d.get('bar_height_max', 500))
            self.radius_spin.setValue(d.get('circle_radius', 150)); self.seg_spin.setValue(d.get('circle_segments', 1))
            self.a1rot_check.setChecked(d.get('circle_a1_rotation', True)); self.a1rad_check.setChecked(d.get('circle_a1_radius', True))
            self.rdamp_slider.setValue(int(d.get('radius_damping', 0.92) * 100))
            self.rspring_slider.setValue(int(d.get('radius_spring', 0.15) * 100))
            self.rgrav_slider.setValue(int(d.get('radius_gravity', 0.3) * 100))
            self.freq_min_spin.setValue(d.get('freq_min', 20)); self.freq_max_spin.setValue(d.get('freq_max', 20000))
            self.bar_len_min_spin.setValue(d.get('bar_length_min', 0)); self.bar_len_max_spin.setValue(d.get('bar_length_max', 300))
            self.a1_spin.setValue(d.get('a1_time_window', 10.0))
            self.k2_check.setChecked(d.get('k2_enabled', False))
            self.k2_pow_spin.setValue(d.get('k2_pow', 1.0))
            self.trans_check.setChecked(d.get('bg_transparent', True)); self.top_check.setChecked(d.get('always_on_top', True))

            # 颜色/渐变
            self.grad_check.setChecked(d.get('gradient_enabled', True))
            self.grad_mode_combo.setCurrentIndex(0 if d.get('gradient_mode', 'frequency') == 'frequency' else 1)
            self.dyn_check.setChecked(d.get('color_dynamic', False))
            self.cyc_spd_slider.setValue(int(d.get('color_cycle_speed', 1.0) * 100))
            self.cyc_pow_slider.setValue(int(d.get('color_cycle_pow', 2.0) * 100))
            self.cyc_a1_check.setChecked(d.get('color_cycle_a1', True))
            self._rebuild_gradient_ui()

            # 五层轮廓
            for li in range(1, 6):
                getattr(self, f'c{li}_on_check').setChecked(d.get(f'c{li}_on', False))
                cc = d.get(f'c{li}_color', (255, 255, 255))
                getattr(self, f'c{li}_color_btn').setStyleSheet(
                    f"background:rgb({cc[0]},{cc[1]},{cc[2]}); border:1px solid #aaa; border-radius:2px;")
                getattr(self, f'c{li}_thick_spin').setValue(d.get(f'c{li}_thick', 2))
                getattr(self, f'c{li}_alpha_slider').setValue(d.get(f'c{li}_alpha', 180))
                getattr(self, f'c{li}_fill_check').setChecked(d.get(f'c{li}_fill', False))
                getattr(self, f'c{li}_fill_alpha_slider').setValue(d.get(f'c{li}_fill_alpha', 50))
                if hasattr(self, f'c{li}_step_spin'):
                    getattr(self, f'c{li}_step_spin').setValue(d.get(f'c{li}_step', 2))
                if hasattr(self, f'c{li}_decay_slider'):
                    getattr(self, f'c{li}_decay_slider').setValue(int(d.get(f'c{li}_decay', 0.995) * 1000))
                getattr(self, f'c{li}_rot_speed_slider').setValue(int(d.get(f'c{li}_rot_speed', 1.0) * 100))
                getattr(self, f'c{li}_rot_pow_slider').setValue(int(d.get(f'c{li}_rot_pow', 0.5) * 100))

            # 四层条形
            for key in ('b12', 'b23', 'b34', 'b45'):
                getattr(self, f'{key}_on_check').setChecked(d.get(f'{key}_on', False))
                getattr(self, f'{key}_thick_spin').setValue(d.get(f'{key}_thick', 3))
                getattr(self, f'{key}_fixed_check').setChecked(d.get(f'{key}_fixed', False))
                getattr(self, f'{key}_fixed_len_spin').setValue(d.get(f'{key}_fixed_len', 30))
                getattr(self, f'{key}_start_check').setChecked(d.get(f'{key}_from_start', True))
                getattr(self, f'{key}_end_check').setChecked(d.get(f'{key}_from_end', False))
                getattr(self, f'{key}_center_check').setChecked(d.get(f'{key}_from_center', False))
                getattr(self, f'{key}_mode_widget').setVisible(d.get(f'{key}_fixed', False))
        finally:
            self._applying_config = False

        self._save_config()
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
                if 'a1' in st:
                    self.current_a1 = st['a1']
                    self.a1_lbl.setText(f"{self.current_a1:.2f}")
                if 'k2' in st:
                    self.k2_lbl.setText(f"{st['k2']:.2f}")
                if 'pos_x' in st and 'pos_y' in st:
                    # 只有在用户没有聚焦pos控件时才更新显示，避免干扰用户输入
                    if not (self.pos_x_spin.hasFocus() or self.pos_y_spin.hasFocus()):
                        self.pos_x_spin.blockSignals(True)
                        self.pos_y_spin.blockSignals(True)
                        self.pos_x_spin.setValue(st['pos_x'])
                        self.pos_y_spin.setValue(st['pos_y'])
                        self.pos_x_spin.blockSignals(False)
                        self.pos_y_spin.blockSignals(False)
        except:
            pass

    def closeEvent(self, event):
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
    pal = app.palette()
    _hi = pal.color(QPalette.ColorRole.Highlight)
    app.setStyleSheet(f"""
        QCheckBox::indicator {{ width: 15px; height: 15px; border-radius: 2px; }}
        QCheckBox::indicator:unchecked {{
            background-color: #bbb;
            border: 1px solid #888;
        }}
        QCheckBox::indicator:checked {{
            background-color: {_hi.name()};
            border: 1px solid {_hi.darker(120).name()};
        }}
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
