// SPDX-License-Identifier: GPL-2.0
/* Read CPU identities on each online CPU. No PMU, timer or policy writes. */
#include <linux/cpu.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/smp.h>
#include <asm/cputype.h>

static void audit_cpu(void *unused)
{
	pr_info("s9plus-mpidr-audit: cpu=%u mpidr=%#llx midr=%#x\n",
		smp_processor_id(), read_cpuid_mpidr(), read_cpuid_id());
}

static int __init audit_init(void)
{
	if (!of_machine_is_compatible("samsung,star2lte"))
		return -ENODEV;
	cpus_read_lock();
	on_each_cpu(audit_cpu, NULL, 1);
	cpus_read_unlock();
	return 0;
}

static void __exit audit_exit(void) {}
module_init(audit_init);
module_exit(audit_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Read-only Galaxy S9+ MPIDR suspend identity audit");
