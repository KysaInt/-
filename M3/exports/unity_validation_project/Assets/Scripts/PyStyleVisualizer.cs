using System;
using System.Collections.Generic;
using UnityEngine;

[Serializable]
public class PyStyleGradientPoint
{
    [Range(0f, 1f)]
    public float position = 0f;
    public Color color = Color.white;

    public PyStyleGradientPoint()
    {
    }

    public PyStyleGradientPoint(float position, Color color)
    {
        this.position = position;
        this.color = color;
    }
}

/// <summary>
/// PyOpenGL circular spectrum visualizer adapted to Unity.
/// Mirrors the original Python behavior with log bins, K1/K2,
/// closed B-spline contours, peak decay layers, and fixed bar links.
/// </summary>
public class PyStyleVisualizer : MonoBehaviour
{
    [Header("Core")]
    public int numBars = 64;
    [Range(0f, 0.999f)] public float smoothing = 0.7f;
    [Range(0f, 2f)] public float damping = 0.8f;
    [Range(0f, 3f)] public float springStrength = 0.45f;
    [Range(0f, 2f)] public float gravity = 0.5f;
    [Range(0f, 10f)] public float rotationBase = 1f;
    [Range(0.1f, 10f)] public float mainRadiusScale = 1f;
    public int barHeightMin = 0;
    public int barHeightMax = 500;

    [Header("Color")]
    public string colorScheme = "rainbow";
    public bool gradientEnabled = true;
    public string gradientMode = "frequency";
    public List<PyStyleGradientPoint> gradientPoints = new List<PyStyleGradientPoint>
    {
        new PyStyleGradientPoint(0f, new Color32(255, 0, 128, 255)),
        new PyStyleGradientPoint(1f, new Color32(0, 255, 255, 255)),
    };
    public bool colorDynamic = false;
    [Range(0f, 5f)] public float colorCycleSpeed = 1f;
    [Range(0.01f, 5f)] public float colorCyclePow = 2f;
    public bool colorCycleFollowsAudio = true;

    [Header("Circle")]
    public float circleRadius = 150f;
    public int circleSegments = 1;
    [Range(0.1f, 4f)] public float globalScale = 1f;
    public bool rotationFollowsAudio = true;
    public bool radiusFollowsAudio = true;
    [Range(0f, 0.999f)] public float radiusDamping = 0.92f;
    [Range(0f, 1f)] public float radiusSpring = 0.15f;
    [Range(0f, 1f)] public float radiusGravity = 0.3f;

    [Header("Bars")]
    public float barLengthMin = 0f;
    public float barLengthMax = 300f;
    public int freqMin = 20;
    public int freqMax = 20000;
    [Min(1f)] public float spectrumSampleRate = 48000f;
    public float a1TimeWindow = 10f;
    public bool k2Enabled = false;
    public float k2Pow = 1f;
    public bool masterVisible = true;

    [Header("M2 Dynamics")]
    [Range(0f, 0.999f)] public float kRiseDamping = 0.1f;
    [Range(0f, 0.999f)] public float kFallDamping = 0.999f;
    public bool barUseIndependentDamping = false;
    [Range(0f, 0.999f)] public float barIndependentRiseDamping = 0.1f;
    [Range(0f, 0.999f)] public float barIndependentFallDamping = 0.999f;
    public bool barUseIndependentTimeWindow = false;
    [Min(0.01f)] public float barTimeWindow = 10f;
    public float barDefaultHeight = 0f;
    public float barInternalMin = 0f;
    public float barInternalMax = 300f;

    [Header("Presentation")]
    public bool autoFrameMainCamera = true;

    [Header("C1 Inner Slow Peak")]
    public bool c1On = true;
    public Color c1Color = new Color32(100, 180, 255, 255);
    public int c1Alpha = 100;
    public int c1Thick = 1;
    public bool c1Fill = false;
    public int c1FillAlpha = 30;
    public int c1Step = 2;
    public float c1Decay = 0.995f;
    public float c1RotSpeed = 1f;
    public float c1RotPow = 0.5f;
    public bool c1UseIndependentDamping = false;
    [Range(0f, 0.999f)] public float c1IndependentRiseDamping = 0.1f;
    [Range(0f, 0.999f)] public float c1IndependentFallDamping = 0.999f;

    [Header("C2 Inner Fast")]
    public bool c2On = false;
    public Color c2Color = new Color32(150, 220, 255, 255);
    public int c2Alpha = 150;
    public int c2Thick = 2;
    public bool c2Fill = false;
    public int c2FillAlpha = 50;
    public int c2Step = 2;
    public float c2RotSpeed = 1f;
    public float c2RotPow = 0.5f;
    public bool c2UseIndependentDamping = false;
    [Range(0f, 0.999f)] public float c2IndependentRiseDamping = 0.1f;
    [Range(0f, 0.999f)] public float c2IndependentFallDamping = 0.999f;

    [Header("C3 Base Circle")]
    public bool c3On = false;
    public Color c3Color = Color.white;
    public int c3Alpha = 60;
    public int c3Thick = 1;
    public bool c3Fill = false;
    public int c3FillAlpha = 20;
    public float c3RotSpeed = 1f;
    public float c3RotPow = 0.5f;

    [Header("C4 Outer Fast")]
    public bool c4On = true;
    public Color c4Color = Color.white;
    public int c4Alpha = 180;
    public int c4Thick = 2;
    public bool c4Fill = true;
    public int c4FillAlpha = 60;
    public int c4Step = 2;
    public float c4RotSpeed = 1f;
    public float c4RotPow = 0.5f;
    public bool c4UseIndependentDamping = false;
    [Range(0f, 0.999f)] public float c4IndependentRiseDamping = 0.1f;
    [Range(0f, 0.999f)] public float c4IndependentFallDamping = 0.999f;

    [Header("C5 Outer Slow Peak")]
    public bool c5On = true;
    public Color c5Color = new Color32(255, 200, 100, 255);
    public int c5Alpha = 100;
    public int c5Thick = 1;
    public bool c5Fill = false;
    public int c5FillAlpha = 30;
    public int c5Step = 2;
    public float c5Decay = 0.995f;
    public float c5RotSpeed = 1f;
    public float c5RotPow = 0.5f;
    public bool c5UseIndependentDamping = false;
    [Range(0f, 0.999f)] public float c5IndependentRiseDamping = 0.1f;
    [Range(0f, 0.999f)] public float c5IndependentFallDamping = 0.999f;

    [Header("B12")]
    public bool b12On = false;
    public int b12Thick = 2;
    public bool b12Fixed = false;
    public int b12FixedLen = 30;
    public bool b12FromStart = true;
    public bool b12FromEnd = false;
    public bool b12FromCenter = false;
    public bool b12UseIndependentDamping = false;
    [Range(0f, 0.999f)] public float b12IndependentRiseDamping = 0.1f;
    [Range(0f, 0.999f)] public float b12IndependentFallDamping = 0.999f;

    [Header("B23")]
    public bool b23On = false;
    public int b23Thick = 3;
    public bool b23Fixed = false;
    public int b23FixedLen = 30;
    public bool b23FromStart = true;
    public bool b23FromEnd = false;
    public bool b23FromCenter = false;
    public bool b23UseIndependentDamping = false;
    [Range(0f, 0.999f)] public float b23IndependentRiseDamping = 0.1f;
    [Range(0f, 0.999f)] public float b23IndependentFallDamping = 0.999f;

    [Header("B34")]
    public bool b34On = true;
    public int b34Thick = 3;
    public bool b34Fixed = false;
    public int b34FixedLen = 30;
    public bool b34FromStart = true;
    public bool b34FromEnd = false;
    public bool b34FromCenter = false;
    public bool b34UseIndependentDamping = false;
    [Range(0f, 0.999f)] public float b34IndependentRiseDamping = 0.1f;
    [Range(0f, 0.999f)] public float b34IndependentFallDamping = 0.999f;

    [Header("B45")]
    public bool b45On = false;
    public int b45Thick = 2;
    public bool b45Fixed = false;
    public int b45FixedLen = 30;
    public bool b45FromStart = true;
    public bool b45FromEnd = false;
    public bool b45FromCenter = false;
    public bool b45UseIndependentDamping = false;
    [Range(0f, 0.999f)] public float b45IndependentRiseDamping = 0.1f;
    [Range(0f, 0.999f)] public float b45IndependentFallDamping = 0.999f;

    [Header("M3 Groups")]
    public bool contoursEnabled = true;
    public bool barsEnabled = true;
    public bool tentaclesEnabled = true;

    [Header("M3 Tentacles")]
    public bool tentacleOn = true;
    public Color tentacleColor = new Color32(130, 240, 220, 255);
    public int tentacleAlpha = 170;
    public int tentacleThick = 3;
    public int tentacleCount = 16;
    public float tentacleLength = 280f;
    public float tentacleLengthJitter = 80f;
    public float tentacleLengthJitterSpeed = 0.35f;
    public bool tentacleLengthJitterRandom = false;
    public int tentacleControlPointsMin = 3;
    public int tentacleControlPointsMax = 5;
    public float tentacleTipBias = 1.85f;
    public float tentacleTurbulence = 46f;
    public float tentacleKInfluence = 1.35f;
    public float tentacleSwaySpeed = 1.1f;
    public float tentacleSwayDensity = 2.4f;
    public float tentacleTipThickness = 0.15f;
    public float tentacleWaterDamping = 0.84f;
    public float tentacleAngleStiffness = 0.18f;
    public float tentacleLengthStiffness = 0.24f;
    public float tentacleStretchLimit = 1.12f;
    public bool tentacleShaderEnabled = true;
    public Color tentacleShaderTipColor = new Color32(88, 170, 255, 255);
    public float tentacleShaderAlphaStart = 1f;
    public float tentacleShaderAlphaEnd = 0.18f;
    public float tentacleShaderBias = 1.15f;
    public bool tentacleCoreOn = true;
    public Color tentacleCoreColor = new Color32(225, 255, 245, 255);
    public int tentacleCoreAlpha = 180;
    public int tentacleCoreThick = 2;
    public int tentacleCorePoints = 6;
    public float tentacleCoreOuterRadius = 26f;
    public float tentacleCoreInnerRatio = 0.42f;
    public float tentacleCoreBaseSpeed = 0.75f;
    public float tentacleCoreKSpeed = 1.2f;
    public float tentacleCorePSpeed = 1.35f;

    [Header("M3 Tentacle Bindings")]
    public bool kpBindTentacleTurbulenceK = true;
    public float kpTentacleTurbulenceKWmin = 0.22f;
    public float kpTentacleTurbulenceKWmax = 0.683f;
    public bool kpBindTentacleCoreBaseSpeedK = true;
    public float kpTentacleCoreBaseSpeedKWmin = 0f;
    public float kpTentacleCoreBaseSpeedKWmax = 1.2f;
    public bool kpBindTentacleCoreBaseSpeedP = true;
    public float kpTentacleCoreBaseSpeedPWmin = 0f;
    public float kpTentacleCoreBaseSpeedPWmax = 1.35f;
    public bool kpBindTentacleTipThicknessP = false;
    public float kpTentacleTipThicknessPWmin = 0f;
    public float kpTentacleTipThicknessPWmax = 1f;
    public bool kpBindTentacleThickP = false;
    public float kpTentacleThickPWmin = 150f;
    public float kpTentacleThickPWmax = 0f;
    public bool kpBindTentacleThickK = true;
    public float kpTentacleThickKWmin = 0f;
    public float kpTentacleThickKWmax = 200f;
    public bool kpBindTentacleLengthK = true;
    public float kpTentacleLengthKWmin = 0f;
    public float kpTentacleLengthKWmax = 300f;
    public bool kpBindTentacleLengthJitterSpeedP = false;
    public float kpTentacleLengthJitterSpeedPWmin = 0f;
    public float kpTentacleLengthJitterSpeedPWmax = 1f;
    public bool kpBindTentacleShaderAlphaStartP = false;
    public float kpTentacleShaderAlphaStartPWmin = 0f;
    public float kpTentacleShaderAlphaStartPWmax = 1f;
    public bool kpBindTentacleShaderAlphaStartK = false;
    public float kpTentacleShaderAlphaStartKWmin = 0f;
    public float kpTentacleShaderAlphaStartKWmax = 1f;
    public bool kpBindTentacleLengthJitterK = true;
    public float kpTentacleLengthJitterKWmin = 0f;
    public float kpTentacleLengthJitterKWmax = 4000f;

