"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ChatIcon, MenuIcon, ShieldIcon, StaffIcon } from "@/components/icons";
import { ApiError, apiRequest, type AuthUser } from "@/lib/api";

function readStoredAuthUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  const storedUser = window.localStorage.getItem("vinuni-auth-user");
  if (!storedUser) return null;
  try {
    const parsed = JSON.parse(storedUser) as Partial<AuthUser>;
    return parsed.user_id && parsed.email && parsed.display_name ? parsed as AuthUser : null;
  } catch {
    window.localStorage.removeItem("vinuni-auth-user");
    return null;
  }
}

export function SiteHeader() {
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [user, setUser] = useState<AuthUser | null>(readStoredAuthUser);
  const [loggingOut, setLoggingOut] = useState(false);

  useEffect(() => {
    const token = window.localStorage.getItem("vinuni-auth-token");
    // The local profile is only a fast first paint.  Validate it against the
    // backend so an expired/revoked session never leaves a false signed-in
    // state in the shared header.
    if (!token) return;
    void apiRequest<AuthUser>("/api/v1/auth/me", { method: "GET" }, 8_000)
      .then((freshUser) => {
        setUser(freshUser);
        window.localStorage.setItem("vinuni-auth-user", JSON.stringify(freshUser));
      })
      .catch((caught) => {
        if (caught instanceof ApiError && caught.status === 401) {
          window.localStorage.removeItem("vinuni-auth-token");
          window.localStorage.removeItem("vinuni-auth-user");
          setUser(null);
        }
      });
  }, []);

  function handleLogout() {
    setLoggingOut(true);
    // Revoke the server session in the background, but never make the user
    // wait for a slow/unavailable backend before leaving the protected view.
    void apiRequest("/api/v1/auth/logout", { method: "POST" }).catch(() => undefined);
    window.localStorage.removeItem("vinuni-auth-token");
    window.localStorage.removeItem("vinuni-auth-user");
    setUser(null);
    setLoggingOut(false);
    setOpen(false);
    router.replace("/auth");
  }

  const links = [
    { href: "/", label: "Tổng quan" },
    { href: "/chat", label: "Hỏi đáp", icon: ChatIcon },
    { href: "/staff", label: "Dành cho cán bộ", icon: StaffIcon },
    { href: "/admin", label: "Quản trị", icon: ShieldIcon },
  ];

  return (
    <header className="site-header">
      <div className="header-inner">
        <Link className="brand" href="/" onClick={() => setOpen(false)}>
          <span className="brand-mark"><ShieldIcon /></span>
          <span>
            <strong>VinUni Guide</strong>
            <small>Admissions assistant</small>
          </span>
        </Link>

        <button
          aria-expanded={open}
          aria-label="Mở menu"
          className="menu-button"
          onClick={() => setOpen((value) => !value)}
          type="button"
        >
          <MenuIcon />
        </button>

        <nav aria-label="Điều hướng chính" className={open ? "main-nav nav-open" : "main-nav"}>
          {links.map(({ href, label, icon: Icon }) => (
            <Link
              className={pathname === href ? "nav-link active" : "nav-link"}
              href={href}
              key={href}
              onClick={() => setOpen(false)}
            >
              {Icon ? <Icon /> : null}
              {label}
            </Link>
          ))}
          {user ? (
            <div className="auth-user-menu">
              <span className="auth-user-name" title={user.email}>{user.display_name}</span>
              <button className="auth-logout" disabled={loggingOut} onClick={handleLogout} type="button">
                {loggingOut ? "Đang thoát…" : "Đăng xuất"}
              </button>
            </div>
          ) : (
            <Link className={pathname === "/auth" ? "nav-link active auth-nav-link" : "nav-link auth-nav-link"} href="/auth" onClick={() => setOpen(false)}>
              Đăng nhập
            </Link>
          )}
        </nav>
      </div>
    </header>
  );
}
