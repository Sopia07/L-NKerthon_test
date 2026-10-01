import random
import math
from flask import Flask, render_template, request, jsonify

app = Flask(__name__, template_folder='.')

# 해커톤 데모용 가상 과목 데이터베이스 (연세대 마일리지 방식 참고)
COURSES = {
    "CS101": {
        "id": "CS101",
        "name": "컴퓨터프로그래밍 (컴공 필수)",
        "professor": "김연세 교수",
        "capacity": 40,
        "max_mileage": 36,
        "is_major_required": True,
        "bids_count": 68
    },
    "BA201": {
        "id": "BA201",
        "name": "경영학개론 (전공선택)",
        "professor": "이혁신 교수",
        "capacity": 60,
        "max_mileage": 36,
        "is_major_required": False,
        "bids_count": 85
    },
    "AI301": {
        "id": "AI301",
        "name": "인공지능과 딥러닝 (핵심교양)",
        "professor": "박스마트 교수",
        "capacity": 30,
        "max_mileage": 36,
        "is_major_required": False,
        "bids_count": 92
    },
    "EC102": {
        "id": "EC102",
        "name": "경제학원론 (교양필수)",
        "professor": "최효율 교수",
        "capacity": 80,
        "max_mileage": 36,
        "is_major_required": False,
        "bids_count": 75
    }
}

def generate_simulated_bids(course_id):
    """
    각 과목별로 다른 학생들의 마일리지 베팅 현황 및 동점자 처리용 학생 프로필을 생성합니다.
    연세대 시스템처럼 전공여부, 이수학점 비율, 직전학기 평점 등이 복합 반영됩니다.
    """
    random.seed(hash(course_id) % 10000)
    course = COURSES[course_id]
    bids = []
    
    # 과목 인기도에 따른 마일리지 분포 가중치 설정
    is_popular = course["bids_count"] > course["capacity"] * 1.5
    
    for i in range(course["bids_count"]):
        # 마일리지 산정 (인기 과목일수록 상위 마일리지 몰림)
        if is_popular:
            mileage = int(random.triangular(1, 36, 28))
        else:
            mileage = int(random.triangular(1, 36, 18))
            
        # 연세대 방식 동점자 처리 우대 조건 가상 생성
        is_major = random.choices([True, False], weights=[0.6, 0.4])[0]
        completed_credit_ratio = round(random.uniform(0.2, 0.95), 2)  # 총 졸업이수학점 대비 비율
        gpa = round(random.uniform(2.5, 4.3), 2)
        is_last_semester = random.choices([True, False], weights=[0.15, 0.85])[0]
        
        # 종합 동점자 우선순위 점수 (가상 알고리즘)
        tie_breaker_score = (
            (50.0 if is_major else 0.0) +
            (completed_credit_ratio * 30.0) +
            ((gpa / 4.3) * 10.0) +
            (10.0 if is_last_semester else 0.0)
        )
        
        bids.append({
            "student_id": f"2024_{i+1000}",
            "mileage": mileage,
            "is_major": is_major,
            "credit_ratio": completed_credit_ratio,
            "gpa": gpa,
            "is_last_semester": is_last_semester,
            "tie_breaker_score": round(tie_breaker_score, 2)
        })
        
    # 마일리지 내림차순, 같으면 동점자 우선순위 점수 내림차순 정렬
    bids.sort(key=lambda x: (x["mileage"], x["tie_breaker_score"]), reverse=True)
    return bids

def calculate_order_book(course_id, user_mileage=None, user_profile=None):
    """
    주식 호가창(Order Book)처럼 마일리지 구간별 신청자 수와 수강정원 컷오프를 산출합니다.
    """
    bids = generate_simulated_bids(course_id)
    course = COURSES[course_id]
    
    # 사용자 데이터가 존재하는 경우 가상 입찰 목록에 통합
    if user_mileage is not None and user_profile is not None:
        user_tie_score = (
            (50.0 if user_profile.get("is_major") else 0.0) +
            (float(user_profile.get("credit_ratio", 0.5)) * 30.0) +
            ((float(user_profile.get("gpa", 3.5)) / 4.3) * 10.0) +
            (10.0 if user_profile.get("is_last_semester") else 0.0)
        )
        bids.append({
            "student_id": "CURRENT_USER",
            "mileage": int(user_mileage),
            "is_major": user_profile.get("is_major", False),
            "credit_ratio": float(user_profile.get("credit_ratio", 0.5)),
            "gpa": float(user_profile.get("gpa", 3.5)),
            "is_last_semester": user_profile.get("is_last_semester", False),
            "tie_breaker_score": round(user_tie_score, 2)
        })
        bids.sort(key=lambda x: (x["mileage"], x["tie_breaker_score"]), reverse=True)

    capacity = course["capacity"]
    
    # 컷오프 정보 계산
    if len(bids) >= capacity:
        cutoff_bid = bids[capacity - 1]
        predicted_cutoff_mileage = cutoff_bid["mileage"]
        predicted_cutoff_tie_score = cutoff_bid["tie_breaker_score"]
    else:
        predicted_cutoff_mileage = 1
        predicted_cutoff_tie_score = 0.0

    # 마일리지 1~36점별 호가(Depth) 집계
    depth = {}
    for m in range(36, 0, -1):
        depth[m] = {"mileage": m, "count": 0, "accumulated": 0}
        
    accumulated = 0
    for b in bids:
        m = b["mileage"]
        if m in depth:
            depth[m]["count"] += 1

    for m in range(36, 0, -1):
        accumulated += depth[m]["count"]
        depth[m]["accumulated"] = accumulated

    # 주식 호가창 형태로 변환
    orderbook_list = []
    for m in range(36, 0, -1):
        is_cutoff_line = False
        # 수강정원 경계선이 유효한 위치에 표시되도록 지정
        if depth[m]["accumulated"] >= capacity and (m == 36 or depth[m+1]["accumulated"] < capacity):
            is_cutoff_line = True
            
        orderbook_list.append({
            "mileage": m,
            "count": depth[m]["count"],
            "accumulated": depth[m]["accumulated"],
            "is_cutoff_line": is_cutoff_line,
            "ratio_to_capacity": round((depth[m]["accumulated"] / capacity) * 100, 1)
        })

    return bids, orderbook_list, predicted_cutoff_mileage, predicted_cutoff_tie_score

