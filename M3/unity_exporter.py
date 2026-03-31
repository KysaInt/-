from __future__ import annotations

import hashlib
import re
from pathlib import Path


FALLBACK_EXPORT_DIR = Path(__file__).parent / "exports" / "unity"
BUNDLED_UNITY_ASSETS_DIR = Path(__file__).parent / "exports" / "unity_validation_project" / "Assets"
BUNDLED_UNITY_SCRIPTS_DIR = BUNDLED_UNITY_ASSETS_DIR / "Scripts"
BUNDLED_UNITY_SHADERS_DIR = BUNDLED_UNITY_ASSETS_DIR / "Shaders"
REFERENCE_UNITY_SCRIPTS_DIR = BUNDLED_UNITY_SCRIPTS_DIR
REFERENCE_PY_STYLE_VISUALIZER = BUNDLED_UNITY_SCRIPTS_DIR / "PyStyleVisualizer.cs"
REFERENCE_WINDOWS_AUDIO_CAPTURE = BUNDLED_UNITY_SCRIPTS_DIR / "WindowsAudioCapture.cs"
REFERENCE_TENTACLE_SHADER = BUNDLED_UNITY_SHADERS_DIR / "AyeTentacleSoftLine.shader"

_REFERENCE_RUNTIME_FILES = {
    "PyStyleVisualizer.cs": REFERENCE_PY_STYLE_VISUALIZER,
    "WindowsAudioCapture.cs": REFERENCE_WINDOWS_AUDIO_CAPTURE,
}

_FIELD_KEY_OVERRIDES = {
    "rotationFollowsAudio": "circle_a1_rotation",
    "radiusFollowsAudio": "circle_a1_radius",
    "colorCycleFollowsAudio": "color_cycle_a1",
}

_REFERENCE_PUBLIC_FIELD_RE = re.compile(
    r"\bpublic\s+(?P<type>[A-Za-z0-9_<>,]+)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*="
)

_RING_KEYS = ("c1", "c2", "c3", "c4", "c5")
_RING_SCALES = (0.62, 0.82, 1.0, 1.2, 1.38)
_BAR_KEYS = (
    ("b12", 0, 1),
    ("b23", 1, 2),
    ("b34", 2, 3),
    ("b45", 3, 4),
)


def sanitize_csharp_identifier(name: str, fallback: str = "AyeExportedPresetEffect") -> str:
    raw_text = str(name or "").strip()
    text = re.sub(r"[^0-9A-Za-z_]+", " ", raw_text).strip()
    parts = [segment for segment in re.split(r"\s+", text) if segment]
    if parts:
        candidate = "".join(segment[:1].upper() + segment[1:] for segment in parts)
    elif raw_text:
        digest = hashlib.md5(raw_text.encode("utf-8")).hexdigest()[:8]
        candidate = f"AyePreset{digest}"
    else:
        candidate = fallback
    if candidate and candidate[0].isdigit():
        candidate = f"Aye{candidate}"
    return candidate or fallback


def normalize_unity_project_dir(project_dir: str | Path | None = None, last_path: str | Path | None = None) -> Path | None:
    candidate = project_dir if project_dir else last_path
    if not candidate:
        return None
    try:
        path = Path(candidate)
    except Exception:
        return None

    if path.suffix.lower() == ".cs":
        if path.parent.name.lower() == "scripts" and path.parent.parent.name.lower() == "assets":
            return path.parent.parent.parent
        return path.parent

    if path.name.lower() == "scripts" and path.parent.name.lower() == "assets":
        return path.parent.parent
    if path.name.lower() == "assets":
        return path.parent
    return path


def build_unity_export_path(project_dir: str | Path | None, class_name: str) -> Path | None:
    normalized_project_dir = normalize_unity_project_dir(project_dir=project_dir)
    if not normalized_project_dir:
        return None
    candidate_name = sanitize_csharp_identifier(class_name)
    return normalized_project_dir / "Assets" / "Scripts" / f"{candidate_name}.cs"


def build_unity_wrapper_path(project_dir: str | Path | None, class_name: str) -> Path | None:
    normalized_project_dir = normalize_unity_project_dir(project_dir=project_dir)
    if not normalized_project_dir:
        return None
    candidate_name = sanitize_csharp_identifier(class_name)
    return normalized_project_dir / "Assets" / "Scripts" / f"{candidate_name}Component.cs"


def build_unity_audio_source_path(project_dir: str | Path | None) -> Path | None:
    normalized_project_dir = normalize_unity_project_dir(project_dir=project_dir)
    if not normalized_project_dir:
        return None
    return normalized_project_dir / "Assets" / "Scripts" / "AyeExportAudioSource.cs"


def build_unity_camera_controller_path(project_dir: str | Path | None) -> Path | None:
    normalized_project_dir = normalize_unity_project_dir(project_dir=project_dir)
    if not normalized_project_dir:
        return None
    return normalized_project_dir / "Assets" / "Scripts" / "AyeExportCameraController.cs"


def build_unity_py_style_visualizer_path(project_dir: str | Path | None) -> Path | None:
    normalized_project_dir = normalize_unity_project_dir(project_dir=project_dir)
    if not normalized_project_dir:
        return None
    return normalized_project_dir / "Assets" / "Scripts" / "PyStyleVisualizer.cs"


def build_unity_windows_audio_capture_path(project_dir: str | Path | None) -> Path | None:
    normalized_project_dir = normalize_unity_project_dir(project_dir=project_dir)
    if not normalized_project_dir:
        return None
    return normalized_project_dir / "Assets" / "Scripts" / "WindowsAudioCapture.cs"


def build_unity_audio_file_driver_path(project_dir: str | Path | None) -> Path | None:
    normalized_project_dir = normalize_unity_project_dir(project_dir=project_dir)
    if not normalized_project_dir:
        return None
    return normalized_project_dir / "Assets" / "Scripts" / "AyeExportAudioFileDriver.cs"


def build_unity_tentacle_shader_path(project_dir: str | Path | None) -> Path | None:
    normalized_project_dir = normalize_unity_project_dir(project_dir=project_dir)
    if not normalized_project_dir:
        return None
    return normalized_project_dir / "Assets" / "Shaders" / "AyeTentacleSoftLine.shader"


def list_unity_legacy_conflicting_paths(project_dir: str | Path | None) -> list[Path]:
    normalized_project_dir = normalize_unity_project_dir(project_dir=project_dir)
    if not normalized_project_dir:
        return []
    scripts_dir = normalized_project_dir / "Assets" / "Scripts"
    return [
        scripts_dir / "PyStyleVisualizer-K.cs",
    ]


def list_unity_shared_prerequisite_paths(project_dir: str | Path | None) -> list[Path]:
    paths: list[Path] = []
    py_style_visualizer_path = build_unity_py_style_visualizer_path(project_dir)
    windows_audio_capture_path = build_unity_windows_audio_capture_path(project_dir)
    audio_file_driver_path = build_unity_audio_file_driver_path(project_dir)
    camera_controller_path = build_unity_camera_controller_path(project_dir)
    tentacle_shader_path = build_unity_tentacle_shader_path(project_dir)
    if py_style_visualizer_path is not None:
        paths.append(py_style_visualizer_path)
    if windows_audio_capture_path is not None:
        paths.append(windows_audio_capture_path)
    if audio_file_driver_path is not None:
        paths.append(audio_file_driver_path)
    if camera_controller_path is not None:
        paths.append(camera_controller_path)
    if tentacle_shader_path is not None:
        paths.append(tentacle_shader_path)
    return paths


def check_unity_audio_module(project_dir: Path | None) -> bool:
    """Check if the Unity project has the audio module enabled."""
    if not project_dir:
        return True
    
    # Check manifest.json for explicit exclusion or missing dependency in modern Unity
    manifest = project_dir / "Packages" / "manifest.json"
    if manifest.exists():
        try:
            content = manifest.read_text(encoding="utf-8")
            # If we have dependencies but audio is not listed, it might be disabled
            if '"dependencies"' in content and "com.unity.modules.audio" not in content:
                # Need to be careful. Some templates don't list modules if they are default? 
                # But usually manifest lists everything in 2018+.
                # If dependencies is empty {} (as seen in user project), it means minimal setup.
                # If audio is not there, we assume it's missing.
                return False
        except Exception:
            pass
            
    return True

def suggest_export_path(preset_name: str, class_name: str, project_dir: str | Path | None = None, last_path: str | None = None) -> Path:
    candidate_name = sanitize_csharp_identifier(class_name or preset_name)
    suggested_from_project = build_unity_export_path(project_dir, candidate_name)
    if suggested_from_project:
        return suggested_from_project

    normalized_last_project_dir = normalize_unity_project_dir(last_path=last_path)
    suggested_from_last = build_unity_export_path(normalized_last_project_dir, candidate_name)
    if suggested_from_last:
        return suggested_from_last

    if REFERENCE_UNITY_SCRIPTS_DIR.exists():
        return REFERENCE_UNITY_SCRIPTS_DIR / f"{candidate_name}.cs"
    return FALLBACK_EXPORT_DIR / f"{candidate_name}.cs"


def export_unity_component(config: dict, preset_name: str, output_path: str | Path, class_name: str | None = None) -> Path:
    target = Path(output_path)
    if target.suffix.lower() != ".cs":
        target = target.with_suffix(".cs")
    
    project_dir = normalize_unity_project_dir(last_path=target)
    has_audio_module = check_unity_audio_module(project_dir)
    ensure_unity_shared_prerequisites(project_dir, has_audio_module=has_audio_module)
    
    final_class_name = sanitize_csharp_identifier(class_name or target.stem or preset_name)
    source = build_unity_component_source(config, preset_name=preset_name, class_name=final_class_name, has_audio_module=has_audio_module)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8")

    wrapper_target = build_unity_wrapper_path(project_dir, final_class_name)
    if wrapper_target and wrapper_target.exists():
        try:
            wrapper_target.unlink()
        except Exception:
            pass
    wrapper_meta_target = Path(f"{wrapper_target}.meta") if wrapper_target else None
    if wrapper_meta_target and wrapper_meta_target.exists():
        try:
            wrapper_meta_target.unlink()
        except Exception:
            pass

    for legacy_target in list_unity_legacy_conflicting_paths(project_dir):
        if legacy_target.exists():
            try:
                legacy_target.unlink()
            except Exception:
                pass
        legacy_meta_target = Path(f"{legacy_target}.meta")
        if legacy_meta_target.exists():
            try:
                legacy_meta_target.unlink()
            except Exception:
                pass
    return target


