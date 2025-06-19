import os
import json
from dotenv import load_dotenv
from openai import AzureOpenAI
from tqdm import tqdm

load_dotenv()

client = AzureOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    api_version=os.getenv("OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("OPENAI_ENDPOINT")
)

embedding_model = os.getenv("OPENAI_EMBEDDING_DEPLOYMENT")

# 파일 경로
json_path = "data/preprocess_results/project_history.json"
output_path = "data/preprocess_results/enriched_project_history.json"

# 데이터 로드
with open(json_path, "r", encoding="utf-8") as f:
    data = json.load(f)

# embedding 생성
for item in tqdm(data):
    text = item["summary_text"]
    response = client.embeddings.create(
        model=embedding_model,
        input=text
    )
    item["embedding"] = response.data[0].embedding

# 저장
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"✅ embedding 생성 완료 → {output_path}")
