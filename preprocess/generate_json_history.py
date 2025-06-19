import csv
import json

# 입력 CSV 경로
csv_file = "data/history_csv/project_history.csv"

# 출력 JSON 경로
json_file = "data/preprocess_results/project_history.json"

data = []

with open(csv_file, newline='', encoding='cp949') as csvfile:
    reader = csv.DictReader(csvfile)

    for idx, row in enumerate(reader):
        summary_text = (
            f"{row['수행부서명']}이(가) {row['프로젝트명']} 프로젝트를 수행하였으며, "
            f"기간은 {row['시작일']} ~ {row['종료일']}, "
            f"계약 금액은 {row['수주계약금액']}원, "
            f"포트폴리오는 {row['포트폴리오']}, "
            f"수주부서는 {row['수주부서명']}, "
            f"고객사는 {row['고객명']}입니다."
        )

        record = {
            "id": f"proj-{idx+1:05}",
            "department": row["수행부서명"],
            "project_name": row["프로젝트명"],
            "start_date": row["시작일"],
            "end_date": row["종료일"],
            "portfolio": row["포트폴리오"],
            "contract_amount": row["수주계약금액"],
            "order_department": row["수주부서명"],
            "client": row["고객명"],
            "summary_text": summary_text
        }

        data.append(record)

with open(json_file, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"✅ JSON 변환 완료 → {json_file}")

