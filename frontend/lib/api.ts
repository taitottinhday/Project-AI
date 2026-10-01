export type AnswerStatus =
  | "answered"
  | "needs_clarification"
  | "handover_suggested"
  | "insufficient_evidence";

export type Citation = {
  source_id: string;
  title: string;
  url: string;
  section?: string | null;
  published_or_updated?: string | null;
  version?: string | null;
  warning?: string | null;
};

export type ChatResponse = {
  request_id: string;
  session_id: string;
  status: AnswerStatus;
  response: string;
  citations: Citation[];
  confidence: number;
  grounded: boolean;
  reason_code: string;
  warnings: string[];
  handover_recommended: boolean;
  cache_hit: boolean;
  latency_ms: number;
};

export type MetricBreakdown = {
  key: string;
  count: number;
};

export type AnalyticsSummary = {
  window_days: number;
  generated_at: string;
  total_interactions: number;
  unique_sessions: number;
  answered: number;
  answer_rate: number;
  grounded_answer_compliance: number;
  handover_count: number;
  handover_rate: number;
  feedback_count: number;
  helpful_rate?: number | null;
  cache_hits: number;
  cache_hit_rate: number;
  average_latency_ms: number;
  status_breakdown: MetricBreakdown[];
  top_reason_codes: MetricBreakdown[];
};

export type TicketStatus = "new" | "assigned" | "in_progress" | "waiting_for_user" | "resolved" | "closed";
export type TicketCategory = "admissions" | "tuition" | "scholarship" | "program" | "application" | "technical" | "other";
export type TicketPriority = "low" | "medium" | "high" | "urgent";
export type StaffAvailability = "available" | "busy" | "offline";

export type StaffMember = {
  staff_id: string;
  display_name: string;
  department: string;
  specialties: TicketCategory[];
  availability: StaffAvailability;
  active: boolean;
  open_ticket_count: number;
  updated_at: string;
};

export type RoutingRule = {
  category: TicketCategory;
  department: string;
  auto_assign: boolean;
};

export type TicketMessage = {
  message_id: string;
  role: "user" | "assistant" | "staff";
  content: string;
  author_id?: string | null;
  request_id?: string | null;
  confidence?: number | null;
  grounded?: boolean | null;
  reason_code?: string | null;
  created_at: string;
};

export type TicketEvidence = {
  evidence_id: string;
  source_id: string;
  title: string;
  url: string;
  content_preview?: string | null;
  retrieval_score?: number | null;
  source_category?: string | null;
  created_at: string;
};

export type TicketNote = { note_id: string; author_id: string; note: string; created_at: string };
export type TicketActivity = { activity_id: string; actor_id: string; action: string; detail?: string | null; created_at: string };

export type Ticket = {
  ticket_id: string;
  status: TicketStatus;
  question: string;
  reason: string;
  staff_reply?: string | null;
  assigned_to?: string | null;
  created_at: string;
  updated_at: string;
};

export type StaffTicket = Ticket & {
  contact?: string | null;
  user_email?: string | null;
  assigned_department?: string | null;
  category: TicketCategory;
  priority: TicketPriority;
  escalation_reason: string;
  ai_confidence?: number | null;
  ai_summary?: string | null;
  suggested_reply?: string | null;
  resolution_summary?: string | null;
  resolution_type?: string | null;
  knowledge_gap: boolean;
  first_response_at?: string | null;
  last_response_at?: string | null;
  resolved_at?: string | null;
  closed_at?: string | null;
  email_delivery_status?: string | null;
  sla_deadline: string;
  sla_state: "on_track" | "due_soon" | "overdue" | "completed";
  messages: TicketMessage[];
  evidence: TicketEvidence[];
  notes: TicketNote[];
  activities: TicketActivity[];
};

export type StaffTicketMetrics = {
  open_count: number;
  unassigned_count: number;
  overdue_count: number;
  resolved_today: number;
  average_first_response_minutes?: number | null;
  by_status: MetricBreakdown[];
  by_category: MetricBreakdown[];
  by_priority: MetricBreakdown[];
};

export type KnowledgeStatus = {
  ready: boolean;
  dataset_id?: string | null;
  academic_year?: string | null;
  verified_as_of?: string | null;
  documents: number;
  chunks: number;
  sources: number;
  load_errors: string[];
};

export type AuthUser = {
  user_id: string;
  email: string;
  display_name: string;
};

export type AuthSession = {
  access_token: string;
  user: AuthUser;
};

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

function errorMessage(payload: unknown, fallback: string): string {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return fallback;
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
  timeoutMs = 35_000,
): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const authToken = window.localStorage.getItem("vinuni-auth-token");
    const response = await fetch(`${API_BASE}${path}`, {
      ...init,
      cache: "no-store",
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
        ...init.headers,
      },
    });
    const payload: unknown = await response.json().catch(() => null);
    if (!response.ok) {
      throw new ApiError(errorMessage(payload, `Yêu cầu thất bại (${response.status})`), response.status);
    }
    return payload as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("Hệ thống phản hồi quá thời gian. Vui lòng thử lại.", 408);
    }
    if (error instanceof TypeError) {
      throw new ApiError(
        "Không thể kết nối tới máy chủ tư vấn. Vui lòng kiểm tra backend đang chạy rồi thử lại.",
        0,
      );
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

export function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("vi-VN", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}
