import React, { useState, useMemo } from 'react';
import {
    Upload, FileText, CheckCircle2, AlertCircle, Sparkles, XCircle,
    TrendingUp, Lightbulb, Target, Award, ArrowRight,
    Cpu, BrainCircuit, Zap, Layers, BarChart3, ShieldCheck, Clock, Flame
} from 'lucide-react';
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

/* ─── Score Ring (SVG) ─── */
const ScoreRing = ({ score, size = 200 }: { score: number; size?: number }) => {
    const radius = (size / 2) - 12;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - (score / 100) * circumference;
    const color = score >= 80 ? '#10b981' : score >= 60 ? '#06b6d4' : score >= 40 ? '#8b5cf6' : '#ef4444';

    return (
        <div className="score-ring-container flex items-center justify-center" style={{ width: size, height: size }}>
            <svg width={size} height={size} className="transform -rotate-90">
                <circle cx={size / 2} cy={size / 2} r={radius} className="score-ring-bg" />
                <circle
                    cx={size / 2} cy={size / 2} r={radius}
                    className="score-ring-fill"
                    style={{
                        stroke: color,
                        strokeDasharray: circumference,
                        strokeDashoffset: offset,
                        color: color,
                    }}
                />
            </svg>
            <div className="absolute flex flex-col items-center">
                <span className="text-5xl font-black font-mono tracking-tighter" style={{ color }}>
                    {Math.round(score)}
                </span>
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em] mt-1">Match Score</span>
            </div>
        </div>
    );
};

/* ─── Skill Tag ─── */
const SkillTag = ({ name, type }: { name: string; type: 'matched' | 'missing' | 'partial' }) => {
    const cls = type === 'matched' ? 'skill-matched' : type === 'partial' ? 'skill-partial' : 'skill-missing';
    const Icon = type === 'matched' ? CheckCircle2 : type === 'partial' ? Sparkles : XCircle;
    return (
        <span className={`skill-tag ${cls}`}>
            <Icon className="w-3.5 h-3.5" />
            {name}
        </span>
    );
};

/* ─── Stat Bar ─── */
const StatBar = ({ label, value, color, icon: Icon }: { label: string; value: number; color: string; icon: React.ElementType }) => (
    <div className="space-y-2">
        <div className="flex justify-between items-center">
            <span className="text-xs font-semibold text-slate-400 flex items-center gap-2">
                <Icon className="w-3.5 h-3.5" style={{ color }} />
                {label}
            </span>
            <span className="text-sm font-bold font-mono" style={{ color }}>{Math.round(value)}%</span>
        </div>
        <div className="progress-track">
            <div className="progress-fill" style={{ width: `${value}%`, backgroundColor: color, color }} />
        </div>
    </div>
);

