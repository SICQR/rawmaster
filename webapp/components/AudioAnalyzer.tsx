'use client';

import { useState, useCallback, useRef } from 'react';
import AudioDropzone from './AudioDropzone';
import WaveformVisualizer from './WaveformVisualizer';
import AnalysisResults from './AnalysisResults';
import AudioPlayer from './AudioPlayer';
import { analyzeAudio, buildWaveform, type AnalysisResult } from '@/lib/audioAnalysis';

type Phase = 'idle' | 'decoding' | 'analyzing' | 'done' | 'error';

export default function AudioAnalyzer() {
  const [phase, setPhase] = useState<Phase>('idle');
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [waveform, setWaveform] = useState<Float32Array | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [filename, setFilename] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [currentTime, setCurrentTime] = useState(0);
  const [audioDuration, setAudioDuration] = useState(1);
  const prevUrlRef = useRef<string | null>(null);

  const handleFile = useCallback(async (file: File) => {
    // Revoke old object URL to avoid memory leak
    if (prevUrlRef.current) URL.revokeObjectURL(prevUrlRef.current);

    const url = URL.createObjectURL(file);
    prevUrlRef.current = url;
    setAudioUrl(url);
    setFilename(file.name);
    setResult(null);
    setWaveform(null);
    setErrorMsg('');
    setCurrentTime(0);
    setPhase('decoding');

    try {
      const arrayBuffer = await file.arrayBuffer();
      setPhase('analyzing');

      const audioCtx = new AudioContext();
      const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
      await audioCtx.close();

      // Build waveform for display (800 points fills most screens)
      const wf = buildWaveform(audioBuffer, 800);
      setWaveform(wf);
      setAudioDuration(audioBuffer.duration);

      const analysis = await analyzeAudio(audioBuffer);
      setResult(analysis);
      setPhase('done');
    } catch (err) {
      console.error(err);
      setErrorMsg(err instanceof Error ? err.message : 'Could not decode audio. Try a different file.');
      setPhase('error');
    }
  }, []);

  const reset = useCallback(() => {
    if (prevUrlRef.current) URL.revokeObjectURL(prevUrlRef.current);
    prevUrlRef.current = null;
    setAudioUrl(null);
    setResult(null);
    setWaveform(null);
    setPhase('idle');
    setFilename('');
    setErrorMsg('');
    setCurrentTime(0);
  }, []);

  const isProcessing = phase === 'decoding' || phase === 'analyzing';

  return (
    <div className="w-full max-w-2xl mx-auto space-y-5">
      {/* Drop zone — always visible until done */}
      {phase !== 'done' && (
        <AudioDropzone onFile={handleFile} disabled={isProcessing} />
      )}

      {/* Processing indicator */}
      {isProcessing && (
        <div className="flex items-center gap-3 rounded-xl border border-white/[0.06] bg-[#141414] px-5 py-4">
          <div className="w-4 h-4 rounded-full border-2 border-[#e63012] border-t-transparent animate-spin shrink-0" />
          <span className="text-sm text-[#E5E5E5]/70 font-mono">
            {phase === 'decoding' ? 'Decoding audio…' : 'Analysing BPM & key…'}
          </span>
        </div>
      )}

      {/* Error */}
      {phase === 'error' && (
        <div className="rounded-xl border border-red-500/20 bg-red-500/5 px-5 py-4 text-sm text-red-400 font-mono">
          {errorMsg}
          <button onClick={reset} className="ml-4 underline text-red-400/70 hover:text-red-400">
            Try again
          </button>
        </div>
      )}

      {/* Waveform */}
      {waveform && (
        <div className="rounded-xl border border-white/[0.06] bg-[#141414] p-4">
          <WaveformVisualizer
            waveform={waveform}
            currentTime={currentTime}
            duration={audioDuration}
          />
        </div>
      )}

      {/* Audio player */}
      {audioUrl && phase === 'done' && (
        <AudioPlayer
          src={audioUrl}
          onTimeUpdate={(t, d) => { setCurrentTime(t); setAudioDuration(d); }}
        />
      )}

      {/* Results */}
      {result && phase === 'done' && (
        <AnalysisResults result={result} filename={filename} />
      )}

      {/* Upsell */}
      {phase === 'done' && (
        <a
          href="https://scanme2.gumroad.com"
          target="_blank"
          rel="noopener noreferrer"
          className="block rounded-xl border border-[#e63012]/20 bg-[#e63012]/5 px-5 py-4 hover:bg-[#e63012]/10 transition-colors"
        >
          <p className="text-sm font-mono text-[#E5E5E5]/80">
            Need stems, MIDI, or reference mastering?
          </p>
          <p className="text-xs font-mono text-[#e63012] mt-1">
            Get Full RAWMASTER — from £19, one-time, 100% local →
          </p>
        </a>
      )}

      {/* Analyse another */}
      {phase === 'done' && (
        <button
          onClick={reset}
          className="w-full rounded-xl border border-white/[0.08] bg-transparent px-5 py-3 text-sm text-white/40 hover:text-white/70 hover:border-white/20 transition-colors font-mono"
        >
          Analyse another file
        </button>
      )}
    </div>
  );
}
