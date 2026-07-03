"""
Stooq 무료 CSV에서 ETF 월간 종가를 받아 국면 로테이션 검증용 상대강도 비율을 계산,
markets.json을 생성한다. API 키 불필요.

비율 체계 (백창규 센터장 로테이션 표 기반):
  em_us     EEM/SPY   : 이머징 vs 미국       (성장 국면에 상승해야 정상)
  nonus_us  EFA/SPY   : 선진국(미국外) vs 미국
  qqq_spy   QQQ/SPY   : 나스닥 vs S&P500     (회복 국면에 상승)
  iwm_spy   IWM/SPY   : 러셀2000 vs S&P500   (성장 국면에 상승)
  vug_vtv   VUG/VTV   : 성장주 vs 가치주      (회복 상승 / 둔화 하락)
  dia_spy   DIA/SPY   : 다우 vs S&P500       (둔화 국면에 상승)
  usd       UUP       : 달러 (절대 방향)      (성장 약세 / 둔화·침체 강세)

실행: python scripts/fetch_markets.py
"""
import json
import os
import csv
import io
import urllib.request

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "markets.json")
MONTHS_KEEP = 14  # 최근 14개월 보관 (12개월 비교 + 여유)

TICKERS = ["spy.us", "eem.us", "efa.us", "qqq.us", "iwm.us", "vug.us", "vtv.us", "dia.us", "uup.us"]

RATIOS = {
    "em_us":    {"label": "이머징 / 미국 (EEM/SPY)",      "num": "eem.us", "den": "spy.us"},
    "nonus_us": {"label": "선진국(미국外) / 미국 (EFA/SPY)", "num": "efa.us", "den": "spy.us"},
    "qqq_spy":  {"label": "나스닥 / S&P500 (QQQ/SPY)",    "num": "qqq.us", "den": "spy.us"},
    "iwm_spy":  {"label": "러셀2000 / S&P500 (IWM/SPY)",  "num": "iwm.us", "den": "spy.us"},
    "vug_vtv":  {"label": "성장주 / 가치주 (VUG/VTV)",     "num": "vug.us", "den": "vtv.us"},
    "dia_spy":  {"label": "다우 / S&P500 (DIA/SPY)",      "num": "dia.us", "den": "spy.us"},
    "usd":      {"label": "달러 (UUP)",                    "num": "uup.us", "den": None},
}


def fetch_monthly_closes(ticker: str) -> dict:
    """월키(YYYY-MM) -> 종가"""
    url = f"https://stooq.com/q/d/l/?s={ticker}&i=m"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        text = resp.read().decode("utf-8", errors="replace")
    out = {}
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        date, close = row.get("Date", ""), row.get("Close", "")
        if len(date) >= 7 and close not in ("", "N/A"):
            try:
                out[date[:7]] = float(close)
            except ValueError:
                pass
    return out


def pct_change(series: list, back: int):
    """마지막 값 대비 back개월 전 변화율(%). 데이터 부족 시 None."""
    if len(series) <= back or series[-1] is None or series[-1 - back] in (None, 0):
        return None
    return round((series[-1] / series[-1 - back] - 1) * 100, 2)


def direction(chg):
    if chg is None:
        return "?"
    if chg > 1.0:
        return "↑"
    if chg < -1.0:
        return "↓"
    return "→"


def main():
    prices = {}
    for t in TICKERS:
        try:
            prices[t] = fetch_monthly_closes(t)
            print(f"[ok] {t}: {len(prices[t])}개월")
        except Exception as e:
            print(f"[warn] {t} 수집 실패: {e}")
            prices[t] = {}

    # 공통 월 목록 (SPY 기준 최근 MONTHS_KEEP개월)
    base_months = sorted(prices.get("spy.us", {}).keys())[-MONTHS_KEEP:]
    if not base_months:
        print("SPY 데이터가 없어 중단합니다. (첫 실행 실패 시 소스 점검 필요)")
        return

    ratios_out = {}
    for key, cfg in RATIOS.items():
        num, den = prices.get(cfg["num"], {}), prices.get(cfg["den"], {}) if cfg["den"] else None
        series = []
        for m in base_months:
            n = num.get(m)
            if cfg["den"] is None:
                series.append(round(n, 4) if n else None)
            else:
                d = den.get(m)
                series.append(round(n / d, 4) if (n and d) else None)
        chg3, chg6 = pct_change(series, 3), pct_change(series, 6)
        ratios_out[key] = {
            "label": cfg["label"],
            "months": base_months,
            "values": series,
            "chg3m": chg3,
            "chg6m": chg6,
            "dir": direction(chg3),
        }

    out = {"updated": base_months[-1], "ratios": ratios_out}
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("저장 완료:", {k: v["dir"] for k, v in ratios_out.items()})


if __name__ == "__main__":
    main()
