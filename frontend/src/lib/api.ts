import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export interface User {
  id: number;
  email: string;
  name: string;
  role: 'candidate' | 'recruiter' | 'admin';
  created_at?: string;
}

export interface AuthResponse {
  token: string;
  user: User;
}

const TOKEN_KEY = 'aiscreenx_token';

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t: string) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

export const api = axios.create({ baseURL: API_BASE });

// Active organization context — sent as X-Org-Id; backend still verifies membership.
let activeOrgId: number | null = null;
export const orgContext = {
  get: () => activeOrgId,
  set: (id: number | null) => { activeOrgId = id; },
};

api.interceptors.request.use((config) => {
  const token = tokenStore.get();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  if (activeOrgId != null) config.headers['X-Org-Id'] = String(activeOrgId);
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) tokenStore.clear();
    return Promise.reject(err);
  }
);

// ---------- auth ----------
export const authApi = {
  register: (body: { email: string; password: string; name: string; role: 'candidate' | 'recruiter' }) =>
    api.post<AuthResponse>('/auth/register', body).then((r) => r.data),
  login: (body: { email: string; password: string }) =>
    api.post<AuthResponse>('/auth/login', body).then((r) => r.data),
  me: () => api.get<{ user: User }>('/auth/me').then((r) => r.data.user),
};

// ---------- organizations ----------
export interface Org {
  id: number;
  name: string;
  my_role: string;
  created_at?: string | null;
}

export interface OrgMember {
  user_id: number;
  name: string | null;
  email: string | null;
  role: string;
  joined_at: string | null;
}

export interface OrgInvite {
  id: number;
  email: string;
  role: string;
  expires_at: string | null;
  expired?: boolean;
}

export const orgsApi = {
  list: () => api.get<{ organizations: Org[] }>('/orgs').then((r) => r.data.organizations),
  create: (name: string) => api.post<Org>('/orgs', { name }).then((r) => r.data),
  get: (id: number) =>
    api.get<Org & { members: OrgMember[] }>(`/orgs/${id}`).then((r) => r.data),
  createInvite: (orgId: number, email: string, role: string) =>
    api.post<{ id: number; token: string; email: string; role: string }>(`/orgs/${orgId}/invites`, { email, role }).then((r) => r.data),
  listInvites: (orgId: number) =>
    api.get<{ invites: OrgInvite[] }>(`/orgs/${orgId}/invites`).then((r) => r.data.invites),
  revokeInvite: (orgId: number, inviteId: number) =>
    api.delete(`/orgs/${orgId}/invites/${inviteId}`).then((r) => r.data),
  acceptInvite: (token: string) =>
    api.post<{ organization: Org; role: string }>('/orgs/invites/accept', { token }).then((r) => r.data),
  setMemberRole: (orgId: number, userId: number, role: string) =>
    api.patch<OrgMember>(`/orgs/${orgId}/members/${userId}`, { role }).then((r) => r.data),
  removeMember: (orgId: number, userId: number) =>
    api.delete(`/orgs/${orgId}/members/${userId}`).then((r) => r.data),
  analytics: (orgId: number) =>
    api.get<{ organization_id: number; total_jobs: number; total_applications: number; avg_score: number; by_status: Record<string, number> }>(`/orgs/${orgId}/analytics`).then((r) => r.data),
};

// ---------- ATS types ----------
export interface Job {
  id: number;
  title: string;
  description: string;
  location: string;
  status: 'open' | 'closed' | 'draft';
  required_skills: string[];
  min_years: number | null;
  created_at: string | null;
  application_count: number;
  avg_score: number;
}

export interface ApplicationSummary {
  id: number;
  job_id: number;
  job_title: string;
  candidate_name: string;
  candidate_email: string;
  resume_filename: string;
  score: number;
  status: string;
  recruiter_notes: string;
  skills: string[];
  experience_years: number | null;
  matched_skills: string[];
  missing_skills: string[];
  confidence: number | null;
  created_at: string | null;
}

