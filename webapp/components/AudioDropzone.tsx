'use client';

import { useRef, useState, useCallback } from 'react';

interface Props {
  onFile: (file: File) => void;
  disabled?: boolean;
}

const ACCEPTED = ['audio/mpeg', 'audio/wav', 'audio/flac', 'audio/aiff', 'audio/x-aiff', 'audio/ogg', 'audio/mp4', 'audio/x-m4a', 'audio/webm'];

export default function AudioDropzone({ onFile, disabled }: Props) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(
    (file: File) => {
      if (!ACCEPTED.includes(file.type) && !file.name.match(/\.(mp3|wav|flac|aif|aiff|ogg|m4a|webm|opus)$/i)) return;
      onFile(file);
    },
    [onFile]
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const onInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); if (!disabled) setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={disabled ? undefined : onDrop}
      onClick={() => { if (!disabled) inputRef.current?.click(); }}
      className={[
        'relative flex flex-col items-center justify-center gap-4 rounded-2xl border-2 border-dashed transition-all duration-200 cursor-pointer select-none',
        'min-h-[280px] px-8 py-12',
        dragging
          ? 'border-[#C8962C] bg-[#C8962C]/5 shadow-[0_0_40px_0px_rgba(200,150,44,0.25)]'
          : 'border-white/10 hover:border-[#C8962C]/50 hover:bg-white/[0.02]',
        disabled ? 'opacity-50 cursor-not-allowed pointer-events-none' : '',
      ].join(' ')}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".mp3,.wav,.flac,.aif,.aiff,.ogg,.m4a,.webm,.opus,audio/*"
        className="hidden"
        onChange={onInputChange}
        disabled={disabled}
      />

      {/* Icon */}
      <div className={`w-16 h-16 rounded-full flex items-center justify-center transition-colors ${dragging ? 'bg-[#C8962C]/20' : 'bg-white/5'}`}>
        <svg viewBox="0 0 24 24" fill="none" className="w-8 h-8" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 9l10.5-3m0 6.553v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 11-.99-3.467l2.31-.66a2.25 2.25 0 001.632-2.163zm0 0V2.25L9 5.25v10.303m0 0v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 01-.99-3.467l2.31-.66A2.25 2.25 0 009 15.553z" />
        </svg>
      </div>

      <div className="text-center">
        <p className="text-lg font-medium text-[#E5E5E5]">
          {dragging ? 'Drop it' : 'Drop an audio file'}
        </p>
        <p className="mt-1 text-sm text-white/40">
          or click to browse &nbsp;·&nbsp; MP3, WAV, FLAC, AIFF, OGG, M4A
        </p>
      </div>
    </div>
  );
}
