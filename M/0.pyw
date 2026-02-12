"""
音频可视化控制台 - 主框架
支持选择不同可视化模式（当前仅圆形频谱）
通过 multiprocessing 启动子程序并实时传递配置
"""

import sys
import os
import json
import time
import multiprocessing as mp
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QSlider,
    QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox,
    QFrame, QMessageBox, QColorDialog, QScrollArea,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor, QPalette

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

        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status)

        self._init_ui()

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
        self._send_config()
        self._save_config()

    def _send_config(self):
        if not self.config_queue or self.config_queue.full():
            return
        try:
            while not self.config_queue.empty():
                try:
                    self.config_queue.get_nowait()
                except:
                    break
            self.config_queue.put(self.config)
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
        self._build_visual_section(vlay)
        self._build_color_section(vlay)
        self._build_physics_section(vlay)
        self._build_window_section(vlay)
        self._build_spectrum_section(vlay)
        self._build_contour_section(vlay)
        self._build_bars_section(vlay)
        self._build_a1_section(vlay)

        vlay.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll)

    # ── 控制区 ──────────────────────────────────────────

    def _build_control_section(self, vlay):
        s = _Collapsible("控制")
        g = QVBoxLayout()

        row = QHBoxLayout()
        row.addWidget(QLabel("模式:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["圆形频谱"])
        row.addWidget(self.mode_combo); row.addStretch()
        g.addLayout(row)

        self.toggle_btn = QPushButton("🚀 启动可视化")
        self.toggle_btn.setMinimumHeight(40)
        self._set_btn_start_style()
        self.toggle_btn.clicked.connect(self._toggle)
        g.addWidget(self.toggle_btn)

        rrow = QHBoxLayout()
        b1 = QPushButton("📍 复位位置"); b1.setMinimumHeight(30)
        b1.clicked.connect(self._center_window); rrow.addWidget(b1)
        b2 = QPushButton("🔄 复位参数"); b2.setMinimumHeight(30)
        b2.clicked.connect(self._reset_all); rrow.addWidget(b2)
        g.addLayout(rrow)

        s.add_layout(g)
        vlay.addWidget(s)

    # ── 视觉设置 ──────────────────────────────────────────

    def _build_visual_section(self, vlay):
        s = _Collapsible("通用视觉", expanded=False)
        g = QGridLayout(); g.setSpacing(3); g.setContentsMargins(0,0,0,0); r = 0

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

        s.add_layout(g)
        vlay.addWidget(s)

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
        self.cyc_a1_check = QCheckBox("受A1响度控制")
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

    # ── 频谱基础 ──────────────────────────────────────────

    def _build_spectrum_section(self, vlay):
        s = _Collapsible("频谱基础")
        g = QGridLayout(); g.setSpacing(3); g.setContentsMargins(0,0,0,0); r = 0

        self.master_visible_check = QCheckBox("总开关（显示全部）")
        self.master_visible_check.setChecked(self.config.get('master_visible', True))
        self.master_visible_check.toggled.connect(lambda v: self._update_cfg('master_visible', v))
        g.addWidget(self.master_visible_check, r, 0, 1, 3); r += 1

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
        self.a1rot_check = QCheckBox("A1 驱动旋转")
        self.a1rot_check.setChecked(self.config['circle_a1_rotation'])
        self.a1rot_check.toggled.connect(lambda v: self._update_cfg('circle_a1_rotation', v))
        self.a1rad_check = QCheckBox("A1 响应半径")
        self.a1rad_check.setChecked(self.config['circle_a1_radius'])
        self.a1rad_check.toggled.connect(lambda v: self._update_cfg('circle_a1_radius', v))
        hr.addWidget(self.a1rot_check); hr.addWidget(self.a1rad_check); hr.addStretch()
        g.addLayout(hr, r, 0, 1, 3); r += 1

        _sh = QLabel("── 半径缓动 ──")
        _sh.setStyleSheet("color:#888; font-size:8pt; padding:3px 0 1px 0;")
        g.addWidget(_sh, r, 0, 1, 3); r += 1
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

        _sh2 = QLabel("── 频率 · 条形长度 ──")
        _sh2.setStyleSheet("color:#888; font-size:8pt; padding:3px 0 1px 0;")
        g.addWidget(_sh2, r, 0, 1, 3); r += 1

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

    # ── 五层轮廓 ──────────────────────────────────────────

    def _build_contour_section(self, vlay):
        s = _Collapsible("五层轮廓 (C1~C5)", expanded=False)
        _layers = [
            (1, "内缓慢", True, True),
            (2, "内快速", True, False),
            (3, "基圆",   False, False),
            (4, "外快速", True, False),
            (5, "外缓慢", True, True),
        ]
        for li, lname, has_step, has_decay in _layers:
            sec = _Collapsible(f"L{li} {lname}", expanded=False)
            gl = QGridLayout(); gl.setSpacing(3); gl.setContentsMargins(0,0,0,0); rl = 0

            chk = QCheckBox("显示")
            chk.setChecked(self.config.get(f'c{li}_on', False))
            chk.toggled.connect(lambda v, k=f'c{li}_on': self._update_cfg(k, v))
            setattr(self, f'c{li}_on_check', chk)
            gl.addWidget(chk, rl, 0)

            cbtn = QPushButton()
            cc = self.config.get(f'c{li}_color', (255, 255, 255))
            cbtn.setFixedSize(40, 18)
            cbtn.setStyleSheet(f"background:rgb({cc[0]},{cc[1]},{cc[2]}); border:1px solid #aaa; border-radius:2px;")
            cbtn.clicked.connect(lambda _, i=li: self._pick_layer_color(i))
            setattr(self, f'c{li}_color_btn', cbtn)
            gl.addWidget(cbtn, rl, 1)

            sp = QSpinBox(); sp.setRange(1, 20)
            sp.setValue(self.config.get(f'c{li}_thick', 2))
            sp.valueChanged.connect(lambda v, k=f'c{li}_thick': self._update_cfg(k, v))
            setattr(self, f'c{li}_thick_spin', sp)
            ht = QHBoxLayout()
            ht.addWidget(QLabel("粗:")); ht.addWidget(sp)
            gl.addLayout(ht, rl, 2, 1, 2); rl += 1

            gl.addWidget(QLabel("透明:"), rl, 0)
            sl_a = QSlider(Qt.Horizontal); sl_a.setRange(0, 255)
            av = self.config.get(f'c{li}_alpha', 180)
            sl_a.setValue(av)
            lb_a = QLabel(str(av)); lb_a.setFixedWidth(30)
            sl_a.valueChanged.connect(lambda v, k=f'c{li}_alpha', l=lb_a: (l.setText(str(v)), self._update_cfg(k, v)))
            setattr(self, f'c{li}_alpha_slider', sl_a)
            gl.addWidget(sl_a, rl, 1, 1, 2); gl.addWidget(lb_a, rl, 3); rl += 1

            fc = QCheckBox("填充")
            fc.setChecked(self.config.get(f'c{li}_fill', False))
            fc.toggled.connect(lambda v, k=f'c{li}_fill': self._update_cfg(k, v))
            setattr(self, f'c{li}_fill_check', fc)
            gl.addWidget(fc, rl, 0)
            fsl = QSlider(Qt.Horizontal); fsl.setRange(0, 255)
            fv = self.config.get(f'c{li}_fill_alpha', 50)
            fsl.setValue(fv)
            flb = QLabel(str(fv)); flb.setFixedWidth(30)
            fsl.valueChanged.connect(lambda v, k=f'c{li}_fill_alpha', l=flb: (l.setText(str(v)), self._update_cfg(k, v)))
            setattr(self, f'c{li}_fill_alpha_slider', fsl)
            gl.addWidget(fsl, rl, 1, 1, 2); gl.addWidget(flb, rl, 3); rl += 1

            if has_step:
                gl.addWidget(QLabel("间隔:"), rl, 0)
                ssp = QSpinBox(); ssp.setRange(1, 32)
                ssp.setValue(self.config.get(f'c{li}_step', 2))
                ssp.valueChanged.connect(lambda v, k=f'c{li}_step': self._update_cfg(k, v))
                setattr(self, f'c{li}_step_spin', ssp)
                gl.addWidget(ssp, rl, 1); rl += 1

            if has_decay:
                gl.addWidget(QLabel("衰减:"), rl, 0)
                dsl = QSlider(Qt.Horizontal); dsl.setRange(900, 1000)
                dv = self.config.get(f'c{li}_decay', 0.995)
                dsl.setValue(int(dv * 1000))
                dlb = QLabel(f"{dv:.3f}"); dlb.setFixedWidth(42)
                dsl.valueChanged.connect(lambda v, k=f'c{li}_decay', l=dlb: (l.setText(f"{v/1000:.3f}"), self._update_cfg(k, v / 1000)))
                setattr(self, f'c{li}_decay_slider', dsl)
                gl.addWidget(dsl, rl, 1, 1, 2); gl.addWidget(dlb, rl, 3); rl += 1

            gl.addWidget(QLabel("转速:"), rl, 0)
            rsl = QSlider(Qt.Horizontal); rsl.setRange(-500, 500)
            rv = self.config.get(f'c{li}_rot_speed', 1.0)
            rsl.setValue(int(rv * 100))
            rlb = QLabel(f"{rv:.2f}"); rlb.setFixedWidth(42)
            rsl.valueChanged.connect(lambda v, k=f'c{li}_rot_speed', l=rlb: (l.setText(f"{v/100:.2f}"), self._update_cfg(k, v / 100)))
            setattr(self, f'c{li}_rot_speed_slider', rsl)
            gl.addWidget(rsl, rl, 1, 1, 2); gl.addWidget(rlb, rl, 3); rl += 1

            gl.addWidget(QLabel("pow:"), rl, 0)
            psl = QSlider(Qt.Horizontal); psl.setRange(-300, 300)
            pv = self.config.get(f'c{li}_rot_pow', 0.5)
            psl.setValue(int(pv * 100))
            plb = QLabel(f"{pv:.2f}"); plb.setFixedWidth(42)
            psl.valueChanged.connect(lambda v, k=f'c{li}_rot_pow', l=plb: (l.setText(f"{v/100:.2f}"), self._update_cfg(k, v / 100)))
            setattr(self, f'c{li}_rot_pow_slider', psl)
            gl.addWidget(psl, rl, 1, 1, 2); gl.addWidget(plb, rl, 3); rl += 1

            sec.add_layout(gl)
            s.add_widget(sec)
        vlay.addWidget(s)

    # ── 四层条形 ──────────────────────────────────────────

    def _build_bars_section(self, vlay):
        s = _Collapsible("四层条形 (B12~B45)", expanded=False)
        for key, bname in [('b12', 'C1-C2 间'), ('b23', 'C2-C3 间'),
                           ('b34', 'C3-C4 间'), ('b45', 'C4-C5 间')]:
            sec = _Collapsible(f"{bname}", expanded=False)
            gl = QGridLayout(); gl.setSpacing(3); gl.setContentsMargins(0,0,0,0); rl = 0

            chk = QCheckBox("显示")
            chk.setChecked(self.config.get(f'{key}_on', False))
            chk.toggled.connect(lambda v, k=f'{key}_on': self._update_cfg(k, v))
            setattr(self, f'{key}_on_check', chk)
            gl.addWidget(chk, rl, 0)
            sp = QSpinBox(); sp.setRange(1, 20)
            sp.setValue(self.config.get(f'{key}_thick', 3))
            sp.valueChanged.connect(lambda v, k=f'{key}_thick': self._update_cfg(k, v))
            setattr(self, f'{key}_thick_spin', sp)
            ht = QHBoxLayout()
            ht.addWidget(QLabel("粗:")); ht.addWidget(sp)
            gl.addLayout(ht, rl, 1, 1, 2); rl += 1

            # 固定长度
            fchk = QCheckBox("固定长度")
            fchk.setChecked(self.config.get(f'{key}_fixed', False))
            setattr(self, f'{key}_fixed_check', fchk)
            gl.addWidget(fchk, rl, 0)
            fsp = QSpinBox(); fsp.setRange(1, 500)
            fsp.setValue(self.config.get(f'{key}_fixed_len', 30))
            fsp.valueChanged.connect(lambda v, k=f'{key}_fixed_len': self._update_cfg(k, v))
            setattr(self, f'{key}_fixed_len_spin', fsp)
            fh = QHBoxLayout()
            fh.addWidget(fsp); fh.addWidget(QLabel("px"))
            gl.addLayout(fh, rl, 1, 1, 2); rl += 1

            # 三模式复选框（仅固定长度启用时可用）
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
            gl.addWidget(mode_w, rl, 0, 1, 3); rl += 1

            fchk.toggled.connect(lambda v, k=key, w=mode_w: (self._update_cfg(f'{k}_fixed', v), w.setVisible(v)))

            sec.add_layout(gl)
            s.add_widget(sec)
        vlay.addWidget(s)

    # ── A1 响度监测 ──────────────────────────────────────────

    def _build_a1_section(self, vlay):
        s = _Collapsible("A1 响度监测", expanded=False)
        g = QVBoxLayout()

        vrow = QHBoxLayout()
        vrow.addWidget(QLabel("当前 A1:"))
        self.a1_lbl = QLabel("0.00")
        self.a1_lbl.setStyleSheet(
            "QLabel{font-size:18px;font-weight:bold;color:#0080ff;"
            "padding:6px;background:#f0f0f0;border-radius:4px;}")
        vrow.addWidget(self.a1_lbl); vrow.addStretch()
        g.addLayout(vrow)

        trow = QHBoxLayout()
        trow.addWidget(QLabel("窗口:"))
        self.a1_spin = QDoubleSpinBox()
        self.a1_spin.setRange(0.01, 60.0); self.a1_spin.setSingleStep(0.1); self.a1_spin.setDecimals(2)
        self.a1_spin.setValue(self.config['a1_time_window']); self.a1_spin.setSuffix(" 秒")
        self.a1_spin.valueChanged.connect(lambda v: self._update_cfg('a1_time_window', v))
        trow.addWidget(self.a1_spin); trow.addStretch()
        g.addLayout(trow)

        s.add_layout(g)
        vlay.addWidget(s)

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

    def _toggle(self):
        if self.viz_process and self.viz_process.is_alive():
            self._stop_visualizer()
        else:
            self._start_visualizer()

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

            self.toggle_btn.setText("⏹️ 停止可视化")
            self._set_btn_stop_style()
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
        self.toggle_btn.setText("🚀 启动可视化")
        self._set_btn_start_style()

    def _set_btn_start_style(self):
        self.toggle_btn.setStyleSheet("""
            QPushButton { font-size:14pt; font-weight:bold; background-color:#4CAF50; color:white; border-radius:5px; }
            QPushButton:hover { background-color:#45a049; }
        """)

    def _set_btn_stop_style(self):
        self.toggle_btn.setStyleSheet("""
            QPushButton { font-size:14pt; font-weight:bold; background-color:#f44336; color:white; border-radius:5px; }
            QPushButton:hover { background-color:#da190b; }
        """)

    def _center_window(self):
        if not self.viz_process or not self.viz_process.is_alive():
            return
        if self.config_queue and not self.config_queue.full():
            try:
                self.config_queue.put({'command': 'center_window'})
            except:
                pass

    def _reset_all(self):
        if QMessageBox.question(self, "确认", "确定要将所有参数复位到默认值吗？",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return

        self.config = _get_defaults()
        d = self.config

        # 基础 UI
        self.width_spin.setValue(0); self.height_spin.setValue(0)
        self.bars_spin.setValue(64); self.smooth_slider.setValue(70)
        self.alpha_slider.setValue(255); self.ui_alpha_slider.setValue(180)
        self.color_combo.setCurrentIndex(0)
        self.damp_slider.setValue(85); self.spring_slider.setValue(30); self.grav_slider.setValue(50)
        self.hmin_spin.setValue(0); self.hmax_spin.setValue(500)
        self.master_visible_check.setChecked(True)
        self.radius_spin.setValue(150); self.seg_spin.setValue(1)
        self.a1rot_check.setChecked(True); self.a1rad_check.setChecked(True)
        self.rdamp_slider.setValue(92); self.rspring_slider.setValue(15); self.rgrav_slider.setValue(30)
        self.freq_min_spin.setValue(20); self.freq_max_spin.setValue(20000)
        self.bar_len_min_spin.setValue(0); self.bar_len_max_spin.setValue(300)
        self.a1_spin.setValue(10.0)
        self.trans_check.setChecked(True); self.top_check.setChecked(True)

        # 五层轮廓
        for li in range(1, 6):
            getattr(self, f'c{li}_on_check').setChecked(d.get(f'c{li}_on', False))
            cc = d.get(f'c{li}_color', (255,255,255))
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

        if self.viz_process and self.viz_process.is_alive():
            self._send_config()

    def _update_status(self):
        if not self.status_queue:
            return
        try:
            while not self.status_queue.empty():
                st = self.status_queue.get_nowait()
                if 'a1' in st:
                    self.current_a1 = st['a1']
                    self.a1_lbl.setText(f"{self.current_a1:.2f}")
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
    app.setStyleSheet("""
        QCheckBox::indicator { width: 15px; height: 15px; border-radius: 2px; }
        QCheckBox::indicator:unchecked {
            background-color: #e8e8e8;
            border: 1px solid #aaa;
        }
        QCheckBox::indicator:checked {
            background-color: #2d2d2d;
            border: 1px solid #555;
        }
    """)
    w = VisualizerControlUI()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
