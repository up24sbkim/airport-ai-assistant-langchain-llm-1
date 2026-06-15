from datetime import datetime, timedelta

from .schemas import FlightInfo
from .timezone_info import (
    build_time_difference_summary,
    convert_kst_to_destination_time,
)


def calculate_recommended_arrival(scheduled_time: str, type_of_flight: str | None) -> str:
    try:
        departure_dt = datetime.strptime(scheduled_time, "%Y-%m-%d %H:%M")

        if type_of_flight == "D":
            recommended_dt = departure_dt - timedelta(hours=2)
            return f"국내선 기준 출발 2시간 전인 {recommended_dt.strftime('%H:%M')}까지 도착을 권장합니다."

        recommended_dt = departure_dt - timedelta(hours=3)
        return f"국제선 기준 출발 3시간 전인 {recommended_dt.strftime('%H:%M')}까지 도착을 권장합니다."

    except Exception:
        return "출발 시간이 확인되지 않아 권장 도착 시간을 계산할 수 없습니다."


def build_route_steps(info: FlightInfo) -> list[str]:
    if info.terminal == "탑승동":
        return [
            "제1여객터미널 도착",
            f"체크인 카운터 확인: {info.checkin_counter or '확인 필요'}",
            "수하물 위탁",
            "보안검색",
            "출국심사",
            "셔틀트레인으로 탑승동 이동",
            "면세구역 이동",
            f"탑승구 이동: {info.gate or '확인 필요'}",
        ]

    return [
        f"{info.terminal} 도착",
        f"체크인 카운터 확인: {info.checkin_counter or '확인 필요'}",
        "수하물 위탁",
        "보안검색",
        "출국심사",
        "면세구역 이동",
        f"탑승구 이동: {info.gate or '확인 필요'}",
    ]


def extract_counter_zones(checkin_counter: str | None) -> str:
    if not checkin_counter:
        return "확인 필요"

    try:
        # 예: A01-C33 → A,B,C
        start_part, end_part = checkin_counter.split("-")
        start_zone = start_part[0]
        end_zone = end_part[0]

        zones = []
        for code in range(ord(start_zone), ord(end_zone) + 1):
            zones.append(chr(code))

        return ",".join(zones)

    except Exception:
        # 예: A01처럼 범위가 아닌 경우
        return checkin_counter[0] if checkin_counter else "확인 필요"


def build_shortest_route(info: FlightInfo) -> str:
    counter_zones = extract_counter_zones(info.checkin_counter)

    if info.terminal == "제2여객터미널":
        parking_area = "제2터미널 단기주차장"
        connector = f"{counter_zones} 구역 연결통로"
    else:
        parking_area = "A/D 주차장"
        connector = f"{counter_zones} 연결통로"

    gate_text = info.gate if info.gate else "탑승구"

    return (
        f"{parking_area} → "
        f"{connector} → "
        f"{info.checkin_counter or '체크인 카운터'} 체크인 카운터 → "
        f"{gate_text}"
    )


def build_flight_summary(info: FlightInfo) -> str:
    arrival_tip = calculate_recommended_arrival(info.scheduled_time, info.type_of_flight)
    departure_time_display = format_departure_time_display(
        info.scheduled_time,
        info.estimated_time,
    )


    display_terminal = (
        "제1여객터미널 출국 후 탑승동 이동"
        if info.terminal == "탑승동"
        else info.terminal
    )

    shortest_route = build_shortest_route(info)

    return f"""
항공편: {info.flight_id}
항공사: {info.airline}
터미널: {display_terminal}
목적지: {info.destination}({info.destination_code})
출발 예정 시간: {departure_time_display}
체크인 카운터: {info.checkin_counter or "확인 필요"}
탑승구: {info.gate or "확인 필요"}
운항 상태: {info.status or "확인 필요"}

최단이동경로:
{shortest_route}

출국심사 후 예상 이동시간:
약 15분
""".strip()

def format_departure_time_display(scheduled_time: str, estimated_time: str) -> str:
    """
    출발 예정 시간과 변경 출발 시간이 다르면
    기존 시간에는 취소선을 적용하고 변경 시간을 함께 표시합니다.
    """

    if not scheduled_time or scheduled_time == "확인 필요":
        return "확인 필요"

    if not estimated_time or estimated_time == "확인 필요":
        return scheduled_time

    if scheduled_time == estimated_time:
        return scheduled_time

    try:
        scheduled_date = scheduled_time[:10]
        scheduled_clock = scheduled_time[11:16]
        estimated_date = estimated_time[:10]
        estimated_clock = estimated_time[11:16]

        if scheduled_date == estimated_date:
            return f"{scheduled_date} ~~{scheduled_clock}~~ {estimated_clock}"

        return f"~~{scheduled_time}~~ {estimated_time}"

    except Exception:
        return f"~~{scheduled_time}~~ {estimated_time}"