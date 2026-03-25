using System;
using System.Runtime.InteropServices;
using System.Threading;
using UnityEngine;

/// <summary>
/// 通过 WASAPI loopback 读取 Windows 默认回放设备的输出音频。
/// </summary>
public class WindowsAudioCapture : MonoBehaviour
{
    [Header("Windows Loopback Capture")]
    public bool enableCapture = true;

    [Range(256, 8192)]
    public int fftSize = 2048;

    [Range(0.1f, 8f)]
    public float spectrumGain = 2.5f;

    [Range(0.1f, 8f)]
    public float loudnessGain = 1.5f;

    [Range(0f, 0.02f)]
    public float silenceFloor = 0.00035f;

    [Header("Status")]
    public bool isCapturing = false;
    public bool hasSignal = false;
    public float currentVolume = 0f;
    public string statusMessage = "未启动";
    public string deviceFormat = "";

    private const int DefaultBufferDurationHundredNanoseconds = 2000000;
    private const int RpcChangedMode = unchecked((int)0x80010106);
    private const ushort WaveFormatPcm = 0x0001;
    private const ushort WaveFormatIeeeFloat = 0x0003;
    private const ushort WaveFormatExtensibleTag = 0xFFFE;

    private static readonly Guid AudioClientGuid = typeof(IAudioClient).GUID;
    private static readonly Guid AudioCaptureClientGuid = typeof(IAudioCaptureClient).GUID;
    private static readonly Guid KsdFormatSubtypePcm = new Guid("00000001-0000-0010-8000-00AA00389B71");
    private static readonly Guid KsdFormatSubtypeIeeeFloat = new Guid("00000003-0000-0010-8000-00AA00389B71");

    private PyStyleVisualizer visualizer;
    private readonly object bufferLock = new object();
    private float[] spectrumBuffer;
    private float[] sampleHistory;
    private float[] fftWindow;
    private float[] fftReal;
    private float[] fftImag;
    private Thread captureThread;
    private volatile bool threadRunning;
    private int historyFillCount;
    private volatile int captureSampleRate = 48000;

    private void Start()
    {
        visualizer = GetComponent<PyStyleVisualizer>();
        ConfigureBuffers();

        if (enableCapture)
        {
            StartCapture();
        }
    }

    private void Update()
    {
        if (!isCapturing || visualizer == null || spectrumBuffer == null)
        {
            return;
        }

        lock (bufferLock)
        {
            visualizer.SetExternalSpectrum(spectrumBuffer, currentVolume, captureSampleRate);
        }
    }

    private void OnDisable()
    {
        if (Application.isPlaying)
        {
            StopCapture();
        }
    }

    private void OnDestroy()
    {
        StopCapture();
    }

    private void OnApplicationQuit()
    {
        StopCapture();
    }

    public void StartCapture()
    {
        if (threadRunning)
        {
            return;
        }

        ConfigureBuffers();
        captureSampleRate = 48000;
        threadRunning = true;
        isCapturing = false;
        hasSignal = false;
        currentVolume = 0f;
        statusMessage = "正在连接 Windows 默认回放设备";

        captureThread = new Thread(CaptureThreadMain)
        {
            IsBackground = true,
            Name = "Windows Loopback Capture",
            Priority = System.Threading.ThreadPriority.AboveNormal
        };
        captureThread.Start();
    }

    public void StopCapture()
    {
        threadRunning = false;

        if (captureThread != null && captureThread.IsAlive)
        {
            captureThread.Join(1500);
        }

        captureThread = null;
        isCapturing = false;
        hasSignal = false;
        currentVolume = 0f;

        lock (bufferLock)
        {
            if (spectrumBuffer != null)
            {
                Array.Clear(spectrumBuffer, 0, spectrumBuffer.Length);
            }
        }

        if (string.IsNullOrEmpty(statusMessage) || !statusMessage.StartsWith("Windows 音频捕获失败", StringComparison.Ordinal))
        {
            statusMessage = "已停止";
        }
    }

