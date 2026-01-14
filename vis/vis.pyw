
# -*- coding: utf-8 -*-
import sys
import os
import subprocess
import ctypes
from dataclasses import dataclass
from typing import Optional, List


_ICON_CACHE = {}


def _script_dir() -> str:
	if getattr(sys, "frozen", False):
		return os.path.dirname(sys.executable)
	return os.path.dirname(os.path.abspath(__file__))


def check_and_regenerate_ui():
	"""根据本目录的 form.ui 生成 ui_form.py（若缺失或过期）。"""
	script_dir = _script_dir()
	ui_file = os.path.join(script_dir, "form.ui")
	py_file = os.path.join(script_dir, "ui_form.py")

	if not os.path.exists(ui_file):
		print("缺少 form.ui，无法生成 ui_form.py。")
		return

	if (not os.path.exists(py_file)) or (os.path.getmtime(ui_file) > os.path.getmtime(py_file)):
		print(f"正在从 {ui_file} 生成 {py_file} …")
		try:
			subprocess.run(["pyside6-uic", ui_file, "-o", py_file], check=True)
			print("UI 生成成功。")
		except (subprocess.CalledProcessError, FileNotFoundError) as e:
			print(f"生成 UI 失败: {e}")
			print("请确认已安装 PySide6，并且 pyside6-uic 可用。")
			sys.exit(1)


check_and_regenerate_ui()

# 确保本目录的 ui_form.py 可被导入
_THIS_DIR = _script_dir()
if _THIS_DIR not in sys.path:
	sys.path.insert(0, _THIS_DIR)

from PySide6.QtCore import Qt, QSize, QThread, Signal, QSettings
from PySide6.QtGui import QIcon, QGuiApplication, QPixmap
from PySide6.QtWidgets import (
	QApplication,
	QWidget,
	QVBoxLayout,
	QHBoxLayout,
	QLabel,
	QPushButton,
	QPlainTextEdit,
	QFileDialog,
	QCheckBox,
	QComboBox,
	QLineEdit,
	QGroupBox,
	QFormLayout,
	QSpinBox,
	QDoubleSpinBox,
	QSizePolicy,
)

try:
	from PySide6.QtWidgets import QSystemTrayIcon, QMenu
	from PySide6.QtGui import QAction
except Exception:
	QSystemTrayIcon = None

try:
	from ui_form import Ui_Widget
except Exception:
	# 兜底：再次尝试生成并导入
	check_and_regenerate_ui()
	from ui_form import Ui_Widget


def _load_app_icon_with_fallbacks() -> Optional[QIcon]:
	script_dir = _script_dir()
	icon_candidates = [
		os.path.join(script_dir, "vision.ico"),
		os.path.join(os.path.dirname(script_dir), "QT", "AYE", "icon.ico"),
	]

	for p in icon_candidates:
		p = os.path.normpath(os.path.abspath(p))
		if os.path.exists(p):
			ic = QIcon(p)
			if not ic.isNull():
				_ICON_CACHE["app_icon"] = ic
				return ic
	return None


def _ensure_system_tray(parent_widget: QWidget, icon: Optional[QIcon]):
	if QSystemTrayIcon is None:
		return
	if not QSystemTrayIcon.isSystemTrayAvailable():
		return
	try:
		tray = QSystemTrayIcon(parent_widget)
		if icon is None or icon.isNull():
			icon = parent_widget.windowIcon() or QApplication.instance().windowIcon()
		if icon is not None and not icon.isNull():
			tray.setIcon(icon)
		tray.setToolTip("AYE Vision 工具集")

		menu = QMenu(parent_widget)
		act_show = QAction("显示窗口", parent_widget)
		act_quit = QAction("退出", parent_widget)
		menu.addAction(act_show)
		menu.addSeparator()
		menu.addAction(act_quit)
		tray.setContextMenu(menu)

		def _on_show():
			parent_widget.showNormal()
			parent_widget.activateWindow()

		act_show.triggered.connect(_on_show)
		act_quit.triggered.connect(QApplication.instance().quit)

		tray.show()
		parent_widget._tray_icon = tray
		parent_widget._tray_menu = menu
	except Exception:
		return


