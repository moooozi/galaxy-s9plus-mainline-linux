"""Replay firmware fault storms through the driver's actual recovery policy."""
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[3]


class AboxFaultTests(unittest.TestCase):
    def test_fault_storm_exhausts_budget_and_only_manual_retry_resets_it(self):
        code = r'''
#include <assert.h>
#include "s9plus-abox-fault.h"
int main(void) {
    struct s9plus_abox_fault f = {0};
    /* Ordinary pre-fault watchdog errors do not consume the firmware budget. */
    for (unsigned i = 0; i < 100; i++)
        assert(s9plus_abox_fault_recover(&f));
    assert(!f.reports && !f.recoveries && !f.blocked);
    for (unsigned boot = 0; boot < 3; boot++) {
        /* One snapshot per firmware instance, even under a 1000-IRQ burst. */
        assert(s9plus_abox_fault_report(&f));
        for (unsigned i = 0; i < 999; i++)
            assert(!s9plus_abox_fault_report(&f));
        assert(s9plus_abox_fault_recover(&f));
        assert(f.recoveries == boot + 1);
        s9plus_abox_fault_begin_boot(&f);
        assert(!f.pending && f.faulted && !f.blocked);
    }
    assert(f.reports == 3000);
    assert(s9plus_abox_fault_report(&f));
    assert(!s9plus_abox_fault_recover(&f));
    assert(f.blocked && f.recoveries == 3);
    for (unsigned i = 0; i < 100; i++) {
        s9plus_abox_fault_begin_boot(&f);
        assert(!s9plus_abox_fault_recover(&f));
    }
    s9plus_abox_fault_manual_retry(&f);
    assert(!f.blocked && !f.recoveries && f.reports == 3001);
    for (unsigned i = 0; i < 3; i++)
        assert(s9plus_abox_fault_recover(&f));
    assert(!s9plus_abox_fault_recover(&f));
    /* Report counters saturate instead of wrapping and masking an old fault. */
    f.reports = ~0U;
    s9plus_abox_fault_report(&f);
    assert(f.reports == ~0U);
    return 0;
}
'''
        self.compile_and_run(code)

    def test_firmware_register_dump_pointer_stays_inside_owned_mappings(self):
        code = r'''
#include <assert.h>
#include "s9plus-abox-fault.h"
int main(void) {
    const unsigned bases[] = {0, 0x80000000U, 0x90000000U};
    const unsigned sizes[] = {0x31000U, 0x1200000U, 0x80000U};
    for (unsigned region = 0; region < 3; region++) {
        unsigned base = bases[region], size = sizes[region];
        assert(s9plus_abox_fault_range(base, base, size, 64));
        assert(s9plus_abox_fault_range(base + size - 64, base, size, 64));
        assert(!s9plus_abox_fault_range(base + size - 60, base, size, 64));
        assert(!s9plus_abox_fault_range(base + size, base, size, 64));
        assert(!s9plus_abox_fault_range(base + 1, base, size, 64));
        assert(!s9plus_abox_fault_range(0xfffffffcU, base, size, 64));
        assert(!s9plus_abox_fault_range(base, base, 32, 64));
        if (base)
            assert(!s9plus_abox_fault_range(base - 4, base, size, 64));
    }
    return 0;
}
'''
        self.compile_and_run(code)

    def compile_and_run(self, code):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'test.c').write_text(code)
            subprocess.run(['cc', '-O2', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-I', str(REPO / 'experiments/audio/driver'),
                            str(root / 'test.c'), '-o', str(root / 'test')], check=True)
            subprocess.run([str(root / 'test')], check=True)


if __name__ == '__main__':
    unittest.main()
