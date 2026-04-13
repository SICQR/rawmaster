'use client';

import { useState } from 'react';
import type { AnalysisResult } from '@/lib/audioAnalysis';

interface Props {
  result: AnalysisResult;
  filename: string;
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function formatSampleRate(hz: number): string {
  return `${(hz / 1000).toFixed(1)} kHz`;
}

interface StatCardProps {
  label: string;
  value: string;
  sub?: string;
  accent?: boolean;
}

function StatCard({ label, value, sub, accent }: StatCardProps) {
  return (
    <div className="flex flex-col gap-1 rounded-xl bg-white/[0.03] border border-white/[0.06] px-5 py-4">
      <span className="text-xs font-medium uppercase tracking-widest text-white/30">{label}</span>
      <span
        className={`font-mono text-3xl font-semibold leading-none ${accent ? 'text-[#e63012]' : 'text-[#E5E5E5]'}`}
      >
        {value}
      </span>
      {sub && <span className="text-xs text-white/25 font-mono">{sub}</span>}
    </div>
  );
}

export default function AnalysisResults({ result, filename }: Props) {
  const [keyRoot, keyMode] = result.key.split(' ');
  const [copied, setCopied] = useState(false);

  const copyResults = () => {
    const text = `BPM: ${result.bpm} | Key: ${result.key} | Duration: ${formatDuration(result.duration)}`;
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className="rounded-2xl border border-white/[0.08] bg-[#141414] p-6 space-y-4 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-widest text-white/30 font-medium mb-1">Analysis Complete</p>
          <p className="truncate text-sm text-[#E5E5E5]/70 font-mono">{filename}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={copyResults}
            className="rounded-full border border-white/10 px-3 py-1 text-xs font-mono text-white/40 hover:text-white/70 hover:border-white/20 transition-colors"
          >
            {copied ? 'Copied!' : 'Copy'}
          </button>
          <span className="rounded-full bg-[#e63012]/15 px-3 py-1 text-xs font-medium text-[#e63012] border border-[#e63012]/20">
            RAWMASTER
          </span>
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="BPM" value={result.bpm.toString()} accent />
        <StatCard
          label="Key"
          value={keyRoot}
          sub={keyMode}
          accent
        />
        <StatCard label="Duration" value={formatDuration(result.duration)} />
        <StatCard label="Sample Rate" value={formatSampleRate(result.sampleRate)} />
      </div>

      {/* Confidence note */}
      <p className="text-xs text-white/20 font-mono">
        BPM and key are estimated via Web Audio API autocorrelation + chroma analysis.
      </p>
    </div>
  );
}
