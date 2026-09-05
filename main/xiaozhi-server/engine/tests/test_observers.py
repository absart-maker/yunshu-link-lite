import unittest

from engine.contracts import PipelineStage
from engine.observers import EventBus, MetricsCollector, PipelineEvent


class EventBusTest(unittest.TestCase):
    def test_any_and_specific_subscription(self) -> None:
        bus = EventBus()
        any_events = []
        specific = []
        bus.subscribe(lambda e: any_events.append(e.name), EventBus.ANY)
        bus.subscribe(lambda e: specific.append(e.name), "turn.done")
        bus.publish(PipelineEvent("stage.enter", PipelineStage.IDLE))
        bus.publish(PipelineEvent("turn.done", PipelineStage.DONE))
        self.assertEqual(any_events, ["stage.enter", "turn.done"])
        self.assertEqual(specific, ["turn.done"])

    def test_unsubscribe(self) -> None:
        bus = EventBus()
        seen = []

        def listener(event):
            seen.append(event.name)

        bus.subscribe(listener, "x")
        bus.unsubscribe(listener, "x")
        bus.publish(PipelineEvent("x", PipelineStage.IDLE))
        self.assertEqual(seen, [])


class MetricsCollectorTest(unittest.TestCase):
    def test_counts_and_durations(self) -> None:
        collector = MetricsCollector()
        collector(PipelineEvent("stage.enter", PipelineStage.THINKING))
        collector(PipelineEvent("stage.exit", PipelineStage.THINKING))
        snapshot = collector.snapshot()
        self.assertEqual(snapshot["counts"]["stage.enter"], 1)
        self.assertIn("thinking", snapshot["durations"])


if __name__ == "__main__":
    unittest.main()
