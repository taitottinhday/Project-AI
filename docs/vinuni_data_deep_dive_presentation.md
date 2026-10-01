# Bài thuyết trình chuyên sâu về Data — VinUni Guide

Thời lượng đề xuất: 8–10 phút.

## 1. Mở đầu: Data không chỉ là “thu thập nhiều trang”

> Phần data của VinUni Guide được thiết kế để trả lời một câu hỏi quan trọng: “Thông tin này có đúng, có còn hiệu lực và có thể kiểm chứng được không?”. Vì chatbot tuyển sinh xử lý học phí, deadline, điều kiện và quy chế, một câu trả lời nghe hợp lý nhưng sai nguồn có thể gây thiệt hại cho người dùng. Vì vậy nhóm xây dựng data theo hướng official-only, year-aware và evidence-first.

Thông điệp cần nhấn mạnh:

```text
Nguồn đúng → Dữ liệu có cấu trúc → Evidence có thể truy vết
→ Retrieval đúng ngữ cảnh → Câu trả lời an toàn
```

## 2. Data phải giải quyết bài toán gì?

Một câu hỏi như “Học phí VinUni bao nhiêu?” chưa đủ rõ. Hệ thống cần biết:

- Người dùng hỏi chương trình nào?
- Năm học nào?
- Đây là học phí niêm yết hay học phí sau hỗ trợ?
- Nguồn là policy hiện hành, curriculum PDF, FAQ cũ hay thông báo có ngày?
- Có điều kiện, ngoại lệ hoặc footnote nào không?
- Nếu hai nguồn có con số khác nhau thì nguồn nào được ưu tiên?

Vì vậy, nhóm không gom toàn bộ website thành một đoạn văn lớn. Nhóm xây dựng một knowledge base có phạm vi, schema, source registry, trạng thái và quy tắc an toàn.

## 3. Phạm vi dataset hiện tại

Dataset có manifest tại:

```text
metadata/vinuni_undergraduate_2026_2027_manifest.json
```

Phạm vi chính:

- VinUni bậc đại học.
- Năm học ưu tiên: 2026–2027.
- Bao gồm cả chương trình Bác sĩ Y khoa.
- Ngôn ngữ chính: tiếng Việt; giữ tên tiếng Anh khi là tên chính thức.
- Chỉ sử dụng nguồn chính thức thuộc `vinuni.edu.vn` và các subdomain của trường.
- Mốc kiểm chứng của snapshot hiện tại: 23/09/2026.

Manifest công bố các nhóm dữ liệu sau:

1. Source registry.
2. Chương trình đào tạo.
3. Học phí.
4. Tuyển sinh và hồ sơ.
5. Học bổng, hỗ trợ tài chính và các khoản phí.
6. Quy chế học vụ.
7. Minor.
8. Đời sống và dịch vụ sinh viên.
9. Sinh viên quốc tế và cơ hội toàn cầu.
10. Quyền, nghĩa vụ, kỷ luật và khiếu nại.
11. Ma trận coverage.
12. Policy inventory.
13. Quality audit.

Runtime hiện báo cáo **12 tài liệu dữ liệu, 62 nguồn và 219 evidence chunks**. Trong đó, manifest còn bao gồm các file quản trị như coverage và quality; các file này không phải tất cả đều được coi là câu trả lời applicant-facing.

## 4. Đã lấy data từ đâu?

### 4.1. Source registry

File chính:

```text
metadata/sources/vinuni_official_sources_2026_2027.json
```

Mỗi nguồn có các metadata quan trọng:

- `id`: mã nguồn duy nhất.
- `title`: tên trang hoặc văn bản.
- `url`: đường dẫn gốc để kiểm tra.
- `source_type`: policy, procedure, curriculum, webpage, FAQ...
- `reference_number` hoặc `version`.
- `effective_date` hoặc `published_or_updated`.
- `accessed_at`.
- `warning` nếu nguồn có rủi ro hoặc điều kiện sử dụng.

Dữ kiện trong JSON không lặp lại URL ở mọi record. Dữ kiện chỉ lưu `source_ids`, sau đó hệ thống tra sang source registry. Cách này giúp:

