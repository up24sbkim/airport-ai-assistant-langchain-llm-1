import os
import re
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from .web_search_fallback import (
    WEB_SEARCH_SENTINEL,
    WebSearchFallback,
    documents_look_unrelated,
    extract_search_terms,
    needs_web_search,
)

load_dotenv()

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

_CONTACT_QUERY_ALIASES = {
    "고객센터": "공항이용안내 Help Desk 헬프데스크 콜센터 대표번호",
    "콜센터": "공항이용안내 Help Desk 헬프데스크 고객센터 대표번호",
    "헬프데스크": "공항이용안내 Help Desk 콜센터 고객센터 대표번호",
    "help desk": "공항이용안내 헬프데스크 콜센터 고객센터 대표번호",
    "대표번호": "공항이용안내 Help Desk 헬프데스크 콜센터 고객센터",
    "분실물": "유실물관리소 분실물센터",
}

_PHONE_INTENT_WORDS = (
    "전화번호",
    "연락처",
    "대표번호",
    "문의 번호",
    "고객센터 번호",
    "콜센터 번호",
    "헬프데스크 번호",
    "전화해",
    "전화해야",
)

_GENERIC_CONTACT_TERMS = {
    "전화번호",
    "연락처",
    "대표번호",
    "문의",
    "번호",
}

_ENTITY_SUFFIXES = (
    "매장",
    "센터",
    "관리소",
    "데스크",
    "사무소",
    "식당",
    "카페",
)


def clean_chunk_for_retrieval(chunk: str) -> str:
    """Remove generated query examples while preserving source metadata."""
    marker = "\n관련 질문 표현:"
    if marker not in chunk:
        return chunk.strip()

    content, noisy_section = chunk.split(marker, 1)
    source_index = noisy_section.find("\n출처:")
    if source_index == -1:
        return content.strip()

    source_metadata = noisy_section[source_index:].strip()
    return f"{content.strip()}\n\n{source_metadata}"


def expand_query_for_retrieval(question: str) -> str:
    """Add Korean compound variants without changing the original question."""
    terms = extract_search_terms(question)
    compounds = [
        terms[index] + terms[index + 1]
        for index in range(len(terms) - 1)
    ]
    if 2 <= len(terms) <= 4:
        compounds.append("".join(terms))
    aliases = [
        alias
        for keyword, alias in _CONTACT_QUERY_ALIASES.items()
        if keyword in question.lower()
    ]
    additions = list(dict.fromkeys([*compounds, *aliases]))
    return " ".join([question, *additions]).strip()


def _is_phone_question(question: str) -> bool:
    normalized = question.lower()
    return any(word in normalized for word in _PHONE_INTENT_WORDS)


def _is_customer_center_question(question: str) -> bool:
    normalized = question.lower()
    if any(
        keyword in normalized
        for keyword in ("고객센터", "콜센터", "헬프데스크", "help desk", "대표번호")
    ):
        return True

    specific_terms = [
        term
        for term in extract_search_terms(question)
        if term not in _GENERIC_CONTACT_TERMS
    ]
    return _is_phone_question(question) and not specific_terms


def _extract_field_lines(content: str, field_name: str) -> List[str]:
    lines = content.splitlines()
    values: List[str] = []
    collecting = False

    for line in lines:
        stripped = line.strip()
        if not collecting:
            prefix = f"{field_name}:"
            if stripped.startswith(prefix):
                collecting = True
                inline_value = stripped[len(prefix):].strip()
                if inline_value:
                    values.append(inline_value)
            continue

        if not stripped:
            if values:
                break
            continue
        if stripped.endswith(":") and values:
            break

        value = stripped.lstrip("- ").strip()
        if value:
            values.append(value)

    return values


def _deduplicate_field_values(values: List[str]) -> List[str]:
    normalized = []
    for value in values:
        parts = [part.strip() for part in value.split(",") if part.strip()]
        deduplicated = ", ".join(dict.fromkeys(parts))
        if deduplicated and deduplicated not in normalized:
            normalized.append(deduplicated)
    return normalized


def _contact_query_terms(question: str) -> List[str]:
    terms = [
        term
        for term in extract_search_terms(question)
        if term not in _GENERIC_CONTACT_TERMS
    ]
    expanded = list(terms)
    for term in terms:
        for suffix in _ENTITY_SUFFIXES:
            if term.endswith(suffix) and len(term) - len(suffix) >= 2:
                expanded.append(term[: -len(suffix)])
                break
    return list(dict.fromkeys(expanded))


def _contact_document_score(question: str, document: Document) -> int:
    title = document.metadata.get("title", "").lower()
    content = document.page_content.lower()
    normalized_question = question.lower()
    score = 0

    terms = _contact_query_terms(question)
    for term in terms:
        if term in title:
            score += 8
        elif term in content:
            score += 2

    if _is_customer_center_question(question):
        if any(
            keyword in title
            for keyword in ("공항이용안내", "help desk", "헬프데스크", "콜센터")
        ):
            score += 20

    if "분실물" in normalized_question or "유실물" in normalized_question:
        if "유실물관리소" in title:
            score += 20

    if "제1" in normalized_question and "제1" in content:
        score += 10
    if "제2" in normalized_question and "제2" in content:
        score += 10

    return score


