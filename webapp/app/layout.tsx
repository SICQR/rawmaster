import type { Metadata, Viewport } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import './globals.css';

const geistSans = Geist({ variable: '--font-geist-sans', subsets: ['latin'] });
const geistMono = Geist_Mono({ variable: '--font-geist-mono', subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'RAWMASTER — Audio Analysis',
  description: 'Browser-based BPM detection, key detection and waveform visualisation. No upload, no login — runs entirely in your browser.',
  openGraph: {
    title: 'RAWMASTER — Audio Analysis',
    description: 'Instant BPM & key detection. Drag-drop any audio file.',
    type: 'website',
  },
};

export const viewport: Viewport = {
  themeColor: '#0a0a0a',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      style={{ colorScheme: 'dark' }}
    >
      <body className="min-h-full flex flex-col bg-[#0a0a0a] text-[#e5e5e5]">{children}</body>
    </html>
  );
}
