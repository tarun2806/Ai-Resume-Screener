import React from 'react';
import { Sparkles } from 'lucide-react';
import CandidateDashboard from './pages/CandidateDashboard';

function App() {
  return (
    <div className="min-h-screen bg-[#020617] text-white font-sans selection:bg-rose-500/30">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 h-16 bg-slate-950/50 backdrop-blur-xl z-50 px-6 flex items-center justify-between border-b border-white/5">
        <div className="flex items-center gap-2">
          <div className="w-9 h-9 bg-gradient-to-br from-rose-500 to-rose-600 rounded-xl flex items-center justify-center shadow-lg shadow-rose-500/20">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <span className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400">
            Smart Resume Checker
          </span>
        </div>

        <div className="hidden md:flex items-center gap-4">
          <div className="px-3 py-1 rounded-full bg-rose-500/10 border border-rose-500/20">
            <span className="text-[10px] font-black uppercase tracking-widest text-rose-400">AI Powered Analysis</span>
          </div>
        </div>
      </nav>

      <main className="pt-24 pb-12 px-6 max-w-7xl mx-auto">
        <CandidateDashboard />
      </main>
    </div>
  );
}

export default App;