    public float CurrentA1 => a1Value;
    public float CurrentK2 => k2Value;
    public float CurrentP => k2Value;
    public float EffectiveA1 => k2Enabled ? k2Value : a1Value;
    public IReadOnlyList<float> PreviewBarHeights => barHeights ?? Array.Empty<float>();
    public IReadOnlyList<float> PreviewBarLengths => cachedLengthPixels ?? Array.Empty<float>();
    public IReadOnlyList<Color> PreviewBarColors => barColors ?? Array.Empty<Color>();
    public int PreviewBarCount => Mathf.Max(1, runtimeNumBars > 0 ? runtimeNumBars : numBars);
    public float PreviewColorCycleHue => colorCycleHue;
    public float PreviewColorCycleRate => GetColorCycleRate();
    public Color PreviewCurrentColor => GetPreviewColor();

    private const int SpectrumSize = 2048;

    private float[] spectrumData;
    private float[] barHeights;
    private float[] barVelocities;
    private float[] smoothedBarValues;
    private float[] peakOuterHeights;
    private float[] peakInnerHeights;
    private float[] cachedLengthPixels;
    private float[] layerRotations;
    private Color[] barColors;

    private float currentRadius;
    private float radiusVelocity;
    private float a1Value;
    private float k2Value;
    private float previousEffectiveA1Value;
    private float colorCycleHue;
    private float externalDataTimeout;
    private float externalLoudnessTimeout;
    private float lastExternalLoudness;
    private bool useExternalData;

    private int runtimeNumBars = -1;
    private int runtimeSegments = -1;
    private int runtimeTentacleCount = -1;
    private int runtimeTentacleControlPointsMin = -1;
    private int runtimeTentacleControlPointsMax = -1;

    private Material lineMaterial;
    private readonly List<LineRenderer> layerRenderers = new List<LineRenderer>();
    private readonly List<MeshRenderer> fillRenderers = new List<MeshRenderer>();
    private readonly List<Mesh> fillMeshes = new List<Mesh>();
    private readonly List<Material> fillMaterials = new List<Material>();
    private readonly List<LineRenderer> barRenderers = new List<LineRenderer>();
    private readonly List<LineRenderer> tentacleRenderers = new List<LineRenderer>();
    private readonly Queue<LoudnessFrame> loudnessHistory = new Queue<LoudnessFrame>();
    private readonly Queue<SpectrumFrame> spectrumHistory = new Queue<SpectrumFrame>();
    private readonly Dictionary<string, float[]> objectLengthStates = new Dictionary<string, float[]>();
    private LineRenderer tentacleCoreRenderer;
    private float[] tentaclePhaseOffsets;
    private Vector2[][] tentacleOffsets;
    private Vector2[][] tentacleVelocities;
    private bool[] tentacleInitialized;
    private int[] tentacleControlPointCounts;
    private int tentaclePhysicsSegments;
    private float tentacleCoreCurrentRotation;
    private float tentacleCoreAngularVelocity;
    private float tentacleCoreAccelDirection = 1f;
    private float tentaclePrevAbsP;
    private bool tentaclePrevPRising;
    private float tentaclePPeakReference;
    private int tentaclePPeakCooldown;

    private readonly float pixelScale = 0.01f;
    private static readonly string[] DampedObjectKeys = { "bar", "c1", "c2", "c4", "c5", "b12", "b23", "b34", "b45" };

    private float[] spectrumHistorySum;

    private struct LoudnessFrame
    {
        public float time;
        public float value;

        public LoudnessFrame(float time, float value)
        {
            this.time = time;
            this.value = value;
        }
    }

    private struct SpectrumFrame
    {
        public float time;
        public float[] values;

        public SpectrumFrame(float time, float[] values)
        {
            this.time = time;
            this.values = values;
        }
    }

    private struct BarSegmentData
    {
        public Vector3 start;
        public Vector3 end;
        public Color color;

        public BarSegmentData(Vector3 start, Vector3 end, Color color)
        {
            this.start = start;
            this.end = end;
            this.color = color;
        }
    }

    private void Start()
    {
        EnsureGradientPoints();
        RebuildRuntimeState(true);
        if (autoFrameMainCamera)
        {
            SetupCamera();
        }
    }

    private void Update()
    {
        EnsureGradientPoints();
        EnsureRuntimeState();
        ProcessAudio();
        UpdateVisualState();
        Render();
        if (autoFrameMainCamera)
        {
            UpdateCameraFrame();
        }
    }

    public void EnsureGradientPoints()
    {
        if (gradientPoints == null)
        {
            gradientPoints = new List<PyStyleGradientPoint>();
        }

        if (gradientPoints.Count == 0)
        {
            gradientPoints.Add(new PyStyleGradientPoint(0f, new Color32(255, 0, 128, 255)));
            gradientPoints.Add(new PyStyleGradientPoint(0.5f, new Color32(255, 240, 96, 255)));
            gradientPoints.Add(new PyStyleGradientPoint(1f, new Color32(0, 255, 255, 255)));
        }

        for (int i = 0; i < gradientPoints.Count; i++)
        {
            if (gradientPoints[i] == null)
            {
                gradientPoints[i] = new PyStyleGradientPoint(i / Mathf.Max(1f, gradientPoints.Count - 1f), Color.white);
            }

            gradientPoints[i].position = Mathf.Clamp01(gradientPoints[i].position);
        }

        SortGradientPoints();
    }

    public void SortGradientPoints()
    {
        if (gradientPoints == null)
        {
            return;
        }

        gradientPoints.Sort((a, b) => a.position.CompareTo(b.position));
    }

    public void SetExternalSpectrum(float[] data)
    {
        SetExternalSpectrum(data, -1f);
    }

    public void SetExternalSpectrum(float[] data, float loudness)
    {
        SetExternalSpectrum(data, loudness, spectrumSampleRate);
    }

    public void SetExternalSpectrum(float[] data, float loudness, float sampleRate)
    {
        if (data == null || data.Length == 0)
        {
            return;
        }

        if (spectrumData == null || spectrumData.Length != SpectrumSize)
        {
            spectrumData = new float[SpectrumSize];
        }

        Array.Clear(spectrumData, 0, spectrumData.Length);
        int length = Mathf.Min(data.Length, spectrumData.Length);
        Array.Copy(data, spectrumData, length);

        if (sampleRate > 1f)
        {
            spectrumSampleRate = sampleRate;
        }

        useExternalData = true;
        externalDataTimeout = 0.15f;

        if (loudness >= 0f)
        {
            lastExternalLoudness = NormalizeExternalLoudness(loudness);
            externalLoudnessTimeout = 0.15f;
        }
    }

    private void SetupCamera()
    {
        Camera cam = Camera.main;
        if (cam == null)
        {
            return;
        }

        cam.orthographic = true;
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.backgroundColor = new Color(0f, 0f, 0f, 0f);
        cam.transform.position = new Vector3(0f, 0f, -10f);
        UpdateCameraFrame();
    }

    public float EstimateSuggestedCameraSize()
    {
        float maxFixedBarLength = Mathf.Max(Mathf.Max(b12FixedLen, b23FixedLen), Mathf.Max(b34FixedLen, b45FixedLen));
        float maxBarReach = Mathf.Max(barLengthMax, maxFixedBarLength);
        float radiusPixels = Mathf.Max(currentRadius, circleRadius * globalScale * mainRadiusScale);
        float circleAndBars = (radiusPixels + maxBarReach + 180f) * pixelScale;

        float tentacleReach = 0f;
        if (tentacleOn && tentaclesEnabled)
        {
            float jitterPixels = tentacleLengthJitter * globalScale;
            float barDrivenPixels = Mathf.Max(barLengthMax, barInternalMax) * 0.38f * globalScale;
            float corePixels = tentacleCoreOuterRadius * globalScale;
            tentacleReach = (radiusPixels + (tentacleLength * globalScale) + jitterPixels + barDrivenPixels + corePixels + 180f) * pixelScale;
        }

        return Mathf.Max(6f, Mathf.Max(circleAndBars, tentacleReach));
    }

    private void UpdateCameraFrame()
    {
        Camera cam = Camera.main;
        if (cam == null)
        {
            return;
        }

        float desired = EstimateSuggestedCameraSize();
        cam.orthographicSize = Mathf.Lerp(cam.orthographicSize <= 0f ? desired : cam.orthographicSize, desired, 0.1f);
    }

    private void EnsureRuntimeState()
    {
        numBars = Mathf.Max(1, numBars);
        circleSegments = Mathf.Max(1, circleSegments);
        tentacleCount = Mathf.Max(3, tentacleCount);
        barHeightMax = Mathf.Max(barHeightMin + 1, barHeightMax);
        freqMin = Mathf.Max(1, freqMin);
        freqMax = Mathf.Max(freqMin + 1, freqMax);

        if (runtimeNumBars != numBars ||
            runtimeSegments != circleSegments ||
            runtimeTentacleCount != tentacleCount ||
            runtimeTentacleControlPointsMin != tentacleControlPointsMin ||
            runtimeTentacleControlPointsMax != tentacleControlPointsMax ||
            tentaclePhysicsSegments != Mathf.Max(2, Mathf.Max(tentacleControlPointsMin, tentacleControlPointsMax) - 1) ||
            spectrumData == null)
        {
            RebuildRuntimeState(false);
        }
    }