def build_contact_answer(
    question: str, documents: List[Document]
) -> Optional[Dict]:
    """Return exact contact fields without asking the LLM to reproduce numbers."""
    if not _is_phone_question(question):
        return None

    candidates = []
    for index, document in enumerate(documents):
        phone_numbers = _extract_field_lines(
            document.page_content, "전화번호"
        )
        phone_numbers = _deduplicate_field_values(phone_numbers)
        if not phone_numbers:
            continue
        candidates.append(
            (
                _contact_document_score(question, document),
                -index,
                document,
                phone_numbers,
            )
        )

    if not candidates:
        return None

    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    best_score = candidates[0][0]
    if best_score < 8:
        return None
    selected = [
        item
        for item in candidates
        if item[0] == best_score
    ][:2]

    is_customer_center = _is_customer_center_question(question)
    if is_customer_center:
        selected = selected[:1]

    answer_lines = []
    sources = []
    seen_records = set()
    for _, _, document, phone_numbers in selected:
        title = document.metadata.get("title", "공항 연락처")
        locations = _extract_field_lines(
            document.page_content, "위치/터미널"
        )
        location = locations[0] if locations else ""
        phone_text = ", ".join(dict.fromkeys(phone_numbers))
        record_key = (title, location, phone_text)
        if record_key in seen_records:
            continue
        seen_records.add(record_key)

        if is_customer_center:
            answer_lines.append(
                f"인천공항 고객센터(공항이용안내/Help Desk) 전화번호는 "
                f"{phone_text}입니다."
            )
        elif title.startswith("공항 내 매장 - ") and location:
            store_name = title.removeprefix("공항 내 매장 - ").strip()
            answer_lines.append(
                f"- {store_name} ({location}): {phone_text}"
            )
        elif location:
            answer_lines.append(f"- {location}: {phone_text}")
        else:
            answer_lines.append(f"- {title}: {phone_text}")

        sources.append(
            {
                "title": title,
                "source": document.metadata.get("source", "unknown"),
                "content": document.page_content[:300],
            }
        )

    if not answer_lines:
        return None

    if is_customer_center:
        answer = answer_lines[0]
    elif len(answer_lines) == 1:
        answer = f"확인된 전화번호입니다.\n{answer_lines[0]}"
    else:
        answer = "터미널별 전화번호입니다.\n" + "\n".join(answer_lines)

    return {"answer": answer, "sources": sources}


