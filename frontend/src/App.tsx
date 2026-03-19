import { Sparkles, Github, ExternalLink } from 'lucide-react';
import CandidateDashboard from './pages/CandidateDashboard';

function App() {
  return (
    <div className="min-h-screen text-white font-sans selection:bg-cyan-500/30">
      {/* Premium Navigation */}
      <nav className="fixed top-0 left-0 right-0 h-16 bg-[#050a14]/80 backdrop-blur-2xl z-50 px-6 flex items-center justify-between border-b border-white/5">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-cyan-400 to-violet-500 rounded-xl flex items-center justify-center shadow-lg shadow-cyan-500/20 animate-pulse-glow">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div className="flex flex-col">
            <span className="text-lg font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white via-cyan-100 to-slate-300">
              AI ScreenX
            </span>
            <span className="text-[9px] font-semibold text-slate-500 tracking-widest uppercase -mt-0.5">
              Intelligent Resume Analysis
            </span>
          </div>
        </div>

        <div className="hidden md:flex items-center gap-3">
          <a
            href="https://github.com/tarun2806/Ai-Resume-Screener"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/5 border border-white/5 text-xs font-medium text-slate-400 hover:text-white hover:bg-white/10 hover:border-white/10 transition-all"
          >
            <Github className="w-3.5 h-3.5" />
            Source
            <ExternalLink className="w-3 h-3 opacity-50" />
          </a>
          <div className="px-4 py-1.5 rounded-full bg-gradient-to-r from-cyan-500/10 to-violet-500/10 border border-cyan-500/20">
            <span className="text-[10px] font-bold uppercase tracking-widest bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-violet-400">
              AI Powered
            </span>
          </div>
        </div>
      </nav>

      <main className="pt-24 pb-16 px-4 sm:px-6 max-w-[1400px] mx-auto">
        <CandidateDashboard />
      </main>

      {/* Footer */}
      <footer className="border-t border-white/5 py-6 px-6 text-center">
        <p className="text-[10px] font-medium text-slate-600 tracking-wider">
          Built with ❤️ by <span className="text-cyan-500/60 font-bold">Tarun S</span> • Powered by FastAPI + React + SBERT
        </p>
      </footer>
    </div>
  );
}

export default App;
