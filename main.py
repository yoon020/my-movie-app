import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# 1. 페이지 설정 (주식 모니터 느낌의 어두운 테마/스타일)
st.set_page_config(page_title="K-BOX 영화 거래소", page_icon="📈", layout="wide")

st.markdown("""
    <style>
    .metric-card {
        background-color: #1e1e1e;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #333;
    }
    .status-badge {
        padding: 4px 8px;
        border-radius: 5px;
        font-weight: bold;
        font-size: 13px;
    }
    </style>
""", unsafe_allow_html=True)

st.title("📈 K-BOX 영화 거래소 (Movie Stock Exchange)")
st.caption("어제 자 극장가 데이터를 실시간 주식 시장처럼 분석해 드립니다.")

# Secrets 키 확인
if "KOBIS_KEY" not in st.secrets:
    st.error("Secrets에 KOBIS_KEY가 설정되지 않았습니다.")
    st.stop()

KOBIS_KEY = st.secrets["KOBIS_KEY"]

# 2. 날짜 선택기 (기본값: 어제)
yesterday = (datetime.now(ZoneInfo("Asia/Seoul")) - timedelta(days=1)).date()

col_date, _ = st.columns([1, 2])
with col_date:
    selected_date = st.date_input(
        "📅 개장일(조회 날짜) 선택",
        value=yesterday,
        max_value=yesterday,
        help="박스오피스는 어제 날짜 데이터까지 집계되어 개장됩니다."
    )

target_dt = selected_date.strftime("%Y%m%d")

# 3. KOBIS API 데이터 요청
url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"

try:
    res = requests.get(url, params={"key": KOBIS_KEY, "targetDt": target_dt}, timeout=10)
    res.raise_for_status()
except requests.exceptions.RequestException as e:
    st.error(f"거래소 통신 오류: {e}")
    st.stop()

data = res.json()

if "faultInfo" in data:
    st.error("인증키 오류가 발생했습니다.")
    st.stop()

box_list = data.get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])
if not box_list:
    st.warning("⚠️ 해당 날짜는 거래소 휴장일(집계 전)입니다.")
    st.stop()

df = pd.DataFrame(box_list)

# 숫자형 변환
num_cols = ["rank", "audiCnt", "audiAcc", "scrnCnt", "showCnt", "rankInten", "audiChange"]
for col in num_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col])

df = df.sort_values("rank").reset_index(drop=True)

# 4. 주식 시장 스타일 데이터 가공
def analyze_stock(row):
    audi_change_rate = row.get("audiChange", 0)  # 전일 대비 관객수 증감 비율(%)
    is_new = row.get("rankOldAndNew") == "NEW"
    rank = row["rank"]
    
    # 종목 상태 분석 (태그 지정)
    if is_new:
        status = "🆕 신규 상장 (IPO)"
        status_color = "#1f77b4"
    elif rank == 1:
        status = "🔥 시장 대장주"
        status_color = "#d62728"
    elif audi_change_rate > 15:
        status = "🚀 입소문 떡상주"
        status_color = "#ff7f0e"
    elif audi_change_rate < -20:
        status = "🚨 상장폐지(종영) 위기"
        status_color = "#7f7f7f"
    else:
        status = "⚖️ 보합세 유지"
        status_color = "#2ca02c"
        
    return pd.Series([status, status_color])

df[["종목상태", "상태색상"]] = df.apply(analyze_stock, axis=1)

# 5. 거래소 종합 지수 (Market Summary)
total_daily_audi = df["audiCnt"].sum()
top_stock = df.iloc[0]

st.markdown("---")
st.markdown("### 📊 오늘의 극장가 주식 시장 요약")

m1, m2, m3, m4 = st.columns(4)
m1.metric("오늘의 시장 전체 거래량", f"{total_daily_audi:,} 관객")
m2.metric("대장주 (1위 종목)", top_stock["movieNm"])
m3.metric("대장주 일일 거래량", f"{top_stock['audiCnt']:,} 명", f"{top_stock.get('audiChange', 0)}% 전일대비")
m4.metric("대장주 누적 시가총액", f"{top_stock['audiAcc']:,} 명")

st.markdown("---")

# 6. 상장 종목 시세표 (박스오피스 TOP 10)
st.subheader("🏛️ K-BOX 상장 종목 시세표")

table_df = df[["rank", "movieNm", "audiCnt", "audiChange", "audiAcc", "scrnCnt", "종목상태"]].copy()
table_df.columns = ["순위", "종목명(영화)", "일일 거래량(관객수)", "전일대비 등락률(%)", "누적 시가총액(누적관객)", "상영 스크린수", "종목 상태"]

st.dataframe(
    table_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "순위": st.column_config.NumberColumn("순위", format="%d위"),
        "일일 거래량(관객수)": st.column_config.NumberColumn("일일 거래량(관객수)", format="%d 명"),
        "전일대비 등락률(%)": st.column_config.NumberColumn("전일대비 등락률", format="%.1f%%"),
        "누적 시가총액(누적관객)": st.column_config.NumberColumn("누적 시가총액(누적관객)", format="%d 명"),
        "상영 스크린수": st.column_config.NumberColumn("상영 스크린수", format="%d 개"),
    }
)

st.markdown("---")

# 7. 개별 종목 정밀 진단 및 떡상 예측기
st.subheader("🔍 관심 종목 떡상 예측 진단서")

selected_movie = st.selectbox("진단할 종목(영화)을 선택하세요:", df["movieNm"].tolist())
movie_data = df[df["movieNm"] == selected_movie].iloc[0]

col_left, col_right = st.columns([1, 1])

with col_left:
    st.markdown(f"#### 🎬 [{movie_data['movieNm']}] 진단 결과")
    st.write(f"• **현재 순위:** {movie_data['rank']}위")
    st.write(f"• **현재 상태:** {movie_data['종목상태']}")
    st.write(f"• **개봉일:** {movie_data['openDt']}")
    st.write(f"• **누적 관객수:** {movie_data['audiAcc']:,} 명")
    
    # 천만 관객 가능성 진단 로직
    acc = movie_data["audiAcc"]
    change = movie_data.get("audiChange", 0)
    
    st.markdown("##### 🔮 AI 종목 전망 예측")
    if acc >= 10_000_000:
        st.success("🎉 **[신화 달성]** 이미 천만 관객을 돌파한 전설적인 대장주입니다!")
    elif acc >= 3_000_000 or (acc >= 1_000_000 and change > 10):
        st.info("🚀 **[상승 우상향]** 입소문과 화제성이 살아있어 추가 흥행 고지 달성이 유력합니다.")
    elif change < -30:
        st.warning("⚠️ **[하강 국면]** 관객 이탈이 가빠지고 있습니다. 조기 상장폐지(종영) 가능성에 유의하세요.")
    else:
        st.write("⚖️ **[보합세]** 무난한 흐름을 유지하고 있습니다.")

with col_right:
    # TOP 5 종목 거래량(관객수) 점유율 차트
    st.markdown("#### 🍩 상위 5개 종목 거래량(관객) 점유율")
    top5 = df.head(5)
    
    fig = px.pie(
        top5,
        names="movieNm",
        values="audiCnt",
        hole=0.4,
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    fig.update_traces(textinfo="percent+label")
    fig.update_layout(margin=dict(t=20, b=20, l=10, r=10), showlegend=False, height=280)
    
    st.plotly_chart(fig, use_container_width=True)