1. Không lặp metadata nguồn.
2. Dễ cập nhật URL, version hoặc warning.
3. Citation được sinh nhất quán.
4. Có thể audit ngược từ câu trả lời về nguồn gốc.

### 4.2. Nhóm nguồn

Nhóm đã rà soát:

- Admissions và trang tuyển sinh.
- Trang chương trình của các College.
- Curriculum framework PDF.
- Financial regulations và tuition tariff.
- Academic Affairs Policy Library.
- Student Affairs Policy Library.
- Student Gateway.
- Thông báo chính thức có ngày.
- FAQ chính thức.

Search engine chỉ được dùng để phát hiện trang. Nội dung đưa vào dataset phải được mở và kiểm chứng từ domain chính thức.

## 5. Quy trình thu thập và chuẩn hóa

### 5.1. Với webpage

1. Xác nhận hostname thuộc allowlist chính thức.
2. Đọc title, phạm vi áp dụng, ngày cập nhật và version.
3. Phân loại trang: policy, curriculum, admissions, announcement hoặc FAQ.
4. Trích các field theo domain tương ứng.
5. Giữ nguyên các trạng thái như `tentative`, `draft`, `subject to change` hoặc `restricted`.
6. Lưu URL, ngày truy cập và source metadata.
7. Gắn `source_ids` vào từng record có sử dụng thông tin.

### 5.2. Với PDF

1. Kiểm tra tên tài liệu, năm học, cohort, mã văn bản, version và ngày hiệu lực.
2. Dùng text layer để tìm kiếm nhanh.
3. Với bảng phức tạp, kiểm tra lại bố cục render để tránh lệch cột.
4. Đọc cả header, merged cell và footnote.
5. Đối chiếu tổng tiền, tổng tín chỉ hoặc thời lượng với phần summary nếu có.
6. Không dùng tên file làm bằng chứng duy nhất.

Điểm cần nói khi mentor hỏi về rủi ro PDF:

> Text extraction chỉ hỗ trợ đọc nhanh, không phải bằng chứng tuyệt đối. Những field nhạy cảm như học phí, mã ngành và tổng tín chỉ phải được đối chiếu lại với bố cục PDF hoặc một nguồn chính thức liên quan.

### 5.3. Chuẩn hóa thành JSON

Mỗi domain có file riêng. Ví dụ:

```text
programs/       → chương trình, thời lượng, tín chỉ
tuition/        → học phí, hỗ trợ, quy tắc áp dụng
admissions/     → vòng tuyển sinh, hồ sơ, tiêu chí
academics/      → GPA, tín chỉ, cảnh báo, phúc khảo
student_life/   → nội trú, sức khỏe, dịch vụ
international/  → visa, trao đổi, internship
```

Các giá trị chưa được công bố không được điền bằng suy đoán. Chúng được biểu diễn bằng `null`, `not_published` hoặc đưa vào coverage gap.

## 6. Từ JSON đến evidence chunks

File thực hiện việc load, chuẩn hóa và tìm kiếm là:

```text
src/services/knowledge_base.py
```

Pipeline runtime:

```text
Manifest + source registry
        ↓
Đọc từng JSON domain
        ↓
Thu thập source_ids
        ↓
Render record thành text có section
        ↓
Tách list/record lớn thành chunk độc lập
        ↓
Gắn flags: draft, conflict, dynamic, restricted...
        ↓
Tokenize và tạo document frequency
        ↓
Search theo token, query expansion và source priority
```

Một evidence chunk có các thành phần:

```text
chunk_id
document
section
text
source_ids
tokens
flags
```

### Vì sao không để một file lớn thành một chunk?

Nếu toàn bộ quy chế học vụ nằm trong một chunk, truy xuất câu hỏi về GPA có thể kéo theo nội dung về nghỉ học, tốt nghiệp hoặc khiếu nại. Chia nhỏ theo record giúp:

- tăng precision khi retrieve;
- tránh trộn hai chương trình;
- cô lập conflict;
- gắn citation đúng field;
- không để dữ liệu restricted làm ảnh hưởng dữ liệu public.

