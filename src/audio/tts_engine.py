import os
import re
import shutil
import tempfile
import time
import wave
from contextlib import contextmanager
from datetime import datetime

import pyttsx3

from config import OUTPUTS_DIR, NEWSPAPER_NAME, NEWSPAPER_TAGLINE

# Audio length modes (shorter script = much faster recording)
MODE_HEADLINES = "Headlines only"
MODE_SUMMARIES = "Summaries"
MODE_FULL = "Summaries + counter-perspectives"
AUDIO_MODES = [MODE_HEADLINES, MODE_SUMMARIES, MODE_FULL]

# Characters that read badly (or not at all) when spoken
SPEECH_REPLACEMENTS = {
    "\u2010": "-",
    "\u2011": "-",
    "\u2012": "-",
    "\u2212": "-",
    "\u00a0": " ",
    "\u202f": " ",
    "\u2009": " ",
    "\u200b": "",
    "\u2060": "",
    "\ufeff": "",
    "&": " and ",
    "%": " percent",
}

SILENCE_BETWEEN_SEGMENTS_SEC = 0.5


@contextmanager
def _com_initialized():
    """
    Windows speech (SAPI5) uses COM. Any non-main thread (Streamlit's worker thread,
    or our background recording thread) must initialize COM itself.
    """
    comtypes = None
    initialized = False
    try:
        import comtypes as _comtypes
        comtypes = _comtypes
        comtypes.CoInitialize()
        initialized = True
    except Exception:
        pass
    try:
        yield
    finally:
        if initialized and comtypes is not None:
            try:
                comtypes.CoUninitialize()
            except Exception:
                pass


class PaperNarrator:
    """Turns a list of synthesized articles into a spoken WAV briefing, fully offline."""

    def __init__(self, voice_id: str = None, rate: int = 175, volume: float = 1.0):
        self.voice_id = voice_id   # None = system default voice
        self.rate = rate           # words per minute (~120 slow, 175 normal, 240 fast)
        self.volume = volume       # 0.0 to 1.0

    # ---------- Voices ----------
    @staticmethod
    def list_voices() -> list:
        """Returns [(voice_id, voice_name), ...] for voices installed on this computer."""
        try:
            with _com_initialized():
                engine = pyttsx3.init()
                try:
                    return [(v.id, v.name) for v in engine.getProperty("voices")]
                finally:
                    try:
                        engine.stop()
                    except Exception:
                        pass
        except Exception as e:
            print(f"VOICE LIST ERROR: {type(e).__name__}: {e}")
            return []

    # ---------- Script building ----------
    def _clean(self, text) -> str:
        """Strips markup, links and odd characters so the voice doesn't stumble."""
        if not text:
            return ""
        text = str(text)
        for old, new in SPEECH_REPLACEMENTS.items():
            text = text.replace(old, new)
        text = re.sub(r"https?://\S+", "", text)       # URLs
        text = re.sub(r"[*#_`>|~]", "", text)          # markdown symbols
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def build_segments(self, articles: list, mode: str = MODE_SUMMARIES) -> list:
        """
        Builds the script as a short list of segments.
        Fewer segments = fewer synthesis calls = faster recording.
        """
        date_str = datetime.now().strftime("%A, %B %d, %Y")
        total = len(articles)

        intro = (
            f"Good morning. This is {self._clean(NEWSPAPER_NAME)}. "
            f"{self._clean(NEWSPAPER_TAGLINE)}. Edition for {date_str}. "
            f"Today's paper has {total} {'story' if total == 1 else 'stories'}."
        )
        outro = "That concludes today's edition. Thank you for listening."

        # Headlines only: one single segment, very fast
        if mode == MODE_HEADLINES:
            lines = [intro]
            for i, article in enumerate(articles, start=1):
                category = self._clean(article.get("category", "General"))
                headline = self._clean(article.get("headline", "Untitled"))
                lines.append(f"Story {i}. {category}. {headline}.")
            lines.append(outro)
            return [" ".join(lines)]

        # Summaries (optionally with counter-perspectives): one segment per story
        segments = [intro]
        for i, article in enumerate(articles, start=1):
            category = self._clean(article.get("category", "General"))
            headline = self._clean(article.get("headline", "Untitled"))
            summary = self._clean(article.get("summary", ""))
            dialectic = self._clean(article.get("dialectic_perspective", ""))

            block = f"Story {i} of {total}. {category}. {headline}. {summary}"
            if mode == MODE_FULL and dialectic and dialectic.lower() != "n/a":
                block += f" The counter perspective. {dialectic}"
            segments.append(block)

        segments.append(outro)
        return [s for s in segments if s.strip()]

    # ---------- Audio generation ----------
    @staticmethod
    def _merge_wavs(part_paths: list, output_path: str):
        """Joins WAV parts into one file, with a short pause between segments."""
        with wave.open(part_paths[0], "rb") as first:
            params = first.getparams()

        silence = b"\x00" * int(
            params.framerate * params.sampwidth * params.nchannels * SILENCE_BETWEEN_SEGMENTS_SEC
        )

        with wave.open(output_path, "wb") as out:
            out.setparams(params)
            for i, path in enumerate(part_paths):
                with wave.open(path, "rb") as part:
                    out.writeframes(part.readframes(part.getnframes()))
                if i < len(part_paths) - 1:
                    out.writeframes(silence)

    def generate_audio(
        self,
        articles: list,
        mode: str = MODE_SUMMARIES,
        filename: str = None,
        progress_callback=None,
    ) -> str:
        """
        Synthesizes the briefing to a WAV file and returns its path.
        progress_callback(done, total) is called after each segment.
        Works offline using the voices installed in Windows.
        """
        if not articles:
            raise ValueError("There are no articles to read.")

        if not filename:
            filename = f"edition_{datetime.now().strftime('%Y-%m-%d')}.wav"

        os.makedirs(OUTPUTS_DIR, exist_ok=True)
        filepath = os.path.join(OUTPUTS_DIR, filename)

        segments = self.build_segments(articles, mode)
        total = len(segments)

        tmp_dir = tempfile.mkdtemp(prefix="chroniclex_tts_")
        part_paths = []
        started = time.perf_counter()

        try:
            with _com_initialized():
                engine = pyttsx3.init()
                try:
                    if self.voice_id:
                        engine.setProperty("voice", self.voice_id)
                    engine.setProperty("rate", self.rate)
                    engine.setProperty("volume", self.volume)

                    for done, segment in enumerate(segments, start=1):
                        seg_start = time.perf_counter()
                        part = os.path.join(tmp_dir, f"part_{done:03d}.wav")
                        engine.save_to_file(segment, part)
                        engine.runAndWait()

                        if not os.path.exists(part) or os.path.getsize(part) < 100:
                            raise RuntimeError(f"Voice produced no audio for segment {done}.")

                        part_paths.append(part)
                        words = len(segment.split())
                        print(
                            f"[audio] segment {done}/{total}: {words} words "
                            f"in {time.perf_counter() - seg_start:.1f}s"
                        )
                        if progress_callback:
                            progress_callback(done, total)
                finally:
                    try:
                        engine.stop()
                    except Exception:
                        pass

            self._merge_wavs(part_paths, filepath)
            print(f"[audio] finished in {time.perf_counter() - started:.1f}s -> {filepath}")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        return filepath