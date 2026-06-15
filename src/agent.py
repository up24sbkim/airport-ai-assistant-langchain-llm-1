import json
from dataclasses import asdict
from datetime import datetime
from threading import Lock
from typing import Dict, List, Optional

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool

from .destination_info import (
    build_destination_weather_summary,
    get_destination_weather_from_icn,
)
from .flight_api import get_departure_flight_info
from .flight_summary import build_flight_summary
from .planner import build_airport_plan
from .rag import AirportRAG
from .schemas import FlightInput
from .travel_time_api import get_driving_and_transit_minutes
from .web_search_fallback import (
    extract_facility_search_term,
    is_dynamic_facility_question,
)


AGENT_SYSTEM_PROMPT = """
너는 인천공항 출국 준비를 돕는 Tool-calling Agent다.
사용자의 질문을 해결하기 위해 등록된 도구 중 필요한 도구를 스스로 선택하고,
도구 결과를 확인한 뒤 추가 호출 또는 최종 답변을 결정한다.

[도구 선택 원칙]
- 수하물, 전화번호, 터미널 규정 등 일반 공항 정보는
  search_airport_documents를 먼저 사용한다.
- search_airport_documents 결과가 found=true이면 그 근거만으로 답하고,
  search_official_airport_web을 추가 호출하지 않는다.
- 로컬 문서 결과에 found=false가 나오거나 최신 매장/운영 정보가 필요하면
  search_official_airport_web을 사용한다.
- 매장·카페·식당의 위치, 영업시간, 연락처 질문은 로컬 문서 결과와 관계없이
  search_official_airport_web을 호출하고 모든 터미널 결과를 종합한다.
- 공식 웹 검색 도구가 answer를 반환하면 그 답변의 터미널 구분과 세부 정보를
  그대로 유지하고 다른 터미널의 정보를 합치거나 새 위치를 추론하지 않는다.
- 항공편 번호와 날짜가 있는 운항 질문은 lookup_departure_flight를 사용한다.
- 출발지에서 공항까지 소요시간 질문은 lookup_travel_time을 사용한다.
- 도착지 날씨와 시차 질문은 lookup_destination_info를 사용한다.
- 몇 시에 집에서 출발해야 하는지 묻는 질문은 필요한 정보를 확보한 후
  calculate_airport_plan을 사용한다.
- 도구에 필요한 항공편 날짜, 출발 위치 등이 없으면 추측하지 말고
  사용자에게 필요한 정보를 짧게 질문한다.
- 현재 항공편 문맥에 이미 있는 정보는 다시 질문하지 말고 활용한다.
- 사실이나 숫자를 임의로 만들지 않는다.
- 최소 한 개 이상의 도구 결과를 근거로 답변한다.
- 같은 질문과 같은 인자로 동일한 도구를 반복 호출하지 않는다.

[답변 원칙]
- 첫 문장에 핵심 답변을 말한다.
- 필요한 경우 2~4개의 짧은 항목으로 정리한다.
- 한국어로 친절하고 간결하게 답한다.
- 도구 이름이나 내부 구현 세부사항은 사용자에게 설명하지 않는다.

현재 조회된 항공편 문맥:
{flight_context}
""".strip()


def _json_result(**payload) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def _normalize_searchday(value: str) -> str:
    normalized = value.strip().replace("-", "").replace(".", "")
    if len(normalized) != 8 or not normalized.isdigit():
        raise ValueError("출발 날짜는 YYYY-MM-DD 형식으로 입력해주세요.")
    return normalized


def _normalize_departure_date(value: str) -> str:
    return datetime.strptime(
        _normalize_searchday(value),
        "%Y%m%d",
    ).strftime("%Y-%m-%d")


def _history_to_messages(history: Optional[List[Dict]]) -> List:
    messages = []
    for message in history or []:
        content = str(message.get("content", "")).strip()
        if not content:
            continue
        if message.get("role") == "user":
            messages.append(HumanMessage(content=content))
        elif message.get("role") == "assistant":
            messages.append(AIMessage(content=content))
    return messages[-8:]


def _looks_like_facility_existence_question(question: str) -> bool:
    normalized = question.lower().replace(" ", "")
    existence_markers = (
        "있어",
        "있나요",
        "있습니까",
        "입점",
        "매장",
    )
    return bool(extract_facility_search_term(question)) and any(
        marker in normalized for marker in existence_markers
    )


