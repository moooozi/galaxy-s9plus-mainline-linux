# Experimental S9+ speaker support

User confirmed audible speaker playback on SM-G965F on 2026-11-02.
Direct ALSA and protected PipeWire playback completed without pointer stalls,
watchdog recoveries, DSP restarts or reported PipeWire errors. Automatic service
loading survived reboot. Longer playback and volume testing remain outstanding.
Microphones, headphone jack and call audio are disabled or unverified.

Driver adapted from Zerone-Laboratories/ztOS at commit
94b35c2a1f4ceb568bc0ab60f5a1acebe7cfefaf, `audio/driver/snd-zrn-abox.c`
(GPL-2.0). The checked-in driver is the actual tested adaptation: cp_vss is off,
capture is off, digital gain is capped at 0x30, bottom analogue gain is 0x03,
and boost is 0x10. Full Maxim DSM speaker protection is not implemented;
retain these limits and the supplied crossover, high-pass and limiter chain.
Do not expose the raw ALSA sink as the normal desktop output.

## Build from the existing exact kernel

In the original cross-build container, with this repository mounted at /work:

```sh
cd /work
mkdir -p .build/audio-work/driver
cp experiments/audio/driver/Makefile experiments/audio/driver/snd-zrn-abox.c .build/audio-work/driver/
bash experiments/audio/build-modules.sh
```

Requires `.build/src/mainline/out` from the original 7.1.0-dirty build,
including Module.symvers and vmlinux.o, and its GCC 13.3.0 ARM64 cross compiler.
Output: seven modules under `.build/audio-work/modules`. No BOOT rebuild.
Verify vermagic against the target kernel before installing.

## Install on the target

Use `/usr/lib/modules/7.1.0-dirty/extra/s9plus-audio/` for those seven modules,
then run `depmod -a 7.1.0-dirty`. Install Ubuntu packages `alsa-utils`,
`lsp-plugins-ladspa`, `rtkit` and their dependencies. The limiter path used
by the tested Ubuntu package is `/usr/lib/ladspa/lsp-plugins-ladspa.so`.
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
The `s9plus-speaker` protected output should be the default sink.
The loader retains `/var/lib/s9plus-audio/loading` after an interrupted load;
inspect the previous boot logs before clearing it manually. No retries are
automatically forced after a failed initialization.
