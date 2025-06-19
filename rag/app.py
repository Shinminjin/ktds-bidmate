import streamlit as st
import os
import json
import requests
import PyPDF2
import fitz  # PyMuPDF
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from openai import AzureOpenAI
import time
import io

# ✅ Streamlit 페이지 설정
st.set_page_config(
    page_title="KT DS 제안서 도우미",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ✅ 커스텀 CSS
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #4a90e2 0%, #357abd 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    .feature-card {
        background: white;
        padding: 1.5rem;
        border-radius: 8px;
        border: 1px solid #e1e5e9;
        border-left: 4px solid #4a90e2;
        margin: 0.8rem 0;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
        transition: box-shadow 0.2s ease;
    }
    
    .feature-card:hover {
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
    }
    
    .success-box {
        background: linear-gradient(90deg, #28a745 0%, #20c997 100%);
        padding: 1rem;
        border-radius: 8px;
        color: white;
        margin: 1rem 0;
    }
    
    .warning-box {
        background: linear-gradient(90deg, #dc3545 0%, #fd7e14 100%);
        padding: 1rem;
        border-radius: 8px;
        color: white;
        margin: 1rem 0;
    }
    
    .info-box {
        background: #f1f3f4;
        border: 1px solid #9aa0a6;
        border-left: 4px solid #4a90e2;
        padding: 1rem 1.5rem;
        border-radius: 6px;
        color: #3c4043;
        margin: 1rem 0;
    }
    
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        border: 1px solid #e0e0e0;
    }
    
    .stProgress .st-bo {
        background-color: #4a90e2;
    }
    
    .proposal-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        text-align: center;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3);
    }
    
    .completion-box {
        background: linear-gradient(90deg, #28a745 0%, #20c997 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        margin: 2rem 0;
        text-align: center;
    }
    
    .ready-box {
        background: #f8f9fa;
        border: 2px dashed #6c757d;
        border-radius: 10px;
        padding: 2rem;
        text-align: center;
        margin: 2rem 0;
    }
    
    .warning-analysis-box {
        background: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 8px;
        padding: 1.5rem;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# ✅ 환경 변수 로드
if os.path.exists('.env'):
    load_dotenv(override=True)

# ✅ Azure Search 설정
SEARCH_ENDPOINT = os.getenv("SEARCH_ENDPOINT")
SEARCH_KEY = os.getenv("SEARCH_ADMIN_KEY")
API_VERSION = "2023-10-01-Preview"
HEADERS = {
    "Content-Type": "application/json",
    "api-key": SEARCH_KEY
}

# ✅ Azure OpenAI 설정
@st.cache_resource
def get_openai_client():
    return AzureOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        api_version=os.getenv("OPENAI_API_VERSION"),
        azure_endpoint=os.getenv("OPENAI_ENDPOINT")
    )

client = get_openai_client()
embedding_model = os.getenv("OPENAI_EMBEDDING_DEPLOYMENT")
chat_model = os.getenv("OPENAI_CHAT_DEPLOYMENT")

# ✅ 세션 상태 초기화
def init_session_state():
    if 'analysis_result' not in st.session_state:
        st.session_state.analysis_result = None
    if 'projects_result' not in st.session_state:
        st.session_state.projects_result = None
    if 'solutions_result' not in st.session_state:
        st.session_state.solutions_result = None
    if 'proposal_content' not in st.session_state:
        st.session_state.proposal_content = None
    if 'edit_mode' not in st.session_state:
        st.session_state.edit_mode = False

class TaskOrderProcessor:
    def __init__(self):
        self.client = client
        self.embedding_model = embedding_model
        self.chat_model = chat_model
    
    def extract_text_from_pdf(self, pdf_file):
        """PDF에서 텍스트 추출"""
        try:
            # PyMuPDF로 시도
            pdf_bytes = pdf_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            text = ""
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text += page.get_text() + "\n"
            
            doc.close()
            
            if text.strip():
                return text
            
            # PyPDF2로 재시도
            pdf_file.seek(0)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = ""
            
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            
            return text
            
        except Exception as e:
            st.error(f"PDF 텍스트 추출 실패: {str(e)}")
            return None
    
    def analyze_task_order(self, document_text):
        """과업지시서 분석"""
        prompt = f"""
다음은 과업지시서입니다. 제안서 작성에 필요한 모든 핵심 정보를 JSON으로 추출해주세요.

중요 지침:
- HTML 태그(예: <br>, <div> 등)는 제거하고 순수 텍스트만 추출
- 관리자 정보는 이름만 추출 (연락처, 이메일 등 JSON 형태 제외)
- 모든 텍스트는 읽기 쉬운 형태로 정리
- 불필요한 기호나 태그는 모두 제거

과업지시서 내용:
{document_text[:5000]}

JSON 형식:
{{
    "project_info": {{
        "project_title": "과업명/프로젝트명",
        "client_organization": "발주처/고객사",
        "project_period": "과업기간",
        "project_budget": "과업예산",
        "project_manager": "과업관리자 이름만",
        "delivery_location": "결과물 납품장소"
    }},
    "objectives": {{
        "main_purpose": "과업의 주요 목적",
        "expected_outcomes": ["기대성과1", "기대성과2"],
        "success_criteria": ["성공기준1", "성공기준2"]
    }},
    "scope_of_work": {{
        "main_tasks": ["주요업무1", "주요업무2"],
        "detailed_activities": ["세부활동1", "세부활동2"],
        "exclusions": ["제외사항1", "제외사항2"]
    }},
    "technical_requirements": {{
        "technologies": ["기술요구사항1", "기술요구사항2"],
        "platforms": ["플랫폼1", "플랫폼2"],
        "standards": ["표준/규격1", "표준/규격2"],
        "security_requirements": ["보안요구사항1", "보안요구사항2"]
    }},
    "deliverables": {{
        "documents": ["문서산출물1", "문서산출물2"],
        "systems": ["시스템산출물1", "시스템산출물2"],
        "reports": ["보고서1", "보고서2"]
    }},
    "timeline": {{
        "phases": ["단계1", "단계2"],
        "milestones": ["마일스톤1", "마일스톤2"],
        "key_dates": ["주요일정1", "주요일정2"]
    }},
    "resources": {{
        "required_roles": ["필요역할1", "필요역할2"],
        "skill_requirements": ["필요기술1", "필요기술2"],
        "equipment_needs": ["필요장비1", "필요장비2"]
    }}
}}
"""
        
        response = self.client.chat.completions.create(
            model=self.chat_model,
            messages=[
                {"role": "system", "content": "과업지시서 분석 전문가. 제안서 작성에 필요한 정보를 체계적으로 추출하며, HTML 태그나 불필요한 기호는 모두 제거하고 깔끔한 텍스트만 추출합니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.05,
            max_tokens=2500
        )
        
        try:
            result = json.loads(response.choices[0].message.content)
            # 데이터 정제 함수 적용
            return self.clean_analysis_data(result)
        except:
            return {"error": "분석 실패"}
    
    def clean_analysis_data(self, data):
        """분석 데이터 정제"""
        import re
        
        def clean_text(text):
            if isinstance(text, str):
                # HTML 태그 제거
                text = re.sub(r'<[^>]+>', '', text)
                # 연속된 공백을 하나로
                text = re.sub(r'\s+', ' ', text)
                # 앞뒤 공백 제거
                text = text.strip()
                # JSON 형태나 이상한 문자열 감지
                if text.startswith('{') or text.startswith('[') or 'department' in text.lower():
                    return "확인 필요"
            return text
        
        def clean_list(items):
            if isinstance(items, list):
                return [clean_text(item) for item in items if item and clean_text(item) != "확인 필요"]
            return items
        
        def clean_dict(d):
            if isinstance(d, dict):
                cleaned = {}
                for key, value in d.items():
                    if isinstance(value, dict):
                        cleaned[key] = clean_dict(value)
                    elif isinstance(value, list):
                        cleaned[key] = clean_list(value)
                    elif isinstance(value, str):
                        cleaned_value = clean_text(value)
                        if cleaned_value and cleaned_value != "확인 필요":
                            cleaned[key] = cleaned_value
                    else:
                        cleaned[key] = value
                return cleaned
            return d
        
        return clean_dict(data)
    
    def get_embedding(self, text):
        """임베딩 생성"""
        response = self.client.embeddings.create(
            model=self.embedding_model,
            input=text
        )
        return response.data[0].embedding
    
    def search_projects(self, query_embedding, top_k=6):
        """프로젝트 검색"""
        url = f"{SEARCH_ENDPOINT}/indexes/project-history-index/docs/search?api-version={API_VERSION}"
        
        search_body = {
            "search": "*",
            "vectorQueries": [
                {
                    "kind": "vector",
                    "vector": query_embedding,
                    "fields": "embedding",
                    "k": top_k
                }
            ]
        }
        
        try:
            response = requests.post(url, headers=HEADERS, json=search_body)
            response.raise_for_status()
            return response.json().get("value", [])
        except Exception as e:
            st.error(f"프로젝트 검색 실패: {str(e)}")
            return []
    
    def search_solutions(self, query_embedding, top_k=5):
        """솔루션 검색"""
        url = f"{SEARCH_ENDPOINT}/indexes/solution-embedding-index/docs/search?api-version={API_VERSION}"
        
        search_body = {
            "search": "*",
            "vectorQueries": [
                {
                    "kind": "vector",
                    "vector": query_embedding,
                    "fields": "embedding",
                    "k": top_k
                }
            ]
        }
        
        try:
            response = requests.post(url, headers=HEADERS, json=search_body)
            response.raise_for_status()
            return response.json().get("value", [])
        except Exception as e:
            st.error(f"솔루션 검색 실패: {str(e)}")
            return []
    
    def generate_proposal(self, analysis, projects, solutions):
        """최적화된 제안서 생성"""
        
        project_info = analysis.get('project_info', {})
        objectives = analysis.get('objectives', {})
        scope_of_work = analysis.get('scope_of_work', {})
        technical_requirements = analysis.get('technical_requirements', {})
        deliverables = analysis.get('deliverables', {})
        timeline = analysis.get('timeline', {})
        resources = analysis.get('resources', {})
        
        # 프로젝트 경험을 더 구체적으로 정리
        project_experience_detail = []
        for proj in projects[:4]:  # 상위 4개만 사용
            name = proj.get('project_name', 'Unknown')
            dept = proj.get('department', 'N/A')
            score = proj.get('@search.score', 0)
            detail = proj.get('description', '') or proj.get('summary', '')
            project_experience_detail.append({
                'name': name,
                'department': dept,
                'score': score,
                'detail': detail[:200] if detail else ''
            })
        
        # 솔루션을 더 구체적으로 정리
        solution_capabilities_detail = []
        for sol in solutions[:3]:  # 상위 3개만 사용
            name = sol.get('name', 'Unknown')
            desc = sol.get('description', '')
            score = sol.get('@search.score', 0)
            benefits = sol.get('benefits', '') or sol.get('features', '')
            solution_capabilities_detail.append({
                'name': name,
                'description': desc[:300] if desc else '',
                'score': score,
                'benefits': benefits[:200] if benefits else ''
            })
        
        # 핵심 키워드 추출
        core_keywords = []
        if technical_requirements.get('technologies'):
            core_keywords.extend(technical_requirements.get('technologies', []))
        if scope_of_work.get('main_tasks'):
            core_keywords.extend([task.split()[0] for task in scope_of_work.get('main_tasks', [])][:3])
        
        # 기대성과 문자열 생성
        expected_outcomes_text = ""
        for outcome in objectives.get('expected_outcomes', []):
            expected_outcomes_text += f"• {outcome}\n"
        
        # 성공기준 문자열 생성
        success_criteria_text = ""
        for criteria in objectives.get('success_criteria', []):
            success_criteria_text += f"• {criteria}\n"
        
        # 주요업무 문자열 생성
        main_tasks_text = ""
        for i, task in enumerate(scope_of_work.get('main_tasks', []), 1):
            main_tasks_text += f"{i}. {task}\n"
        
        # 기술요구사항 문자열 생성
        tech_stack = ', '.join(technical_requirements.get('technologies', []))
        platforms = ', '.join(technical_requirements.get('platforms', []))
        security_reqs = ', '.join(technical_requirements.get('security_requirements', []))
        
        # 산출물 문자열 생성
        documents = ', '.join(deliverables.get('documents', []))
        systems = ', '.join(deliverables.get('systems', []))
        
        # 프로젝트 경험 문자열 생성
        project_experience_text = ""
        for i, proj in enumerate(project_experience_detail, 1):
            project_experience_text += f"**{i}. {proj['name']}**\n"
            project_experience_text += f"   - 담당부서: {proj['department']}\n"
            project_experience_text += f"   - 유사도: {proj['score']:.1%}\n"
            project_experience_text += f"   - 상세: {proj['detail'][:150]}\n\n"
        
        # 솔루션 역량 문자열 생성
        solution_capabilities_text = ""
        for i, sol in enumerate(solution_capabilities_detail, 1):
            solution_capabilities_text += f"**{i}. {sol['name']}**\n"
            solution_capabilities_text += f"   - 적합도: {sol['score']:.1%}\n"
            solution_capabilities_text += f"   - 솔루션 개요: {sol['description'][:200]}\n"
            solution_capabilities_text += f"   - 핵심 강점: {sol['benefits'][:150]}\n\n"
        
        # 개선된 구조화 프롬프트
        prompt = f"""
당신은 KT DS의 수석 제안서 작성 전문가입니다. 다음 과업지시서를 바탕으로 수주 확률을 최대화할 수 있는 전략적 제안서를 작성해주세요.

# 📋 CONTEXT: 과업 정보
## 기본 정보
- **과업명**: {project_info.get('project_title', '미확인')}
- **발주처**: {project_info.get('client_organization', '미확인')}
- **과업기간**: {project_info.get('project_period', '미확인')}
- **과업예산**: {project_info.get('project_budget', '미확인')}
- **과업관리자**: {project_info.get('project_manager', '미확인')}

## 핵심 목표 & 요구사항
**목적**: {objectives.get('main_purpose', '미확인')}

**기대성과**: 
{expected_outcomes_text}

**성공기준**: 
{success_criteria_text}

**주요 업무**:
{main_tasks_text}

**기술 요구사항**:
- 기술스택: {tech_stack}
- 플랫폼: {platforms}
- 보안요구: {security_reqs}

**핵심 산출물**:
- 문서: {documents}
- 시스템: {systems}

# 💪 KT DS 경쟁력 자산
## 관련 프로젝트 수행실적
{project_experience_text}

## 보유 솔루션 및 기술역량
{solution_capabilities_text}

# 🎯 MISSION: 전략적 제안서 작성

다음 구조로 **설득력 있고 차별화된** 제안서를 작성하세요:

## 1. 🎯 **과업 이해 및 접근전략**
### 1.1 과업의 핵심 이슈 진단
- 발주처가 직면한 **근본적 문제**와 **해결 필요성** 분석
- 과업의 **전략적 중요성**과 **비즈니스 임팩트** 해석
- **성공 요인**과 **위험 요소** 식별

### 1.2 KT DS만의 차별화된 접근법
- 단순 요구사항 충족을 넘어선 **부가가치 창출** 방안
- **혁신적 아이디어**와 **최신 기술 트렌드** 반영
- **지속가능한 성과**를 위한 **전략적 관점** 제시

## 2. 💼 **수행 역량 및 경쟁우위**
### 2.1 프로젝트 수행 경험
- 위 관련 프로젝트들의 **구체적 성과**와 **학습된 노하우**
- **유사 도메인** 경험을 통한 **리스크 최소화** 능력
- **성공 패턴**과 **베스트 프랙티스** 적용 방안

### 2.2 기술적 우위 및 솔루션 활용
- 보유 솔루션의 **이 과업에 특화된** 적용 방안
- **기술적 차별화** 요소와 **성능 우위**
- **커스터마이징** 및 **최적화** 계획

### 2.3 조직역량 및 전문인력
- **핵심 역할별** 투입 예정 **전문가** 프로필
- **팀워크**와 **소통체계**의 **효율성**
- **프로젝트 관리** 역량과 **품질보증** 시스템

## 3. 📋 **구체적 수행계획**
### 3.1 단계별 수행전략
- **Phase별** 세부 계획과 **핵심 마일스톤**
- 각 단계별 **검증 포인트**와 **품질 기준**
- **조기 성과** 창출을 위한 **Quick Win** 전략

### 3.2 일정 및 자원관리
- **현실적이고 여유있는** 일정 계획
- **리스크 대응**을 위한 **버퍼 시간** 확보
- **효율적 자원 배분**과 **역할 분담**

### 3.3 소통 및 협업체계
- **발주처와의** 원활한 **의사소통** 채널
- **정기 보고** 및 **피드백** 시스템
- **이슈 해결**을 위한 **에스컬레이션** 프로세스

## 4. 🎁 **부가가치 및 차별화 요소**
### 4.1 과업 범위를 넘어선 가치 제공
- **무상 추가 서비스** 또는 **부가 기능** 제안
- **운영 효율성** 개선을 위한 **컨설팅** 지원
- **미래 확장성**을 고려한 **아키텍처** 설계

### 4.2 KT DS만의 특별한 강점
- **KT그룹**의 **인프라**와 **네트워크** 활용 혜택
- **대기업 수준**의 **보안**과 **안정성** 보장
- **지속적 지원**과 **장기 파트너십** 의지

## 5. 📊 **기대효과 및 성과측정**
### 5.1 정량적 성과 지표
- **구체적 수치**로 표현된 **개선 목표**
- **ROI 계산**과 **비용 절감** 효과
- **성능 향상** 및 **효율성** 증대 지표

### 5.2 정성적 가치 창출
- **사용자 만족도** 개선과 **업무 편의성** 증대
- **경쟁력 강화**와 **브랜드 가치** 제고
- **조직 역량** 향상과 **디지털 전환** 가속화

### 5.3 지속적 발전 방안
- **운영 단계**에서의 **지속적 개선** 계획
- **기술 진화**에 따른 **업그레이드** 로드맵
- **확장 가능성**과 **연계 프로젝트** 기회

# ✅ 작성 가이드라인

1. **구체성**: 추상적 표현보다는 **구체적 수치**와 **실제 사례** 활용
2. **차별화**: 일반적 내용보다는 **KT DS만의 독특한** 강점 부각
3. **신뢰성**: 과대 포장보다는 **현실적이고 달성 가능한** 약속
4. **고객 중심**: 기술 자랑보다는 **고객 가치**와 **문제 해결**에 집중
5. **전문성**: 해당 도메인에 대한 **깊이 있는 이해**와 **전문 용어** 적절 사용
6. **스토리텔링**: 단순 나열보다는 **논리적 흐름**과 **설득 구조** 구성

마크다운 형식으로 **가독성 높게** 작성하되, **이모지**와 **강조 표시**를 적절히 활용해 **임팩트**를 높여주세요.
"""
        
        # 개선된 시스템 프롬프트
        system_prompt = """당신은 KT DS의 수석 제안서 작성 전문가입니다.

## 전문성 영역
- IT 프로젝트 제안서 작성 15년 경력
- 대기업/공공기관 발주 프로젝트 수주율 85% 달성
- 디지털 트랜스포메이션, 클라우드, AI/빅데이터 전문
- KT그룹 계열사 시너지 효과 극대화 노하우

## 작성 철학
1. **고객 니즈 우선**: 기술 자랑보다 고객 문제 해결에 집중
2. **차별화된 가치**: 단순 기능 구현을 넘어선 부가가치 창출
3. **신뢰 기반**: 과대 약속보다 현실적이고 달성 가능한 계획
4. **전략적 사고**: 단기 과업을 넘어선 장기 파트너십 관점
5. **스토리텔링**: 논리적 흐름과 감정적 어필의 조화

## 핵심 성공 요소
- 발주처의 **숨겨진 니즈** 파악 및 해결책 제시
- KT DS의 **고유한 강점** 스토리로 구성
- **구체적 수치**와 **실제 사례**로 신뢰성 확보
- **위험 요소**를 사전 식별하고 **대응 방안** 제시
- **경쟁사와 차별화**되는 **혁신적 접근법** 개발

매번 수주에 성공하는 **설득력 있는 제안서**를 작성하세요."""
        
        response = self.client.chat.completions.create(
            model=self.chat_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.15,  # 창의성과 일관성의 균형
            max_tokens=4500,   # 더 상세한 내용
            top_p=0.9         # 다양성 확보
        )
        
        return response.choices[0].message.content

def display_analysis_results(analysis):
    """분석 결과 표시 - 깔끔한 카드 형태"""
    st.markdown("### 📊 과업지시서 분석 결과")
    
    project_info = analysis.get('project_info', {})
    objectives = analysis.get('objectives', {})
    scope_of_work = analysis.get('scope_of_work', {})
    technical_requirements = analysis.get('technical_requirements', {})
    deliverables = analysis.get('deliverables', {})
    timeline = analysis.get('timeline', {})
    resources = analysis.get('resources', {})
    
    # 프로젝트 기본 정보 - 전체 너비 사용
    if project_info.get('project_title') or project_info.get('client_organization'):
        basic_info_content = ""
        
        if project_info.get('project_title'):
            basic_info_content += f"<div style='margin-bottom: 16px;'><strong style='color: #2c3e50; font-size: 1.4em;'>{project_info.get('project_title')}</strong></div>"
        
        basic_items = []
        if project_info.get('client_organization'):
            basic_items.append(f"<strong>발주처</strong>: {project_info.get('client_organization')}")
        if project_info.get('project_period'):
            basic_items.append(f"<strong>기간</strong>: {project_info.get('project_period')}")
        if project_info.get('project_budget'):
            basic_items.append(f"<strong>예산</strong>: {project_info.get('project_budget')}")
        if project_info.get('project_manager'):
            basic_items.append(f"<strong>관리자</strong>: {project_info.get('project_manager')}")
        
        if basic_items:
            # 2개씩 나누어서 표시
            left_items = basic_items[:2]
            right_items = basic_items[2:]
            
            basic_info_content += "<div style='display: flex; gap: 3rem;'>"
            basic_info_content += f"<div style='flex: 1; font-size: 1.1em; line-height: 1.8;'>{'<br>'.join(left_items)}</div>"
            if right_items:
                basic_info_content += f"<div style='flex: 1; font-size: 1.1em; line-height: 1.8;'>{'<br>'.join(right_items)}</div>"
            basic_info_content += "</div>"
        
        st.markdown(f"""
        <div class="feature-card" style="margin-bottom: 1.5rem;">
            <div style="margin-bottom: 12px; font-weight: 600; color: #495057; font-size: 1.15em;">📋 프로젝트 정보</div>
            {basic_info_content}
        </div>
        """, unsafe_allow_html=True)
    
    # 나머지 정보들 - 각각 한 줄씩
    
    # 과업 목적
    if objectives.get('main_purpose'):
        st.markdown(f"""
        <div class="feature-card">
            <div style="margin-bottom: 8px; font-weight: 600; color: #495057; font-size: 1.05em;">🎯 과업 목적</div>
            <div style="font-size: 1em; line-height: 1.5; color: #343a40;">{objectives.get('main_purpose')}</div>
        </div>
        """, unsafe_allow_html=True)
    
    # 기대성과
    if objectives.get('expected_outcomes'):
        outcomes_content = ""
        for outcome in objectives.get('expected_outcomes', []):
            outcomes_content += f"<div style='margin-bottom: 4px;'>• {outcome}</div>"
        
        st.markdown(f"""
        <div class="feature-card">
            <div style="margin-bottom: 8px; font-weight: 600; color: #495057; font-size: 1.05em;">✨ 기대성과</div>
            <div style="font-size: 0.95em; line-height: 1.5; color: #343a40;">{outcomes_content}</div>
        </div>
        """, unsafe_allow_html=True)
    
    # 주요 업무
    if scope_of_work.get('main_tasks'):
        tasks_content = ""
        for i, task in enumerate(scope_of_work.get('main_tasks', []), 1):
            tasks_content += f"<div style='margin-bottom: 4px;'>{i}. {task}</div>"
        
        st.markdown(f"""
        <div class="feature-card">
            <div style="margin-bottom: 8px; font-weight: 600; color: #495057; font-size: 1.05em;">📝 주요 업무</div>
            <div style="font-size: 0.95em; line-height: 1.5; color: #343a40;">{tasks_content}</div>
        </div>
        """, unsafe_allow_html=True)
    
    # 세부 활동
    if scope_of_work.get('detailed_activities'):
        activities_content = ""
        for activity in scope_of_work.get('detailed_activities', []):
            activities_content += f"<div style='margin-bottom: 4px;'>• {activity}</div>"
        
        st.markdown(f"""
        <div class="feature-card">
            <div style="margin-bottom: 8px; font-weight: 600; color: #495057; font-size: 1.05em;">📋 세부 활동</div>
            <div style="font-size: 0.95em; line-height: 1.5; color: #343a40;">{activities_content}</div>
        </div>
        """, unsafe_allow_html=True)
    
    # 기술 요구사항
    tech_has_content = any([
        technical_requirements.get('technologies'),
        technical_requirements.get('platforms'),
        technical_requirements.get('standards')
    ])
    
    if tech_has_content:
        tech_content = ""
        if technical_requirements.get('technologies'):
            tech_list = ', '.join(technical_requirements.get('technologies', []))
            tech_content += f"<div style='margin-bottom: 8px;'><strong>기술</strong>: {tech_list}</div>"
        
        if technical_requirements.get('platforms'):
            platform_list = ', '.join(technical_requirements.get('platforms', []))
            tech_content += f"<div style='margin-bottom: 8px;'><strong>플랫폼</strong>: {platform_list}</div>"
        
        if technical_requirements.get('standards'):
            standards_list = ', '.join(technical_requirements.get('standards', []))
            tech_content += f"<div style='margin-bottom: 8px;'><strong>표준</strong>: {standards_list}</div>"
        
        st.markdown(f"""
        <div class="feature-card">
            <div style="margin-bottom: 8px; font-weight: 600; color: #495057; font-size: 1.05em;">🔧 기술 요구사항</div>
            <div style="font-size: 0.95em; line-height: 1.5; color: #343a40;">{tech_content}</div>
        </div>
        """, unsafe_allow_html=True)
    
    # 보안 요구사항
    if technical_requirements.get('security_requirements'):
        security_content = ""
        for req in technical_requirements.get('security_requirements', []):
            security_content += f"<div style='margin-bottom: 4px;'>• {req}</div>"
        
        st.markdown(f"""
        <div class="feature-card">
            <div style="margin-bottom: 8px; font-weight: 600; color: #495057; font-size: 1.05em;">🔒 보안 요구사항</div>
            <div style="font-size: 0.95em; line-height: 1.5; color: #343a40;">{security_content}</div>
        </div>
        """, unsafe_allow_html=True)
    
    # 주요 산출물
    deliverable_has_content = any([
        deliverables.get('documents'),
        deliverables.get('systems'),
        deliverables.get('reports')
    ])
    
    if deliverable_has_content:
        deliverable_content = ""
        if deliverables.get('documents'):
            doc_list = ', '.join(deliverables.get('documents', []))
            deliverable_content += f"<div style='margin-bottom: 8px;'><strong>문서</strong>: {doc_list}</div>"
        
        if deliverables.get('systems'):
            sys_list = ', '.join(deliverables.get('systems', []))
            deliverable_content += f"<div style='margin-bottom: 8px;'><strong>시스템</strong>: {sys_list}</div>"
        
        if deliverables.get('reports'):
            report_list = ', '.join(deliverables.get('reports', []))
            deliverable_content += f"<div style='margin-bottom: 8px;'><strong>보고서</strong>: {report_list}</div>"
        
        st.markdown(f"""
        <div class="feature-card">
            <div style="margin-bottom: 8px; font-weight: 600; color: #495057; font-size: 1.05em;">📦 주요 산출물</div>
            <div style="font-size: 0.95em; line-height: 1.5; color: #343a40;">{deliverable_content}</div>
        </div>
        """, unsafe_allow_html=True)
    
    # 일정 및 자원
    schedule_has_content = any([
        timeline.get('phases'),
        timeline.get('milestones'),
        resources.get('required_roles'),
        resources.get('skill_requirements')
    ])
    
    if schedule_has_content:
        schedule_content = ""
        if timeline.get('phases'):
            phases_list = ', '.join(timeline.get('phases', []))
            schedule_content += f"<div style='margin-bottom: 8px;'><strong>단계</strong>: {phases_list}</div>"
        
        if timeline.get('milestones'):
            milestones_list = ', '.join(timeline.get('milestones', []))
            schedule_content += f"<div style='margin-bottom: 8px;'><strong>마일스톤</strong>: {milestones_list}</div>"
        
        if resources.get('required_roles'):
            roles_list = ', '.join(resources.get('required_roles', []))
            schedule_content += f"<div style='margin-bottom: 8px;'><strong>필요 역할</strong>: {roles_list}</div>"
        
        if resources.get('skill_requirements'):
            skills_list = ', '.join(resources.get('skill_requirements', []))
            schedule_content += f"<div style='margin-bottom: 8px;'><strong>필요 기술</strong>: {skills_list}</div>"
        
        st.markdown(f"""
        <div class="feature-card">
            <div style="margin-bottom: 8px; font-weight: 600; color: #495057; font-size: 1.05em;">⏰ 일정 및 자원</div>
            <div style="font-size: 0.95em; line-height: 1.5; color: #343a40;">{schedule_content}</div>
        </div>
        """, unsafe_allow_html=True)

def display_matching_results(projects, solutions):
    """매칭 결과 표시"""
    st.markdown("### 🎯 자사 역량 매칭 결과")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 💼 관련 프로젝트 경험")
        
        if projects:
            for i, proj in enumerate(projects, 1):
                name = proj.get('project_name', 'Unknown')
                dept = proj.get('department', 'N/A')
                score = proj.get('@search.score', 0)
                
                st.markdown(f"""
                <div class="feature-card">
                    <strong>{i}. {name}</strong><br>
                    <small>부서: {dept} | 매칭도: {score:.3f}</small>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("관련 프로젝트를 찾을 수 없습니다.")
    
    with col2:
        st.markdown("#### 🛠️ 활용 가능한 솔루션")

        if solutions:
            for i, sol in enumerate(solutions, 1):
                name = sol.get('name', 'Unknown')
                score = sol.get('@search.score', 0)
                full_desc = sol.get('description', '')

                cutoff = full_desc.find(".")
                desc = full_desc[:cutoff + 1] if cutoff != -1 else full_desc[:100] + "..."
                
                pdf_path = f"static/solution_pdf/{name}.pdf"
                pdf_available = os.path.exists(pdf_path)

                st.markdown(f"""
                <div class="feature-card">
                    <strong>{i}. {name}</strong><br>
                    <small>매칭도: {score:.3f}</small><br>
                    <p style="margin-top: 8px; font-size: 0.9em;">{desc}</p>
                """, unsafe_allow_html=True)
                
                if pdf_available:
                    with open(pdf_path, "rb") as f:
                        pdf_bytes = f.read()
                    
                    st.download_button(
                        label="📄 소개서 다운로드",
                        data=pdf_bytes,
                        file_name=f"{name}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        key=f"solution_download_{i}"
                    )

                st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("관련 솔루션을 찾을 수 없습니다.")

def display_proposal_with_enhanced_ui(proposal_content):
    """개선된 제안서 표시 UI"""
    
    # 제안서 헤더
    st.markdown("""
    <div class="proposal-header">
        <h1 style="margin: 0; font-size: 2rem;">📋 과업 수행 제안서</h1>
        <p style="margin: 0.5rem 0 0 0; font-size: 1.1rem; opacity: 0.9;">KT DS 맞춤형 솔루션 제안</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 다운로드 버튼들
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    
    with col2:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        txt_filename = f"KTDS_제안서_{timestamp}.txt"
        
        st.download_button(
            label="📄 TXT 다운로드",
            data=proposal_content,
            file_name=txt_filename,
            mime="text/plain",
            use_container_width=True,
            key="proposal_download_txt"
        )
    
    with col3:
        # Markdown 파일로 다운로드
        md_filename = f"KTDS_제안서_{timestamp}.md"
        
        st.download_button(
            label="📝 MD 다운로드",
            data=proposal_content,
            file_name=md_filename,
            mime="text/markdown",
            use_container_width=True,
            key="proposal_download_md"
        )
    
    st.markdown("---")
    
    # 제안서 내용을 마크다운으로 렌더링
    st.markdown(proposal_content, unsafe_allow_html=True)
    
    # 액션 버튼들
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        if st.button("🔄 제안서 재생성", use_container_width=True):
            st.session_state.proposal_content = None
            st.rerun()
    
    with col2:
        if st.button("✏️ 내용 수정", use_container_width=True):
            # 수정 모드로 전환하는 세션 상태 설정
            st.session_state.edit_mode = True
            st.rerun()
    
    with col3:
        if st.button("📊 분석 리포트", use_container_width=True):
            # 분석 리포트 생성 (추가 기능)
            st.info("📊 상세 분석 리포트 기능은 준비 중입니다.")

def display_editable_proposal(proposal_content):
    """편집 가능한 제안서 표시"""
    
    st.markdown("### ✏️ 제안서 편집 모드")
    
    # 편집 가능한 텍스트 영역
    edited_content = st.text_area(
        "제안서 내용을 수정하세요:",
        value=proposal_content,
        height=600,
        key="proposal_editor"
    )
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("💾 수정 내용 저장", type="primary", use_container_width=True):
            st.session_state.proposal_content = edited_content
            st.session_state.edit_mode = False
            st.success("✅ 제안서가 수정되었습니다!")
            st.rerun()
    
    with col2:
        if st.button("❌ 편집 취소", use_container_width=True):
            st.session_state.edit_mode = False
            st.rerun()

def main():
    init_session_state()
    
    st.markdown("""
    <div class="main-header">
        <h1>📋 KT DS 제안서 도우미</h1>
        <p>AI 기반 과업지시서 분석 및 맞춤형 제안서 생성 시스템</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 사이드바
    with st.sidebar:
        st.markdown("""
        <div style="
            background:linear-gradient(135deg, #4a90e2 0%, #357abd 100%);
            padding: 1.5rem;
            border-radius: 15px;
            text-align: center;
            color: white;
            margin-bottom: 1.5rem;
            box-shadow: 0 4px 15px rgba(74, 144, 226, 0.4);
        ">
            <h2 style="margin: 0; font-size: 1.5rem;">📋</h2>
            <h3 style="margin: 0.5rem 0 0 0; font-size: 1.1rem;">과업지시서 도우미</h3>
            <p style="margin: 0.3rem 0 0 0; font-size: 0.85rem; opacity: 0.9;">AI 기반 제안서 작성 지원</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("### 🚀 주요 기능")
        st.markdown("""
        - 📄 과업지시서 자동 분석
        - 🎯 요구사항 추출 및 정리
        - 🔍 자사 역량 매칭
        - 📝 맞춤형 제안서 생성
        - 💼 프로젝트 경험 활용
        - 🛠️ 솔루션 추천
        """)
        
        st.markdown("### 📊 시스템 상태")
        if SEARCH_ENDPOINT and SEARCH_KEY:
            st.success("✅ Azure AI Search 연결됨")
        else:
            st.error("❌ Azure AI Search 연결 실패")
        
        if os.getenv("OPENAI_API_KEY"):
            st.success("✅ Azure OpenAI 연결됨")
        else:
            st.error("❌ Azure OpenAI 연결 실패")
    
    # 메인 컨텐츠
    tab1, tab2, tab3 = st.tabs(["📄 과업지시서 분석", "🔍 분석 결과", "📝 제안서"])
    
    with tab1:
        st.markdown("### 📄 과업지시서 업로드")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("""
            <div class="feature-card">
                <h4>📋 지원 파일 형식</h4>
                <ul>
                    <li><strong>PDF</strong> - HWP를 PDF로 변환한 파일 (권장)</li>
                    <li><strong>텍스트</strong> - 과업지시서 내용을 직접 입력</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
            <div class="info-box">
                <h4>💡 변환 방법</h4>
                <p>한글 → 파일 → PDF로 내보내기</p>
            </div>
            """, unsafe_allow_html=True)
        
        # 파일 업로드 옵션
        upload_option = st.radio(
            "입력 방법 선택",
            ["PDF 파일 업로드", "텍스트 직접 입력"],
            horizontal=True
        )
        
        document_text = None
        
        if upload_option == "PDF 파일 업로드":
            uploaded_file = st.file_uploader(
                "PDF 과업지시서를 업로드하세요",
                type=['pdf'],
                help="HWP 파일을 PDF로 변환한 후 업로드해주세요"
            )
            
            if uploaded_file is not None:
                st.success(f"✅ 파일 업로드 완료: {uploaded_file.name}")
                
                with st.spinner("📄 PDF에서 텍스트 추출 중..."):
                    processor = TaskOrderProcessor()
                    document_text = processor.extract_text_from_pdf(uploaded_file)
                
                if document_text:
                    st.success(f"✅ 텍스트 추출 완료 ({len(document_text)} 글자)")
                    
                    with st.expander("📋 추출된 텍스트 미리보기"):
                        st.text_area(
                            "추출된 내용",
                            document_text[:1000] + "..." if len(document_text) > 1000 else document_text,
                            height=200,
                            disabled=True
                        )
                else:
                    st.error("❌ 텍스트 추출에 실패했습니다. PDF 파일을 확인해주세요.")
        
        else:  # 텍스트 직접 입력
            document_text = st.text_area(
                "과업지시서 내용을 입력하세요",
                height=300,
                placeholder="과업지시서 내용을 여기에 붙여넣으세요...",
                help="HWP 파일을 열어서 내용을 복사해서 붙여넣으세요"
            )
        
        # 분석 버튼
        if document_text and st.button("🔍 과업지시서 분석 시작", type="primary", use_container_width=True):
            
            # 새로운 분석 시작 시 기존 결과 초기화
            st.session_state.analysis_result = None
            st.session_state.projects_result = None
            st.session_state.solutions_result = None
            st.session_state.proposal_content = None  # 제안서도 초기화
            
            # 진행률 표시
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            processor = TaskOrderProcessor()
            
            # 1. 과업지시서 분석
            status_text.text("🔍 과업지시서 분석 중...")
            progress_bar.progress(20)
            
            analysis = processor.analyze_task_order(document_text)
            
            if "error" not in analysis:
                progress_bar.progress(40)
                st.session_state.analysis_result = analysis
                
                # 2. 자사 역량 검색
                status_text.text("🔍 자사 역량 검색 중...")
                progress_bar.progress(60)
                
                project_info = analysis.get('project_info', {})
                objectives = analysis.get('objectives', {})
                scope_of_work = analysis.get('scope_of_work', {})
                technical_requirements = analysis.get('technical_requirements', {})
                
                # 검색 쿼리 생성
                search_query = f"""
                {project_info.get('project_title', '')}
                {objectives.get('main_purpose', '')}
                {' '.join(scope_of_work.get('main_tasks', []))}
                {' '.join(technical_requirements.get('technologies', []))}
                """
                
                embedding = processor.get_embedding(search_query)
                
                projects = processor.search_projects(embedding)
                solutions = processor.search_solutions(embedding)
                
                progress_bar.progress(80)
                
                st.session_state.projects_result = projects
                st.session_state.solutions_result = solutions
                
                progress_bar.progress(100)
                status_text.text("✅ 분석 완료!")
                
                time.sleep(1)
                progress_bar.empty()
                status_text.empty()
                
                st.success("🎉 과업지시서 분석이 완료되었습니다! '분석 결과' 탭에서 확인하세요.")
                
            else:
                st.error("❌ 과업지시서 분석에 실패했습니다.")
    
    with tab2:
        if st.session_state.analysis_result:
            display_analysis_results(st.session_state.analysis_result)
            
            if st.session_state.projects_result is not None and st.session_state.solutions_result is not None:
                # 구분선 추가
                st.markdown("---")
                st.markdown("")  # 여백 추가
                display_matching_results(st.session_state.projects_result, st.session_state.solutions_result)
        else:
            st.info("먼저 과업지시서를 업로드하고 분석을 시작해주세요.")
    
    with tab3:
        if st.session_state.analysis_result and st.session_state.projects_result is not None:
            
            st.markdown("### 📝 맞춤형 제안서 생성")
            
            # 편집 모드 확인
            if st.session_state.get('edit_mode', False) and st.session_state.proposal_content:
                display_editable_proposal(st.session_state.proposal_content)
            
            # 제안서가 이미 생성되어 있는지 확인
            elif st.session_state.proposal_content:
                display_proposal_with_enhanced_ui(st.session_state.proposal_content)
                
                # 성공 메시지
                st.markdown("""
                <div class="completion-box">
                    <h4 style="margin: 0;">🎉 제안서 생성 완료!</h4>
                    <p style="margin: 0.5rem 0 0 0;">AI가 생성한 제안서를 검토하고 필요에 따라 수정하여 활용하세요.</p>
                </div>
                """, unsafe_allow_html=True)
                
            else:
                # 제안서 생성 안내
                st.markdown("""
                <div class="ready-box">
                    <h3>🚀 AI 제안서 생성 준비 완료</h3>
                    <p>과업지시서 분석과 자사 역량 매칭이 완료되었습니다.<br>
                    이제 맞춤형 제안서를 생성할 수 있습니다.</p>
                </div>
                """, unsafe_allow_html=True)
                
                # 제안서 생성 버튼
                if st.button("🚀 AI 제안서 생성 시작", type="primary", use_container_width=True, key="generate_proposal"):
                    
                    # 진행률 표시
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    status_text.text("🤖 AI가 제안서를 생성하고 있습니다...")
                    progress_bar.progress(20)
                    
                    processor = TaskOrderProcessor()
                    
                    status_text.text("📊 과업 정보 분석 중...")
                    progress_bar.progress(40)
                    
                    status_text.text("💼 프로젝트 경험 정리 중...")
                    progress_bar.progress(60)
                    
                    status_text.text("🛠️ 솔루션 매칭 중...")
                    progress_bar.progress(80)
                    
                    proposal = processor.generate_proposal(
                        st.session_state.analysis_result,
                        st.session_state.projects_result,
                        st.session_state.solutions_result
                    )
                    
                    progress_bar.progress(100)
                    status_text.text("✅ 제안서 생성 완료!")
                    
                    # 제안서를 세션 상태에 저장
                    st.session_state.proposal_content = proposal
                    
                    time.sleep(1)
                    progress_bar.empty()
                    status_text.empty()
                    
                    # 페이지 새로고침하여 생성된 제안서 표시
                    st.rerun()
                    
        else:
            st.markdown("""
            <div class="warning-analysis-box">
                <h4>⚠️ 분석이 필요합니다</h4>
                <p>제안서 생성을 위해서는 먼저 과업지시서 분석을 완료해주세요.</p>
            </div>
            """, unsafe_allow_html=True)
    
    # 푸터
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 1rem;">
        <p>📋 KT DS 제안서 도우미 | Powered by Azure OpenAI & AI Search</p>
        <p>더 나은 제안서 작성을 위해 지속적으로 개선하고 있습니다.</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()