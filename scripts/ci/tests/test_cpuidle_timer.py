"""Inject MCT write failures and expired deadlines into the actual driver code."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


class CpuIdleTimerTests(unittest.TestCase):
    def test_failed_programming_never_reports_a_usable_wakeup(self):
        source = (Path(__file__).resolve().parents[3] / 'src/cpuidle/s9plus-idle.c').read_text()
        functions = []
        for name in ('mct_wr', 'mct_comp0_stop', 'zrn_bc_set_next'):
            match = re.search(r'static int ' + name + r'\([^{}]*\)\n\{.*?^\}', source, re.M | re.S)
            self.assertIsNotNone(match, name)
            functions.append(match.group())
        constants = '\n'.join(line for line in source.splitlines() if line.startswith('#define MCT_'))
        harness = r'''
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <string.h>
typedef uint32_t u32;
typedef uint64_t u64;
typedef int64_t s64;
static u32 registers[0x800 / 4];
static unsigned char *mct = (unsigned char *)registers;
static unsigned writes, fail_at, reads;
static u64 ticks[2];
static unsigned long mct_write_failures, mct_late_events;
static int mct_lock;
struct clock_event_device { int unused; };
#define raw_spin_lock_irqsave(lock, flags) do { (void)(lock); (flags) = 0; } while (0)
#define raw_spin_unlock_irqrestore(lock, flags) do { (void)(lock); (void)(flags); } while (0)
#define pr_warn_ratelimited(...) do { } while (0)
static u64 mct_count(void) { return ticks[reads++ ? 1 : 0]; }
static u32 readl_relaxed(const void *address) { return *(const u32 *)address; }
static void writel_relaxed(u32 value, void *address) {
    unsigned offset = (unsigned)((unsigned char *)address - mct);
    if (offset == MCT_G_WSTAT) {
        registers[offset / 4] &= ~value;
        return;
    }
    *(u32 *)address = value;
    if (offset == MCT_G_TCON || offset == MCT_G_COMP0_L || offset == MCT_G_COMP0_U) {
        unsigned bit = offset == MCT_G_TCON ? 16 : offset == MCT_G_COMP0_L ? 0 : 1;
        if (++writes != fail_at)
            registers[MCT_G_WSTAT / 4] |= 1U << bit;
    }
}
#define readl_poll_timeout_atomic(address, value, condition, delay, timeout) \
    ((value) = readl_relaxed(address), (condition) ? 0 : -ETIMEDOUT)
'''
        checks = r'''
static void reset(u64 start, u64 end, unsigned fail) {
    memset(registers, 0, sizeof(registers));
    registers[MCT_G_TCON / 4] = MCT_TCON_START;
    registers[MCT_G_INT_ENB / 4] = 8; /* A sibling interrupt must survive. */
    ticks[0] = start; ticks[1] = end;
    writes = reads = 0; fail_at = fail;
    mct_write_failures = mct_late_events = 0;
}
static void stopped(void) {
    assert(registers[MCT_G_INT_ENB / 4] == 8);
    assert(!(registers[MCT_G_TCON / 4] & MCT_TCON_COMP0_EN));
    assert(registers[MCT_G_TCON / 4] & MCT_TCON_START);
}
int main(void) {
    struct clock_event_device event = {0};
    reset(100, 550, 0);
    assert(zrn_bc_set_next(500, &event) == 0);
    assert(registers[MCT_G_COMP0_L / 4] == 600);
    assert(registers[MCT_G_INT_ENB / 4] == 9);
    assert(registers[MCT_G_TCON / 4] & MCT_TCON_COMP0_EN);
    for (unsigned failure = 1; failure <= 4; failure++) {
        reset(100, 550, failure);
        assert(zrn_bc_set_next(500, &event) == -ETIME);
        assert(mct_write_failures == 1);
        stopped();
    }
    for (unsigned late = 600; late <= 601; late++) {
        reset(100, late, 0);
        assert(zrn_bc_set_next(500, &event) == -ETIME);
        assert(mct_late_events == 1);
        stopped();
    }
    /* Comparisons remain correct when the hardware counter wraps. */
    reset(UINT64_MAX - 100, 50, 0);
    assert(zrn_bc_set_next(200, &event) == 0);
    assert(registers[MCT_G_COMP0_L / 4] == 99);
    reset(UINT64_MAX - 100, 100, 0);
    assert(zrn_bc_set_next(200, &event) == -ETIME);
    stopped();
    reset(100, 100, 0);
    assert(zrn_bc_set_next(0, &event) == -ETIME);
    stopped();
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'timer.c').write_text('#include <limits.h>\n' + constants + '\n' + harness +
                                         '\n'.join(functions) + checks)
            subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                            '-Wno-unused-parameter', str(root / 'timer.c'),
                            '-o', str(root / 'timer-test')], check=True)
            subprocess.run([str(root / 'timer-test')], check=True)


if __name__ == '__main__':
    unittest.main()
