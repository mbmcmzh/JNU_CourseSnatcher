import time
import requests
import json
from seleniumwire import webdriver


class JNUCourseSnatcher:
    def __init__(self):
        """
        初始化抢课助手。
        - 设置抢课 URL、基础 URL 和 User-Agent。
        """
        self.course_snatch_url = "https://jwxk.jnu.edu.cn/xsxkapp/sys/xsxkapp/elective/volunteer.do"
        self.base_url = "https://jwxk.jnu.edu.cn/"
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0"

    @staticmethod
    def cookies_str_to_dict(cookies_str):
        """
        将 cookies 字符串转换为字典。
        - 分割 cookies 字符串并处理键值对。
        """
        cookies_dict = {}
        cookies_list = cookies_str.split('; ')
        for cookie in cookies_list:
            if '=' in cookie:
                key, value = cookie.split('=', 1)
                cookies_dict[key.strip()] = value.strip().strip('"')
        return cookies_dict

    def get_cookie_and_token(self, max_retry=20):
        """
        从注册接口响应中获取学号、Cookie 和 Token。
        - 打开浏览器，访问教务系统，获取注册响应中的学号。
        - 然后从学号对应的请求中获取 Cookie 和 Token。
        - 重试多次以确保成功。
        """
        print("\n正在获取学号...\n")
        driver = self._init_browser()
        driver.get(self.base_url)

        student_code = None
        retry_count = 0
        
        while retry_count < max_retry and not student_code:
            for request in driver.requests:
                # 从注册接口响应获取学号
                if request.response and request.url.startswith(f"{self.base_url}xsxkapp/sys/xsxkapp/student/register.do"):
                    try:
                        response_body = request.response.body.decode('utf-8')
                        response_json = json.loads(response_body)
                        if response_json.get("code") == "1":
                            student_code = response_json["data"]["number"]
                            print(f"\n\n成功获取学号: {student_code}\n")
                    except Exception as e:
                        print(f"\n\n解析响应失败: {str(e)}\n")
                        continue

                # 获取 Cookie 和 Token
                if student_code and request.url.startswith(f"{self.base_url}xsxkapp/sys/xsxkapp/student/{student_code}.do"):
                    print("\n正在获取Cookie和Token...\n")
                    cookie = request.headers.get('Cookie')
                    token = request.headers.get('token')
                    if cookie and token:
                        print(f"\n成功获取Cookie和Token\n\n正在关闭浏览器...\n")
                        time.sleep(1)
                        driver.quit()
                        print("\n浏览器已关闭\n\n请输入课程数据后点击开始抢课按钮\n")
                        return {
                            "student_code": student_code,
                            "Cookie": cookie,
                            "Token": token,
                            "User-Agent": self.user_agent
                        }

            time.sleep(3)
            print(f"\n第{retry_count}次尝试 ({retry_count + 1}/{max_retry}) ...")
            retry_count += 1

        raise Exception("\n自动获取学号失败，请确保已正确登录教务系统\n")

    def _init_browser(self):
        """
        初始化浏览器驱动。
        - 优先使用 Edge 浏览器，如果失败则使用 Chrome。
        """
        try:
            return webdriver.Edge()
        except Exception as e:
            return webdriver.Chrome(seleniumwire_options={'disable_encoding': True})

    def parse_course_data(self, raw_data):
        """
        解析用户输入的课程数据（在新流程中未使用，但保留以兼容旧代码）。
        - 将原始数据按行分割，解析每行的 JSON 字符串。
        - 提取课程信息并构造 course_list。
        """
        course_list = []
        lines = [line.strip() for line in raw_data.split('\n') if line.strip()]

        for param_str in lines:
            try:
                if param_str.startswith(('addParam:', 'addParam=')):
                    param_str = param_str.split(' ', 1)[-1].strip()

                json_data = json.loads(param_str)
                course_info = json_data['data']
                course = {
                    'class_data': {"addParam": param_str},
                    'display_name': f"课程ID: {course_info['teachingClassId']}, 类型: {course_info['teachingClassType']}"
                }
                course_list.append(course)
            except Exception as e:
                raise ValueError(f"课程解析失败: {str(e)}")
        return course_list

    def start_snatching(self, headers, course_list, callback, stop_event):
        """
        开始抢课循环。
        - 循环发送抢课请求，直到 stop_event 被设置。
        - 每轮抢课后等待 1 秒。
        """
        while not stop_event.is_set():
            for course in course_list:
                try:
                    response = requests.post(
                        self.course_snatch_url,
                        headers=headers,
                        data=course['class_data']
                    )
                    callback(f"{course['display_name']} - 响应: {response.text}")
                except Exception as e:
                    callback(f"{course['display_name']} - 错误: {str(e)}")

            print("\n\n == 本轮抢课周期已完成，1s后进行下一轮抢课 == \n\n")
            time.sleep(1)