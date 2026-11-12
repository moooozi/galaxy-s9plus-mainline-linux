// SPDX-License-Identifier: GPL-2.0
/* Adapted from Zerone-Laboratories/ztOS power/idle/zrn-idle.c at
 * 7f42ddc3ba468e4e21c7145cbb973f5aa57d5358.
 * See experiments/cpuidle/SOURCE.md in the port repository.
 * Per-core C2 only, CPUs 2 and 3. No SICD, hotplug or system suspend.
 * Built into the kernel; C2 starts disabled until userspace validates the guard.
 */
#include <linux/cpu.h>
#include <linux/clocksource.h>
#include <linux/interrupt.h>
#include <linux/irq.h>
#include <linux/iopoll.h>
#include <linux/of.h>
#include <linux/of_irq.h>
#include <linux/cpu_pm.h>
#include <linux/cpuidle.h>
#include <linux/io.h>
#include <linux/module.h>
#include <linux/spinlock.h>
#include <linux/arm-smccc.h>
#include <linux/tick.h>
#include <asm/cputype.h>
#include <asm/memory.h>
#include <asm/smp_plat.h>
#include <asm/suspend.h>


#define PMU_BASE		0x14060000
#define PMU_CPU_INFORM(c)	(0x0860 + 4 * (c))
#define PMU_EVENT_INT_EN_GRP2	0x7f08
#define BID_BASE		0x14070000
#define GRP1_PEND		0x0108
#define GRP1_CLEAR		0x010c
#define GRP2_ENABLE		0x0200
#define GRP2_PEND		0x0208
#define GRP2_CLEAR		0x020c
#define INFORM_C2		1
#define PSCI_CORE_POWERDOWN	0x10000

static bool integrated = true;
module_param(integrated, bool, 0444);
static unsigned int cpus = 0x0c;
module_param(cpus, uint, 0444);
MODULE_PARM_DESC(cpus, "mask of the CPUs to give the power-down state");

static unsigned long cpu_resume_pa;
static void __iomem *pmu, *bid;
/*
 * The finisher: one SMC, the function id Samsung's firmware implements
 * (from the stock device tree's psci node), with the state and the physical
 * address cpu_resume runs at. It must not touch the stack: cpu_suspend has
 * already saved the register frame it will be resumed into.
 */
static int zrn_suspend_finisher(unsigned long state)
{
	struct arm_smccc_res res;

	arm_smccc_smc(0xC4000001, state, cpu_resume_pa, 0, 0, 0, 0, 0, &res);
	return (int)res.a0;
}
static DEFINE_RAW_SPINLOCK(pmu_lock);

/*
 * The PMU's core number, as Samsung's linear_phycpu(): cluster * 4 + core.
 * The little Cortex-A55s report a multithreading-style MPIDR (MT set, core
 * in Aff1, cluster in Aff2); the big cores the plain one (core in Aff0).
 */
static unsigned int zrn_core(u64 mpidr)
{
	int lvl = (mpidr & MPIDR_MT_BITMASK) ? 1 : 0;

	return (MPIDR_AFFINITY_LEVEL(mpidr, (lvl + 1)) << 2) | MPIDR_AFFINITY_LEVEL(mpidr, lvl);
}

static void rmw(void __iomem *reg, u32 mask, u32 value)
{
	writel_relaxed((readl_relaxed(reg) & ~mask) | value, reg);
}

static void core_off(unsigned int core)
{
	u32 bit = BIT((core + 4) & 7);

	if (WARN_ON_ONCE(core > 7))
		return;
	raw_spin_lock(&pmu_lock);
	writel_relaxed(INFORM_C2, pmu + PMU_CPU_INFORM(core));
	rmw(bid + GRP2_ENABLE, bit, bit);
	if (readl_relaxed(bid + GRP1_PEND) & bit)
		rmw(bid + GRP1_CLEAR, bit, bit);
	rmw(pmu + PMU_EVENT_INT_EN_GRP2, bit, bit);
	raw_spin_unlock(&pmu_lock);
	wmb();
}

static void core_on(unsigned int core)
{
	u32 bit = BIT((core + 4) & 7);

	if (core > 7)
		return;
	raw_spin_lock(&pmu_lock);
	writel_relaxed(0, pmu + PMU_CPU_INFORM(core));
	rmw(bid + GRP2_ENABLE, bit, 0);
	if (readl_relaxed(bid + GRP2_PEND) & bit)
		rmw(bid + GRP2_CLEAR, bit, bit);
	rmw(pmu + PMU_EVENT_INT_EN_GRP2, bit, 0);
	raw_spin_unlock(&pmu_lock);
}