class AirportToolAgent:
    """LangChain tool-calling agent for airport questions."""

    def __init__(self, rag: Optional[AirportRAG] = None):
        self.rag = rag or AirportRAG()
        self.llm = self.rag.llm
        self._local_evidence_found = False
        self._execution_lock = Lock()
        self.tools = self._build_tools()
        self.executor = self._build_executor()

    @property
    def enabled(self) -> bool:
        return self.executor is not None

    def _build_tools(self):
        rag = self.rag

        @tool
        def search_airport_documents(question: str) -> str:
            """Search bundled Incheon Airport documents for rules, baggage, facilities, terminals, contacts, and FAQs. Use this before official web search for general airport questions."""
            dynamic_facility = is_dynamic_facility_question(question)
            if dynamic_facility:
                self._local_evidence_found = False
                return _json_result(
                    found=False,
                    answer=(
                        "매장과 시설 정보는 변경될 수 있어 "
                        "공식 웹 검색이 필요합니다."
                    ),
                    sources=[],
                    web_search_recommended=True,
                    instruction=(
                        "search_official_airport_web을 호출하세요."
                    ),
                )

            result = rag.answer_from_local(question)
            found = not result.get("needs_web_search", False)
            self._local_evidence_found = found and not dynamic_facility
            return _json_result(
                found=found,
                answer=result["answer"],
                sources=result["sources"],
                web_search_recommended=dynamic_facility or not found,
                instruction=(
                    "web_search_recommended가 true이면 "
                    "search_official_airport_web을 호출하세요. "
                    "그 외에는 이 답변으로 종료하세요."
                ),
            )

        @tool
        def search_official_airport_web(question: str) -> str:
            """Search only official airport.kr web results for current stores, operating hours, locations, and information missing from bundled documents."""
            if self._local_evidence_found:
                return _json_result(
                    found=False,
                    blocked=True,
                    reason=(
                        "로컬 공항 문서에서 충분한 근거를 찾았으므로 "
                        "웹 검색을 생략합니다."
                    ),
                    sources=[],
                )
            results = rag.web_search.search_results(question)
            summarized = rag.web_search.answer_from_results(
                question,
                results,
                rag.llm,
            )
            return _json_result(
                found=bool(results),
                answer=summarized["answer"],
                results=results,
                searched_terminals=[
                    result.get("terminal")
                    for result in results
                    if result.get("terminal_id")
                ],
                instruction=(
                    "검색 결과 전체를 종합해 확인된 모든 지점을 "
                    "터미널별로 나열하세요. 일부 결과만 보고 다른 "
                    "터미널에 지점이 없다고 단정하지 마세요."
                ),
                sources=summarized["sources"],
            )

        @tool
        def lookup_departure_flight(
            flight_number: str,
            departure_date: str,
        ) -> str:
            """Look up an Incheon Airport departure flight. departure_date must be YYYY-MM-DD. Returns schedule, delay, terminal, counter, gate, status, and destination."""
            try:
                searchday = _normalize_searchday(departure_date)
                info = get_departure_flight_info(
                    flight_number,
                    searchday,
                )
            except Exception as exc:
                return _json_result(found=False, error=str(exc))

            if info is None:
                return _json_result(
                    found=False,
                    error="항공편 정보를 찾을 수 없습니다.",
                )

            return _json_result(
                found=True,
                flight=asdict(info),
                summary=build_flight_summary(info),
                sources=[
                    {
                        "title": "인천공항 출발 항공편 API",
                        "source": "apis.data.go.kr",
                        "content": build_flight_summary(info)[:300],
                    }
                ],
            )

        @tool
        def lookup_travel_time(
            origin: str,
            terminal: str = "제1여객터미널",
        ) -> str:
            """Look up driving and public-transit minutes from a Korean origin address to Incheon Airport Terminal 1 or Terminal 2."""
            try:
                result = get_driving_and_transit_minutes(
                    origin=origin,
                    terminal=terminal,
                )
            except Exception as exc:
                return _json_result(found=False, error=str(exc))

            return _json_result(
                found=bool(
                    result.get("driving") or result.get("transit")
                ),
                origin=origin,
                terminal=terminal,
                driving_minutes=result.get("driving"),
                transit_minutes=result.get("transit"),
                sources=[
                    {
                        "title": "Google Directions 이동시간",
                        "source": "maps.googleapis.com",
                        "content": (
                            f"자동차 {result.get('driving')}분, "
                            f"대중교통 {result.get('transit')}분"
                        ),
                    }
                ],
            )

        @tool
        def lookup_destination_info(
            flight_number: str,
            departure_date: str,
        ) -> str:
            """Look up destination weather and time difference for an Incheon departure flight. departure_date must be YYYY-MM-DD."""
            try:
                info = get_departure_flight_info(
                    flight_number,
                    _normalize_searchday(departure_date),
                )
                if info is None:
                    return _json_result(
                        found=False,
                        error="항공편 정보를 찾을 수 없습니다.",
                    )
                weather = get_destination_weather_from_icn(info)
                summary = build_destination_weather_summary(weather)
            except Exception as exc:
                return _json_result(found=False, error=str(exc))

            return _json_result(
                found=weather is not None,
                destination=info.destination,
                destination_code=info.destination_code,
                summary=summary,
                sources=[
                    {
                        "title": "인천공항 도착지 날씨 API",
                        "source": "apis.data.go.kr",
                        "content": summary[:300],
                    }
                ],
            )

        @tool
        def calculate_airport_plan(
            flight_number: str,
            departure_date: str,
            departure_time: str,
            destination: str,
            start_place: str,
            travel_minutes: int,
            has_checked_baggage: bool = True,
        ) -> str:
            """Calculate recommended airport arrival, home departure, check-in, boarding times, checklist, and warnings. departure_time must be HH:MM."""
            try:
                flight_input = FlightInput(
                    flight_no=flight_number,
                    departure_date=_normalize_departure_date(
                        departure_date
                    ),
                    departure_time=departure_time,
                    airport="인천공항",
                    destination=destination,
                    start_place=start_place,
                    travel_minutes=travel_minutes,
                    has_checked_baggage=has_checked_baggage,
                )
                plan = build_airport_plan(flight_input)
            except Exception as exc:
                return _json_result(found=False, error=str(exc))

            return _json_result(
                found=True,
                plan=plan.model_dump(),
            )

        return [
            search_airport_documents,
            search_official_airport_web,
            lookup_departure_flight,
            lookup_travel_time,
            lookup_destination_info,
            calculate_airport_plan,
        ]

    def _build_executor(self) -> Optional[AgentExecutor]:
        if self.llm is None:
            return None

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", AGENT_SYSTEM_PROMPT),
                MessagesPlaceholder(
                    variable_name="chat_history",
                    optional=True,
                ),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )
        agent = create_tool_calling_agent(
            self.llm,
            self.tools,
            prompt,
        )
        return AgentExecutor(
            agent=agent,
            tools=self.tools,
            return_intermediate_steps=True,
            handle_parsing_errors=True,
            max_iterations=6,
            verbose=False,
        )

    def ask(
        self,
        question: str,
        flight_context: str = "",
        chat_history: Optional[List[Dict]] = None,
    ) -> Dict:
        if self.executor is None:
            fallback = self.rag.ask(question)
            return {
                **fallback,
                "used_tools": ["legacy_rag_fallback"],
                "agent_mode": False,
            }

        try:
            with self._execution_lock:
                self._local_evidence_found = False
                result = self.executor.invoke(
                    {
                        "input": question,
                        "flight_context": (
                            flight_context or "현재 조회된 항공편 없음"
                        ),
                        "chat_history": _history_to_messages(
                            chat_history
                        ),
                    }
                )
        except Exception:
            fallback = self.rag.ask(question)
            return {
                **fallback,
                "used_tools": ["legacy_rag_fallback"],
                "agent_mode": False,
            }

        if (
            not result.get("intermediate_steps")
            and _looks_like_facility_existence_question(question)
        ):
            web_tool = next(
                tool
                for tool in self.tools
                if tool.name == "search_official_airport_web"
            )
            observation = web_tool.invoke({"question": question})
            try:
                payload = json.loads(observation)
            except (TypeError, json.JSONDecodeError):
                payload = {}
            if payload.get("found"):
                return {
                    "answer": self.rag._postprocess_answer(
                        payload.get("answer", result.get("output", ""))
                    ),
                    "sources": payload.get("sources", []),
                    "used_tools": ["search_official_airport_web"],
                    "agent_mode": True,
                }

        used_tools = []
        sources = []
        seen_sources = set()
        authoritative_web_answer = ""

        for action, observation in result.get(
            "intermediate_steps",
            [],
        ):
            try:
                payload = json.loads(observation)
            except (TypeError, json.JSONDecodeError):
                used_tools.append(action.tool)
                continue

            if payload.get("blocked"):
                continue

            used_tools.append(action.tool)
            if (
                action.tool == "search_official_airport_web"
                and payload.get("found")
                and payload.get("answer")
            ):
                authoritative_web_answer = payload["answer"]
            for source in payload.get("sources", []):
                source_key = (
                    source.get("title"),
                    source.get("source"),
                )
                if source_key in seen_sources:
                    continue
                seen_sources.add(source_key)
                sources.append(source)

        raw_answer = result.get("output", "")
        if (
            authoritative_web_answer
            and is_dynamic_facility_question(question)
        ):
            raw_answer = authoritative_web_answer
        answer = self.rag._postprocess_answer(raw_answer)
        return {
            "answer": answer,
            "sources": sources,
            "used_tools": list(dict.fromkeys(used_tools)),
            "agent_mode": True,
        }
