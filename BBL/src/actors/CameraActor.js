(function () {
	window.AYE48 = window.AYE48 || {};
	window.AYE48.Actors = window.AYE48.Actors || {};

	function CameraActor(scene, config) {
		this.scene = scene;
		this.config = config;

		const start = config.camera.startPos;
		this.camera = new BABYLON.UniversalCamera(
			"camera",
			new BABYLON.Vector3(start.x, start.y, start.z),
			scene
		);
		this.camera.minZ = 0.02;
		this.camera.maxZ = 5000;

		try {
			this.camera.inputs.clear();
		} catch {
			// ignore
		}

		this.yaw = 0;
		this.pitch = 0.1;
		this.pitchMin = config.camera.pitchMin;
		this.pitchMax = config.camera.pitchMax;

		this.baseY = this.camera.position.y;
		this.verticalVel = 0;
		this.grounded = true;
		this.jumpLatch = false;

		this.spawnPos = this.camera.position.clone();
		this.spawnYaw = this.yaw;
		this.spawnPitch = this.pitch;
		this.spawnBaseY = this.baseY;

		this.applyRotation();
	}

	CameraActor.prototype.applyRotation = function () {
		this.camera.rotation.x = this.pitch;
		this.camera.rotation.y = this.yaw;
		this.camera.rotation.z = 0;
	};

	CameraActor.prototype.clampPitch = function () {
		this.pitch = Math.max(this.pitchMin, Math.min(this.pitchMax, this.pitch));
	};

	CameraActor.prototype.saveSpawn = function () {
		this.spawnPos = this.camera.position.clone();
		this.spawnYaw = this.yaw;
		this.spawnPitch = this.pitch;
		this.spawnBaseY = this.baseY;
	};

	CameraActor.prototype.resetToSpawn = function () {
		this.camera.position.copyFrom(this.spawnPos);
		this.yaw = this.spawnYaw;
		this.pitch = this.spawnPitch;
		this.baseY = this.spawnBaseY;
		this.verticalVel = 0;
		this.grounded = true;
		this.jumpLatch = false;
		this.applyRotation();
	};

	CameraActor.prototype.lookAt = function (target) {
		const toCenter = target.subtract(this.camera.position).normalize();
		this.yaw = Math.atan2(toCenter.x, toCenter.z);
		this.pitch = Math.asin(toCenter.y);
		this.clampPitch();
		this.applyRotation();
	};

	CameraActor.prototype.getForwardRight = function () {
		const forward = new BABYLON.Vector3(Math.sin(this.yaw), 0, Math.cos(this.yaw));
		const right = new BABYLON.Vector3(Math.cos(this.yaw), 0, -Math.sin(this.yaw));
		return { forward, right };
	};

	window.AYE48.Actors.CameraActor = CameraActor;
})();
