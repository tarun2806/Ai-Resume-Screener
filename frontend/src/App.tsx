import { useEffect, useState } from 'react';
import { Sparkles, LogOut, User as UserIcon, ShieldCheck } from 'lucide-react';
import AuthPage from './components/AuthPage';
import CandidatePortal from './pages/CandidatePortal';
import RecruiterDashboard from './pages/RecruiterDashboard';
import { authApi, tokenStore } from './lib/api';
import type { User } from './lib/api';

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [booting, setBooting] = useState(() => !!tokenStore.get());

  useEffect(() => {
    if (!tokenStore.get()) return;
    authApi.me()
      .then(setUser)
      .catch(() => tokenStore.clear())
      .finally(() => setBooting(false));
  }, []);

  const logout = () => {
    tokenStore.clear();
    setUser(null);
  };

  return (
    <div className="min-h-screen text-white font-sans selection:bg-cyan-500/30">
      <nav className="fixed top-0 left-0 right-0 h-16 bg-[#050a14]/80 backdrop-blur-2xl z-50 px-6 flex items-center justify-between border-b border-white/5">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-cyan-400 to-violet-500 rounded-xl flex items-center justify-center shadow-lg shadow-cyan-500/20">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div className="flex flex-col">
            <span className="text-lg font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white via-cyan-100 to-slate-300">
              AI ScreenX
            </span>
            <span className="text-[9px] font-semibold text-slate-500 tracking-widest uppercase -mt-0.5">
              Intelligent ATS
            </span>
          </div>
        </div>

        {user && (
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/5 border border-white/5">
              <UserIcon className="w-3.5 h-3.5 text-cyan-400" />
              <span className="text-xs font-medium text-slate-300">{user.name}</span>
              <span className="text-[9px] font-bold uppercase tracking-wider text-violet-400 flex items-center gap-1">
                {user.role === 'admin' && <ShieldCheck className="w-3 h-3" />}{user.role}
              </span>
            </div>
            <button
              onClick={logout}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/5 border border-white/5 text-xs font-medium text-slate-400 hover:text-white hover:bg-white/10 transition-all"
            >
              <LogOut className="w-3.5 h-3.5" />
              Sign out
            </button>
          </div>
        )}
      </nav>

      <main className="pt-24 pb-16 px-4 sm:px-6 max-w-[1400px] mx-auto">
        {booting ? (
          <div className="flex justify-center py-32">
            <div className="w-10 h-10 border-2 border-cyan-500/20 border-t-cyan-500 rounded-full animate-spin" />
          </div>
        ) : !user ? (
          <AuthPage onAuth={(u) => setUser(u)} />
        ) : user.role === 'candidate' ? (
          <CandidatePortal />
        ) : (
          <RecruiterDashboard user={user} />
        )}
      </main>

      <footer className="border-t border-white/5 py-6 px-6 text-center">
        <p className="text-[10px] font-medium text-slate-600 tracking-wider">
          AI ScreenX ATS • Deterministic skill matching • Explainable scores
        </p>
      </footer>
    </div>
  );
}

export default App;
