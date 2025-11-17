#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cinema 4D 渲染队列状态查看器

在 C4D 脚本管理器中运行，输出当前渲染队列的渲染相关信息：
- 队列统计（总数、完成、失败、运行中、等待中）
- 每个任务的名称、状态、进度、渲染时间、帧范围、输出路径、最后消息

用法：
1) 在 C4D 中：脚本 > 脚本管理器 > 打开本文件 > 执行
2) 若在非 C4D 环境运行，将提示需要在 C4D 中执行
"""

from __future__ import annotations

import sys
import traceback
from typing import Any, Dict, List, Optional

# 检测 C4D Python 环境
try:
	import c4d
	from c4d import documents
	C4D_AVAILABLE = True
except Exception:
	c4d = None  # type: ignore
	documents = None  # type: ignore
	C4D_AVAILABLE = False


def c4d_print(message: Any) -> None:
	"""在 C4D 中优先使用 GePrint，兼容外部环境，并对编码问题做降级处理。"""
	msg = str(message)
	if C4D_AVAILABLE and hasattr(c4d, "GePrint"):
		try:
			c4d.GePrint(msg)
			return
		except Exception:
			# 编码失败时降级为 ASCII 打印
			try:
				c4d.GePrint(msg.encode("ascii", errors="replace").decode("ascii"))
				return
			except Exception:
				pass
	print(msg)


def show_dialog(text: str) -> None:
	"""在 C4D 弹出一个提示对话框，确保用户能看到脚本结果。"""
	if C4D_AVAILABLE and hasattr(c4d, "gui"):
		try:
			c4d.gui.MessageDialog(text)
			return
		except Exception:
			pass
	# 回退到控制台输出
	c4d_print(text)


def _status_to_str(status: int) -> str:
	if not C4D_AVAILABLE:
		return "unknown"
	try:
		if status == c4d.RENDERQUEUE_STATUS_PENDING:
			return "pending"
		if status == c4d.RENDERQUEUE_STATUS_RENDERING:
			return "running"
		if status == c4d.RENDERQUEUE_STATUS_COMPLETED:
			return "completed"
		if status == c4d.RENDERQUEUE_STATUS_FAILED:
			return "failed"
		if status == c4d.RENDERQUEUE_STATUS_PAUSED:
			return "paused"
	except Exception:
		pass
	return "unknown"


def _status_icon(s: str) -> str:
	return {
		"pending": "⏳",
		"running": "",
		"completed": "✅",
		"failed": "❌",
		"paused": "⏸️",
		"unknown": "❓",
	}.get(s, "❓")


def get_render_queue_info() -> Optional[Dict[str, Any]]:
	"""读取渲染队列的信息摘要和任务详情。需要在 C4D 环境中运行。"""
	if not C4D_AVAILABLE:
		return None

	try:
		rq = documents.GetRenderQueue()
		if rq is None:
			return None

		job_count = rq.GetJobCount()
		info: Dict[str, Any] = {
			"total_jobs": job_count,
			"completed_jobs": 0,
			"failed_jobs": 0,
			"running_jobs": 0,
			"pending_jobs": 0,
			"jobs": [],  # type: List[Dict[str, Any]]
		}

		for i in range(job_count):
			job = rq.GetJob(i)
			if job is None:
				continue

			try:
				status_str = _status_to_str(job.GetStatus())
				job_info = {
					"index": i,
					"name": job.GetName(),
					"status": status_str,
					"progress": float(job.GetProgress()),
					"render_time": float(job.GetRenderTime()),
					"output_path": job.GetOutputPath(),
					"frame_from": job.GetFrameFrom(),
					"frame_to": job.GetFrameTo(),
					"last_message": job.GetLastMessage(),
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
			except Exception:
				# 某个任务读信息失败时，跳过但不影响其它任务
				continue

		return info
	except Exception as e:
		c4d_print(f"获取渲染队列信息时出错: {e}")
		return None


def print_queue(info: Dict[str, Any]) -> None:
	c4d_print("\n" + "=" * 60)
	c4d_print(" C4D 渲染队列状态")
	c4d_print("=" * 60)
	c4d_print(f"总任务数: {info['total_jobs']}")
	c4d_print(f"✅ 已完成: {info['completed_jobs']}")
	c4d_print(f"❌ 失败: {info['failed_jobs']}")
	c4d_print(f" 运行中: {info['running_jobs']}")
	c4d_print(f"⏳ 等待中: {info['pending_jobs']}")

	for job in info.get("jobs", []):
		status = job.get("status", "unknown")
		icon = _status_icon(status)
		c4d_print("")
		c4d_print(f"{icon} 任务 {job['index'] + 1}: {job.get('name', '')}")
		c4d_print(f"   状态: {status}")
		try:
			c4d_print(f"   进度: {job.get('progress', 0.0):.1f}%")
		except Exception:
			pass
		try:
			rt = float(job.get("render_time", 0.0))
			if rt > 0:
				c4d_print(f"   渲染时间: {rt:.2f} 秒")
		except Exception:
			pass

		ff = job.get("frame_from")
		ft = job.get("frame_to")
		if ff is not None and ft is not None and ff != ft:
			c4d_print(f"   帧范围: {ff} - {ft}")

		op = job.get("output_path")
		if op:
			c4d_print(f"   输出路径: {op}")

		lm = job.get("last_message")
		if lm:
			c4d_print(f"   最后消息: {lm}")


def main() -> None:
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

	print_queue(info)

	# 弹窗简要汇总，避免用户未打开控制台时“无反应”
	summary_lines = [
		"渲染队列状态",
		f"总任务数: {info['total_jobs']}",
		f"已完成: {info['completed_jobs']}  失败: {info['failed_jobs']}",
		f"运行中: {info['running_jobs']}  等待中: {info['pending_jobs']}",
	]
	# 展示最多前3个任务的简要状态
	jobs = info.get("jobs", [])
	if jobs:
		for j in jobs[:3]:
			name = j.get("name", "")
			status = j.get("status", "unknown")
			try:
				prog = float(j.get("progress", 0.0))
				summary_lines.append(f"- {name} | {status} | {prog:.0f}%")
			except Exception:
				summary_lines.append(f"- {name} | {status}")
		if len(jobs) > 3:
			summary_lines.append(f"... 以及 {len(jobs)-3} 个任务")

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

