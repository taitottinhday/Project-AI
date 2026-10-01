# Cấu hình đăng nhập Google và đăng ký OTP

## Các màn hình đã thêm

- `/auth`: nút đăng nhập Google, đăng nhập email/mật khẩu và đăng ký bằng email.
- `/auth/callback`: nhận mã callback OAuth một lần từ backend.
- Sau khi đăng ký email, backend gửi OTP qua SMTP; chỉ nhập OTP đúng mới tạo tài khoản.
- Mật khẩu được băm bằng `scrypt`; OTP chỉ lưu dưới dạng hash, có thời hạn và giới hạn số lần thử.

## Biến môi trường Railway (Production)

Điền các biến sau trong Railway backend:

```text
FRONTEND_URL=https://project-ai-peach.vercel.app
AUTH_SECRET=<chuỗi ngẫu nhiên dài ít nhất 32 ký tự>
AUTH_SESSION_TTL_HOURS=168
OTP_TTL_MINUTES=10
OTP_MAX_ATTEMPTS=5

GOOGLE_CLIENT_ID=<Google OAuth Client ID>
GOOGLE_CLIENT_SECRET=<Google OAuth Client Secret>
GOOGLE_REDIRECT_URI=https://project-ai-production-556f.up.railway.app/api/v1/auth/google/callback

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=<gmail gửi OTP>
SMTP_PASSWORD=<Google App Password 16 ký tự>
SMTP_FROM_EMAIL=<gmail gửi OTP>
SMTP_FROM_NAME=VinUni Guide
SMTP_STARTTLS=true
```

Không commit các giá trị thật vào GitHub. `AUTH_SECRET`, `GOOGLE_CLIENT_SECRET` và `SMTP_PASSWORD` phải chỉ nằm trong Railway Variables.

## Tạo Google OAuth Client

Trong Google Cloud Console:

1. Tạo/chọn project.
2. Configure OAuth consent screen.
3. Chọn loại External nếu người dùng không chỉ thuộc một Google Workspace.
4. Tạo OAuth Client ID loại **Web application**.
5. Thêm Authorized redirect URI chính xác:

```text
https://project-ai-production-556f.up.railway.app/api/v1/auth/google/callback
```

6. Copy Client ID và Client Secret vào Railway.

Redirect URI phải khớp tuyệt đối, gồm cả `https`, hostname và path.

## Tạo Gmail App Password cho SMTP

Tài khoản Gmail gửi OTP cần bật 2-Step Verification, sau đó tạo App Password:

1. Mở Google Account → Security.
2. Bật 2-Step Verification.
3. Tạo App Password cho ứng dụng VinUni Guide.
4. Dùng chuỗi 16 ký tự đó làm `SMTP_PASSWORD`.

Không dùng mật khẩu Gmail chính và không bật “less secure apps”.

## API auth

```text
GET  /api/v1/auth/google/start
GET  /api/v1/auth/google/callback
POST /api/v1/auth/google/exchange
POST /api/v1/auth/register/request-otp
POST /api/v1/auth/register/verify-otp
POST /api/v1/auth/login
GET  /api/v1/auth/me
POST /api/v1/auth/logout
```

Google callback chỉ chuyển một exchange code dùng một lần về frontend; access token phiên thật không đi qua Google URL. OTP bị hết hạn sau `OTP_TTL_MINUTES` và khóa sau `OTP_MAX_ATTEMPTS` lần thử sai.

## Giới hạn MVP cần biết

Tài khoản hiện xác thực danh tính và sẵn sàng cho các tính năng cá nhân hóa. Ticket cũ vẫn gắn với anonymous session hiện tại; bước tiếp theo nên liên kết `user_id` với ticket để người dùng đăng nhập trên thiết bị khác vẫn nhìn thấy lịch sử của mình.
