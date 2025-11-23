import os
import json
import webbrowser
import smtplib
import ssl
import random
import string
from email.message import EmailMessage
from datetime import datetime, timedelta
from pathlib import Path
from auth import create_token
from flask import Flask, render_template, jsonify, send_from_directory, request
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from mysql.connector import pooling

from analyzer import analyze_and_save
from session_logger import start_session_logging, stop_session_logging

app = Flask(__name__)

# ==============================
# 경로 / 설정
# ==============================

# backend/ 절대경로
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ✅ (수정 1) backend/data 로 통일
# 기존: DATA_DIR = os.path.join(BASE_DIR, "..", "data")
DATA_DIR = os.path.join(BASE_DIR, "data")

ANALYZER_SESSION_LOG_DIR = Path(DATA_DIR) / "session_logs"
ANALYZER_SESSION_LOG_DIR.mkdir(parents=True, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# 퍼지/분석 결과 JSON 저장 경로
DATA_PATH = os.path.join(DATA_DIR, "result.json")

# 단순 테스트용 세션 상태
current_test_session = {
    "is_running": False,
    "user_id": None,
    "selected_task": None,
    "session_id": None,
    "usage_index": None,
}

# 유저별 검사 횟수 카운터 (메모리 기반)
user_run_counts = {}  # { user_id: n_th_test }

# 활동 타입별 분류
ACTIVE_TASKS = {"game", "sns", "webtoon"}          # 입력이 있어야 하는 쪽
PASSIVE_TASKS = {"youtube-ent", "youtube-music"}   # 시청/청취 위주
# 세션 길이 최소 기준 (이보다 짧으면 신뢰도 낮음)
MIN_SESSION_SEC = 30  # analyzer.py에서 사용하는 기준과 맞추기

# ==============================
# DB / 이메일 설정
# ==============================

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "1210"),  # 네 비밀번호
    "database": os.getenv("DB_NAME", "monitor_sketcher"),
}

SMTP_HOST = "smtp.gmail.com"       # 예: "smtp.gmail.com"
SMTP_PORT = 465
SMTP_USER = "akcjs31@gmail.com"
SMTP_PASS = "nhxn cltl wjbt kucx"
EMAIL_FROM = SMTP_USER

# MySQL 커넥션 풀
db_pool = pooling.MySQLConnectionPool(
    pool_name="ms_pool",
    pool_size=5,
    **DB_CONFIG
)


# ==============================
# 유틸 함수
# ==============================

def generate_code(length: int = 6) -> str:
    """6자리 숫자 코드 생성 (예: 493201)"""
    return "".join(random.choices(string.digits, k=length))


def send_verification_email(to_email: str, code: str):
    """
    실제 이메일 전송 함수.
    - 로컬 개발 단계에서 SMTP 설정 안 돼 있으면, 그냥 콘솔에 출력만 하고 넘어감.
    """
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS:
        print("=== [DEV] 이메일 전송 스킵 ===")
        print(f"수신자: {to_email}")
        print(f"인증코드: {code}")
        print("SMTP 설정이 없어서 콘솔에만 출력했습니다.")
        return

    msg = EmailMessage()
    msg["Subject"] = "Monitor Sketcher 이메일 인증 코드"
    msg["From"] = EMAIL_FROM
    msg["To"] = to_email
    msg.set_content(
        f"Monitor Sketcher 이메일 인증 코드입니다.\n\n인증 코드: {code}\n\n10분 이내에 입력해주세요."
    )

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)


# ==============================
# 프론트엔드 페이지 라우팅 (frontend 폴더)
# ==============================

FRONT_BASE = os.path.join(BASE_DIR, "..", "frontend")      # ../frontend

@app.route("/")
def front_index():
    """메인 서비스 화면 (frontend/index.html)"""
    return send_from_directory(FRONT_BASE, "index.html")

@app.route("/index.html")
def front_index_html():
    return send_from_directory(FRONT_BASE, "index.html")

@app.route("/login.html")
def login_page():
    return send_from_directory(FRONT_BASE, "login.html")


@app.route("/signup.html")
def signup_page():
    return send_from_directory(FRONT_BASE, "signup.html")


@app.route("/test.html")
def test_page():
    return send_from_directory(FRONT_BASE, "test.html")


@app.route("/ranking.html")
def ranking_page():
    return send_from_directory(FRONT_BASE, "ranking.html")


@app.route("/contact.html")
def contact_page():
    return send_from_directory(FRONT_BASE, "contact.html")


@app.route("/about.html")
def about_page():
    return send_from_directory(FRONT_BASE, "about.html")


@app.route("/mypage.html")
def mypage_page():
    return send_from_directory(FRONT_BASE, "mypage.html")


# front 정적 파일(css, js, 이미지 등)
@app.route("/css/<path:filename>")
def front_css(filename):
    return send_from_directory(os.path.join(FRONT_BASE, "css"), filename)


@app.route("/js/<path:filename>")
def front_js(filename):
    return send_from_directory(os.path.join(FRONT_BASE, "js"), filename)


@app.route("/src/<path:filename>")
def front_src(filename):
    return send_from_directory(os.path.join(FRONT_BASE, "src"), filename)


# 퍼지 결과 대시보드 페이지 (기존 backend/index.html)
@app.route("/result")
def result_page():
    """검사 결과 보기 화면 (backend/index.html)"""
    return send_from_directory(".", "index.html")

