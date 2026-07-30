import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# 1. 페이지 설정 및 주식 거래소 전용 CSS 커스텀
st.set_page_config(
    page_title="MOVIE X - 영화 주식 거래소",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    /* 거래소 다크 스타일 커스텀 */
    .stApp {
        background-color: #0d1117;
        color: #e6edf3;
    }
    .stock-card {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .up-color { color: #ff4d4f !important; font-weight: bold; } /* 한국 주식 빨간색=상승 */
    .down-color { color: #1890ff !important; font-weight: bold; } /* 한국 주식 파란색=하락 */
    .ticker-header {
        font-size: 24px;
        font-weight: 800;
        margin-bottom: 4px;
    }
</style>
""", unsafe_allow_html=True)

# Secrets 키 확인
if "KOBIS_KEY" not in st.secrets:
    st.error("Secrets에 KOBIS_KEY가 설정되지 않았습니다.")
    st.stop()

KOBIS_KEY = st.secrets["KOBIS_KEY"]

# 2. 사이드바 - 날짜 선택 및 검색
st.sidebar.image("https://img.icons8.com/color/96/bullish.png", width=60)
st.sidebar.title("MOVIE X 거래소")
st.sidebar.caption("K-BOX 실시간 영화 시세 & 분석 시스템")

yesterday = (datetime.now(ZoneInfo("Asia/Seoul")) - timedelta(days=1)).date()

selected_date = st.sidebar.date_input(
    "📅 개장일(조회일자)",
    value=yesterday,
    max_value=yesterday
)

target_dt = selected_date.strftime("%Y%m%d")

# 3. API 데이터 로드
@st.cache_data(ttl=600)
def fetch_boxoffice(date_str):
    url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
    try:
        res = requests.get(url, params={"key": KOBIS_KEY, "targetDt": date_str}, timeout=10)
        res.raise_for_status()
        data = res.json()
        return data.get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])
    except Exception:
        return []

raw_data = fetch_boxoffice(target_dt)

if not raw_data:
    st.warning("⚠️ 해당 날짜는 거래소 휴장일(데이터 집계 전)입니다.")
    st.stop()

df = pd.DataFrame(raw_data)

# 데이터 가공
for col in ["rank", "audiCnt", "audiAcc", "scrnCnt", "showCnt", "audiChange"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col])

# 가상의 주가 생성 (관객수와 스크린 효율을 조합하여 '1주당 가치(원)' 계산)
df["주가(원)"] = (df["audiCnt"] * 10 + (df["audiCnt"] / df["scrnCnt"].replace(0, 1)) * 1000).round(-1).astype(int)
df["전일대비_원"] = (df["주가(원)"] * (df["audiChange"] / 100)).round(-1).astype(int)

# 4. 상단 전광판 (Ticker)
st.markdown("### 🔔 실시간 마켓 보드")
ticker_cols = st.columns(5)

for idx, row in df.head(5).iterrows():
    change_val = row["audiChange"]
    color_class = "up-color" if change_val >= 0 else "down-color"
    sign = "▲" if change_val >= 0 else "▼"
    
    with ticker_cols[idx]:
        st.markdown(f"""
        <div class="stock-card">
            <div style="font-size:12px; color:#8b949e;">No.{row['rank']} 종목</div>
            <div style="font-weight:bold; font-size:15px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{row['movieNm']}</div>
            <div style="font-size:18px; font-weight:800; margin-top:4px;">{row['주가(원)']:,} 원</div>
            <div class="{color_class}" style="font-size:13px;">{sign} {abs(change_val):.1f}%</div>
        </div>
        """, unsafe_allow_html=True)

st.divider()

# 5. 메인 레이아웃 (좌: 종목 차트/상세 | 우: 거래소 시세표 & 종목 토론방)
col_left, col_right = st.columns([7, 5])

with col_left:
    st.subheader("📊 종목 선택 및 차트 분석")
    
    selected_movie = st.selectbox(
        "분석할 영화 종목을 선택하세요",
        options=df["movieNm"].tolist(),
        index=0
    )
    
    movie_info = df[df["movieNm"] == selected_movie].iloc[0]
    
    # AI 투자의견 분석 알고리즘
    scrn_efficiency = movie_info["audiCnt"] / max(movie_info["scrnCnt"], 1)
    change = movie_info["audiChange"]
    
    if change > 15 and scrn_efficiency > 100:
        opinion = "🔥 강력 매수 (Strong Buy)"
        op_color = "#ff4d4f"
        reason = "관객증가율이 폭발적이며 스크린 대비 효율이 높아 입소문 떡상이 확정적입니다."
    elif change >= 0:
        opinion = "📈 매수 (Buy)"
        op_color = "#f50"
        reason = "우상향 흐름을 유지 중이며 무난하게 관객수를 확보하고 있습니다."
    elif change > -20:
        opinion = "⚖️ 중립 / 관망 (Hold)"
        op_color = "#faad14"
        reason = "흥행세가 주춤하는 구간입니다. 주말 관객 수치를 보고 판단하세요."
    else:
        opinion = "🚨 매도 / 손절 (Sell)"
        op_color = "#1890ff"
        reason = "관객수가 급감하고 있으며 조기 하강 국면에 접어들었습니다."

    # 선택 종목 헤더
    st.markdown(f"""
    <div style="background:#161b22; padding:16px; border-radius:8px; border-left: 5px solid {op_color}; margin-bottom:15px;">
        <span class="ticker-header">{movie_info['movieNm']}</span>
        <span style="background:{op_color}; color:white; padding:3px 10px; border-radius:12px; font-size:12px; font-weight:bold; margin-left:10px;">{opinion}</span>
        <div style="color:#8b949e; margin-top:8px; font-size:14px;">💡 <b>애널리스트 리포트:</b> {reason}</div>
    </div>
    """, unsafe_allow_html=True)

    # 가상 주가 캔들스틱(봉차트) 생성기
    st.markdown("##### 🕯️ 최근 7일간의 가상 주가 봉차트 (Candlestick)")
    
    # 7일간의 가상 주가 동향 생성
    dates = [(selected_date - timedelta(days=i)).strftime("%m/%d") for i in range(6, -1, -1)]
    base_price = movie_info["주가(원)"]
    
    # 변동성 주가 패턴 연산
    np.random.seed(hash(selected_movie) % 1000)
    prices = [max(1000, int(base_price * (1 + (i - 3) * 0.08 + np.random.uniform(-0.05, 0.05)))) for i in range(7)]
    prices[-1] = base_price  # 마지막 날은 현재 데이터
    
    opens = [p * np.random.uniform(0.96, 1.02) for p in prices]
    # (수정 완료) 문법 오류 수정 부분
    highs = [max(p, o) * np.random.uniform(1.01, 1.05) for p, o in zip(prices, opens)]
    lows = [min(p, o) * np.random.uniform(0.95, 0.99) for p, o in zip(prices, opens)]
    
    fig = go.Figure(data=[go.Candlestick(
        x=dates,
        open=opens, high=highs, low=lows, close=prices,
        increasing_line_color='#ff4d4f', decreasing_line_color='#1890ff'
    )])
    
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0d1117",
        plot_bgcolor="#161b22",
        margin=dict(l=20, r=20, t=20, b=20),
        height=320,
        xaxis_rangeslider_visible=False
    )
    st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.subheader("🏛️ K-BOX 시세 리스트")
    
    # 시세표 데이터프레임
    display_df = df[["rank", "movieNm", "주가(원)", "audiChange", "audiAcc"]].copy()
    display_df.columns = ["순위", "종목명", "주가", "등락률(%)", "누적관객"]
    
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=280,
        column_config={
            "순위": st.column_config.NumberColumn("순위", format="%d위"),
            "주가": st.column_config.NumberColumn("주가", format="%d 원"),
            "등락률(%)": st.column_config.NumberColumn("등락률", format="%.1f%%"),
            "누적관객": st.column_config.NumberColumn("누적관객", format="%d 명"),
        }
    )
    
    st.divider()
    
    # 6. 주식 종목 토론방 (커뮤니티 인터랙션)
    st.subheader(f"💬 [{selected_movie}] 종목 토론방")
    
    # 세션 상태로 댓글 저장
    if "comments" not in st.session_state:
        st.session_state.comments = {
            selected_movie: [
                {"user": "개미1호", "text": "이 영화 주말에 관객수 떡상할 듯 ㅋㅋㅋ 층층이 매수 들어간다!", "type": "🔴 매수"},
                {"user": "영진위탐정", "text": "스크린 수 대비 관객수 낮아서 내일 하강 곡선 그릴 확률 80%", "type": "🔵 매도"}
            ]
        }
    
    if selected_movie not in st.session_state.comments:
        st.session_state.comments[selected_movie] = [
            {"user": "익명 개미", "text": f"{selected_movie} 종목 가즈아!", "type": "🔴 매수"}
        ]
        
    # 댓글 입력
    with st.form(key="comment_form", clear_on_submit=True):
        c_col1, c_col2 = st.columns([3, 1])
        with c_col1:
            user_text = st.text_input("의견을 남겨주세요", placeholder="예: 주말에 친구들이랑 보러 감!")
        with c_col2:
            position = st.selectbox("포지션", ["🔴 매수", "🔵 매도"])
        
        submit = st.form_submit_button("토론 참여")
        
        if submit and user_text:
            st.session_state.comments[selected_movie].insert(0, {
                "user": f"주식개미_{np.random.randint(100, 999)}",
                "text": user_text,
                "type": position
            })
            st.rerun()

    # 댓글 리스트 출력
    for comment in st.session_state.comments[selected_movie][:5]:
        badge_color = "#ff4d4f" if "매수" in comment["type"] else "#1890ff"
        st.markdown(f"""
        <div style="background:#161b22; padding:8px 12px; border-radius:6px; margin-bottom:6px; font-size:13px;">
            <span style="color:{badge_color}; font-weight:bold;">[{comment['type']}]</span> 
            <b>{comment['user']}</b>: {comment['text']}
        </div>
        """, unsafe_allow_html=True)
