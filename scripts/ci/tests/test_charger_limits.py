"""Execute charger helpers with register failures and current-limit boundaries."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[3]


class ChargerLimits(unittest.TestCase):
    def test_current_encoding_aicl_and_read_failures(self):
        source = (REPO / 'src/soc/max77705_charger.c').read_text()
        names = ('max77705_aicl_irq', 'max77705_set_current',
                 'max77705_check_battery', 'max77705_get_battery_health',
                 'max77705_get_input_current', 'max77705_get_charge_current',
                 'max77705_get_float_voltage')
        functions = []
        for name in names:
            match = re.search(r'static (?:int|irqreturn_t) ' + name + r'\(.*?\n}\n', source, re.S)
            self.assertIsNotNone(match, name)
            functions.append(match[0])
        preamble = r'''
#include <assert.h>
#include <limits.h>
#include <stdbool.h>
#include <errno.h>
#define BIT(n) (1U << (n))
#define clamp_val(v, lo, hi) ((v) < (lo) ? (lo) : (v) > (hi) ? (hi) : (v))
#define dev_dbg(...) ((void)0)
#define MAX77705_CHG_REG_INT_OK 0
#define MAX77705_CHG_REG_DETAILS_00 1
#define MAX77705_CHG_REG_DETAILS_01 2
#define MAX77705_AICL_I 7
#define MAX77705_BATP_OK BIT(2)
#define MAX77705_BATP_DTLS BIT(0)
#define MAX77705_BAT_DTLS 0x70
#define MAX77705_BAT_DTLS_SHIFT 4
#define MAX77705_CURRENT_CHGIN_MIN 100000
#define MAX77705_CURRENT_CHGIN_MAX 3200000
#define MAX77705_CURRENT_CHGIN_STEP 25000
#define MAX77705_CURRENT_CHG_STEP 50000
#define AICL_WORK_DELAY_MS 100
#define IRQ_HANDLED 1
typedef int irqreturn_t;
enum max77705_field_idx { MAX77705_CHG_CHGIN_LIM, MAX77705_CHG_CC_LIM,
                          MAX77705_CHG_CV_PRM };
enum { MAX77705_BATTERY_NOBAT, MAX77705_BATTERY_PREQUALIFICATION,
       MAX77705_BATTERY_DEAD, MAX77705_BATTERY_GOOD,
       MAX77705_BATTERY_LOWVOLTAGE, MAX77705_BATTERY_OVERVOLTAGE };
enum { POWER_SUPPLY_HEALTH_NO_BATTERY, POWER_SUPPLY_HEALTH_DEAD,
       POWER_SUPPLY_HEALTH_GOOD, POWER_SUPPLY_HEALTH_OVERVOLTAGE,
       POWER_SUPPLY_HEALTH_UNSPEC_FAILURE };
struct regmap { unsigned int reg[3]; int fail_reg; };
struct regmap_field { unsigned int value, mask; int error; };
struct max77705_charger_data {
    struct regmap *regmap;
    struct regmap_field *rfield[3];
};
static unsigned int reads, writes, sleeps;
static bool external_writer;
static int regmap_read(struct regmap *map, int reg, unsigned int *value)
{
    if (map->fail_reg == reg) return -EIO;
    *value = map->reg[reg];
    return 0;
}
static int regmap_field_read(struct regmap_field *field, unsigned int *value)
{
    reads++;
    if (field->error) return field->error;
    *value = field->value;
    return 0;
}
static int regmap_field_write(struct regmap_field *field, unsigned int value)
{
    writes++;
    if (field->error) return field->error;
    /* Model real field masking, including its otherwise dangerous wrap. */
    field->value = external_writer ? 127 : value & field->mask;
    return 0;
}
static void msleep(unsigned int ms) { assert(ms == 100); sleeps++; }
'''
        checks = r'''
int main(void)
{
    struct regmap map = { .fail_reg = -1 };
    struct regmap_field input = { .mask = 127 }, charge = { .mask = 63 },
                        voltage = { .mask = 63 };
    struct max77705_charger_data chg = { &map, { &input, &charge, &voltage } };
    int value;
    /* Input-current requests never round up beyond the requested current. */
    for (int ua = 100000; ua <= 3200000; ua++) {
        assert(max77705_set_current(&chg, MAX77705_CHG_CHGIN_LIM, ua) == 0);
        assert(max77705_get_input_current(&chg, &value) == 0);
        assert(value <= ua && ua - value < 25000);
    }
    for (int ua = 100000; ua <= 3150000; ua++) {
        assert(max77705_set_current(&chg, MAX77705_CHG_CC_LIM, ua) == 0);
        assert(max77705_get_charge_current(&chg, &value) == 0);
        assert(value <= ua && ua - value < 50000);
    }
    assert(max77705_set_current(&chg, MAX77705_CHG_CHGIN_LIM, INT_MAX) == 0);
    assert(input.value == 127);
    assert(max77705_set_current(&chg, MAX77705_CHG_CHGIN_LIM, INT_MIN) == 0);
    assert(input.value == 3);
    assert(max77705_set_current(&chg, MAX77705_CHG_CC_LIM, 3200000) == 0);
    assert(charge.value == 63);
    assert(max77705_set_current(&chg, MAX77705_CHG_CC_LIM, INT_MIN) == 0);
    assert(charge.value == 2);
    assert(max77705_set_current(&chg, MAX77705_CHG_CV_PRM, 100000) == -EINVAL);

    /* A stuck-low AICL indication reaches 100 mA, never wraps to 3.2 A. */
    input.value = 127;
    writes = sleeps = reads = 0;
    assert(max77705_aicl_irq(0, &chg) == IRQ_HANDLED);
    assert(input.value == 3 && writes == 124 && sleeps == 124);
    for (unsigned int minimum = 0; minimum <= 3; minimum++) {
        input.value = minimum;
        writes = 0;
        max77705_aicl_irq(0, &chg);
        assert(input.value == minimum && writes == 0);
    }
    /* Concurrent limit increases cannot keep the threaded IRQ alive forever. */
    external_writer = true;
    input.value = 127;
    writes = sleeps = 0;
    max77705_aicl_irq(0, &chg);
    assert(writes == 128 && sleeps == 128);
    external_writer = false;
    map.reg[0] = BIT(7);
    writes = 0;
    max77705_aicl_irq(0, &chg);
    assert(writes == 0);

    /* Register failures preserve the caller's output and propagate errno. */
    value = 12345;
    map.fail_reg = 0;
    assert(max77705_check_battery(&chg, &value) == -EIO && value == 12345);
    map.fail_reg = 1;
    assert(max77705_check_battery(&chg, &value) == -EIO && value == 12345);
    map.fail_reg = 2;
    assert(max77705_get_battery_health(&chg, &value) == -EIO && value == 12345);
    map.fail_reg = -1;
    map.reg[2] = MAX77705_BATTERY_PREQUALIFICATION << 4;
    assert(max77705_get_battery_health(&chg, &value) == 0);
    assert(value == POWER_SUPPLY_HEALTH_GOOD);
    value = 12345;
    input.error = charge.error = voltage.error = -EIO;
    assert(max77705_get_input_current(&chg, &value) == -EIO && value == 12345);
    assert(max77705_get_charge_current(&chg, &value) == -EIO && value == 12345);
    assert(max77705_get_float_voltage(&chg, &value) == -EIO && value == 12345);
    assert(max77705_set_current(&chg, MAX77705_CHG_CHGIN_LIM, 500000) == -EIO);
    assert(max77705_set_current(&chg, MAX77705_CHG_CC_LIM, 500000) == -EIO);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'charger.c'
            path.write_text(preamble + '\n'.join(functions) + checks)
            executable = root / 'charger-test'
            subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                            '-Wno-unused-parameter', str(path), '-o', str(executable)], check=True)
            subprocess.run([str(executable)], check=True)


if __name__ == '__main__':
    unittest.main()
