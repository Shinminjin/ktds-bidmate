# 📋 KT DS 제안서 도우미 (BidMate)

AI 기반으로 과업지시서를 분석하고, 유사 프로젝트 및 솔루션 정보를 자동 검색하여 전략적 제안서 초안을 생성해주는 시스템

> Azure OpenAI, Azure AI Search, Streamlit을 활용한 엔드투엔드 자동화 데모

---

## ✅ 주요 기능

- 📄 과업지시서 분석 (PDF / 텍스트 입력)
- 🔍 Azure AI Search 기반 유사 사례 검색
- 🧠 GPT 기반 제안서 초안 자동 생성
- 💻 Streamlit UI 기반 인터페이스
- 📝 수정 및 다운로드 (TXT / Markdown)

---

## 🏗️ 아키텍처 개요

```
과업지시서 입력
      ↓
텍스트 추출 및 GPT 요약
      ↓
임베딩 생성 (text-embedding-3-small)
      ↓
Azure AI Search (프로젝트/솔루션 검색)
      ↓
GPT 제안서 생성 (gpt-4.1-mini)
      ↓
Streamlit UI 출력 및 수정/다운로드
```

---

## ⚙️ 사용 기술

| 항목       | 스택                                |
|------------|-------------------------------------|
| LLM        | Azure OpenAI (gpt-4.1-mini)         |
| 임베딩     | Azure OpenAI (text-embedding-3-small) |
| 검색엔진   | Azure AI Search (벡터 검색)         |
| 프론트엔드 | Streamlit                           |
| 기타       | dotenv, PyMuPDF, requests, JSON     |

---

## 🧹 전처리 (Preprocessing) 단계

GPT 임베딩 및 요약을 위한 전처리 데이터 생성 단계입니다. 아래 순서대로 Poetry 가상환경에서 스크립트를 실행하세요:

---

### ✅ 1. 프로젝트 이력 CSV → JSON 변환

```bash
poetry run python generate_json_history.py
```

- 입력: `data/history_csv/project_history.csv`
- 출력: `data/preprocess_results/project_history.json`

---

### ✅ 2. 프로젝트 이력 Embedding 생성

```bash
poetry run python generate_enriched_history.py
```

- 입력: `data/preprocess_results/project_history.json`
- 출력: `data/preprocess_results/enriched_project_history.json`

---

### ✅ 3. 솔루션 PDF 요약 + Embedding 생성

```bash
poetry run python generate_enriched_solution.py
```

- 입력:
  - JSON: `data/solution_json/solution.json`
  - PDF: `data/solution_pdf/*.pdf`
- 출력: `data/preprocess_results/enriched_solution.json`

---

> 최종 생성된 enriched JSON 파일들을 Azure AI Search에 업로드합니다.

---

## 🗂️ 데이터 업로드 (Azure AI Search)

Azure 포털에서 `project-history-index`, `solution-embedding-index`를 생성한 뒤, 아래 스크립트로 업로드하세요:

---

### 1. 프로젝트 이력 업로드

```bash
poetry run python index/upload_history_data.py
```

- 대상 인덱스: `project-history-index`
- 입력 파일: `data/preprocess_results/enriched_project_history.json`

> ✅ 성공 메시지: `모든 프로젝트 이력 데이터 업로드 완료!`

---

### 2. 솔루션 정보 업로드

```bash
poetry run python index/upload_solution_data.py
```

- 대상 인덱스: `solution-embedding-index`
- 입력 파일: `data/preprocess_results/enriched_solution.json`

> ✅ 성공 메시지: `모든 솔루션 정보 업로드 완료!`

---

## 📁 데이터 인덱스 구조

### 1. `project-history-index`
- `project_name`, `department`, `summary_text`, `embedding`

### 2. `solution-embedding-index`
- `name`, `description`, `pdf_summary`, `embedding`

> ✅ 모든 데이터는 Azure AI Search에 사전 인덱싱되어야 검색이 가능합니다

---

## 🚀 실행 방법

### 1. Poetry 설치 (최초 1회만)

```bash
# macOS / Linux
curl -sSL https://install.python-poetry.org | python3 -

# Windows (PowerShell)
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
```

> 설치 후 아래 명령으로 정상 설치 여부 확인:
```bash
poetry --version
```

---

### 2. 프로젝트 클론 및 종속성 설치

```bash
git clone https://github.com/your-repo/ktds-bidmate.git
cd ktds-bidmate
poetry install
```

---

### 3. 환경 변수 설정

`.env.sample` 파일을 참고하여 `.env` 파일을 생성 후 다음 정보 입력:

```dotenv
OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
OPENAI_API_KEY="your_openai_key"
OPENAI_EMBEDDING_DEPLOYMENT="text-embedding-3-small"
OPENAI_CHAT_DEPLOYMENT="gpt-4.1-mini"
OPENAI_API_VERSION="2023-05-15"

SEARCH_ENDPOINT="https://your-search.search.windows.net"
SEARCH_ADMIN_KEY="your_search_key"
```

---

### 4. 앱 실행

```bash
poetry run streamlit run rag/app.py
```

---

## ☁️ 배포 가이드 (VSCode Azure AppService 확장 사용)

1. VSCode에서 `Azure App Service` 확장 설치  
2. 좌측 Azure 아이콘 클릭 → 대상 App Service 선택  
3. 루트 폴더 우클릭 → **Deploy to Web App**  
4. `.streamlit.sh` 포함된 전체 프로젝트 디렉토리 업로드  
5. Azure Portal → App Service → 구성 → **일반 설정 > 시작 명령** 입력:

```bash
bash /home/site/wwwroot/streamlit.sh
```

---

## 📈 향후 확장 계획

### 🧠 제안 품질 자동 점검 기능 도입
- 문장 품질, 중복률, 맞춤법, 설득력 등을 AI 기반 자동 평가  
- 품질 피드백 루프 통한 제안서 완성도 향상

### 📡 나라장터 공고 API 연동
- 실시간 신규 입찰 공고 수집 → 과업지시서 자동 파싱  
- 공고 → 분석 → 제안서 초안 생성까지 전자동 흐름 구축

### 🎯 프로젝트 자동 선별 및 추천 고도화
- 기술 요건 기반 유사도 + 임팩트 기반 유사 프로젝트 자동 추천  
- 최적 이력 자동 매칭 알고리즘으로 제안 경쟁력 강화

---
## 🎬 실행화면

![실행 화면](https://github.com/user-attachments/assets/ddc22a3d-9fab-44c7-ba5f-b6a414bc67c7)

📽️ [실행 영상 보기 (Google Drive)](https://drive.google.com/file/d/1hdNHW0yV8ub8lIugCo15ajA4lZEoDZr1/view?usp=sharing)

