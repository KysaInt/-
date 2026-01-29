(function () {
	const canvas = document.getElementById("renderCanvas");
	const hudRoot = document.getElementById("hud");
	const editorRoot = document.getElementById("editor");
	const config = window.AYE48.Config;

	const engine = new BABYLON.Engine(canvas, true, {
		preserveDrawingBuffer: true,
		stencil: true,
		disableWebGL2Support: false,
	});

	const hud = window.AYE48.UI.mountHud(hudRoot, config);
	if (editorRoot && window.AYE48.UI.mountEditorPanel) {
		window.AYE48.UI.mountEditorPanel(editorRoot, config, hud);
	}

	if (window.location.protocol === "file:") {
		const params = new URLSearchParams(window.location.search);
		const noRedirect = params.get("noRedirect") === "1";
		const port = parseInt(params.get("port") || "8000", 10) || 8000;
		const host = params.get("host") || "127.0.0.1";
		const candidateUrls = [`http://${host}:${port}/GAME.HTML`, `http://${host}:${port}/BBL/GAME.HTML`];

		async function probe(url, timeoutMs) {
			const ctrl = new AbortController();
			const t = setTimeout(() => ctrl.abort(), timeoutMs);
			try {
				// 从 file:// 发起到 http:// 的探测：只要 TCP 能连上，一般就会 resolve（即使 404）。
				await fetch(url, { method: "GET", cache: "no-store", signal: ctrl.signal, mode: "no-cors" });
				return true;
			} catch {
				return false;
			} finally {
				clearTimeout(t);
			}
		}

		async function autoRedirect() {
			for (const url of candidateUrls) {
				const ok = await probe(url, 1200);
				if (ok) return url;
			}
			return null;
		}

		if (!noRedirect) {
			hud.setStatus(
				`检测到 file:// 打开，正在尝试连接本地服务器（${host}:${port}）…（追加 ?noRedirect=1 可跳过）`
			);
			setTimeout(async () => {
				const target = await autoRedirect();
				if (target) {
					hud.setStatus(`已检测到本地服务器，正在跳转： ${target}`);
					try {
						window.location.href = target;
					} catch {
						// ignore
					}
					return;
				}
				hud.setStatus(
					[
						"未检测到本地服务器，无法自动跳转。你需要先启动一个静态服务器：",
						`1) 在 BBL 目录运行：python -m http.server ${port}  然后打开：${candidateUrls[0]}`,
						`2) 或在工作区根目录运行：python -m http.server ${port}  然后打开：${candidateUrls[1]}`,
						"（也可以改端口：例如 ?port=5500 或改主机：?host=localhost）",
					].join("\n")
				);
			}, 50);
		} else {
			hud.setStatus(
				[
					"你正在用 file:// 方式打开（已跳过自动跳转）。建议用本地服务器打开：",
						`- ${candidateUrls[0]}`,
						`- ${candidateUrls[1]}`,
				].join("\n")
			);
		}
	}

	(async () => {
		try {
			const map = await window.AYE48.Maps.createShowcaseMap(engine, canvas, hud, config);
			engine.runRenderLoop(() => map.scene.render());
		} catch (err) {
			console.error(err);
			hud.setStatus("加载失败：可能是浏览器拦截了 file:// 资源或模型路径不对。建议用本地服务器打开。");
		}
	})();

	window.addEventListener("resize", () => engine.resize());
})();
