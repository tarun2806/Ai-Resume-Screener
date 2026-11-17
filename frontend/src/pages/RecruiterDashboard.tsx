import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Briefcase, Plus, Upload, Download, Users, BarChart3,
  CheckCircle2, Clock, XCircle, MessageSquare, ChevronDown, ChevronUp,
  Sparkles, Building2, Mail, AlertCircle, Loader2, ShieldCheck,
} from 'lucide-react';
import { atsApi } from '../lib/api';
import type { Analytics, ApplicationDetail, ApplicationSummary, CompareResult, Job, JobInsights, ScoreComponent, User } from '../lib/api';

const STATUSES = ['new', 'reviewed', 'shortlisted', 'rejected', 'interview'];

const statusColor: Record<string, string> = {
  new: 'bg-slate-500/15 text-slate-300 border-slate-500/20',
  reviewed: 'bg-blue-500/15 text-blue-300 border-blue-500/20',
  shortlisted: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/20',
  interview: 'bg-violet-500/15 text-violet-300 border-violet-500/20',
  rejected: 'bg-red-500/15 text-red-300 border-red-500/20',
};

const ScorePill = ({ score }: { score: number }) => {
  const color = score >= 70 ? 'text-emerald-400' : score >= 50 ? 'text-cyan-400' : score >= 30 ? 'text-violet-400' : 'text-red-400';
  return <span className={`font-mono font-bold ${color}`}>{Math.round(score)}</span>;
};

const SkillChips = ({ skills, tone }: { skills: string[]; tone: 'matched' | 'missing' }) => (
  <div className="flex flex-wrap gap-1.5">
    {skills.slice(0, 12).map((s) => (
      <span key={s} className={`text-[10px] px-2 py-0.5 rounded-full border ${tone === 'matched' ? 'skill-matched' : 'skill-missing'}`}>
        {s}
      </span>
    ))}
    {skills.length > 12 && <span className="text-[10px] text-slate-600">+{skills.length - 12}</span>}
  </div>
);

/* ---------- Job create/edit form ---------- */
const JobForm = ({ initial, onSave, onCancel }: {
  initial?: Job;
  onSave: (body: { title: string; description: string; location: string; status: string }) => Promise<void>;
  onCancel: () => void;
}) => {
  const [title, setTitle] = useState(initial?.title || '');
  const [location, setLocation] = useState(initial?.location || '');
  const [description, setDescription] = useState(initial?.description || '');
  const [status, setStatus] = useState<string>(initial?.status || 'open');
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async () => {
    if (title.trim().length < 3 || description.trim().length < 50) {
      setErr('Title (3+ chars) and description (50+ chars) are required.');
      return;
    }
    setSaving(true); setErr(null);
    try {
      await onSave({ title: title.trim(), description: description.trim(), location: location.trim(), status });
    } catch (e) {
      const ax = e as { response?: { data?: { detail?: string } } };
      setErr(ax.response?.data?.detail || 'Failed to save job');
    } finally {
      setSaving(false);
    }
  };

  const cls = 'w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-cyan-500/50 transition-all';
  return (
    <div className="glass-panel p-6 space-y-4 animate-slide-up">
      <h3 className="text-base font-bold text-white flex items-center gap-2">
        <Briefcase className="w-4 h-4 text-cyan-400" />
        {initial ? 'Edit Job' : 'Post a New Job'}
      </h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <input className={cls} placeholder="Job title *" value={title} onChange={(e) => setTitle(e.target.value)} />
        <input className={cls} placeholder="Location" value={location} onChange={(e) => setLocation(e.target.value)} />
      </div>
      <textarea className={`${cls} h-44 resize-none`} placeholder="Full job description (requirements, responsibilities, skills)..." value={description} onChange={(e) => setDescription(e.target.value)} />
      <div className="flex items-center gap-3">
        <select className={cls + ' w-36'} value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="open">Open</option>
          <option value="draft">Draft</option>
          <option value="closed">Closed</option>
        </select>
        <button onClick={submit} disabled={saving} className="btn-glow px-6 py-2.5 text-xs font-bold uppercase tracking-wider">
          {saving ? 'Saving...' : initial ? 'Update' : 'Create Job'}
        </button>
        <button onClick={onCancel} className="px-4 py-2.5 text-xs font-bold text-slate-500 hover:text-white transition-colors">Cancel</button>
      </div>
      {err && <p className="text-xs text-red-400 flex items-center gap-1"><AlertCircle className="w-3.5 h-3.5" />{err}</p>}
      <p className="text-[10px] text-slate-600">AI will extract required skills and experience requirements from the description automatically.</p>
    </div>
  );
};

