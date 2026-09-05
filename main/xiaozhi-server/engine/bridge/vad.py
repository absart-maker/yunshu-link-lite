"""语音活动检测桥接适配。"""

from __future__ import annotations

from ..contracts import AudioChunk


class LegacyVoiceActivityDetector:
    """把旧式 `is_vad(conn, pcm_frame)` 包装成新契约。"""

    def __init__(self, detector, connection: object | None = None, frame_size: int = 1600) -> None:
        self._detector = detector
        self._connection = connection
        self._frame_size = frame_size

    def is_speech(self, audio: AudioChunk) -> bool:
        frames = [
            audio.pcm[index : index + self._frame_size]
            for index in range(0, len(audio.pcm), self._frame_size)
        ]
        return any(self._detector.is_vad(self._connection, frame) for frame in frames)
