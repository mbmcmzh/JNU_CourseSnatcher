import time
import json
import os
import atexit
import shutil
import sys
import tempfile
import urllib3
import requests
from seleniumwire import webdriver

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://jwxk.jnu.edu.cn/"

class RequestSniffer:
    """
    一个模块化的网络请求嗅探器，用于捕获指定URL的请求和响应数据。
    模仿 core.py 的浏览器初始化方式，使用 selenium-wire 捕获网络流量。
    """
    
    def __init__(self):
        """
        初始化嗅探器。
        """
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0"

    def _init_browser(self):
        """
        初始化Chrome浏览器驱动。
        - 优先使用内置的Chrome浏览器 (./chrome/chrome.exe)
        - 仅使用 Chrome 浏览器
        - 为每个实例创建唯一的用户数据目录
        - 增加稳定性参数防止崩溃
        - 注册退出时自动清理临时目录
        - 解决seleniumwire打包后证书文件缺失问题
        """
        # 为 Chrome 创建唯一的临时用户数据目录
        pid = os.getpid()
        timestamp = int(time.time())
        # 使用更唯一的目录名，包含时间戳
        chrome_temp_dir = os.path.join(tempfile.gettempdir(), f"jnu_sniffer_chrome_{pid}_{timestamp}")

        # 启动前强制清理旧的临时目录
        shutil.rmtree(chrome_temp_dir, ignore_errors=True)
        os.makedirs(chrome_temp_dir, exist_ok=True)

        # 注册退出时清理函数
        def _clean_temp_dirs():
            try:
                if os.path.exists(chrome_temp_dir):
                    shutil.rmtree(chrome_temp_dir, ignore_errors=True)
                    print(f"临时目录 {chrome_temp_dir} 已清理。")
            except Exception as e:
                print(f"清理临时目录失败: {e}")

        atexit.register(_clean_temp_dirs)

        # 配置seleniumwire选项
        seleniumwire_options = {
            'disable_encoding': True,
            'verify_ssl': False,
            'suppress_connection_errors': True,
            'disable_capture': False,
        }

        # 尝试使用Chrome
        try:
            print("正在启动 Chrome 浏览器...")
            chrome_options = webdriver.ChromeOptions()
            
            # --- 定位内置Chrome ---
            # 检查是否在PyInstaller打包环境中运行
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                # 在打包后运行
                base_path = sys._MEIPASS
                print(f"程序运行在打包环境中，基础路径: {base_path}")
            else:
                # 在开发环境中作为脚本运行
                base_path = os.path.dirname(os.path.abspath(__file__))
                print(f"程序以脚本方式运行，基础路径: {base_path}")

            chrome_exe_path = os.path.join(base_path, 'chrome', 'chrome.exe')
            
            print(f"正在检查内置Chrome路径: {chrome_exe_path}")

            if os.path.exists(chrome_exe_path):
                print(f"✅ 找到内置Chrome，将使用此版本: {chrome_exe_path}")
                chrome_options.binary_location = chrome_exe_path
            else:
                print("⚠️ 未找到内置Chrome，将尝试使用系统安装的Chrome。")
                print("   如果您希望使用内置版，请确保Chrome浏览器文件夹位于程序根目录下的'chrome'文件夹中（最终路径为 chrome/chrome.exe）。")
            # --- 内置Chrome定位结束 ---
            
            chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # 基础参数
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument('--ignore-certificate-errors')
            chrome_options.add_argument('--ignore-ssl-errors')
            chrome_options.add_argument('--allow-running-insecure-content')
            chrome_options.add_argument('--disable-web-security')
            
            # 安全和稳定性参数
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-features=VizDisplayCompositor')
            
            # Chrome特定参数
            chrome_options.add_argument('--disable-background-timer-throttling')
            chrome_options.add_argument('--disable-backgrounding-occluded-windows')
            chrome_options.add_argument('--disable-renderer-backgrounding')
            chrome_options.add_argument('--disable-background-networking')
            
            # 为Chrome设置唯一的用户数据目录，解决打包后的目录冲突问题
            chrome_options.add_argument(f'--user-data-dir={chrome_temp_dir}')
            # 强制设置磁盘缓存目录
            chrome_options.add_argument(f'--disk-cache-dir={chrome_temp_dir}/cache')
            # 禁用首次运行体验
            chrome_options.add_argument('--no-first-run')
            chrome_options.add_argument('--no-default-browser-check')
            
            print(f"Chrome 临时目录: {chrome_temp_dir}")
            
            return webdriver.Chrome(
                options=chrome_options,
                seleniumwire_options=seleniumwire_options
            )
        except Exception as e:
            print(f"Chrome 浏览器启动失败: {e}")
            print("=" * 60)
            print("错误：未检测到 Chrome 浏览器")
            print("请按照以下步骤安装 Chrome 浏览器：")
            print("1. 访问 Chrome 官方下载页面：https://www.google.com/chrome/")
            print("2. 下载适合您操作系统的版本")
            print("3. 安装完成后重新运行程序")
            print("=" * 60)
            raise Exception("Chrome 浏览器未安装或无法启动。请安装 Chrome 浏览器后重试。")

    def sniff_requests(self, visit_url, target_url, timeout=60):
        """
        启动浏览器，访问页面，并监听捕获特定URL的请求。

        Args:
            visit_url (str): 需要在浏览器中打开的初始网页URL。
            target_url (str): 需要监听和捕获其请求/响应数据的目标URL。
            timeout (int): 等待捕获请求的超时时间（秒）。

        Returns:
            dict or None: 如果成功捕获，返回包含请求详情的字典，否则返回 None。
        """
        print(f"正在启动浏览器并访问: {visit_url}")
        driver = self._init_browser()
        driver.get(visit_url)

        print(f"\n浏览器已启动。请在浏览器中进行必要操作（如登录）以触发目标请求。")
        print(f"正在监听目标URL (或包含该片段的URL): {target_url}")
        print(f"脚本将等待最多 {timeout} 秒...")

        start_time = time.time()
        captured_data = None

        try:
            while time.time() - start_time < timeout:
                # 遍历所有捕获到的请求
                for request in driver.requests:
                    if request.response and target_url in request.url:
                        print(f"\n--- 捕获到目标请求: {request.url} ---")

                        # 1. 提取请求标头
                        headers = dict(request.headers)

                        # 2. 提取请求载荷 (Payload)
                        payload_str = "无"
                        if request.body:
                            try:
                                # 尝试以JSON格式解析和美化
                                payload_json = json.loads(request.body.decode('utf-8'))
                                payload_str = json.dumps(payload_json, indent=2, ensure_ascii=False)
                            except (json.JSONDecodeError, UnicodeDecodeError):
                                # 如果不是JSON，则以纯文本显示
                                payload_str = request.body.decode('utf-8', errors='ignore')

                        # 3. 提取响应内容 (Response Body)
                        response_body_str = "无"
                        if request.response.body:
                            try:
                                # 尝试以JSON格式解析和美化
                                response_json = json.loads(request.response.body.decode('utf-8'))
                                response_body_str = json.dumps(response_json, indent=2, ensure_ascii=False)
                            except (json.JSONDecodeError, UnicodeDecodeError):
                                # 如果不是JSON，则以纯文本显示
                                response_body_str = request.response.body.decode('utf-8', errors='ignore')

                        captured_data = {
                            "url": request.url,
                            "request_headers": headers,
                            "request_payload": payload_str,
                            "response_body": response_body_str
                        }
                        
                        # 清除已处理的请求，防止重复捕获
                        del driver.requests
                        
                        # 跳出内层循环
                        break
                
                if captured_data:
                    # 如果已捕获到数据，跳出外层循环
                    break

                time.sleep(1)
            
            if not captured_data:
                print(f"\n在 {timeout} 秒内未捕获到目标URL的请求。")

        finally:
            print("\n操作完成，正在关闭浏览器...")
            driver.quit()
        
        return captured_data

