"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { CheckIcon, RefreshIcon, ShieldIcon } from "@/components/icons";
import {
  ApiError,
  apiRequest,
  notifyAuthChanged,
  type AnalyticsSummary,
  type KnowledgeGapItem,
  type KnowledgeGapStatus,
  type RoutingRule,
  type StaffAvailability,
  type StaffMember,
  type StaffTicket,
  type TicketCategory,
} from "@/lib/api";

const ADMIN_TOKEN_KEY = "vinuni-admin-token";
const ADMIN_POLL_INTERVAL_MS = 8_000;

const categories: Array<{ value: TicketCategory; label: string }> = [
  { value: "admissions", label: "Tuyển sinh" },
  { value: "tuition", label: "Học phí" },
  { value: "scholarship", label: "Học bổng" },
  { value: "program", label: "Chương trình" },
  { value: "application", label: "Hồ sơ" },
  { value: "technical", label: "Kỹ thuật" },
  { value: "other", label: "Khác" },
];

const availabilityLabels: Record<StaffAvailability, string> = {
  available: "Rảnh · nhận ticket",
  busy: "Bận · không auto-assign",
  offline: "Ngoại tuyến",
};

type StaffDraft = {
  staff_id: string;
  display_name: string;
  department: string;
  specialties: TicketCategory[];
  availability: StaffAvailability;
  active: boolean;
};

const emptyDraft: StaffDraft = {
  staff_id: "",
  display_name: "",
  department: "",
  specialties: [],
  availability: "available",
  active: true,
};

