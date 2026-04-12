export interface AnalysisResult {
  bpm: number;
  key: string;
  duration: number;
  sampleRate: number;
}

// Cooley-Tukey in-place FFT (power-of-2 sizes only)
function fft(re: Float64Array, im: Float64Array): void {
  const n = re.length;

  // Bit-reversal permutation
  for (let i = 1, j = 0; i < n; i++) {
    let bit = n >> 1;
    for (; j & bit; bit >>= 1) j ^= bit;
    j ^= bit;
    if (i < j) {
      let t = re[i]; re[i] = re[j]; re[j] = t;
      t = im[i]; im[i] = im[j]; im[j] = t;
    }
  }

  // Butterfly stages
  for (let len = 2; len <= n; len <<= 1) {
    const ang = (-2 * Math.PI) / len;
    const wBaseRe = Math.cos(ang);
    const wBaseIm = Math.sin(ang);
    for (let i = 0; i < n; i += len) {
      let uRe = 1,
        uIm = 0;
      const half = len >> 1;
      for (let k = 0; k < half; k++) {
        const tRe = uRe * re[i + k + half] - uIm * im[i + k + half];
        const tIm = uRe * im[i + k + half] + uIm * re[i + k + half];
        re[i + k + half] = re[i + k] - tRe;
        im[i + k + half] = im[i + k] - tIm;
        re[i + k] += tRe;
        im[i + k] += tIm;
        const nu = uRe * wBaseRe - uIm * wBaseIm;
        uIm = uRe * wBaseIm + uIm * wBaseRe;
        uRe = nu;
      }
    }
  }
}

// ── Chroma / key detection ──────────────────────────────────────────────────

const KEY_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];

// Krumhansl-Schmuckler profiles
const MAJOR_PROFILE = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88];
const MINOR_PROFILE = [6.33, 2.68, 3.52, 5.38, 2.6, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17];

function pearsonCorr(a: number[], b: number[]): number {
  const n = a.length;
  const mA = a.reduce((s, x) => s + x, 0) / n;
  const mB = b.reduce((s, x) => s + x, 0) / n;
  let num = 0, dA = 0, dB = 0;
  for (let i = 0; i < n; i++) {
    const da = a[i] - mA, db = b[i] - mB;
    num += da * db;
    dA += da * da;
    dB += db * db;
  }
  return dA === 0 || dB === 0 ? 0 : num / Math.sqrt(dA * dB);
}

function computeChroma(channel: Float32Array, sampleRate: number): number[] {
  const FFT_SIZE = 4096;
  const chroma = new Array(12).fill(0);

  // Hanning window
  const win = new Float64Array(FFT_SIZE);
  for (let i = 0; i < FFT_SIZE; i++) {
    win[i] = 0.5 * (1 - Math.cos((2 * Math.PI * i) / (FFT_SIZE - 1)));
  }

  // Pre-map each FFT bin → pitch class (null if out of musical range)
  const freqPerBin = sampleRate / FFT_SIZE;
  const binPC: (number | null)[] = new Array(FFT_SIZE / 2).fill(null);
  for (let b = 1; b < FFT_SIZE / 2; b++) {
    const freq = b * freqPerBin;
    if (freq < 65 || freq > 2093) continue;
    const midi = 12 * Math.log2(freq / 440) + 69;
    binPC[b] = ((Math.round(midi) % 12) + 12) % 12;
  }

  const re = new Float64Array(FFT_SIZE);
  const im = new Float64Array(FFT_SIZE);

  // Sample evenly across first 60 s (cap 150 frames)
  const maxSamples = Math.min(channel.length, sampleRate * 60);
  const totalFrames = Math.floor((maxSamples - FFT_SIZE) / FFT_SIZE);
  const step = Math.max(1, Math.floor(totalFrames / 150));

  for (let f = 0; f < totalFrames; f += step) {
    const offset = f * FFT_SIZE;
    for (let i = 0; i < FFT_SIZE; i++) {
      re[i] = channel[offset + i] * win[i];
      im[i] = 0;
    }
    fft(re, im);
    for (let b = 1; b < FFT_SIZE / 2; b++) {
      const pc = binPC[b];
      if (pc !== null) chroma[pc] += re[b] * re[b] + im[b] * im[b];
    }
  }

  // Normalize
  const max = Math.max(...chroma);
  if (max > 0) for (let i = 0; i < 12; i++) chroma[i] /= max;
  return chroma;
}