/* ─── Main Dashboard ─── */
const CandidateDashboard = () => {
    const [file, setFile] = useState<File | null>(null);
    const [loading, setLoading] = useState(false);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const [result, setResult] = useState<any>(null);
    const [jdText, setJdText] = useState('');
    const [error, setError] = useState<string | null>(null);

    const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0]);
            setError(null);
        }
    };

    const handleMatch = async () => {
        if (!file || jdText.length < 50) return;
        setLoading(true);
        setError(null);
        setResult(null);

        try {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('job_description', jdText);

            const response = await axios.post(`${API_BASE}/matches/analyze`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });

            setResult(response.data);
        } catch (err: unknown) {
            console.error("Match Error:", err);
            const axErr = err as { response?: { data?: { detail?: string } } };
            const msg = axErr.response?.data?.detail || "AI check failed. Please make sure the backend server is running.";
            setError(msg);
        } finally {
            setLoading(false);
        }
    };

    const verdictConfig = useMemo(() => {
        if (!result) return null;
        const s = result.overall_score;
        if (s >= 80) return { text: 'Excellent Match', color: '#10b981', bg: 'from-emerald-500/10 to-emerald-500/5', icon: Flame };
        if (s >= 60) return { text: 'Strong Potential', color: '#06b6d4', bg: 'from-cyan-500/10 to-cyan-500/5', icon: TrendingUp };
        if (s >= 40) return { text: 'Needs Work', color: '#8b5cf6', bg: 'from-violet-500/10 to-violet-500/5', icon: Target };
        return { text: 'Major Gaps', color: '#ef4444', bg: 'from-red-500/10 to-red-500/5', icon: AlertCircle };
    }, [result]);

    return (
        <div className="space-y-8">
            {/* Hero Header */}
            <div className="text-center space-y-3 animate-slide-up">
                <h1 className="text-4xl sm:text-5xl font-black tracking-tight">
                    <span className="bg-clip-text text-transparent bg-gradient-to-r from-white via-cyan-100 to-slate-300">
                        Resume
                    </span>
                    {' '}
                    <span className="bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-violet-400">
                        Intelligence
                    </span>
                </h1>
                <p className="text-sm font-medium text-slate-500 max-w-lg mx-auto">
                    Upload your resume and paste a job description. Our AI engine will analyze semantic alignment, skill overlap, and provide actionable improvement insights.
                </p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* ─── LEFT: INPUT PANEL ─── */}
                <div className="lg:col-span-5 space-y-5 stagger">
                    {/* Resume Upload */}
                    <div className="glass-panel p-6">
                        <div className="flex items-center gap-3 mb-5">
                            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500/20 to-cyan-500/5 flex items-center justify-center border border-cyan-500/20">
                                <FileText className="w-5 h-5 text-cyan-400" />
                            </div>
                            <div>
                                <h2 className="text-lg font-bold text-white">Your Resume</h2>
                                <p className="text-[10px] text-slate-500 font-medium">PDF or DOCX supported</p>
                            </div>
                        </div>

                        <div className="relative">
                            <input
                                type="file"
                                accept=".pdf,.docx"
                                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
                                onChange={handleFileUpload}
                            />
                            <div className={`upload-zone flex flex-col items-center justify-center text-center ${file ? 'has-file' : ''}`}>
                                <div className={`w-14 h-14 rounded-2xl flex items-center justify-center mb-4 transition-all ${file ? 'bg-emerald-500/10 border border-emerald-500/20' : 'bg-white/5 border border-white/5'}`}>
                                    {file ? (
                                        <CheckCircle2 className="w-7 h-7 text-emerald-400" />
                                    ) : (
                                        <Upload className="w-7 h-7 text-slate-500" />
                                    )}
                                </div>
                                <h3 className="text-sm font-bold text-white mb-1">
                                    {file ? file.name : "Drop your resume here"}
                                </h3>
                                <p className="text-[10px] text-slate-600 font-medium">
                                    {file ? 'Click to change file' : 'or click to browse'}
                                </p>
                            </div>
                        </div>
                    </div>

                    {/* Job Description */}
                    <div className="glass-panel p-6">
                        <div className="flex items-center gap-3 mb-5">
                            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500/20 to-violet-500/5 flex items-center justify-center border border-violet-500/20">
                                <Target className="w-5 h-5 text-violet-400" />
                            </div>
                            <div>
                                <h2 className="text-lg font-bold text-white">Job Description</h2>
                                <p className="text-[10px] text-slate-500 font-medium">Paste the full JD below</p>
                            </div>
                        </div>

                        <div className="relative">
                            <textarea
                                className="jd-textarea h-56"
                                placeholder="Paste the full job description here to begin AI analysis..."
                                value={jdText}
                                onChange={(e) => setJdText(e.target.value)}
                            />
                            <div className="absolute bottom-3 right-4">
                                <span className={`text-[10px] font-bold px-3 py-1 rounded-full transition-all ${jdText.length >= 50
                                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                    : 'bg-slate-800/50 text-slate-600 border border-white/5'
                                    }`}>
                                    {jdText.length < 50 ? `${50 - jdText.length} more chars needed` : '✓ Ready'}
                                </span>
                            </div>
                        </div>

                        {/* Action Button */}
                        <button
                            onClick={handleMatch}
                            disabled={loading || !file || jdText.length < 50}
                            className="btn-glow w-full py-4 mt-4 text-sm font-bold uppercase tracking-wider flex items-center justify-center gap-2"
                        >
                            <span className="relative z-10 flex items-center gap-2">
                                {loading ? (
                                    <>
                                        <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                        Analyzing...
                                    </>
                                ) : (
                                    <>
                                        <Sparkles className="w-5 h-5" />
                                        Analyze with AI
                                        <ArrowRight className="w-4 h-4" />
                                    </>
                                )}
                            </span>
                        </button>

                        {error && (
                            <div className="mt-4 p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-start gap-3 animate-slide-up">
                                <AlertCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
                                <p className="text-xs font-medium text-red-300 leading-relaxed">{error}</p>
                            </div>
                        )}
                    </div>

                    {/* Feature Cards */}
                    <div className="grid grid-cols-2 gap-3">
                        {[
                            { icon: BrainCircuit, label: 'Semantic AI', desc: 'Context-aware matching' },
                            { icon: Zap, label: 'Lightning Fast', desc: 'Sub-second results' },
                            { icon: ShieldCheck, label: 'Bias Free', desc: 'Layout-independent' },
                            { icon: Clock, label: 'Real-time', desc: 'Instant feedback' },
                        ].map((f) => (
                            <div key={f.label} className="glass-panel p-4 flex items-start gap-3">
                                <f.icon className="w-4 h-4 text-cyan-500/60 mt-0.5 shrink-0" />
                                <div>
                                    <p className="text-[11px] font-bold text-slate-300">{f.label}</p>
                                    <p className="text-[9px] text-slate-600 font-medium">{f.desc}</p>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* ─── RIGHT: RESULTS PANEL ─── */}
                <div className="lg:col-span-7 space-y-5">
                    {!result ? (
                        <div className="h-full min-h-[500px] flex flex-col items-center justify-center text-center glass-panel p-10">
                            {loading ? (
                                <div className="space-y-6 flex flex-col items-center animate-slide-up">
                                    <div className="relative">
                                        <div className="w-24 h-24 border-4 border-cyan-500/10 border-t-cyan-500 rounded-full animate-spin" />
                                        <div className="absolute inset-0 flex items-center justify-center">
                                            <BrainCircuit className="w-8 h-8 text-cyan-400/50" />
                                        </div>
                                    </div>
                                    <div className="space-y-2">
                                        <p className="text-cyan-400 font-bold uppercase tracking-[0.3em] text-xs animate-pulse">
                                            AI Processing
                                        </p>
                                        <p className="text-slate-600 text-xs font-medium">
                                            Analyzing skills, experience, and semantic alignment...
                                        </p>
                                    </div>
                                </div>
                            ) : (
                                <div className="space-y-5 animate-slide-up">
                                    <div className="w-20 h-20 bg-white/[0.02] rounded-3xl flex items-center justify-center border border-white/5 mx-auto animate-float">
                                        <Layers className="w-10 h-10 text-slate-700" />
                                    </div>
                                    <div className="space-y-2">
                                        <p className="text-slate-500 font-bold text-sm">Your AI Analysis Will Appear Here</p>
                                        <p className="text-slate-700 text-xs font-medium max-w-xs mx-auto">
                                            Upload a resume and paste a job description to get started with the intelligent matching engine.
                                        </p>
                                    </div>
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="space-y-5 stagger">
                            {/* Verdict Banner */}
                            {verdictConfig && (
                                <div className={`glass-panel p-5 bg-gradient-to-r ${verdictConfig.bg} flex items-center justify-between`}>
                                    <div className="flex items-center gap-4">
                                        <div className="w-12 h-12 rounded-2xl flex items-center justify-center" style={{ backgroundColor: `${verdictConfig.color}15`, border: `1px solid ${verdictConfig.color}30` }}>
                                            <verdictConfig.icon className="w-6 h-6" style={{ color: verdictConfig.color }} />
                                        </div>
                                        <div>
                                            <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">AI Verdict</p>
                                            <p className="text-xl font-black" style={{ color: verdictConfig.color }}>{verdictConfig.text}</p>
                                        </div>
                                    </div>
                                    <div className="text-right hidden sm:block">
                                        <p className="text-[10px] text-slate-600 font-medium">Powered by SBERT + Custom Ontology</p>
                                    </div>
                                </div>
                            )}

                            {/* Score + Breakdown */}
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                                {/* Score Ring */}
                                <div className="glass-panel p-8 flex flex-col items-center justify-center">
                                    <ScoreRing score={result.overall_score} />
                                    <p className="mt-4 text-xs font-medium text-slate-500 italic text-center max-w-xs leading-relaxed">
                                        "{result.explanation}"
                                    </p>
                                </div>

                                {/* Breakdown Bars */}
                                <div className="glass-panel p-6 flex flex-col justify-center">
                                    <div className="flex items-center gap-2 mb-6">
                                        <BarChart3 className="w-4 h-4 text-cyan-400" />
                                        <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400">Detailed Breakdown</h3>
                                    </div>
                                    <div className="space-y-5">
                                        <StatBar label="Skill Match" value={result.breakdown.skill_match} color="#10b981" icon={Award} />
                                        <StatBar label="Experience" value={result.breakdown.experience_relevance} color="#06b6d4" icon={TrendingUp} />
                                        <StatBar label="Semantic Fit" value={result.breakdown.semantic_alignment} color="#8b5cf6" icon={BrainCircuit} />
                                        <StatBar label="Resume Quality" value={result.breakdown.resume_quality} color="#64748b" icon={ShieldCheck} />
                                    </div>
                                </div>
                            </div>

                            {/* Skill Analysis */}
                            <div className="glass-panel p-6">
                                <div className="flex items-center gap-2 mb-5">
                                    <Award className="w-5 h-5 text-cyan-400" />
                                    <h3 className="text-base font-bold text-white">Skills Analysis</h3>
                                </div>
                                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                                    {Object.entries(result.categorized_skills || {}).map(([cat, skills]) => (
                                        <div key={cat} className="space-y-3">
                                            <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest border-b border-white/5 pb-2">
                                                {cat}
                                            </p>
                                            <div className="flex flex-wrap gap-2">
                                                {(skills as Array<{ name: string }>).length > 0 ? (skills as Array<{ name: string }>).map((s) => {
                                                    const sLower = s.name.toLowerCase();
                                                    let type: 'matched' | 'missing' | 'partial' = 'missing';
                                                    if (result.matched_skills?.some((m: string) => m.toLowerCase() === sLower)) type = 'matched';
                                                    else if (result.partial_matches?.some((p: string) => p.toLowerCase() === sLower)) type = 'partial';
                                                    return <SkillTag key={s.name} name={s.name} type={type} />;
                                                }) : <p className="text-[10px] text-slate-700 italic">No skills detected</p>}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            {/* Improvement Suggestions */}
                            <div className="glass-panel p-6">
                                <div className="flex items-center gap-2 mb-5">
                                    <Lightbulb className="w-5 h-5 text-amber-400" />
                                    <h3 className="text-base font-bold text-white">How to Improve</h3>
                                </div>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    {result.suggestions?.map((s: { tip: string; impact: string }, i: number) => (
                                        <div key={i} className="suggestion-card flex gap-4">
                                            <div className="flex-shrink-0 w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500/10 to-violet-500/10 flex items-center justify-center text-sm font-black text-cyan-400 border border-cyan-500/20">
                                                {i + 1}
                                            </div>
                                            <div className="space-y-1 min-w-0">
                                                <p className="text-sm font-semibold text-slate-300 leading-snug">{s.tip}</p>
                                                <p className="text-[10px] font-bold text-emerald-400 uppercase tracking-widest">{s.impact} boost</p>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            {/* Tech Footer */}
                            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 p-4 rounded-2xl bg-black/30 border border-white/5 text-[9px] font-medium text-slate-600">
                                <div className="flex items-center gap-2">
                                    <Cpu className="w-3 h-3 text-cyan-500/30" />
                                    <span>Engine v2.0 • SBERT + Custom Ontology</span>
                                </div>
                                <span>Made with ❤️ by Tarun S • © 2025</span>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default CandidateDashboard;
