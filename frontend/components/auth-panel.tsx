"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { API_BASE, apiRequest, type AuthSession } from "@/lib/api";

type Mode = "login" | "register" | "verify";

export function AuthPanel() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const title = mode === "register" ? "Tạo tài khoản" : mode === "verify" ? "Xác minh email" : "Chào mừng trở lại";
  const description = mode === "register"
    ? "Tạo tài khoản để lưu phiên tư vấn và theo dõi phản hồi từ cán bộ tuyển sinh."
    : mode === "verify"
      ? `Chúng tôi đã gửi mã xác minh gồm 6 số tới ${email}.`
      : "Đăng nhập để tiếp tục hành trình tìm hiểu và ứng tuyển vào VinUni.";

  function saveSession(session: AuthSession) {
    window.localStorage.setItem("vinuni-auth-token", session.access_token);
    window.localStorage.setItem("vinuni-auth-user", JSON.stringify(session.user));
    router.replace("/");
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      if (mode === "login") {
        saveSession(await apiRequest<AuthSession>("/api/v1/auth/login", {
          method: "POST", body: JSON.stringify({ email, password }),
        }));
      } else if (mode === "register") {
        const result = await apiRequest<{ message: string }>("/api/v1/auth/register/request-otp", {
          method: "POST", body: JSON.stringify({ email, display_name: name, password }),
        });
        setMode("verify");
        setMessage(`${result.message}. Kiểm tra cả mục Spam/Quảng cáo.`);
      } else {
        saveSession(await apiRequest<AuthSession>("/api/v1/auth/register/verify-otp", {
          method: "POST", body: JSON.stringify({ email, code }),
        }));
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Có lỗi xảy ra. Vui lòng thử lại.");
    } finally {
      setBusy(false);
    }
  }

  function switchMode(nextMode: Mode) {
    setMode(nextMode);
    setError("");
    setMessage("");
    setCode("");
    setShowPassword(false);
  }

  return (
    <main className="auth-page">
      <div aria-hidden="true" className="auth-ambient auth-ambient-one" />
      <div aria-hidden="true" className="auth-ambient auth-ambient-two" />

      <section className="auth-experience">
        <aside className="auth-story">
          <Link className="auth-story-brand" href="/">
            <span className="auth-story-mark">
              <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M12 3 5.5 5.5v5.2c0 4.2 2.7 8 6.5 9.3 3.8-1.3 6.5-5.1 6.5-9.3V5.5L12 3Z"/><path d="m9.2 11.7 1.8 1.8 3.9-4.2"/></svg>
            </span>
            <span><strong>VinUni Guide</strong><small>Admissions Assistant</small></span>
          </Link>

          <div className="auth-story-copy">
            <span className="auth-story-kicker"><i /> Đồng hành cùng hành trình tuyển sinh</span>
            <h2>Thông tin đáng tin cậy.<br/><em>Quyết định tự tin hơn.</em></h2>
            <p>Tra cứu thông tin tuyển sinh từ kho dữ liệu đã kiểm chứng và kết nối trực tiếp với cán bộ khi bạn cần hỗ trợ.</p>
          </div>

          <ul className="auth-benefits">
            <li><span><svg aria-hidden="true" viewBox="0 0 24 24"><path d="m5 12 4 4L19 6"/></svg></span><div><strong>Nguồn chính thức</strong><small>Mỗi câu trả lời factual đều kèm căn cứ để đối chiếu.</small></div></li>
            <li><span><svg aria-hidden="true" viewBox="0 0 24 24"><path d="M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z"/><path d="M12 7v5l3 2"/></svg></span><div><strong>Theo dõi liền mạch</strong><small>Lưu phiên hỗ trợ và nhận phản hồi từ cán bộ tuyển sinh.</small></div></li>
            <li><span><svg aria-hidden="true" viewBox="0 0 24 24"><path d="M7 11V8a5 5 0 0 1 10 0v3"/><rect width="16" height="10" x="4" y="11" rx="2"/></svg></span><div><strong>Riêng tư và an toàn</strong><small>Bạn chủ động quyết định nội dung được chia sẻ.</small></div></li>
          </ul>

          <div className="auth-story-footer"><span className="auth-live-dot" /> Hệ thống tư vấn đang hoạt động</div>
        </aside>

        <section className="auth-card">
          <div className="auth-mobile-brand"><span className="auth-story-mark"><svg aria-hidden="true" viewBox="0 0 24 24"><path d="M12 3 5.5 5.5v5.2c0 4.2 2.7 8 6.5 9.3 3.8-1.3 6.5-5.1 6.5-9.3V5.5L12 3Z"/><path d="m9.2 11.7 1.8 1.8 3.9-4.2"/></svg></span><strong>VinUni Guide</strong></div>

          <div className="auth-card-heading">
            {mode === "verify" ? <button className="auth-back" onClick={() => switchMode("register")} type="button">← Quay lại</button> : <span className="auth-step-label">{mode === "register" ? "Bắt đầu với VinUni Guide" : "Tài khoản của bạn"}</span>}
            <h1>{title}</h1>
            <p className="auth-lead">{description}</p>
          </div>

          {mode !== "verify" ? (
            <>
              <a className="google-button" href={`${API_BASE}/api/v1/auth/google/start`}>
                <svg aria-hidden="true" className="google-mark" viewBox="0 0 24 24"><path fill="#4285F4" d="M21.6 12.2c0-.7-.1-1.5-.2-2.2H12v4.3h5.4a4.7 4.7 0 0 1-2 3v2.8h3.5c2-1.9 3.2-4.6 3.2-7.9Z"/><path fill="#34A853" d="M12 22c2.9 0 5.3-1 7-2.6l-3.5-2.8c-1 .7-2.2 1-3.5 1-2.7 0-5-1.8-5.8-4.3H2.6v2.8A10 10 0 0 0 12 22Z"/><path fill="#FBBC05" d="M6.2 13.3a6 6 0 0 1 0-3.8V6.7H2.6a10 10 0 0 0 0 9.4l3.6-2.8Z"/><path fill="#EA4335" d="M12 5.4c1.6 0 3 .5 4.1 1.6l3.1-3A10 10 0 0 0 2.6 6.7l3.6 2.8C7 7 9.3 5.4 12 5.4Z"/></svg>
                <span>Tiếp tục với Google</span>
                <svg aria-hidden="true" className="auth-arrow" viewBox="0 0 24 24"><path d="m9 18 6-6-6-6"/></svg>
              </a>
              <div className="auth-divider"><span>hoặc tiếp tục bằng email</span></div>
            </>
          ) : null}

          <form className="auth-form" onSubmit={submit}>
            {mode === "register" ? (
              <label><span>Tên hiển thị</span><input autoComplete="name" required maxLength={100} onChange={(event) => setName(event.target.value)} placeholder="Tên bạn muốn hiển thị" value={name} /></label>
            ) : null}

            {mode !== "verify" ? <label><span>Email</span><input autoComplete="email" required type="email" onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" value={email} /></label> : null}

            {mode === "verify" ? (
              <label className="otp-field"><span>Mã OTP 6 số</span><input aria-describedby="otp-hint" autoComplete="one-time-code" inputMode="numeric" maxLength={6} pattern="[0-9]{6}" placeholder="••••••" required onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))} value={code} /><small id="otp-hint">Mã có hiệu lực trong 10 phút. Kiểm tra cả mục Spam hoặc Quảng cáo.</small></label>
            ) : (
              <label><span>Mật khẩu</span><span className="password-field"><input autoComplete={mode === "login" ? "current-password" : "new-password"} minLength={8} required type={showPassword ? "text" : "password"} onChange={(event) => setPassword(event.target.value)} placeholder={mode === "register" ? "Tối thiểu 8 ký tự" : "Nhập mật khẩu"} value={password} /><button aria-label={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"} onClick={() => setShowPassword((current) => !current)} type="button">{showPassword ? "Ẩn" : "Hiện"}</button></span></label>
            )}

            <button className="button button-primary auth-submit" disabled={busy} type="submit">
              <span>{busy ? "Đang xử lý…" : mode === "login" ? "Đăng nhập" : mode === "register" ? "Gửi mã xác minh" : "Xác minh tài khoản"}</span>
              {!busy ? <svg aria-hidden="true" viewBox="0 0 24 24"><path d="m9 18 6-6-6-6"/></svg> : <i className="auth-spinner" />}
            </button>
          </form>

          {message ? <p className="auth-message"><span>✓</span>{message}</p> : null}
          {error ? <p className="auth-error"><span>!</span>{error}</p> : null}

          {mode === "login" ? <p className="auth-switch">Chưa có tài khoản? <button onClick={() => switchMode("register")} type="button">Tạo tài khoản miễn phí</button></p> : null}
          {mode === "register" ? <p className="auth-switch">Đã có tài khoản? <button onClick={() => switchMode("login")} type="button">Đăng nhập</button></p> : null}
          {mode === "verify" ? <p className="auth-switch">Email chưa đúng? <button onClick={() => switchMode("register")} type="button">Thay đổi email</button></p> : null}

          <div className="auth-privacy"><svg aria-hidden="true" viewBox="0 0 24 24"><path d="M7 11V8a5 5 0 0 1 10 0v3"/><rect width="16" height="10" x="4" y="11" rx="2"/></svg><p><strong>Dữ liệu đăng nhập được bảo vệ</strong><span>Mật khẩu được băm ở backend và OTP không được lưu dưới dạng nguyên văn.</span></p></div>
        </section>
      </section>
    </main>
  );
}
