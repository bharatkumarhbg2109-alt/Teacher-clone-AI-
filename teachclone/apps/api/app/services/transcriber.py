"""faster-whisper transcription -> RAG-friendly timestamped chunks.

Streams whisper segments, so it handles media of any length. The model is
loaded once per worker process.
"""
import threading
from dataclasses import dataclass

from faster_whisper import WhisperModel

from app.config import settings


@dataclass
class TranscriptChunkData:
    text: str
    start_time: float
    end_time: float
    speaker_label: str | None
    chunk_index: int
    token_count: int


_model: WhisperModel | None = None
_lock = threading.Lock()


def get_model() -> WhisperModel:
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                _model = WhisperModel(
                    settings.WHISPER_MODEL,
                    device=settings.WHISPER_DEVICE,
                    compute_type=settings.WHISPER_COMPUTE_TYPE,
                )
    return _model


class Transcriber:
    MAX_TOKENS = 400
    OVERLAP_WORDS = 12
    WORDS_PER_TOKEN = 0.75

    def transcribe(self, audio_path: str) -> list[TranscriptChunkData]:
        model = get_model()
        segments, _ = model.transcribe(
            audio_path,
            beam_size=5,
            language=None,
            word_timestamps=False,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
        )
        return self._segments_to_chunks(segments)

    def _segments_to_chunks(self, segments) -> list[TranscriptChunkData]:
        chunks: list[TranscriptChunkData] = []
        current_words: list[str] = []
        current_start = 0.0
        current_end = 0.0
        idx = 0

        for seg in segments:
            words = seg.text.strip().split()
            if not words:
                continue
            if not current_words:
                current_start = seg.start

            est_tokens = len(current_words) / self.WORDS_PER_TOKEN
            seg_tokens = len(words) / self.WORDS_PER_TOKEN

            if est_tokens + seg_tokens > self.MAX_TOKENS and current_words:
                chunks.append(
                    TranscriptChunkData(
                        text=" ".join(current_words),
                        start_time=current_start,
                        end_time=seg.start,
                        speaker_label=None,
                        chunk_index=idx,
                        token_count=int(est_tokens),
                    )
                )
                idx += 1
                overlap = current_words[-self.OVERLAP_WORDS :]
                current_words = overlap + words
                current_start = seg.start
            else:
                current_words.extend(words)
            current_end = seg.end

        if current_words:
            chunks.append(
                TranscriptChunkData(
                    text=" ".join(current_words),
                    start_time=current_start,
                    end_time=current_end,
                    speaker_label=None,
                    chunk_index=idx,
                    token_count=int(len(current_words) / self.WORDS_PER_TOKEN),
                )
            )
        return chunks


transcriber = Transcriber()
