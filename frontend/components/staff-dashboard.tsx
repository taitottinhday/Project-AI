"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { CheckIcon, ClockIcon, ExternalIcon, RefreshIcon, SendIcon, ShieldIcon, StaffIcon } from "@/components/icons";
import {
  ApiError,
  apiRequest,
  formatDateTime,
  type StaffTicket,
  type StaffTicketMetrics,
  type StaffAvailability,
  type StaffMember,
  type TicketCategory,
  type TicketPriority,
  type TicketStatus,
} from "@/lib/api";

const STAFF_TOKEN_KEY = "vinuni-staff-token";
const STAFF_ID_KEY = "vinuni-staff-id";
const POLL_INTERVAL_MS = 8_000;

const statusLabels: Record<TicketStatus, string> = {
  new: "Mới tiếp nhận",
  assigned: "Đã phân công",
  in_progress: "Đang xử lý",
  waiting_for_user: "Chờ ứng viên",
  resolved: "Đã hoàn tất",
  closed: "Đã đóng",
};

const categoryLabels: Record<TicketCategory, string> = {
  admissions: "Tuyển sinh",
  tuition: "Học phí",
  scholarship: "Học bổng",
  program: "Chương trình",
  application: "Hồ sơ",
  technical: "Kỹ thuật",
  other: "Khác",
};

const priorityLabels: Record<TicketPriority, string> = {
  low: "Thấp",
  medium: "Trung bình",
  high: "Cao",
  urgent: "Khẩn cấp",
};

const categories = Object.keys(categoryLabels) as TicketCategory[];
const priorities = Object.keys(priorityLabels) as TicketPriority[];
const statuses = Object.keys(statusLabels) as TicketStatus[];

