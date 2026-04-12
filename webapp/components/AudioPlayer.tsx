'use client';

import { useEffect, useRef, useState } from 'react';

interface Props {
  src: string;
  onTimeUpdate?: (currentTime: number, duration: number) => void;
}

function formatTime(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, '0')}`;
}

export default function AudioPlayer({ src, onTimeUpdate }: Props) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [seeking, setSeeking] = useState(false);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const onMeta = () => setDuration(audio.duration || 0);
    const onTime = () => {
      setCurrentTime(audio.currentTime);
      onTimeUpdate?.(audio.currentTime, audio.duration || 1);
    };
    const onEnded = () => setPlaying(false);

    audio.addEventListener('loadedmetadata', onMeta);
    audio.addEventListener('timeupdate', onTime);
    audio.addEventListener('ended', onEnded);
    return () => {
      audio.removeEventListener('loadedmetadata', onMeta);
      audio.removeEventListener('timeupdate', onTime);
      audio.removeEventListener('ended', onEnded);
    };
  }, [onTimeUpdate]);

  const togglePlay = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (playing) {
      audio.pause();
      setPlaying(false);
    } else {
      audio.play().then(() => setPlaying(true)).catch(() => {});
    }
  };

  const onSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const audio = audioRef.current;
    if (!audio) return;
    const t = parseFloat(e.target.value);
    audio.currentTime = t;
    setCurrentTime(t);
  };

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div className="flex items-center gap-4 rounded-xl border border-white/[0.08] bg-[#141414] px-5 py-4">
      <audio ref={audioRef} src={src} preload="metadata" />

      {/* Play / Pause */}
      <button
        onClick={togglePlay}
        className="shrink-0 w-10 h-10 rounded-full flex items-center justify-center bg-[#C8962C] hover:bg-[#D9A83C] transition-colors active:scale-95"
        aria-label={playing ? 'Pause' : 'Play'}
      >
        {playing ? (
          <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 text-black">
            <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 text-black ml-0.5">
            <path d="M8 5v14l11-7z" />
          </svg>
        )}
      </button>

      {/* Scrubber */}
      <div className="flex-1 flex flex-col gap-1 min-w-0">
        <div className="relative h-1 rounded-full bg-white/10 cursor-pointer">
          <div
            className="absolute inset-y-0 left-0 rounded-full bg-[#C8962C] transition-none"
            style={{ width: `${progress}%` }}
          />
          <input
            type="range"
            min={0}
            max={duration || 100}
            step={0.01}
            value={currentTime}
            onChange={onSeek}
            onMouseDown={() => setSeeking(true)}
            onMouseUp={() => setSeeking(false)}
            className="absolute inset-0 w-full opacity-0 cursor-pointer h-full"
            aria-label="Seek"
          />
        </div>
        <div className="flex justify-between text-xs font-mono text-white/30">
          <span>{formatTime(currentTime)}</span>
          <span>{formatTime(duration)}</span>
        </div>
      </div>
    </div>
  );
}
