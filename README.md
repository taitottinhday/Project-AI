# VinUni Admissions Assistant — Accuracy-First RAG

Ứng dụng web hai vai trò cho trợ lý tuyển sinh VinUni, ưu tiên độ chính xác:
chỉ trả lời khi có evidence trong bộ dữ liệu chính thức, hiển thị citation,
chặn số liệu không được chứng minh và chuyển cán bộ khi nguồn thiếu, mâu thuẫn
hoặc không công khai.

- Ứng viên: chat nhiều lượt, xem nguồn/cảnh báo, đánh giá câu trả lời, tạo handover có consent và theo dõi phản hồi.
- Cán bộ: đăng nhập bằng staff token, xem metric 30 ngày, lọc hàng chờ, nhận, phản hồi và đóng ticket.
- Trang chủ: kiểm tra trực tiếp trạng thái, năm học và quy mô kho dữ liệu từ backend.
- Guardrail: chặn cam kết hồ sơ, số liệu thiếu nguồn, prompt injection và dữ liệu cá nhân phổ biến.
- Cache: chỉ lưu câu đầu phiên đã grounded, có TTL và namespace theo version dataset.
- Web: <http://localhost:3000> · Chat: <http://localhost:3000/chat> · Staff: <http://localhost:3000/staff>
- Swagger: <http://localhost:8000/docs>
- Chạy test: `python -m pytest -q`
- Chạy golden eval: `python scripts/evaluate.py`
- Chạy adversarial safety eval: `python scripts/evaluate.py --dataset eval/adversarial_questions.json`
- Chạy canonical coverage gate (toàn bộ chunk, strict): `python scripts/evaluate_canonical_coverage.py --strict`
- Kiểm tra thay đổi URL nguồn chính thức (không tự cập nhật fact): `python scripts/check_sources.py`
- Chạy quality pipeline: `python scripts/evaluate_quality.py`; thêm `--judge` khi đã cấu hình API key.
- Tài liệu vận hành: [`docs/accuracy_first_backend.md`](docs/accuracy_first_backend.md)
- Kiến trúc: [`ARCHITECTURE.md`](ARCHITECTURE.md)

## Chạy nhanh trên Windows

Terminal 1 — backend:

```powershell
Set-Location "D:\project AI\P-051"
Copy-Item .env.example .env
# Dataset canonical đã nằm tại .\metadata trong repository. Chỉ đổi KNOWLEDGE_BASE_DIR
# khi dùng một bản dữ liệu khác đã được duyệt.
# Đặt STAFF_API_TOKEN trong .env nếu cần dùng màn hình cán bộ.
python -m pip install -r requirements.txt
python -m uvicorn src.main:app --reload --port 8000
```

Terminal 2 — frontend:

```powershell
Set-Location "D:\project AI\P-051\frontend"
Copy-Item .env.example .env.local
npm install
npm run dev
```

Token nhập tại `/staff` phải trùng với `STAFF_API_TOKEN` trong file `.env` của
backend. Frontend chỉ giữ token trong `sessionStorage` của tab hiện tại.

Hoặc chạy cả hai dịch vụ bằng Docker:

```powershell
docker compose up --build
```

Docker mount canonical dataset ở chế độ chỉ đọc. Backend chỉ được đánh dấu healthy khi
`GET /ready` xác nhận dữ liệu còn trong hạn kiểm chứng; không dùng `/health` như một
cam kết dữ liệu đã sẵn sàng.

## Nền tảng ban đầu

Template chính thức cho học viên VinUni AI20K Build Phase: cấu trúc dự án, code
mẫu và hướng dẫn kỹ thuật để xây dựng một AI Agent hoàn chỉnh — từ kiến trúc,
code, test cho đến deploy và nộp bài Demo Day.

Technical Guidebook: <https://phoenix.note.transformerlabs.ai/technical-book>

## Template có sẵn những gì

- **Cấu trúc thư mục tách lớp** — `agents/`, `api/`, `services/`, `models/` đã
  chia sẵn, không phải bàn lại từ đầu.
- **Code mẫu chạy được** — LangGraph agent (state, node, tool), FastAPI routes,
  Pydantic settings, schema.
