from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import streamlit as st


st.set_page_config(
    page_title="AIVIO Bridge-Up",
    page_icon="A",
    layout="wide",
    initial_sidebar_state="collapsed",
)


CORE_STEPS = [
    "현장 자료 확인",
    "작업 단계 태깅",
    "SOP 초안 작성",
    "체크리스트 구성",
    "주니어 WBS 실행",
    "멘토 피드백 반영",
    "성과 리포트 작성",
]

DEFAULT_TASKS = [
    {"task": "자료 확인", "owner": "멘토", "status": "대기", "progress": 15},
    {"task": "작업 단계 태깅", "owner": "멘토", "status": "진행", "progress": 35},
    {"task": "체크리스트 실습", "owner": "주니어", "status": "대기", "progress": 20},
    {"task": "결과물 제출", "owner": "주니어", "status": "대기", "progress": 10},
]


def inject_style() -> None:
    st.markdown(
        """
        <style>
        :root {
          --aivio-bg: #f6f7f9;
          --aivio-text: #111318;
          --aivio-muted: #626b76;
          --aivio-line: #dfe4ea;
          --aivio-blue: #155eef;
          --aivio-green: #147d64;
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
          max-width: 760px;
        }

        .aivio-card {
          border: 1px solid var(--aivio-line);
          border-radius: 8px;
          background: #fff;
          padding: 1rem;
          min-height: 100%;
        }

        .aivio-card strong {
          display: block;
          margin-bottom: 0.35rem;
        }

        .aivio-card small {
          color: var(--aivio-muted);
          line-height: 1.5;
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
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def ensure_state() -> None:
    st.session_state.setdefault("materials", [])
    st.session_state.setdefault("tasks", DEFAULT_TASKS.copy())
    st.session_state.setdefault("mentor_notes", "")
    st.session_state.setdefault("approved", False)


def uploaded_file_meta(file: Any, source: str) -> dict[str, Any]:
    return {
        "name": getattr(file, "name", source),
        "type": getattr(file, "type", "unknown") or "unknown",
        "size_mb": round((getattr(file, "size", 0) or 0) / (1024 * 1024), 2),
        "source": source,
    }


def media_type_counts(files: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"video": 0, "image": 0, "audio": 0, "document": 0, "other": 0}
    for item in files:
        mime = str(item.get("type", ""))
        if mime.startswith("video/"):
            counts["video"] += 1
        elif mime.startswith("image/"):
            counts["image"] += 1
        elif mime.startswith("audio/"):
            counts["audio"] += 1
        elif mime == "application/pdf":
            counts["document"] += 1
        else:
            counts["other"] += 1
    return counts


def infer_steps(raw_text: str) -> list[str]:
    candidates = [
        line.strip(" -0123456789.·")
        for line in raw_text.splitlines()
        if line.strip()
    ]
    if len(candidates) >= 3:
        return candidates[:6]

    return [
        "작업 전 장비와 안전 상태를 확인합니다.",
        "핵심 작업 순서를 영상과 이미지 기준으로 나눕니다.",
        "정상/이상 판단 기준과 실패 사례를 분리합니다.",
        "주니어가 따라 할 수 있는 체크리스트로 정리합니다.",
    ]


def build_analysis(
    title: str,
    industry: str,
    raw_text: str,
    voice_text: str,
    media_files: list[dict[str, Any]],
    consent_scope: str,
) -> dict[str, Any]:
    counts = media_type_counts(media_files)
    steps = infer_steps(raw_text)
    source_count = len(media_files)
    field = industry or "현장 업무"

    summary = (
        f"{field} 숙련자의 작업 자료를 AI 지식화하여 "
        "멘토 검수형 학습 콘텐츠와 주니어 실행 WBS로 전환합니다."
    )

    risks = [
        "사람 얼굴, 고객 정보, 기업 기밀이 포함된 장면은 공개 전에 마스킹해야 합니다.",
        "AI가 분해한 작업 단계는 숙련자 또는 멘토의 사실 확인이 필요합니다.",
        "학습 콘텐츠 활용 범위는 촬영 동의와 공개 범위를 기준으로 제한합니다.",
    ]

    if consent_scope == "비공개 보관":
        risks.insert(0, "현재 공개 범위는 비공개이므로 멘토 검수와 학습 활용 전 별도 승인이 필요합니다.")

    return {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "title": title,
        "industry": field,
        "summary": summary,
        "source_count": source_count,
        "media_counts": counts,
        "voice_summary": voice_text.strip()[:500],
        "raw_context": raw_text.strip(),
        "steps": steps,
        "knowledge_assets": [
            "작업 단계별 SOP 초안",
            "현장 점검 체크리스트",
            "주의사항과 실패 사례 카드",
            "주니어 실습 퀴즈",
            "멘토 검수 요청 목록",
        ],
        "mentor_review": [
            "작업 단계 누락 여부 확인",
            "도구명, 장비명, 판단 기준 정확도 확인",
            "위험 장면과 공개 제한 사항 표시",
            "주니어에게 맡길 수 있는 실습 단위 확정",
        ],
        "wbs": CORE_STEPS,
        "risks": risks,
    }


def latest_material() -> dict[str, Any] | None:
    if not st.session_state["materials"]:
        return None
    return st.session_state["materials"][-1]


def render_hero() -> None:
    st.markdown(
        """
        <div class="aivio-hero">
          <div class="aivio-kicker">AIVIO / Bridge-Up Streamlit MVP</div>
          <h1>현장 영상을 지식으로, 지식을 주니어 실행으로.</h1>
          <p>
            모바일 촬영과 파일 업로드로 숙련자의 작업 자료를 수집하고,
            AI 지식화 초안, 멘토 검수, 주니어 WBS, 운영 리포트까지 한 번에 확인합니다.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_status_cards(material: dict[str, Any] | None) -> None:
    count = 0 if material is None else int(material["analysis"]["source_count"])
    approved = "승인 완료" if st.session_state["approved"] else "검수 전"
    progress = int(
        sum(task["progress"] for task in st.session_state["tasks"])
        / max(len(st.session_state["tasks"]), 1)
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("등록 자료", count)
    col2.metric("AI 지식화", "완료" if material else "대기")
    col3.metric("멘토 검수", approved)
    col4.metric("WBS 평균", f"{progress}%")


def render_capture_tab() -> None:
    st.subheader("현장 자료 수집")
    st.caption("모바일에서는 사진 촬영, 영상 선택/촬영, 기존 파일 업로드 흐름으로 사용할 수 있습니다.")

    col_main, col_side = st.columns([1.35, 0.65], gap="large")
    with col_main:
        title = st.text_input("자료 제목", placeholder="예: CNC 설비 일상 점검과 이상 소리 판별")
        industry = st.text_input("분야", placeholder="제조, 품질, 물류, 교육")
        raw_text = st.text_area(
            "작업 맥락과 판단 기준",
            height=180,
            placeholder="작업 목적, 단계, 정상/이상 판단 기준, 실패 사례, 주의사항을 적어 주세요.",
        )
        voice_text = st.text_area(
            "음성 설명 기록",
            height=110,
            placeholder="모바일 음성 입력으로 설명을 남기거나, STT 결과를 붙여 넣어 주세요.",
        )

    with col_side:
        consent_scope = st.selectbox(
            "공개 및 검수 범위",
            ["비공개 보관", "멘토 검수 허용", "주니어 학습 콘텐츠 활용 허용"],
        )
        st.markdown('<span class="status-chip">권장: 멘토 검수 후 학습 활용</span>', unsafe_allow_html=True)

    st.divider()
    photo_col, video_col, file_col = st.columns(3)
    with photo_col:
        st.markdown("#### 사진 촬영")
        captured_photo = st.camera_input("작업 장면 촬영", label_visibility="collapsed")
    with video_col:
        st.markdown("#### 영상 촬영")
        video_files = st.file_uploader(
            "작업 영상 선택",
            type=["mp4", "mov", "webm"],
            accept_multiple_files=True,
            label_visibility="collapsed",
        )
    with file_col:
        st.markdown("#### 파일 업로드")
        extra_files = st.file_uploader(
            "기존 자료 선택",
            type=["jpg", "jpeg", "png", "webp", "mp3", "m4a", "wav", "pdf"],
            accept_multiple_files=True,
            label_visibility="collapsed",
        )

    submitted = st.button("AI 지식화 초안 생성", type="primary", use_container_width=True)
    if submitted:
        files: list[dict[str, Any]] = []
        if captured_photo is not None:
            files.append(uploaded_file_meta(captured_photo, "사진 촬영"))
        files.extend(uploaded_file_meta(file, "영상 촬영/업로드") for file in video_files or [])
        files.extend(uploaded_file_meta(file, "파일 업로드") for file in extra_files or [])

        if not title.strip() or not raw_text.strip():
            st.error("자료 제목과 작업 맥락은 필수입니다.")
            return

        analysis = build_analysis(title, industry, raw_text, voice_text, files, consent_scope)
        st.session_state["materials"].append(
            {
                "title": title,
                "industry": industry,
                "consent_scope": consent_scope,
                "files": files,
                "analysis": analysis,
            }
        )
        st.session_state["approved"] = False
        st.success("AI 지식화 초안이 생성되었습니다. 상단의 AI 지식화 탭에서 확인하세요.")


def render_ai_tab(material: dict[str, Any] | None) -> None:
    st.subheader("AI 지식화 초안")
    if material is None:
        st.info("먼저 현장 수집 탭에서 자료를 등록해 주세요.")
        return

    analysis = material["analysis"]
    st.markdown(f"### {analysis['title']}")
    st.write(analysis["summary"])

    counts = analysis["media_counts"]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("영상", counts["video"])
    col2.metric("이미지", counts["image"])
    col3.metric("음성", counts["audio"])
    col4.metric("문서", counts["document"])

    step_col, asset_col = st.columns(2, gap="large")
    with step_col:
        st.markdown("#### 작업 단계")
        for index, step in enumerate(analysis["steps"], start=1):
            st.write(f"{index}. {step}")

    with asset_col:
        st.markdown("#### 생성할 학습 자산")
        for asset in analysis["knowledge_assets"]:
            st.write(f"- {asset}")

    if material["files"]:
        st.markdown("#### 등록 파일")
        st.dataframe(material["files"], use_container_width=True, hide_index=True)


def render_review_tab(material: dict[str, Any] | None) -> None:
    st.subheader("멘토 검수")
    if material is None:
        st.info("검수할 자료가 아직 없습니다.")
        return

    analysis = material["analysis"]
    st.markdown("#### 검수 체크리스트")
    checked = []
    for item in analysis["mentor_review"]:
        checked.append(st.checkbox(item, key=f"review-{item}"))

    st.session_state["mentor_notes"] = st.text_area(
        "멘토 수정 메모",
        value=st.session_state["mentor_notes"],
        height=140,
        placeholder="작업 단계 수정, 위험 장면, 공개 제한, 주니어 실습 범위를 기록하세요.",
    )

    if st.button("검수 승인", type="primary", disabled=not all(checked)):
        st.session_state["approved"] = True
        st.success("멘토 검수가 승인되었습니다.")

    with st.expander("리스크와 공개 범위 확인", expanded=True):
        for risk in analysis["risks"]:
            st.write(f"- {risk}")


def render_learning_tab(material: dict[str, Any] | None) -> None:
    st.subheader("주니어 학습 WBS")
    if material is None:
        st.info("AI 지식화 초안이 생성되면 WBS를 확인할 수 있습니다.")
        return

    for index, task in enumerate(st.session_state["tasks"]):
        with st.container(border=True):
            cols = st.columns([1.4, 0.7, 0.9])
            task["task"] = cols[0].text_input("작업", value=task["task"], key=f"task-name-{index}")
            task["owner"] = cols[1].selectbox(
                "담당",
                ["멘토", "주니어", "운영자"],
                index=["멘토", "주니어", "운영자"].index(task["owner"]),
                key=f"task-owner-{index}",
            )
            task["status"] = cols[2].selectbox(
                "상태",
                ["대기", "진행", "완료"],
                index=["대기", "진행", "완료"].index(task["status"]),
                key=f"task-status-{index}",
            )
            task["progress"] = st.slider(
                "진행률",
                min_value=0,
                max_value=100,
                value=int(task["progress"]),
                step=5,
                key=f"task-progress-{index}",
            )

    avg = int(
        sum(task["progress"] for task in st.session_state["tasks"])
        / max(len(st.session_state["tasks"]), 1)
    )
    st.progress(avg / 100, text=f"전체 진행률 {avg}%")


def render_report_tab(material: dict[str, Any] | None) -> None:
    st.subheader("운영 리포트")
    if material is None:
        st.info("자료 등록 후 리포트를 생성할 수 있습니다.")
        return

    analysis = material["analysis"]
    progress = int(
        sum(task["progress"] for task in st.session_state["tasks"])
        / max(len(st.session_state["tasks"]), 1)
    )
    report = {
        "service": "AIVIO Bridge-Up",
        "generated_at": datetime.now().isoformat(timespec="minutes"),
        "material": material,
        "mentor_notes": st.session_state["mentor_notes"],
        "approved": st.session_state["approved"],
        "wbs_tasks": st.session_state["tasks"],
        "progress": progress,
    }

    st.markdown("#### 기업·운영자 요약")
    st.write(
        f"{analysis['industry']} 자료 {analysis['source_count']}건을 기반으로 "
        f"작업 단계 {len(analysis['steps'])}개와 학습 자산 {len(analysis['knowledge_assets'])}개를 도출했습니다. "
        f"현재 WBS 평균 진행률은 {progress}%입니다."
    )

    st.download_button(
        "JSON 리포트 다운로드",
        data=json.dumps(report, ensure_ascii=False, indent=2),
        file_name="aivio_bridge_up_report.json",
        mime="application/json",
        use_container_width=True,
    )

    with st.expander("Streamlit Community Cloud 배포 메모"):
        st.code(
            """
            1. GitHub 저장소에 aivio 폴더를 올립니다.
            2. Streamlit Community Cloud에서 New app을 선택합니다.
            3. Main file path를 aivio/streamlit_app.py로 지정합니다.
            4. Python dependencies는 aivio/requirements.txt가 자동으로 설치됩니다.
            """.strip(),
            language="text",
        )


def main() -> None:
    inject_style()
    ensure_state()
    render_hero()
    material = latest_material()
    render_status_cards(material)

    tabs = st.tabs(["현장 수집", "AI 지식화", "멘토 검수", "주니어 학습", "운영 리포트"])
    with tabs[0]:
        render_capture_tab()
    with tabs[1]:
        render_ai_tab(latest_material())
    with tabs[2]:
        render_review_tab(latest_material())
    with tabs[3]:
        render_learning_tab(latest_material())
    with tabs[4]:
        render_report_tab(latest_material())


if __name__ == "__main__":
    main()
