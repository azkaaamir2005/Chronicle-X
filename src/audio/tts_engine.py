import os
import re
import shutil
import tempfile
import time
import wave
import json
from contextlib import contextmanager
from datetime import datetime

import pyttsx3

from config import OUTPUTS_DIR, NEWSPAPER_NAME, NEWSPAPER_TAGLINE

# Audio length mode optimized for instant demo rendering
MODE_HEADLINES = "Headlines only"
AUDIO_MODES = [MODE_HEADLINES]

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

SILENCE_BETWEEN_SEGMENTS_SEC = 0.3


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
    """Turns a list of synthesized articles into a rapid headline audio briefing with word-timing metadata, fully offline."""

    def __init__(self, voice_id: str = None, rate: int = 185, volume: float = 1.0):
        self.voice_id = voice_id    # None = system default voice
        self.rate = rate            # words per minute (slightly faster for snappy demo)
        self.volume = volume        # 0.0 to 1.0

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
        text = re.sub(r"https?://\S+", "", text)      # URLs
        text = re.sub(r"[*#_`>|~]", "", text)          # markdown symbols
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def build_segments(self, articles: list, mode: str = MODE_HEADLINES) -> list:
        """
        Builds a rapid headline-only briefing script for instant demo readiness.
        """
        date_str = datetime.now().strftime("%A, %B %d, %Y")
        total = len(articles)

        intro = (
            f"Good morning. This is {self._clean(NEWSPAPER_NAME)}. "
            f"{self._clean(NEWSPAPER_TAGLINE)}. Edition for {date_str}. "
            f"Today's paper features {total} {'story' if total == 1 else 'stories'}."
        )
        outro = "That concludes today's headline brief. Thank you for listening."

        lines = [intro]
        for i, article in enumerate(articles, start=1):
            category = self._clean(article.get("category", "General"))
            headline = self._clean(article.get("headline", "Untitled"))
            lines.append(f"Story {i}. {category}. {headline}.")
        lines.append(outro)

        return [" ".join(lines)]

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
        mode: str = MODE_HEADLINES,
        filename: str = None,
        progress_callback=None,
    ) -> tuple[str, str]:
        """
        Synthesizes briefing to WAV, generates a word-timing JSON metadata file for live highlighting, 
        and returns (wav_filepath, json_filepath).
        """
        if not articles:
            raise ValueError("There are no articles to read.")

        if not filename:
            base_name = f"edition_{datetime.now().strftime('%Y-%m-%d')}"
        else:
            base_name = os.path.splitext(filename)[0]

        os.makedirs(OUTPUTS_DIR, exist_ok=True)
        filepath = os.path.join(OUTPUTS_DIR, f"{base_name}.wav")
        json_path = os.path.join(OUTPUTS_DIR, f"{base_name}_timing.json")

        segments = self.build_segments(articles, mode)
        total = len(segments)

        tmp_dir = tempfile.mkdtemp(prefix="chroniclex_tts_")
        part_paths = []
        word_timings = []
        current_time = 0.0

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

                        # Calculate exact audio duration of this segment using wave module
                        with wave.open(part, "rb") as w_part:
                            frames = w_part.getnframes()
                            rate_Hz = w_part.getframerate()
                            actual_seg_duration = frames / float(rate_Hz)

                        part_paths.append(part)

                        # Map words to timestamps for highlighting UI
                        words = segment.split()
                        if words:
                            time_per_word_actual = actual_seg_duration / len(words)
                            for w in words:
                                start_t = current_time
                                end_t = current_time + time_per_word_actual
                                word_timings.append({"word": w, "start": round(start_t, 2), "end": round(end_t, 2)})
                                current_time = end_t

                        current_time += SILENCE_BETWEEN_SEGMENTS_SEC

                        if progress_callback:
                            progress_callback(done, total)
                finally:
                    try:
                        engine.stop()
                    except Exception:
                        pass

            self._merge_wavs(part_paths, filepath)
            
            # Save timing map to JSON
            with open(json_path, "w", encoding="utf-8") as jf:
                json.dump(word_timings, jf, indent=2)

            print(f"[audio] finished in {time.perf_counter() - started:.1f}s -> {filepath}")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        return filepath, json_path