    private void RebuildRuntimeState(bool firstInit)
    {
        float[] oldBarHeights = barHeights;
        float[] oldBarVelocities = barVelocities;
        float[] oldSmoothed = smoothedBarValues;
        float[] oldPeakOuter = peakOuterHeights;
        float[] oldPeakInner = peakInnerHeights;

        runtimeNumBars = Mathf.Max(1, numBars);
        runtimeSegments = Mathf.Max(1, circleSegments);
        runtimeTentacleCount = Mathf.Max(3, tentacleCount);
        runtimeTentacleControlPointsMin = tentacleControlPointsMin;
        runtimeTentacleControlPointsMax = tentacleControlPointsMax;

        spectrumData = new float[SpectrumSize];
        barHeights = new float[runtimeNumBars];
        barVelocities = new float[runtimeNumBars];
        smoothedBarValues = new float[runtimeNumBars];
        peakOuterHeights = new float[runtimeNumBars];
        peakInnerHeights = new float[runtimeNumBars];
        cachedLengthPixels = new float[runtimeNumBars];
        barColors = new Color[runtimeNumBars];
        spectrumHistorySum = new float[runtimeNumBars];

        CopyState(oldBarHeights, barHeights);
        CopyState(oldBarVelocities, barVelocities);
        CopyState(oldSmoothed, smoothedBarValues);
        CopyState(oldPeakOuter, peakOuterHeights);
        CopyState(oldPeakInner, peakInnerHeights);

        if (layerRotations == null || layerRotations.Length != 6)
        {
            layerRotations = new float[6];
        }

        tentaclePhaseOffsets = new float[runtimeTentacleCount];
        for (int index = 0; index < runtimeTentacleCount; index++)
        {
            tentaclePhaseOffsets[index] = (index * 1.6180339f) % (Mathf.PI * 2f);
        }

        // Reset soft-body physics state when topology changes
        int cpMin = Mathf.Max(3, tentacleControlPointsMin);
        int cpMax = Mathf.Max(cpMin, tentacleControlPointsMax);
        int physSegsNeeded = Mathf.Max(2, cpMax - 1);
        tentaclePhysicsSegments = physSegsNeeded;
        tentacleControlPointCounts = new int[runtimeTentacleCount];
        tentacleOffsets = new Vector2[runtimeTentacleCount][];
        tentacleVelocities = new Vector2[runtimeTentacleCount][];
        tentacleInitialized = new bool[runtimeTentacleCount];
        int cpRange = Mathf.Max(1, cpMax - cpMin + 1);
        for (int i = 0; i < runtimeTentacleCount; i++)
        {
            int cpCount = cpMin + (i % cpRange);
            int outerPoints = Mathf.Max(2, cpCount - 1);
            tentacleControlPointCounts[i] = cpCount;
            tentacleOffsets[i] = new Vector2[outerPoints];
            tentacleVelocities[i] = new Vector2[outerPoints];
        }

        tentacleCoreCurrentRotation = 0f;
        tentacleCoreAngularVelocity = 0f;
        tentacleCoreAccelDirection = 1f;
        tentaclePrevAbsP = 0f;
        tentaclePrevPRising = false;
        tentaclePPeakReference = 0f;
        tentaclePPeakCooldown = 0;

        if (firstInit || currentRadius <= 0f)
        {
            currentRadius = circleRadius * globalScale * mainRadiusScale;
        }

        ResetSpectrumHistory();
        InitializeObjectLengthStates();

        InitRenderers();
    }

    private void CopyState(float[] source, float[] destination)
    {
        if (source == null || destination == null)
        {
            return;
        }

        Array.Copy(source, destination, Mathf.Min(source.Length, destination.Length));
    }

    private void ResetSpectrumHistory()
    {
        spectrumHistory.Clear();
        if (spectrumHistorySum == null || spectrumHistorySum.Length != runtimeNumBars)
        {
            spectrumHistorySum = new float[runtimeNumBars];
            return;
        }

        Array.Clear(spectrumHistorySum, 0, spectrumHistorySum.Length);
    }

    private void InitializeObjectLengthStates()
    {
        objectLengthStates.Clear();
        float initialLength = Mathf.Clamp(GetDefaultBarHeight(), Mathf.Min(barLengthMin, barLengthMax), Mathf.Max(barLengthMin, barLengthMax)) * globalScale;
        foreach (string key in DampedObjectKeys)
        {
            float[] state = new float[runtimeNumBars];
            for (int index = 0; index < state.Length; index++)
            {
                state[index] = initialLength;
            }

            objectLengthStates[key] = state;
        }
    }

    private float GetDefaultBarHeight()
    {
        float minValue = Mathf.Min(barInternalMin, barInternalMax);
        float maxValue = Mathf.Max(barInternalMin, barInternalMax);
        return Mathf.Clamp(barDefaultHeight, minValue, maxValue);
    }

    private float GetSpectrumWindowSeconds()
    {
        float value = barUseIndependentTimeWindow ? barTimeWindow : a1TimeWindow;
        return Mathf.Max(0.01f, value);
    }

    private static float ClampDamping(float value)
    {
        return Mathf.Clamp(value, 0f, 0.999f);
    }

    private static float ApplyDampingStep(float current, float target, float riseDamping, float fallDamping)
    {
        float blend = target >= current ? 1f - ClampDamping(riseDamping) : 1f - ClampDamping(fallDamping);
        return Mathf.Lerp(current, target, Mathf.Max(0.001f, blend));
    }

    private void ApplyDampingStep(float[] state, float[] targets, float riseDamping, float fallDamping, float minValue, float maxValue)
    {
        if (state == null || targets == null)
        {
            return;
        }

        int count = Mathf.Min(state.Length, targets.Length);
        for (int index = 0; index < count; index++)
        {
            state[index] = Mathf.Clamp(ApplyDampingStep(state[index], targets[index], riseDamping, fallDamping), minValue, maxValue);
        }
    }

    private Vector2 GetDampingPair(string key = null)
    {
        if (string.IsNullOrEmpty(key))
        {
            return new Vector2(ClampDamping(kRiseDamping), ClampDamping(kFallDamping));
        }

        bool useIndependent;
        float rise;
        float fall;

        switch (key)
        {
            case "bar":
                useIndependent = barUseIndependentDamping;
                rise = barIndependentRiseDamping;
                fall = barIndependentFallDamping;
                break;
            case "c1":
                useIndependent = c1UseIndependentDamping;
                rise = c1IndependentRiseDamping;
                fall = c1IndependentFallDamping;
                break;
            case "c2":
                useIndependent = c2UseIndependentDamping;
                rise = c2IndependentRiseDamping;
                fall = c2IndependentFallDamping;
                break;
            case "c4":
                useIndependent = c4UseIndependentDamping;
                rise = c4IndependentRiseDamping;
                fall = c4IndependentFallDamping;
                break;
            case "c5":
                useIndependent = c5UseIndependentDamping;
                rise = c5IndependentRiseDamping;
                fall = c5IndependentFallDamping;
                break;
            case "b12":
                useIndependent = b12UseIndependentDamping;
                rise = b12IndependentRiseDamping;
                fall = b12IndependentFallDamping;
                break;
            case "b23":
                useIndependent = b23UseIndependentDamping;
                rise = b23IndependentRiseDamping;
                fall = b23IndependentFallDamping;
                break;
            case "b34":
                useIndependent = b34UseIndependentDamping;
                rise = b34IndependentRiseDamping;
                fall = b34IndependentFallDamping;
                break;
            case "b45":
                useIndependent = b45UseIndependentDamping;
                rise = b45IndependentRiseDamping;
                fall = b45IndependentFallDamping;
                break;
            default:
                useIndependent = false;
                rise = kRiseDamping;
                fall = kFallDamping;
                break;
        }

        if (!useIndependent)
        {
            return new Vector2(ClampDamping(kRiseDamping), ClampDamping(kFallDamping));
        }

        return new Vector2(ClampDamping(rise), ClampDamping(fall));
    }

    private float[] PushSpectrumHistory(float[] values)
    {
        if (values == null)
        {
            return Array.Empty<float>();
        }

        if (spectrumHistorySum == null || spectrumHistorySum.Length != values.Length)
        {
            spectrumHistorySum = new float[values.Length];
            spectrumHistory.Clear();
        }

        float now = Time.unscaledTime;
        float[] snapshot = new float[values.Length];
        Array.Copy(values, snapshot, values.Length);
        spectrumHistory.Enqueue(new SpectrumFrame(now, snapshot));
        for (int index = 0; index < snapshot.Length; index++)
        {
            spectrumHistorySum[index] += snapshot[index];
        }

        float cutoff = now - GetSpectrumWindowSeconds();
        while (spectrumHistory.Count > 0 && spectrumHistory.Peek().time < cutoff)
        {
            SpectrumFrame old = spectrumHistory.Dequeue();
            for (int index = 0; index < old.values.Length; index++)
            {
                spectrumHistorySum[index] -= old.values[index];
            }
        }

        float[] averaged = new float[values.Length];
        if (spectrumHistory.Count == 0)
        {
            return averaged;
        }

        float invCount = 1f / spectrumHistory.Count;
        for (int index = 0; index < averaged.Length; index++)
        {
            averaged[index] = spectrumHistorySum[index] * invCount;
        }

        return averaged;
    }

    private float[] GetLengthState(string key)
    {
        if (!objectLengthStates.TryGetValue(key, out float[] state) || state == null || state.Length != runtimeNumBars)
        {
            state = new float[runtimeNumBars];
            objectLengthStates[key] = state;
        }

        return state;
    }

    private float[] UpdateLengthState(string key, float[] targetLengths)
    {
        float[] state = GetLengthState(key);
        if (targetLengths == null)
        {
            return state;
        }

        if (key == "bar" && !barUseIndependentDamping)
        {
            Array.Copy(targetLengths, state, Mathf.Min(targetLengths.Length, state.Length));
            return state;
        }

        Vector2 dampingPair = GetDampingPair(key);
        if ((key != "bar" && Mathf.Approximately(dampingPair.x, kRiseDamping) && Mathf.Approximately(dampingPair.y, kFallDamping) && !IsIndependentKey(key)) ||
            (key == "bar" && !barUseIndependentDamping))
        {
            Array.Copy(targetLengths, state, Mathf.Min(targetLengths.Length, state.Length));
            return state;
        }

        float minLength = Mathf.Min(barLengthMin, barLengthMax) * globalScale;
        float maxLength = Mathf.Max(barLengthMin, barLengthMax) * globalScale;
        ApplyDampingStep(state, targetLengths, dampingPair.x, dampingPair.y, minLength, maxLength);
        return state;
    }

    private bool IsIndependentKey(string key)
    {
        switch (key)
        {
            case "c1": return c1UseIndependentDamping;
            case "c2": return c2UseIndependentDamping;
            case "c4": return c4UseIndependentDamping;
            case "c5": return c5UseIndependentDamping;
            case "b12": return b12UseIndependentDamping;
            case "b23": return b23UseIndependentDamping;
            case "b34": return b34UseIndependentDamping;
            case "b45": return b45UseIndependentDamping;
            default: return false;
        }
    }

