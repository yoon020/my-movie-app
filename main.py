import pandas as pd
import requests
import streamlit as st
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

st.set_page_config(page_title="박스오피스 대시보드", page_icon="🎬", layout="wide")
st.title("🎬 박스오피스 대시보드")

# 비밀 금고에서 인증키 꺼내기
if "KOBIS_KEY" not in st.secrets:
    st.error("Secrets에 KOBIS_KEY가 설정되지 않았습니다.")
    st.stop()

KOBIS_KEY = st.secrets["KOBIS_KEY"]

# 1. 날짜 선택 기능 (가장 늦은 날짜는 어제까지로 제한)
yesterday = (datetime.now(ZoneInfo("Asia/Seoul")) - timedelta(days=1)).date()

selected_date = st.date_input(
    "조회할 날짜를 선택하세요",
    value=yesterday,
    max_value=yesterday,
    help="박스오피스는 어제 날짜 데이터까지 조회할 수 있습니다."
)

target_dt = selected_date.strftime("%Y%m%d")
st.caption(f"조회 기준일: {selected_date.strftime('%Y년 %m월 %d일')}")

# 2. KOBIS API 데이터 요청
url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"

try:
    res = requests.get(url, params={"key": KOBIS_KEY, "targetDt": target_dt}, timeout=10)
    res.raise_for_status()
except requests.exceptions.RequestException as e:
    st.error(f"요청이 실패했습니다: {e}")
    st.stop()

data = res.json()

# KOBIS 인증키 에러 예외 처리
if "faultInfo" in data:
    st.error("인증키가 올바르지 않습니다. 금고(Secrets)의 KOBIS_KEY를 확인해 주세요.")
    st.stop()

# 3. 데이터가 비어있는 경우 안내 문구 처리
box_list = data.get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])
if not box_list:
    st.warning("그날은 아직 집계 전입니다")
    st.stop()

df = pd.DataFrame(box_list)

# 글자로 온 숫자들을 진짜 숫자로 변환
num_cols = ["rank", "audiCnt", "audiAcc", "scrnCnt", "showCnt", "rankInten"]
for col in num_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col])

df = df.sort_values("rank").reset_index(drop=True)

# 4. 데이터 가공 (순위 증감 화살표 & 100만 관객 트로피 이모지)
def format_rank_inten(row):
    if row.get("rankOldAndNew") == "NEW":
        return "NEW"
    
    inten = row.get("rankInten", 0)
    if inten > 0:
        return f"🔺 {inten}"  # 상승 (빨간 위 화살표)
    elif inten < 0:
        return f"🔹 {abs(inten)}"  # 내림 (파란 아래 화살표)
    else:
        return "-"

def format_movie_name(row):
    name = row["movieNm"]
    # 누적 관객 100만 명 이상 시 트로피 붙이기
    if row["audiAcc"] >= 1_000_000:
        return f"{name} 🏆"
    return name

df["순위변동"] = df.apply(format_rank_inten, axis=1)
df["display_movieNm"] = df.apply(format_movie_name, axis=1)

# 5. 1위 영화 지표 카드 세 장
top = df.iloc[0]
c1, c2, c3 = st.columns(3)
c1.metric("1위 영화", top["display_movieNm"])
c2.metric("당일 관객수", f"{top['audiCnt']:,}명")
c3.metric("누적 관객수", f"{top['audiAcc']:,}명")

st.markdown("---")

# 6. 표 구성 및 한국어 열 정리
table = df[["rank", "순위변동", "display_movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]].copy()
table.columns = ["순위", "전일대비", "영화명", "개봉일", "관객수", "누적관객", "스크린수"]

st.subheader(f"📋 {selected_date.strftime('%Y-%m-%d')} 박스오피스 TOP 10")
st.dataframe(
    table,
    use_container_width=True,
    hide_index=True,
    column_config={
        "순위": st.column_config.NumberColumn("순위", format="%d위"),
        "관객수": st.column_config.NumberColumn("관객수", format="%d명"),
        "누적관객": st.column_config.NumberColumn("누적관객", format="%d명"),
        "스크린수": st.column_config.NumberColumn("스크린수", format="%d개"),
    }
)

# 7. 관객수 상위 5편 바 차트
st.subheader("📈 관객수 상위 5편")
top5 = table.sort_values("관객수", ascending=False).head(5)
st.bar_chart(top5.set_index("영화명")["관객수"])
