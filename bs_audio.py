"""Sounds: chimes, the downloaded recordings, and recording your own voice."""
import array
import math
import os
import wave

import pygame

from bs_paths import APP_DIR, DATA_DIR

SOUNDS_DIR = os.path.join(APP_DIR, "sounds")        # what things sound like: <Word>.wav
WORDS_DIR = os.path.join(SOUNDS_DIR, "words")       # downloaded voices saying words: <Word>.wav
OUR_VOICE_DIR = os.path.join(DATA_DIR, "sounds", "our_voice")  # your own recordings of the names: <id>.wav
OUR_SFX_DIR = os.path.join(DATA_DIR, "sounds", "our_sfx")      # your own recordings of what things sound like
RATE = 44100
MAX_RECORD_SECONDS = 4.0

PENTATONIC = [0, 2, 4, 7, 9, 12, 14, 16, 19, 21, 24]  # always sounds nice together


def make_tone(freq, dur=0.7, vol=0.35):
    rate, _size, channels = pygame.mixer.get_init()
    buf = array.array("h")
    for i in range(int(rate * dur)):
        t = i / rate
        env = min(1.0, t / 0.01) * math.exp(-5 * t)
        v = math.sin(2 * math.pi * freq * t) + 0.3 * math.sin(4 * math.pi * freq * t)
        buf.extend([int(32767 * vol * env * v / 1.3)] * channels)
    return pygame.mixer.Sound(buffer=buf.tobytes())


_chime_notes = []  # raw audio of each counting note, made once and reused


def counting_chimes(n, gap=0.42):
    """n rising chimes - the sound of a number: 3 goes ding, ding, ding."""
    rate, _size, channels = pygame.mixer.get_init()
    if not _chime_notes:
        for i in range(len(PENTATONIC)):
            freq = 523.25 * 2 ** (PENTATONIC[i] / 12)
            length = int(rate * gap)
            note = array.array("h")
            for j in range(length):
                t = j / rate
                v = (math.sin(2 * math.pi * freq * t) + 0.3 * math.sin(4 * math.pi * freq * t)) / 1.3
                fade = min(1.0, t / 0.01, (length - j) / (rate * 0.03))  # soft start and end, no clicks
                note.extend([int(32767 * 0.3 * fade * math.exp(-6 * t) * v)] * channels)
            _chime_notes.append(note.tobytes())
    notes = [_chime_notes[i % len(_chime_notes)] for i in range(n)]
    return pygame.mixer.Sound(buffer=b"".join(notes))


def our_voice_path(name):
    return os.path.join(OUR_VOICE_DIR, f"{name}.wav")


def load_voices(names, prefer_ours=True):
    """A voice saying each word: your own recording if there is one (and wanted), else the downloaded one.

    Objects you added have no downloaded voice, so they always use yours.
    """
    clips = {}
    for name in names:
        ours, builtin = our_voice_path(name), os.path.join(WORDS_DIR, f"{name}.wav")
        paths = [ours, builtin] if prefer_ours else [builtin, ours]
        path = next((p for p in paths if os.path.exists(p)), None)
        if path:
            clips[name] = pygame.mixer.Sound(path)
    return clips


def load_sound_effects(names):
    """What each thing sounds like (a dog barking...): your recording if there is one, else the downloaded one."""
    clips = {}
    for name in names:
        paths = [os.path.join(OUR_SFX_DIR, f"{name}.wav"), os.path.join(SOUNDS_DIR, f"{name}.wav")]
        path = next((p for p in paths if os.path.exists(p)), None)
        if path:
            clips[name] = pygame.mixer.Sound(path)
    return clips


def count_our_recordings(names):
    return sum(os.path.exists(our_voice_path(n)) for n in names)


# ------------------------------------------------------------------ recording
class MicRecorder:
    """Records from the default microphone (SDL capture device)."""

    def __init__(self):
        self.device = None
        self.chunks = []
        self.level = 0.0  # 0..1, loudness of the latest chunk (for a meter)

    @staticmethod
    def available():
        from pygame._sdl2 import audio as sdl_audio
        names = sdl_audio.get_audio_device_names(True)
        return names[0] if names else None

    def start(self):
        from pygame._sdl2 import audio as sdl_audio
        self.chunks = []
        self.level = 0.0
        self.device = sdl_audio.AudioDevice(
            devicename=self.available(), iscapture=True, frequency=RATE, audioformat=sdl_audio.AUDIO_S16,
            numchannels=1, chunksize=1024, allowed_changes=0, callback=self._callback)
        self.device.pause(0)

    def _callback(self, _device, memory):
        # runs on the audio thread: must never raise
        try:
            data = bytes(memory)
            self.chunks.append(data)
            samples = array.array("h", data[:len(data) // 2 * 2])
            if samples:
                self.level = max(max(samples), -min(samples)) / 32768
        except Exception:
            pass

    def seconds(self):
        return sum(len(c) for c in self.chunks) / 2 / RATE

    def stop(self):
        device, self.device = self.device, None
        if device:
            try:
                device.pause(1)
            finally:
                device.close()
        data = b"".join(self.chunks)
        return array.array("h", data[:len(data) // 2 * 2])


def clean_recording(samples):
    """Trim silence, even out the volume and fade the edges. None if nothing was heard."""
    if not samples:
        return None
    mean = sum(samples) / len(samples)  # remove any DC offset from the mic
    x = [v - mean for v in samples]
    peak = max(abs(v) for v in x)
    if peak < 800:
        return None
    loud = [i for i, v in enumerate(x) if abs(v) > peak * 0.06]
    x = x[max(0, loud[0] - int(0.08 * RATE)):loud[-1] + int(0.15 * RATE)]
    active = [v for v in x if abs(v) > peak * 0.02] or x
    rms = math.sqrt(sum(v * v for v in active) / len(active)) or 1
    k = min(0.16 * 32767 / rms, 0.9 * 32767 / peak)
    fade_in, fade_out = int(0.01 * RATE), int(0.04 * RATE)
    return array.array("h", (int(max(-32767, min(32767, v * k * min(1.0, i / fade_in, (len(x) - i) / fade_out))))
                             for i, v in enumerate(x)))


def save_wav(path, samples):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(samples.tobytes())
