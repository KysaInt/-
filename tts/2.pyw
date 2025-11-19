"""
字幕停顿匹配工具
用途: 检测语音文件的停顿间隙，自动调整字幕时间以匹配语音节奏
"""

import sys
import os
import json
import threading
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple, Optional

import numpy as np
from scipy import signal as scipy_signal
from scipy.io import wavfile

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit,
    QLabel, QLineEdit, QFileDialog, QSpinBox, QDoubleSpinBox, QCheckBox,
    QComboBox, QFrame, QScrollArea, QProgressBar, QMessageBox, QGridLayout,
    QSizePolicy
)
from PySide6.QtCore import QThread, Signal, Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QPalette, QFontDatabase, QIcon


# ============================================================================
# 工具函数与数据结构
# ============================================================================

@dataclass
class Silence:
    """静音段信息"""
    start: float  # 秒
    end: float    # 秒
    duration: float

    @property
    def center(self) -> float:
        return (self.start + self.end) / 2


class SRTSubtitle:
    """SRT 字幕条目"""
    def __init__(self, index: int, start: float, end: float, text: str):
        self.index = index
        self.start = start  # 秒
        self.end = end      # 秒
        self.text = text

    def shift(self, delta: float):
        """整体时移"""
        self.start += delta
        self.end += delta

    def to_srt_time(self, seconds: float) -> str:
        """转换为 SRT 时间格式 HH:MM:SS,mmm"""
        total_ms = int(seconds * 1000)
        h = total_ms // 3600000
        m = (total_ms % 3600000) // 60000
        s = (total_ms % 60000) // 1000
        ms = total_ms % 1000
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def to_srt_line(self) -> str:
        """生成 SRT 格式的一行"""
        return f"{self.index}\n{self.to_srt_time(self.start)} --> {self.to_srt_time(self.end)}\n{self.text}\n\n"


# ============================================================================
# 音频分析模块
# ============================================================================

class AudioAnalyzer:
    """音频分析引擎"""

    def __init__(self, audio_path: str, threshold_db: float = -40, min_silence_duration: float = 0.01):
        """
        Args:
            audio_path: 音频文件路径
            threshold_db: 音量阈值（dB），低于此值视为静音
            min_silence_duration: 最小静音时长（秒）
        """
        self.audio_path = audio_path
        self.threshold_db = threshold_db
        self.min_silence_duration = min_silence_duration
        self.silences: List[Silence] = []
        self.sr = None
        self.duration = 0.0

    def analyze(self) -> List[Silence]:
        """分析音频，返回静音段列表"""
        try:
            # 读取音频
            sr, audio_data = wavfile.read(self.audio_path)
            self.sr = sr

            # 转换为单声道
            if len(audio_data.shape) > 1:
                audio_data = np.mean(audio_data, axis=1)

            # 归一化到 [-1, 1]
            if audio_data.dtype != np.float32 and audio_data.dtype != np.float64:
                audio_data = audio_data.astype(np.float32) / np.iinfo(audio_data.dtype).max

            self.duration = len(audio_data) / sr

            # 计算瞬时能量
            frame_length = int(sr * 0.01)  # 10ms 帧
            hop_length = frame_length // 2
            energy = self._compute_energy(audio_data, frame_length, hop_length)

            # 转换为 dB
            energy_db = 20 * np.log10(energy + 1e-10)

            # 检测静音帧
            silent_mask = energy_db < self.threshold_db

            # 连接相邻静音帧
            self.silences = self._merge_silences(silent_mask, hop_length, sr)

            return self.silences

        except Exception as e:
            raise RuntimeError(f"音频分析失败: {str(e)}")

    @staticmethod
    def _compute_energy(audio: np.ndarray, frame_length: int, hop_length: int) -> np.ndarray:
        """计算每帧的能量"""
        n_frames = 1 + (len(audio) - frame_length) // hop_length
        energy = np.zeros(n_frames)

        for i in range(n_frames):
            start = i * hop_length
            end = start + frame_length
            frame = audio[start:end]
            energy[i] = np.sqrt(np.mean(frame ** 2))

        return energy

    def _merge_silences(self, silent_mask: np.ndarray, hop_length: int, sr: int) -> List[Silence]:
        """合并相邻的静音帧"""
        silences = []
        in_silence = False
        silence_start = 0

        for i, is_silent in enumerate(silent_mask):
            time = i * hop_length / sr

            if is_silent and not in_silence:
                silence_start = time
                in_silence = True
            elif not is_silent and in_silence:
                silence_end = time
                duration = silence_end - silence_start

                # 只保留足够长的静音段
                if duration >= self.min_silence_duration:
                    silences.append(Silence(silence_start, silence_end, duration))

                in_silence = False

        # 处理最后一个静音段
        if in_silence:
            silence_end = len(silent_mask) * hop_length / sr
            duration = silence_end - silence_start
            if duration >= self.min_silence_duration:
                silences.append(Silence(silence_start, silence_end, duration))

        return silences


