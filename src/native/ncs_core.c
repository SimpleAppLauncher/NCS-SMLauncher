/*
 * ncs_core.c -- the NCS ball's per-frame math, in C.
 *
 * WHY THIS EXISTS
 *
 * The Python renderer is fully vectorized with numpy, but "vectorized" means
 * every frame allocates and frees roughly 16 MB of temporaries (rotation
 * planes, the wave field, perspective, shading, three colour planes...). At
 * 60 fps that is ~1 GB/s of allocation churn, which is exactly the "sudden
 * RAM spike" class of behaviour this project is not allowed to have. The math
 * itself is per-point and independent -- ideal for a single C pass over
 * caller-owned, reused buffers: zero allocation per frame.
 *
 * WHAT IS PORTED
 *
 * Two functions, both exact ports of the numpy code in ncs_sphere.py:
 *
 *   ncs_project  rotation, rim, domain-warped wave field, displacement,
 *                perspective, screen projection, ridge/shading and the
 *                gold/dark colour planes. Two passes over the points (the
 *                field is normalized across its own range, so its min and
 *                max must be known before colours are derived).
 *   ncs_splat    the additive scatter into the (h, w, 3) accumulator. The
 *                numpy version used bincount over the points' bounding box to
 *                avoid an 8 MB allocation per channel; C needs no such trick
 *                because it allocates nothing -- it scatters directly, with
 *                per-tap bounds checks.
 *
 * Fidelity contract: tests/test_ncs_native.py renders both paths and compares
 * them, so the two implementations cannot drift silently.
 *
 * Called from src/ncs_native.py via ctypes with float32 buffers. Everything
 * the caller passes in is owned by the caller and reused across frames.
 */

#include <math.h>

#ifdef _WIN32
#define NCS_API __declspec(dllexport)
#else
#define NCS_API __attribute__((visibility("default")))
#endif

/*
 * Per-point projection + shading.
 *
 * Inputs (length n each):
 *   bx, by, bz   unit-sphere base positions
 *   la, lo       latitude, longitude (radians)
 *   ang, tilt    Y-spin and X-tilt angles (radians)
 *   t            animation time (seconds, drives the field)
 *   bass, mid, high   smoothed audio bands 0..1
 *   disp_amp     0.040 + 0.130 * bass, computed by the caller
 *   cx, cy, radius    projected centre and radius, in internal-resolution px
 *   ridge_lo, ridge_pow   crest threshold/shape (0.45 / 1.40)
 *   crest/dark   the measured reference colours
 *   scratch_f    length-n buffer for the wave field (pass 1 -> pass 2)
 *
 * Outputs (length n each):
 *   sx, sy       screen coordinates, float32 (the caller may truncate to
 *                int32; the splat casts the same way internally, so passing
 *                the float plane down avoids a conversion per frame)
 *   cr, cg, cb   shaded colours BEFORE density normalization
 *   out_ridge, out_rim   the crest and limb fields (the fill-pass mask reads
 *                        these: solid = ridge > 0.30 | rim > 0.15)
 *   fmin, fmax   the field's range this frame (out params)
 */