    private void ConfigureBuffers()
    {
        fftSize = Mathf.Clamp(Mathf.NextPowerOfTwo(Mathf.Max(256, fftSize)), 256, 8192);

        if (spectrumBuffer != null && spectrumBuffer.Length == fftSize)
        {
            return;
        }

        spectrumBuffer = new float[fftSize];
        sampleHistory = new float[fftSize];
        fftWindow = new float[fftSize];
        fftReal = new float[fftSize];
        fftImag = new float[fftSize];
        historyFillCount = 0;

        for (int i = 0; i < fftSize; i++)
        {
            fftWindow[i] = 0.5f * (1f - Mathf.Cos((2f * Mathf.PI * i) / (fftSize - 1f)));
        }
    }

    private void CaptureThreadMain()
    {
#if UNITY_STANDALONE_WIN || UNITY_EDITOR_WIN
        string exitStatus = "已停止";
        WasapiLoopbackSession session = new WasapiLoopbackSession();

        try
        {
            if (!session.Initialize(DefaultBufferDurationHundredNanoseconds, out string initializeError))
            {
                exitStatus = initializeError;
                enableCapture = false;
                return;
            }

            deviceFormat = session.FormatDescription;
            captureSampleRate = Mathf.Max(1, session.SampleRate);

            if (!session.Start(out string startError))
            {
                exitStatus = startError;
                enableCapture = false;
                return;
            }

            isCapturing = true;
            statusMessage = "已连接，等待外部音频";

            float[] packetBuffer = new float[Mathf.Max(1, session.MaxFramesPerPacket)];
            while (threadRunning)
            {
                bool readAnyPacket = false;
                while (threadRunning && session.TryReadPacket(packetBuffer, out int sampleCount))
                {
                    readAnyPacket = true;
                    if (sampleCount > 0)
                    {
                        ProcessSamples(packetBuffer, sampleCount);
                    }
                }

                if (!readAnyPacket)
                {
                    DecaySignal();
                    Thread.Sleep(8);
                }
            }
        }
        catch (Exception ex)
        {
            exitStatus = $"Windows 音频捕获失败: {ex.Message}";
            enableCapture = false;
        }
        finally
        {
            session.Dispose();
            isCapturing = false;
            hasSignal = false;
            currentVolume = 0f;
            threadRunning = false;

            lock (bufferLock)
            {
                if (spectrumBuffer != null)
                {
                    Array.Clear(spectrumBuffer, 0, spectrumBuffer.Length);
                }
            }

            if (!string.IsNullOrEmpty(exitStatus))
            {
                statusMessage = exitStatus;
            }
        }
#else
        threadRunning = false;
        enableCapture = false;
        statusMessage = "当前平台不支持 Windows 回放环回捕获";
#endif
    }

    private void ProcessSamples(float[] samples, int sampleCount)
    {
        if (samples == null || sampleCount <= 0)
        {
            return;
        }

        int clampedCount = Mathf.Min(sampleCount, samples.Length);
        if (clampedCount >= fftSize)
        {
            Array.Copy(samples, clampedCount - fftSize, sampleHistory, 0, fftSize);
            historyFillCount = fftSize;
        }
        else
        {
            int keepCount = fftSize - clampedCount;
            Array.Copy(sampleHistory, clampedCount, sampleHistory, 0, keepCount);
            Array.Copy(samples, 0, sampleHistory, keepCount, clampedCount);
            historyFillCount = Mathf.Min(fftSize, historyFillCount + clampedCount);
        }

        float sumSquares = 0f;
        float peak = 0f;
        for (int i = 0; i < clampedCount; i++)
        {
            float value = samples[i];
            sumSquares += value * value;
            float abs = Mathf.Abs(value);
            if (abs > peak)
            {
                peak = abs;
            }
        }

        float rms = Mathf.Sqrt(sumSquares / Mathf.Max(1, clampedCount)) * Mathf.Max(0.1f, loudnessGain);
        float gatedRms = rms < silenceFloor ? 0f : rms;

        lock (bufferLock)
        {
            currentVolume = Mathf.Lerp(currentVolume, gatedRms, 0.35f);
            hasSignal = peak > silenceFloor * 2f || currentVolume > silenceFloor;
            statusMessage = hasSignal ? "正在监听 Windows 回放" : "已连接，等待外部音频";
        }

        if (historyFillCount < fftSize)
        {
            return;
        }

        ComputeSpectrum();
    }

