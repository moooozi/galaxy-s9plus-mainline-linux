#!/usr/bin/env python3
"""Normalize star2lte A55 suspend identities to the firmware/DT affinity layout.

The firmware uses compact A55 core IDs (0..3), while MPIDR_EL1 has MT=1
and the core number in Aff1. Apply the same normalization on save and resume.
All other machines retain the upstream hash. Does not enable any idle states.
"""
from pathlib import Path
import sys


def patch(root, relative, old, new):
    path = root / relative
    source = path.read_text()
    if new in source:
        return
    if source.count(old) != 1:
        raise SystemExit(f'{relative}: expected exactly one matching anchor')
    path.write_text(source.replace(old, new, 1))


def main(root):
    patch(root, 'arch/arm64/kernel/setup.c',
          '#include <linux/of_fdt.h>\n',
          '#include <linux/of.h>\n#include <linux/of_fdt.h>\n')
    patch(root, 'arch/arm64/include/asm/smp_plat.h',
          '\tu32\tbits;\n', '\tu32\tbits;\n\tu32\tstar2lte_mt_affinity;\n')
    patch(root, 'arch/arm64/kernel/setup.c',
          '\tmpidr_hash.mask = mask;\n',
          '\t/* star2lte firmware IDs compact the MT A55 affinity by one level. */\n'
          '\tmpidr_hash.star2lte_mt_affinity =\n'
          '\t\tof_machine_is_compatible("samsung,star2lte");\n'
          '\tmpidr_hash.mask = mask;\n')
    patch(root, 'arch/arm64/kernel/asm-offsets.c',
          '  DEFINE(MPIDR_HASH_MASK,\toffsetof(struct mpidr_hash, mask));\n',
          '  DEFINE(MPIDR_HASH_MASK,\toffsetof(struct mpidr_hash, mask));\n'
          '  DEFINE(MPIDR_HASH_STAR2LTE_MT, offsetof(struct mpidr_hash, star2lte_mt_affinity));\n')
    patch(root, 'arch/arm64/kernel/sleep.S',
          '\t.macro compute_mpidr_hash dst, rs0, rs1, rs2, rs3, mpidr, mask\n',
          '\t/* tmp is overwritten by the subsequent hash-shift loads. */\n'
          '\t.macro star2lte_suspend_affinity mpidr, hash, tmp\n'
          '\tldr\t\\tmp, [\\hash, #MPIDR_HASH_STAR2LTE_MT]\n'
          '\tcbz\t\\tmp, .Lstar2lte_done\\@\n'
          '\ttbz\t\\mpidr, #24, .Lstar2lte_done\\@\n'
          '\tlsr\t\\mpidr, \\mpidr, #8\n'
          '.Lstar2lte_done\\@:\n'
          '\t.endm\n\n'
          '\t.macro compute_mpidr_hash dst, rs0, rs1, rs2, rs3, mpidr, mask\n')
    patch(root, 'arch/arm64/kernel/sleep.S',
          '\tadr_l\tx9, mpidr_hash\n',
          '\tadr_l\tx9, mpidr_hash\n'
          '\tstar2lte_suspend_affinity x7, x9, w3\n')
    patch(root, 'arch/arm64/kernel/sleep.S',
          '\tadr_l\tx8, mpidr_hash\t\t// x8 = struct mpidr_hash virt address\n',
          '\tadr_l\tx8, mpidr_hash\t\t// x8 = struct mpidr_hash virt address\n'
          '\tstar2lte_suspend_affinity x1, x8, w3\n')


if __name__ == '__main__':
    main(Path(sys.argv[1]))
