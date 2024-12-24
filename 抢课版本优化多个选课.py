import time
import requests
import json


def cookies_str_to_dict(cookies_str):
    """将cookies字符串转换为字典"""
    cookies_dict = {}
    cookies_list = cookies_str.split('; ')
    for cookie in cookies_list:
        if '=' in cookie:
            key, value = cookie.split('=', 1)
            cookies_dict[key.strip()] = value.strip().strip('"')
    return cookies_dict


def build_cookie_string(response_cookies, initial_cookies, weu_value):
    """构建完整的cookie字符串"""
    cookie_parts = [
        "Secure",
        "Secure",
        f"_WEU={weu_value}",
        f"JSESSIONID={response_cookies.get('JSESSIONID')}",
        f"JNU_AUTH_VERIFY_TOKEN={initial_cookies.get('JNU_AUTH_VERIFY_TOKEN')}",
        f'CASTGC="{initial_cookies.get("CASTGC")}"',
        f"MOD_AMP_AUTH={initial_cookies.get('MOD_AMP_AUTH')}",
        f"route={initial_cookies.get('route')}",
        "Secure"
    ]
    return "; ".join(cookie_parts)


def get_course_data():
    """获取多个课程数据输入"""
    print("\n请输入课程信息（每个课程一行，输入空行结束）：")
    print("""示例格式：
addParam: {"data":{"operationType":"1","studentCode":"学号","electiveBatchCode":"一串32位的字符","teachingClassId":"课程代码","isMajor":"1","campus":"校区编号","teachingClassType":"选课类型","chooseVolunteer":"1"}}""")
    print("请逐行输入课程数据，输入空行结束：")

    course_list = []
    while True:
        param_str = input("请输入课程参数（直接回车结束输入）: ").strip()
        if not param_str:  # 如果是空行，结束输入
            break

        try:
            if param_str.startswith('addParam:'):
                param_str = param_str[9:].strip()
            elif param_str.startswith('addParam='):
                param_str = param_str[9:].strip()

            # 验证JSON格式
            json_data = json.loads(param_str)
            # 提取课程信息用于显示
            course_info = json_data['data']
            course_list.append({
                'data': {
                    "addParam": param_str
                },
                'display_name': f"课程ID: {course_info['teachingClassId']}, 类型: {course_info['teachingClassType']}"
            })
            print(f"成功添加课程: {course_list[-1]['display_name']}")

        except json.JSONDecodeError:
            print("JSON格式错误，请重新输入此课程")
        except KeyError:
            print("JSON数据格式不完整，请重新输入此课程")

    if not course_list:
        print("未输入任何课程，请重新开始")
        return get_course_data()

    return course_list


def main():
    # 基础配置
    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0"
    base_url = "https://jwxk.jnu.edu.cn/"

    # 获取用户输入
    print("请从F12开发者工具-网络-jwxk.jnu.edu.cn的请求标头中获取初始Cookie")
    cookies_str = input("请输入初始Cookie: ")
    print("\n请从F12开发者工具-网络中找到register.do?number=XXXXXXX字样的URL")
    register_url = input("请输入完整的register.do URL: ")

    # 第一次请求
    cookies_dict = cookies_str_to_dict(cookies_str)
    response_1 = requests.get(base_url, headers={"User-Agent": UA}, cookies=cookies_dict)

    # 第二次请求
    initial_cookie = build_cookie_string(response_1.cookies, cookies_dict, response_1.cookies.get("_WEU"))
    headers_2 = {
        "Cookie": initial_cookie,
        "User-Agent": UA
    }

    response_2 = requests.get(register_url, headers=headers_2)
    token_data = json.loads(response_2.text)

    # 构建最终请求
    final_cookie = build_cookie_string(response_1.cookies, cookies_dict, response_2.cookies.get("_WEU"))
    final_headers = {
        "Cookie": final_cookie,
        "Token": token_data['data']['token'],
        "User-Agent": UA
    }

    # 获取多个课程数据
    course_list = get_course_data()

    # 开始抢课循环
    print("\n开始抢课...")
    while True:
        for course in course_list:
            try:
                response = requests.post(
                    f"{base_url}xsxkapp/sys/xsxkapp/elective/volunteer.do",
                    headers=final_headers,
                    data=course['data']
                )
                print(f"\n{course['display_name']}")
                print(f"响应结果: {response.text}")

            except Exception as e:
                print(f"\n{course['display_name']}")
                print(f"发生错误: {e}")

        time.sleep(0.5)  # 所有课程请求完成后等待一段时间


if __name__ == "__main__":
    main()