# ============================================================================
# SRT 处理模块
# ============================================================================

class SRTParser:
    """SRT 字幕解析与处理"""

    @staticmethod
    def parse_srt_time(time_str: str) -> float:
        """解析 SRT 时间格式 HH:MM:SS,mmm 为秒"""
        parts = time_str.replace(',', '.').split(':')
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds

    @staticmethod
    def load(filepath: str) -> List[SRTSubtitle]:
        """加载 SRT 文件"""
        subtitles = []
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read().strip()

        blocks = content.split('\n\n')
        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) < 3:
                continue

            try:
                index = int(lines[0])
                time_range = lines[1].split(' --> ')
                start = SRTParser.parse_srt_time(time_range[0].strip())
                end = SRTParser.parse_srt_time(time_range[1].strip())
                text = '\n'.join(lines[2:])

                subtitles.append(SRTSubtitle(index, start, end, text))
            except Exception:
                continue

        return subtitles

    @staticmethod
    def save(filepath: str, subtitles: List[SRTSubtitle]):
        """保存 SRT 文件"""
        lines = []
        for i, sub in enumerate(subtitles, 1):
            sub.index = i
            lines.append(sub.to_srt_line())
        
        with open(filepath, 'w', encoding='utf-8') as f:
            # 将所有行连接，然后移除最后一个多余的空行
            content = ''.join(lines).rstrip() + '\n'
            f.write(content)


# ============================================================================
# 匹配算法模块
# ============================================================================