function detectKey(channel: Float32Array, sampleRate: number): string {
  const chroma = computeChroma(channel, sampleRate);
  let bestKey = 0, bestScore = -Infinity, bestMode = 'Major';

  for (let root = 0; root < 12; root++) {
    const maj = MAJOR_PROFILE.map((_, i) => MAJOR_PROFILE[(i - root + 12) % 12]);
    const min = MINOR_PROFILE.map((_, i) => MINOR_PROFILE[(i - root + 12) % 12]);
    const mj = pearsonCorr(chroma, maj);
    const mn = pearsonCorr(chroma, min);
    if (mj > bestScore) { bestScore = mj; bestKey = root; bestMode = 'Major'; }
    if (mn > bestScore) { bestScore = mn; bestKey = root; bestMode = 'Minor'; }
  }

  return `${KEY_NAMES[bestKey]} ${bestMode}`;
}

// ── BPM detection ───────────────────────────────────────────────────────────

function detectBPM(channel: Float32Array, sampleRate: number): number {
  const FRAME = 1024;
  const HOP = 512;
  // Process up to 90 s
  const maxSamples = Math.min(channel.length, sampleRate * 90);
  const numFrames = Math.floor((maxSamples - FRAME) / HOP);

  // RMS energy per frame
  const energy: number[] = [];
  for (let i = 0; i < numFrames; i++) {
    let e = 0;
    const off = i * HOP;
    for (let j = 0; j < FRAME; j++) e += channel[off + j] ** 2;
    energy.push(Math.sqrt(e / FRAME));
  }

  // Half-wave rectified first difference of log energy = onset strength
  const onset: number[] = [0];
  for (let i = 1; i < energy.length; i++) {
    onset.push(Math.max(0, Math.log1p(energy[i] * 1000) - Math.log1p(energy[i - 1] * 1000)));
  }

  // Autocorrelation over tempo range 60–200 BPM
  const fps = sampleRate / HOP;
  const minLag = Math.round((fps * 60) / 200);
  const maxLag = Math.round((fps * 60) / 60);

  let bestLag = minLag, bestCorr = -Infinity;
  const n = onset.length;
  for (let lag = minLag; lag <= maxLag; lag++) {
    let corr = 0;
    for (let i = 0; i < n - lag; i++) corr += onset[i] * onset[i + lag];
    if (corr > bestCorr) { bestCorr = corr; bestLag = lag; }
  }

  // Convert lag → BPM, fold into 60–180 range
  let bpm = (60 * fps) / bestLag;
  while (bpm > 180) bpm /= 2;
  while (bpm < 60) bpm *= 2;
  return Math.round(bpm);
}

// ── Public API ──────────────────────────────────────────────────────────────

export async function analyzeAudio(audioBuffer: AudioBuffer): Promise<AnalysisResult> {
  const channel = audioBuffer.getChannelData(0);
  const { sampleRate, duration } = audioBuffer;

  // Yield to browser between heavy ops so the spinner renders
  await new Promise<void>((r) => setTimeout(r, 0));
  const bpm = detectBPM(channel, sampleRate);

  await new Promise<void>((r) => setTimeout(r, 0));
  const key = detectKey(channel, sampleRate);

  return { bpm, key, duration, sampleRate };
}

// Build a normalised waveform for display (downsampled to `points` values)
export function buildWaveform(audioBuffer: AudioBuffer, points: number): Float32Array {
  const channel = audioBuffer.getChannelData(0);
  const blockSize = Math.floor(channel.length / points);
  const out = new Float32Array(points);
  for (let i = 0; i < points; i++) {
    let max = 0;
    const offset = i * blockSize;
    for (let j = 0; j < blockSize; j++) {
      const abs = Math.abs(channel[offset + j]);
      if (abs > max) max = abs;
    }
    out[i] = max;
  }
  return out;
}
