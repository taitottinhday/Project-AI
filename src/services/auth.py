from __future__ import annotations

import hashlib
import hmac
import secrets
import smtplib
import sqlite3
import ssl
import uuid
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path

import httpx

from src.config import get_settings


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime) -> str:
    return value.isoformat()


def _hash_token(value: str) -> str:
    return hmac.new(get_settings().auth_secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt_hex, digest_hex = encoded.split("$", 2)
        if algorithm != "scrypt":
            return False
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1)
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


class AuthStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or get_settings().sqlite_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS auth_users (
                    user_id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    password_hash TEXT,
                    google_subject TEXT UNIQUE,
                    created_at TEXT NOT NULL,
                    verified_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS auth_otp_challenges (
                    challenge_id TEXT PRIMARY KEY,
                    email TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    code_hash TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_otp_email_created
                    ON auth_otp_challenges(email, created_at);
                CREATE TABLE IF NOT EXISTS auth_sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES auth_users(user_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS auth_oauth_states (
                    state_hash TEXT PRIMARY KEY,
                    expires_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS auth_exchange_codes (
                    code_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES auth_users(user_id) ON DELETE CASCADE
                );
                """
            )

    def email_exists(self, email: str) -> bool:
        with self._connect() as connection:
            row = connection.execute("SELECT 1 FROM auth_users WHERE email = ?", (email,)).fetchone()
        return row is not None

    def save_otp(self, email: str, display_name: str, password_hash: str, code: str) -> None:
        now = _now()
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM auth_otp_challenges WHERE email = ? OR expires_at < ?",
                (email, _iso(now)),
            )
            connection.execute(
                "INSERT INTO auth_otp_challenges VALUES (?, ?, ?, ?, ?, 0, ?, ?)",
                (
                    uuid.uuid4().hex,
                    email,
                    display_name,
                    password_hash,
                    _hash_token(code),
                    _iso(now + timedelta(minutes=get_settings().otp_ttl_minutes)),
                    _iso(now),
                ),
            )

    def verify_otp(self, email: str, code: str) -> dict[str, str] | None:
        now = _now()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM auth_otp_challenges WHERE email = ? ORDER BY created_at DESC LIMIT 1",
                (email,),
            ).fetchone()
            if row is None or datetime.fromisoformat(row["expires_at"]) < now:
                return None
            if row["attempts"] >= get_settings().otp_max_attempts:
                return None
            connection.execute(
                "UPDATE auth_otp_challenges SET attempts = attempts + 1 WHERE challenge_id = ?",
                (row["challenge_id"],),
            )
            if not hmac.compare_digest(row["code_hash"], _hash_token(code)):
                return None
            user_id = uuid.uuid4().hex
            connection.execute(
                "INSERT INTO auth_users VALUES (?, ?, ?, ?, NULL, ?, ?)",
                (user_id, email, row["display_name"], row["password_hash"], _iso(now), _iso(now)),
            )
            connection.execute("DELETE FROM auth_otp_challenges WHERE email = ?", (email,))
            return {"user_id": user_id, "email": email, "display_name": row["display_name"]}

    def create_or_update_google_user(self, email: str, display_name: str, subject: str) -> dict[str, str]:
        now = _now()
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM auth_users WHERE email = ?", (email,)).fetchone()
            if row is None:
                user_id = uuid.uuid4().hex
                connection.execute(
                    "INSERT INTO auth_users VALUES (?, ?, ?, NULL, ?, ?, ?)",
                    (user_id, email, display_name or email, subject, _iso(now), _iso(now)),
                )
            else:
                user_id = row["user_id"]
                connection.execute(
                    "UPDATE auth_users SET display_name = ?, google_subject = ?, verified_at = ? WHERE user_id = ?",
                    (display_name or row["display_name"], subject, _iso(now), user_id),
                )
            return {"user_id": user_id, "email": email, "display_name": display_name or email}

    def create_session(self, user_id: str) -> str:
        token = secrets.token_urlsafe(48)
        now = _now()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO auth_sessions VALUES (?, ?, ?, ?)",
                (_hash_token(token), user_id, _iso(now + timedelta(hours=get_settings().auth_session_ttl_hours)), _iso(now)),
            )
        return token

    def user_from_session(self, token: str) -> dict[str, str] | None:
        now = _now()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT u.user_id, u.email, u.display_name FROM auth_sessions s JOIN auth_users u ON u.user_id = s.user_id WHERE s.token_hash = ? AND s.expires_at > ?",
                (_hash_token(token), _iso(now)),
            ).fetchone()
        return dict(row) if row else None

    def password_user(self, email: str, password: str) -> dict[str, str] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM auth_users WHERE email = ?", (email,)).fetchone()
        if row is None or not row["password_hash"] or not verify_password(password, row["password_hash"]):
            return None
        return {"user_id": row["user_id"], "email": row["email"], "display_name": row["display_name"]}

    def revoke_session(self, token: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (_hash_token(token),))

    def save_oauth_state(self) -> str:
        value = secrets.token_urlsafe(32)
        now = _now()
        with self._connect() as connection:
            connection.execute("DELETE FROM auth_oauth_states WHERE expires_at < ?", (_iso(now),))
            connection.execute(
                "INSERT INTO auth_oauth_states VALUES (?, ?)",
                (_hash_token(value), _iso(now + timedelta(minutes=10))),
            )
        return value

    def consume_oauth_state(self, value: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT expires_at FROM auth_oauth_states WHERE state_hash = ?",
                (_hash_token(value),),
            ).fetchone()
            if row is None or datetime.fromisoformat(row["expires_at"]) < _now():
                return False
            connection.execute("DELETE FROM auth_oauth_states WHERE state_hash = ?", (_hash_token(value),))
            return True

    def save_exchange_code(self, user_id: str) -> str:
        code = secrets.token_urlsafe(36)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO auth_exchange_codes VALUES (?, ?, ?)",
                (_hash_token(code), user_id, _iso(_now() + timedelta(minutes=2))),
            )
        return code

    def exchange_code(self, code: str) -> str | None:
        user = self.consume_exchange_code(code)
        return self.create_session(user["user_id"]) if user else None

    def consume_exchange_code(self, code: str) -> dict[str, str] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT u.user_id, u.email, u.display_name, c.expires_at FROM auth_exchange_codes c "
                "JOIN auth_users u ON u.user_id = c.user_id WHERE c.code_hash = ?",
                (_hash_token(code),),
            ).fetchone()
            if row is None or datetime.fromisoformat(row["expires_at"]) < _now():
                return None
            connection.execute("DELETE FROM auth_exchange_codes WHERE code_hash = ?", (_hash_token(code),))
            return {"user_id": row["user_id"], "email": row["email"], "display_name": row["display_name"]}


def _send_resend_message(message: EmailMessage) -> None:
    settings = get_settings()
    api_key = settings.resend_api_key.strip()
    from_email = (settings.resend_from_email or settings.smtp_from_email or settings.smtp_username).strip()
    if not from_email:
        raise RuntimeError("Resend chưa được cấu hình. Thiếu RESEND_FROM_EMAIL")

    payload = {
        "from": f"{settings.smtp_from_name} <{from_email}>",
        "to": [message["To"]],
        "subject": message["Subject"],
        "text": message.get_content(),
    }
    try:
        with httpx.Client(timeout=20) as client:
            response = client.post(
                settings.resend_api_url,
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise RuntimeError("Không thể kết nối Resend API từ backend.") from exc

    if response.is_error:
        try:
            detail = response.json().get("message", "Resend từ chối yêu cầu")
        except ValueError:
            detail = "Resend từ chối yêu cầu"
        raise RuntimeError(f"Resend không gửi được email: {detail}")


def _send_smtp_message(message: EmailMessage) -> None:
    settings = get_settings()
    host = settings.smtp_host.strip()
    username = settings.smtp_username.strip()
    # Google displays App Passwords with spaces; Gmail authenticates the same
    # 16 characters when the separators are removed.
    password = "".join(settings.smtp_password.split())
    from_email = (settings.smtp_from_email or username).strip()
    missing = [
        name
        for name, value in (
            ("SMTP_HOST", host),
            ("SMTP_USERNAME", username),
            ("SMTP_PASSWORD", password),
            ("SMTP_FROM_EMAIL", from_email),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(f"SMTP chưa được cấu hình. Thiếu: {', '.join(missing)}")

    message["From"] = f"{settings.smtp_from_name} <{from_email}>"
    context = ssl.create_default_context()
    if settings.smtp_starttls:
        with smtplib.SMTP(host, settings.smtp_port, timeout=20) as client:
            client.ehlo()
            client.starttls(context=context)
            client.ehlo()
            client.login(username, password)
            client.send_message(message)
    else:
        with smtplib.SMTP_SSL(host, settings.smtp_port, context=context, timeout=20) as client:
            client.login(username, password)
            client.send_message(message)


def _send_email(message: EmailMessage) -> None:
    settings = get_settings()
    if settings.resend_api_key.strip():
        _send_resend_message(message)
    else:
        _send_smtp_message(message)


def send_otp_email(email: str, code: str) -> None:
    settings = get_settings()
    message = EmailMessage()
    message["Subject"] = "Mã xác minh VinUni Guide"
    message["To"] = email
    message.set_content(
        f"Mã OTP đăng ký VinUni Guide của bạn là: {code}\n\n"
        f"Mã có hiệu lực trong {settings.otp_ttl_minutes} phút. "
        "Nếu bạn không yêu cầu mã này, hãy bỏ qua email."
    )
    _send_email(message)


def send_login_notification_email(email: str, display_name: str) -> None:
    """Send a security notice after Google login without blocking the login."""
    now = _now().astimezone().strftime("%H:%M %d/%m/%Y")
    message = EmailMessage()
    message["Subject"] = "Bạn vừa đăng nhập VinUni Guide"
    message["To"] = email
    message.set_content(
        f"Xin chào {display_name or email},\n\n"
        f"Tài khoản Google của bạn vừa đăng nhập vào VinUni Guide lúc {now}.\n\n"
        "Nếu đây không phải là bạn, hãy đổi mật khẩu Google và kiểm tra hoạt động đăng nhập.\n"
    )
    _send_email(message)


_auth_store: AuthStore | None = None


def get_auth_store() -> AuthStore:
    global _auth_store
    if _auth_store is None:
        _auth_store = AuthStore()
    return _auth_store
