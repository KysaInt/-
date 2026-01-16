(function () {
	window.AYE48 = window.AYE48 || {};
	window.AYE48.Actors = window.AYE48.Actors || {};

	function GroundActor(scene, config) {
		this.scene = scene;
		this.config = config;

		const g = config.ground;
		this.ground = BABYLON.MeshBuilder.CreateGround(
			"ground",
			{ width: g.width, height: g.height, subdivisions: 2 },
			scene
		);
		this.ground.position.y = g.y;
		this.ground.receiveShadows = true;
		this.ground.isPickable = false;

		const gridMat = new BABYLON.GridMaterial("gridMat", scene);
		gridMat.opacity = 0.65;
		gridMat.gridRatio = g.gridRatio;
		gridMat.majorUnitFrequency = g.majorUnitFrequency;
		gridMat.minorUnitVisibility = 0.45;
		gridMat.mainColor = new BABYLON.Color3(0.12, 0.14, 0.18);
		gridMat.lineColor = new BABYLON.Color3(0.65, 0.7, 0.8);
		gridMat.majorUnitVisibility = 0.75;
		this.ground.material = gridMat;
	}

	GroundActor.prototype.followCamera = function (cameraPosition) {
		const step = this.config.ground.followStep;
		this.ground.position.x = Math.round(cameraPosition.x / step) * step;
		this.ground.position.z = Math.round(cameraPosition.z / step) * step;
	};

	window.AYE48.Actors.GroundActor = GroundActor;
})();