@app.route("/api/ranking/daily", methods=["GET"])
def api_daily_ranking():
    """
    일일 누적 집중도 TOP10
    - date=YYYY-MM-DD (없으면 오늘)
    - sessions.focus_percent 합으로 누적 집중도 계산
    """
    date_str = request.args.get("date")  # optional

    try:
        if date_str:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        else:
            target_date = datetime.now().date()
    except ValueError:
        return jsonify(ok=False, error="invalid date"), 400

    conn = db_pool.get_connection()
    cur = conn.cursor(dictionary=True)

    try:
        sql = """
SELECT 
    u.nickname,
    u.id AS user_id,
    SUM(COALESCE(s.focus_percent, 0)) AS total_focus,
    COUNT(*) AS session_count
FROM sessions s
JOIN users u ON s.user_id = u.id
WHERE DATE(s.created_at) = %s
GROUP BY s.user_id
ORDER BY total_focus DESC
LIMIT 10
"""
        cur.execute(sql, (target_date,))
        rows = cur.fetchall()

        ranking = []
        for i, r in enumerate(rows):
            ranking.append({
                "rank": i + 1,
                "user_id": r["user_id"],
                "nickname": r.get("nickname") or f"User {r['user_id']}",
                "total_focus": float(r.get("total_focus") or 0),
                "session_count": int(r.get("session_count") or 0),
            })

        return jsonify(ok=True, date=str(target_date), ranking=ranking)

    finally:
        cur.close()
        conn.close()


# ✅ /api/ranking/today : 프론트 호환용 (오늘 랭킹)
@app.route("/api/ranking/today", methods=["GET"])
def api_ranking_today():
    """
    프론트가 /api/ranking/today 로 부를 수 있게 만든 호환 API.
    내부적으로는 daily 랭킹(오늘 날짜)과 동일한 결과를 반환.
    응답 키도 ranking.js가 쓰는 형태(user, score)로 맞춰줌.
    """
    target_date = datetime.now().date()

    conn = db_pool.get_connection()
    cur = conn.cursor(dictionary=True)

    try:
        sql = """
        SELECT 
            u.nickname,
            u.id AS user_id,
            SUM(COALESCE(s.focus_percent, 0)) AS total_focus,
            COUNT(*) AS session_count
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE DATE(s.created_at) = %s
        GROUP BY s.user_id
        ORDER BY total_focus DESC
        LIMIT 10
        """
        cur.execute(sql, (target_date,))
        rows = cur.fetchall()

        ranking = []
        for i, r in enumerate(rows):
            ranking.append({
                "rank": i + 1,
                "user_id": r["user_id"],
                # ✅ 프론트가 list[n].user 로 읽으니까 user 키도 같이 준다
                "user": r.get("nickname") or f"User {r['user_id']}",
                "nickname": r.get("nickname") or f"User {r['user_id']}",
                # ✅ 프론트가 score로 읽을 수도 있으니 score도 같이 준다
                "score": float(r.get("total_focus") or 0),
                "total_focus": float(r.get("total_focus") or 0),
                "session_count": int(r.get("session_count") or 0),
            })

        return jsonify(ok=True, date=str(target_date), ranking=ranking)

    finally:
        cur.close()
        conn.close()

# ==============================
# 퍼지 결과 API
# ==============================

@app.route("/api/result")
def get_result():
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)
    else:
        return jsonify({"error": "No result.json found. Please run a test first."})


# ==============================
# DB 테스트용
# ==============================

@app.route("/api/ping")
def ping():
    try:
        conn = db_pool.get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT 1 AS result")
        row = cur.fetchone()
        cur.close()
        conn.close()
        return jsonify({"ok": True, "db": row["result"]})
    except Exception as e:
        print("DB 테스트 실패:", e)
        return jsonify({"ok": False, "message": "DB 연결 실패"}), 500


# ==============================
# 1) 인증번호 전송 API
# ==============================

@app.route("/api/send-code", methods=["POST"])
def send_code():
    try:
        data = request.get_json() or {}
        email = (data.get("email") or "").strip()

        if not email:
            return jsonify({"ok": False, "message": "이메일을 입력해주세요."}), 400

        conn = db_pool.get_connection()
        cur = conn.cursor(dictionary=True)

        # 이미 해당 이메일로 가입된 유저가 있으면 막을지 말지는 정책에 따라
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        existing = cur.fetchone()
        if existing:
            cur.close()
            conn.close()
            return jsonify({"ok": False, "message": "이미 가입된 이메일입니다."}), 409

        # 인증 코드 생성 및 만료시간 설정 (10분)
        code = generate_code(6)
        expires_at = datetime.utcnow() + timedelta(minutes=10)

        # email_verifications 테이블에 insert
        cur.execute(
            "INSERT INTO email_verifications (email, code, expires_at) VALUES (%s, %s, %s)",
            (email, code, expires_at)
        )
        conn.commit()

        cur.close()
        conn.close()

        # 실제 이메일 전송 (로컬에서는 콘솔 출력만 할 수도 있음)
        send_verification_email(email, code)

        return jsonify({"ok": True, "message": "인증번호를 전송했습니다."})

    except Exception as e:
        print("인증번호 전송 오류:", e)
        return jsonify({"ok": False, "message": "서버 오류가 발생했습니다."}), 500