def build_unity_component_source(config: dict, *, preset_name: str, class_name: str, has_audio_module: bool = True) -> str:
    return build_unity_runtime_host_source(config, preset_name=preset_name, class_name=class_name, has_audio_module=has_audio_module)


def _write_text_if_changed(target_path: Path, content: str) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        try:
            if target_path.read_text(encoding="utf-8") == content:
                return
        except Exception:
            pass
    target_path.write_text(content, encoding="utf-8")


def ensure_unity_shared_prerequisites(project_dir: str | Path | None, *, has_audio_module: bool) -> None:
    runtime_targets = {
        build_unity_py_style_visualizer_path(project_dir): REFERENCE_PY_STYLE_VISUALIZER,
        build_unity_windows_audio_capture_path(project_dir): REFERENCE_WINDOWS_AUDIO_CAPTURE,
    }
    for target_path, source_path in runtime_targets.items():
        if target_path is None or source_path is None or not source_path.exists():
            continue
        _write_text_if_changed(target_path, source_path.read_text(encoding="utf-8"))

    audio_file_driver_path = build_unity_audio_file_driver_path(project_dir)
    if audio_file_driver_path:
        _write_text_if_changed(
            audio_file_driver_path,
            build_unity_audio_file_driver_source(has_audio_module=has_audio_module),
        )

    camera_controller_path = build_unity_camera_controller_path(project_dir)
    if camera_controller_path:
        _write_text_if_changed(
            camera_controller_path,
            build_unity_camera_controller_source(),
        )

    tentacle_shader_path = build_unity_tentacle_shader_path(project_dir)
    if tentacle_shader_path and REFERENCE_TENTACLE_SHADER.exists():
        _write_text_if_changed(
            tentacle_shader_path,
            REFERENCE_TENTACLE_SHADER.read_text(encoding="utf-8"),
        )


def _camel_to_snake(name: str) -> str:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(name or ""))
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", text)
    return text.lower()


def _load_reference_py_style_field_metadata() -> list[tuple[str, str]]:
    if not REFERENCE_PY_STYLE_VISUALIZER.exists():
        return []
    fields: list[tuple[str, str]] = []
    for raw_line in REFERENCE_PY_STYLE_VISUALIZER.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or "=>" in line:
            continue
        match = _REFERENCE_PUBLIC_FIELD_RE.search(line)
        if not match:
            continue
        field_type = match.group("type")
        field_name = match.group("name")
        fields.append((field_name, field_type))
    return fields


def _build_effective_export_config(config: dict) -> dict:
    effective = dict(config or {})

    contours_enabled = bool(effective.get("contours_enabled", True))
    bars_enabled = bool(effective.get("bars_enabled", True))
    tentacles_enabled = bool(effective.get("tentacles_enabled", True))

    for layer_index in range(1, 6):
        ring_key = f"c{layer_index}_on"
        fill_key = f"c{layer_index}_fill"
        fill_alpha_key = f"c{layer_index}_fill_alpha"
        
        # Contour visibility is now independent
        effective[ring_key] = contours_enabled and bool(effective.get(ring_key, False))
        
        # Fill visibility is also independent
        effective[fill_key] = bool(effective.get(fill_key, False))
        
        if not effective[fill_key]:
            effective[fill_alpha_key] = 0

    for bar_key in ("b12", "b23", "b34", "b45"):
        effective[f"{bar_key}_on"] = bars_enabled and bool(effective.get(f"{bar_key}_on", False))

    tentacle_enabled = tentacles_enabled and bool(effective.get("tentacle_on", False))
    effective["tentacle_on"] = tentacle_enabled
    effective["tentacle_core_on"] = tentacle_enabled and bool(effective.get("tentacle_core_on", False))

    return effective


def _build_py_style_visualizer_assignments(config: dict) -> list[str]:
    effective_config = _build_effective_export_config(config)
    assignments: list[str] = []
    for field_name, field_type in _load_reference_py_style_field_metadata():
        config_key = _FIELD_KEY_OVERRIDES.get(field_name, _camel_to_snake(field_name))
        if config_key not in effective_config:
            continue
        value_expr = _build_visualizer_value_expression(field_type, effective_config.get(config_key))
        if value_expr is None:
            continue
        if "\n" in value_expr:
            assignments.append(f"            visualizer.{field_name} = {value_expr};")
        else:
            assignments.append(f"            visualizer.{field_name} = {value_expr};")
    return assignments


def _build_visualizer_value_expression(field_type: str, value) -> str | None:
    normalized_type = str(field_type or "").strip()
    if normalized_type in {"bool"}:
        return _cs_bool(value)
    if normalized_type in {"int"}:
        try:
            return str(int(value))
        except Exception:
            return None
    if normalized_type in {"float", "double"}:
        return f"{_cs_float(value)}f"
    if normalized_type == "string":
        return f'"{_escape_csharp_string(str(value or ""))}"'
    if normalized_type == "Color":
        red, green, blue = _normalize_rgb(value)
        return f"new Color32({red}, {green}, {blue}, 255)"
    if normalized_type.startswith("List<PyStyleGradientPoint>"):
        gradient_points = value if isinstance(value, list) else []
        entries = []
        for point in gradient_points:
            try:
                position = max(0.0, min(1.0, float(point[0])))
                color = point[1]
            except Exception:
                continue
            red, green, blue = _normalize_rgb(color)
            entries.append(
                f"new PyStyleGradientPoint({_cs_float(position)}f, new Color32({red}, {green}, {blue}, 255))"
            )
        if not entries:
            return None
        return "new List<PyStyleGradientPoint>\n            {\n                " + ",\n                ".join(entries) + "\n            }"
    return None


def build_unity_runtime_host_source(config: dict, *, preset_name: str, class_name: str, has_audio_module: bool) -> str:
    visualizer_assignments = _build_py_style_visualizer_assignments(config)
    visualizer_block = "\n".join(visualizer_assignments) if visualizer_assignments else "            // Keep PyStyleVisualizer defaults when no config mapping is available."

    audio_driver_fields = ""
    audio_driver_apply = ""
    windows_capture_apply = "        if (windowsCapture != null)\n        {\n            windowsCapture.enableCapture = true;\n        }\n\n"
    audio_require_component = "[RequireComponent(typeof(AyeExportAudioFileDriver))]\n"
    if has_audio_module:
        windows_capture_apply = (
            "        if (windowsCapture != null)\n"
            "        {\n"
            "            windowsCapture.enableCapture = audioInputMode == ExportAudioInputMode.WindowsLoopback;\n"
            "        }\n\n"
        )
        audio_driver_fields = (
            "    public ExportAudioInputMode audioInputMode = ExportAudioInputMode.WindowsLoopback;\n"
            "    public AudioClip audioFile;\n"
            "    public bool autoPlayAudioFile = true;\n"
            "    public bool loopAudioFile = true;\n\n"
        )
        audio_driver_apply = (
            "        AyeExportAudioFileDriver audioFileDriver = GetComponent<AyeExportAudioFileDriver>();\n"
            "        if (audioFileDriver != null)\n"
            "        {\n"
            "            audioFileDriver.enableFileInput = audioInputMode == ExportAudioInputMode.AudioFile;\n"
            "            audioFileDriver.audioClip = audioFile;\n"
            "            audioFileDriver.playOnStart = autoPlayAudioFile;\n"
            "            audioFileDriver.loopPlayback = loopAudioFile;\n"
            "        }\n"
        )
    else:
        audio_require_component = ""
        audio_driver_fields = "    public ExportAudioInputMode audioInputMode = ExportAudioInputMode.WindowsLoopback;\n\n"

    return (
        "using System.Collections.Generic;\n"
        "using UnityEngine;\n\n"
        "[DefaultExecutionOrder(-1000)]\n"
        "[DisallowMultipleComponent]\n"
        f"[AddComponentMenu(\"AYE导出/预设效果/{_escape_csharp_string(preset_name)}\")]\n"
        "[RequireComponent(typeof(PyStyleVisualizer))]\n"
        "[RequireComponent(typeof(WindowsAudioCapture))]\n"
        + audio_require_component +
        f"public class {class_name} : MonoBehaviour\n"
        "{\n"
        "    public enum ExportAudioInputMode\n"
        "    {\n"
        "        WindowsLoopback = 0,\n"
        "        AudioFile = 1,\n"
        "    }\n\n"
        "    [Header(\"Preset\")]\n"
        f"    public string sourcePresetName = \"{_escape_csharp_string(preset_name)}\";\n\n"
        "    [Header(\"Audio Input\")]\n"
        + audio_driver_fields +
        "    [Header(\"Camera\")]\n"
        "    public bool attachCameraControllerIfMissing = true;\n\n"
        "    private void Reset()\n"
        "    {\n"
        "        ApplyDefaults();\n"
        "    }\n\n"
        "    private void Awake()\n"
        "    {\n"
        "        ApplyDefaults();\n"
        "    }\n\n"
        "    private void OnValidate()\n"
        "    {\n"
        "        ApplyDefaults();\n"
        "    }\n\n"
        "    private void ApplyDefaults()\n"
        "    {\n"
        "        PyStyleVisualizer visualizer = GetComponent<PyStyleVisualizer>();\n"
        "        WindowsAudioCapture windowsCapture = GetComponent<WindowsAudioCapture>();\n"
        "        if (visualizer != null)\n"
        "        {\n"
        "            visualizer.autoFrameMainCamera = false;\n"
        + visualizer_block + "\n"
        "            NormalizeVisualizerVisibility(visualizer);\n"
        "        }\n\n"
        + windows_capture_apply
        + audio_driver_apply + "\n"
        "        if (attachCameraControllerIfMissing)\n"
        "        {\n"
        "            Camera mainCamera = Camera.main;\n"
        "            if (mainCamera != null && mainCamera.GetComponent<AyeExportCameraController>() == null)\n"
        "            {\n"
        "                mainCamera.gameObject.AddComponent<AyeExportCameraController>();\n"
        "            }\n"
        "        }\n"
        "    }\n"
        "\n"
        "    private static void NormalizeVisualizerVisibility(PyStyleVisualizer visualizer)\n"
        "    {\n"
        "        if (visualizer == null)\n"
        "        {\n"
        "            return;\n"
        "        }\n"
        "\n"
        "        // Fill visibility is independent of contour visibility.\n"
        "        // Just ensure fill alpha is zero when fill is disabled.\n"
        "        if (!visualizer.c1Fill) visualizer.c1FillAlpha = 0;\n"
        "        if (!visualizer.c2Fill) visualizer.c2FillAlpha = 0;\n"
        "        if (!visualizer.c3Fill) visualizer.c3FillAlpha = 0;\n"
        "        if (!visualizer.c4Fill) visualizer.c4FillAlpha = 0;\n"
        "        if (!visualizer.c5Fill) visualizer.c5FillAlpha = 0;\n"
        "\n"
        "        visualizer.b12On = visualizer.barsEnabled && visualizer.b12On;\n"
        "        visualizer.b23On = visualizer.barsEnabled && visualizer.b23On;\n"
        "        visualizer.b34On = visualizer.barsEnabled && visualizer.b34On;\n"
        "        visualizer.b45On = visualizer.barsEnabled && visualizer.b45On;\n"
        "\n"
        "        visualizer.tentacleOn = visualizer.tentaclesEnabled && visualizer.tentacleOn;\n"
        "        visualizer.tentacleCoreOn = visualizer.tentacleOn && visualizer.tentacleCoreOn;\n"
        "    }\n"
        "}\n"
    )


