# Kịch bản demo VinUni Guide cho mentor

## 1. Mở đầu: sản phẩm đang giải quyết vấn đề gì?

> VinUni Guide là trợ lý tuyển sinh accuracy-first. Sản phẩm không cố trả lời mọi câu hỏi bằng mọi giá. Nó trả lời các thông tin công khai khi có nguồn chính thức, hiển thị căn cứ để người dùng kiểm tra, và chuyển cho cán bộ khi câu hỏi mang tính cá nhân hoặc chưa đủ bằng chứng.

Người dùng tuyển sinh thường gặp ba vấn đề:

1. Thông tin nằm rải rác ở nhiều tài liệu, khó tìm và dễ nhầm năm học.
2. Một câu trả lời nghe hợp lý nhưng không có nguồn sẽ không đủ đáng tin đối với học phí, deadline hoặc điều kiện tuyển sinh.
3. Khi AI không biết, người dùng thường bị yêu cầu tự gửi email và mất ngữ cảnh.

VinUni Guide giải quyết theo mô hình:

```text
Tra cứu có nguồn → Nhận diện giới hạn → Chuyển người thật đúng lúc
```

## 2. Nên demo những gì?

Nên demo hai luồng liên tiếp trong khoảng 4–5 phút. Không nên mở quá nhiều màn hình hoặc thử các câu hỏi ngẫu nhiên.

### Luồng A — Ứng viên hỏi AI

**Bước 1: hỏi một câu factual có giá trị cao**

Nhập:

> Học phí Điều dưỡng năm học 2026–2027 là bao nhiêu?

Nói với mentor:

> Ở đây AI không chỉ đưa ra một con số. Câu trả lời phải đi kèm nguồn, đúng năm học và đúng chương trình. Đây là điểm quan trọng vì học phí là thông tin có rủi ro cao nếu trả lời sai.

Cho mentor xem:

- Số tiền và cách diễn giải.
- Citation hoặc tài liệu nguồn.
- Trạng thái đã kiểm chứng nguồn.

**Bước 2: hỏi một câu AI không nên tự quyết định**

Nhập:

> Hồ sơ của em có chắc chắn đậu VinUni không?

Nói:

> Đây không còn là câu hỏi tra cứu. Đây là quyết định cá nhân và dữ liệu hiện có không đủ để cam kết. Sản phẩm chọn không đoán, nói rõ giới hạn và đề xuất chuyển cho cán bộ.

**Bước 3: tạo handover**

- Bấm “Hỏi cán bộ”.
- Kiểm tra và đồng ý chia sẻ nội dung.
- Tạo ticket.

Nói:

> Người dùng không phải tự chép lại câu hỏi hoặc tự tìm email. Ngữ cảnh được chuyển thành một ticket có trạng thái và có thể theo dõi.

### Luồng B — Cán bộ xử lý

Mở khu vực cán bộ và thực hiện:

1. Ticket mới xuất hiện trong hàng chờ.
2. Cán bộ nhận xử lý.
3. Trạng thái chuyển từ “Đang chờ” sang “Đang xử lý”.
4. Cán bộ nhập phản hồi đã xác minh.
5. Gửi phản hồi và hoàn tất ticket.
6. Quay lại màn hình ứng viên để cho thấy trạng thái “Đã phản hồi”.

Nói:

> Đây không phải hộp chat thứ hai tách rời. Đây là workflow human-in-the-loop: AI xử lý câu hỏi có thể tự động hóa, còn cán bộ xử lý phần cần trách nhiệm con người. Trạng thái được đồng bộ tự động nên không cần F5.

## 3. Tư duy sản phẩm

### Job-to-be-done của ứng viên

> “Khi tôi đang tìm hiểu VinUni, tôi muốn có câu trả lời nhanh, có căn cứ và biết bước tiếp theo, để không phải tự kiểm tra nhiều trang hoặc lo mình hiểu sai thông tin.”

### Job-to-be-done của cán bộ

