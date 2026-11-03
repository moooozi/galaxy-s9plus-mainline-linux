"""Check Samsung mode geometry and encoder PPS against captured native state."""
from pathlib import Path
import subprocess
import re
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[3]


class DisplayModeTests(unittest.TestCase):
    def test_active_dpp_receives_image_width_while_dma_receives_padded_pitch(self):
        source = (REPO / 'src/gpu/drm/s9p/s9p-decon.c').read_text()
        function = re.search(r'static void s9p_decon_source_geometry\(.*?\n}\n', source, re.S)[0]
        code = r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#define __iomem
#define IDMA_SRC_SIZE 0x10
#define IDMA_IMG_SIZE 0x18
#define DPP_IMG_SIZE 0x18
struct drm_framebuffer { unsigned height, width, pitches[1]; };
struct s9p_decon { void *postproc; uint32_t dma[32]; };
static void *s9p_chan_regs(struct s9p_decon *p, unsigned channel) {
    assert(channel == 0); return p->dma;
}
#define writel(v,p) (*(uint32_t *)(p)=(v))
'''.replace('uint32_t dma[32];', 'uint32_t dma[32]; unsigned chan;') + function + r'''
int main(void) {
    uint32_t dpp[16] = {0};
    struct s9p_decon p = {.postproc=dpp};
    /* FHD buffers are padded to 1088 pixels, while DPP consumes 1080. */
    struct drm_framebuffer fb = {2220,1080,{4352}};
    s9p_decon_source_geometry(&p,&fb);
    assert(p.dma[0x10/4] == 0x08ac0440);
    assert(p.dma[0x18/4] == 0x08ac0438);
    assert(dpp[0x18/4] == 0x08ac0438);
    /* Native geometry restores all three size registers. */
    fb=(struct drm_framebuffer){2960,1440,{5760}};
    s9p_decon_source_geometry(&p,&fb);
    assert(p.dma[0x10/4] == 0x0b9005a0);
    assert(p.dma[0x18/4] == 0x0b9005a0);
    assert(dpp[0x18/4] == 0x0b9005a0);
    /* Unrecognized/inactive DPP is never written. */
    p.postproc=NULL;
    fb=(struct drm_framebuffer){1480,720,{2880}};
    s9p_decon_source_geometry(&p,&fb);
    assert(p.dma[0x18/4] == 0x05c802d0);
    assert(dpp[0x18/4] == 0x0b9005a0);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'test.c').write_text(code)
            subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                            str(root / 'test.c'), '-o', str(root / 'test')], check=True)
            subprocess.run([str(root / 'test')], check=True)

    def test_native_encoder_parity_and_lower_resolution_geometry(self):
        code = r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
typedef uint8_t u8;
typedef uint32_t u32;
#include "s9p-display-modes.h"
static unsigned be16(const u8 *p) { return (p[0] << 8) | p[1]; }
int main(void) {
    /* Aligned 32-bit read-only capture, installed 7.3.1 RFKILL kernel,
     * 2026-11-03: DSC0 and DSC1, offsets 0x24..0x74.
     */
    const u32 native[] = {
        0x30800b90, 0x02d00028, 0x02d002d0, 0x020001b4,
        0x0020046c, 0x000a000c, 0x027701e9, 0x180010f0,
        0x030c2000, 0x060b0b33, 0x0e1c2a38, 0x46546269,
        0x7077797b, 0x7d7e0102, 0x01000940, 0x09be19fc,
        0x19fa19f8, 0x1a381a78, 0x1ab62af6, 0x2b342b74,
        0x3b746bf4
    };
    const unsigned widths[] = {1440,1080,720};
    const unsigned heights[] = {2960,2220,1480};
    const unsigned slices[] = {40,30,74};
    const unsigned scalers[] = {1,2,0};
    const struct s9p_display_mode *mode = s9p_display_mode_find(1440,2960);
    assert(mode);
    for (unsigned i=0; i<sizeof(native)/sizeof(native[0]); i++)
        assert(s9p_encoder_pps_word(mode,4+i*4)==native[i]);
    for (unsigned i=0; i<3; i++) {
        mode=s9p_display_mode_find(widths[i],heights[i]);
        assert(mode && mode->scaler==scalers[i]);
        assert(be16(mode->pps+6)==heights[i]);
        assert(be16(mode->pps+8)==widths[i]);
        assert(be16(mode->pps+10)==slices[i]);
        assert(be16(mode->pps+12)==widths[i]/2);
        assert(be16(mode->pps+14)==widths[i]/2);
        assert(heights[i]%slices[i]==0);
        assert(s9p_encoder_pps_word(mode,8)==((widths[i]/2)<<16|slices[i]));
        assert((s9p_encoder_pps_word(mode,16)&0xffff)==0x1b4);
    }
    assert(!s9p_display_mode_find(1080,1920));
    assert(!s9p_display_mode_find(720,1048)); /* erroneous vendor comment */
    assert(!s9p_display_mode_find(0,0));
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'test.c'
            source.write_text(code)
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-I', str(REPO / 'src/gpu/drm/s9p'), str(source),
                            '-o', str(root / 'test')], check=True)
            subprocess.run([str(root / 'test')], check=True)