    private void DecaySignal()
    {
        lock (bufferLock)
        {
            currentVolume = Mathf.Lerp(currentVolume, 0f, 0.12f);
            hasSignal = currentVolume > silenceFloor;
            statusMessage = hasSignal ? "正在监听 Windows 回放" : "已连接，等待外部音频";

            if (spectrumBuffer == null)
            {
                return;
            }

            if (!hasSignal)
            {
                Array.Clear(spectrumBuffer, 0, spectrumBuffer.Length);
                return;
            }

            for (int i = 0; i < spectrumBuffer.Length; i++)
            {
                spectrumBuffer[i] *= 0.92f;
            }
        }
    }

    private void ComputeSpectrum()
    {
        for (int i = 0; i < fftSize; i++)
        {
            fftReal[i] = sampleHistory[i] * fftWindow[i];
            fftImag[i] = 0f;
        }

        PerformFft(fftReal, fftImag);

        float gain = Mathf.Max(0.05f, spectrumGain) / fftSize;
        int usable = Mathf.Min(spectrumBuffer.Length, fftSize / 2);

        lock (bufferLock)
        {
            Array.Clear(spectrumBuffer, 0, spectrumBuffer.Length);
            for (int i = 0; i < usable; i++)
            {
                float magnitude = Mathf.Sqrt((fftReal[i] * fftReal[i]) + (fftImag[i] * fftImag[i])) * gain;
                spectrumBuffer[i] = Mathf.Clamp(magnitude, 0f, 4f);
            }
        }
    }

    private static void PerformFft(float[] real, float[] imag)
    {
        int length = real.Length;
        int bitReversed = 0;
        for (int i = 1; i < length; i++)
        {
            int bit = length >> 1;
            while ((bitReversed & bit) != 0)
            {
                bitReversed ^= bit;
                bit >>= 1;
            }

            bitReversed |= bit;
            if (i >= bitReversed)
            {
                continue;
            }

            (real[i], real[bitReversed]) = (real[bitReversed], real[i]);
            (imag[i], imag[bitReversed]) = (imag[bitReversed], imag[i]);
        }

        for (int step = 2; step <= length; step <<= 1)
        {
            int halfStep = step >> 1;
            float angle = -2f * Mathf.PI / step;
            float stepCos = Mathf.Cos(angle);
            float stepSin = Mathf.Sin(angle);

            for (int start = 0; start < length; start += step)
            {
                float rotCos = 1f;
                float rotSin = 0f;
                for (int offset = 0; offset < halfStep; offset++)
                {
                    int evenIndex = start + offset;
                    int oddIndex = evenIndex + halfStep;

                    float oddReal = (real[oddIndex] * rotCos) - (imag[oddIndex] * rotSin);
                    float oddImag = (real[oddIndex] * rotSin) + (imag[oddIndex] * rotCos);

                    real[oddIndex] = real[evenIndex] - oddReal;
                    imag[oddIndex] = imag[evenIndex] - oddImag;
                    real[evenIndex] += oddReal;
                    imag[evenIndex] += oddImag;

                    float nextCos = (rotCos * stepCos) - (rotSin * stepSin);
                    rotSin = (rotCos * stepSin) + (rotSin * stepCos);
                    rotCos = nextCos;
                }
            }
        }
    }

    private sealed class WasapiLoopbackSession : IDisposable
    {
        private IMMDeviceEnumerator enumerator;
        private IMMDevice device;
        private IAudioClient audioClient;
        private IAudioCaptureClient captureClient;
        private bool comInitialized;
        private bool started;
        private SampleEncoding sampleEncoding;
        private float[] floatBuffer;
        private short[] shortBuffer;
        private int[] intBuffer;
        private byte[] byteBuffer;

        public int Channels { get; private set; }
        public int SampleRate { get; private set; }
        public int BitsPerSample { get; private set; }
        public int MaxFramesPerPacket { get; private set; }
        public string FormatDescription { get; private set; }

