# sample_user_algo_p2.py

# This script must contain a function:
# process_chunk(data_chunk_bytes, sequence_number, timestamp_ns)

# --- State for accumulation and handling chunk boundaries ---
current_problem_total_anomalies = 0
# Buffer to handle anomalies spanning across chunk boundaries
# Max length of anomaly pattern (0xFF, 0xFF, 0xFF) is 3. Buffer needs to be pattern_len - 1.
previous_bytes_buffer = b''


def process_chunk(data_chunk_bytes, sequence_number, server_timestamp_ns):
    """
    Processes a single chunk to detect anomalies (three consecutive 0xFF bytes).
    Handles anomalies that might span across chunk boundaries.
    Logs the final accumulated count using [USER_METRIC] tag.
    """
    global current_problem_total_anomalies, previous_bytes_buffer

    if sequence_number == 1:  # Reset for a new stream
        current_problem_total_anomalies = 0
        previous_bytes_buffer = b''

    # Combine with buffer from previous chunk
    data_to_scan = previous_bytes_buffer + data_chunk_bytes

    chunk_anomalies = 0
    i = 0
    # Iterate up to a point where a full pattern can still be found
    while i <= len(data_to_scan) - 3:
        if data_to_scan[i:i + 3] == b'\xFF\xFF\xFF':
            chunk_anomalies += 1
            i += 3  # Move past the found anomaly to avoid overlapping counts if desired
            # Or i += 1 if overlapping anomalies should be counted
        else:
            i += 1

    current_problem_total_anomalies += chunk_anomalies

    # Update buffer for the next chunk: last (pattern_length - 1) bytes
    # Anomaly is 3 bytes, so buffer last 2 bytes.
    if len(data_to_scan) >= 2:
        previous_bytes_buffer = data_to_scan[-2:]
    elif len(data_to_scan) == 1:  # data_to_scan could be shorter than 2 if data_chunk_bytes is very small
        previous_bytes_buffer = data_to_scan[-1:]
    else:  # data_to_scan is empty
        previous_bytes_buffer = b''

    # This specific print is for the scoring system to parse.
    print(f"[USER_METRIC] Anomalies_Found: {current_problem_total_anomalies}")

    # return f"Chunk {sequence_number} had {chunk_anomalies} anomalies. Cumulative: {current_problem_total_anomalies}"
    return None