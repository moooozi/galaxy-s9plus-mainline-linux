"""Execute the portable recognizer shipped in the Mutter source patch."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[3]


class TouchWakeupTests(unittest.TestCase):
    def test_contacts_only_wake_after_a_valid_double_tap(self):
        compiler = shutil.which('cc')
        if not compiler:
            self.skipTest('A C compiler is required for the Mutter gesture test')
        patch = (REPO / 'image/gnome-mobile/patches/mutter/0001-opt-in-double-tap-wake.patch').read_text()
        section = patch.split('+++ b/src/core/meta-touch-wakeup.h\n', 1)[1].split('--- ', 1)[0]
        header = ''.join(line[1:] for line in section.splitlines(True) if line.startswith('+'))
        test = r'''
#include "meta-touch-wakeup.h"
#include <assert.h>
static void contact(MetaTouchWakeup *s, uint32_t t, float x) {
  assert(!meta_touch_wakeup_event(s, 0, t, x, 100));
}
static bool release(MetaTouchWakeup *s, uint32_t t, float x) {
  return meta_touch_wakeup_event(s, 2, t, x, 100);
}
int main(void) {
  MetaTouchWakeup s = {0};
  contact(&s, 100, 100); assert(!release(&s, 150, 100));
  contact(&s, 250, 100); assert(release(&s, 300, 100));
  contact(&s, 400, 100); assert(!release(&s, 450, 100)); /* no triple-tap wake */
  s = (MetaTouchWakeup){0};
  contact(&s, 100, 100); assert(!release(&s, 150, 100));
  contact(&s, 900, 100); assert(!release(&s, 950, 100)); /* too slow */
  s = (MetaTouchWakeup){0};
  contact(&s, 100, 100); assert(!release(&s, 150, 100));
  contact(&s, 250, 300); assert(!release(&s, 300, 300)); /* too far apart */
  s = (MetaTouchWakeup){0};
  contact(&s, 100, 100); assert(!release(&s, 500, 100)); /* long hold */
  contact(&s, 600, 100); assert(!release(&s, 650, 100));
  s = (MetaTouchWakeup){0};
  contact(&s, 100, 100);
  assert(!meta_touch_wakeup_event(&s, 1, 120, 200, 100)); /* swipe */
  assert(!release(&s, 150, 100));
  contact(&s, 250, 100); assert(!release(&s, 300, 100));
  s = (MetaTouchWakeup){0};
  contact(&s, 100, 100); contact(&s, 110, 100); /* multiple contacts */
  assert(!release(&s, 130, 100)); assert(!release(&s, 150, 100));
  contact(&s, 250, 100); assert(!release(&s, 300, 100));
  assert(!meta_touch_wakeup_event(&s, 3, 310, 0, 0)); /* cancellation */
  contact(&s, 400, 100); assert(!release(&s, 450, 100));
  s = (MetaTouchWakeup){0}; /* input timestamp wraparound */
  contact(&s, UINT32_MAX-100, 100); assert(!release(&s, UINT32_MAX-50, 100));
  contact(&s, 50, 100); assert(release(&s, 100, 100));
  return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'meta-touch-wakeup.h').write_text(header)
            (path / 'test.c').write_text(test)
            subprocess.run([compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', str(path / 'test.c'), '-o', str(path / 'test')], check=True)
            subprocess.run([str(path / 'test')], check=True)
