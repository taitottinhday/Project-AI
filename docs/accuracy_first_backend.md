# Hướng dẫn hệ thống accuracy-first

## 1. Phạm vi đã làm

Hệ thống hiện hỗ trợ các chức năng cốt lõi cho hai vai trò:

- Ứng viên hỏi về ngành, học phí, học bổng, tuyển sinh, học vụ, ký túc xá,
  visa, trao đổi và các chủ đề có trong dataset VinUni 2026–2027.
- Mỗi câu trả lời thành công trả nguồn, mục nguồn, ngày/phiên bản nếu registry có
  và confidence của bước truy xuất.
- Câu hỏi mơ hồ được hỏi lại; câu ngoài phạm vi bị từ chối; câu yêu cầu dự đoán
  kết quả cá nhân hoặc thông tin chưa công khai được chuyển cán bộ.
- Ứng viên có thể tạo ticket handover khi đồng ý chia sẻ nội dung.
- Cán bộ có thể xem hàng đợi, nhận ticket, phản hồi và đóng ticket.

Frontend Next.js đã có ba màn hình: trang giới thiệu và trạng thái kho dữ liệu,
chat cho ứng viên, cùng hàng chờ cho cán bộ. Deploy cloud chưa nằm trong phần đã
hoàn thành.

## 2. Dữ liệu được dùng như thế nào

Ứng dụng không quét toàn bộ thư mục rồi coi mọi JSON là đúng. Nó chỉ đọc các
file được khai báo trong manifest canonical:

`metadata/vinuni_undergraduate_2026_2027_manifest.json`

Khi khởi động, hệ thống:

1. Nạp source registry và manifest.
2. Chỉ nạp file nằm trong manifest.
3. Chia các record độc lập thành evidence chunk riêng.
4. Loại chunk không ánh xạ được tới source ID chính thức.
5. Gắn cờ dữ liệu draft, tentative, conflict, unresolved, restricted và dynamic.
6. Tạo chỉ mục lexical có IDF và mở rộng từ đồng nghĩa Việt–Anh.

Endpoint kiểm tra:

```text
GET /api/v1/knowledge/status
```

Dataset hiện tại báo 12 tài liệu canonical, 62 nguồn và 219 chunks, verified as
of 2026-09-23.

## 3. Cách hệ thống tránh trả lời sai

Ba lớp kiểm soát chạy độc lập:

### Trước khi truy xuất

- Phát hiện prompt injection.
- Không hứa trúng tuyển hoặc học bổng.
- Không bịa chỉ tiêu 2026–2027 khi chưa có nguồn công khai đã kiểm chứng.
- Không tự trả lời câu ngoài phạm vi VinUni.
- Hỏi lại nếu người dùng nói “ngành này/chương trình đó” nhưng không có ngữ cảnh.

### Trong khi truy xuất

- Lọc tài liệu theo intent.
- Ưu tiên policy/curriculum có ngày và phiên bản hơn FAQ.
- Rerank theo chủ đề cụ thể để tránh câu hỏi học phí lấy nhầm phần loại trừ hoặc
  câu visa lấy nhầm dữ liệu trao đổi.
- Không trả lời nếu điểm retrieval dưới ngưỡng.

### Sau khi tạo câu trả lời

- Schema đầu ra bắt buộc có answer, evidence IDs và support status.
- Evidence ID lạ bị chặn.
- Mọi số từ hai chữ số trở lên phải xuất hiện trong evidence đã chọn; khác cách
  viết dấu chấm/phẩy vẫn được chuẩn hóa trước khi so sánh.
- Evidence `unresolved`, `not_publicly_verified`, `restricted` hoặc `dynamic`
  không được dùng để khẳng định factual answer.
- Nếu model báo nguồn thiếu/mâu thuẫn, câu trả lời bị thay bằng thông báo an toàn
  và handover.

Khi có API key, model dùng Structured Outputs để bám schema. Schema chỉ kiểm
soát hình dạng đầu ra, không bảo đảm nội dung đúng, nên validator phía sau vẫn
bắt buộc. Tài liệu tham khảo: <https://developers.openai.com/api/docs/guides/structured-outputs>.

## 4. API chính

### Chat

```http
POST /api/v1/chat
Content-Type: application/json

{
  "message": "Học phí Bác sĩ Y khoa năm 2026-2027 bao nhiêu?",
  "session_id": null
}
```

Các trạng thái trả về:

- `answered`: có evidence, citation và `grounded=true`.
- `needs_clarification`: thiếu ngữ cảnh hoặc yêu cầu bị chặn.
- `handover_suggested`: cần người có thẩm quyền xác nhận.
- `insufficient_evidence`: ngoài phạm vi hoặc retrieval không đủ.

