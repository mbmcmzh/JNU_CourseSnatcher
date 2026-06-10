"""从抓包数据中解析抢课凭据。"""

from dataclasses import dataclass
from urllib.parse import parse_qs

from .config import USER_AGENT


class CredentialError(Exception):
    """凭据缺失或解析失败。"""


def get_header_case_insensitive(headers, key):
    """按大小写不敏感方式从请求头中取值。"""
    if not headers:
        return None
    key_lower = key.lower()
    for header_key, header_value in headers.items():
        if str(header_key).lower() == key_lower:
            return header_value
    return None


@dataclass(frozen=True)
class Credentials:
    """一次成功登录后抢课所需的全部凭据。"""

    cookie: str
    token: str
    student_code: str
    elective_batch_code: str

    @property
    def headers(self):
        """构造选课接口所需的请求头。"""
        return {
            "User-Agent": USER_AGENT,
            "cookie": self.cookie,
            "token": self.token,
        }

    @classmethod
    def from_capture(cls, captured_data):
        """从嗅探器捕获的请求数据中解析凭据。

        失败时抛出 CredentialError，并携带可读的诊断信息。
        """
        request_headers = captured_data.get("request_headers", {})
        cookie = get_header_case_insensitive(request_headers, "cookie")
        token = get_header_case_insensitive(request_headers, "token")

        missing = [name for name, value in (("cookie", cookie), ("token", token)) if not value]
        if missing:
            available = ", ".join(request_headers.keys()) or "(空)"
            raise CredentialError(
                f"缺少必要请求头: {', '.join(missing)}；当前捕获到的请求头键: {available}"
            )

        payload_params = parse_qs(captured_data.get("request_payload", "") or "")
        student_code = payload_params.get("xh", [None])[0]
        elective_batch_code = payload_params.get("xklcdm", [None])[0]
        if not student_code or not elective_batch_code:
            raise CredentialError(
                "无法从请求体中解析到 xh（学号）或 xklcdm（选课批次），请确认已触发正确请求。"
            )

        return cls(
            cookie=cookie,
            token=token,
            student_code=student_code,
            elective_batch_code=elective_batch_code,
        )
