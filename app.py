import streamlit as st
import pandas as pd
import pydeck as pdk
from FlightRadarAPI import FlightRadar24API

# --- 1. 가상 데이터(Mock Data) 생성 함수 ---
def get_mock_data():
    mock_flights = [
        ['KOREAN_AIR_01', 'KAL', 'ICN(인천)', 'LAX(로스앤젤레스)', 126.45, 37.45, 10500, 250, 45],
        ['ASIANA_02', 'AAR', 'PUS(부산)', 'NRT(도쿄)', 129.12, 35.17, 7200, 200, 90],
        ['JEJU_03', 'JJA', 'CJU(제주)', 'GMP(김포)', 126.49, 33.50, 4500, 150, 10],
        ['JIN_AIR_04', 'JNA', 'CJJ(청주)', 'KIX(오사카)', 127.42, 36.71, 8800, 220, 120]
    ]
    columns = ['콜사인(이름)', '항공사코드', '출발지', '도착지', 'lon', 'lat', '기압고도', '속도', '방향(각도)']
    return pd.DataFrame(mock_flights, columns=columns), True

# --- 2. 진짜 데이터 가져오기 함수 (FlightRadar24) ---
@st.cache_data(ttl=15)
def get_real_flights_fr24():
    try:
        fr_api = FlightRadar24API()
        # bounds format: "N,S,W,E" (북, 남, 서, 동 경계선 설정)
        bounds = "39.0,33.0,124.0,132.0"
        
        flights = fr_api.get_flights(bounds=bounds)
        
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
                '속도': int(f.ground_speed * 0.514444), # 노트 -> m/s 변환
                '방향(각도)': f.heading
            })
            
        df = pd.DataFrame(flight_list)
        return df, False

    except Exception:
        # 에러 발생 시 안전하게 가상 데이터 리턴
        return get_mock_data()

# ---------------------------------------------------------
# 화면 UI 및 3D 지도 그리기
# ---------------------------------------------------------
st.set_page_config(page_title="한반도 3D 비행기 추적기", page_icon="✈️", layout="wide")

st.title("✈️ 한반도 실시간 3D 비행기 추적기")
st.write("파이썬 코드로 하늘 위 비행기 데이터를 수집하고 3D로 시각화한 프로젝트입니다!")

if st.button("🔄 데이터 새로고침", use_container_width=True):
    st.cache_data.clear()

with st.spinner("레이더 탐지 중..."):
    flights_df, is_mock = get_real_flights_fr24()

if not flights_df.empty:
    if is_mock:
        st.warning("⚠️ **서버 IP가 차단되었거나 응답이 없습니다.** 화면 테스트를 위해 가상(Mock) 비행기 4대를 표시합니다.")
    else:
        st.success(f"📡 성공! 현재 한반도 상공에서 **{len(flights_df)}대**의 '진짜 비행기'를 찾았습니다!")
    
    tooltip = {
        "html": "<b>콜사인:</b> {콜사인(이름)} ({항공사코드}) <br/>"
                "<b>경로:</b> {출발지} ➡️ {도착지} <br/>"
                "<b>고도:</b> {기압고도} m <br/>"
                "<b>속도:</b> {속도} m/s",
        "style": {"backgroundColor": "darkblue", "color": "white", "font-family": "sans-serif"}
    }

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

    view_state = pdk.ViewState(latitude=36.0, longitude=127.5, zoom=5.8, pitch=45, bearing=0)

    st.pydeck_chart(pdk.Deck(
        map_style="mapbox://styles/mapbox/dark-v11",
        initial_view_state=view_state,
        layers=[column_layer],
        tooltip=tooltip
    ))
    
    st.caption("🖱️ **팁:** 마우스 우클릭 + 드래그 = 지도 3D 회전 / 좌클릭 + 드래그 = 지도 이동")
    
    st.subheader("📋 비행기 상세 데이터 표")
    st.dataframe(flights_df, use_container_width=True)