export interface ApplicationDetail extends ApplicationSummary {
  match_result: Record<string, unknown>;
  parsed_profile_full: Record<string, unknown>;
  updated_at: string | null;
}

export interface ScoreComponent {
  component: string;
  key: string;
  score: number;
  weight: number;
}

export interface CompareCandidate {
  id: number;
  candidate_name: string;
  candidate_email: string;
  score: number;
  status: string;
  experience_years: number | null;
  confidence: number | null;
  matched_skills: string[];
  missing_skills: string[];
  preferred_skills_matched: string[];
  score_breakdown: ScoreComponent[];
  verdict?: string;
  extraction_limitations: string[];
}

export interface CompareResult {
  job_id: number;
  candidates: CompareCandidate[];
  skill_matrix: Record<string, Record<string, 'matched' | 'missing'>>;
}

export interface JobInsights {
  job_id: number;
  total_applications: number;
  by_status: Record<string, number>;
  score: { avg: number | null; min: number | null; max: number | null };
  avg_confidence: number | null;
  top_missing_skills: [string, number][];
  top_matched_skills: [string, number][];
}

export interface Analytics {
  total_jobs: number;
  total_applications: number;
  avg_score: number;
  by_status: Record<string, number>;
  per_job: { job_id: number; title: string; status: string; applications: number; avg_score: number; shortlisted: number }[];
}

export const atsApi = {
  createJob: (body: { title: string; description: string; location?: string; status?: string }) =>
    api.post<Job>('/ats/jobs', body).then((r) => r.data),
  listJobs: () => api.get<{ jobs: Job[] }>('/ats/jobs').then((r) => r.data.jobs),
  getJob: (id: number) => api.get<Job>(`/ats/jobs/${id}`).then((r) => r.data),
  updateJob: (id: number, body: { title: string; description: string; location?: string; status?: string }) =>
    api.patch<Job>(`/ats/jobs/${id}`, body).then((r) => r.data),
  screen: (jobId: number, files: File[]) => {
    const fd = new FormData();
    files.forEach((f) => fd.append('files', f));
    return api.post<{ screened: number; errors: { file: string; error: string }[]; ranked: ApplicationSummary[] }>(
      `/ats/jobs/${jobId}/screen`, fd
    ).then((r) => r.data);
  },
  listApplications: (jobId: number, params?: { status?: string; min_score?: number; sort?: string }) =>
    api.get<{ applications: ApplicationSummary[] }>(`/ats/jobs/${jobId}/applications`, { params }).then((r) => r.data.applications),
  getApplication: (id: number) => api.get<ApplicationDetail>(`/ats/applications/${id}`).then((r) => r.data),
  updateApplication: (id: number, body: { status?: string; notes?: string }) =>
    api.patch<ApplicationSummary>(`/ats/applications/${id}`, body).then((r) => r.data),
  apply: (jobId: number, file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return api.post<ApplicationSummary>(`/ats/jobs/${jobId}/apply`, fd).then((r) => r.data);
  },
  myApplications: () => api.get<{ applications: ApplicationSummary[] }>('/ats/me/applications').then((r) => r.data.applications),
  exportCsv: (jobId: number) =>
    api.get(`/ats/jobs/${jobId}/export.csv`, { responseType: 'blob' }).then((r) => r.data as Blob),
  analytics: () => api.get<Analytics>('/ats/analytics').then((r) => r.data),
  compare: (jobId: number, ids: number[]) =>
    api.get<CompareResult>(`/ats/jobs/${jobId}/compare`, { params: { ids: ids.join(',') } }).then((r) => r.data),
  insights: (jobId: number) => api.get<JobInsights>(`/ats/jobs/${jobId}/insights`).then((r) => r.data),
  listUsers: () => api.get<{ users: User[] }>('/ats/admin/users').then((r) => r.data.users),
  setUserRole: (id: number, role: string) =>
    api.patch<{ id: number; role: string }>(`/ats/admin/users/${id}/role`, { role }).then((r) => r.data),
};