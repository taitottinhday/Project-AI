"use client";

import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";

import {
  CheckIcon,
  ClockIcon,
  CloseIcon,
  CopyIcon,
  ExternalIcon,
  RefreshIcon,
  SendIcon,
  ShieldIcon,
  SourceIcon,
  SparkIcon,
  StaffIcon,
} from "@/components/icons";
import { KnowledgeStatus } from "@/components/knowledge-status";
import {
  apiRequest,
  formatDateTime,
  type AnswerStatus,
  type ChatResponse,
  type Citation,
  type Ticket,
  type TicketStatus,
} from "@/lib/api";

type ConversationMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  result?: ChatResponse;
};

const SESSION_KEY = "vinuni-guide-session";
const MESSAGE_KEY = "vinuni-guide-messages";
const TICKET_KEY = "vinuni-guide-tickets";

const welcomeMessage: ConversationMessage = {
  id: "welcome",
  role: "assistant",
  text: "Xin chào! Mình có thể giúp bạn tra cứu ngành học, học phí, học bổng, hồ sơ và quy định tại VinUni. Bạn không cần cung cấp thông tin cá nhân để bắt đầu.",
};

const suggestions = [
  "VinUni có những ngành đại học nào?",
  "Học phí năm 2026–2027 là bao nhiêu?",
  "VinUni có những học bổng nào?",
  "Quy trình nộp hồ sơ như thế nào?",
];

const statusMeta: Record<AnswerStatus, { label: string; className: string }> = {
  answered: { label: "Đã kiểm chứng nguồn", className: "status-grounded" },
  needs_clarification: { label: "Cần làm rõ", className: "status-clarify" },
  handover_suggested: { label: "Nên chuyển cán bộ", className: "status-handover" },
  insufficient_evidence: { label: "Chưa đủ căn cứ", className: "status-insufficient" },
};

const ticketMeta: Record<TicketStatus, { label: string; className: string }> = {
  waiting: { label: "Đang chờ", className: "ticket-waiting" },
  in_progress: { label: "Đang xử lý", className: "ticket-progress" },
  resolved: { label: "Đã phản hồi", className: "ticket-resolved" },
};

