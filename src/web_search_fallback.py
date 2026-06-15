import base64
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, unquote, urlencode, urlparse

import requests
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from lxml import html


WEB_SEARCH_SENTINEL = "WEB_SEARCH_NEEDED"

_UNKNOWN_MARKERS = (
    WEB_SEARCH_SENTINEL,
    "제공된 문서에서 확인되지",
    "문서에서 확인되지",
    "관련 내용을 찾지 못",
    "정보를 찾지 못",
    "알 수 없",
    "모르겠습니다",
    "공식 안내 확인이 필요",
    "최신 정보를 확인",
    "정확한 영업시간은",
)

_STOP_WORDS = {
    "공항",
    "인천공항",
    "인천국제공항",
    "알려줘",
    "알려주세요",
    "있어",
    "있나요",
    "어디",
    "어디에",
    "어떻게",
    "관련",
    "정보",
    "질문",
    "좀",
    "뭐가",
    "무엇",
    "여부",
    "운영",
}

_KOREAN_SUFFIXES = (
    "으로",
    "에서",
    "에게",
    "까지",
    "부터",
    "처럼",
    "보다",
    "이나",
    "거나",
    "하고",
    "이며",
    "인가요",
    "있나요",
    "있어",
    "알려줘",
    "주세요",
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "에",
    "의",
    "도",
    "만",
)

_SEARCH_INTENT_TERMS = {
    "검색",
    "매장",
    "위치",
    "어디",
    "전화번호",
    "연락처",
    "운영시간",
    "영업시간",
    "시간",
    "가격",
    "메뉴",
    "문의",
}

_DYNAMIC_FACILITY_TERMS = {
    "매장",
    "카페",
    "식당",
    "편의점",
    "약국",
    "라운지",
    "은행",
    "환전소",
    "면세점",
    "영업시간",
    "운영시간",
    "위치",
    "어디",
    "전화번호",
    "연락처",
}

_STATIC_CONTACT_TERMS = {
    "고객센터",
    "콜센터",
    "헬프데스크",
    "help desk",
    "대표번호",
    "공항이용안내",
}

_TERMINAL_LABELS = {
    "P01": "제1여객터미널",
    "P02": "탑승동",
    "P03": "제2여객터미널",
}

_FACILITY_FUNCTIONS = {
    "21": "면세점 쇼핑",
    "22": "일반 쇼핑",
    "23": "식음료",
    "25": "편의·공공시설",
    "26": "전시·공연·체험",
}

_FACILITY_PAGE_IDS = {
    "21": "1003",
    "22": "1004",
    "23": "1006",
    "25": "1008",
    "26": "1009",
}

_FACILITY_TERM_EXCLUDES = {
    "제1여객터미널",
    "제2여객터미널",
    "제1터미널",
    "제2터미널",
    "1터미널",
    "2터미널",
    "터미널1",
    "터미널2",
    "터미널",
    "탑승동",
    "t1",
    "t2",
}

_OFFICIAL_FACILITY_URL = (
    "https://www.airport.kr/facilityInfo/ap_ko/{function_no}/list.do"
)


def extract_search_terms(text: str) -> List[str]:
    terms = []
    for raw_term in re.findall(r"[0-9A-Za-z가-힣]+", text.lower()):
        term = raw_term
        for suffix in _KOREAN_SUFFIXES:
            if term.endswith(suffix) and len(term) - len(suffix) >= 2:
                term = term[: -len(suffix)]
                break
        if len(term) >= 2 and term not in _STOP_WORDS:
            terms.append(term)
    return list(dict.fromkeys(terms))


def extract_focus_terms(text: str) -> List[str]:
    """Return entity-like terms, excluding words that only describe intent."""
    terms = [
        term
        for term in extract_search_terms(text)
        if term not in _SEARCH_INTENT_TERMS
    ]
    return sorted(terms, key=len, reverse=True)


def is_dynamic_facility_question(question: str) -> bool:
    """Return True for store/facility details that can change over time."""
    normalized = question.lower()
    if any(term in normalized for term in _STATIC_CONTACT_TERMS):
        return False
    return any(term in normalized for term in _DYNAMIC_FACILITY_TERMS)


