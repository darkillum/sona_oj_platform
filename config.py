# sonar_oj_platform_project_root/config.py
import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))  # 加载 .env 文件中的环境变量


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-very-complex-and-random-secret-key-dev'

    # 数据库配置
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
                              'sqlite:///' + os.path.join(basedir, 'instance', 'site.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 应用特定路径配置
    UPLOAD_FOLDER = os.path.join(basedir, 'uploaded_algorithms')
    LOG_FOLDER = os.path.join(basedir, 'evaluation_logs')
    PROBLEM_DATA_FOLDER = os.path.join(basedir, 'problem_data')
    INSTANCE_FOLDER_PATH = os.path.join(basedir, 'instance')  # instance 文件夹用于 SQLite 数据库等

    # 应用特定参数配置 (示例)
    PROBLEMS_PER_PAGE = 5
    SUBMISSIONS_PER_PROBLEM_PAGE = 3
    SUBMISSIONS_PER_USER_PAGE = 10
    ADMIN_SUBMISSIONS_PER_PAGE = 10
    ADMIN_USERS_PER_PAGE = 10
    RUNNER_TIMEOUT_SECONDS = 300  # 判题脚本超时时间 (秒)

    @staticmethod
    def init_app(app):
        # 应用初始化时确保这些文件夹存在
        os.makedirs(Config.INSTANCE_FOLDER_PATH, exist_ok=True)
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.LOG_FOLDER, exist_ok=True)
        os.makedirs(Config.PROBLEM_DATA_FOLDER, exist_ok=True)