@dataclass
class VisionSettings:
	# ImageAnalysisClient.analyze(language=...) language hint.
	# Azure 视觉通常接受 BCP-47（如 zh-Hans / en）。
	# 但不同区域/模型支持的 language 可能更少；为避免 NotSupportedLanguage，默认用 "zh"。
	language: str = "zh"
	model_version: str = "latest"
	gender_neutral_caption: bool = True
	include_confidence: bool = True
	min_confidence: float = 0.0
	max_items: int = 50
	output_format: str = "text"  # text | json


def _normalize_language(lang: str) -> str:
	"""将用户语言输入规范化为更可能被服务端接受的值。"""
	val = (lang or "").strip()
	if not val:
		return "en"
	l = val.lower().replace("_", "-")
	# 观察到部分资源对 zh-Hans 会报 NotSupportedLanguage，这里统一降级为 zh。
	if l in {"zh-hans", "zh-cn", "zh-sg", "zh-hant", "zh-tw", "zh-hk", "zh-mo"}:
		return "zh"
	# 常见语言直接放行
	if l in {"zh", "en", "ja", "ko", "es", "pt", "fr", "de", "it", "ru"}:
		return l
	# 其它 BCP-47：保留原始值（有可能被支持）
	return val


def _get_runtime_settings() -> VisionSettings:
	"""运行时设置：默认从 QSettings 读取，并允许环境变量覆盖。"""
	# 先从本机持久化设置读（非敏感）
	qs = QSettings("AYE", "AYE Vision")
	def _get_bool(key: str, default: bool) -> bool:
		v = qs.value(key, default)
		if isinstance(v, bool):
			return v
		return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}

	def _get_int(key: str, default: int) -> int:
		try:
			return int(qs.value(key, default))
		except Exception:
			return default

	def _get_float(key: str, default: float) -> float:
		try:
			return float(qs.value(key, default))
		except Exception:
			return default

	s = VisionSettings(
		language=str(qs.value("vision/language", VisionSettings.language)).strip() or VisionSettings.language,
		model_version=str(qs.value("vision/model_version", VisionSettings.model_version)).strip() or VisionSettings.model_version,
		gender_neutral_caption=_get_bool("vision/gender_neutral_caption", VisionSettings.gender_neutral_caption),
		include_confidence=_get_bool("vision/include_confidence", VisionSettings.include_confidence),
		min_confidence=_get_float("vision/min_confidence", VisionSettings.min_confidence),
		max_items=_get_int("vision/max_items", VisionSettings.max_items),
		output_format=str(qs.value("vision/output_format", VisionSettings.output_format)).strip() or VisionSettings.output_format,
	)

	# 环境变量覆盖（方便脚本化/便携）
	lang_env = (os.environ.get("VISION_LANGUAGE", "") or "").strip()
	ver_env = (os.environ.get("VISION_MODEL_VERSION", "") or "").strip()
	if lang_env:
		s.language = lang_env
	if ver_env:
		s.model_version = ver_env
	return s


def _save_runtime_settings(s: VisionSettings) -> None:
	qs = QSettings("AYE", "AYE Vision")
	qs.setValue("vision/language", s.language)
	qs.setValue("vision/model_version", s.model_version)
	qs.setValue("vision/gender_neutral_caption", bool(s.gender_neutral_caption))
	qs.setValue("vision/include_confidence", bool(s.include_confidence))
	qs.setValue("vision/min_confidence", float(s.min_confidence))
	qs.setValue("vision/max_items", int(s.max_items))
	qs.setValue("vision/output_format", s.output_format)


