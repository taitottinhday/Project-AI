import type { Metadata } from "next";

import { StaffDashboard } from "@/components/staff-dashboard";

export const metadata: Metadata = {
  title: "Hàng chờ cán bộ",
};

export default function StaffPage() {
  return (
    <main className="staff-page">
      <div className="page-shell staff-page-heading">
        <div><span className="section-kicker">Human-in-the-loop</span><h1>Trung tâm xử lý yêu cầu</h1><p>Nhận và phản hồi những trường hợp AI không đủ thẩm quyền hoặc không có căn cứ chắc chắn.</p></div>
      </div>
      <div className="page-shell"><StaffDashboard /></div>
    </main>
  );
}