    private void InitRenderers()
    {
        ClearRendererObjects();

        Shader lineShader = Shader.Find("Sprites/Default");
        if (lineShader == null)
        {
            lineShader = Shader.Find("Unlit/Color");
        }
        if (lineShader == null)
        {
            lineShader = Shader.Find("HDRP/Unlit");
        }
        Shader fillShader = Shader.Find("Sprites/Default");
        if (fillShader == null)
        {
            fillShader = Shader.Find("Unlit/Transparent");
        }
        if (fillShader == null)
        {
            fillShader = Shader.Find("Unlit/Color");
        }
        if (fillShader == null)
        {
            fillShader = lineShader;
        }

        if (lineShader == null)
        {
            Debug.LogError("[PyStyleVisualizer] 未找到可用的线条着色器。");
            return;
        }

        lineMaterial = new Material(lineShader);

        bool[] layerEnabledStates =
        {
            contoursEnabled && c1On,
            contoursEnabled && c2On,
            contoursEnabled && c3On,
            contoursEnabled && c4On,
            contoursEnabled && c5On,
        };
        bool[] layerFillStates =
        {
            contoursEnabled && c1Fill,
            contoursEnabled && c2Fill,
            contoursEnabled && c3Fill,
            contoursEnabled && c4Fill,
            contoursEnabled && c5Fill,
        };

        for (int i = 1; i <= 5; i++)
        {
            if (layerEnabledStates[i - 1])
            {
                GameObject lineObject = new GameObject($"Layer_{i}");
                lineObject.transform.SetParent(transform, false);

                LineRenderer line = lineObject.AddComponent<LineRenderer>();
                line.material = lineMaterial;
                line.loop = true;
                line.useWorldSpace = false;
                line.textureMode = LineTextureMode.Stretch;
                line.alignment = LineAlignment.TransformZ;
                line.numCapVertices = 8;
                line.numCornerVertices = 8;
                line.sortingOrder = i * 2;
                line.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                line.receiveShadows = false;
                layerRenderers.Add(line);
            }
            else
            {
                layerRenderers.Add(null);
            }

            if (layerFillStates[i - 1])
            {
                GameObject fillObject = new GameObject($"Layer_{i}_Fill");
                fillObject.transform.SetParent(transform, false);

                MeshRenderer renderer = fillObject.AddComponent<MeshRenderer>();
                Material material = new Material(fillShader);
                MeshFilter filter = fillObject.AddComponent<MeshFilter>();
                Mesh mesh = new Mesh { name = $"Layer_{i}_FillMesh" };

                material.renderQueue = (int)UnityEngine.Rendering.RenderQueue.Transparent;

                filter.sharedMesh = mesh;
                renderer.material = material;
                renderer.sortingOrder = i * 2 - 1;
                renderer.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                renderer.receiveShadows = false;

                fillRenderers.Add(renderer);
                fillMeshes.Add(mesh);
                fillMaterials.Add(material);
            }
            else
            {
                fillRenderers.Add(null);
                fillMeshes.Add(null);
                fillMaterials.Add(null);
            }
        }

        int barCapacity = 0;
        if (barsEnabled && b45On)
        {
            barCapacity += runtimeNumBars * runtimeSegments * ((b45FromStart ? 1 : 0) + (b45FromEnd ? 1 : 0) + (b45FromCenter ? 1 : 0));
        }
        if (barsEnabled && b34On)
        {
            barCapacity += runtimeNumBars * runtimeSegments * ((b34FromStart ? 1 : 0) + (b34FromEnd ? 1 : 0) + (b34FromCenter ? 1 : 0));
        }
        if (barsEnabled && b23On)
        {
            barCapacity += runtimeNumBars * runtimeSegments * ((b23FromStart ? 1 : 0) + (b23FromEnd ? 1 : 0) + (b23FromCenter ? 1 : 0));
        }
        if (barsEnabled && b12On)
        {
            barCapacity += runtimeNumBars * runtimeSegments * ((b12FromStart ? 1 : 0) + (b12FromEnd ? 1 : 0) + (b12FromCenter ? 1 : 0));
        }
        for (int i = 0; i < barCapacity; i++)
        {
            GameObject barObject = new GameObject($"Bar_{i}");
            barObject.transform.SetParent(transform, false);

            LineRenderer line = barObject.AddComponent<LineRenderer>();
            line.material = lineMaterial;
            line.loop = false;
            line.positionCount = 2;
            line.useWorldSpace = false;
            line.textureMode = LineTextureMode.Stretch;
            line.alignment = LineAlignment.TransformZ;
            line.numCapVertices = 4;
            line.numCornerVertices = 2;
            line.sortingOrder = 20;
            line.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            line.receiveShadows = false;
            barRenderers.Add(line);
        }

        int tentacleCapacity = tentaclesEnabled && tentacleOn ? runtimeTentacleCount : 0;
        for (int i = 0; i < tentacleCapacity; i++)
        {
            GameObject tentacleObject = new GameObject($"Tentacle_{i}");
            tentacleObject.transform.SetParent(transform, false);

            LineRenderer line = tentacleObject.AddComponent<LineRenderer>();
            line.material = lineMaterial;
            line.loop = false;
            line.useWorldSpace = false;
            line.textureMode = LineTextureMode.Stretch;
            line.alignment = LineAlignment.TransformZ;
            line.numCapVertices = 8;
            line.numCornerVertices = 8;
            line.sortingOrder = 24;
            line.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            line.receiveShadows = false;
            tentacleRenderers.Add(line);
        }
    }

    private void ClearRendererObjects()
    {
        foreach (LineRenderer line in layerRenderers)
        {
            if (line != null)
            {
                Destroy(line.gameObject);
            }
        }
        layerRenderers.Clear();

        foreach (MeshRenderer renderer in fillRenderers)
        {
            if (renderer != null)
            {
                Destroy(renderer.gameObject);
            }
        }
        fillRenderers.Clear();

        foreach (Mesh mesh in fillMeshes)
        {
            if (mesh != null)
            {
                Destroy(mesh);
            }
        }
        fillMeshes.Clear();

        foreach (Material material in fillMaterials)
        {
            if (material != null)
            {
                Destroy(material);
            }
        }
        fillMaterials.Clear();

        foreach (LineRenderer line in barRenderers)
        {
            if (line != null)
            {
                Destroy(line.gameObject);
            }
        }
        barRenderers.Clear();

        foreach (LineRenderer line in tentacleRenderers)
        {
            if (line != null)
            {
                Destroy(line.gameObject);
            }
        }
        tentacleRenderers.Clear();

        if (lineMaterial != null)
        {
            Destroy(lineMaterial);
            lineMaterial = null;
        }
    }

    private void ProcessAudio()
    {
        if (useExternalData)
        {
            externalDataTimeout -= Time.deltaTime;
            if (externalDataTimeout <= 0f)
            {
                useExternalData = false;
                Array.Clear(spectrumData, 0, spectrumData.Length);
            }
        }
        else if (spectrumData != null)
        {
            Array.Clear(spectrumData, 0, spectrumData.Length);
        }

        externalLoudnessTimeout -= Time.deltaTime;
        float loudness = externalLoudnessTimeout > 0f ? lastExternalLoudness : EstimateSpectrumLoudness();
        UpdateA1(loudness);
    }

    private float EstimateSpectrumLoudness()
    {
        if (spectrumData == null || spectrumData.Length == 0)
        {
            return 0f;
        }

        int usable = GetUsableSpectrumLength();
        float sum = 0f;
        for (int i = 0; i < usable; i++)
        {
            sum += spectrumData[i] * spectrumData[i];
        }

        return Mathf.Sqrt(sum / Mathf.Max(1, usable)) * 4000f;
    }

    private float NormalizeExternalLoudness(float loudness)
    {
        if (loudness <= 0f)
        {
            return 0f;
        }

        if (loudness < 1f)
        {
            return Mathf.Pow(loudness * 2000f, 0.75f) * 35f;
        }

        if (loudness < 20f)
        {
            return Mathf.Pow(loudness * 120f, 0.78f) * 12f;
        }

        return Mathf.Pow(loudness, 0.85f) * 25f;
    }

    private void UpdateA1(float loudness)
    {
        float now = Time.unscaledTime;
        loudnessHistory.Enqueue(new LoudnessFrame(now, loudness));

        float cutoff = now - Mathf.Max(0.01f, a1TimeWindow);
        while (loudnessHistory.Count > 0 && loudnessHistory.Peek().time < cutoff)
        {
            loudnessHistory.Dequeue();
        }

        float previous = a1Value;
        float sum = 0f;
        foreach (LoudnessFrame frame in loudnessHistory)
        {
            sum += frame.value;
        }

        float target = loudnessHistory.Count > 0 ? sum / loudnessHistory.Count : 0f;
        Vector2 dampingPair = GetDampingPair();
        a1Value = ApplyDampingStep(a1Value, target, dampingPair.x, dampingPair.y);
        float delta = a1Value - previous;
        float power = Mathf.Max(0.01f, k2Pow);
        k2Value = Mathf.Sign(delta) * Mathf.Pow(Mathf.Abs(delta), power);
    }

    private int GetUsableSpectrumLength()
    {
        if (spectrumData == null)
        {
            return 0;
        }

        return spectrumData.Length < 8 ? spectrumData.Length : Mathf.Max(8, spectrumData.Length / 2);
    }

    private float[] GetBarValues()
    {
        float[] values = new float[runtimeNumBars];
        int usableLength = GetUsableSpectrumLength();
        if (usableLength <= 1)
        {
            return values;
        }

        float sampleRate = Mathf.Max(1f, spectrumSampleRate);
        float frequencyResolution = sampleRate / (usableLength * 2f);
        int low = Mathf.Clamp(Mathf.RoundToInt(freqMin / Mathf.Max(1f, frequencyResolution)), 1, usableLength - 1);
        int high = Mathf.Clamp(Mathf.RoundToInt(freqMax / Mathf.Max(1f, frequencyResolution)), low + 1, usableLength);
        int subLength = Mathf.Max(2, high - low);

        int[] bins = BuildLogBins(subLength, runtimeNumBars);
        for (int barIndex = 0; barIndex < runtimeNumBars; barIndex++)
        {
            int start = low + bins[barIndex];
            int end = low + bins[barIndex + 1];
            if (end <= start)
            {
                end = start + 1;
            }

            float sum = 0f;
            int count = 0;
            for (int spectrumIndex = start; spectrumIndex < end && spectrumIndex < usableLength; spectrumIndex++)
            {
                sum += spectrumData[spectrumIndex];
                count++;
            }

            float average = count > 0 ? sum / count : 0f;
            average = Mathf.Max(0f, average - 0.0002f);
            float scaled = Mathf.Pow(Mathf.Max(0f, average), 0.35f) * 1250f;
            float mappedHeight = MapSpectrumToHeight(scaled);
            float previous = smoothedBarValues[barIndex];
            float hold = Mathf.Clamp01(smoothing);
            float riseResponse = Mathf.Lerp(18f, 48f, 1f - hold);
            float fallResponse = Mathf.Lerp(2.5f, 16f, 1f - hold);
            float response = mappedHeight >= previous
                ? 1f - Mathf.Exp(-riseResponse * Time.unscaledDeltaTime)
                : 1f - Mathf.Exp(-fallResponse * Time.unscaledDeltaTime);

            // Fast attack for sharp gear-like bursts, slower release for a calmer return to circle.
            smoothedBarValues[barIndex] = Mathf.Lerp(previous, mappedHeight, response);
            values[barIndex] = smoothedBarValues[barIndex];
        }

        return PushSpectrumHistory(values);
    }

    private int[] BuildLogBins(int length, int count)
    {
        int[] bins = new int[count + 1];
        double logMin = Math.Log10(1d);
        double logMax = Math.Log10(Math.Max(2, length));

        for (int index = 0; index <= count; index++)
        {
            double t = index / (double)count;
            double value = Math.Pow(10d, logMin + (logMax - logMin) * t);
            bins[index] = Mathf.Clamp((int)Math.Round(value), 0, length);
        }

        bins[0] = 0;
        bins[count] = length;
        for (int index = 1; index < bins.Length; index++)
        {
            if (bins[index] < bins[index - 1])
            {
                bins[index] = bins[index - 1];
            }
        }

        return bins;
    }

    private float MapSpectrumToHeight(float scaledValue)
    {
        float minHeight = Mathf.Max(0f, barHeightMin);
        float maxHeight = Mathf.Max(minHeight + 1f, barHeightMax);
        float normalized = 1f - Mathf.Exp(-Mathf.Max(0f, scaledValue) / Mathf.Max(1f, maxHeight * 0.55f));
        return Mathf.Lerp(minHeight, maxHeight, Mathf.Clamp01(normalized));
    }

