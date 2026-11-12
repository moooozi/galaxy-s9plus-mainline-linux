# MAX77705 charging control on star2lte

On 2026-11-02, the installed 7.3.1 driver accepted `inhibit-charge` while
charging continued. Its control used CNFG_09 bit 7 (input-current control),
leaving CNFG_00 MODE=5, buck + charger. The fuel gauge reported Full at 100%,
but that is based on learned capacity and did not establish charger termination.

The corrected driver changes only CNFG_00's CHG bit: mode 5 becomes mode 4
(buck only), retaining USB power and every other mode/configuration bit.
`auto` sets that charging bit again. Status, charge type and charge behaviour
now read the actual mode; inhibited status uses STATUS_NOT_CHARGING rather than
the unrelated CHARGE_TYPE_NONE enum. Register access errors are propagated by
the control and mode-reporting paths. Probe retains the existing CNFG_09
input-current control selection separately.

This matches the mode transition in Samsung's MAX77705 driver:
https://github.com/ianmacd/d2s/blob/master/drivers/battery_v2/max77705_charger.c
(`max77705_chg_set_mode_state`, CHARGING_OFF from MODE_5_BUCK_CHG_ON).

## Evidence and limits

- Before stopping, the battery was about 4.24–4.25 V, 32 °C, with sustained
  positive charging current despite sysfs inhibit. There was no measured
  overvoltage or high battery temperature during these observations.
- A guarded one-shot test on the physical phone changed only CNFG_00 0x05 to
  0x04. Over the next 30 seconds, current fell to roughly -8 to +5 mA;
  the average decayed toward zero. USB networking remained operational.
- The corrected driver compiles against the installed kernel source/config.
  A compiled C regression harness exercises its actual helper functions against
  a simulated register map, testing all 256 original byte values, stop/resume,
  disabled/full/charging status, and control/read failures.
- **The corrected kernel booted with the GNOME Mobile image on 2026-11-02.**
  Writing sysfs `inhibit-charge` changed MODE to 4, reported Not charging and
  stopped positive net charging current. This verifies deployed stop control.
- **Autonomous end-of-charge termination has not been observed.** The gauge's
  Full label and a successful forced stop are not proof of autonomous cutoff.
  Existing CV 4.4 V, top-off 150 mA/30 minutes and disabled fast-charge timer
  were not changed by this fix; this is not a validation of those settings for
  every physical battery, including replacement batteries.
- A manual inhibit is volatile. Driver probe/reboot enables charging again;
  there is no installed persistent charge limiter. Do not assume the phone
  remains inhibited after reboot or reconnect/reinitialization.

With the corrected kernel, request a stop through
`/sys/class/power_supply/max77705-charger/charge_behaviour` by writing
`inhibit-charge` as root. Verify battery current and charger status rather than
relying on capacity alone. Writing `auto` resumes the existing charging policy.

## Driver review on 2026-11-12

The AICL current-reduction loop now stops at the 100 mA hardware minimum and
has a finite iteration bound even if another writer keeps raising the limit.
It previously could underflow the unsigned field and wrap back to a high
input-current setting. Current setters now use the input field's `(code+1)`
encoding and clamp the six-bit charge-current field to 3.15 A, preventing a
3.2 A request from wrapping to code zero. These bounds describe register
encoding; they are not a recommendation to increase charging current.

Property getters propagate register-read failures, prequalification reports
defined battery health, and initialization fails if float-voltage or watchdog
configuration writes fail. The existing charge-inhibit mode transition is
unchanged. Host C regressions exercise the real functions against simulated
registers, including every integer request in the supported current ranges,
field limits, stuck AICL and bus errors. New hardware validation is recorded
separately in the session status; these simulations do not establish physical
charge termination or a persistent capacity limit.