function authHeaders(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` };
}

function compactTime(value: number | null | undefined): string {
  if (value == null) return "Chưa có dữ liệu";
  if (value < 60) return `${Math.round(value)} phút`;
  return `${(value / 60).toFixed(1)} giờ`;
}

export function StaffDashboard() {
  const [token, setToken] = useState("");
  const [staffId, setStaffId] = useState("");
  const [loggedIn, setLoggedIn] = useState(false);
  const [tickets, setTickets] = useState<StaffTicket[]>([]);
  const [metrics, setMetrics] = useState<StaffTicketMetrics | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<"all" | TicketStatus>("all");
  const [categoryFilter, setCategoryFilter] = useState<"all" | TicketCategory>("all");
  const [priorityFilter, setPriorityFilter] = useState<"all" | TicketPriority>("all");
  const [sort, setSort] = useState<"oldest" | "newest" | "priority">("priority");
  const [search, setSearch] = useState("");
  const [reply, setReply] = useState("");
  const [note, setNote] = useState("");
  const [profile, setProfile] = useState<StaffMember | null>(null);
  const [resolutionSummary, setResolutionSummary] = useState("");
  const [resolutionType, setResolutionType] = useState("answered");
  const [knowledgeGap, setKnowledgeGap] = useState(false);
  const [knowledgeGapDescription, setKnowledgeGapDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState("");

  const selected = useMemo(
    () => tickets.find((ticket) => ticket.ticket_id === selectedId) || null,
    [selectedId, tickets],
  );

  const visibleTickets = useMemo(() => tickets.filter((ticket) => {
    if (statusFilter !== "all" && ticket.status !== statusFilter) return false;
    if (categoryFilter !== "all" && ticket.category !== categoryFilter) return false;
    if (priorityFilter !== "all" && ticket.priority !== priorityFilter) return false;
    const needle = search.trim().toLocaleLowerCase("vi");
    return !needle || `${ticket.ticket_id} ${ticket.question} ${ticket.ai_summary || ""} ${ticket.contact || ""}`
      .toLocaleLowerCase("vi").includes(needle);
  }), [categoryFilter, priorityFilter, search, statusFilter, tickets]);

  useEffect(() => {
    const hydration = window.setTimeout(() => {
      setToken(window.sessionStorage.getItem(STAFF_TOKEN_KEY) || "");
      setStaffId(window.sessionStorage.getItem(STAFF_ID_KEY) || "");
    }, 0);
    return () => window.clearTimeout(hydration);
  }, []);

  const loadDashboard = useCallback(async (activeToken = token) => {
    if (!activeToken) return;
    setLoading(true);
    try {
      const [ticketData, metricData] = await Promise.all([
        apiRequest<StaffTicket[]>(`/api/v1/staff/tickets?sort=${sort}`, {
          headers: authHeaders(activeToken),
        }, 12_000),
        apiRequest<StaffTicketMetrics>("/api/v1/staff/tickets/metrics", {
          headers: authHeaders(activeToken),
        }, 12_000),
      ]);
      setTickets(ticketData);
      setMetrics(metricData);
      setLoggedIn(true);
      setSelectedId((current) => ticketData.some((ticket) => ticket.ticket_id === current)
        ? current
        : ticketData[0]?.ticket_id || null);
      try {
        const member = await apiRequest<StaffMember>("/api/v1/staff/me", {
          headers: authHeaders(activeToken),
        }, 8_000);
        setProfile(member);
      } catch {
        // A legacy development token may not have an Admin-created profile.
        setProfile(null);
      }
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể tải dashboard.");
      if (caught instanceof ApiError && [401, 503].includes(caught.status)) setLoggedIn(false);
    } finally {
      setLoading(false);
    }
  }, [sort, token]);

  useEffect(() => {
    if (!loggedIn || !token) return;
    const timer = window.setInterval(() => void loadDashboard(token), POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [loadDashboard, loggedIn, token]);

  useEffect(() => {
    if (!loggedIn || !token) return;
    const refresh = window.setTimeout(() => void loadDashboard(token), 0);
    return () => window.clearTimeout(refresh);
  }, [loadDashboard, loggedIn, token]);

  async function login(event: FormEvent) {
    event.preventDefault();
    if (!token.trim() || !staffId.trim()) {
      setError("Vui lòng nhập mã cán bộ và staff token.");
      return;
    }
    window.sessionStorage.setItem(STAFF_TOKEN_KEY, token.trim());
    window.sessionStorage.setItem(STAFF_ID_KEY, staffId.trim());
    await loadDashboard(token.trim());
  }

  function logout() {
    window.sessionStorage.removeItem(STAFF_TOKEN_KEY);
    window.sessionStorage.removeItem(STAFF_ID_KEY);
    setLoggedIn(false);
    setToken("");
    setTickets([]);
    setMetrics(null);
    setSelectedId(null);
    setError("");
  }

  function updateTicket(updated: StaffTicket) {
    setTickets((current) => current.map((ticket) => ticket.ticket_id === updated.ticket_id ? updated : ticket));
  }

  async function action(path: string, body: object): Promise<StaffTicket | null> {
    setActionLoading(true);
    setError("");
    try {
      const updated = await apiRequest<StaffTicket>(path, {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify(body),
      });
      updateTicket(updated);
      return updated;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Thao tác không thành công.");
      return null;
    } finally {
      setActionLoading(false);
    }
  }

  async function setMyAvailability(availability: StaffAvailability) {
    setActionLoading(true);
    try {
      const member = await apiRequest<StaffMember>("/api/v1/staff/me/availability", {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify({ availability }),
      });
      setProfile(member);
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể cập nhật trạng thái làm việc.");
    } finally {
      setActionLoading(false);
    }
  }

  async function changeStatus(nextStatus: TicketStatus) {
    if (!selected) return;
    await action(`/api/v1/staff/tickets/${encodeURIComponent(selected.ticket_id)}/status`, {
      staff_id: staffId,
      status: nextStatus,
    });
  }

  async function updateClassification(category: TicketCategory, priority: TicketPriority) {
    if (!selected) return;
    await action(`/api/v1/staff/tickets/${encodeURIComponent(selected.ticket_id)}/classification`, {
      staff_id: staffId,
      category,
      priority,
    });
  }

  async function addNote() {
    if (!selected || !note.trim()) return;
    const updated = await action(`/api/v1/staff/tickets/${encodeURIComponent(selected.ticket_id)}/notes`, {
      staff_id: staffId,
      note: note.trim(),
    });
    if (updated) setNote("");
  }

  async function regenerateAi() {
    if (!selected) return;
    await action(`/api/v1/staff/tickets/${encodeURIComponent(selected.ticket_id)}/regenerate-ai`, {
      staff_id: staffId,
    });
  }

  async function sendReply() {
    if (!selected || !reply.trim()) return;
    const updated = await action(`/api/v1/staff/tickets/${encodeURIComponent(selected.ticket_id)}/reply`, {
      staff_id: staffId,
      reply: reply.trim(),
    });
    if (updated) setReply("");
  }

  async function resolveTicket() {
    if (!selected || !resolutionSummary.trim()) {
      setError("Vui lòng nhập tóm tắt kết quả trước khi hoàn tất.");
      return;
    }
    const updated = await action(`/api/v1/staff/tickets/${encodeURIComponent(selected.ticket_id)}/resolve`, {
      staff_id: staffId,
      resolution_summary: resolutionSummary.trim(),
      resolution_type: resolutionType,
      knowledge_gap: knowledgeGap,
      knowledge_gap_description: knowledgeGapDescription.trim() || null,
    });
    if (updated) {
      setResolutionSummary("");
      setKnowledgeGap(false);
      setKnowledgeGapDescription("");
    }
  }

  if (!loggedIn) {
    return (
      <section className="staff-login-card">
        <div className="staff-login-visual">
          <span><ShieldIcon /></span>
          <div><strong>Khu vực được bảo vệ</strong><p>Chỉ cán bộ có token hợp lệ mới xem được hội thoại và dữ liệu handover.</p></div>
        </div>
        <form className="staff-login-form" onSubmit={login}>
          <span className="section-kicker"><StaffIcon /> Xác thực cán bộ</span>
          <h2>Đăng nhập Staff Dashboard</h2>
          <p>Token chỉ được lưu trong tab hiện tại và gửi qua HTTPS tới backend.</p>
          <label className="field-label" htmlFor="staff-id">Mã cán bộ</label>
          <input id="staff-id" maxLength={100} onChange={(event) => setStaffId(event.target.value)} placeholder="Ví dụ: admissions-01" value={staffId} />
          <label className="field-label" htmlFor="staff-token">Staff API token</label>
          <input id="staff-token" onChange={(event) => setToken(event.target.value)} placeholder="Token được cấu hình ở backend" type="password" value={token} />
          {error ? <p className="form-error" role="alert">{error}</p> : null}
          <button className="button button-primary full-width" disabled={loading} type="submit">{loading ? "Đang xác thực…" : "Vào dashboard"}</button>
          <small>Production nên thay token tĩnh bằng SSO/JWT và RBAC.</small>
        </form>
      </section>
    );
  }

  const canEdit = selected?.assigned_to === staffId && !["resolved", "closed"].includes(selected.status);
  const myOpenTicketCount = tickets.filter((ticket) => (
    ticket.assigned_to === staffId && !["resolved", "closed"].includes(ticket.status)
  )).length;

  return (
    <div className="staff-dashboard hitl-dashboard">
      <div className="staff-topbar">
        <div><span className="eyebrow">Human-in-the-loop workspace</span><strong>{profile?.display_name || staffId}</strong>{profile ? <label className="staff-availability">Trạng thái<select disabled={actionLoading} onChange={(event) => void setMyAvailability(event.target.value as StaffAvailability)} value={profile.availability}><option value="available">Rảnh · nhận ticket</option><option value="busy">Bận · tạm dừng nhận</option><option value="offline">Ngoại tuyến</option></select></label> : null}</div>
        <div>
          <button className="text-button" disabled={loading} onClick={() => void loadDashboard()} type="button"><RefreshIcon className={loading ? "spin" : ""} /> Làm mới</button>
          <button className="text-button danger" onClick={logout} type="button">Đăng xuất</button>
        </div>
      </div>

      <div className="staff-metrics hitl-metrics">
        <article><span className="metric-icon waiting"><ClockIcon /></span><div><strong>{metrics?.open_count ?? 0}</strong><span>Đang mở</span></div></article>
        <article><span className="metric-icon progress"><StaffIcon /></span><div><strong>{myOpenTicketCount}</strong><span>Ticket của tôi</span></div></article>
        <article><span className="metric-icon urgent"><ClockIcon /></span><div><strong>{metrics?.overdue_count ?? 0}</strong><span>Quá SLA</span></div></article>
        <article><span className="metric-icon resolved"><CheckIcon /></span><div><strong>{metrics?.resolved_today ?? 0}</strong><span>Hoàn tất hôm nay</span></div></article>
        <article><span className="metric-icon neutral"><RefreshIcon /></span><div><strong>{compactTime(metrics?.average_first_response_minutes)}</strong><span>Phản hồi đầu TB</span></div></article>
      </div>

      {error ? <div className="connection-error" role="alert"><span>{error}</span><button onClick={() => setError("")} type="button">Đóng</button></div> : null}

      <section className="hitl-filterbar" aria-label="Bộ lọc ticket">
        <input aria-label="Tìm ticket" onChange={(event) => setSearch(event.target.value)} placeholder="Tìm mã ticket, câu hỏi, email…" value={search} />
        <select aria-label="Trạng thái" onChange={(event) => setStatusFilter(event.target.value as typeof statusFilter)} value={statusFilter}>
          <option value="all">Tất cả trạng thái</option>{statuses.map((value) => <option key={value} value={value}>{statusLabels[value]}</option>)}
        </select>
        <select aria-label="Danh mục" onChange={(event) => setCategoryFilter(event.target.value as typeof categoryFilter)} value={categoryFilter}>
          <option value="all">Tất cả danh mục</option>{categories.map((value) => <option key={value} value={value}>{categoryLabels[value]}</option>)}
        </select>
        <select aria-label="Ưu tiên" onChange={(event) => setPriorityFilter(event.target.value as typeof priorityFilter)} value={priorityFilter}>
          <option value="all">Mọi ưu tiên</option>{priorities.map((value) => <option key={value} value={value}>{priorityLabels[value]}</option>)}
        </select>
        <select aria-label="Sắp xếp" onChange={(event) => setSort(event.target.value as typeof sort)} value={sort}>
          <option value="priority">Ưu tiên cao trước</option><option value="oldest">Cũ nhất trước</option><option value="newest">Mới nhất trước</option>
        </select>
      </section>

      <div className="staff-workspace hitl-workspace">
        <section className="ticket-queue">
          <div className="queue-header"><div><span className="eyebrow">Queue</span><h2>Yêu cầu cần xử lý</h2></div><span>{visibleTickets.length} ticket</span></div>
          <div className="queue-list hitl-queue-list">
            {loading && !tickets.length ? <div className="queue-loading">Đang tải hàng chờ…</div> : null}
            {!loading && !visibleTickets.length ? <div className="empty-state"><CheckIcon /><h3>Không có ticket</h3><p>Thử thay đổi bộ lọc hiện tại.</p></div> : null}
            {visibleTickets.map((ticket) => (
              <button className={selectedId === ticket.ticket_id ? "queue-item selected" : "queue-item"} key={ticket.ticket_id} onClick={() => { setSelectedId(ticket.ticket_id); setReply(""); setNote(""); setError(""); }} type="button">
                <div><strong>{ticket.ticket_id}</strong><span className={`priority-badge priority-${ticket.priority}`}>{priorityLabels[ticket.priority]}</span></div>
                <p>{ticket.question}</p>
                <div className="queue-badges"><span className={`ticket-badge ticket-${ticket.status}`}>{statusLabels[ticket.status]}</span><span>{categoryLabels[ticket.category]}</span><span className={`sla-badge sla-${ticket.sla_state}`}>{ticket.sla_state === "overdue" ? "Quá SLA" : ticket.sla_state === "due_soon" ? "Sắp quá SLA" : "Trong SLA"}</span></div>
                <small>{formatDateTime(ticket.created_at)} · {ticket.assigned_to || "Chưa phân công"}</small>
              </button>
            ))}
          </div>
        </section>

        <section className="ticket-detail hitl-detail">
          {!selected ? <div className="detail-placeholder"><StaffIcon /><h3>Chọn một ticket</h3><p>Toàn bộ ngữ cảnh xử lý sẽ hiển thị tại đây.</p></div> : (
            <>
              <div className="detail-heading">
                <div><span className="eyebrow">{selected.ticket_id}</span><h2>{statusLabels[selected.status]}</h2></div>
                <div className="detail-badges"><span className={`priority-badge priority-${selected.priority}`}>{priorityLabels[selected.priority]}</span><span className={`sla-badge sla-${selected.sla_state}`}>{selected.sla_state === "overdue" ? "Quá SLA" : `SLA ${formatDateTime(selected.sla_deadline)}`}</span></div>
              </div>

              <div className="hitl-detail-body">
                <section className="hitl-panel triage-panel">
                  <div className="panel-heading"><div><span className="eyebrow">AI triage</span><h3>Tóm tắt xử lý</h3></div><button className="text-button" disabled={actionLoading} onClick={() => void regenerateAi()} type="button"><RefreshIcon /> Tạo lại</button></div>
                  <p>{selected.ai_summary || "Chưa có tóm tắt."}</p>
                  <div className="triage-grid">
                    <label>Danh mục<select disabled={actionLoading || ["resolved", "closed"].includes(selected.status)} onChange={(event) => void updateClassification(event.target.value as TicketCategory, selected.priority)} value={selected.category}>{categories.map((value) => <option key={value} value={value}>{categoryLabels[value]}</option>)}</select></label>
                    <label>Ưu tiên<select disabled={actionLoading || ["resolved", "closed"].includes(selected.status)} onChange={(event) => void updateClassification(selected.category, event.target.value as TicketPriority)} value={selected.priority}>{priorities.map((value) => <option key={value} value={value}>{priorityLabels[value]}</option>)}</select></label>
                    <dl><dt>Lý do chuyển</dt><dd>{selected.escalation_reason}</dd></dl>
                    <dl><dt>AI confidence</dt><dd>{selected.ai_confidence == null ? "Không có" : `${Math.round(selected.ai_confidence * 100)}%`}</dd></dl>
                  </div>
                </section>

                <section className="hitl-panel assignment-panel">
                  <div className="panel-heading"><div><span className="eyebrow">Ownership</span><h3>Phân công</h3></div><span>{selected.assigned_to || "Chưa có người nhận"}</span></div>
                  <p className="muted-copy">{selected.assigned_to === staffId ? `Ticket do hệ thống phân công cho bạn${selected.assigned_department ? ` · ${selected.assigned_department}` : ""}.` : selected.assigned_to ? `Ticket hiện do ${selected.assigned_to} phụ trách. Admin có thể điều phối lại khi cần.` : "Ticket đang chờ Admin phân công cho cán bộ phù hợp."}</p>
                  {canEdit ? <div className="status-actions"><button disabled={actionLoading} onClick={() => void changeStatus("in_progress")} type="button">Đang xử lý</button><button disabled={actionLoading} onClick={() => void changeStatus("waiting_for_user")} type="button">Chờ ứng viên</button></div> : null}
                </section>

                <section className="hitl-panel conversation-panel">
                  <div className="panel-heading"><div><span className="eyebrow">Context</span><h3>Toàn bộ hội thoại</h3></div><span>{selected.messages.length} tin nhắn</span></div>
                  <div className="staff-conversation">{selected.messages.map((message) => <article className={`staff-message staff-message-${message.role}`} key={message.message_id}><div><strong>{message.role === "user" ? "Ứng viên" : message.role === "staff" ? message.author_id || "Cán bộ" : "VinUni Guide"}</strong><small>{formatDateTime(message.created_at)}</small></div><p>{message.content}</p>{message.role === "assistant" && message.confidence != null ? <span>Grounded: {message.grounded ? "Có" : "Không"} · Confidence {Math.round(message.confidence * 100)}%</span> : null}</article>)}</div>
                </section>

                <section className="hitl-panel evidence-panel">
                  <div className="panel-heading"><div><span className="eyebrow">Evidence</span><h3>Nguồn AI đã sử dụng</h3></div><span>{selected.evidence.length} nguồn</span></div>
                  {!selected.evidence.length ? <p className="muted-copy">Không có nguồn đủ chắc chắn được chuyển kèm. Cán bộ cần kiểm tra trước khi kết luận.</p> : <div className="staff-evidence-list">{selected.evidence.map((item) => <a href={item.url} key={item.evidence_id} rel="noreferrer" target="_blank"><span><strong>{item.title}</strong><small>{item.source_id}{item.source_category ? ` · ${item.source_category}` : ""}</small></span><ExternalIcon /></a>)}</div>}
                </section>

                <section className="hitl-panel reply-panel">
                  <div className="panel-heading"><div><span className="eyebrow">Human response</span><h3>Soạn phản hồi</h3></div><span>{selected.user_email ? `Email: ${selected.user_email}` : "Không có email"}</span></div>
                  <div className="suggested-reply"><strong>Gợi ý của AI · bắt buộc cán bộ kiểm tra</strong><p>{selected.suggested_reply || "Chưa có gợi ý."}</p><button className="text-button" disabled={!canEdit} onClick={() => setReply(selected.suggested_reply || "")} type="button">Dùng làm bản nháp</button></div>
                  {!canEdit ? <div className="reply-locked" role="status"><div><strong>Ticket chưa thuộc quyền xử lý của bạn</strong><p>{selected.assigned_to ? `Ticket hiện do ${selected.assigned_to} phụ trách. Hãy liên hệ Admin nếu cần điều phối lại.` : "Admin sẽ phân công ticket cho đúng nhóm chuyên môn và cán bộ đang rảnh."}</p></div></div> : null}
                  <textarea disabled={!canEdit} maxLength={5000} onChange={(event) => setReply(event.target.value)} placeholder={canEdit ? "Nhập phản hồi đã được kiểm tra…" : "Nhận/phân công ticket cho bạn để trả lời"} rows={6} value={reply} />
                  <div className="editor-actions"><span>{reply.length}/5000</span><button className="button button-primary" disabled={actionLoading || !canEdit || !reply.trim()} onClick={() => void sendReply()} type="button"><SendIcon /> Gửi phản hồi</button></div>
                  {selected.email_delivery_status ? <p className={`delivery-status delivery-${selected.email_delivery_status}`}>Trạng thái email: {selected.email_delivery_status}</p> : null}
                </section>

                <section className="hitl-panel notes-panel">
                  <div className="panel-heading"><div><span className="eyebrow">Private</span><h3>Ghi chú nội bộ</h3></div><span>Không hiển thị cho ứng viên</span></div>
                  <div className="inline-form"><input maxLength={5000} onChange={(event) => setNote(event.target.value)} placeholder="Thêm ghi chú cho nhóm…" value={note} /><button className="button button-secondary" disabled={actionLoading || !note.trim()} onClick={() => void addNote()} type="button">Thêm</button></div>
                  <div className="note-list">{selected.notes.map((item) => <article key={item.note_id}><div><strong>{item.author_id}</strong><small>{formatDateTime(item.created_at)}</small></div><p>{item.note}</p></article>)}</div>
                </section>

                {selected.status === "waiting_for_user" && selected.assigned_to === staffId ? <section className="hitl-panel resolve-panel"><div className="panel-heading"><div><span className="eyebrow">Resolution</span><h3>Hoàn tất ticket</h3></div></div><textarea maxLength={5000} onChange={(event) => setResolutionSummary(event.target.value)} placeholder="Tóm tắt kết quả đã xử lý…" rows={3} value={resolutionSummary} /><select onChange={(event) => setResolutionType(event.target.value)} value={resolutionType}><option value="answered">Đã trả lời</option><option value="policy_clarified">Đã làm rõ chính sách</option><option value="referred">Đã chuyển đơn vị phụ trách</option><option value="duplicate">Trùng yêu cầu</option></select><label className="consent-row"><input checked={knowledgeGap} onChange={(event) => setKnowledgeGap(event.target.checked)} type="checkbox" /><span>Đây là khoảng trống tri thức cần bổ sung vào knowledge base</span></label>{knowledgeGap ? <textarea maxLength={3000} onChange={(event) => setKnowledgeGapDescription(event.target.value)} placeholder="Mô tả dữ liệu hoặc tài liệu còn thiếu…" rows={2} value={knowledgeGapDescription} /> : null}<button className="button button-primary" disabled={actionLoading || !resolutionSummary.trim()} onClick={() => void resolveTicket()} type="button"><CheckIcon /> Xác nhận hoàn tất</button></section> : null}

                {selected.status === "resolved" ? <section className="hitl-panel"><p><strong>Kết quả:</strong> {selected.resolution_summary}</p><button className="button button-secondary" disabled={actionLoading} onClick={() => void action(`/api/v1/staff/tickets/${encodeURIComponent(selected.ticket_id)}/close`, { staff_id: staffId })} type="button">Đóng ticket</button></section> : null}

                <details className="hitl-panel audit-panel"><summary>Nhật ký hoạt động ({selected.activities.length})</summary><ol>{selected.activities.map((item) => <li key={item.activity_id}><span>{formatDateTime(item.created_at)}</span><strong>{item.actor_id}</strong><span>{item.action}{item.detail ? ` · ${item.detail}` : ""}</span></li>)}</ol></details>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
