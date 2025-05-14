# sonar_oj_platform_project_root/routes/problem.py
# ... (其他导入和蓝图定义保持不变) ...
import os
import sys
import subprocess
import threading
import uuid
import json
from datetime import datetime, timezone
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import current_user, login_required
from models import db, Problem, Submission, SubmissionStatus  # 从根目录导入
from forms import AlgorithmSubmissionForm  # 从根目录导入
from scoring_strategies import get_scoring_function  # 从根目录导入

problem_bp = Blueprint('problem', __name__)  # 确保蓝图已定义


# ... (detail 路由函数保持不变) ...
@problem_bp.route('/<int:problem_id>', methods=['GET', 'POST'])
@login_required
def detail(problem_id):
    problem = db.get_or_404(Problem, problem_id)
    form = AlgorithmSubmissionForm()

    if request.method == 'GET':
        form.bandwidth_mbps.data = problem.default_bandwidth_mbps
        form.latency_ms.data = problem.default_latency_ms

    if form.validate_on_submit():
        if not form.algorithm_script.data:
            flash('Please select an algorithm script file.', 'warning')  # 英文
            return render_template('problem/problem_detail.html', title=problem.title, problem=problem, form=form,
                                   submissions=Submission.query.filter_by(problem_id=problem.id,
                                                                          user_id=current_user.id)
                                   .order_by(Submission.submitted_at.desc())
                                   .paginate(page=1, per_page=current_app.config.get('SUBMISSIONS_PER_PROBLEM_PAGE', 3),
                                             error_out=False))

        script_file = form.algorithm_script.data
        base, ext = os.path.splitext(secure_filename(script_file.filename))
        unique_filename_part = uuid.uuid4().hex[:8]
        submission_script_filename = f"{base}_{current_user.id}_{problem_id}_{unique_filename_part}{ext}"

        upload_folder = current_app.config['UPLOAD_FOLDER']
        script_save_path = os.path.join(upload_folder, submission_script_filename)

        try:
            script_file.save(script_save_path)
        except Exception as e:
            flash(f"Error saving uploaded script: {str(e)}", "danger")  # 英文
            current_app.logger.error(
                f"Error saving script {submission_script_filename} for user {current_user.id}: {e}", exc_info=True)
            return redirect(url_for('problem.detail', problem_id=problem_id))

        submission_id_str = str(uuid.uuid4())
        log_filename = f"{submission_id_str}.log"

        new_submission = Submission(
            id=submission_id_str, user_id=current_user.id, problem_id=problem.id,
            algorithm_script_filename=submission_script_filename,
            actual_bandwidth_mbps=form.bandwidth_mbps.data,
            actual_latency_ms=form.latency_ms.data,
            status=SubmissionStatus.INITIALIZING,
            log_filename=log_filename,
            submitted_at=datetime.now(timezone.utc)
        )
        db.session.add(new_submission)
        try:
            db.session.commit()
        except Exception as e_commit:
            db.session.rollback()
            flash(f"Database error during submission: {str(e_commit)}", "danger")  # 英文
            current_app.logger.error(f"DB error creating submission {submission_id_str}: {e_commit}", exc_info=True)
            if os.path.exists(script_save_path):
                try:
                    os.remove(script_save_path)
                except Exception as e_remove:
                    current_app.logger.error(f"Failed to clean up script {script_save_path}: {e_remove}")  # 英文
            return redirect(url_for('problem.detail', problem_id=problem_id))

        eval_thread = threading.Thread(
            target=run_evaluation_logic_thread,
            args=(current_app._get_current_object(), submission_id_str, script_save_path,
                  problem.dataset_identifier, form.bandwidth_mbps.data,
                  form.latency_ms.data, problem.scoring_function_name)
        )
        eval_thread.daemon = True
        eval_thread.start()

        flash('Your solution has been submitted! Evaluation has started.', 'success')  # 英文
        return redirect(url_for('submission.detail', submission_id=submission_id_str))

    page = request.args.get('page', 1, type=int)
    submissions_per_page = current_app.config.get('SUBMISSIONS_PER_PROBLEM_PAGE', 3)
    user_submissions_pagination = Submission.query.filter_by(problem_id=problem.id, user_id=current_user.id) \
        .order_by(Submission.submitted_at.desc()) \
        .paginate(page=page, per_page=submissions_per_page, error_out=False)
    return render_template('problem/problem_detail.html', title=problem.title, problem=problem,
                           form=form, submissions=user_submissions_pagination)


