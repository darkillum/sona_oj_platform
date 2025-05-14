# sonar_oj_platform_project_root/routes/admin.py
import os
from functools import wraps  # 用于创建装饰器
from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import current_user, login_required
from models import db, User, UserRole, Problem, Submission  # 从根目录导入
from forms import ProblemForm  # 从根目录导入

admin_bp = Blueprint('admin', __name__)


# --- admin_required 装饰器定义 ---
def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != UserRole.ADMIN:
            flash("您没有权限访问此页面。请以管理员身份登录。", "danger")
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)

    return decorated_function


# --- 管理员面板路由 ---
@admin_bp.route('/')
@admin_required
def dashboard():
    page = request.args.get('page', 1, type=int)  # 用于提交记录分页
    submissions_per_page = current_app.config.get('ADMIN_SUBMISSIONS_PER_PAGE', 10)

    all_submissions_pagination = Submission.query.order_by(Submission.submitted_at.desc()).paginate(
        page=page, per_page=submissions_per_page, error_out=False
    )
    problems_list = Problem.query.order_by(Problem.title).all()  # 获取所有题目
    users_count = User.query.count()  # 获取用户总数

    return render_template('admin/admin_dashboard.html', title='管理员面板',
                           submissions=all_submissions_pagination, problems=problems_list, users_count=users_count)


@admin_bp.route('/problem/new', methods=['GET', 'POST'])
@admin_required
def new_problem():
    form = ProblemForm()
    if form.validate_on_submit():
        # 检查数据集文件是否存在 (可选，但推荐)
        data_file_path = os.path.join(current_app.config['PROBLEM_DATA_FOLDER'], form.dataset_identifier.data)
        if not os.path.exists(data_file_path):
            flash(f'警告: 数据集文件 "{form.dataset_identifier.data}" 在目录 '
                  f'{current_app.config["PROBLEM_DATA_FOLDER"]} 中不存在。请确保在判题前该文件存在。', 'warning')

        problem = Problem(
            title=form.title.data, description=form.description.data,
            dataset_identifier=form.dataset_identifier.data,
            default_bandwidth_mbps=form.default_bandwidth_mbps.data,
            default_latency_ms=form.default_latency_ms.data,
            scoring_function_name=form.scoring_function_name.data,
            created_at=datetime.now(timezone.utc)  # 记录创建时间
        )
        db.session.add(problem)
        try:
            db.session.commit()
            flash('题目已成功创建!', 'success')
            return redirect(url_for('admin.dashboard'))  # 创建后重定向到管理员面板
        except Exception as e:
            db.session.rollback()
            flash(f"创建题目时发生错误: {str(e)}", 'danger')
            current_app.logger.error(f"创建题目 {form.title.data} 时出错: {e}", exc_info=True)

    return render_template('admin/create_edit_problem.html', title='创建新题目', form=form, legend='创建新题目')


@admin_bp.route('/problem/<int:problem_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_problem(problem_id):
    problem = db.get_or_404(Problem, problem_id)  # 获取题目，不存在则404
    form = ProblemForm(obj=problem)  # 用现有题目数据预填充表单
    if form.validate_on_submit():
        data_file_path = os.path.join(current_app.config['PROBLEM_DATA_FOLDER'], form.dataset_identifier.data)
        if not os.path.exists(data_file_path):
            flash(f'警告: 数据集文件 "{form.dataset_identifier.data}" 不存在。请确保文件存在以供判题使用。', 'warning')

        problem.title = form.title.data
        problem.description = form.description.data
        problem.dataset_identifier = form.dataset_identifier.data
        problem.default_bandwidth_mbps = form.default_bandwidth_mbps.data
        problem.default_latency_ms = form.default_latency_ms.data
        problem.scoring_function_name = form.scoring_function_name.data
        # created_at 通常在编辑时不更新
        try:
            db.session.commit()
            flash('题目已成功更新!', 'success')
            return redirect(url_for('admin.dashboard'))  # 更新后重定向
        except Exception as e:
            db.session.rollback()
            flash(f"更新题目时发生错误: {str(e)}", 'danger')
            current_app.logger.error(f"更新题目 P{problem_id} 时出错: {e}", exc_info=True)

    return render_template('admin/create_edit_problem.html', title='编辑题目', form=form,
                           legend=f'编辑题目: {problem.title}')


@admin_bp.route('/users')
@admin_required
def manage_users_route():  # 路由函数名与蓝图名不冲突
    page = request.args.get('page', 1, type=int)
    users_per_page = current_app.config.get('ADMIN_USERS_PER_PAGE', 10)
    users_pagination = User.query.order_by(User.username).paginate(page=page, per_page=users_per_page, error_out=False)
    return render_template('admin/manage_users.html', title="用户管理", users=users_pagination)