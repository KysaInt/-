(function () {
	window.AYE48 = window.AYE48 || {};
	window.AYE48.Blueprints = window.AYE48.Blueprints || {};

	function PlayerControllerBP(scene, canvas, cameraActor, hud, config) {
		this.scene = scene;
		this.canvas = canvas;
		this.cameraActor = cameraActor;
		this.hud = hud;
		this.config = config;

		this.keysDown = new Set();
		this.isRightMouseDown = false;
		this.lastMouseX = 0;
		this.lastMouseY = 0;

		this._bindInputs();
	}

	PlayerControllerBP.prototype._bindInputs = function () {
		const canvas = this.canvas;
		const scene = this.scene;
		const cameraActor = this.cameraActor;
		const cfg = this.config;

		canvas.addEventListener("contextmenu", (e) => e.preventDefault());

		window.addEventListener("keydown", (e) => {
			const k = (e.key || "").toLowerCase();
			if (k === "w" || k === "a" || k === "s" || k === "d") {
				this.keysDown.add(k);
				e.preventDefault();
			}
			if (k === " ") {
				this.keysDown.add("space");
				e.preventDefault();
			}
		});

		window.addEventListener("keyup", (e) => {
			const k = (e.key || "").toLowerCase();
			if (k === " ") {
				this.keysDown.delete("space");
				return;
			}
			this.keysDown.delete(k);
		});

		scene.onPointerObservable.add((pointerInfo) => {
			const evt = pointerInfo.event;
			if (!evt) return;
			if (pointerInfo.type === BABYLON.PointerEventTypes.POINTERDOWN) {
				if (evt.button === 2) {
					this.isRightMouseDown = true;
					this.lastMouseX = evt.clientX;
					this.lastMouseY = evt.clientY;
				}
			}
			if (pointerInfo.type === BABYLON.PointerEventTypes.POINTERUP) {
				if (evt.button === 2) this.isRightMouseDown = false;
			}
			if (pointerInfo.type === BABYLON.PointerEventTypes.POINTERMOVE) {
				if (!this.isRightMouseDown) return;
				const dx = evt.clientX - this.lastMouseX;
				const dy = evt.clientY - this.lastMouseY;
				this.lastMouseX = evt.clientX;
				this.lastMouseY = evt.clientY;

				const mouseTurn = this.hud.getMouseTurn ? this.hud.getMouseTurn() : cfg.movement.mouseTurn;
				cameraActor.yaw += dx * mouseTurn;
				cameraActor.pitch += dy * mouseTurn;
				cameraActor.clampPitch();
				cameraActor.applyRotation();
			}
		});

		canvas.addEventListener(
			"wheel",
			(e) => {
				e.preventDefault();
				const delta = Math.sign(e.deltaY);
				const dir = cameraActor.camera.getDirection(BABYLON.Axis.Z);
				cameraActor.camera.position.addInPlace(dir.scale(delta * cfg.movement.wheelStep));
			},
			{ passive: false }
		);
	};

	PlayerControllerBP.prototype.tick = function (dt) {
		const ca = this.cameraActor;
		const { forward, right } = ca.getForwardRight();

		let move = BABYLON.Vector3.Zero();
		if (this.keysDown.has("w")) move.addInPlace(forward);
		if (this.keysDown.has("s")) move.addInPlace(forward.scale(-1));
		if (this.keysDown.has("d")) move.addInPlace(right);
		if (this.keysDown.has("a")) move.addInPlace(right.scale(-1));

		if (move.lengthSquared() > 1e-6) {
			move.normalize();
			const speed = this.hud.getMoveSpeed();
			ca.camera.position.addInPlace(move.scale(speed * dt));
		}

		const wantsJump = this.keysDown.has("space");
		if (wantsJump && !ca.jumpLatch && ca.grounded) {
			ca.verticalVel = this.config.movement.jumpVel;
			ca.grounded = false;
			ca.jumpLatch = true;
		}
		if (!wantsJump) ca.jumpLatch = false;

		if (!ca.grounded) {
			ca.verticalVel -= this.config.movement.gravity * dt;
			ca.camera.position.y += ca.verticalVel * dt;
			if (ca.camera.position.y <= ca.baseY) {
				ca.camera.position.y = ca.baseY;
				ca.verticalVel = 0;
				ca.grounded = true;
			}
		}
	};

	window.AYE48.Blueprints.PlayerControllerBP = PlayerControllerBP;
})();
