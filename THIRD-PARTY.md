# Third-party components

| Component | Where | Origin | Licence |
|---|---|---|---|
| uniLoader | `bootloader/uniLoader/` | https://github.com/ivoszbg/uniLoader, plus this port's `configs/star2lte_defconfig` | see `bootloader/uniLoader/LICENSE` |
| Samsung UFS PHY calibration | `src/ufs/ufs-cal-9810.[ch]` | Samsung Exynos9810 vendor kernel, unchanged | GPL-2.0 |
| MAX77705 charger driver | `src/soc/max77705_charger.c` | mainline Linux v7.1 (Dzmitry Sankouski), with this port's `charge_behaviour` addition | GPL-2.0 |
| Pinned upstream copy of that driver | `src/reference/max77705_charger.c` | torvalds/linux v7.1, unmodified | GPL-2.0 |
| `exynos-bootfb.c` | generated at build time | `drivers/gpu/drm/sysfb/simpledrm.c` from the kernel tree being built, with `DRIVER_NAME` renamed | GPL-2.0 |
| BCM4361 firmware, NVRAM, CLM blob, Bluetooth patchram | `firmware/`, `device/base/lib/firmware/brcm/` | Samsung SM-G965F stock firmware | Broadcom, redistributed as shipped on the device; not GPL |
| `regulatory.db`, `regulatory.db.p7s` | `firmware/` | `wireless-regdb` | ISC |
| TWRP 3.3.1-0 for star2lte | not in this repository | https://twrp.me | its own terms |
| Boot logo | `branding/shero_logo.ppm` | this project (`scripts/build/make_logo.py`) | GPL-2.0 |

The firmware blobs are device firmware, not part of the kernel's own source.
They are included so `WLAN=1` builds do not race a firmware loader at boot.

## Mobile build additions

- S6E3HA8 corner-mask image: Samsung GPL-2.0 panel source, with original notice
  retained in `src/gpu/drm/s9p/s9p-panel-self-mask.h`.
  Provenance and verified commands are in `docs/panel-sleep-wake.md`.
- Experimental ABOX and Bluetooth board drivers: Zerone-Laboratories/ztOS at
  `94b35c2a1f4ceb568bc0ab60f5a1acebe7cfefaf`, GPL-2.0; local adaptations are
  documented in `experiments/audio` and `experiments/bluetooth`.
- GNOME Mobile Shell and Mutter: GPL-2.0-or-later; Settings Daemon also contains
  LGPL components. Source/license notices are retained in the corresponding
  source archives. Exact fork URLs, commits and Ubuntu packaging versions are
  recorded in `image/gnome-mobile/sources.json`. These sources are fetched at
  build time; binary package artifacts include their corresponding source.
- Owner-specific Calliope audio firmware and Bluetooth identity are not
  distributed in public images. Existing board Wi-Fi/Bluetooth firmware remains
  subject to the firmware attribution above.
- BCM4773 transport and conservative Exynos9810 C2/MCT idle implementation:
  Zerone-Laboratories/ztOS at `7f42ddc3ba468e4e21c7145cbb973f5aa57d5358`.
  Kernel files retain GPL-2.0/vendor notices; sensor userspace derivatives use
  GPL-3.0-only. Original file hashes, adaptations and firmware provenance are in
  `experiments/sensors/SOURCE.md`, `experiments/cpuidle/SOURCE.md` and their
  `upstream.json` manifests. Embedded Broadcom sensor patch headers come from
  the vendor kernel; the proprietary Android runtime and `lhd` are not bundled.