- **Docker và CI** — Dockerfile multi-stage, `docker-compose.yml`, workflow
  GitHub Actions chạy `ruff` + `pytest` khi push lên `main`/`develop` và khi mở
  pull request vào `main`.
- **Technical Guidebook 10 chương** trong `docs/guide/`, đồng thời đọc được
  online.
- **Checklist 10 deliverables** của Demo Day.
- **AI usage logging** — hook cài sẵn cho 6 công cụ AI, log tự động gửi lên
  grading server mỗi lần `git push`.

## Yêu cầu

- Python 3.11 (phiên bản CI đang dùng)
- Node.js 20.9 trở lên và npm (nếu chạy frontend không qua Docker)
- Git
- Docker — tuỳ chọn, chỉ cần nếu chạy `docker compose`

## Bắt đầu

### 1. Clone repo của đội

Khi đội được chốt, hệ thống tự sinh repo cho đội từ template này, nằm trong org
GitHub của khoá bạn đang học và đặt tên theo mã đội. Copy URL ở trang đội trên
Phoenix rồi clone về:

```bash
git clone https://github.com/<ORG-CỦA-KHOÁ>/<MÃ-ĐỘI>.git
cd <MÃ-ĐỘI>
```

Không cần `rm -rf .git`, `git init` hay `git remote add`: repo sinh từ template
đã bắt đầu bằng lịch sử riêng của đội và remote trỏ sẵn đúng chỗ. Chưa thấy repo
của đội thì báo BTC — repo tự tạo nằm ngoài org sẽ không được chấm.

### 2. Cài môi trường

```bash
python3.11 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cd frontend
npm install
cd ..
```

### 3. Cấu hình biến môi trường

```bash
cp .env.example .env
```

