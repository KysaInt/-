using UnityEngine;

[DisallowMultipleComponent]
[AddComponentMenu("AYE导出/基础组件/场景相机控制器")]
public class AyeExportCameraController : MonoBehaviour
{
    [Header("General")]
    public bool controllerEnabled = true;
    public bool requireRightMouse = false;

    [Header("Movement")]
    public float moveSpeed = 10f;
    public float sprintMultiplier = 3f;

    [Header("Perspective")]
    public float lookSensitivity = 2.5f;
    public float perspectivePanSpeed = 6f;

    [Header("Orthographic")]
    public float orthographicPanSpeed = 8f;
    public float orthographicDragSpeed = 1f;
    public float orthographicZoomSpeed = 2f;
    public float orthographicMinSize = 2f;
    public float orthographicMaxSize = 400f;

    private Camera _cachedCamera;
    private float _yaw;
    private float _pitch;
    private bool _isOrthographicDragging;
    private bool _isPerspectiveDragging;
    private Vector3 _lastDragMousePosition;

    private void Awake()
    {
        _cachedCamera = GetComponent<Camera>();
        Vector3 euler = transform.eulerAngles;
        _yaw = euler.y;
        _pitch = NormalizePitch(euler.x);
    }

    private void Update()
    {
        if (!Application.isPlaying || !controllerEnabled)
        {
            _isOrthographicDragging = false;
            _isPerspectiveDragging = false;
            return;
        }

        Camera cam = GetControlledCamera();
        if (cam == null)
        {
            return;
        }

        if (cam.orthographic)
        {
            UpdateOrthographicCamera(cam);
            return;
        }

        UpdatePerspectiveCamera();
    }

    private Camera GetControlledCamera()
    {
        if (_cachedCamera == null)
        {
            _cachedCamera = GetComponent<Camera>();
        }
        return _cachedCamera != null ? _cachedCamera : Camera.main;
    }

    private void UpdatePerspectiveCamera()
    {
        UpdateMovement(transform.forward, transform.right, transform.up);
        UpdatePerspectiveLook();
        UpdatePerspectivePan();
    }

    private void UpdateOrthographicCamera(Camera cam)
    {
        UpdateOrthographicKeyboardPan(cam);
        UpdateOrthographicZoom(cam);
        UpdateOrthographicDrag(cam);
    }

    private void UpdateMovement(Vector3 forward, Vector3 right, Vector3 up)
    {
        float speed = moveSpeed * ((Input.GetKey(KeyCode.LeftShift) || Input.GetKey(KeyCode.RightShift)) ? sprintMultiplier : 1f);
        Vector3 moveDirection = Vector3.zero;
        if (Input.GetKey(KeyCode.W)) moveDirection += forward;
        if (Input.GetKey(KeyCode.S)) moveDirection -= forward;
        if (Input.GetKey(KeyCode.D)) moveDirection += right;
        if (Input.GetKey(KeyCode.A)) moveDirection -= right;
        if (Input.GetKey(KeyCode.E)) moveDirection += up;
        if (Input.GetKey(KeyCode.Q)) moveDirection -= up;
        if (moveDirection.sqrMagnitude > 0f)
        {
            transform.position += moveDirection.normalized * speed * Time.unscaledDeltaTime;
        }
    }

    private void UpdatePerspectiveLook()
    {
        bool lookHeld = Input.GetMouseButton(1);
        if (requireRightMouse && !lookHeld)
        {
            return;
        }

        if (!requireRightMouse && !lookHeld && !Input.GetMouseButton(0))
        {
            return;
        }

        float mouseX = Input.GetAxisRaw("Mouse X");
        float mouseY = -Input.GetAxisRaw("Mouse Y");
        _yaw += mouseX * lookSensitivity;
        _pitch = Mathf.Clamp(_pitch + mouseY * lookSensitivity, -89f, 89f);
        transform.rotation = Quaternion.Euler(_pitch, _yaw, 0f);
    }

    private void UpdatePerspectivePan()
    {
        bool dragHeld = Input.GetMouseButton(2);
        bool dragStarted = Input.GetMouseButtonDown(2);
        bool dragEnded = Input.GetMouseButtonUp(2);
        if (dragStarted)
        {
            _isPerspectiveDragging = true;
            _lastDragMousePosition = Input.mousePosition;
        }
        if (!dragHeld || dragEnded)
        {
            _isPerspectiveDragging = false;
            return;
        }
        if (!_isPerspectiveDragging)
        {
            return;
        }
        Vector3 delta = Input.mousePosition - _lastDragMousePosition;
        Vector3 pan = (-transform.right * delta.x + -transform.up * delta.y) * perspectivePanSpeed * Time.unscaledDeltaTime;
        transform.position += pan;
        _lastDragMousePosition = Input.mousePosition;
    }

    private void UpdateOrthographicKeyboardPan(Camera cam)
    {
        Vector3 move = Vector3.zero;
        if (Input.GetKey(KeyCode.W)) move += Vector3.up;
        if (Input.GetKey(KeyCode.S)) move += Vector3.down;
        if (Input.GetKey(KeyCode.D)) move += Vector3.right;
        if (Input.GetKey(KeyCode.A)) move += Vector3.left;
        if (move.sqrMagnitude <= 0f)
        {
            return;
        }
        float speed = orthographicPanSpeed * cam.orthographicSize * 0.08f;
        transform.position += move.normalized * speed * Time.unscaledDeltaTime;
    }

    private void UpdateOrthographicZoom(Camera cam)
    {
        float scroll = Input.mouseScrollDelta.y;
        if (Mathf.Abs(scroll) <= 0.001f)
        {
            return;
        }
        float sizeStep = Mathf.Max(0.1f, cam.orthographicSize * 0.12f) * orthographicZoomSpeed;
        cam.orthographicSize = Mathf.Clamp(cam.orthographicSize - scroll * sizeStep, orthographicMinSize, orthographicMaxSize);
    }

    private void UpdateOrthographicDrag(Camera cam)
    {
        bool dragHeld = Input.GetMouseButton(0) || Input.GetMouseButton(2);
        bool dragStarted = Input.GetMouseButtonDown(0) || Input.GetMouseButtonDown(2);
        bool dragEnded = Input.GetMouseButtonUp(0) || Input.GetMouseButtonUp(2);
        if (dragStarted)
        {
            _isOrthographicDragging = true;
            _lastDragMousePosition = Input.mousePosition;
        }
        if (!dragHeld || dragEnded)
        {
            _isOrthographicDragging = false;
            return;
        }
        if (!_isOrthographicDragging)
        {
            return;
        }
        Vector3 delta = Input.mousePosition - _lastDragMousePosition;
        float scale = cam.orthographicSize / Mathf.Max(1f, Screen.height) * 2f * orthographicDragSpeed;
        transform.position += new Vector3(-delta.x * scale, -delta.y * scale, 0f);
        _lastDragMousePosition = Input.mousePosition;
    }

    private static float NormalizePitch(float x)
    {
        x %= 360f;
        if (x > 180f)
        {
            x -= 360f;
        }
        return x;
    }
}
