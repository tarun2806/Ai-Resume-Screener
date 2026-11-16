import { useState } from 'react';
import { Sparkles, LogIn, UserPlus, AlertCircle } from 'lucide-react';
import { authApi } from '../lib/api';
import type { User } from '../lib/api';

interface Props {
  onAuth: (user: User, token: string) => void;
}

export default function AuthPage({ onAuth }: Props) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<'candidate' | 'recruiter'>('candidate');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res =
        mode === 'login'
          ? await authApi.login({ email, password })
          : await authApi.register({ email, password, name, role });
      localStorage.setItem('aiscreenx_token', res.token);
      onAuth(res.user, res.token);
    } catch (err) {
      const ax = err as { response?: { data?: { detail?: string } } };
      setError(ax.response?.data?.detail || 'Authentication failed. Check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  const inputCls =
    'w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-cyan-500/50 focus:bg-white/[0.07] transition-all';

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-md space-y-6 animate-slide-up">
        <div className="text-center space-y-3">
          <div className="w-16 h-16 mx-auto bg-gradient-to-br from-cyan-400 to-violet-500 rounded-2xl flex items-center justify-center shadow-lg shadow-cyan-500/20">
            <Sparkles className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-3xl font-black tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white via-cyan-100 to-slate-300">
            AI ScreenX
          </h1>
          <p className="text-sm text-slate-500 font-medium">
            Intelligent resume screening and applicant tracking
          </p>
        </div>

        <div className="glass-panel p-8 space-y-5">
          <div className="flex rounded-xl bg-white/5 border border-white/5 p-1">
            {(['login', 'register'] as const).map((m) => (
              <button
                key={m}
                onClick={() => { setMode(m); setError(null); }}
                className={`flex-1 py-2 text-xs font-bold uppercase tracking-wider rounded-lg transition-all ${
                  mode === m ? 'bg-gradient-to-r from-cyan-500/20 to-violet-500/20 text-white border border-cyan-500/20' : 'text-slate-500 hover:text-slate-300'
                }`}
              >
                {m === 'login' ? 'Sign In' : 'Create Account'}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="space-y-4">
            {mode === 'register' && (
              <>
                <input className={inputCls} placeholder="Full name" value={name} onChange={(e) => setName(e.target.value)} required />
                <div className="flex rounded-xl bg-white/5 border border-white/10 p-1">
                  {(['candidate', 'recruiter'] as const).map((r) => (
                    <button
                      type="button"
                      key={r}
                      onClick={() => setRole(r)}
                      className={`flex-1 py-2 text-[11px] font-bold uppercase tracking-wider rounded-lg transition-all ${
                        role === r ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/20' : 'text-slate-500'
                      }`}
                    >
                      {r}
                    </button>
                  ))}
                </div>
              </>
            )}
            <input className={inputCls} type="email" placeholder="Email address" value={email} onChange={(e) => setEmail(e.target.value)} required />
            <input className={inputCls} type="password" placeholder="Password (min 8 chars)" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={mode === 'register' ? 8 : 1} />

            {error && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
                <p className="text-xs text-red-300">{error}</p>
              </div>
            )}

            <button type="submit" disabled={loading} className="btn-glow w-full py-3.5 text-sm font-bold uppercase tracking-wider flex items-center justify-center gap-2">
              {loading ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : mode === 'login' ? (
                <><LogIn className="w-4 h-4" /> Sign In</>
              ) : (
                <><UserPlus className="w-4 h-4" /> Create Account</>
              )}
            </button>
          </form>
        </div>

        <p className="text-center text-[10px] text-slate-600 font-medium">
          Demo: register a recruiter or candidate account to explore the ATS.
        </p>
      </div>
    </div>
  );
}
