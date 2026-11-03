"""Exercise the actual DAC write guard across every 16-bit register value."""
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[3]


class HeadphoneLimitTests(unittest.TestCase):
    def test_cap_preserves_mute_and_latch_bits_and_other_registers(self):
        code = r'''
#include <assert.h>
#include "s9plus-headphone-limit.h"
int main(void) {
    /* A louder accidental edit must fail CI rather than silently raise gain. */
    _Static_assert(S9PLUS_HEADPHONE_VOLUME_MAX == 68, "-30dB ceiling");
    for (unsigned reg = 0x400; reg < 0x700; reg++) {
        for (unsigned v = 0; v <= 0xffff; v++) {
            unsigned result = s9plus_headphone_limit(reg, v);
            if (reg == 0x419 || reg == 0x41d) {
                assert((result & 0xff) <= 68);
                assert((result & 0xff) <= (v & 0xff));
                assert((result & ~0xffU) == (v & ~0xffU));
                assert(s9plus_headphone_limit(reg, result) == result);
            } else {
                assert(result == v);
            }
        }
    }
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'test.c').write_text(code)
            subprocess.run(['cc', '-O2', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-I', str(REPO / 'experiments/audio/driver'),
                            str(root / 'test.c'), '-o', str(root / 'test')], check=True)
            subprocess.run([str(root / 'test')], check=True)

    def test_codec_writes_cannot_skip_guard(self):
        source = (REPO / 'experiments/audio/driver/snd-zrn-abox.c').read_text()
        function = source.split('static void codec_write(u32 reg, u16 val)\n{', 1)[1].split('\n}', 1)[0]
        self.assertLess(function.index('s9plus_headphone_limit(reg, val)'),
                        function.index('u8 tx[8]'))
