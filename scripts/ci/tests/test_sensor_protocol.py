"""Exercise wire framing and serialized SSP transactions without hardware."""
import importlib.util
from pathlib import Path
import struct
import unittest

REPO = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('s9plus_ssp', REPO /
    'experiments/sensors/rootfs/usr/local/lib/s9plus-sensors/ssp.py')
ssp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ssp)


def packet(data):
    return struct.pack('<H', len(data)) + data


def frame(sensor=0, values=(0, 4096, -12)):
    payload = b'\x37' + bytes([sensor]) + struct.pack('<hhh', *values) + bytes(8)
    return struct.pack('<HH', 2, len(payload)) + payload


class SensorProtocolTests(unittest.TestCase):
    def setUp(self):
        self.writes = []
        self.samples = []

        def write(fd, data):
            self.writes.append(data)
            return len(data)

        self.hub = ssp.Hub(123, lambda *sample: self.samples.append(sample), write)

    def test_each_possible_fragment_boundary(self):
        data = packet(frame())
        for cut in range(len(data) + 1):
            samples = []
            hub = ssp.Hub(123, lambda *sample: samples.append(sample))
            hub.feed(data[:cut])
            hub.feed(data[cut:])
            self.assertEqual(samples, [(0, (0, 4096, -12))])

    def test_ssp_message_spans_transport_packets(self):
        data = frame()
        for byte in data:
            self.hub.feed(packet(bytes([byte])))
        self.assertEqual(self.samples, [(0, (0, 4096, -12))])

    def test_commands_wait_for_payload_echo(self):
        payload = struct.pack('<BiiB', 0, 200, 0, 0)
        self.hub.begin(0xa1, payload)
        opts = self.hub.pending[0]
        with self.assertRaises(ssp.ProtocolError):
            self.hub.begin(0xa2, b'12345')
        self.assertEqual(len(self.writes), 1)
        self.hub.feed(packet(frame()))
        self.assertIsNotNone(self.hub.pending)
        self.hub.feed(packet(struct.pack('<HH', opts, len(payload))))
        self.assertEqual(self.writes[-1], payload)
        self.assertIsNone(self.hub.pending)

    def test_read_reply_can_be_fragmented(self):
        self.hub.begin(0xf4, read=8)
        opts = self.hub.pending[0]
        response = packet(struct.pack('<HHQ', opts, 8, 0x203))
        for byte in response:
            self.hub.feed(bytes([byte]))
        self.assertEqual(int.from_bytes(self.hub.reply, 'little'), 0x203)

    def test_mismatched_echo_never_sends_payload(self):
        self.hub.begin(0xa1, b'12345')
        opts = self.hub.pending[0]
        with self.assertRaises(ssp.ProtocolError):
            self.hub.feed(packet(struct.pack('<HH', opts, 4)))
        self.assertEqual(len(self.writes), 1)

    def test_short_writes_are_errors(self):
        hub = ssp.Hub(123, lambda *_: None, lambda fd, data: len(data) - 1)
        with self.assertRaises(ssp.ProtocolError):
            hub.begin(0xf4, read=8)

    def test_truncated_records_never_publish(self):
        for length in range(1, 16):
            with self.assertRaises(ssp.ProtocolError):
                list(ssp.records((b'\x37\x00' + bytes(14))[:length]))

    def test_oversized_frames_rejected(self):
        with self.assertRaises(ssp.ProtocolError):
            self.hub.feed(packet(struct.pack('<HH', 2, 8192)))
        with self.assertRaises(ssp.ProtocolError):
            ssp.Hub(123, lambda *_: None).feed(struct.pack('<H', 8193))

    def test_light_is_lux_and_signed_motion_preserved(self):
        raw = b'\x37\x09' + struct.pack('<I', 12345) + bytes(14 + 8)
        self.assertEqual(list(ssp.records(raw)), [(9, (12345, 0, 0))])

    def test_reset_stops_old_session(self):
        with self.assertRaises(ssp.ProtocolError):
            list(ssp.records(b'\x0a'))

    def test_phone_gyro_frame_uses_32_bit_axes(self):
        # Captured from SM-G965F: a 6-byte gyro assumption treated timestamp
        # bytes as record tags, reporting false debug truncation/hub resets.
        raw = bytes.fromhex(
            '370046f7d7036ff3339c0a7c07000000'
            '370168d1fdff6008fcff683c0100339c0a7c07000000')
        self.assertEqual(list(ssp.records(raw)), [
            (0, (-2234, 983, -3217)), (1, (-143000, -260000, 81000))])


if __name__ == '__main__':
    unittest.main()
