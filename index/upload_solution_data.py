import os
import json
import requests
from dotenv import load_dotenv
from math import ceil

# env 불러오기
load_dotenv()

AZURE_SEARCH_ENDPOINT = os.getenv("SEARCH_ENDPOINT")
AZURE_SEARCH_KEY = os.getenv("SEARCH_ADMIN_KEY")
API_VERSION = "2023-10-01-Preview"

headers = {
    "Content-Type": "application/json",
    "api-key": AZURE_SEARCH_KEY
}

index_name = "solution-embedding-index"

# JSON 파일 로드
with open("data/preprocess_results/enriched_solution.json", "r", encoding="utf-8") as f:
    documents = json.load(f)

# documents 변환
upload_docs = []
for doc in documents:
    upload_docs.append({
        "@search.action": "upload",
        "id": doc["id"],
        "name": doc["name"],
        "description": doc.get("longDescription", ""),
        "embedding": doc["embedding"]
    })

# 배치 분할 (최대 1000건씩)
batch_size = 500
total_batches = ceil(len(upload_docs) / batch_size)

for i in range(total_batches):
    batch = upload_docs[i * batch_size:(i + 1) * batch_size]
    url = f"{AZURE_SEARCH_ENDPOINT}/indexes/{index_name}/docs/index?api-version={API_VERSION}"
    response = requests.post(url, headers=headers, json={"value": batch})

    print(f"Batch {i+1}/{total_batches} → Status: {response.status_code}")
    print(response.json())

print("✅ 모든 데이터 업로드 완료!")
