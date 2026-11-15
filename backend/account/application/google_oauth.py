from __future__ import annotations

import base64
import hashlib
import http.server
import os
from pathlib import Path
import secrets
import threading
import time
import urllib.parse
import webbrowser
from dataclasses import dataclass
from queue import Empty, Queue

import requests


class GoogleOAuthError(RuntimeError):
    pass


class GoogleOAuthCancelled(GoogleOAuthError):
    pass


@dataclass(frozen=True)
class GoogleAuthorization:
    code: str
    code_verifier: str
    redirect_uri: str


@dataclass(frozen=True)
class GoogleOAuthConfig:
    client_id: str
    redirect_uri: str
    scopes: tuple[str, ...] = ("openid", "email", "profile")
    timeout_seconds: int = 180

    @classmethod
    def from_environment(cls) -> "GoogleOAuthConfig | None":
        # The desktop UI imports Account Layer before the legacy backend
        # configuration module. Read only the public Google settings here;
        # never load the whole dev.env because it also contains server-side
        # SMTP credentials.
        if not os.getenv("GOOGLE_CLIENT_ID") or os.getenv("GOOGLE_AUTH_ENABLED") is None:
            env_path = Path(__file__).resolve().parents[2] / "dev.env"
            try:
                for raw_line in env_path.read_text(encoding="utf-8").splitlines():
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    name, value = line.split("=", 1)
                    if name.strip() in {"GOOGLE_AUTH_ENABLED", "GOOGLE_CLIENT_ID", "GOOGLE_REDIRECT_URI"}:
                        os.environ.setdefault(name.strip(), value.strip().strip("\"'"))
            except (OSError, UnicodeError):
                pass
        enabled = os.getenv("GOOGLE_AUTH_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
        client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
        redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://127.0.0.1:8765/").strip()
        return cls(client_id, redirect_uri) if enabled and client_id else None


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path not in {"", "/", "/oauth/callback"}:
            self.send_error(404)
            return
        params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        self.server.result_queue.put({key: values[0] for key, values in params.items()})
        body = b"<html><body><h2>JARVIS</h2><p>Authorization response received. You can return to Jarvis.</p></body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        return


class _CallbackServer(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, handler):
        super().__init__(address, handler)
        self.result_queue: Queue[dict[str, str]] = Queue(maxsize=1)


class GoogleLoopbackOAuthClient:
    def __init__(self, config: GoogleOAuthConfig, http_session: requests.Session | None = None) -> None:
        self.config = config
        self.http = http_session or requests.Session()

    def authenticate(self) -> str:
        parsed_redirect = urllib.parse.urlparse(self.config.redirect_uri)
        if parsed_redirect.scheme != "http" or parsed_redirect.hostname not in {"127.0.0.1", "localhost"} or parsed_redirect.path not in {"", "/", "/oauth/callback"}:
            raise GoogleOAuthError("Google desktop redirect must be a loopback HTTP URI")
        if not parsed_redirect.port:
            raise GoogleOAuthError("Google desktop redirect must specify a fixed port")
        state = secrets.token_urlsafe(32)
        verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
        server = None
        try:
            server = _CallbackServer((parsed_redirect.hostname, parsed_redirect.port), _CallbackHandler)
        except OSError:
            # A stale or unrelated local process may already own the
            # configured port. Desktop OAuth permits a dynamically selected
            # loopback port; keep the listener local and use the actual port
            # consistently for both authorization and token exchange.
            server = _CallbackServer((parsed_redirect.hostname, 0), _CallbackHandler)
        actual_port = int(server.server_address[1])
        effective_redirect_uri = parsed_redirect._replace(
            netloc=f"{parsed_redirect.hostname}:{actual_port}"
        ).geturl()
        params = {
            "client_id": self.config.client_id,
            "redirect_uri": effective_redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.config.scopes),
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "access_type": "offline",
        }
        thread = threading.Thread(target=server.serve_forever, name="jarvis-google-loopback", daemon=True)
        thread.start()
        try:
            url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
            if not webbrowser.open(url):
                raise GoogleOAuthError("Could not open the system browser")
            try:
                result = server.result_queue.get(timeout=self.config.timeout_seconds)
            except Empty as exc:
                raise GoogleOAuthError("Google authorization timed out") from exc
            if result.get("error"):
                if result["error"] == "access_denied":
                    raise GoogleOAuthCancelled("Google authorization was cancelled")
                raise GoogleOAuthError("Google authorization failed")
            if not secrets.compare_digest(result.get("state", ""), state):
                raise GoogleOAuthError("Google OAuth state validation failed")
            code = result.get("code")
            if not code:
                raise GoogleOAuthError("Google authorization code is missing")
            return GoogleAuthorization(code=code, code_verifier=verifier, redirect_uri=effective_redirect_uri)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

