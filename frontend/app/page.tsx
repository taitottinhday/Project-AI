import Link from "next/link";

import { ArrowIcon, ChatIcon, ShieldIcon, SourceIcon, SparkIcon, StaffIcon } from "@/components/icons";
import { KnowledgeStatus } from "@/components/knowledge-status";

const topics = [
  "Ngành và chương trình đào tạo",
  "Học phí và chính sách hỗ trợ",
  "Học bổng và hỗ trợ tài chính",
  "Quy trình và hạn nộp hồ sơ",
  "Ký túc xá và đời sống sinh viên",
  "Quy định học vụ, visa và trao đổi",
];

export default function HomePage() {
  return (
    <main>
      <section className="hero-section">
        <div className="hero-orb hero-orb-one" />
        <div className="hero-orb hero-orb-two" />
        <div className="page-shell hero-grid">
          <div className="hero-copy">
            <span className="section-kicker"><SparkIcon /> Trợ lý dữ liệu tuyển sinh VinUni</span>
            <h1>Hỏi đúng điều bạn cần.<br/><em>Kiểm chứng được từng câu trả lời.</em></h1>
            <p className="hero-lead">
              Tra cứu ngành học, học phí, học bổng và quy trình tuyển sinh từ kho dữ liệu chính thức.
              Khi chưa đủ căn cứ, hệ thống nói rõ giới hạn và chuyển bạn tới cán bộ phụ trách.
            </p>
            <div className="hero-actions">
              <Link className="button button-primary button-large" href="/chat">
                Bắt đầu hỏi đáp <ArrowIcon />
              </Link>
              <Link className="button button-ghost button-large" href="/staff">
                <StaffIcon /> Khu vực cán bộ
              </Link>
            </div>
            <div className="trust-line">
              <span><ShieldIcon /> Không dự đoán trúng tuyển</span>
              <span><SourceIcon /> Câu trả lời factual có nguồn</span>
            </div>
          </div>

          <div className="hero-demo" aria-label="Minh họa câu trả lời">
            <div className="demo-window">
              <div className="demo-topbar">
                <div className="window-dots"><i/><i/><i/></div>
                <KnowledgeStatus compact />
              </div>
              <div className="demo-thread">
                <div className="demo-user">Học phí Bác sĩ Y khoa được tính như thế nào?</div>
                <div className="demo-answer">
                  <div className="assistant-avatar"><SparkIcon /></div>
                  <div>
                    <span className="answer-label"><ShieldIcon /> Đã kiểm chứng nguồn</span>
                    <p>Hệ thống đã tìm thấy mức học phí, cách tính theo kỳ hoặc tín chỉ và ghi chú hỗ trợ trong tài liệu đúng năm học. Mở trợ lý để xem số liệu hiện hành kèm nguồn.</p>
                    <div className="source-preview"><SourceIcon /> Quy định tài chính và biểu phí đúng năm học</div>
                  </div>
                </div>
              </div>
              <div className="demo-composer">Nhập câu hỏi tuyển sinh… <span><ArrowIcon /></span></div>
            </div>
          </div>
        </div>
      </section>

      <section className="page-shell status-section">
        <KnowledgeStatus />
      </section>

      <section className="page-shell content-section">
        <div className="section-heading">
          <span className="section-kicker">Phạm vi hỗ trợ</span>
          <h2>Một nơi để tra cứu các câu hỏi quan trọng</h2>
          <p>Dữ liệu được tổ chức theo năm học và nguồn, không ghép thông tin cũ vào chính sách hiện hành.</p>
        </div>
        <div className="topic-grid">
          {topics.map((topic, index) => (
            <Link className="topic-card" href={`/chat?q=${encodeURIComponent(topic)}`} key={topic}>
              <span className="topic-number">0{index + 1}</span>
              <strong>{topic}</strong>
              <ArrowIcon />
            </Link>
          ))}
        </div>
      </section>

      <section className="principles-section">
        <div className="page-shell principles-grid">
          <div className="section-heading align-left">
            <span className="section-kicker light">Cách hệ thống hoạt động</span>
            <h2>Chính xác trước, trôi chảy sau</h2>
            <p>Mỗi câu hỏi đi qua nhiều lớp kiểm tra trước khi xuất hiện trên màn hình của bạn.</p>
          </div>
          <div className="principle-list">
            <article><span><SourceIcon /></span><div><strong>Truy xuất đúng tài liệu</strong><p>Lọc theo chủ đề, năm học và thứ tự ưu tiên của nguồn.</p></div></article>
            <article><span><ShieldIcon /></span><div><strong>Kiểm tra từng con số</strong><p>Số liệu không có trong evidence sẽ bị chặn trước khi trả lời.</p></div></article>
            <article><span><StaffIcon /></span><div><strong>Biết khi nào cần con người</strong><p>Trường hợp cá nhân, nguồn thiếu hoặc mâu thuẫn được handover.</p></div></article>
          </div>
        </div>
      </section>

      <section className="page-shell final-cta">
        <div>
          <span className="section-kicker"><ChatIcon /> Sẵn sàng tra cứu</span>
          <h2>Bắt đầu với một câu hỏi cụ thể</h2>
          <p>Bạn không cần cung cấp CCCD, địa chỉ hoặc hồ sơ cá nhân để sử dụng phần hỏi đáp.</p>
        </div>
        <Link className="button button-primary button-large" href="/chat">Mở trợ lý <ArrowIcon /></Link>
      </section>
    </main>
  );
}