def build_unity_audio_file_driver_source(*, has_audio_module: bool) -> str:
    if not has_audio_module:
        return (
            "using UnityEngine;\n\n"
            "[DisallowMultipleComponent]\n"
            "[AddComponentMenu(\"AYE导出/基础组件/音频文件输入驱动\")]\n"
            "public class AyeExportAudioFileDriver : MonoBehaviour\n"
            "{\n"
            "    public bool enableFileInput = false;\n"
            "}\n"
        )

    return r'''using UnityEngine;

[DisallowMultipleComponent]
[AddComponentMenu("AYE导出/基础组件/音频文件输入驱动")]
[RequireComponent(typeof(PyStyleVisualizer))]
[RequireComponent(typeof(AudioSource))]
public class AyeExportAudioFileDriver : MonoBehaviour
{
    public bool enableFileInput = false;
    public AudioClip audioClip;
    public bool playOnStart = true;
    public bool loopPlayback = true;
    public int spectrumSize = 2048;
    public FFTWindow fftWindow = FFTWindow.BlackmanHarris;

    private PyStyleVisualizer visualizer;
    private AudioSource audioSource;
    private float[] spectrum;

    private void Awake()
    {
        visualizer = GetComponent<PyStyleVisualizer>();
        audioSource = GetComponent<AudioSource>();
        ConfigureAudioSource();
        ConfigureSpectrumBuffer();
    }

    private void OnValidate()
    {
        ConfigureAudioSource();
        ConfigureSpectrumBuffer();
    }

    private void Update()
    {
        if (audioSource == null || visualizer == null)
        {
            return;
        }

        ConfigureAudioSource();
        ConfigureSpectrumBuffer();

        if (!enableFileInput || audioClip == null)
        {
            if (audioSource.isPlaying)
            {
                audioSource.Stop();
            }
            return;
        }

        if (audioSource.clip != audioClip)
        {
            audioSource.clip = audioClip;
        }

        if (playOnStart && audioSource.clip != null && !audioSource.isPlaying)
        {
            audioSource.Play();
        }

        if (!audioSource.isPlaying)
        {
            return;
        }

        audioSource.GetSpectrumData(spectrum, 0, fftWindow);
        float loudness = 0f;
        int count = Mathf.Max(1, spectrum.Length / 4);
        for (int i = 0; i < count; i++)
        {
            loudness += spectrum[i];
        }
        float sampleRate = 48000f;
        if (audioSource.clip != null && audioSource.clip.frequency > 0)
        {
            sampleRate = audioSource.clip.frequency;
        }
        visualizer.SetExternalSpectrum(spectrum, loudness / count, sampleRate);
    }

    private void ConfigureAudioSource()
    {
        if (audioSource == null)
        {
            return;
        }

        audioSource.playOnAwake = false;
        audioSource.loop = loopPlayback;
        audioSource.spatialBlend = 0f;
        audioSource.clip = audioClip;
    }

    private void ConfigureSpectrumBuffer()
    {
        spectrumSize = Mathf.Clamp(Mathf.NextPowerOfTwo(Mathf.Max(64, spectrumSize)), 64, 8192);
        if (spectrum != null && spectrum.Length == spectrumSize)
        {
            return;
        }
        spectrum = new float[spectrumSize];
    }
}
'''
    ring_lines = []
    for layer_index, (prefix, scale) in enumerate(zip(_RING_KEYS, _RING_SCALES)):
        ring_lines.append(
            "        new RingStyle(%s, %sf, %s, %sf, %s, %sf, %d, %sf, %sf, %sf, %sf),"
            % (
                _cs_bool(config.get(f"{prefix}_on", False)),
                _cs_float(config.get(f"{prefix}_thick", 1.0)),
                _cs_color(config.get(f"{prefix}_color", (255, 255, 255)), alpha=255),
                _alpha01(config.get(f"{prefix}_alpha", 255)),
                _cs_bool(config.get(f"{prefix}_fill", False)),
                _alpha01(config.get(f"{prefix}_fill_alpha", 0)),
                int(config.get(f"{prefix}_step", 1) or 1),
                _cs_float(config.get(f"{prefix}_decay", 0.995 if prefix in {"c1", "c5"} else 1.0)),
                _cs_float(config.get(f"{prefix}_rot_speed", 1.0)),
                _cs_float(config.get(f"{prefix}_rot_pow", 0.5)),
                _cs_float(scale),
            )
        )

    bar_lines = []
    for prefix, start_ring, end_ring in _BAR_KEYS:
        bar_lines.append(
            "        new BarStyle(%s, %sf, %s, %sf, %s, %s, %s, %d, %d),"
            % (
                _cs_bool(config.get(f"{prefix}_on", False)),
                _cs_float(config.get(f"{prefix}_thick", 1.0)),
                _cs_bool(config.get(f"{prefix}_fixed", False)),
                _cs_float(config.get(f"{prefix}_fixed_len", 0.0)),
                _cs_bool(config.get(f"{prefix}_from_start", True)),
                _cs_bool(config.get(f"{prefix}_from_end", False)),
                _cs_bool(config.get(f"{prefix}_from_center", False)),
                start_ring,
                end_ring,
            )
        )

    gradient_points = config.get("gradient_points") or []
    normalized_gradient_points = []
    for point in gradient_points:
        try:
            position = max(0.0, min(1.0, float(point[0])))
            color = point[1]
        except Exception:
            continue
        normalized_gradient_points.append((position, color))
    normalized_gradient_points.sort(key=lambda item: item[0])
    gradient_lines = [
        "        new GradientPointData(%sf, %s)," % (_cs_float(position), _cs_color(color, alpha=255))
        for position, color in normalized_gradient_points
    ]
    if not gradient_lines:
        gradient_lines = [
            "        new GradientPointData(0f, new Color32(255, 0, 128, 255)),",
            "        new GradientPointData(1f, new Color32(0, 255, 255, 255)),",
        ]

    replacements = {
        "__CLASS_NAME__": class_name,
        "__PRESET_NAME__": _escape_csharp_string(preset_name),
        "__ADD_COMPONENT_MENU__": _escape_csharp_string(f"AYE Exported/{preset_name}"),
        "__NUM_BARS__": str(int(config.get("num_bars", 64) or 64)),
        "__SMOOTHING__": f"{_cs_float(config.get('smoothing', 0.7))}f",
        "__ROTATION_BASE__": f"{_cs_float(config.get('rotation_base', 1.0))}f",
        "__MAIN_RADIUS_SCALE__": f"{_cs_float(config.get('main_radius_scale', 1.0))}f",
        "__BAR_HEIGHT_MIN__": f"{_cs_float(config.get('bar_height_min', 0.0))}f",
        "__BAR_HEIGHT_MAX__": f"{_cs_float(config.get('bar_height_max', 300.0))}f",
        "__BAR_LENGTH_MIN__": f"{_cs_float(config.get('bar_length_min', 0.0))}f",
        "__BAR_LENGTH_MAX__": f"{_cs_float(config.get('bar_length_max', 300.0))}f",
        "__FREQ_MIN__": f"{_cs_float(config.get('freq_min', 20.0))}f",
        "__FREQ_MAX__": f"{_cs_float(config.get('freq_max', 20000.0))}f",
        "__A1_WINDOW__": f"{_cs_float(config.get('a1_time_window', 10.0))}f",
        "__K2_ENABLED__": _cs_bool(config.get('k2_enabled', False)),
        "__K2_POW__": f"{_cs_float(config.get('k2_pow', 1.0))}f",
        "__MASTER_VISIBLE__": _cs_bool(config.get('master_visible', True)),
        "__GLOBAL_SCALE__": f"{_cs_float(config.get('global_scale', 1.0))}f",
        "__CIRCLE_RADIUS__": f"{_cs_float(config.get('circle_radius', 150.0))}f",
        "__CIRCLE_SEGMENTS__": str(max(1, int(config.get('circle_segments', 1) or 1))),
        "__ROTATION_FOLLOWS_AUDIO__": _cs_bool(config.get('circle_a1_rotation', True)),
        "__RADIUS_FOLLOWS_AUDIO__": _cs_bool(config.get('circle_a1_radius', True)),
        "__RADIUS_DAMPING__": f"{_cs_float(config.get('radius_damping', 0.92))}f",
        "__RADIUS_SPRING__": f"{_cs_float(config.get('radius_spring', 0.15))}f",
        "__RADIUS_GRAVITY__": f"{_cs_float(config.get('radius_gravity', 0.3))}f",
        "__KR_DAMPING__": f"{_cs_float(config.get('k_rise_damping', 0.1))}f",
        "__KF_DAMPING__": f"{_cs_float(config.get('k_fall_damping', 0.999))}f",
        "__COLOR_DYNAMIC__": _cs_bool(config.get('color_dynamic', False)),
        "__COLOR_CYCLE_SPEED__": f"{_cs_float(config.get('color_cycle_speed', 1.0))}f",
        "__COLOR_CYCLE_POW__": f"{_cs_float(config.get('color_cycle_pow', 2.0))}f",
        "__COLOR_CYCLE_A1__": _cs_bool(config.get('color_cycle_a1', True)),
        "__COLOR_SCHEME__": _escape_csharp_string(str(config.get('color_scheme', 'rainbow'))),
        "__GRADIENT_ENABLED__": _cs_bool(config.get('gradient_enabled', True)),
        "__GRADIENT_MODE__": _escape_csharp_string(str(config.get('gradient_mode', 'frequency'))),
        "__CONTOURS_ENABLED__": _cs_bool(config.get('contours_enabled', True)),
        "__BARS_ENABLED__": _cs_bool(config.get('bars_enabled', True)),
        "__TENTACLES_ENABLED__": _cs_bool(config.get('tentacles_enabled', True) and config.get('tentacle_on', True)),
        "__TENTACLE_BASE_COLOR__": _cs_color(config.get('tentacle_color', (130, 240, 220)), alpha=config.get('tentacle_alpha', 255)),
        "__TENTACLE_TIP_COLOR__": _cs_color(config.get('tentacle_shader_tip_color', config.get('tentacle_color', (130, 240, 220))), alpha=max(1, int(float(config.get('tentacle_shader_alpha_end', 1.0)) * 255.0))),
        "__TENTACLE_THICKNESS__": f"{_cs_float(config.get('tentacle_thick', 2.0))}f",
        "__TENTACLE_COUNT__": str(max(1, int(config.get('tentacle_count', 8) or 8))),
        "__TENTACLE_LENGTH__": f"{_cs_float(config.get('tentacle_length', 220.0))}f",
        "__TENTACLE_JITTER__": f"{_cs_float(config.get('tentacle_length_jitter', 0.0))}f",
        "__TENTACLE_JITTER_SPEED__": f"{_cs_float(config.get('tentacle_length_jitter_speed', 0.0))}f",
        "__TENTACLE_RANDOM_JITTER__": _cs_bool(config.get('tentacle_length_jitter_random', False)),
        "__TENTACLE_CP_MIN__": str(max(2, int(config.get('tentacle_control_points_min', 4) or 4))),
        "__TENTACLE_CP_MAX__": str(max(2, int(config.get('tentacle_control_points_max', 6) or 6))),
        "__TENTACLE_TIP_BIAS__": f"{_cs_float(config.get('tentacle_tip_bias', 1.0))}f",
        "__TENTACLE_TIP_THICKNESS__": f"{_cs_float(config.get('tentacle_tip_thickness', 0.15))}f",
        "__TENTACLE_TURBULENCE__": f"{_cs_float(config.get('tentacle_turbulence', 0.0))}f",
        "__TENTACLE_K_INFLUENCE__": f"{_cs_float(config.get('tentacle_k_influence', 1.0))}f",
        "__TENTACLE_SWAY_SPEED__": f"{_cs_float(config.get('tentacle_sway_speed', 1.0))}f",
        "__TENTACLE_SWAY_DENSITY__": f"{_cs_float(config.get('tentacle_sway_density', 1.0))}f",
        "__TENTACLE_WATER_DAMPING__": f"{_cs_float(config.get('tentacle_water_damping', 0.84))}f",
        "__TENTACLE_ANGLE_STIFFNESS__": f"{_cs_float(config.get('tentacle_angle_stiffness', 0.2))}f",
        "__TENTACLE_LENGTH_STIFFNESS__": f"{_cs_float(config.get('tentacle_length_stiffness', 0.24))}f",
        "__TENTACLE_STRETCH_LIMIT__": f"{_cs_float(config.get('tentacle_stretch_limit', 1.12))}f",
        "__TENTACLE_SHADER_ENABLED__": _cs_bool(config.get('tentacle_shader_enabled', True)),
        "__TENTACLE_SHADER_ALPHA_START__": f"{_cs_float(config.get('tentacle_shader_alpha_start', 1.0))}f",
        "__TENTACLE_SHADER_ALPHA_END__": f"{_cs_float(config.get('tentacle_shader_alpha_end', 0.18))}f",
        "__TENTACLE_SHADER_BIAS__": f"{_cs_float(config.get('tentacle_shader_bias', 1.15))}f",
        "__TENTACLE_CORE_ENABLED__": _cs_bool(config.get('tentacle_core_on', True)),
        "__TENTACLE_CORE_COLOR__": _cs_color(config.get('tentacle_core_color', (225, 255, 245)), alpha=config.get('tentacle_core_alpha', 255)),
        "__TENTACLE_CORE_THICKNESS__": f"{_cs_float(config.get('tentacle_core_thick', 2.0))}f",
        "__TENTACLE_CORE_POINTS__": str(max(3, int(config.get('tentacle_core_points', 6) or 6))),
        "__TENTACLE_CORE_OUTER_RADIUS__": f"{_cs_float(config.get('tentacle_core_outer_radius', 26.0))}f",
        "__TENTACLE_CORE_INNER_RATIO__": f"{_cs_float(config.get('tentacle_core_inner_ratio', 0.42))}f",
        "__TENTACLE_CORE_BASE_SPEED__": f"{_cs_float(config.get('tentacle_core_base_speed', 0.75))}f",
        "__TENTACLE_CORE_K_SPEED__": f"{_cs_float(config.get('tentacle_core_k_speed', 1.2))}f",
        "__TENTACLE_CORE_P_SPEED__": f"{_cs_float(config.get('tentacle_core_p_speed', 1.35))}f",
        "__RING_STYLES__": "\n".join(ring_lines),
        "__BAR_STYLES__": "\n".join(bar_lines),
        "__GRADIENT_POINTS__": "\n".join(gradient_lines),
    }

    source = _UNITY_TEMPLATE
    for key, value in replacements.items():
        source = source.replace(key, value)
    return source