### Cô lập conflict

Nếu một record có xung đột mã ngành hoặc deadline quay lại sau bảo lưu, hệ thống tách phần conflict thành chunk riêng. Phần an toàn vẫn có thể trả lời; phần tranh chấp sẽ bị đánh dấu và không được trả lời chắc chắn.

## 7. Retrieval không chỉ là tìm từ khóa

Khi người dùng hỏi, hệ thống thực hiện các bước:

1. Normalize tiếng Việt: bỏ dấu, chuẩn hóa `đ`, chữ thường và token.
2. Loại stopwords.
3. Mở rộng truy vấn theo alias, ví dụ:
   - “học phí” → tuition, fee, financial;
   - “ký túc xá” → dormitory, housing, residential;
   - “phúc khảo” → grade appeal, appeal.
4. Tính điểm theo token overlap/document frequency.
5. Ưu tiên source type đáng tin cậy hơn.
6. Giữ đúng context năm học và chương trình.
7. Gửi các hit có liên quan vào answer generator.

Điểm quan trọng:

> Query expansion chỉ giúp tìm đúng evidence; nó không được phép tự thêm facts mới vào câu trả lời.

## 8. Từ evidence đến câu trả lời an toàn

File tạo câu trả lời là:

```text
src/services/answer_generator.py
```

Answer generator được ràng buộc bởi các nguyên tắc:

- chỉ dùng evidence được cung cấp;
- không tự tạo học phí, deadline, điều kiện hoặc cam kết kết quả;
- `evidence_ids` phải là chunk thực sự hỗ trợ câu trả lời;
- chọn đúng năm học và cohort;
- giữ cảnh báo draft, tentative, conflict, dynamic hoặc restricted;
- câu hỏi cá nhân về khả năng đỗ, học bổng hoặc hồ sơ không được trả lời chắc chắn.

Nếu evidence thiếu hoặc mâu thuẫn, hệ thống trả về trạng thái insufficient/conflicting để graph chuyển sang clarify hoặc handover.

## 9. Data quality và governance

### 9.1. Quy tắc ưu tiên nguồn

Nhóm ưu tiên theo loại nguồn:

1. Policy PDF chính thức có ngày hiệu lực.
2. Procedure/guideline chính thức.
3. Curriculum đúng cohort.
4. Trang chính thức hiện hành.
5. Announcement có ngày.
6. FAQ chính thức.

Đây không phải quy tắc “nguồn nào xuất hiện sau thì đúng tuyệt đối”. Phải xét thêm phạm vi áp dụng, version và effective date.

### 9.2. Không resolve conflict âm thầm

Ví dụ các loại conflict cần biểu diễn:

- hai mã ngành khác nhau;
- deadline cũ và mới;
- phí phòng trong FAQ cũ khác policy tài chính mới;
- lịch học vẫn là draft;
- thông tin cần đăng nhập trong SIS/SharePoint.

Quy tắc của nhóm:

> Nếu không xác định được nguồn hiện hành một cách có căn cứ, giữ conflict, gắn warning và fallback/handover thay vì chọn một con số cho đẹp.

### 9.3. Dynamic và restricted data

Thông tin cần đăng nhập, dữ liệu cá nhân, quyết định hồ sơ, trạng thái deadline theo thời gian thực hoặc thông tin nội bộ không được đóng băng thành authoritative static fact.

## 10. Validation và monitoring

Các lớp kiểm tra:

### Static validation

- JSON hợp lệ.
- Manifest trỏ đúng file.
- Source ID tồn tại trong registry.
- URL dùng HTTPS và domain chính thức.
- Số chương trình và minor khớp manifest.
- Không có field bắt buộc bị thiếu.

### Runtime readiness

Endpoint `/ready` kiểm tra dataset có load được, fingerprint và ngày verified có hợp lệ hay không.

### Source monitoring

Script:

```text
scripts/check_sources.py
```

Script chỉ đọc source URL, tính digest và tạo change-detection report. Nó không tự động ghi đè production data. Nếu nguồn thay đổi, cần review trước khi approve baseline mới.

