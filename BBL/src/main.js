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
		hud.setStatus(
			"你正在用 file:// 方式打开。浏览器通常会拦截 glb 加载；请用本地服务器打开： http://127.0.0.1:8000/GAME.HTML"
		);
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
