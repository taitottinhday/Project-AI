import type { Metadata } from "next";

import { ChatAssistant } from "@/components/chat-assistant";

export const metadata: Metadata = {
  title: "Hỏi đáp tuyển sinh",
};

export default function ChatPage() {
  return (
    <main className="chat-page">
      <div className="page-shell chat-page-heading">
        <div>
          <span className="section-kicker">Trợ lý tuyển sinh có căn cứ</span>
          <h1>Bạn muốn tìm hiểu điều gì?</h1>
          <p>Câu trả lời thành công luôn đi kèm nguồn. Confidence chỉ phản ánh mức khớp truy xuất, không phải xác suất đúng.</p>
        </div>
      </div>
      <div className="page-shell"><ChatAssistant /></div>
    </main>
  );
}
