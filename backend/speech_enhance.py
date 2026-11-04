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


def _spectral_gate(src_wav: Path, dst_wav: Path, profile: Optional[Path]) -> dict:
    import numpy as np
    import noisereduce as nr
    import soundfile as sf
    y, sr = _load_wav(src_wav)
    info = {"profile": None, "passes": 0}
    if profile and profile.exists():
        prof_wav = dst_wav.with_suffix(".profile.wav")
        _ff(["-i", str(profile), "-ac", "1", "-ar", str(sr), "-c:a", "pcm_s16le", str(prof_wav)])
        noise, _ = _load_wav(prof_wav)
        prof_wav.unlink(missing_ok=True)
        # Referenz-Atmo leiser/lauter als in der Aufnahme -> auf Aufnahme-Rauschteppich skalieren
        y_rms = float(np.sqrt(np.mean(np.square(y)))) or 1e-6
        n_rms = float(np.sqrt(np.mean(np.square(noise)))) or 1e-6
        noise = noise * min(1.0, (y_rms * 0.35) / n_rms)
        y = nr.reduce_noise(y=y, sr=sr, y_noise=noise, stationary=True, prop_decrease=0.9, n_fft=2048, freq_mask_smooth_hz=400, time_mask_smooth_ms=60)
        info["profile"] = profile.name
        info["passes"] += 1
    # Rest-Rauschen / Hall adaptiv
    y = nr.reduce_noise(y=y, sr=sr, stationary=False, prop_decrease=0.7, n_fft=2048, time_constant_s=1.5, freq_mask_smooth_hz=500, time_mask_smooth_ms=50)
    info["passes"] += 1
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
        filters = ["afftdn=nr=10:nf=-40:tn=1", "agate=threshold=0.02:ratio=2:attack=5:release=150",
                   "acompressor=threshold=-20dB:ratio=3:attack=8:release=180:makeup=2dB"]
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