        public bool Initialize(int bufferDuration, out string error)
        {
            error = null;

            int hr = CoInitializeEx(IntPtr.Zero, 0);
            if (hr == RpcChangedMode)
            {
                comInitialized = false;
            }
            else if (hr < 0)
            {
                error = BuildComError("CoInitializeEx", hr);
                return false;
            }
            else
            {
                comInitialized = true;
            }

            enumerator = (IMMDeviceEnumerator)new MMDeviceEnumeratorComObject();
            hr = enumerator.GetDefaultAudioEndpoint(EDataFlow.eRender, ERole.eMultimedia, out device);
            if (hr < 0)
            {
                error = BuildComError("GetDefaultAudioEndpoint", hr);
                return false;
            }

            Guid audioClientGuid = AudioClientGuid;
            object audioClientObject;
            hr = device.Activate(ref audioClientGuid, CLSCTX.ALL, IntPtr.Zero, out audioClientObject);
            if (hr < 0)
            {
                error = BuildComError("IMMDevice.Activate", hr);
                return false;
            }

            audioClient = (IAudioClient)audioClientObject;

            IntPtr mixFormatPtr = IntPtr.Zero;
            try
            {
                hr = audioClient.GetMixFormat(out mixFormatPtr);
                if (hr < 0)
                {
                    error = BuildComError("IAudioClient.GetMixFormat", hr);
                    return false;
                }

                if (!ReadWaveFormat(mixFormatPtr, out error))
                {
                    return false;
                }

                hr = audioClient.Initialize(
                    AudioClientShareMode.Shared,
                    AudioClientStreamFlags.Loopback,
                    bufferDuration,
                    0,
                    mixFormatPtr,
                    IntPtr.Zero);

                if (hr < 0)
                {
                    error = BuildComError("IAudioClient.Initialize", hr);
                    return false;
                }
            }
            finally
            {
                if (mixFormatPtr != IntPtr.Zero)
                {
                    Marshal.FreeCoTaskMem(mixFormatPtr);
                }
            }

            hr = audioClient.GetBufferSize(out uint bufferFrameCount);
            if (hr < 0)
            {
                error = BuildComError("IAudioClient.GetBufferSize", hr);
                return false;
            }

            MaxFramesPerPacket = Mathf.Max(1, (int)bufferFrameCount);

            Guid audioCaptureClientGuid = AudioCaptureClientGuid;
            object captureClientObject;
            hr = audioClient.GetService(ref audioCaptureClientGuid, out captureClientObject);
            if (hr < 0)
            {
                error = BuildComError("IAudioClient.GetService", hr);
                return false;
            }

            captureClient = (IAudioCaptureClient)captureClientObject;
            FormatDescription = $"默认回放 / {SampleRate} Hz / {Channels} ch / {sampleEncoding}";
            return true;
        }

        public bool Start(out string error)
        {
            error = null;
            int hr = audioClient.Start();
            if (hr < 0)
            {
                error = BuildComError("IAudioClient.Start", hr);
                return false;
            }

            started = true;
            return true;
        }

        public bool TryReadPacket(float[] monoBuffer, out int sampleCount)
        {
            sampleCount = 0;

            int hr = captureClient.GetNextPacketSize(out uint nextPacketSize);
            ThrowIfFailed("IAudioCaptureClient.GetNextPacketSize", hr);
            if (nextPacketSize == 0)
            {
                return false;
            }

            hr = captureClient.GetBuffer(out IntPtr dataPointer, out uint frameCount, out AudioClientBufferFlags flags, out long _, out long _);
            ThrowIfFailed("IAudioCaptureClient.GetBuffer", hr);

            try
            {
                int frames = (int)frameCount;
                if (monoBuffer == null || monoBuffer.Length < frames)
                {
                    throw new InvalidOperationException("环回缓冲区尺寸不足。");
                }

                if ((flags & AudioClientBufferFlags.Silent) != 0 || dataPointer == IntPtr.Zero)
                {
                    Array.Clear(monoBuffer, 0, frames);
                    sampleCount = frames;
                    return true;
                }

                DecodeToMono(dataPointer, frames, monoBuffer);
                sampleCount = frames;
                return true;
            }
            finally
            {
                captureClient.ReleaseBuffer(frameCount);
            }
        }

