import os
import json
import fitz
import re
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

client = AzureOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    api_version=os.getenv("OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("OPENAI_ENDPOINT")
)

embedding_model = os.getenv("OPENAI_EMBEDDING_DEPLOYMENT")
chat_model = os.getenv("OPENAI_CHAT_DEPLOYMENT")

# ✅ 파일 경로 설정
json_path = "data/solution_json/solution.json"
pdf_dir = "data/solution_pdf"
output_path = "data/preprocess_results/enriched_solution.json"

# ✅ PDF 텍스트 추출
def extract_pdf_text(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

# ✅ GPT-4.1-mini 요약 (프롬프트 최적화)
def summarize_pdf(pdf_text):
    system_prompt = """
    너는 기업 솔루션 브로셔 요약을 전문으로 하는 AI야.
    다음 원문에서 중요한 기술적 기능, 제공 서비스, 독보적 강점 중심으로 요약해줘.
    - 반복 표현, 마케팅성 문구, 장황한 설명은 제거
    - 기능, 기술, 서비스, 강점만 남긴다
    - 차별화된 경쟁력은 적극 강조
    - 길이는 1000자 이내로 간결하게 작성
    """
    response = client.chat.completions.create(
        model=chat_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": pdf_text}
        ],
        temperature=0.2,
        max_tokens=1000
    )
    return response.choices[0].message.content

# ✅ Embedding 생성 (Azure Native)
def get_embedding(text):
    response = client.embeddings.create(
        model=embedding_model,
        input=text
    )
    return response.data[0].embedding

# ✅ 기존 JSON 로드
with open(json_path, 'r', encoding='utf-8') as f:
    solutions = json.load(f)

# ✅ 전체 데이터 통합 처리
new_data = []

for solution in solutions:
    solution_name = solution['name']
    pdf_filename = f"{solution_name}.pdf"
    pdf_path = os.path.join(pdf_dir, pdf_filename)

    # PDF 존재 여부 확인 → 요약 수행
    if os.path.exists(pdf_path):
        print(f"[INFO] PDF 요약 진행 중: {pdf_filename}")
        pdf_text = extract_pdf_text(pdf_path)
        pdf_summary = summarize_pdf(pdf_text)
        solution['pdf_summary'] = pdf_summary
        # solution['pdf_url'] = f"https://smjstorage.blob.core.windows.net/solution-pdf/{pdf_filename}"
    else:
        print(f"[INFO] PDF 없음 → 요약 생략: {pdf_filename}")
        solution['pdf_summary'] = ""
        # solution['pdf_url'] = ""

    # embedding_text 생성 (RAG 최적화)
    benefits = ", ".join(solution['benefits'] or [])
    techSpecs = ", ".join(solution['techSpecs'] or [])
    caseStudies = ", ".join([
        case.get('title', '(제목없음)') 
        for case in (solution['caseStudies'] or [])
    ])

    embedding_text = f"""
    솔루션명: {solution_name}.
    설명: {solution.get('longDescription', '')}.
    PDF 요약: {solution['pdf_summary']}.
    주요 강점: {benefits}.
    기술 사양: {techSpecs}.
    적용 사례: {caseStudies}.
    이 솔루션의 경쟁사 대비 차별화된 독보적 강점은: {benefits}.
    """

    solution['embedding_text'] = embedding_text
    solution['embedding'] = get_embedding(embedding_text)

    new_data.append(solution)

# ✅ 결과 저장
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(new_data, f, ensure_ascii=False, indent=2)

print(f"[완료] enriched_solution.json 저장 완료 → {output_path}")
