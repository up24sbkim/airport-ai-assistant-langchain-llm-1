from datetime import datetime, timedelta
from .schemas import FlightInput, AirportPlan


def _parse_datetime(date_text: str, time_text: str) -> datetime:
    # date_text 예: 2026-06-12, time_text 예: 09:30
    return datetime.strptime(f"{date_text} {time_text}", "%Y-%m-%d %H:%M")


def build_airport_plan(user_input: FlightInput) -> AirportPlan:
    departure_dt = _parse_datetime(user_input.departure_date, user_input.departure_time)

    # 국제선 기본 권장: 3시간 전 공항 도착
    airport_arrival_dt = departure_dt - timedelta(hours=3)
    leave_home_dt = airport_arrival_dt - timedelta(minutes=user_input.travel_minutes)
    checkin_dt = departure_dt - timedelta(hours=2, minutes=30)
    boarding_dt = departure_dt - timedelta(minutes=40)

    checklist = [
        "여권 확인",
        "항공권 또는 모바일 탑승권 확인",
        "지갑/카드/현금 확인",
        "충전기와 보조배터리 준비",
        "액체류는 100ml 이하 용기와 지퍼백 기준 확인",
    ]
    if user_input.has_checked_baggage:
        checklist.append("위탁 수하물 무게와 금지 물품 확인")

    warnings = [
        "보조배터리는 위탁 수하물이 아니라 기내 반입 기준을 확인하세요.",
        "성수기나 가족 여행이면 권장 시간보다 더 일찍 출발하는 것이 안전합니다.",
        "터미널은 항공권 또는 항공사 안내에서 최종 확인하세요.",
    ]

    next_questions = [
        "보조배터리 위탁수하물 가능해?",
        "인천공항 고객센터 전화번호 알려줘",
        "액체류 기내 반입 기준 알려줘",
        "제1터미널 식당 정보 알려줘",
    ]

    summary = (
        f"{user_input.flight_no}편으로 {user_input.destination}에 가는 일정입니다. "
        f"출발 시간이 {user_input.departure_time}이므로, 최소 {airport_arrival_dt.strftime('%H:%M')}까지 "
        f"{user_input.airport}에 도착하는 것을 권장합니다."
    )

    return AirportPlan(
        leave_home_time=leave_home_dt.strftime("%H:%M"),
        airport_arrival_time=airport_arrival_dt.strftime("%H:%M"),
        checkin_time=checkin_dt.strftime("%H:%M"),
        boarding_time=boarding_dt.strftime("%H:%M"),
        summary=summary,
        checklist=checklist,
        warnings=warnings,
        next_questions=next_questions,
    )
