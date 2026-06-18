/**
 * Central API client for the N-CIIA dashboard.
 *
 * Components consume typed domain functions from this file instead of calling
 * fetch directly. The default base URL is same-origin so production deployments
 * can route through the serving origin; Vite dev uses proxy rules.
 */

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: unknown,
    message?: string,
  ) {
    super(message ?? `API error ${status}`);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  const contentType = response.headers.get('content-type') ?? '';
  const body = contentType.includes('application/json')
    ? await response.json().catch(() => null)
    : await response.text().catch(() => null);

  if (!response.ok) {
    throw new ApiError(response.status, body);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return body as T;
}

export interface HealthResponse {
  status: string;
  version: string;
  environment: string;
  uptime_seconds: number;
  request_id?: string;
}

export interface Signal {
  id: string;
  type: string;
  source_name: string;
  source_url?: string | null;
  raw_content: string;
  extracted_text?: string | null;
  metadata: Record<string, unknown>;
  discovered_at: string;
  content_hash?: string | null;
  is_processed: boolean | number;
  processing_notes?: string[];
}

export interface ThreatScore {
  overall_score?: number;
  score?: number;
  level?: 'critical' | 'high' | 'medium' | 'low' | 'unknown';
  risk_level?: 'critical' | 'high' | 'medium' | 'low' | 'unknown';
}

export interface Persona {
  id: string;
  case_id?: string | null;
  primary_identifier: string;
  identifier_type: string;
  entities?: unknown[];
  aliases?: unknown[];
  signal_ids?: string[];
  platforms_detected: string[];
  first_activity?: string | null;
  last_activity?: string | null;
  activity_count: number;
  threat_score?: ThreatScore | null;
  overall_confidence?: { score?: number; level?: string } | null;
  is_active_watch: boolean | number;
  analyst_notes?: string[];
  created_at: string;
  updated_at: string;
}

export interface Case {
  id: string;
  name: string;
  description?: string;
  persona_ids: string[];
  evidence_ids: string[];
  status: 'open' | 'active' | 'closed' | 'archived' | string;
  priority: 'critical' | 'high' | 'medium' | 'low' | string;
  analyst_id?: string | null;
  team_ids: string[];
  created_at: string;
  updated_at: string;
  closed_at?: string | null;
  action_log: unknown[];
}

export interface Threat {
  id: string;
  // IOC value (URL, hash, IP, domain, etc.)
  value: string;
  indicator: string;
  type: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  source: string;
  description: string;
  first_seen: string;
  last_seen: string;
  is_active: boolean;
  is_blocked: boolean;
  tags: string[];
  context?: string;
}

export interface ThreatStats {
  total: number;
  by_severity: Record<string, number>;
  by_source: Record<string, number>;
  blocked: number;
}

export interface LiveThreatsResponse {
  threats: Threat[];
  stats: ThreatStats;
  fetched_at: string;
}

export interface Alert {
  id: string;
  signal_id: string;
  level: 'critical' | 'high' | 'medium' | 'low';
  title: string;
  message: string;
  source_name: string;
  created_at: string;
  is_acknowledged: boolean;
}

export interface DashboardStats {
  active_personas: number;
  signals_today: number;
  critical_threats: number;
  escalations_24h: number;
}

export interface CreatePersonaRequest {
  seed_type: string;
  seed_value: string;
  case_id?: string;
  start_investigation?: boolean;
}

export interface CreateCaseRequest {
  name: string;
  description?: string;
  priority?: string;
  analyst_id?: string;
}

export interface CyberNewsItem {
  source: string;
  title: string;
  link: string;
  published: string;
}

export interface OsintSearchResponse {
  status: string;
  query: string;
  signals_found: number;
  signals: Array<{
    id: string;
    type: string;
    source: string;
    content_preview: string;
  }>;
}

export interface ResponseActionRequest {
  case_id: string;
  action_type: string;
  target: string;
  details?: Record<string, unknown>;
}

export interface ResponseAction {
  id: string;
  status: string;
  metadata: Record<string, unknown>;
}

interface SignalListResponse {
  signals: Signal[];
  total: number;
}

interface PersonaListResponse {
  personas: Persona[];
  total: number;
}

interface CaseListResponse {
  cases: Case[];
  total: number;
}

const asSignalList = (payload: SignalListResponse | Signal[]) =>
  Array.isArray(payload) ? payload : payload.signals;

const asPersonaList = (payload: PersonaListResponse | Persona[]) =>
  Array.isArray(payload) ? payload : payload.personas;

const asCaseList = (payload: CaseListResponse | Case[]) =>
  Array.isArray(payload) ? payload : payload.cases;

export const fetchHealth = () => request<HealthResponse>('/health');

export interface SignalFilters {
  type?: string;
  limit?: number;
  offset?: number;
}

export const fetchSignals = (filters: SignalFilters = {}) => {
  const query = new URLSearchParams();
  if (filters.type) query.set('type', filters.type);
  if (filters.limit != null) query.set('limit', String(filters.limit));
  if (filters.offset != null) query.set('offset', String(filters.offset));
  const suffix = query.toString();
  return request<SignalListResponse | Signal[]>(`/api/signals/${suffix ? `?${suffix}` : ''}`).then(asSignalList);
};

export const fetchSignal = (id: string) => request<Signal>(`/api/signals/${id}`);

export interface PersonaFilters {
  q?: string;
  case_id?: string;
  is_active_watch?: boolean;
  limit?: number;
}

export const fetchPersonas = (filters: PersonaFilters = {}) => {
  const query = new URLSearchParams();
  if (filters.q) query.set('identifier', filters.q);
  if (filters.case_id) query.set('case_id', filters.case_id);
  if (filters.is_active_watch != null) query.set('is_active_watch', String(filters.is_active_watch));
  if (filters.limit != null) query.set('limit', String(filters.limit));
  const suffix = query.toString();
  return request<PersonaListResponse | Persona[]>(`/api/personas/${suffix ? `?${suffix}` : ''}`).then(asPersonaList);
};

export const fetchPersona = (id: string) => request<Persona>(`/api/personas/${id}`);

export const createPersona = (data: CreatePersonaRequest) =>
  request<{ status: string; persona_id: string; message: string }>('/api/personas/', {
    method: 'POST',
    body: JSON.stringify(data),
  });

export const fetchCases = (params: { status?: string; limit?: number } = {}) => {
  const query = new URLSearchParams();
  if (params.status) query.set('status', params.status);
  if (params.limit != null) query.set('limit', String(params.limit));
  const suffix = query.toString();
  return request<CaseListResponse | Case[]>(`/api/cases/${suffix ? `?${suffix}` : ''}`).then(asCaseList);
};

export const fetchCase = (id: string) => request<Case>(`/api/cases/${id}`);

export const createCase = (data: CreateCaseRequest) =>
  request<{ status: string; case_id: string; name: string }>('/api/cases/', {
    method: 'POST',
    body: JSON.stringify(data),
  });

export const exportCase = (id: string) =>
  request<Record<string, unknown>>(`/api/cases/${id}/export`);

export const fetchThreats = (params: { limit?: number; active_only?: boolean } = {}) =>
  fetchLiveThreats(params.limit ?? 100).then((payload) =>
    params.active_only ? payload.threats.filter((threat) => !threat.is_blocked) : payload.threats,
  );

// Block an IOC by its value (not id) — used by ThreatIntelligence page
export const blockThreat = (ioc: string, reason?: string) =>
  request<void>(`/api/threats/block`, {
    method: 'POST',
    body: JSON.stringify({ ioc, reason }),
  });

export const unblockThreat = (ioc: string) =>
  request<void>(`/api/threats/unblock`, {
    method: 'POST',
    body: JSON.stringify({ ioc }),
  });

// Fetch live threats in the format expected by ThreatIntelligence page
export const fetchLiveThreats = async (limit = 100): Promise<LiveThreatsResponse> => {
  return request<LiveThreatsResponse>(`/api/threats/live?limit=${limit}`);
};

const severityFromSignal = (signal: Signal, index: number): Alert['level'] => {
  const severity = signal.metadata?.severity;
  if (severity === 'critical' || severity === 'high' || severity === 'medium' || severity === 'low') {
    return severity;
  }
  const confidence = signal.metadata?.confidence;
  if (typeof confidence === 'number') {
    if (confidence >= 0.9) return 'critical';
    if (confidence >= 0.7) return 'high';
    if (confidence >= 0.4) return 'medium';
    return 'low';
  }
  return index === 0 ? 'high' : 'medium';
};

export const fetchAlerts = (params: { limit?: number } = {}) =>
  fetchSignals({ limit: params.limit ?? 50 }).then((signals) =>
    signals
      .filter((signal) => !Boolean(signal.is_processed))
      .map((signal, index) => ({
        id: signal.id,
        signal_id: signal.id,
        level: severityFromSignal(signal, index),
        title: `${signal.type.replace(/_/g, ' ')} signal`,
        message: signal.extracted_text ?? signal.raw_content.slice(0, 160),
        source_name: signal.source_name,
        created_at: signal.discovered_at,
        is_acknowledged: Boolean(signal.is_processed),
      })),
  );

export const acknowledgeAlert = (alert: Alert, notes: string[] = ['Acknowledged from dashboard']) =>
  request<{ status: string; signal_id: string }>(`/api/signals/${alert.signal_id}/process`, {
    method: 'PATCH',
    body: JSON.stringify(notes),
  });

export const fetchDashboardStats = async (): Promise<DashboardStats> => {
  const [personas, signals, threats] = await Promise.all([
    fetchPersonas({ limit: 200 }),
    fetchSignals({ limit: 200 }),
    fetchThreats({ limit: 200, active_only: true }),
  ]);

  const today = new Date().toDateString();
  const signalsToday = signals.filter(
    (signal) => new Date(signal.discovered_at).toDateString() === today,
  ).length;

  const criticalThreats = threats.filter((threat) => threat.severity === 'critical').length;
  const criticalPersonas = personas.filter((persona) => {
    const score = persona.threat_score;
    return score?.risk_level === 'critical' || score?.risk_level === 'high' || score?.level === 'critical' || score?.level === 'high';
  }).length;

  return {
    active_personas: personas.length,
    signals_today: signalsToday,
    critical_threats: criticalThreats + criticalPersonas,
    escalations_24h: criticalPersonas,
  };
};

export const searchOsint = (query: string) =>
  request<OsintSearchResponse>('/api/ingestion/search', {
    method: 'POST',
    body: JSON.stringify({ query }),
  });

export const askAssistant = (question: string, context?: Record<string, unknown>) =>
  request<{ answer: string; sources: string[] }>('/api/assistant/query', {
    method: 'POST',
    body: JSON.stringify({ question, context }),
  });

export const fetchCyberNews = () =>
  request<{ data: CyberNewsItem[] }>('/api/ingestion/news').then((payload) => payload.data);

export const executeResponseAction = (data: ResponseActionRequest) =>
  request<ResponseAction>('/api/response/execute', {
    method: 'POST',
    body: JSON.stringify(data),
  });
