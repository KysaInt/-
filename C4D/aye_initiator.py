# -*- coding: utf-8 -*-
import c4d, os, sys, io, ssl, socket, urllib.request, zipfile, subprocess

ZIP_URL = "https://github.com/KysaInt/-/raw/main/C4D/AYE.zip"

def main():
    doc = c4d.documents.GetActiveDocument()
    if not doc or not doc.GetDocumentPath():
        print("错误：请先保存C4D文档"); return

    aye_dir  = os.path.join(doc.GetDocumentPath(), "AYE")
    main_pyw = os.path.join(aye_dir, "main.pyw")

    # --- 下载并解压（main.pyw 不存在时）---
    if not os.path.exists(main_pyw):
        print(f"下载 {ZIP_URL} ...")
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        socket.setdefaulttimeout(60)

        req = urllib.request.Request(ZIP_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, context=ctx, timeout=120) as r:
            data = r.read()
        print(f"下载完成 {len(data)//1024} KB，解压中...")

        def fix_name(info):
            n = info.filename
            if info.flag_bits & 0x800: return n
            try: return n.encode("cp437").decode("gbk")
            except: return n

        os.makedirs(aye_dir, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for info in z.infolist():
                name = fix_name(info).replace("\\", "/")
                if info.is_dir(): continue
                parts = name.split("/", 1)            # 剥掉 "AYE/" 前缀
                rel = parts[1] if len(parts) == 2 else parts[0]
                if not rel: continue
                dst = os.path.join(aye_dir, rel.replace("/", os.sep))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with z.open(info) as src, open(dst, "wb") as f:
                    f.write(src.read())
        print("解压完成")

    if not os.path.exists(main_pyw):
        print("错误：解压后找不到 main.pyw"); return

    # --- 找有 PySide6 的 Python 并启动 ---
    python = None
    for cmd in [sys.executable, "py", "python"]:
        try:
            r = subprocess.run([cmd, "-c", "import PySide6,sys;print(sys.executable)"],
                capture_output=True, text=True, timeout=8)
            if r.returncode == 0:
                python = r.stdout.strip(); break
        except: continue

    if not python:
        print("错误：找不到安装了 PySide6 的 Python"); return

    print(f"启动 {main_pyw}")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    subprocess.Popen([python, main_pyw], cwd=aye_dir, env=env,
                     stdin=subprocess.DEVNULL,
                     creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW)
    print("完成")

if __name__ == "__main__":
    main()
