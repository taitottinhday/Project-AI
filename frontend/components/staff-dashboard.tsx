"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { CheckIcon, ClockIcon, RefreshIcon, SendIcon, ShieldIcon, StaffIcon } from "@/components/icons";
import {
  ApiError,
  apiRequest,
  formatDateTime,
  type AnalyticsSummary,
  type Ticket,
  type TicketStatus,
} from "@/lib/api";

const STAFF_TOKEN_KEY = "vinuni-staff-token";
const STAFF_ID_KEY = "vinuni-staff-id";
const STAFF_QUEUE_POLL_INTERVAL_MS = 3_000;
const STAFF_ANALYTICS_POLL_INTERVAL_MS = 30_000;

const statusLabels: Record<TicketStatus, string> = {
  waiting: "Đang chờ",
  in_progress: "Đang xử lý",
  resolved: "Đã xử lý",
};

function percent(value: number | null | undefined): string {
  return value == null ? "Chưa có mẫu" : `${Math.round(value * 100)}%`;
}

function authHeaders(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` };
}

export function StaffDashboard() {
  const [token, setToken] = useState("");
  const [staffId, setStaffId] = useState("");
  const [loggedIn, setLoggedIn] = useState(false);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | TicketStatus>("all");
  const [reply, setReply] = useState("");
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState("");

  const selected = useMemo(
    () => tickets.find((ticket) => ticket.ticket_id === selectedId) || null,
    [selectedId, tickets],
  );
  const visibleTickets = useMemo(
    () => filter === "all" ? tickets : tickets.filter((ticket) => ticket.status === filter),
    [filter, tickets],
  );

  useEffect(() => {
    const hydration = window.setTimeout(() => {
      setToken(window.sessionStorage.getItem(STAFF_TOKEN_KEY) || "");
      setStaffId(window.sessionStorage.getItem(STAFF_ID_KEY) || "");
    }, 0);
    return () => window.clearTimeout(hydration);
  }, []);

  const loadTickets = useCallback(async (activeToken = token) => {
    if (!activeToken) return;
    setLoading(true);
    setError("");
    try {
      // Ticket delivery is critical. Do not make it depend on the slower
      // metrics query completing successfully.
      const data = await apiRequest<Ticket[]>("/api/v1/staff/tickets", {
        headers: authHeaders(activeToken),
      }, 10_000);
      setTickets(data);
      setLoggedIn(true);
      setSelectedId((currentSelected) => {
        if (!data.length) return null;
        return data.some((ticket) => ticket.ticket_id === currentSelected)
          ? currentSelected
          : data[0].ticket_id;
      });
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "Không thể tải hàng chờ.";
      setError(message);
      if (caught instanceof ApiError && [401, 503].includes(caught.status)) setLoggedIn(false);
    } finally {
      setLoading(false);
    }
  }, [token]);

  const loadAnalytics = useCallback(async (activeToken = token) => {
    if (!activeToken) return;
    try {
      const data = await apiRequest<AnalyticsSummary>("/api/v1/staff/analytics?days=30", {
        headers: authHeaders(activeToken),
      }, 10_000);
      setAnalytics(data);
    } catch {
      // Metrics are non-critical; the ticket queue keeps refreshing.
    }
  }, [token]);

  useEffect(() => {
    if (!loggedIn || !token) return;
    const interval = window.setInterval(() => void loadTickets(token), STAFF_QUEUE_POLL_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [loadTickets, loggedIn, token]);

  useEffect(() => {
    if (!loggedIn || !token) return;
    const initialRefresh = window.setTimeout(() => void loadAnalytics(token), 0);
    const interval = window.setInterval(() => void loadAnalytics(token), STAFF_ANALYTICS_POLL_INTERVAL_MS);
    return () => {
      window.clearTimeout(initialRefresh);
      window.clearInterval(interval);
    };
  }, [loadAnalytics, loggedIn, token]);

  async function login(event: FormEvent) {
    event.preventDefault();
    if (!token.trim() || !staffId.trim()) {
      setError("Vui lòng nhập mã cán bộ và staff token.");
      return;
    }
    window.sessionStorage.setItem(STAFF_TOKEN_KEY, token.trim());
    window.sessionStorage.setItem(STAFF_ID_KEY, staffId.trim());
    await loadTickets(token.trim());
  }

  function logout() {
    window.sessionStorage.removeItem(STAFF_TOKEN_KEY);
    window.sessionStorage.removeItem(STAFF_ID_KEY);
    setToken("");
    setTickets([]);
    setAnalytics(null);
    setSelectedId(null);
    setLoggedIn(false);
    setError("");
  }

  function updateTicket(updated: Ticket) {
    setTickets((current) => current.map((ticket) => ticket.ticket_id === updated.ticket_id ? updated : ticket));
  }

  async function ticketAction(path: string, body: object) {
    setActionLoading(true);
    setError("");
    try {
      const updated = await apiRequest<Ticket>(path, {
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

  async function claim() {
    if (!selected) return;
    await ticketAction(`/api/v1/staff/tickets/${encodeURIComponent(selected.ticket_id)}/claim`, {
      staff_id: staffId,
    });
  }

  async function sendReply() {
    if (!selected || !reply.trim()) {
      setError("Vui lòng nhập phản hồi trước khi gửi.");
      return;
    }
    const updated = await ticketAction(`/api/v1/staff/tickets/${encodeURIComponent(selected.ticket_id)}/reply`, {
      staff_id: staffId,
      reply: reply.trim(),
    });
    if (updated) setReply("");
  }

  function changeFilter(next: "all" | TicketStatus) {
    setFilter(next);
    const nextVisible = next === "all" ? tickets : tickets.filter((ticket) => ticket.status === next);
    if (!nextVisible.some((ticket) => ticket.ticket_id === selectedId)) {
      setSelectedId(nextVisible[0]?.ticket_id || null);
    }
  }

  if (!loggedIn) {
    return (
      <section className="staff-login-card">
        <div className="staff-login-visual">
          <span><ShieldIcon /></span>
          <div><strong>Khu vực được bảo vệ</strong><p>Chỉ cán bộ có staff token hợp lệ mới xem được hàng chờ handover.</p></div>
        </div>
        <form className="staff-login-form" onSubmit={login}>
          <span className="section-kicker"><StaffIcon /> Xác thực cán bộ</span>
          <h2>Đăng nhập hàng chờ</h2>
          <p>Trong MVP, mã truy cập được kiểm tra trực tiếp bởi FastAPI và chỉ lưu trong tab hiện tại.</p>
          <label className="field-label" htmlFor="staff-id">Mã cán bộ</label>
          <input id="staff-id" maxLength={100} onChange={(event) => setStaffId(event.target.value)} placeholder="Ví dụ: admissions-01" value={staffId} />
          <label className="field-label" htmlFor="staff-token">Staff API token</label>
          <input id="staff-token" onChange={(event) => setToken(event.target.value)} placeholder="Token được cấu hình ở backend" type="password" value={token} />
          {error ? <p className="form-error" role="alert">{error}</p> : null}
          <button className="button button-primary full-width" disabled={loading} type="submit">
            {loading ? "Đang xác thực…" : "Vào hàng chờ"}
          </button>
          <small>Production cần thay token dùng chung bằng SSO/JWT và phân quyền theo vai trò.</small>
        </form>
      </section>
    );
  }

  const counts = {
    waiting: tickets.filter((ticket) => ticket.status === "waiting").length,
    in_progress: tickets.filter((ticket) => ticket.status === "in_progress").length,
    resolved: tickets.filter((ticket) => ticket.status === "resolved").length,
  };

  return (
    <div className="staff-dashboard">
      <div className="staff-topbar">
        <div><span className="eyebrow">Đã xác thực</span><strong>{staffId}</strong></div>
        <div><button className="text-button" disabled={loading} onClick={() => void loadTickets()} type="button"><RefreshIcon className={loading ? "spin" : ""} /> Làm mới</button><button className="text-button danger" onClick={logout} type="button">Đăng xuất</button></div>
      </div>

      <div className="staff-metrics">
        <article><span className="metric-icon waiting"><ClockIcon /></span><div><strong>{counts.waiting}</strong><span>Đang chờ</span></div></article>
        <article><span className="metric-icon progress"><StaffIcon /></span><div><strong>{counts.in_progress}</strong><span>Đang xử lý</span></div></article>
        <article><span className="metric-icon resolved"><CheckIcon /></span><div><strong>{counts.resolved}</strong><span>Đã xử lý</span></div></article>
      </div>

      <section className="analytics-panel">
        <div className="analytics-heading">
          <div><span className="eyebrow">30 ngày gần nhất</span><h2>Chất lượng và tương tác</h2></div>
          <small>Không lưu câu hỏi hoặc câu trả lời thô trong bảng metric.</small>
        </div>
        <div className="analytics-grid">
          <article><span>Lượt hỏi</span><strong>{analytics?.total_interactions ?? 0}</strong><small>{analytics?.unique_sessions ?? 0} phiên ẩn danh</small></article>
          <article><span>Tỷ lệ trả lời</span><strong>{percent(analytics?.answer_rate)}</strong><small>{analytics?.answered ?? 0} lượt có căn cứ</small></article>
          <article><span>Grounded</span><strong>{percent(analytics?.grounded_answer_compliance)}</strong><small>trên các lượt đã trả lời</small></article>
          <article><span>Handover</span><strong>{percent(analytics?.handover_rate)}</strong><small>{analytics?.handover_count ?? 0} lượt chuyển người</small></article>
          <article><span>Hữu ích</span><strong>{percent(analytics?.helpful_rate)}</strong><small>{analytics?.feedback_count ?? 0} phản hồi người dùng</small></article>
          <article><span>Cache hit</span><strong>{percent(analytics?.cache_hit_rate)}</strong><small>{analytics?.cache_hits ?? 0} lượt tái sử dụng an toàn</small></article>
          <article><span>Độ trễ TB</span><strong>{Math.round(analytics?.average_latency_ms ?? 0)} ms</strong><small>đo tại API</small></article>
        </div>
      </section>

      {error ? <div className="connection-error" role="alert"><span>{error}</span><button onClick={() => setError("")} type="button">Đóng</button></div> : null}

      <div className="staff-workspace">
        <section className="ticket-queue">
          <div className="queue-header"><div><span className="eyebrow">Handover</span><h2>Hàng chờ tuyển sinh</h2></div><span>{visibleTickets.length} yêu cầu</span></div>
          <div className="filter-tabs">
            {(["all", "waiting", "in_progress", "resolved"] as const).map((value) => (
              <button className={filter === value ? "active" : ""} key={value} onClick={() => changeFilter(value)} type="button">
                {value === "all" ? "Tất cả" : statusLabels[value]}
              </button>
            ))}
          </div>
          <div className="queue-list">
            {loading ? <div className="queue-loading"><i/><i/><i/> Đang tải hàng chờ…</div> : null}
            {!loading && !visibleTickets.length ? <div className="empty-state"><CheckIcon /><h3>Hàng chờ trống</h3><p>Không có yêu cầu phù hợp bộ lọc hiện tại.</p></div> : null}
            {visibleTickets.map((ticket) => (
              <button className={selectedId === ticket.ticket_id ? "queue-item selected" : "queue-item"} key={ticket.ticket_id} onClick={() => { setSelectedId(ticket.ticket_id); setReply(""); setError(""); }} type="button">
                <div><strong>{ticket.ticket_id}</strong><span className={`ticket-badge ticket-${ticket.status === "in_progress" ? "progress" : ticket.status}`}>{statusLabels[ticket.status]}</span></div>
                <p>{ticket.question}</p>
                <small>{formatDateTime(ticket.created_at)}{ticket.assigned_to ? ` · ${ticket.assigned_to}` : ""}</small>
              </button>
            ))}
          </div>
        </section>

        <section className="ticket-detail">
          {!selected ? (
            <div className="detail-placeholder"><StaffIcon /><h3>Chọn một yêu cầu</h3><p>Chi tiết và thao tác xử lý sẽ hiển thị tại đây.</p></div>
          ) : (
            <>
              <div className="detail-heading">
                <div><span className="eyebrow">{selected.ticket_id}</span><h2>Chi tiết yêu cầu</h2></div>
                <span className={`ticket-badge large ticket-${selected.status === "in_progress" ? "progress" : selected.status}`}>{statusLabels[selected.status]}</span>
              </div>
              <dl className="ticket-metadata">
                <div><dt>Lý do chuyển</dt><dd>{selected.reason}</dd></div>
                <div><dt>Tạo lúc</dt><dd>{formatDateTime(selected.created_at)}</dd></div>
                <div><dt>Người xử lý</dt><dd>{selected.assigned_to || "Chưa có"}</dd></div>
              </dl>
              <div className="question-card"><span>Nội dung ứng viên đồng ý chia sẻ</span><p>{selected.question}</p></div>

              {selected.status === "waiting" ? (
                <button className="button button-primary" disabled={actionLoading} onClick={() => void claim()} type="button"><StaffIcon /> Nhận xử lý</button>
              ) : null}

              {selected.status === "in_progress" && selected.assigned_to === staffId ? (
                <div className="reply-editor">
                  <label className="field-label" htmlFor="staff-reply">Phản hồi cho ứng viên</label>
                  <textarea id="staff-reply" maxLength={5000} onChange={(event) => setReply(event.target.value)} placeholder="Chỉ sử dụng thông tin đã được xác minh…" rows={6} value={reply} />
                  <div><span>{reply.length}/5000</span><button className="button button-secondary" disabled={actionLoading || !reply.trim()} onClick={() => void sendReply()} type="button"><SendIcon /> Gửi phản hồi</button></div>
                </div>
              ) : null}

              {selected.staff_reply ? (
                <div className="existing-reply"><span><CheckIcon /> Phản hồi đã gửi · Yêu cầu đã hoàn tất</span><p>{selected.staff_reply}</p></div>
              ) : null}

              {selected.status === "in_progress" && selected.assigned_to !== staffId ? (
                <p className="ownership-note"><ShieldIcon /> Ticket đang do <strong>{selected.assigned_to}</strong> xử lý; bạn không thể chỉnh sửa.</p>
              ) : null}
            </>
          )}
        </section>
      </div>
    </div>
  );
}
