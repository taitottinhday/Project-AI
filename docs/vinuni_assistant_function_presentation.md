# Thuyết trình chức năng VinUni Guide

## 1. Mở đầu — nhóm đang giải quyết vấn đề gì?

Nhóm xây dựng **VinUni Guide**, trợ lý tuyển sinh AI cho VinUniversity. Sản phẩm giúp ứng viên tra cứu nhanh các thông tin như ngành học, học phí, học bổng, quy trình hồ sơ, đời sống sinh viên và quy định liên quan.

Điểm định hướng của nhóm không phải là trả lời thật nhiều, mà là **trả lời có căn cứ**:

- Chỉ trả lời factual khi tìm được dữ liệu trong kho tài liệu chính thức đã kiểm chứng.
- Hiển thị nguồn để người dùng tự đối chiếu.
- Nếu thiếu căn cứ, câu hỏi cá nhân hoặc chính sách chưa chắc chắn, hệ thống không đoán mà chuyển sang cán bộ tuyển sinh.

Sản phẩm có hai luồng chính: **ứng viên** và **cán bộ tuyển sinh**.

---

## 2. Các chức năng chính

### Cho ứng viên

1. **Chat hỏi đáp tuyển sinh**
   - Hỏi bằng tiếng Việt tự nhiên về ngành, học phí, học bổng, hồ sơ, ký túc xá, trao đổi quốc tế...
   - Hỗ trợ hội thoại nhiều lượt trong phạm vi ngữ cảnh ngắn hạn.

2. **Câu trả lời grounded kèm nguồn**
   - Mỗi câu trả lời factual hiển thị nguồn/đường dẫn tài liệu VinUni tương ứng.
   - Có trạng thái: đã kiểm chứng nguồn, cần làm rõ, nên chuyển cán bộ, hoặc chưa đủ căn cứ.

3. **Guardrail chống trả lời mơ hồ hoặc bịa**
   - Không tự suy đoán điều kiện, hạn nộp, học phí hoặc kết quả hồ sơ khi dữ liệu chưa đủ.
   - Cảnh báo dữ liệu cũ, xung đột nguồn, yêu cầu mang tính cá nhân và dữ liệu nhạy cảm.

4. **Handover đến cán bộ**
   - Ứng viên chủ động chuyển câu hỏi cho cán bộ hoặc được hệ thống đề xuất chuyển khi AI không đủ căn cứ.
   - Người dùng phải xem nội dung và đồng ý trước khi gửi.
   - Có thể để lại email/số điện thoại, nhưng không bắt buộc.

5. **Theo dõi phản hồi không cần tài khoản**
   - Ticket được cập nhật tự động; ứng viên không cần tải lại trang.
   - Quay lại cùng trình duyệt vẫn theo dõi được trạng thái và phản hồi cán bộ.

### Cho cán bộ tuyển sinh

1. **Khu vực cán bộ có xác thực**
   - Cán bộ đăng nhập bằng mã cán bộ và staff token.
   - Endpoint staff không công khai cho ứng viên.

2. **Hàng chờ handover**
   - Xem các yêu cầu theo trạng thái: tất cả, đang chờ, đang xử lý, đã xử lý.
   - Hàng chờ tự đồng bộ mỗi 3 giây, không cần refresh trang.

3. **Nhận xử lý, phản hồi và hoàn tất ticket**
   - Cán bộ nhận ticket trước khi phản hồi.
   - Chỉ cán bộ đã nhận ticket được phản hồi; tránh hai người trả lời chồng chéo.
   - Khi gửi phản hồi, ticket tự hoàn tất.

4. **Dashboard vận hành**
   - Theo dõi số ticket theo trạng thái.
   - Xem các chỉ số như lượt hỏi, answer rate, grounded compliance, handover rate, feedback, cache hit và độ trễ.
   - Analytics cập nhật nền, không được làm chậm hàng chờ ticket.

---

## 3. Luồng 1 — Ứng viên hỏi AI

```text
Ứng viên đặt câu hỏi
        ↓
AI hiểu ý định và tìm evidence trong kho dữ liệu chính thức
        ↓
Evidence đủ, hợp lệ?
 ├─ Có  → Trả lời + citation + cảnh báo nếu cần
 └─ Không → Nêu rõ giới hạn, không đoán
                 ↓
           Đề xuất/chủ động handover tới cán bộ
```

### Ví dụ demo

> “VinUni có những ngành đại học nào?”

Hệ thống trả lời dựa trên dữ liệu chương trình đã kiểm chứng và hiển thị nguồn.

> “Hồ sơ của em có chắc chắn đỗ không?”

Đây là câu hỏi cá nhân và không thể cam kết. Hệ thống không trả lời bừa; hệ thống giải thích giới hạn và mở luồng hỏi cán bộ.

### Khi tạo handover

```text
Ứng viên bấm “Hỏi cán bộ”
        ↓
Kiểm tra/chỉnh sửa nội dung cần chuyển
        ↓
Đồng ý chia sẻ nội dung
        ↓
Backend tạo ticket trên database
        ↓
Ứng viên theo dõi trạng thái tự động
```

