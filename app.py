

import streamlit as st
import pandas as pd
import requests
import pydeck as pdk
import numpy as np

st.set_page_config(page_title="한반도 실시간 비행기 추적", layout="wide")

st.title("✈️ 한반도 상공 실시간 비행기 이상 탐지 웹앱")
st.write("OpenSky API 데이터에 Z-score 통계 기법을 적용하여 급강하 중인 비행기를 자동으로 감지합니다.")

# -----------------------------------------------------------
# 1. 사이드바 UI 설정 (슬라이더 추가)
# -----------------------------------------------------------
st.sidebar.header("⚙️ 컨트롤 타워")

# 캐시를 클리어하고 화면을 강제 새로고침하는 버튼
if st.sidebar.button("🔄 실시간 데이터 새로고침"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("🚨 이상 탐지(Anomaly Detection) 설정")

# 사용자가 직접 Z-score 기준값을 조절할 수 있는 슬라이더
z_threshold = st.sidebar.slider(
    "급강하 감지 Z-score 기준값",
    min_value=-5.0,
    max_value=5.0,
    value=-3.0,
    step=0.1
)

# -----------------------------------------------------------
# 2. 데이터 수집 (OpenSky API) - 캐싱 추가로 API 차단 방지
# -----------------------------------------------------------
@st.cache_data(ttl=15) # 15초 동안 캐싱하여 서버 과부하 및 차단 방지
def get_flight_data():
    # [수정] &quot; 오타를 지우고 깔끔한 URL 주소로 변경
    url = "https://opensky-network.org/api/states/all"
    params = {"lamin": 33.0, "lamax": 39.0, "lomin": 124.0, "lomax": 132.0}
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data is not None and data.get("states") is not None:
            return data["states"]
        return []
    except Exception as e:
        st.error(f"데이터를 가져오는 중 오류가 발생했습니다: {e}")
        return []

raw_data = get_flight_data()

# -----------------------------------------------------------
# 3. 데이터 전처리 및 Z-score 계산 (Pandas)
# -----------------------------------------------------------
if len(raw_data) > 0:
    columns = [
        'icao24', 'callsign', 'origin_country', 'time_position', 'last_contact',
        'longitude', 'latitude', 'baro_altitude', 'on_ground', 'velocity',
        'true_track', 'vertical_rate', 'sensors', 'geo_altitude', 'squawk', 'spi', 'position_source'
    ]
    df = pd.DataFrame(raw_data, columns=columns)
    
    # 필요한 컬럼만 추출
    df = df[['callsign', 'longitude', 'latitude', 'baro_altitude', 'velocity', 'vertical_rate']].copy()
    
    # 위치 정보와 수직 속도가 없는 데이터 정제
    df = df.dropna(subset=['longitude', 'latitude', 'vertical_rate'])
    df['callsign'] = df['callsign'].astype(str).str.strip().replace('', '알 수 없음')

    # --- [핵심 기능] Z-score 계산 ---
    mean_vr = df['vertical_rate'].mean()
    std_vr = df['vertical_rate'].std()
    
    if std_vr > 0:
        df['z_score'] = (df['vertical_rate'] - mean_vr) / std_vr
    else:
        df['z_score'] = 0.0

    # 툴팁 가독성을 위해 Z-score 소수점 둘째자리까지 반올림
    df['z_score'] = df['z_score'].round(2)

    # 상태 분류
    df['status'] = df['z_score'].apply(lambda z: '위험(급강하)' if z <= z_threshold else '정상')

    # --- [시각화 꿀팁] Pydeck 호환 컬러 리스트 부여 ---
    # Pydeck에 넣을 때는 아예 튜플이나 순수 리스트 상태여야 에러가 안 납니다.
    df['color'] = df['status'].apply(lambda s: [255, 0, 0, 255] if s == '위험(급강하)' else [255, 200, 0, 180])

    # 대시보드 사이드바 요약 정보 표시
    diving_count = len(df[df['status'] == '위험(급강하)'])
    st.sidebar.success(f"현재 추적 비행기: {len(df)}대")
    if diving_count > 0:
        st.sidebar.error(f"⚠️ 급강하 감지: {diving_count}대!!")
    else:
        st.sidebar.info("✅ 현재 특이 이상 징후 없음")

    # -----------------------------------------------------------
    # 4. Pydeck 3D 지도 시각화
    # -----------------------------------------------------------
    view_state = pdk.ViewState(latitude=36.0, longitude=128.0, zoom=6, pitch=45)

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position="[longitude, latitude]",
        get_radius=7000,          # 지도에서 조금 더 잘 보이게 크기 소폭 상향
        get_fill_color="color",   # 우리가 만든 color 컬럼 매핑
        pickable=True
    )

    tooltip = {
        "html": """
        <b>콜사인:</b> {callsign} <br/>
        <b>상태:</b> <span style='color:red;'><b>{status}</b></span> <br/>
        <b>수직 속도:</b> {vertical_rate} m/s <br/>
        <b>Z-score:</b> {z_score} <br/>
        <b>현재 고도:</b> {baro_altitude} m
        """,
        "style": {"backgroundColor": "black", "color": "white"}
    }

    r = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip=tooltip,
        map_style="mapbox://styles/mapbox/dark-v10" # 완전히 어두운 다크맵 스타일 지정
    )

    st.pydeck_chart(r)
    
    # -----------------------------------------------------------
    # 5. 데이터 테이블 확인
    # -----------------------------------------------------------
    st.subheader("📊 실시간 항공 통계 및 데이터")
    col1, col2 = st.columns(2)
    with col1:
        st.metric(label="평균 수직 속도", value=f"{mean_vr:.2f} m/s")
    with col2:
        st.metric(label="수직 속도 표준편차", value=f"{std_vr:.2f}")
       
    st.dataframe(df[['callsign', 'status', 'z_score', 'vertical_rate', 'baro_altitude', 'velocity']], use_container_width=True)
else:
    st.warning("현재 한반도 상공에서 감지된 비행기 데이터가 없거나, OpenSky API 요청 제한에 걸렸습니다. 잠시 후 새로고침을 눌러보세요.")
