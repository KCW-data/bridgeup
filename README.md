# AIVIO / Bridge-Up MVP

숙련자의 작업 영상, 음성 설명, 사진, 문서화된 작업표준을 수집하고 STT 기반 노하우 문서화, 주니어 협업, 시니어·기업 검수, 특허 선행기술 예비 검토로 연결하는 MVP입니다.

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

1. 시니어·멘토가 현장 영상, 음성 녹음, 기존 음성 파일, 사진, PDF 문서를 등록합니다.
2. 영상·음성 자료를 STT로 전사해 작업 설명 텍스트를 생성합니다.
3. 전사문을 기반으로 작업 절차, 판단 기준, 주의사항, 체크리스트를 노하우 문서로 정리합니다.
4. 주니어가 전사문, 작업 순서, 검수 질문을 확인합니다.
5. 시니어와 기업이 현장 정확성, 공개 범위, 보안 정보를 검수합니다.
6. 노하우 문서에서 특허 검색 키워드와 청구항 후보 문장을 추출합니다.

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

Streamlit 버전은 서버 DB 없이 세션 기반으로 동작합니다. 업로드 원본은 전사·분석 처리에만 사용하고, 다운로드 리포트에는 파일명과 메타데이터만 남깁니다. GitHub에는 `app.py`, `streamlit_app.py`, `requirements.txt`, `.streamlit/config.toml`을 함께 올려야 합니다.

화면은 시니어 사용자를 기준으로 4단계만 보이도록 구성했습니다.

1. 입력
2. AI 정리
3. 협업 검수
4. 결과

### Streamlit secrets

STT와 AI 지식화를 실제로 실행하려면 Streamlit Community Cloud의 Secrets에 아래 값을 등록합니다. 실제 API 키는 코드, README, GitHub 저장소, `.streamlit/secrets.example.toml`에 넣지 않습니다.

```toml
SAM_API_KEY = "sam-..."
SAM_MODEL = "claude-haiku"
SAM_FALLBACK_MODELS = "gpt-5.4-mini"
SAM_BASE_URL = "https://sam.soonsoon.ai"
```

특허 검색을 자동화하려면 KIPRISPlus에서 Open API 상품을 신청한 뒤 발급 정보를 Streamlit Cloud Secrets에 추가합니다. API 키는 `마이페이지 > API KEY > REST AccessKey`에서 확인하고, endpoint는 신청한 상품의 설명 페이지 또는 API 통합설명서의 REST 호출 URL에서 확인합니다.

```toml
KIPRISPLUS_API_KEY = "발급받은 키"
KIPRISPLUS_ENDPOINT = "신청한 검색 상품의 REST 호출 URL"
KIPRISPLUS_QUERY_PARAM = "word"
KIPRISPLUS_EXTRA_PARAMS = '{"pageNo":"1","numOfRows":"5"}'
```

첨부 샘플의 `getBibliographySumryInfoSearch`는 이미 알고 있는 출원번호로 서지요약을 조회하는 예시입니다. 사용자가 업로드한 영상·음성에서 추출한 키워드로 선행기술을 검색하려면 자유검색 또는 항목별검색 endpoint를 사용하고 `KIPRISPLUS_QUERY_PARAM`을 해당 상품의 검색어 파라미터명으로 맞춰야 합니다. 상품 설명에 나온 파라미터명이 `word`가 아니면 이 값도 함께 바꿉니다.

현재 Streamlit MVP는 SAM 기반 STT, AI 초안 생성, 주니어 협업 체크리스트, 시니어·기업 검수, 특허 검색 키워드·청구항 후보 생성, KIPRISPlus 검색 결과 후보 표시까지 구현되어 있습니다.
