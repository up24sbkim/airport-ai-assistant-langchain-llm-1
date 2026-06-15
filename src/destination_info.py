import os
import requests
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

from .schemas import FlightInfo

from .timezone_info import build_time_difference_summary

load_dotenv()

SERVICE_KEY = os.getenv("ICN_API_SERVICE_KEY")


WEATHER_BASE_URL = (
    "https://apis.data.go.kr/B551177/"
    "StatusOfPassengerWorldWeatherInfo/"
    "getPassengerDeparturesWorldWeather"
)


@dataclass
class DestinationWeatherInfo:
    airline: Optional[str]
    flight_id: Optional[str]
    schedule_time: Optional[str]
    estimated_time: Optional[str]
    airport: Optional[str]
    airport_code: Optional[str]
    gate_number: Optional[str]
    remark: Optional[str]
    weekday: Optional[str]
    humidity: Optional[str]
    weather: Optional[str]
    weather_image: Optional[str]
    wind: Optional[str]
    temperature: Optional[str]
    sensed_temperature: Optional[str]
    terminal_id: Optional[str]


def _normalize_flight_id(value: str) -> str:
    return value.strip().upper().replace(" ", "")


def _get_items_from_response(data: dict) -> list[dict]:
    body = data.get("response", {}).get("body", {})
    items = body.get("items", [])

    if isinstance(items, dict):
        items = items.get("item", [])

    if isinstance(items, dict):
        items = [items]

    if not items:
        return []

    return items


def parse_weather_item(item: dict) -> DestinationWeatherInfo:
    return DestinationWeatherInfo(
        airline=item.get("airline"),
        flight_id=item.get("flightId"),
        schedule_time=format_datetime(item.get("scheduleDateTime")),
        estimated_time=format_datetime(item.get("estimatedDateTime")),
        airport=item.get("airport"),
        airport_code=item.get("airportCode"),
        gate_number=item.get("gatenumber"),
        remark=item.get("remark"),
        weekday=item.get("yoil"),
        humidity=item.get("himidity"),
        weather=item.get("weather"),
        weather_image=item.get("wimage"),
        wind=item.get("wind"),
        temperature=item.get("temp"),
        sensed_temperature=item.get("senstemp"),
        terminal_id=item.get("terminalid"),
    )

def format_datetime(value: str | None) -> str:
    if not value:
        return "확인 필요"

    value = str(value)

    if len(value) != 12:
        return value

    return f"{value[0:4]}-{value[4:6]}-{value[6:8]} {value[8:10]}:{value[10:12]}"


def get_destination_weather_from_icn(
    info: FlightInfo,
    from_time: str = "0000",
    to_time: str = "2400",
) -> DestinationWeatherInfo | None:
    """
    인천공항 기상 정보 API를 사용해
    인천공항에서 출발하는 항공편의 도착도시 날씨를 조회합니다.

    주의:
    이 API는 조회 당일 데이터 제공이 기본입니다.
    """

    if not SERVICE_KEY:
        print("ICN_API_SERVICE_KEY가 설정되지 않았습니다. .env 파일을 확인해주세요.")
        return None

    params = {
        "serviceKey": SERVICE_KEY,
        "type": "json",
        "from_time": from_time,
        "to_time": to_time,
        "flight_id": _normalize_flight_id(info.flight_id),
        "airport": info.destination_code,
        "lang": "K",
        "numOfRows": 10,
        "pageNo": 1,
    }

    response = requests.get(WEATHER_BASE_URL, params=params, timeout=10)
    response.raise_for_status()

    data = response.json()

    header = data.get("response", {}).get("header", {})
    if header.get("resultCode") != "00":
        print("기상 API 오류:", header)
        return None

    items = _get_items_from_response(data)

    if not items:
        return None

    input_flight_id = _normalize_flight_id(info.flight_id)
    input_airport_code = (info.destination_code or "").upper()

    for item in items:
        api_flight_id = _normalize_flight_id(str(item.get("flightId", "")))
        api_airport_code = str(item.get("airportCode", "")).upper()

        if api_flight_id == input_flight_id and api_airport_code == input_airport_code:
            return parse_weather_item(item)

    return parse_weather_item(items[0])


def build_destination_weather_summary(weather: DestinationWeatherInfo | None) -> str:
    if weather is None:
        return """
도착지 정보를 찾을 수 없습니다.
기상 API는 조회 당일 운항편 기준으로 제공되므로, 미래 날짜 항공편은 결과가 없을 수 있습니다.
""".strip()

    time_difference = build_time_difference_summary(weather.airport_code)

    return f"""
도착지 : {weather.airport or "확인 필요"} ({weather.airport_code or "확인 필요"})

날씨 정보 : {weather.temperature or "확인 필요"}℃

시차 : {time_difference}
""".strip()