function authHeaders(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` };
}

function ticketStatus(status: StaffTicket["status"]): string {
  return {
    new: "Chờ phân công",
    assigned: "Đã phân công",
    in_progress: "Đang xử lý",
    waiting_for_user: "Chờ ứng viên",
    resolved: "Hoàn tất",
    closed: "Đã đóng",
  }[status];
}

export function AdminDashboard() {
  const [token, setToken] = useState(() => (
    typeof window === "undefined" ? "" : window.sessionStorage.getItem(ADMIN_TOKEN_KEY) || ""
  ));
  const [ready, setReady] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [staff, setStaff] = useState<StaffMember[]>([]);
  const [rules, setRules] = useState<RoutingRule[]>([]);
  const [tickets, setTickets] = useState<StaffTicket[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null);
  const [knowledgeGaps, setKnowledgeGaps] = useState<KnowledgeGapItem[]>([]);
  const [ticketFilter, setTicketFilter] = useState<"all" | StaffTicket["status"]>("all");
  const [selectedTicketId, setSelectedTicketId] = useState("");
  const [draft, setDraft] = useState<StaffDraft>(emptyDraft);
  const [saving, setSaving] = useState(false);

  const selectedTicket = useMemo(
    () => tickets.find((ticket) => ticket.ticket_id === selectedTicketId) || null,
    [selectedTicketId, tickets],
  );

  const visibleTickets = useMemo(
    () => ticketFilter === "all" ? tickets : tickets.filter((ticket) => ticket.status === ticketFilter),
    [ticketFilter, tickets],
  );

  const selectedCanDispatch = Boolean(selectedTicket && !["resolved", "closed"].includes(selectedTicket.status));

  const load = useCallback(async (activeToken = token) => {
    if (!activeToken.trim()) return;
    setLoading(true);
    try {
      const [staffData, ruleData, ticketData, analyticsData, knowledgeGapData] = await Promise.all([
        apiRequest<StaffMember[]>("/api/v1/admin/staff", { headers: authHeaders(activeToken) }, 12_000),
        apiRequest<RoutingRule[]>("/api/v1/admin/routing-rules", { headers: authHeaders(activeToken) }, 12_000),
        apiRequest<StaffTicket[]>("/api/v1/admin/tickets?sort=priority", { headers: authHeaders(activeToken) }, 12_000),
        apiRequest<AnalyticsSummary>("/api/v1/admin/analytics?days=30", { headers: authHeaders(activeToken) }, 12_000),
        apiRequest<KnowledgeGapItem[]>("/api/v1/admin/knowledge-gaps?status=open", { headers: authHeaders(activeToken) }, 12_000),
      ]);
      setStaff(staffData);
      setRules(ruleData);
      setTickets(ticketData);
      setAnalytics(analyticsData);
      setKnowledgeGaps(knowledgeGapData);
      setSelectedTicketId((current) => ticketData.some((ticket) => ticket.ticket_id === current) ? current : ticketData[0]?.ticket_id || "");
      setReady(true);
      setError("");
    } catch (caught) {
      setReady(false);
      setError(caught instanceof Error ? caught.message : "Không thể tải trang quản trị.");
      if (caught instanceof ApiError && [401, 503].includes(caught.status)) {
        window.sessionStorage.removeItem(ADMIN_TOKEN_KEY);
        notifyAuthChanged();
        setToken("");
      }
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (!token) return;
    const hydration = window.setTimeout(() => void load(token), 0);
    return () => window.clearTimeout(hydration);
  }, [load, token]);

  useEffect(() => {
    if (!ready || !token) return;
    const refresh = () => {
      if (document.visibilityState === "visible" && !saving) void load(token);
    };
    const interval = window.setInterval(refresh, ADMIN_POLL_INTERVAL_MS);
    const onVisibilityChange = () => {
      if (document.visibilityState === "visible") refresh();
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [load, ready, saving, token]);

  // Re-announce after the protected data has loaded. This covers the small
  // hydration window where the root Header can miss the initial login event.
  useEffect(() => {
    if (ready) notifyAuthChanged();
  }, [ready]);

  async function login(event: FormEvent) {
    event.preventDefault();
    if (!token.trim()) {
      setError("Nhập Admin API token để tiếp tục.");
      return;
    }
    window.sessionStorage.setItem(ADMIN_TOKEN_KEY, token.trim());
    notifyAuthChanged();
    try {
      await load(token.trim());
    } catch {
      // load keeps the API error in the panel; guard the submit promise too.
    }
  }

  function logout() {
    window.sessionStorage.removeItem(ADMIN_TOKEN_KEY);
    notifyAuthChanged();
    setToken("");
    setReady(false);
    setStaff([]);
    setRules([]);
    setTickets([]);
    setAnalytics(null);
    setKnowledgeGaps([]);
    setError("");
  }

  async function updateKnowledgeGap(gapId: string, status: KnowledgeGapStatus) {
    setSaving(true);
    try {
      await apiRequest<KnowledgeGapItem>(`/api/v1/admin/knowledge-gaps/${encodeURIComponent(gapId)}`, {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify({ status }),
      });
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể cập nhật knowledge gap.");
    } finally {
      setSaving(false);
    }
  }

  async function saveStaff(event: FormEvent) {
    event.preventDefault();
    if (!draft.staff_id.trim() || !draft.display_name.trim() || !draft.department.trim() || !draft.specialties.length) {
      setError("Nhập mã, tên, nhóm phụ trách và ít nhất một chuyên môn.");
      return;
    }
    setSaving(true);
    try {
      await apiRequest<StaffMember>("/api/v1/admin/staff", {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify(draft),
      });
      setDraft(emptyDraft);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể lưu cán bộ.");
    } finally {
      setSaving(false);
    }
  }

  async function updateRule(category: TicketCategory, patch: Partial<RoutingRule>) {
    const current = rules.find((rule) => rule.category === category);
    if (!current) return;
    setSaving(true);
    try {
      await apiRequest(`/api/v1/admin/routing-rules/${category}`, {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify({ department: patch.department ?? current.department, auto_assign: patch.auto_assign ?? current.auto_assign }),
      });
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể cập nhật routing.");
    } finally {
      setSaving(false);
    }
  }

  async function assignTicket(assignedTo: string | null) {
    if (!selectedTicket) return;
    setSaving(true);
    try {
      await apiRequest(`/api/v1/admin/tickets/${encodeURIComponent(selectedTicket.ticket_id)}/assign`, {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify({ assigned_to: assignedTo }),
      });
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể phân công ticket.");
    } finally {
      setSaving(false);
    }
  }

  function toggleSpecialty(category: TicketCategory) {
    setDraft((current) => ({
      ...current,
      specialties: current.specialties.includes(category)
        ? current.specialties.filter((item) => item !== category)
        : [...current.specialties, category],
    }));
  }

  if (!ready) {
    return <section className="admin-login-card"><div className="admin-login-visual"><span><ShieldIcon /></span><div><strong>Khu vực quản trị</strong><p>Thiết lập nhóm chuyên môn, trạng thái cán bộ và quy tắc phân phối ticket.</p></div></div><form className="staff-login-form" onSubmit={login}><span className="section-kicker"><ShieldIcon /> Admin</span><h2>Đăng nhập quản trị vận hành</h2><p>Admin token được cấu hình trên backend, tách biệt với token của cán bộ.</p><label className="field-label" htmlFor="admin-token">Admin API token</label><input id="admin-token" onChange={(event) => setToken(event.target.value)} placeholder="Token quản trị" type="password" value={token} />{error ? <p className="form-error" role="alert">{error}</p> : null}<button className="button button-primary full-width" disabled={loading} type="submit">{loading ? "Đang xác thực…" : "Vào trang quản trị"}</button></form></section>;
  }

  return <div className="admin-dashboard">
    <div className="admin-topbar"><div><span className="eyebrow">Operations control center</span><h2>Điều phối nhân sự & ticket</h2></div><div><button className="text-button" disabled={loading} onClick={() => void load()} type="button"><RefreshIcon className={loading ? "spin" : ""} /> Làm mới</button><button className="text-button danger" onClick={logout} type="button">Đăng xuất</button></div></div>
    {error ? <div className="connection-error" role="alert"><span>{error}</span><button onClick={() => setError("")} type="button">Đóng</button></div> : null}

    <section className="admin-overview" aria-label="Tổng quan vận hành"><article><strong>{tickets.filter((item) => item.status === "new").length}</strong><span>Đang chờ phân công</span></article><article><strong>{staff.filter((item) => item.active && item.availability === "available").length}</strong><span>Cán bộ đang rảnh</span></article><article><strong>{tickets.filter((item) => ["assigned", "in_progress"].includes(item.status)).length}</strong><span>Ticket đang xử lý</span></article><article><strong>{staff.reduce((total, item) => total + item.open_ticket_count, 0)}</strong><span>Tổng tải công việc</span></article></section>

    <section className="admin-workflow-banner" aria-label="Quy tắc ownership">
      <div><span className="eyebrow">Ownership contract</span><strong>Admin điều phối · Staff xử lý · Hệ thống ghi audit</strong><p>Ticket mới vào hàng chờ nhóm; Auto-dispatch hoặc Admin gắn owner; Staff claim đúng specialty rồi mới trả lời.</p></div>
      <div className="workflow-statuses"><span>new</span><i>→</i><span>assigned</span><i>→</i><span>in progress</span><i>→</i><span>waiting</span><i>→</i><span>resolved</span></div>
    </section>

    <section className="admin-operations-grid" aria-label="Chất lượng và knowledge gaps">
      <div className="admin-panel admin-quality-panel">
        <div className="panel-heading"><div><span className="eyebrow">Quality loop · 30 ngày</span><h3>Đo lường từ chat đến ticket</h3></div><span>{analytics ? `${analytics.total_interactions} lượt` : "Đang tải"}</span></div>
        <div className="admin-quality-grid">
          <article><strong>{analytics ? `${Math.round(analytics.answer_rate * 100)}%` : "—"}</strong><span>Trả lời được</span></article>
          <article><strong>{analytics ? `${Math.round(analytics.handover_rate * 100)}%` : "—"}</strong><span>Cần cán bộ</span></article>
          <article><strong>{analytics?.helpful_rate == null ? "—" : `${Math.round(analytics.helpful_rate * 100)}%`}</strong><span>Đánh giá hữu ích</span></article>
          <article><strong>{analytics ? `${Math.round(analytics.average_latency_ms)}ms` : "—"}</strong><span>Độ trễ trung bình</span></article>
        </div>
        <p className="muted-copy">Số liệu giúp admin phát hiện chủ đề chatbot chưa trả lời tốt, rồi chuyển ticket đã xử lý thành việc bổ sung knowledge base.</p>
      </div>
      <div className="admin-panel knowledge-gap-panel">
        <div className="panel-heading"><div><span className="eyebrow">Human feedback loop</span><h3>Knowledge gaps</h3></div><span>{knowledgeGaps.length} đang mở</span></div>
        {knowledgeGaps.length ? <div className="knowledge-gap-list">{knowledgeGaps.slice(0, 6).map((gap) => <article className="knowledge-gap-row" key={gap.gap_id}><div><strong>{gap.ticket_id} · {categories.find((item) => item.value === gap.category)?.label || gap.category}</strong><p>{gap.description}</p><small>{new Date(gap.created_at).toLocaleDateString("vi-VN")}</small></div><select aria-label={`Trạng thái ${gap.gap_id}`} disabled={saving} onChange={(event) => void updateKnowledgeGap(gap.gap_id, event.target.value as KnowledgeGapStatus)} value={gap.status}><option value="open">Mở</option><option value="in_review">Đang review</option><option value="resolved">Đã xử lý</option></select></article>)}</div> : <div className="empty-compact"><CheckIcon /><p>Chưa có khoảng trống tri thức cần review.</p></div>}
      </div>
    </section>

    <div className="admin-grid">
      <section className="admin-panel admin-staff-panel"><div className="panel-heading"><div><span className="eyebrow">People & teams</span><h3>Nhóm cán bộ</h3></div><span>{staff.length} hồ sơ</span></div><div className="admin-staff-list">{staff.map((member) => <button className={draft.staff_id === member.staff_id ? "admin-staff-row selected" : "admin-staff-row"} key={member.staff_id} onClick={() => setDraft({ staff_id: member.staff_id, display_name: member.display_name, department: member.department, specialties: member.specialties, availability: member.availability, active: member.active })} type="button"><span><strong>{member.display_name}</strong><small>{member.staff_id} · {member.department}</small></span><span className={`availability availability-${member.availability}`}>{availabilityLabels[member.availability]}</span><small>{member.open_ticket_count} ticket mở</small></button>)}</div><form className="admin-staff-form" onSubmit={saveStaff}><strong>{draft.staff_id ? "Cập nhật cán bộ" : "Thêm cán bộ"}</strong><div className="admin-form-grid"><label>Mã cán bộ<input onChange={(event) => setDraft((current) => ({ ...current, staff_id: event.target.value }))} placeholder="tuition-01" value={draft.staff_id} /></label><label>Tên hiển thị<input onChange={(event) => setDraft((current) => ({ ...current, display_name: event.target.value }))} placeholder="Nguyễn Minh Anh" value={draft.display_name} /></label><label>Nhóm phụ trách<input onChange={(event) => setDraft((current) => ({ ...current, department: event.target.value }))} placeholder="Tài chính & Học phí" value={draft.department} /></label><label>Trạng thái<select onChange={(event) => setDraft((current) => ({ ...current, availability: event.target.value as StaffAvailability }))} value={draft.availability}>{Object.entries(availabilityLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label></div><fieldset><legend>Chuyên môn nhận ticket</legend><div className="specialty-options">{categories.map((category) => <label key={category.value}><input checked={draft.specialties.includes(category.value)} onChange={() => toggleSpecialty(category.value)} type="checkbox" />{category.label}</label>)}</div></fieldset><label className="consent-row"><input checked={draft.active} onChange={(event) => setDraft((current) => ({ ...current, active: event.target.checked }))} type="checkbox" /><span>Đang hoạt động</span></label><div className="admin-form-actions"><button className="text-button" onClick={() => setDraft(emptyDraft)} type="button">Tạo hồ sơ mới</button><button className="button button-primary" disabled={saving} type="submit"><CheckIcon /> Lưu cán bộ</button></div></form></section>

      <section className="admin-panel"><div className="panel-heading"><div><span className="eyebrow">Routing policy</span><h3>Phân loại → Nhóm phụ trách</h3></div><span>Auto-dispatch</span></div><p className="muted-copy">Hệ thống chỉ chọn cán bộ đang rảnh, đúng chuyên môn và có ít ticket mở nhất. Nếu đồng tải, hệ thống chọn ngẫu nhiên.</p><div className="routing-rule-list">{rules.map((rule) => <div className="routing-rule" key={rule.category}><strong>{categories.find((item) => item.value === rule.category)?.label || rule.category}</strong><input aria-label={`Nhóm cho ${rule.category}`} disabled={saving} onBlur={(event) => { if (event.target.value.trim() && event.target.value !== rule.department) void updateRule(rule.category, { department: event.target.value.trim() }); }} defaultValue={rule.department} /><label><input checked={rule.auto_assign} disabled={saving} onChange={(event) => void updateRule(rule.category, { auto_assign: event.target.checked })} type="checkbox" />Tự động phân công</label></div>)}</div></section>

      <section className="admin-panel admin-ticket-panel"><div className="panel-heading"><div><span className="eyebrow">Queue control</span><h3>Điều phối ticket</h3></div><div className="panel-heading-tools"><span>{visibleTickets.length}/{tickets.length} ticket</span><select aria-label="Lọc ticket theo trạng thái" onChange={(event) => setTicketFilter(event.target.value as typeof ticketFilter)} value={ticketFilter}><option value="all">Tất cả</option><option value="new">Chờ phân công</option><option value="assigned">Đã phân công</option><option value="in_progress">Đang xử lý</option><option value="waiting_for_user">Chờ ứng viên</option><option value="resolved">Hoàn tất</option><option value="closed">Đã đóng</option></select></div></div><div className="admin-ticket-list">{visibleTickets.map((ticket) => <button className={selectedTicketId === ticket.ticket_id ? "admin-ticket-row selected" : "admin-ticket-row"} key={ticket.ticket_id} onClick={() => setSelectedTicketId(ticket.ticket_id)} type="button"><span><strong>{ticket.ticket_id}</strong><small>{ticketStatus(ticket.status)} · {categories.find((item) => item.value === ticket.category)?.label}</small></span><p>{ticket.question}</p><small>{ticket.assigned_department || "Chưa định tuyến"} · {ticket.assigned_to || "Chưa có cán bộ"}</small></button>)}</div>{selectedTicket ? <div className="ticket-dispatch"><strong>{selectedTicket.assigned_to ? `Điều phối lại ${selectedTicket.ticket_id}` : `Phân công ${selectedTicket.ticket_id}`}</strong><p>{selectedTicket.question}</p><small className="muted-copy">Admin là nơi quyết định ownership. Cán bộ chỉ nhận xử lý khi ticket đã được phân công hoặc thuộc đúng hàng chờ chuyên môn.</small><select disabled={saving || !selectedCanDispatch} onChange={(event) => { if (event.target.value) void assignTicket(event.target.value); }} value=""><option value="">Chọn cán bộ đang nhận ticket…</option>{staff.filter((member) => member.active && member.availability !== "offline").map((member) => <option key={member.staff_id} value={member.staff_id}>{member.display_name} · {member.department} · {availabilityLabels[member.availability]}</option>)}</select>{selectedTicket.assigned_to && selectedCanDispatch ? <button className="text-button danger" disabled={saving} onClick={() => void assignTicket(null)} type="button">Gỡ phân công, đưa về hàng chờ</button> : null}{!selectedCanDispatch ? <span className="muted-copy">Ticket đã kết thúc; không thể điều phối lại.</span> : null}</div> : null}</section>
    </div>
  </div>;
}
