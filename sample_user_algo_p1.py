# sample_user_algo_p1.py

# This script must contain a function:
# process_chunk(data_chunk_bytes, sequence_number, timestamp_ns)

# --- State for accumulation across chunks ---
# This state should be managed carefully if the runner were to execute
# multiple problem types or be re-entrant without re-initialization.
# For the current model (one script per problem run), global is fine.
current_problem_total_echoes = 0
chunks_processed_by_user_script = 0


def process_chunk(data_chunk_bytes, sequence_number, server_timestamp_ns):
    """
    Processes a single chunk of sonar data to count "echoes".
    An "echo" is a byte with a value greater than 200 (0xC8).
    Logs the final accumulated count using [USER_METRIC] tag.
    """
    global current_problem_total_echoes, chunks_processed_by_user_script

    if sequence_number == 1:  # Reset for a new stream (if script instance was reused)
        current_problem_total_echoes = 0
        chunks_processed_by_user_script = 0

    chunk_echoes = 0
    for byte_val in data_chunk_bytes:
        if byte_val > 200:  # 0xC8
            chunk_echoes += 1

    current_problem_total_echoes += chunk_echoes
    chunks_processed_by_user_script += 1

    # This specific print is for the scoring system to parse.
    # It will be printed after processing each chunk. The scorer should pick the last one or be designed accordingly.
    print(f"[USER_METRIC] Total_Echoes: {current_problem_total_echoes}")

    # Optional: Return a string for per-chunk logging by the runner (if runner is modified to print it)
    # return f"Chunk {sequence_number} had {chunk_echoes} echoes. Cumulative: {current_problem_total_echoes}"
    return None  # Or some other meaningful per-chunk result if desired for debugging