class SubtitleMatcher:
    """字幕与停顿匹配引擎"""

    @staticmethod
    def match_subtitles(subtitles: List[SRTSubtitle], silences: List[Silence]) -> Tuple[List[SRTSubtitle], str]:
        """
        根据停顿间隙的出入点调整字幕时间
        
        规则:
        字幕数: n, 间隙数: m
        
        标准情况 (m = n+1): 首尾都有间隙
        - 间隙[i]的出点(end) = 字幕[i]的入点(start)
        - 间隙[i+1]的入点(start) = 字幕[i]的出点(end)
        
        单端情况 (m = n): 首或尾只有一端有间隙
        - 需要根据语音时长和间隙时长判断
        - 然后做出相应的匹配
        
        无端情况 (m = n-1): 首尾都没有间隙
        - 第一段字幕的入点和最后一段字幕的出点不需要修改

        Args:
            subtitles: 原始字幕列表
            silences: 检测到的停顿列表

        Returns:
            (调整后的字幕列表, 详细日志字符串)
        """
        log_lines = []
        
        if not subtitles or not silences:
            log_lines.append("⚠ 字幕或停顿列表为空，无法匹配")
            return subtitles, "\n".join(log_lines)

        n = len(subtitles)
        m = len(silences)
        
        log_lines.append(f"{'=' * 70}")
        log_lines.append(f"字幕匹配分析")
        log_lines.append(f"{'=' * 70}")
        log_lines.append(f"字幕数量 (n): {n}")
        log_lines.append(f"间隙数量 (m): {m}")
        log_lines.append(f"关系: m - n = {m - n}")
        log_lines.append("")
        
        # 确定情况类型并匹配
        if m == n + 1:
            case_type = "标准情况: m = n + 1 (首尾都有间隙)"
            log_lines.append(f"✓ {case_type}")
            log_lines.append("  规则: 间隙出点→字幕入点, 间隙入点→字幕出点")
            adjusted = SubtitleMatcher._match_standard(subtitles, silences, log_lines)
        
        elif m == n:
            case_type = "单端情况: m = n (首或尾只有一端有间隙)"
            log_lines.append(f"✓ {case_type}")
            log_lines.append("  判断逻辑: 根据语音和间隙时长判断首部或尾部")
            adjusted = SubtitleMatcher._match_single_end(subtitles, silences, log_lines)
        
        elif m == n - 1:
            case_type = "无端情况: m = n - 1 (首尾都没有间隙)"
            log_lines.append(f"✓ {case_type}")
            log_lines.append("  规则: 首尾字幕入出点不修改，中间字幕映射到间隙")
            adjusted = SubtitleMatcher._match_no_ends(subtitles, silences, log_lines)
        
        else:
            log_lines.append(f"⚠ 特殊情况: m={m}, n={n}, 关系不符合预期")
            log_lines.append("  使用通用比例分配方法")
            adjusted = SubtitleMatcher._match_fallback(subtitles, silences, log_lines)
        
        log_lines.append("")
        log_lines.append(f"{'=' * 70}")
        log_lines.append("调整后的字幕详情:")
        log_lines.append(f"{'=' * 70}")
        for i, sub in enumerate(adjusted, 1):
            log_lines.append(f"{i}. [{sub.index}] {sub.to_srt_time(sub.start)} --> {sub.to_srt_time(sub.end)}")
            log_lines.append(f"   时长: {sub.end - sub.start:.3f}s | 文本: {sub.text[:60]}")
        
        return adjusted, "\n".join(log_lines)

    @staticmethod
    def _match_standard(subtitles: List[SRTSubtitle], silences: List[Silence], log_lines: list) -> List[SRTSubtitle]:
        """
        标准情况: m = n + 1 (首尾都有间隙)
        
        规则:
        - 间隙[i]的出点(end) = 字幕[i]的入点(start)
        - 间隙[i+1]的入点(start) = 字幕[i]的出点(end)
        """
        log_lines.append("")
        log_lines.append(f"{'─' * 70}")
        log_lines.append("标准情况处理:")
        log_lines.append(f"{'─' * 70}")
        
        adjusted = []
        
        for i, sub in enumerate(subtitles):
            # 字幕[i]应该在间隙[i]和间隙[i+1]之间
            gap_out = silences[i]      # 这个间隙的出点 = 字幕入点
            gap_in = silences[i + 1]   # 下一个间隙的入点 = 字幕出点
            
            new_start = gap_out.end
            new_end = gap_in.start
            
            log_lines.append(f"字幕 {i+1}:")
            log_lines.append(f"  原始: {sub.to_srt_time(sub.start)} --> {sub.to_srt_time(sub.end)}")
            log_lines.append(f"  映射: 间隙[{i}].end={SubtitleMatcher._format_time(gap_out.end)}")
            log_lines.append(f"        间隙[{i+1}].start={SubtitleMatcher._format_time(gap_in.start)}")
            log_lines.append(f"  调整: {SubtitleMatcher._format_time(new_start)} --> {SubtitleMatcher._format_time(new_end)}")
            log_lines.append(f"  时长: {new_end - new_start:.3f}s")
            
            new_sub = SRTSubtitle(sub.index, new_start, new_end, sub.text)
            adjusted.append(new_sub)
        
        return adjusted

    @staticmethod
    def _match_single_end(subtitles: List[SRTSubtitle], silences: List[Silence], log_lines: list) -> List[SRTSubtitle]:
        """
        单端情况: m = n (首或尾只有一端有间隙)
        
        判断逻辑:
        - 计算总间隙时长 vs 语音中间隙以外的部分
        - 如果第一个间隙很靠后，说明头部无间隙
        - 如果最后一个间隙很靠前，说明尾部无间隙
        """
        log_lines.append("")
        log_lines.append(f"{'─' * 70}")
        log_lines.append("单端情况处理:")
        log_lines.append(f"{'─' * 70}")
        
        # 分析间隙分布
        if len(silences) > 0:
            first_silence_start = silences[0].start
            last_silence_end = silences[-1].end
            
            # 启发式判断: 如果第一个间隙距离开头较远，说明前面有内容（头部无间隙）
            # 如果最后一个间隙不是很靠后，说明后面有内容（尾部无间隙）
            has_head_gap = first_silence_start < 2.0  # 假设2秒内有第一个间隙
            has_tail_gap = last_silence_end > 5.0  # 假设靠后有最后一个间隙（简化）
        else:
            has_head_gap = False
            has_tail_gap = False
        
        log_lines.append(f"第一个间隙开始时间: {silences[0].start:.3f}s")
        log_lines.append(f"最后一个间隙结束时间: {silences[-1].end:.3f}s")
        log_lines.append(f"判定: 头部{'有' if has_head_gap else '无'}间隙, 尾部{'有' if has_tail_gap else '无'}间隙")
        log_lines.append("")
        
        adjusted = []
        
        if has_head_gap and not has_tail_gap:
            # 头部有间隙，尾部无间隙
            log_lines.append("策略: 头部有间隙，尾部无间隙")
            for i in range(len(subtitles) - 1):
                # 前n-1个字幕
                new_start = silences[i].end
                new_end = silences[i + 1].start
                new_sub = SRTSubtitle(subtitles[i].index, new_start, new_end, subtitles[i].text)
                adjusted.append(new_sub)
                log_lines.append(f"字幕 {i+1}: {SubtitleMatcher._format_time(new_start)} --> {SubtitleMatcher._format_time(new_end)}")
            
            # 最后一个字幕保持原始长度，从最后间隙末尾开始
            last_sub = subtitles[-1]
            last_start = silences[-1].end
            last_end = last_start + (last_sub.end - last_sub.start)
            new_sub = SRTSubtitle(last_sub.index, last_start, last_end, last_sub.text)
            adjusted.append(new_sub)
            log_lines.append(f"字幕 {len(subtitles)}: {SubtitleMatcher._format_time(last_start)} --> {SubtitleMatcher._format_time(last_end)} (尾部无间隙)")
        
        else:  # 默认: 尾部有间隙，头部无间隙
            # 头部无间隙，尾部有间隙
            log_lines.append("策略: 头部无间隙，尾部有间隙")
            
            # 第一个字幕保持原始长度，到第一个间隙开始
            first_sub = subtitles[0]
            first_end = silences[0].start
            first_start = first_end - (first_sub.end - first_sub.start)
            new_sub = SRTSubtitle(first_sub.index, first_start, first_end, first_sub.text)
            adjusted.append(new_sub)
            log_lines.append(f"字幕 1: {SubtitleMatcher._format_time(first_start)} --> {SubtitleMatcher._format_time(first_end)} (头部无间隙)")
            
            # 后续字幕
            for i in range(1, len(subtitles)):
                new_start = silences[i - 1].end
                new_end = silences[i].start
                new_sub = SRTSubtitle(subtitles[i].index, new_start, new_end, subtitles[i].text)
                adjusted.append(new_sub)
                log_lines.append(f"字幕 {i+1}: {SubtitleMatcher._format_time(new_start)} --> {SubtitleMatcher._format_time(new_end)}")
        
        return adjusted

    @staticmethod
    def _match_no_ends(subtitles: List[SRTSubtitle], silences: List[Silence], log_lines: list) -> List[SRTSubtitle]:
        """
        无端情况: m = n - 1 (首尾都没有间隙)
        
        规则:
        - 第一段字幕的入点(start)不修改
        - 最后一段字幕的出点(end)不修改
        - 中间n-1段字幕映射到m个间隙
        """
        log_lines.append("")
        log_lines.append(f"{'─' * 70}")
        log_lines.append("无端情况处理:")
        log_lines.append(f"{'─' * 70}")
        
        adjusted = []
        
        # 第一个字幕保持原始入点
        first_sub = subtitles[0]
        if len(silences) > 0:
            first_end = silences[0].start
        else:
            first_end = first_sub.end
        
        new_sub = SRTSubtitle(first_sub.index, first_sub.start, first_end, first_sub.text)
        adjusted.append(new_sub)
        log_lines.append(f"字幕 1: {SubtitleMatcher._format_time(first_sub.start)} --> {SubtitleMatcher._format_time(first_end)} (首部无间隙，入点不修改)")
        
        # 中间字幕
        for i in range(1, len(subtitles) - 1):
            gap_idx = i - 1
            new_start = silences[gap_idx].end
            new_end = silences[gap_idx + 1].start if gap_idx + 1 < len(silences) else subtitles[-1].start
            
            new_sub = SRTSubtitle(subtitles[i].index, new_start, new_end, subtitles[i].text)
            adjusted.append(new_sub)
            log_lines.append(f"字幕 {i+1}: {SubtitleMatcher._format_time(new_start)} --> {SubtitleMatcher._format_time(new_end)}")
        
        # 最后一个字幕保持原始出点
        last_sub = subtitles[-1]
        if len(silences) > 0:
            last_start = silences[-1].end
        else:
            last_start = last_sub.start
        
        new_sub = SRTSubtitle(last_sub.index, last_start, last_sub.end, last_sub.text)
        adjusted.append(new_sub)
        log_lines.append(f"字幕 {len(subtitles)}: {SubtitleMatcher._format_time(last_start)} --> {SubtitleMatcher._format_time(last_sub.end)} (尾部无间隙，出点不修改)")
        
        return adjusted

    @staticmethod
    def _match_fallback(subtitles: List[SRTSubtitle], silences: List[Silence], log_lines: list) -> List[SRTSubtitle]:
        """
        Fallback: 其他特殊情况，按比例分配
        """
        log_lines.append("")
        log_lines.append(f"{'─' * 70}")
        log_lines.append("Fallback 处理 (比例分配):")
        log_lines.append(f"{'─' * 70}")
        
        n = len(subtitles)
        m = len(silences)
        
        if m > n:
            # 间隙多于字幕: 选择均匀分布的间隙子集
            log_lines.append(f"间隙过多({m} > {n})，选择均匀分布的 {n} 个间隙")
            step = m / n
            adjusted = []
            for i, sub in enumerate(subtitles):
                idx = int(i * step)
                idx = min(idx, len(silences) - 1)
                gap = silences[idx]
                new_start = gap.start
                new_end = gap.end
                new_sub = SRTSubtitle(sub.index, new_start, new_end, sub.text)
                adjusted.append(new_sub)
                log_lines.append(f"字幕 {i+1}: {SubtitleMatcher._format_time(new_start)} --> {SubtitleMatcher._format_time(new_end)} (使用间隙 {idx})")
        else:
            # 字幕多于间隙: 尽量分配
            log_lines.append(f"字幕过多({n} > {m})，按分布分配")
            step = n / m
            adjusted = []
            for i, sub in enumerate(subtitles):
                gap_idx = int(i / step)
                gap_idx = min(gap_idx, len(silences) - 1)
                gap = silences[gap_idx]
                
                # 在这个间隙内的位置
                new_start = gap.start + (i % step) / step * (gap.end - gap.start)
                new_end = new_start + (sub.end - sub.start)
                
                new_sub = SRTSubtitle(sub.index, new_start, new_end, sub.text)
                adjusted.append(new_sub)
                log_lines.append(f"字幕 {i+1}: {SubtitleMatcher._format_time(new_start)} --> {SubtitleMatcher._format_time(new_end)}")
        
        return adjusted

    @staticmethod
    def _format_time(seconds: float) -> str:
        """格式化时间为字符串"""
        total_ms = int(seconds * 1000)
        h = total_ms // 3600000
        m = (total_ms % 3600000) // 60000
        s = (total_ms % 60000) // 1000
        ms = total_ms % 1000
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# ============================================================================
# 可折叠面板组件
# ============================================================================

