from titan_backend.media.chunker import MediaSemanticChunker, format_seconds_to_timecode
from titan_backend.media.transcriber import MediaTranscriptionEngine, TranscriptionSegment


def test_format_seconds_to_timecode():
    assert format_seconds_to_timecode(45) == "00:45"
    assert format_seconds_to_timecode(124.5) == "02:04"
    assert format_seconds_to_timecode(3665) == "01:01:05"


def test_media_transcription_engine_fallback():
    mock_audio_bytes = b"MOCK_PCM_AUDIO_STREAM_DATA" * 1000
    res = MediaTranscriptionEngine.transcribe(mock_audio_bytes, mime_type="audio/mpeg")

    assert res.duration_seconds > 0
    assert res.language == "en"
    assert res.speaker_count >= 1
    assert len(res.segments) >= 2
    assert "TitanRAG" in res.full_transcript


def test_media_semantic_chunker():
    segments = [
        TranscriptionSegment(start_sec=0.0, end_sec=20.0, text="First point regarding architecture.", speaker="Alice"),
        TranscriptionSegment(start_sec=20.0, end_sec=40.0, text="Second point covering PostgreSQL and Qdrant.", speaker="Alice"),
        TranscriptionSegment(start_sec=40.0, end_sec=65.0, text="Third point from Bob discussing media.", speaker="Bob"),
    ]

    chunks = MediaSemanticChunker.chunk_segments(segments, target_chunk_duration_sec=35.0)

    assert len(chunks) == 2
    assert chunks[0].time_start_sec == 0.0
    assert chunks[0].time_end_sec == 40.0
    assert chunks[0].timecode_label == "00:00"
    assert "First point regarding architecture." in chunks[0].text
    assert "Second point covering PostgreSQL" in chunks[0].text
    assert chunks[1].time_start_sec == 40.0
    assert chunks[1].speaker == "Bob"
