import { useState } from 'react';
import {
  Sparkles, ArrowRight, Upload, Brain, GitCompare, ShieldCheck,
  Building2, UserCheck, FileSearch, BarChart3, PlayCircle, AlertTriangle,
} from 'lucide-react';
import { authApi, tokenStore } from '../lib/api';
import type { User } from '../lib/api';

// Public demo credentials — seeded synthetic data only, no real resumes or PII.
// Mirrors backend/seed_demo.py (DEMO_RECRUITER_EMAIL / DEMO_RECRUITER_PASSWORD).
const DEMO_EMAIL = 'demo@aiscreenx.app';
const DEMO_PASSWORD = 'DemoScreenX2025';

interface Props {
  onAuth: (user: User) => void;
  onEnterAuth: () => void;
}

const FEATURES = [
  { icon: Upload, title: 'Resume ingestion', desc: 'PDF & DOCX parsing with private storage and pre-parse malware scanning.' },
  { icon: Brain, title: 'Explainable AI matching', desc: 'Deterministic TF-IDF scoring with skill overlap, experience fit, and evidence — no black box.' },
  { icon: FileSearch, title: 'Skill gap analysis', desc: 'Matched skills, missing skills, and confidence scores for every candidate.' },
  { icon: GitCompare, title: 'Candidate comparison', desc: 'Side-by-side ranking across applicants for any job.' },
  { icon: Building2, title: 'Multi-tenant ATS', desc: 'Organizations, memberships, invitations, and strict tenant isolation.' },
  { icon: ShieldCheck, title: 'Security-first', desc: 'JWT auth, audit logging, rate limiting, private resume storage, GDPR-style deletion.' },
];

const STEPS = [
  { icon: UserCheck, title: 'Register or sign in', desc: 'Create a candidate or recruiter account. Recruiters get their own organization automatically.' },
  { icon: FileSearch, title: 'Create a job', desc: 'Define the role with required skills, experience, and a job description.' },
  { icon: Upload, title: 'Upload resumes', desc: 'Drop in PDF or DOCX resumes — they are scanned, stored privately, and parsed.' },
  { icon: BarChart3, title: 'Review AI scores', desc: 'See ranked candidates with match scores, matched/missing skills, and evidence.' },
];

export default function LandingPage({ onAuth, onEnterAuth }: Props) {
  const [demoLoading, setDemoLoading] = useState(false);
  const [demoError, setDemoError] = useState<string | null>(null);

  const enterDemo = async () => {
    setDemoLoading(true);
    setDemoError(null);
    try {
      const res = await authApi.login({ email: DEMO_EMAIL, password: DEMO_PASSWORD });
      tokenStore.set(res.token);
      onAuth(res.user);
    } catch {
      setDemoError('Demo login unavailable — the demo service may be waking up. Try again in a minute.');
    } finally {
      setDemoLoading(false);
    }
  };

  return (
    <div className="space-y-20 animate-slide-up">
      {/* Hero */}
      <section className="text-center space-y-6 pt-10">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-cyan-500/10 border border-cyan-500/20 text-cyan-300 text-xs font-semibold tracking-wide">
          <Sparkles className="w-3.5 h-3.5" />
          AI-powered applicant tracking system
        </div>
        <h1 className="text-4xl sm:text-6xl font-black tracking-tight leading-tight">
          Screen resumes with{' '}
          <span className="bg-clip-text text-transparent bg-gradient-to-r from-cyan-300 via-sky-400 to-violet-400">
            explainable AI
          </span>
        </h1>
        <p className="max-w-2xl mx-auto text-slate-400 text-base sm:text-lg leading-relaxed">
          AI ScreenX parses resumes, matches candidates to jobs with transparent
          skill-based scoring, and gives recruiters an evidence-backed view of
          every applicant — no black-box rankings, no protected-characteristic bias.
        </p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
          <button
            onClick={enterDemo}
            disabled={demoLoading}
            className="flex items-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-cyan-500 to-violet-500 text-white text-sm font-bold hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            <PlayCircle className="w-4 h-4" />
            {demoLoading ? 'Waking up demo…' : 'Explore the live demo'}
          </button>
          <button
            onClick={onEnterAuth}
            className="flex items-center gap-2 px-6 py-3 rounded-xl bg-white/5 border border-white/10 text-sm font-semibold text-slate-200 hover:bg-white/10 transition-colors"
          >
            Create your own account <ArrowRight className="w-4 h-4" />
          </button>
        </div>
        {demoError && <p className="text-xs text-rose-400">{demoError}</p>}
      </section>

      {/* Features */}
      <section>
        <h2 className="text-2xl font-bold text-center mb-10">Everything a modern ATS needs</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {FEATURES.map((f) => (
            <div key={f.title} className="glass-panel p-6 space-y-3">
              <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center">
                <f.icon className="w-5 h-5 text-cyan-400" />
              </div>
              <h3 className="font-bold text-white text-sm">{f.title}</h3>
              <p className="text-xs text-slate-400 leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section>
        <h2 className="text-2xl font-bold text-center mb-10">How it works</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {STEPS.map((s, i) => (
            <div key={s.title} className="glass-panel p-6 space-y-3 relative">
              <span className="absolute top-4 right-5 text-3xl font-black text-white/5">{i + 1}</span>
              <s.icon className="w-6 h-6 text-violet-400" />
              <h3 className="font-bold text-white text-sm">{s.title}</h3>
              <p className="text-xs text-slate-400 leading-relaxed">{s.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Demo section */}
      <section className="glass-panel p-8 sm:p-10 space-y-6">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center shrink-0">
            <PlayCircle className="w-6 h-6 text-violet-400" />
          </div>
          <div>
            <h2 className="text-xl font-bold">Try the recruiter demo</h2>
            <p className="text-sm text-slate-400 mt-1 leading-relaxed">
              Sign in to a pre-loaded demo organization with 3 sample jobs and 24
              screened synthetic candidates. Explore rankings, skill gaps,
              evidence snippets, candidate comparison, and application statuses.
            </p>
          </div>
        </div>
        <div className="rounded-xl bg-white/5 border border-white/10 p-5 font-mono text-xs space-y-1">
          <p><span className="text-slate-500">email:</span> <span className="text-cyan-300">{DEMO_EMAIL}</span></p>
          <p><span className="text-slate-500">password:</span> <span className="text-cyan-300">{DEMO_PASSWORD}</span></p>
        </div>
        <button
          onClick={enterDemo}
          disabled={demoLoading}
          className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-white/5 border border-white/10 text-sm font-semibold text-white hover:bg-white/10 transition-colors disabled:opacity-50"
        >
          <PlayCircle className="w-4 h-4" />
          {demoLoading ? 'Signing in…' : 'Enter demo as recruiter'}
        </button>
        <div className="flex items-start gap-2 text-[11px] text-slate-500 leading-relaxed">
          <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0 text-amber-500/70" />
          <p>
            This is a public demo running on free-tier infrastructure. All demo
            data is synthetic — no real resumes or personal information. The demo
            service may sleep after periods of inactivity and take ~1 minute to
            wake. Malware scanning runs in optional mode on this deployment.
          </p>
        </div>
      </section>
    </div>
  );
}
