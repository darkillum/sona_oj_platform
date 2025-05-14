# sonar_oj_platform_project_root/routes/main.py
from flask import Blueprint, render_template, request, current_app
from flask_login import login_required
from models import Problem # 从项目根目录的 models.py 导入

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@main_bp.route('/index')
@login_required # 访问主页/题目列表需要登录
def index():
    page = request.args.get('page', 1, type=int)
    problems_per_page = current_app.config.get('PROBLEMS_PER_PAGE', 5)
    # 按创建时间降序排列题目
    problems_pagination = Problem.query.order_by(Problem.created_at.desc()).paginate(
        page=page, per_page=problems_per_page, error_out=False # error_out=False 防止页码超出时抛出404
    )
    return render_template('problem/index.html', title='题目列表', problems=problems_pagination)