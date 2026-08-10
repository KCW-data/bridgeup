from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import streamlit as st


st.set_page_config(
    page_title="AIVIO Bridge-Up",
    page_icon="A",
    layout="wide",
    initial_sidebar_state="collapsed",
)


MAX_SAM_MEDIA_BYTES = 25 * 1024 * 1024
SAM_MEDIA_EXTENSIONS = {".flac", ".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".mov", ".ogg", ".wav", ".webm"}
SAM_BASE_URL = "https://sam.soonsoon.ai"

PIPELINE_STAGES = [
    ("collected", "자료 수집"),
    ("ai_drafted", "AI 초안"),
    ("junior_editing", "주니어 협업"),
    ("senior_review", "시니어 검수"),
    ("company_review", "기업 검수"),
    ("approved", "최종 승인"),
]
PIPELINE_LABELS = dict(PIPELINE_STAGES)
STATUS_OPTIONS = ["대기", "진행", "검수요청", "수정요청", "완료"]

DEFAULT_JUNIOR_TASKS = [
    {
        "id": "transcript-cleanup",
        "title": "STT 전사문 정리",
        "owner": "주니어",
        "status": "진행",
        "progress": 30,
        "evidence": "",
        "question": "",
    },
    {
        "id": "work-uniting",
        "title": "작업 단위 분리",
        "owner": "주니어",
        "status": "대기",
        "progress": 10,
        "evidence": "",
        "question": "",
    },
    {
        "id": "draft-making",
        "title": "결과물 초안 구성",
        "owner": "주니어",
        "status": "대기",
        "progress": 10,
        "evidence": "",
        "question": "",
    },
    {
        "id": "review-questions",
        "title": "시니어·기업 검수 질문 정리",
        "owner": "주니어",
        "status": "대기",
        "progress": 0,
        "evidence": "",
        "question": "",
    },
    {
        "id": "revision",
        "title": "검수 의견 반영",
        "owner": "주니어",
        "status": "대기",
        "progress": 0,
        "evidence": "",
        "question": "",
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
          --aivio-muted: #626b76;
          --aivio-line: #dfe4ea;
          --aivio-blue: #155eef;
          --aivio-green: #147d64;
          --aivio-amber: #b7791f;
        }

        .block-container {
          padding-top: 2.2rem;
          padding-bottom: 3rem;
        }

        .aivio-hero {
          border-bottom: 1px solid var(--aivio-line);
          margin-bottom: 1.4rem;
          padding-bottom: 1.2rem;
        }

        .aivio-kicker {
          color: var(--aivio-blue);
          font-size: 0.78rem;
          font-weight: 800;
          letter-spacing: 0;
          margin-bottom: 0.4rem;
          text-transform: uppercase;
        }

        .aivio-hero h1 {
          color: var(--aivio-text);
          font-size: clamp(2.1rem, 6vw, 4.4rem);
          line-height: 1.04;
          margin: 0 0 0.7rem;
        }

        .aivio-hero p {
          color: var(--aivio-muted);
          font-size: 1.05rem;
          line-height: 1.65;
          max-width: 860px;
        }

        .stage-strip {
          display: grid;
          grid-template-columns: repeat(6, minmax(0, 1fr));
          gap: 0.5rem;
          margin: 1rem 0 1.4rem;
        }

        .stage-pill {
          border: 1px solid var(--aivio-line);
          border-radius: 8px;
          background: #fff;
          color: var(--aivio-muted);
          padding: 0.55rem 0.65rem;
          text-align: center;
          font-size: 0.82rem;
          font-weight: 750;
        }

        .stage-pill.active {
          border-color: rgba(21, 94, 239, 0.5);
          color: var(--aivio-blue);
          background: #f4f7ff;
        }

        .status-chip {
          display: inline-block;
          border: 1px solid var(--aivio-line);
          border-radius: 8px;
          padding: 0.25rem 0.5rem;
          color: var(--aivio-muted);
          font-size: 0.8rem;
          font-weight: 700;
        }

        .status-chip.ready {
          border-color: rgba(20, 125, 100, 0.35);
          color: var(--aivio-green);
        }

        .status-chip.warn {
          border-color: rgba(183, 121, 31, 0.35);
          color: var(--aivio-amber);
        }

        .doc-box {
          border: 1px solid var(--aivio-line);
          border-radius: 8px;
          background: #fff;
          padding: 1rem;
        }

        .stTabs [data-baseweb="tab-list"] {
          gap: 0.4rem;
          overflow-x: auto;
        }

        .stTabs [data-baseweb="tab"] {
          border: 1px solid var(--aivio-line);
          border-radius: 8px;
          padding: 0.55rem 0.8rem;
          white-space: nowrap;
        }

        @media (max-width: 720px) {
          .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
          }

          .stage-strip {
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
    st.session_state.setdefault("materials", [])
    st.session_state.setdefault("approved", False)


def uploaded_file_meta(file: Any, source: str) -> dict[str, Any]:
    return {
        "name": getattr(file, "name", source) or source,
        "type": getattr(file, "type", "unknown") or "unknown",
        "size_mb": round((getattr(file, "size", 0) or 0) / (1024 * 1024), 2),
        "source": source,
    }


def media_type_counts(files: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"video": 0, "image": 0, "audio": 0, "document": 0, "other": 0}
    for item in files:
        mime = str(item.get("type", ""))
        name = str(item.get("name", "")).lower()
        if mime.startswith("video/") or name.endswith((".mp4", ".mov", ".webm")):
            counts["video"] += 1
        elif mime.startswith("image/"):
            counts["image"] += 1
        elif mime.startswith("audio/") or name.endswith((".mp3", ".m4a", ".wav", ".webm", ".ogg")):
            counts["audio"] += 1
        elif mime == "application/pdf" or name.endswith(".pdf"):
            counts["document"] += 1
        else:
            counts["other"] += 1
    return counts


def split_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []

    parts = re.split(r"(?<=[.!?。])\s+|(?:다\.|요\.|니다\.)\s*", normalized)
    cleaned = [part.strip(" .\n\t") for part in parts if len(part.strip()) >= 8]
    return cleaned[:10]


def infer_steps(text: str) -> list[str]:
    lines = [
        line.strip(" -0123456789.·")
        for line in text.splitlines()
        if len(line.strip()) >= 8
    ]
    if len(lines) >= 3:
        return lines[:7]

    sentences = split_sentences(text)
    if len(sentences) >= 3:
        return sentences[:7]

    return [
        "음성 또는 영상 전사문을 바탕으로 작업 전 준비 상태를 확인합니다.",
        "숙련자의 설명에서 반복되는 행동, 도구, 판단 기준을 분리합니다.",
        "정상/이상 상황과 실패 사례를 별도 항목으로 정리합니다.",
        "주니어가 따라 할 수 있는 작업 단위로 전환합니다.",
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


def transcribe_file(file: Any) -> tuple[str, str]:
    file_name = getattr(file, "name", "audio.wav") or "audio.wav"
    suffix = Path(file_name).suffix.lower() or ".wav"
    size = getattr(file, "size", 0) or 0

    if suffix not in SAM_MEDIA_EXTENSIONS:
        return "", f"{file_name}: SAM STT 미지원 형식입니다."

    if size > MAX_SAM_MEDIA_BYTES:
        return "", f"{file_name}: SAM API 처리 한도 25MB를 넘었습니다."

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
        return transcript, f"{file_name}: SAM STT 완료"
    except Exception as exc:
        return "", f"{file_name}: SAM STT 실패 - {exc}"


def transcribe_sources(files: list[Any]) -> tuple[str, list[str]]:
    transcripts: list[str] = []
    statuses: list[str] = []

    for file in files:
        text, status = transcribe_file(file)
        statuses.append(status)
        if text:
            transcripts.append(f"[{getattr(file, 'name', 'audio')}] {text}")

    return "\n\n".join(transcripts).strip(), statuses


def local_knowledge_bundle(title: str, industry: str, source_text: str, files: list[dict[str, Any]]) -> dict[str, Any]:
    steps = infer_steps(source_text)
    keywords = extract_keywords(source_text)
    field = industry or "현장 업무"
    file_summary = ", ".join(f"{item['source']}:{item['name']}" for item in files) or "미디어 없음"
    document = f"""# {title}

## 1. 노하우 개요
- 분야: {field}
- 수집 자료: {file_summary}
- 핵심 설명: {source_text[:360] if source_text else "SAM STT 또는 보완 메모가 필요합니다."}

## 2. 핵심 키워드
{", ".join(keywords) if keywords else "핵심 키워드가 아직 충분하지 않습니다."}

## 3. 작업 절차
{chr(10).join(f"{index}. {step}" for index, step in enumerate(steps, start=1))}

## 4. 주니어 협업 포인트
- 전사문에서 장비명과 현장 용어를 확인합니다.
- 작업 단위를 분리하고 누락된 질문을 정리합니다.
- 시니어와 기업이 검수할 항목을 따로 표시합니다.

## 5. 검수 유의사항
- 기업기밀, 개인정보, 영업비밀, 원본자료 권리를 확인합니다.
- AI 초안은 시니어와 기업 검수 전 확정본으로 사용하지 않습니다.
"""
    return {
        "document_markdown": document,
        "keywords": keywords,
        "claims": [f"{keyword} 기반 작업 판단 또는 전수 방법" for keyword in keywords[:5]],
        "junior_work_units": steps[:5],
        "review_questions": [
            "이 절차가 실제 작업 순서와 맞습니까?",
            "주니어가 독립적으로 수행하면 위험한 구간이 있습니까?",
            "기업 외부 공개가 제한되는 장면이나 용어가 있습니까?",
        ],
        "risk_notes": [
            "촬영 동의와 공개 범위를 확인해야 합니다.",
            "AI 초안의 현장 정확성은 시니어 검수 후 확정해야 합니다.",
        ],
    }


def sam_knowledge_bundle(title: str, industry: str, source_text: str, files: list[dict[str, Any]]) -> dict[str, Any]:
    fallback = local_knowledge_bundle(title, industry, source_text, files)
    if not secret_value("SAM_API_KEY") or not source_text.strip():
        return fallback

    prompt = {
        "title": title,
        "industry": industry,
        "source_text": source_text,
        "files": files,
        "required_json": {
            "document_markdown": "노하우 초안 Markdown",
            "keywords": ["검색/분류 키워드"],
            "claims": ["권리/IP 검토 후보 문장"],
            "junior_work_units": ["주니어가 정리하거나 제작할 작업 단위"],
            "review_questions": ["시니어와 기업에게 확인할 질문"],
            "risk_notes": ["권리, 보안, 공개 범위 관련 주의사항"],
        },
    }

    try:
        response = sam_generate(
            [
                {
                    "role": "system",
                    "content": "Bridge-Up 운영 MVP의 AI 지식화 에이전트입니다. 반드시 JSON 객체만 반환하세요.",
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
        "keywords": list(parsed.get("keywords") or fallback["keywords"]),
        "claims": list(parsed.get("claims") or fallback["claims"]),
        "junior_work_units": list(parsed.get("junior_work_units") or fallback["junior_work_units"]),
        "review_questions": list(parsed.get("review_questions") or fallback["review_questions"]),
        "risk_notes": list(parsed.get("risk_notes") or fallback["risk_notes"]),
    }


def build_junior_tasks(work_units: list[str]) -> list[dict[str, Any]]:
    tasks = [task.copy() for task in DEFAULT_JUNIOR_TASKS]
    for index, unit in enumerate(work_units[:4], start=1):
        tasks.append(
            {
                "id": f"unit-{index}",
                "title": f"작업 단위 검토: {unit[:32]}",
                "owner": "주니어",
                "status": "대기",
                "progress": 0,
                "evidence": "",
                "question": "",
            }
        )
    return tasks


def build_patent_review(document: str, keywords: list[str], claims: list[str]) -> dict[str, Any]:
    keywords = keywords or extract_keywords(document, 16)
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
            "운영 버전에서는 KIPRISPlus API로 발명의 명칭, 초록, 청구범위, IPC/CPC를 검색해 유사 문헌을 비교해야 합니다.",
        ],
    }


def build_material(
    project_context: dict[str, Any],
    consent_scope: str,
    files: list[dict[str, Any]],
    transcript: str,
    stt_status: list[str],
    memo: str,
) -> dict[str, Any]:
    title = str(project_context.get("title") or "현장 노하우")
    industry = str(project_context.get("industry") or "현장 업무")
    source_text = "\n".join(part for part in [transcript, memo] if part.strip())
    bundle = sam_knowledge_bundle(title, industry, source_text, files)
    document = str(bundle["document_markdown"])
    patent_review = build_patent_review(document, list(bundle["keywords"]), list(bundle["claims"]))
    counts = media_type_counts(files)
    junior_tasks = build_junior_tasks(list(bundle["junior_work_units"]))

    return {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "workflow_stage": "ai_drafted",
        "title": title,
        "industry": industry,
        "consent_scope": consent_scope,
        "project_context": project_context,
        "files": files,
        "transcript": transcript,
        "stt_status": stt_status,
        "memo": memo,
        "document": document,
        "patent_review": patent_review,
        "collaboration": {
            "junior_brief": "AI 초안을 기준으로 주니어가 작업 단위를 정리하고, 시니어·기업 검수 질문을 분리합니다.",
            "junior_tasks": junior_tasks,
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
        "senior_review": {
            "checks": {},
            "feedback": "",
            "approved": False,
        },
        "company_review": {
            "checks": {},
            "feedback": "",
            "approved": False,
        },
        "analysis": {
            "source_count": len(files),
            "media_counts": counts,
            "steps": infer_steps(source_text),
            "keywords": patent_review["keywords"],
            "summary": f"{industry} 자료를 SAM 기반으로 전사·초안화하고 주니어 협업 상태로 전환했습니다.",
        },
    }


def latest_material() -> dict[str, Any] | None:
    if not st.session_state["materials"]:
        return None
    return st.session_state["materials"][-1]


def stage_index(stage: str) -> int:
    keys = [key for key, _ in PIPELINE_STAGES]
    return keys.index(stage) if stage in keys else 0


def set_stage(material: dict[str, Any], stage: str, actor: str, event: str) -> None:
    material["workflow_stage"] = stage
    material.setdefault("collaboration", {}).setdefault("activity_log", []).append(
        {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "actor": actor,
            "event": event,
        }
    )


def task_progress(material: dict[str, Any] | None) -> int:
    if material is None:
        return 0
    tasks = material.get("collaboration", {}).get("junior_tasks", [])
    if not tasks:
        return 0
    return int(sum(int(task.get("progress", 0)) for task in tasks) / len(tasks))


def render_hero() -> None:
    st.markdown(
        """
        <div class="aivio-hero">
          <div class="aivio-kicker">AIVIO / Bridge-Up Streamlit MVP</div>
          <h1>AI 초안을 주니어 협업과 현장 검수로 완성합니다.</h1>
          <p>
            기업 과제와 시니어 노하우를 영상·음성·문서로 수집하고, SAM API가 만든 초안을
            주니어가 구조화한 뒤 시니어와 기업이 검수하는 관리형 프로젝트 흐름입니다.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_stage_strip(material: dict[str, Any] | None) -> None:
    active = stage_index(material.get("workflow_stage", "collected")) if material else -1
    html = ['<div class="stage-strip">']
    for index, (_, label) in enumerate(PIPELINE_STAGES):
        class_name = "stage-pill active" if index <= active else "stage-pill"
        html.append(f'<div class="{class_name}">{label}</div>')
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def render_status_cards(material: dict[str, Any] | None) -> None:
    count = 0 if material is None else int(material["analysis"]["source_count"])
    stage = "대기" if material is None else PIPELINE_LABELS.get(material.get("workflow_stage", ""), "대기")
    progress = task_progress(material)
    review_state = "완료" if material and material.get("workflow_stage") == "approved" else "진행"

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("입력 자료", count)
    col2.metric("현재 단계", stage)
    col3.metric("주니어 진행률", f"{progress}%")
    col4.metric("검수 상태", review_state if material else "대기")


def render_capture_tab() -> None:
    st.subheader("과제·노하우 등록")
    st.caption("기업 과제형과 시니어 노하우형을 같은 구조로 받고, 이후 주니어 협업과 검수 상태로 넘깁니다.")

    if secret_value("SAM_API_KEY"):
        st.markdown('<span class="status-chip ready">SAM_API_KEY 연결됨 · SAM 지식화 가능</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="status-chip warn">SAM_API_KEY 없음 · 로컬 초안만 생성</span>', unsafe_allow_html=True)

    type_col, meta_col = st.columns([0.72, 1.28], gap="large")
    with type_col:
        intake_type = st.radio("등록 유형", ["기업 과제형", "시니어 노하우형"], horizontal=False)
        consent_scope = st.selectbox(
            "공개 및 검수 범위",
            ["비공개 보관", "멘토 검수 허용", "주니어 학습 콘텐츠 활용 허용"],
        )
    with meta_col:
        title = st.text_input("과제/노하우 제목", placeholder="예: CNC 설비 이상 소리 판별 노하우")
        industry = st.text_input("분야", placeholder="제조, 품질, 물류, 교육")
        company_name = st.text_input("기업명", placeholder="실증 또는 과제 제시 기업")

    role_col1, role_col2, role_col3 = st.columns(3)
    senior_name = role_col1.text_input("시니어/숙련자", placeholder="검수자")
    junior_name = role_col2.text_input("주니어", placeholder="정리·제작 담당")
    company_reviewer = role_col3.text_input("기업 검수자", placeholder="현장 적용 검토")

    objective = st.text_area(
        "과제 목적",
        height=90,
        placeholder="기업이 해결하려는 문제, 시니어가 전수하려는 핵심 경험, 주니어가 만들어야 할 방향을 적어 주세요.",
    )
    acceptance_criteria = st.text_area(
        "완료 기준",
        height=80,
        placeholder="검수 기준, 현장 적용 기준, 공개 제한 조건을 간단히 적어 주세요.",
    )

    st.divider()
    audio_col, video_col, file_col = st.columns(3)
    with audio_col:
        st.markdown("#### 음성 녹음")
        recorded_audio = st.audio_input("현장 설명 녹음")
    with video_col:
        st.markdown("#### 영상 업로드")
        video_files = st.file_uploader(
            "작업 영상",
            type=["mp4", "webm", "mov"],
            accept_multiple_files=True,
        )
    with file_col:
        st.markdown("#### 음성·문서 업로드")
        extra_files = st.file_uploader(
            "음성, 이미지, PDF",
            type=["mp3", "m4a", "wav", "webm", "ogg", "jpg", "jpeg", "png", "webp", "pdf"],
            accept_multiple_files=True,
        )

    memo = st.text_area(
        "보완 메모",
        height=90,
        placeholder="STT가 놓치기 쉬운 장비명, 현장 용어, 금지 공개 정보만 짧게 적어 주세요.",
    )

    submitted = st.button("SAM 지식화 초안 생성", type="primary", use_container_width=True)
    if submitted:
        source_files: list[Any] = []
        file_meta: list[dict[str, Any]] = []

        if recorded_audio is not None:
            source_files.append(recorded_audio)
            file_meta.append(uploaded_file_meta(recorded_audio, "현장 음성 녹음"))

        for file in video_files or []:
            source_files.append(file)
            file_meta.append(uploaded_file_meta(file, "작업 영상"))

        for file in extra_files or []:
            file_meta.append(uploaded_file_meta(file, "추가 파일"))
            name = str(getattr(file, "name", "")).lower()
            mime = str(getattr(file, "type", ""))
            if mime.startswith("audio/") or name.endswith(tuple(SAM_MEDIA_EXTENSIONS)):
                source_files.append(file)

        if not title.strip():
            st.error("과제/노하우 제목은 필요합니다.")
            return

        if not source_files and not memo.strip() and not objective.strip():
            st.error("영상·음성 자료, 보완 메모, 과제 목적 중 하나는 필요합니다.")
            return

        project_context = {
            "intake_type": intake_type,
            "title": title,
            "industry": industry,
            "company_name": company_name,
            "senior_name": senior_name,
            "junior_name": junior_name,
            "company_reviewer": company_reviewer,
            "objective": objective,
            "acceptance_criteria": acceptance_criteria,
        }

        with st.spinner("SAM 기반 전사와 AI 초안 생성을 진행하고 있습니다."):
            transcript, statuses = transcribe_sources(source_files)
            material = build_material(project_context, consent_scope, file_meta, transcript, statuses, memo)

        st.session_state["materials"].append(material)
        st.session_state["approved"] = False
        st.success("AI 초안이 생성되었습니다. 주니어 협업 탭에서 작업을 이어가세요.")


def render_stt_tab(material: dict[str, Any] | None) -> None:
    st.subheader("자료 전사")
    if material is None:
        st.info("먼저 과제·노하우 등록 탭에서 자료를 등록해 주세요.")
        return

    for status in material.get("stt_status", []):
        if "완료" in status:
            st.success(status)
        else:
            st.warning(status)

    transcript = material.get("transcript", "")
    if transcript:
        material["transcript"] = st.text_area("전사문", value=transcript, height=320)
    else:
        st.info("전사문이 아직 없습니다. Streamlit secrets에 SAM_API_KEY를 등록하면 SAM 기반 전사가 실행됩니다.")

    if material.get("memo"):
        material["memo"] = st.text_area("보완 메모", value=material["memo"], height=110)


def render_ai_draft_tab(material: dict[str, Any] | None) -> None:
    st.subheader("AI 초안")
    if material is None:
        st.info("자료 등록 후 AI 초안이 생성됩니다.")
        return

    context = material.get("project_context", {})
    st.caption(f"{context.get('intake_type', '등록')} · {context.get('company_name') or '기업명 미입력'}")
    material["document"] = st.text_area("AI 초안", value=material["document"], height=430)

    col1, col2 = st.columns(2)
    if col1.button("주니어 협업 시작", type="primary", use_container_width=True):
        set_stage(material, "junior_editing", "운영자", "주니어 협업 시작")
        st.success("주니어 협업 단계로 전환했습니다.")
    if col2.button("AI 초안 재생성", use_container_width=True):
        source_text = "\n".join(part for part in [material.get("transcript", ""), material.get("memo", "")] if part.strip())
        bundle = sam_knowledge_bundle(material["title"], material["industry"], source_text, material.get("files", []))
        material["document"] = str(bundle["document_markdown"])
        material["patent_review"] = build_patent_review(material["document"], list(bundle["keywords"]), list(bundle["claims"]))
        material["collaboration"]["review_questions"] = list(bundle["review_questions"])
        material["collaboration"]["risk_notes"] = list(bundle["risk_notes"])
        set_stage(material, "ai_drafted", "AI", "AI 초안 재생성")
        st.success("AI 초안을 다시 생성했습니다.")


def render_junior_collaboration_tab(material: dict[str, Any] | None) -> None:
    st.subheader("주니어 협업")
    if material is None:
        st.info("AI 초안 생성 후 주니어 협업을 진행할 수 있습니다.")
        return

    collaboration = material.setdefault("collaboration", {})
    tasks = collaboration.setdefault("junior_tasks", [task.copy() for task in DEFAULT_JUNIOR_TASKS])
    context = material.get("project_context", {})

    col1, col2, col3 = st.columns(3)
    col1.metric("주니어", context.get("junior_name") or "미정")
    col2.metric("진행률", f"{task_progress(material)}%")
    col3.metric("현재 단계", PIPELINE_LABELS.get(material.get("workflow_stage", ""), "대기"))

    collaboration["junior_brief"] = st.text_area(
        "주니어 작업 브리프",
        value=collaboration.get("junior_brief", ""),
        height=100,
        placeholder="주니어가 AI 초안을 어떤 방향으로 정리·제작해야 하는지 적습니다.",
    )

    st.markdown("#### 작업 보드")
    for index, task in enumerate(tasks):
        with st.container(border=True):
            title_col, owner_col, status_col = st.columns([1.3, 0.7, 0.8])
            task["title"] = title_col.text_input("작업명", value=task.get("title", ""), key=f"junior-title-{index}")
            task["owner"] = owner_col.text_input("담당", value=task.get("owner", "주니어"), key=f"junior-owner-{index}")
            task["status"] = status_col.selectbox(
                "상태",
                STATUS_OPTIONS,
                index=STATUS_OPTIONS.index(task.get("status", "대기")) if task.get("status") in STATUS_OPTIONS else 0,
                key=f"junior-status-{index}",
            )
            task["progress"] = st.slider(
                "진행률",
                0,
                100,
                int(task.get("progress", 0)),
                5,
                key=f"junior-progress-{index}",
            )
            evidence_col, question_col = st.columns(2)
            task["evidence"] = evidence_col.text_area(
                "작업 메모/산출 링크",
                value=task.get("evidence", ""),
                height=80,
                key=f"junior-evidence-{index}",
            )
            task["question"] = question_col.text_area(
                "검수 질문",
                value=task.get("question", ""),
                height=80,
                key=f"junior-question-{index}",
            )

    add_col, review_col = st.columns(2)
    new_task = add_col.text_input("추가 작업", placeholder="필요한 주니어 작업을 추가")
    if add_col.button("작업 추가", use_container_width=True) and new_task.strip():
        tasks.append(
            {
                "id": f"custom-{len(tasks) + 1}",
                "title": new_task.strip(),
                "owner": context.get("junior_name") or "주니어",
                "status": "대기",
                "progress": 0,
                "evidence": "",
                "question": "",
            }
        )
        set_stage(material, "junior_editing", "주니어", "협업 작업 추가")
        st.success("작업을 추가했습니다.")

    if review_col.button("시니어 검수 요청", type="primary", use_container_width=True):
        for task in tasks:
            if task.get("status") == "진행":
                task["status"] = "검수요청"
        set_stage(material, "senior_review", "주니어", "시니어 검수 요청")
        st.success("시니어 검수 단계로 전환했습니다.")

    with st.expander("AI가 만든 검수 질문"):
        for question in collaboration.get("review_questions", []):
            st.write(f"- {question}")


def render_review_tab(material: dict[str, Any] | None) -> None:
    st.subheader("시니어·기업 검수")
    if material is None:
        st.info("주니어 협업 이후 검수를 진행할 수 있습니다.")
        return

    senior = material.setdefault("senior_review", {"checks": {}, "feedback": "", "approved": False})
    company = material.setdefault("company_review", {"checks": {}, "feedback": "", "approved": False})
    context = material.get("project_context", {})

    senior_items = [
        "전사문과 현장 용어가 맞다.",
        "작업 순서와 판단 기준이 현장과 맞다.",
        "주니어 작업 메모의 누락 질문을 확인했다.",
        "외부 공개 제한 정보가 표시되어 있다.",
    ]
    company_items = [
        "기업 과제 목적과 결과물 방향이 맞다.",
        "현장 적용 또는 내부 검토에 사용할 수 있다.",
        "개인정보·영업비밀·권리 범위를 확인했다.",
        "완료 기준과 수정 요청 사항이 정리되어 있다.",
    ]

    senior_col, company_col = st.columns(2, gap="large")
    with senior_col:
        st.markdown(f"#### 시니어 검수 · {context.get('senior_name') or '미정'}")
        senior_checks = senior.setdefault("checks", {})
        for index, item in enumerate(senior_items):
            senior_checks[item] = st.checkbox(
                item,
                value=bool(senior_checks.get(item, False)),
                key=f"senior-check-{index}",
            )
        senior["feedback"] = st.text_area("시니어 피드백", value=senior.get("feedback", ""), height=130)
        senior["approved"] = all(senior_checks.get(item, False) for item in senior_items)

    with company_col:
        st.markdown(f"#### 기업 검수 · {context.get('company_reviewer') or '미정'}")
        company_checks = company.setdefault("checks", {})
        for index, item in enumerate(company_items):
            company_checks[item] = st.checkbox(
                item,
                value=bool(company_checks.get(item, False)),
                key=f"company-check-{index}",
            )
        company["feedback"] = st.text_area("기업 피드백", value=company.get("feedback", ""), height=130)
        company["approved"] = all(company_checks.get(item, False) for item in company_items)

    request_col, company_col, approve_col = st.columns(3)
    if request_col.button("주니어 수정 요청", use_container_width=True):
        set_stage(material, "junior_editing", "검수자", "주니어 수정 요청")
        st.warning("주니어 협업 단계로 되돌렸습니다.")

    if company_col.button("기업 검수로 넘기기", disabled=not senior["approved"], use_container_width=True):
        set_stage(material, "company_review", "시니어", "기업 검수 요청")
        st.success("기업 검수 단계로 전환했습니다.")

    if approve_col.button("최종 승인", type="primary", disabled=not (senior["approved"] and company["approved"]), use_container_width=True):
        set_stage(material, "approved", "기업", "최종 승인")
        st.session_state["approved"] = True
        st.success("최종 승인되었습니다.")

    with st.expander("권리·보안 리스크"):
        for note in material.get("collaboration", {}).get("risk_notes", []):
            st.write(f"- {note}")


def render_patent_tab(material: dict[str, Any] | None) -> None:
    st.subheader("특허 등록 가능성 예비 검토")
    if material is None:
        st.info("노하우 문서가 생성되면 특허 검색 키워드와 예비 검토가 표시됩니다.")
        return

    review = material["patent_review"]
    col1, col2 = st.columns([0.7, 0.3], gap="large")
    with col1:
        st.markdown(f"### {review['readiness']}")
        st.write("이 단계는 자동 예비 검토입니다. 최종 등록 가능성은 변리사 또는 특허 전문가 검토가 필요합니다.")
    with col2:
        kipris_key_ready = bool(secret_value("KIPRISPLUS_API_KEY"))
        chip = "ready" if kipris_key_ready else "warn"
        label = "KIPRISPlus API 키 연결됨" if kipris_key_ready else "KIPRISPlus API 키 없음"
        st.markdown(f'<span class="status-chip {chip}">{label}</span>', unsafe_allow_html=True)

    st.markdown("#### 선행기술 검색 키워드")
    st.write(", ".join(review["keywords"]) if review["keywords"] else "추출된 키워드가 없습니다.")

    st.markdown("#### 청구항 후보 문장")
    for claim in review["claims"]:
        st.write(f"- {claim}")

    st.markdown("#### 검색 경로")
    st.write(f"- KIPRIS 검색: {review['kipris_url']}")
    st.write(f"- KIPRISPlus API 상품: {review['kipris_plus_url']}")
    st.code(review["query"] or "검색어 없음", language="text")


def render_report_tab(material: dict[str, Any] | None) -> None:
    st.subheader("운영 리포트")
    if material is None:
        st.info("자료 등록 후 리포트를 생성할 수 있습니다.")
        return

    report = {
        "service": "AIVIO Bridge-Up",
        "generated_at": datetime.now().isoformat(timespec="minutes"),
        "workflow_stage": material.get("workflow_stage"),
        "project_context": material.get("project_context"),
        "material": material,
        "junior_progress": task_progress(material),
    }

    st.markdown("#### 협업 요약")
    st.write(
        f"{material['industry']} 자료 {material['analysis']['source_count']}건을 기반으로 "
        f"현재 `{PIPELINE_LABELS.get(material.get('workflow_stage'), '대기')}` 단계입니다. "
        f"주니어 협업 진행률은 {task_progress(material)}%입니다."
    )

    log = material.get("collaboration", {}).get("activity_log", [])
    if log:
        st.markdown("#### 활동 기록")
        st.dataframe(log, use_container_width=True, hide_index=True)

    st.download_button(
        "JSON 리포트 다운로드",
        data=json.dumps(report, ensure_ascii=False, indent=2),
        file_name="aivio_bridge_up_report.json",
        mime="application/json",
        use_container_width=True,
    )

    with st.expander("Streamlit secrets 예시"):
        st.code(
            """
            SAM_API_KEY = "sam-..."
            SAM_MODEL = "claude-haiku"
            SAM_FALLBACK_MODELS = "gpt-5.4-mini"
            SAM_BASE_URL = "https://sam.soonsoon.ai"
            KIPRISPLUS_API_KEY = "발급받은 키"
            KIPRISPLUS_ENDPOINT = "신청 상품의 API endpoint"
            """.strip(),
            language="toml",
        )


def main() -> None:
    inject_style()
    ensure_state()
    render_hero()
    material = latest_material()
    render_stage_strip(material)
    render_status_cards(material)

    tabs = st.tabs(["등록·수집", "전사", "AI 초안", "주니어 협업", "검수", "특허 검토", "리포트"])
    with tabs[0]:
        render_capture_tab()
    with tabs[1]:
        render_stt_tab(latest_material())
    with tabs[2]:
        render_ai_draft_tab(latest_material())
    with tabs[3]:
        render_junior_collaboration_tab(latest_material())
    with tabs[4]:
        render_review_tab(latest_material())
    with tabs[5]:
        render_patent_tab(latest_material())
    with tabs[6]:
        render_report_tab(latest_material())


if __name__ == "__main__":
    main()
