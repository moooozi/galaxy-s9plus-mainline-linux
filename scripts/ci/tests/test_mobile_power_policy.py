"""Exercise the actual GSD policy functions carried by the source patch."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[3]
PATCHES = REPO / 'image/gnome-mobile/patches/gnome-settings-daemon'


def added_source(path):
    # Reconstruct the target-side hunk text, including unchanged context.
    return ''.join(line[1:] for line in path.read_text().splitlines(True)
                   if line.startswith((' ', '+')) and not line.startswith('+++'))


class MobilePowerPolicyTests(unittest.TestCase):
    def test_short_release_long_hold_and_modal_cleanup(self):
        compiler = shutil.which('cc')
        if not compiler:
            self.skipTest('A C compiler is required for the GSD policy test')
        source = added_source(PATCHES / '0001-mobile-power-key-press-release.patch')
        functions = []
        for name in ('do_toggle_blank', 'mobile_power_long_press', 'mobile_power_cancel', 'on_accelerator_deactivated'):
            match = re.search(r'static (?:void|gboolean)\n' + name + r' \(.*?\n}\n', source, re.S)
            self.assertIsNotNone(match, name)
            functions.append(match.group())
        test = r'''
#include <assert.h>
#include <stddef.h>
typedef unsigned guint;
typedef int gboolean;
typedef void *gpointer;
typedef void ShellKeyGrabber;
typedef void GVariant;
#define TRUE 1
#define G_SOURCE_REMOVE 0
typedef struct {
  unsigned mobile_power_action, mobile_power_timer;
  int mobile_power_was_off, mobile_power_had_shield, power_button_disabled;
  void *screen_saver_proxy;
} GsdMediaKeysManager;
typedef GsdMediaKeysManager GsdMediaKeysManagerPrivate;
#define GSD_MEDIA_KEYS_MANAGER_GET_PRIVATE(m) (m)
static int active_calls, power_calls, power_mode, menus, removed;
static void mobile_set_display_power(GsdMediaKeysManager *m, int mode) {
  power_calls++; power_mode = mode;
}
static void *gnome_settings_bus_get_screen_saver_proxy(void) { return (void *)1; }
static void toggle_blank_cb(void) {}
static void gsd_screen_saver_call_set_active(void *p, int active, void *c, void (*cb)(void), void *d) {
  assert(active); active_calls++;
}
static void gnome_session_shutdown(GsdMediaKeysManager *m) {
  assert(m->mobile_power_action == 0 && m->mobile_power_timer == 0);
  menus++;
}
static int g_source_remove(unsigned id) { assert(id); removed++; return 1; }
#define g_clear_handle_id(p, f) do { if (*(p)) { f(*(p)); *(p)=0; } } while(0)
''' + '\n'.join(functions) + r'''
static GsdMediaKeysManager fresh(void) {
  active_calls=power_calls=menus=removed=0;
  return (GsdMediaKeysManager){.mobile_power_action=173, .mobile_power_timer=99};
}
int main(void) {
  GsdMediaKeysManager m=fresh();
  on_accelerator_deactivated(NULL, 173, NULL, &m);
  assert(active_calls==1 && power_calls==0 && menus==0); /* let initial lock finish */
  assert(m.mobile_power_action==0 && m.mobile_power_timer==0 && removed==1);
  m=fresh(); m.mobile_power_had_shield=1;
  on_accelerator_deactivated(NULL, 173, NULL, &m);
  assert(active_calls==0 && power_calls==1 && power_mode==3); /* blank lit shield */
  m=fresh(); m.mobile_power_was_off=1; m.mobile_power_had_shield=1;
  on_accelerator_deactivated(NULL, 173, NULL, &m);
  assert(active_calls==0 && power_calls==1 && power_mode==0); /* wake, retain lock */
  m=fresh();
  assert(mobile_power_long_press(&m)==G_SOURCE_REMOVE);
  assert(menus==1 && active_calls==0 && power_calls==1 && power_mode==0);
  on_accelerator_deactivated(NULL, 173, NULL, &m);
  assert(menus==1 && active_calls==0 && power_calls==1); /* no extra short action */
  m=fresh(); m.power_button_disabled=1;
  on_accelerator_deactivated(NULL, 173, NULL, &m);
  assert(active_calls==0 && power_calls==0 && menus==0 && removed==1);
  m=fresh();
  on_accelerator_deactivated(NULL, 999, NULL, &m);
  assert(m.mobile_power_action==173 && m.mobile_power_timer==99 && removed==0);
  return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'test.c').write_text(test)
            subprocess.run([compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter', str(path / 'test.c'), '-o', str(path / 'test')], check=True)
            subprocess.run([str(path / 'test')], check=True)

    def test_power_grab_requests_mutters_release_protocol_bit(self):
        source = added_source(PATCHES / '0002-request-power-key-release-events.patch')
        self.assertRegex(source, r'META_KEY_BINDING_TRIGGER_RELEASE\s*=\s*1\s*<<\s*7')
        power = re.search(r'\{ POWER_KEY,[^\n]+', source).group()
        self.assertIn('META_KEY_BINDING_TRIGGER_RELEASE', power)
        self.assertIn('META_KEY_BINDING_IGNORE_AUTOREPEAT', power)
