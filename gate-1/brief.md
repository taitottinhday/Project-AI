# Trợ lý tuyển sinh X
**Gate G1 — Brief | EDU-12 | Nhóm 1009 | Mã đội T051 | 20/09/2026**

## Bài toán và người dùng
Phòng tuyển sinh Trường đại học X nhận nhiều câu hỏi lặp về ngành học, quy trình, học phí và học bổng trên nhiều kênh. Cán bộ quá tải; ứng viên chờ lâu, thiếu hướng dẫn và có thể bỏ cuộc. Người dùng chính là ứng viên tìm hiểu hoặc chuẩn bị nộp hồ sơ; người dùng thứ hai là cán bộ tuyển sinh tiếp nhận các tình huống cần con người xử lý. Đây là mô tả bài toán được giao, chưa phải kết quả khảo sát của nhóm.

## Giải pháp
Web app với trợ lý AI tư vấn 24/7, tra cứu tài liệu tuyển sinh chính thức bằng RAG và trả lời có trích nguồn. Trợ lý hỗ trợ hội thoại nhiều lượt, hỏi thêm ngành/bậc học quan tâm khi cần, hướng dẫn bước tiếp theo và chuyển cán bộ khi thiếu căn cứ, vượt phạm vi hoặc có nội dung nhạy cảm. Không tự quyết định trúng tuyển, hứa học bổng hay suy diễn học phí, điều kiện và hạn nộp.

## Phạm vi MVP
1. **Ứng viên:** hỏi đáp, xem nguồn và checklist nộp hồ sơ lấy từ tài liệu đã xác minh; ngữ cảnh chỉ giữ trong phiên mặc định.
2. **AI có kiểm soát:** phát hiện ý định, truy xuất + rerank, kiểm tra căn cứ; hỏi làm rõ hoặc từ chối kết luận và đề nghị handover khi cần.
3. **Cán bộ:** đăng nhập, xem hàng chờ handover, nhận xử lý, phản hồi và đóng yêu cầu; ứng viên xem trạng thái bằng mã phiên/yêu cầu.
4. **Đánh giá:** bộ câu hỏi có nhãn và báo cáo answer rate, accuracy, lỗi nghiêm trọng, chi phí và độ trễ.

Nâng cao sau MVP: hồ sơ tự nguyện, nurture có đồng ý, dashboard engagement và caching có kiểm soát phiên bản nguồn. Ngoài phạm vi: nhận hồ sơ chính thức, thanh toán, quyết định tuyển sinh và tích hợp đa kênh ngay ở G1.

## Mục tiêu và cách kiểm chứng
**Answer rate ≥70%**, **accuracy ≥85%** trên bộ test có nhãn được cán bộ xác nhận; **giảm ≥50% câu hỏi trực tiếp cho cán bộ** qua pilot so sánh hai giai đoạn tương đương. Đây là mục tiêu, chưa có số đo đạt. PRD định nghĩa mẫu số và cách đo; không dùng tỷ lệ chatbot trả lời để thay thế KPI giảm tải thực tế.

## Thiết kế và điều kiện triển khai
Next.js chat widget → FastAPI → LangGraph → RAG PostgreSQL/pgvector + reranker → LLM; kho tài liệu có URL, phiên bản, kỳ tuyển sinh và ngày xác minh. Docker/cloud cho giai đoạn triển khai. Cần xác nhận trường X, nguồn tài liệu, cán bộ phụ trách và dữ liệu pilot. Chỉ thu thập dữ liệu cần thiết; không yêu cầu CCCD, điểm cá nhân hay số điện thoại cho hỏi đáp thông thường.

## Thành viên
| Họ tên | Mã học viên |
|---|---|
| Nguyễn Quang Huy | 2A202602820 |
| Lê Văn Tài | 2A202602464 |
| Cao Văn Cường | 2A202602493 |
| Chu Phúc Anh | 2A202602370 |

**Minh chứng G1:** Brief, PRD, wireframe/UI flow. Bản in một trang: `brief.html`. Tài liệu thiết kế chưa chứng minh sản phẩm hoặc AI logging đã chạy.