    private void UpdateVisualState()
    {
        if (!masterVisible)
        {
            return;
        }

        float scale = globalScale;
        float baseRadius = circleRadius * scale * mainRadiusScale;
        float targetRadius = baseRadius;
        float effectiveA1 = EffectiveA1;

        if (radiusFollowsAudio && effectiveA1 > 0f)
        {
            float audioRadiusLift = Mathf.Clamp((effectiveA1 / 320f) * 85f * scale, 0f, baseRadius * 0.75f);
            targetRadius = baseRadius + audioRadiusLift;
        }

        float springForce = (targetRadius - currentRadius) * radiusSpring;
        float gravityForce = -(currentRadius - baseRadius) * radiusGravity * 0.01f;
        radiusVelocity *= radiusDamping;
        radiusVelocity += springForce + gravityForce;
        currentRadius = Mathf.Max(10f, currentRadius + radiusVelocity);

        float[] barValues = GetBarValues();
        float frameScale = Mathf.Clamp(Time.deltaTime * 60f, 0.25f, 3f);
        float minInternal = Mathf.Min(barInternalMin, barInternalMax);
        float maxInternal = Mathf.Max(barInternalMin, barInternalMax);
        float defaultHeight = GetDefaultBarHeight();
        float maxDynamicHeight = Mathf.Max(maxInternal, Mathf.Max(barHeightMax, Mathf.CeilToInt(barLengthMax)));
        for (int index = 0; index < runtimeNumBars; index++)
        {
            float target = Mathf.Max(defaultHeight, barValues[index]);
            float spring = (target - barHeights[index]) * springStrength * 0.12f;
            float dampingFactor = Mathf.Pow(Mathf.Max(0f, damping), frameScale);
            barVelocities[index] *= dampingFactor;
            barVelocities[index] += spring * frameScale;
            if (barHeights[index] > target)
            {
                barVelocities[index] -= gravity * 0.04f * frameScale;
            }

            barHeights[index] = Mathf.Clamp(barHeights[index] + barVelocities[index] * frameScale, minInternal, maxDynamicHeight);
        }

        float[] sharedLengths = new float[runtimeNumBars];
        float minLength = Mathf.Min(barLengthMin, barLengthMax) * scale;
        float maxLength = Mathf.Max(barLengthMin, barLengthMax) * scale;
        for (int index = 0; index < runtimeNumBars; index++)
        {
            sharedLengths[index] = Mathf.Clamp(barHeights[index], Mathf.Min(barLengthMin, barLengthMax), Mathf.Max(barLengthMin, barLengthMax)) * scale;
        }

        float[] barLengths = UpdateLengthState("bar", sharedLengths);
        float[] c1Lengths = UpdateLengthState("c1", sharedLengths);
        float[] c2Lengths = UpdateLengthState("c2", sharedLengths);
        float[] c4Lengths = UpdateLengthState("c4", sharedLengths);
        float[] c5Lengths = UpdateLengthState("c5", sharedLengths);
        float[] b12Lengths = UpdateLengthState("b12", sharedLengths);
        float[] b23Lengths = UpdateLengthState("b23", sharedLengths);
        float[] b34Lengths = UpdateLengthState("b34", sharedLengths);
        float[] b45Lengths = UpdateLengthState("b45", sharedLengths);

        for (int index = 0; index < runtimeNumBars; index++)
        {
            cachedLengthPixels[index] = Mathf.Clamp(barLengths[index], minLength, maxLength);
        }

        for (int index = 0; index < runtimeNumBars; index++)
        {
            peakInnerHeights[index] = Mathf.Max(c1Lengths[index], peakInnerHeights[index] * c1Decay);
            peakOuterHeights[index] = Mathf.Max(c5Lengths[index], peakOuterHeights[index] * c5Decay);
        }

        float a1Delta = Mathf.Abs(effectiveA1 - previousEffectiveA1Value);
        previousEffectiveA1Value = effectiveA1;
        float normalizedDelta = Mathf.Min(a1Delta / 120f, 1f);

        for (int layerIndex = 1; layerIndex <= 5; layerIndex++)
        {
            float speed = GetLayerRotationSpeed(layerIndex);
            float power = GetLayerRotationPower(layerIndex);

            if (rotationFollowsAudio && normalizedDelta > 0.0001f)
            {
                float factor = power >= 0f
                    ? Mathf.Pow(normalizedDelta + 0.001f, power)
                    : Mathf.Max(0f, 1f - Mathf.Pow(normalizedDelta, Mathf.Abs(power)));
                layerRotations[layerIndex] += speed * factor * 2f * rotationBase;
            }
            else
            {
                layerRotations[layerIndex] += speed * 0.1f * rotationBase;
            }

            layerRotations[layerIndex] %= 360f;
        }

        Array.Copy(c2Lengths, GetLengthState("c2"), runtimeNumBars);
        Array.Copy(c4Lengths, GetLengthState("c4"), runtimeNumBars);
        Array.Copy(b12Lengths, GetLengthState("b12"), runtimeNumBars);
        Array.Copy(b23Lengths, GetLengthState("b23"), runtimeNumBars);
        Array.Copy(b34Lengths, GetLengthState("b34"), runtimeNumBars);
        Array.Copy(b45Lengths, GetLengthState("b45"), runtimeNumBars);

        UpdateColors();
    }

    private void UpdateColors()
    {
        if (barColors == null || barColors.Length != runtimeNumBars)
        {
            barColors = new Color[runtimeNumBars];
        }

        if (colorDynamic)
        {
            float speed = Mathf.Pow(Mathf.Max(0.01f, colorCycleSpeed), Mathf.Max(0.01f, colorCyclePow));
            float follow = colorCycleFollowsAudio ? 1f + Mathf.Clamp(Mathf.Abs(EffectiveA1) / 1000f, 0f, 4f) : 1f;
            colorCycleHue = Mathf.Repeat(colorCycleHue + Time.deltaTime * 0.05f * speed * follow, 1f);
        }

        for (int index = 0; index < runtimeNumBars; index++)
        {
            barColors[index] = GetColorForBar(index, cachedLengthPixels[index]);
        }
    }

    private float GetColorCycleRate()
    {
        if (!colorDynamic)
        {
            return 0f;
        }

        float speed = Mathf.Pow(Mathf.Max(0.01f, colorCycleSpeed), Mathf.Max(0.01f, colorCyclePow));
        float follow = colorCycleFollowsAudio ? 1f + Mathf.Clamp(Mathf.Abs(EffectiveA1) / 1000f, 0f, 4f) : 1f;
        return 0.05f * speed * follow;
    }

    private Color GetPreviewColor()
    {
        if (barColors != null && barColors.Length > 0)
        {
            return barColors[Mathf.Clamp(barColors.Length / 2, 0, barColors.Length - 1)];
        }

        if (gradientPoints != null && gradientPoints.Count > 0)
        {
            return gradientPoints[Mathf.Clamp(gradientPoints.Count / 2, 0, gradientPoints.Count - 1)].color;
        }

        return c4Color;
    }

    private Color GetColorForBar(int barIndex, float barHeight)
    {
        string scheme = (colorScheme ?? "rainbow").ToLowerInvariant();
        float ratio = runtimeNumBars <= 1 ? 0f : barIndex / (float)runtimeNumBars;

        if (scheme == "custom")
        {
            List<PyStyleGradientPoint> sortedPoints = GetSortedGradientPoints();
            float gradientRatio = ratio;
            if ((gradientMode ?? "frequency").Equals("height", StringComparison.OrdinalIgnoreCase))
            {
                gradientRatio = barHeightMax > barHeightMin
                    ? Mathf.Clamp01((barHeight - barHeightMin) / (barHeightMax - barHeightMin))
                    : 0f;
            }

            Color baseColor = gradientEnabled ? InterpolateGradient(sortedPoints, gradientRatio) : sortedPoints[0].color;
            return colorDynamic ? ShiftHue(baseColor, colorCycleHue) : baseColor;
        }

        Color presetColor;
        switch (scheme)
        {
            case "fire":
                presetColor = new Color(1f, ratio * 0.8f, ratio * 0.2f, 1f);
                break;
            case "ice":
                presetColor = new Color(ratio * 0.3f, ratio * 0.7f, 1f, 1f);
                break;
            case "neon":
                presetColor = Color.HSVToRGB((ratio + 0.5f) % 1f, 1f, 1f);
                break;
            default:
                presetColor = Color.HSVToRGB(ratio, 1f, 1f);
                break;
        }

        return colorDynamic ? ShiftHue(presetColor, colorCycleHue) : presetColor;
    }

    private List<PyStyleGradientPoint> GetSortedGradientPoints()
    {
        EnsureGradientPoints();
        List<PyStyleGradientPoint> sorted = new List<PyStyleGradientPoint>(gradientPoints);
        sorted.Sort((a, b) => a.position.CompareTo(b.position));
        return sorted;
    }

    private Color InterpolateGradient(List<PyStyleGradientPoint> points, float ratio)
    {
        if (points == null || points.Count == 0)
        {
            return Color.white;
        }

        ratio = Mathf.Clamp01(ratio);
        for (int index = 0; index < points.Count - 1; index++)
        {
            PyStyleGradientPoint a = points[index];
            PyStyleGradientPoint b = points[index + 1];
            if (ratio < a.position || ratio > b.position)
            {
                continue;
            }

            float blend = Mathf.Approximately(a.position, b.position) ? 0f : Mathf.InverseLerp(a.position, b.position, ratio);
            return Color.Lerp(a.color, b.color, blend);
        }

        return ratio <= points[0].position ? points[0].color : points[points.Count - 1].color;
    }

    private Color ShiftHue(Color baseColor, float hueOffset)
    {
        Color.RGBToHSV(baseColor, out float hue, out float saturation, out float value);
        return Color.HSVToRGB(Mathf.Repeat(hue + hueOffset, 1f), saturation, value);
    }

    private void Render()
    {
        if (!masterVisible)
        {
            DisableAllRenderers();
            return;
        }

        float[] c2Lengths = GetLengthState("c2");
        float[] c4Lengths = GetLengthState("c4");
        float[] b12Lengths = GetLengthState("b12");
        float[] b23Lengths = GetLengthState("b23");
        float[] b34Lengths = GetLengthState("b34");
        float[] b45Lengths = GetLengthState("b45");

        float[] radiusMap1 = new float[runtimeNumBars];
        float[] radiusMap2 = new float[runtimeNumBars];
        float[] radiusMap3 = new float[runtimeNumBars];
        float[] radiusMap4 = new float[runtimeNumBars];
        float[] radiusMap5 = new float[runtimeNumBars];

        for (int index = 0; index < runtimeNumBars; index++)
        {
            radiusMap1[index] = Mathf.Max(0f, currentRadius - peakInnerHeights[index]);
            radiusMap2[index] = Mathf.Max(0f, currentRadius - c2Lengths[index]);
            radiusMap3[index] = currentRadius;
            radiusMap4[index] = currentRadius + c4Lengths[index];
            radiusMap5[index] = currentRadius + peakOuterHeights[index];
        }

        float segmentAngle = Mathf.PI * 2f / runtimeSegments;
        float[] rotations = new float[6];
        for (int layerIndex = 1; layerIndex <= 5; layerIndex++)
        {
            rotations[layerIndex] = layerRotations[layerIndex] * Mathf.Deg2Rad;
        }

        List<Vector3>[] contourPoints = new List<Vector3>[6];
        if (c1On || c1Fill) contourPoints[1] = BuildContourFromRadii(radiusMap1, rotations[1], runtimeSegments, segmentAngle, Mathf.Max(1, c1Step));
        if (c2On || c2Fill) contourPoints[2] = BuildContourFromRadii(radiusMap2, rotations[2], runtimeSegments, segmentAngle, Mathf.Max(1, c2Step));
        if (c4On || c4Fill) contourPoints[4] = BuildContourFromRadii(radiusMap4, rotations[4], runtimeSegments, segmentAngle, Mathf.Max(1, c4Step));
        if (c5On || c5Fill) contourPoints[5] = BuildContourFromRadii(radiusMap5, rotations[5], runtimeSegments, segmentAngle, Mathf.Max(1, c5Step));
        contourPoints[3] = BuildCirclePoints(currentRadius, Mathf.Max(96, runtimeNumBars * runtimeSegments * 4), rotations[3]);

        RenderLayer(1, contourPoints[1], contoursEnabled && c1On, c1Color, c1Alpha, c1Thick, contoursEnabled && c1Fill, c1FillAlpha);
        RenderLayer(2, contourPoints[2], contoursEnabled && c2On, c2Color, c2Alpha, c2Thick, contoursEnabled && c2Fill, c2FillAlpha);
        RenderLayer(3, contourPoints[3], contoursEnabled && c3On, c3Color, c3Alpha, c3Thick, contoursEnabled && c3Fill, c3FillAlpha);
        RenderLayer(4, contourPoints[4], contoursEnabled && c4On, c4Color, c4Alpha, c4Thick, contoursEnabled && c4Fill, c4FillAlpha);
        RenderLayer(5, contourPoints[5], contoursEnabled && c5On, c5Color, c5Alpha, c5Thick, contoursEnabled && c5Fill, c5FillAlpha);

        List<BarSegmentData> segments = new List<BarSegmentData>();
        if (barsEnabled)
        {
            if (b45On) segments.AddRange(BuildBarSegments(radiusMap4, radiusMap5, rotations[4], rotations[5], runtimeSegments, segmentAngle, b45Lengths, "b45"));
            if (b34On) segments.AddRange(BuildBarSegments(radiusMap3, radiusMap4, rotations[3], rotations[4], runtimeSegments, segmentAngle, b34Lengths, "b34"));
            if (b23On) segments.AddRange(BuildBarSegments(radiusMap2, radiusMap3, rotations[2], rotations[3], runtimeSegments, segmentAngle, b23Lengths, "b23"));
            if (b12On) segments.AddRange(BuildBarSegments(radiusMap1, radiusMap2, rotations[1], rotations[2], runtimeSegments, segmentAngle, b12Lengths, "b12"));
        }

        RenderBars(segments);
        RenderTentacles(radiusMap4, rotations[4], segmentAngle);
    }

