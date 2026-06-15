import os
import requests
from dotenv import load_dotenv

from .schemas import FlightInfo

load_dotenv()

SERVICE_KEY = os.getenv("ICN_API_SERVICE_KEY")

BASE_URL = "https://apis.data.go.kr/B551177/StatusOfPassengerFlightsDeOdp/getPassengerDeparturesDeOdp"


def convert_terminal(terminal_id: str) -> str:
    terminal_map = {
        "P01": "제1여객터미널",
        "P02": "탑승동",
        "P03": "제2여객터미널",
        "C01": "화물터미널 남측",
        "C02": "화물터미널 북측",
        "C03": "제2화물터미널",
    }
    return terminal_map.get(terminal_id, "확인 필요")


def format_datetime(value: str | None) -> str:
    if not value:
        return "확인 필요"

    value = str(value)

    if len(value) != 12:
        return value

    year = value[0:4]
    month = value[4:6]
    day = value[6:8]
    hour = value[8:10]
    minute = value[10:12]

    return f"{year}-{month}-{day} {hour}:{minute}"


def parse_flight_item(item: dict) -> FlightInfo:
    return FlightInfo(
        flight_id=item.get("flightId", "확인 필요"),
        airline=item.get("airline", "확인 필요"),
        destination=item.get("airport", "확인 필요"),
        destination_code=item.get("airportCode", "확인 필요"),
        scheduled_time=format_datetime(item.get("scheduleDateTime")),
        estimated_time=format_datetime(item.get("estimatedDateTime")),
        terminal=convert_terminal(item.get("terminalid", "")),
        checkin_counter=item.get("chkinrange"),
        gate=item.get("gatenumber"),
        status=item.get("remark"),
        codeshare=item.get("codeshare"),
        master_flight_id=item.get("masterflightid"),
        type_of_flight=item.get("typeOfFlight"),
    )


def get_departure_flight_info(flight_id: str, searchday: str) -> FlightInfo | None:
    if not SERVICE_KEY:
        print("ICN_API_SERVICE_KEY가 설정되지 않았습니다. .env 파일을 확인해주세요.")
        return None

    params = {
        "serviceKey": SERVICE_KEY,
        "type": "json",
        "searchday": searchday.strip(),
        "from_time": "0000",
        "to_time": "2400",
        "flight_id": flight_id.strip().upper().replace(" ", ""),
        "lang": "K",
        "numOfRows": 10,
        "pageNo": 1,
    }

    response = requests.get(BASE_URL, params=params, timeout=10)

    try:
        response.raise_for_status()
    except requests.HTTPError:
        print("항공편 API 요청 실패")
        print("상태 코드:", response.status_code)
        print("응답 내용:", response.text[:300])
        return None

    data = response.json()

    header = data.get("response", {}).get("header", {})
    body = data.get("response", {}).get("body", {})

    if header.get("resultCode") != "00":
        print("API 오류:", header)
        return None

    items = body.get("items", [])

    if isinstance(items, dict):
        items = items.get("item", [])

    if isinstance(items, dict):
        items = [items]

    if not items:
        return None

    normalized_input = flight_id.strip().upper().replace(" ", "")

    for item in items:
        api_flight_id = str(item.get("flightId", "")).upper().replace(" ", "")
        if api_flight_id == normalized_input:
            return parse_flight_item(item)

    return parse_flight_item(items[0])
