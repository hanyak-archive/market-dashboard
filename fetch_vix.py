"""
FRED API에서 VIX(공포지수) 최근 90일 일별 데이터를 받아 vix_daily.json을 생성한다.
매일 자동 실행되며, 월간 지표(fetch_indicators.py)와는 별도로 관리된다.

필요 사전 준비: FRED_API_KEY 환경변수 (기존 워크플로우와 동일한 Secret 재사용)
실행: python scripts/fetch_vix.py
"""
import json
import os
import sys
import datetime
import urllib.request

API_KEY = os.environ.get("FRED_API_KEY")
DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "vix_daily.json")
DAYS_BACK = 90

FRED_URL = "https://api.stlouisfed.org/fred/series/observations"


def fetch_daily(series_id: str, start: str):
    params = f"series_id={series_id}&api_key={API_KEY}&file_type=json&observation_start={start}&units=lin"
    with urllib.request.urlopen(f"{FRED_URL}?{params}", timeout=30) as resp:
        payload = json.loads(resp.read().decode())
    out = []
    for obs in payload["observations"]:
        if obs["value"] == ".":
            continue
        out.append({"date": obs["date"], "value": round(float(obs["value"]), 2)})
    return out


def main():
    if not API_KEY:
        print("FRED_API_KEY 환경변수가 없습니다.", file=sys.stderr)
        sys.exit(1)

    start = (datetime.date.today() - datetime.timedelta(days=DAYS_BACK)).isoformat()
    values = fetch_daily("VIXCLS", start)
    if not values:
        print("VIX 데이터를 받지 못했습니다.", file=sys.stderr)
        sys.exit(1)

    out = {
        "updated": values[-1]["date"],
        "latest": values[-1]["value"],
        "values": values,
    }
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"VIX {len(values)}일치 저장 완료. 최신({values[-1]['date']}): {values[-1]['value']}")


if __name__ == "__main__":
    main()