    private void DisableAllRenderers()
    {
        foreach (LineRenderer line in layerRenderers)
        {
            if (line != null)
            {
                line.enabled = false;
            }
        }

        foreach (MeshRenderer renderer in fillRenderers)
        {
            if (renderer != null)
            {
                renderer.gameObject.SetActive(false);
            }
        }

        foreach (LineRenderer line in barRenderers)
        {
            if (line != null)
            {
                line.enabled = false;
            }
        }

        foreach (LineRenderer line in tentacleRenderers)
        {
            if (line != null)
            {
                line.enabled = false;
            }
        }
    }

    private void RenderLayer(int layerIndex, List<Vector3> points, bool enabled, Color baseColor, int alpha, int thickness, bool fillEnabled, int fillAlpha)
    {
        LineRenderer line = layerRenderers[layerIndex - 1];
        MeshRenderer fillRenderer = fillRenderers[layerIndex - 1];
        Mesh fillMesh = fillMeshes[layerIndex - 1];
        Material fillMaterial = fillMaterials[layerIndex - 1];

        bool hasPoints = points != null && points.Count >= 3;
        if (line != null)
        {
            line.enabled = enabled && hasPoints;
        }

        if (line != null && line.enabled)
        {
            Color color = baseColor;
            color.a = Mathf.Clamp01(alpha / 255f);

            line.positionCount = points.Count;
            line.SetPositions(points.ToArray());
            line.startWidth = thickness * pixelScale;
            line.endWidth = thickness * pixelScale;
            line.startColor = color;
            line.endColor = color;
        }

        if (fillRenderer != null && fillMesh != null && fillMaterial != null && fillEnabled && hasPoints)
        {
            fillRenderer.gameObject.SetActive(true);
            Color fillColor = baseColor;
            fillColor.a = Mathf.Clamp01(fillAlpha / 255f);
            fillMaterial.color = fillColor;
            UpdateFillMesh(fillMesh, points);
        }
        else if (fillRenderer != null && fillMesh != null)
        {
            fillRenderer.gameObject.SetActive(false);
            fillMesh.Clear();
        }
    }

    private void UpdateFillMesh(Mesh mesh, List<Vector3> points)
    {
        mesh.Clear();

        Vector3[] vertices = new Vector3[points.Count + 1];
        int[] triangles = new int[points.Count * 3];
        vertices[0] = Vector3.zero;
        for (int index = 0; index < points.Count; index++)
        {
            vertices[index + 1] = points[index];
            triangles[index * 3] = 0;
            triangles[index * 3 + 1] = index + 1;
            triangles[index * 3 + 2] = (index + 1) % points.Count + 1;
        }

        mesh.vertices = vertices;
        mesh.triangles = triangles;
        mesh.RecalculateBounds();
    }

    private List<Vector3> BuildContourFromRadii(float[] radii, float rotationRad, int segments, float segmentAngle, int step)
    {
        step = Mathf.Max(1, step);
        List<Vector3> controls = new List<Vector3>();

        for (int segment = 0; segment < segments; segment++)
        {
            float segmentOffset = segment * segmentAngle;
            for (int barIndex = 0; barIndex < runtimeNumBars; barIndex += step)
            {
                float angle = barIndex / (float)runtimeNumBars * segmentAngle - Mathf.PI * 0.5f + rotationRad + segmentOffset;
                float radius = radii[Mathf.Clamp(barIndex, 0, radii.Length - 1)] * pixelScale;
                controls.Add(new Vector3(Mathf.Cos(angle) * radius, Mathf.Sin(angle) * radius, 0f));
            }
        }

        if (controls.Count < 4 && step > 1)
        {
            return BuildContourFromRadii(radii, rotationRad, segments, segmentAngle, 1);
        }

        return BuildClosedBSpline(controls);
    }

    private List<Vector3> BuildCirclePoints(float radiusPixels, int pointCount, float rotationRad)
    {
        List<Vector3> points = new List<Vector3>(pointCount);
        float radius = radiusPixels * pixelScale;
        int count = Mathf.Max(32, pointCount);
        for (int index = 0; index < count; index++)
        {
            float angle = index / (float)count * Mathf.PI * 2f + rotationRad - Mathf.PI * 0.5f;
            points.Add(new Vector3(Mathf.Cos(angle) * radius, Mathf.Sin(angle) * radius, 0f));
        }
        return points;
    }

    private List<Vector3> BuildClosedBSpline(List<Vector3> controlPoints)
    {
        if (controlPoints == null || controlPoints.Count < 4)
        {
            return controlPoints ?? new List<Vector3>();
        }

        int count = controlPoints.Count;
        int samplesPerSegment = Mathf.Max(8, Mathf.CeilToInt(220f / count));
        List<Vector3> points = new List<Vector3>(count * samplesPerSegment);

        for (int index = 0; index < count; index++)
        {
            Vector3 p0 = controlPoints[(index - 1 + count) % count];
            Vector3 p1 = controlPoints[index];
            Vector3 p2 = controlPoints[(index + 1) % count];
            Vector3 p3 = controlPoints[(index + 2) % count];

            for (int sample = 0; sample < samplesPerSegment; sample++)
            {
                float t = sample / (float)samplesPerSegment;
                float t2 = t * t;
                float t3 = t2 * t;
                float b0 = (-t3 + 3f * t2 - 3f * t + 1f) / 6f;
                float b1 = (3f * t3 - 6f * t2 + 4f) / 6f;
                float b2 = (-3f * t3 + 3f * t2 + 3f * t + 1f) / 6f;
                float b3 = t3 / 6f;
                points.Add(p0 * b0 + p1 * b1 + p2 * b2 + p3 * b3);
            }
        }

        return points;
    }

    private List<BarSegmentData> BuildBarSegments(float[] radiiA, float[] radiiB, float rotationA, float rotationB, int segments, float segmentAngle, float[] lengths, string key)
    {
        List<BarSegmentData> segmentsData = new List<BarSegmentData>();
        bool fixedLength = GetBarFixed(key);
        float fixedPixels = GetBarFixedLength(key) * pixelScale;
        bool fromStart = GetBarMode(key, "start");
        bool fromEnd = GetBarMode(key, "end");
        bool fromCenter = GetBarMode(key, "center");

        for (int segment = 0; segment < segments; segment++)
        {
            float segmentOffset = segment * segmentAngle;
            for (int barIndex = 0; barIndex < runtimeNumBars; barIndex++)
            {
                float angleA = barIndex / (float)runtimeNumBars * segmentAngle - Mathf.PI * 0.5f + rotationA + segmentOffset;
                float angleB = barIndex / (float)runtimeNumBars * segmentAngle - Mathf.PI * 0.5f + rotationB + segmentOffset;
                Vector3 start = new Vector3(Mathf.Cos(angleA) * radiiA[barIndex] * pixelScale, Mathf.Sin(angleA) * radiiA[barIndex] * pixelScale, 0f);
                Vector3 end = new Vector3(Mathf.Cos(angleB) * radiiB[barIndex] * pixelScale, Mathf.Sin(angleB) * radiiB[barIndex] * pixelScale, 0f);

                int colorIndex = (barIndex + segment * runtimeNumBars / Mathf.Max(1, segments)) % Mathf.Max(1, barColors.Length);
                Color color = GetColorForBar(colorIndex, lengths[barIndex]);
                color.a = 1f;

                if (!fixedLength)
                {
                    segmentsData.Add(new BarSegmentData(start, end, color));
                    continue;
                }

                Vector3 delta = end - start;
                float fullLength = delta.magnitude;
                if (fullLength <= 0.0001f)
                {
                    continue;
                }

                Vector3 direction = delta / fullLength;
                float clipped = Mathf.Min(fixedPixels, fullLength);

                if (fromStart)
                {
                    segmentsData.Add(new BarSegmentData(start, start + direction * clipped, color));
                }
                if (fromEnd)
                {
                    segmentsData.Add(new BarSegmentData(end, end - direction * clipped, color));
                }
                if (fromCenter)
                {
                    Vector3 center = (start + end) * 0.5f;
                    Vector3 half = direction * (clipped * 0.5f);
                    segmentsData.Add(new BarSegmentData(center - half, center + half, color));
                }
            }
        }

        return segmentsData;
    }

    private void RenderBars(List<BarSegmentData> segments)
    {
        int index = 0;
        int b45Count = barsEnabled && b45On ? runtimeNumBars * runtimeSegments * GetSegmentModeCount("b45") : 0;
        int b34Count = barsEnabled && b34On ? runtimeNumBars * runtimeSegments * GetSegmentModeCount("b34") : 0;
        int b23Count = barsEnabled && b23On ? runtimeNumBars * runtimeSegments * GetSegmentModeCount("b23") : 0;

        for (; index < segments.Count && index < barRenderers.Count; index++)
        {
            LineRenderer renderer = barRenderers[index];
            BarSegmentData segment = segments[index];

            int thickness = index < b45Count
                ? b45Thick
                : index < b45Count + b34Count
                    ? b34Thick
                    : index < b45Count + b34Count + b23Count
                        ? b23Thick
                        : b12Thick;

            renderer.enabled = true;
            renderer.startWidth = thickness * pixelScale;
            renderer.endWidth = thickness * pixelScale;
            renderer.SetPosition(0, segment.start);
            renderer.SetPosition(1, segment.end);
            renderer.startColor = segment.color;
            renderer.endColor = segment.color;
        }

        for (; index < barRenderers.Count; index++)
        {
            barRenderers[index].enabled = false;
        }
    }

