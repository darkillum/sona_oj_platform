# sonar_oj_platform_project_root/app.py
import os
import sys
from flask import Flask, render_template  # render_template 用于错误页面
from datetime import datetime, timezone  # 用于模板全局变量

# 从项目根目录导入配置和模型 (db 实例在 models.py 中定义)
from config import Config
from models import db, User, UserRole, SubmissionStatus  # 导入 Enum 以便在模板中使用

# 初始化 Flask 扩展 (在 create_app 外定义，在 create_app 内用 app 初始化)
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from flask_login import LoginManager

migrate = Migrate()
bcrypt = Bcrypt()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'  # 蓝图名.视图函数名
login_manager.login_message_category = 'info'  # Flash 消息的类别
login_manager.login_message = "请先登录以访问此页面。"


def create_app(config_class=Config):
    """应用工厂函数"""
    app = Flask(__name__, instance_relative_config=True)  # instance_relative_config=True 使 instance 文件夹生效
    app.config.from_object(config_class)  # 从配置对象加载配置

    # 初始化 Flask 扩展
    db.init_app(app)  # 将 models.py 中定义的 db 与 app 关联
    migrate.init_app(app, db)  # 初始化 Flask-Migrate
    bcrypt.init_app(app)  # 初始化 Flask-Bcrypt
    login_manager.init_app(app)  # 初始化 Flask-Login

    # 调用 Config 中的静态方法来确保文件夹存在
    config_class.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        """Flask-Login 用于加载用户的回调函数"""
        return User.query.get(int(user_id))

    @app.context_processor
    def inject_global_vars_for_templates():
        """向所有模板注入全局变量"""
        return dict(
            UserRole=UserRole,  # 使 UserRole 枚举在模板中可用
            SubmissionStatus=SubmissionStatus,  # 使 SubmissionStatus 枚举在模板中可用
            now=datetime.now(timezone.utc),  # 用于页脚年份等
            config=app.config  # 使应用配置在模板中可用 (谨慎使用)
        )

    # 注册蓝图
    # 确保从正确的路径导入蓝图实例
    from routes.main import main_bp
    from routes.auth import auth_bp
    from routes.problem import problem_bp
    from routes.submission import submission_bp
    from routes.admin import admin_bp  # 确保 admin_bp 在 routes/admin.py 中定义

    app.register_blueprint(main_bp)  # 注册主蓝图，通常没有 URL 前缀
    app.register_blueprint(auth_bp, url_prefix='/auth')  # 认证蓝图，URL 前缀 /auth
    app.register_blueprint(problem_bp, url_prefix='/problem')  # 题目蓝图
    app.register_blueprint(submission_bp, url_prefix='/submission')  # 提交蓝图
    app.register_blueprint(admin_bp, url_prefix='/admin')  # 管理员蓝图

    # 注册自定义错误处理器
    @app.errorhandler(403)
    def forbidden_page(error):
        return render_template('errors/403.html', title="禁止访问 (403)"), 403

    @app.errorhandler(404)
    def page_not_found_error(error):  # 重命名以避免与内置的 page_not_found 冲突
        return render_template('errors/404.html', title="页面未找到 (404)"), 404

    @app.errorhandler(500)
    def internal_server_error(error):  # 重命名以避免与内置的 internal_server_error 冲突
        # 在发生 500 错误时记录异常信息
        app.logger.error(f'服务器内部错误: {error}', exc_info=sys.exc_info())
        if db.session.is_active:  # 如果数据库会话活动，则回滚，防止会话挂起
            db.session.rollback()
        return render_template('errors/500.html', title="服务器内部错误 (500)"), 500

    # 定义 Flask CLI 命令
    @app.cli.command("init-db")
    def init_db_command():
        """初始化数据库：创建所有表并填充初始数据。"""
        # db.drop_all() # 如果需要完全重置，请取消注释，但要小心！
        db.create_all()  # 创建在 models.py 中定义的表
        from initial_data import create_initial_data_cli  # 从项目根目录导入
        create_initial_data_cli(app)  # 调用函数填充数据
        print("数据库已初始化并填充了初始数据。")

    return app

# 如果你想通过 `python app.py` 直接运行 (尽管 `flask run` 是开发时的首选方式)
# if __name__ == '__main__':
#    app = create_app()
#    # 从环境变量或配置中获取 debug 状态
#    is_debug_mode = os.environ.get('FLASK_ENV') == 'development' or app.config.get('DEBUG', False)
#    app.run(debug=is_debug_mode, port=5000)
