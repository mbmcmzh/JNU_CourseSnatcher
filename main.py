"""暨南大学抢课助手 —— 命令行入口。"""

from jnu_snatcher.api import ApiError, CourseClient
from jnu_snatcher.config import BASE_URL, DEFAULT_BROWSER_WAIT, DEFAULT_SNATCH_ROUNDS, XKXF_URL
from jnu_snatcher.credentials import CredentialError, Credentials
from jnu_snatcher.sniffer import BrowserStartupError, RequestSniffer


def _collect_class_ids():
    """交互式收集教学班号列表。"""
    class_ids = []
    while True:
        value = input("请输入课程的班号（输入空值结束，注意是教学班号而非课程号）: ").strip()
        if not value:
            if class_ids:
                return class_ids
            print("至少需要输入一个班号。")
            continue
        if value in class_ids:
            print(f"班号 {value} 已在列表中。")
            continue
        class_ids.append(value)


def main():
    sniffer = RequestSniffer()
    try:
        captured_data = sniffer.sniff_requests(
            visit_url=BASE_URL,
            target_url=XKXF_URL,
            timeout=DEFAULT_BROWSER_WAIT,
        )
    except BrowserStartupError as exc:
        print(f"错误: {exc}")
        return

    if not captured_data:
        print("未能捕获到登录凭据，请检查网络连接或重试。")
        return

    try:
        credentials = Credentials.from_capture(captured_data)
    except CredentialError as exc:
        print(f"凭据解析失败: {exc}")
        return

    print(f"凭据解析成功 — 学号: {credentials.student_code}，"
          f"选课批次: {credentials.elective_batch_code}")

    client = CourseClient(credentials)

    courses = []
    for class_id in _collect_class_ids():
        try:
            course = client.search_class(class_id)
        except ApiError as exc:
            print(f"跳过: {exc}")
            continue
        courses.append(course)
        print(f"已添加课程 -> {course.summary}")

    if not courses:
        print("没有可抢的课程，已退出。")
        return

    if input("课程信息获取完成，是否开始抢课？（输入 是 开始，其他输入取消）: ").strip() != "是":
        print("已取消。")
        return

    def on_result(course, result):
        print(f"[{course.name}] {result}")

    for round_index in range(DEFAULT_SNATCH_ROUNDS):
        client.snatch_round(courses, on_result=on_result)
        print(f"抢课轮次 {round_index + 1}/{DEFAULT_SNATCH_ROUNDS} 完成")

    print("抢课结束。")


if __name__ == "__main__":
    main()