    private void RenderTentacles(float[] outerRadii, float rotationRad, float segmentAngle)
    {
        bool active = tentaclesEnabled && tentacleOn && tentacleRenderers.Count > 0;
        if (!active)
        {
            for (int index = 0; index < tentacleRenderers.Count; index++)
            {
                if (tentacleRenderers[index] != null)
                    tentacleRenderers[index].enabled = false;
            }

            return;
        }

        int count = tentacleRenderers.Count;
        float scale = Mathf.Max(0.01f, globalScale);
        float effectiveK = Mathf.Min(1f, Mathf.Log(1f + Mathf.Abs(EffectiveA1)) / 6f);
        float effectiveP = Mathf.Min(1f, Mathf.Log(1f + Mathf.Abs(CurrentP)) / 6f);

        float absP = Mathf.Abs(CurrentP);
        tentaclePPeakReference = tentaclePPeakReference * 0.94f + absP * 0.06f;
        bool isRising = absP > tentaclePrevAbsP + 0.0001f;
        if (tentaclePPeakCooldown > 0)
        {
            tentaclePPeakCooldown--;
        }

        float peakThreshold = Mathf.Max(0.015f, tentaclePPeakReference * 1.08f);
        if (tentaclePrevPRising && !isRising && tentaclePrevAbsP >= peakThreshold && tentaclePPeakCooldown == 0)
        {
            tentacleCoreAccelDirection *= -1f;
            tentaclePPeakCooldown = 10;
        }

        tentaclePrevPRising = isRising;
        tentaclePrevAbsP = absP;

        float coreAcceleration = tentacleCoreBaseSpeed;
        if (kpBindTentacleCoreBaseSpeedK)
        {
            coreAcceleration += Mathf.Lerp(kpTentacleCoreBaseSpeedKWmin, kpTentacleCoreBaseSpeedKWmax, effectiveK);
        }
        else
        {
            coreAcceleration += effectiveK * tentacleCoreKSpeed;
        }

        if (kpBindTentacleCoreBaseSpeedP)
        {
            coreAcceleration += Mathf.Lerp(kpTentacleCoreBaseSpeedPWmin, kpTentacleCoreBaseSpeedPWmax, effectiveP);
        }
        else
        {
            coreAcceleration += effectiveP * tentacleCorePSpeed;
        }

        coreAcceleration *= tentacleCoreAccelDirection;
        tentacleCoreAngularVelocity *= 0.92f;
        tentacleCoreAngularVelocity += coreAcceleration * 0.0028f * rotationBase;
        tentacleCoreAngularVelocity = Mathf.Clamp(tentacleCoreAngularVelocity, -0.12f, 0.12f);
        tentacleCoreCurrentRotation = Mathf.Repeat(tentacleCoreCurrentRotation + tentacleCoreAngularVelocity, Mathf.PI * 2f);
        float swirlStrength = Mathf.Min(1.65f, Mathf.Abs(tentacleCoreAngularVelocity) * (7.5f + tentacleSwaySpeed * 2f));

        // Physics parameters — exact M3 Python formulas
        float waterDamping = Mathf.Clamp(tentacleWaterDamping, 0f, 0.999f);
        float fluidDamping = 0.86f + waterDamping * 0.13f;
        float bendResponse = 0.04f + tentacleAngleStiffness * 0.18f;
        float stretchResponse = 0.04f + tentacleLengthStiffness * 0.16f;
        float followResponse = 0.06f + (tentacleAngleStiffness + tentacleLengthStiffness) * 0.08f;
        float swayDensity = Mathf.Max(0.1f, tentacleSwayDensity);
        float timeNow = Time.unscaledTime;
        float flowTime = timeNow * (0.18f + tentacleSwaySpeed * 0.18f);

        // K-driven turbulence coefficient (matching M3 Python logic)
        float turbulenceBase = Mathf.Max(0f, tentacleTurbulence * scale);
        float turbCoef;
        if (kpBindTentacleTurbulenceK)
            turbCoef = Mathf.Lerp(kpTentacleTurbulenceKWmin, kpTentacleTurbulenceKWmax, effectiveK);
        else
            turbCoef = 0.22f + effectiveK * Mathf.Min(0.55f, 0.22f + tentacleKInfluence * 0.18f);
        turbCoef = Mathf.Clamp(turbCoef, 0f, 2.5f);
        float turbulence = turbulenceBase * turbCoef;

        // Width
        float thicknessFactor = EvaluateBindingMultiplier(kpBindTentacleThickK, kpTentacleThickKWmin, kpTentacleThickKWmax, effectiveK) *
            EvaluateBindingMultiplier(kpBindTentacleThickP, kpTentacleThickPWmin, kpTentacleThickPWmax, effectiveP);
        float tipFactor = EvaluateBindingMultiplier(kpBindTentacleTipThicknessP, kpTentacleTipThicknessPWmin, kpTentacleTipThicknessPWmax, effectiveP);
        float shaderAlphaStartFactor = tentacleShaderEnabled
            ? EvaluateBindingMultiplier(kpBindTentacleShaderAlphaStartK, kpTentacleShaderAlphaStartKWmin, kpTentacleShaderAlphaStartKWmax, effectiveK) *
              EvaluateBindingMultiplier(kpBindTentacleShaderAlphaStartP, kpTentacleShaderAlphaStartPWmin, kpTentacleShaderAlphaStartPWmax, effectiveP)
            : 1f;
        float width = Mathf.Max(0.01f, tentacleThick * pixelScale * Mathf.Max(0.05f, thicknessFactor));
        float tipWidth = Mathf.Max(0.001f, width * Mathf.Clamp01(Mathf.Max(0.01f, tentacleTipThickness) * Mathf.Max(0.05f, tipFactor)));
        float shaderAlphaStart = tentacleShaderAlphaStart * shaderAlphaStartFactor;

        // Base length + jitter
        float baseLength = Mathf.Max(1f, tentacleLength * scale);
        float jitterAmplitude = Mathf.Max(0f, tentacleLengthJitter) * scale *
            EvaluateBindingMultiplier(kpBindTentacleLengthJitterK, kpTentacleLengthJitterKWmin, kpTentacleLengthJitterKWmax, effectiveK);
        float jitterSpeedEff = tentacleLengthJitterSpeed *
            EvaluateBindingMultiplier(kpBindTentacleLengthJitterSpeedP, kpTentacleLengthJitterSpeedPWmin, kpTentacleLengthJitterSpeedPWmax, effectiveP);

        // Ensure physics state arrays are allocated and correctly sized
        int cpMin = Mathf.Max(3, tentacleControlPointsMin);
        int cpMax = Mathf.Max(cpMin, tentacleControlPointsMax);
        int cpRange = Mathf.Max(1, cpMax - cpMin + 1);
        int physSegs = Mathf.Max(2, cpMax - 1);
        if (tentacleOffsets == null || tentacleOffsets.Length != count || tentaclePhysicsSegments != physSegs || tentacleControlPointCounts == null || tentacleControlPointCounts.Length != count)
        {
            tentaclePhysicsSegments = physSegs;
            tentacleControlPointCounts = new int[count];
            tentacleOffsets = new Vector2[count][];
            tentacleVelocities = new Vector2[count][];
            tentacleInitialized = new bool[count];
            for (int i = 0; i < count; i++)
            {
                int cpCount = cpMin + (i % cpRange);
                int outerPointsForTentacle = Mathf.Max(2, cpCount - 1);
                tentacleControlPointCounts[i] = cpCount;
                tentacleOffsets[i] = new Vector2[outerPointsForTentacle];
                tentacleVelocities[i] = new Vector2[outerPointsForTentacle];
            }
        }

        for (int tentacleIndex = 0; tentacleIndex < count; tentacleIndex++)
        {
            LineRenderer renderer = tentacleRenderers[tentacleIndex];
            if (renderer == null)
                continue;

            // Angle: evenly distributed + spinning core + K-driven wobble (M3 Python formula)
            float angle = tentacleCoreCurrentRotation + (tentacleIndex / (float)count) * Mathf.PI * 2f - Mathf.PI * 0.5f;
            angle += 0.08f * Mathf.Sin(timeNow * (0.35f + tentacleSwaySpeed * 0.25f) + tentacleIndex * 0.91f) * (0.2f + effectiveK * 0.8f);
            Vector2 direction = new Vector2(Mathf.Cos(angle), Mathf.Sin(angle));
            Vector2 normal = new Vector2(-direction.y, direction.x);

            float phase = tentaclePhaseOffsets != null && tentacleIndex < tentaclePhaseOffsets.Length
                ? tentaclePhaseOffsets[tentacleIndex] : 0f;

            // Length jitter (random or synchronized, matching M3)
            float jitter;
            if (tentacleLengthJitterRandom)
            {
                float hashed = Mathf.Abs(Mathf.Sin(tentacleIndex * 12.9898f + 78.233f) * 43758.5453f);
                hashed -= Mathf.Floor(hashed);
                float jitterPhase = (timeNow * Mathf.Max(0f, jitterSpeedEff)) % 1f;
                float jitterTri = 1f - Mathf.Abs(2f * jitterPhase - 1f);
                jitter = jitterTri * jitterAmplitude * (0.25f + 0.75f * hashed);
            }
            else
            {
                // Triangle wave (matching Python: 1 - abs(2*phase - 1)), always non-negative like the Python version
                float jitterPhase = (timeNow * Mathf.Max(0f, jitterSpeedEff)) % 1f;
                jitter = (1f - Mathf.Abs(2f * jitterPhase - 1f)) * jitterAmplitude;
            }

            // Shared length from bar at this tentacle's position (bar heights drive tentacle length like M3)
            int barIndex = Mathf.Clamp(Mathf.RoundToInt((tentacleIndex / (float)count) * runtimeNumBars), 0, runtimeNumBars - 1);
            float sharedLength = cachedLengthPixels != null && barIndex < cachedLengthPixels.Length
                ? Mathf.Max(0f, cachedLengthPixels[barIndex]) : 0f;

            float totalLength = Mathf.Max(12f, baseLength + sharedLength * 0.38f + jitter * 0.45f);
            int outerPoints = tentacleOffsets[tentacleIndex] != null ? tentacleOffsets[tentacleIndex].Length : Mathf.Max(2, tentaclePhysicsSegments);
            float segmentLength = totalLength / Mathf.Max(1, outerPoints);

            // Pre-compute desired offsets (non-physics spring reference targets, in pixel units from center)
            Vector2[] desiredOffsets = new Vector2[outerPoints + 1]; // desiredOffsets[0] = Vector2.zero (root)
            for (int si = 0; si < outerPoints; si++)
            {
                float ratio = (si + 1f) / outerPoints;
                float tipWeight = Mathf.Pow(ratio, Mathf.Max(0.01f, tentacleTipBias));
                float arcLength = segmentLength * (si + 1);
                float radialWave = Mathf.Sin(flowTime * (0.75f + swayDensity * 0.22f) + tentacleIndex * 0.73f + ratio * (2.4f + swayDensity * 0.8f));
                float lateralWave = Mathf.Cos(flowTime * (0.58f + swayDensity * 0.17f) + tentacleIndex * 0.41f - ratio * 1.9f);
                float lateralOffset = turbulence * tipWeight * 0.16f * lateralWave;
                float radialOffset = turbulence * tipWeight * 0.12f * radialWave;
                float contractAmount = swirlStrength * totalLength * Mathf.Pow(ratio, 1.35f) * (0.1f + tentacleAngleStiffness * 0.22f);
                float swirlDrag = tentacleCoreAngularVelocity * totalLength * tipWeight * (0.3f + tentacleAngleStiffness * 0.6f);
                Vector2 inwardPull = -direction * (swirlStrength * totalLength * Mathf.Pow(ratio, 1.55f) * (0.035f + tentacleLengthStiffness * 0.08f));
                Vector2 desiredPrev = desiredOffsets[si];
                float prevLen = desiredPrev.magnitude;
                float contractedArc = Mathf.Max(segmentLength * (1f + 0.08f * tentacleLengthStiffness), arcLength + radialOffset - contractAmount);
                Vector2 desiredSeg = direction * Mathf.Max(segmentLength * 0.75f, contractedArc - prevLen);
                desiredSeg += normal * (lateralOffset * 0.38f + swirlDrag * 0.72f);
                float segNorm = desiredSeg.magnitude;
                if (segNorm > 1e-6f)
                    desiredSeg = desiredSeg / segNorm * Mathf.Max(segmentLength * 0.72f, Mathf.Min(segNorm, segmentLength * 1.08f));
                desiredOffsets[si + 1] = desiredPrev + desiredSeg + inwardPull;
            }

            // Soft-body physics simulation (M3 exact force equations with fluid damping)
            bool initialized = tentacleInitialized != null && tentacleInitialized[tentacleIndex];
            for (int si = 0; si < outerPoints; si++)
            {
                float ratio = (si + 1f) / outerPoints;
                float arcLength = segmentLength * (si + 1);
                float tipWeight = Mathf.Pow(ratio, Mathf.Max(0.01f, tentacleTipBias));
                float contractAmount = swirlStrength * totalLength * Mathf.Pow(ratio, 1.35f) * (0.1f + tentacleAngleStiffness * 0.22f);
                float contractedArc = Mathf.Max(segmentLength * (1f + 0.08f * tentacleLengthStiffness), arcLength - contractAmount);
                float swirlDrag = tentacleCoreAngularVelocity * totalLength * tipWeight * (0.3f + tentacleAngleStiffness * 0.6f);
                float lateralWave = Mathf.Cos(flowTime * (0.58f + swayDensity * 0.17f) + tentacleIndex * 0.41f - ratio * 1.9f);
                float lateralOffset = turbulence * tipWeight * 0.16f * lateralWave;
                float radialTarget = contractedArc;
                float tangentialTarget = lateralOffset + swirlDrag;

                if (!initialized)
                {
                    tentacleOffsets[tentacleIndex][si] = desiredOffsets[si + 1];
                    tentacleVelocities[tentacleIndex][si] = Vector2.zero;
                }
                else
                {
                    Vector2 current = tentacleOffsets[tentacleIndex][si];
                    Vector2 velocity = tentacleVelocities[tentacleIndex][si];
                    Vector2 parentCurrent = si > 0 ? tentacleOffsets[tentacleIndex][si - 1] : Vector2.zero;
                    Vector2 parentDesired = desiredOffsets[si];
                    float radialCurrent = Vector2.Dot(current, direction);
                    float tangentialCurrent = Vector2.Dot(current, normal);
                    Vector2 currentSeg = current - parentCurrent;
                    Vector2 desiredSeg = desiredOffsets[si + 1] - parentDesired;
                    Vector2 blendedTarget = current * 0.72f + desiredOffsets[si + 1] * 0.28f;
                    Vector2 force = (blendedTarget - current) * (0.05f + stretchResponse * 0.45f);
                    force += (desiredSeg - currentSeg) * (0.07f + stretchResponse * 0.38f);
                    force += direction * (radialTarget - radialCurrent) * stretchResponse;
                    force += normal * (tangentialTarget - tangentialCurrent) * (bendResponse + 0.04f * swirlStrength);
                    force += (parentCurrent - parentDesired) * followResponse;
                    velocity = velocity * fluidDamping + force;
                    float maxVel = Mathf.Max(0.6f, segmentLength * (0.11f + tentacleSwaySpeed * 0.015f));
                    float velMag = velocity.magnitude;
                    if (velMag > maxVel)
                        velocity = velocity * (maxVel / velMag);
                    current += velocity;
                    float maxOffsetLen = Mathf.Max(1f, arcLength * Mathf.Max(1f, tentacleStretchLimit));
                    float currentLen = current.magnitude;
                    if (currentLen > maxOffsetLen)
                    {
                        float clampRatio = maxOffsetLen / currentLen;
                        current *= clampRatio;
                        velocity *= clampRatio;
                    }

                    tentacleOffsets[tentacleIndex][si] = current;
                    tentacleVelocities[tentacleIndex][si] = velocity;
                }
            }

            if (tentacleInitialized != null)
                tentacleInitialized[tentacleIndex] = true;

            // Build raw control points (root at local center, then physics offsets in world units)
            int totalCtrl = outerPoints + 1;
            Vector3[] ctrlPoints = new Vector3[totalCtrl];
            ctrlPoints[0] = Vector3.zero;
            for (int si = 0; si < outerPoints; si++)
            {
                Vector2 offset = tentacleOffsets[tentacleIndex][si];
                ctrlPoints[si + 1] = new Vector3(offset.x * pixelScale, offset.y * pixelScale, 0f);
            }

            // Smooth with open B-spline (Catmull-Rom) — matching Python's _build_open_spline behavior
            int splineCount = Mathf.Max(totalCtrl * 12, 64);
            Vector3[] points = BuildOpenSpline(ctrlPoints, splineCount);

            renderer.enabled = true;
            renderer.positionCount = points.Length;
            renderer.SetPositions(points);
            renderer.widthCurve = AnimationCurve.Linear(0f, width, 1f, tipWidth);

            Color rootColor = tentacleColor;
            rootColor.a = Mathf.Clamp01(tentacleAlpha / 255f);
            if (!tentacleShaderEnabled)
            {
                renderer.startColor = rootColor;
                renderer.endColor = rootColor;
                continue;
            }

            Color tipColor = tentacleShaderTipColor;
            tipColor.a = Mathf.Clamp01((tentacleAlpha / 255f) * Mathf.Clamp01(tentacleShaderAlphaEnd));
            rootColor.a = Mathf.Clamp01((tentacleAlpha / 255f) * Mathf.Clamp01(shaderAlphaStart));
            Gradient gradient = new Gradient();
            float midPoint = Mathf.Clamp01(1f / Mathf.Max(1f, tentacleShaderBias + 1f));
            gradient.SetKeys(
                new GradientColorKey[]
                {
                    new GradientColorKey(rootColor, 0f),
                    new GradientColorKey(Color.Lerp(rootColor, tipColor, 0.35f), midPoint),
                    new GradientColorKey(tipColor, 1f),
                },
                new GradientAlphaKey[]
                {
                    new GradientAlphaKey(rootColor.a, 0f),
                    new GradientAlphaKey(Mathf.Lerp(rootColor.a, tipColor.a, 0.5f), midPoint),
                    new GradientAlphaKey(tipColor.a, 1f),
                });
            renderer.colorGradient = gradient;
        }
    }

