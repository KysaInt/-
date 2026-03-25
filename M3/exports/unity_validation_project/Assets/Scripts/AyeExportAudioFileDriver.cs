using UnityEngine;

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
