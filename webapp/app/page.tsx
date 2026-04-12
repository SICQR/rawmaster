import AudioAnalyzer from '@/components/AudioAnalyzer';

export default function Home() {
  return (
    <main className="flex flex-col flex-1 min-h-screen px-4 py-16 sm:px-6">
      {/* Header */}
      <div className="w-full max-w-2xl mx-auto mb-12 space-y-2">
        <div className="flex items-center gap-3">
          <span className="font-mono text-2xl font-bold tracking-tighter text-[#C8962C]">
            RAWMASTER
          </span>
          <span className="rounded-full border border-[#C8962C]/30 px-2 py-0.5 text-[10px] font-mono uppercase tracking-widest text-[#C8962C]/70">
            web
          </span>
        </div>
        <p className="text-sm text-white/40 font-mono leading-relaxed">
          Drag-drop any audio file. BPM + key detection runs entirely in your browser.
          <br />
          No upload. No login. No limits.
        </p>
      </div>

      {/* Analyser */}
      <AudioAnalyzer />

      {/* Footer */}
      <footer className="mt-auto pt-16 pb-6 text-center">
        <p className="text-xs font-mono text-white/20">
          Powered by{' '}
          <span className="text-[#C8962C]/60">RAWMASTER</span>
          {' '}· Web Audio API · Runs 100% client-side
        </p>
      </footer>
    </main>
  );
}
