import unittest

from engine.registry import ProviderNotFoundError, ProviderRegistry
from engine.stubs import EchoASR


class RegistryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = ProviderRegistry()

    def test_register_and_get(self) -> None:
        self.registry.register("echo", "asr", EchoASR, description="示例")
        spec = self.registry.get("asr", "echo")
        self.assertEqual(spec.category, "asr")
        self.assertEqual(spec.description, "示例")
        self.assertTrue(self.registry.has("asr", "echo"))

    def test_duplicate_override(self) -> None:
        self.registry.register("x", "llm", EchoASR)
        self.registry.register("x", "llm", EchoASR)
        self.assertEqual(len(self.registry._specs["llm"]), 1)

    def test_names_and_categories(self) -> None:
        self.registry.register("a", "asr", EchoASR)
        self.registry.register("b", "llm", EchoASR)
        self.assertEqual(self.registry.names("asr"), ["a"])
        self.assertEqual(self.registry.categories(), ["asr", "llm"])

    def test_unknown_provider_message(self) -> None:
        with self.assertRaises(ProviderNotFoundError) as ctx:
            self.registry.get("asr", "missing")
        self.assertIn("asr.missing", str(ctx.exception))

    def test_create_validates_required_config(self) -> None:
        def factory(**options):
            return EchoASR()

        self.registry.register("needs_key", "llm", factory, ["api_key"])
        with self.assertRaises(ValueError):
            self.registry.create("llm", "needs_key")
        self.assertIsInstance(
            self.registry.create("llm", "needs_key", options={"api_key": "k"}),
            EchoASR,
        )


if __name__ == "__main__":
    unittest.main()
