#!/usr/bin/env python3
"""Execute the patched kernel's actual AArch64 hash macros under qemu-user."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

source = (Path(sys.argv[1]) / 'arch/arm64/kernel/sleep.S').read_text()
macros = []
for name in ('star2lte_suspend_affinity', 'compute_mpidr_hash'):
    match = re.search(r'\t\.macro ' + name + r'\b.*?\t\.endm', source, re.S)
    if not match:
        raise SystemExit(f'Missing {name}')
    macros.append(match.group())
assembly = '''#define MPIDR_HASH_STAR2LTE_MT 0
.text
''' + '\n'.join(macros) + '''
.global hash_test
hash_test:
    star2lte_suspend_affinity x0, x1, w3
    mov x2, #0x103
    mov x3, #0
    mov x4, #6
    mov x5, #13
    mov x6, #29
    compute_mpidr_hash x8, x3, x4, x5, x6, x0, x2
    mov x0, x8
    ret
.section .note.GNU-stack,"",%progbits
'''
harness = r'''
#include <stdint.h>
#include <stdio.h>
extern uint64_t hash_test(uint64_t, const uint32_t *);
int main(void) {
    /* Exact full MPIDRs measured with the read-only diagnostic on this phone. */
    uint64_t raw[] = {0x81000000, 0x81000100, 0x81000200, 0x81000300,
                      0x80000100, 0x80000101, 0x80000102, 0x80000103};
    uint64_t old[] = {0, 4, 0, 4, 4, 5, 6, 7};
    uint32_t enabled = 1, disabled = 0;
    for (unsigned i = 0; i < 8; i++) {
        uint64_t fixed = hash_test(raw[i], &enabled);
        uint64_t original = hash_test(raw[i], &disabled);
        if (fixed != i || original != old[i]) return 1;
        printf("CPU%u: original=%llu corrected=%llu\n", i,
               (unsigned long long)original, (unsigned long long)fixed);
    }
    puts("PASS: eight distinct in-bounds slots; other-board path unchanged");
    return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='s9plus-hash-') as directory:
    temp = Path(directory)
    (temp / 'hash.S').write_text(assembly)
    (temp / 'test.c').write_text(harness)
    subprocess.run(['aarch64-linux-gnu-gcc', '-static', '-Wall', '-Werror',
                    str(temp / 'test.c'), str(temp / 'hash.S'), '-o', str(temp / 'test')], check=True)
    subprocess.run(['qemu-aarch64-static', str(temp / 'test')], check=True)