NCS_API void ncs_project(
        const float *bx, const float *by, const float *bz,
        const float *la, const float *lo, int n,
        float ang, float tilt, float t,
        float bass, float mid, float high,
        float disp_amp, float cx, float cy, float radius,
        float ridge_lo, float ridge_pow,
        float crest_r, float crest_g, float crest_b,
        float dark_r, float dark_g, float dark_b,
        float *scratch_f,
        float *sx, float *sy,
        float *cr, float *cg, float *cb,
        float *out_ridge, float *out_rim,
        float *fmin_out, float *fmax_out)
{
    const float ca = cosf(ang), sa = sinf(ang);
    const float ct = cosf(tilt), st = sinf(tilt);
    const float warp_scale = 0.55f + 0.95f * bass;

    /* ---- pass 1: rotation, field, projection; track the field's range --- */
    float fmin = 1e30f, fmax = -1e30f;
    for (int i = 0; i < n; i++) {
        const float bxv = bx[i], byv = by[i], bzv = bz[i];
        const float x = bxv * ca + bzv * sa;
        const float z0 = -bxv * sa + bzv * ca;
        const float y = byv * ct - z0 * st;
        const float z = byv * st + z0 * ct;

        /* field: warp (sine of a sine) then the three-band sheet (see
         * ncs_sphere.py::_sphere_field -- speeds, phases and weights are the
         * tuned values, do not round them) */
        const float lav = la[i], lov = lo[i];
        const float warp = (2.6f * sinf(1.0f * lav + 1.9f * t)
                            + 1.1f * sinf(1.3f * lov - 1.6f * t)) * warp_scale;
        const float f = 0.78f * sinf(0.80f * lov + 0.95f * lav + warp
                                     + 2.1f * t + mid * 1.4f)
                      + 0.14f * sinf(6.0f * lav + 4.0f * lov + 3.2f * t
                                     + high * 5.0f)
                      + 0.08f * cosf(1.8f * lav - 1.2f * lov - 1.3f * t);
        scratch_f[i] = f;
        if (f < fmin) fmin = f;
        if (f > fmax) fmax = f;

        const float disp = 1.0f + disp_amp * f;
        const float persp = 3.0f / (3.0f - z * disp);
        sx[i] = cx + x * disp * radius * persp;
        sy[i] = cy - y * disp * radius * persp;
        out_rim[i] = expf(-(z0 / 0.30f) * (z0 / 0.30f));
    }
    *fmin_out = fmin;
    *fmax_out = fmax;

    /* ---- pass 2: colours, now that the field's range is known ---------- */
    const float fspan = fmax - fmin > 1e-6f ? fmax - fmin : 1e-6f;
    for (int i = 0; i < n; i++) {
        const float f = scratch_f[i];
        float f01 = (f - fmin) / fspan;
        if (f01 < 0.0f) f01 = 0.0f; else if (f01 > 1.0f) f01 = 1.0f;

        float ridge = (f01 - ridge_lo) / (1.0f - ridge_lo);
        if (ridge < 0.0f) ridge = 0.0f; else if (ridge > 1.0f) ridge = 1.0f;
        ridge = powf(ridge, ridge_pow);
        out_ridge[i] = ridge;

        /* rim again from the stored screen geometry is not possible -- z is
         * cheap to recompute, but rim is already in out_rim from pass 1 */
        const float rim = out_rim[i];
        const float rim_light = 3.20f * rim * (1.0f - 0.85f * ridge);

        /* z from pass 1 is recoverable from persp, but simplest is to
         * recompute the rotation -- four multiplies. */
        const float bxv = bx[i], byv = by[i], bzv = bz[i];
        const float z0 = -bxv * sa + bzv * ca;
        const float z = byv * st + z0 * ct;
        float zc = z < 0.0f ? 0.0f : (z > 1.0f ? 1.0f : z);
        const float shade = (1.0f - 0.18f * zc) * (1.0f + rim_light);

        const float gold = ridge;
        cr[i] = (crest_r * gold + dark_r * (1.0f - gold)) * shade;
        cg[i] = (crest_g * gold + dark_g * (1.0f - gold)) * shade;
        cb[i] = (crest_b * gold + dark_b * (1.0f - gold)) * shade;
    }
}

/*
 * Additive kernel scatter.
 *
 *   buf   (h, w, 3) float32 accumulator, row-major, caller-owned, REUSED
 *   sx,sy integer point positions (length n)
 *   r,g,b per-point colours (length n), already multiplied by their weight
 *   kdx,kdy,kwt  the kernel: k taps of (dx, dy, weight)
 *   weight global scale for this call (the fill pass's 0.30)
 *
 * The numpy version built (k, n) coordinate planes and two masked gathers per
 * channel per call. The C loop is branch-light and touches each tap exactly
 * once; for the 9-tap fill over ~50k solid points that is ~450k inbounds-
 * checked adds, well under a millisecond.
 */
NCS_API void ncs_splat(
        float *buf, int w, int h, int n,
        const float *sx, const float *sy,
        const float *r, const float *g, const float *b,
        const int *kdx, const int *kdy, const float *kwt, int k,
        float weight)
{
    for (int i = 0; i < n; i++) {
        const float rv = r[i] * weight;
        const float gv = g[i] * weight;
        const float bv = b[i] * weight;
        if (rv == 0.0f && gv == 0.0f && bv == 0.0f) continue;
        const int px = (int)sx[i];
        const int py = (int)sy[i];
        for (int j = 0; j < k; j++) {
            const int xx = px + kdx[j];
            const int yy = py + kdy[j];
            if (xx < 0 || xx >= w || yy < 0 || yy >= h) continue;
            float *cell = buf + ((long)yy * w + xx) * 3;
            const float wt = kwt[j];
            cell[0] += rv * wt;
            cell[1] += gv * wt;
            cell[2] += bv * wt;
        }
    }
}