        public void Dispose()
        {
            if (audioClient != null && started)
            {
                audioClient.Stop();
                started = false;
            }

            ReleaseComObject(ref captureClient);
            ReleaseComObject(ref audioClient);
            ReleaseComObject(ref device);
            ReleaseComObject(ref enumerator);

            if (comInitialized)
            {
                CoUninitialize();
                comInitialized = false;
            }
        }

        private bool ReadWaveFormat(IntPtr formatPointer, out string error)
        {
            error = null;
            WaveFormatEx format = Marshal.PtrToStructure<WaveFormatEx>(formatPointer);

            Channels = Mathf.Max(1, format.nChannels);
            SampleRate = (int)format.nSamplesPerSec;
            BitsPerSample = format.wBitsPerSample;

            if (format.wFormatTag == WaveFormatIeeeFloat)
            {
                sampleEncoding = SampleEncoding.Float32;
                return true;
            }

            if (format.wFormatTag == WaveFormatPcm)
            {
                return TryAssignPcmEncoding(BitsPerSample, out error);
            }

            if (format.wFormatTag == WaveFormatExtensibleTag)
            {
                WaveFormatExtensible extensible = Marshal.PtrToStructure<WaveFormatExtensible>(formatPointer);
                BitsPerSample = extensible.Format.wBitsPerSample;

                if (extensible.SubFormat == KsdFormatSubtypeIeeeFloat)
                {
                    sampleEncoding = SampleEncoding.Float32;
                    return true;
                }

                if (extensible.SubFormat == KsdFormatSubtypePcm)
                {
                    return TryAssignPcmEncoding(BitsPerSample, out error);
                }
            }

            error = $"Windows 音频捕获失败: 不支持的回放格式 {format.wFormatTag}";
            return false;
        }

        private bool TryAssignPcmEncoding(int bitsPerSample, out string error)
        {
            error = null;
            switch (bitsPerSample)
            {
                case 8:
                    sampleEncoding = SampleEncoding.Pcm8;
                    return true;
                case 16:
                    sampleEncoding = SampleEncoding.Pcm16;
                    return true;
                case 24:
                    sampleEncoding = SampleEncoding.Pcm24;
                    return true;
                case 32:
                    sampleEncoding = SampleEncoding.Pcm32;
                    return true;
                default:
                    error = $"Windows 音频捕获失败: 不支持的 PCM 位深 {bitsPerSample}";
                    return false;
            }
        }

        private void DecodeToMono(IntPtr sourcePointer, int frames, float[] monoBuffer)
        {
            int totalSamples = frames * Channels;
            switch (sampleEncoding)
            {
                case SampleEncoding.Float32:
                    EnsureFloatBuffer(totalSamples);
                    Marshal.Copy(sourcePointer, floatBuffer, 0, totalSamples);
                    MixFloatToMono(floatBuffer, frames, monoBuffer);
                    break;

                case SampleEncoding.Pcm8:
                    EnsureByteBuffer(totalSamples);
                    Marshal.Copy(sourcePointer, byteBuffer, 0, totalSamples);
                    MixPcm8ToMono(byteBuffer, frames, monoBuffer);
                    break;

                case SampleEncoding.Pcm16:
                    EnsureShortBuffer(totalSamples);
                    Marshal.Copy(sourcePointer, shortBuffer, 0, totalSamples);
                    MixPcm16ToMono(shortBuffer, frames, monoBuffer);
                    break;

                case SampleEncoding.Pcm24:
                    EnsureByteBuffer(totalSamples * 3);
                    Marshal.Copy(sourcePointer, byteBuffer, 0, totalSamples * 3);
                    MixPcm24ToMono(byteBuffer, frames, monoBuffer);
                    break;

                case SampleEncoding.Pcm32:
                    EnsureIntBuffer(totalSamples);
                    Marshal.Copy(sourcePointer, intBuffer, 0, totalSamples);
                    MixPcm32ToMono(intBuffer, frames, monoBuffer);
                    break;

                default:
                    throw new NotSupportedException($"不支持的采样编码 {sampleEncoding}");
            }
        }

