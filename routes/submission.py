import os
import json
from flask import Blueprint, render_template, request, current_app, flash, redirect, url_for
from flask_login import current_user, login_required
from models import db, Submission, UserRole, SubmissionStatus  # 从根目录导入

submission_bp = Blueprint('submission', __name__)


@submission_bp.route('/<submission_id>')
@login_required
def detail(submission_id):
    submission = db.get_or_404(Submission, submission_id)
    if submission.user_id != current_user.id and current_user.role != UserRole.ADMIN:
        flash('您没有权限查看此提交记录。', 'danger')
        return redirect(url_for('main.index'))

    log_content = "日志文件无法读取或提交仍在处理中。"
    if submission.log_filename:
        log_file_path = os.path.join(current_app.config['LOG_FOLDER'], submission.log_filename)
        if os.path.exists(log_file_path):
            try:
                # 修正：在打开文件时添加 errors='replace'
                with open(log_file_path, 'r', encoding='utf-8', errors='replace') as f:
                    log_content = f.read()
            except Exception as e:
                log_content = f"读取日志文件时出错: {str(e)}"
                current_app.logger.error(f"读取日志 {log_file_path} (提交 S{submission_id}) 时出错: {e}", exc_info=True)
        elif submission.status not in [SubmissionStatus.PENDING, SubmissionStatus.INITIALIZING,
                                       SubmissionStatus.RUNNING]:
            log_content = "日志文件未找到。判题可能已完成但日志丢失，或启动时遇到问题。"

    detailed_results_parsed = {}
    if submission.detailed_results:
        try:
            detailed_results_parsed = json.loads(submission.detailed_results)
        except json.JSONDecodeError:
            detailed_results_parsed = {"error": "无法解析存储的评分详情。"}
            current_app.logger.warning(f"无法解析 S{submission_id} 的 detailed_results: {submission.detailed_results}")

    return render_template('submission/submission_detail.html', title=f'提交详情 {submission.id[:8]}',
                           submission=submission, log_content=log_content, detailed_results=detailed_results_parsed)


@submission_bp.route('/my')
@login_required
def list_my_submissions():
    page = request.args.get('page', 1, type=int)
    submissions_per_page = current_app.config.get('SUBMISSIONS_PER_USER_PAGE', 10)
    submissions_pagination = Submission.query.filter_by(user_id=current_user.id) \
        .order_by(Submission.submitted_at.desc()) \
        .paginate(page=page, per_page=submissions_per_page, error_out=False)
    return render_template('submission/my_submissions.html', title='我的提交记录', submissions=submissions_pagination)