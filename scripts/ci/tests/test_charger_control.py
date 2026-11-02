"""Exercise the real driver control helpers against a simulated register map."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[3]


class ChargerControl(unittest.TestCase):
    def test_hardware_mode_and_error_paths(self):
        source = (REPO / 'src/soc/max77705_charger.c').read_text()
        names = ('max77705_set_charging', 'max77705_get_charging',
                 'max77705_get_charge_type', 'max77705_get_status')
        functions = []
        for name in names:
            match = re.search(r'static int ' + name + r'\(.*?\n}\n', source, re.S)
            self.assertIsNotNone(match, name)
            functions.append(match[0])
        preamble = r'''
#include <assert.h>
#include <stdbool.h>
#define MAX77705_CHG_REG_CNFG_00 7
#define MAX77705_CHG_REG_DETAILS_01 4
#define MAX77705_CHG_MASK 1
#define MAX77705_CHG_DTLS 15
#define MAX77705_CHARGER_CONSTANT_CURRENT 1
#define MAX77705_CHARGER_CONSTANT_VOLTAGE 2
#define MAX77705_CHARGER_END_OF_CHARGE 3
#define MAX77705_CHARGER_DONE 4
enum { POWER_SUPPLY_STATUS_UNKNOWN, POWER_SUPPLY_STATUS_CHARGING,
       POWER_SUPPLY_STATUS_DISCHARGING, POWER_SUPPLY_STATUS_NOT_CHARGING,
       POWER_SUPPLY_STATUS_FULL };
enum { POWER_SUPPLY_CHARGE_TYPE_NONE = 10, POWER_SUPPLY_CHARGE_TYPE_FAST };
struct regmap { unsigned int registers[32]; int error; };
struct max77705_charger_data { struct regmap *regmap; };
static int regmap_read(struct regmap *map, int reg, unsigned int *value)
{
    if (map->error) return map->error;
    *value = map->registers[reg];
    return 0;
}
static int regmap_update_bits(struct regmap *map, int reg, unsigned int mask,
                              unsigned int value)
{
    if (map->error) return map->error;
    map->registers[reg] = (map->registers[reg] & ~mask) | (value & mask);
    return 0;
}
'''
        checks = r'''
int main(void)
{
    struct regmap map = {0};
    struct max77705_charger_data chg = { &map };
    unsigned int enabled;
    int value;
    /* Exercise every combination, including buck, OTG and watchdog bits. */
    for (unsigned int mode = 0; mode < 256; mode++) {
        map.registers[7] = mode;
        assert(max77705_set_charging(&chg, false) == 0);
        assert(map.registers[7] == (mode & ~1U));
        assert(max77705_get_charging(&chg, &enabled) == 0 && !enabled);
        assert(max77705_get_status(&chg, &value) == 0);
        assert(value == POWER_SUPPLY_STATUS_NOT_CHARGING);
        assert(max77705_get_charge_type(&chg, &value) == 0);
        assert(value == POWER_SUPPLY_CHARGE_TYPE_NONE);
        assert(max77705_set_charging(&chg, true) == 0);
        assert(map.registers[7] == (mode | 1U));
        assert(max77705_get_charging(&chg, &enabled) == 0 && enabled);
    }
    map.registers[4] = 1;
    assert(max77705_get_status(&chg, &value) == 0);
    assert(value == POWER_SUPPLY_STATUS_CHARGING);
    map.registers[4] = 4;
    assert(max77705_get_status(&chg, &value) == 0);
    assert(value == POWER_SUPPLY_STATUS_FULL);
    map.error = -5;
    assert(max77705_set_charging(&chg, false) == -5);
    assert(max77705_get_charging(&chg, &enabled) == -5);
    assert(max77705_get_status(&chg, &value) == -5);
    assert(max77705_get_charge_type(&chg, &value) == -5);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'charger.c'
            path.write_text(preamble + '\n'.join(functions) + checks)
            executable = root / 'charger-test'
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            str(path), '-o', str(executable)], check=True)
            subprocess.run([str(executable)], check=True)


if __name__ == '__main__':
    unittest.main()
