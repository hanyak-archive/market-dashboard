"""
구글 뉴스 RSS에서 경제 기사 헤드라인을 수집해 '경기 국면 서사 신호'를 키워드 룰로 분석,
news_signals.json을 생성한다. API 키 불필요.

신호 체계 (백창규 센터장 3부작 프레임 기반):
  trap_growth_end  🔴 성장말기 함정: 후행지표 낙관 + 주가 하락 + 저가매수 유혹 서사
  recovery_pessim  🟢 회복기 비관(=역발상 기회): 나홀로 상승/거품론 서사
  overheat         🟡 과열: 빚투/영끌/차트분석 열풍 서사
  slowdown         🟠 둔화: 소비 위축/재고/폐업 서사

실행: python scripts/fetch_news.py
"""
import json
import os
import re
import datetime
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "news_signals.json")
HISTORY_DAYS = 30   # 신호 히스토리 보관 일수
MAX_HEADLINES = 12  # 대시보드에 보여줄 최근 매칭 기사 수

QUERIES = [
    "미국 경제",
    "미국 증시",
    "실업률 성장률",
    "코스피 전망",
    "연준 금리",
]

# 구글 뉴스가 차단될 경우를 대비한 언론사 공식 RSS (경제 섹션)
DIRECT_FEEDS = [
    "https://www.mk.co.kr/rss/30100041/",            # 매일경제 경제
    "https://rss.hankyung.com/feed/economy.xml",     # 한국경제 경제
    "https://www.yonhapnewstv.co.kr/category/news/economy/feed/",  # 연합뉴스TV 경제
]

# ── 특수 신호 룰 (국면 전환 마커) ──────────────────────────
# 각 신호는 그룹의 조합(AND)으로 판정. 그룹 안은 OR.
RULES = {
    "trap_growth_end": {
        "label": "🔴 성장말기 함정 서사",
        "desc": "후행지표 낙관+주가 하락+저가매수 유혹 — 성장→둔화 전환기 전형 패턴",
        "groups": [
            ["실업률", "고용 호조", "고용 견조", "견조한 고용", "탄탄한 고용", "성장률", "펀더멘털 양호", "양호한 펀더멘털", "경제 탄탄", "탄탄한 경제", "소비 견조", "견조한 소비"],
            ["하락", "조정", "급락", "약세", "밀렸", "부진"],
            ["저가 매수", "매수 기회", "밸류에이션", "저평가", "바닥", "줍줍", "기회"],
        ],
    },
    "recovery_pessim": {
        "label": "🟢 회복기 비관 서사 (역발상 기회)",
        "desc": "나홀로 상승·거품론·실물 괴리 — 회복 초입에 나오는 전형 패턴",
        "groups": [
            ["나홀로 상승", "거품", "버블", "실물과 괴리", "펀더멘털 부진", "이유 없는 상승", "과열 우려 속 상승"],
        ],
    },
    "overheat": {
        "label": "🟡 과열 서사",
        "desc": "빚투·영끌·차트 열풍 — 성장국면 끄트머리의 도파민 신호",
        "groups": [
            ["빚투", "영끌", "신용융자", "레버리지 급증", "돈복사", "차트 분석", "너도나도", "묻지마 투자", "개미 순매수 사상"],
        ],
    },
    "slowdown": {
        "label": "🟠 둔화 서사",
        "desc": "소비 위축·재고·폐업 — 둔화 국면 진입 신호",
        "groups": [
            ["소비 위축", "지갑 닫", "재고 급증", "감산", "폐업", "구조조정", "소비 절벽", "불황형"],
        ],
    },
}

# ── 국면별 서사 키워드 (단순 OR 매칭, 국면 점수 집계용) ──────
# 기사 헤드라인이 어느 국면의 '전형적 이야기'를 하고 있는지 측정
PHASE_RULES = {
    "회복": {
        "label": "회복 서사",
        "keywords": ["금리 인하", "인하 기대", "바닥 통과", "반등 조짐", "회복 조짐", "저점 통과",
                     "유동성 회복", "긴축 종료", "완화 전환", "경기 부양", "반등세", "회복세 진입"],
    },
    "성장": {
        "label": "성장 서사",
        "keywords": ["사상 최고", "신고가", "최고치 경신", "호실적", "어닝 서프라이즈", "실적 잔치",
                     "고용 호조", "소비 호조", "매출 급증", "역대 최대", "훈풍", "질주", "랠리",
                     "명품 매출", "리셀", "완판"],
    },
    "둔화": {
        "label": "둔화 서사",
        "keywords": ["소비 위축", "지갑 닫", "재고 급증", "감산", "판매 부진", "성장 둔화", "경기 둔화",
                     "수요 둔화", "실적 둔화", "침체 우려", "경기 우려", "방어주", "소비 절벽",
                     "고금리 부담", "긴축 장기화"],
    },
    "침체": {
        "label": "침체 서사",
        "keywords": ["감원", "정리해고", "구조조정", "파산", "부도", "폐업 급증", "유동성 위기",
                     "신용 경색", "긴급 지원", "폭락", "패닉", "투매", "경기 침체 진입", "리세션",
                     "실업 급증", "연쇄 도산"],
    },
}


