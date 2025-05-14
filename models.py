# sonar_oj_platform_project_root/models.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone  # 确保使用 timezone-aware datetime
import enum
import uuid

db = SQLAlchemy()  # 在这里定义 db 实例


class UserRole(enum.Enum):
    ADMIN = 'admin'
    CONTESTANT = 'contestant'


class User(UserMixin, db.Model):
    __tablename__ = 'user'  # 明确表名
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256))  # 存储哈希后的密码
    role = db.Column(db.Enum(UserRole), default=UserRole.CONTESTANT, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # 反向关系: 一个用户可以有多个提交记录
    submissions = db.relationship('Submission', backref='author', lazy='dynamic', cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if self.password_hash is None:
            return False
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username} ({self.role.value})>'


class Problem(db.Model):
    __tablename__ = 'problem'  # 明确表名
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)  # 题目描述
    dataset_identifier = db.Column(db.String(100), nullable=False)  # 数据集标识符 (例如文件名)
    default_bandwidth_mbps = db.Column(db.Float, default=10.0)  # 默认模拟带宽
    default_latency_ms = db.Column(db.Integer, default=50)  # 默认模拟延迟
    scoring_function_name = db.Column(db.String(100), nullable=False, default="default_log_scorer")  # 评分函数名
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    # 反向关系: 一个题目可以有多个提交记录
    submissions = db.relationship('Submission', backref='problem', lazy='dynamic', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Problem {self.id}: {self.title}>'


class SubmissionStatus(enum.Enum):
    PENDING = '等待中'  # Pending
    INITIALIZING = '初始化中'  # Initializing
    RUNNING = '运行中'  # Running
    COMPLETED = '已完成'  # Completed
    FAILED = '失败'  # Failed
    ERROR_STARTING = '启动错误'  # Error Starting Runner
    TIMEOUT = '超时'  # Timeout


class Submission(db.Model):
    __tablename__ = 'submission'  # 明确表名
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))  # 使用 UUID 作为主键
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    problem_id = db.Column(db.Integer, db.ForeignKey('problem.id'), nullable=False, index=True)
    algorithm_script_filename = db.Column(db.String(255), nullable=False)  # 上传的算法脚本文件名
    submitted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    status = db.Column(db.Enum(SubmissionStatus), default=SubmissionStatus.PENDING, nullable=False)
    score = db.Column(db.Float, nullable=True)  # 判题得分
    log_filename = db.Column(db.String(100), nullable=True)  # 日志文件名 (例如 submission_id.log)
    actual_bandwidth_mbps = db.Column(db.Float, nullable=True)  # 本次提交实际使用的带宽
    actual_latency_ms = db.Column(db.Integer, nullable=True)  # 本次提交实际使用的延迟
    return_code = db.Column(db.Integer, nullable=True)  # 判题脚本的返回码
    detailed_results = db.Column(db.Text, nullable=True)  # JSON 字符串格式的详细评分结果

    def __repr__(self):
        return f'<Submission {self.id[:8]} for P{self.problem_id} by U{self.user_id} - Status: {self.status.value}>'