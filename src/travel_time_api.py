import os
import requests
from dotenv import load_dotenv

load_dotenv()

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

ICN_TERMINAL_1 = "Incheon International Airport Terminal 1, Incheon, South Korea"
ICN_TERMINAL_2 = "Incheon International Airport Terminal 2, Incheon, South Korea"


def _get_api_key() -> str | None:
    return GOOGLE_MAPS_API_KEY


def get_travel_minutes(
    origin: str,
    destination: str,
    mode: str,
) -> int | None:
    """
    mode 예시:
    - driving
    - transit
    """
    api_key = _get_api_key()

    if not api_key:
        return None

    url = "https://maps.googleapis.com/maps/api/directions/json"

    params = {
        "origin": origin,
        "destination": destination,
        "mode": mode,
        "language": "ko",
        "region": "kr",
        "key": api_key,
    }

    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()

    data = response.json()

    if data.get("status") != "OK":
        return None

    routes = data.get("routes", [])
    if not routes:
        return None

    legs = routes[0].get("legs", [])
    if not legs:
        return None

    duration_seconds = legs[0].get("duration", {}).get("value")

    if duration_seconds is None:
        return None

    return round(duration_seconds / 60)


def get_airport_destination_by_terminal(terminal: str | None) -> str:
    if terminal == "제2여객터미널":
        return ICN_TERMINAL_2

    return ICN_TERMINAL_1


def get_driving_and_transit_minutes(
    origin: str,
    terminal: str | None = None,
) -> dict:
    destination = get_airport_destination_by_terminal(terminal)

    driving_minutes = get_travel_minutes(
        origin=origin,
        destination=destination,
        mode="driving",
    )

    transit_minutes = get_travel_minutes(
        origin=origin,
        destination=destination,
        mode="transit",
    )

    return {
        "driving": driving_minutes,
        "transit": transit_minutes,
    }