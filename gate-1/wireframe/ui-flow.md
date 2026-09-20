# UI Flow — EDU-12
Nhóm 1009 · T051 · Gate G1 · 20/09/2026

Đây là thiết kế đề xuất, chưa kết nối backend. Mở `index.html` bằng trình duyệt để xem các màn hình và thử thao tác minh họa. Nội dung nguồn, ticket và cán bộ đều là dữ liệu minh họa; không có thông tin tuyển sinh thật.

```mermaid
flowchart TD
    A[W01: Ứng viên mở chat] --> B[Nhập câu hỏi / chọn ngành, kỳ]
    B --> C{Đầu vào hợp lệ?}
    C -->|Không| D[Thông báo cần nhập lại]
    D --> B
    C -->|Có| E[Đang xử lý]
    E --> F{Đủ thông tin và căn cứ?}
    F -->|Cần làm rõ| G[Hỏi ngành / kỳ còn thiếu]
    G --> B
    F -->|Có| H[Trả lời kèm nguồn và bước tiếp theo]
    H --> B
    F -->|Không / nhạy cảm| I[Thông báo giới hạn]
    E -->|Lỗi hệ thống| J[Thông báo lỗi + thử lại]
    J --> B
    I --> K[W02: Xem trước nội dung handover]
    H -->|Người dùng yêu cầu| K
    K --> L{Đồng ý chuyển?}
    L -->|Hủy| A
    L -->|Có| M[W03: Mã yêu cầu và trạng thái chờ]
    L -->|Gửi lỗi| N[Báo chưa gửi + thử lại]
    N --> K
    O[W04: Cán bộ đăng nhập] --> P{Được phân quyền?}
    P -->|Không| Q[Báo lỗi đăng nhập / không có quyền]
    P -->|Có| R[W05: Hàng chờ]
    R --> S[W06: Xem chi tiết và nhận xử lý]
    S --> T[Phản hồi rồi đóng yêu cầu]
    T --> U[Ứng viên xem phản hồi trong W03]
    M --> U
```

| Màn hình | Nội dung và hành động | Yêu cầu PRD |
|---|---|---|
| W01 Chat | Gợi ý chủ đề; ngữ cảnh tự chọn; câu hỏi; loading; nguồn; fallback; retry | FR-01–05, FR-08 |
| W02 Handover | Tóm tắt có thể sửa; liên hệ tùy chọn; đồng ý; gửi/hủy | FR-06 |
| W03 Theo dõi | Ticket và trạng thái chờ/đang xử lý/đã giải quyết; phản hồi | FR-06–07 |
| W04 Đăng nhập | Tài khoản cán bộ; lỗi xác thực; không có quyền | FR-07 |
| W05 Hàng chờ | Danh sách tối thiểu, trạng thái, hàng chờ trống | FR-07 |
| W06 Chi tiết | Tóm tắt đã đồng ý chia sẻ; nhận xử lý; phản hồi; đóng | FR-07 |

## Cách duyệt prototype
1. Ở Chat, chọn trạng thái minh họa rồi gửi một câu hỏi. Các trạng thái không gọi AI.
2. Chọn “Chuyển cán bộ”, xem/sửa tóm tắt, đánh dấu đồng ý rồi gửi để thấy mã yêu cầu.
3. Mở “Cán bộ”, vào hàng chờ demo, nhận xử lý, nhập phản hồi và đóng.
4. Mở “Theo dõi” để xem trạng thái/phản hồi được cập nhật trong bộ nhớ trang.

Prototype không xác thực thật, không lưu dữ liệu sau tải lại, không gửi mạng. Bản sản phẩm phải thực thi phân quyền server và chính sách lưu trữ trong PRD. Link nguồn chính thức và SLA cán bộ chỉ được bổ sung khi trường xác nhận.
