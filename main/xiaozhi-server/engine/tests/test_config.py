import json
import tempfile
import unittest
from pathlib import Path

from engine.config import config_from_dict, load_config, validate_config
from engine.config import _provider_from_dict
from engine.stubs import register_standard_providers


class ConfigTest(unittest.TestCase):
    def test_config_from_dict(self) -> None:
        config = config_from_dict(
            {
                "engine": {
                    "asr": {"name": "echo"},
                    "llm": {"name": "rule", "options": {"reply": "ok"}},
                    "tts": {"name": "palette"},
                    "vad": {"name": "always_voice"},
                    "timeout_seconds": 12,
                    "max_retries": 2,
                }
            }
        )
        self.assertEqual(config.asr.name, "echo")
        self.assertEqual(config.llm.options["reply"], "ok")
        self.assertEqual(config.timeout_seconds, 12.0)
        self.assertEqual(config.max_retries, 2)

    def test_load_and_validate_json(self) -> None:
        registry = register_standard_providers()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "engine.json"
            path.write_text(
                json.dumps(
                    {
                        "engine": {
                            "asr": {"name": "echo"},
                            "llm": {"name": "rule"},
                            "tts": {"name": "palette"},
                        }
                    }
                ),
                encoding="utf-8",
            )
            config = load_config(path)
            self.assertEqual(validate_config(config, registry), [])

    def test_validate_reports_missing_provider(self) -> None:
        registry = register_standard_providers()
        config = config_from_dict(
            {
                "asr": {"name": "missing"},
                "llm": {"name": "rule"},
                "tts": {"name": "palette"},
            }
        )
        self.assertIn("未注册的 asr.missing", validate_config(config, registry)[0])

    def test_missing_provider_name_raises(self) -> None:
        with self.assertRaises(ValueError):
            _provider_from_dict("asr", {})


if __name__ == "__main__":
    unittest.main()
