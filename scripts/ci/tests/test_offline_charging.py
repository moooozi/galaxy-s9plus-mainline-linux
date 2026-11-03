"""Boot selection and power transitions must fail safely on missing telemetry."""
import importlib.machinery
import importlib.util
from pathlib import Path
import tempfile
import struct
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[3]


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(REPO / path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


ui = load('charging_ui', 'device/base/usr/local/sbin/s9plus-offline-charging')
generator = load('charging_generator', 'device/base/usr/lib/systemd/system-generators/s9plus-charging-generator')


def fdt(args):
    def word(n):
        return struct.pack('>I', n)
    def padded(value):
        return value + bytes((-len(value)) % 4)
    value = args.encode('ascii') + b'\0'
    block = word(1) + bytes(4) + word(1) + padded(b'chosen\0')
    block += word(3) + word(len(value)) + word(0) + padded(value)
    block += word(2) + word(2) + word(9)
    strings = b'bootargs\0'
    return struct.pack('>10I', 0xD00DFEED, 56 + len(block) + len(strings),
                       56, 56 + len(block), 40, 17, 16, 0, len(strings), len(block)) + bytes(16) + block + strings


class ChargingTests(unittest.TestCase):
    def test_device_memory_reads_are_aligned_words_with_bounded_tail(self):
        calls = []
        def word(address):
            self.assertEqual(address % 4, 0)
            calls.append(address)
            return 0x44332211
        self.assertEqual(generator.read_words(0x1000, 7, word), bytes.fromhex('11223344112233'))
        self.assertEqual(calls, [0x1000, 0x1004])
        with self.assertRaises(ValueError):
            generator.read_words(0x1000, generator.LIMIT + 1, word)

    def test_sboot_modes_use_complete_unambiguous_tokens(self):
        for value in ('androidboot.mode=charger', 'quiet androidboot.mode=charger foo=bar'):
            self.assertTrue(generator.is_charger(generator.bootargs_from_fdt(fdt(value))))
        for value in ('androidboot.mode=normal', 'androidboot.mode=chargerX',
                      'xandroidboot.mode=charger', 'lpcharge=1', '',
                      'androidboot.mode=charger androidboot.mode=normal'):
            self.assertFalse(generator.is_charger(generator.bootargs_from_fdt(fdt(value))))

    def test_truncated_and_invalid_vendor_trees_cannot_select_charging(self):
        data = fdt('androidboot.mode=charger')
        for size in range(len(data)):
            with self.assertRaises(ValueError):
                generator.bootargs_from_fdt(data[:size])
        for offset, value in ((0, 0), (4, generator.LIMIT + 1), (8, 4),
                              (12, len(data) + 4), (32, 0xFFFFFFFF), (36, 0xFFFFFFFF)):
            bad = bytearray(data)
            struct.pack_into('>I', bad, offset, value)
            with self.assertRaises(ValueError):
                generator.bootargs_from_fdt(bad)

    def test_unreserved_vendor_address_is_never_read(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'chosen').mkdir()
            (root / 'chosen/s9plus,sboot-fdt-address').write_bytes(struct.pack('>Q', 0x12340000))
            with patch.object(generator.os, 'open') as opened:
                with self.assertRaises(ValueError):
                    generator.read_mode(root)
                opened.assert_not_called()

    def test_charger_boot_selects_target_before_desktop(self):
        with tempfile.TemporaryDirectory() as temp:
            early = Path(temp)
            generator.generate(early, 'normal')
            self.assertEqual(list(early.iterdir()), [])
            generator.generate(early, 'charger', debug=True)
            self.assertEqual((early / 'default.target').readlink().name,
                             's9plus-offline-charging.target')
            self.assertEqual((early / 'plymouth-start.service').readlink(), Path('/dev/null'))
            self.assertTrue((early / 's9plus-offline-charging.target.wants/ssh.service').is_symlink())

    def test_framebuffer_activates_its_vt_and_restores_previous_vt(self):
        calls = []

        def ioctl(fd, request, value, *_args):
            calls.append((fd, request, value if isinstance(value, int) else None))
            if request == 0x4600:
                struct.pack_into('7I', value, 0, 1440, 2960, 1440, 2960, 0, 0, 32)
                for offset, channel in ((32, (16, 8, 0)), (44, (8, 8, 0)), (56, (0, 8, 0))):
                    struct.pack_into('3I', value, offset, *channel)
            elif request == 0x4602:
                struct.pack_into('I', value, 24, 5760 * 2960)
                struct.pack_into('I', value, 48, 5760)
            elif request == 0x5603:
                struct.pack_into('H', value, 0, 2)

        with patch.object(ui.os, 'open', side_effect=[10, 11, 12]), \
                patch.object(ui.os, 'close'), patch.object(ui.mmap, 'mmap'), \
                patch.object(ui.fcntl, 'ioctl', side_effect=ioctl):
            fb = ui.Framebuffer()
            self.assertLess(calls.index((11, 0x5606, 1)), calls.index((11, 0x5607, 1)))
            self.assertLess(calls.index((11, 0x5607, 1)), calls.index((12, 0x4B3A, 1)))
            fb.close()
            self.assertLess(calls.index((12, 0x4B3A, 0)), calls.index((11, 0x5606, 2)))

    def test_exit_starts_display_manager_without_reboot_or_isolation(self):
        with patch.object(ui.subprocess, 'run') as run:
            ui.transition('boot')
            run.assert_called_once_with(
                ['systemctl', '--no-block', 'start', 'graphical.target', 'display-manager.service'], check=True)

    def test_poweroff_uses_orderly_systemd_shutdown(self):
        with patch.object(ui.subprocess, 'run') as run:
            ui.transition('poweroff')
            run.assert_called_once_with(['systemctl', '--no-block', 'poweroff'], check=True)

    def test_disconnect_debounce_and_telemetry_failure(self):
        policy = ui.Policy()
        self.assertEqual(policy.step(0, None), 'show')
        self.assertEqual(policy.step(1, 0), 'show')
        self.assertEqual(policy.step(3, 0), 'show')
        policy.step(3.1, None)  # uncertainty resets, never power off on read failure
        policy.step(4, 0)
        policy.step(5, 1)  # cable bounce resets too
        policy.step(6, 0)
        self.assertEqual(policy.step(16, 0), 'poweroff')

    def test_short_press_wakes_long_press_boots_and_release_cancels(self):
        policy = ui.Policy()
        self.assertEqual(policy.step(20, 1), 'blank')
        policy.key(1, 21)
        policy.key(2, 21.5)  # autorepeat must not reset long-press timer
        self.assertEqual(policy.step(22, 1), 'show')
        self.assertEqual(policy.step(23, 1), 'boot')
        policy.key(0, 23.1)
        self.assertEqual(policy.step(24, 1), 'show')
        self.assertEqual(policy.step(34, 1), 'blank')

    def test_unplug_wins_over_simultaneous_boot_request(self):
        policy = ui.Policy()
        policy.step(0, 0)
        policy.key(1, 8)
        self.assertEqual(policy.step(10, 0), 'poweroff')

    def test_missing_and_invalid_capacity_never_looks_full(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(ui.sample(root), (None, None))
            battery = root / 'gauge'
            battery.mkdir()
            (battery / 'capacity').write_text('101')
            self.assertEqual(ui.sample(root), (None, None))
            (battery / 'capacity').write_text('64')
            self.assertEqual(ui.sample(root), (None, 64))


if __name__ == '__main__':
    unittest.main()