# ==============================
# 2) 인증번호 확인 API
# ==============================

@app.route("/api/verify-code", methods=["POST"])
def verify_code():
    try:
        data = request.get_json() or {}
        email = (data.get("email") or "").strip()
        code = (data.get("code") or "").strip()

        if not email or not code:
            return jsonify({"ok": False, "message": "이메일과 인증번호를 입력해주세요."}), 400

        conn = db_pool.get_connection()
        cur = conn.cursor(dictionary=True)

        # 최신 코드 하나만 확인
        cur.execute(
            """
            SELECT id, expires_at
            FROM email_verifications
            WHERE email = %s AND code = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (email, code)
        )
        row = cur.fetchone()

        if not row:
            cur.close()
            conn.close()
            return jsonify({"ok": False, "message": "인증번호가 올바르지 않습니다."}), 400

        # 만료시간 체크 (UTC 기준)
        expires_at = row["expires_at"]
        if expires_at < datetime.utcnow():
            cur.close()
            conn.close()
            return jsonify({"ok": False, "message": "인증번호가 만료되었습니다."}), 400

        # verified 플래그 업데이트
        cur.execute(
            "UPDATE email_verifications SET verified = 1 WHERE id = %s",
            (row["id"],)
        )
        conn.commit()

        cur.close()
        conn.close()

        return jsonify({"ok": True, "message": "이메일 인증이 완료되었습니다."})

    except Exception as e:
        print("인증번호 확인 오류:", e)
        return jsonify({"ok": False, "message": "서버 오류가 발생했습니다."}), 500


# ==============================
# 3) 회원가입 API
# ==============================

@app.route("/api/signup", methods=["POST"])
def signup():
    try:
        data = request.get_json() or {}
        email = (data.get("email") or "").strip()
        password = data.get("password") or ""
        nickname = (data.get("nickname") or "").strip()
        student_id = (data.get("student_id") or "").strip() or None

        if not email or not password or not nickname:
            return jsonify({"ok": False, "message": "이메일, 비밀번호, 닉네임은 필수입니다."}), 400

        conn = db_pool.get_connection()
        cur = conn.cursor(dictionary=True)

        # 1) 이메일 인증 여부 확인
        cur.execute(
            """
            SELECT id
            FROM email_verifications
            WHERE email = %s
              AND verified = 1
              AND expires_at > UTC_TIMESTAMP()
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (email,)
        )
        ver = cur.fetchone()
        if not ver:
            cur.close()
            conn.close()
            return jsonify({"ok": False, "message": "이메일 인증이 필요합니다."}), 400

        # 2) 이메일/닉네임 중복 체크
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"ok": False, "message": "이미 사용 중인 이메일입니다."}), 409

        cur.execute("SELECT id FROM users WHERE nickname = %s", (nickname,))
        if cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"ok": False, "message": "이미 사용 중인 닉네임입니다."}), 409

        # 3) 비밀번호 해시
        password_hash = generate_password_hash(password)

        # 4) DB insert (email_verified = 1로 바로 저장)
        cur.execute(
            """
            INSERT INTO users (email, nickname, student_id, password_hash, email_verified)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (email, nickname, student_id, password_hash, 1)
        )
        conn.commit()
        user_id = cur.lastrowid

        cur.close()
        conn.close()
        
        token = create_token(user_id)

        return jsonify({
            "ok": True,
            "userId": user_id,
            "nickname": nickname,
            "emailVerified": True,
            "token": token,
            "message": "회원가입 성공"
        })

    except Exception as e:
        print("회원가입 오류:", e)
        return jsonify({"ok": False, "message": "서버 오류가 발생했습니다."}), 500


# ==============================
# 로그인 API
# ==============================

@app.route("/api/login", methods=["POST"])
def login():
    try:
        data = request.get_json() or {}
        email = (data.get("email") or "").strip()
        password = data.get("password") or ""

        if not email or not password:
            return jsonify({"ok": False, "message": "이메일과 비밀번호를 입력하세요."}), 400

        conn = db_pool.get_connection()
        cur = conn.cursor(dictionary=True)

        cur.execute(
            "SELECT id, email, nickname, password_hash, email_verified FROM users WHERE email = %s",
            (email,)
        )
        user = cur.fetchone()
        cur.close()
        conn.close()

        if not user:
            return jsonify({"ok": False, "message": "존재하지 않는 이메일입니다."}), 400

        if not check_password_hash(user["password_hash"], password):
            return jsonify({"ok": False, "message": "비밀번호가 일치하지 않습니다."}), 400
        
        token = create_token(user["id"])

        return jsonify({
            "ok": True,
            "userId": user["id"],
            "nickname": user["nickname"],
            "emailVerified": bool(user["email_verified"]),
            "token": token
        })

    except Exception as e:
        print("로그인 오류:", e)
        return jsonify({"ok": False, "message": "서버 오류가 발생했습니다."}), 500


# ==============================
# 검사 시작 / 종료 API
# ==============================

@app.route("/api/test/start", methods=["POST"])
def api_test_start():
    """
    검사 시작 신호.
    - 프론트에서: { userId, task } 전송
    """
    global current_test_session, user_run_counts

    try:
        data = request.get_json() or {}
        user_id = data.get("userId")
        selected_task = data.get("task")

        if not user_id:
            return jsonify({"ok": False, "message": "로그인 정보가 없습니다."}), 400

        if not selected_task:
            return jsonify({"ok": False, "message": "작업(task)을 선택해주세요."}), 400

        if current_test_session["is_running"]:
            return jsonify({"ok": False, "message": "이미 검사 중입니다."}), 400

        # 사용 횟수 ID (이 유저의 n번째 검사)
        prev_count = user_run_counts.get(user_id, 0)
        usage_index = prev_count + 1
        user_run_counts[user_id] = usage_index

        # session_id 생성 (UTC 시각 + user_id + 랜덤)
        ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
        session_id = f"{ts}_{user_id}_{rand}"

        # 세션 상태 저장
        current_test_session["is_running"] = True
        current_test_session["user_id"] = user_id
        current_test_session["selected_task"] = selected_task
        current_test_session["session_id"] = session_id
        current_test_session["usage_index"] = usage_index

        print("=== [TEST START] ===")
        print("user_id:", user_id)
        print("selected_task:", selected_task)
        print("session_id:", session_id)
        print("usage_index:", usage_index)

        # 실제 로거 시작
        start_session_logging(
            user_id=user_id,
            session_id=session_id,
            usage_index=usage_index,
            task=selected_task,
        )

        return jsonify({"ok": True})

    except Exception as e:
        print("검사 시작 오류:", e)
        # 혹시 중간까지 세팅되었으면 초기화
        current_test_session = {
            "is_running": False,
            "user_id": None,
            "selected_task": None,
            "session_id": None,
            "usage_index": None,
        }

        return jsonify({"ok": False, "message": "서버 오류가 발생했습니다."}), 500


@app.route("/api/test/stop", methods=["POST"])
def api_test_stop():
    """
    검사 종료 신호.
    - 프론트에서: { userId } 전송
    - 여기서: 로거를 멈추고, analyzer + fuzzy 로직으로 최종 라벨 계산
    """
    global current_test_session

    try:
        data = request.get_json() or {}
        user_id = data.get("userId")

        if not current_test_session["is_running"]:
            return jsonify({"ok": False, "message": "진행 중인 검사가 없습니다."}), 400

        # userId 검증
        if user_id and current_test_session["user_id"] != user_id:
            return jsonify({"ok": False, "message": "검사 사용자 정보가 일치하지 않습니다."}), 400

        print("=== [TEST STOP] ===")
        print("user_id:", current_test_session["user_id"])
        print("selected_task:", current_test_session["selected_task"])
        print("session_id:", current_test_session["session_id"])
        print("usage_index:", current_test_session["usage_index"])

        # 1) 로거 종료
        session_meta = stop_session_logging()
        print("[server] session_meta from logger:", session_meta)

        # 2) current_session_id.txt 기록 (analyzer용)
        session_id = current_test_session["session_id"]
        current_sid_path = os.path.join(DATA_DIR, "current_session_id.txt")
        try:
            with open(current_sid_path, "w", encoding="utf-8") as f:
                f.write(session_id)
        except Exception as e:
            print("[server] current_session_id.txt 기록 실패:", e)

        # 3) 분석 실행
        # ✅ (수정 2) analyzer가 정확한 세션을 찾도록 session_id 등 전달
       # 3) 분석 실행
        try:
            analyze_result = analyze_and_save(
             session_id=current_test_session["session_id"],
             user_id=current_test_session["user_id"],
             selected_task=current_test_session["selected_task"],
             usage_index=current_test_session["usage_index"],
            )
        except Exception as e:
            print("검사 종료 오류(분석 단계):", e)
            analyze_result = {}
            
        try:
            save_analysis_to_db(analyze_result, session_meta)
        except Exception as e:
            print("DB 저장 실패:", e)

        # -------------------------
        # 분석 결과 정리
        # -------------------------

        # 최종 라벨
        selected_task = current_test_session["selected_task"]
        
        predicted_label = (
            analyze_result.get("final_label")
            or analyze_result.get("predicted_label")
            or selected_task
        )

        # 활동 분포
        activity_dist = analyze_result.get("activity_distribution", {}) or {}
        dist_ratio = activity_dist.get("ratio", {}) or {}
        dist_percent = activity_dist.get("percent", {}) or {}
        selected_percent = dist_percent.get(selected_task)

        # 입력/세션 시간 정보
        window_info = analyze_result.get("window", {}) or {}
        input_info = analyze_result.get("input", {}) or {}
        engagement = analyze_result.get("engagement", {}) or {}

        session_dur = float(engagement.get("session_duration_sec") or 0.0)
        key_count = int(input_info.get("key_count", 0) or 0)
        mouse_count = int(input_info.get("mouse_count", 0) or 0)
        total_input = key_count + mouse_count

        input_per_min = (
            total_input / (session_dur / 60.0)
            if session_dur > 0 else 0.0
        )

        # engagement (analyzer 계산값 사용)
        engagement = analyze_result.get("engagement", {}) or {}
        idle_percent = engagement.get("idle_percent", 0.0)
        idle_ratio = engagement.get("idle_ratio", 0.0)

        # -------------------------
        # 신뢰도 / 경고 계산
        # -------------------------

        reliability = "high"
        warnings = []

        # other 비율이 너무 크면 신뢰도↓
        other_ratio = dist_ratio.get("other", 0.0)
        if other_ratio > 0.3:
            reliability = "medium"
            warnings.append("high_other_ratio")

        # 세션 너무 짧으면↓
        if session_dur < MIN_SESSION_SEC:
            reliability = "low"
            warnings.append("session_too_short")

        is_active_task = selected_task in ACTIVE_TASKS
        is_passive_task = selected_task in PASSIVE_TASKS
        is_study = (selected_task == "study")

        # AFK 판단 (idle_ratio 기반)
        if session_dur >= 60 and selected_percent is not None:
            if idle_ratio >= 0.5:
                if selected_percent >= 50.0:
                    if reliability == "high":
                        reliability = "medium"
                    warnings.append("high_idle_but_high_focus")
                else:
                    reliability = "low"
                    warnings.append("high_idle_low_focus")

            if is_passive_task:
                warnings.append("passive_task_focus_uncertain")

        # -------------------------
        # focus 블록 구성
        # -------------------------
        analyze_result["focus"] = {
            "selected_task": selected_task,
            "selected_task_percent": selected_percent,
            "idle_percent_of_session": idle_percent,
            "reliability": reliability,
            "warnings": warnings,
        }

        analyze_result["selected_task"] = selected_task
        analyze_result["focus_ratio"] = dist_ratio.get(selected_task)
        analyze_result["focus_percent"] = selected_percent

        # -------------------------
        # result.json 저장
        # -------------------------
        try:
            with open(DATA_PATH, "w", encoding="utf-8") as f:
                json.dump(analyze_result, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("[server] result.json 저장 실패:", e)

        # -------------------------
        # 세션 초기화 + 응답
        # -------------------------
        current_test_session = {
            "is_running": False,
            "user_id": None,
            "selected_task": None,
            "session_id": None,
            "usage_index": None,
        }

        return jsonify(
            {
                "ok": True,
                "predicted": predicted_label,      # 퍼지/분석 최종 라벨
                "analyzeResult": analyze_result,   # 상세 분석 결과 전체
                "selectedTask": selected_task,     # 사용자가 고른 라벨
                "focusPercent": selected_percent,  # 선택 라벨 기준 집중도(%)
                "idlePercent": idle_percent,       # 전체 시간 중 잠수 비율(%)
                "inputPerMin": input_per_min,
                "message": "분석 완료",
            }
        )

    except Exception as e:
        print("검사 종료 오류:", e)

        current_test_session = {
            "is_running": False,
            "user_id": None,
            "selected_task": None,
            "session_id": None,
            "usage_index": None,
        }

        return jsonify({"ok": False, "message": "서버 오류가 발생했습니다."}), 500

def _safe_load_json(p: Path):
    try:
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def _parse_date_ymd(s: str):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None
def _db_fetch_sessions(user_id: int, df=None, dt=None):
    """
    sessions 테이블에서 user_id 세션 목록 조회.
    df/dt는 dateFrom/dateTo (date 객체) 필터.
    """
    conn = db_pool.get_connection()
    cur = conn.cursor(dictionary=True)

    sql = """
        SELECT
            session_id, selected_task, final_label, focus_percent,
            session_start, session_end, created_at,
            JSON_EXTRACT(activity_distribution_json, '$.percent') AS activity_percent
        FROM sessions
        WHERE user_id = %s
    """
    params = [user_id]

    if df:
        sql += " AND DATE(created_at) >= %s"
        params.append(df.isoformat())
    if dt:
        sql += " AND DATE(created_at) <= %s"
        params.append(dt.isoformat())

    sql += " ORDER BY created_at DESC"

    cur.execute(sql, params)
    rows = cur.fetchall()

    cur.close()
    conn.close()
    return rows


def _db_fetch_session_detail(session_id: str):
    """특정 session_id 상세 조회"""
    conn = db_pool.get_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute(
        "SELECT * FROM sessions WHERE session_id = %s LIMIT 1",
        (session_id,)
    )
    row = cur.fetchone()

    cur.close()
    conn.close()
    return row

@app.route("/api/mypage/sessions", methods=["GET"])
def api_mypage_sessions():
    """
    유저별 세션 목록 (+ 날짜 필터)
    query:
      - userId (required)
      - dateFrom (optional, YYYY-MM-DD)
      - dateTo   (optional, YYYY-MM-DD)

    ✅ DB 우선 조회 → 없으면 기존 파일 스캔 fallback
    """
    user_id = request.args.get("userId", type=int)
    date_from = request.args.get("dateFrom", default="", type=str)
    date_to = request.args.get("dateTo", default="", type=str)

    if not user_id:
        return jsonify({"ok": False, "message": "userId가 필요합니다."}), 400

    df = _parse_date_ymd(date_from) if date_from else None
    dt = _parse_date_ymd(date_to) if date_to else None

    # ---------------------------
    # 1) ✅ DB 우선
    # ---------------------------
    try:
        conn = db_pool.get_connection()
        cur = conn.cursor(dictionary=True)

        sql = """
            SELECT
                session_id, selected_task, final_label, focus_percent,
                session_start, session_end, created_at
            FROM sessions
            WHERE user_id = %s
        """
        params = [user_id]

        if df:
            sql += " AND DATE(created_at) >= %s"
            params.append(df.isoformat())
        if dt:
            sql += " AND DATE(created_at) <= %s"
            params.append(dt.isoformat())

        sql += " ORDER BY created_at DESC"

        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        if rows:
            sessions = []
            for r in rows:
                ses_date = r["created_at"].date() if r.get("created_at") else None
                sessions.append({
                    "session_id": r.get("session_id"),
                    "date": ses_date.isoformat() if ses_date else None,
                    "selected_task": r.get("selected_task"),
                    "final_label": r.get("final_label"),
                    "focus_percent": r.get("focus_percent"),
                    "duration_sec": None,
                })
            return jsonify({"ok": True, "sessions": sessions})
    except Exception as e:
        print("[mypage/sessions] DB 조회 실패, 파일 fallback:", e)

    # ---------------------------
    # 2) ✅ 기존 파일 스캔 fallback
    # ---------------------------
    sessions = []
    for p in ANALYZER_SESSION_LOG_DIR.glob("*_analysis.json"):
        data = _safe_load_json(p)
        if not data:
            continue

        if int(data.get("user_id") or -1) != user_id:
            continue

        sid = data.get("session_id")
        selected_task = data.get("selected_task")
        final_label = data.get("final_label") or data.get("predicted")
        focus_percent = data.get("focus_percent")
        duration = (data.get("engagement") or {}).get("session_duration_sec")

        session_start = data.get("session_start")
        ses_date = None
        if session_start:
            try:
                ses_date = datetime.fromisoformat(session_start).date()
            except Exception:
                ses_date = None
        if ses_date is None and isinstance(sid, str) and len(sid) >= 8:
            try:
                ses_date = datetime.strptime(sid[:8], "%Y%m%d").date()
            except Exception:
                ses_date = None

        if df and ses_date and ses_date < df:
            continue
        if dt and ses_date and ses_date > dt:
            continue

        sessions.append({
            "session_id": sid,
            "date": ses_date.isoformat() if ses_date else None,
            "selected_task": selected_task,
            "final_label": final_label,
            "focus_percent": focus_percent,
            "duration_sec": duration,
        })

    sessions.sort(key=lambda x: x["date"] or "0000-00-00", reverse=True)
    return jsonify({"ok": True, "sessions": sessions})


@app.route("/api/mypage/session/<session_id>", methods=["GET"])
def api_mypage_session_detail(session_id):
    """
    특정 세션 상세 결과 반환
    ✅ DB 우선 → 없으면 파일 fallback
    """
    try:
        conn = db_pool.get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM sessions WHERE session_id=%s LIMIT 1", (session_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        if row:
            return jsonify({"ok": True, "result": row})
    except Exception as e:
        print("[mypage/session] DB 조회 실패, 파일 fallback:", e)

    p = ANALYZER_SESSION_LOG_DIR / f"{session_id}_analysis.json"
    if not p.exists():
        return jsonify({"ok": False, "message": "해당 세션 분석 파일이 없습니다."}), 404

    data = _safe_load_json(p)
    if not data:
        return jsonify({"ok": False, "message": "세션 파일 로드 실패"}), 500

    return jsonify({"ok": True, "result": data})


@app.route("/api/mypage/study-summary", methods=["GET"])
def api_mypage_study_summary():
    user_id = request.args.get("userId", type=int)
    if not user_id:
        return jsonify({"ok": False, "message": "userId가 필요합니다."}), 400

    # 1) DB 우선
    try:
        conn = db_pool.get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT session_id, focus_percent, created_at, activity_distribution_json
            FROM sessions
            WHERE user_id=%s AND selected_task='study'
            ORDER BY created_at ASC
        """, (user_id,))
        rows = cur.fetchall()
        cur.close(); conn.close()

        if rows:
            focus_trend = []
            distraction_acc = {}

            for r in rows:
                focus_trend.append({
                    "session_id": r["session_id"],
                    "focus_percent": r.get("focus_percent")
                })

                ad = r.get("activity_distribution_json") or {}
                if isinstance(ad, str):
                    try: ad = json.loads(ad)
                    except: ad = {}

                dist_ratio = (ad.get("ratio") or {})
                for label, ratio in dist_ratio.items():
                    if label in ("study", "other"):
                        continue
                    distraction_acc[label] = distraction_acc.get(label, 0.0) + float(ratio)

            distraction_rank = sorted(
                [{"label": k, "ratio_sum": v} for k, v in distraction_acc.items()],
                key=lambda x: x["ratio_sum"],
                reverse=True
            )
            top_distraction = distraction_rank[0]["label"] if distraction_rank else None

            return jsonify({
                "ok": True,
                "study_count": len(focus_trend),
                "focus_trend": focus_trend,
                "distraction_rank": distraction_rank,
                "top_distraction": top_distraction,
            })
    except Exception as e:
        print("[mypage/study-summary] DB 조회 실패, 파일 fallback:", e)

    # 2) 파일 fallback
    study_sessions = []
    distraction_acc = {}

    for p in ANALYZER_SESSION_LOG_DIR.glob("*_analysis.json"):
        data = _safe_load_json(p)
        if not data:
            continue
        if int(data.get("user_id") or -1) != user_id:
            continue
        if data.get("selected_task") != "study":
            continue

        sid = data.get("session_id")
        focus_percent = data.get("focus_percent")
        session_start = data.get("session_start")
        sort_key = session_start or sid or ""

        study_sessions.append({
            "session_id": sid,
            "session_start": session_start,
            "focus_percent": focus_percent,
            "sort_key": sort_key
        })

        dist_ratio = ((data.get("activity_distribution") or {}).get("ratio") or {})
        for label, ratio in dist_ratio.items():
            if label in ("study", "other"):
                continue
            distraction_acc[label] = distraction_acc.get(label, 0.0) + float(ratio)

    study_sessions.sort(key=lambda x: x["sort_key"])

    focus_trend = [
        {"session_id": s["session_id"], "focus_percent": s["focus_percent"]}
        for s in study_sessions
    ]

    distraction_rank = sorted(
        [{"label": k, "ratio_sum": v} for k, v in distraction_acc.items()],
        key=lambda x: x["ratio_sum"],
        reverse=True
    )
    top_distraction = distraction_rank[0]["label"] if distraction_rank else None

    return jsonify({
        "ok": True,
        "study_count": len(study_sessions),
        "focus_trend": focus_trend,
        "distraction_rank": distraction_rank,
        "top_distraction": top_distraction,
    })