        private void EnsureFloatBuffer(int sampleCount)
        {
            if (floatBuffer == null || floatBuffer.Length < sampleCount)
            {
                floatBuffer = new float[sampleCount];
            }
        }

        private void EnsureShortBuffer(int sampleCount)
        {
            if (shortBuffer == null || shortBuffer.Length < sampleCount)
            {
                shortBuffer = new short[sampleCount];
            }
        }

        private void EnsureIntBuffer(int sampleCount)
        {
            if (intBuffer == null || intBuffer.Length < sampleCount)
            {
                intBuffer = new int[sampleCount];
            }
        }

        private void EnsureByteBuffer(int byteCount)
        {
            if (byteBuffer == null || byteBuffer.Length < byteCount)
            {
                byteBuffer = new byte[byteCount];
            }
        }

        private void MixFloatToMono(float[] input, int frames, float[] output)
        {
            for (int frame = 0; frame < frames; frame++)
            {
                float sum = 0f;
                int offset = frame * Channels;
                for (int channel = 0; channel < Channels; channel++)
                {
                    sum += input[offset + channel];
                }

                output[frame] = sum / Channels;
            }
        }

        private void MixPcm8ToMono(byte[] input, int frames, float[] output)
        {
            for (int frame = 0; frame < frames; frame++)
            {
                float sum = 0f;
                int offset = frame * Channels;
                for (int channel = 0; channel < Channels; channel++)
                {
                    sum += (input[offset + channel] - 128f) / 128f;
                }

                output[frame] = sum / Channels;
            }
        }

        private void MixPcm16ToMono(short[] input, int frames, float[] output)
        {
            for (int frame = 0; frame < frames; frame++)
            {
                float sum = 0f;
                int offset = frame * Channels;
                for (int channel = 0; channel < Channels; channel++)
                {
                    sum += input[offset + channel] / 32768f;
                }

                output[frame] = sum / Channels;
            }
        }

        private void MixPcm24ToMono(byte[] input, int frames, float[] output)
        {
            int bytesPerFrame = Channels * 3;
            for (int frame = 0; frame < frames; frame++)
            {
                float sum = 0f;
                int frameOffset = frame * bytesPerFrame;
                for (int channel = 0; channel < Channels; channel++)
                {
                    int sampleOffset = frameOffset + (channel * 3);
                    int sample = input[sampleOffset] | (input[sampleOffset + 1] << 8) | (input[sampleOffset + 2] << 16);
                    if ((sample & 0x00800000) != 0)
                    {
                        sample |= unchecked((int)0xFF000000);
                    }

                    sum += sample / 8388608f;
                }

                output[frame] = sum / Channels;
            }
        }

        private void MixPcm32ToMono(int[] input, int frames, float[] output)
        {
            for (int frame = 0; frame < frames; frame++)
            {
                double sum = 0d;
                int offset = frame * Channels;
                for (int channel = 0; channel < Channels; channel++)
                {
                    sum += input[offset + channel] / 2147483648d;
                }

                output[frame] = (float)(sum / Channels);
            }
        }

        private static string BuildComError(string operation, int hr)
        {
            return $"Windows 音频捕获失败: {operation} (0x{hr:X8})";
        }

        private static void ThrowIfFailed(string operation, int hr)
        {
            if (hr < 0)
            {
                throw new InvalidOperationException(BuildComError(operation, hr));
            }
        }

        private static void ReleaseComObject<T>(ref T comObject) where T : class
        {
            if (comObject == null)
            {
                return;
            }

#if UNITY_STANDALONE_WIN || UNITY_EDITOR_WIN
            try
            {
                Marshal.ReleaseComObject(comObject);
            }
            catch
            {
            }
#endif

            comObject = null;
        }
    }

    private enum SampleEncoding
    {
        Pcm8,
        Pcm16,
        Pcm24,
        Pcm32,
        Float32
    }

    [StructLayout(LayoutKind.Sequential, Pack = 2)]
    private struct WaveFormatEx
    {
        public ushort wFormatTag;
        public ushort nChannels;
        public uint nSamplesPerSec;
        public uint nAvgBytesPerSec;
        public ushort nBlockAlign;
        public ushort wBitsPerSample;
        public ushort cbSize;
    }