def extract_facility_search_term(question: str) -> str:
    """Extract the store or facility phrase used by the official search."""
    candidates = [
        term
        for term in extract_focus_terms(question)
        if term not in _FACILITY_TERM_EXCLUDES
    ]
    if not candidates:
        candidates = [
            term
            for term in extract_search_terms(question)
            if term not in _FACILITY_TERM_EXCLUDES
        ]
    return max(candidates, key=len) if candidates else ""


def _requested_terminal_ids(question: str) -> List[str]:
    normalized = question.lower().replace(" ", "")
    terminal_ids = []

    if any(
        marker in normalized
        for marker in ("제1여객터미널", "1터미널", "터미널1", "t1")
    ):
        terminal_ids.append("P01")
    if any(
        marker in normalized
        for marker in ("탑승동", "concourse")
    ):
        terminal_ids.append("P02")
    if any(
        marker in normalized
        for marker in ("제2여객터미널", "2터미널", "터미널2", "t2")
    ):
        terminal_ids.append("P03")

    return terminal_ids


def _decode_terminal_id(url: str) -> Optional[str]:
    encoded = parse_qs(urlparse(url).query).get("enc", [None])[0]
    if not encoded:
        return None

    try:
        padded = encoded + "=" * (-len(encoded) % 4)
        decoded = base64.urlsafe_b64decode(padded).decode(
            "utf-8",
            errors="ignore",
        )
        decoded = unquote(decoded)
    except Exception:
        return None

    match = re.search(r"srchTerminalId=(P0[123])", decoded)
    return match.group(1) if match else None


def extract_relevant_context(
    question: str, content: str, window: int = 240
) -> str:
    """Trim a search snippet to the section around the requested entity."""
    compact = re.sub(r"\s+", " ", content).strip()
    if not compact:
        return ""

    lowered = compact.lower()
    matched_term = next(
        (term for term in extract_focus_terms(question) if term in lowered),
        None,
    )
    if not matched_term:
        return compact

    match_index = lowered.find(matched_term)
    start = max(0, match_index - 180)
    end = min(len(compact), match_index + len(matched_term) + window)

    next_detail = lowered.find("상세보기", match_index)
    if next_detail != -1 and next_detail < end:
        end = next_detail + len("상세보기")

    excerpt = compact[start:end].strip(" .·-|")
    if start > 0:
        excerpt = f"... {excerpt}"
    if end < len(compact) and not excerpt.endswith("상세보기"):
        excerpt = f"{excerpt} ..."
    return excerpt


def needs_web_search(answer: str) -> bool:
    """Return True only when the local answer explicitly indicates a gap."""
    normalized = answer.strip()
    return any(marker in normalized for marker in _UNKNOWN_MARKERS)


def documents_look_unrelated(question: str, documents: List[Any]) -> bool:
    """Cheap guard for no-LLM mode where BM25 always returns top documents."""
    if not documents:
        return True

    question_terms = extract_search_terms(question)
    if not question_terms:
        return False

    context = " ".join(
        getattr(document, "page_content", str(document))
        for document in documents
    ).lower()
    matched_terms = [term for term in question_terms if term in context]
    if not matched_terms:
        return True

    distinctive_terms = [term for term in question_terms if len(term) >= 4]
    if distinctive_terms and not any(
        term in context for term in distinctive_terms
    ):
        return True

    return False