---

## 4. Luồng 2 — Cán bộ xử lý ticket

```text
Ticket mới được tạo
        ↓
Trạng thái: Đang chờ
        ↓
Cán bộ nhận xử lý
        ↓
Trạng thái: Đang xử lý
        ↓
Cán bộ gửi phản hồi đã xác minh
        ↓
Ticket tự hoàn tất
        ↓
Ứng viên tự thấy “Đã phản hồi”
```

### Quy ước trạng thái

| Trạng thái database | Ứng viên thấy | Cán bộ thấy | Ý nghĩa |
|---|---|---|---|
| `waiting` | Đang chờ | Đang chờ | Chưa có cán bộ nhận yêu cầu. |
| `in_progress` | Đang xử lý | Đang xử lý | Cán bộ đã nhận nhưng chưa gửi phản hồi. |
| `resolved` | Đã phản hồi | Đã xử lý | Cán bộ đã gửi phản hồi; ticket hoàn tất. |

Điểm cần nhấn mạnh: trạng thái phía ứng viên và cán bộ dùng ngôn ngữ khác nhau nhưng phản ánh cùng một trạng thái nghiệp vụ. Ví dụ `resolved` nghĩa là ứng viên đã nhận phản hồi, còn cán bộ đã xử lý xong.

---

## 5. Cơ chế đồng bộ và lưu lịch sử

### Đồng bộ không cần tải lại trang

- Hàng chờ cán bộ gọi API nền mỗi **3 giây**.
- Màn hình theo dõi của ứng viên gọi API nền mỗi **5 giây**.
- Vì vậy ticket mới hoặc phản hồi mới tự xuất hiện; không cần F5 cho mỗi thao tác.

### Lưu lịch sử có giới hạn

| Thành phần | Cách lưu |
|---|---|
| Nội dung chat trên UI | `sessionStorage`, chỉ trong tab hiện tại. |
| Ngữ cảnh AI | RAM backend, tối đa 8 lượt và TTL 24 giờ. |
| Session ẩn danh + ID ticket | `localStorage`, giữ trên cùng browser profile. |
| Ticket và phản hồi cán bộ | SQLite `app.db` trên Railway Volume `/app/data`, bền vững sau deploy/restart. |

Không cần tài khoản giúp ứng viên bắt đầu nhanh. Đổi lại, nếu đổi máy, đổi trình duyệt, dùng ẩn danh hoặc xóa dữ liệu web thì không thể tự khôi phục ticket. Hướng mở rộng phù hợp là SSO/đăng nhập hoặc mã tra cứu an toàn đa thiết bị.

---

## 6. Kiến trúc ngắn gọn

```text
Next.js trên Vercel
  ├─ Trang chat cho ứng viên
  └─ Dashboard cho cán bộ
           ↓ HTTPS API
FastAPI trên Railway
  ├─ RAG + guardrails + source citations
  ├─ Ticket/handover service
  ├─ Authentication cho staff
  └─ Analytics service
           ↓
Railway Volume /app/data
  └─ SQLite: ticket, phản hồi, analytics, monitor state
```

---

## 7. Bảo vệ chất lượng và an toàn

- Dữ liệu tuyển sinh được tổ chức theo năm học, nguồn và trạng thái kiểm chứng.
- Có citation để người dùng và cán bộ đối chiếu.
- Khi data thiếu, mâu thuẫn, quá hạn kiểm chứng hoặc không nằm trong phạm vi, hệ thống fail closed/handover thay vì suy đoán.
- Handover cần consent rõ ràng.
- Ticket ứng viên chỉ đọc được khi có đúng `ticket_id` và session ẩn danh sở hữu ticket.
- Staff token gắn với mã cán bộ để tránh giả danh hoặc thao tác chồng chéo.

---

## 8. Kịch bản demo 2–3 phút

1. Mở trang chat ứng viên, hỏi một câu factual, ví dụ: “VinUni có những ngành đại học nào?”
2. Chỉ cho mentor thấy câu trả lời và citation nguồn.
3. Hỏi câu ngoài phạm vi/cá nhân, ví dụ: “Hồ sơ của em có chắc chắn đỗ không?”
4. Cho thấy AI từ chối cam kết và đề xuất chuyển cán bộ.
5. Tạo handover, đồng ý chia sẻ nội dung.
6. Mở trang cán bộ: ticket xuất hiện tự động, cán bộ nhận xử lý.
7. Cán bộ nhập phản hồi và gửi.
8. Quay lại trang ứng viên: trong tối đa 5 giây trạng thái đổi thành **Đã phản hồi** và nội dung phản hồi xuất hiện.

## 9. Câu kết khi thuyết trình

> “MVP của nhóm không cố thay thế cán bộ tuyển sinh. Phần AI xử lý các câu hỏi phổ biến có dữ liệu chính thức và có trích nguồn; các tình huống thiếu căn cứ hoặc mang tính cá nhân được chuyển đúng lúc cho con người. Nhờ đó sản phẩm giảm tải câu hỏi lặp lại nhưng vẫn ưu tiên độ chính xác, minh bạch và trách nhiệm.”