    [StructLayout(LayoutKind.Sequential, Pack = 2)]
    private struct WaveFormatExtensible
    {
        public WaveFormatEx Format;
        public ushort wValidBitsPerSample;
        public uint dwChannelMask;
        public Guid SubFormat;
    }

    private enum EDataFlow
    {
        eRender,
        eCapture,
        eAll,
        EDataFlowEnumCount
    }

    private enum ERole
    {
        eConsole,
        eMultimedia,
        eCommunications,
        ERoleEnumCount
    }

    [Flags]
    private enum AudioClientBufferFlags
    {
        None = 0,
        DataDiscontinuity = 0x1,
        Silent = 0x2,
        TimestampError = 0x4
    }

    [Flags]
    private enum AudioClientStreamFlags
    {
        None = 0,
        Loopback = 0x00020000
    }

    private enum AudioClientShareMode
    {
        Shared,
        Exclusive
    }

    private enum CLSCTX
    {
        ALL = 23
    }

    [ComImport]
    [Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")]
    private class MMDeviceEnumeratorComObject
    {
    }

    [ComImport]
    [Guid("A95664D2-9614-4F35-A746-DE8DB63617E6")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IMMDeviceEnumerator
    {
        int EnumAudioEndpoints(EDataFlow dataFlow, int dwStateMask, out object ppDevices);
        int GetDefaultAudioEndpoint(EDataFlow dataFlow, ERole role, out IMMDevice ppEndpoint);
        int GetDevice([MarshalAs(UnmanagedType.LPWStr)] string pwstrId, out IMMDevice ppDevice);
        int RegisterEndpointNotificationCallback(IntPtr pClient);
        int UnregisterEndpointNotificationCallback(IntPtr pClient);
    }

    [ComImport]
    [Guid("D666063F-1587-4E43-81F1-B948E807363F")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IMMDevice
    {
        int Activate(ref Guid iid, CLSCTX dwClsCtx, IntPtr pActivationParams, [MarshalAs(UnmanagedType.IUnknown)] out object ppInterface);
        int OpenPropertyStore(int stgmAccess, out IntPtr ppProperties);
        int GetId([MarshalAs(UnmanagedType.LPWStr)] out string ppstrId);
        int GetState(out int pdwState);
    }

    [ComImport]
    [Guid("1CB9AD4C-DBFA-4c32-B178-C2F568A703B2")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IAudioClient
    {
        int Initialize(AudioClientShareMode shareMode, AudioClientStreamFlags streamFlags, long hnsBufferDuration, long hnsPeriodicity, IntPtr pFormat, IntPtr audioSessionGuid);
        int GetBufferSize(out uint pNumBufferFrames);
        int GetStreamLatency(out long phnsLatency);
        int GetCurrentPadding(out uint pNumPaddingFrames);
        int IsFormatSupported(AudioClientShareMode shareMode, IntPtr pFormat, out IntPtr closestMatch);
        int GetMixFormat(out IntPtr deviceFormatPointer);
        int GetDevicePeriod(out long phnsDefaultDevicePeriod, out long phnsMinimumDevicePeriod);
        int Start();
        int Stop();
        int Reset();
        int SetEventHandle(IntPtr eventHandle);
        int GetService(ref Guid riid, [MarshalAs(UnmanagedType.IUnknown)] out object ppv);
    }

    [ComImport]
    [Guid("C8ADBD64-E71E-48a0-A4DE-185C395CD317")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IAudioCaptureClient
    {
        int GetBuffer(out IntPtr ppData, out uint pNumFramesToRead, out AudioClientBufferFlags pdwFlags, out long pu64DevicePosition, out long pu64QPCPosition);
        int ReleaseBuffer(uint numFramesRead);
        int GetNextPacketSize(out uint pNumFramesInNextPacket);
    }

    [DllImport("ole32.dll")]
    private static extern int CoInitializeEx(IntPtr reserved, uint coInit);

    [DllImport("ole32.dll")]
    private static extern void CoUninitialize();
}