Mở `.env` và điền `OPENAI_API_KEY`. Riêng `AI_LOG_API_KEY`, mỗi thành viên tự
tạo key riêng tại [dashboard Phoenix](https://phoenix.note.transformerlabs.ai/api-keys)
rồi thay vào chỗ `<get-your-api-key-from-dashboard-phoenix>` — giá trị trong
`.env.example` chỉ là placeholder, để nguyên thì log không vào được hệ thống chấm.

### 4. Cài hook ghi log AI

```bash
bash scripts/setup_hooks.sh                                      # Linux / macOS / Git Bash
powershell -ExecutionPolicy Bypass -File scripts\setup_hooks.ps1 # Windows PowerShell
```

Chạy một lần sau khi clone. Hook ghi lại prompt khi bạn dùng Claude Code, Cursor,
Codex CLI, Gemini CLI, Antigravity hoặc GitHub Copilot, và cài pre-push hook để
đẩy log lên server.

### 5. Chạy ứng dụng

```bash
python -m uvicorn src.main:app --reload --port 8000
```

Mở terminal thứ hai:

```bash
cd frontend
npm run dev
```

Giao diện ở <http://localhost:3000>; Swagger UI ở
<http://localhost:8000/docs>. Hoặc dùng `make run`, `make test`, `make lint` —
xem `Makefile`.

## Cấu trúc thư mục

```
src/
  agents/            LangGraph agent
    graph.py         State graph (nodes + edges)
    state.py         State schema (TypedDict)
    nodes/           Node functions
    tools/           Agent tools (@tool)
  api/routes.py      FastAPI endpoints
  models/schemas.py  Pydantic schemas
  services/llm.py    LLM client
  config.py          Pydantic Settings
  main.py            App entry point
frontend/             Next.js App Router
  app/                Trang chủ, chat và staff
  components/         UI và luồng tương tác
  lib/api.ts          API client có timeout/error handling
tests/               pytest suite
scripts/             Hook ghi log AI + installer
docs/
  guide/             Technical Guidebook (nguồn của bản online)
  architecture_diagram.md
eval/                Kết quả evaluation
presentation/        Slide và video Demo Day
.claude/ .codex/ .cursor/ .gemini/ .agents/ .github/hooks/
                     Config hook cho từng công cụ
.github/workflows/   CI
Dockerfile           Multi-stage build backend
frontend/Dockerfile  Multi-stage build frontend
docker-compose.yml   Chạy frontend và backend bằng Docker
README_boilerplate.md  Khung README cho dự án của đội
```

## Technical Guidebook

| Chương | Nội dung | Thời gian |
|---|---|---|
| 1 | Lời mở đầu — mục tiêu, cách sử dụng | 15 phút |
| 2 | Khởi tạo dự án — clone, setup, git workflow | 4 giờ |
| 3 | Thiết kế kiến trúc — 3-tier, diagram, ADR | 6 giờ |
| 4 | LangGraph Agent — state, node, edge, tool, RAG | 8 giờ |
| 5 | FastAPI — routes, validation, error handling, streaming | 6 giờ |
| 6 | Giao diện — Next.js và Streamlit | 6 giờ |
| 7 | DevOps — Docker, CI/CD, deploy, logging | 6 giờ |
| 8 | Kiểm thử — unit test, integration test, RAGAS | 4 giờ |
| 9 | Demo Day — 10 deliverables, checklist | 2 giờ |
| 10 | Tài nguyên — khoá học, tài liệu, BMAD method | tham khảo |

Đọc online tại <https://phoenix.note.transformerlabs.ai/technical-book>: đăng
nhập bằng GitHub (đúng account đã được BTC mời vào org của khoá), chọn tab
**Technical Book** ở sidebar trái. Bản offline nằm trong `docs/guide/`, mở được
bằng bất kỳ markdown viewer nào.

## 10 deliverables cho Demo Day

| # | Deliverable | Vị trí | Template lo tới đâu |
|---|---|---|---|
| 1 | Source code | `src/` | Khung sẵn |
| 2 | README | copy `README_boilerplate.md` thành `README.md` | Khung sẵn |
| 3 | Architecture diagram | `docs/architecture_diagram.md` | Khung sẵn |
| 4 | AI logs | LangSmith (3 biến môi trường) + auto AI usage logging | Cấu hình sẵn |
| 5 | Live URL | deploy lên Render/Vercel | CI/CD sẵn |
| 6 | Video demo | `presentation/` | Đội tự làm |
| 7 | Pitch deck | `presentation/` | Đội tự làm |
| 8 | Development journal | `JOURNAL.md` | Khung sẵn |
| 9 | Worklog | `WORKLOG.md` | Khung sẵn |
| 10 | Evaluation evidence | `eval/` | Đội tự làm |

## Tech stack

| Lớp | Công nghệ |
|---|---|
| Agent | LangGraph + LangChain 0.3 |
| Backend | FastAPI 0.115 + Uvicorn |
| LLM | OpenAI, mặc định `gpt-4o-mini` (đổi trong `src/config.py`) |
| Giao diện | Next.js App Router + React + TypeScript |
| Lint / test | ruff + pytest 8 |
| DevOps | Docker + GitHub Actions |

## AI usage logging

Mọi prompt được ghi vào `.ai-log/session.jsonl` và tự động gửi lên grading server
ở bước pre-push.

| Công cụ | Cấu hình | Thời điểm ghi |
|---|---|---|
| Claude Code | `.claude/settings.json` | mỗi prompt (`UserPromptSubmit`) |
| Cursor | `.cursor/hooks.json` | mỗi prompt và khi dừng |
| OpenAI Codex CLI | `.codex/hooks.json` | mỗi prompt và khi dừng |
| Gemini CLI | `.gemini/settings.json` | mỗi lượt agent chạy |
| GitHub Copilot | `.github/hooks/hooks.json` | mỗi prompt và cuối session |
| Antigravity IDE | `.agents/hooks.json` | mỗi prompt, kèm lần quét lại lúc `git push` |

Dùng ChatGPT hay công cụ web khác thì log thủ công:

```bash
bash scripts/_pyrun.sh scripts/log_manual.py --tool chatgpt --prompt "What you asked"
```

## Đóng góp

Repo này là open source. Đọc [CONTRIBUTING.md](CONTRIBUTING.md) trước khi mở PR.

Nội dung trong `docs/guide/` là nguồn của Technical Book và được đồng bộ lên bản
online, nên mọi thay đổi ở đó cần review của
[@AI20K-Build-Phase/book-maintainers](https://github.com/orgs/AI20K-Build-Phase/teams/book-maintainers)
— xem [.github/CODEOWNERS](.github/CODEOWNERS).

Báo lỗ hổng bảo mật theo [SECURITY.md](SECURITY.md), đừng mở public issue.

## License

[MIT](LICENSE) — dùng tự do cho mục đích giáo dục.
