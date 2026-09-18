from dataclasses import dataclass
from typing import Any

from titan_backend.media.transcriber import TranscriptionSegment


@dataclass
class MediaChunk:
    chunk_index: int
    text: str
    time_start_sec: float
    time_end_sec: float
    speaker: str
    timecode_label: str
    metadata: dict[str, Any]


def format_seconds_to_timecode(seconds: float) -> str:
    """Format 124.5 -> '02:04' or 3661.0 -> '01:01:01'."""
    total_sec = int(seconds)
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    secs = total_sec % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


class MediaSemanticChunker:
    """
    Chunks audio/video transcription segments into semantic timecode blocks (~30-60 seconds)
    suitable for vector embeddings and timestamped playback citations.
    """

    @classmethod
    def chunk_segments(
        cls,
        segments: list[TranscriptionSegment],
        target_chunk_duration_sec: float = 45.0,
    ) -> list[MediaChunk]:
        if not segments:
            return []

        chunks: list[MediaChunk] = []
        current_texts: list[str] = []
        chunk_start = segments[0].start_sec
        chunk_speaker = segments[0].speaker
        chunk_idx = 0

        for i, seg in enumerate(segments):
            if not current_texts:
                chunk_start = seg.start_sec
                chunk_speaker = seg.speaker

            current_texts.append(seg.text)
            current_duration = seg.end_sec - chunk_start

            if current_duration >= target_chunk_duration_sec or i == len(segments) - 1:
                start_label = format_seconds_to_timecode(chunk_start)
                end_label = format_seconds_to_timecode(seg.end_sec)
                chunk_text = " ".join(current_texts)

                chunks.append(
                    MediaChunk(
                        chunk_index=chunk_idx,
                        text=f"[{start_label} - {end_label}] ({chunk_speaker}): {chunk_text}",
                        time_start_sec=chunk_start,
                        time_end_sec=seg.end_sec,
                        speaker=chunk_speaker,
                        timecode_label=start_label,
                        metadata={
                            "time_start_sec": chunk_start,
                            "time_end_sec": seg.end_sec,
                            "speaker": chunk_speaker,
                            "timecode_label": start_label,
                        },
                    )
                )
                chunk_idx += 1
                current_texts = []

        return chunks