class CollapsibleBox(QWidget):
    """可折叠的设置面板"""

    def __init__(self, title: str = "", parent=None, duration: int = 250):
        super().__init__(parent)
        self._title = title

        # 保证折叠时不占据多余空间，配合下方弹簧可贴顶
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        # 标题按钮
        self.toggle_button = QPushButton()
        f = self.toggle_button.font()
        f.setBold(True)
        self.toggle_button.setFont(f)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(False)
        self.toggle_button.setMaximumHeight(32)
        self.toggle_button.setCursor(Qt.PointingHandCursor)

        # 内容区
        self.content_area = QFrame()
        self.content_area.setFrameShape(QFrame.StyledPanel)
        self.content_area.setMaximumHeight(0)
        self.content_area.setMinimumHeight(0)

        # 动画
        self.anim = QPropertyAnimation(self.content_area, b"maximumHeight")
        self.anim.setDuration(duration)
        self.anim.setEasingCurve(QEasingCurve.InOutCubic)

        # 布局
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        lay.addWidget(self.toggle_button)
        lay.addWidget(self.content_area)

        self.toggle_button.clicked.connect(self._on_toggled)
        self._update_arrow(False)

    def setContentLayout(self, layout):
        """设置内容布局"""
        old = self.content_area.layout()
        if old:
            while old.count():
                it = old.takeAt(0)
                w = it.widget()
                if w:
                    w.setParent(None)

        self.content_area.setLayout(layout)

    def _on_toggled(self, checked):
        """处理展开/收起"""
        self._update_arrow(checked)
        layout = self.content_area.layout()
        h = layout.sizeHint().height() if layout else 0

        self.anim.stop()
        self.anim.setStartValue(self.content_area.maximumHeight())
        self.anim.setEndValue(h if checked else 0)
        self.anim.start()

    def _update_arrow(self, expanded):
        """更新箭头"""
        arrow = "▼" if expanded else "►"
        self.toggle_button.setText(f"{arrow} {self._title}")