static int enter_wfi(struct cpuidle_device *dev, struct cpuidle_driver *drv, int idx)
{
	dsb(sy);
	wfi();
	return idx;
}

static int enter_powerdown(struct cpuidle_device *dev, struct cpuidle_driver *drv, int idx)
{
 unsigned int core = zrn_core(read_cpuid_mpidr());
 int ret;
 if (core != 2 && core != 3)
  return enter_wfi(dev, drv, 0);
 ret = cpu_pm_enter();
 if (ret)
  return -EBUSY;
 core_off(core);
 /* Samsung's legacy PSCI encoding needs an explicit context resume address. */
 ret = cpu_suspend(PSCI_CORE_POWERDOWN, zrn_suspend_finisher);
 core_on(core);
 cpu_pm_exit();
 return ret ? -EBUSY : idx;
}

static struct cpuidle_driver driver = {
 .name = "s9plus_idle_little",
 .states = {
  { .name = "WFI", .desc = "wait for interrupt", .enter = enter_wfi,
    .exit_latency = 1, .target_residency = 1 },
  { .name = "C2", .desc = "A55 core power down", .enter = enter_powerdown,
    .flags = CPUIDLE_FLAG_TIMER_STOP | CPUIDLE_FLAG_RCU_IDLE | CPUIDLE_FLAG_OFF,
    .exit_latency = 160, .target_residency = 2000 },
 },
 .state_count = 2,
};
static cpumask_t idle_mask;

#define MCT_PHYS		0x10040000UL
#define MCT_G_CNT_L		0x100
#define MCT_G_CNT_U		0x104
#define MCT_G_CNT_WSTAT		0x110
#define MCT_G_COMP0_L		0x200
#define MCT_G_COMP0_U		0x204
#define MCT_G_TCON		0x240
#define MCT_G_INT_CSTAT		0x244
#define MCT_G_INT_ENB		0x248
#define MCT_G_WSTAT		0x24c
#define MCT_TCON_START		(1U << 8)
#define MCT_TCON_COMP0_EN	(1U << 0)
#define MCT_G0_SPI		466

static void __iomem *mct;
static struct clock_event_device zrn_bc;
static bool zrn_bc_live;
static unsigned long mct_late_events;
module_param(mct_late_events, ulong, 0444);
static unsigned long g0_irqs;
module_param(g0_irqs, ulong, 0444);
static unsigned long mct_write_failures;
module_param(mct_write_failures, ulong, 0444);
static DEFINE_RAW_SPINLOCK(mct_lock);

static int mct_wr(u32 v, u32 off, u32 wstat_bit)
{
	u32 stat;

	writel_relaxed(v, mct + off);
	if (readl_poll_timeout_atomic(mct + MCT_G_WSTAT, stat,
				      stat & wstat_bit, 1, 100)) {
		mct_write_failures++;
		pr_warn_ratelimited("zrn-idle: MCT write %#x did not land\n", off);
		return -ETIMEDOUT;
	}
	writel_relaxed(wstat_bit, mct + MCT_G_WSTAT);	/* the status clears on a 1 */
	return 0;
}

static u64 mct_count(void)
{
	u32 hi, hi2, lo;

	hi = readl_relaxed(mct + MCT_G_CNT_U);
	do {
		lo = readl_relaxed(mct + MCT_G_CNT_L);
		hi2 = readl_relaxed(mct + MCT_G_CNT_U);
		if (hi == hi2)
			return ((u64)hi << 32) | lo;
		hi = hi2;
	} while (1);
}

static unsigned long mct_measure_rate(void)
{
	u64 a, b, ns;
	ktime_t t0 = ktime_get();

	a = mct_count();
	while (ktime_to_ns(ktime_sub(ktime_get(), t0)) < 200 * NSEC_PER_MSEC)
		cpu_relax();
	ns = ktime_to_ns(ktime_sub(ktime_get(), t0));
	b = mct_count();
	return ns ? (unsigned long)div64_u64((b - a) * NSEC_PER_SEC, ns) : 0;
}

