"""A handshake level must not turn a sensor reset into repeated power cycles."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[3]


class SensorReset(unittest.TestCase):
    def test_park_drives_only_host_output_pins_low(self):
        source = (REPO / 'experiments/sensors/driver/zrn_bbd_board.c').read_text()
        function = re.search(r'static void hub_pins_park\(.*?\n}\n', source, re.S)
        self.assertIsNotNone(function)
        code = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#define BIT(n) (1U << (n))
#define PIN_SCK BIT(0)
#define PIN_MOSI BIT(1)
#define PIN_MISO BIT(2)
#define PIN_CS BIT(3)
#define PIN_MCU_REQ BIT(5)
#define GPH0_CON 0
#define ZRN_GPIO_AP_SLEEP 0
static uint32_t registers[2], data;
static unsigned char *gph0 = (unsigned char *)registers;
static bool bitbang;
static int ap_sleep, zrn_gpios[1];
static uint32_t readl(const void *address) { return *(const uint32_t *)address; }
static void writel(uint32_t value, void *address) { *(uint32_t *)address = value; }
static void gph0_set(uint32_t pins, bool high) {
    data = high ? data | pins : data & ~pins;
}
static void zrn_mcu_req(int high) { gph0_set(PIN_MCU_REQ, high); }
static void gpiod_set_value(int gpio, int high) { (void)gpio; ap_sleep = high; }
'''
        checks = r'''
int main(void) {
    for (unsigned unrelated = 0; unrelated < 0x10000; unrelated++) {
        for (unsigned mode = 0; mode < 2; mode++) {
            uint32_t original = (unrelated << 12) | 0x222;
            registers[0] = original; data = 0xff; ap_sleep = 1; bitbang = mode;
            hub_pins_park();
            assert(!(data & (PIN_SCK | PIN_MOSI | PIN_CS | PIN_MCU_REQ)));
            assert(data & PIN_MISO); /* Input pin level is never driven by us. */
            assert(!ap_sleep);
            assert((registers[0] & ~0xfffU) == (original & ~0xfffU));
            if (!bitbang) {
                assert((registers[0] & 0xfffU) == 0x11);
                assert(((registers[0] >> 8) & 0xf) == 0); /* MISO stays input. */
            } else {
                assert(registers[0] == original);
            }
        }
    }
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'pins.c').write_text(code + function[0] + checks)
            subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                            str(root / 'pins.c'), '-o', str(root / 'pins-test')], check=True)
            subprocess.run([str(root / 'pins-test')], check=True)

    def test_one_hold_for_every_response_level_and_failure(self):
        source = (REPO / 'experiments/sensors/driver/zrn_bbd_board.c').read_text()
        function = re.search(r'static int hub_power_sequence\(.*?\n}\n', source, re.S)
        self.assertIsNotNone(function)
        preamble = r'''
#include <assert.h>
#include <stdbool.h>
#define ZRN_GPIO_SHUB_INT 0
#define pr_info(...) ((void)0)
static int zrn_gpios[1];
static bool response[2], supply_cut;
static unsigned int reads, calls, hold;
static int cycle_error;
static bool mcu_resp_high(void) { return response[reads++ % 2]; }
static int gpiod_get_value(int gpio) { (void)gpio; return 0; }
static int hub_cycle(unsigned int ms) { calls++; hold = ms; return cycle_error; }
'''
        checks = r'''
int main(void)
{
    for (int before = 0; before < 2; before++)
        for (int after = 0; after < 2; after++)
            for (int error = 0; error < 2; error++) {
                response[0] = before;
                response[1] = after;
                calls = reads = 0;
                cycle_error = error ? -5 : 0;
                assert(hub_power_sequence(1000) == cycle_error);
                assert(calls == 1 && hold == 1000);
            }
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'reset.c'
            path.write_text(preamble + function[0] + checks)
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-Wno-unused-variable', '-Wno-unused-function',
                            str(path), '-o', str(root / 'reset-test')], check=True)
            subprocess.run([str(root / 'reset-test')], check=True)


if __name__ == '__main__':
    unittest.main()
