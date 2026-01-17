(function () {
	window.AYE48 = window.AYE48 || {};
	window.AYE48.Actors = window.AYE48.Actors || {};

	function _computeBounds(meshes) {
		let min = new BABYLON.Vector3(
			Number.POSITIVE_INFINITY,
			Number.POSITIVE_INFINITY,
			Number.POSITIVE_INFINITY
		);
		let max = new BABYLON.Vector3(
			Number.NEGATIVE_INFINITY,
			Number.NEGATIVE_INFINITY,
			Number.NEGATIVE_INFINITY
		);
		let hasBounds = false;

		for (const m of meshes) {
			if (!m || !m.isVisible || !m.getTotalVertices || m.getTotalVertices() <= 0) continue;
			m.computeWorldMatrix(true);
			const bi = m.getBoundingInfo && m.getBoundingInfo();
			if (!bi) continue;
			const bb = bi.boundingBox;
			min = BABYLON.Vector3.Minimize(min, bb.minimumWorld);
			max = BABYLON.Vector3.Maximize(max, bb.maximumWorld);
			hasBounds = true;
		}

		if (!hasBounds) return null;
		return { min, max };
	}

	async function loadModel(scene, shadowGen, modelUrl, setStatus) {
		// 一次性配置 glTF 所需解码器（draco/meshopt/ktx2），避免“模型能出但材质/贴图加载失败”
		if (!window.AYE48._decodersConfigured) {
			window.AYE48._decodersConfigured = true;
			try {
				if (window.BABYLON && BABYLON.DracoCompression) {
					BABYLON.DracoCompression.Configuration = BABYLON.DracoCompression.Configuration || {};
					BABYLON.DracoCompression.Configuration.decoder = {
						wasmUrl: "https://cdn.babylonjs.com/draco_wasm_wrapper_gltf.js",
						wasmBinaryUrl: "https://cdn.babylonjs.com/draco_decoder_gltf.wasm",
						fallbackUrl: "https://cdn.babylonjs.com/draco_decoder_gltf.js",
					};
				}
			} catch {
				// ignore
			}
			try {
				// meshopt_decoder.js 会提供全局 MeshoptDecoder
				if (window.BABYLON && BABYLON.MeshoptCompression && window.MeshoptDecoder) {
					BABYLON.MeshoptCompression.Configuration = BABYLON.MeshoptCompression.Configuration || {};
					BABYLON.MeshoptCompression.Configuration.decoder = window.MeshoptDecoder;
				}
			} catch {
				// ignore
			}
		}

		// 贴图加载错误提示（方便定位：通常是 ktx2/basisu 解码器缺失、file://、或资源路径）
		try {
			if (!scene.__aye48TextureErrHooked) {
				scene.__aye48TextureErrHooked = true;
				scene.onTextureLoadErrorObservable.add((tex) => {
					try {
						const name = (tex && (tex.name || tex.url)) || "<unknown>";
						setStatus && setStatus(`贴图加载失败：${name}`);
					} catch {
						// ignore
					}
				});
			}
		} catch {
			// ignore
		}

		const root = new BABYLON.TransformNode("root", scene);
		setStatus && setStatus("正在加载 48.glb …");

		const result = await BABYLON.SceneLoader.ImportMeshAsync(
			null,
			"",
			modelUrl,
			scene,
			(evt) => {
				if (!setStatus || !evt.lengthComputable) return;
				const pct = Math.round((evt.loaded / evt.total) * 100);
				setStatus(`正在加载 48.glb … ${pct}%`);
			}
		);

		const modelRoot = result.meshes.find((m) => m && m.name === "__root__") || result.meshes[0];
		if (modelRoot) {
			modelRoot.parent = root;
			for (const m of result.meshes) {
				if (!m || m === modelRoot) continue;
				if (m.parent == null) m.parent = modelRoot;
			}
		}

		let centeredCenter = new BABYLON.Vector3(0, 1.0, 0);
		let radius = 1.0;

		try {
			const meshes = modelRoot ? modelRoot.getChildMeshes(false) : root.getChildMeshes(false);
			const bounds = _computeBounds(meshes);
			if (bounds) {
				const { min, max } = bounds;
				const center = min.add(max).scale(0.5);
				const extents = max.subtract(min).scale(0.5);
				radius = Math.max(extents.x, extents.y, extents.z);

				if (modelRoot) {
					modelRoot.position.subtractInPlace(new BABYLON.Vector3(center.x, min.y, center.z));
				}

				centeredCenter = new BABYLON.Vector3(0, (max.y - min.y) * 0.5, 0);
			}
		} catch {
			// ignore
		}

		for (const m of root.getChildMeshes(false)) {
			if (m && m.getTotalVertices && m.getTotalVertices() > 0) {
				shadowGen.addShadowCaster(m, true);
			}
		}

		return {
			root,
			result,
			centeredCenter,
			radius,
		};
	}

	window.AYE48.Actors.loadModel = loadModel;
})();