> “Khi AI không đủ chắc chắn, tôi muốn nhận được câu hỏi đã có ngữ cảnh, xử lý theo trạng thái rõ ràng và phản hồi mà không bị trùng ticket.”

### Nguyên tắc thiết kế

- **Trust over fluency:** câu trả lời có căn cứ quan trọng hơn câu trả lời nghe tự nhiên.
- **Fail closed:** thiếu bằng chứng thì làm rõ hoặc handover, không bịa.
- **Low friction:** ứng viên có thể bắt đầu mà chưa cần tạo tài khoản.
- **Human-in-the-loop:** AI không thay thế quyết định tuyển sinh của cán bộ.
- **Đo được:** mọi claim quan trọng phải có test về groundedness, citation và safety.

## 4. Dữ liệu được lấy và xử lý như thế nào?

Nguồn ưu tiên là tài liệu chính thức của VinUni theo đúng năm học, chẳng hạn:

- chương trình đào tạo;
- học phí và chính sách tài chính;
- học bổng;
- quy trình và vòng tuyển sinh;
- quy chế học vụ;
- ký túc xá và đời sống sinh viên;
- trao đổi quốc tế và visa.

Quy trình dữ liệu:

```text
Tài liệu chính thức
        ↓
Kiểm tra năm học, ngày xác minh và nguồn
        ↓
Chuẩn hóa thành evidence chunks
        ↓
Gắn section, source URL và trạng thái an toàn
        ↓
Retriever chọn evidence liên quan
        ↓
Answer generator chỉ trả lời trong evidence đã chọn
```

Dataset hiện tại có **12 tài liệu, 62 nguồn và 219 evidence chunks**. Dữ liệu được tách theo năm học để tránh trộn chính sách cũ với chính sách hiện hành. Những phần chưa xác minh, mâu thuẫn hoặc có tính động không được dùng để tạo câu trả lời factual chắc chắn.

Điểm cần nhấn mạnh:

> Hệ thống không tự lấy một trang web mới rồi coi ngay đó là sự thật. Việc cập nhật dữ liệu phải có bước kiểm tra nguồn và ngày hiệu lực.

## 5. Evaluation và bằng chứng chất lượng

Evaluation được chia thành ba lớp:

1. **Golden set:** 17 câu hỏi chuẩn về ngành, học phí, học bổng và quy trình.
2. **Adversarial set:** 40 câu kiểm tra câu hỏi mơ hồ, sai năm học, prompt injection, dữ liệu cá nhân và yêu cầu cam kết đỗ.
3. **Canonical coverage:** sinh case đại diện từ toàn bộ evidence chunks để kiểm tra hệ thống có truy xuất đúng nguồn hay không.

Kết quả hiện tại:

- 113/113 factual coverage cases đạt.
- 5/5 safety cases đạt.
- 101 chunks metadata được audit cấu trúc.
- Toàn bộ test backend hiện tại đã pass.

Nói chính xác với mentor:

> 113/113 là kết quả trên các scenario đại diện của dataset, không phải tuyên bố rằng chatbot hiểu mọi câu hỏi ngoài phạm vi dữ liệu. Các chỉ số cần bổ sung là latency production, user satisfaction và human review trên câu hỏi thực tế.

## 6. Điểm mạnh của sản phẩm

- Trả lời có nguồn và có thể kiểm chứng.
- Phân biệt được factual question với câu hỏi cần con người quyết định.
- Có handover thực sự, không chỉ hiện một email liên hệ.
- Ticket được lưu trên backend và có trạng thái rõ ràng.
- Ứng viên và cán bộ thấy cùng một trạng thái nghiệp vụ phù hợp với vai trò.
- Có benchmark, golden set, adversarial test và coverage audit thay vì chỉ demo vài câu hỏi đẹp.
- Giảm rào cản ban đầu vì ứng viên chưa cần đăng nhập để hỏi.

## 7. Điểm yếu và giới hạn hiện tại

