import unittest

from engine.device_simulator import DeviceSimulator, default_server


class DeviceSimulatorTest(unittest.IsolatedAsyncioTestCase):
    async def test_full_protocol(self) -> None:
        server = default_server()
        frames = await DeviceSimulator(server).run()
        types = [frame.type for frame in frames]
        self.assertEqual(
            types[:5],
            ["ready", "listening", "transcript", "reply", "audio"],
        )
        reply = frames[[f.type for f in frames].index("reply")]
        self.assertEqual(reply.metadata.get("text"), "设备模拟回复")


if __name__ == "__main__":
    unittest.main()
