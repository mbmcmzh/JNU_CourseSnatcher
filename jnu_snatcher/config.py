"""全局配置与常量。"""

import os

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


def _default_data_dir():
    """跨平台的应用数据目录（用于持久化登录 profile）。

    持久化登录 profile 的意义：网易易盾会在 localStorage / cookie 里写入
    设备标识，跨启动稳定后该设备能积累信誉，风控分下降，滑块通过率提升
    （详见 README 的排查记录）。因此 profile 必须落盘到一个稳定、可写的位置。
    """
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(
            os.path.expanduser("~"), ".local", "share"
        )
    return os.path.join(base, "JNU_CourseSnatcher")


DATA_DIR = _default_data_dir()
# 登录用持久化 profile 的存储 / 缓存目录（让易盾设备指纹跨启动稳定）
LOGIN_PROFILE_DIR = os.path.join(DATA_DIR, "login_profile")
LOGIN_CACHE_DIR = os.path.join(DATA_DIR, "login_cache")