def build_unity_audio_source_source(*, has_audio_module: bool) -> str:
    if has_audio_module:
        sample_impl = r'''    private bool TrySampleBuiltInAudio()
    {
        if (!preferBuiltInAudio)
        {
            return false;
        }

        AudioListener.GetSpectrumData(_spectrum, 0, FFTWindow.BlackmanHarris);
        _sampleRate = Mathf.Max(1f, AudioSettings.outputSampleRate);
        for (int i = 0; i < _spectrum.Length; i++)
        {
            if (_spectrum[i] > silenceFloor)
            {
                return true;
            }
        }
        return false;
    }
'''
    else:
        sample_impl = r'''    private bool TrySampleBuiltInAudio()
    {
        return false;
    }
'''

    return (
        "using System;\n"
        "using UnityEngine;\n\n"
        "[DisallowMultipleComponent]\n"
        "[AddComponentMenu(\"AYE导出/基础组件/共享音频源\")]\n"
        "public class AyeExportAudioSource : MonoBehaviour\n"
        "{\n"
        "    [Header(\"Audio Source\")]\n"
        "    public bool preferBuiltInAudio = true;\n"
        "    public bool enableTestSignal = true;\n"
        "    [Range(64, 8192)] public int spectrumSize = 1024;\n"
        "    [Range(0.1f, 10f)] public float testSpeed = 2f;\n"
        "    [Range(0.01f, 1f)] public float intensity = 0.3f;\n"
        "    [Range(0f, 1f)] public float noiseAmount = 0.5f;\n"
        "    [Range(1, 8)] public int beatCount = 4;\n"
        "    [Range(0f, 0.02f)] public float silenceFloor = 0.00035f;\n\n"
        "    private float[] _spectrum;\n"
        "    private float _sampleRate = 44100f;\n"
        "    private float _phase;\n"
        "    private float[] _beatPhases;\n"
        "    private float[] _beatFreqs;\n\n"
        "    public float SampleRate\n"
        "    {\n"
        "        get { return _sampleRate; }\n"
        "    }\n\n"
        "    private void Awake()\n"
        "    {\n"
        "        ConfigureBuffers();\n"
        "        RandomizeBeatPattern();\n"
        "    }\n\n"
        "    private void OnValidate()\n"
        "    {\n"
        "        ConfigureBuffers();\n"
        "    }\n\n"
        "    private void Update()\n"
        "    {\n"
        "        ConfigureBuffers();\n"
        "        if (!TrySampleBuiltInAudio())\n"
        "        {\n"
        "            if (enableTestSignal)\n"
        "            {\n"
        "                GenerateTestSpectrum();\n"
        "            }\n"
        "            else\n"
        "            {\n"
        "                ClearSpectrum();\n"
        "            }\n"
        "        }\n"
        "        if (Time.frameCount % 300 == 0)\n"
        "        {\n"
        "            RandomizeOneBeat();\n"
        "        }\n"
        "    }\n\n"
        "    public void CopySpectrum(float[] target)\n"
        "    {\n"
        "        if (target == null)\n"
        "        {\n"
        "            return;\n"
        "        }\n"
        "        ConfigureBuffers();\n"
        "        for (int i = 0; i < target.Length; i++)\n"
        "        {\n"
        "            target[i] = 0f;\n"
        "        }\n"
        "        int copyLength = Mathf.Min(target.Length, _spectrum.Length);\n"
        "        Array.Copy(_spectrum, 0, target, 0, copyLength);\n"
        "    }\n\n"
        "    private void ConfigureBuffers()\n"
        "    {\n"
        "        spectrumSize = Mathf.Clamp(Mathf.NextPowerOfTwo(Mathf.Max(64, spectrumSize)), 64, 8192);\n"
        "        if (_spectrum != null && _spectrum.Length == spectrumSize && _beatPhases != null && _beatPhases.Length == Mathf.Max(1, beatCount))\n"
        "        {\n"
        "            return;\n"
        "        }\n"
        "        _spectrum = new float[spectrumSize];\n"
        "        _beatPhases = new float[Mathf.Max(1, beatCount)];\n"
        "        _beatFreqs = new float[Mathf.Max(1, beatCount)];\n"
        "        RandomizeBeatPattern();\n"
        "    }\n\n"
        "    private void RandomizeBeatPattern()\n"
        "    {\n"
        "        if (_beatPhases == null || _beatFreqs == null)\n"
        "        {\n"
        "            return;\n"
        "        }\n"
        "        for (int i = 0; i < _beatPhases.Length; i++)\n"
        "        {\n"
        "            _beatPhases[i] = UnityEngine.Random.Range(0f, Mathf.PI * 2f);\n"
        "            _beatFreqs[i] = UnityEngine.Random.Range(0.5f, 3f);\n"
        "        }\n"
        "    }\n\n"
        "    private void RandomizeOneBeat()\n"
        "    {\n"
        "        if (_beatFreqs == null || _beatFreqs.Length == 0)\n"
        "        {\n"
        "            return;\n"
        "        }\n"
        "        int idx = UnityEngine.Random.Range(0, _beatFreqs.Length);\n"
        "        _beatFreqs[idx] = UnityEngine.Random.Range(0.5f, 3f);\n"
        "    }\n\n"
        + sample_impl +
        "    private void GenerateTestSpectrum()\n"
        "    {\n"
        "        if (_spectrum == null)\n"
        "        {\n"
        "            return;\n"
        "        }\n"
        "        _sampleRate = 44100f;\n"
        "        _phase += Time.deltaTime * testSpeed;\n"
        "        int localBeatCount = Mathf.Max(1, beatCount);\n"
        "        for (int i = 0; i < _spectrum.Length; i++)\n"
        "        {\n"
        "            float freq = (float)i / Mathf.Max(1, _spectrum.Length);\n"
        "            float value = 0f;\n"
        "            if (freq < 0.1f)\n"
        "            {\n"
        "                float bassPhase = _phase * 2f + _beatPhases[0];\n"
        "                value += Mathf.Pow(Mathf.Sin(bassPhase), 2f) * (1f - freq * 5f) * 2f;\n"
        "                value += Mathf.Sin(_phase * _beatFreqs[0] * 0.5f) * 0.5f + 0.5f;\n"
        "            }\n"
        "            if (freq > 0.05f && freq < 0.4f)\n"
        "            {\n"
        "                for (int b = 1; b < Mathf.Min(3, localBeatCount); b++)\n"
        "                {\n"
        "                    float midPhase = _phase * _beatFreqs[b] + _beatPhases[b];\n"
        "                    float envelope = Mathf.Exp(-Mathf.Abs(freq - 0.15f * b) * 20f);\n"
        "                    value += Mathf.Pow(Mathf.Sin(midPhase), 4f) * envelope * 1.5f;\n"
        "                }\n"
        "            }\n"
        "            if (freq > 0.3f && freq < 0.8f)\n"
        "            {\n"
        "                for (int b = 2; b < localBeatCount; b++)\n"
        "                {\n"
        "                    float highPhase = _phase * _beatFreqs[b] * 2f + _beatPhases[b];\n"
        "                    float envelope = Mathf.Exp(-Mathf.Abs(freq - 0.2f * b) * 15f);\n"
        "                    value += Mathf.Pow(Mathf.Abs(Mathf.Sin(highPhase)), 3f) * envelope;\n"
        "                }\n"
        "            }\n"
        "            value += UnityEngine.Random.Range(0f, noiseAmount * 0.1f);\n"
        "            value *= Mathf.Exp(-freq * 2f);\n"
        "            _spectrum[i] = Mathf.Clamp01(value * intensity);\n"
        "        }\n"
        "    }\n\n"
        "    private void ClearSpectrum()\n"
        "    {\n"
        "        if (_spectrum == null)\n"
        "        {\n"
        "            return;\n"
        "        }\n"
        "        for (int i = 0; i < _spectrum.Length; i++)\n"
        "        {\n"
        "            _spectrum[i] = 0f;\n"
        "        }\n"
        "    }\n"
        "}\n"
    )


