# Galaxy S9+ direction — 2026-11-12

User-approved direction, superseding the Ubuntu image roadmap:

- Switch to Debian and postmarketOS.
- Maintain two kernel variants: full and embedding.
- Produce three images: postmarketOS with Plasma Mobile, postmarketOS with
  Phosh, and vanilla Debian without a desktop using the embedding kernel and
  a preconfigured SSH tunnel.
- Move kernel releases into a separate repository with GitHub Actions building
  both variants and GitHub Pages hosting the package repository.
- Trigger kernel builds for new 7.3.x patches. Move to 7.4.x at the first stable
  7.4 release. Do not support 7.5.x or subsequent series.
- Image builds consume released kernels from that repository rather than
  compiling them. Configure the package repository in each image so normal
  system updates deliver kernel patches.
- The embedding kernel excludes audio, Bluetooth, display and other drivers
  unnecessary for server workloads. It has a 65% charging limit. Consult the
  LineageOS 24 sources for charging-limit and fast-charging support as needed.

Immediate priority: repair, test and integrate the existing kernel drivers,
then push the validated changes before implementing the image/repository split.
Keep the existing installed system available for hardware validation meanwhile.

Details to settle during the later image work: kernel repository identity,
Debian release, SSH tunnel destination/authentication, and whether the 65%
limit also applies to the full variant. Do not embed private SSH keys in a
public image.
