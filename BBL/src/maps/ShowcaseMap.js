(function () {
	window.AYE48 = window.AYE48 || {};
	window.AYE48.Maps = window.AYE48.Maps || {};

	async function createShowcaseMap(engine, canvas, hud, config) {
		const scene = new BABYLON.Scene(engine);
		scene.clearColor = new BABYLON.Color4(0.04, 0.06, 0.1, 1);

		// Lights + shadows
		const hemi = new BABYLON.HemisphericLight("hemi", new BABYLON.Vector3(0, 1, 0), scene);
		hemi.intensity = 0.55;

		const dir = new BABYLON.DirectionalLight("dir", new BABYLON.Vector3(-0.4, -1.0, 0.6), scene);
		dir.intensity = 1.1;

		const shadowGen = new BABYLON.ShadowGenerator(2048, dir);
		shadowGen.useBlurExponentialShadowMap = true;
		shadowGen.blurKernel = 16;

		scene.environmentIntensity = 0.9;

		// Actors
		const cameraActor = new window.AYE48.Actors.CameraActor(scene, config);
		scene.activeCamera = cameraActor.camera;

		const groundActor = new window.AYE48.Actors.GroundActor(scene, config);

		const model = await window.AYE48.Actors.loadModel(scene, shadowGen, config.modelUrl, hud.setStatus);

		// 自动取景（放在模型居中贴地之后）
		try {
			cameraActor.camera.position = new BABYLON.Vector3(
				0,
				model.centeredCenter.y + Math.max(1.2, model.radius * 0.35),
				-Math.max(3.5, model.radius * 2.2)
			);
			cameraActor.baseY = cameraActor.camera.position.y;
			cameraActor.lookAt(model.centeredCenter);
		} catch {
			// ignore
		}

		// 通用物件蓝图：基础高度(≈相机高度2/3) + 自转 + 上下浮动
		const propBP = new window.AYE48.Blueprints.PropActorBP(
			model.root,
			cameraActor,
			model.centeredCenter,
			config
		);
		// 抬高/浮动后，重新对准视线并保存复位点
		cameraActor.lookAt(propBP.getSuggestedLookTarget());
		cameraActor.saveSpawn();

		const controller = new window.AYE48.Blueprints.PlayerControllerBP(
			scene,
			canvas,
			cameraActor,
			hud,
			config
		);

		hud.wireReset(() => cameraActor.resetToSpawn());

		hud.setStatus(`加载完成：mesh ${model.result.meshes.length} / materials ${scene.materials.length}`);

		const start = performance.now();
		scene.onBeforeRenderObservable.add(() => {
			const dt = engine.getDeltaTime() / 1000;
			hud.setFps(`${engine.getFps().toFixed(0)} fps`);

			groundActor.followCamera(cameraActor.camera.position);
			propBP.tick(dt);
			controller.tick(dt);
		});

		return { scene, cameraActor, model, groundActor, controller, propBP };
	}

	window.AYE48.Maps.createShowcaseMap = createShowcaseMap;
})();
