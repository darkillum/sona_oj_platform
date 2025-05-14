# sonar_oj_platform_project_root/routes/auth.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, current_user, login_required
from models import db, User, UserRole  # 从项目根目录的 models.py 导入
from forms import LoginForm, RegistrationForm  # 从项目根目录的 forms.py 导入

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))  # 如果已登录，重定向到主页

    form = LoginForm()
    if form.validate_on_submit():  # 处理 POST 请求且表单验证通过
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')  # 获取重定向回来的 URL
            flash(f'欢迎回来, {user.username}!', 'success')
            return redirect(next_page or url_for('main.index'))
        else:
            flash('登录失败。请检查用户名和密码是否正确。', 'danger')
            # 如果登录失败，会重新渲染登录表单 (下面的 return)

    # 处理 GET 请求或表单验证失败的 POST 请求
    return render_template('auth/login.html', title='用户登录', form=form)


@auth_bp.route('/logout')
@login_required  # 必须登录才能注销
def logout():
    logout_user()
    flash('您已成功注销。', 'info')
    return redirect(url_for('auth.login'))  # 注销后重定向到登录页面


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    # 如果用户已登录且不是管理员，则不允许访问注册页面
    if current_user.is_authenticated and current_user.role != UserRole.ADMIN:
        flash('您已登录。只有管理员可以注册新用户或您需要先注销。', 'warning')
        return redirect(url_for('main.index'))

    form = RegistrationForm()
    is_admin_creating = current_user.is_authenticated and current_user.role == UserRole.ADMIN

    if not is_admin_creating:
        # 如果是用户自行注册，则角色固定为 CONTESTANT
        form.role.choices = [(UserRole.CONTESTANT.name, UserRole.CONTESTANT.value.capitalize())]
        form.role.data = UserRole.CONTESTANT.name  # 预选并固定
    elif request.method == 'GET' or not form.role.choices:  # 确保管理员在GET时或表单重新加载时有所有角色选项
        form.role.choices = [(role.name, role.value.capitalize()) for role in UserRole]
        if not form.role.data:  # 如果是GET请求且没有预设数据，则默认
            form.role.data = UserRole.CONTESTANT.name

    if form.validate_on_submit():
        # 再次确认角色，防止篡改
        user_role_enum = UserRole[
            form.role.data] if is_admin_creating and form.role.data in UserRole._member_names_ else UserRole.CONTESTANT

        # 后端再次校验用户名和邮箱唯一性，防止并发或绕过前端验证
        if User.query.filter_by(username=form.username.data).first():
            form.username.errors.append('该用户名已被注册。')
        if User.query.filter_by(email=form.email.data).first():
            form.email.errors.append('该邮箱已被注册。')

        if not form.errors:  # 如果没有新的验证错误
            user = User(username=form.username.data, email=form.email.data, role=user_role_enum)
            user.set_password(form.password.data)
            db.session.add(user)
            try:
                db.session.commit()
                flash(f'用户 {form.username.data} 创建成功！现在可以登录了。', 'success')
                if is_admin_creating:
                    return redirect(url_for('admin.manage_users_route'))  # 管理员创建后重定向到用户管理
                return redirect(url_for('auth.login'))  # 用户自注册后重定向到登录
            except Exception as e:  # 处理数据库提交可能发生的错误
                db.session.rollback()
                flash(f'创建账户时发生数据库错误: {str(e)}', 'danger')
                current_app.logger.error(f"注册用户 {form.username.data} 时数据库提交出错: {e}", exc_info=True)

    # 如果是GET请求或表单验证失败，则渲染注册页面
    return render_template('auth/register.html', title='用户注册', form=form, is_admin_creating=is_admin_creating)