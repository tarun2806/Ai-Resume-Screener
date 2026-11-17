import { useCallback, useEffect, useState } from 'react';
import { BrainCircuit, Briefcase, Upload, CheckCircle2, Clock, XCircle, Loader2, FileText } from 'lucide-react';
import CandidateDashboard from './CandidateDashboard';
import { atsApi } from '../lib/api';
import { usePublicConfig } from '../hooks/usePublicConfig';
import type { ApplicationSummary, Job } from '../lib/api';

const statusColor: Record<string, string> = {
  new: 'bg-slate-500/15 text-slate-300 border-slate-500/20',
  reviewed: 'bg-blue-500/15 text-blue-300 border-blue-500/20',
  shortlisted: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/20',
  interview: 'bg-violet-500/15 text-violet-300 border-violet-500/20',
  rejected: 'bg-red-500/15 text-red-300 border-red-500/20',
};

export default function CandidatePortal() {
  const { uploads_enabled: uploadsEnabled } = usePublicConfig();
  const [tab, setTab] = useState<'analyze' | 'applications' | 'jobs'>('analyze');
  const [apps, setApps] = useState<ApplicationSummary[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [a, j] = await Promise.all([atsApi.myApplications(), atsApi.listJobs()]);
      setApps(a); setJobs(j);
    } catch { /* ignore */ } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const apply = async (jobId: number, file: File) => {
    setErr(null); setMsg(null);
    try {
      const app = await atsApi.apply(jobId, file);
      setMsg(`Application submitted for "${jobs.find(j => j.id === jobId)?.title}". Match score: ${Math.round(app.score)}.`);
      load();
    } catch (e) {
      const ax = e as { response?: { data?: { detail?: string } } };
      setErr(ax.response?.data?.detail || 'Application failed');
    }
  };

  const tabs = [
    { id: 'analyze' as const, label: 'AI Analyzer', icon: BrainCircuit },
    { id: 'jobs' as const, label: 'Browse Jobs', icon: Briefcase },
    { id: 'applications' as const, label: 'My Applications', icon: FileText },
  ];

  return (
    <div className="space-y-6">
      <div className="flex justify-center">
        <div className="flex rounded-2xl bg-white/5 border border-white/5 p-1.5">
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold uppercase tracking-wider transition-all ${
                tab === t.id ? 'bg-gradient-to-r from-cyan-500/20 to-violet-500/20 text-white border border-cyan-500/20' : 'text-slate-500 hover:text-slate-300'
              }`}
            >
              <t.icon className="w-4 h-4" />{t.label}
            </button>
          ))}
        </div>
      </div>

      {msg && <div className="max-w-2xl mx-auto p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-xs text-emerald-300 flex items-center gap-2"><CheckCircle2 className="w-4 h-4" />{msg}</div>}
      {err && <div className="max-w-2xl mx-auto p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-xs text-red-300 flex items-center gap-2"><XCircle className="w-4 h-4" />{err}</div>}

      {tab === 'analyze' && <CandidateDashboard />}

      {tab === 'jobs' && (
        <div className="max-w-3xl mx-auto space-y-4">
          {loading ? <Loader2 className="w-6 h-6 animate-spin text-cyan-400 mx-auto" /> : jobs.length === 0 ? (
            <div className="glass-panel p-12 text-center text-slate-600 text-xs">No open positions right now.</div>
          ) : jobs.map((j) => (
            <JobCard key={j.id} job={j} onApply={apply} uploadsEnabled={uploadsEnabled} />
          ))}
        </div>
      )}

      {tab === 'applications' && (
        <div className="max-w-3xl mx-auto space-y-3">
          {loading ? <Loader2 className="w-6 h-6 animate-spin text-cyan-400 mx-auto" /> : apps.length === 0 ? (
            <div className="glass-panel p-12 text-center text-slate-600 text-xs">You haven't applied to any jobs yet.</div>
          ) : apps.map((a) => (
            <div key={a.id} className="glass-panel p-5">
              <div className="flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <p className="text-sm font-bold text-white">{a.job_title || `Job #${a.job_id}`}</p>
                  <p className="text-[10px] text-slate-500 mt-0.5">{a.resume_filename} · {a.created_at ? new Date(a.created_at).toLocaleDateString() : ''}</p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="font-mono font-black text-cyan-400">{Math.round(a.score)}</span>
                  <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full border ${statusColor[a.status] || statusColor.new}`}>{a.status}</span>
                </div>
              </div>
              <div className="flex flex-wrap gap-1.5 mt-3">
                {a.matched_skills.slice(0, 6).map((s) => <span key={s} className="skill-tag skill-matched text-[9px]"><CheckCircle2 className="w-3 h-3" />{s}</span>)}
                {a.missing_skills.slice(0, 4).map((s) => <span key={s} className="skill-tag skill-missing text-[9px]"><XCircle className="w-3 h-3" />{s}</span>)}
              </div>
              {a.recruiter_notes && <p className="text-[10px] text-slate-500 mt-2 italic">"{a.recruiter_notes}"</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function JobCard({ job, onApply, uploadsEnabled }: { job: Job; onApply: (id: number, f: File) => void; uploadsEnabled: boolean }) {
  const [busy, setBusy] = useState(false);
  return (
    <div className="glass-panel p-6 space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-base font-bold text-white">{job.title}</h3>
          <p className="text-[10px] text-slate-500 mt-1 flex items-center gap-2">
            <Clock className="w-3 h-3" />{job.location || 'Remote'}
            {job.min_years ? ` · ${job.min_years}+ yrs` : ''} · {job.application_count} applicants
          </p>
        </div>
        <span className="text-[9px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">open</span>
      </div>
      <p className="text-xs text-slate-400 line-clamp-3 leading-relaxed">{job.description}</p>
      <div className="flex flex-wrap gap-1.5">
        {job.required_skills.slice(0, 10).map((s) => <span key={s} className="skill-tag text-[9px]"><Briefcase className="w-3 h-3" />{s}</span>)}
      </div>
      {uploadsEnabled ? (
        <label className={`btn-glow inline-flex px-5 py-2.5 text-[10px] font-bold uppercase tracking-wider cursor-pointer ${busy ? 'opacity-50 pointer-events-none' : ''}`}>
          {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <><Upload className="w-3.5 h-3.5" /> Apply with Resume</>}
          <input
            type="file" accept=".pdf,.docx" className="hidden"
            onChange={async (e) => {
              const f = e.target.files?.[0];
              if (!f) return;
              setBusy(true);
              await onApply(job.id, f);
              setBusy(false);
              e.target.value = '';
            }}
          />
        </label>
      ) : (
        <span className="inline-flex px-4 py-2 text-[10px] font-bold uppercase tracking-wider text-amber-400/80 border border-amber-500/20 rounded-lg">
          Applications closed — demo mode
        </span>
      )}
    </div>
  );
}