/* ---------- Application detail drawer ---------- */
const ApplicationDetailPanel = ({ appId, onClose, onUpdated }: {
  appId: number; onClose: () => void; onUpdated: () => void;
}) => {
  const [detail, setDetail] = useState<ApplicationDetail | null>(null);
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    atsApi.getApplication(appId).then((d) => { setDetail(d); setNotes(d.recruiter_notes || ''); }).catch(() => {});
  }, [appId]);

  if (!detail) return <div className="glass-panel p-8 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-cyan-400" /></div>;

  const mr = detail.match_result as {
    overall_score?: number; verdict?: string; explanation?: string;
    breakdown?: Record<string, number>; suggestions?: { tip: string; impact: string }[];
    confidence?: number; ai_reasoning?: string[];
    score_breakdown?: ScoreComponent[];
    preferred_skills?: string[]; preferred_skills_matched?: string[];
    evidence?: { skill: string; snippet: string | null }[];
    extraction_limitations?: string[];
  };

  const saveNotes = async () => {
    setSaving(true);
    try { await atsApi.updateApplication(appId, { notes }); onUpdated(); } finally { setSaving(false); }
  };

  return (
    <div className="glass-panel p-6 space-y-5 animate-slide-up">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-lg font-bold text-white">{detail.candidate_name || 'Unknown candidate'}</h3>
          <p className="text-xs text-slate-500 flex items-center gap-2 mt-1">
            <Mail className="w-3 h-3" />{detail.candidate_email} · {detail.resume_filename}
          </p>
        </div>
        <button onClick={onClose} className="text-slate-500 hover:text-white text-lg leading-none">×</button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          ['Score', `${Math.round(detail.score)}`, 'text-cyan-400'],
          ['Verdict', String(mr.verdict || '—'), 'text-white'],
          ['Confidence', mr.confidence != null ? `${mr.confidence}%` : '—', 'text-violet-400'],
          ['Experience', detail.experience_years != null ? `${detail.experience_years} yrs` : 'Unknown', 'text-emerald-400'],
        ].map(([l, v, c]) => (
          <div key={l as string} className="bg-white/[0.03] border border-white/5 rounded-xl p-3 text-center">
            <p className="text-[9px] uppercase tracking-widest text-slate-600 font-bold">{l}</p>
            <p className={`text-sm font-black mt-1 ${c}`}>{v}</p>
          </div>
        ))}
      </div>

      {mr.breakdown && (
        <div className="space-y-2">
          {Object.entries(mr.breakdown).map(([k, v]) => (
            <div key={k}>
              <div className="flex justify-between text-[10px] font-semibold text-slate-400 mb-1">
                <span className="capitalize">{k.replace(/_/g, ' ')}</span><span className="font-mono">{Math.round(v as number)}%</span>
              </div>
              <div className="progress-track"><div className="progress-fill" style={{ width: `${v}%`, backgroundColor: '#06b6d4', color: '#06b6d4' }} /></div>
            </div>
          ))}
        </div>
      )}

      {Array.isArray(mr.score_breakdown) && mr.score_breakdown.length > 0 && (
        <div>
          <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2">Score formula (weighted)</p>
          <div className="space-y-1.5">
            {mr.score_breakdown.map((c) => (
              <div key={c.key} className="flex items-center gap-3 text-[11px]">
                <span className="w-40 text-slate-400 truncate">{c.component}</span>
                <div className="flex-1 progress-track"><div className="progress-fill" style={{ width: `${c.score}%`, backgroundColor: '#8b5cf6', color: '#8b5cf6' }} /></div>
                <span className="font-mono text-slate-300 w-10 text-right">{Math.round(c.score)}</span>
                <span className="font-mono text-slate-600 w-12 text-right">×{c.weight.toFixed(2)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {Array.isArray(mr.preferred_skills) && mr.preferred_skills.length > 0 && (
        <div>
          <p className="text-[10px] font-bold text-amber-400 uppercase tracking-widest mb-2">
            Preferred skills ({(mr.preferred_skills_matched || []).length}/{mr.preferred_skills.length} found)
          </p>
          <SkillChips skills={mr.preferred_skills} tone={(mr.preferred_skills_matched || []).length ? 'matched' : 'missing'} />
        </div>
      )}

      {Array.isArray(mr.evidence) && mr.evidence.some((e) => e.snippet) && (
        <div>
          <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2">Resume evidence</p>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {mr.evidence.filter((e) => e.snippet).slice(0, 8).map((e, i) => (
              <p key={i} className="text-[11px] text-slate-400 bg-white/[0.03] border border-white/5 rounded-lg px-3 py-1.5">
                <span className="text-cyan-400 font-bold">{e.skill}:</span> {e.snippet}
              </p>
            ))}
          </div>
        </div>
      )}

      {Array.isArray(mr.extraction_limitations) && mr.extraction_limitations.length > 0 && (
        <div className="bg-amber-500/[0.06] border border-amber-500/15 rounded-xl p-3">
          <p className="text-[10px] font-bold text-amber-400 uppercase tracking-widest mb-1.5">Extraction limitations</p>
          <ul className="space-y-1">
            {mr.extraction_limitations.map((l, i) => <li key={i} className="text-[11px] text-amber-200/70">• {l}</li>)}
          </ul>
        </div>
      )}

      {mr.explanation && <p className="text-xs text-slate-400 italic">"{mr.explanation}"</p>}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <p className="text-[10px] font-bold text-emerald-400 uppercase tracking-widest mb-2">Matched skills ({detail.matched_skills.length})</p>
          <SkillChips skills={detail.matched_skills} tone="matched" />
        </div>
        <div>
          <p className="text-[10px] font-bold text-red-400 uppercase tracking-widest mb-2">Missing skills ({detail.missing_skills.length})</p>
          <SkillChips skills={detail.missing_skills} tone="missing" />
        </div>
      </div>

      {Array.isArray(mr.suggestions) && mr.suggestions.length > 0 && (
        <div>
          <p className="text-[10px] font-bold text-amber-400 uppercase tracking-widest mb-2">AI Suggestions</p>
          <ul className="space-y-1.5">
            {mr.suggestions.slice(0, 4).map((s, i) => (
              <li key={i} className="text-xs text-slate-400 flex gap-2"><Sparkles className="w-3 h-3 text-amber-400/60 shrink-0 mt-0.5" />{s.tip} <span className="text-emerald-400 font-bold whitespace-nowrap">{s.impact}</span></li>
            ))}
          </ul>
        </div>
      )}

      <div className="space-y-2">
        <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest flex items-center gap-1.5"><MessageSquare className="w-3 h-3" />Recruiter notes</p>
        <textarea className="w-full px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-xs text-white h-20 resize-none focus:outline-none focus:border-cyan-500/50" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Internal notes, interview feedback..." />
        <button onClick={saveNotes} disabled={saving} className="text-[10px] font-bold uppercase tracking-wider text-cyan-400 hover:text-cyan-300">{saving ? 'Saving...' : 'Save notes'}</button>
      </div>
    </div>
  );
};

/* ---------- Candidate comparison view ---------- */
const CompareView = ({ data, onClose }: { data: CompareResult; onClose: () => void }) => {
  const skills = Object.keys(data.skill_matrix);
  return (
    <div className="glass-panel p-6 space-y-5 animate-slide-up">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-bold text-white flex items-center gap-2"><Users className="w-5 h-5 text-violet-400" />Candidate comparison</h3>
        <button onClick={onClose} className="text-slate-500 hover:text-white text-lg leading-none">×</button>
      </div>

      <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(${data.candidates.length}, minmax(0,1fr))` }}>
        {data.candidates.map((c, rank) => (
          <div key={c.id} className="bg-white/[0.03] border border-white/10 rounded-xl p-4 space-y-3">
            <div>
              <p className="text-[9px] font-bold text-slate-600 uppercase tracking-widest">Rank #{rank + 1}</p>
              <p className="text-sm font-bold text-white truncate">{c.candidate_name || 'Unknown'}</p>
              <p className="text-[10px] text-slate-500 truncate">{c.candidate_email}</p>
            </div>
            <div className="flex items-baseline gap-2">
              <span className={`text-2xl font-black font-mono ${c.score >= 70 ? 'text-emerald-400' : c.score >= 50 ? 'text-cyan-400' : 'text-red-400'}`}>{Math.round(c.score)}</span>
              <span className="text-[9px] text-slate-500">{c.verdict || ''}</span>
            </div>
            <div className="text-[10px] text-slate-500 space-y-0.5">
              <p>Experience: {c.experience_years != null ? `${c.experience_years} yrs` : 'Unknown'}</p>
              <p>Confidence: {c.confidence != null ? `${c.confidence}%` : '—'}</p>
              <p>Preferred found: {c.preferred_skills_matched.length}</p>
            </div>
            <div className="space-y-1">
              {c.score_breakdown.map((b) => (
                <div key={b.key} className="flex items-center gap-2 text-[9px]">
                  <span className="w-16 text-slate-500 truncate">{b.component.split(' ')[0]}</span>
                  <div className="flex-1 progress-track"><div className="progress-fill" style={{ width: `${b.score}%`, backgroundColor: '#8b5cf6', color: '#8b5cf6' }} /></div>
                  <span className="font-mono text-slate-400 w-6 text-right">{Math.round(b.score)}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {skills.length > 0 && (
        <div>
          <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2">Skill coverage matrix</p>
          <div className="overflow-x-auto">
            <table className="w-full text-[11px]">
              <thead>
                <tr className="text-slate-500 text-left">
                  <th className="py-1.5 pr-3 font-semibold">Skill</th>
                  {data.candidates.map((c) => <th key={c.id} className="py-1.5 px-2 font-semibold truncate max-w-[120px]">{c.candidate_name || `#${c.id}`}</th>)}
                </tr>
              </thead>
              <tbody>
                {skills.map((s) => (
                  <tr key={s} className="border-t border-white/5">
                    <td className="py-1.5 pr-3 text-slate-300">{s}</td>
                    {data.candidates.map((c) => {
                      const st = data.skill_matrix[s]?.[String(c.id)];
                      return (
                        <td key={c.id} className="py-1.5 px-2 text-center">
                          {st === 'matched' ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 inline" /> :
                           st === 'missing' ? <XCircle className="w-3.5 h-3.5 text-red-400/70 inline" /> :
                           <span className="text-slate-700">—</span>}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {data.candidates.some((c) => c.extraction_limitations.length > 0) && (
        <p className="text-[10px] text-slate-600">Scores are screening aids for recruiter review — extraction limitations apply per candidate.</p>
      )}
    </div>
  );
};

/* ---------- Main dashboard ---------- */
export default function RecruiterDashboard({ user }: { user: User }) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [apps, setApps] = useState<ApplicationSummary[]>([]);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [showJobForm, setShowJobForm] = useState(false);
  const [editingJob, setEditingJob] = useState<Job | null>(null);
  const [filterStatus, setFilterStatus] = useState('');
  const [minScore, setMinScore] = useState('');
  const [sort, setSort] = useState('score_desc');
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [screenMsg, setScreenMsg] = useState<string | null>(null);
  const [screenErr, setScreenErr] = useState<string | null>(null);
  const [screening, setScreening] = useState(false);
  const [compareIds, setCompareIds] = useState<number[]>([]);
  const [compareData, setCompareData] = useState<CompareResult | null>(null);
  const [insights, setInsights] = useState<JobInsights | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const loadJobs = useCallback(async () => {
    try { setJobs(await atsApi.listJobs()); } catch { /* ignore */ }
  }, []);

  const loadApps = useCallback(async (job: Job) => {
    try {
      setApps(await atsApi.listApplications(job.id, {
        status: filterStatus || undefined,
        min_score: minScore ? parseFloat(minScore) : undefined,
        sort,
      }));
    } catch { setApps([]); }
  }, [filterStatus, minScore, sort]);

  const loadAnalytics = useCallback(async () => {
    try { setAnalytics(await atsApi.analytics()); } catch { /* ignore */ }
  }, []);

  useEffect(() => { loadJobs(); loadAnalytics(); }, [loadJobs, loadAnalytics]);
  useEffect(() => { if (user.role === 'admin') atsApi.listUsers().then(setUsers).catch(() => {}); }, [user.role]);
  useEffect(() => { if (selectedJob) loadApps(selectedJob); }, [selectedJob, loadApps]);
  useEffect(() => {
    setCompareIds([]); setCompareData(null);
    if (selectedJob) {
      atsApi.insights(selectedJob.id).then(setInsights).catch(() => setInsights(null));
    } else {
      setInsights(null);
    }
  }, [selectedJob]);

  const toggleCompare = (id: number) => {
    setCompareIds((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : prev.length < 4 ? [...prev, id] : prev);
    setCompareData(null);
  };

  const runCompare = async () => {
    if (!selectedJob || compareIds.length < 2) return;
    try { setCompareData(await atsApi.compare(selectedJob.id, compareIds)); }
    catch { setCompareData(null); }
  };

  const saveJob = async (body: { title: string; description: string; location: string; status: string }) => {
    if (editingJob) await atsApi.updateJob(editingJob.id, body);
    else await atsApi.createJob(body);
    setShowJobForm(false); setEditingJob(null);
    await loadJobs(); await loadAnalytics();
  };

  const onFiles = async (files: FileList | null) => {
    if (!files || !selectedJob) return;
    setScreening(true); setScreenMsg(null); setScreenErr(null);
    try {
      const res = await atsApi.screen(selectedJob.id, Array.from(files));
      setScreenMsg(`Screened ${res.screened} resume(s)${res.errors.length ? `, ${res.errors.length} failed` : ''}.`);
      if (res.errors.length) setScreenErr(res.errors.map((e) => `${e.file}: ${e.error}`).join('\n'));
      await loadApps(selectedJob); await loadJobs(); await loadAnalytics();
    } catch (e) {
      const ax = e as { response?: { data?: { detail?: string } } };
      setScreenErr(ax.response?.data?.detail || 'Screening failed');
    } finally {
      setScreening(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const exportCsv = async () => {
    if (!selectedJob) return;
    const blob = await atsApi.exportCsv(selectedJob.id);
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `job_${selectedJob.id}_candidates.csv`; a.click();
    URL.revokeObjectURL(url);
  };

  const changeStatus = async (app: ApplicationSummary, status: string) => {
    await atsApi.updateApplication(app.id, { status });
    if (selectedJob) loadApps(selectedJob);
    loadAnalytics();
  };

  const statusCounts = useMemo(() => analytics?.by_status || {}, [analytics]);

  return (
    <div className="space-y-6">
      {/* Analytics strip */}
      {analytics && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 stagger">
          {[
            { icon: Briefcase, label: 'Jobs', value: analytics.total_jobs, color: '#06b6d4' },
            { icon: Users, label: 'Applications', value: analytics.total_applications, color: '#8b5cf6' },
            { icon: BarChart3, label: 'Avg Score', value: Math.round(analytics.avg_score), color: '#10b981' },
            { icon: CheckCircle2, label: 'Shortlisted', value: statusCounts.shortlisted || 0, color: '#f59e0b' },
          ].map((s) => (
            <div key={s.label} className="glass-panel p-4 flex items-center gap-4">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ backgroundColor: `${s.color}15`, border: `1px solid ${s.color}30` }}>
                <s.icon className="w-5 h-5" style={{ color: s.color }} />
              </div>
              <div>
                <p className="text-2xl font-black text-white font-mono">{s.value}</p>
                <p className="text-[9px] font-bold text-slate-500 uppercase tracking-widest">{s.label}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Jobs sidebar */}
        <div className="lg:col-span-4 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-white flex items-center gap-2"><Briefcase className="w-5 h-5 text-cyan-400" />Jobs</h2>
            <button onClick={() => { setEditingJob(null); setShowJobForm(!showJobForm); }} className="btn-glow px-4 py-2 text-[10px] font-bold uppercase tracking-wider flex items-center gap-1.5">
              <Plus className="w-3.5 h-3.5" /> New
            </button>
          </div>

          {showJobForm && <JobForm initial={editingJob || undefined} onSave={saveJob} onCancel={() => { setShowJobForm(false); setEditingJob(null); }} />}

          <div className="space-y-3">
            {jobs.length === 0 && !showJobForm && (
              <div className="glass-panel p-8 text-center text-slate-600 text-xs">No jobs yet. Create your first job posting.</div>
            )}
            {jobs.map((j) => (
              <button
                key={j.id}
                onClick={() => setSelectedJob(j)}
                className={`glass-panel p-4 w-full text-left transition-all ${selectedJob?.id === j.id ? 'border-cyan-500/30 bg-cyan-500/[0.04]' : 'hover:border-white/10'}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm font-bold text-white truncate">{j.title}</p>
                    <p className="text-[10px] text-slate-500 mt-0.5 flex items-center gap-1"><Building2 className="w-3 h-3" />{j.location || 'Remote'} · {j.status}</p>
                  </div>
                  <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full border ${j.status === 'open' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-slate-500/10 text-slate-400 border-slate-500/20'}`}>{j.status}</span>
                </div>
                <div className="flex items-center gap-4 mt-3 text-[10px] text-slate-500">
                  <span className="flex items-center gap-1"><Users className="w-3 h-3" />{j.application_count} applicants</span>
                  <span className="flex items-center gap-1"><BarChart3 className="w-3 h-3" />avg {Math.round(j.avg_score)}</span>
                  <span className="ml-auto text-cyan-500/60 font-bold">{j.required_skills.length} skills</span>
                </div>
              </button>
            ))}
          </div>

          {user.role === 'admin' && users.length > 0 && (
            <div className="glass-panel p-4 space-y-2">
              <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest flex items-center gap-1.5"><ShieldCheck className="w-3 h-3" />Users</p>
              {users.map((u) => (
                <div key={u.id} className="flex items-center justify-between text-xs">
                  <span className="text-slate-300 truncate">{u.name} <span className="text-slate-600">({u.email})</span></span>
                  <select
                    className="bg-white/5 border border-white/10 rounded-lg text-[10px] px-2 py-1 text-slate-300"
                    value={u.role}
                    onChange={async (e) => { await atsApi.setUserRole(u.id, e.target.value); atsApi.listUsers().then(setUsers); }}
                  >
                    <option value="candidate">candidate</option>
                    <option value="recruiter">recruiter</option>
                    <option value="admin">admin</option>
                  </select>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Applications panel */}
        <div className="lg:col-span-8 space-y-4">
          {!selectedJob ? (
            <div className="glass-panel p-16 flex flex-col items-center justify-center text-center min-h-[400px]">
              <Briefcase className="w-12 h-12 text-slate-700 mb-4" />
              <p className="text-slate-500 font-bold text-sm">Select a job to manage candidates</p>
              <p className="text-slate-700 text-xs mt-1">Upload resumes in bulk and let AI rank them against the job description.</p>
            </div>
          ) : (
            <>
              <div className="glass-panel p-5 space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h2 className="text-xl font-black text-white">{selectedJob.title}</h2>
                    <p className="text-[10px] text-slate-500 mt-1">
                      {selectedJob.required_skills.slice(0, 8).join(' · ')}{selectedJob.required_skills.length > 8 ? ` +${selectedJob.required_skills.length - 8}` : ''}
                      {selectedJob.min_years ? ` · ${selectedJob.min_years}+ yrs required` : ''}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button onClick={() => { setEditingJob(selectedJob); setShowJobForm(true); }} className="px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-slate-400 hover:text-white border border-white/10 rounded-lg">Edit</button>
                    <button onClick={exportCsv} className="px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-emerald-400 hover:text-emerald-300 border border-emerald-500/20 rounded-lg flex items-center gap-1.5"><Download className="w-3 h-3" />CSV</button>
                    <button onClick={() => fileRef.current?.click()} disabled={screening} className="btn-glow px-4 py-2 text-[10px] font-bold uppercase tracking-wider flex items-center gap-1.5">
                      {screening ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />} Upload Resumes
                    </button>
                    <input ref={fileRef} type="file" multiple accept=".pdf,.docx" className="hidden" onChange={(e) => onFiles(e.target.files)} />
                  </div>
                </div>

                {screenMsg && <p className="text-xs text-emerald-400 flex items-center gap-1.5"><CheckCircle2 className="w-3.5 h-3.5" />{screenMsg}</p>}
                {screenErr && <p className="text-xs text-red-400 whitespace-pre-line">{screenErr}</p>}

                <div className="flex flex-wrap gap-2">
                  <select className="bg-white/5 border border-white/10 rounded-lg text-xs px-3 py-2 text-slate-300" value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}>
                    <option value="">All statuses</option>
                    {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                  <select className="bg-white/5 border border-white/10 rounded-lg text-xs px-3 py-2 text-slate-300" value={sort} onChange={(e) => setSort(e.target.value)}>
                    <option value="score_desc">Score: high → low</option>
                    <option value="score_asc">Score: low → high</option>
                    <option value="newest">Newest first</option>
                  </select>
                  <input className="bg-white/5 border border-white/10 rounded-lg text-xs px-3 py-2 text-slate-300 w-32" placeholder="Min score" value={minScore} onChange={(e) => setMinScore(e.target.value)} />
                  {compareIds.length >= 2 && (
                    <button onClick={runCompare} className="px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-violet-300 hover:text-violet-200 border border-violet-500/30 rounded-lg flex items-center gap-1.5">
                      <Users className="w-3 h-3" /> Compare ({compareIds.length})
                    </button>
                  )}
                </div>

                {insights && insights.total_applications > 0 && (
                  <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 pt-1 border-t border-white/5">
                    <span className="text-[10px] text-slate-500"><span className="text-white font-bold font-mono">{insights.total_applications}</span> applicants</span>
                    {Object.entries(insights.by_status).map(([s, n]) => (
                      <span key={s} className="text-[10px] text-slate-500">{s}: <span className="text-slate-300 font-bold">{n}</span></span>
                    ))}
                    {insights.score.avg != null && <span className="text-[10px] text-slate-500">avg score <span className="text-cyan-400 font-bold font-mono">{Math.round(insights.score.avg)}</span></span>}
                    {insights.top_missing_skills.length > 0 && (
                      <span className="text-[10px] text-slate-500">top gap: <span className="text-amber-300/80">{insights.top_missing_skills[0][0]}</span></span>
                    )}
                  </div>
                )}
              </div>

              {compareData ? (
                <CompareView data={compareData} onClose={() => setCompareData(null)} />
              ) : expandedId ? (
                <ApplicationDetailPanel appId={expandedId} onClose={() => setExpandedId(null)} onUpdated={() => { if (selectedJob) loadApps(selectedJob); loadAnalytics(); }} />
              ) : apps.length === 0 ? (
                <div className="glass-panel p-12 text-center text-slate-600 text-xs">No applications yet. Upload candidate resumes above.</div>
              ) : (
                <div className="space-y-2">
                  {apps.map((a, i) => (
                    <div key={a.id} className="glass-panel p-4">
                      <div className="flex flex-wrap items-center gap-4">
                        <input
                          type="checkbox"
                          className="accent-violet-500 w-3.5 h-3.5 shrink-0"
                          checked={compareIds.includes(a.id)}
                          onChange={() => toggleCompare(a.id)}
                          title="Select for comparison"
                        />
                        <span className="text-slate-600 font-mono text-xs w-6">#{i + 1}</span>
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-bold text-white truncate">{a.candidate_name || 'Unknown'}</p>
                          <p className="text-[10px] text-slate-500 truncate">{a.candidate_email} · {a.resume_filename}</p>
                        </div>
                        <ScorePill score={a.score} />
                        <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full border ${statusColor[a.status] || statusColor.new}`}>{a.status}</span>
                        <select
                          className="bg-white/5 border border-white/10 rounded-lg text-[10px] px-2 py-1.5 text-slate-300"
                          value={a.status}
                          onChange={(e) => changeStatus(a, e.target.value)}
                        >
                          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                        </select>
                        <button onClick={() => setExpandedId(expandedId === a.id ? null : a.id)} className="p-2 text-slate-500 hover:text-cyan-400 transition-colors">
                          {expandedId === a.id ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                        </button>
                      </div>
                      <div className="flex flex-wrap items-center gap-2 mt-3">
                        {a.matched_skills.slice(0, 6).map((s) => <span key={s} className="skill-tag skill-matched text-[9px]"><CheckCircle2 className="w-3 h-3" />{s}</span>)}
                        {a.missing_skills.slice(0, 4).map((s) => <span key={s} className="skill-tag skill-missing text-[9px]"><XCircle className="w-3 h-3" />{s}</span>)}
                        {a.experience_years != null && <span className="text-[9px] text-slate-600 ml-auto"><Clock className="w-3 h-3 inline" /> {a.experience_years} yrs</span>}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