def course_search(headers, student_code, electiveBatchCode, queryContent, teachingClassType='QXKC'):
    
    publicCourse_url = f"{BASE_URL}xsxkapp/sys/xsxkapp/elective/publicCourse.do"
    
    query_settings_dict = {
        "data":{
            "studentCode":student_code,
            "campus":"",
            "electiveBatchCode":electiveBatchCode,
            "isMajor":"1",
            "teachingClassType":teachingClassType,
            "isMajor":"1",
            "queryContent":queryContent
        },
        "pageSize":"10",
        "pageNumber":"0",
        "order":""
    }

    query_settings_json = json.dumps(query_settings_dict, separators=(',', ':'))

    payload = {
        'querySetting': query_settings_json
    }

    try:
        response = requests.post(publicCourse_url, headers=headers, data=payload)
        return response.json()
    except Exception as e:
        print(f"请求失败: {e}")
        return None

def course_addParam_generate(course_info_list, student_code, electiveBatchCode, ):
    addParam_list = []
    
    for course_info in course_info_list:
        addParam_dict = {
            "data":{
                "operationType":"1",
                "studentCode":student_code,
                "electiveBatchCode":electiveBatchCode,
                "teachingClassId":course_info['dataList'][0]['teachingClassID'],
                "isMajor":"1",
                "campus":course_info['dataList'][0]['campus'],
                "teachingClassType":"QXKC"
            }
        }

        addParam_json = json.dumps(addParam_dict, separators=(',', ':'))

        payload = {
            'addParam': addParam_json
        }

        addParam_list.append(payload)
        print(f"成功添加课程 "
              f"名称:{course_info['dataList'][0]['courseName']}, "
              f"课程号:{course_info['dataList'][0]['courseNumber']}, "
              f"班号:{course_info['dataList'][0]['teachingClassID']}, "
              f"校区:{course_info['dataList'][0]['campusName']}, "
              f"教师:{course_info['dataList'][0]['teacherName']}, "
              f"教学地点:{course_info['dataList'][0]['teachingPlace']}")

    return addParam_list
    
