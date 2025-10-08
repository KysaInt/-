#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Cinema 4D 渲染队列状态查看器（可在 C4D Python 解释器内运行）

功能：
- 显示当前渲染队列是否有任务
- 判断是否有任务正在执行（渲染中）
- 判断是否处于等待/暂停/已停止（无进行中且无等待）
- 列出每个队列任务的简要状态

用法：
1) 在 C4D 中：脚本 > 用户脚本 > 运行脚本
2) 或使用 c4dpy 运行本文件（需 C4D Python 环境）：c4dpy API.PYW

说明：
脚本尽量使用 C4D 内置的 Render Queue API（documents.GetRenderQueue 等）。
不同版本的 C4D API 可能略有差异，已加入容错与回退逻辑，避免直接报错退出。
"""

from __future__ import annotations
import sys
import importlib
from typing import Any, Callable, Dict, Iterable, List, Optional

# 尝试导入 C4D API
try:
	c4d = importlib.import_module("c4d")
	documents = importlib.import_module("c4d.documents")
	c4d_gui = importlib.import_module("c4d.gui")
	modules = importlib.import_module("c4d.modules")
	C4D_AVAILABLE = True
except Exception:
	c4d = None
	documents = None
	c4d_gui = None
	modules = None
	C4D_AVAILABLE = False


# ---------- 输出工具 ----------
def _out(msg: str) -> None:
	if C4D_AVAILABLE:
		try:
			c4d.GePrint(str(msg))
		except Exception:
			print(msg)
	else:
		print(msg)


def _err(msg: str) -> None:
	if C4D_AVAILABLE:
		try:
			c4d.GePrint("[错误] " + str(msg))
		except Exception:
			print("[错误] " + str(msg), file=sys.stderr)
	else:
		print("[错误] " + str(msg), file=sys.stderr)


# ---------- 动态 API 兼容辅助 ----------
_RENDERQUEUE_MODULE: Any = None
_RENDERQUEUE_MODULE_CHECKED = False


def _get_renderqueue_module() -> Any:
	global _RENDERQUEUE_MODULE, _RENDERQUEUE_MODULE_CHECKED
	if not C4D_AVAILABLE:
		return None
	if _RENDERQUEUE_MODULE_CHECKED:
		return _RENDERQUEUE_MODULE
	_RENDERQUEUE_MODULE_CHECKED = True
	try:
		rq_module = importlib.import_module("c4d.modules.renderqueue")
		_RENDERQUEUE_MODULE = rq_module
		return _RENDERQUEUE_MODULE
	except Exception:
		pass
	try:
		_RENDERQUEUE_MODULE = getattr(modules, "renderqueue")
	except Exception:
		_RENDERQUEUE_MODULE = None
	return _RENDERQUEUE_MODULE


def _try_callable(label: str, func: Callable[[], Any], errors: List[str]) -> Optional[Any]:
	try:
		result = func()
	except AttributeError as exc:
		errors.append(f"{label}缺少属性：{exc}")
		return None
	except Exception as exc:
		errors.append(f"{label}失败：{exc}")
		return None
	if result is not None:
		_out(f"{label}获取渲染队列成功。")
		return result
	errors.append(f"{label}返回空对象。")
	return None


def _find_render_queue() -> Optional[Any]:
	if not C4D_AVAILABLE:
		return None
	errors: List[str] = []

	getter = getattr(c4d, "GetRenderQueue", None)
	if callable(getter):
		rq = _try_callable("全局方法", getter, errors)
		if rq is not None:
			return rq
	else:
		errors.append("全局方法不可用：c4d.GetRenderQueue 不存在或不可调用。")

	getter = getattr(documents, "GetRenderQueue", None)
	if callable(getter):
		rq = _try_callable("文档方法", getter, errors)
		if rq is not None:
			return rq
	else:
		errors.append("文档方法不可用：c4d.documents.GetRenderQueue 不存在或不可调用。")

	active_doc_getter = getattr(documents, "GetActiveDocument", None)
	if callable(active_doc_getter):
		try:
			doc = active_doc_getter()
		except Exception as exc:
			errors.append(f"获取当前文档失败：{exc}")
			doc = None
		if doc:
			for method_name in ("GetRenderQueue", "GetQueue"):
				method = getattr(doc, method_name, None)
				if callable(method):
					try:
						rq = method()
					except Exception as exc:
						errors.append(f"文档.{method_name}() 失败：{exc}")
					else:
						if rq is not None:
							_out(f"文档.{method_name}() 获取渲染队列成功。")
							return rq
				else:
					errors.append(f"文档对象不支持 {method_name}()。")

	try:
		render_module = importlib.import_module("c4d.modules.render")
		getter = getattr(render_module, "GetRenderQueue", None)
		if callable(getter):
			rq = _try_callable("渲染模块方法", getter, errors)
			if rq is not None:
				return rq
		else:
			errors.append("渲染模块方法不可用：c4d.modules.render.GetRenderQueue 不存在或不可调用。")
	except Exception as exc:
		errors.append(f"渲染模块方法不可用：{exc}")

	try:
		net_module = importlib.import_module("c4d.modules.net")
		getter = getattr(net_module, "GetRenderQueue", None)
		if callable(getter):
			rq = _try_callable("网络模块方法", getter, errors)
			if rq is not None:
				return rq
		else:
			errors.append("网络模块方法不可用：c4d.modules.net.GetRenderQueue 不存在或不可调用。")
	except Exception as exc:
		errors.append(f"网络模块方法不可用：{exc}")

	rq_module = _get_renderqueue_module()
	if rq_module:
		for method_name in ("GetManager", "GetRenderQueue", "GetQueue", "GetRenderQueueManager"):
			getter = getattr(rq_module, method_name, None)
			if callable(getter):
				rq = _try_callable(f"renderqueue.{method_name}()", getter, errors)
				if rq is not None:
					return rq
		for class_name in ("RenderQueueManager", "RenderQueue"):
			cls = getattr(rq_module, class_name, None)
			if cls:
				try:
					rq = cls()
				except Exception as exc:
					errors.append(f"renderqueue.{class_name}() 初始化失败：{exc}")
					continue
				if rq is not None:
					_out(f"renderqueue.{class_name}() 创建渲染队列成功。")
					return rq

	plugins_module = getattr(c4d, "plugins", None)
	plugin_type_candidates: Iterable[str] = ("PLUGINTYPE_GLOBAL", "PLUGINTYPE_DATA", "PLUGINTYPE_SCENEHOOK")
	if plugins_module and hasattr(plugins_module, "FindPlugin"):
		plugin_type_value = None
		for type_name in plugin_type_candidates:
			plugin_type_value = getattr(c4d, type_name, None)
			if isinstance(plugin_type_value, int):
				break
		find_plugin = getattr(plugins_module, "FindPlugin")
		if callable(find_plugin) and isinstance(plugin_type_value, int):
			def plugin_getter() -> Any:
				RENDER_QUEUE_PLUGIN_ID = 465001511
				plugin = find_plugin(RENDER_QUEUE_PLUGIN_ID, plugin_type_value)
				if not plugin:
					return None
				get_data = getattr(plugin, "GetData", None)
				if callable(get_data):
					return get_data()
				return None
			rq = _try_callable("插件方法", plugin_getter, errors)
			if rq is not None:
				return rq

	for msg in errors:
		_err(msg)
	return None


def _get_named_constant(*names: str) -> Optional[int]:
	for name in names:
		value = getattr(c4d, name, None)
		if isinstance(value, int):
			return value
		rq_module = _get_renderqueue_module()
		if rq_module:
			value = getattr(rq_module, name, None)
			if isinstance(value, int):
				return value
	return None


def _value_matches(status_value: Any, *names: str) -> bool:
	constant = _get_named_constant(*names)
	return constant is not None and status_value == constant


# ---------- 队列/任务工具 ----------
def _status_to_text(job: Any) -> str:
	"""将 c4d 渲染任务对象转为状态文本。"""
	if not job:
		return "unknown"

	try:
		status_value = job.GetStatus()
		status_str = str(status_value).lower()

		# 核心状态判断 - 兼容不同版本常量
		if _value_matches(status_value, "RENDERQUEUE_STATUS_RENDERING", "RENDERQUEUE_RENDERING", "RENDERQUEUE_STATUS_RUN") or "render" in status_str or "running" in status_str:
			return "running"
		if _value_matches(status_value, "RENDERQUEUE_STATUS_COMPLETED", "RENDERQUEUE_COMPLETED", "RENDERQUEUE_STATUS_DONE") or "complete" in status_str or "finished" in status_str or "success" in status_str:
			return "completed"
		if _value_matches(status_value, "RENDERQUEUE_STATUS_FAILED", "RENDERQUEUE_FAILED", "RENDERQUEUE_STATUS_ERROR") or "fail" in status_str or "error" in status_str:
			return "failed"
		if _value_matches(status_value, "RENDERQUEUE_STATUS_PAUSED", "RENDERQUEUE_PAUSED") or "pause" in status_str or "wait" in status_str:
			return "paused"

		# 对于 PENDING 状态，需要额外检查任务是否被勾选
		if _value_matches(status_value, "RENDERQUEUE_STATUS_PENDING", "RENDERQUEUE_PENDING") or "pending" in status_str or "queue" in status_str:
			is_active = _is_job_active(job)
			return "pending" if is_active else "disabled"

	except Exception:
		pass
	
	return "unknown"


def _status_icon(text_status: str) -> str:
	return {
		"pending": "⏳",
		"running": "➡️",
		"completed": "✅",
		"failed": "❌",
		"paused": "⏸️",
		"disabled": "⚪",  # 灰色圆圈表示未勾选
		"unknown": "❓",
	}.get(text_status, "❓")


def _invoke_int_accessor(obj: Any, names: Iterable[str]) -> Optional[int]:
	for name in names:
		try:
			attr = getattr(obj, name)
		except Exception:
			continue
		try:
			value = attr() if callable(attr) else attr
		except Exception:
			continue
		if isinstance(value, int):
			return value
	try:
		attr = obj.__getattr__  # type: ignore[attr-defined]
		if callable(attr):
			for name in names:
				try:
					value = attr(name)
				except Exception:
					continue
				if isinstance(value, int):
					return value
	except Exception:
		pass
	return None


def _invoke_job_accessor(obj: Any, names: Iterable[str], index: int) -> Optional[Any]:
	for name in names:
		try:
			attr = getattr(obj, name)
		except Exception:
			continue
		try:
			value = attr(index) if callable(attr) else None
		except Exception:
			continue
		if value is not None:
			return value
	return None


def _get_job_count(queue: Any) -> int:
	value = _invoke_int_accessor(queue, ("GetJobCount", "GetEntryCount", "GetTaskCount", "GetCount", "GetElementCount"))
	return int(value or 0)


def _get_job(queue: Any, index: int) -> Optional[Any]:
	return _invoke_job_accessor(queue, ("GetJob", "GetEntry", "GetTask", "GetElement"), index)


def _get_job_name(job: Any, fallback_index: int) -> str:
	for name in ("GetName", "GetTitle", "GetLabel"):
		try:
			attr = getattr(job, name)
		except Exception:
			continue
		try:
			value = attr() if callable(attr) else attr
		except Exception:
			continue
		if isinstance(value, str) and value:
			return value
	return f"Job {fallback_index + 1}"


def _get_job_progress(job: Any) -> Optional[float]:
	for name in ("GetProgress", "GetProgressPercent", "GetPercent", "GetCompletion", "GetCompleted"):
		try:
			attr = getattr(job, name)
		except Exception:
			continue
		try:
			value = attr() if callable(attr) else attr
		except Exception:
			continue
		if isinstance(value, (float, int)):
			val = float(value)
			if 0.0 <= val <= 1.0:
				return val * 100.0
			return val
	return None


def _is_job_active(job: Any) -> bool:
	for name in ("IsActive", "GetIsActive", "IsEnabled", "GetEnabled", "GetActive"):
		try:
			attr = getattr(job, name)
		except Exception:
			continue
		try:
			value = attr() if callable(attr) else attr
		except Exception:
			continue
		if isinstance(value, bool):
			return value
	return True


def get_render_queue_snapshot() -> Optional[Dict[str, Any]]:
	"""抓取一次渲染队列快照，返回结构化信息。

	返回示例：
	{
	  'total': 3,
	  'running': 1,
	  'pending': 1,
	  'paused': 0,
	  'completed': 1,
	  'failed': 0,
	  'jobs': [
		 { 'index': 0, 'name': 'Job A', 'status': 'running', 'progress': 12.3 },
		 ...
	  ]
	}
	"""
	if not C4D_AVAILABLE:
		_err("需要在 C4D Python 环境中运行此脚本。")
		return None

	try:
		rq = _find_render_queue()
		if rq is None:
			_err("所有方法都无法获取渲染队列。")
			return None

		snapshot: Dict[str, Any] = {
			"total": 0,
			"running": 0,
			"pending": 0,
			"paused": 0,
			"completed": 0,
			"failed": 0,
			"disabled": 0,
			"unknown": 0,
			"jobs": [],
		}

		count = _get_job_count(rq)
		snapshot["total"] = int(count or 0)

		for i in range(snapshot["total"]):
			job = _get_job(rq, i)

			if not job:
				snapshot["unknown"] += 1
				snapshot["jobs"].append({
					"index": i,
					"name": f"Job {i + 1}",
					"status": "unknown",
					"progress": None,
				})
				continue

			name = _get_job_name(job, i)

			try:
				status = _status_to_text(job)
			except Exception:
				status = "unknown"

			progress = _get_job_progress(job)

			snapshot["jobs"].append({
				"index": i,
				"name": name,
				"status": status,
				"progress": progress,
			})

			# 计数
			if status == "running":
				snapshot["running"] += 1
			elif status == "pending":
				snapshot["pending"] += 1
			elif status == "paused":
				snapshot["paused"] += 1
			elif status == "completed":
				snapshot["completed"] += 1
			elif status == "failed":
				snapshot["failed"] += 1
			elif status == "disabled":
				snapshot["disabled"] += 1
			else:
				snapshot["unknown"] += 1

		return snapshot
	except Exception as e:
		_err(f"获取渲染队列信息失败：{e}")
		return None


def describe_overall(snapshot: Dict[str, Any]) -> str:
	"""综合当前快照，给出中文摘要。"""
	total = snapshot.get("total", 0)
	running = snapshot.get("running", 0)
	pending = snapshot.get("pending", 0)
	paused = snapshot.get("paused", 0)

	if total == 0:
		return "队列为空（没有任何任务）。"
	if running > 0:
		return "有任务正在渲染。"
	if paused > 0 and running == 0:
		return "队列处于暂停（无进行中的任务）。"
	if pending > 0 and running == 0:
		return "有任务等待中（当前未在渲染）。"
	# 无进行中且无等待：视为已停止/全部完成（或失败）
	return "渲染进程已停止（无进行中且无等待的任务）。"


def print_snapshot(snapshot: Dict[str, Any]) -> None:
	_out("\n" + "=" * 48)
	_out("C4D 渲染队列状态")
	_out("=" * 48)
	_out(f"总任务: {snapshot.get('total', 0)}  |  进行中: {snapshot.get('running', 0)}  |  等待: {snapshot.get('pending', 0)}  |  暂停: {snapshot.get('paused', 0)}")
	_out(f"完成: {snapshot.get('completed', 0)}  |  失败: {snapshot.get('failed', 0)}  |  禁用: {snapshot.get('disabled', 0)}  |  未知: {snapshot.get('unknown', 0)}")
	_out("")

	overall = describe_overall(snapshot)
	_out(f"摘要: {overall}")
	_out("")

	for job in snapshot.get("jobs", []):
		icon = _status_icon(job.get("status", "unknown"))
		name = job.get("name", "(未命名)")
		status = job.get("status", "unknown")
		prog = job.get("progress")
		suffix = f" 进度: {prog:.1f}%" if isinstance(prog, (int, float)) else ""
		_out(f"{icon} 任务 {job.get('index', 0) + 1}: {name}")
		_out(f"   状态: {status}{suffix}")


def _build_dialog_text(snapshot: Dict[str, Any]) -> str:
	lines = []
	lines.append("C4D 渲染队列状态\n")
	lines.append(f"总任务: {snapshot.get('total', 0)}")
	lines.append(f"进行中: {snapshot.get('running', 0)}    等待: {snapshot.get('pending', 0)}    暂停: {snapshot.get('paused', 0)}")
	lines.append(f"完成: {snapshot.get('completed', 0)}    失败: {snapshot.get('failed', 0)}    禁用: {snapshot.get('disabled', 0)}")
	lines.append("")
	lines.append("摘要: " + describe_overall(snapshot))
	lines.append("")

	jobs = snapshot.get("jobs", [])
	max_list = min(len(jobs), 5)  # 对话框里最多列出前 5 条，避免过长
	for i in range(max_list):
		j = jobs[i]
		name = j.get("name", f"Job {i+1}")
		status = j.get("status", "unknown")
		prog = j.get("progress")
		prog_txt = f" 进度 {prog:.1f}%" if isinstance(prog, (int, float)) else ""
		lines.append(f"{i+1}. {name}  —  {status}{prog_txt}")

	if len(jobs) > max_list:
		lines.append(f"... 以及另外 {len(jobs) - max_list} 个任务")

	return "\n".join(lines)


def _show_dialog(snapshot: Dict[str, Any]) -> None:
	"""在 C4D 内弹出一个简要状态对话框；非 C4D 环境不执行。"""
	if not C4D_AVAILABLE:
		return
	try:
		text = _build_dialog_text(snapshot)
		# 状态栏也提示一下（非阻塞）
		try:
			c4d.StatusSetText("渲染队列状态已更新")
		except Exception:
			pass
		# 弹出对话框（阻塞）
		c4d_gui.MessageDialog(text)
	except Exception:
		pass


def show_status_in_main_thread() -> None:
	"""在主线程中执行状态检查和显示逻辑。"""
	snap = get_render_queue_snapshot()
	if not snap:
		_err("未能获取渲染队列状态。")
		# 在 C4D 中也弹窗提示错误
		if C4D_AVAILABLE:
			try:
				c4d_gui.MessageDialog("错误：未能获取渲染队列状态。\n\n请检查控制台输出获取更多信息。")
			except Exception:
				pass
		return

	print_snapshot(snap)
	# 在 C4D 内给一个可见反馈的弹窗
	_show_dialog(snap)


def main() -> None:
	if not C4D_AVAILABLE:
		_err("未检测到 C4D Python 环境。请在 C4D 脚本控制台或使用 c4dpy 运行。")
		# 在非 C4D 环境下，.pyw 不显示控制台，这里尝试弹系统对话框提示
		try:
			import ctypes
			ctypes.windll.user32.MessageBoxW(None, "请在 Cinema 4D 环境中运行此脚本。\n\n路径: C4D/ C4D主要接口状态查看器 / API.PYW", "提示", 0x40)
		except Exception:
			pass
		return

	# 直接执行状态检查（C4D 脚本通常在主线程中运行）
	show_status_in_main_thread()


if __name__ == "__main__":
	main()


# C4D 插件消息入口（可选，不做具体处理，仅保证与 C4D 兼容）
def PluginMessage(id, data):  # noqa: N802 (C4D 约定命名)
	return True