function makeId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random()}`;
}

function CitationCard({ citation, index }: { citation: Citation; index: number }) {
  return (
    <a className="citation-card" href={citation.url} rel="noreferrer" target="_blank">
      <span className="citation-index">{index + 1}</span>
      <span className="citation-body">
        <strong>{citation.title}</strong>
        <small>
          {[citation.section, citation.published_or_updated, citation.version]
            .filter(Boolean)
            .join(" · ") || citation.source_id}
        </small>
        {citation.warning ? <em>{citation.warning}</em> : null}
      </span>
      <ExternalIcon />
    </a>
  );
}

function AssistantMessage({ message, onHandover }: { message: ConversationMessage; onHandover: () => void }) {
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState<"helpful" | "unhelpful" | null>(null);
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const [feedbackError, setFeedbackError] = useState("");
  const result = message.result;

  async function copyAnswer() {
    await navigator.clipboard.writeText(message.text);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1_500);
  }

  async function submitFeedback(rating: "helpful" | "unhelpful") {
    if (!result || feedbackLoading || feedback) return;
    setFeedbackLoading(true);
    setFeedbackError("");
    try {
      await apiRequest<{ recorded: boolean }>("/api/v1/feedback", {
        method: "POST",
        body: JSON.stringify({
          request_id: result.request_id,
          session_id: result.session_id,
          rating,
          reason: rating === "unhelpful" ? "other" : null,
        }),
      }, 8_000);
      setFeedback(rating);
    } catch (caught) {
      setFeedbackError(caught instanceof Error ? caught.message : "Chưa thể ghi nhận phản hồi.");
    } finally {
      setFeedbackLoading(false);
    }
  }

  return (
    <div className="message-row assistant-row">
      <span className="message-avatar"><SparkIcon /></span>
      <div className="message-stack">
        <div className="message-meta">
          <strong>VinUni Guide</strong>
          {result ? (
            <span className={`answer-status ${statusMeta[result.status].className}`}>
              {result.grounded ? <ShieldIcon /> : <ClockIcon />}
              {statusMeta[result.status].label}
            </span>
          ) : null}
        </div>
        <div className="message-bubble assistant-bubble">
          <p className="answer-text">{message.text}</p>

          {result?.warnings.length ? (
            <div className="warning-box">
              <strong>Lưu ý khi sử dụng thông tin</strong>
              {result.warnings.map((warning) => <p key={warning}>{warning}</p>)}
            </div>
          ) : null}

          {result?.citations.length ? (
            <details className="sources-panel" open>
              <summary><SourceIcon /> Nguồn kiểm chứng ({result.citations.length})</summary>
              <div className="citation-list">
                {result.citations.map((citation, index) => (
                  <CitationCard citation={citation} index={index} key={`${citation.source_id}-${index}`} />
                ))}
              </div>
            </details>
          ) : null}

          {result ? (
            <>
              <div className="answer-footer">
                <button className="text-button" onClick={copyAnswer} type="button">
                  {copied ? <CheckIcon /> : <CopyIcon />}{copied ? "Đã sao chép" : "Sao chép"}
                </button>
                {result.grounded ? (
                  <span
                    className="retrieval-score"
                    title="Đây là điểm khớp của bước truy xuất, không phải xác suất câu trả lời đúng."
                  >
                    Khớp nguồn {Math.round(result.confidence * 100)}%
                  </span>
                ) : null}
              </div>
              <div className="answer-feedback" aria-label="Đánh giá câu trả lời">
                <span>{feedback ? "Đã ghi nhận phản hồi" : "Câu trả lời này có ích không?"}</span>
                <button
                  aria-pressed={feedback === "helpful"}
                  className={feedback === "helpful" ? "selected" : ""}
                  disabled={feedbackLoading || feedback !== null}
                  onClick={() => void submitFeedback("helpful")}
                  type="button"
                >Có ích</button>
                <button
                  aria-pressed={feedback === "unhelpful"}
                  className={feedback === "unhelpful" ? "selected negative" : ""}
                  disabled={feedbackLoading || feedback !== null}
                  onClick={() => void submitFeedback("unhelpful")}
                  type="button"
                >Cần xem lại</button>
              </div>
              {feedbackError ? <p className="feedback-error" role="alert">{feedbackError}</p> : null}
            </>
          ) : null}
        </div>
        {result?.handover_recommended ? (
          <button className="button button-handover" onClick={onHandover} type="button">
            <StaffIcon /> Chuyển câu hỏi cho cán bộ
          </button>
        ) : null}
      </div>
    </div>
  );
}

function HandoverDialog({
  question,
  reason,
  sessionId,
  onClose,
  onCreated,
}: {
  question: string;
  reason: string;
  sessionId: string | null;
  onClose: () => void;
  onCreated: (ticket: Ticket) => void;
}) {
  const [summary, setSummary] = useState(question);
  const [contact, setContact] = useState("");
  const [consent, setConsent] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!sessionId) {
      setError("Chưa có phiên chat để tạo yêu cầu.");
      return;
    }
    if (!summary.trim() || !consent) {
      setError("Vui lòng kiểm tra nội dung và xác nhận đồng ý trước khi gửi.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const ticket = await apiRequest<Ticket>("/api/v1/handover", {
        method: "POST",
        body: JSON.stringify({
          session_id: sessionId,
          question: summary.trim(),
          reason,
          consent: true,
          contact: contact.trim() || null,
        }),
      });
      onCreated(ticket);
      onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Chưa thể gửi yêu cầu.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section aria-labelledby="handover-title" aria-modal="true" className="modal-card" role="dialog">
        <div className="modal-header">
          <div><span className="section-kicker"><StaffIcon /> Handover an toàn</span><h2 id="handover-title">Chuyển cho cán bộ tuyển sinh</h2></div>
          <button aria-label="Đóng" className="icon-button" onClick={onClose} type="button"><CloseIcon /></button>
        </div>
        <p className="modal-intro">Chỉ nội dung dưới đây và kênh liên hệ tùy chọn được chuyển. Hệ thống không hứa thời gian phản hồi khi chưa có SLA chính thức.</p>
        <form onSubmit={submit}>
          <label className="field-label" htmlFor="handover-summary">Nội dung chuyển</label>
          <textarea id="handover-summary" maxLength={2000} onChange={(event) => setSummary(event.target.value)} rows={5} value={summary} />
          <label className="field-label" htmlFor="handover-contact">Email hoặc số điện thoại <span>(không bắt buộc)</span></label>
          <input id="handover-contact" maxLength={255} onChange={(event) => setContact(event.target.value)} placeholder="Để trống nếu chỉ theo dõi trong phiên" value={contact} />
          <label className="consent-row">
            <input checked={consent} onChange={(event) => setConsent(event.target.checked)} type="checkbox" />
            <span>Tôi đồng ý chuyển nội dung trên cho cán bộ phụ trách.</span>
          </label>
          {error ? <p className="form-error" role="alert">{error}</p> : null}
          <div className="modal-actions">
            <button className="button button-ghost" onClick={onClose} type="button">Hủy</button>
            <button className="button button-primary" disabled={submitting} type="submit">
              {submitting ? "Đang gửi…" : "Xác nhận chuyển"} {!submitting ? <SendIcon /> : null}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

function TicketTracker({ sessionId, ticketIds }: { sessionId: string | null; ticketIds: string[] }) {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(false);

  async function refresh() {
    if (!sessionId || !ticketIds.length) return;
    setLoading(true);
    const results = await Promise.allSettled(
      ticketIds.map((ticketId) =>
        apiRequest<Ticket>(`/api/v1/handover/${encodeURIComponent(ticketId)}`, {
          headers: { "X-Session-ID": sessionId },
        }, 8_000),
      ),
    );
    setTickets(results.flatMap((result) => result.status === "fulfilled" ? [result.value] : []));
    setLoading(false);
  }

  useEffect(() => {
    const initialRefresh = window.setTimeout(() => void refresh(), 0);
    const interval = window.setInterval(() => void refresh(), 20_000);
    return () => {
      window.clearTimeout(initialRefresh);
      window.clearInterval(interval);
    };
    // The serialized IDs keep polling stable when the list content is unchanged.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, ticketIds.join("|")]);

  return (
    <section className="side-card ticket-tracker">
      <div className="side-card-title">
        <div><span className="eyebrow">Theo dõi</span><h3>Yêu cầu cán bộ</h3></div>
        <button aria-label="Làm mới ticket" className="icon-button small" disabled={loading} onClick={() => void refresh()} type="button"><RefreshIcon className={loading ? "spin" : ""} /></button>
      </div>
      {!ticketIds.length ? (
        <div className="empty-compact"><ClockIcon /><p>Chưa có yêu cầu handover trong phiên này.</p></div>
      ) : null}
      <div className="ticket-mini-list">
        {tickets.map((ticket) => {
          const meta = ticketMeta[ticket.status];
          return (
            <article className="ticket-mini" key={ticket.ticket_id}>
              <div><strong>{ticket.ticket_id}</strong><span className={`ticket-badge ${meta.className}`}>{meta.label}</span></div>
              <p>{ticket.question}</p>
              {ticket.staff_reply ? <div className="staff-reply"><StaffIcon /><span><b>Phản hồi:</b> {ticket.staff_reply}</span></div> : null}
              <small>Cập nhật {formatDateTime(ticket.updated_at)}</small>
            </article>
          );
        })}
      </div>
    </section>
  );
}

export function ChatAssistant() {
  const [messages, setMessages] = useState<ConversationMessage[]>([welcomeMessage]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [ticketIds, setTicketIds] = useState<string[]>([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [lastQuestion, setLastQuestion] = useState("");
  const [lastReason, setLastReason] = useState("user_requested_handover");
  const [handoverOpen, setHandoverOpen] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const hydration = window.setTimeout(() => {
      const storedSession = window.sessionStorage.getItem(SESSION_KEY);
      const storedMessages = window.sessionStorage.getItem(MESSAGE_KEY);
      const storedTickets = window.sessionStorage.getItem(TICKET_KEY);
      if (storedSession) setSessionId(storedSession);
      if (storedMessages) {
        try { setMessages(JSON.parse(storedMessages) as ConversationMessage[]); } catch { /* ignore invalid browser state */ }
      }
      if (storedTickets) {
        try { setTicketIds(JSON.parse(storedTickets) as string[]); } catch { /* ignore invalid browser state */ }
      }
      const topic = new URLSearchParams(window.location.search).get("q");
      if (topic) setDraft(`Tôi muốn tìm hiểu về ${topic.toLocaleLowerCase("vi-VN")}.`);
      setHydrated(true);
    }, 0);
    return () => window.clearTimeout(hydration);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    window.sessionStorage.setItem(MESSAGE_KEY, JSON.stringify(messages));
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [hydrated, messages, loading]);

  async function sendQuestion(override?: string) {
    const question = (override ?? draft).trim();
    if (!question || loading) return;
    const userMessage: ConversationMessage = { id: makeId(), role: "user", text: question };
    setMessages((current) => [...current, userMessage]);
    setLastQuestion(question);
    setDraft("");
    setError("");
    setLoading(true);
    try {
      const result = await apiRequest<ChatResponse>("/api/v1/chat", {
        method: "POST",
        body: JSON.stringify({ message: question, session_id: sessionId }),
      });
      setSessionId(result.session_id);
      setLastReason(result.reason_code);
      window.sessionStorage.setItem(SESSION_KEY, result.session_id);
      setMessages((current) => [
        ...current,
        { id: result.request_id, role: "assistant", text: result.response, result },
      ]);
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "Không thể kết nối trợ lý.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendQuestion();
    }
  }

  async function clearConversation() {
    if (sessionId) {
      await apiRequest<void>(`/api/v1/session/${encodeURIComponent(sessionId)}`, { method: "DELETE" }, 8_000).catch(() => undefined);
    }
    setMessages([welcomeMessage]);
    setDraft("");
    setError("");
    setLastQuestion("");
    setLastReason("user_requested_handover");
    window.sessionStorage.removeItem(MESSAGE_KEY);
  }

  function addTicket(ticket: Ticket) {
    const next = Array.from(new Set([ticket.ticket_id, ...ticketIds]));
    setTicketIds(next);
    window.sessionStorage.setItem(TICKET_KEY, JSON.stringify(next));
  }

  return (
    <div className="chat-layout">
      <section className="chat-panel">
        <div className="chat-toolbar">
          <div>
            <KnowledgeStatus compact />
            <span className="session-note">Phiên ẩn danh · không yêu cầu hồ sơ cá nhân</span>
          </div>
          <button className="text-button" onClick={() => void clearConversation()} type="button"><RefreshIcon /> Xóa hội thoại</button>
        </div>

        <div aria-live="polite" className="message-list">
          {messages.map((message) => message.role === "user" ? (
            <div className="message-row user-row" key={message.id}><div className="message-bubble user-bubble">{message.text}</div></div>
          ) : (
            <AssistantMessage
              key={message.id}
              message={message}
              onHandover={() => {
                setLastQuestion(messages.filter((item) => item.role === "user").at(-1)?.text || "");
                setLastReason(message.result?.reason_code || "user_requested_handover");
                setHandoverOpen(true);
              }}
            />
          ))}
          {loading ? (
            <div className="message-row assistant-row"><span className="message-avatar"><SparkIcon /></span><div className="typing-card"><i/><i/><i/><span>Đang đối chiếu nguồn chính thức…</span></div></div>
          ) : null}
          <div ref={endRef} />
        </div>

        {messages.length === 1 ? (
          <div className="suggestion-area">
            <span>Gợi ý câu hỏi</span>
            <div>{suggestions.map((suggestion) => <button key={suggestion} onClick={() => void sendQuestion(suggestion)} type="button">{suggestion}</button>)}</div>
          </div>
        ) : null}

        {error ? (
          <div className="connection-error" role="alert"><span>{error}</span><button onClick={() => void sendQuestion(lastQuestion)} type="button"><RefreshIcon /> Thử lại</button></div>
        ) : null}

        <div className="chat-composer-wrap">
          <div className="chat-composer">
            <textarea
              aria-label="Câu hỏi tuyển sinh"
              disabled={loading}
              maxLength={2000}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Hỏi về ngành, học phí, học bổng, hồ sơ…"
              rows={2}
              value={draft}
            />
            <button aria-label="Gửi câu hỏi" className="send-button" disabled={loading || !draft.trim()} onClick={() => void sendQuestion()} type="button"><SendIcon /></button>
          </div>
          <div className="composer-meta"><span>Enter để gửi · Shift + Enter để xuống dòng</span><span>{draft.length}/2000</span></div>
        </div>
      </section>

      <aside className="chat-sidebar">
        <section className="side-card safety-card">
          <span className="side-icon"><ShieldIcon /></span>
          <div><span className="eyebrow">Nguyên tắc trả lời</span><h3>Không đoán khi thiếu căn cứ</h3></div>
          <ul><li>Có nguồn cho thông tin factual</li><li>Giữ nguyên cảnh báo và kỳ áp dụng</li><li>Chuyển cán bộ với trường hợp cá nhân</li></ul>
        </section>
        <TicketTracker sessionId={sessionId} ticketIds={ticketIds} />
        <button
          className="button button-secondary full-width"
          disabled={!sessionId || !lastQuestion}
          onClick={() => setHandoverOpen(true)}
          type="button"
        ><StaffIcon /> Chủ động hỏi cán bộ</button>
      </aside>

      {handoverOpen ? (
        <HandoverDialog
          onClose={() => setHandoverOpen(false)}
          onCreated={addTicket}
          question={lastQuestion}
          reason={lastReason}
          sessionId={sessionId}
        />
      ) : null}
    </div>
  );
}
