# Experimental S9+ speaker and headphone support

User confirmed audible speaker playback on SM-G965F on 2026-11-02.
Direct ALSA and protected PipeWire playback completed without pointer stalls,
watchdog recoveries, DSP restarts or reported PipeWire errors. Automatic service
loading survived reboot. Longer playback and volume testing remain outstanding.
Headphone playback was user-confirmed on 2026-11-03 after bringing up the
CS47L93 codec and applying its DAC volume-update bits. Microphone capture is
disabled in the supported configuration; call audio is unsupported.

On 2026-11-03 the user also confirmed the capped headphone volume and automatic
speaker/headphone switching on unplug/replug, followed by manual selection of
Speakers with headphones connected using the standard desktop ports. The capped module was installed
for kernel 7.3.1-s9plus and reloaded successfully from its installed path;
full reboot validation of this updated module remains outstanding.

Driver adapted from Zerone-Laboratories/ztOS at commit
94b35c2a1f4ceb568bc0ab60f5a1acebe7cfefaf, `audio/driver/snd-zrn-abox.c`
(GPL-2.0). The checked-in driver is the actual tested adaptation: cp_vss is off,
capture is off, digital gain is capped at 0x30, bottom analogue gain is 0x03,
and boost is 0x10. Full Maxim DSM speaker protection is not implemented;
retain these driver gain limits. The software crossover/high-pass/limiter
was removed at the user’s request after poor sound and duplicate outputs were
reported. The built-in ALSA speaker sink is the normal desktop output.

## Build from the existing exact kernel

In the original cross-build container, with this repository mounted at /work:

```sh
cd /work
mkdir -p .build/audio-work/driver
cp experiments/audio/driver/* .build/audio-work/driver/
bash experiments/audio/build-modules.sh
```

Requires `.build/src/mainline/out` from the original 7.1.0-dirty build,
including Module.symvers and vmlinux.o, and its GCC 13.3.0 ARM64 cross compiler.
Output: seven modules under `.build/audio-work/modules`. No BOOT rebuild.
Verify vermagic against the target kernel before installing.

## Install on the target

Use `/usr/lib/modules/7.1.0-dirty/extra/s9plus-audio/` for those seven modules,
then run `depmod -a 7.1.0-dirty`. Install Ubuntu packages `alsa-utils`,
`rtkit` and their dependencies. For newer kernels, build against the exact
running kernel and use its module directory; do not mix module ABIs. The tested
7.3.1-s9plus install replaced only `snd-zrn-abox.ko`, retaining its matching
installed ALSA/I2C dependencies.
Supply `calliope_sram.bin`, `calliope_dram.bin`, `calliope_iva.bin` from the
owner's phone VENDOR partition to `/usr/lib/firmware/`; firmware is not included.
Copy the rootfs overlay preserving `/lib -> usr/lib`, with root ownership:

```sh
# Run on the target, from this directory after transferring the source files.
tar -C rootfs --owner=0 --group=0 -cf - . | tar -C / --keep-directory-symlink --no-same-owner --no-overwrite-dir -xpf -
systemctl daemon-reload
systemctl enable --now s9plus-audio.service
```

Restart the desktop PipeWire/WirePlumber services to pick up the configs.
Use the built-in speaker output. No virtual speaker filter is installed.
The loader retains `/var/lib/s9plus-audio/loading` after an interrupted load;
inspect the previous boot logs before clearing it manually. No retries are
automatically forced after a failed initialization.

## Headphone gain ceiling

Headphone DAC gain is capped at **-30 dB**, code68 (0.5 dB steps from-64dB).
This corresponds to the user's accepted old40% setting: the old-18dB DAC
combined with measured PipeWire amplitude0.254788 gives-29.876dB. The new
ceiling rounds down to the next0.5dB step.

The cap is in `s9plus-headphone-limit.h` and applied by `codec_write` to both
headphone DAC registers. It preserves mute/update bits. Startup, reinsertion,
ALSA mixer changes and direct PCM playback all share this guard. The maximum
is not a module parameter. The test suite exercises every16-bit write value
and verifies unrelated codec registers are unchanged.

The WirePlumber overlay uses software volume so the headphone route does not
inherit speaker-mixer gain compensation. This configuration is not the gain
ceiling: the kernel's DAC guard remains active when the sound server is absent.
Both mobile image builds compile this same driver and include the same overlay.

The device-specific `s9plus.conf` ALSA card profile exposes standard Speakers
and Headphones ports on the shared PCM. The driver reports `Headphone Jack`
and provides independent `Speaker Playback Switch` and `Headphone Playback
Switch` controls. WirePlumber's existing policy handles automatic switching,
manual port selection and per-port volume memory. Speakers remain selectable
with headphones connected; the driver no longer forces headphones on insertion.
No custom switching daemon or desktop policy is needed.

The two mixer paths fix headphone gain at 68 and speaker gain at 48 (the existing
driver maximum), leaving desktop volume and mute in software. Generic path
probing can zero the headphone gain even with `api.alsa.soft-mixer = true`, so
these hardware-specific gain declarations remain necessary. Port changes only
gate/mute outputs; already initialized headphone clocks are retained. Custom UCM
files from the earlier experiment are unnecessary; UCM is disabled for this card.

Use `Headphone Playback Volume` for direct ALSA volume changes; its maximum
is68 (-30dB). `Headphone Jack` exposes insertion state. The desktop selects
the output using the standard playback switches. Capture and voice paths
must stay disabled in this profile. Playback loudness still varies with source
material and headphones; the ceiling is a relative hardware gain bound.