def load_airport_documents() -> List[Document]:
    docs: List[Document] = []
    for path in sorted(DATA_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        # 아주 단순하게 제목 단위로 나누기
        chunks = [c.strip() for c in text.split("\n## ") if c.strip()]
        for i, chunk in enumerate(chunks):
            chunk = clean_chunk_for_retrieval(chunk)
            if i == 0 and chunk.startswith("#"):
                title = chunk.splitlines()[0].replace("#", "").strip()
            else:
                first_line = chunk.splitlines()[0].strip()
                title = first_line.replace("#", "").strip()
            docs.append(
                Document(
                    page_content=chunk,
                    metadata={"source": path.name, "title": title},
                )
            )
    return docs


class AirportRAG:
    """공항 문서를 찾아서 답변하는 간단한 RAG 엔진."""

    def __init__(self):
        self.documents = load_airport_documents()
        self.retriever = BM25Retriever.from_documents(self.documents)
        self.retriever.k = 4
        self.llm = self._build_llm()
        self.web_search = WebSearchFallback()
        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "너는 인천공항 출국 준비를 도와주는 공항 AI 도우미야. "
                    "반드시 제공된 공항 문서 내용을 근거로 답해. "
                    "핵심 답변을 먼저 말하고, 필요한 경우 2~4개의 짧은 항목으로 정리해. "
                    "사용자가 이해하기 쉬운 친절한 서비스 말투로 답해. "
                    "Markdown 강조 문법(**텍스트**, __텍스트__)과 긴 출처 URL은 쓰지 마. "
                    "문서가 질문과 관련 없거나 답을 찾을 수 없으면 다른 설명 없이 "
                    f"정확히 {WEB_SEARCH_SENTINEL}라고만 답해. "
                    "문서에 특정 매장, 시설, 서비스가 언급되지 않았다는 이유로 "
                    "존재하지 않는다고 단정하지 마. "
                    "질문에 포함된 고유명사가 문서에 명시되어 있지 않거나 "
                    "운영 여부를 확인할 근거가 없으면 "
                    f"정확히 {WEB_SEARCH_SENTINEL}라고만 답해. "
                    "실시간으로 달라질 수 있는 내용은 공식 안내 확인이 필요하다고 안내해. "
                    "답변은 한국어로 쉽고 짧게 해.",
                ),
                (
                    "human",
                    "질문: {question}\n\n검색된 공항 문서:\n{context}\n\n답변:",
                ),
            ]
        )

    def _build_llm(self):
        api_key = os.getenv("UPSTAGE_API_KEY")
        model = os.getenv("SOLAR_MODEL", "solar-pro3")
        if not api_key or api_key == "your_upstage_solar_api_key_here":
            return None
        return ChatOpenAI(
            api_key=api_key,
            base_url="https://api.upstage.ai/v1",
            model=model,
            temperature=0.2,
        )

    def _postprocess_answer(self, answer: str) -> str:
        """서비스 화면에 자연스럽게 보이도록 최종 답변을 정리한다."""
        if not answer:
            return (
                "제공된 공항 안내 문서에서 정확한 정보를 찾지 못했어요. "
                "인천국제공항 공식 사이트나 항공사 안내를 확인해 주세요."
            )

        text = answer.strip()
        text = re.sub(r"<\|[^|]+\|>", "", text)
        text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
        text = re.sub(r"__(.*?)__", r"\1", text)
        text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
        text = text.replace("`", "")
        text = re.sub(r"^\s*>\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\(?출처\s*:\s*.*?\)?", "", text)
        text = re.sub(r"출처 URL\s*:\s*.*", "", text)
        text = re.sub(r"https?://\S+", "", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _finalize_result(self, result: Dict) -> Dict:
        result["answer"] = self._postprocess_answer(result.get("answer", ""))
        return result

    def retrieve_local(self, question: str) -> Dict:
        """Retrieve local airport evidence without invoking web search."""
        contact_answer = build_contact_answer(question, self.documents)
        if contact_answer is not None:
            return {
                "found": True,
                "direct_answer": contact_answer["answer"],
                "context": contact_answer["answer"],
                "fallback_content": contact_answer["answer"],
                "sources": contact_answer["sources"],
            }

        retrieval_query = expand_query_for_retrieval(question)
        docs = self.retriever.invoke(retrieval_query)
        if not docs:
            return {
                "found": False,
                "direct_answer": "",
                "context": "",
                "fallback_content": "",
                "sources": [],
            }

        if documents_look_unrelated(question, docs):
            return {
                "found": False,
                "direct_answer": "",
                "context": "",
                "fallback_content": "",
                "sources": [],
            }

        context = "\n\n".join(
            [f"[{idx+1}] {d.metadata.get('title')}\n{d.page_content}" for idx, d in enumerate(docs)]
        )
        sources = [
            {
                "title": d.metadata.get("title", "문서"),
                "source": d.metadata.get("source", "unknown"),
                "content": d.page_content[:300],
            }
            for d in docs
        ]
        return {
            "found": True,
            "direct_answer": "",
            "context": context,
            "fallback_content": docs[0].page_content[:500],
            "sources": sources,
        }

    def answer_from_local(self, question: str) -> Dict:
        """Answer from bundled airport documents only."""
        retrieved = self.retrieve_local(question)
        if not retrieved["found"]:
            return {
                "answer": (
                    "로컬 공항 문서에서 질문과 직접 관련된 근거를 "
                    "찾지 못했습니다."
                ),
                "sources": [],
                "needs_web_search": True,
            }

        if retrieved["direct_answer"]:
            return {
                "answer": self._postprocess_answer(
                    retrieved["direct_answer"]
                ),
                "sources": retrieved["sources"],
                "needs_web_search": False,
            }

        # API 키가 없을 때도 데모가 죽지 않게 문서 기반 답변을 반환
        if self.llm is None:
            answer = (
                "현재 .env에 UPSTAGE_API_KEY가 없어서 Solar API 답변 대신, "
                "검색된 문서 내용을 기준으로 안내할게요.\n\n"
                f"{retrieved['fallback_content']}"
            )
        else:
            try:
                chain = self.prompt | self.llm
                response = chain.invoke(
                    {
                        "question": question,
                        "context": retrieved["context"],
                    }
                )
                answer = response.content
            except Exception:
                answer = (
                    "현재 LLM 연결에 문제가 있어 검색된 문서 내용을 기준으로 "
                    "안내합니다.\n\n"
                    f"{retrieved['fallback_content']}"
                )

        if needs_web_search(answer):
            return {
                "answer": (
                    "로컬 공항 문서에서 질문에 답할 충분한 근거를 "
                    "찾지 못했습니다."
                ),
                "sources": retrieved["sources"],
                "needs_web_search": True,
            }

        return {
            "answer": self._postprocess_answer(answer),
            "sources": retrieved["sources"],
            "needs_web_search": False,
        }

    def search_official_web(self, question: str) -> Dict:
        """Search airport.kr and summarize official web results."""
        return self._finalize_result(
            self.web_search.answer(question, self.llm)
        )

    def ask(self, question: str) -> dict:
        """Legacy one-shot RAG API retained as a safe fallback."""
        local_result = self.answer_from_local(question)
        if local_result.get("needs_web_search"):
            return self.search_official_web(question)
        return {
            "answer": local_result["answer"],
            "sources": local_result["sources"],
        }
