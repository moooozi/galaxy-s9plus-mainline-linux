"""Execute the real uniLoader framebuffer console with quiet and debug configs."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[3]
LOADER = REPO / 'bootloader/uniLoader'


class QuietLoader(unittest.TestCase):
    def test_console_preserves_artwork_until_an_allowed_message(self):
        for quiet, preserve in ((True, True), (False, True), (False, False)):
            with self.subTest(quiet=quiet, preserve=preserve), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                shutil.copyfile(LOADER / 'lib/unic/util.h', root / 'util.h')
                code = r'''
#include <assert.h>
#include <string.h>
#include "CONSOLE_SOURCE"
#include "FRAMEBUFFER_SOURCE"
static unsigned char pixels[256 * 128 * 4];
static void assert_artwork(void) {
    for (unsigned i = 0; i < sizeof(pixels); i++) assert(pixels[i] == 0x5a);
}
int main(void) {
    memset(pixels, 0x5a, sizeof(pixels));
    struct video_info info = {.format = FB_FORMAT_ARGB8888, .width = 256,
        .height = 128, .stride = 4, .scale = 1, .address = pixels};
    assert(simplefb_probe(&info) == 0);
#ifdef TEST_QUIET
    assert_artwork();
    printk(KERN_INFO, "startup banner\n");
    printk(KERN_WARNING, "routine warning\n");
    assert_artwork();
#endif
    printk(KERN_ERR, "failure\n");
    /* The first visible message clears firmware pixels before drawing errors. */
    for (unsigned i = 0; i < sizeof(pixels); i++) assert(pixels[i] != 0x5a);
    pixels[sizeof(pixels) - 1] = 0x5a;
    printk(KERN_CRIT, "critical\n");
    /* Later messages must not erase the prior console contents. */
    assert(pixels[sizeof(pixels) - 1] == 0x5a);
    return 0;
}
'''.replace('CONSOLE_SOURCE', str(LOADER / 'lib/console/console.c')).replace('FRAMEBUFFER_SOURCE', str(LOADER / 'lib/simplefb/simplefb.c'))
                (root / 'test.c').write_text(code)
                flags = ['-DCONFIG_LOGLEVEL=' + ('3' if quiet else '7')]
                if quiet:
                    flags += ['-DTEST_QUIET']
                if preserve:
                    flags += ['-DCONFIG_SIMPLE_FB_PRESERVE_CONTENTS']
                subprocess.run(['cc', '-std=gnu11', '-O2', '-I' + str(LOADER / 'include'),
                                '-I' + str(root), *flags, str(root / 'test.c'), '-o', str(root / 'test')], check=True)
                subprocess.run([str(root / 'test')], check=True)