def build_unity_camera_controller_source() -> str:
    return r'''using UnityEngine;

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
'''


def _alpha01(value) -> str:
    try:
        alpha = max(0.0, min(1.0, float(value) / 255.0))
    except Exception:
        alpha = 1.0
    return _cs_float(alpha)


def _cs_bool(value) -> str:
    return "true" if bool(value) else "false"


def _cs_float(value) -> str:
    try:
        number = float(value)
    except Exception:
        number = 0.0
    text = f"{number:.6f}".rstrip("0").rstrip(".")
    if text in {"", "-0"}:
        text = "0"
    if "." not in text:
        text += ".0"
    return text


def _cs_color(value, *, alpha=255) -> str:
    red, green, blue = _normalize_rgb(value)
    alpha_value = max(0, min(255, int(alpha)))
    return f"new Color32({red}, {green}, {blue}, {alpha_value})"


def _normalize_rgb(value) -> tuple[int, int, int]:
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        try:
            return tuple(max(0, min(255, int(channel))) for channel in value[:3])
        except Exception:
            pass
    return 255, 255, 255


def _escape_csharp_string(value: str) -> str:
    return str(value or "").replace("\\", "\\\\").replace('"', '\\"')


_UNITY_TEMPLATE = r'''using System;
using System.Collections.Generic;
using UnityEngine;

#pragma warning disable 0162 // Suppress unreachable code due to const bools

[AddComponentMenu("__ADD_COMPONENT_MENU__")]
[DisallowMultipleComponent]
[RequireComponent(typeof(AyeExportAudioSource))]
public class __CLASS_NAME__ : MonoBehaviour
{
    private const string SourcePresetName = "__PRESET_NAME__";
    private const int NumBars = __NUM_BARS__;
    private const float Smoothing = __SMOOTHING__;
    private const float RotationBase = __ROTATION_BASE__;
    private const float MainRadiusScale = __MAIN_RADIUS_SCALE__;
    private const float BarHeightMin = __BAR_HEIGHT_MIN__;
    private const float BarHeightMax = __BAR_HEIGHT_MAX__;
    private const float BarLengthMin = __BAR_LENGTH_MIN__;
    private const float BarLengthMax = __BAR_LENGTH_MAX__;
    private const float FreqMin = __FREQ_MIN__;
    private const float FreqMax = __FREQ_MAX__;
    private const float A1TimeWindow = __A1_WINDOW__;
    private const bool K2Enabled = __K2_ENABLED__;
    private const float K2Pow = __K2_POW__;
    private const bool MasterVisible = __MASTER_VISIBLE__;
    private const float GlobalScale = __GLOBAL_SCALE__;
    private const float CircleRadius = __CIRCLE_RADIUS__;
    private const int CircleSegments = __CIRCLE_SEGMENTS__;
    private const bool RotationFollowsAudio = __ROTATION_FOLLOWS_AUDIO__;
    private const bool RadiusFollowsAudio = __RADIUS_FOLLOWS_AUDIO__;
    private const float RadiusDamping = __RADIUS_DAMPING__;
    private const float RadiusSpring = __RADIUS_SPRING__;
    private const float RadiusGravity = __RADIUS_GRAVITY__;
    private const float KRiseDamping = __KR_DAMPING__;
    private const float KFallDamping = __KF_DAMPING__;
    private const bool ColorDynamic = __COLOR_DYNAMIC__;
    private const float ColorCycleSpeed = __COLOR_CYCLE_SPEED__;
    private const float ColorCyclePow = __COLOR_CYCLE_POW__;
    private const bool ColorCycleFollowsAudio = __COLOR_CYCLE_A1__;
    private const string ColorScheme = "__COLOR_SCHEME__";
    private const bool GradientEnabled = __GRADIENT_ENABLED__;
    private const string GradientMode = "__GRADIENT_MODE__";
    private const bool ContoursEnabled = __CONTOURS_ENABLED__;
    private const bool BarsEnabled = __BARS_ENABLED__;
    private const bool TentaclesEnabled = __TENTACLES_ENABLED__;
    private static readonly Color32 TentacleBaseColor = __TENTACLE_BASE_COLOR__;
    private static readonly Color32 TentacleTipColor = __TENTACLE_TIP_COLOR__;
    private const float TentacleThickness = __TENTACLE_THICKNESS__;
    private const int TentacleCount = __TENTACLE_COUNT__;
    private const float TentacleLength = __TENTACLE_LENGTH__;
    private const float TentacleJitter = __TENTACLE_JITTER__;
    private const float TentacleJitterSpeed = __TENTACLE_JITTER_SPEED__;
    private const bool TentacleRandomJitter = __TENTACLE_RANDOM_JITTER__;
    private const int TentacleControlPointsMin = __TENTACLE_CP_MIN__;
    private const int TentacleControlPointsMax = __TENTACLE_CP_MAX__;
    private const float TentacleTipBias = __TENTACLE_TIP_BIAS__;
    private const float TentacleTipThickness = __TENTACLE_TIP_THICKNESS__;
    private const float TentacleTurbulence = __TENTACLE_TURBULENCE__;
    private const float TentacleKInfluence = __TENTACLE_K_INFLUENCE__;
    private const float TentacleSwaySpeed = __TENTACLE_SWAY_SPEED__;
    private const float TentacleSwayDensity = __TENTACLE_SWAY_DENSITY__;
    private const float TentacleWaterDamping = __TENTACLE_WATER_DAMPING__;
    private const float TentacleAngleStiffness = __TENTACLE_ANGLE_STIFFNESS__;
    private const float TentacleLengthStiffness = __TENTACLE_LENGTH_STIFFNESS__;
    private const float TentacleStretchLimit = __TENTACLE_STRETCH_LIMIT__;
    private const bool TentacleShaderEnabled = __TENTACLE_SHADER_ENABLED__;
    private const float TentacleShaderAlphaStart = __TENTACLE_SHADER_ALPHA_START__;
    private const float TentacleShaderAlphaEnd = __TENTACLE_SHADER_ALPHA_END__;
    private const float TentacleShaderBias = __TENTACLE_SHADER_BIAS__;
    private const bool TentacleCoreEnabled = __TENTACLE_CORE_ENABLED__;
    private static readonly Color32 TentacleCoreColor = __TENTACLE_CORE_COLOR__;
    private const float TentacleCoreThickness = __TENTACLE_CORE_THICKNESS__;
    private const int TentacleCorePoints = __TENTACLE_CORE_POINTS__;
    private const float TentacleCoreOuterRadius = __TENTACLE_CORE_OUTER_RADIUS__;
    private const float TentacleCoreInnerRatio = __TENTACLE_CORE_INNER_RATIO__;
    private const float TentacleCoreBaseSpeed = __TENTACLE_CORE_BASE_SPEED__;
    private const float TentacleCoreKSpeed = __TENTACLE_CORE_K_SPEED__;
    private const float TentacleCorePSpeed = __TENTACLE_CORE_P_SPEED__;

    private static readonly RingStyle[] RingStyles = new RingStyle[]
    {
__RING_STYLES__
    };

    private static readonly BarStyle[] BarStyles = new BarStyle[]
    {
__BAR_STYLES__
    };

    private static readonly GradientPointData[] GradientPoints = new GradientPointData[]
    {
__GRADIENT_POINTS__
    };

    private sealed class RingStyle
    {
        public readonly bool Enabled;
        public readonly float Thickness;
        public readonly Color32 Color;
        public readonly float Alpha;
        public readonly bool FillEnabled;
        public readonly float FillAlpha;
        public readonly int Step;
        public readonly float Decay;
        public readonly float RotationSpeed;
        public readonly float RotationPower;
        public readonly float Scale;

        public RingStyle(bool enabled, float thickness, Color32 color, float alpha, bool fillEnabled, float fillAlpha, int step, float decay, float rotationSpeed, float rotationPower, float scale)
        {
            Enabled = enabled;
            Thickness = Mathf.Max(0.01f, thickness);
            Color = color;
            Alpha = Mathf.Clamp01(alpha);
            FillEnabled = fillEnabled;
            FillAlpha = Mathf.Clamp01(fillAlpha);
            Step = Mathf.Max(1, step);
            Decay = Mathf.Clamp(decay, 0f, 0.9999f);
            RotationSpeed = rotationSpeed;
            RotationPower = Mathf.Max(0.01f, rotationPower);
            Scale = scale;
        }
    }

    private sealed class BarStyle
    {
        public readonly bool Enabled;
        public readonly float Thickness;
        public readonly bool FixedLength;
        public readonly float FixedLengthValue;
        public readonly bool FromStart;
        public readonly bool FromEnd;
        public readonly bool FromCenter;
        public readonly int StartRing;
        public readonly int EndRing;

        public BarStyle(bool enabled, float thickness, bool fixedLength, float fixedLengthValue, bool fromStart, bool fromEnd, bool fromCenter, int startRing, int endRing)
        {
            Enabled = enabled;
            Thickness = Mathf.Max(0.01f, thickness);
            FixedLength = fixedLength;
            FixedLengthValue = Mathf.Max(0f, fixedLengthValue);
            FromStart = fromStart;
            FromEnd = fromEnd;
            FromCenter = fromCenter;
            StartRing = startRing;
            EndRing = endRing;
        }
    }

    private struct GradientPointData
    {
        public readonly float Position;
        public readonly Color32 Color;

        public GradientPointData(float position, Color32 color)
        {
            Position = Mathf.Clamp01(position);
            Color = color;
        }
    }

    private sealed class RingRuntime
    {
        public RingStyle Style;
        public LineRenderer Line;
        public Mesh Mesh;
        public MeshFilter MeshFilter;
        public MeshRenderer MeshRenderer;
        public Material FillMaterial;
        public float[] Peaks;
    }

    private sealed class BarRuntime
    {
        public BarStyle Style;
        public LineRenderer[] Lines;
    }

    private sealed class TentacleRuntime
    {
        public LineRenderer Line;
        public float Seed;
        public float JitterSeed;
        public float Velocity;
    }

    private Material _sharedLineMaterial;
    private AyeExportAudioSource _audioSource;
    private RingRuntime[] _ringRuntimes;
    private BarRuntime[] _barRuntimes;
    private TentacleRuntime[] _tentacleRuntimes;
    private LineRenderer _coreLine;
    private readonly float[] _spectrum = new float[1024];
    private readonly float[] _barSamples = new float[NumBars];
    private readonly float[] _barTargets = new float[NumBars];
    private readonly Vector3[][] _layerPositions = new Vector3[5][];
    private float _dynamicRange = 0.015f;
    private float _rawA1;
    private float _a1;
    private float _k2;
    private float _rotation;
    private float _radiusVelocity;
    private float _radiusState;
    private float _colorPhase;

    private void Awake()
    {
        _audioSource = GetComponent<AyeExportAudioSource>();
        if (_audioSource == null)
        {
            _audioSource = gameObject.AddComponent<AyeExportAudioSource>();
        }
        EnsureSharedMaterial();
        BuildRingRuntimes();
        BuildBarRuntimes();
        BuildTentacles();
        BuildCore();
        for (int i = 0; i < _layerPositions.Length; i++)
        {
            _layerPositions[i] = new Vector3[Mathf.Max(NumBars * Mathf.Max(1, CircleSegments), 16) + 1];
        }
        _radiusState = CircleRadius * GlobalScale * MainRadiusScale;
        EnsureMainCameraReady();
        ApplyMasterVisible();
    }

    private void Start()
    {
        EnsureMainCameraReady();
    }

    private void OnDestroy()
    {
        if (_sharedLineMaterial != null)
        {
            Destroy(_sharedLineMaterial);
        }
        if (_ringRuntimes == null)
        {
            return;
        }
        foreach (RingRuntime runtime in _ringRuntimes)
        {
            if (runtime != null && runtime.Mesh != null)
            {
                Destroy(runtime.Mesh);
            }
            if (runtime != null && runtime.FillMaterial != null)
            {
                Destroy(runtime.FillMaterial);
            }
        }
    }

    private void Update()
    {
        ApplyMasterVisible();
        if (!MasterVisible)
        {
            return;
        }

        SampleSpectrum();
        UpdateSignalState();
        UpdateLayerPositions();
        DrawContours();
        DrawBars();
        DrawTentacles();
        DrawCore();
    }

    private void EnsureSharedMaterial()
    {
        if (_sharedLineMaterial != null)
        {
            return;
        }
        Shader shader = Shader.Find("Sprites/Default");
        if (shader == null)
        {
            shader = Shader.Find("Universal Render Pipeline/Unlit");
        }
        _sharedLineMaterial = new Material(shader);
        _sharedLineMaterial.hideFlags = HideFlags.HideAndDontSave;
    }

    private void BuildRingRuntimes()
    {
        _ringRuntimes = new RingRuntime[RingStyles.Length];
        for (int i = 0; i < RingStyles.Length; i++)
        {
            RingStyle style = RingStyles[i];
            RingRuntime runtime = new RingRuntime();
            runtime.Style = style;
            runtime.Peaks = new float[NumBars];

            GameObject lineObject = new GameObject("Ring_" + (i + 1));
            lineObject.transform.SetParent(transform, false);
            LineRenderer line = lineObject.AddComponent<LineRenderer>();
            ConfigureLine(line, style.Thickness, true);
            runtime.Line = line;

            if (style.FillEnabled)
            {
                GameObject fillObject = new GameObject("RingFill_" + (i + 1));
                fillObject.transform.SetParent(transform, false);
                runtime.Mesh = new Mesh();
                runtime.Mesh.name = "RingFill_" + (i + 1);
                runtime.Mesh.MarkDynamic();
                runtime.MeshFilter = fillObject.AddComponent<MeshFilter>();
                runtime.MeshFilter.sharedMesh = runtime.Mesh;
                runtime.MeshRenderer = fillObject.AddComponent<MeshRenderer>();
                runtime.FillMaterial = new Material(_sharedLineMaterial);
                runtime.FillMaterial.hideFlags = HideFlags.HideAndDontSave;
                runtime.MeshRenderer.sharedMaterial = runtime.FillMaterial;
            }

            _ringRuntimes[i] = runtime;
        }
    }

    private void BuildBarRuntimes()
    {
        _barRuntimes = new BarRuntime[BarStyles.Length];
        for (int i = 0; i < BarStyles.Length; i++)
        {
            BarStyle style = BarStyles[i];
            BarRuntime runtime = new BarRuntime();
            runtime.Style = style;
            runtime.Lines = new LineRenderer[NumBars];
            for (int barIndex = 0; barIndex < NumBars; barIndex++)
            {
                GameObject lineObject = new GameObject("Bar_" + (i + 1) + "_" + (barIndex + 1));
                lineObject.transform.SetParent(transform, false);
                LineRenderer line = lineObject.AddComponent<LineRenderer>();
                ConfigureLine(line, style.Thickness, false);
                line.positionCount = 2;
                runtime.Lines[barIndex] = line;
            }
            _barRuntimes[i] = runtime;
        }
    }

    private void BuildTentacles()
    {
        _tentacleRuntimes = new TentacleRuntime[TentacleCount];
        for (int i = 0; i < TentacleCount; i++)
        {
            GameObject lineObject = new GameObject("Tentacle_" + (i + 1));
            lineObject.transform.SetParent(transform, false);
            LineRenderer line = lineObject.AddComponent<LineRenderer>();
            ConfigureLine(line, TentacleThickness, false);
            line.positionCount = Mathf.Max(TentacleControlPointsMax, 3);
            line.widthCurve = BuildTentacleWidthCurve();
            _tentacleRuntimes[i] = new TentacleRuntime
            {
                Line = line,
                Seed = 0.41f * (i + 1),
                JitterSeed = 0.77f * (i + 1),
                Velocity = 0f,
            };
        }
    }

    private void BuildCore()
    {
        GameObject lineObject = new GameObject("TentacleCore");
        lineObject.transform.SetParent(transform, false);
        _coreLine = lineObject.AddComponent<LineRenderer>();
        ConfigureLine(_coreLine, TentacleCoreThickness, true);
        _coreLine.positionCount = Mathf.Max(TentacleCorePoints * 2, 6) + 1;
    }

    private void ConfigureLine(LineRenderer line, float width, bool loop)
    {
        line.sharedMaterial = _sharedLineMaterial;
        line.useWorldSpace = false;
        line.loop = loop;
        line.numCornerVertices = 4;
        line.numCapVertices = 4;
        line.textureMode = LineTextureMode.Stretch;
        line.alignment = LineAlignment.View;
        line.widthMultiplier = Mathf.Max(0.1f, width);
    }

    private float EstimateSuggestedCameraSize()
    {
        float baseRadius = CircleRadius * GlobalScale * Mathf.Max(0.1f, MainRadiusScale);
        float contourReach = baseRadius + Mathf.Max(BarHeightMax, 0f);
        float tentacleReach = baseRadius + Mathf.Max(TentacleLength, 0f) + Mathf.Min(Mathf.Abs(TentacleJitter), 400f);
        float coreReach = baseRadius + TentacleCoreOuterRadius * 2f;
        return Mathf.Max(32f, Mathf.Max(contourReach, Mathf.Max(tentacleReach, coreReach)) * 1.15f);
    }

    private void EnsureMainCameraReady()
    {
        Camera cam = Camera.main;
        if (cam == null)
        {
            GameObject cameraObject = new GameObject("Main Camera");
            cameraObject.tag = "MainCamera";
            cam = cameraObject.AddComponent<Camera>();
        }

        AyeExportCameraController controller = cam.GetComponent<AyeExportCameraController>();
        if (controller == null)
        {
            controller = cam.gameObject.AddComponent<AyeExportCameraController>();
        }

        controller.controllerEnabled = true;
        controller.requireRightMouse = false;
        controller.moveSpeed = 10f;
        controller.perspectivePanSpeed = 6f;
        controller.orthographicPanSpeed = 8f;
        controller.orthographicDragSpeed = 1f;
        controller.orthographicZoomSpeed = 2f;
        controller.orthographicMinSize = 2f;
        controller.orthographicMaxSize = Mathf.Max(64f, EstimateSuggestedCameraSize() * 3f);

        cam.orthographic = true;
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.backgroundColor = new Color(0f, 0f, 0f, 0f);
        Vector3 position = cam.transform.position;
        position.x = 0f;
        position.y = 0f;
        if (float.IsNaN(position.z) || float.IsInfinity(position.z) || position.z >= -1f)
        {
            position.z = -10f;
        }
        else
        {
            position.z = Mathf.Min(position.z, -10f);
        }
        cam.transform.position = position;
        cam.transform.rotation = Quaternion.identity;
        cam.orthographicSize = Mathf.Max(cam.orthographicSize, EstimateSuggestedCameraSize());
    }

    private AnimationCurve BuildTentacleWidthCurve()
    {
        Keyframe[] keys = new Keyframe[3];
        keys[0] = new Keyframe(0f, 1f);
        keys[1] = new Keyframe(Mathf.Clamp01(1f / Mathf.Max(1f, TentacleShaderBias)), Mathf.Lerp(1f, TentacleTipThickness, 0.4f));
        keys[2] = new Keyframe(1f, Mathf.Max(0.01f, TentacleTipThickness));
        return new AnimationCurve(keys);
    }

    private void ApplyMasterVisible()
    {
        if (_ringRuntimes != null)
        {
            foreach (RingRuntime runtime in _ringRuntimes)
            {
                if (runtime == null)
                {
                    continue;
                }
                if (runtime.Line != null)
                {
                    runtime.Line.enabled = MasterVisible && ContoursEnabled && runtime.Style.Enabled;
                }
                if (runtime.MeshRenderer != null)
                {
                    runtime.MeshRenderer.enabled = MasterVisible && ContoursEnabled && runtime.Style.Enabled && runtime.Style.FillEnabled;
                }
            }
        }
        if (_barRuntimes != null)
        {
            foreach (BarRuntime runtime in _barRuntimes)
            {
                if (runtime == null || runtime.Lines == null)
                {
                    continue;
                }
                bool visible = MasterVisible && BarsEnabled && runtime.Style.Enabled;
                foreach (LineRenderer line in runtime.Lines)
                {
                    if (line != null)
                    {
                        line.enabled = visible;
                    }
                }
            }
        }
        if (_tentacleRuntimes != null)
        {
            bool visible = MasterVisible && TentaclesEnabled;
            foreach (TentacleRuntime runtime in _tentacleRuntimes)
            {
                if (runtime != null && runtime.Line != null)
                {
                    runtime.Line.enabled = visible;
                }
            }
        }
        if (_coreLine != null)
        {
            _coreLine.enabled = MasterVisible && TentaclesEnabled && TentacleCoreEnabled;
        }
    }

    private void SampleSpectrum()
    {
        if (_audioSource == null)
        {
            FillFallbackSpectrum();
            return;
        }

        _audioSource.CopySpectrum(_spectrum);
        float sampleRate = Mathf.Max(1f, _audioSource.SampleRate);
        float nyquist = Mathf.Max(1f, sampleRate * 0.5f);
        float logMin = Mathf.Log10(Mathf.Max(1f, FreqMin));
        float logMax = Mathf.Log10(Mathf.Max(FreqMin + 1f, Mathf.Min(FreqMax, nyquist)));
        float energy = 0f;

        for (int i = 0; i < NumBars; i++)
        {
            float t0 = i / Mathf.Max(1f, NumBars);
            float t1 = (i + 1f) / Mathf.Max(1f, NumBars);
            float f0 = Mathf.Pow(10f, Mathf.Lerp(logMin, logMax, t0));
            float f1 = Mathf.Pow(10f, Mathf.Lerp(logMin, logMax, t1));
            int start = Mathf.Clamp(Mathf.FloorToInt((f0 / nyquist) * (_spectrum.Length - 1)), 0, _spectrum.Length - 1);
            int end = Mathf.Clamp(Mathf.CeilToInt((f1 / nyquist) * (_spectrum.Length - 1)), start + 1, _spectrum.Length);
            float sum = 0f;
            int count = 0;
            for (int index = start; index < end; index++)
            {
                sum += _spectrum[index];
                count++;
            }
            float value = count > 0 ? sum / count : 0f;
            _barTargets[i] = value;
            energy += value;
        }

        if (energy <= 0.000001f)
        {
            FillFallbackSpectrum();
            return;
        }

        float framePeak = 0.0001f;
        for (int i = 0; i < NumBars; i++)
        {
            framePeak = Mathf.Max(framePeak, _barTargets[i]);
        }
        _dynamicRange = Mathf.Max(framePeak, Mathf.Lerp(_dynamicRange, framePeak, Time.deltaTime * 2.5f));

        float blend = Mathf.Clamp01(1f - Smoothing);
        for (int i = 0; i < NumBars; i++)
        {
            float normalized = Mathf.Clamp01(_barTargets[i] / (_dynamicRange * 1.15f + 0.00001f));
            _barSamples[i] = Mathf.Lerp(_barSamples[i], normalized, blend);
        }
    }

    private void FillFallbackSpectrum()
    {
        float blend = Mathf.Clamp01(1f - Smoothing);
        float t = Time.time;
        for (int i = 0; i < NumBars; i++)
        {
            float v = 0.35f;
            v += Mathf.Sin(t * 1.11f + i * 0.24f) * 0.18f;
            v += Mathf.Sin(t * 0.53f + i * 0.11f) * 0.12f;
            v += Mathf.Sin(t * 1.93f + i * 0.05f) * 0.05f;
            _barSamples[i] = Mathf.Lerp(_barSamples[i], Mathf.Clamp01(v), blend);
        }
    }

    private void UpdateSignalState()
    {
        float sum = 0f;
        float maxValue = 0f;
        for (int i = 0; i < NumBars; i++)
        {
            sum += _barSamples[i];
            maxValue = Mathf.Max(maxValue, _barSamples[i]);
        }
        _rawA1 = NumBars > 0 ? sum / NumBars : 0f;
        float previous = _a1;
        _a1 = ApplyDamping(previous, _rawA1, KRiseDamping, KFallDamping);
        float delta = _a1 - previous;
        _k2 = Mathf.Sign(delta) * Mathf.Pow(Mathf.Abs(delta), Mathf.Max(0.01f, K2Pow));
        float drive = GetAudioDrive();

        float radiusTarget = CircleRadius * GlobalScale * MainRadiusScale;
        if (RadiusFollowsAudio)
        {
            radiusTarget *= 1f + drive * 0.28f;
        }
        float spring = Mathf.Clamp01(RadiusSpring + Mathf.Abs(drive) * RadiusGravity * 0.1f);
        _radiusVelocity = Mathf.Lerp(_radiusVelocity, (radiusTarget - _radiusState) * spring, 1f - RadiusDamping);
        _radiusState += _radiusVelocity * Mathf.Max(Time.deltaTime, 0.0001f);

        float rotationInput = RotationBase;
        if (RotationFollowsAudio)
        {
            rotationInput += Mathf.Sign(drive) * Mathf.Pow(Mathf.Abs(drive) + 0.0001f, 0.65f) * 2.2f;
        }
        _rotation += rotationInput * Time.deltaTime;

        float phaseSpeed = ColorCycleSpeed;
        if (ColorCycleFollowsAudio)
        {
            phaseSpeed *= 0.5f + Mathf.Pow(Mathf.Clamp01(Mathf.Abs(drive)), Mathf.Max(0.01f, ColorCyclePow));
        }
        _colorPhase = Mathf.Repeat(_colorPhase + phaseSpeed * Time.deltaTime * 0.1f, 1f);
    }

    private float GetAudioDrive()
    {
        return K2Enabled ? _k2 : _a1;
    }

    private float ApplyDamping(float current, float target, float riseDamping, float fallDamping)
    {
        float blend = target >= current ? 1f - Mathf.Clamp01(riseDamping) : 1f - Mathf.Clamp01(fallDamping);
        return Mathf.Lerp(current, target, Mathf.Max(0.001f, blend));
    }

    private void UpdateLayerPositions()
    {
        int pointCount = _layerPositions[0].Length - 1;
        int segmentCount = Mathf.Max(1, CircleSegments);
        float drive = GetAudioDrive();
        float baseAngleStep = Mathf.PI * 2f / Mathf.Max(1, pointCount);

        for (int layerIndex = 0; layerIndex < RingStyles.Length; layerIndex++)
        {
            RingStyle style = RingStyles[layerIndex];
            for (int pointIndex = 0; pointIndex < pointCount; pointIndex++)
            {
                int barIndex = (pointIndex / segmentCount) % NumBars;
                int sampleIndex = (barIndex * style.Step) % NumBars;
                float sample = _barSamples[sampleIndex];
                if (style.Decay > 0f)
                {
                    float peak = style.Decay >= 0.9998f ? sample : Mathf.Max(sample, _ringRuntimes[layerIndex].Peaks[sampleIndex] * style.Decay);
                    _ringRuntimes[layerIndex].Peaks[sampleIndex] = peak;
                    sample = Mathf.Max(sample, peak);
                }
                float amplitude = Mathf.Lerp(BarHeightMin, BarHeightMax, sample) * RingAmplitude(layerIndex);
                float radius = _radiusState * style.Scale + amplitude;
                float angle = pointIndex * baseAngleStep;
                angle += _rotation * style.RotationSpeed;
                angle += Mathf.Sign(drive) * Mathf.Pow(Mathf.Abs(drive) + 0.0001f, style.RotationPower) * 0.12f;
                _layerPositions[layerIndex][pointIndex] = new Vector3(Mathf.Cos(angle), Mathf.Sin(angle), 0f) * radius;
            }
            _layerPositions[layerIndex][pointCount] = _layerPositions[layerIndex][0];
        }
    }

    private float RingAmplitude(int layerIndex)
    {
        switch (layerIndex)
        {
            case 0: return 0.18f;
            case 1: return 0.26f;
            case 2: return 0.08f;
            case 3: return 0.3f;
            default: return 0.22f;
        }
    }

    private void DrawContours()
    {
        if (_ringRuntimes == null)
        {
            return;
        }

        for (int i = 0; i < _ringRuntimes.Length; i++)
        {
            RingRuntime runtime = _ringRuntimes[i];
            if (runtime == null)
            {
                continue;
            }

            bool visible = MasterVisible && ContoursEnabled && runtime.Style.Enabled;
            if (runtime.Line != null)
            {
                runtime.Line.enabled = visible;
            }
            if (runtime.MeshRenderer != null)
            {
                runtime.MeshRenderer.enabled = visible && runtime.Style.FillEnabled;
            }
            if (!visible)
            {
                continue;
            }

            Vector3[] positions = _layerPositions[i];
            runtime.Line.positionCount = positions.Length;
            runtime.Line.SetPositions(positions);
            Color ringColor = EvaluateExportColor(i / Mathf.Max(1f, RingStyles.Length - 1f), runtime.Style.Color);
            ringColor.a = runtime.Style.Alpha;
            runtime.Line.startColor = ringColor;
            runtime.Line.endColor = ringColor;

            if (runtime.Mesh != null)
            {
                UpdateFillMesh(runtime, positions, ringColor);
            }
        }
    }

    private void UpdateFillMesh(RingRuntime runtime, Vector3[] positions, Color ringColor)
    {
        if (runtime.Mesh == null || runtime.MeshRenderer == null)
        {
            return;
        }

        int edgeCount = positions.Length - 1;
        Vector3[] vertices = new Vector3[edgeCount + 1];
        int[] triangles = new int[edgeCount * 3];
        vertices[0] = Vector3.zero;
        for (int i = 0; i < edgeCount; i++)
        {
            vertices[i + 1] = positions[i];
            int tri = i * 3;
            triangles[tri] = 0;
            triangles[tri + 1] = i + 1;
            triangles[tri + 2] = i == edgeCount - 1 ? 1 : i + 2;
        }
        runtime.Mesh.Clear();
        runtime.Mesh.vertices = vertices;
        runtime.Mesh.triangles = triangles;
        runtime.Mesh.RecalculateBounds();
        Color fillColor = ringColor;
        fillColor.a = runtime.Style.FillAlpha;
        runtime.MeshRenderer.sharedMaterial.color = fillColor;
    }

    private void DrawBars()
    {
        if (_barRuntimes == null)
        {
            return;
        }

        for (int runtimeIndex = 0; runtimeIndex < _barRuntimes.Length; runtimeIndex++)
        {
            BarRuntime runtime = _barRuntimes[runtimeIndex];
            if (runtime == null || runtime.Lines == null)
            {
                continue;
            }

            bool visible = MasterVisible && BarsEnabled && runtime.Style.Enabled;
            for (int barIndex = 0; barIndex < runtime.Lines.Length; barIndex++)
            {
                LineRenderer line = runtime.Lines[barIndex];
                if (line == null)
                {
                    continue;
                }
                line.enabled = visible;
                if (!visible)
                {
                    continue;
                }

                int layerPointIndex = Mathf.Clamp(barIndex * Mathf.Max(1, CircleSegments), 0, _layerPositions[runtime.Style.StartRing].Length - 2);
                Vector3 start = _layerPositions[runtime.Style.StartRing][layerPointIndex];
                Vector3 end = _layerPositions[runtime.Style.EndRing][layerPointIndex];
                Vector3 span = end - start;
                float fullLength = span.magnitude;
                if (fullLength <= 0.0001f)
                {
                    line.SetPosition(0, start);
                    line.SetPosition(1, end);
                    continue;
                }

                float signal = _barSamples[barIndex % NumBars];
                float desiredLength = runtime.Style.FixedLength
                    ? runtime.Style.FixedLengthValue
                    : Mathf.Lerp(BarLengthMin, Mathf.Min(BarLengthMax, fullLength), signal);
                desiredLength = Mathf.Clamp(desiredLength, 0f, fullLength);
                Vector3 dir = span / fullLength;
                if (runtime.Style.FromCenter)
                {
                    Vector3 center = Vector3.Lerp(start, end, 0.5f);
                    Vector3 half = dir * desiredLength * 0.5f;
                    start = center - half;
                    end = center + half;
                }
                else if (runtime.Style.FromEnd)
                {
                    start = end - dir * desiredLength;
                }
                else
                {
                    end = start + dir * desiredLength;
                }

                line.SetPosition(0, start);
                line.SetPosition(1, end);
                Color startColor = EvaluateExportColor(runtime.Style.StartRing / 4f, RingStyles[runtime.Style.StartRing].Color);
                Color endColor = EvaluateExportColor(runtime.Style.EndRing / 4f, RingStyles[runtime.Style.EndRing].Color);
                startColor.a = Mathf.Lerp(0.25f, 1f, signal);
                endColor.a = Mathf.Lerp(0.25f, 1f, signal);
                line.startColor = startColor;
                line.endColor = endColor;
            }
        }
    }

    private void DrawTentacles()
    {
        if (_tentacleRuntimes == null)
        {
            return;
        }

        bool visible = MasterVisible && TentaclesEnabled;
        float drive = GetAudioDrive();
        float time = Time.time;
        float baseRadius = _radiusState * 1.05f;
        int controlPoints = Mathf.Clamp((TentacleControlPointsMin + TentacleControlPointsMax) / 2, 3, 20);

        for (int tentacleIndex = 0; tentacleIndex < _tentacleRuntimes.Length; tentacleIndex++)
        {
            TentacleRuntime runtime = _tentacleRuntimes[tentacleIndex];
            if (runtime == null || runtime.Line == null)
            {
                continue;
            }
            runtime.Line.enabled = visible;
            if (!visible)
            {
                continue;
            }

            runtime.Line.positionCount = controlPoints;
            float normalizedIndex = tentacleIndex / Mathf.Max(1f, TentacleCount);
            float rootAngle = normalizedIndex * Mathf.PI * 2f + _rotation * 0.2f;
            float jitter = TentacleJitter <= 0f ? 0f : Mathf.Sin(time * Mathf.Max(0.01f, TentacleJitterSpeed) + runtime.JitterSeed) * TentacleJitter;
            if (TentacleRandomJitter)
            {
                jitter *= Mathf.PerlinNoise(runtime.JitterSeed, time * 0.1f);
            }
            float lengthTarget = TentacleLength + jitter + Mathf.Abs(drive) * TentacleKInfluence * 40f;
            runtime.Velocity = Mathf.Lerp(runtime.Velocity, lengthTarget, 1f - TentacleWaterDamping);
            float clampedLength = Mathf.Clamp(runtime.Velocity, TentacleLength * 0.15f, TentacleLength * Mathf.Max(1f, TentacleStretchLimit + 0.2f));

            for (int pointIndex = 0; pointIndex < controlPoints; pointIndex++)
            {
                float t = pointIndex / Mathf.Max(1f, controlPoints - 1f);
                float lengthFactor = Mathf.Pow(t, Mathf.Max(0.05f, 2f - TentacleTipBias));
                float radial = baseRadius + clampedLength * lengthFactor;
                float sway = Mathf.Sin(time * Mathf.Max(0.01f, TentacleSwaySpeed) + runtime.Seed + t * TentacleSwayDensity * 6.28318f);
                float noise = Mathf.PerlinNoise(runtime.Seed * 2.1f, time * 0.35f + t * 1.7f) - 0.5f;
                float side = (sway * TentacleAngleStiffness + noise * TentacleLengthStiffness) * TentacleTurbulence;
                side *= (1f - t) * (0.25f + Mathf.Abs(drive));
                float angle = rootAngle + side * 0.004f;
                Vector2 dir = new Vector2(Mathf.Cos(angle), Mathf.Sin(angle));
                Vector2 tangent = new Vector2(-dir.y, dir.x);
                Vector2 point = dir * radial + tangent * side;
                runtime.Line.SetPosition(pointIndex, new Vector3(point.x, point.y, 0f));
            }

            Color baseColor = EvaluateExportColor(normalizedIndex, TentacleBaseColor);
            baseColor.a = TentacleShaderEnabled ? TentacleShaderAlphaStart : TentacleShaderAlphaStart;
            Color tipColor = EvaluateExportColor(Mathf.Repeat(normalizedIndex + 0.2f, 1f), TentacleShaderEnabled ? TentacleTipColor : TentacleBaseColor);
            tipColor.a = TentacleShaderEnabled ? TentacleShaderAlphaEnd : baseColor.a;
            runtime.Line.startColor = baseColor;
            runtime.Line.endColor = tipColor;
        }
    }

    private void DrawCore()
    {
        if (_coreLine == null)
        {
            return;
        }

        bool visible = MasterVisible && TentaclesEnabled && TentacleCoreEnabled;
        _coreLine.enabled = visible;
        if (!visible)
        {
            return;
        }

        int steps = Mathf.Max(TentacleCorePoints * 2, 6);
        _coreLine.positionCount = steps + 1;
        float drive = GetAudioDrive();
        float rotation = Time.time * (TentacleCoreBaseSpeed + Mathf.Abs(_k2) * TentacleCoreKSpeed + Mathf.Abs(_a1) * TentacleCorePSpeed);
        float outer = TentacleCoreOuterRadius * GlobalScale * (1f + Mathf.Abs(drive) * 0.12f);
        for (int index = 0; index < steps; index++)
        {
            float angle = rotation + (index / (float)steps) * Mathf.PI * 2f;
            float radius = (index % 2 == 0) ? outer : outer * Mathf.Clamp(TentacleCoreInnerRatio, 0.05f, 0.95f);
            _coreLine.SetPosition(index, new Vector3(Mathf.Cos(angle) * radius, Mathf.Sin(angle) * radius, 0f));
        }
        _coreLine.SetPosition(steps, _coreLine.GetPosition(0));
        Color coreColor = EvaluateExportColor(0.5f, TentacleCoreColor);
        coreColor.a = TentacleCoreColor.a / 255f;
        _coreLine.startColor = coreColor;
        _coreLine.endColor = coreColor;
    }

    private Color EvaluateExportColor(float normalizedPosition, Color32 fallback)
    {
        if (!ColorDynamic)
        {
            return fallback;
        }

        float shifted = Mathf.Repeat(normalizedPosition + _colorPhase, 1f);
        Color dynamicColor = GradientEnabled ? EvaluateGradient(shifted) : EvaluateScheme(shifted);
        return Color.Lerp(fallback, dynamicColor, 0.72f);
    }

    private Color EvaluateGradient(float position)
    {
        if (GradientPoints == null || GradientPoints.Length == 0)
        {
            return EvaluateScheme(position);
        }
        if (GradientPoints.Length == 1)
        {
            return GradientPoints[0].Color;
        }

        GradientPointData previous = GradientPoints[0];
        for (int i = 1; i < GradientPoints.Length; i++)
        {
            GradientPointData next = GradientPoints[i];
            if (position <= next.Position)
            {
                float t = Mathf.InverseLerp(previous.Position, next.Position, position);
                return Color.Lerp(previous.Color, next.Color, t);
            }
            previous = next;
        }
        return GradientPoints[GradientPoints.Length - 1].Color;
    }

    private Color EvaluateScheme(float position)
    {
        position = Mathf.Repeat(position, 1f);
        switch (ColorScheme)
        {
            case "fire":
                return Color.Lerp(new Color(1f, 0.25f, 0.05f, 1f), new Color(1f, 0.9f, 0.15f, 1f), position);
            case "ocean":
                return Color.Lerp(new Color(0.1f, 0.7f, 1f, 1f), new Color(0f, 1f, 0.8f, 1f), position);
            case "mono":
                return Color.Lerp(Color.white, new Color(0.45f, 0.45f, 0.45f, 1f), position);
            default:
                return Color.HSVToRGB(position, 0.85f, 1f);
        }
    }
}
'''