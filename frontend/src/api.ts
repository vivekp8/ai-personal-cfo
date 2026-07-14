// API client + shared types for the AI Personal CFO frontend.
// In dev, requests go through the Vite proxy at /api -> http://localhost:8000.
// In production, set VITE_API_BASE to the backend URL (e.g. https://api.example.com)
// at build time; otherwise it falls back to "/api" (expects a reverse proxy).
const BASE = (import.meta.env.VITE_API_BASE as string | undefined) || "/api";
export const DEFAULT_USER = "demo_user";

// ---------- Types (mirror the backend response shapes) ----------
export interface Transaction {
  date: string;
  description: string;
  amount: number;
  category: string;
}

export interface MonthlySummary {
  months: string[];
  by_month_category: Record<string, Record<string, number>>;
  monthly_income: Record<string, number>;
  monthly_expenses: Record<string, number>;
  category_totals: Record<string, number>;
}

export interface Anomaly {
  type: "category_spike" | "large_transaction";
  month?: string;
  date?: string;
  category: string;
  description?: string;
  amount: number;
  expected: number;
  severity: "high" | "medium";
  message: string;
}

export interface Forecast {
  next_month: string;
  total_expense_forecast: number;
  category_forecast: Record<string, number>;
  history: { months: string[]; expenses: number[] };
}

export interface HealthScore {
  score: number;
  savings_rate: number;
  income: number;
  expenses: number;
  anomalies_count: number;
  emergency_fund_months: number;
  active_emis: number;
  reference_month: string;
  rating: string;
}

export interface SavingsSuggestion {
  category: string;
  title: string;
  detail: string;
  monthly_savings: number;
}

export interface DashboardData {
  user_id: string;
  transactions: Transaction[];
  monthly_summary: MonthlySummary;
  anomalies: Anomaly[];
  forecast: Forecast;
  health_score: HealthScore;
  savings_suggestions: SavingsSuggestion[];
}

export interface Capabilities {
  llm_configured: boolean;
  llm_providers?: string[];
  rag_available: boolean;
  langgraph: boolean;
  whisper: boolean;
  gtts: boolean;
  voice?: {
    stt_providers: string[];
    tts_providers: string[];
  };
}

export interface ChatResponse {
  response: string;
  intent: string;
  retrieved_context: string[];
  llm_used: boolean;
  llm_error?: string | null;
}

export interface ChatHistoryMessage {
  role: "user" | "assistant";
  content: string;
  intent?: string | null;
  llm_used?: boolean | null;
  created_at?: string;
}

export interface DebateOpinion {
  agent: string;
  key: string;
  focus: string;
  stance: string;
  confidence: number;
  opinion: string;
  reasoning_summary: string;
  llm_used: boolean;
  error?: string | null;
}

export interface DebateDecision {
  agent: string;
  recommendation: string;
  overall_confidence: number;
  llm_used: boolean;
  error?: string | null;
}

export interface DebateResponse {
  question: string;
  opinions: DebateOpinion[];
  decision: DebateDecision;
  meta: { agent_count: number; langgraph: boolean; llm_configured: boolean };
}

export interface ScenarioFull {
  label: string;
  new_savings: number;
  emergency_fund_months: number;
  monthly_outflow: number;
  savings_rate: number;
  health_score: number;
  affordable: boolean;
}

export interface ScenarioEmi {
  label: string;
  emi_monthly: number;
  total_paid: number;
  interest_paid: number;
  emergency_fund_months: number;
  monthly_outflow: number;
  savings_rate: number;
  health_score: number;
}

export interface Simulation {
  purchase_amount: number;
  tenure_months: number;
  current_savings: number;
  monthly_expenses: number;
  pay_full: ScenarioFull;
  emi: ScenarioEmi;
  recommendation: "pay_full" | "emi";
}

export interface WhatIfResponse {
  simulation: Simulation;
  explanation: ChatResponse | null;
}

// ---------- Helpers ----------
async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

// ---------- Endpoints ----------
export async function getHealth(): Promise<{ status: string }> {
  return handle(await fetch(`${BASE}/health`));
}

export async function getCapabilities(): Promise<Capabilities> {
  return handle(await fetch(`${BASE}/capabilities`));
}

export async function listSamples(): Promise<{ samples: string[] }> {
  return handle(await fetch(`${BASE}/samples`));
}

