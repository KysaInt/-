using System.Collections.Generic;
using UnityEngine;

[DisallowMultipleComponent]
[AddComponentMenu("AYE导出/预设效果/validation_preset")]
[RequireComponent(typeof(PyStyleVisualizer))]
[RequireComponent(typeof(WindowsAudioCapture))]
[RequireComponent(typeof(AyeExportAudioFileDriver))]
public class ValidationPreset : MonoBehaviour
{
    public enum ExportAudioInputMode
    {
        WindowsLoopback = 0,
        AudioFile = 1,
    }

    [Header("Preset")]
    public string sourcePresetName = "validation_preset";

    [Header("Audio Input")]
    public ExportAudioInputMode audioInputMode = ExportAudioInputMode.WindowsLoopback;
    public AudioClip audioFile;
    public bool autoPlayAudioFile = true;
    public bool loopAudioFile = true;

    [Header("Camera")]
    public bool attachCameraControllerIfMissing = true;

    private void Reset()
    {
        ApplyDefaults();
    }

    private void Awake()
    {
        ApplyDefaults();
    }

    private void OnValidate()
    {
        ApplyDefaults();
    }

    private void ApplyDefaults()
    {
        PyStyleVisualizer visualizer = GetComponent<PyStyleVisualizer>();
        WindowsAudioCapture windowsCapture = GetComponent<WindowsAudioCapture>();
        if (visualizer != null)
        {
            visualizer.autoFrameMainCamera = false;
            visualizer.numBars = 4;
            visualizer.smoothing = 0.7f;
            visualizer.rotationBase = 1.0f;
            visualizer.mainRadiusScale = 1.0f;
            visualizer.barHeightMin = 167;
            visualizer.barHeightMax = 762;
            visualizer.colorScheme = "custom";
            visualizer.gradientEnabled = false;
            visualizer.gradientMode = "frequency";
            visualizer.gradientPoints = new List<PyStyleGradientPoint>
            {
                new PyStyleGradientPoint(0.0f, new Color32(172, 161, 255, 255)),
                new PyStyleGradientPoint(1.0f, new Color32(176, 255, 218, 255)),
                new PyStyleGradientPoint(0.5f, new Color32(246, 255, 142, 255))
            };
            visualizer.colorDynamic = true;
            visualizer.colorCycleSpeed = 1.7f;
            visualizer.colorCyclePow = 2.68f;
            visualizer.colorCycleFollowsAudio = true;
            visualizer.circleRadius = 300.0f;
            visualizer.circleSegments = 2;
            visualizer.globalScale = 1.4f;
            visualizer.rotationFollowsAudio = true;
            visualizer.radiusFollowsAudio = true;
            visualizer.radiusDamping = 0.7f;
            visualizer.radiusSpring = 0.12f;
            visualizer.radiusGravity = 0.12f;
            visualizer.barLengthMin = 38.0f;
            visualizer.barLengthMax = 1000.0f;
            visualizer.freqMin = 20;
            visualizer.freqMax = 20400;
            visualizer.a1TimeWindow = 0.02f;
            visualizer.k2Enabled = false;
            visualizer.k2Pow = 1.8f;
            visualizer.masterVisible = true;
            visualizer.kRiseDamping = 0.1f;
            visualizer.kFallDamping = 0.5f;
            visualizer.barUseIndependentDamping = false;
            visualizer.barIndependentRiseDamping = 0.02f;
            visualizer.barIndependentFallDamping = 0.02f;
            visualizer.barUseIndependentTimeWindow = false;
            visualizer.barTimeWindow = 0.01f;
            visualizer.barDefaultHeight = 0.0f;
            visualizer.barInternalMin = 0.0f;
            visualizer.barInternalMax = 300.0f;
            visualizer.c1On = true;
            visualizer.c1Color = new Color32(100, 180, 255, 255);
            visualizer.c1Alpha = 100;
            visualizer.c1Thick = 1;
            visualizer.c1Fill = false;
            visualizer.c1FillAlpha = 30;
            visualizer.c1Step = 2;
            visualizer.c1Decay = 0.995f;
            visualizer.c1RotSpeed = 1.0f;
            visualizer.c1RotPow = 0.5f;
            visualizer.c1UseIndependentDamping = false;
            visualizer.c1IndependentRiseDamping = 0.1f;
            visualizer.c1IndependentFallDamping = 0.999f;
            visualizer.c2On = false;
            visualizer.c2Color = new Color32(150, 220, 255, 255);
            visualizer.c2Alpha = 150;
            visualizer.c2Thick = 2;
            visualizer.c2Fill = false;
            visualizer.c2FillAlpha = 50;
            visualizer.c2Step = 2;
            visualizer.c2RotSpeed = 1.0f;
            visualizer.c2RotPow = 0.5f;
            visualizer.c2UseIndependentDamping = false;
            visualizer.c2IndependentRiseDamping = 0.1f;
            visualizer.c2IndependentFallDamping = 0.999f;
            visualizer.c3On = false;
            visualizer.c3Color = new Color32(255, 255, 255, 255);
            visualizer.c3Alpha = 60;
            visualizer.c3Thick = 1;
            visualizer.c3Fill = false;
            visualizer.c3FillAlpha = 20;
            visualizer.c3RotSpeed = 1.0f;
            visualizer.c3RotPow = 0.5f;
            visualizer.c4On = true;
            visualizer.c4Color = new Color32(255, 255, 255, 255);
            visualizer.c4Alpha = 180;
            visualizer.c4Thick = 2;
            visualizer.c4Fill = true;
            visualizer.c4FillAlpha = 60;
            visualizer.c4Step = 2;
            visualizer.c4RotSpeed = 1.0f;
            visualizer.c4RotPow = 0.5f;
            visualizer.c4UseIndependentDamping = false;
            visualizer.c4IndependentRiseDamping = 0.1f;
            visualizer.c4IndependentFallDamping = 0.999f;
            visualizer.c5On = true;
            visualizer.c5Color = new Color32(255, 200, 100, 255);
            visualizer.c5Alpha = 100;
            visualizer.c5Thick = 1;
            visualizer.c5Fill = false;
            visualizer.c5FillAlpha = 30;
            visualizer.c5Step = 2;
            visualizer.c5Decay = 0.995f;
            visualizer.c5RotSpeed = 1.0f;
            visualizer.c5RotPow = 0.5f;
            visualizer.c5UseIndependentDamping = false;
            visualizer.c5IndependentRiseDamping = 0.1f;
            visualizer.c5IndependentFallDamping = 0.999f;
            visualizer.b12On = false;
            visualizer.b12Thick = 2;
            visualizer.b12Fixed = false;
            visualizer.b12FixedLen = 30;
            visualizer.b12FromStart = true;
            visualizer.b12FromEnd = false;
            visualizer.b12FromCenter = false;
            visualizer.b12UseIndependentDamping = false;
            visualizer.b12IndependentRiseDamping = 0.1f;
            visualizer.b12IndependentFallDamping = 0.999f;
            visualizer.b23On = false;
            visualizer.b23Thick = 3;
            visualizer.b23Fixed = false;
            visualizer.b23FixedLen = 30;
            visualizer.b23FromStart = true;
            visualizer.b23FromEnd = false;
            visualizer.b23FromCenter = false;
            visualizer.b23UseIndependentDamping = false;
            visualizer.b23IndependentRiseDamping = 0.1f;
            visualizer.b23IndependentFallDamping = 0.999f;
            visualizer.b34On = true;
            visualizer.b34Thick = 3;
            visualizer.b34Fixed = false;
            visualizer.b34FixedLen = 30;
            visualizer.b34FromStart = true;
            visualizer.b34FromEnd = false;
            visualizer.b34FromCenter = false;
            visualizer.b34UseIndependentDamping = false;
            visualizer.b34IndependentRiseDamping = 0.1f;
            visualizer.b34IndependentFallDamping = 0.999f;
            visualizer.b45On = false;
            visualizer.b45Thick = 2;
            visualizer.b45Fixed = false;
            visualizer.b45FixedLen = 30;
            visualizer.b45FromStart = true;
            visualizer.b45FromEnd = false;
            visualizer.b45FromCenter = false;
            visualizer.b45UseIndependentDamping = false;
            visualizer.b45IndependentRiseDamping = 0.1f;
            visualizer.b45IndependentFallDamping = 0.999f;
            visualizer.contoursEnabled = false;
            visualizer.barsEnabled = false;
            visualizer.tentaclesEnabled = true;
            visualizer.tentacleOn = true;
            visualizer.tentacleColor = new Color32(204, 56, 56, 255);
            visualizer.tentacleAlpha = 255;
            visualizer.tentacleThick = 1;
            visualizer.tentacleCount = 4;
            visualizer.tentacleLength = 0.0f;
            visualizer.tentacleLengthJitter = 8000.0f;
            visualizer.tentacleLengthJitterSpeed = 0.0f;
            visualizer.tentacleLengthJitterRandom = true;
            visualizer.tentacleControlPointsMin = 6;
            visualizer.tentacleControlPointsMax = 6;
            visualizer.tentacleTipBias = 0.5f;
            visualizer.tentacleTurbulence = 0.0f;
            visualizer.tentacleKInfluence = 0.46f;
            visualizer.tentacleSwaySpeed = 0.0f;
            visualizer.tentacleSwayDensity = 0.0f;
            visualizer.tentacleTipThickness = 0.15f;
            visualizer.tentacleWaterDamping = 0.0f;
            visualizer.tentacleAngleStiffness = 0.18f;
            visualizer.tentacleLengthStiffness = 0.24f;
            visualizer.tentacleStretchLimit = 1.16f;
            visualizer.tentacleShaderEnabled = true;
            visualizer.tentacleShaderTipColor = new Color32(0, 0, 0, 255);
            visualizer.tentacleShaderAlphaStart = 0.0f;
            visualizer.tentacleShaderAlphaEnd = 1.0f;
            visualizer.tentacleShaderBias = 3.0f;
            visualizer.tentacleCoreOn = true;
            visualizer.tentacleCoreColor = new Color32(225, 255, 245, 255);
            visualizer.tentacleCoreAlpha = 180;
            visualizer.tentacleCoreThick = 2;
            visualizer.tentacleCorePoints = 6;
            visualizer.tentacleCoreOuterRadius = 26.0f;
            visualizer.tentacleCoreInnerRatio = 0.42f;
            visualizer.tentacleCoreBaseSpeed = 0.0f;
            visualizer.tentacleCoreKSpeed = 3.0f;
            visualizer.tentacleCorePSpeed = 1.35f;
            visualizer.kpBindTentacleTurbulenceK = false;
            visualizer.kpTentacleTurbulenceKWmin = 0.22f;
            visualizer.kpTentacleTurbulenceKWmax = 0.523f;
            visualizer.kpBindTentacleCoreBaseSpeedK = true;
            visualizer.kpTentacleCoreBaseSpeedKWmin = 0.0f;
            visualizer.kpTentacleCoreBaseSpeedKWmax = 3.0f;
            visualizer.kpBindTentacleCoreBaseSpeedP = true;
            visualizer.kpTentacleCoreBaseSpeedPWmin = 0.0f;
            visualizer.kpTentacleCoreBaseSpeedPWmax = 10.0f;
            visualizer.kpBindTentacleTipThicknessP = false;
            visualizer.kpTentacleTipThicknessPWmin = 0.0f;
            visualizer.kpTentacleTipThicknessPWmax = 1.0f;
            visualizer.kpBindTentacleThickP = false;
            visualizer.kpTentacleThickPWmin = 150.0f;
            visualizer.kpTentacleThickPWmax = 0.0f;
            visualizer.kpBindTentacleThickK = true;
            visualizer.kpTentacleThickKWmin = 0.0f;
            visualizer.kpTentacleThickKWmax = 200.0f;
            visualizer.kpBindTentacleLengthK = true;
            visualizer.kpTentacleLengthKWmax = 600.0f;
            visualizer.kpBindTentacleLengthJitterSpeedP = false;
            visualizer.kpTentacleLengthJitterSpeedPWmax = 1.0f;
            visualizer.kpBindTentacleShaderAlphaStartP = false;
            visualizer.kpTentacleShaderAlphaStartPWmax = 1.0f;
            visualizer.kpBindTentacleShaderAlphaStartK = true;
            visualizer.kpTentacleShaderAlphaStartKWmin = 1.0f;
            visualizer.kpTentacleShaderAlphaStartKWmax = -1.0f;
            visualizer.kpBindTentacleLengthJitterK = true;
            visualizer.kpTentacleLengthJitterKWmin = -8000.0f;
            visualizer.kpTentacleLengthJitterKWmax = 0.0f;
        }

        if (windowsCapture != null)
        {
            windowsCapture.enableCapture = audioInputMode == ExportAudioInputMode.WindowsLoopback;
        }

        AyeExportAudioFileDriver audioFileDriver = GetComponent<AyeExportAudioFileDriver>();
        if (audioFileDriver != null)
        {
            audioFileDriver.enableFileInput = audioInputMode == ExportAudioInputMode.AudioFile;
            audioFileDriver.audioClip = audioFile;
            audioFileDriver.playOnStart = autoPlayAudioFile;
            audioFileDriver.loopPlayback = loopAudioFile;
        }

        if (attachCameraControllerIfMissing)
        {
            Camera mainCamera = Camera.main;
            if (mainCamera != null && mainCamera.GetComponent<AyeExportCameraController>() == null)
            {
                mainCamera.gameObject.AddComponent<AyeExportCameraController>();
            }
        }
    }
}
