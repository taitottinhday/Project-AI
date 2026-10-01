# VinUni Guide — Bài thuyết trình tổng hợp cho Mentor

Thời lượng đề xuất: 10–12 phút.

## 1. Mở đầu: nhóm đang giải quyết vấn đề gì?

> VinUni Guide là trợ lý tuyển sinh AI cho VinUniversity. Sản phẩm giúp ứng viên tra cứu thông tin chính thức về ngành học, học phí, học bổng, hồ sơ, quy chế học vụ và đời sống sinh viên. Khi AI không đủ căn cứ hoặc câu hỏi mang tính cá nhân, hệ thống chuyển câu hỏi cho cán bộ thay vì tự đoán.

Vấn đề nhóm muốn giải quyết không chỉ là “tìm một câu trả lời nhanh”. Người dùng cần:

- thông tin đúng năm học;
- nguồn để kiểm tra;
- cảnh báo khi dữ liệu chưa chắc chắn;
- một bước tiếp theo khi AI không thể quyết định;
- không phải tự chép lại câu hỏi khi cần liên hệ cán bộ.

Thông điệp sản phẩm:

```text
Trả lời có căn cứ → Nói rõ giới hạn → Chuyển người thật đúng lúc
```

## 2. Tư duy sản phẩm

### Job-to-be-done của ứng viên

> Khi đang tìm hiểu VinUni, tôi muốn có câu trả lời nhanh, có căn cứ và biết bước tiếp theo để không phải tự kiểm tra nhiều trang hoặc lo mình hiểu sai.

### Job-to-be-done của cán bộ

> Khi AI không đủ chắc chắn, tôi muốn nhận được câu hỏi đã có ngữ cảnh, xử lý theo trạng thái rõ ràng và phản hồi mà không bị trùng ticket.

### Nguyên tắc sản phẩm

- **Trust over fluency:** đúng và kiểm chứng được quan trọng hơn nói hay.
- **Fail closed:** thiếu evidence thì làm rõ hoặc chuyển người thật.
- **Low friction:** ứng viên có thể bắt đầu mà chưa cần tạo tài khoản.
- **Human-in-the-loop:** AI hỗ trợ cán bộ, không thay thế quyết định tuyển sinh.
- **Measurable:** chất lượng phải được đo bằng citation, groundedness, safety và coverage.

## 3. Demo sản phẩm

### Luồng 1: Ứng viên hỏi AI

Nhập câu hỏi:

> Học phí Điều dưỡng năm học 2026–2027 là bao nhiêu?

Nói:

> Đây là câu hỏi factual. Hệ thống phải trả lời đúng chương trình, đúng năm học và hiển thị nguồn. Giá trị không chỉ nằm ở con số mà ở khả năng kiểm tra lại con số đó.

Sau đó nhập:

> Hồ sơ của em có chắc chắn đậu VinUni không?

Nói:

> Đây là quyết định cá nhân. AI không có đủ căn cứ để cam kết, nên hệ thống không đoán mà giải thích giới hạn và đề xuất chuyển cán bộ.

### Luồng 2: Cán bộ xử lý handover

1. Ứng viên kiểm tra nội dung và đồng ý chia sẻ.
2. Backend tạo ticket.
3. Ticket xuất hiện ở hàng chờ cán bộ.
4. Cán bộ nhận ticket: `Đang chờ → Đang xử lý`.
5. Cán bộ gửi phản hồi đã xác minh.
6. Ticket chuyển thành `Đã phản hồi`.
7. Màn hình ứng viên tự cập nhật, không cần F5.

Nói:

> Đây là workflow human-in-the-loop hoàn chỉnh. Khi AI không biết, câu hỏi không bị rơi và người dùng không phải bắt đầu lại từ đầu với một email khác.

## 4. Data: nhóm đã lấy và xây dựng dữ liệu như thế nào?

### 4.1. Phạm vi dataset

Manifest:

```text
metadata/vinuni_undergraduate_2026_2027_manifest.json
```

Phạm vi:

- Bậc đại học VinUni, bao gồm Bác sĩ Y khoa.
- Ưu tiên năm học 2026–2027.
- Mốc kiểm chứng snapshot: 23/09/2026.
- Chỉ sử dụng nguồn chính thức thuộc `vinuni.edu.vn` và subdomain.
- Không tự suy đoán giá trị chưa được công bố.

Quy mô runtime hiện tại:

- 12 tài liệu dữ liệu.
- 62 nguồn chính thức.
- 219 evidence chunks.
- 11 chương trình đã xác nhận.
- 20 chương trình minor.

### 4.2. Nguồn dữ liệu

Các nhóm nguồn chính:

- Admissions và trang tuyển sinh.
- Trang chương trình của các College.
- Curriculum framework PDF.
- Financial regulations và tuition tariff.
- Academic Affairs Policy Library.
- Student Affairs Policy Library.
- Student Gateway.
- Thông báo và FAQ chính thức.

Source registry:

```text
metadata/sources/vinuni_official_sources_2026_2027.json
```

Mỗi source có `id`, title, URL, loại nguồn, version, ngày hiệu lực/ngày cập nhật, ngày truy cập và warning nếu cần. Dữ liệu chỉ lưu `source_ids`, sau đó hệ thống tra ngược sang registry để tạo citation.

### 4.3. Quy trình data pipeline

```text
Tìm nguồn chính thức
        ↓
Kiểm tra domain, năm học, version và ngày hiệu lực
        ↓
Chuẩn hóa thành JSON theo domain
        ↓
Gắn source_ids, trạng thái và warning
        ↓
Chia thành evidence chunks
        ↓
Normalize/query expansion/retrieval
        ↓
Trả lời có citation hoặc fallback/handover
```

Các domain được tách riêng gồm chương trình, học phí, admissions, học bổng, quy chế học vụ, minor, đời sống, quốc tế và governance.

### 4.4. Vì sao phải chia evidence chunks?

Một file lớn chứa quá nhiều chủ đề sẽ làm retrieval lấy nhầm thông tin. Chunk theo record giúp:

- truy xuất đúng section;
- không trộn hai chương trình;
- gắn citation chính xác;
- cô lập dữ liệu conflict hoặc restricted;
- kiểm tra coverage theo từng evidence.

Mỗi chunk có:

```text
chunk_id, document, section, text, source_ids, tokens, flags
```

Các flag như `draft`, `tentative`, `conflict`, `dynamic` và `restricted` không bị xóa trong quá trình chuẩn hóa.

### 4.5. Xử lý conflict và dữ liệu động

Nếu hai nguồn chính thức có khác biệt về mã ngành, deadline hoặc học phí, nhóm không âm thầm chọn một con số. Nhóm giữ dấu vết conflict, xét loại nguồn, version, ngày hiệu lực và phạm vi áp dụng.

Thông tin cần đăng nhập, thông tin cá nhân, quyết định hồ sơ hoặc dữ liệu thay đổi theo thời gian thực không được đóng băng thành authoritative static fact.

Nguyên tắc:

> Không xác minh được thì nói rõ chưa có căn cứ và chuyển tới đơn vị có thẩm quyền.

## 5. Kiến trúc kỹ thuật

```text
Next.js trên Vercel
  ├─ Chat ứng viên
  └─ Dashboard cán bộ
          ↓ HTTPS API
FastAPI trên Railway
  ├─ Retrieval + guardrails + citations
  ├─ Handover/ticket service
  ├─ Staff authentication
  └─ Analytics
          ↓
Railway Volume
  └─ SQLite: ticket, reply, analytics, monitor state
```

Các cơ chế vận hành quan trọng:

- Cán bộ polling hàng chờ khoảng 3 giây.
- Ứng viên polling ticket khoảng 5 giây.
- Ticket được lưu bền vững sau restart/redeploy.
- Staff phải nhận ticket trước khi phản hồi.
- CORS giữa domain Vercel và Railway được cấu hình theo domain production.

## 6. Benchmark và evaluation

### 6.1. Benchmark sản phẩm

Nhóm tham khảo các chatbot tuyển sinh như NYUAdmissionsBot, UTSA Rowdy Bot, CSUSB Ask Cody, CSUNny và Georgia State Pounce.

Bài học chính:

- Phân biệt cohort và đối tượng người dùng.
- Public facts nên được AI trả lời; hồ sơ cá nhân cần human/portal.
- Giá trị không chỉ là Q&A mà còn là checklist, nhắc việc và giảm bỏ sót trong hành trình tuyển sinh.

### 6.2. Evaluation nội bộ

- **Golden set:** 17 câu hỏi chuẩn.
- **Adversarial set:** 40 câu hỏi về mơ hồ, sai năm, prompt injection và dữ liệu nhạy cảm.
- **Canonical coverage:** kiểm tra evidence coverage trên toàn bộ dataset.

Kết quả hiện tại:

- 113/113 factual coverage cases đạt.
- 5/5 safety cases đạt.
- 101 metadata chunks được audit.
- Không có invalid source mapping trong full canonical report.

Nói chính xác:

> Đây là kết quả trên các scenario đại diện của dataset, không phải tuyên bố chatbot hiểu mọi câu hỏi ngoài phạm vi dữ liệu. Nhóm vẫn cần đo latency production, user satisfaction và human review.

