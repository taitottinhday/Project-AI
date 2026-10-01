"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { ChatIcon, MenuIcon, ShieldIcon, StaffIcon } from "@/components/icons";

export function SiteHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const links = [
    { href: "/", label: "Tổng quan" },
    { href: "/chat", label: "Hỏi đáp", icon: ChatIcon },
    { href: "/staff", label: "Dành cho cán bộ", icon: StaffIcon },
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
          <Link className={pathname === "/auth" ? "nav-link active auth-nav-link" : "nav-link auth-nav-link"} href="/auth" onClick={() => setOpen(false)}>
            Đăng nhập
          </Link>
        </nav>
      </div>
    </header>
  );
}
