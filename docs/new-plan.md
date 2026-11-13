# Galaxy S9+ direction — 2026-11-12

User-approved direction, superseding the Ubuntu image roadmap:

- Switch to Debian and postmarketOS.
- Maintain two kernel variants: full and embedding.
- Produce three images: postmarketOS with Plasma Mobile, postmarketOS with
  Phosh, and vanilla Debian without a desktop using the embedding kernel and
  an enabled SSH server (clarified: no reverse SSH tunnel).
- Move kernel releases into a separate repository with GitHub Actions building
  both variants and GitHub Pages hosting the package repository.
- Trigger kernel builds for new supported 7.3.x patches only. Stay on 7.3;
  do not switch to 7.4 or later. Stop automatic selection if 7.3 reaches EOL.
- Image builds consume released kernels from that repository rather than
  compiling them. Configure the package repository in each image so normal
  system updates deliver kernel patches.
- The embedding kernel excludes audio, Bluetooth, display and other drivers
  unnecessary for server workloads. It defaults to a configurable 65% charging limit. Consult the
  LineageOS 24 sources for charging-limit and fast-charging support as needed.

Immediate priority: repair, test and integrate the existing kernel drivers,
then push the validated changes before implementing the image/repository split.
Keep the existing installed system available for hardware validation meanwhile.

Decisions confirmed during the split:

- Kernel repository: `moooozi/galaxy-s9plus-kernel`.
- Headless distribution: Debian 13 (trixie).
- Enable sshd, use DHCP, and allow offline username/public-key configuration.
  Unconfigured Debian images use `debian` / `debian`, with a required password
  change at first login. Generate SSH host keys per device; include no private
  SSH keys or reverse-tunnel credentials in public images.
- Embedding defaults to stop/resume at 65/63%; full defaults to no added limit.
  Both expose configurable preservation settings, persisted by userspace.
- postmarketOS targets v26.06 (Alpine v3.24), with systemd for the existing
  guarded CPU/sensor runtime.

Implementation/build evidence and installation instructions are in
[new-images.md](new-images.md). Local build checks do not establish new-device
hardware validation. Keep the installed Ubuntu test system available.
