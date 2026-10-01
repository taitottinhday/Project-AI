"use client";

import { FormEvent, useState } from "react";

import { API_BASE, apiRequest, type AuthSession } from "@/lib/api";

type Mode = "login" | "register" | "verify";

export function AuthPanel() {
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  function saveSession(session: AuthSession) {
    window.localStorage.setItem("vinuni-auth-token", session.access_token);
    window.localStorage.setItem("vinuni-auth-user", JSON.stringify(session.user));
    window.location.assign("/");
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
        await apiRequest("/api/v1/auth/register/request-otp", {
          method: "POST", body: JSON.stringify({ email, display_name: name, password }),
        });
        setMode("verify");
        setMessage("Mã OTP đã được gửi tới email. Kiểm tra cả mục Spam/Quảng cáo.");
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

  return (
    <main className="auth-page page-shell">
      <section className="auth-card">
        <p className="eyebrow">VINUNI GUIDE</p>
        <h1>{mode === "register" ? "Tạo tài khoản" : mode === "verify" ? "Xác minh email" : "Đăng nhập"}</h1>
        <p className="auth-lead">Lưu lại phiên hỗ trợ và thuận tiện theo dõi phản hồi từ cán bộ tuyển sinh.</p>
        {mode !== "verify" ? (
          <a className="google-button" href={`${API_BASE}/api/v1/auth/google/start`}>
            <span aria-hidden="true">G</span> Tiếp tục với Google
          </a>
        ) : null}
        <div className="auth-divider"><span>hoặc</span></div>
        <form className="auth-form" onSubmit={submit}>
          {mode === "register" ? (
            <label>Tên hiển thị<input required maxLength={100} onChange={(event) => setName(event.target.value)} value={name} /></label>
          ) : null}
          <label>Email<input autoComplete="email" required type="email" onChange={(event) => setEmail(event.target.value)} value={email} /></label>
          {mode === "verify" ? (
            <label>Mã OTP 6 số<input inputMode="numeric" maxLength={6} pattern="[0-9]{6}" required onChange={(event) => setCode(event.target.value)} value={code} /></label>
          ) : (
            <label>Mật khẩu<input autoComplete={mode === "login" ? "current-password" : "new-password"} minLength={8} required type="password" onChange={(event) => setPassword(event.target.value)} value={password} /></label>
          )}
          <button className="button button-primary auth-submit" disabled={busy} type="submit">
            {busy ? "Đang xử lý…" : mode === "login" ? "Đăng nhập" : mode === "register" ? "Gửi mã OTP" : "Xác minh và tạo tài khoản"}
          </button>
        </form>
        {message ? <p className="auth-message">{message}</p> : null}
        {error ? <p className="auth-error">{error}</p> : null}
        {mode === "login" ? <p className="auth-switch">Chưa có tài khoản? <button onClick={() => { setMode("register"); setError(""); }} type="button">Đăng ký bằng email</button></p> : null}
        {mode === "register" ? <p className="auth-switch">Đã có tài khoản? <button onClick={() => { setMode("login"); setError(""); }} type="button">Đăng nhập</button></p> : null}
        {mode === "verify" ? <p className="auth-switch"><button onClick={() => setMode("register")} type="button">Đổi email đăng ký</button></p> : null}
        <p className="auth-privacy">Mật khẩu được băm ở backend. OTP chỉ có hiệu lực trong thời gian ngắn và không được lưu dạng nguyên văn.</p>
      </section>
    </main>
  );
}