### Coverage/evaluation

- Golden questions kiểm tra câu trả lời mong đợi.
- Adversarial questions kiểm tra safety và fail-closed.
- Canonical coverage kiểm tra từng evidence chunk có được truy xuất đúng không.

Kết quả hiện tại của canonical report:

- 113/113 answer coverage cases đạt.
- 5/5 safety cases đạt.
- 101 metadata chunks được audit cấu trúc.
- Không có invalid source mapping trong report đầy đủ.

## 11. Demo riêng cho phần data

Nên demo theo thứ tự sau:

### Demo 1: Từ câu hỏi đến citation

Hỏi:

> Học phí Điều dưỡng năm 2026–2027 là bao nhiêu?

Cho mentor xem:

- query đã được normalize;
- hit thuộc đúng section tuition;
- source ID;
- citation URL;
- năm học và ngày kiểm chứng.

### Demo 2: Câu hỏi không được đoán

Hỏi:

> Em có chắc chắn đậu VinUni không?

Giải thích:

> Không có evidence nào có thể biến thành cam kết cá nhân. Đây là lúc data governance bảo vệ người dùng và bảo vệ uy tín trường.

### Demo 3: Conflict hoặc dynamic data

Hỏi về deadline đã gia hạn hoặc một thông tin đang draft.

Nói:

> Dataset không che conflict. Nó giữ trạng thái và buộc hệ thống làm rõ hoặc chuyển người có thẩm quyền.

## 12. Điểm mạnh của phần data

- Có phạm vi và mốc kiểm chứng rõ.
- Có source registry và citation chain.
- Tách domain thay vì một FAQ khổng lồ.
- Có trạng thái cho draft, conflict, dynamic và restricted.
- Có chính sách không suy đoán giá trị chưa công bố.
- Có fingerprint để nhận biết dataset thay đổi.
- Có coverage matrix, quality audit và evaluation.
- Có thể giải thích ngược từ câu trả lời về chunk, record và URL nguồn.

## 13. Điểm yếu và giới hạn

- Dataset hiện là snapshot; freshness chưa được cập nhật tự động hoàn toàn.
- Thu thập và xử lý conflict vẫn cần review con người.
- PDF layout/OCR vẫn có rủi ro khi bảng phức tạp.
- Chưa phủ hết dữ liệu nội bộ hoặc dữ liệu cá nhân trong SIS/SharePoint.
- Coverage 113/113 chỉ chứng minh các scenario đại diện, không chứng minh mọi cách hỏi tự nhiên.
- Chưa có đủ telemetry production để đo freshness SLA, latency và user satisfaction.

## 14. Hai câu hỏi data nên hỏi mentor

### Câu hỏi 1 — Ngưỡng freshness

> Với các nhóm dữ liệu như học phí và deadline, mentor muốn nhóm đặt SLA freshness như thế nào? Ví dụ: nguồn thay đổi bao lâu phải phát hiện, bao lâu phải review và khi nào chatbot phải chuyển sang trạng thái “chưa xác minh”?

### Câu hỏi 2 — Quyền quyết định khi conflict

> Khi hai nguồn chính thức không thống nhất, nhóm nên xây dựng một data steward/reviewer cố định của từng phòng ban, hay dùng cơ chế ưu tiên theo policy và effective date? Ai là người có thẩm quyền phê duyệt để data được đưa lại vào production?

Hai câu hỏi này biến phần data từ “đã thu thập bao nhiêu” thành bài toán vận hành, trách nhiệm và độ tin cậy lâu dài.

## 15. Lời kết

> Giá trị của phần data không nằm ở việc có nhiều JSON hay nhiều URL. Giá trị nằm ở việc mỗi factual claim đều có nguồn, đúng bối cảnh và có trạng thái khi chưa chắc chắn. Nhờ source registry, schema theo domain, evidence chunks, conflict flags và validation, chatbot không biến phần chưa biết thành câu trả lời chắc chắn. Bước tiếp theo của nhóm là tự động phát hiện thay đổi nguồn, bổ sung review workflow và đo freshness trong production.
