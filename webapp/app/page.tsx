import AudioAnalyzer from '@/components/AudioAnalyzer';

export default function Home() {
  return (
    <main className="flex flex-col flex-1 min-h-screen px-4 py-16 sm:px-6">
      {/* Header */}
      <div className="w-full max-w-2xl mx-auto mb-12 space-y-2">
        <div className="flex items-center gap-3">
          <span className="font-mono text-2xl font-bold tracking-tighter text-[#e63012]">
            RAWMASTER
          </span>
          <span className="rounded-full border border-[#e63012]/30 px-2 py-0.5 text-[10px] font-mono uppercase tracking-widest text-[#e63012]/70">
            web
          </span>
        </div>
        <p className="text-sm text-white/40 font-mono leading-relaxed">
          Drag-drop any audio file. BPM + key detection runs entirely in your browser.
          <br />
          No upload. No login. No limits.
        </p>
        <p className="text-xs text-white/20 font-mono mt-2">
          Need stems, MIDI, or reference mastering?{' '}
          <a href="https://scanme2.gumroad.com" target="_blank" rel="noopener noreferrer" className="text-[#e63012]/60 hover:text-[#e63012] transition-colors">
            Get the full version
          </a>
        </p>
      </div>

      {/* Analyser */}
      <AudioAnalyzer />

      {/* Footer */}
      <footer className="mt-auto pt-16 pb-6 text-center">
        <p className="text-xs font-mono text-white/20">
          Powered by{' '}
          <span className="text-[#e63012]/60">RAWMASTER</span>
          {' '}· Web Audio API · Runs 100% client-side
        </p>
      </footer>
    </main>
  );
}
