# Cơ chế lưu lịch sử, handover và quyền riêng tư

Tài liệu này dùng để giải thích phần lưu lịch sử khi trình bày với mentor.

## Tóm tắt một câu

Hệ thống **không yêu cầu ứng viên tạo tài khoản**: hội thoại chỉ tồn tại ngắn hạn trong tab và RAM; riêng yêu cầu chuyển cán bộ (handover) cùng phản hồi được lưu bền vững trên Railway Volume để người dùng quay lại cùng trình duyệt vẫn xem được.

## Dữ liệu được lưu ở đâu?

| Dữ liệu | Nơi lưu | Thời hạn / mục đích |
|---|---|---|
| Nội dung hiển thị của hội thoại | `sessionStorage` của trình duyệt | Chỉ trong tab hiện tại. Reload trang vẫn còn, đóng tab hoặc xóa dữ liệu web thì mất. |
| Ngữ cảnh hội thoại cho AI | RAM của FastAPI (`SessionStore`) | Tối đa 8 lượt gần nhất, TTL cấu hình 24 giờ. Không phải lịch sử dài hạn. |
| Mã phiên ẩn danh và ID ticket | `localStorage` của trình duyệt | Giữ trong cùng browser profile, kể cả sau khi đóng/mở lại trình duyệt; không lưu toàn bộ nội dung chat. |
| Ticket handover và phản hồi cán bộ | SQLite `app.db` tại Railway Volume `/app/data` | Bền vững qua restart/redeploy, phục vụ theo dõi tiến trình và xử lý nghiệp vụ. |
| Analytics | SQLite `app.db` | Lưu chỉ số vận hành và mã băm của session; bảng metrics không lưu câu hỏi/câu trả lời thô. |

## Luồng của ứng viên

1. Ứng viên chat không cần đăng ký tài khoản.
2. AI chỉ giữ ngữ cảnh ngắn hạn để hiểu câu hỏi tiếp theo; lịch sử hiển thị chỉ nằm trong tab trình duyệt.
3. Khi AI thiếu căn cứ hoặc ứng viên chủ động chọn **Hỏi cán bộ**, ứng viên kiểm tra nội dung và tick đồng ý trước khi gửi.
4. Backend tạo ticket gồm: `ticket_id`, session ẩn danh, câu hỏi đã đồng ý chia sẻ, lý do chuyển, trạng thái, thời gian và phản hồi cán bộ khi có.
5. Frontend chỉ lưu mã phiên ẩn danh có entropy cao và ID ticket vào `localStorage`. Khi ứng viên trở lại trên cùng browser profile, frontend gọi lại ticket thuộc đúng session đó.
6. Trang theo dõi ứng viên tự kiểm tra thay đổi ticket mỗi 5 giây; câu trả lời cán bộ xuất hiện mà không cần reload.

## Luồng của cán bộ

1. Cán bộ vào `/staff` và xác thực bằng mã cán bộ + staff token.
2. Cán bộ xem toàn bộ hàng chờ và nhận một ticket. Khi gửi phản hồi, ticket tự chuyển sang hoàn tất để trạng thái phản ánh đúng kết quả với cả hai bên.
3. Quy tắc ownership: chỉ cán bộ đã nhận ticket mới được gửi phản hồi hoặc đóng ticket; cán bộ khác không thể ghi đè.
4. Hàng chờ được refresh độc lập mỗi 3 giây. Analytics chạy nền mỗi 30 giây và không được phép làm chậm hoặc chặn việc thấy ticket mới.

## Quy ước trạng thái hiển thị

| Trạng thái kỹ thuật | Ứng viên thấy | Cán bộ thấy | Khi nào xảy ra |
|---|---|---|---|
| `waiting` | Đang chờ | Đang chờ | Ứng viên vừa gửi yêu cầu, chưa có cán bộ nhận. |
| `in_progress` | Đang xử lý | Đang xử lý | Cán bộ đã nhận ticket nhưng chưa gửi phản hồi. |
| `resolved` | Đã phản hồi | Đã xử lý | Cán bộ gửi phản hồi; đây là bước hoàn tất ticket. |

Quy ước này tránh tình trạng cán bộ đã trả lời nhưng ứng viên vẫn thấy “Đang xử lý”.

## Vì sao không bị mất ticket sau deploy?

Ticket không chỉ ở bộ nhớ server. SQLite được đặt tại `/app/data/app.db`; Railway Volume được mount đúng tại `/app/data`, vì vậy database vẫn tồn tại sau redeploy hoặc restart. Container cần biến môi trường `RAILWAY_RUN_UID=0` để có quyền ghi volume do Railway mount với quyền `root`.

Mã session ẩn danh cũng được backend tôn trọng khi tiến trình khởi động lại: backend có thể tạo lại state ngữ cảnh trống với chính session ID cũ, nhờ đó không làm mất quyền xem các ticket đã lưu trong database.

## Cơ chế bảo vệ dữ liệu

- Endpoint ứng viên lấy ticket yêu cầu cả `ticket_id` và header `X-Session-ID` khớp với session đã tạo ticket. Không thể liệt kê hoặc đoán ticket của người khác chỉ bằng ID.
- Staff endpoint bắt buộc Bearer token. Ở production, token có thể gắn với mã cán bộ cụ thể để ngăn một tài khoản thao tác dưới tên cán bộ khác.
- Handover yêu cầu consent rõ ràng trước khi lưu/chuyển nội dung cho cán bộ.
- Nút **Xóa hội thoại** chỉ xóa ngữ cảnh chat, không xóa ticket đang chờ của ứng viên.
- Các chỉ số dashboard dùng session hash; không dùng bảng analytics để lưu hội thoại thô.

## Giới hạn cần trình bày trung thực

Không có đăng nhập đồng nghĩa với việc người dùng chỉ khôi phục được ticket trên **cùng browser profile**. Ticket không thể tự xuất hiện khi:

- đổi máy hoặc đổi trình duyệt;
- dùng chế độ ẩn danh;
- xóa site data/localStorage.

Đây là đánh đổi có chủ đích ở MVP: giảm ma sát cho ứng viên và giảm thu thập dữ liệu cá nhân. Nếu triển khai chính thức, phương án tiếp theo là cho ứng viên chọn đăng nhập/SSO hoặc cấp mã tra cứu kèm secret một lần để theo dõi đa thiết bị.

## Câu trả lời ngắn khi mentor hỏi

> “Bọn em tách lịch sử chat và ticket nghiệp vụ. Chat chỉ giữ ngắn hạn trong tab và RAM để giảm lưu dữ liệu không cần thiết. Khi người dùng đồng ý handover, ticket và phản hồi cán bộ mới được lưu vào SQLite trên Railway Volume. Người dùng không cần tài khoản vì browser giữ session ẩn danh và ID ticket; quay lại cùng browser vẫn theo dõi được. Đổi lại, nếu đổi máy hoặc xóa dữ liệu trình duyệt thì không khôi phục được — đây là giới hạn minh bạch của MVP và hướng mở rộng là SSO hoặc mã tra cứu an toàn.”
