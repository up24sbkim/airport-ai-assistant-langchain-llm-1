from pydantic import BaseModel, Field
from dataclasses import dataclass
from typing import List, Optional


class FlightInput(BaseModel):
    flight_no: str = Field(..., description="항공편 번호")
    departure_date: str = Field(..., description="출발 날짜")
    departure_time: str = Field(..., description="출발 시간 HH:MM")
    airport: str = Field(default="인천공항", description="출발 공항")
    destination: str = Field(..., description="목적지")
    start_place: str = Field(..., description="출발 위치")
    travel_minutes: int = Field(default=90, description="집에서 공항까지 예상 이동 시간")
    has_checked_baggage: bool = Field(default=True, description="위탁 수하물 여부")


class AirportPlan(BaseModel):
    leave_home_time: str
    airport_arrival_time: str
    checkin_time: str
    boarding_time: str
    summary: str
    checklist: List[str]
    warnings: List[str]
    next_questions: List[str]


class RetrievedSource(BaseModel):
    title: str
    content: str
    score: Optional[float] = None


class ChatAnswer(BaseModel):
    answer: str
    sources: List[RetrievedSource]


@dataclass
class FlightInfo:
    flight_id: str
    airline: str
    destination: str
    destination_code: str
    scheduled_time: str
    estimated_time: str
    terminal: str
    checkin_counter: Optional[str]
    gate: Optional[str]
    status: Optional[str]
    codeshare: Optional[str]
    master_flight_id: Optional[str]
    type_of_flight: Optional[str]