static int mct_comp0_stop(void)
{
	u32 tcon = readl_relaxed(mct + MCT_G_TCON);
	int ret;

	writel_relaxed(readl_relaxed(mct + MCT_G_INT_ENB) & ~1U, mct + MCT_G_INT_ENB);
	tcon &= ~MCT_TCON_COMP0_EN;
	ret = mct_wr(tcon, MCT_G_TCON, 1U << 16);
	/* a match that landed before the stop stays latched; left there, the
	 * firmware sees G0 pending at the next SYS_SLEEP and refuses it */
	writel_relaxed(1, mct + MCT_G_INT_CSTAT);
	return ret;
}

static int zrn_bc_set_next(unsigned long cycles, struct clock_event_device *evt)
{
	u64 comp;
	u32 tcon;
	unsigned long flags;
	int ret = 0;

	raw_spin_lock_irqsave(&mct_lock, flags);
	comp = mct_count() + cycles;
	tcon = readl_relaxed(mct + MCT_G_TCON);

	writel_relaxed(1, mct + MCT_G_INT_CSTAT);
	tcon &= ~MCT_TCON_COMP0_EN;
	if (mct_wr(tcon, MCT_G_TCON, 1U << 16) ||
	    mct_wr((u32)comp, MCT_G_COMP0_L, 1U << 0) ||
	    mct_wr((u32)(comp >> 32), MCT_G_COMP0_U, 1U << 1)) {
		ret = -ETIME;
		goto stop;
	}
	writel_relaxed(readl_relaxed(mct + MCT_G_INT_ENB) | 1U, mct + MCT_G_INT_ENB);
	tcon |= MCT_TCON_COMP0_EN;
	if (mct_wr(tcon, MCT_G_TCON, 1U << 16)) {
		ret = -ETIME;
		goto stop;
	}
	/* MCT compares for equality. If programming took longer than the
	 * requested interval, the event will never arrive. Returning success
	 * leaves tick_broadcast_force_mask set and every CPU polling forever.
	 * Let the clockevent core retry with its minimum-delta backoff. */
	if ((s64)(mct_count() - comp) >= 0) {
		mct_late_events++;
		ret = -ETIME;
		goto stop;
	}
	goto out;
stop:
	mct_comp0_stop();
out:
	raw_spin_unlock_irqrestore(&mct_lock, flags);
	return ret;
}

static int zrn_bc_stop(struct clock_event_device *evt)
{
	unsigned long flags;
	int ret = 0;

	raw_spin_lock_irqsave(&mct_lock, flags);
	if (zrn_bc_live)
		ret = mct_comp0_stop();
	raw_spin_unlock_irqrestore(&mct_lock, flags);
	return ret;
}

static irqreturn_t zrn_bc_isr(int irq, void *dev)
{
	struct clock_event_device *evt = dev;

	/* only comparator 0's flag is ours; a stray line (wrong SPI guess)
	 * shows up as spurious instead of waking cores at random */
	if (!(readl_relaxed(mct + MCT_G_INT_CSTAT) & 1))
		return IRQ_NONE;
	writel_relaxed(1, mct + MCT_G_INT_CSTAT);
	g0_irqs++;
	evt->event_handler(evt);
	return IRQ_HANDLED;
}

static void zrn_bc_noop(struct clock_event_device *evt)
{
}

/*
 * Register the comparator as a global oneshot clockevent. Rating 300: above
 * bc_hrtimer (0), so the framework installs it as the broadcast device, and
 * below the arch timers (~400), so the per-CPU tick devices are untouched.
 */
