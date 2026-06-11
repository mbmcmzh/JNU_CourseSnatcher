"""全局配置与常量。"""

BASE_URL = "https://jwxk.jnu.edu.cn/"

# 选课系统接口
XKXF_URL = f"{BASE_URL}xsxkapp/sys/xsxkapp/student/xkxf.do"
PUBLIC_COURSE_URL = f"{BASE_URL}xsxkapp/sys/xsxkapp/elective/publicCourse.do"
VOLUNTEER_URL = f"{BASE_URL}xsxkapp/sys/xsxkapp/elective/volunteer.do"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# 默认参数
DEFAULT_SNATCH_ROUNDS = 3      # 重复抢课轮数
DEFAULT_BROWSER_WAIT = 120     # 等待登录捕获凭据的超时（秒）
REQUEST_INTERVAL = 1.0         # 连续抢课请求之间的间隔（秒）
TEACHING_CLASS_TYPE = "QXKC"   # 全校公选课
