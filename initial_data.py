# sonar_oj_platform_project_root/initial_data.py
import os
import sys
from datetime import datetime, timezone
from models import db, User, UserRole, Problem  # 从项目根目录的 models.py 导入


def create_initial_data_cli(flask_app):  # flask_app 用于获取应用上下文和配置
    with flask_app.app_context():
        # 创建管理员用户
        if not User.query.filter_by(username='admin').first():
            admin_user = User(username='admin', email='admin@sonaroj.com', role=UserRole.ADMIN)
            # 建议从环境变量或安全配置中获取默认密码
            admin_user.set_password(os.environ.get('ADMIN_DEFAULT_PASSWORD', 'AdminPass123!'))
            db.session.add(admin_user)
            print("管理员用户 'admin' 已创建。")

        # 创建参赛者用户
        if not User.query.filter_by(username='contestant1').first():
            contestant_user = User(username='contestant1', email='contestant1@sonaroj.com', role=UserRole.CONTESTANT)
            contestant_user.set_password(os.environ.get('CONTESTANT_DEFAULT_PASSWORD', 'ContestantPass123!'))
            db.session.add(contestant_user)
            print("用户 'contestant1' 已创建。")

        problem_data_list = [
            {
                "title": 'Sonar Echo Counter',
                "description": '''处理模拟声纳信号数据流。每个数据块代表一个小的时间窗口。
您的算法应计算整个数据流中的“回声”数量。
“回声”定义为任何值大于 200 (0xC8) 的字节。
脚本中的 `process_chunk` 函数将接收 `data_chunk_bytes`、`sequence_number` 和 `server_timestamp_ns`。
在处理结束时（或在每个块后更新），使用以下格式打印总回声数：`print(f"[USER_METRIC] Total_Echoes: {your_total_count}")`。
数据集是一个约 1MB 的二进制流。''',
                "dataset_identifier": 'problem1_data.bin',
                "default_bandwidth_mbps": 5.0, "default_latency_ms": 100,
                "scoring_function_name": 'default_log_scorer',
                "data_size_mb": 1  # 用于生成虚拟数据
            },
            {
                "title": 'Stream Anomaly Detector',
                "description": '''分析连续数据流中的异常模式。
“异常”定义为三个连续的 0xFF 字节 (即 `b'\\xff\\xff\\xff'`)。
您的任务是计算在流中找到的此类异常的总数。请注意处理跨数据块边界的异常情况。
在处理结束时（或在每个块后更新），打印总异常数：`print(f"[USER_METRIC] Anomalies_Found: {your_anomaly_count}")`
数据集是一个约 2MB 的二进制流，其中包含一些注入的异常点。''',
                "dataset_identifier": 'problem2_data.bin',
                "default_bandwidth_mbps": 20.0, "default_latency_ms": 20,
                "scoring_function_name": 'default_log_scorer',
                "data_size_mb": 2  # 用于生成虚拟数据
            }
        ]

        for p_data in problem_data_list:
            if not Problem.query.filter_by(title=p_data["title"]).first():
                problem_data_filename = p_data["dataset_identifier"]
                problem_data_path = os.path.join(flask_app.config['PROBLEM_DATA_FOLDER'], problem_data_filename)

                if not os.path.exists(problem_data_path):
                    size_mb = p_data.get("data_size_mb", 1)
                    try:
                        with open(problem_data_path, "wb") as f:
                            if p_data["title"] == 'Stream Anomaly Detector':  # 为P2生成特定数据
                                base_chunk = os.urandom(1024)  # 基础随机数据块
                                for _ in range(size_mb * 1024 // len(base_chunk)):  # 写入大约 size_mb MB
                                    f.write(base_chunk)
                                # 注入一些异常点
                                num_anomalies_to_inject = min(20, size_mb * 5)  # 根据文件大小注入
                                file_current_size = f.tell()
                                if file_current_size > 3:  # 确保文件足够大以注入
                                    for i in range(num_anomalies_to_inject):
                                        # 尝试在随机位置注入，避免过于规律
                                        # 使用简单的伪随机，避免依赖外部哈希库导致的问题
                                        seed = (i * 13 + flask_app.config['SECRET_KEY'].encode().__len__()) % (
                                                    file_current_size - 3)
                                        seek_pos = seed
                                        try:
                                            f.seek(seek_pos)
                                            f.write(b'\xFF\xFF\xFF')
                                        except Exception:
                                            pass  # 如果seek失败（不太可能），则跳过
                            else:  # 其他题目使用通用随机数据
                                f.write(os.urandom(size_mb * 1024 * 1024))
                        print(f"已为题目 '{p_data['title']}' 创建虚拟数据文件: {problem_data_path}")
                    except Exception as e_file:
                        print(f"错误：创建虚拟数据文件 {problem_data_path} 失败: {e_file}", file=sys.stderr)

                new_problem_obj = Problem(  # 重命名变量以避免与外部 problem 冲突
                    title=p_data["title"], description=p_data["description"],
                    dataset_identifier=p_data["dataset_identifier"],
                    default_bandwidth_mbps=p_data["default_bandwidth_mbps"],
                    default_latency_ms=p_data["default_latency_ms"],
                    scoring_function_name=p_data["scoring_function_name"],
                    created_at=datetime.now(timezone.utc)
                )
                db.session.add(new_problem_obj)
                print(f"题目 '{p_data['title']}' 已创建。")

        try:
            db.session.commit()
            print("初始数据提交成功。")
        except Exception as e_commit:
            db.session.rollback()
            print(f"错误：提交初始数据时出错: {e_commit}", file=sys.stderr)