# ============================================================================
# 后台工作线程
# ============================================================================

class AnalysisWorker(QThread):
    """后台分析线程"""
    progress = Signal(str)
    finished = Signal(list)  # 返回 silences 列表
    error = Signal(str)

    def __init__(self, audio_path: str, threshold_db: float, min_silence: float):
        super().__init__()
        self.audio_path = audio_path
        self.threshold_db = threshold_db
        self.min_silence = min_silence

    def run(self):
        try:
            self.progress.emit("正在分析音频文件...")
            analyzer = AudioAnalyzer(self.audio_path, self.threshold_db, self.min_silence)
            silences = analyzer.analyze()
            self.progress.emit(f"分析完成！检测到 {len(silences)} 个停顿")
            self.finished.emit(silences)
        except Exception as e:
            self.error.emit(str(e))


class MatchingWorker(QThread):
    """后台匹配线程"""
    progress = Signal(str)
    finished = Signal(list, str)  # 返回(调整后的字幕列表, 详细日志)
    error = Signal(str)

    def __init__(self, srt_path: str, silences: List[Silence]):
        super().__init__()
        self.srt_path = srt_path
        self.silences = silences

    def run(self):
        try:
            self.progress.emit("正在加载字幕...")
            subtitles = SRTParser.load(self.srt_path)
            self.progress.emit(f"正在匹配 {len(subtitles)} 条字幕与 {len(self.silences)} 个停顿...")
            adjusted, log = SubtitleMatcher.match_subtitles(subtitles, self.silences)
            self.progress.emit("匹配完成！")
            self.finished.emit(adjusted, log)
        except Exception as e:
            self.error.emit(str(e))


