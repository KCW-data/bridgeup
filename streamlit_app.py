from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlencode

import streamlit as st


st.set_page_config(
    page_title="AIVIO Bridge-Up",
    page_icon="A",
    layout="centered",
    initial_sidebar_state="collapsed",
)


MAX_SAM_MEDIA_BYTES = 25 * 1024 * 1024
SAM_MEDIA_EXTENSIONS = {".flac", ".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".mov", ".ogg", ".wav", ".webm"}
SAM_BASE_URL = "https://sam.soonsoon.ai"
KIPRISPLUS_BASE_URL = "http://plus.kipris.or.kr"
KIPRISPLUS_DEFAULT_ENDPOINT = (
    "http://plus.kipris.or.kr/kipo-api/kipi/patUtiModInfoSearchSevice/getAdvancedSearch"
)

STEP_LABELS = [
    ("capture", "1 입력"),
    ("draft", "2 AI 정리"),
    ("collab", "3 협업 검수"),
    ("result", "4 결과"),
]

STATUS_OPTIONS = ["대기", "진행", "확인 필요", "완료"]

DEFAULT_JUNIOR_TASKS = [
    {
        "id": "transcript-check",
        "title": "전사문과 현장 용어 확인",
        "status": "대기",
        "memo": "",
    },
    {
        "id": "process-structure",
        "title": "작업 순서와 판단 기준 정리",
        "status": "대기",
        "memo": "",
    },
    {
        "id": "review-questions",
        "title": "시니어·기업 검수 질문 표시",
        "status": "대기",
        "memo": "",
    },
    {
        "id": "final-document",
        "title": "최종 문서 다듬기",
        "status": "대기",
        "memo": "",
    },
]

STOPWORDS = {
    "그리고",
    "그래서",
    "합니다",
    "있습니다",
    "때문",
    "작업",
    "영상",
    "음성",
    "자료",
    "확인",
    "경우",
    "부분",
    "현장",
    "정리",
    "사용",
}


def inject_style() -> None:
    st.markdown(
        """
        <style>
        :root {
          --aivio-text: #111318;
          --aivio-muted: #59616d;
          --aivio-line: #dce2ea;
          --aivio-soft: #f7f8fa;
          --aivio-blue: #155eef;
          --aivio-green: #147d64;
          --aivio-amber: #a15c00;
        }

        html, body, [data-testid="stAppViewContainer"] {
          font-size: 20px;
        }

        .block-container {
          max-width: 900px;
          padding: 1.35rem 1rem 3rem;
        }

        [data-testid="stMarkdownContainer"] p,
        [data-testid="stMarkdownContainer"] li {
          color: var(--aivio-text);
          font-size: 1.05rem;
          line-height: 1.7;
        }

        h1, h2, h3 {
          letter-spacing: 0;
        }

        .aivio-hero {
          border-bottom: 1px solid var(--aivio-line);
          margin-bottom: 1.05rem;
          padding-bottom: 1.1rem;
        }

        .aivio-kicker {
          color: var(--aivio-blue);
          font-size: 0.9rem;
          font-weight: 850;
          letter-spacing: 0;
          margin-bottom: 0.45rem;
        }

        .aivio-hero h1 {
          color: var(--aivio-text);
          font-size: clamp(2.25rem, 8vw, 4rem);
          line-height: 1.08;
          margin: 0 0 0.75rem;
        }

        .aivio-hero p {
          color: var(--aivio-muted);
          font-size: clamp(1.05rem, 3.5vw, 1.25rem);
          line-height: 1.65;
          margin: 0;
        }

        .step-strip {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 0.55rem;
          margin: 1.05rem 0 1.2rem;
        }

        .step-pill {
          border: 1px solid var(--aivio-line);
          border-radius: 8px;
          background: #fff;
          color: var(--aivio-muted);
          padding: 0.8rem 0.45rem;
          text-align: center;
          font-size: 0.95rem;
          font-weight: 850;
        }

        .step-pill.active {
          border-color: rgba(21, 94, 239, 0.55);
          color: var(--aivio-blue);
          background: #f3f7ff;
        }

        .status-chip {
          display: inline-block;
          border: 1px solid var(--aivio-line);
          border-radius: 8px;
          color: var(--aivio-muted);
          font-size: 0.95rem;
          font-weight: 800;
          margin: 0.15rem 0.35rem 0.15rem 0;
          padding: 0.42rem 0.6rem;
        }

        .status-chip.ready {
          border-color: rgba(20, 125, 100, 0.38);
          color: var(--aivio-green);
          background: #f3fbf8;
        }

        .status-chip.warn {
          border-color: rgba(161, 92, 0, 0.35);
          color: var(--aivio-amber);
          background: #fff8ed;
        }

        .section-title {
          color: var(--aivio-text);
          font-size: 1.45rem;
          font-weight: 850;
          margin: 1.2rem 0 0.65rem;
        }

        .document-preview {
          border: 1px solid var(--aivio-line);
          border-radius: 8px;
          background: #fff;
          padding: 1rem 1.05rem;
        }

        div[data-testid="stRadio"] label,
        div[data-testid="stTextInput"] label,
        div[data-testid="stTextArea"] label,
        div[data-testid="stFileUploader"] label,
        div[data-testid="stCameraInput"] label,
        div[data-testid="stAudioInput"] label,
        div[data-testid="stSelectbox"] label,
        div[data-testid="stCheckbox"] label {
          color: var(--aivio-text);
          font-size: 1.08rem !important;
          font-weight: 850 !important;
        }

        div[data-testid="stTextInput"] input,
        div[data-testid="stTextArea"] textarea,
        div[data-baseweb="select"] {
          font-size: 1.08rem !important;
        }

        div[data-testid="stTextArea"] textarea {
          line-height: 1.65;
        }

        .stButton > button,
        .stDownloadButton > button,
        div[data-testid="stLinkButton"] a {
          border-radius: 10px;
          font-size: 1.12rem;
          font-weight: 850;
          min-height: 62px;
        }

        div[data-testid="stExpander"] summary {
          font-size: 1.05rem;
          font-weight: 850;
        }

        @media (max-width: 720px) {
          .block-container {
            padding-left: 0.85rem;
            padding-right: 0.85rem;
          }

          .step-strip {
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def secret_value(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return str(value or os.getenv(name, default) or "")


def secret_list(name: str, default: str = "") -> list[str]:
    raw = secret_value(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def ensure_state() -> None:
    st.session_state.setdefault("case", None)


def uploaded_file_meta(file: Any, source: str) -> dict[str, Any]:
    return {
        "name": getattr(file, "name", source) or source,
        "type": getattr(file, "type", "unknown") or "unknown",
        "size_mb": round((getattr(file, "size", 0) or 0) / (1024 * 1024), 2),
        "source": source,
    }


def split_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []

    parts = re.split(r"(?<=[.!?。])\s+|(?:다\.|요\.|니다\.)\s*", normalized)
    return [part.strip(" .\n\t") for part in parts if len(part.strip()) >= 8][:8]


def infer_steps(text: str) -> list[str]:
    lines = [
        line.strip(" -0123456789.·")
        for line in text.splitlines()
        if len(line.strip()) >= 8
    ]
    if len(lines) >= 3:
        return lines[:6]

    sentences = split_sentences(text)
    if len(sentences) >= 3:
        return sentences[:6]

    return [
        "숙련자의 설명에서 작업 준비 상태를 확인합니다.",
        "반복되는 행동, 도구, 판단 기준을 나눕니다.",
        "정상 상황과 위험 상황을 별도 항목으로 표시합니다.",
        "주니어가 확인할 질문을 남깁니다.",
    ]


def extract_keywords(text: str, limit: int = 12) -> list[str]:
    words = re.findall(r"[가-힣A-Za-z0-9]{2,}", text)
    scored: dict[str, int] = {}
    for word in words:
        lowered = word.lower()
        if lowered in STOPWORDS or word in STOPWORDS:
            continue
        scored[word] = scored.get(word, 0) + 1

    return [
        word
        for word, _ in sorted(scored.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


def media_type_for_file(file: Any, suffix: str) -> str:
    detected = getattr(file, "type", "") or ""
    if detected:
        return detected

    return {
        ".flac": "audio/flac",
        ".mp3": "audio/mpeg",
        ".mp4": "video/mp4",
        ".mpeg": "audio/mpeg",
        ".mpga": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".mov": "video/quicktime",
        ".ogg": "audio/ogg",
        ".wav": "audio/wav",
        ".webm": "video/webm",
    }.get(suffix, "application/octet-stream")


def sam_content_type(media_type: str) -> str:
    if media_type.startswith("audio/"):
        return "audio"
    if media_type.startswith("video/"):
        return "video"
    if media_type.startswith("image/"):
        return "image"
    return "document"


def sam_media_part(file: Any, suffix: str) -> dict[str, str]:
    media_type = media_type_for_file(file, suffix)
    encoded = base64.b64encode(file.getvalue()).decode("ascii")
    return {
        "type": sam_content_type(media_type),
        "source": "base64",
        "data": encoded,
        "media_type": media_type,
    }


def sam_generate(messages: list[dict[str, Any]], task: str = "analyze", max_tokens: int = 4096) -> str:
    api_key = secret_value("SAM_API_KEY")
    if not api_key:
        raise RuntimeError("SAM_API_KEY가 없어 SAM API를 실행하지 않았습니다.")

    base_url = secret_value("SAM_BASE_URL", SAM_BASE_URL).rstrip("/")
    body = {
        "model": secret_value("SAM_MODEL", "claude-haiku"),
        "task": task,
        "messages": messages,
        "fallback": secret_list("SAM_FALLBACK_MODELS", "gpt-5.4-mini"),
        "options": {
            "stream": False,
            "temperature": 0.2,
            "max_tokens": max_tokens,
        },
    }

    request = urllib.request.Request(
        f"{base_url}/v1/generate",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "X-API-Key": api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            decoded = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"SAM API 오류 {exc.code}: {detail[:500]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"SAM API 연결 실패: {exc.reason}") from exc

    if decoded.get("ok") is not True:
        error = decoded.get("error") or {}
        message = error.get("message") or "SAM API 응답이 실패 상태입니다."
        raise RuntimeError(str(message))

    content = (decoded.get("output") or {}).get("content", "")
    if isinstance(content, list):
        chunks = []
        for item in content:
            if isinstance(item, str):
                chunks.append(item)
            elif isinstance(item, dict):
                chunks.append(str(item.get("text") or item.get("content") or ""))
        return "\n".join(chunk for chunk in chunks if chunk).strip()

    return str(content).strip()


def parse_json_object(text: str) -> dict[str, Any] | None:
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None

    try:
        value = json.loads(match.group(0))
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        return None


def as_text_list(value: Any, fallback: list[str]) -> list[str]:
    if isinstance(value, list):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return cleaned or fallback
    if isinstance(value, str) and value.strip():
        return [line.strip(" -") for line in value.splitlines() if line.strip()]
    return fallback


def transcribe_file(file: Any) -> tuple[str, str]:
    file_name = getattr(file, "name", "audio.wav") or "audio.wav"
    suffix = Path(file_name).suffix.lower() or ".wav"
    size = getattr(file, "size", 0) or 0

    if suffix not in SAM_MEDIA_EXTENSIONS:
        return "", f"{file_name}: 전사 미지원 형식"

    if size > MAX_SAM_MEDIA_BYTES:
        return "", f"{file_name}: 25MB 초과"

    try:
        transcript = sam_generate(
            [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "첨부된 영상 또는 음성의 한국어 발화를 가능한 정확히 전사하세요. "
                                "불확실한 구간은 [불명확]으로 표시하고, 설명 없이 전사문만 반환하세요."
                            ),
                        },
                        sam_media_part(file, suffix),
                    ],
                }
            ],
            task="analyze",
            max_tokens=6000,
        )
        return transcript, f"{file_name}: 전사 완료"
    except Exception as exc:
        return "", f"{file_name}: 전사 실패 - {exc}"


def transcribe_sources(files: list[Any]) -> tuple[str, list[str]]:
    transcripts: list[str] = []
    statuses: list[str] = []

    for file in files:
        text, status = transcribe_file(file)
        statuses.append(status)
        if text:
            transcripts.append(f"[{getattr(file, 'name', 'audio')}] {text}")

    return "\n\n".join(transcripts).strip(), statuses


def local_knowledge_bundle(title: str, field: str, source_text: str, files: list[dict[str, Any]]) -> dict[str, Any]:
    steps = infer_steps(source_text)
    keywords = extract_keywords(source_text)
    file_summary = ", ".join(f"{item['source']}:{item['name']}" for item in files) or "등록 자료 없음"
    core_text = source_text[:420] if source_text else "전사문 생성 후 보강이 필요합니다."

    document = f"""# {title}

## 한 줄 요약
{field} 분야의 현장 경험을 영상·음성 기반으로 수집해 주니어가 검수 가능한 노하우 문서로 전환합니다.

## 핵심 내용
- 수집 자료: {file_summary}
- 핵심 설명: {core_text}

## 작업 순서
{chr(10).join(f"{index}. {step}" for index, step in enumerate(steps, start=1))}

## 판단 기준
- 숙련자가 중요하게 보는 소리, 움직임, 순서, 예외 상황을 확인합니다.
- 위험하거나 공개하면 안 되는 정보는 검수 단계에서 분리합니다.
- 주니어가 따라 할 수 있는 단위와 반드시 질문해야 할 단위를 나눕니다.

## 주니어 협업
- 전사문과 현장 용어를 먼저 확인합니다.
- 작업 순서, 판단 기준, 주의사항을 문서 형식으로 정리합니다.
- 시니어와 기업 검수 질문을 남깁니다.

## 검수 질문
1. 실제 작업 순서와 문서의 순서가 맞습니까?
2. 주니어가 혼자 수행하면 위험한 구간이 있습니까?
3. 외부 공개가 제한되는 장면, 장비명, 고객 정보가 있습니까?
"""

    return {
        "document_markdown": document,
        "keywords": keywords,
        "claims": [f"{keyword} 기반 작업 판단 또는 전수 방법" for keyword in keywords[:5]],
        "junior_work_units": steps[:4],
        "review_questions": [
            "실제 작업 순서와 문서의 순서가 맞습니까?",
            "주니어가 혼자 수행하면 위험한 구간이 있습니까?",
            "외부 공개가 제한되는 장면, 장비명, 고객 정보가 있습니까?",
        ],
        "risk_notes": [
            "영상·음성에 개인정보, 영업비밀, 고객 정보가 포함될 수 있습니다.",
            "AI 초안은 시니어와 기업 검수 전 확정본으로 사용하지 않습니다.",
        ],
    }


def sam_knowledge_bundle(title: str, field: str, source_text: str, files: list[dict[str, Any]]) -> dict[str, Any]:
    fallback = local_knowledge_bundle(title, field, source_text, files)
    if not secret_value("SAM_API_KEY") or not source_text.strip():
        return fallback

    prompt = {
        "title": title,
        "field": field,
        "source_text": source_text,
        "files": files,
        "required_json": {
            "document_markdown": "시니어 노하우 문서 Markdown",
            "keywords": ["특허/분류 검색 키워드"],
            "claims": ["권리화 가능성을 검토할 후보 문장"],
            "junior_work_units": ["주니어가 보강해야 할 작업 단위"],
            "review_questions": ["시니어와 기업에게 확인할 질문"],
            "risk_notes": ["권리, 보안, 공개 범위 관련 주의사항"],
        },
    }

    try:
        response = sam_generate(
            [
                {
                    "role": "system",
                    "content": "AIVIO Bridge-Up의 지식화 에이전트입니다. 반드시 JSON 객체만 반환하세요.",
                },
                {
                    "role": "user",
                    "content": json.dumps(prompt, ensure_ascii=False),
                },
            ],
            task="analyze",
            max_tokens=7000,
        )
    except Exception:
        return fallback

    parsed = parse_json_object(response)
    if parsed is None:
        return fallback

    return {
        "document_markdown": str(parsed.get("document_markdown") or fallback["document_markdown"]),
        "keywords": as_text_list(parsed.get("keywords"), fallback["keywords"]),
        "claims": as_text_list(parsed.get("claims"), fallback["claims"]),
        "junior_work_units": as_text_list(parsed.get("junior_work_units"), fallback["junior_work_units"]),
        "review_questions": as_text_list(parsed.get("review_questions"), fallback["review_questions"]),
        "risk_notes": as_text_list(parsed.get("risk_notes"), fallback["risk_notes"]),
    }


def build_junior_tasks(work_units: list[str]) -> list[dict[str, Any]]:
    tasks = [task.copy() for task in DEFAULT_JUNIOR_TASKS]
    for index, unit in enumerate(work_units[:3], start=1):
        tasks.append(
            {
                "id": f"unit-{index}",
                "title": f"작업 단위 확인: {unit[:36]}",
                "status": "대기",
                "memo": "",
            }
        )
    return tasks


def secret_json_object(name: str) -> dict[str, Any]:
    raw = secret_value(name)
    if not raw.strip():
        return {}

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}

    return parsed if isinstance(parsed, dict) else {}


def kiprisplus_endpoint() -> str:
    endpoint = secret_value("KIPRISPLUS_ENDPOINT", KIPRISPLUS_DEFAULT_ENDPOINT).strip()
    if endpoint.startswith(("http://", "https://")):
        return endpoint
    if endpoint.startswith("/"):
        return f"{KIPRISPLUS_BASE_URL}{endpoint}"
    return f"{KIPRISPLUS_BASE_URL}/{endpoint.lstrip('/')}"


def kiprisplus_query_param(endpoint: str) -> str:
    configured = secret_value("KIPRISPLUS_QUERY_PARAM")
    if configured:
        return configured
    if "getBibliographySumryInfoSearch" in endpoint:
        return "applicationNumber"
    return "word"


def strip_xml_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def xml_element_to_dict(element: ET.Element) -> dict[str, Any] | str:
    children = list(element)
    if not children:
        return (element.text or "").strip()

    data: dict[str, Any] = {}
    for child in children:
        key = strip_xml_tag(child.tag)
        value = xml_element_to_dict(child)
        if key in data:
            existing = data[key]
            if isinstance(existing, list):
                existing.append(value)
            else:
                data[key] = [existing, value]
        else:
            data[key] = value

    text = (element.text or "").strip()
    if text:
        data["_text"] = text
    return data


def parse_kiprisplus_payload(payload: bytes) -> dict[str, Any]:
    decoded = payload.decode("utf-8", errors="replace")
    try:
        parsed_json = json.loads(decoded)
        items = parsed_json.get("items") or parsed_json.get("item") or []
        if isinstance(items, dict):
            items = [items]
        return {
            "items": items if isinstance(items, list) else [],
            "message": str(parsed_json.get("message") or parsed_json.get("resultMsg") or ""),
            "raw_preview": decoded[:1200],
        }
    except json.JSONDecodeError:
        pass

    root = ET.fromstring(payload)
    result_message = ""
    for node in root.iter():
        if strip_xml_tag(node.tag) in {"resultMsg", "resultMessage"}:
            result_message = (node.text or "").strip()
            break

    items = []
    for item in root.iter():
        if strip_xml_tag(item.tag) == "item":
            parsed_item = xml_element_to_dict(item)
            if isinstance(parsed_item, dict):
                items.append(parsed_item)

    return {
        "items": items,
        "message": result_message,
        "raw_preview": decoded[:1200],
    }


def call_kiprisplus_search(query: str, limit: int = 5) -> dict[str, Any]:
    api_key = secret_value("KIPRISPLUS_API_KEY")
    if not api_key:
        raise RuntimeError("KIPRISPLUS_API_KEY가 없습니다. Streamlit Cloud Secrets에 등록해 주세요.")

    endpoint = kiprisplus_endpoint()
    query_param = kiprisplus_query_param(endpoint)
    params: dict[str, Any] = {
        "pageNo": "1",
        "numOfRows": str(limit),
    }
    params.update(secret_json_object("KIPRISPLUS_EXTRA_PARAMS"))
    params[query_param] = query
    params["ServiceKey"] = api_key

    separator = "&" if "?" in endpoint else "?"
    url = f"{endpoint}{separator}{urlencode(params, safe='%')}"
    request = urllib.request.Request(url, method="GET")

    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"KIPRISPlus API 오류 {exc.code}: {detail[:500]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"KIPRISPlus API 연결 실패: {exc.reason}") from exc

    parsed = parse_kiprisplus_payload(payload)
    parsed["endpoint"] = endpoint
    parsed["query_param"] = query_param
    parsed["query"] = query
    parsed["count"] = len(parsed.get("items", []))
    return parsed


def patent_item_value(item: dict[str, Any], keys: list[str]) -> str:
    lowered = {str(key).lower(): value for key, value in item.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if value is None:
            continue
        if isinstance(value, list):
            return ", ".join(str(part) for part in value if str(part).strip())
        if isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False)
        return str(value).strip()
    return ""


def build_patent_review(document: str, keywords: list[str], claims: list[str]) -> dict[str, Any]:
    keywords = keywords or extract_keywords(document, 12)
    claims = claims or [f"{keyword} 기반 작업 판단 또는 전수 방법" for keyword in keywords[:5]]
    query = " ".join(keywords[:6])
    kipris_url = "https://www.kipris.or.kr/"
    kipris_plus_url = "https://plus.kipris.or.kr/portal/data/service/DBII_000000000000001/view.do"

    readiness = "검토 필요"
    if len(document) > 900 and len(keywords) >= 8:
        readiness = "선행기술 검색 후 출원 검토 가능"
    elif len(document) > 450:
        readiness = "문서 보강 후 검색 권장"

    return {
        "readiness": readiness,
        "keywords": keywords,
        "claims": claims,
        "query": query,
        "kipris_url": kipris_url,
        "kipris_plus_url": kipris_plus_url,
        "search_url": f"{kipris_url}?query={quote_plus(query)}" if query else kipris_url,
        "notes": [
            "이 결과는 자동 예비 검토이며 등록 가능 여부의 법적 판단이 아닙니다.",
            "실제 등록 가능성은 신규성, 진보성, 산업상 이용가능성, 공개 이력, 청구항 작성에 따라 달라집니다.",
            "운영 버전에서는 KIPRISPlus API로 유사 문헌을 비교해야 합니다.",
        ],
    }


def build_case(
    context: dict[str, Any],
    files: list[dict[str, Any]],
    transcript: str,
    stt_status: list[str],
    memo: str,
) -> dict[str, Any]:
    title = str(context.get("title") or "현장 노하우")
    field = str(context.get("field") or "현장 업무")
    source_text = "\n".join(
        part
        for part in [
            transcript,
            context.get("purpose", ""),
            memo,
        ]
        if str(part).strip()
    )
    bundle = sam_knowledge_bundle(title, field, source_text, files)
    document = str(bundle["document_markdown"])

    return {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "stage": "draft",
        "title": title,
        "field": field,
        "context": context,
        "files": files,
        "transcript": transcript,
        "stt_status": stt_status,
        "memo": memo,
        "document": document,
        "collaboration": {
            "junior_tasks": build_junior_tasks(list(bundle["junior_work_units"])),
            "review_questions": list(bundle["review_questions"]),
            "risk_notes": list(bundle["risk_notes"]),
            "activity_log": [
                {
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "actor": "AI",
                    "event": "AI 초안 생성",
                }
            ],
        },
        "review": {
            "senior_ok": False,
            "company_ok": False,
            "memo": "",
        },
        "patent_review": build_patent_review(document, list(bundle["keywords"]), list(bundle["claims"])),
    }


def case_step_index(case: dict[str, Any] | None) -> int:
    if case is None:
        return 0
    keys = [key for key, _ in STEP_LABELS]
    stage = str(case.get("stage", "capture"))
    return keys.index(stage) if stage in keys else 0


def set_stage(case: dict[str, Any], stage: str, actor: str, event: str) -> None:
    case["stage"] = stage
    case.setdefault("collaboration", {}).setdefault("activity_log", []).append(
        {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "actor": actor,
            "event": event,
        }
    )


def task_progress(case: dict[str, Any] | None) -> int:
    if case is None:
        return 0
    tasks = case.get("collaboration", {}).get("junior_tasks", [])
    if not tasks:
        return 0
    done = sum(1 for task in tasks if task.get("status") == "완료")
    return int(done / len(tasks) * 100)


def render_hero() -> None:
    st.markdown(
        """
        <div class="aivio-hero">
          <div class="aivio-kicker">AIVIO Bridge-Up</div>
          <h1>말로 남기면, AI가 노하우 문서로 정리합니다.</h1>
          <p>영상과 음성을 바탕으로 시니어 경험을 문서화하고, 주니어 협업과 검수까지 이어갑니다.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_step_strip(case: dict[str, Any] | None) -> None:
    active = case_step_index(case)
    html = ['<div class="step-strip">']
    for index, (_, label) in enumerate(STEP_LABELS):
        class_name = "step-pill active" if index <= active else "step-pill"
        html.append(f'<div class="{class_name}">{label}</div>')
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def render_navigation(case: dict[str, Any] | None) -> str:
    labels = [label for _, label in STEP_LABELS]
    keys = [key for key, _ in STEP_LABELS]
    selected = st.selectbox(
        "화면",
        labels,
        index=case_step_index(case),
    )
    return keys[labels.index(selected)]


def render_api_status() -> None:
    sam_ready = bool(secret_value("SAM_API_KEY"))
    chip_class = "ready" if sam_ready else "warn"
    label = "SAM 연결됨" if sam_ready else "SAM 키 필요"
    st.markdown(f'<span class="status-chip {chip_class}">{label}</span>', unsafe_allow_html=True)


def render_capture() -> None:
    st.markdown('<div class="section-title">자료 입력</div>', unsafe_allow_html=True)
    render_api_status()

    title = st.text_input("제목", placeholder="예: 설비 이상 소리 판별 노하우")
    intake_type = st.selectbox("유형", ["시니어 노하우", "기업 과제"])
    company_name = st.text_input("기업명", placeholder="선택 입력")

    st.markdown('<div class="section-title">자료</div>', unsafe_allow_html=True)
    recorded_audio = st.audio_input("음성 녹음")
    video_files = st.file_uploader(
        "영상 업로드",
        type=["mp4", "mov", "webm"],
        accept_multiple_files=True,
        key="video-upload",
    )
    photo_file = st.camera_input("사진 촬영")
    extra_files = st.file_uploader(
        "파일 업로드",
        type=["mp3", "m4a", "wav", "webm", "ogg", "jpg", "jpeg", "png", "webp", "pdf", "txt", "docx"],
        accept_multiple_files=True,
        key="file-upload",
    )

    with st.expander("추가 정보"):
        field = st.text_input("분야", placeholder="제조, 품질, 물류, 교육")
        purpose = st.text_area("목적", height=90, placeholder="해결하려는 문제나 전수하려는 경험")
        senior_name = st.text_input("시니어", placeholder="선택 입력")
        junior_name = st.text_input("주니어", placeholder="선택 입력")
        reviewer_name = st.text_input("기업 검수자", placeholder="선택 입력")
        memo = st.text_area("보완 메모", height=100, placeholder="장비명, 현장 용어, 공개 금지 정보")

    if st.button("AI로 정리하기", type="primary", use_container_width=True):
        source_files: list[Any] = []
        file_meta: list[dict[str, Any]] = []

        if recorded_audio is not None:
            source_files.append(recorded_audio)
            file_meta.append(uploaded_file_meta(recorded_audio, "음성 녹음"))

        for file in video_files or []:
            source_files.append(file)
            file_meta.append(uploaded_file_meta(file, "영상"))

        if photo_file is not None:
            file_meta.append(uploaded_file_meta(photo_file, "사진"))

        for file in extra_files or []:
            file_meta.append(uploaded_file_meta(file, "파일"))
            name = str(getattr(file, "name", "")).lower()
            mime = str(getattr(file, "type", ""))
            if mime.startswith("audio/") or mime.startswith("video/") or name.endswith(tuple(SAM_MEDIA_EXTENSIONS)):
                source_files.append(file)

        if not title.strip():
            st.error("제목은 필요합니다.")
            return

        if source_files and not secret_value("SAM_API_KEY"):
            st.error("영상·음성 전사를 하려면 Streamlit Secrets에 SAM_API_KEY를 먼저 등록해야 합니다.")
            return

        if not source_files and not str(purpose).strip() and not str(memo).strip():
            st.error("음성, 영상, 목적, 보완 메모 중 하나는 필요합니다.")
            return

        context = {
            "title": title.strip(),
            "intake_type": intake_type,
            "company_name": company_name.strip(),
            "field": field.strip() or "현장 업무",
            "purpose": purpose.strip(),
            "senior_name": senior_name.strip(),
            "junior_name": junior_name.strip(),
            "reviewer_name": reviewer_name.strip(),
        }

        with st.spinner("전사와 AI 정리를 진행하고 있습니다."):
            transcript, statuses = transcribe_sources(source_files)
            st.session_state["case"] = build_case(context, file_meta, transcript, statuses, memo.strip())

        st.rerun()


def render_draft(case: dict[str, Any] | None) -> None:
    st.markdown('<div class="section-title">AI 정리 결과</div>', unsafe_allow_html=True)
    if case is None:
        st.info("먼저 자료를 입력해 주세요.")
        return

    statuses = case.get("stt_status", [])
    if statuses:
        with st.expander("전사 상태"):
            for status in statuses:
                if "완료" in status:
                    st.success(status)
                else:
                    st.warning(status)

    st.markdown('<div class="document-preview">', unsafe_allow_html=True)
    st.markdown(case.get("document", ""))
    st.markdown("</div>", unsafe_allow_html=True)

    with st.expander("문서 직접 수정"):
        case["document"] = st.text_area("문서", value=case.get("document", ""), height=420)

    if st.button("주니어 협업으로 넘기기", type="primary", use_container_width=True):
        set_stage(case, "collab", "운영자", "주니어 협업 시작")
        st.rerun()

    if st.button("다시 정리하기", use_container_width=True):
        source_text = "\n".join(part for part in [case.get("transcript", ""), case.get("memo", "")] if part.strip())
        bundle = sam_knowledge_bundle(case["title"], case["field"], source_text, case.get("files", []))
        case["document"] = str(bundle["document_markdown"])
        case["patent_review"] = build_patent_review(case["document"], list(bundle["keywords"]), list(bundle["claims"]))
        case["collaboration"]["review_questions"] = list(bundle["review_questions"])
        case["collaboration"]["risk_notes"] = list(bundle["risk_notes"])
        set_stage(case, "draft", "AI", "AI 재정리")
        st.rerun()


def render_collaboration(case: dict[str, Any] | None) -> None:
    st.markdown('<div class="section-title">협업 검수</div>', unsafe_allow_html=True)
    if case is None:
        st.info("AI 정리 후 협업 검수를 진행할 수 있습니다.")
        return

    collaboration = case.setdefault("collaboration", {})
    tasks = collaboration.setdefault("junior_tasks", [task.copy() for task in DEFAULT_JUNIOR_TASKS])
    review = case.setdefault("review", {"senior_ok": False, "company_ok": False, "memo": ""})

    st.progress(task_progress(case) / 100, text=f"주니어 작업 {task_progress(case)}%")

    for index, task in enumerate(tasks):
        done = task.get("status") == "완료"
        checked = st.checkbox(task.get("title", "작업 확인"), value=done, key=f"task-done-{index}")
        task["status"] = "완료" if checked else "진행"

    with st.expander("주니어 메모"):
        for index, task in enumerate(tasks):
            task["memo"] = st.text_area(
                task.get("title", f"작업 {index + 1}"),
                value=task.get("memo", ""),
                height=80,
                key=f"task-memo-{index}",
            )

    st.markdown('<div class="section-title">검수 확인</div>', unsafe_allow_html=True)
    review["senior_ok"] = st.checkbox(
        "시니어가 내용과 순서를 확인했습니다.",
        value=bool(review.get("senior_ok", False)),
        key="senior-ok",
    )
    review["company_ok"] = st.checkbox(
        "기업 공개 범위와 보안 정보를 확인했습니다.",
        value=bool(review.get("company_ok", False)),
        key="company-ok",
    )
    review["memo"] = st.text_area("검수 메모", value=review.get("memo", ""), height=110)

    with st.expander("AI 검수 질문"):
        for question in collaboration.get("review_questions", []):
            st.write(f"- {question}")

    if st.button("수정 필요", use_container_width=True):
        set_stage(case, "collab", "검수자", "수정 필요")
        st.warning("주니어 협업 상태로 남겨 두었습니다.")

    can_finish = bool(review.get("senior_ok")) and bool(review.get("company_ok"))
    if st.button("최종 결과 보기", type="primary", disabled=not can_finish, use_container_width=True):
        set_stage(case, "result", "검수자", "최종 결과 확인")
        st.rerun()


def render_kiprisplus_item(item: dict[str, Any], index: int) -> None:
    title = patent_item_value(
        item,
        ["inventionTitle", "title", "korTitle", "articleTitle", "발명의명칭"],
    )
    application_number = patent_item_value(
        item,
        ["applicationNumber", "applicationNo", "applNo", "applno", "출원번호"],
    )
    applicant = patent_item_value(
        item,
        ["applicantName", "applicant", "applicantNames", "출원인"],
    )
    application_date = patent_item_value(
        item,
        ["applicationDate", "filingDate", "openDate", "registrationDate", "출원일자"],
    )
    summary = patent_item_value(
        item,
        ["astrtCont", "abstract", "summary", "bibliographySummary", "초록"],
    )

    display_title = title or application_number or f"검색 결과 {index}"
    st.markdown(f"#### {index}. {display_title}")
    if application_number:
        st.write(f"출원번호: `{application_number}`")
    if applicant:
        st.write(f"출원인: {applicant}")
    if application_date:
        st.write(f"일자: {application_date}")
    if summary:
        st.write(summary[:500])

    with st.expander("원문 응답 필드"):
        st.json(item)


def render_result(case: dict[str, Any] | None) -> None:
    st.markdown('<div class="section-title">최종 결과</div>', unsafe_allow_html=True)
    if case is None:
        st.info("자료 입력 후 결과를 확인할 수 있습니다.")
        return

    st.markdown('<div class="document-preview">', unsafe_allow_html=True)
    st.markdown(case.get("document", ""))
    st.markdown("</div>", unsafe_allow_html=True)

    report = {
        "service": "AIVIO Bridge-Up",
        "generated_at": datetime.now().isoformat(timespec="minutes"),
        "case": case,
        "junior_progress": task_progress(case),
    }

    st.download_button(
        "문서 다운로드",
        data=case.get("document", ""),
        file_name="aivio_knowledge_document.md",
        mime="text/markdown",
        use_container_width=True,
    )
    st.download_button(
        "JSON 다운로드",
        data=json.dumps(report, ensure_ascii=False, indent=2),
        file_name="aivio_bridge_up_report.json",
        mime="application/json",
        use_container_width=True,
    )

    with st.expander("특허 예비 검토"):
        review = case.get("patent_review", {})
        st.markdown(f"### {review.get('readiness', '검토 필요')}")
        keywords = review.get("keywords", [])
        claims = review.get("claims", [])
        st.write(", ".join(keywords) if keywords else "추출된 키워드가 없습니다.")
        for claim in claims:
            st.write(f"- {claim}")
        if review.get("query"):
            st.code(review["query"], language="text")
        st.markdown(f"[KIPRIS에서 검색]({review.get('kipris_url', 'https://www.kipris.or.kr/')})")

        kipris_ready = bool(secret_value("KIPRISPLUS_API_KEY"))
        endpoint = kiprisplus_endpoint()
        query_param = kiprisplus_query_param(endpoint)
        if kipris_ready:
            st.success("KIPRISPlus API 키가 Secrets에 등록되어 있습니다.")
        else:
            st.info("KIPRISPlus 실시간 검색은 API 신청 후 Secrets에 키를 등록하면 연결할 수 있습니다.")

        if query_param == "applicationNumber":
            st.warning("현재 endpoint는 출원번호 조회형입니다. 업로드 자료 기반 검색에는 자유검색/항목별검색 endpoint와 `KIPRISPLUS_QUERY_PARAM = \"word\"` 설정이 필요합니다.")

        default_query = review.get("query") or " ".join(keywords[:6])
        patent_query = st.text_input("특허 검색어", value=default_query)

        if st.button("KIPRISPlus로 검색", disabled=not kipris_ready or not patent_query.strip(), use_container_width=True):
            with st.spinner("KIPRISPlus에서 선행기술 후보를 검색하고 있습니다."):
                try:
                    review["kiprisplus_results"] = call_kiprisplus_search(patent_query.strip(), limit=5)
                    st.success("검색이 완료되었습니다.")
                except Exception as exc:
                    review["kiprisplus_results"] = {
                        "error": str(exc),
                        "items": [],
                        "query": patent_query.strip(),
                    }
                    st.error(str(exc))

        results = review.get("kiprisplus_results")
        if results:
            if results.get("error"):
                st.warning(results["error"])
            else:
                st.caption(
                    f"검색어: {results.get('query', '')} · 파라미터: {results.get('query_param', '')} · 결과 {results.get('count', 0)}건"
                )
                for index, item in enumerate(results.get("items", [])[:5], start=1):
                    render_kiprisplus_item(item, index)
                if not results.get("items"):
                    st.info("표시할 검색 결과가 없습니다. 검색어 또는 API endpoint 상품을 확인해 주세요.")

    with st.expander("보안 확인"):
        st.write("- 실제 API 키는 코드나 GitHub 저장소에 저장하지 않습니다.")
        st.write("- 이 앱은 Streamlit Secrets 또는 환경변수에서만 키를 읽습니다.")
        st.write("- 업로드 원본은 세션 처리에만 사용하고, 리포트에는 파일명과 메타데이터만 남깁니다.")


def main() -> None:
    inject_style()
    ensure_state()
    render_hero()

    case = st.session_state.get("case")
    render_step_strip(case)
    selected_step = render_navigation(case)

    if selected_step == "capture":
        render_capture()
    elif selected_step == "draft":
        render_draft(st.session_state.get("case"))
    elif selected_step == "collab":
        render_collaboration(st.session_state.get("case"))
    else:
        render_result(st.session_state.get("case"))


if __name__ == "__main__":
    main()
