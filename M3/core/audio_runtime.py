from __future__ import annotations

from collections import deque
import queue
import time
from typing import Any, Mapping

import numpy as np
import pyaudiowpatch as pyaudio

try:
    from scipy.fft import fft as scipy_fft
    _HAS_SCIPY_FFT = True
except Exception:
    scipy_fft = np.fft.fft
    _HAS_SCIPY_FFT = False
    print("⚠ SciPy FFT 不可用 — 使用 NumPy FFT")


def clamp_time_window(value: Any, fallback: float) -> float:
    try:
        result = float(value)
    except Exception:
        result = float(fallback)
    if result <= 0:
        result = float(fallback)
    return max(0.005, result)


try:
    import cupy as cp

    _HAS_GPU = True
    cp.fft.fft(cp.zeros(2048))
    print("✓ CuPy 可用 — 启用 GPU FFT")
except Exception:
    cp = None
    _HAS_GPU = False
    print("⚠ CuPy 不可用 — 使用 CPU FFT")


class LoopbackAudioCapture:
    def __init__(self, *, chunk: int):
        self.chunk = int(chunk)
        self.audio_queue: queue.Queue[np.ndarray] = queue.Queue()
        self.device_info: dict[str, Any] | None = None
        self.channel_count = 2
        self.rate = 44100
        self.stream = None
        self.p = None

    def start(self):
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
            self.rate = int(default_speakers["defaultSampleRate"])
            self.channel_count = max(1, int(default_speakers.get("maxInputChannels", 2) or 2))
            print(f"使用设备: {default_speakers['name']}")
        except Exception:
            self.close()
            raise

        self.stream = self.p.open(
            format=pyaudio.paInt16,
            channels=self.channel_count,
            rate=self.rate,
            frames_per_buffer=self.chunk,
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

    def pull_latest_frame(self):
        if self.audio_queue.empty():
            return None
        try:
            return self.audio_queue.get_nowait()
        except queue.Empty:
            return None

    def close(self):
        if self.stream is not None:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        if self.p is not None:
            self.p.terminate()
            self.p = None


class AudioSignalProcessor:
    def __init__(self, config: Mapping[str, Any], *, chunk: int, rate: int = 44100, channel_count: int = 2):
        self.chunk = int(chunk)
        self.rate = int(rate)
        self.channel_count = int(channel_count)
        self.num_bars = int(config.get("num_bars", 64))
        self.config: dict[str, Any] = {}
        self.a1_time_window = 10.0
        self.loudness_history: list[tuple[float, float]] = []
        self.raw_a1_value = 0.0
        self.a1_value = 0.0
        self.k2_value = 0.0
        self.spectrum_history: deque[tuple[float, np.ndarray]] = deque()
        self.spectrum_history_sum = np.zeros(self.num_bars, dtype=float)
        self.smoothed_bar_values = np.zeros(self.num_bars, dtype=float)
        self.update_config(config)
        self.reset()

    def update_config(self, config: Mapping[str, Any]):
        self.config = dict(config)
        new_num_bars = int(self.config.get("num_bars", self.num_bars))
        bars_changed = new_num_bars != self.num_bars
        self.num_bars = new_num_bars
        self.a1_time_window = clamp_time_window(self.config.get("a1_time_window", self.a1_time_window), self.a1_time_window)
        if bars_changed:
            self.reset()

    def set_stream_format(self, *, rate: int, channel_count: int):
        self.rate = int(rate)
        self.channel_count = max(1, int(channel_count))

    def reset(self):
        self.loudness_history = []
        self.raw_a1_value = 0.0
        self.a1_value = 0.0
        self.k2_value = 0.0
        self.spectrum_history = deque()
        self.spectrum_history_sum = np.zeros(self.num_bars, dtype=float)
        self.smoothed_bar_values = np.zeros(self.num_bars, dtype=float)

    @staticmethod
    def _clamp_damping(value, fallback):
        try:
            return max(0.0, min(0.999, float(value)))
        except Exception:
            return max(0.0, min(0.999, float(fallback)))

    def get_damping_pair(self, prefix: str | None = None):
        global_rise = self._clamp_damping(self.config.get("k_rise_damping", 0.1), 0.1)
        global_fall = self._clamp_damping(self.config.get("k_fall_damping", 0.999), 0.999)
        if not prefix:
            return global_rise, global_fall
        if not self.config.get(f"{prefix}_use_independent_damping", False):
            return global_rise, global_fall
        rise = self._clamp_damping(self.config.get(f"{prefix}_independent_rise_damping", global_rise), global_rise)
        fall = self._clamp_damping(self.config.get(f"{prefix}_independent_fall_damping", global_fall), global_fall)
        return rise, fall

    def get_bar_time_window(self):
        base_time_window = clamp_time_window(self.a1_time_window, 10.0)
        if not self.config.get("bar_use_independent_time_window", False):
            return base_time_window
        return clamp_time_window(self.config.get("bar_time_window", base_time_window), base_time_window)

    def prune_spectrum_history(self, now: float | None = None):
        current_time = time.time() if now is None else now
        cutoff = current_time - self.get_bar_time_window()
        while self.spectrum_history and self.spectrum_history[0][0] < cutoff:
            _, old_values = self.spectrum_history.popleft()
            self.spectrum_history_sum -= old_values
        if not self.spectrum_history:
            self.smoothed_bar_values = np.zeros(self.num_bars, dtype=float)
        else:
            self.smoothed_bar_values = self.spectrum_history_sum / len(self.spectrum_history)
        return self.smoothed_bar_values.copy()

    def update_spectrum_history(self, bar_values, now: float | None = None):
        current_time = time.time() if now is None else now
        values = np.asarray(bar_values, dtype=float).reshape(-1)
        if values.size != self.num_bars:
            resized = np.zeros(self.num_bars, dtype=float)
            copy_count = min(self.num_bars, values.size)
            resized[:copy_count] = values[:copy_count]
            values = resized
        self.spectrum_history.append((current_time, values.copy()))
        if len(self.spectrum_history_sum) != self.num_bars:
            self.spectrum_history_sum = np.zeros(self.num_bars, dtype=float)
        self.spectrum_history_sum += values
        return self.prune_spectrum_history(current_time)

    @staticmethod
    def apply_damping_step(current, target, rise_damping, fall_damping):
        rise_factor = max(0.001, 1.0 - rise_damping)
        fall_factor = max(0.001, 1.0 - fall_damping)
        if np.isscalar(current) and np.isscalar(target):
            blend = rise_factor if target >= current else fall_factor
            return current + (target - current) * blend
        current_arr = np.asarray(current, dtype=float)
        target_arr = np.asarray(target, dtype=float)
        blend = np.where(target_arr >= current_arr, rise_factor, fall_factor)
        return current_arr + (target_arr - current_arr) * blend

    def build_band_edges(self, spectrum_length: int, freq_res: float):
        lower_bin = max(1, int(self.config.get("freq_min", 20) / freq_res))
        upper_bin = min(spectrum_length, int(np.ceil(self.config.get("freq_max", 20000) / freq_res)) + 1)
        if upper_bin <= lower_bin:
            upper_bin = min(spectrum_length, lower_bin + 1)

        min_freq = max(freq_res, lower_bin * freq_res)
        max_freq = max(min_freq + freq_res, upper_bin * freq_res)
        edges = np.geomspace(min_freq, max_freq, self.num_bars + 1) / freq_res

        bins = np.clip(np.rint(edges).astype(int), lower_bin, upper_bin)
        bins[0] = lower_bin
        bins[-1] = upper_bin
        bins = np.maximum.accumulate(bins)
        return bins

    def process_frame(self, audio_data):
        audio_values = np.asarray(audio_data)
        if self.channel_count > 1 and len(audio_values) % self.channel_count == 0:
            audio_values = audio_values.reshape(-1, self.channel_count).mean(axis=1)
        if len(audio_values) >= self.chunk:
            audio_values = audio_values[: self.chunk]
        else:
            audio_values = np.pad(audio_values, (0, self.chunk - len(audio_values)))

        loudness = np.sqrt(np.mean(audio_values.astype(float) ** 2))
        self._update_a1(loudness)

        windowed = audio_values * np.hamming(len(audio_values))
        if _HAS_GPU:
            try:
                gpu_window = cp.asarray(windowed)
                spectrum = cp.asnumpy(cp.abs(cp.fft.fft(gpu_window))[: self.chunk // 2])
            except Exception:
                spectrum = np.abs(scipy_fft(windowed))[: self.chunk // 2]
        else:
            spectrum = np.abs(scipy_fft(windowed))[: self.chunk // 2]

        freq_res = self.rate / self.chunk
        bins = self.build_band_edges(len(spectrum), freq_res)
        limit = int(bins[-1])

        bar_values = np.zeros(self.num_bars, dtype=float)
        for index in range(self.num_bars):
            start = int(bins[index])
            end = int(bins[index + 1])
            if end <= start and start < limit:
                end = min(limit, start + 1)
            if end > start:
                bar_values[index] = float(np.mean(spectrum[start:end]))
        return bar_values

    def _update_a1(self, loudness: float):
        now = time.time()
        self.loudness_history.append((now, float(loudness)))
        cutoff = now - self.a1_time_window
        self.loudness_history = [(stamp, value) for stamp, value in self.loudness_history if stamp >= cutoff]

        previous = self.a1_value
        self.raw_a1_value = np.mean([value for _, value in self.loudness_history]) if self.loudness_history else 0.0
        k_rise_damping, k_fall_damping = self.get_damping_pair()
        self.a1_value = float(self.apply_damping_step(previous, self.raw_a1_value, k_rise_damping, k_fall_damping))
        delta = self.a1_value - previous
        power = float(self.config.get("k2_pow", 1.0))
        self.k2_value = np.sign(delta) * (abs(delta) ** power)

    def update_loudness(self, loudness: float):
        self._update_a1(loudness)

    @property
    def effective_a1(self):
        if self.config.get("k2_enabled", False):
            return self.k2_value
        return self.a1_value