static int __init zrn_broadcast_init(void)
{
	struct device_node *gic;
	struct irq_fwspec spec = { };
	unsigned long rate;
	u32 tcon;
	int virq, ret;

	mct = ioremap(MCT_PHYS, 0x800);
	if (!mct)
		return -ENOMEM;
	tcon = readl_relaxed(mct + MCT_G_TCON);
	if (!(tcon & MCT_TCON_START)) {	/* the counter is not even running */
		ret = mct_wr(tcon | MCT_TCON_START, MCT_G_TCON, 1U << 16);
		if (ret)
			goto err;
	}
	rate = mct_measure_rate();
	if (rate < 1000000) {
		pr_err("zrn-idle: MCT not ticking (rate %lu Hz): no broadcast, no C2\n", rate);
		ret = -ENODEV;
		goto err;
	}
	pr_info("zrn-idle: MCT G0 at %lu Hz is the broadcast timer\n", rate);

	gic = of_find_compatible_node(NULL, NULL, "arm,gic-400");
	if (!gic) {
		ret = -ENODEV;
		goto err;
	}
	spec.fwnode = of_fwnode_handle(gic);
	spec.param_count = 3;
	spec.param[0] = 0;			/* GIC_SPI */
	spec.param[1] = MCT_G0_SPI;
	spec.param[2] = IRQ_TYPE_LEVEL_HIGH;
	virq = irq_create_fwspec_mapping(&spec);
	of_node_put(gic);
	if (virq <= 0) {
		ret = -ENOENT;
		goto err;
	}

	zrn_bc = (struct clock_event_device){
		.name = "zrn-mct-g0",
		.features = CLOCK_EVT_FEAT_ONESHOT,
		.rating = 300,
		.irq = virq,
		.set_next_event = zrn_bc_set_next,
		.set_state_shutdown = zrn_bc_stop,
		.set_state_oneshot = zrn_bc_stop,
		.set_state_oneshot_stopped = zrn_bc_stop,
		.tick_resume = zrn_bc_stop,
		.cpumask = cpumask_of(0),
		.owner = THIS_MODULE,
		.event_handler = zrn_bc_noop,
	};
	/* Firmware may leave comparator0 armed. Clear it before installing an
	 * interrupt handler, and let clockevents' initial shutdown callback run.
	 */
	ret = mct_comp0_stop();
	if (ret)
		goto err_dispose;
	ret = request_irq(virq, zrn_bc_isr,
			  IRQF_TIMER | IRQF_IRQPOLL | IRQF_NOBALANCING,
			  "zrn-mct-g0", &zrn_bc);
	if (ret)
		goto err_dispose;
	/* CPU0 is deliberately excluded from C2 so the broadcast interrupt
	 * remains serviceable while both participating A55 cores are asleep.
	 */
	ret = irq_set_affinity(virq, cpumask_of(0));
	if (ret)
		goto err_free_irq;
	/* Several synchronized MMIO writes precede arming the comparator.
	 * Fifteen cycles (<1 us) can expire before it is enabled. */
	zrn_bc_live = true;
	clockevents_config_and_register(&zrn_bc, rate, DIV_ROUND_UP(rate, 5000), UINT_MAX);
	return 0;

err_free_irq:
	free_irq(virq, &zrn_bc);
err_dispose:
	irq_dispose_mapping(virq);
err:
	iounmap(mct);
	mct = NULL;
	return ret;
}

static int __init s9plus_idle_init(void)
{
 int ret;
 /* Keep the validated mask, including on older kernels with hash collisions.
  * The hash correction alone does not validate additional cores. Keep CPU0
  * available for the broadcast timer. */
 if (cpus != 0x0c || !of_machine_is_compatible("samsung,star2lte"))
  return -EINVAL;
 /* Do not assume logical numbering matches the validated PMU cores. */
 if (!cpu_online(0) || !cpu_online(2) || !cpu_online(3) ||
     zrn_core(cpu_logical_map(2)) != 2 || zrn_core(cpu_logical_map(3)) != 3)
  return -ENODEV;
 cpu_resume_pa = __pa_symbol(cpu_resume);
 pmu = ioremap(PMU_BASE, 0x8000);
 bid = ioremap(BID_BASE, 0x1000);
 if (!pmu || !bid) {
  ret = -ENOMEM;
  goto unmap;
 }
 ret = zrn_broadcast_init();
 if (ret)
  goto unmap;
 cpumask_clear(&idle_mask);
 cpumask_set_cpu(2, &idle_mask);
 cpumask_set_cpu(3, &idle_mask);
 driver.cpumask = &idle_mask;
 ret = cpuidle_register(&driver, NULL);
 if (ret) {
  pr_err("s9plus-cpuidle: registration failed %d; built-in broadcast remains registered\n", ret);
  /* A built-in clockevent remains valid even if idle registration fails. */
  return ret;
 }
 pr_info("s9plus-cpuidle: C2 registered disabled for CPUs 2,3; no cluster or system suspend\n");
 return 0;
unmap:
 if (bid)
  iounmap(bid);
 if (pmu)
  iounmap(pmu);
 return ret;
}
late_initcall(s9plus_idle_init);
MODULE_DESCRIPTION("Galaxy S9+ conservative A55 C2 idle and MCT broadcast timer");
MODULE_LICENSE("GPL");