def _try_create_client():
	try:
		from azure.ai.vision.imageanalysis import ImageAnalysisClient
		from azure.core.credentials import AzureKeyCredential
	except Exception as e:
		return None, (
			"未检测到 Azure Vision SDK 依赖。\n\n"
			"请安装：\n"
			"  pip install azure-ai-vision-imageanalysis azure-core\n\n"
			f"导入错误：{e}"
		)

	endpoint = (os.environ.get("VISION_ENDPOINT", "") or "").strip()
	key = (os.environ.get("VISION_KEY", "") or "").strip()
	if not endpoint or not key:
		return None, (
			"缺少环境变量：VISION_ENDPOINT / VISION_KEY\n\n"
			"请在运行程序前设置（示例）：\n"
			"  PowerShell(临时)：\n"
			"    $env:VISION_ENDPOINT=\"https://<resource>.cognitiveservices.azure.com\"\n"
			"    $env:VISION_KEY=\"<你的KEY>\"\n\n"
			"  PowerShell(永久)：\n"
			"    setx VISION_ENDPOINT \"https://<resource>.cognitiveservices.azure.com\"\n"
			"    setx VISION_KEY \"<你的KEY>\"\n\n"
			"设置后请重启 VS Code / 终端再运行。"
		)

	try:
		client = ImageAnalysisClient(endpoint=endpoint, credential=AzureKeyCredential(key))
		return client, None
	except Exception as e:
		return None, f"创建客户端失败：{e}"


