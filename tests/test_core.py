"""核心逻辑单元测试（不依赖网络与浏览器）。"""

import json

import pytest

from jnu_snatcher.api import ApiError, CourseClient, CourseInfo
from jnu_snatcher.credentials import (
    CredentialError,
    Credentials,
    get_header_case_insensitive,
)


def make_credentials():
    return Credentials(
        cookie="JSESSIONID=abc",
        token="tok-123",
        student_code="2021001",
        elective_batch_code="BATCH01",
    )


class TestHeaderLookup:
    def test_case_insensitive(self):
        headers = {"Cookie": "a=1", "TOKEN": "t"}
        assert get_header_case_insensitive(headers, "cookie") == "a=1"
        assert get_header_case_insensitive(headers, "Token") == "t"

    def test_missing_and_empty(self):
        assert get_header_case_insensitive({}, "cookie") is None
        assert get_header_case_insensitive(None, "cookie") is None


class TestCredentials:
    def test_from_capture_success(self):
        captured = {
            "request_headers": {"cookie": "JSESSIONID=abc", "token": "tok-123"},
            "request_payload": "xh=2021001&xklcdm=BATCH01",
        }
        creds = Credentials.from_capture(captured)
        assert creds.student_code == "2021001"
        assert creds.elective_batch_code == "BATCH01"
        assert creds.headers["cookie"] == "JSESSIONID=abc"
        assert creds.headers["token"] == "tok-123"
        assert "User-Agent" in creds.headers

    def test_missing_headers(self):
        captured = {"request_headers": {"cookie": "x"}, "request_payload": ""}
        with pytest.raises(CredentialError, match="token"):
            Credentials.from_capture(captured)

    def test_missing_payload_fields(self):
        captured = {
            "request_headers": {"cookie": "x", "token": "y"},
            "request_payload": "other=1",
        }
        with pytest.raises(CredentialError, match="xh"):
            Credentials.from_capture(captured)


class TestCourseClient:
    def test_build_add_param(self):
        client = CourseClient(make_credentials())
        course = CourseInfo(
            name="高等数学",
            course_number="MA101",
            teaching_class_id="MA101-01",
            campus="1",
            campus_name="石牌校区",
            teacher="张三",
            place="教学楼A101",
        )
        payload = client.build_add_param(course)
        data = json.loads(payload["addParam"])["data"]
        assert data["studentCode"] == "2021001"
        assert data["electiveBatchCode"] == "BATCH01"
        assert data["teachingClassId"] == "MA101-01"
        assert data["campus"] == "1"
        assert data["operationType"] == "1"

    def test_search_class_empty_result(self, monkeypatch):
        client = CourseClient(make_credentials())

        class FakeResponse:
            @staticmethod
            def json():
                return {"dataList": [], "msg": "未找到课程"}

        monkeypatch.setattr(client.session, "post", lambda *a, **kw: FakeResponse())
        with pytest.raises(ApiError, match="未找到课程"):
            client.search_class("XX-00")

    def test_search_class_success(self, monkeypatch):
        client = CourseClient(make_credentials())

        class FakeResponse:
            @staticmethod
            def json():
                return {
                    "dataList": [
                        {
                            "courseName": "线性代数",
                            "courseNumber": "MA102",
                            "teachingClassID": "MA102-02",
                            "campus": "2",
                            "campusName": "番禺校区",
                            "teacherName": "李四",
                            "teachingPlace": "教学楼B202",
                        }
                    ]
                }

        captured_payload = {}

        def fake_post(url, data=None, timeout=None):
            captured_payload.update(data)
            return FakeResponse()

        monkeypatch.setattr(client.session, "post", fake_post)
        course = client.search_class("MA102-02")

        assert course.name == "线性代数"
        assert course.teaching_class_id == "MA102-02"
        query = json.loads(captured_payload["querySetting"])
        assert query["data"]["queryContent"] == "MA102-02"
        assert query["data"]["studentCode"] == "2021001"
