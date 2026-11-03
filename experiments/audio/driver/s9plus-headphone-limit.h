/* SPDX-License-Identifier: GPL-2.0 */
#ifndef S9PLUS_HEADPHONE_LIMIT_H
#define S9PLUS_HEADPHONE_LIMIT_H

/* CS47L93 DAC: -64dB + code*0.5dB. Old -18dB DAC at desktop40%
 * used amplitude0.254788 (-11.876dB). Round down to -30dB.
 * This is deliberately not a module parameter or a userspace policy. */
#define S9PLUS_HEADPHONE_VOLUME_MAX 68U

static inline unsigned int s9plus_headphone_limit(unsigned int reg,
                                                 unsigned int value)
{
    if (reg == 0x0419 || reg == 0x041d) {
        unsigned int gain = value & 0xffU;
        if (gain > S9PLUS_HEADPHONE_VOLUME_MAX)
            gain = S9PLUS_HEADPHONE_VOLUME_MAX;
        value = (value & ~0xffU) | gain;
    }
    return value;
}
#endif