class AnalyzeWorker(QThread):
	finished_ok = Signal(str)
	finished_err = Signal(str)

	def __init__(
		self,
		*,
		image_path: str,
		language: str,
		model_version: str,
		gender_neutral_caption: bool,
		include_confidence: bool,
		min_confidence: float,
		max_items: int,
		output_format: str,
		enable_caption: bool,
		enable_tags: bool,
		enable_objects: bool,
		enable_dense_captions: bool,
		enable_people: bool,
	):
		super().__init__()
		self.image_path = image_path
		self.language = language
		self.model_version = model_version
		self.gender_neutral_caption = gender_neutral_caption
		self.include_confidence = include_confidence
		self.min_confidence = float(min_confidence)
		self.max_items = int(max_items)
		self.output_format = (output_format or "text").strip().lower()
		self.enable_caption = enable_caption
		self.enable_tags = enable_tags
		self.enable_objects = enable_objects
		self.enable_dense_captions = enable_dense_captions
		self.enable_people = enable_people

	def run(self):
		client, err = _try_create_client()
		if err:
			self.finished_err.emit(err)
			return

		try:
			from azure.ai.vision.imageanalysis.models import VisualFeatures
		except Exception as e:
			self.finished_err.emit(f"导入 VisualFeatures 失败：{e}")
			return

		if not self.image_path or (not os.path.exists(self.image_path)):
			self.finished_err.emit("请选择有效的图片文件。")
			return

		features: List[VisualFeatures] = []
		if self.enable_caption:
			features.append(VisualFeatures.CAPTION)
		if self.enable_dense_captions and hasattr(VisualFeatures, "DENSE_CAPTIONS"):
			features.append(getattr(VisualFeatures, "DENSE_CAPTIONS"))
		if self.enable_tags:
			features.append(VisualFeatures.TAGS)
		if self.enable_objects:
			features.append(VisualFeatures.OBJECTS)
		if self.enable_people and hasattr(VisualFeatures, "PEOPLE"):
			features.append(getattr(VisualFeatures, "PEOPLE"))
		if not features:
			self.finished_err.emit("请至少勾选一个分析项（描述/标签/对象/密集描述/人物）。")
			return

		try:
			with open(self.image_path, "rb") as f:
				image_data = f.read()

			req_language = _normalize_language(self.language)
			try:
				result = client.analyze(
					image_data=image_data,
					visual_features=features,
					language=req_language,
					model_version=(self.model_version or "latest"),
					gender_neutral_caption=bool(self.gender_neutral_caption),
				)
			except Exception as e:
				msg = str(e)
				if ("NotSupportedLanguage" in msg) or ("language is not supported" in msg.lower()):
					result = client.analyze(
						image_data=image_data,
						visual_features=features,
						language="en",
						model_version=(self.model_version or "latest"),
						gender_neutral_caption=bool(self.gender_neutral_caption),
					)
					req_language = "en"
				else:
					raise

			min_conf = max(0.0, min(1.0, float(self.min_confidence)))
			max_items = max(1, min(200, int(self.max_items)))

			def _fmt_conf(v: Optional[float]) -> str:
				if (not self.include_confidence) or v is None:
					return ""
				try:
					return f"（置信度={float(v):.4f}）"
				except Exception:
					return ""

			# 支持 JSON 输出（方便后续自动化/复制）
			if self.output_format == "json":
				import json
				payload = {
					"image_path": self.image_path,
					"language": req_language,
					"model_version": self.model_version,
					"caption": None,
					"dense_captions": [],
					"tags": [],
					"objects": [],
					"people": [],
				}
				cap = getattr(result, "caption", None)
				if cap is not None:
					payload["caption"] = {"text": getattr(cap, "text", ""), "confidence": getattr(cap, "confidence", None)}
				dc = getattr(result, "dense_captions", None)
				if dc:
					for item in list(dc)[:max_items]:
						payload["dense_captions"].append({
							"text": getattr(item, "text", ""),
							"confidence": getattr(item, "confidence", None),
						})
				tags = getattr(result, "tags", None)
				if tags:
					for t in tags:
						conf = getattr(t, "confidence", None)
						if conf is not None and float(conf) < min_conf:
							continue
						payload["tags"].append({"name": getattr(t, "name", ""), "confidence": conf})
						if len(payload["tags"]) >= max_items:
							break
				objs = getattr(result, "objects", None)
				if objs:
					for o in list(objs)[:max_items]:
						rect = getattr(o, "bounding_box", None)
						bbox = None
						if rect is not None:
							bbox = {"x": getattr(rect, "x", None), "y": getattr(rect, "y", None), "w": getattr(rect, "w", None), "h": getattr(rect, "h", None)}
						tags2 = getattr(o, "tags", None) or []
						tag_name = getattr(tags2[0], "name", "") if tags2 else ""
						payload["objects"].append({"name": tag_name, "bounding_box": bbox})
				people = getattr(result, "people", None)
				if people:
					for p in list(people)[:max_items]:
						rect = getattr(p, "bounding_box", None)
						bbox = None
						if rect is not None:
							bbox = {"x": getattr(rect, "x", None), "y": getattr(rect, "y", None), "w": getattr(rect, "w", None), "h": getattr(rect, "h", None)}
						payload["people"].append({"bounding_box": bbox})
				self.finished_ok.emit(json.dumps(payload, ensure_ascii=False, indent=2))
				return

			lines: List[str] = []
			lines.append("图像分析结果：")
			lines.append(f"- 语言：{req_language}")
			lines.append(f"- 模型版本：{self.model_version}")

			cap = getattr(result, "caption", None)
			if cap is not None:
				lines.append("\n[描述]")
				lines.append(f"{cap.text}{_fmt_conf(getattr(cap, 'confidence', None))}")

			dc = getattr(result, "dense_captions", None)
			if dc:
				lines.append("\n[密集描述]")
				count = 0
				for item in dc:
					conf = getattr(item, "confidence", None)
					if conf is not None and float(conf) < min_conf:
						continue
					text = getattr(item, "text", "")
					lines.append(f"- {text}{_fmt_conf(conf)}")
					count += 1
					if count >= max_items:
						break

			tags = getattr(result, "tags", None)
			if tags:
				lines.append("\n[标签]")
				count = 0
				for t in tags:
					conf = getattr(t, "confidence", None)
					if conf is not None and float(conf) < min_conf:
						continue
					lines.append(f"- {t.name}{_fmt_conf(conf)}")
					count += 1
					if count >= max_items:
						break

			objs = getattr(result, "objects", None)
			if objs:
				lines.append("\n[对象]")
				for o in list(objs)[:max_items]:
					rect = getattr(o, "bounding_box", None)
					bbox = ""
					if rect is not None:
						bbox = f"x={rect.x}, y={rect.y}, w={rect.w}, h={rect.h}"
					tag_name = "对象"
					tags2 = getattr(o, "tags", None)
					if tags2:
						try:
							tag_name = getattr(tags2[0], "name", None) or str(tags2[0])
						except Exception:
							tag_name = "对象"
					lines.append(f"- {tag_name}（{bbox}）" if bbox else f"- {tag_name}")

			people = getattr(result, "people", None)
			if people:
				lines.append("\n[人物]")
				for idx, p in enumerate(list(people)[:max_items], start=1):
					rect = getattr(p, "bounding_box", None)
					if rect is not None:
						lines.append(f"- 人物{idx}（x={rect.x}, y={rect.y}, w={rect.w}, h={rect.h}）")
					else:
						lines.append(f"- 人物{idx}")

			self.finished_ok.emit("\n".join(lines).strip())
		except Exception as e:
			self.finished_err.emit(str(e))