@app.route("/api/sessions", methods=["GET"])
def api_sessions():
    try:
        user_id = request.args.get("user_id")
        from_date = request.args.get("from")
        to_date = request.args.get("to")

        if not user_id:
            return {"ok": False, "message": "user_id가 없습니다."}, 400

        # backend/data/session_logs 안의 *_analysis.json 파일들을 모두 스캔
        session_dir =  Path(BASE_DIR) / "data" / "session_logs"
        session_files = list(session_dir.glob("*_analysis.json"))

        results = []

        for path in session_files:
            try:
                with path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
            except:
                continue

            # user_id 매칭
            if str(data.get("user_id")) != str(user_id):
                continue

            # 세션 종료 시간
            session_end = data.get("engagement", {}).get("session_duration_sec")
            session_id = data.get("session_id")

            # 종료 시간은 logs/session_meta.csv 기반이 아닌 analysis 내부 값 기반으로 계산
            # analysis.json 안에는 session_start, session_end는 없음 → session_logs/<id>.json 참고
            raw_path = session_dir / f"{session_id}.json"
            if raw_path.exists():
                try:
                    with raw_path.open("r", encoding="utf-8") as f:
                        raw_json = json.load(f)
                    end_ts = raw_json.get("session_end")  # ISO string
                except:
                    end_ts = None
            else:
                end_ts = None

            # 날짜 필터
            if from_date and end_ts:
                if end_ts[:10] < from_date:
                    continue
            if to_date and end_ts:
                if end_ts[:10] > to_date:
                    continue

            results.append({
                "session_id": session_id,
                "final_label": data.get("final_label"),
                "selected_task": data.get("selected_task"),
                "focus_percent": data.get("focus_percent"),
                "session_end": end_ts
            })

        # 최신 순으로 정렬
        results.sort(key=lambda x: (x.get("session_end") or ""), reverse=True)

        return {"ok": True, "sessions": results}

    except Exception as e:
        print("[API] /api/sessions 오류:", e)
        return {"ok": False, "message": "세션 조회 실패"}, 500



