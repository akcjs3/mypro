# save_analysis.py
import json
from db import execute

def save_analysis_to_db(user_id: int, result: dict):
    params = {
        "session_id": result.get("session_id"),
        "user_id": user_id,
        "usage_index": result.get("usage_index"),
        "selected_task": result.get("selected_task"),
        "final_label": result.get("final_label"),
        "focus_percent": result.get("focus_percent"),
        "focus_ratio": result.get("focus_ratio"),
        "session_start": result.get("session_start"),
        "session_end": result.get("session_end"),
        "input_per_min": result.get("engagement", {}).get("input_per_min"),
        "total_input": result.get("engagement", {}).get("total_input"),
        "idle_time_sec": result.get("engagement", {}).get("idle_time_sec"),
        "capture_count": result.get("process", {}).get("capture_count"),

        "activity_distribution_json": json.dumps(result.get("activity_distribution"), ensure_ascii=False),
        "screen_probs_json": json.dumps(result.get("screen", {}).get("screen_probs"), ensure_ascii=False),
        "window_titles_json": json.dumps(result.get("window", {}).get("titles"), ensure_ascii=False),
        "window_labels_json": json.dumps(result.get("window", {}).get("labels"), ensure_ascii=False)
    }

    q = """
    INSERT INTO sessions (
        session_id, user_id, usage_index, selected_task,
        final_label, focus_percent, focus_ratio,
        session_start, session_end,
        input_per_min, total_input, idle_time_sec, capture_count,
        activity_distribution_json, screen_probs_json,
        window_titles_json, window_labels_json
    ) VALUES (
        %(session_id)s, %(user_id)s, %(usage_index)s, %(selected_task)s,
        %(final_label)s, %(focus_percent)s, %(focus_ratio)s,
        %(session_start)s, %(session_end)s,
        %(input_per_min)s, %(total_input)s, %(idle_time_sec)s, %(capture_count)s,
        %(activity_distribution_json)s, %(screen_probs_json)s,
        %(window_titles_json)s, %(window_labels_json)s
    );
    """

    execute(q, params)
