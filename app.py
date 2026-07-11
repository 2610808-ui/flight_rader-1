!pip install streamlit -q
!pip install FlightRadarAPI
!wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
!chmod +x cloudflared-linux-amd64
print("다운로드 완료")

import streamlit as st
import pandas as pd
import pydeck as pdk
from FlightRadar24 import FlightRadar24API

# --- 1. 가상 데이터(Mock Data) 생성 함수 ---
# 코랩 IP가 차단되었을 때 화면이 비어있지 않도록 띄워줄 테스트용 비행기 4대입니다.
def get_mock_data():
    mock_flights = [
        ['KOREAN_AIR_01', 'KAL', 'ICN(인천)', 'LAX(로스앤젤레스)', 126.45, 37.45, 10500, 250, 45],
        ['ASIANA_02', 'AAR', 'PUS(부산)', 'NRT(도쿄)', 129.12, 35.17, 7200, 200, 90],
        ['JEJU_03', 'JJA', 'CJU(제주)', 'GMP(김포)', 126.49, 33.50, 4500, 150, 10],
        ['JIN_AIR_04', 'JNA', 'CJJ(청주)', 'KIX(오사카)', 127.42, 36.71, 8800, 220, 120]
    ]
    columns = ['콜사인(이름)', '항공사코드', '출발지', '도착지', 'lon', 'lat', '기압고도', '속도', '방향(각도)']
    return pd.DataFrame(mock_flights, columns=columns), True # True는 가상 데이터임을 의미합니다.

# --- 2. 진짜 데이터 가져오기 함수 (FlightRadar24) ---
@st.cache_data(ttl=15) 
def get_real_flights_fr24():
    try:
        fr_api = FlightRadar24API()
        bounds = "39.0,33.0,124.0,132.0" # 한반도 좌표
        
        flights = fr_api.get_flights(bounds=bounds)
        
        # 만약 FlightRadar24가 코랩 IP를 봇으로 의심해서 빈 리스트([])를 주면 가상 데이터를 리턴합니다.
        if not flights or len(flights) == 0:
            return get_mock_data()
            
        flight_list = []
        for f in flights:
            flight_list.append({
                '콜사인(이름)': f.callsign if f.callsign else '알수없음',
                '항공사코드': f.airline_iata if f.airline_iata else 'N/A',
                '출발지': f.origin_airport_iata if f.origin_airport_iata else 'N/A',
                '도착지': f.destination_airport_iata if f.destination_airport_iata else 'N/A',
                'lat': f.latitude,
                'lon': f.longitude,
                '기압고도': int(f.altitude * 0.3048),  # 피트 -> 미터 변환
                '속도': int(f.ground_speed * 0.514444), # 노트 -> 초속 변환
                '방향(각도)': f.heading
            })
            
        df = pd.DataFrame(flight_list)
        return df, False # False는 진짜 데이터임을 의미합니다.

    except Exception:
        # 에러가 발생해도 앱이 멈추지 않고 가상 데이터를 보여줍니다.
        return get_mock_data()

# ---------------------------------------------------------
# 화면 UI 및 3D 지도 그리기
# ---------------------------------------------------------
st.set_page_config(page_title="한반도 3D 비행기 추적기", page_icon="✈️", layout="wide")

st.title("✈️ 한반도 실시간 3D 비행기 추적기")
st.write("파이썬 코드로 하늘 위 비행기 데이터를 수집하고 3D로 시각화한 프로젝트입니다!")

if st.button("🔄 데이터 새로고침", use_container_width=True):
    st.cache_data.clear() 

with st.spinner("레이더 탐지 중... (코랩 차단 시 안전장치 가동)"):
    flights_df, is_mock = get_real_flights_fr24()

if not flights_df.empty:
    # 진짜 데이터인지 가상 데이터인지에 따라 메시지 색상과 내용을 다르게 보여줍니다.
    if is_mock:
        st.warning("⚠️ **코랩(클라우드) 서버 IP가 보안에 의해 차단되었습니다.** 화면 테스트를 위해 가상(Mock) 비행기 4대를 표시합니다. (로컬 PC에서 실행 시 진짜 데이터가 나옵니다)")
    else:
        st.success(f"📡 성공! 현재 한반도 상공에서 **{len(flights_df)}대**의 '진짜 비행기'를 찾았습니다!")
    
    # 3D 지도 툴팁(마우스 올리면 나오는 정보)
    tooltip = {
        "html": "<b>콜사인:</b> {콜사인(이름)} ({항공사코드}) <br/>"
                "<b>경로:</b> {출발지} ➡️ {도착지} <br/>"
                "<b>고도:</b> {기압고도} m <br/>"
                "<b>속도:</b> {속도} m/s",
        "style": {"backgroundColor": "darkblue", "color": "white", "font-family": "sans-serif"}
    }

    # 비행기 기둥 레이어 (고도에 따라 높이와 색상이 실시간으로 적용됨)
    column_layer = pdk.Layer(
        "ColumnLayer",
        data=flights_df,
        get_position=["lon", "lat"],
        get_elevation="기압고도",
        elevation_scale=1.2, 
        radius=2500,         
        get_fill_color=["255", "255 - (기압고도/100)", "50", "220"], 
        pickable=True,
        auto_highlight=True,
    )

    # 초기 지도 시점
    view_state = pdk.ViewState(latitude=36.0, longitude=127.5, zoom=5.8, pitch=45, bearing=0)

    # 3D 지도 렌더링
    st.pydeck_chart(pdk.Deck(
        map_style="mapbox://styles/mapbox/dark-v11",
        initial_view_state=view_state,
        layers=[column_layer],
        tooltip=tooltip
    ))
    
    st.caption("🖱️ **팁:** 마우스 우클릭 + 드래그 = 지도 3D 회전 / 좌클릭 + 드래그 = 지도 이동")
    
    st.subheader("📋 비행기 상세 데이터 표")
    st.dataframe(flights_df, use_container_width=True)

!head -3 app.py

!streamlit run app.py --server.port 8502 &>/content/logs.txt &
import time
time.sleep(6)
!cat /content/logs.txt

!nohup ./cloudflared-linux-amd64 tunnel --url http://localhost:8502 > tunnel.log 2>&1 &
import time
time.sleep(10)
!grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' tunnel.log | head -1
