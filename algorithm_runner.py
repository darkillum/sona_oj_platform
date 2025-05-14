# sonar_oj_platform_project_root/algorithm_runner.py
import grpc
import time
import argparse
import importlib.util
import sys
import os
import evaluation_platform_pb2
import evaluation_platform_pb2_grpc


def load_user_algorithm_func(script_path):
    module_name = os.path.splitext(os.path.basename(script_path))[0]
    try:
        spec = importlib.util.spec_from_file_location(module_name, script_path)
        if spec is None or spec.loader is None:
            # 英文错误信息
            raise ImportError(f"Could not create module spec from '{script_path}'")

        user_module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = user_module
        spec.loader.exec_module(user_module)
    except Exception as e:
        # 英文错误信息
        print(f"[Runner] CRITICAL: Error loading/executing user script '{script_path}': {e}", file=sys.stderr)
        raise

    if hasattr(user_module, 'process_chunk') and callable(user_module.process_chunk):
        return user_module.process_chunk
    else:
        msg = (f"Function 'process_chunk(data_chunk_bytes, sequence_number, server_timestamp_ns)' "
               f"not found or not callable in script '{script_path}'.")  # 英文
        print(f"[Runner] CRITICAL: {msg}", file=sys.stderr)
        raise AttributeError(msg)


