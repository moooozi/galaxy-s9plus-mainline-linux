# Mobile browser and boot presentation

## Firefox

Both mobile images install `s9plus-mobile-firefox`, built from the reviewed
commit in `image/mobile/firefox-source.json`. The upstream project is
[postmarketOS mobile-config-firefox](https://docs.nura.eco/mobile-config-firefox/main/).
It adapts Firefox's toolbar, tabs, menus, built-in pages and website identification
for a narrow touchscreen. Open `about:mobile` for customization. This uses
Mozilla's normal ARM64 DEB Firefox and its normal security updates.

Only the upstream runtime is installed. Its enterprise policy file, search-engine
changes and extension installation policy are omitted. Existing profiles receive
the configuration on browser startup; no profile is replaced. After installing
or removing the package, fully quit and restart Firefox. To restore desktop UI:

```sh
sudo apt remove s9plus-mobile-firefox
```

The browser remains installed and user profiles remain intact. The package can
be built locally with `scripts/ci/install-mobile-firefox.py OUTPUT.deb`; optional
`--source CHECKOUT` requires a clean checkout at the exact locked commit.

## Ubuntu boot screen

Mobile kernel builds use the Ubuntu wordmark instead of the port author's logo.
`branding/ubuntu-logo-source.md` records the original Ubuntu asset. The Ubuntu
Plymouth spinner theme takes over in userspace; both desktops use the same theme.

The mobile kernel command line selects `quiet splash loglevel=4` and
`systemd.show_status=error`. Routine initramfs messages go to the kernel log,
and `/var/log/s9p-boot.log` still records the full boot diagnostics. Missing
storage, mount/init failure and rescue-shell errors are explicitly printed to
the console. `s9plus-boot-errors.service` watches this boot's error-priority
journal messages while Plymouth runs. On an error it hides the splash and
prints the errors to the console; it exits when Plymouth finishes or after
120 seconds. Existing driver errors can therefore still reveal text during boot.

For verbose debugging, rebuild the forced kernel command line with
`s9p_boot_debug=1 loglevel=7 systemd.show_status=yes nosplash`, removing `quiet`
and `splash`. Changing the outer Android BOOT command line alone does not override
`CONFIG_CMDLINE_FORCE=y`. Full diagnostics remain available with `journalctl -b`
and `dmesg` in normal operation.

## Display resolution options

The shared mobile kernel advertises these modes to GNOME/KDE display settings:

| Mode | Panel input | Rendered pixels relative to native |
| --- | --- | --- |
| Native WQHD+ | 1440×2960 | 100% |
| FHD+ | 1080×2220 | 56.25% |
| HD+ | 720×1480 | 25% |

Select a resolution under Settings → Displays and choose a comfortable scale.
Both mobile images initialize new users to FHD+ (1080×2220) at 250% scaling.
The kernel still advertises native as its preferred mode; the desktop initializer
selects FHD+ once and then preserves the user’s display choices. GNOME's global
`scaling-factor` stays automatic (`0`), allowing Mutter to recommend a supported
scale for each resolution: FHD+ 250%, HD+ about 167%. Forcing a global 300%
scale makes Settings submit unsupported resolution/scale combinations.
Scaling the desktop UI alone does not
provide these lower panel-input modes. HD+ is 720×1480: the vendor header's
720×1048 comment is a typo; its DSC PPS and page-address bytes encode 1480.

The driver changes the active IDMA source pitch/crop, DPP image size, blender
window/background, DSC encoder geometry, OUTFIFO, DSIM command dimensions and
Samsung's panel DSC/PPS/address/scaler sequence together. FHD buffers can have
an 1088-pixel allocation pitch while the visible image and DPP width remain 1080.
Transport clocks, lane configuration, routing and compression topology stay at
bootloader values. Lower modes are offered only when the inherited active
channel is the verified channel 0/DPP0 and its native geometry is recognized.

The mode tables retain Samsung's GPL-2.0 attribution. The encoder-table test
matches every native PPS word to an aligned read-only snapshot of the actual
phone. Another regression executes the real IDMA/DPP helper to check padded
pitch versus visible geometry. On-phone mode testing must check hardware
readback and transfer errors as well as Mutter's reported mode: a successful
DisplayConfig request alone is insufficient evidence.

Lower modes reduce rendering and framebuffer work. Actual battery-life or
power improvement has not been measured; panel emission and transport clocks
also contribute to power use. Test results and installed build details are
recorded in the installation STATUS.md outside this source repository.
