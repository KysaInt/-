import os
import sys
import subprocess
import importlib
import asyncio
from datetime import datetime


# 自动检查并安装 edge-tts，并处理同名脚本导致的导入冲突
def ensure_edge_tts():
	script_dir = os.path.dirname(os.path.abspath(__file__))
	removed_entry = None
	for idx, path in enumerate(list(sys.path)):
		if path in (script_dir, ""):
			removed_entry = (idx, path)
			del sys.path[idx]
			break
	if "edge_tts" in sys.modules and getattr(sys.modules["edge_tts"], "__file__", None) == __file__:
		del sys.modules["edge_tts"]
	try:
		return importlib.import_module("edge_tts")
	except ImportError:
		print("未检测到 edge-tts，正在自动安装……")
		subprocess.check_call([sys.executable, "-m", "pip", "install", "edge-tts"])
		if "edge_tts" in sys.modules and getattr(sys.modules["edge_tts"], "__file__", None) == __file__:
			del sys.modules["edge_tts"]
		return importlib.import_module("edge_tts")
	finally:
		if removed_entry is not None:
			sys.path.insert(*removed_entry)


edge_tts = ensure_edge_tts()

# 语音模型，可在 https://learn.microsoft.com/zh-cn/azure/ai-services/speech-service/language-support#text-to-speech 查询
VOICE = "zh-CN-XiaoxiaoNeural"  # 最新中文女声
OUTPUT_EXT = ".mp3"


# 兼容新版 edge-tts API
async def tts(text, voice, output):
	try:
		# 新版 edge-tts 推荐用 async_api.communicate
		from edge_tts import async_api
		communicate = async_api.Communicate(text, voice)
		print("    → 正在调用微软语音服务，文字较长时请耐心等待……", flush=True)
		await communicate.save(output)
	except Exception:
		# 兼容旧版
		communicate = edge_tts.Communicate(text, voice)
		print("    → 检测到旧版 edge-tts API，已切换兼容模式。", flush=True)
		await communicate.save(output)
	print(f"    ✓ 语音已保存到 {output}", flush=True)

async def main():
	dir_path = os.path.dirname(os.path.abspath(__file__))
	print("===============================", flush=True)
	print(" 微软 Edge TTS 文本转语音助手", flush=True)
	print("===============================", flush=True)
	print("1. 将需要转换的文本放在本目录的 .txt 文件中", flush=True)
	print("2. 每个 .txt 会生成同名的音频文件", flush=True)
	print("3. 处理过程中请保持窗口打开", flush=True)
	print("", flush=True)
	files = [f for f in os.listdir(dir_path) if f.lower().endswith('.txt')]
	if not files:
		print("未找到任何 .txt 文件！")
		return
	print("待处理的文本文件：", flush=True)
	for txt_file in files:
		print(f"  • {txt_file}", flush=True)
	print("", flush=True)
	for txt_file in files:
		txt_path = os.path.join(dir_path, txt_file)
		with open(txt_path, 'r', encoding='utf-8') as f:
			text = f.read().strip()
		if not text:
			print(f"{txt_file} 为空，跳过。")
			continue
		first_line = text.splitlines()[0] if text else ""
		preview = (first_line[:40] + "…") if len(first_line) > 40 else first_line
		print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始处理 {txt_file}", flush=True)
		if preview:
			print(f"    文本预览：{preview}", flush=True)
		output_file = os.path.splitext(txt_file)[0] + OUTPUT_EXT
		output_path = os.path.join(dir_path, output_file)
		await tts(text, VOICE, output_path)
		print("", flush=True)
	print("全部文本处理完毕！", flush=True)


if __name__ == "__main__":
	try:
		asyncio.run(main())
	except Exception as e:
		print(f"发生错误: {e}")
	input("\n任务完成，按回车键退出...")
