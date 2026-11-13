The Plymouth Samsung artwork comes from `logo.jpg` in this phone's original
UP_PARAM partition, copied read-only on 2026-11-03. Samsung branding belongs to
Samsung. No firmware partition was modified.

On 2026-11-13, the existing 1079x1747 PNG was cropped to its non-black bounding
box (48, 48, 1032, 344), producing a 984x296 `samsung-boot-logo.png`. This removes
the surrounding black margins and the long empty lower canvas. Every retained
pixel is unchanged; every discarded pixel was black. No image generation,
redrawing, resampling or JPEG recompression was used. Knox and Android branding
remain excluded.

Plymouth displays the cropped image at 75% of the display width, centered
horizontally, with its center at 42% of screen height. Placement is handled by
the theme rather than black image padding.
Ubuntu's packaged spinner watermark remains centered near the bottom with its
existing placement. The source overlay includes the same relative symlink used
on the phone: `ubuntu-wordmark.png -> ../spinner/watermark.png`.
This userspace theme adds no EFI/BGRT support. The new crop is source-only until
the theme is installed; no phone changes or reboot were performed in this step.
