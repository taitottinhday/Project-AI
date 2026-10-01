import type { Metadata } from "next";

import { AdminDashboard } from "@/components/admin-dashboard";

export const metadata: Metadata = {
  title: "Quản trị vận hành",
};

export default function AdminPage() {
  return (
    <main className="staff-page admin-page">
      <div className="page-shell staff-page-heading">
        <div>
          <span className="section-kicker">Administration</span>
          <h1>Điều phối đội ngũ tuyển sinh</h1>
          <p>Quản lý nhóm chuyên môn, năng lực cán bộ và tự động phân công các yêu cầu cần con người xử lý.</p>
        </div>
      </div>
      <div className="page-shell"><AdminDashboard /></div>
    </main>
  );
}
