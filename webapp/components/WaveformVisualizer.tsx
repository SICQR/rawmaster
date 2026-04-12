'use client';

import { useEffect, useRef } from 'react';

interface Props {
  waveform: Float32Array;
  currentTime?: number;
  duration?: number;
}

export default function WaveformVisualizer({ waveform, currentTime = 0, duration = 1 }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const w = canvas.offsetWidth;
    const h = canvas.offsetHeight;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.scale(dpr, dpr);

    ctx.clearRect(0, 0, w, h);

    const progress = duration > 0 ? currentTime / duration : 0;
    const progressX = progress * w;
    const barW = Math.max(1, w / waveform.length);
    const mid = h / 2;

    for (let i = 0; i < waveform.length; i++) {
      const x = (i / waveform.length) * w;
      const barH = Math.max(2, waveform[i] * h * 0.9);

      const isPast = x < progressX;
      ctx.fillStyle = isPast ? '#C8962C' : 'rgba(255,255,255,0.15)';
      ctx.fillRect(x, mid - barH / 2, barW - 1, barH);
    }

    // Playhead line
    if (progress > 0) {
      ctx.strokeStyle = '#C8962C';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(progressX, 0);
      ctx.lineTo(progressX, h);
      ctx.stroke();
    }
  }, [waveform, currentTime, duration]);

  return (
    <canvas
      ref={canvasRef}
      className="w-full h-20 rounded-lg"
      style={{ display: 'block' }}
    />
  );
}
