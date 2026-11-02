import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'resolve_kernel', Path(__file__).resolve().parents[1] / 'resolve-kernel.py')
resolver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resolver)
POLICY = {'series': '7.3', 'policy': 'latest-supported-patch'}


def release(version, *, eol=False, moniker='stable'):
    return {'version': version, 'iseol': eol, 'moniker': moniker}


class KernelSelectionTests(unittest.TestCase):
    def test_newest_patch_is_selected_numerically(self):
        metadata = {'releases': [release('7.3.1'), release('7.3.9'), release('7.3.10')]}
        self.assertEqual(resolver.select_release(POLICY, metadata), '7.3.10')

    def test_other_series_and_release_candidates_are_excluded(self):
        metadata = {'releases': [release('7.4.1'), release('7.3.11-rc1'), release('7.3.2')]}
        self.assertEqual(resolver.select_release(POLICY, metadata), '7.3.2')

    def test_eol_series_requires_review(self):
        with self.assertRaisesRegex(ValueError, 'No supported'):
            resolver.select_release(POLICY, {'releases': [release('7.3.20', eol=True)]})

    def test_stable_base_release_is_allowed(self):
        self.assertEqual(resolver.select_release(POLICY, {
            'releases': [release('7.3', moniker='mainline')]}), '7.3')


if __name__ == '__main__':
    unittest.main()
