//! Allocation-free radix-2 FFT spectrum extraction for the desktop player.
//!
//! The C ABI writes to caller-owned scratch arrays. Python owns and reuses
//! those buffers, so this runs without a Vec allocation per frame. The audio
//! ring is already float32; the transform is float64 to match NumPy's rfft
//! precision closely enough for the renderer's reference path.

use std::f64::consts::TAU;

const MAX_SAMPLES: usize = 1 << 20;
const MAX_BARS: usize = 512;

fn valid(n: usize, sample_rate: f64, low: f64, high: f64, bars: usize, gain: f64) -> bool {
    n >= 2
        && n.is_power_of_two()
        && n <= MAX_SAMPLES
        && sample_rate.is_finite()
        && sample_rate > 0.0
        && low.is_finite()
        && high.is_finite()
        && low >= 0.0
        && high > low
        && bars > 0
        && bars <= MAX_BARS
        && gain.is_finite()
        && gain >= 0.0
}

/// Compute Hann-windowed FFT magnitudes, grouped into logarithmic bands.
///
/// `real`, `imag`, and `output` are caller-owned workspaces with lengths
/// `samples.len()`, `samples.len()`, and `bars` respectively. No memory is
/// allocated here. Returns false for invalid arguments.
fn spectrum_into(
    samples: &[f32],
    sample_rate: f64,
    low: f64,
    high: f64,
    bars: usize,
    gain: f64,
    denominator: f64,
    real: &mut [f64],
    imag: &mut [f64],
    output: &mut [f32],
) -> bool {
    let n = samples.len();
    if !valid(n, sample_rate, low, high, bars, gain)
        || !denominator.is_finite()
        || denominator <= 0.0
        || real.len() < n
        || imag.len() < n
        || output.len() < bars
    {
        return false;
    }

    // NumPy's np.hanning(N): 0.5 - 0.5*cos(2*pi*i/(N-1)).
    let window_denom = (n - 1) as f64;
    for i in 0..n {
        let hann = 0.5 - 0.5 * (TAU * i as f64 / window_denom).cos();
        real[i] = samples[i] as f64 * hann;
        imag[i] = 0.0;
    }

    // In-place bit-reversal permutation.
    let mut j = 0usize;
    for i in 1..n {
        let mut bit = n >> 1;
        while j & bit != 0 {
            j ^= bit;
            bit >>= 1;
        }
        j ^= bit;
        if i < j {
            real.swap(i, j);
            imag.swap(i, j);
        }
    }

    // Iterative decimation-in-time radix-2 FFT, forward sign convention.
    let mut size = 2usize;
    while size <= n {
        let half = size / 2;
        let angle = -TAU / size as f64;
        let step_re = angle.cos();
        let step_im = angle.sin();
        for base in (0..n).step_by(size) {
            let mut twiddle_re = 1.0f64;
            let mut twiddle_im = 0.0f64;
            for offset in 0..half {
                let even = base + offset;
                let odd = even + half;
                let odd_re = real[odd] * twiddle_re - imag[odd] * twiddle_im;
                let odd_im = real[odd] * twiddle_im + imag[odd] * twiddle_re;
                let even_re = real[even];
                let even_im = imag[even];
                real[even] = even_re + odd_re;
                imag[even] = even_im + odd_im;
                real[odd] = even_re - odd_re;
                imag[odd] = even_im - odd_im;
                let next_re = twiddle_re * step_re - twiddle_im * step_im;
                twiddle_im = twiddle_re * step_im + twiddle_im * step_re;
                twiddle_re = next_re;
            }
        }
        if size == n {
            break;
        }
        size <<= 1;
    }

    let bin_count = n / 2 + 1;
    let hz_per_bin = sample_rate / n as f64;
    let ratio = high / low.max(f64::MIN_POSITIVE);
    for (bar, value) in output.iter_mut().take(bars).enumerate() {
        let lower = low * ratio.powf(bar as f64 / bars as f64);
        let upper = low * ratio.powf((bar + 1) as f64 / bars as f64);
        let start = ((lower / hz_per_bin).ceil() as usize).min(bin_count);
        let end = ((upper / hz_per_bin).ceil() as usize).min(bin_count);
        let mut peak = 0.0f64;
        for k in start..end {
            let magnitude = real[k].hypot(imag[k]);
            if magnitude > peak {
                peak = magnitude;
            }
        }
        let scaled = (peak * gain).ln_1p() / denominator;
        *value = scaled.clamp(0.0, 1.0) as f32;
    }
    true
}