def compute_pass_probability(course_id, user_mileage, user_profile):
    """
    사용자의 입력 점수와 조건을 분석하여 실시간 신호등 UI (🟢안전 / 🟡적정 / 🔴위험) 확률값을 산출합니다.
    """
    bids, orderbook, cutoff_mileage, cutoff_tie_score = calculate_order_book(course_id, user_mileage, user_profile)
    course = COURSES[course_id]
    
    # 사용자의 현재 석차 찾기
    user_rank = 1
    for idx, b in enumerate(bids):
        if b["student_id"] == "CURRENT_USER":
            user_rank = idx + 1
            break
            
    capacity = course["capacity"]
    
    # 신호등 상태 및 확률 판정
    if user_rank <= math.floor(capacity * 0.8):
        status = "GREEN"  # 안전
        label = "합격 유력 (안전)"
        color = "#10B981" # Emerald Green
        probability = min(99, math.floor(95 - (user_rank / capacity) * 20))
        recommendation = "현재 매우 안정권입니다. 여유 마일리지 1~2점을 타 과목에 배분하는 전략을 고려하세요."
    elif user_rank <= capacity:
        status = "YELLOW" # 적정/경계
        label = "커트라인 경계 (주의)"
        color = "#F59E0B" # Amber Yellow
        probability = math.floor(75 - ((user_rank - capacity * 0.8) / (capacity * 0.2)) * 30)
        recommendation = "정원 내 위치하지만 동점자가 몰릴 경우 위험합니다. 전공 여부 및 동점자 가산점을 확인하세요."
    else:
        status = "RED"    # 위험
        label = "탈락 위험 (불안)"
        color = "#EF4444" # Rose Red
        diff = user_rank - capacity
        probability = max(5, math.floor(40 - diff * 4))
        recommendation = f"예상 정원(40명) 대비 현재 {user_rank}위입니다. 마일리지를 최소 {max(1, cutoff_mileage - user_mileage + 1)}점 이상 증액해야 합니다."

    return {
        "user_rank": user_rank,
        "capacity": capacity,
        "total_bids": len(bids),
        "cutoff_mileage": cutoff_mileage,
        "cutoff_tie_score": cutoff_tie_score,
        "status": status,
        "status_label": label,
        "status_color": color,
        "probability": probability,
        "recommendation": recommendation
    }

@app.route("/")
def index():
    """메인 HTML 화면 렌더링"""
    return render_template("index.html")

@app.route("/api/courses", methods=["GET"])
def get_courses():
    """전체 수강과목 목록 및 기본 현황 반환 API"""
    result = []
    for c_id, course in COURSES.items():
        _, _, cutoff_m, _ = calculate_order_book(c_id)
        result.append({
            **course,
            "predicted_cutoff": cutoff_m
        })
    return jsonify({"success": True, "courses": result})

@app.route("/api/simulate", methods=["POST"])
def simulate():
    """마일리지 조정 및 프로필 변경에 따른 실시간 확률/호가창 시뮬레이션 API"""
    data = request.json or {}
    course_id = data.get("course_id", "CS101")
    user_mileage = int(data.get("mileage", 18))
    user_profile = {
        "is_major": bool(data.get("is_major", True)),
        "credit_ratio": float(data.get("credit_ratio", 0.75)),
        "gpa": float(data.get("gpa", 3.8)),
        "is_last_semester": bool(data.get("is_last_semester", False))
    }

    _, orderbook, _, _ = calculate_order_book(course_id, user_mileage, user_profile)
    analysis = compute_pass_probability(course_id, user_mileage, user_profile)

    return jsonify({
        "success": True,
        "course_id": course_id,
        "user_mileage": user_mileage,
        "analysis": analysis,
        "orderbook": orderbook
    })

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 CourseX (해커톤 차별화 수강신청 모델) 백엔드 서버 시작")
    print("📍 연세대학교 마일리지 검증 모델 + 주식 호가창 예측 알고리즘 탑재")
    
    # pyngrok 설치 시 외부 공유 가능한 Public URL 자동 발행
    try:
        from pyngrok import ngrok
        public_url = ngrok.connect(5000).public_url
        print(f"🔗 외부 공유용 공용 주소: {public_url}")
    except Exception:
        print("💡 외부 사람에게 공유하려면 터미널에 [npx localtunnel --port 5000] 또는 ngrok을 실행하세요.")

    print("🌐 로컬 접속 주소: http://127.0.0.1:5000")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=False)