export async function uploadCsv(
  file: File,
  userId = DEFAULT_USER
): Promise<DashboardData> {
  const form = new FormData();
  form.append("file", file);
  form.append("user_id", userId);
  return handle(await fetch(`${BASE}/upload`, { method: "POST", body: form }));
}

export async function loadSample(
  name: string,
  userId = DEFAULT_USER
): Promise<DashboardData> {
  const form = new FormData();
  form.append("name", name);
  form.append("user_id", userId);
  return handle(await fetch(`${BASE}/load-sample`, { method: "POST", body: form }));
}

export async function getDashboard(userId = DEFAULT_USER): Promise<DashboardData> {
  return handle(await fetch(`${BASE}/dashboard/${userId}`));
}

export async function sendChat(
  query: string,
  userId = DEFAULT_USER
): Promise<ChatResponse> {
  return handle(
    await fetch(`${BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, query }),
    })
  );
}

export async function getChatHistory(
  userId = DEFAULT_USER
): Promise<{ history: ChatHistoryMessage[] }> {
  return handle(await fetch(`${BASE}/chat/history/${userId}`));
}

// ---------- Phase 2: Multi-Agent Debate ----------
export interface AgentOpinion {
  agent: string;
  role: string;
  icon: string;
  stance: string;
  summary: string;
  key_points: string[];
  confidence: number;
  llm_used: boolean;
  latency_ms: number;
  retries: number;
  error?: string | null;
}

export interface DebateDecision {
  summary: string;
  consensus_confidence: number;
  priorities: { agent: string; icon: string; action: string; confidence: number }[];
  llm_used: boolean;
}

export interface DebateResult {
  opinions: AgentOpinion[];
  decision: DebateDecision;
  meta: {
    agent_count: number;
    langgraph: boolean;
    elapsed_ms: number;
    llm_used: boolean;
  };
}

export async function runDebate(
  question = "",
  userId = DEFAULT_USER
): Promise<DebateResult> {
  return handle(
    await fetch(`${BASE}/debate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, question }),
    })
  );
}

// ---------- Phase 3: Digital Financial Twin ----------
export interface TwinGoal {
  name: string;
  target_amount: number;
}

export interface ScenarioInput {
  name: string;
  years: number;
  monthly_income: number;
  monthly_expenses: number;
  current_savings: number;
  salary_growth: number;
  expense_growth: number;
  inflation: number;
  investment_return: number;
  current_age?: number | null;
  retirement_age?: number | null;
  goals: TwinGoal[];
}

export interface YearProjection {
  year: number;
  age?: number | null;
  annual_income: number;
  annual_expenses: number;
  annual_savings: number;
  invested: number;
  net_worth: number;
  real_net_worth: number;
  emergency_fund_months: number;
}

export interface RetirementEstimate {
  applicable: boolean;
  retirement_age?: number | null;
  years_to_retirement?: number | null;
  projected_corpus?: number | null;
  sustainable_annual_income?: number | null;
  sustainable_monthly_income?: number | null;
  real_sustainable_monthly_income?: number | null;
}

export interface GoalTimeline {
  name: string;
  target_amount: number;
  reached: boolean;
  year_reached?: number | null;
  years_to_reach?: number | null;
}

export interface TwinResult {
  scenario: ScenarioInput;
  projection: YearProjection[];
  final_net_worth: number;
  final_real_net_worth: number;
  total_contributed: number;
  total_growth: number;
  retirement: RetirementEstimate;
  goals: GoalTimeline[];
}

export interface SavedSimulation {
  id: number;
  name: string;
  params: Partial<ScenarioInput>;
  result: TwinResult;
  created_at: string;
}

