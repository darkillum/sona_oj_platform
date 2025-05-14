# sonar_oj_platform_project_root/forms.py
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, PasswordField, SubmitField, BooleanField, TextAreaField, FloatField, IntegerField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError, Length, NumberRange
from models import User, UserRole # 从项目根目录的 models.py 导入

class LoginForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired("用户名不能为空。"), Length(min=3, max=80, message="用户名长度应在3到80个字符之间。")])
    password = PasswordField('密码', validators=[DataRequired("密码不能为空。")])
    remember_me = BooleanField('记住我')
    submit = SubmitField('登录')

class RegistrationForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired("用户名不能为空。"), Length(min=3, max=80)])
    email = StringField('邮箱地址', validators=[DataRequired("邮箱地址不能为空。"), Email("请输入有效的邮箱地址。"), Length(max=120)])
    password = PasswordField('密码', validators=[DataRequired("密码不能为空。"), Length(min=6, max=128, message="密码长度应在6到128个字符之间。")])
    confirm_password = PasswordField('确认密码',
                                     validators=[DataRequired("请再次输入密码。"), EqualTo('password', message='两次输入的密码必须一致。')])
    role = SelectField('角色',
                       choices=[(role.name, role.value.capitalize()) for role in UserRole],
                       default=UserRole.CONTESTANT.name, # 默认为参赛者
                       validators=[DataRequired("请选择角色。")])
    submit = SubmitField('注册')

    def validate_username(self, username_field): # 参数名通常是字段对象本身
        user = User.query.filter_by(username=username_field.data).first()
        if user:
            raise ValidationError('该用户名已被注册，请选择其他用户名。')

    def validate_email(self, email_field): # 参数名通常是字段对象本身
        user = User.query.filter_by(email=email_field.data).first()
        if user:
            raise ValidationError('该邮箱地址已被注册，请选择其他邮箱地址。')

class AlgorithmSubmissionForm(FlaskForm):
    algorithm_script = FileField('算法脚本 (.py)', validators=[
        FileRequired(message='请选择一个 Python 脚本文件。'),
        FileAllowed(['py'], '只允许上传 Python 脚本 (.py) 文件！')
    ])
    bandwidth_mbps = FloatField('模拟带宽 (Mbps)', default=10.0,
                                validators=[DataRequired("带宽不能为空。"), NumberRange(min=0.01, max=10000, message="带宽值应在 0.01 到 10000 Mbps 之间。")])
    latency_ms = IntegerField('模拟延迟 (ms)', default=50,
                              validators=[DataRequired("延迟不能为空。"), NumberRange(min=0, max=60000, message="延迟值应在 0 到 60000 ms 之间。")])
    submit = SubmitField('提交判题')

class ProblemForm(FlaskForm):
    title = StringField('题目名称', validators=[DataRequired("题目名称不能为空。"), Length(min=5, max=150)])
    description = TextAreaField('题目描述 (支持 Markdown)', validators=[DataRequired("题目描述不能为空。"), Length(min=20)])
    dataset_identifier = StringField('数据集标识符 (例如: problem1_data.bin)',
                                     validators=[DataRequired("数据集标识符不能为空。"), Length(max=100)])
    default_bandwidth_mbps = FloatField('默认带宽 (Mbps)', default=10.0,
                                        validators=[DataRequired(), NumberRange(min=0.01, max=10000)])
    default_latency_ms = IntegerField('默认延迟 (ms)', default=50,
                                      validators=[DataRequired(), NumberRange(min=0, max=60000)])
    scoring_function_name = StringField('评分函数名称', default='default_log_scorer',
                                        validators=[DataRequired("评分函数名称不能为空。"), Length(max=100)])
    submit = SubmitField('保存题目')