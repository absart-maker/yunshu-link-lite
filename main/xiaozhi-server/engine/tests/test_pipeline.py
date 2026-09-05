import asyncio
import unittest

from engine.contracts import AudioChunk, Message, ReplyChunk
from engine.pipeline import AiPipeline, PipelineError
from engine.stubs import (
    AlwaysSilenceVAD,
    AlwaysVoiceVAD,
    EchoASR,
    FailingLLM,
    PaletteTTS,
    RuleLLM,
)


def make_pipeline(vad=AlwaysVoiceVAD(), fallback=None, **kwargs):
    return AiPipeline(
        EchoASR(),
        RuleLLM(reply="引擎"),
        PaletteTTS(),
        vad,
        fallback_llm=fallback,
        **kwargs,
    )


class PipelineTest(unittest.TestCase):
    def test_happy_path(self) -> None:
        result = asyncio.run(
            make_pipeline().run_turn(AudioChunk(b"\x00" * 640), "s1")
        )
        self.assertEqual(result.transcript, "请介绍一下这个引擎")
        self.assertEqual(result.reply, "引擎")
        self.assertGreater(len(result.speech), 0)
        names = [event.name for event in result.events]
        self.assertIn("turn.done", names)
        self.assertIn("asr.done", names)
        self.assertIn("tts.done", names)
        self.assertIn("asr", result.metrics)

    def test_vad_reject_short_circuit(self) -> None:
        result = asyncio.run(
            make_pipeline(vad=AlwaysSilenceVAD()).run_turn(
                AudioChunk(b"\x00" * 640), "s2"
            )
        )
        self.assertEqual(result.reply, "")
        names = [event.name for event in result.events]
        self.assertIn("voice.rejected", names)
        self.assertNotIn("asr.done", names)

    def test_fallback_llm(self) -> None:
        pipeline = AiPipeline(
            EchoASR(),
            FailingLLM(),
            PaletteTTS(),
            AlwaysVoiceVAD(),
            fallback_llm=RuleLLM(reply="兜底"),
            max_retries=1,
        )
        result = asyncio.run(
            pipeline.run_turn(AudioChunk(b"\x00" * 640), "s3")
        )
        self.assertEqual(result.reply, "兜底")
        names = [event.name for event in result.events]
        self.assertIn("llm.retry", names)

    def test_all_llm_failures_raise_pipeline_error(self) -> None:
        pipeline = AiPipeline(
            EchoASR(), FailingLLM(), PaletteTTS(), AlwaysVoiceVAD(), max_retries=1
        )
        with self.assertRaises(PipelineError):
            asyncio.run(pipeline.run_turn(AudioChunk(b"\x00" * 640), "s4"))

    def test_multi_turn_conversation_history(self) -> None:
        from engine.session import Conversation

        conversation = Conversation(system_prompt="系统提示")
        pipeline = make_pipeline()
        for _ in range(2):
            asyncio.run(
                pipeline.run_turn(AudioChunk(b"\x00" * 640), "s5", conversation)
            )
        self.assertEqual(len(conversation.messages), 4)

    def test_llm_timeout_raises_pipeline_error(self) -> None:
        class SleepingLLM:
            def stream_reply(self, messages, session_id):
                async def generate():
                    await asyncio.sleep(5)
                    yield ReplyChunk("太晚了")

                return generate()

        pipeline = AiPipeline(
            EchoASR(),
            SleepingLLM(),
            PaletteTTS(),
            AlwaysVoiceVAD(),
            timeout_seconds=0.05,
        )
        with self.assertRaises(PipelineError):
            asyncio.run(pipeline.run_turn(AudioChunk(b"\x00" * 640), "s6"))


if __name__ == "__main__":
    unittest.main()
