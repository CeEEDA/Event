"""Sprach-Optimierung fuer Durchsagen (Aufnahme per Mikrofon oder Upload):
1. Bandpass fuer Sprache, 2. Spektrales Gating gegen Nebengeraeusche (Referenz: audio_profiles/*.wav,
z.B. Hallen-/Lobby-Atmo) + Rest-Rauschen, 3. afftdn, Kompressor, Spitzenpegel 0 dBFS -> MP3.
Wird fuer Messe-Testdurchsagen genutzt und ist fuer Auftrags-Durchsagen vorbereitet (mbox_audio.process_audio(enhance=True))."""
import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

import ffmpeg_setup

logger = logging.getLogger(__name__)
PROFILE_DIR = Path(__file__).resolve().parent / "audio_profiles"
DEFAULT_PROFILE = PROFILE_DIR / "ambience_lobby.wav"
SR = 48000


def _ff(args: list, timeout: int = 600):
    kwargs = {"creationflags": 0x08000000} if sys.platform == "win32" else {}
    r = subprocess.run([ffmpeg_setup.find_ffmpeg() or "ffmpeg", "-hide_banner", "-y", *args], capture_output=True, text=True, timeout=timeout, **kwargs)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or "ffmpeg Fehler")[-300:])
    return r


def _peak_db(path: Path) -> float:
    r = subprocess.run([ffmpeg_setup.find_ffmpeg() or "ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
                       capture_output=True, text=True, timeout=300)
    m = re.search(r"max_volume: (-?[\d.]+) dB", r.stderr)
    return float(m.group(1)) if m else 0.0


def _load_wav(path: Path):
    import soundfile as sf
    y, sr = sf.read(str(path), dtype="float32", always_2d=False)
    if y.ndim > 1:
        y = y.mean(axis=1)
    return y, sr


def _speech_bounds(y, sr: int):
    """Erster/letzter Sprachanteil (Sample-Index) ueber RMS-Rahmen von 50 ms.
    Schwelle = max(Rauschteppich + 12 dB, Sprachpegel (90. Perzentil) - 12 dB) -> leises Vorgeraeusch zaehlt nicht als Sprache."""
    import numpy as np
    frame = int(0.05 * sr)
    n = len(y) // frame
    if n < 4:
        return 0, len(y), 0.0
    rms = np.sqrt(np.mean(np.square(y[:n * frame].reshape(n, frame)), axis=1)) + 1e-9
    floor = float(np.percentile(rms, 15))
    speech = float(np.percentile(rms, 90))
    thresh = max(floor * 4.0, speech * 0.25, 0.004)
    # Spektrale Flachheit 150-4000 Hz: Rauschen/Atmo ~0.15-0.3, Sprache < 0.1 -> lautes Vorgeraeusch (z.B. AGC) ist keine Sprache
    spec = np.abs(np.fft.rfft(y[:n * frame].reshape(n, frame) * np.hanning(frame), axis=1)) ** 2 + 1e-12
    band = spec[:, (np.fft.rfftfreq(frame, 1 / sr) > 150) & (np.fft.rfftfreq(frame, 1 / sr) < 4000)]
    flat = np.exp(np.mean(np.log(band), axis=1)) / np.mean(band, axis=1)
    above = (rms > thresh) & (flat < 0.12)
    hits = [i for i in range(n - 2) if above[i] and above[i + 1] and above[i + 2]]
    if not hits:
        return 0, len(y), floor
    return hits[0] * frame, min(len(y), (hits[-1] + 3) * frame), floor


def _spectral_gate(src_wav: Path, dst_wav: Path, profile: Optional[Path]) -> dict:
    import numpy as np
    import noisereduce as nr
    import soundfile as sf
    y, sr = _load_wav(src_wav)
    info = {"profile": None, "passes": 0}
    onset, offset, _floor = _speech_bounds(y, sr)
    # Eigenes Raumgeraeusch der Aufnahme (Vorlauf bis zum ersten Wort, max. 1 s; sonst erste 0,4 s) als Referenz
    lead = y[:min(onset, sr)] if onset >= int(0.25 * sr) else y[:int(0.4 * sr)]
    noise_parts = []
    if profile and profile.exists():
        prof_wav = dst_wav.with_suffix(".profile.wav")
        _ff(["-i", str(profile), "-ac", "1", "-ar", str(sr), "-c:a", "pcm_s16le", str(prof_wav)])
        noise, _ = _load_wav(prof_wav)
        prof_wav.unlink(missing_ok=True)
        # Referenz-Atmo leiser/lauter als in der Aufnahme -> auf Aufnahme-Rauschteppich skalieren
        y_rms = float(np.sqrt(np.mean(np.square(y)))) or 1e-6
        n_rms = float(np.sqrt(np.mean(np.square(noise)))) or 1e-6
        noise_parts.append(noise * min(1.0, (y_rms * 0.35) / n_rms))
        info["profile"] = profile.name
    if len(lead) > int(0.2 * sr):
        noise_parts.append(np.tile(lead, max(1, int(3 * sr / len(lead)))))
        info["lead_noise_sec"] = round(len(lead) / sr, 2)
    if noise_parts:
        # sanft: weiche Masken (lange Zeitglaettung), nicht alles wegnehmen -> keine abgehackten Wortanfaenge/-enden
        y = nr.reduce_noise(y=y, sr=sr, y_noise=np.concatenate(noise_parts), stationary=True, prop_decrease=0.75, n_fft=2048,
                            freq_mask_smooth_hz=600, time_mask_smooth_ms=200, n_std_thresh_stationary=1.2)
        info["passes"] += 1
    # Rest-Rauschen / Hall adaptiv - mit 2 s "Aufwaermen" (eigener Vorlauf vorangestellt), damit der Anfang nicht ungefiltert bleibt
    warm = np.tile(lead, max(1, int(2 * sr / max(1, len(lead)))))[: 2 * sr] if len(lead) > int(0.1 * sr) else np.zeros(0, dtype=y.dtype)
    yy = nr.reduce_noise(y=np.concatenate([warm, y]), sr=sr, stationary=False, prop_decrease=0.45, n_fft=2048, time_constant_s=2.0,
                         freq_mask_smooth_hz=800, time_mask_smooth_ms=250, thresh_n_mult_nonstationary=2.5)
    y = yy[len(warm):]
    info["passes"] += 1
    # Bis zum ersten Wort alles abschneiden (0,15 s Vorlauf + 60 ms Einblenden), nach dem letzten Wort 0,4 s behalten
    onset2, offset2, _ = _speech_bounds(y, sr)
    keep_in, keep_out, fade = int(0.15 * sr), int(0.4 * sr), int(0.06 * sr)
    start = max(0, onset2 - keep_in)
    end = min(len(y), offset2 + keep_out)
    if end - start > sr // 2:
        if start > 0:
            info["lead_cut_sec"] = round(start / sr, 2)
        if end < len(y):
            info["tail_cut_sec"] = round((len(y) - end) / sr, 2)
        y = y[start:end].copy()
        y[:fade] *= np.linspace(0.0, 1.0, fade, dtype=y.dtype)
        y[-fade:] *= np.linspace(1.0, 0.0, fade, dtype=y.dtype)
    y = np.clip(y, -1.0, 1.0)
    sf.write(str(dst_wav), y, sr, subtype="PCM_16")
    return info


def enhance_speech(src: Path, dst: Path, profile: Optional[Path] = DEFAULT_PROFILE) -> dict:
    """src (beliebiges Format, auch webm/opus aus dem Browser) -> dst (MP3 192k, Spitze 0 dBFS)."""
    work = dst.with_suffix(".stage1.wav")
    gated = dst.with_suffix(".stage2.wav")
    try:
        _ff(["-i", str(src), "-vn", "-ac", "1", "-ar", str(SR), "-af", "highpass=f=90,lowpass=f=9000", "-c:a", "pcm_s16le", str(work)])
        before_peak = _peak_db(work)
        try:
            gate = _spectral_gate(work, gated, profile)
            stage = gated
        except Exception as e:
            logger.warning(f"Spektrales Gating uebersprungen: {e}")
            gate = {"profile": None, "passes": 0, "error": str(e)[:120]}
            stage = work
        # kein Noise-Gate mehr (schnitt leise Silbenanfaenge/-enden ab); leichtes afftdn, Kompressor mit langsamem Release
        filters = ["afftdn=nr=6:nf=-48:tn=1", "acompressor=threshold=-22dB:ratio=2.5:attack=15:release=400:makeup=2dB:knee=6"]
        tmp = dst.with_suffix(".stage3.wav")
        _ff(["-i", str(stage), "-af", ",".join(filters), "-c:a", "pcm_s16le", str(tmp)])
        gain = -_peak_db(tmp)
        _ff(["-i", str(tmp), "-af", f"volume={gain:.2f}dB,alimiter=limit=0.999", "-codec:a", "libmp3lame", "-b:a", "192k", str(dst)])
        tmp.unlink(missing_ok=True)
        after_peak = _peak_db(dst)
        return {"enhanced": True, "before": {"max_volume_db": before_peak}, "after": {"max_volume_db": after_peak},
                "noise_reduction": True, "gain_db": round(gain, 2), "spectral_gate": gate, "filters": filters}
    finally:
        for p in (work, gated):
            p.unlink(missing_ok=True)
