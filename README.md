# 시장지표 자동 갱신 대시보드

매달 FRED(세인트루이스 연준) API에서 5개 지표의 **최근 5년치 전체**를 가져와 `data.json`을 새로 만들고,
`index.html`이 그 값을 읽어 국면을 자동 판정합니다. PMI만 ISM 발표(매월 첫 영업일경) 후 수동 입력하세요.

**새 기능**: 대시보드에서 지표 카드를 클릭하면 아래에 3년 / 5년 / 전체 추이 그래프가 펼쳐집니다.

## 폴더 구성

```
├── index.html                          대시보드 (GitHub Pages 진입 파일)
├── data.json                           지표 데이터 (자동 갱신됨)
├── scripts/fetch_indicators.py         FRED API 수집 스크립트
└── .github/workflows/update-indicators.yml   매월 자동 실행 워크플로우
```

## 설정 방법 (최초 1회, 약 15분)

**1) FRED API 키 발급**
https://fred.stlouisfed.org/docs/api/api_key.html 에서 무료 가입 후 즉시 발급됩니다.

**2) GitHub 저장소 만들기**
- 이미 GitHub Pages로 쓰시던 저장소가 있다면 그 저장소에 이 폴더(`automation/` 안의 파일들)를
  루트에 그대로 복사해 넣으세요.
- 새로 시작하신다면 github.com에서 New repository → 이름 정하고 Public으로 생성 → 이 폴더 안의
  파일을 그대로 업로드(드래그 앤 드롭 가능) 또는 `git push`로 올리세요.

**3) GitHub Pages 활성화**
저장소 > Settings > Pages > Build and deployment > Source를 **"Deploy from a branch"**로 두고
Branch를 `main` / `(root)`로 선택 후 저장. 몇 분 뒤 `https://[아이디].github.io/[저장소명]/`으로 접속되면 성공.

**4) API 키를 GitHub Secret으로 등록**
저장소 > Settings > Secrets and variables > Actions > New repository secret
- Name: `FRED_API_KEY`
- Value: 1번에서 발급받은 키

**5) 첫 실행으로 5년치 데이터 백필**
저장소 > Actions 탭 > "경기 지표 자동 갱신" 워크플로우 선택 > **Run workflow** 버튼 클릭.
1~2분 후 `data.json`이 5년치 데이터로 가득 채워진 커밋이 생깁니다. 이후로는 매월 25일 자동 실행.

## 매달 해야 하는 유일한 수동 작업 — PMI 입력

ISM 제조업 PMI가 발표되면(매월 첫 영업일경, 또는 트레이딩 이코노믹스에서 확인) `data.json`을
열어 해당 월의 `"pmi": null` 을 실제 값으로 바꾸고 커밋하세요. 예:

```json
{"m": "2026-06", "stock": 7480, "pmi": 55.8, "ip": 1.9, "retail": 7.1, "gdp": 2.8, "unemp": 4.2}
```

## 자동 갱신 주기를 바꾸고 싶다면

`.github/workflows/update-indicators.yml`의 `cron: '0 0 25 * *'` 값을 수정하세요.
(예: 매주 월요일 = `'0 0 * * 1'`)

## 로컬에서 미리 보기

`index.html`을 더블클릭해서 바로 열면 `data.json`을 fetch하지 못해(브라우저 보안 정책) 예시 데이터로 표시됩니다.
정확히 보려면 터미널에서 이 폴더로 이동 후 `python3 -m http.server 8000` 실행 → 브라우저에서 `localhost:8000` 접속.
GitHub Pages에 배포하면 이 문제 없이 정상 작동합니다.