    private void RenderTentacleCore()
    {
        return;
    }

    private float EvaluateBindingMultiplier(bool enabled, float wmin, float wmax, float signal)
    {
        if (!enabled)
        {
            return 1f;
        }

        float low = Mathf.Min(wmin, wmax);
        float high = Mathf.Max(wmin, wmax);
        if (Mathf.Approximately(low, high))
        {
            return Mathf.Max(0f, low);
        }

        return Mathf.Max(0f, Mathf.Lerp(low, high, Mathf.Clamp01(signal)));
    }

    private int GetSegmentModeCount(string key)
    {
        if (!GetBarFixed(key))
        {
            return 1;
        }

        int count = 0;
        if (GetBarMode(key, "start")) count++;
        if (GetBarMode(key, "end")) count++;
        if (GetBarMode(key, "center")) count++;
        return Mathf.Max(1, count);
    }

    private bool GetBarFixed(string key)
    {
        switch (key)
        {
            case "b12": return b12Fixed;
            case "b23": return b23Fixed;
            case "b34": return b34Fixed;
            case "b45": return b45Fixed;
            default: return false;
        }
    }

    private int GetBarFixedLength(string key)
    {
        switch (key)
        {
            case "b12": return b12FixedLen;
            case "b23": return b23FixedLen;
            case "b34": return b34FixedLen;
            case "b45": return b45FixedLen;
            default: return 30;
        }
    }

    private bool GetBarMode(string key, string mode)
    {
        switch (key)
        {
            case "b12": return mode == "start" ? b12FromStart : mode == "end" ? b12FromEnd : b12FromCenter;
            case "b23": return mode == "start" ? b23FromStart : mode == "end" ? b23FromEnd : b23FromCenter;
            case "b34": return mode == "start" ? b34FromStart : mode == "end" ? b34FromEnd : b34FromCenter;
            case "b45": return mode == "start" ? b45FromStart : mode == "end" ? b45FromEnd : b45FromCenter;
            default: return false;
        }
    }

    private float GetLayerRotationSpeed(int layerIndex)
    {
        switch (layerIndex)
        {
            case 1: return c1RotSpeed;
            case 2: return c2RotSpeed;
            case 3: return c3RotSpeed;
            case 4: return c4RotSpeed;
            case 5: return c5RotSpeed;
            default: return 0f;
        }
    }

    private float GetLayerRotationPower(int layerIndex)
    {
        switch (layerIndex)
        {
            case 1: return c1RotPow;
            case 2: return c2RotPow;
            case 3: return c3RotPow;
            case 4: return c4RotPow;
            case 5: return c5RotPow;
            default: return 0f;
        }
    }

    /// <summary>
    /// Catmull-Rom open spline interpolation — matches Python's _build_open_spline (scipy BSpline degree-3 clamped).
    /// Adds phantom endpoints so the curve passes through the first and last control points.
    /// outputCount matches Python's max(count*12, 64).
    /// </summary>
    private static Vector3[] BuildOpenSpline(Vector3[] controlPoints, int outputCount)
    {
        int count = controlPoints.Length;
        if (count == 0)
        {
            return new Vector3[0];
        }

        if (count == 1)
        {
            Vector3[] single = new Vector3[outputCount];
            for (int i = 0; i < outputCount; i++) single[i] = controlPoints[0];
            return single;
        }

        if (count == 2)
        {
            Vector3[] lerped = new Vector3[outputCount];
            for (int i = 0; i < outputCount; i++)
                lerped[i] = Vector3.Lerp(controlPoints[0], controlPoints[1], i / (float)Mathf.Max(1, outputCount - 1));
            return lerped;
        }

        // Extend array with phantom endpoints to produce a clamped/pinned curve
        // phantom start = 2*P[0] - P[1], phantom end = 2*P[n-1] - P[n-2]
        Vector3[] pts = new Vector3[count + 2];
        pts[0] = 2f * controlPoints[0] - controlPoints[1];
        for (int i = 0; i < count; i++) pts[i + 1] = controlPoints[i];
        pts[count + 1] = 2f * controlPoints[count - 1] - controlPoints[count - 2];

        Vector3[] result = new Vector3[outputCount];
        float totalSegments = count - 1f;

        for (int i = 0; i < outputCount; i++)
        {
            float t = i / (float)Mathf.Max(1, outputCount - 1);
            float pos = t * totalSegments;
            int seg = Mathf.Clamp((int)pos, 0, count - 2);
            float lt = pos - seg;

            // pts indices: seg+0 (phantom or earlier), seg+1, seg+2, seg+3 (phantom or later)
            Vector3 p0 = pts[seg];
            Vector3 p1 = pts[seg + 1];
            Vector3 p2 = pts[seg + 2];
            Vector3 p3 = pts[seg + 3];

            float lt2 = lt * lt;
            float lt3 = lt2 * lt;

            result[i] = 0.5f * (
                2f * p1 +
                (-p0 + p2) * lt +
                (2f * p0 - 5f * p1 + 4f * p2 - p3) * lt2 +
                (-p0 + 3f * p1 - 3f * p2 + p3) * lt3
            );
        }

        return result;
    }

    private void OnDestroy()
    {
        ClearRendererObjects();
    }
}
