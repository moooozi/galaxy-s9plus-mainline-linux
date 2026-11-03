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
