#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Cinema 4D 渲染队列状态查看器

在 C4D 脚本管理器中运行，输出当前渲染队列的渲染相关信息：
- 队列统计（总数、完成、失败、运行中、等待中）
- 每个任务的名称、状态、进度、渲染时间、帧范围、输出路径、最后消息

兼容性说明：
- 为兼容部分旧版 C4D（仍使用 Python 2.7/3.x），本脚本避免使用 f-string、类型注解、
  以及较新的 __future__ 特性；并对不同版本 API 做了容错读取。

用法：
1) 在 C4D 中：脚本 > 脚本管理器 > 打开本文件 > 执行
2) 若在非 C4D 环境运行，将提示需要在 C4D 中执行
"""

import os
import sys
import time
import traceback


PY2 = sys.version_info[0] == 2
if PY2:
	text_type = unicode  # noqa: F821
else:
	text_type = str

# 检测 C4D Python 环境
try:
	import c4d
	from c4d import documents
	C4D_AVAILABLE = True
except Exception:
	c4d = None  # type: ignore
	documents = None  # type: ignore
	C4D_AVAILABLE = False



def _to_text(message):
	"""把任意对象转成可打印的文本，兼容 Py2/Py3。"""
	try:
		if isinstance(message, text_type):
			return message
		# Py2: bytes -> unicode
		if PY2 and isinstance(message, str):
			try:
				return message.decode("utf-8", "replace")
			except Exception:
				return text_type(message)
		return text_type(message)
	except Exception:
		try:
			return text_type(repr(message))
		except Exception:
			return u"<unprintable>" if PY2 else "<unprintable>"


def c4d_print(message):
	"""在 C4D 中优先使用 GePrint，兼容外部环境，并对编码问题做降级处理。"""
	msg = _to_text(message)
	if C4D_AVAILABLE and hasattr(c4d, "GePrint"):
		try:
			c4d.GePrint(msg)
			return
		except Exception:
			# 编码失败时降级为 ASCII 打印
			try:
				if PY2:
					fallback = msg.encode("ascii", "replace")
					c4d.GePrint(fallback)
				else:
					c4d.GePrint(msg.encode("ascii", errors="replace").decode("ascii"))
				return
			except Exception:
				pass
	try:
		print(msg)
	except Exception:
		# 最后兜底：尽量输出 repr
		print(repr(msg))



def show_dialog(text):
	"""在 C4D 弹出一个提示对话框，确保用户能看到脚本结果。"""
	if C4D_AVAILABLE and hasattr(c4d, "gui"):
		try:
			c4d.gui.MessageDialog(text)
			return
		except Exception:
			pass
	# 回退到控制台输出
	c4d_print(text)



def _safe_getattr(obj, name, default=None):
	try:
		return getattr(obj, name)
	except Exception:
		return default


def _safe_call(obj, method_name, default=None):
	"""安全调用对象方法；不存在或异常则返回 default。"""
	fn = _safe_getattr(obj, method_name)
	if fn is None:
		return default
	try:
		return fn()
	except Exception:
		return default


def _status_to_str(status):
	if not C4D_AVAILABLE:
		return "unknown"
	try:
		pending = _safe_getattr(c4d, "RENDERQUEUE_STATUS_PENDING")
		rendering = _safe_getattr(c4d, "RENDERQUEUE_STATUS_RENDERING")
		completed = _safe_getattr(c4d, "RENDERQUEUE_STATUS_COMPLETED")
		failed = _safe_getattr(c4d, "RENDERQUEUE_STATUS_FAILED")
		paused = _safe_getattr(c4d, "RENDERQUEUE_STATUS_PAUSED")

		if pending is not None and status == pending:
			return "pending"
		if rendering is not None and status == rendering:
			return "running"
		if completed is not None and status == completed:
			return "completed"
		if failed is not None and status == failed:
			return "failed"
		if paused is not None and status == paused:
			return "paused"
	except Exception:
		pass
	return "unknown"


def _detect_render_activity_without_queue(window_seconds=15):
	"""在拿不到 RenderQueue 对象时，尝试用日志文件的最近更新时间判断是否可能在渲染。

	注意：这只是兜底启发式判断。
	"""
	result = {
		"log_dir": "",
		"checked_files": [],
		"recent_files": [],
		"window_seconds": window_seconds,
	}
	if not C4D_AVAILABLE:
		return result

	try:
		prefs_path = None
		try:
			prefs_path = c4d.storage.GeGetC4DPath(c4d.C4D_PATH_PREFS)
		except Exception:
			prefs_path = None

		if not prefs_path:
			return result

		log_dir = os.path.join(prefs_path, "logs")
		result["log_dir"] = log_dir
		if not os.path.isdir(log_dir):
			return result

		possible_names = [
			"render.log",
			"c4d_render.log",
			"render_queue.log",
			"renderqueue.log",
			"console.log",
			"c4d.log",
		]

		candidates = []
		for name in possible_names:
			p = os.path.join(log_dir, name)
			if os.path.isfile(p):
				candidates.append(p)

		# 如果没找到常见文件名，就退化为扫描 .log
		if not candidates:
			try:
				for fn in os.listdir(log_dir):
					if fn.lower().endswith(".log"):
						p = os.path.join(log_dir, fn)
						if os.path.isfile(p):
							candidates.append(p)
			except Exception:
				pass

		now = time.time()
		result["checked_files"] = candidates[:]
		recent = []
		for p in candidates:
			try:
				mtime = os.path.getmtime(p)
				if now - mtime <= float(window_seconds):
					recent.append(p)
			except Exception:
				continue
		result["recent_files"] = recent
		return result
	except Exception:
		return result



def _status_icon(s):
	# 旧版 Py2 控制台/GePrint 对 emoji 支持不稳定，默认用 ASCII；
	# 若你确认 C4D 版本/字体支持，可把这些符号换回 emoji。
	return {
		"pending": "...",
		"running": ">>",
		"completed": "OK",
		"failed": "!!",
		"paused": "||",
		"unknown": "?",
	}.get(s, "?")


def _is_running_job(status_str, progress):
	"""判断任务是否正在执行。

	优先用 status；若 status 不可靠，则用 progress(0..100) 兜底。
	"""
	try:
		if status_str == "running":
			return True
	except Exception:
		pass
	try:
		p = float(progress)
		# progress 一般 0..100；在渲染中通常会介于其间
		if p > 0.0 and p < 100.0:
			return True
	except Exception:
		pass
	return False



def get_render_queue_info():
	"""读取渲染队列的信息摘要和任务详情。需要在 C4D 环境中运行。"""
	if not C4D_AVAILABLE:
		return None

	try:
		rq = None
		# 部分版本提供全局 RenderQueue
		if documents is not None and hasattr(documents, "GetRenderQueue"):
			rq = documents.GetRenderQueue()
		# 兜底：尝试从活动文档获取（不同版本 API 可能不同）
		if rq is None and documents is not None and hasattr(documents, "GetActiveDocument"):
			doc = documents.GetActiveDocument()
			if doc is not None and hasattr(doc, "GetRenderQueue"):
				rq = doc.GetRenderQueue()
		if rq is None:
			# 某些情况下（例如使用外部 Maxon Render Queue/命令行渲染，或队列组件未加载），
			# C4D 内部 API 可能拿不到 RenderQueue 对象。
			fallback = _detect_render_activity_without_queue(window_seconds=15)
			return {
				"queue_available": False,
				"total_jobs": 0,
				"completed_jobs": 0,
				"failed_jobs": 0,
				"running_jobs": 0,
				"pending_jobs": 0,
				"is_rendering": True if fallback.get("recent_files") else False,
				"running_job_names": [],
				"jobs": [],
				"fallback": fallback,
			}

		job_count = _safe_call(rq, "GetJobCount", 0) or 0
		info = {
			"queue_available": True,
			"total_jobs": job_count,
			"completed_jobs": 0,
			"failed_jobs": 0,
			"running_jobs": 0,
			"pending_jobs": 0,
			"is_rendering": False,
			"running_job_names": [],
			"jobs": [],
		}

		for i in range(job_count):
			try:
				job = rq.GetJob(i)
			except Exception:
				job = None
			if job is None:
				continue

			try:
				status_str = _status_to_str(_safe_call(job, "GetStatus"))
				name = _safe_call(job, "GetName", "") or ""
				progress = _safe_call(job, "GetProgress")
				# C4D 的进度通常是 0..1，这里统一成 0..100
				try:
					progress = float(progress) * 100.0
				except Exception:
					progress = 0.0
				render_time = _safe_call(job, "GetRenderTime")
				try:
					render_time = float(render_time)
				except Exception:
					render_time = 0.0

				# 不同版本字段名可能不同，逐个尝试
				output_path = (
					_safe_call(job, "GetOutputPath")
					or _safe_call(job, "GetDestination")
					or _safe_call(job, "GetPath")
					or ""
				)
				frame_from = _safe_call(job, "GetFrameFrom")
				frame_to = _safe_call(job, "GetFrameTo")
				last_message = _safe_call(job, "GetLastMessage", "") or ""

				is_running = _is_running_job(status_str, progress)

				job_info = {
					"index": i,
					"name": name,
					"status": status_str,
					"progress": progress,
					"render_time": render_time,
					"output_path": output_path,
					"frame_from": frame_from,
					"frame_to": frame_to,
					"last_message": last_message,
					"is_running": is_running,
				}
				info["jobs"].append(job_info)

				if status_str == "completed":
					info["completed_jobs"] += 1
				elif status_str == "failed":
					info["failed_jobs"] += 1
				elif status_str == "running":
					info["running_jobs"] += 1
				elif status_str == "pending":
					info["pending_jobs"] += 1

				# 兜底统计：如果 status 没报 running，但 progress 显示在跑，也算“正在执行”
				if is_running:
					info["is_rendering"] = True
					try:
						info["running_job_names"].append(name)
					except Exception:
						pass
			except Exception:
				# 某个任务读信息失败时，跳过但不影响其它任务
				continue

		return info
	except Exception as e:
		c4d_print("获取渲染队列信息时出错: {0}".format(e))
		return None



def print_queue(info):
	c4d_print("\n" + "=" * 60)
	c4d_print(" C4D 渲染队列状态")
	c4d_print("=" * 60)
	if not info.get("queue_available", True):
		c4d_print("RenderQueue: 不可用（API 未返回队列对象）")
		c4d_print("是否正在执行(兜底判断): {0}".format("是" if info.get("is_rendering") else "否"))
		fb = info.get("fallback") or {}
		try:
			log_dir = fb.get("log_dir")
			recent = fb.get("recent_files") or []
			win = fb.get("window_seconds")
			if log_dir:
				c4d_print("日志目录: {0}".format(log_dir))
			if recent:
				c4d_print("最近 {0}s 内更新的日志: {1}".format(win, "; ".join([os.path.basename(x) for x in recent[:5]])))
			else:
				c4d_print("最近 {0}s 内未检测到日志更新".format(win))
		except Exception:
			pass
		c4d_print("提示：如果你在用外部 Maxon Render Queue/命令行渲染，这里无法直接列出队列任务。")
		return

	c4d_print("总任务数: {0}".format(info.get("total_jobs", 0)))
	c4d_print("已完成: {0}".format(info.get("completed_jobs", 0)))
	c4d_print("失败: {0}".format(info.get("failed_jobs", 0)))
	c4d_print("运行中: {0}".format(info.get("running_jobs", 0)))
	c4d_print("等待中: {0}".format(info.get("pending_jobs", 0)))
	c4d_print("是否正在执行: {0}".format("是" if info.get("is_rendering") else "否"))
	try:
		rn = info.get("running_job_names", [])
		if rn:
			c4d_print("正在执行任务: {0}".format("; ".join([_to_text(x) for x in rn[:5]])))
			if len(rn) > 5:
				c4d_print("... 以及 {0} 个".format(len(rn) - 5))
	except Exception:
		pass

	for job in info.get("jobs", []):
		status = job.get("status", "unknown")
		icon = _status_icon(status)
		c4d_print("")
		c4d_print("{0} 任务 {1}: {2}".format(icon, job.get("index", 0) + 1, job.get("name", "")))
		c4d_print("   状态: {0}".format(status))
		try:
			c4d_print("   进度: {0:.1f}%".format(float(job.get("progress", 0.0))))
		except Exception:
			pass
		try:
			rt = float(job.get("render_time", 0.0))
			if rt > 0:
				c4d_print("   渲染时间: {0:.2f} 秒".format(rt))
		except Exception:
			pass

		ff = job.get("frame_from")
		ft = job.get("frame_to")
		if ff is not None and ft is not None and ff != ft:
			c4d_print("   帧范围: {0} - {1}".format(ff, ft))

		op = job.get("output_path")
		if op:
			c4d_print("   输出路径: {0}".format(op))

		lm = job.get("last_message")
		if lm:
			c4d_print("   最后消息: {0}".format(lm))



def main():
	c4d_print("C4D 渲染队列状态查看器")
	c4d_print("-" * 60)

	if not C4D_AVAILABLE:
		c4d_print("此脚本需要在 Cinema 4D 的 Python 解释器中运行。")
		return

	info = get_render_queue_info()
	if not info:
		msg = "未找到渲染队列或队列为空。\n\n提示：打开脚本控制台(Shift+F10)可查看详细输出。"
		c4d_print(msg)
		show_dialog(msg)
		return

	# 如果队列对象不可用，就走兜底信息展示（不要直接提示“未找到队列”）
	if not info.get("queue_available", True):
		print_queue(info)
		lines = [
			"渲染队列状态",
			"RenderQueue: 不可用（API 未返回队列对象）",
			"是否正在执行(兜底判断): {0}".format("是" if info.get("is_rendering") else "否"),
		]
		fb = info.get("fallback") or {}
		try:
			log_dir = fb.get("log_dir")
			recent = fb.get("recent_files") or []
			win = fb.get("window_seconds")
			if log_dir:
				lines.append("日志目录: {0}".format(log_dir))
			if recent:
				lines.append("最近 {0}s 内更新: {1}".format(win, "; ".join([os.path.basename(x) for x in recent[:3]])))
			else:
				lines.append("最近 {0}s 内未检测到日志更新".format(win))
		except Exception:
			pass
		lines.append("\n提示：如果你在用外部 Maxon Render Queue/命令行渲染，C4D Python 无法直接列出队列任务。")
		show_dialog("\n".join(lines) + "\n\n详细信息已输出到控制台(Shift+F10)")
		return

	print_queue(info)

	# 弹窗简要汇总，避免用户未打开控制台时“无反应”
	summary_lines = [
		"渲染队列状态",
		"总任务数: {0}".format(info.get("total_jobs", 0)),
		"已完成: {0}  失败: {1}".format(info.get("completed_jobs", 0), info.get("failed_jobs", 0)),
		"运行中: {0}  等待中: {1}".format(info.get("running_jobs", 0), info.get("pending_jobs", 0)),
		"是否正在执行: {0}".format("是" if info.get("is_rendering") else "否"),
	]
	try:
		rn = info.get("running_job_names", [])
		if rn:
			summary_lines.append("正在执行: {0}".format("; ".join([_to_text(x) for x in rn[:3]])))
			if len(rn) > 3:
				summary_lines.append("... 以及 {0} 个".format(len(rn) - 3))
	except Exception:
		pass
	# 展示最多前3个任务的简要状态
	jobs = info.get("jobs", [])
	if jobs:
		for j in jobs[:3]:
			name = j.get("name", "")
			status = j.get("status", "unknown")
			try:
				prog = float(j.get("progress", 0.0))
				summary_lines.append("- {0} | {1} | {2:.0f}%".format(name, status, prog))
			except Exception:
				summary_lines.append("- {0} | {1}".format(name, status))
		if len(jobs) > 3:
			summary_lines.append("... 以及 {0} 个任务".format(len(jobs) - 3))

	show_dialog("\n".join(summary_lines) + "\n\n详细信息已输出到控制台(Shift+F10)")

	# 在状态栏也显示一条简短提示
	if C4D_AVAILABLE and hasattr(c4d, "StatusSetText"):
		try:
			c4d.StatusSetText("渲染队列状态已输出到控制台")
			c4d.EventAdd()
		except Exception:
			pass


if __name__ == "__main__":
	# 确保任何错误都会被输出到控制台，避免“没反应”的体验
	try:
		main()
	except Exception:
		c4d_print("[错误] 脚本执行失败：")
		c4d_print(traceback.format_exc())

# 在 C4D 脚本管理器中运行时也调用一次（某些上下文下 __name__ 可能不是 __main__）
if C4D_AVAILABLE and __name__ != "__main__":
	try:
		main()
	except Exception:
		c4d_print("[错误] 脚本执行失败：")
		c4d_print(traceback.format_exc())