# ================================================================
# 📌 세션 상세 조회
#    /api/session/20251122060150_1_bgm5
# ================================================================
@app.route("/api/session/<session_id>", methods=["GET"])
def api_session_detail(session_id):
    try:
        session_dir = Path(BASE_DIR) / "data" / "session_logs"

        analysis_path = session_dir / f"{session_id}_analysis.json"
        if not analysis_path.exists():
            return {"ok": False, "message": "해당 세션 분석 결과 없음"}, 404

        with analysis_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        return {"ok": True, "analyzeResult": data}

    except Exception as e:
        print("[API] /api/session/<id> 오류:", e)
        return {"ok": False, "message": "세션 상세 조회 실패"}, 500


def _parse_iso_dt(s):
    """'2025-11-22T12:34:56' 같은 ISO를 MySQL DATETIME으로"""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", ""))
    except Exception:
        return None

def save_analysis_to_db(analyze_result: dict, session_state: dict):
    """
    analyze_result(분석 dict) + current_test_session(세션상태 dict) 를
    sessions 테이블에 그대로 적재.
    실패해도 서버 죽지 않게 예외는 바깥에서 잡는 구조로.
    """
    if analyze_result is None:
        analyze_result = {}
    if session_state is None:
        session_state = {}

    # 세션 기본 메타
    session_id = session_state.get("session_id")
    user_id = session_state.get("user_id")
    usage_index = session_state.get("usage_index")
    selected_task = session_state.get("selected_task") or session_state.get("task")

    # 분석 핵심값
    final_label = (
        analyze_result.get("final_label")
        or analyze_result.get("predicted_label")
        or analyze_result.get("predicted")
    )

    focus_percent = analyze_result.get("focus_percent")
    focus_ratio = analyze_result.get("focus_ratio")

    # 시간 정보 (없으면 None으로)
    session_start = _parse_iso_dt(analyze_result.get("session_start"))
    session_end   = _parse_iso_dt(analyze_result.get("session_end"))


    # engagement / input
    engagement = analyze_result.get("engagement") or {}
    input_per_min = engagement.get("input_per_min") or analyze_result.get("input_per_min")
    total_input   = engagement.get("total_input")   or analyze_result.get("total_input")
    idle_time_sec = engagement.get("idle_time_sec")

    # capture count
    screen_block = analyze_result.get("screen") or {}
    capture_count = screen_block.get("capture_count") or engagement.get("capture_count")

    # json 통째로 저장할 것들
    activity_distribution_json = analyze_result.get("activity_distribution")
    screen_probs_json = (analyze_result.get("screen") or {}).get("screen_probs") \
                        or analyze_result.get("screen_probs")
    window_titles_json = (analyze_result.get("window") or {}).get("titles") \
                         or analyze_result.get("window_titles")
    window_labels_json = (analyze_result.get("window") or {}).get("labels") \
                         or analyze_result.get("window_labels")

    conn = db_pool.get_connection()
    cur = conn.cursor()

    sql = """
        INSERT INTO sessions (
            session_id, user_id, usage_index, selected_task, final_label,
            focus_percent, focus_ratio,
            session_start, session_end,
            input_per_min, total_input, idle_time_sec, capture_count,
            activity_distribution_json, screen_probs_json,
            window_titles_json, window_labels_json
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s,
            %s, %s,
            %s, %s, %s, %s,
            %s, %s,
            %s, %s
        )
    """

    cur.execute(sql, (
        session_id, user_id, usage_index, selected_task, final_label,
        focus_percent, focus_ratio,
        session_start, session_end,
        input_per_min, total_input, idle_time_sec, capture_count,
        json.dumps(activity_distribution_json, ensure_ascii=False) if activity_distribution_json is not None else None,
        json.dumps(screen_probs_json, ensure_ascii=False) if screen_probs_json is not None else None,
        json.dumps(window_titles_json, ensure_ascii=False) if window_titles_json is not None else None,
        json.dumps(window_labels_json, ensure_ascii=False) if window_labels_json is not None else None,
    ))

    conn.commit()
    cur.close()
    conn.close()

