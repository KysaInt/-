(function () {
	window.AYE48 = window.AYE48 || {};
	window.AYE48.Config = {
		modelUrl: new URL("assets/models/48.glb", window.location.href).toString(),
		ui: {
			title: "48.glb 展示",
		},
		camera: {
			startPos: { x: 0, y: 1.6, z: -6 },
			pitchMin: -1.2,
			pitchMax: 1.2,
		},
		ground: {
			y: -0.02,
			width: 2000,
			height: 2000,
			followStep: 10,
			gridRatio: 1,
			majorUnitFrequency: 10,
		},
		movement: {
			mouseTurn: 0.008,
			wheelStep: 0.6,
			moveSpeed: 6,
			jumpVel: 5.2,
			gravity: 12.0,
		},
		prop: {
			baseHeightFactor: 2 / 3,
			rotationSpeed: 0.6,
			bobAmplitudeFactor: 0.08,
			bobFrequency: 1.0,
		},
	};
})();