/// Caller-owned-memory C ABI. Return 0 on success, -1 for invalid pointers or
/// parameters. On error the output is not read by the caller.
///
/// # Safety
/// All non-null pointers must reference arrays with the lengths described by
/// `n` and `bars`; they must be properly aligned and writable where applicable.
#[no_mangle]
pub unsafe extern "C" fn ncs_spectrum(
    samples: *const f32,
    n: usize,
    sample_rate: f64,
    low: f64,
    high: f64,
    bars: usize,
    gain: f64,
    denominator: f64,
    real: *mut f64,
    imag: *mut f64,
    output: *mut f32,
) -> i32 {
    if samples.is_null()
        || real.is_null()
        || imag.is_null()
        || output.is_null()
        || n > MAX_SAMPLES
        || bars > MAX_BARS
    {
        return -1;
    }
    // SAFETY: the caller promises these buffers have at least the requested
    // lengths; the bounds above cap malformed FFI calls before slice creation.
    let samples = unsafe { std::slice::from_raw_parts(samples, n) };
    let real = unsafe { std::slice::from_raw_parts_mut(real, n) };
    let imag = unsafe { std::slice::from_raw_parts_mut(imag, n) };
    let output = unsafe { std::slice::from_raw_parts_mut(output, bars) };
    if spectrum_into(
        samples,
        sample_rate,
        low,
        high,
        bars,
        gain,
        denominator,
        real,
        imag,
        output,
    ) {
        0
    } else {
        -1
    }
}

#[cfg(test)]
fn spectrum_bins(
    samples: &[f32],
    sample_rate: f64,
    low: f64,
    high: f64,
    bars: usize,
    gain: f64,
) -> Vec<f32> {
    if !valid(samples.len(), sample_rate, low, high, bars, gain) {
        return Vec::new();
    }
    let mut out = vec![0.0; bars];
    let mut real = vec![0.0; samples.len()];
    let mut imag = vec![0.0; samples.len()];
    let denominator = (1.0 + gain * 5.0).ln();
    // The unit-test helper uses a generic curve normalization. The C ABI's
    // production denominator is supplied by Python (ln(41) or ln(11)).
    let _ = spectrum_into(
        samples,
        sample_rate,
        low,
        high,
        bars,
        gain,
        denominator,
        &mut real,
        &mut imag,
        &mut out,
    );
    out
}

#[cfg(test)]
mod tests {
    use super::spectrum_bins;

    #[test]
    fn silence_returns_only_zero_bands() {
        let samples = vec![0.0_f32; 4096];
        let result = spectrum_bins(&samples, 44_100.0, 50.0, 16_000.0, 64, 8.0);
        assert_eq!(result, vec![0.0; 64]);
    }

    #[test]
    fn a_tone_activates_its_frequency_band_not_every_band() {
        let n = 4096;
        let samples: Vec<f32> = (0..n)
            .map(|i| (std::f32::consts::TAU * 440.0 * i as f32 / 44_100.0).sin())
            .collect();
        let result = spectrum_bins(&samples, 44_100.0, 50.0, 16_000.0, 64, 8.0);
        assert_eq!(result.len(), 64);
        assert!(result.iter().all(|x| (0.0..=1.0).contains(x)));
        let active = result.iter().filter(|&&x| x > 0.20).count();
        assert!(
            (3..=8).contains(&active),
            "unexpected active-band count: {active}"
        );
        let peak = result
            .iter()
            .enumerate()
            .max_by(|a, b| a.1.total_cmp(b.1))
            .unwrap()
            .0;
        assert!((23..=24).contains(&peak), "440 Hz peaked in band {peak}");
        assert!(result.iter().copied().fold(0.0_f32, f32::max) > 0.5);
    }

    #[test]
    fn invalid_sizes_and_frequency_ranges_are_rejected_without_panicking() {
        assert!(spectrum_bins(&[1.0, 2.0, 3.0], 44_100.0, 50.0, 16_000.0, 32, 8.0).is_empty());
        assert!(spectrum_bins(&[0.0; 8], 44_100.0, 50.0, 16_000.0, 0, 8.0).is_empty());
        assert!(spectrum_bins(&[0.0; 8], 44_100.0, 50.0, 16_000.0, 8, -1.0).is_empty());
    }
}
