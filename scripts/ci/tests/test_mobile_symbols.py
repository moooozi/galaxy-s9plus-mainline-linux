import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    'gnome_builder', Path(__file__).resolve().parents[1] / 'build-gnome-mobile.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class MobileSymbolsTests(unittest.TestCase):
    def test_only_reviewed_abi_differences_are_removed(self):
        removals = json.loads((builder.REPO / 'image/gnome-mobile/mutter-symbol-removals.json').read_text())
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'debian').mkdir()
            symbols = root / 'debian/libmutter-51-0.symbols'
            retained = 'libmutter-51.so.0 libmutter-51-0 #MINVER#\n retained_symbol@Base 51.0\n'
            symbols.write_text(retained + ''.join(' ' + line + '\n' for line in removals))
            builder.mobile_mutter_symbols(root)
            self.assertEqual(symbols.read_text(), retained)
            with self.assertRaisesRegex(ValueError, 'baseline changed'):
                builder.mobile_mutter_symbols(root)