export async function simulateTwin(
  scenario: Partial<ScenarioInput>,
  opts: { save?: boolean; name?: string; userId?: string } = {}
): Promise<{ result: TwinResult; saved_id: number | null }> {
  const { save = false, name, userId = DEFAULT_USER } = opts;
  return handle(
    await fetch(`${BASE}/twin/simulate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, scenario, save, name }),
    })
  );
}

export async function compareTwin(
  scenarios: Partial<ScenarioInput>[],
  userId = DEFAULT_USER
): Promise<{ results: TwinResult[] }> {
  return handle(
    await fetch(`${BASE}/twin/compare`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, scenarios }),
    })
  );
}

export async function getSimulations(
  userId = DEFAULT_USER
): Promise<{ scenarios: SavedSimulation[] }> {
  return handle(await fetch(`${BASE}/twin/scenarios/${userId}`));
}

export async function deleteSimulation(
  id: number,
  userId = DEFAULT_USER
): Promise<{ status: string; id: number }> {
  return handle(
    await fetch(`${BASE}/twin/scenario/${id}?user_id=${userId}`, {
      method: "DELETE",
    })
  );
}


export async function clearChatHistory(
  userId = DEFAULT_USER
): Promise<{ status: string; removed: number }> {
  return handle(
    await fetch(`${BASE}/chat/history/${userId}`, { method: "DELETE" })
  );
}

export async function runWhatIf(params: {
  purchase_amount: number;
  tenure_months: number;
  current_savings?: number | null;
  explain?: boolean;
  userId?: string;
}): Promise<WhatIfResponse> {
  const { userId = DEFAULT_USER, explain = true, ...rest } = params;
  return handle(
    await fetch(`${BASE}/whatif`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, explain, ...rest }),
    })
  );
}

export interface TranscriptionResult {
  text: string;
  available: boolean;
  error?: string | null;
  bytes?: number;
  provider?: string;
  confidence?: number;
  language?: string | null;
  latency_ms?: number;
  low_confidence?: boolean;
}

export interface VoiceConfig {
  stt_providers: string[];
  tts_providers: string[];
  config: {
    stt_priority: string[];
    tts_priority: string[];
    enable_streaming: boolean;
    enable_memory: boolean;
    enable_rag: boolean;
    enable_offline_mode: boolean;
    enable_auto_retry: boolean;
    whisper_model: string;
    whisper_lang: string;
    stt_min_confidence: number;
    tts_lang: string;
  };
}

export async function getVoiceConfig(): Promise<VoiceConfig> {
  return handle(await fetch(`${BASE}/voice/config`));
}

// ---------- Phase 4: Explainable AI ----------
export interface ExplanationCard {
  subject: string;
  title: string;
  why: string;
  evidence: string[];
  confidence: number;
  retrieved_documents: string[];
  transactions_used: Transaction[];
  formula: string;
  model: string;
  reasoning_summary: string;
}

export async function explainSubject(
  subject: string,
  userId = DEFAULT_USER
): Promise<ExplanationCard> {
  return handle(
    await fetch(`${BASE}/explain`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, subject }),
    })
  );
}

// ---------- Phase 9: Goal Planner ----------
export interface GoalType {
  id: string;
  label: string;
  icon: string;
  default_months: number;
  assumed_return: number;
}

export interface GoalPlan {
  id?: number;
  name?: string;
  goal_type: string;
  label: string;
  icon: string;
  target_amount: number;
  current_saved: number;
  remaining: number;
  annual_return: number;
  timeline_months: number;
  target_date: string;
  required_monthly: number;
  monthly_contribution: number;
  monthly_surplus: number;
  completion_probability: number;
  risk: string;
  reachable: boolean;
  trajectory: { month: number; balance: number }[];
  progress_pct: number;
}

export interface GoalCreateInput {
  name: string;
  goal_type: string;
  target_amount: number;
  current_saved?: number;
  target_months?: number | null;
  monthly_contribution?: number | null;
}

export async function getGoalTypes(): Promise<{ types: GoalType[] }> {
  return handle(await fetch(`${BASE}/goals/types`));
}

export async function getGoals(
  userId = DEFAULT_USER
): Promise<{ goals: GoalPlan[]; monthly_surplus: number }> {
  return handle(await fetch(`${BASE}/goals/${userId}`));
}

export async function createGoal(
  input: GoalCreateInput,
  userId = DEFAULT_USER
): Promise<{ goal: GoalPlan }> {
  return handle(
    await fetch(`${BASE}/goals`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, ...input }),
    })
  );
}

export async function deleteGoal(
  id: number,
  userId = DEFAULT_USER
): Promise<{ status: string; id: number }> {
  return handle(
    await fetch(`${BASE}/goals/${id}?user_id=${userId}`, { method: "DELETE" })
  );
}

// ---------- Phase 6: Retrieval Visualization ----------
export interface RagChunk {
  text: string;
  collection: string;
  distance: number;
  similarity: number;
  rank: number;
  point?: [number, number, number];
}

export interface RagTraceResult {
  available: boolean;
  reason?: string;
  query?: string;
  embedding?: { model: string; dimension: number; query_point: [number, number, number] };
  chunks: RagChunk[];
  top_k?: number;
  final_context?: string;
  stages?: string[];
}

export async function ragTrace(
  query: string,
  k = 4,
  userId = DEFAULT_USER
): Promise<RagTraceResult> {
  return handle(
    await fetch(`${BASE}/rag/trace`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, query, k }),
    })
  );
}

// ---------- Phase 5: Long-Term Memory ----------
export interface MemoryItem {
  kind: string;
  mem_key: string;
  content: string;
  data: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export type MemoryByKind = Record<string, MemoryItem[]>;

export async function getMemory(
  userId = DEFAULT_USER
): Promise<{ memory: MemoryByKind }> {
  return handle(await fetch(`${BASE}/memory/${userId}`));
}

export async function addPreference(
  key: string,
  value: string,
  userId = DEFAULT_USER
): Promise<{ kind: string; key: string; value: string }> {
  return handle(
    await fetch(`${BASE}/memory/preference`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, key, value }),
    })
  );
}

export async function addGoal(
  name: string,
  targetAmount: number | null,
  note = "",
  userId = DEFAULT_USER
): Promise<{ kind: string; name: string }> {
  return handle(
    await fetch(`${BASE}/memory/goal`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: userId,
        name,
        target_amount: targetAmount,
        note,
      }),
    })
  );
}

export async function clearMemory(
  userId = DEFAULT_USER,
  kind?: string
): Promise<{ status: string; removed: number }> {
  const q = kind ? `?kind=${encodeURIComponent(kind)}` : "";
  return handle(
    await fetch(`${BASE}/memory/${userId}${q}`, { method: "DELETE" })
  );
}

export async function transcribeAudio(blob: Blob): Promise<TranscriptionResult> {
  const type = blob.type || "audio/webm";
  const ext = type.includes("mp4")
    ? "mp4"
    : type.includes("ogg")
      ? "ogg"
      : "webm";
  const form = new FormData();
  form.append("file", blob, `recording.${ext}`);
  return handle(await fetch(`${BASE}/voice/transcribe`, { method: "POST", body: form }));
}

export async function speak(text: string): Promise<Blob> {
  const res = await fetch(`${BASE}/voice/speak`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) throw new Error("TTS unavailable");
  return res.blob();
}

// ---------- Phase 7: Workflow Visualization ----------
export interface WorkflowNode {
  id: string;
  label: string;
  group: string;
  desc: string;
  deferred?: boolean;
  status?: "ok" | "error" | "pending" | "deferred";
  duration_ms?: number;
  retries?: number;
  error?: string | null;
  detail?: string | null;
}

export interface WorkflowEdge {
  from: string;
  to: string;
}

export interface WorkflowTrace {
  nodes?: WorkflowNode[];
  trace?: WorkflowNode[] | null;
  edges: WorkflowEdge[];
  langgraph: boolean;
  total_ms?: number;
  format?: string;
  supported_formats?: string[];
}

export async function getWorkflowTrace(
  userId = DEFAULT_USER
): Promise<WorkflowTrace> {
  return handle(await fetch(`${BASE}/workflow/trace/${userId}`));
}

export async function getWorkflowGraph(): Promise<WorkflowTrace> {
  return handle(await fetch(`${BASE}/workflow/graph`));
}

// ---------- Phase 8: Model Routing ----------
export interface RouterProvider {
  name: string;
  label: string;
  rank: number;
  model: string;
  status: "healthy" | "unhealthy" | "not_configured" | string;
  available: boolean;
  offline: boolean;
  requests: number;
  avg_latency_ms: number;
  errors: number;
  total_tokens: number;
  cost_estimate_usd: number;
}

export interface RouterStatus {
  providers: RouterProvider[];
  preferred: string;
  active_provider: string;
  last_provider: string | null;
  totals: {
    requests?: number;
    total_tokens?: number;
    cost_estimate_usd?: number;
    avg_latency_ms?: number;
  };
  cache: { hits?: number; misses?: number; hit_rate?: number };
}

export async function getRouterStatus(): Promise<RouterStatus> {
  return handle(await fetch(`${BASE}/router/status`));
}

export async function setPreferredProvider(
  provider: string
): Promise<{ preferred: string; selection: string[] }> {
  return handle(
    await fetch(`${BASE}/router/provider`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider }),
    })
  );
}
