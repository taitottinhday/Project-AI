# Bài thuyết trình Mentor Duty — VinUni Guide

Thời lượng đề xuất: 5–7 phút.

## 1. Mở đầu — 30 giây

> Tuần này nhóm em tập trung biến VinUni Guide từ một chatbot hỏi đáp thành một quy trình hỗ trợ tuyển sinh hoàn chỉnh. Sản phẩm có hai phía: ứng viên tra cứu thông tin và cán bộ tiếp nhận những trường hợp AI không đủ căn cứ để trả lời.

> Mục tiêu của nhóm không phải là trả lời càng nhiều càng tốt, mà là trả lời đúng, có nguồn và chuyển đúng lúc cho con người.

## 2. DONE — Tuần này nhóm đã hoàn thành gì?

### 2.1. Hoàn thiện trợ lý hỏi đáp có kiểm chứng

- Trả lời các câu hỏi về ngành học, học phí, học bổng, hồ sơ, ký túc xá và quy chế học vụ.
- Mỗi câu factual có citation để người dùng kiểm tra.
- Không đoán khi thiếu evidence, dữ liệu cũ, dữ liệu mâu thuẫn hoặc câu hỏi mang tính quyết định cá nhân.

**Câu nói khi demo:**

> Ví dụ, khi ứng viên hỏi học phí Điều dưỡng, hệ thống trả lời từ tài liệu đúng năm học và hiển thị nguồn. Nhưng nếu ứng viên hỏi “em có chắc chắn đậu không”, hệ thống không cam kết mà chuyển sang cán bộ.

### 2.2. Hoàn thiện luồng human-in-the-loop

- Ứng viên có thể gửi câu hỏi cho cán bộ sau khi đồng ý chia sẻ nội dung.
- Ticket có ba trạng thái rõ ràng: `Đang chờ → Đang xử lý → Đã phản hồi`.
- Cán bộ phải nhận ticket trước khi trả lời, tránh hai người xử lý trùng.
- Khi cán bộ gửi phản hồi, ticket tự hoàn tất.

### 2.3. Đồng bộ và lưu lịch sử

- Hàng chờ cán bộ tự cập nhật khoảng 3 giây một lần.
- Màn hình ứng viên tự cập nhật khoảng 5 giây một lần.
- Ticket và phản hồi được lưu trên Railway Volume để không mất sau restart hoặc redeploy.
- Ứng viên có thể theo dõi lại ticket trên cùng trình duyệt mà chưa cần tạo tài khoản.

### 2.4. Triển khai và kiểm thử

- Frontend đã triển khai trên Vercel.
- Backend đã triển khai trên Railway.
- Đã xử lý lỗi CORS giữa domain Vercel và backend Railway.
- Đã bổ sung benchmark, golden set, adversarial set và canonical coverage evaluation.

## 3. Demo trực tiếp — 3 phút

### Bước 1: Câu hỏi có thể trả lời

Nhập:

> Học phí Điều dưỡng năm học 2026–2027 là bao nhiêu?

Nói:

> Đây là câu hỏi factual. Điều em muốn chứng minh không chỉ là hệ thống trả lời được, mà là câu trả lời có nguồn, đúng năm học và đúng chương trình.

### Bước 2: Câu hỏi cần con người

Nhập:

> Hồ sơ của em có chắc chắn đậu VinUni không?

Nói:

> AI không nên tự quyết định kết quả tuyển sinh cá nhân. Hệ thống nêu rõ giới hạn và đề xuất handover thay vì tạo một câu trả lời nghe hợp lý nhưng không có căn cứ.

### Bước 3: Cán bộ tiếp nhận

1. Đồng ý chia sẻ nội dung.
2. Tạo ticket.
3. Mở trang cán bộ.
4. Nhận ticket.
5. Gửi phản hồi.
6. Quay lại phía ứng viên để cho thấy trạng thái tự đổi thành “Đã phản hồi”.

Nói:

> Đây là điểm khác biệt giữa chatbot FAQ và workflow hỗ trợ. Câu hỏi không bị rơi khi AI không biết; nó được chuyển cùng ngữ cảnh cho đúng người xử lý.

## 4. Dữ liệu và evaluation

### 4.1. Dữ liệu

Nhóm sử dụng tài liệu chính thức của VinUni theo năm học, sau đó:

```text
Thu thập nguồn → kiểm tra năm học/ngày hiệu lực → chuẩn hóa
→ chia evidence chunks → gắn source và trạng thái an toàn
→ truy xuất evidence → tạo câu trả lời có citation
```

Kho hiện có:

- 12 tài liệu.
- 62 nguồn.
- 219 evidence chunks.

Nhóm không coi nội dung web mới là sự thật ngay lập tức. Nguồn phải được kiểm tra trước khi dùng cho câu trả lời factual.

### 4.2. Evaluation