def course_snatch(headers, addParam_list):
    snatch_url = f'{BASE_URL}xsxkapp/sys/xsxkapp/elective/volunteer.do'

    for addParam in addParam_list:
        response = requests.post(snatch_url, headers=headers, data=addParam)
        print(response.json())
        time.sleep(1)

def main():
    repeat_snatch_time = 3 # 重复抢课次数
    Browser_wait_time = 120 # 浏览器等待时间，超过这个时间则认为浏览器没有正常启动

    # 监听获取学号，抢课轮次，Cookie，Token
    xkxf_URL = f"{BASE_URL}xsxkapp/sys/xsxkapp/student/xkxf.do"
    
    sniffer = RequestSniffer()
    # 启动嗅探器，超时时间设置为120秒
    captured_data = sniffer.sniff_requests(
        visit_url=BASE_URL, 
        target_url=xkxf_URL,
        timeout=Browser_wait_time 
    )

    if captured_data:
        print("\n\n--- 成功捕获到请求信息 ---")
        
        
        headers = {
            "User-Agent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
            "cookie": captured_data['request_headers']['cookie'],
            "token": captured_data['request_headers']['token']
        }

        # 输入课程班号
        course_classid_list = []
        while True:
            queryContent_input = input("请输入课程的班号(输入空值结束，注意不要输入课程号，输入的班号是教学班号):")
            if queryContent_input == '':
                if len(course_classid_list) == 0:
                    print("至少需要输入一个班号")
                    continue
                else:
                    break
            else:
                course_classid_list.append(queryContent_input)
        
        student_code = captured_data['request_payload'].split('xh=')[1].split('&')[0]
        electiveBatchCode = captured_data['request_payload'].split('xklcdm=')[1].split('&')[0]
        
        # 获取课程信息
        course_info_list = []
        for queryContent in course_classid_list:
            course_info = course_search(headers, student_code, electiveBatchCode, queryContent)
            course_info_list.append(course_info)

        # 生成添加课程的参数
        addParam_list = course_addParam_generate(course_info_list, student_code, electiveBatchCode)
        print("课程信息获取完成，是否开始抢课(y/n):")
        if input() == 'y':
        # 开始抢课
            for i in range(repeat_snatch_time):
                course_snatch(headers, addParam_list)
                print(f"抢课轮次{i+1}完成")
        print("抢课结束")


    else:
        print("浏览器启动失败，请检查网络连接或浏览器配置")

if __name__ == '__main__':
    main()
        