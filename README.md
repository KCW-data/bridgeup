# AIVIO / Bridge-Up MVP

숙련자의 작업 영상, 음성 설명, 단계별 이미지, 문서화된 작업표준을 수집하고 STT 기반 노하우 문서화, 특허 선행기술 검색, 멘토 검수를 거쳐 주니어 학습·실행 프로젝트로 연결하는 MVP입니다.

이 저장소에는 두 가지 실행 방식이 있습니다.

- `html/bridge-up/` 기반 PHP MVP
- `streamlit_app.py` 기반 Streamlit Community Cloud MVP

## 구조

```txt
app/        서버 사이드 PHP 코드
html/       Apache 웹루트
storage/    로그와 업로드 보관 위치
docs/       운영 체크리스트
.streamlit/ Streamlit 테마와 업로드 설정
streamlit_app.py Streamlit 실행 파일
requirements.txt Streamlit Cloud 의존성
```

## 핵심 흐름

1. 시니어·멘토가 현장 영상, 음성 녹음, 기존 음성 파일, 이미지, PDF 문서를 등록합니다.
2. 영상·음성 자료를 STT로 전사해 작업 설명 텍스트를 생성합니다.
3. 전사문을 기반으로 작업 절차, 판단 기준, 주의사항, 체크리스트를 노하우 문서로 정리합니다.
4. 노하우 문서에서 특허 검색 키워드와 청구항 후보 문장을 추출합니다.
5. KIPRISPlus API 또는 수동 KIPRIS 검색으로 선행기술을 확인하고 등록 가능성 예비 검토를 제공합니다.
6. 멘토 검수 후 주니어 학습 WBS와 운영 리포트로 전환합니다.

## PHP 설치

1. Apache 웹루트를 `html/`로 지정합니다.
2. MySQL DB를 준비합니다.
3. `app/Config/config.local.example.php`를 `app/Config/config.local.php`로 복사한 뒤 실제 DB 정보와 Gemini API Key를 입력합니다.
4. PHP 운영 서버에는 `app/`, `storage/`, `html/bridge-up/`가 필요합니다.

## `/bridge-up/` 하위 경로 배포

`https://www.aivio.kr/bridge-up/`로 접속해야 하는 경우 `html/bridge-up/` 폴더도 서버의 동일 경로에 업로드합니다. 이 폴더에는 하위 경로용 `index.php`, `.htaccess`, `assets/`가 포함되어 있어 Apache 403 디렉터리 접근 오류를 피하고 `/bridge-up/login` 같은 라우트도 정상 처리합니다.

## 데모 계정

데모 seed 데이터를 별도로 입력한 경우:

- 시니어: `senior@example.com`
- 주니어: `junior@example.com`
- 비밀번호: `password`

운영 환경에서는 seed 계정을 삭제하거나 즉시 비밀번호를 변경해야 합니다.

## Streamlit Community Cloud 실행

GitHub 저장소에 이 폴더를 올린 뒤 Streamlit Community Cloud에서 새 앱을 만들고 아래처럼 지정합니다.

```txt
Main file path: app.py
```

저장소 루트가 `모두의창업`이고 그 안에 `aivio/` 폴더가 있는 구조로 올리는 경우에는 아래처럼 지정합니다.

```txt
Main file path: aivio/app.py
```

로컬에서 확인할 때는 다음 명령을 사용합니다.

```bash
pip install -r requirements.txt
streamlit run app.py
```

Streamlit 버전은 서버 DB 없이 세션 기반으로 동작합니다. 업로드 파일은 분석 메타데이터와 리포트 생성에 사용되며, 결과는 JSON으로 다운로드할 수 있습니다.

### Streamlit secrets

STT와 AI 지식화를 실제로 실행하려면 Streamlit Community Cloud의 Secrets에 아래 값을 등록합니다.

```toml
SAM_API_KEY = "sam-..."
SAM_MODEL = "claude-haiku"
SAM_FALLBACK_MODELS = "gpt-5.4-mini"
SAM_BASE_URL = "https://sam.soonsoon.ai"
```

특허 검색을 자동화하려면 KIPRISPlus에서 Open API 상품을 신청한 뒤 발급 정보를 추가합니다.

```toml
KIPRISPLUS_API_KEY = "발급받은 키"
KIPRISPLUS_ENDPOINT = "신청 상품의 API endpoint"
```

현재 Streamlit MVP는 SAM 기반 STT, AI 초안 생성, 주니어 협업 보드, 시니어·기업 검수, 특허 검색 키워드·청구항 후보 생성까지 구현되어 있습니다. KIPRISPlus 실시간 검색은 API 신청 후 endpoint와 응답 형식에 맞춰 연결하면 됩니다.
