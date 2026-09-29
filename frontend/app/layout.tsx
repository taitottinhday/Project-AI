import type { Metadata } from "next";
import type { ReactNode } from "react";

import { SiteHeader } from "@/components/site-header";

import "@fontsource-variable/lora/wght.css";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "VinUni Guide | Trợ lý tuyển sinh có nguồn",
    template: "%s | VinUni Guide",
  },
  description: "Trợ lý hỏi đáp tuyển sinh VinUni dựa trên dữ liệu chính thức, có trích nguồn và handover cho cán bộ.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="vi">
      <body>
        <SiteHeader />
        {children}
        <footer className="site-footer">
          <div>
            <strong>VinUni Guide</strong>
            <p>Sản phẩm học tập · Thông tin tham khảo, không thay thế quyết định chính thức của VinUniversity.</p>
          </div>
          <div className="footer-meta">
            <span>Accuracy-first RAG</span>
            <span>Năm học lấy từ kho dữ liệu</span>
          </div>
        </footer>
      </body>
    </html>
  );
}
