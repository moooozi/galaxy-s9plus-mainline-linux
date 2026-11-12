# CPU idle source and scope

Adapted from `power/idle/zrn-idle.c` in
[ztOS at 7f42ddc](https://github.com/Zerone-Laboratories/ztOS/tree/7f42ddc3ba468e4e21c7145cbb973f5aa57d5358/power/idle).
Original source hashes are recorded in `upstream.json`. Kernel source retains
its GPL-2.0 licence.

Retained: Samsung flexible-PMU core hints/wake lines, legacy PSCI core-powerdown
finisher with explicit physical `cpu_resume`, MPIDR decoding, and the MCT G0
broadcast clockevent with late-deadline detection.

Removed: SICD, cluster powerdown, big-core idle, system suspend entry callbacks,
hardware wake-alarm experiments, resume diagnostics, and unrelated BT/GIC debug
register mappings. Only A55 CPUs 2 and 3 are accepted, even when called directly
with module parameters. No failed DT idle state is enabled.

The separate `patch-suspend-hash.py` corrects the arm64 suspend hash on star2lte.
This is an original port fix, not part of the imported ztOS module. The measured
A55 MPIDRs have MT set and the core in Aff1; firmware/DT IDs compact that core
number into Aff0. M3 uses the DT affinity layout directly. The patch shifts MT
identities before the original hash on both save and resume, with a board flag
stored in the hash metadata. Other boards use the original path. It does not
alter firmware CPU IDs, CPU topology, enable masks or system-suspend policy.
`verify-suspend-hash.py` executes the actual patched assembly macros under
qemu-user using all eight measured raw MPIDRs, testing distinct slots and the
unchanged other-board path. It requires the cross compiler and qemu-aarch64-static.

A registered clockevent cannot be safely unregistered through this module's
API. The module pins itself after clockevent registration and is intentionally
not unloadable; reboot is the rollback for a running test. A failed cpuidle
registration leaves the valid broadcast device pinned and reports failure in
the journal; the loader's counter checks reject it as usable C2.

## Built-in integration (November 12)

`src/cpuidle/` is the current Kconfig/Kbuild driver. The historical imported
module is retained under `experiments/cpuidle/driver/`, but is not compiled or
packaged by current pipelines. Direct `cpu_suspend`/`cpu_resume` references
replace private-address module parameters without exporting architecture
symbols. C2 is initially off; the durable userspace guard enables only the
validated CPUs2/3 and requires fresh C2 and G0 progress before confirmation.
The timer clears inherited comparator state before IRQ installation, pins its
IRQ to CPU0 with balancing disabled, and checks synchronized MMIO write status.
These changes do not widen the CPU mask or implement system/cluster suspend.