class OcrWorker(QThread):
	finished_ok = Signal(str)
	finished_err = Signal(str)

	def __init__(self, *, image_path: str, model_version: str):
		super().__init__()
		self.image_path = image_path
		self.model_version = model_version

	def run(self):
		client, err = _try_create_client()
		if err:
			self.finished_err.emit(err)
			return

		try:
			from azure.ai.vision.imageanalysis.models import VisualFeatures
		except Exception as e:
			self.finished_err.emit(f"导入 VisualFeatures 失败：{e}")
			return

		if not self.image_path or (not os.path.exists(self.image_path)):
			self.finished_err.emit("请选择有效的图片文件。")
			return

		try:
			with open(self.image_path, "rb") as f:
				image_data = f.read()

			result = client.analyze(
				image_data=image_data,
				visual_features=[VisualFeatures.READ],
				model_version=(self.model_version or "latest"),
			)

			out_lines: List[str] = []
			out_lines.append("文字识别结果：")
			if getattr(result, "read", None) is None:
				out_lines.append("（没有返回识别结果）")
				self.finished_ok.emit("\n".join(out_lines))
				return

			blocks = getattr(result.read, "blocks", None) or []
			if not blocks:
				out_lines.append("（未检测到文字）")
				self.finished_ok.emit("\n".join(out_lines))
				return

			# 官方示例默认取 blocks[0]，这里合并所有 blocks 的行
			for bi, block in enumerate(blocks):
				lines = getattr(block, "lines", None) or []
				if bi > 0 and lines:
					out_lines.append("")
				for line in lines:
					out_lines.append(line.text)

			self.finished_ok.emit("\n".join(out_lines).strip())
		except Exception as e:
			self.finished_err.emit(str(e))


