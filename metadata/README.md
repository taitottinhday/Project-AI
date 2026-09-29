# Bộ dữ liệu VinUni 2026–2027

Phạm vi: dữ liệu bậc đại học (bao gồm chương trình Bác sĩ Y khoa) để tư vấn tuyển sinh, ngành học, chi phí, quy chế học vụ, đời sống sinh viên và các dịch vụ hỗ trợ.

Mốc kiểm chứng: **2026-09-23**. Chỉ sử dụng nguồn chính thức của VinUni. Giá trị chưa được công bố được để `null`, ghi `not_published` hoặc đưa vào danh sách khoảng trống; không suy đoán.

## Tệp dữ liệu

- `sources/vinuni_official_sources_2026_2027.json`: sổ nguồn và URL kiểm tra lại.
- `programs/vinuni_undergraduate_programs_2026_2027.json`: 11 chương trình, mã ngành, thời lượng, tín chỉ, hướng tập trung và khung chương trình khóa 2026.
- `tuition/vinuni_tuition_undergraduate_2026_2027_clean.json`: học phí, hỗ trợ 35% và quy tắc áp dụng.
- `admissions/vinuni_undergraduate_admissions_2026_2027.json`: đợt tuyển sinh, quy trình, hồ sơ, tiêu chí và chuẩn tiếng Anh.
- `financial_aid/vinuni_financial_aid_and_fees_2026_2027.json`: học bổng, hỗ trợ tài chính, khoản vay, ký túc xá, phí, hoàn phí và ưu đãi thanh toán.
- `academics/vinuni_undergraduate_academic_rules_2026_2027.json`: tín chỉ, tải học, add/drop/withdraw, GPA, cảnh báo, bằng kép, chuyển chương trình, phúc khảo, nghỉ học, tốt nghiệp, GenAI và lịch học.
- `academics/vinuni_undergraduate_minors_2026_2027.json`: 20 minor và nhóm sinh viên đủ điều kiện.
- `student_life/vinuni_student_life_residential_and_services_2026_2027.json`: nội trú, khách, giờ yên tĩnh, hỗ trợ học tập, sức khỏe và dịch vụ.
- `international/vinuni_international_and_global_opportunities_2026_2027.json`: visa, tiếng Việt cho sinh viên quốc tế CHS, trao đổi và internship.
- `governance/vinuni_student_rights_conduct_and_complaints_2026_2027.json`: quyền/nghĩa vụ, kỷ luật, khiếu nại và hỗ trợ tài chính cho sinh viên hiện tại.
- `coverage/vinuni_chatbot_topic_coverage_2026_09_23.json`: ma trận chủ đề đã có, chủ đề động/nội bộ và quy tắc fallback.
- `coverage/vinuni_public_policy_inventory_2026_09_23.json`: kiểm kê các policy liên quan từ Academic Affairs, Student Affairs và External Affairs; phân biệt đã trích xuất, chỉ lập chỉ mục và bị giới hạn nội bộ.
- `quality/vinuni_data_quality_2026_09_22.json`: thứ tự ưu tiên nguồn và các xung đột đã biết (được mở rộng trong audit 23/09/2026).
- `vinuni_undergraduate_2026_2027_manifest.json`: danh sách tệp để ứng dụng/RAG nạp toàn bộ dữ liệu.

## Quy tắc cho chatbot/RAG

1. Trả lời dữ liệu 2026–2027 trước. Dữ liệu năm cũ chỉ dùng cho quy chế thường trực còn hiệu lực hoặc khi người dùng yêu cầu so sánh; luôn nêu năm/phiên bản.
2. Ưu tiên policy/PDF có ngày hiệu lực, sau đó đến curriculum framework đúng khóa, trang hiện hành, thông báo có ngày và cuối cùng là FAQ.
3. Mọi số tiền là VND dưới dạng số nguyên. Trường `derived: true` là phép tính, không phải nguyên văn VinUni.
4. Khi trả lời số tiền, deadline, điều kiện hoặc chế tài, phải kèm URL từ `source_ids` và ngày kiểm chứng.
5. Không biến `draft`, `tentative` hoặc `subject to change` thành thông tin chắc chắn. Lịch học AY26-27 công khai hiện vẫn là bản dự thảo ngày 25/05/2026.
6. Không dùng giá phòng cũ trong FAQ/phụ lục cư trú; dùng Quy định tài chính ngày 22/07/2026.
7. Nếu nguồn công khai chỉ dẫn tới SIS/SharePoint cần đăng nhập, nói rõ đây là dữ liệu nội bộ/động và hướng dẫn đúng đơn vị; không tự điền nội dung.
8. Khi nguồn xung đột, giữ cả dấu vết và trả lời theo nguồn ưu tiên; không hòa trộn.
9. Khi thiếu dữ liệu, trả lời “chưa có nguồn công khai đã kiểm chứng” thay vì dùng kiến thức nền của LLM.

## Kiểm tra cục bộ

Chạy `python scripts/validate_vinuni_data.py` để kiểm tra JSON, source ID, miền chính thức và số chương trình.
