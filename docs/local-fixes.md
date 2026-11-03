# Fixes preserved from the installed SM-G965F

Fifteen logical fixes were identified in the installation notes on 2026-11-02.
The count groups paired settings corrections and hardware bring-up work by
user-visible outcome; build-output ignore rules are additional housekeeping.

1. Reject mounted USERDATA by device number and propagate e2fsck failures.
2. Use recursive /dev binding and slave propagation for rootless image builds.
3. Select Plasma Mobile with GDM 51 FallbackSession, without a .desktop suffix.
4. Normalize display-manager.service to the canonical gdm.service unit.
5. Disable the competing Plasma Mobile direct TTY login service.
6. Install and boot-load the matching FUSE module for document portals.
7. Type the empty dconf extension array as @as [].
8. Initialize Plasma display scale and the packaged virtual keyboard.
9. Install omitted Plasma Mobile dependencies, including plasma-open-settings.
10. Repair outdated Night Color and virtual keyboard quick-setting module names.
11. Bring up speaker playback with matching ABOX modules and protected PipeWire output.
12. Bring up the Bluetooth controller, discovery and ordered automatic startup.
13. Restore S6E3HA8 side RAM and the rounded-corner mask after real panel sleep.
14. Control MAX77705 charging through its actual MODE charge bit and correct inhibited status.
    Corrected kernel booted; sysfs inhibit and hardware mode stop verified; see charging.md.
15. Complete GNOME Mobile runtime typelibs/integration and accept an already active scale 3.
    GNOME Wayland/Panfrost verified; the owner confirmed the visible shell. Touch/keyboard confirmation pending.

16. Repair GNOME Mobile lock interfaces and explicit locking; add short/long power
    handling and opt-in double-tap wake. The Shell repair is runtime-tested on the
    phone; the native Settings Daemon/Mutter candidates compile and their gesture
    tests pass. ARM64 deployment and physical tests remain required.

The Ubuntu 26.10 profile is under image/ubuntu-26.10. Experimental audio and
Bluetooth sources are under experiments, with firmware supplied by the owner.
Panel provenance and verification are documented in panel-sleep-wake.md.
These sources preserve the tested installation, but importing them does not
regenerate the existing rootfs image or reconfigure the installed phone.
Touch/keyboard interaction, Bluetooth pairing/audio, longer speaker playback,
microphones, headphone/call audio and suspend need further validation or work.