- Theo dõi ẩn danh hiện phụ thuộc vào browser storage; đổi máy hoặc xóa dữ liệu có thể mất khả năng tìm lại ticket.
- Đồng bộ đang dùng polling, chưa phải realtime notification hoặc push notification.
- Chưa có email/SMS opt-in khi cán bộ phản hồi sau khi ứng viên rời trang.
- Chưa có dữ liệu người dùng thật đủ lớn để kết luận về satisfaction và latency production.
- Chưa có proactive journey như checklist hồ sơ, nhắc deadline hoặc bước tiếp theo theo từng cohort.
- Phạm vi dữ liệu hiện tập trung vào thông tin tuyển sinh VinUni; câu hỏi cá nhân hoặc thông tin thay đổi theo thời gian vẫn cần handover.

Không nên che giấu các giới hạn này. Đây là cơ sở để chọn roadmap và KPI tiếp theo.

## 8. Hai câu hỏi tâm đắc nhất muốn hỏi mentor

### Câu hỏi 1 — Chọn giá trị sản phẩm ưu tiên

> Với giai đoạn tiếp theo, nhóm nên ưu tiên “trust” hay “conversion”: tiếp tục đầu tư vào độ mới của nguồn, citation và evaluation; hay xây dựng proactive admissions journey gồm checklist hồ sơ, nhắc deadline và bước tiếp theo? Mentor sẽ chọn một north-star metric nào để chứng minh sản phẩm tạo giá trị thật?

Lý do câu hỏi này quan trọng: một sản phẩm có thể trả lời đúng nhưng chưa chắc giúp ứng viên hoàn thành hồ sơ. Nhóm cần biết nên tối ưu chất lượng trả lời hay tác động đến hành trình tuyển sinh trước.

### Câu hỏi 2 — Thiết kế danh tính và continuity cho handover

> Với handover, mentor đánh giá lựa chọn nào phù hợp hơn cho MVP: giữ trải nghiệm không đăng nhập nhưng chỉ theo dõi được trên cùng trình duyệt, hay dùng email/OTP để bảo đảm ứng viên luôn nhận lại được ticket và phản hồi? Mức đánh đổi về friction, privacy và SLA phản hồi nào là chấp nhận được?

Lý do câu hỏi này quan trọng: đây là điểm giao giữa trải nghiệm người dùng, bảo mật và giá trị thực của human handover.

## 9. Lời kết demo

> VinUni Guide không cố thay thế cán bộ tuyển sinh. Sản phẩm tự động hóa phần tra cứu có thể kiểm chứng, minh bạch hóa nguồn và chuyển đúng trường hợp sang con người. Giá trị cốt lõi không phải là trả lời được nhiều nhất, mà là giúp ứng viên biết khi nào có thể tin câu trả lời và luôn có một bước tiếp theo an toàn khi AI không đủ chắc chắn.

## 10. Câu trả lời dự phòng khi mentor hỏi

**“Tại sao không cho AI trả lời tất cả?”**

> Vì học phí, deadline và quyết định tuyển sinh có chi phí sai cao. Một câu trả lời không biết nhưng nói chắc chắn nguy hiểm hơn việc thừa nhận giới hạn và chuyển cho cán bộ.

**“113 câu có phải giới hạn của chatbot không?”**

> Không. 113 là số scenario đại diện dùng để đo coverage. Mỗi evidence chunk có thể hỗ trợ nhiều cách hỏi khác nhau; giới hạn thực tế là phạm vi và độ mới của knowledge base.

**“Sản phẩm khác FAQ ở đâu?”**

> Khác ở ba điểm: có retrieval và citation, có guardrail khi thiếu evidence, và có workflow handover lưu trạng thái từ AI sang cán bộ rồi trả kết quả lại cho ứng viên.

**“Nếu được thêm một tính năng, bạn chọn gì?”**

> Tôi ưu tiên continuity có consent: mã tra cứu hoặc email/OTP để ứng viên không mất ticket khi đổi thiết bị, sau đó mới mở rộng notification và proactive journey.
