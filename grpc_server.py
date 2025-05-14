# sonar_oj_platform_project_root/grpc_server.py
import grpc
from concurrent import futures
import time
import os
import evaluation_platform_pb2
import evaluation_platform_pb2_grpc

PROBLEM_DATA_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'problem_data')
DEFAULT_CHUNK_SIZE = 64 * 1024


class EvaluationServiceImpl(evaluation_platform_pb2_grpc.EvaluationServiceServicer):
    def EvaluateAlgorithm(self, request: evaluation_platform_pb2.EvaluationRequest, context):
        dataset_identifier = request.dataset_id
        # 更详细的请求接收日志
        print(f"[gRPC Server] === New Request Received ===")
        print(f"[gRPC Server] Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"[gRPC Server] Dataset Identifier: '{dataset_identifier}'")
        print(f"[gRPC Server] Client Peer: {context.peer()}")
        print(
            f"[gRPC Server] Network Config: BW={request.device_config.simulated_bandwidth_mbps} Mbps, Delay={request.device_config.simulated_delay_ms} ms")

        data_file_path = os.path.join(PROBLEM_DATA_FOLDER, dataset_identifier)

        if not dataset_identifier or not os.path.isfile(data_file_path):
            error_msg = f"Dataset file not found or invalid identifier: '{data_file_path}'"
            print(f"[gRPC Server] ERROR: {error_msg}")
            context.abort(grpc.StatusCode.NOT_FOUND, error_msg)
            return

        device_config = request.device_config
        delay_s = device_config.simulated_delay_ms / 1000.0 if device_config.simulated_delay_ms > 0 else 0
        bytes_per_second = (device_config.simulated_bandwidth_mbps * 1000 * 1000 / 8.0) \
            if device_config.simulated_bandwidth_mbps > 0 else float('inf')

        sequence_num = 0
        try:
            print(f"[gRPC Server] Starting to stream data from: '{data_file_path}' for client {context.peer()}")
            with open(data_file_path, "rb") as f:
                while context.is_active():
                    chunk_data = f.read(DEFAULT_CHUNK_SIZE)
                    if not chunk_data:
                        print(
                            f"[gRPC Server] End of file reached for '{dataset_identifier}' for client {context.peer()}.")
                        break

                    sequence_num += 1
                    if bytes_per_second != float('inf') and bytes_per_second > 0:
                        time_to_send_chunk_s = len(chunk_data) / bytes_per_second
                        time.sleep(time_to_send_chunk_s)

                    if delay_s > 0:
                        time.sleep(delay_s)

                    chunk_message = evaluation_platform_pb2.SonarDataChunk(
                        sequence_number=sequence_num,
                        data=chunk_data,
                        timestamp_ns=time.time_ns()
                    )
                    yield chunk_message
                    if sequence_num % 50 == 0:
                        print(
                            f"[gRPC Server] Sent chunk {sequence_num} for '{dataset_identifier}' to client {context.peer()}")

            if not context.is_active():
                print(
                    f"[gRPC Server] Client {context.peer()} for '{dataset_identifier}' disconnected during streaming.")

        except grpc.RpcError as rpc_error:
            print(
                f"[gRPC Server] RpcError during streaming for '{dataset_identifier}' (client {context.peer()}): {rpc_error.code()} - {rpc_error.details()}")
        except Exception as e:
            err_stream = f"Unexpected error during streaming for '{dataset_identifier}' (client {context.peer()}): {e}"
            print(f"[gRPC Server] ERROR: {err_stream}")
            if context.is_active():
                context.abort(grpc.StatusCode.INTERNAL, err_stream)
        finally:
            print(
                f"[gRPC Server] Finished streaming {sequence_num} chunks for '{dataset_identifier}' to client {context.peer()}.")
            print(f"[gRPC Server] === Request Processing Ended for client {context.peer()} ===")


def serve():
    os.makedirs(PROBLEM_DATA_FOLDER, exist_ok=True)

    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10),
        # 选项可以帮助调试连接问题，例如 keepalive
        options=[
            ('grpc.keepalive_time_ms', 10000),  # 每 10 秒发送一次 keepalive ping
            ('grpc.keepalive_timeout_ms', 5000),  # 如果 ping 没有在 5 秒内得到确认，则认为连接断开
            ('grpc.keepalive_permit_without_calls', True),  # 即使没有活动调用也允许 keepalive
            ('grpc.http2.min_time_between_pings_ms', 10000),  # 两次 ping 之间的最小间隔
            ('grpc.http2.max_pings_without_data', 0),  # 允许无限次的没有数据的 ping (如果为0)
        ]
    )
    evaluation_platform_pb2_grpc.add_EvaluationServiceServicer_to_server(EvaluationServiceImpl(), server)

    listen_addr = '[::]:50051'  # 监听所有 IPv4 和 IPv6 接口
    try:
        server.add_insecure_port(listen_addr)
        server.start()
        print(f"[gRPC Server] Successfully started on {listen_addr}, serving data from '{PROBLEM_DATA_FOLDER}'")
        print("[gRPC Server] Server is running. Press CTRL+C to stop.")
        # 使用 time.sleep() 循环替代 server.wait_for_termination() 以保持主线程活动并允许捕获 KeyboardInterrupt
        while True:
            time.sleep(3600)  # 每小时唤醒一次，或直到被中断
    except OSError as e:
        print(
            f"[gRPC Server] ERROR: Could not start server on {listen_addr}. Port might be in use or permission denied. Details: {e}")
    except KeyboardInterrupt:
        print("[gRPC Server] Stopping server due to KeyboardInterrupt...")
    finally:
        if 'server' in locals() and server:
            server.stop(grace=5)  # 给予 5 秒的优雅关闭时间
            print("[gRPC Server] Server shut down gracefully.")


if __name__ == '__main__':
    serve()