class ImagePicker(QWidget):
	image_changed = Signal(str)

	def __init__(self, parent=None):
		super().__init__(parent)
		self.image_path = ""

		root = QVBoxLayout(self)
		root.setContentsMargins(0, 0, 0, 0)
		root.setSpacing(8)

		top = QHBoxLayout()
		self.btn_open = QPushButton("选择图片")
		self.path_label = QLabel("未选择")
		self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
		top.addWidget(self.btn_open)
		top.addWidget(self.path_label)
		top.addStretch(1)
		root.addLayout(top)

		self.preview = QLabel()
		self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
		self.preview.setMinimumHeight(220)
		self.preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
		self.preview.setText("图片预览")
		root.addWidget(self.preview)

		self.btn_open.clicked.connect(self._choose)

	def _choose(self):
		path, _ = QFileDialog.getOpenFileName(
			self,
			"选择图片",
			"",
			"Images (*.png *.jpg *.jpeg *.bmp *.webp *.tiff *.tif *.gif *.ico)"
		)
		if not path:
			return
		self.set_image(path)

	def set_image(self, path: str):
		self.image_path = path
		self.path_label.setText(path)
		pm = QPixmap(path)
		if pm.isNull():
			self.preview.setText("无法加载图片预览")
		else:
			self.preview.setPixmap(pm.scaled(self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
		self.image_changed.emit(path)

	def resizeEvent(self, event):
		super().resizeEvent(event)
		if self.image_path:
			pm = QPixmap(self.image_path)
			if not pm.isNull():
				self.preview.setPixmap(pm.scaled(self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))


class ImageAnalysisWidget(QWidget):
	def __init__(self, parent=None):
		super().__init__(parent)
		self._worker: Optional[AnalyzeWorker] = None
		self._init_from_settings(_get_runtime_settings())

		root = QVBoxLayout(self)
		root.setContentsMargins(12, 12, 12, 12)
		root.setSpacing(10)

		self.picker = ImagePicker()
		root.addWidget(self.picker)

		advanced = QGroupBox("高级设置")
		adv_form = QFormLayout(advanced)
		adv_form.setContentsMargins(12, 10, 12, 10)
		adv_form.setHorizontalSpacing(16)
		adv_form.setVerticalSpacing(8)

		self.cmb_language = QComboBox()
		self.cmb_language.addItem("中文（简体）", "zh")
		self.cmb_language.addItem("英文", "en")
		self.cmb_language.addItem("日文", "ja")
		self.cmb_language.addItem("韩文", "ko")
		self.edt_model_version = QLineEdit()
		self.edt_model_version.setPlaceholderText("例如：latest")
		self.chk_gender_neutral = QCheckBox("使用中性描述（gender_neutral_caption）")
		self.chk_include_conf = QCheckBox("显示置信度")
		self.spin_min_conf = QDoubleSpinBox()
		self.spin_min_conf.setRange(0.0, 1.0)
		self.spin_min_conf.setSingleStep(0.05)
		self.spin_min_conf.setDecimals(2)
		self.spin_max_items = QSpinBox()
		self.spin_max_items.setRange(1, 200)
		self.spin_max_items.setSingleStep(5)
		self.cmb_output = QComboBox()
		self.cmb_output.addItem("纯文本", "text")
		self.cmb_output.addItem("JSON", "json")

		adv_form.addRow("语言：", self.cmb_language)
		adv_form.addRow("模型版本：", self.edt_model_version)
		adv_form.addRow("输出格式：", self.cmb_output)
		adv_form.addRow("置信度阈值：", self.spin_min_conf)
		adv_form.addRow("最多条目：", self.spin_max_items)
		adv_form.addRow("", self.chk_include_conf)
		adv_form.addRow("", self.chk_gender_neutral)
		root.addWidget(advanced)

		ops = QHBoxLayout()
		self.chk_caption = QCheckBox("描述")
		self.chk_dense_captions = QCheckBox("密集描述")
		self.chk_tags = QCheckBox("标签")
		self.chk_objects = QCheckBox("对象")
		self.chk_people = QCheckBox("人物")
		self.chk_caption.setChecked(True)
		self.chk_tags.setChecked(True)
		self.chk_objects.setChecked(True)
		ops.addWidget(self.chk_caption)
		ops.addWidget(self.chk_dense_captions)
		ops.addWidget(self.chk_tags)
		ops.addWidget(self.chk_objects)
		ops.addWidget(self.chk_people)
		ops.addStretch(1)
		self.btn_run = QPushButton("开始分析")
		ops.addWidget(self.btn_run)
		root.addLayout(ops)

		self.out = QPlainTextEdit()
		self.out.setReadOnly(True)
		self.out.setPlaceholderText("输出结果…")
		root.addWidget(self.out)

		self.btn_run.clicked.connect(self._run)
		self._apply_settings_to_ui(_get_runtime_settings())
		self._wire_autosave()

	def _init_from_settings(self, s: VisionSettings) -> None:
		# 预留：后续可能需要初始化一些默认值
		_ = s

	def _wire_autosave(self) -> None:
		def _on_change():
			_save_runtime_settings(self._collect_settings_from_ui())
		try:
			self.cmb_language.currentIndexChanged.connect(_on_change)
			self.edt_model_version.textChanged.connect(_on_change)
			self.chk_gender_neutral.toggled.connect(_on_change)
			self.chk_include_conf.toggled.connect(_on_change)
			self.spin_min_conf.valueChanged.connect(_on_change)
			self.spin_max_items.valueChanged.connect(_on_change)
			self.cmb_output.currentIndexChanged.connect(_on_change)
		except Exception:
			pass

	def _apply_settings_to_ui(self, s: VisionSettings) -> None:
		# 语言
		idx = self.cmb_language.findData(s.language)
		if idx >= 0:
			self.cmb_language.setCurrentIndex(idx)
		else:
			# 允许用户输入的任意语言代码：用“当前项”承载
			self.cmb_language.addItem(s.language, s.language)
			self.cmb_language.setCurrentIndex(self.cmb_language.count() - 1)
		self.edt_model_version.setText(s.model_version)
		idx2 = self.cmb_output.findData((s.output_format or "text").strip().lower())
		if idx2 >= 0:
			self.cmb_output.setCurrentIndex(idx2)
		self.spin_min_conf.setValue(float(s.min_confidence))
		self.spin_max_items.setValue(int(s.max_items))
		self.chk_include_conf.setChecked(bool(s.include_confidence))
		self.chk_gender_neutral.setChecked(bool(s.gender_neutral_caption))

	def _collect_settings_from_ui(self) -> VisionSettings:
		return VisionSettings(
			language=str(self.cmb_language.currentData() or "zh-Hans").strip() or "zh-Hans",
			model_version=(self.edt_model_version.text() or "latest").strip() or "latest",
			gender_neutral_caption=bool(self.chk_gender_neutral.isChecked()),
			include_confidence=bool(self.chk_include_conf.isChecked()),
			min_confidence=float(self.spin_min_conf.value()),
			max_items=int(self.spin_max_items.value()),
			output_format=str(self.cmb_output.currentData() or "text").strip().lower() or "text",
		)

	def _run(self):
		# 以 UI 为准（并持久化）；环境变量仍可覆盖关键字段
		s_ui = self._collect_settings_from_ui()
		_save_runtime_settings(s_ui)
		s = _get_runtime_settings()
		# 用当前 UI 的字段覆盖（除了 env 强制覆盖的 language/model_version）
		s.gender_neutral_caption = s_ui.gender_neutral_caption
		s.include_confidence = s_ui.include_confidence
		s.min_confidence = s_ui.min_confidence
		s.max_items = s_ui.max_items
		s.output_format = s_ui.output_format
		image_path = self.picker.image_path

		if self._worker is not None and self._worker.isRunning():
			return

		self.out.setPlainText("正在请求 Azure Vision…")
		self.btn_run.setEnabled(False)

		self._worker = AnalyzeWorker(
			image_path=image_path,
			language=s.language,
			model_version=s.model_version,
			gender_neutral_caption=s.gender_neutral_caption,
			include_confidence=s.include_confidence,
			min_confidence=s.min_confidence,
			max_items=s.max_items,
			output_format=s.output_format,
			enable_caption=self.chk_caption.isChecked(),
			enable_tags=self.chk_tags.isChecked(),
			enable_objects=self.chk_objects.isChecked(),
			enable_dense_captions=self.chk_dense_captions.isChecked(),
			enable_people=self.chk_people.isChecked(),
		)
		self._worker.finished_ok.connect(self._on_ok)
		self._worker.finished_err.connect(self._on_err)
		self._worker.finished.connect(lambda: self.btn_run.setEnabled(True))
		self._worker.start()

	def _on_ok(self, text: str):
		self.out.setPlainText(text)

	def _on_err(self, text: str):
		self.out.setPlainText(text)


class OCRWidget(QWidget):
	def __init__(self, parent=None):
		super().__init__(parent)
		self._worker: Optional[OcrWorker] = None

		root = QVBoxLayout(self)
		root.setContentsMargins(12, 12, 12, 12)
		root.setSpacing(10)

		self.picker = ImagePicker()
		root.addWidget(self.picker)

		cfg = QGroupBox("识别设置")
		cfg_form = QFormLayout(cfg)
		cfg_form.setContentsMargins(12, 10, 12, 10)
		cfg_form.setHorizontalSpacing(16)
		cfg_form.setVerticalSpacing(8)
		self.edt_model_version = QLineEdit()
		self.edt_model_version.setPlaceholderText("例如：latest")
		cfg_form.addRow("模型版本：", self.edt_model_version)
		root.addWidget(cfg)

		row = QHBoxLayout()
		self.btn_run = QPushButton("开始识别")
		row.addStretch(1)
		row.addWidget(self.btn_run)
		root.addLayout(row)

		self.out = QPlainTextEdit()
		self.out.setReadOnly(True)
		self.out.setPlaceholderText("输出文字识别结果…")
		root.addWidget(self.out)

		self.btn_run.clicked.connect(self._run)
		# 从共享设置读取默认 model_version
		try:
			s = _get_runtime_settings()
			self.edt_model_version.setText(s.model_version)
		except Exception:
			pass

	def _run(self):
		s_ui = _get_runtime_settings()
		mv = (self.edt_model_version.text() or "").strip()
		if mv:
			s_ui.model_version = mv
		_save_runtime_settings(s_ui)
		s = _get_runtime_settings()
		image_path = self.picker.image_path

		if self._worker is not None and self._worker.isRunning():
			return

		self.out.setPlainText("正在请求 Azure OCR…")
		self.btn_run.setEnabled(False)

		self._worker = OcrWorker(
			image_path=image_path,
			model_version=s.model_version,
		)
		self._worker.finished_ok.connect(self._on_ok)
		self._worker.finished_err.connect(self._on_err)
		self._worker.finished.connect(lambda: self.btn_run.setEnabled(True))
		self._worker.start()

	def _on_ok(self, text: str):
		self.out.setPlainText(text)

	def _on_err(self, text: str):
		self.out.setPlainText(text)


class MainWidget(QWidget):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.ui = Ui_Widget()
		self.ui.setupUi(self)
		self.setWindowTitle("Vision 工具集")

		# 清理占位并嵌入页面（已取消配置页：只从环境变量读取）
		self._replace_page(self.ui.page_1, ImageAnalysisWidget())
		self._replace_page(self.ui.page_2, OCRWidget())

		# 改导航标题（保持与 UI 一致）
		try:
			self.ui.navigationList.item(0).setText("图像分析")
			self.ui.navigationList.item(1).setText("文字识别")
		except Exception:
			pass

	@staticmethod
	def _replace_page(page: QWidget, widget: QWidget):
		layout = page.layout()
		if layout is None:
			layout = QVBoxLayout(page)
		while layout.count():
			item = layout.takeAt(0)
			w = item.widget()
			if w is not None:
				w.deleteLater()
		layout.addWidget(widget)


if __name__ == "__main__":
	if sys.platform.startswith("win"):
		try:
			ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AYE.Vision.App.1.0")
		except Exception:
			pass

	try:
		QGuiApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
	except Exception:
		pass

	app = QApplication(sys.argv)
	app.setOrganizationName("AYE")
	app.setOrganizationDomain("local.aye")
	app.setApplicationName("AYE Vision")
	app.setApplicationDisplayName("AYE Vision 工具集")

	app_icon = _load_app_icon_with_fallbacks()
	if app_icon is not None and not app_icon.isNull():
		app.setWindowIcon(app_icon)

	w = MainWidget()
	if app_icon is not None:
		w.setWindowIcon(app_icon)

	# 默认高度：参考 TTS_Main.pyw
	try:
		screen = QGuiApplication.primaryScreen()
		geo = screen.availableGeometry() if screen is not None else None
		if geo is not None:
			cur = w.geometry()
			new_h = min(900, geo.height())
			new_w = max(760, min(cur.width() if cur.width() else 820, int(geo.width() * 0.95)))
			x = geo.x() + max(0, int((geo.width() - new_w) / 2))
			y = geo.y() + max(0, int((geo.height() - new_h) / 2))
			w.setGeometry(x, y, new_w, new_h)
		else:
			w.resize(820, 900)
	except Exception:
		pass

	_ensure_system_tray(w, app_icon)
	w.show()

	sys.exit(app.exec())