class WebSearchFallback:
    """One-shot web search fallback that preserves the existing RAG response."""

    def __init__(self, max_results: int = 4):
        self.max_results = max_results
        self.last_search_status = "not_started"
        self.last_search_errors: List[str] = []
        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "너는 인천공항 이용 정보를 안내하는 검색 도우미야. "
                    "반드시 제공된 웹 검색 결과만 근거로 답해. "
                    "매장이나 시설 질문은 검색 결과 전체를 종합해서 "
                    "터미널별 모든 확인된 지점을 나열해. "
                    "각 검색 결과의 [검색 필터: 터미널명]을 해당 정보의 "
                    "터미널로 간주하고, 다른 터미널 정보와 섞지 마. "
                    "위치, 영업시간, 연락처가 같은 근거 안에 명시되지 "
                    "않았다면 추론하지 말고 '세부 정보 확인 필요'라고 써. "
                    "한 터미널의 결과만 확인했다는 이유로 다른 터미널에 "
                    "매장이 없다고 단정하지 마. "
                    "검색 결과에 없는 내용은 추측하지 말고 확인되지 않았다고 말해. "
                    "실시간으로 바뀔 수 있는 정보는 공식 사이트 재확인이 필요하다고 안내해. "
                    "답변은 한국어로 간결하게 작성해.",
                ),
                (
                    "human",
                    "질문: {question}\n\n웹 검색 결과:\n{context}\n\n답변:",
                ),
            ]
        )

    def answer(self, question: str, llm: Optional[Any] = None) -> Dict:
        results = self._search(question)
        return self.answer_from_results(question, results, llm)

    def answer_from_results(
        self,
        question: str,
        results: List[Dict[str, str]],
        llm: Optional[Any] = None,
    ) -> Dict:
        if not results:
            if self.last_search_status == "package_missing":
                detail = (
                    "웹 검색 패키지가 설치되지 않았습니다. "
                    "requirements-search.txt를 설치해주세요."
                )
            elif self.last_search_status == "search_failed":
                detail = "웹 검색 연결에 실패했습니다."
            else:
                detail = "해당 검색 결과를 찾을 수 없습니다."
            return {
                "answer": detail,
                "sources": [],
            }

        sources = [
            {
                "title": result["title"],
                "source": result["url"],
                "content": result["content"][:300],
            }
            for result in results
        ]

        if all(
            result.get("source_type") == "official_facility_list"
            for result in results
        ):
            return {
                "answer": self._format_official_facility_answer(results),
                "sources": sources,
            }

        if llm is None:
            snippets = "\n\n".join(
                f"- {result['title']}: {result['content']}"
                for result in results
            )
            return {
                "answer": (
                    "로컬 문서에 관련 내용이 없어 웹 검색 결과를 안내합니다.\n\n"
                    f"{snippets}"
                ),
                "sources": sources,
            }

        context = "\n\n---\n\n".join(
            f"터미널: {result.get('terminal', '터미널 미확인')}\n"
            f"제목: {result['title']}\n"
            f"내용: {result['content']}\n"
            f"출처: {result['url']}"
            for result in results
        )
        try:
            chain = self.prompt | llm | StrOutputParser()
            answer = chain.invoke(
                {"question": question, "context": context}
            )
            return {"answer": answer, "sources": sources}
        except Exception:
            return {
                "answer": (
                    "웹 검색 결과는 찾았지만 LLM 요약에 실패했습니다. "
                    "아래 참고 문서에서 내용을 확인해주세요."
                ),
                "sources": sources,
            }

    def search_results(self, question: str) -> List[Dict[str, str]]:
        """Return ranked official search results for agent tool use."""
        return self._search(question)

    def _search(self, question: str) -> List[Dict[str, str]]:
        self.last_search_status = "searching"
        self.last_search_errors = []

        if is_dynamic_facility_question(question):
            facility_results = self._search_official_facilities(question)
            if facility_results:
                self.last_search_status = "results_found"
                return facility_results

        try:
            from ddgs import DDGS
        except ImportError as exc:
            self.last_search_status = "package_missing"
            self.last_search_errors.append(str(exc))
            return []

        official_results = self._run_queries(
            self._build_official_queries(question),
            DDGS,
            question,
        )
        official_results = [
            result
            for result in official_results
            if self._is_official_airport_result(result)
        ]
        official_ranked = self._rank_relevant_results(
            question, official_results
        )
        if official_ranked:
            official_ranked = self._select_diverse_results(
                official_ranked
            )
            self.last_search_status = "results_found"
            return official_ranked[: self.max_results]

        self.last_search_status = (
            "search_failed" if self.last_search_errors else "no_results"
        )
        return []

    def _search_official_facilities(
        self,
        question: str,
    ) -> List[Dict[str, str]]:
        search_term = extract_facility_search_term(question)
        if not search_term:
            return []

        terminal_ids = _requested_terminal_ids(question)
        if not terminal_ids:
            terminal_ids = ["P01", "P02", "P03"]

        jobs = [
            (function_no, terminal_id)
            for function_no in _FACILITY_FUNCTIONS
            for terminal_id in terminal_ids
        ]

        def fetch(job):
            function_no, terminal_id = job
            url = _OFFICIAL_FACILITY_URL.format(
                function_no=function_no
            )
            params = {
                "srchTerminalId": terminal_id,
                "srchColumn": "user",
                "srchWrd": search_term,
            }
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"
                ),
                "Accept-Language": "ko-KR,ko;q=0.9",
                "Referer": (
                    "https://www.airport.kr/ap_ko/"
                    f"{_FACILITY_PAGE_IDS[function_no]}/subview.do"
                ),
            }
            try:
                response = requests.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=10,
                )
                response.raise_for_status()
                results = self._parse_facility_cards(
                    response.content,
                    search_term=search_term,
                    function_no=function_no,
                    terminal_id=terminal_id,
                    source_url=f"{url}?{urlencode(params)}",
                )
                return results, None
            except Exception as exc:
                return [], (
                    f"facility/{function_no}/{terminal_id}: {exc}"
                )

        results: List[Dict[str, str]] = []
        worker_count = min(8, len(jobs)) or 1
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            for job_results, error in executor.map(fetch, jobs):
                results.extend(job_results)
                if error:
                    self.last_search_errors.append(error)

        unique_results = []
        seen = set()
        for result in results:
            key = (
                result.get("facility_id"),
                result.get("terminal_id"),
                result.get("name"),
                result.get("location"),
            )
            if key in seen:
                continue
            seen.add(key)
            unique_results.append(result)

        terminal_order = {"P01": 0, "P02": 1, "P03": 2}
        return sorted(
            unique_results,
            key=lambda result: (
                terminal_order.get(result.get("terminal_id"), 9),
                result.get("name", ""),
                result.get("location", ""),
            ),
        )[:20]

    @staticmethod
    def _parse_facility_cards(
        document: bytes,
        search_term: str,
        function_no: str,
        terminal_id: str,
        source_url: str,
    ) -> List[Dict[str, str]]:
        root = html.fromstring(document)
        results = []
        normalized_term = search_term.casefold()

        for element in root.iter("div"):
            classes = (element.get("class") or "").split()
            if "box" not in classes:
                continue

            full_text = " ".join(element.text_content().split())
            if normalized_term not in full_text.casefold():
                continue

            def text_for(class_name: str) -> str:
                matches = element.xpath(
                    ".//*[contains("
                    "concat(' ', normalize-space(@class), ' '), "
                    f"' {class_name} ')]"
                )
                if not matches:
                    return ""
                return " ".join(matches[0].text_content().split())

            strong_matches = element.xpath(
                ".//div[contains("
                "concat(' ', normalize-space(@class), ' '), "
                "' title ')]//strong"
            )
            name = ""
            if strong_matches:
                direct_text = strong_matches[0].xpath("./text()")
                name = " ".join(
                    text.strip()
                    for text in direct_text
                    if text.strip()
                )
            name = name or search_term

            category = text_for("cate")
            badge = text_for("time")
            hours = text_for("icon1")
            phone = text_for("icon2")
            location = text_for("icon3")

            location_terminal_id = terminal_id
            if "제1여객터미널" in location:
                location_terminal_id = "P01"
            elif "제2여객터미널" in location:
                location_terminal_id = "P03"
            elif "탑승동" in location:
                location_terminal_id = "P02"

            facility_id = ""
            for button in element.xpath(".//button"):
                onclick = button.get("onclick") or ""
                match = re.search(r"'(\d+)'", onclick)
                if match:
                    facility_id = match.group(1)
                    break

            details = [name]
            if badge:
                details.append(badge)
            if hours:
                details.append(f"영업시간 {hours}")
            if phone:
                details.append(f"연락처 {phone}")
            if location:
                details.append(f"위치 {location}")

            terminal = _TERMINAL_LABELS.get(
                location_terminal_id,
                "터미널 미확인",
            )
            results.append(
                {
                    "title": f"{name} - {terminal} - {location}",
                    "content": " | ".join(details),
                    "url": source_url,
                    "source_type": "official_facility_list",
                    "category": (
                        category
                        or _FACILITY_FUNCTIONS.get(function_no, "")
                    ),
                    "name": name,
                    "badge": badge,
                    "hours": hours,
                    "phone": phone,
                    "location": location,
                    "facility_id": facility_id,
                    "terminal_id": location_terminal_id,
                    "terminal": terminal,
                }
            )

        return results

    @staticmethod
    def _format_official_facility_answer(
        results: List[Dict[str, str]],
    ) -> str:
        lines = [
            "인천공항 공식 시설 목록에서 다음 지점을 확인했습니다."
        ]
        grouped: Dict[str, List[Dict[str, str]]] = {}
        for result in results:
            grouped.setdefault(result["terminal"], []).append(result)

        for terminal in (
            "제1여객터미널",
            "탑승동",
            "제2여객터미널",
            "터미널 미확인",
        ):
            terminal_results = grouped.get(terminal)
            if not terminal_results:
                continue
            lines.append(f"\n[{terminal}]")
            for result in terminal_results:
                lines.append(f"- {result['name']}")
                hours = result.get("hours", "")
                badge = result.get("badge", "")
                if badge.upper() == "24H":
                    lines.append("  영업시간: 24시간")
                elif hours:
                    lines.append(f"  영업시간: {hours}")
                if result.get("phone"):
                    lines.append(f"  연락처: {result['phone']}")
                if result.get("location"):
                    lines.append(f"  위치: {result['location']}")

        lines.append(
            "\n영업시간과 입점 정보는 변경될 수 있으니 방문 전 "
            "인천공항 공식 사이트에서 다시 확인해 주세요."
        )
        return "\n".join(lines)

    def _run_queries(
        self,
        queries: List[str],
        ddgs_class: Any,
        question: str,
    ) -> List[Dict[str, str]]:
        def run_query(query: str):
            try:
                with ddgs_class() as ddgs:
                    raw_results = list(
                        ddgs.text(query, max_results=self.max_results)
                    )
                return query, raw_results, None
            except Exception as exc:
                return query, [], str(exc)

        combined_results: List[Dict[str, str]] = []
        worker_count = min(4, len(queries)) or 1
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            query_results = executor.map(run_query, queries)

        for query, raw_results, error in query_results:
            if error:
                self.last_search_errors.append(f"{query}: {error}")
                continue

            normalized = self._normalize_results(
                raw_results,
                query=query,
                question=question,
            )
            combined_results.extend(normalized)

        return self._deduplicate_results(combined_results)

    def _rank_relevant_results(
        self, question: str, results: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        relevant = [
            result
            for result in results
            if self._result_matches_question(question, result)
        ]
        return sorted(
            relevant,
            key=lambda result: self._score_result(question, result),
            reverse=True,
        )

    @staticmethod
    def _build_official_queries(question: str) -> List[str]:
        terms = extract_search_terms(question)
        distinctive = max(terms, key=len) if terms else question.strip()
        queries = [
            f'site:airport.kr "{distinctive}"',
            f"site:airport.kr {question}",
        ]
        if is_dynamic_facility_question(question):
            terminal_ids = _requested_terminal_ids(question)
            if not terminal_ids:
                terminal_ids = ["P01", "P02", "P03"]
            queries.extend(
                query
                for terminal_id in terminal_ids
                for query in (
                    (
                        f"site:airport.kr/ap_ko "
                        f"{distinctive} {terminal_id}"
                    ),
                    (
                        f"site:airport.kr/ap_ko "
                        f"{distinctive} "
                        f"{_TERMINAL_LABELS[terminal_id]} 위치"
                    ),
                )
            )
        return list(dict.fromkeys(query for query in queries if query.strip()))

    @classmethod
    def _build_queries(cls, question: str) -> List[str]:
        """Keep the official-only query list for notebook/debug compatibility."""
        return cls._build_official_queries(question)

    @staticmethod
    def _result_matches_question(
        question: str, result: Dict[str, str]
    ) -> bool:
        terms = extract_focus_terms(question)
        if not terms:
            terms = extract_search_terms(question)
        if not terms:
            return True
        searchable = f"{result['title']} {result['content']}".lower()
        return any(term in searchable for term in terms)

    @staticmethod
    def _is_official_airport_result(result: Dict[str, str]) -> bool:
        domain = urlparse(result["url"]).netloc.lower()
        return domain == "airport.kr" or domain.endswith(".airport.kr")

    @staticmethod
    def _score_result(question: str, result: Dict[str, str]) -> int:
        terms = extract_search_terms(question)
        title = result["title"].lower()
        content = result["content"].lower()
        domain = urlparse(result["url"]).netloc.lower()

        score = 0
        if domain == "airport.kr" or domain.endswith(".airport.kr"):
            score += 8
        if "/ap_ko/" in result["url"]:
            score += 5
        if result.get("terminal_id"):
            score += 3
        for term in terms:
            if term in title:
                score += 5
            if term in content:
                score += 2
        return score

    @staticmethod
    def _deduplicate_results(
        results: List[Dict[str, str]],
    ) -> List[Dict[str, str]]:
        merged_by_url: Dict[str, Dict[str, str]] = {}
        for result in results:
            url = result["url"]
            if url not in merged_by_url:
                merged_by_url[url] = {
                    **result,
                    "snippets": [result["content"]]
                    if result["content"]
                    else [],
                    "queries": [result.get("query", "")],
                }
                continue

            merged = merged_by_url[url]
            content = result["content"]
            if content and content not in merged["snippets"]:
                merged["snippets"].append(content)
            query = result.get("query", "")
            if query and query not in merged["queries"]:
                merged["queries"].append(query)

        unique = []
        for result in merged_by_url.values():
            snippets = result.pop("snippets", [])
            terminal_id = result.get("terminal_id")
            if terminal_id:
                snippets = [
                    snippet
                    for snippet in snippets
                    if WebSearchFallback._snippet_matches_terminal(
                        snippet,
                        terminal_id,
                    )
                ]
            result["content"] = " | ".join(snippets)
            unique.append(result)
        return unique

    @staticmethod
    def _snippet_matches_terminal(
        snippet: str,
        terminal_id: str,
    ) -> bool:
        compact = snippet.lower().replace(" ", "")
        terminal_markers = {
            "P01": ("제1여객터미널", "1터미널", "t1"),
            "P02": ("탑승동", "concourse"),
            "P03": ("제2여객터미널", "2터미널", "t2"),
        }
        own_markers = terminal_markers[terminal_id]
        other_markers = [
            marker
            for other_id, markers in terminal_markers.items()
            if other_id != terminal_id
            for marker in markers
        ]
        has_own_marker = any(
            marker in compact for marker in own_markers
        )
        has_other_marker = any(
            marker in compact for marker in other_markers
        )
        return has_own_marker or not has_other_marker

    @staticmethod
    def _normalize_results(
        raw_results: List[Dict],
        query: str = "",
        question: str = "",
    ) -> List[Dict[str, str]]:
        normalized = []
        focus_terms = extract_focus_terms(question)
        for result in raw_results:
            url = str(result.get("href") or result.get("url") or "").strip()
            if not url:
                continue
            title = str(result.get("title") or "웹 검색 결과").strip()
            content = str(
                result.get("body")
                or result.get("description")
                or ""
            ).strip()
            searchable = f"{title} {content}".lower()
            if focus_terms and not any(
                term in searchable for term in focus_terms
            ):
                continue
            if content:
                content = extract_relevant_context(
                    question,
                    content,
                )
            terminal_id = _decode_terminal_id(url)
            normalized.append(
                {
                    "title": title,
                    "content": content,
                    "url": url,
                    "query": query,
                    "terminal_id": terminal_id,
                    "terminal": _TERMINAL_LABELS.get(
                        terminal_id,
                        "터미널 미확인",
                    ),
                }
            )
        return normalized

    def _select_diverse_results(
        self,
        results: List[Dict[str, str]],
    ) -> List[Dict[str, str]]:
        korean_results = [
            result for result in results if "/ap_ko/" in result["url"]
        ]
        candidates = korean_results or results

        selected = []
        selected_urls = set()
        for terminal_id in ("P01", "P02", "P03"):
            terminal_result = next(
                (
                    result
                    for result in candidates
                    if result.get("terminal_id") == terminal_id
                ),
                None,
            )
            if terminal_result:
                selected.append(
                    self._enrich_result_context(
                        terminal_result
                    )
                )
                selected_urls.add(terminal_result["url"])

        for result in candidates:
            if result["url"] in selected_urls:
                continue
            selected.append(self._enrich_result_context(result))
            selected_urls.add(result["url"])

        return selected

    @staticmethod
    def _enrich_result_context(
        result: Dict[str, str],
    ) -> Dict[str, str]:
        terminal = result.get("terminal", "터미널 미확인")
        content = result.get("content", "")
        return {
            **result,
            "content": (
                f"[검색 필터: {terminal}] "
                f"{content}"
            ),
        }