# ============================================================================
# 主界面
# ============================================================================

class SubtitlePauseMatcherUI(QWidget):
    """字幕停顿匹配工具 UI"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("字幕停顿匹配工具")
        self.setGeometry(100, 100, 900, 700)

        # 当前状态
        self.audio_path = None
        self.srt_path = None
        self.current_silences: List[Silence] = []
        self.current_subtitles: List[SRTSubtitle] = []

        # 工作线程
        self.analysis_worker = None
        self.matching_worker = None

        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        """初始化 UI"""
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(4)

        # ====== 状态行 ======
        status_layout = QHBoxLayout()
        status_layout.setContentsMargins(0, 0, 0, 0)

        self.status_label = QLabel("就绪")
        status_layout.addWidget(self.status_label, 1)

        self.open_output_btn = QPushButton("📂 打开输出")
        self.open_output_btn.setMaximumWidth(100)
        self.open_output_btn.clicked.connect(self._open_output)
        status_layout.addWidget(self.open_output_btn)

        root_layout.addLayout(status_layout)

        # ====== 文件选择区 ======
        file_layout = QGridLayout()
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.setSpacing(4)

        file_layout.addWidget(QLabel("语音文件:"), 0, 0)
        self.audio_path_edit = QLineEdit()
        self.audio_path_edit.setReadOnly(True)
        file_layout.addWidget(self.audio_path_edit, 0, 1)
        audio_btn = QPushButton("选择")
        audio_btn.setMaximumWidth(80)
        audio_btn.clicked.connect(self._select_audio)
        file_layout.addWidget(audio_btn, 0, 2)

        file_layout.addWidget(QLabel("字幕文件:"), 1, 0)
        self.srt_path_edit = QLineEdit()
        self.srt_path_edit.setReadOnly(True)
        file_layout.addWidget(self.srt_path_edit, 1, 1)
        srt_btn = QPushButton("选择")
        srt_btn.setMaximumWidth(80)
        srt_btn.clicked.connect(self._select_srt)
        file_layout.addWidget(srt_btn, 1, 2)

        root_layout.addLayout(file_layout)

        # ====== 设置面板 ======
        settings_box = CollapsibleBox("⚙️ 音频分析设置", duration=250)
        settings_layout = QGridLayout()
        settings_layout.setSpacing(6)

        settings_layout.addWidget(QLabel("音量阈值 (dB):"), 0, 0)
        self.threshold_spin = QSpinBox()
        self.threshold_spin.setRange(-80, 0)
        self.threshold_spin.setValue(-40)
        settings_layout.addWidget(self.threshold_spin, 0, 1)

        settings_layout.addWidget(QLabel("最小停顿时长 (秒):"), 1, 0)
        self.min_silence_spin = QDoubleSpinBox()
        self.min_silence_spin.setRange(0.01, 10.0)
        self.min_silence_spin.setSingleStep(0.01)
        self.min_silence_spin.setValue(0.01)
        settings_layout.addWidget(self.min_silence_spin, 1, 1)

        settings_box.setContentLayout(settings_layout)
        root_layout.addWidget(settings_box)

        # ====== 操作按钮行 ======
        action_layout = QHBoxLayout()
        action_layout.setSpacing(6)

        self.analyze_btn = QPushButton("🔍 分析音频")
        self.analyze_btn.clicked.connect(self._analyze_audio)
        action_layout.addWidget(self.analyze_btn)

        self.match_btn = QPushButton("🔗 匹配字幕")
        self.match_btn.setEnabled(False)
        self.match_btn.clicked.connect(self._match_subtitles)
        action_layout.addWidget(self.match_btn)

        self.export_btn = QPushButton("💾 导出字幕")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._export_subtitles)
        action_layout.addWidget(self.export_btn)

        self.reset_btn = QPushButton("🔄 重置")
        self.reset_btn.clicked.connect(self._reset)
        action_layout.addWidget(self.reset_btn)

        # 自动执行后无需手动点击，按钮默认隐藏（保留逻辑备用）
        self.analyze_btn.setVisible(False)
        self.match_btn.setVisible(False)
        root_layout.addLayout(action_layout)

        # ====== 进度条 ======
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(0)  # 不确定模式
        self.progress_bar.setVisible(False)
        root_layout.addWidget(self.progress_bar)

        # ====== 合并后的“分析结果(含日志)” 折叠面板 ======
        info_box = CollapsibleBox("📊 分析结果", duration=250)
        info_layout = QGridLayout()
        info_layout.setSpacing(6)

        info_layout.addWidget(QLabel("检测到的停顿数:"), 0, 0)
        self.silence_count_label = QLabel("0")
        info_layout.addWidget(self.silence_count_label, 0, 1)

        info_layout.addWidget(QLabel("总停顿时长:"), 1, 0)
        self.total_silence_label = QLabel("0.0s")
        info_layout.addWidget(self.total_silence_label, 1, 1)

        info_layout.addWidget(QLabel("字幕条数:"), 2, 0)
        self.subtitle_count_label = QLabel("0")
        info_layout.addWidget(self.subtitle_count_label, 2, 1)

        info_layout.addWidget(QLabel("原始时长:"), 3, 0)
        self.original_duration_label = QLabel("0.0s")
        info_layout.addWidget(self.original_duration_label, 3, 1)

        # 日志区（移入分析结果面板内）
        log_label = QLabel("📋 处理日志")
        f = log_label.font(); f.setBold(True); log_label.setFont(f)
        info_layout.addWidget(log_label, 4, 0, 1, 2)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        # 允许更灵活的高度
        self.log_text.setMinimumHeight(180)
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        self.log_text.setFont(font)
        info_layout.addWidget(self.log_text, 5, 0, 1, 2)

        info_box.setContentLayout(info_layout)
        # 默认展开分析结果面板，展开向下延展
        info_box.toggle_button.setChecked(True)
        info_box._on_toggled(True)
        root_layout.addWidget(info_box)

        # 底部伸缩
        root_layout.addStretch()

    def _connect_signals(self):
        """连接信号"""
        pass

    def _select_audio(self):
        """选择音频文件"""
        # 默认目录 ../AE
        base_dir = os.path.dirname(os.path.abspath(__file__))
        default_dir = os.path.normpath(os.path.join(base_dir, "..", "AE"))
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择音频文件",
            default_dir if os.path.isdir(default_dir) else "",
            "音频文件 (*.wav *.mp3 *.flac);;所有文件 (*)"
        )
        if path:
            self.audio_path = path
            self.audio_path_edit.setText(Path(path).name)
            self._log(f"✓ 已选择音频: {Path(path).name}")
            # 自动开始分析
            # 若分析线程正在运行则跳过
            if not (self.analysis_worker and self.analysis_worker.isRunning()):
                self._analyze_audio()

    def _select_srt(self):
        """选择字幕文件"""
        # 默认目录 ./output
        base_dir = os.path.dirname(os.path.abspath(__file__))
        default_dir = os.path.normpath(os.path.join(base_dir, "output"))
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择字幕文件",
            default_dir if os.path.isdir(default_dir) else "",
            "SRT 字幕 (*.srt);;所有文件 (*)"
        )
        if path:
            self.srt_path = path
            self.srt_path_edit.setText(Path(path).name)
            self._log(f"✓ 已选择字幕: {Path(path).name}")
            # 若已有分析结果则自动匹配；否则等待分析完成后自动匹配
            if self.current_silences:
                if not (self.matching_worker and self.matching_worker.isRunning()):
                    self._match_subtitles()

    def _analyze_audio(self):
        """分析音频"""
        if not self.audio_path:
            QMessageBox.warning(self, "警告", "请先选择音频文件")
            return

        self._log("正在分析音频...")
        self.progress_bar.setVisible(True)
        self.analyze_btn.setEnabled(False)

        self.analysis_worker = AnalysisWorker(
            self.audio_path,
            self.threshold_spin.value(),
            self.min_silence_spin.value()
        )
        self.analysis_worker.progress.connect(self._on_analysis_progress)
        self.analysis_worker.finished.connect(self._on_analysis_finished)
        self.analysis_worker.error.connect(self._on_analysis_error)
        self.analysis_worker.start()

    def _on_analysis_progress(self, msg: str):
        """处理分析进度"""
        self._log(msg)

    def _on_analysis_finished(self, silences: List[Silence]):
        """分析完成"""
        self.current_silences = silences
        self.progress_bar.setVisible(False)
        self.analyze_btn.setEnabled(True)
        self.match_btn.setEnabled(True)

        # 更新统计
        total_silence = sum(s.duration for s in silences)
        self.silence_count_label.setText(str(len(silences)))
        self.total_silence_label.setText(f"{total_silence:.2f}s")

        # 打印停顿列表
        self._log("\n检测到的停顿:")
        for i, s in enumerate(silences, 1):
            self._log(f"  {i}. {s.start:.2f}s - {s.end:.2f}s (时长: {s.duration:.2f}s)")

        # 若已选定字幕文件，自动开始匹配
        if self.srt_path and not (self.matching_worker and self.matching_worker.isRunning()):
            self._match_subtitles()

    def _on_analysis_error(self, error: str):
        """分析出错"""
        self.progress_bar.setVisible(False)
        self.analyze_btn.setEnabled(True)
        self._log(f"❌ 错误: {error}")
        QMessageBox.critical(self, "分析错误", error)

    def _match_subtitles(self):
        """匹配字幕"""
        # 防重入
        if self.matching_worker and self.matching_worker.isRunning():
            return
        if not self.srt_path:
            QMessageBox.warning(self, "警告", "请先选择字幕文件")
            return

        if not self.current_silences:
            QMessageBox.warning(self, "警告", "请先分析音频文件")
            return

        self._log("正在匹配字幕...")
        self.progress_bar.setVisible(True)
        self.match_btn.setEnabled(False)

        self.matching_worker = MatchingWorker(self.srt_path, self.current_silences)
        self.matching_worker.progress.connect(self._on_matching_progress)
        self.matching_worker.finished.connect(self._on_matching_finished)
        self.matching_worker.error.connect(self._on_matching_error)
        self.matching_worker.start()

    def _on_matching_progress(self, msg: str):
        """处理匹配进度"""
        self._log(msg)

    def _on_matching_finished(self, subtitles: List[SRTSubtitle], logs: str):
        """匹配完成"""
        self.current_subtitles = subtitles
        self.progress_bar.setVisible(False)
        self.match_btn.setEnabled(True)
        self.export_btn.setEnabled(True)

        # 更新统计
        if subtitles:
            duration = subtitles[-1].end - subtitles[0].start
            self.original_duration_label.setText(f"{duration:.2f}s")
        self.subtitle_count_label.setText(str(len(subtitles)))

        # 显示详细日志
        self._log(logs)

    def _on_matching_error(self, error: str):
        """匹配出错"""
        self.progress_bar.setVisible(False)
        self.match_btn.setEnabled(True)
        self._log(f"❌ 错误: {error}")
        QMessageBox.critical(self, "匹配错误", error)

    def _export_subtitles(self):
        """导出字幕"""
        if not self.current_subtitles:
            QMessageBox.warning(self, "警告", "没有可导出的字幕")
            return

        # 使用所选字幕文件所在目录，自动命名为 原名+replace.srt
        if not self.srt_path:
            QMessageBox.warning(self, "警告", "尚未选择字幕文件，无法确定导出位置")
            return
        srt_dir = os.path.dirname(self.srt_path)
        base_name = Path(self.srt_path).stem + "replace.srt"
        save_path = os.path.join(srt_dir, base_name)

        try:
            SRTParser.save(save_path, self.current_subtitles)
            self._log(f"✓ 字幕已保存: {save_path}")
            QMessageBox.information(self, "成功", f"字幕已导出至:\n{save_path}")
            self.export_btn.setEnabled(False)
        except Exception as e:
            self._log(f"❌ 导出失败: {str(e)}")
            QMessageBox.critical(self, "导出错误", str(e))

    def _open_output(self):
        """打开输出目录"""
        # 打开桌面或用户目录
        home_dir = str(Path.home())
        os.startfile(home_dir)

    def _reset(self):
        """重置"""
        self.audio_path = None
        self.srt_path = None
        self.current_silences = []
        self.current_subtitles = []

        self.audio_path_edit.clear()
        self.srt_path_edit.clear()
        self.log_text.clear()

        self.silence_count_label.setText("0")
        self.total_silence_label.setText("0.0s")
        self.subtitle_count_label.setText("0")
        self.original_duration_label.setText("0.0s")

        self.match_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        self.analyze_btn.setEnabled(True)

        self._log("已重置")

    def _log(self, msg: str):
        """记录日志"""
        self.log_text.append(msg)
        # 自动滚动到底部
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def _status(self, msg: str):
        """更新状态"""
        self.status_label.setText(msg)


# ============================================================================
# 主程序
# ============================================================================

def main():
    app = QApplication(sys.argv)
    
    # 设置为 Python 可执行文件的图标（pythonw.exe）
    try:
        python_exe = sys.executable  # pythonw.exe 路径
        if os.path.exists(python_exe):
            icon = QIcon(python_exe)
            if not icon.isNull():
                app.setWindowIcon(icon)
    except Exception:
        pass
    
    window = SubtitlePauseMatcherUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
