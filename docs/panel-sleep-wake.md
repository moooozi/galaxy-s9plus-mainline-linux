# S6E3HA8 sleep/wake repair

Verified on SM-G965F / star2lte on 2026-11-02, kernel 7.1.0-dirty.
Real panel sleep is enabled; no no-sleep override is required. User confirmed
that the top/bottom corruption disappeared after physical power-button testing.

Wake now initializes side RAM (77 00 00, 34 ms), selects side RAM (75 10),
reloads the 3552-byte rounded-corner mask in eight aligned packets, and enables
it before display-on. Level-1 keys guard display/sleep commands. Commands
run with TE masked and DECON idle, with FIFO completion and power-mode reads.
Repeated cycles reported power mode 08 asleep and 9d awake without timeouts.

Mask image and command provenance: Samsung GPL-2.0 panel source from
LineageOS/android_kernel_samsung_universal9810 at
5a2dd7d6f3a05168d2f1303c3b29e9e9fa39b781, under
`drivers/video/fbdev/exynos/panel/s6e3ha8/`. Side-RAM initialization also
verified against ExyHyperBrick/android_kernel_samsung_exynos9810 at
88be11c7ef295f9ca5d9249aacc6724781196b7e, matching the phone's Android kernel.
The embedded image matched the backed-up Android kernel byte for byte.
Copyright and license are retained in s9p-panel-self-mask.h.

The normal driver build installs the driver and its new header together.
`scripts/build/build-display-kernel.sh` preserves the exact installed config
and DTB when repackaging an existing local build. It is a resume helper: it
requires an isolated `.build/display-work/src` source/output copy, the original
`.build/src/mainline/out/.config`, and original uniLoader artifacts under dist.
Run inside the cross-build container with the repository mounted at /work.
It does not flash. Installed candidate SHA256:
e76e23770a100b757ce38ca28046e43c0ba7d8dcc3b688e4d5f2b8680af547ee.