# ================================================================
# 📌 Study 집중도 분석
#    /api/study/summary?user_id=1
# ================================================================
@app.route("/api/study/summary", methods=["GET"])
def api_study_summary():
    try:
        user_id = request.args.get("user_id")
        if not user_id:
            return {"ok": False, "message": "user_id 필요"}, 400

        session_dir = Path(BASE_DIR) / "data" / "session_logs"
        session_files = list(session_dir.glob("*_analysis.json"))

        study_sessions = []
        distract_stats = {
            "game": 0, "sns": 0, "webtoon": 0,
            "youtube-ent": 0, "youtube-music": 0
        }

        # 주별 기록
        weekly_focus = {}  # {"2025-W48": [50, 60, 70]}

        for path in session_files:
            try:
                with path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
            except:
                continue

            if str(data.get("user_id")) != str(user_id):
                continue

            if data.get("selected_task") != "study":
                continue

            focus = data.get("focus_percent")
            if focus is None:
                continue

            session_id = data.get("session_id")
            raw_path = session_dir / f"{session_id}.json"

            if not raw_path.exists():
                continue

            try:
                with raw_path.open("r", encoding="utf-8") as f:
                    raw_json = json.load(f)
                end_ts = raw_json.get("session_end")
            except:
                continue

            if not end_ts:
                continue

            # ===== Study 세션 저장 =====
            study_sessions.append({
                "session_id": session_id,
                "focus_percent": focus,
                "final_label": data.get("final_label"),
                "activity": data.get("activity_distribution", {}).get("percent", {}),
                "session_end": end_ts
            })

            # ===== 방해 활동 계산(Other 제외 2등 라벨) =====
            dist = data.get("activity_distribution", {}).get("percent", {})
            dist_sorted = sorted(
                [(k, v) for k, v in dist.items() if k != "other" and k != "study"],
                key=lambda x: x[1],
                reverse=True
            )
            if dist_sorted:
                top_distract = dist_sorted[0][0]
                if top_distract in distract_stats:
                    distract_stats[top_distract] += 1

            # ===== 주별 기록 =====
            week_key = datetime.fromisoformat(end_ts).strftime("%Y-W%U")

            weekly_focus.setdefault(week_key, []).append(focus)

        # ======================================================================
        # 결과 요약
        # ======================================================================
        if not study_sessions:
            return {
                "ok": True,
                "summary": {
                    "total_sessions": 0,
                    "avg_focus_percent": 0,
                    "top_distract_label": None,
                    "weekly_focus": []
                }
            }

        total_sessions = len(study_sessions)
        avg_focus = sum(s["focus_percent"] for s in study_sessions) / total_sessions

        # 방해 활동 1위
        top_distract = max(distract_stats, key=lambda k: distract_stats[k])
        if distract_stats[top_distract] == 0:
            top_distract = None

        # 주별 변화 리스트 변환
        weekly_list = []
        for wk, values in weekly_focus.items():
            weekly_list.append({
                "week": wk,
                "focus_percent": sum(values) / len(values)
            })
        weekly_list.sort(key=lambda x: x["week"])

        return {
            "ok": True,
            "summary": {
                "total_sessions": total_sessions,
                "avg_focus_percent": avg_focus,
                "top_distract_label": top_distract,
                "weekly_focus": weekly_list
            }
        }

    except Exception as e:
        print("[API] /api/study/summary 오류:", e)
        return {"ok": False, "message": "study 요약 실패"}, 500
    
    
    
    

# ==============================
# 메인 실행
# ==============================

if __name__ == "__main__":
    url = "http://localhost:8000"
    webbrowser.open(url)
    app.run(host="0.0.0.0", port=8000, debug=False)


