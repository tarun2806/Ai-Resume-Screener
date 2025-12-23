import React, { useState } from 'react';
import {
    Upload, FileText, CheckCircle2, AlertCircle, Sparkles,
    TrendingUp, Lightbulb, Target, Award,
    Cpu, BrainCircuit, Zap, Layers, BarChart3, HelpCircle, ShieldCheck
} from 'lucide-react';
import axios from 'axios';
import { ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

const API_BASE = 'http://localhost:8000/api/v1';

const SkillBadge = ({ name, type }: { name: string, type: 'matched' | 'missing' | 'partial' }) => {
    const styles = {
        matched: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30 shadow-[0_0_10px_rgba(16,185,129,0.05)]',
        partial: 'bg-rose-500/10 text-rose-400 border-rose-500/30 shadow-[0_0_10px_rgba(244,63,94,0.05)]',
        missing: 'bg-slate-700/30 text-slate-400 border-white/5 opacity-60'
    };

    const labels = {
        matched: 'Matching',
        partial: 'Similar',
        missing: 'Missing'
    };

    const Icon = type === 'matched' ? CheckCircle2 : type === 'partial' ? Sparkles : AlertCircle;

    return (
        <div className={`px-3 py-1.5 rounded-xl border flex flex-col gap-0.5 transition-all hover:scale-105 hover:bg-white/[0.02] ${styles[type]}`}>
            <div className="flex items-center gap-1.5">
                <Icon className="w-3.5 h-3.5" />
                <span className="font-bold text-[11px] tracking-wide capitalize">{name}</span>
            </div>
            <span className="text-[8px] uppercase tracking-[0.1em] opacity-60 font-black pl-5">
                {labels[type]}
            </span>
        </div>
    );
};

const CandidateDashboard = () => {
    const [file, setFile] = useState<File | null>(null);
    const [loading, setLoading] = useState(false);
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

            const parseRes = await axios.post(`${API_BASE}/resumes/parse`, formData);
            const jobRes = await axios.post(`${API_BASE}/jobs/analyze`, { description: jdText });
            const matchRes = await axios.post(`${API_BASE}/matches/`, {
                resume_data: parseRes.data,
                job_data: jobRes.data
            });

            setResult(matchRes.data);
        } catch (err: any) {
            console.error("Match Error:", err);
            const msg = err.response?.data?.detail || "AI check failed. Please make sure the server is running.";
            setError(msg);
        } finally {
            setLoading(false);
        }
    };

    const getScoreColor = (score: number) => {
        if (score >= 80) return '#10b981'; // Emerald
        if (score >= 60) return '#f43f5e'; // Rose
        if (score >= 40) return '#8b5cf6'; // Violet
        return '#475569'; // Slate
    };

    return (
        <div className="max-w-6xl mx-auto space-y-8 pb-16 px-4 animate-in fade-in duration-700 font-sans selection:bg-rose-500/30">
            {/* Header Section */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 pt-4">
                <div>
                    <h1 className="text-3xl font-black tracking-tight text-white mb-1">
                        Smart <span className="text-rose-500">Resume Checker</span>
                    </h1>
                    <p className="text-slate-500 text-xs font-bold tracking-widest uppercase">AI-Based Job Match Tool</p>
                </div>
                {result && (
                    <div className="flex items-center gap-3 bg-white/5 p-1.5 pr-4 rounded-xl border border-white/10 backdrop-blur-md shadow-2xl shadow-rose-500/5">
                        <div className="w-9 h-9 rounded-lg bg-rose-500/10 flex items-center justify-center border border-rose-500/20 animate-pulse">
                            <Zap className="w-5 h-5 text-rose-400" />
                        </div>
                        <div>
                            <p className="text-[9px] font-black text-slate-500 uppercase tracking-widest leading-tight">AI Rating</p>
                            <p className="font-bold text-xs text-rose-400">{result.verdict}</p>
                        </div>
                    </div>
                )}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 text-slate-300">
                {/* LHS: INPUT SECTION */}
                <div className="lg:col-span-5 space-y-6">
                    <section className="glass-card p-6 rounded-[2rem] border border-white/5 shadow-2xl relative overflow-hidden group bg-slate-900/50 backdrop-blur-xl">
                        <div className="absolute -top-16 -right-16 w-48 h-48 bg-rose-600/5 rounded-full blur-[60px]" />

                        <div className="flex items-center gap-3 mb-6 relative">
                            <div className="p-2 bg-rose-500/10 rounded-xl border border-rose-500/20">
                                <FileText className="w-5 h-5 text-rose-400" />
                            </div>
                            <h2 className="text-xl font-bold tracking-tight text-white">Your Resume</h2>
                        </div>

                        <div className="relative group/upload">
                            <input type="file" className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10" onChange={handleFileUpload} />
                            <div className="border border-white/5 rounded-2xl p-8 flex flex-col items-center justify-center transition-all group-hover/upload:bg-rose-500/5 bg-black/20">
                                <div className="w-14 h-14 bg-white/5 rounded-2xl flex items-center justify-center mb-4 border border-white/5 group-hover/upload:border-rose-500/30 transition-all">
                                    <Upload className="w-7 h-7 text-slate-500 group-hover:text-rose-400 transition-colors" />
                                </div>
                                <h3 className="text-base font-bold text-slate-200 mb-1 text-center">
                                    {file ? file.name : "Upload Resume (PDF/DOCX)"}
                                </h3>
                                <p className="text-[9px] text-slate-600 font-black uppercase tracking-widest">AI Scanner Ready</p>
                            </div>
                        </div>
                    </section>

                    <section className="glass-card p-6 rounded-[2rem] border border-white/5 shadow-2xl bg-slate-900/50">
                        <div className="flex items-center gap-3 mb-6">
                            <div className="p-2 bg-violet-500/10 rounded-xl border border-violet-500/20">
                                <Target className="w-5 h-5 text-violet-400" />
                            </div>
                            <h2 className="text-xl font-bold tracking-tight text-white">Job Details</h2>
                        </div>

                        <div className="space-y-4">
                            <div className="relative">
                                <textarea
                                    className="w-full h-64 bg-black/40 border border-white/5 rounded-2xl p-6 focus:ring-2 focus:ring-rose-500/20 focus:outline-none text-sm leading-relaxed text-slate-300 placeholder:text-slate-700 transition-all resize-none shadow-inner"
                                    placeholder="Paste the Job Description here..."
                                    value={jdText}
                                    onChange={(e) => setJdText(e.target.value)}
                                />
                                <div className="absolute bottom-4 right-6">
                                    <div className={`px-3 py-1 rounded-full text-[9px] font-black uppercase tracking-widest border transition-all ${jdText.length >= 50 ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-slate-800 text-slate-500 border-white/5'
                                        }`}>
                                        {jdText.length < 50 ? `${50 - jdText.length} more chars` : 'Ready to Match'}
                                    </div>
                                </div>
                            </div>

                            <button
                                onClick={handleMatch}
                                disabled={loading || !file || jdText.length < 50}
                                className="w-full bg-rose-600 hover:bg-rose-500 disabled:opacity-20 text-white font-black py-4 rounded-2xl transition-all shadow-xl shadow-rose-900/20 flex items-center justify-center gap-2 group uppercase tracking-widest text-xs"
                            >
                                {loading ? (
                                    <><div className="w-5 h-5 border-2 border-white/20 border-t-white rounded-full animate-spin" /> Checking...</>
                                ) : (
                                    <><Sparkles className="w-5 h-5" /> Calculate Match Score</>
                                )}
                            </button>

                            {error && (
                                <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-2xl flex items-start gap-3 animate-in slide-in-from-top-2">
                                    <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
                                    <p className="text-[10px] font-bold text-rose-300 leading-relaxed">{error}</p>
                                </div>
                            )}
                        </div>
                    </section>
                </div>

                {/* RHS: ANALYTICS SECTION */}
                <div className="lg:col-span-7 space-y-6">
                    {!result ? (
                        <div className="h-full flex flex-col items-center justify-center text-center space-y-6 py-16 bg-slate-900/20 rounded-[2rem] border border-white/5 border-dashed">
                            {loading ? (
                                <div className="space-y-6 flex flex-col items-center">
                                    <div className="w-20 h-20 border-4 border-rose-500/10 border-t-rose-500 rounded-full animate-spin" />
                                    <div className="space-y-2">
                                        <p className="text-rose-400 font-black uppercase tracking-[0.3em] text-[10px] animate-pulse">Running AI Check</p>
                                        <p className="text-slate-600 text-[9px] font-bold">Comparing your skills with the job...</p>
                                    </div>
                                </div>
                            ) : (
                                <>
                                    <div className="w-24 h-24 bg-white/5 rounded-3xl flex items-center justify-center border border-white/5 rotate-3 hover:rotate-0 transition-transform">
                                        <Layers className="w-12 h-12 text-slate-800" />
                                    </div>
                                    <p className="text-slate-600 font-bold max-w-[200px] text-[10px] uppercase tracking-widest leading-loose">Upload your resume and the job details to see your score</p>
                                </>
                            )}
                        </div>
                    ) : (
                        <div className="animate-in slide-in-from-right-8 duration-700 space-y-6">
                            {/* SCORE DASHBOARD */}
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div className="glass-card p-6 rounded-[2rem] border border-white/5 flex flex-col items-center justify-center bg-slate-900/50 relative overflow-hidden">
                                    <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-rose-500/20 to-transparent" />
                                    <div className="relative w-40 h-40">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <PieChart>
                                                <Pie
                                                    data={[{ v: result.overall_score }, { v: 100 - result.overall_score }]}
                                                    innerRadius={55}
                                                    outerRadius={75}
                                                    cornerRadius={6}
                                                    dataKey="v"
                                                    stroke="none"
                                                    startAngle={90}
                                                    endAngle={-270}
                                                >
                                                    <Cell fill={getScoreColor(result.overall_score)} fillOpacity={1} />
                                                    <Cell fill="#1e293b" fillOpacity={0.5} />
                                                </Pie>
                                            </PieChart>
                                        </ResponsiveContainer>
                                        <div className="absolute inset-0 flex flex-col items-center justify-center">
                                            <span className="text-4xl font-black italic tracking-tighter" style={{ color: getScoreColor(result.overall_score) }}>
                                                {Math.round(result.overall_score)}%
                                            </span>
                                            <span className="text-[8px] uppercase font-black text-slate-500 tracking-widest mt-1">Match Score</span>
                                        </div>
                                    </div>
                                    <p className="mt-4 text-[10px] font-bold text-slate-400 italic text-center max-w-[240px] leading-relaxed">"{result.explanation}"</p>
                                </div>

                                <div className="glass-card p-6 rounded-[2rem] border border-white/5 flex flex-col justify-center gap-4 bg-slate-900/50">
                                    <div className="flex items-center gap-2 mb-1">
                                        <BarChart3 className="w-4 h-4 text-rose-400" />
                                        <h3 className="text-[9px] font-black uppercase tracking-[0.2em] text-slate-500">Score Breakdown</h3>
                                    </div>
                                    <div className="space-y-4">
                                        {[
                                            { label: 'Skills', val: result.breakdown.skill_match, icon: Award, color: 'text-emerald-400' },
                                            { label: 'Experience', val: result.breakdown.experience_relevance, icon: TrendingUp, color: 'text-rose-400' },
                                            { label: 'Meaning', val: result.breakdown.semantic_alignment, icon: BrainCircuit, color: 'text-violet-400' },
                                            { label: 'Quality', val: result.breakdown.resume_quality, icon: ShieldCheck, color: 'text-slate-400' }
                                        ].map((item) => (
                                            <div key={item.label}>
                                                <div className="flex justify-between items-center mb-1">
                                                    <span className="text-[8px] font-black text-slate-500 uppercase flex items-center gap-1.5">
                                                        <item.icon className={`w-2.5 h-2.5 ${item.color}`} /> {item.label}
                                                    </span>
                                                    <span className="text-[9px] font-black text-white">{Math.round(item.val)}%</span>
                                                </div>
                                                <div className="h-1 bg-white/5 rounded-full overflow-hidden">
                                                    <div className={`h-full opacity-80 transition-all duration-1000 ease-out`} style={{ width: `${item.val}%`, backgroundColor: getScoreColor(result.overall_score) }} />
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </div>

                            {/* SKILL MATRIX */}
                            <div className="glass-card p-6 rounded-[2rem] border border-white/5 bg-slate-900/50">
                                <h3 className="text-xl font-bold mb-6 flex items-center gap-3 text-white">
                                    <Award className="text-rose-400 w-5 h-5" />
                                    Skills Analysis
                                </h3>
                                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                                    {Object.entries(result.categorized_skills).map(([cat, skills]: [any, any]) => (
                                        <div key={cat} className="space-y-4">
                                            <p className="text-[9px] font-black text-slate-500 uppercase tracking-widest border-b border-white/5 pb-1">{cat} List</p>
                                            <div className="flex flex-col gap-2">
                                                {skills.length > 0 ? skills.map((s: any) => {
                                                    const sNameLower = s.name.toLowerCase();
                                                    let type: 'matched' | 'missing' | 'partial' = 'missing';
                                                    if (result.matched_skills.includes(sNameLower)) type = 'matched';
                                                    else if (result.partial_matches.includes(sNameLower)) type = 'partial';
                                                    return <SkillBadge key={s.name} name={s.name} type={type} />;
                                                }) : <p className="text-[9px] text-slate-700 italic">No skills found.</p>}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            {/* OPTIMIZATION PLAN */}
                            <div className="glass-card p-6 rounded-[2rem] border border-rose-500/10 bg-rose-500/[0.01]">
                                <h3 className="text-xl font-bold mb-4 flex items-center gap-3 text-rose-300">
                                    <Lightbulb className="w-6 h-6 text-rose-400" />
                                    How to Improve Your Score
                                </h3>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-semibold">
                                    {result.suggestions.map((s: any, i: number) => (
                                        <div key={i} className="flex gap-4 p-4 bg-slate-900/40 border border-white/5 rounded-2xl hover:border-rose-500/20 transition-all">
                                            <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-rose-500/10 flex items-center justify-center text-[10px] font-black text-rose-400 border border-rose-500/20">
                                                {i + 1}
                                            </div>
                                            <div className="space-y-1">
                                                <p className="text-slate-300 leading-tight">{s.tip}</p>
                                                <p className="text-[8px] font-black text-emerald-400 uppercase tracking-[0.2em]">{s.impact} Boost</p>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            {/* TECHNICAL SPEC SHEET & CREDITS */}
                            <div className="p-5 rounded-[2rem] bg-black/40 border border-white/5 flex flex-col md:flex-row justify-between items-center gap-4 text-[8px] font-black text-slate-600 uppercase tracking-widest">
                                <div className="flex items-center gap-2">
                                    <Cpu className="w-3 h-3 text-rose-500/40" /> AI System v1.0.4
                                </div>
                                <div className="flex items-center gap-4">
                                    <span>AI Model: MiniLM-L6</span>
                                    <span className="text-slate-500/30">|</span>
                                    <span className="text-slate-400 font-bold">Made with ❤️ by Tarun S</span>
                                    <span className="text-slate-500/30">|</span>
                                    <span>© 2025 All Rights Reserved</span>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* INTERVIEW BRIEF */}
            <div className="max-w-5xl mx-auto pt-8 border-t border-white/5 grid grid-cols-1 md:grid-cols-4 gap-4">
                {[
                    { q: "Meaning Match", a: "The AI looks for the meaning of your words, not just exact keywords." },
                    { q: "Related Skills", a: "You get points for skills related to the job, even if they aren't an exact match." },
                    { q: "Layout Free", a: "No bias on your resume design. The AI focuses only on your skills and experience." },
                    { q: "Smart Speed", a: "High-speed AI gives you accurate results in seconds." }
                ].map((item, i) => (
                    <div key={i} className="glass-card p-4 rounded-xl border border-white/5 bg-slate-900/50">
                        <h4 className="text-[9px] font-black text-rose-500/60 mb-1 uppercase tracking-widest flex gap-2 items-center">
                            <HelpCircle className="w-3 h-3" /> {item.q}
                        </h4>
                        <p className="text-[9px] text-slate-500 font-bold leading-relaxed">{item.a}</p>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default CandidateDashboard;
