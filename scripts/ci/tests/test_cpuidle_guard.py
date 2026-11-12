"""Exercise failure recovery before enabling context-losing CPU idle."""
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


HELPER = Path(__file__).resolve().parents[3] / 'experiments/cpuidle/rootfs/usr/local/sbin/s9plus-cpuidle'


class CpuIdleGuardTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        loader = SourceFileLoader('cpuidle_guard', str(HELPER))
        self.helper = module_from_spec(spec_from_loader(loader.name, loader))
        loader.exec_module(self.helper)
        self.helper.STATE = self.root / 'state'
        self.helper.MARK = self.helper.STATE / 'loading'
        self.helper.PARAMS = self.root / 'params'
        self.helper.PARAMS.mkdir()
        (self.helper.PARAMS / 'integrated').write_text('Y\n')
        (self.helper.PARAMS / 'g0_irqs').write_text('100\n')
        self.boot = self.root / 'proc/sys/kernel/random/boot_id'
        self.boot.parent.mkdir(parents=True)
        self.boot.write_text('current-boot\n')
        self.states = []
        for cpu in (2, 3):
            state = self.root / f'sys/devices/system/cpu/cpu{cpu}/cpuidle/state1'
            state.mkdir(parents=True)
            for name, value in [('name', 'C2\n'), ('disable', '1\n'), ('usage', '10\n')]:
                (state / name).write_text(value)
            self.states.append(state)
        def mapped(path):
            path = Path(path)
            return self.root / str(path).lstrip('/') if path.is_absolute() else path
        self.enterContext(patch.object(self.helper, 'Path', mapped))
        for target, value in [('os.geteuid', 0), ('os.sync', None)]:
            self.enterContext(patch.object(self.helper.os, target.split('.')[1], return_value=value))
        self.run = self.enterContext(patch.object(self.helper.subprocess, 'run'))
        self.enterContext(patch.object(self.helper.sys, 'argv', ['s9plus-cpuidle']))

    def trial(self):
        self.helper.main()

    def mark(self, boot='current-boot\n', *, enabled=False):
        self.helper.STATE.mkdir()
        self.helper.MARK.write_text(boot)
        if enabled:
            for state in self.states:
                (state / 'disable').write_text('0\n')

    def disabled(self):
        return [(state / 'disable').read_text().strip() for state in self.states]

    def test_trial_schedules_confirmation_and_enables_only_validated_states(self):
        self.trial()
        self.assertEqual(self.disabled(), ['0', '0'])
        self.assertEqual(self.helper.MARK.read_text(), self.boot.read_text())
        self.assertEqual(self.run.call_args.args[0][0], 'systemd-run')

    def test_stale_failure_marker_prevents_enable(self):
        self.mark('previous-boot\n')
        with self.assertRaisesRegex(SystemExit, 'Previous CPU idle'):
            self.trial()
        self.assertEqual(self.disabled(), ['1', '1'])
        self.run.assert_not_called()

    def test_legacy_module_is_rejected(self):
        (self.helper.PARAMS / 'integrated').unlink()
        with self.assertRaisesRegex(SystemExit, 'integrated'):
            self.trial()
        self.assertEqual(self.disabled(), ['1', '1'])

    def test_wrong_state_prevents_partial_enable(self):
        (self.states[1] / 'name').write_text('unexpected\n')
        with self.assertRaisesRegex(SystemExit, 'Unexpected'):
            self.trial()
        self.assertEqual(self.disabled(), ['1', '1'])

    def test_scheduler_failure_retains_marker_and_leaves_states_disabled(self):
        self.run.side_effect = RuntimeError('scheduler failed')
        with self.assertRaisesRegex(RuntimeError, 'scheduler failed'):
            self.trial()
        self.assertTrue(self.helper.MARK.exists())
        self.assertEqual(self.disabled(), ['1', '1'])

    def test_partial_enable_failure_disables_both_states(self):
        write = Path.write_text
        def fail_second(path, value, *args, **kwargs):
            if path == self.states[1] / 'disable' and value == '0\n':
                raise OSError('CPU3 enable failed')
            return write(path, value, *args, **kwargs)
        with patch.object(Path, 'write_text', fail_second):
            with self.assertRaisesRegex(OSError, 'CPU3 enable failed'):
                self.trial()
        self.assertTrue(self.helper.MARK.exists())
        self.assertEqual(self.disabled(), ['1', '1'])

    def test_confirmation_rejects_stale_boot_marker(self):
        self.mark('previous-boot\n')
        with self.assertRaisesRegex(SystemExit, 'this boot'):
            self.helper.confirm()
        self.assertTrue(self.helper.MARK.exists())

    def test_confirmation_requires_progress_on_both_cores(self):
        self.mark(enabled=True)
        with patch.object(self.helper.time, 'sleep'):
            with self.assertRaisesRegex(SystemExit, 'counters did not advance'):
                self.helper.confirm()
        self.assertTrue(self.helper.MARK.exists())
        self.assertEqual(self.disabled(), ['1', '1'])

    def test_successful_confirmation_clears_marker(self):
        self.mark(enabled=True)
        def advance(_):
            for state in self.states:
                (state / 'usage').write_text('20\n')
            (self.helper.PARAMS / 'g0_irqs').write_text('120\n')
        with patch.object(self.helper.time, 'sleep', advance):
            self.helper.confirm()
        self.assertFalse(self.helper.MARK.exists())

    def test_confirmation_rejects_old_nonzero_irq_count(self):
        self.mark(enabled=True)
        def advance(_):
            for state in self.states:
                (state / 'usage').write_text('20\n')
        with patch.object(self.helper.time, 'sleep', advance):
            with self.assertRaisesRegex(SystemExit, 'fresh MCT'):
                self.helper.confirm()
        self.assertTrue(self.helper.MARK.exists())
        self.assertEqual(self.disabled(), ['1', '1'])


if __name__ == '__main__':
    unittest.main()