## 7. DONE — Tuần này nhóm đã làm được gì?

> Tuần này nhóm em đã hoàn thiện luồng end-to-end của VinUni Guide: chatbot trả lời có nguồn, cơ chế không đoán khi thiếu căn cứ, handover tới cán bộ, ticket có trạng thái, tự động cập nhật và lưu lịch sử trên Railway. Nhóm cũng đã triển khai frontend trên Vercel, backend trên Railway, xử lý CORS, xây dựng bộ benchmark/evaluation và chuẩn hóa tài liệu data.

## 8. DOING — Nhóm đang làm gì?

- Theo dõi chất lượng và độ ổn định trên production.
- Bổ sung đo latency, satisfaction và thời gian phản hồi handover.
- Hoàn thiện data freshness monitoring.
- Thiết kế mã tra cứu hoặc email/OTP cho ticket.
- Nghiên cứu proactive journey: checklist hồ sơ, nhắc deadline và bước tiếp theo.

## 9. BLOCKER — Điều gì đang cản trở?

> Nhóm chưa thể chốt KPI production vì chưa có đủ dữ liệu người dùng thật. Ticket ẩn danh hiện phụ thuộc vào localStorage nên người dùng đổi thiết bị hoặc xóa dữ liệu trình duyệt có thể mất khả năng theo dõi. Hệ thống cũng chưa có push notification khi cán bộ phản hồi sau khi người dùng rời trang.

Đây là trade-off sản phẩm giữa:

- giảm friction bằng cách không bắt đăng nhập;
- bảo đảm continuity bằng email/OTP hoặc mã tra cứu.

## 10. Điểm mạnh của sản phẩm

- Factual answer có citation và đúng phạm vi năm học.
- Fail-closed khi thiếu hoặc conflict evidence.
- Handover là workflow thực tế, không chỉ là nút liên hệ.
- Trạng thái ứng viên/cán bộ rõ ràng và tự cập nhật.
- Ticket tồn tại sau redeploy.
- Có source registry, manifest, flags, evaluation và coverage audit.
- Bắt đầu không cần đăng nhập, phù hợp với MVP public-facing.

## 11. Điểm yếu và giới hạn

- Dataset hiện là snapshot, freshness chưa hoàn toàn tự động.
- Review conflict và PDF phức tạp vẫn cần con người.
- Chưa có đủ user data thật để kết luận về satisfaction và latency production.
- Anonymous tracking chưa hỗ trợ tốt cross-device.
- Chưa có notification sau khi ứng viên rời trang.
- Chưa có proactive journey hoàn chỉnh.

## 12. Hai câu hỏi quan trọng nhất dành cho mentor

### Câu hỏi 1 — North-star metric

> Trong giai đoạn tiếp theo, nhóm nên ưu tiên độ tin cậy của câu trả lời hay khả năng thúc đẩy ứng viên hoàn thành hành trình tuyển sinh? Mentor đề xuất north-star metric và ngưỡng tối thiểu nào để xác định sản phẩm đã tạo ra giá trị thật?

### Câu hỏi 2 — Continuity của handover

> Với ticket chuyển cho cán bộ, nhóm nên giữ trải nghiệm không đăng nhập để giảm friction hay dùng email/OTP để bảo đảm người dùng không mất ticket khi đổi thiết bị và nhận được thông báo? Mức đánh đổi về privacy, friction và SLA nào là phù hợp cho MVP?

## 13. Hai câu hỏi data mở rộng

Nếu mentor muốn đi sâu về data, hỏi thêm:

1. Với học phí và deadline, freshness SLA nên là bao lâu từ lúc nguồn thay đổi đến lúc hệ thống phát hiện, review và cập nhật production?
2. Khi hai nguồn chính thức không thống nhất, ai là data owner có quyền phê duyệt nguồn được dùng lại trong production?

## 14. Lời kết

> VinUni Guide không cố thay thế cán bộ tuyển sinh. Sản phẩm tự động hóa phần tra cứu có thể kiểm chứng, minh bạch hóa nguồn và chuyển đúng trường hợp sang con người. Thành quả hiện tại là nhóm đã có một workflow end-to-end và một data pipeline có thể audit. Bước tiếp theo là chứng minh bằng dữ liệu người dùng thật rằng hệ thống vừa chính xác, vừa dễ dùng và tạo ra tác động trong hành trình tuyển sinh.

## 15. Các link tham khảo

- Frontend: `https://project-ai-peach.vercel.app`
- Backend health: `https://project-ai-production-556f.up.railway.app/health`
- Backend readiness: `https://project-ai-production-556f.up.railway.app/ready`
- Branch: `mentor/benchmark-evaluation`
