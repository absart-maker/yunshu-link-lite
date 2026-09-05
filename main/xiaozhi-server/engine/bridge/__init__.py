"""兼容现有 Provider 的桥接层。

现有 xiaozhi-server 的 Provider 与连接层强耦合，本桥接层把已解耦部分
按能力拆成子模块适配，未覆盖部分可通过各子模块的“接入说明”逐步补齐。
"""

from .asr import FunctionSpeechToText, LegacySpeechToText
from .llm import LegacyLanguageModel
from .tts import LegacyTextToSpeech, StreamingTextToSpeech
from .vad import LegacyVoiceActivityDetector
from .websocket import WebSocketTransport, WebSocketTransportFactory

__all__ = [
    "FunctionSpeechToText",
    "LegacyLanguageModel",
    "LegacySpeechToText",
    "LegacyTextToSpeech",
    "LegacyVoiceActivityDetector",
    "StreamingTextToSpeech",
    "WebSocketTransport",
    "WebSocketTransportFactory",
]
