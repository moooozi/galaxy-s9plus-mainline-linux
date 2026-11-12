/* SPDX-License-Identifier: GPL-2.0 */
#ifndef S9PLUS_ABOX_FAULT_H
#define S9PLUS_ABOX_FAULT_H

/* A permanently faulting firmware must not become an endless reset loop.
 * The caller serializes this state between mailbox IRQ and recovery work.
 * A new firmware boot clears only pending, never the attempt budget.
 */
#define S9PLUS_ABOX_FAULT_RECOVERIES 3U

struct s9plus_abox_fault {
	unsigned int reports;
	unsigned int recoveries;
	int pending;
	int faulted;
	int blocked;
};

static inline int s9plus_abox_fault_report(struct s9plus_abox_fault *state)
{
	int first = !state->pending;

	if (state->reports != ~0U)
		state->reports++;
	state->pending = 1;
	state->faulted = 1;
	return first;
}

static inline int s9plus_abox_fault_recover(struct s9plus_abox_fault *state)
{
	if (!state->faulted)
		return 1;
	if (state->blocked || state->recoveries >= S9PLUS_ABOX_FAULT_RECOVERIES) {
		state->blocked = 1;
		return 0;
	}
	state->recoveries++;
	return 1;
}

static inline void s9plus_abox_fault_begin_boot(struct s9plus_abox_fault *state)
{
	state->pending = 0;
}

static inline void s9plus_abox_fault_manual_retry(struct s9plus_abox_fault *state)
{
	state->recoveries = 0;
	state->blocked = 0;
}

/* Subtraction avoids wrapping a firmware-provided address near UINT_MAX. */
static inline int s9plus_abox_fault_range(unsigned int address,
		unsigned int base, unsigned int size, unsigned int bytes)
{
	return !(address & 3U) && bytes <= size && address >= base &&
		address - base <= size - bytes;
}
#endif