- 17 golden questions kiểm tra các tình huống chuẩn.
- 40 adversarial questions kiểm tra câu hỏi mơ hồ, sai năm, prompt injection và dữ liệu nhạy cảm.
- Canonical coverage kiểm tra khả năng truy xuất đúng evidence trong toàn bộ dataset.

Kết quả hiện tại:

- 113/113 factual coverage cases đạt.
- 5/5 safety cases đạt.
- 101 chunks metadata đã được audit.
- Bộ test backend hiện tại đã pass.

Nói rõ với mentor:

> Đây là kết quả trên các scenario đại diện của dataset, chưa phải tuyên bố chatbot hiểu mọi câu hỏi ngoài phạm vi dữ liệu. Nhóm vẫn cần đo thêm latency production, user satisfaction và human review.

## 5. Tư duy sản phẩm

### Người dùng đang thuê sản phẩm làm gì?

Ứng viên thuê sản phẩm để:

> Tìm được câu trả lời tuyển sinh nhanh, có căn cứ và biết bước tiếp theo an toàn.

Cán bộ thuê sản phẩm để:

> Nhận đúng câu hỏi có ngữ cảnh, xử lý theo trạng thái rõ ràng và không phải trả lời trùng lặp.

### Giá trị cốt lõi

```text
Tin cậy thông tin + giảm friction + chuyển người thật đúng lúc
```

Sản phẩm không tối ưu cho số lượng câu trả lời đơn thuần. Sản phẩm tối ưu cho số câu trả lời có thể kiểm chứng và số trường hợp được chuyển đúng người.

## 6. ĐIỂM MẠNH

- Câu trả lời factual có nguồn.
- Có guardrail và fail-closed khi thiếu căn cứ.
- Handover là workflow thật, không chỉ là nút “liên hệ chúng tôi”.
- Trạng thái ứng viên và cán bộ nhất quán.
- Ticket tồn tại sau redeploy nhờ lưu bền vững.
- Có evaluation về factual coverage và safety, không chỉ demo thủ công.
- Trải nghiệm bắt đầu không cần đăng nhập, phù hợp với MVP public-facing.

## 7. ĐIỂM YẾU / BLOCKER

### Blocker hiện tại

> Nhóm chưa thể chốt KPI production vì chưa có đủ dữ liệu người dùng thật để đo latency và user satisfaction. Ngoài ra, ticket ẩn danh hiện phụ thuộc vào localStorage: nếu người dùng đổi thiết bị hoặc xóa dữ liệu trình duyệt thì có thể mất khả năng theo dõi. Hệ thống cũng chưa có thông báo khi cán bộ phản hồi sau khi người dùng rời trang.

Đây là blocker về quyết định sản phẩm, không phải lỗi demo. Nhóm cần chọn giữa:

- Giữ trải nghiệm không đăng nhập để giảm friction.
- Thêm email/OTP hoặc mã tra cứu để bảo đảm continuity.

## 8. DOING — Nhóm đang làm gì?

- Hoàn thiện tài liệu demo và benchmark/evaluation.
- Theo dõi deployment production và lỗi tích hợp Vercel–Railway.
- Chuẩn bị đo latency, satisfaction và handover response time.
- Đề xuất thiết kế email/OTP hoặc mã tra cứu ticket.
- Xây dựng roadmap cho proactive journey: checklist hồ sơ, nhắc deadline và bước tiếp theo.

## 9. Hai câu hỏi quan trọng muốn xin mentor định hướng

### Câu hỏi 1 — North-star metric

> Trong giai đoạn tiếp theo, nhóm nên ưu tiên độ tin cậy của câu trả lời hay khả năng thúc đẩy ứng viên hoàn thành hành trình tuyển sinh? Mentor đề xuất north-star metric và ngưỡng tối thiểu nào để nhóm biết sản phẩm đã tạo ra giá trị thật?

### Câu hỏi 2 — Continuity của handover

> Với ticket chuyển cho cán bộ, nhóm nên giữ trải nghiệm không đăng nhập để giảm friction hay dùng email/OTP để bảo đảm người dùng không mất ticket khi đổi thiết bị và nhận được thông báo? Mức đánh đổi về privacy, friction và SLA nào là phù hợp cho MVP?

## 10. Kết luận — 20 giây

> VinUni Guide không cố thay thế cán bộ tuyển sinh. Sản phẩm tự động hóa phần tra cứu có thể kiểm chứng, minh bạch hóa nguồn và chuyển đúng trường hợp sang con người. Thành quả tuần này là nhóm đã có một workflow end-to-end có thể chạy thật; bước tiếp theo là chứng minh bằng dữ liệu người dùng thật rằng workflow đó tạo ra giá trị và đáng tin cậy trong production.

## 11. Link để mentor xem

- Repository branch: `mentor/benchmark-evaluation`
- Frontend: `https://project-ai-peach.vercel.app`
- Backend health: `https://project-ai-production-556f.up.railway.app/health`
- Backend readiness: `https://project-ai-production-556f.up.railway.app/ready`
