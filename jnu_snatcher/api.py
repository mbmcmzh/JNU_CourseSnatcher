"""选课系统 HTTP 接口封装。"""

import json
from dataclasses import dataclass

import requests

from .config import PUBLIC_COURSE_URL, REQUEST_INTERVAL, TEACHING_CLASS_TYPE, VOLUNTEER_URL

REQUEST_TIMEOUT = 10


class ApiError(Exception):
    """选课接口请求或解析失败。"""


@dataclass(frozen=True)
class CourseInfo:
    """一门待抢课程的关键信息。"""

    name: str
    course_number: str
    teaching_class_id: str
    campus: str
    campus_name: str
    teacher: str
    place: str

    @property
    def summary(self):
        return (
            f"{self.name} | 课程号 {self.course_number} | 班号 {self.teaching_class_id} | "
            f"{self.campus_name} | {self.teacher} | {self.place}"
        )


class CourseClient:
    """基于已捕获凭据访问选课系统。"""

    def __init__(self, credentials):
        self.credentials = credentials
        self.session = requests.Session()
        self.session.headers.update(credentials.headers)

    def search_class(self, query_content):
        """按班号查询课程，返回 CourseInfo。

        查询失败或无结果时抛出 ApiError。
        """
        query_setting = {
            "data": {
                "studentCode": self.credentials.student_code,
                "campus": "",
                "electiveBatchCode": self.credentials.elective_batch_code,
                "isMajor": "1",
                "teachingClassType": TEACHING_CLASS_TYPE,
                "queryContent": query_content,
            },
            "pageSize": "10",
            "pageNumber": "0",
            "order": "",
        }
        payload = {"querySetting": json.dumps(query_setting, separators=(",", ":"))}

        try:
            response = self.session.post(PUBLIC_COURSE_URL, data=payload, timeout=REQUEST_TIMEOUT)
            result = response.json()
        except requests.RequestException as exc:
            raise ApiError(f"查询班号 {query_content} 网络请求失败: {exc}") from exc
        except ValueError as exc:
            raise ApiError(f"查询班号 {query_content} 返回的不是有效数据") from exc

        data_list = result.get("dataList") or []
        if not data_list:
            msg = result.get("msg", "无具体错误信息")
            raise ApiError(f"查询班号 {query_content} 无结果: {msg}")

        raw = data_list[0]
        return CourseInfo(
            name=raw.get("courseName", ""),
            course_number=raw.get("courseNumber", ""),
            teaching_class_id=raw.get("teachingClassID", ""),
            campus=raw.get("campus", ""),
            campus_name=raw.get("campusName", ""),
            teacher=raw.get("teacherName", ""),
            place=raw.get("teachingPlace", ""),
        )

    def build_add_param(self, course):
        """生成 volunteer.do 所需的提交参数。"""
        add_param = {
            "data": {
                "operationType": "1",
                "studentCode": self.credentials.student_code,
                "electiveBatchCode": self.credentials.elective_batch_code,
                "teachingClassId": course.teaching_class_id,
                "isMajor": "1",
                "campus": course.campus,
                "teachingClassType": TEACHING_CLASS_TYPE,
            }
        }
        return {"addParam": json.dumps(add_param, separators=(",", ":"))}

    def snatch(self, course):
        """对单门课程发起一次选课请求，返回服务端响应。"""
        payload = self.build_add_param(course)
        try:
            response = self.session.post(VOLUNTEER_URL, data=payload, timeout=REQUEST_TIMEOUT)
            return response.json()
        except requests.RequestException as exc:
            raise ApiError(f"选课请求失败: {exc}") from exc
        except ValueError as exc:
            raise ApiError("选课接口返回的不是有效数据") from exc

    def snatch_round(self, courses, on_result=None, interval=REQUEST_INTERVAL, should_stop=None):
        """对一组课程执行一轮抢课。

        on_result(course, result_or_exception) 在每门课请求后回调；
        should_stop() 返回 True 时提前终止。
        """
        import time

        for index, course in enumerate(courses):
            if should_stop and should_stop():
                return
            try:
                result = self.snatch(course)
            except ApiError as exc:
                result = exc
            if on_result:
                on_result(course, result)
            if index < len(courses) - 1:
                time.sleep(interval)