def fetch_rss_url(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        xml_data = resp.read()
    root = ET.fromstring(xml_data)
    items = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        if title:
            items.append({"title": title, "link": link, "pub": pub})
    return items


def fetch_rss(query: str):
    url = ("https://news.google.com/rss/search?q="
           + urllib.parse.quote(query)
           + "&hl=ko&gl=KR&ceid=KR:ko")
    return fetch_rss_url(url)


def match_signal(text: str, rule: dict):
    """모든 그룹에서 최소 1개 키워드가 매칭되어야 신호 성립 (그룹 간 AND).
    성립 시 매칭된 키워드 리스트 반환, 아니면 None."""
    matched = []
    for group in rule["groups"]:
        hits = [kw for kw in group if kw in text]
        if not hits:
            return None
        matched.extend(hits)
    return matched


def main():
    today = datetime.date.today().isoformat()

    # 기사 수집 (구글 뉴스 + 언론사 직접 피드, 중복 제거)
    seen, articles = set(), []
    def add_items(items):
        for it in items:
            key = re.sub(r"\s+", "", it["title"])[:60]
            if key not in seen:
                seen.add(key)
                articles.append(it)

    for q in QUERIES:
        try:
            add_items(fetch_rss(q))
        except Exception as e:
            print(f"[warn] 구글뉴스 '{q}' 수집 실패: {e}")
    for feed in DIRECT_FEEDS:
        try:
            add_items(fetch_rss_url(feed))
        except Exception as e:
            print(f"[warn] 직접피드 수집 실패 ({feed[:40]}...): {e}")

    # 특수 신호 매칭
    counts = {k: 0 for k in RULES}
    flagged = []
    for art in articles:
        for sig, rule in RULES.items():
            kws = match_signal(art["title"], rule)
            if kws:
                counts[sig] += 1
                flagged.append({"signal": sig, "label": rule["label"],
                                "title": art["title"], "link": art["link"],
                                "matched": kws})
                break  # 기사 하나당 특수 신호 하나만

    # 국면 서사 점수 집계 (기사 하나가 여러 국면 키워드를 담을 수 있음)
    phase_scores = {k: 0 for k in PHASE_RULES}
    phase_examples = {k: [] for k in PHASE_RULES}
    for art in articles:
        for ph, rule in PHASE_RULES.items():
            hits = [kw for kw in rule["keywords"] if kw in art["title"]]
            if hits:
                phase_scores[ph] += 1
                if len(phase_examples[ph]) < 3:
                    phase_examples[ph].append({"title": art["title"], "link": art["link"],
                                               "matched": hits})

    total_phase_hits = sum(phase_scores.values())
    news_phase = max(phase_scores, key=phase_scores.get) if total_phase_hits > 0 else None

    # 기존 히스토리 로드 후 오늘치 갱신
    history = []
    if os.path.exists(OUT_PATH):
        try:
            with open(OUT_PATH, encoding="utf-8") as f:
                history = json.load(f).get("history", [])
        except Exception:
            history = []
    history = [h for h in history if h["date"] != today]
    history.append({"date": today, **counts, "phase_scores": phase_scores})
    cutoff = (datetime.date.today() - datetime.timedelta(days=HISTORY_DAYS)).isoformat()
    history = sorted([h for h in history if h["date"] >= cutoff], key=lambda h: h["date"])

    out = {
        "updated": today,
        "scanned": len(articles),
        "counts": counts,
        "rules": {k: {"label": v["label"], "desc": v["desc"]} for k, v in RULES.items()},
        "flagged": flagged[:MAX_HEADLINES],
        "phase_scores": phase_scores,
        "news_phase": news_phase,
        "phase_examples": phase_examples,
        "history": history,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"기사 {len(articles)}건 스캔")
    print(f"특수 신호: {counts}")
    print(f"국면 서사 점수: {phase_scores} -> 기사가 가리키는 국면: {news_phase}")


if __name__ == "__main__":
    main()
