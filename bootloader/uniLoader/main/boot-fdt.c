// SPDX-License-Identifier: GPL-2.0-only
/*
 * Copyright (c) 2026, Igor Belwon <igor.belwon@mentallysanemainliners.org>
 */

#include <drivers/ramdisk-handler.h>
#include <lib/debug.h>
#include <lib/libfdt/libfdt.h>

unsigned long s9plus_boot_fdt_address;

static char fdt_buf[CONFIG_FDT_BUF_SIZE];

void patch_dtb(void** dt)
{
	int ret;

	ret = ramdisk_handler_patch_dtb(*dt, &fdt_buf, sizeof(fdt_buf));
	if (ret != 0)
		printk(KERN_ERR, "failed to patch dtb\n");
	else {
#ifdef CONFIG_EXYNOS_9810
		int node = fdt_path_offset(&fdt_buf, "/chosen");
		ret = fdt_setprop_u64(&fdt_buf, node, "s9plus,sboot-fdt-address",
				     s9plus_boot_fdt_address);
		if (ret) printk(KERN_ERR, "S9P failed to save boot address: %d\n", ret);
#endif
		*dt = &fdt_buf;
	}
}