def run_evaluation_client(runner_args):
    # 所有 print 语句使用英文
    print(f"[Runner Start] Task ID: {runner_args.task_id}, Script: '{runner_args.algorithm_script}'")
    print(f"[Runner Config] Dataset: '{runner_args.dataset_id}', "
          f"BW: {runner_args.bandwidth_mbps} Mbps, Delay: {runner_args.latency_ms} ms")

    try:
        user_process_chunk = load_user_algorithm_func(runner_args.algorithm_script)
    except Exception:
        return 1

    grpc_server_address = 'localhost:50051'
    channel = None
    stub = None
    max_retries = 5
    retry_delay_seconds = 2

    for attempt in range(max_retries):
        try:
            print(
                f"[Runner] Attempting to connect to gRPC server: {grpc_server_address} (Attempt {attempt + 1}/{max_retries})...")
            channel_options = [
                ('grpc.keepalive_time_ms', 10000),
                ('grpc.keepalive_timeout_ms', 5000),
                ('grpc.keepalive_permit_without_calls', True),
            ]
            channel = grpc.insecure_channel(grpc_server_address, options=channel_options)
            grpc.channel_ready_future(channel).result(timeout=5)
            stub = evaluation_platform_pb2_grpc.EvaluationServiceStub(channel)
            print(f"[Runner] Successfully connected to gRPC server {grpc_server_address}.")
            break
        except grpc.FutureTimeoutError:
            print(f"[Runner] WARNING: gRPC server connection timed out (Attempt {attempt + 1}). Retrying...")
            if channel:
                channel.close()
            if attempt < max_retries - 1:
                time.sleep(retry_delay_seconds)
            else:
                print(f"[Runner] CRITICAL ERROR: Max retries reached. Failed to connect to gRPC server.",
                      file=sys.stderr)
                return 2
        except Exception as e_channel:
            print(
                f"[Runner] CRITICAL ERROR: Unknown error during gRPC channel creation (Attempt {attempt + 1}): {e_channel}",
                file=sys.stderr)
            if channel:
                channel.close()
            if attempt < max_retries - 1:
                time.sleep(retry_delay_seconds)
            else:
                return 2

    if not stub:
        print(f"[Runner] CRITICAL ERROR: Failed to initialize gRPC stub after all retries.", file=sys.stderr)
        return 2

    device_config_msg = evaluation_platform_pb2.DeviceConfig(
        simulated_bandwidth_mbps=float(runner_args.bandwidth_mbps),
        simulated_delay_ms=int(runner_args.latency_ms)
    )
    request_msg = evaluation_platform_pb2.EvaluationRequest(
        dataset_id=runner_args.dataset_id,
        device_config=device_config_msg
    )

    start_time_client = time.monotonic()
    total_data_received_bytes = 0
    chunks_processed_count = 0

    try:
        print(f"[Runner] Sending EvaluateAlgorithm request to gRPC server (Dataset: '{runner_args.dataset_id}')...")
        stream_iterator = stub.EvaluateAlgorithm(request_msg, timeout=60.0)
        print(f"[Runner] Obtained stream iterator, starting to receive data...")
        for chunk in stream_iterator:
            client_receive_ts_ns = time.time_ns()
            try:
                user_process_chunk(
                    chunk.data,
                    chunk.sequence_number,
                    chunk.timestamp_ns
                )
            except Exception as e_user_code:
                print(
                    f"[Runner] ERROR: User script process_chunk (Chunk {chunk.sequence_number}) execution error: {e_user_code}",
                    file=sys.stderr)

            total_data_received_bytes += len(chunk.data)
            chunks_processed_count += 1
            if chunks_processed_count % 50 == 0:
                print(f"[Runner] Processed {chunks_processed_count} chunks for dataset '{runner_args.dataset_id}'.")

        print(f"[Runner] Data stream processing finished for dataset '{runner_args.dataset_id}'.")

    except grpc.RpcError as e_grpc:
        print(f"[Runner] CRITICAL: gRPC call failed: Code={e_grpc.code()}, Details='{e_grpc.details()}'",
              file=sys.stderr)
        if e_grpc.code() == grpc.StatusCode.UNAVAILABLE:
            print(f"[Runner Detail] Could not connect to gRPC server {grpc_server_address}. Is it running?",
                  file=sys.stderr)
        elif e_grpc.code() == grpc.StatusCode.NOT_FOUND:
            print(f"[Runner Detail] Dataset '{runner_args.dataset_id}' might not be found on the gRPC server.",
                  file=sys.stderr)
        elif e_grpc.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
            print(f"[Runner Detail] gRPC call timed out. Server might be too slow or there's a network issue.",
                  file=sys.stderr)
        return 2
    except Exception as e_unexpected:
        print(f"[Runner] CRITICAL: Unexpected error during gRPC communication or processing loop: {e_unexpected}",
              file=sys.stderr)
        return 3
    finally:
        if channel:
            channel.close()
            print(f"[Runner] gRPC channel closed.")

        end_time_client = time.monotonic()
        duration_client_s = end_time_client - start_time_client
        print(f"[Runner] Client-side processing loop ended.")
        print(
            f"[Runner] Final count: Processed {chunks_processed_count} chunks. Total bytes: {total_data_received_bytes}.")
        print(
            f"[Runner] Client-side duration (incl. network simulation & user processing): {duration_client_s:.3f} seconds.")

    print(f"[Runner] Evaluation logic completed for task {runner_args.task_id}.")
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Algorithm Runner Client for Sonar OJ Platform")
    parser.add_argument("--algorithm_script", required=True, help="Path to user's Python algorithm script.")
    parser.add_argument("--dataset_id", required=True, help="Dataset identifier (e.g., filename for gRPC server).")
    parser.add_argument("--bandwidth_mbps", type=float, default=10.0, help="Simulated bandwidth (Mbps).")
    parser.add_argument("--latency_ms", type=int, default=50, help="Simulated latency (ms).")
    parser.add_argument("--task_id", default="N/A_direct_run", help="Submission/Task ID for logging context.")

    args = parser.parse_args()

    exit_code = 1
    try:
        exit_code = run_evaluation_client(args)
    except Exception as main_exc:
        print(f"[Runner Main] Unhandled exception: {main_exc}", file=sys.stderr)
        exit_code = 4
    finally:
        print(f"[Runner Script End] Task ID: {args.task_id}. Python script finished. Exit Code: {exit_code}")
        sys.stdout.flush()
        sys.stderr.flush()
        sys.exit(exit_code)
