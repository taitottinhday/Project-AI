"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { apiRequest, type AuthSession } from "@/lib/api";

function AuthCallbackContent() {
  const router = useRouter();
  const params = useSearchParams();
  const [error, setError] = useState("");

  useEffect(() => {
    const code = params.get("code");
    if (!code) {
      setError("Thiếu mã đăng nhập Google.");
      return;
    }
    void apiRequest<AuthSession>("/api/v1/auth/google/exchange", {
      method: "POST",
      body: JSON.stringify({ code }),
    }).then((session) => {
      window.localStorage.setItem("vinuni-auth-token", session.access_token);
      window.localStorage.setItem("vinuni-auth-user", JSON.stringify(session.user));
      router.replace("/?auth=success");
    }).catch((caught) => {
      setError(caught instanceof Error ? caught.message : "Không thể hoàn tất đăng nhập Google.");
    });
  }, [params, router]);

  return (
    <main className="auth-page page-shell">
      <section className="auth-card">
        <p className="eyebrow">XÁC THỰC TÀI KHOẢN</p>
        <h1>{error ? "Đăng nhập chưa hoàn tất" : "Đang hoàn tất đăng nhập…"}</h1>
        <p>{error || "Bạn sẽ được chuyển về VinUni Guide trong giây lát."}</p>
        {error ? <a className="button button-secondary" href="/auth">Quay lại đăng nhập</a> : null}
      </section>
    </main>
  );
}

export default function AuthCallbackPage() {
  return <Suspense fallback={<main className="auth-page page-shell"><section className="auth-card"><h1>Đang xử lý…</h1></section></main>}><AuthCallbackContent /></Suspense>;
}
