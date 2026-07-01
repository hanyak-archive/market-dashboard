"""
FRED API에서 경기 지표 5종의 최근 5년치 전체 히스토리를 받아 data.json을 새로 만든다.
(매달 실행 시 5년 범위를 통째로 다시 받아오므로 FRED의 과거 수치 수정도 자동 반영됨)

PMI는 FRED에 없어 자동화 제외 -> 기존 data.json에 수동 입력된 값은 월별로 그대로 보존.

필요 사전 준비: FRED_API_KEY 환경변수 (GitHub Secrets 또는 로컬 export)
실행: python scripts/fetch_indicators.py
"""
import json
import os
import sys
import datetime
import urllib.request

API_KEY = os.environ.get("FRED_API_KEY")
DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data.json")
YEARS_BACK = 5

SERIES = {
    "stock":  {"id": "SP500",  "units": "lin"},
    "ip":     {"id": "INDPRO", "units": "pc1"},
    "retail": {"id": "RSAFS",  "units": "pc1"},
    "gdp":    {"id": "GDPC1",  "units": "pc1"},
    "unemp":  {"id": "UNRATE", "units": "lin"},
}
FRED_URL = "https://api.stlouisfed.org/fred/series/observations"


def fetch_series(series_id: str, units: str, start: str) -> dict:
    """월키(YYYY-MM) -> 값 딕셔너리. 같은 달에 여러 관측치가 있으면(주가 등) 마지막 값 사용."""
    params = f"series_id={series_id}&api_key={API_KEY}&file_type=json&observation_start={start}&units={units}"
    with urllib.request.urlopen(f"{FRED_URL}?{params}", timeout=30) as resp:
        payload = json.loads(resp.read().decode())
    out = {}
    for obs in payload["observations"]:
        if obs["value"] == ".":
            continue
        month_key = obs["date"][:7]
        out[month_key] = round(float(obs["value"]), 2)
    return out


def month_range(start: str, end: str):
    y, m = int(start[:4]), int(start[5:7])
    ey, em = int(end[:4]), int(end[5:7])
    months = []
    while (y, m) <= (ey, em):
        months.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            m = 1
            y += 1
    return months


def forward_fill(series: dict, months: list) -> dict:
    """분기 지표(GDP)를 월별로 앞으로 채움."""
    filled, last_val = {}, None
    for mo in months:
        if mo in series:
            last_val = series[mo]
        filled[mo] = last_val
    return filled


def main():
    if not API_KEY:
        print("FRED_API_KEY 환경변수가 없습니다.", file=sys.stderr)
        sys.exit(1)

    today = datetime.date.today()
    start = (today.replace(year=today.year - YEARS_BACK)).isoformat()
    end = today.isoformat()

    raw = {key: fetch_series(cfg["id"], cfg["units"], start) for key, cfg in SERIES.items()}
    months = month_range(start[:7], end[:7])
    raw["gdp"] = forward_fill(raw["gdp"], months)

    existing_pmi = {}
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            for r in json.load(f):
                if r.get("pmi") is not None:
                    existing_pmi[r["m"]] = r["pmi"]

    records = []
    for mo in months:
        if mo not in raw["stock"] and mo not in raw["unemp"]:
            continue  # 아직 데이터 없는 미래월 등은 건너뜀
        records.append({
            "m": mo,
            "stock": raw["stock"].get(mo),
            "pmi": existing_pmi.get(mo),
            "ip": raw["ip"].get(mo),
            "retail": raw["retail"].get(mo),
            "gdp": raw["gdp"].get(mo),
            "unemp": raw["unemp"].get(mo),
        })

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"{len(records)}개월 데이터 저장 완료 ({months[0]} ~ {months[-1]})")


if __name__ == "__main__":
    main()
