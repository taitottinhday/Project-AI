"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ChatIcon, MenuIcon, ShieldIcon, StaffIcon } from "@/components/icons";
import { AUTH_CHANGED_EVENT, ApiError, apiRequest, clearAuthSession, type AuthUser } from "@/lib/api";

type HeaderIdentity = {
  user: AuthUser;
  source: "applicant" | "staff" | "admin";
};

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

function readHeaderIdentity(pathname: string): HeaderIdentity | null {
  if (typeof window === "undefined") return null;

  const applicant = readStoredAuthUser();
  const applicantToken = window.localStorage.getItem("vinuni-auth-token");
  const staffToken = window.sessionStorage.getItem("vinuni-staff-token");
  const staffId = window.sessionStorage.getItem("vinuni-staff-id");
  const adminToken = window.sessionStorage.getItem("vinuni-admin-token");

  // Staff/admin tokens are intentionally separate from applicant auth. On
  // their protected pages, prefer the operator identity even if the same
  // browser also has an applicant session.
  if (pathname.startsWith("/staff") && staffToken && staffId) {
    return {
      source: "staff",
      user: { user_id: staffId, email: "Cán bộ tuyển sinh", display_name: staffId },
    };
  }
  if (pathname.startsWith("/admin") && adminToken) {
    return {
      source: "admin",
      user: { user_id: "admin", email: "Quản trị vận hành", display_name: "Quản trị viên" },
    };
  }
  if (applicantToken && applicant) return { source: "applicant", user: applicant };
  if (staffToken && staffId) {
    return {
      source: "staff",
      user: { user_id: staffId, email: "Cán bộ tuyển sinh", display_name: staffId },
    };
  }
  if (adminToken) {
    return {
      source: "admin",
      user: { user_id: "admin", email: "Quản trị vận hành", display_name: "Quản trị viên" },
    };
  }
  return null;
}

export function SiteHeader() {
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [identity, setIdentity] = useState<HeaderIdentity | null>(() => readHeaderIdentity(pathname));
  const [loggingOut, setLoggingOut] = useState(false);

  useEffect(() => {
    let active = true;

    function syncAuthState() {
      const nextIdentity = readHeaderIdentity(pathname);
      // Clear stale UI immediately when logout or another tab removes auth.
      if (!nextIdentity) {
        setIdentity(null);
        return;
      }

      setIdentity(nextIdentity);
      if (nextIdentity.source !== "applicant") return;

      const token = window.localStorage.getItem("vinuni-auth-token");
      if (!token) {
        setIdentity(null);
        return;
      }

      // The local profile is only a fast first paint. Validate it against the
      // backend so an expired/revoked session never leaves a false signed-in
      // state in the shared header. This function is also called after login
      // because the root layout survives client-side navigation.
      void apiRequest<AuthUser>("/api/v1/auth/me", { method: "GET" }, 8_000)
        .then((freshUser) => {
          if (!active || window.localStorage.getItem("vinuni-auth-token") !== token) return;
          setIdentity({ source: "applicant", user: freshUser });
          window.localStorage.setItem("vinuni-auth-user", JSON.stringify(freshUser));
        })
        .catch((caught) => {
          if (!active) return;
          if (caught instanceof ApiError && caught.status === 401 && window.localStorage.getItem("vinuni-auth-token") === token) {
            clearAuthSession();
            setIdentity(null);
          }
        });
    }

    syncAuthState();
    window.addEventListener(AUTH_CHANGED_EVENT, syncAuthState);
    window.addEventListener("storage", syncAuthState);
    return () => {
      active = false;
      window.removeEventListener(AUTH_CHANGED_EVENT, syncAuthState);
      window.removeEventListener("storage", syncAuthState);
    };
  }, [pathname]);

  function handleLogout() {
    setLoggingOut(true);
    // Revoke the server session in the background, but never make the user
    // wait for a slow/unavailable backend before leaving the protected view.
    if (identity?.source === "applicant") {
      void apiRequest("/api/v1/auth/logout", { method: "POST" }).catch(() => undefined);
      clearAuthSession();
    } else if (identity?.source === "staff") {
      window.sessionStorage.removeItem("vinuni-staff-token");
      window.sessionStorage.removeItem("vinuni-staff-id");
      window.dispatchEvent(new Event(AUTH_CHANGED_EVENT));
    } else if (identity?.source === "admin") {
      window.sessionStorage.removeItem("vinuni-admin-token");
      window.dispatchEvent(new Event(AUTH_CHANGED_EVENT));
    }
    setIdentity(null);
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
          {identity ? (
            <div className="auth-user-menu">
              <span className="auth-user-name" title={identity.user.email}>{identity.user.display_name}</span>
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