def run_evaluation_logic_thread(flask_app_context, submission_id, script_path, dataset_identifier_for_problem,
                                bandwidth_mbps, latency_ms, scoring_fn_name):
    with flask_app_context.app_context():
        submission = db.session.get(Submission, submission_id)
        if not submission:
            flask_app_context.logger.error(
                f"[EvalThread-{submission_id}] ERROR: Submission object not found in DB.")  # 英文
            return

        log_folder = flask_app_context.config['LOG_FOLDER']
        log_file_full_path = os.path.join(log_folder, submission.log_filename)

        submission.status = SubmissionStatus.RUNNING
        try:
            db.session.commit()
        except Exception as e_db_commit_running:
            flask_app_context.logger.error(
                f"[EvalThread-{submission_id}] DB ERROR: Failed to commit RUNNING status: {e_db_commit_running}",
                exc_info=True)  # 英文
            submission.status = SubmissionStatus.ERROR_STARTING
            submission.detailed_results = json.dumps(
                {"error": f"DB init error for running status: {str(e_db_commit_running)}"})
            try:
                db.session.commit()
            except Exception as e_final_commit_err:
                flask_app_context.logger.error(
                    f"[EvalThread-{submission_id}] DB ERROR: Failed to commit ERROR_STARTING status: {e_final_commit_err}",
                    exc_info=True)  # 英文
                db.session.rollback()
            return

        flask_app_context.logger.info(f"[EvalThread-{submission_id}] Submission status updated to RUNNING.")  # 英文

        runner_script_path = os.path.join(flask_app_context.root_path, "algorithm_runner.py")
        if not os.path.exists(runner_script_path):
            flask_app_context.logger.error(
                f"[EvalThread-{submission_id}] CRITICAL ERROR: algorithm_runner.py not found at {runner_script_path}")  # 英文
            submission.status = SubmissionStatus.ERROR_STARTING
            submission.detailed_results = json.dumps(
                {"error": "System configuration error: Runner script missing."})  # 英文
            db.session.commit()
            return

        cmd = [
            sys.executable, runner_script_path,
            "--algorithm_script", script_path,
            "--dataset_id", dataset_identifier_for_problem,
            "--bandwidth_mbps", str(bandwidth_mbps),
            "--latency_ms", str(latency_ms),
            "--task_id", submission_id
        ]

        runner_process = None
        execution_successful = False
        timeout_seconds = flask_app_context.config.get('RUNNER_TIMEOUT_SECONDS', 300)

        try:
            flask_app_context.logger.info(
                f"[EvalThread-{submission_id}] Attempting to start runner subprocess: {' '.join(cmd)}")  # 英文
            with open(log_file_full_path, 'w', encoding='utf-8') as lf:
                lf.write(f"[EVALUATION_SYSTEM] Starting evaluation at {datetime.now(timezone.utc)} UTC.\n")  # 英文
                lf.write(f"[EVALUATION_SYSTEM] Command: {' '.join(cmd)}\n\n")  # 英文
                runner_process = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT, text=True, bufsize=1,
                                                  universal_newlines=True)

            flask_app_context.logger.info(
                f"[EvalThread-{submission_id}] Runner PID {runner_process.pid} started.")  # 英文
            runner_process.wait(timeout=timeout_seconds)
            submission.return_code = runner_process.returncode
            execution_successful = (submission.return_code == 0)
            flask_app_context.logger.info(
                f"[EvalThread-{submission_id}] Runner PID {runner_process.pid} finished with code {submission.return_code}.")  # 英文

        except subprocess.TimeoutExpired:
            if runner_process and runner_process.poll() is None:
                flask_app_context.logger.warning(
                    f"[EvalThread-{submission_id}] Runner PID {runner_process.pid} timed out. Killing process.")  # 英文
                runner_process.kill()
                runner_process.wait()
            submission.status = SubmissionStatus.TIMEOUT
            submission.return_code = -100
            with open(log_file_full_path, 'a', encoding='utf-8') as lf:
                lf.write(f"\n\n[EVALUATION_SYSTEM] Execution timed out after {timeout_seconds} seconds.\n")  # 英文
            flask_app_context.logger.warning(f"[EvalThread-{submission_id}] Runner execution timed out.")  # 英文
        except FileNotFoundError as e_fnf:
            submission.status = SubmissionStatus.ERROR_STARTING
            submission.return_code = -101
            err_msg = f"[EVALUATION_SYSTEM] FileNotFoundError (e.g., runner or user script missing): {e_fnf}"  # 英文
            with open(log_file_full_path, 'a', encoding='utf-8') as lf:
                lf.write(f"\n\n{err_msg}\n")
            flask_app_context.logger.error(f"[EvalThread-{submission_id}] {err_msg}", exc_info=True)
        except Exception as e_subproc:
            submission.status = SubmissionStatus.ERROR_STARTING
            submission.return_code = -102
            err_msg = f"[EVALUATION_SYSTEM] Error running/managing subprocess: {e_subproc}"  # 英文
            with open(log_file_full_path, 'a', encoding='utf-8') as lf:
                lf.write(f"\n\n{err_msg}\n")
            flask_app_context.logger.error(f"[EvalThread-{submission_id}] {err_msg}", exc_info=True)

        submission = db.session.get(Submission, submission_id)
        if not submission:
            flask_app_context.logger.error(
                f"[EvalThread-{submission_id}] ERROR: Submission object disappeared before scoring.")  # 英文
            return

        log_content = ""
        if os.path.exists(log_file_full_path):
            try:
                with open(log_file_full_path, 'r', encoding='utf-8', errors='replace') as lf_read:
                    log_content = lf_read.read()
            except Exception as e_log_read:
                log_content = f"[EVALUATION_SYSTEM] Error reading log file for scoring: {str(e_log_read)}"  # 英文
                flask_app_context.logger.error(f"[EvalThread-{submission_id}] {log_content}", exc_info=True)

        problem_obj = db.session.get(Problem, submission.problem_id)
        if not problem_obj:
            flask_app_context.logger.error(
                f"[EvalThread-{submission_id}] ERROR: Problem P{submission.problem_id} not found for scoring.")  # 英文
            submission.status = SubmissionStatus.FAILED
            submission.score = 0.0
            submission.detailed_results = json.dumps({"error": "Problem definition missing for scoring."})  # 英文
        else:
            scoring_function_to_call = get_scoring_function(scoring_fn_name)
            flask_app_context.logger.info(
                f"[EvalThread-{submission_id}] Applying scoring function '{scoring_fn_name}'.")  # 英文
            try:
                score, detailed_results_dict = scoring_function_to_call(log_content, submission, problem_obj)
                submission.score = score
                submission.detailed_results = json.dumps(detailed_results_dict, indent=2, ensure_ascii=False)
            except Exception as e_scoring:
                flask_app_context.logger.error(
                    f"[EvalThread-{submission_id}] ERROR during scoring function '{scoring_fn_name}': {e_scoring}",
                    exc_info=True)  # 英文
                submission.score = 0.0
                submission.detailed_results = json.dumps(
                    {"error": "Scoring function failed.", "details": str(e_scoring)})  # 英文

        if submission.status not in [SubmissionStatus.FAILED, SubmissionStatus.ERROR_STARTING,
                                     SubmissionStatus.TIMEOUT]:
            submission.status = SubmissionStatus.COMPLETED if execution_successful else SubmissionStatus.FAILED

        try:
            db.session.commit()
            flask_app_context.logger.info(
                f"[EvalThread-{submission_id}] Final submission status: {submission.status.value}, Score: {submission.score}.")  # 英文
        except Exception as e_db_final:
            flask_app_context.logger.error(
                f"[EvalThread-{submission_id}] DB ERROR: Failed to commit final submission state: {e_db_final}",
                exc_info=True)  # 英文
            db.session.rollback()