Frontend hiển thị cả trạng thái, nguồn, cảnh báo và nút “Chuyển cán bộ” khi
`handover_recommended=true`, không chỉ hiển thị text.

### Handover

```http
POST /api/v1/handover
Content-Type: application/json

{
  "session_id": "<session từ chat>",
  "question": "Câu hỏi cần cán bộ xác nhận",
  "reason": "personal_case",
  "consent": true,
  "contact": null
}
```

Staff endpoints yêu cầu:

```http
Authorization: Bearer <STAFF_API_TOKEN>
```

## 5. Chạy local

```powershell
Set-Location "D:\project AI\P-051"
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn src.main:app --reload --port 8000
```

Nếu muốn giữ terminal tại `D:\project AI`, dùng lệnh tương đương:

```powershell
python -m uvicorn src.main:app --app-dir P-051 --reload --reload-dir P-051 --port 8000
```

`OPENAI_API_KEY` là tùy chọn cho local. Không có key, hệ thống dùng deterministic
fallback để demo và test mà không gọi model. Production nên đặt
`REQUIRE_LLM_FOR_ANSWERS=true` nếu không muốn fallback.

`STAFF_API_TOKEN` phải được đặt thì staff queue mới mở.

Trong terminal thứ hai, chạy frontend:

```powershell
Set-Location "D:\project AI\P-051\frontend"
Copy-Item .env.example .env.local
npm install
npm run dev
```

Mở <http://localhost:3000/chat> cho ứng viên hoặc
<http://localhost:3000/staff> cho cán bộ. Giá trị token cán bộ nhập trên giao
diện phải trùng `STAFF_API_TOKEN` của backend.

Chạy Docker Compose từ thư mục `P-051` sẽ mount dataset ở `metadata/`
vào container ở chế độ chỉ đọc:

```powershell
docker compose up --build
```

## 6. Kiểm thử và đánh giá

```powershell
python -m pytest -q
python scripts/evaluate.py
python scripts/evaluate.py --dataset eval/adversarial_questions.json
python scripts/evaluate_canonical_coverage.py --strict
python scripts/evaluate.py --verbose
```

Bộ test kỹ thuật kiểm tra loading, source mapping, route an toàn, prompt
injection, số liệu bịa, ticket ownership và vòng đời handover.

Golden set hiện có 17 tình huống; adversarial set có 40 tình huống. Baseline hiện tại:

- 17/17 case đạt rule đã gán nhãn.
- 12/12 câu thuộc phạm vi được trả lời có grounding và citation.
- 5/5 case cần hỏi lại, từ chối hoặc handover được route an toàn.
- 40/40 adversarial case đạt hành vi an toàn đã gán nhãn, bao gồm câu mơ hồ, câu ngoài
  phạm vi, prompt injection, yêu cầu dữ liệu live và yêu cầu cam kết cá nhân.
- Canonical coverage gate kiểm tra 219/219 chunk: 113/113 scenario factual dùng đúng
  evidence chunk, 5/5 scenario có trạng thái rủi ro không trả lời factual, và 101 chunk
  metadata chỉ được audit cấu trúc (không dùng làm evidence trả lời ứng viên).

Canonical coverage là kiểm tra theo một cách diễn đạt đại diện trên từng chunk, không phải
chứng minh đúng cho mọi paraphrase hoặc accuracy production. Đây là kết quả trên bộ test nhỏ, không phải tuyên bố accuracy production hay
cam kết đúng 100%. Trước demo chính thức nên mở rộng tối thiểu 100 câu do người
khác trong nhóm gán nhãn, bao gồm paraphrase, typo, câu nhiều ý, câu mâu thuẫn,
prompt injection và dữ liệu sau khi policy thay đổi.

## 7. Việc cần làm trước production

1. Gán nhãn bộ eval tối thiểu 100–200 câu và khóa test set để tránh chỉnh code
   theo đáp án.
2. Thêm retrieval precision@k, citation correctness, answer correctness và tỷ
   lệ handover sai; không chỉ đo answer rate.
3. Lên lịch chạy `scripts/check_sources.py` và chỉ cập nhật canonical data sau human review,
   sau đó chạy regression eval.
4. Thay token bằng SSO/JWT/RBAC, đưa rate limit ra shared gateway và thêm audit log.
5. Đưa session và queue sang storage phù hợp khi chạy nhiều instance.
6. Kiểm thử accessibility và end-to-end bằng trình duyệt thật trước khi deploy.
7. Human evaluation các câu nhạy cảm trước khi deploy công khai.
