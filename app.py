import streamlit as st
import pandas as pd
import pydeck as pdk
import requests
from requests.auth import HTTPBasicAuth

# --- 1. 가상 데이터(Mock Data) 생성 함수 ---
# API 호출에 실패하거나 레이트 리밋(요청 제한)에 걸렸을 때 화면이 비지 않도록 채워줄 테스트용 비행기 데이터입니다.
def get_mock_data():
    mock_flights = [
        ['KOREAN_AIR_01', 'South Korea', 126.45, 37.45, 10500, 250, 45],
        ['ASIANA_02', 'South Korea', 129.12, 35.17, 7200, 200, 90],
        ['JEJU_03', 'South Korea', 126.49, 33.50, 4500, 150, 10],
        ['JIN_AIR_04', 'South Korea', 127.42, 36.71, 8800, 220, 120]
    ]
    columns = ['콜사인', '국가', 'lon', 'lat', '기압고도', '속도', '방향']
    df = pd.DataFrame(mock_flights, columns=columns)
    
    # 3D 렌더링에 필요한 파생 필드들을 파이썬에서 안전하게 사전 가공합니다.
    df['속도_kmh'] = df['속도'] * 3.6
    df['fill_color'] = df['기압고도'].apply(lambda x: [50, max(0, min(255, int(150 + (x / 100)))), 255, 200])
    
    return df, True # True는 가상 데이터임을 의미합니다.

# --- 2. OpenSky Network API 실시간 데이터 가져오기 함수 ---
@st.cache_data(ttl=10) # 10초 동안 데이터를 캐싱하여 잦은 새로고침으로 인한 차단을 방지합니다.
def get_real_flights_opensky(username="", password=""):
    # 올바른 API 엔드포인트 URL 설정
    url = "https://opensky-network.org/api/states/all"
    
    # 한반도 영역 감싸는 위경도 좌표 설정 (남, 북, 서, 동 순서)
    params = {
        "lamin": 33.0,  # 남한 최남단 (제주도 아래)
        "lamax": 39.0,  # 휴전선 인근 북위
        "lomin": 124.0, # 서해안 끝
        "lomax": 132.0  # 동해안 끝 (울릉도/독도 포함)
    }
    
    try:
        # 로그인 정보가 입력되었다면 Basic Authentication(기본 인증)을 적용합니다.
        if username and password:
            response = requests.get(url, params=params, auth=HTTPBasicAuth(username, password), timeout=8)
        else:
            response = requests.get(url, params=params, timeout=8)
            
        # API 응답 상태 코드가 200(성공)이 아니면 에러를 던집니다.
        if response.status_code != 200:
            return get_mock_data()
            
        data = response.json()
        states = data.get("states", [])
        
        # 조회된 비행기가 없거나 빈 배열인 경우 가상 데이터를 보여줍니다.
        if not states:
            return get_mock_data()
            
        flight_list = []
        for s in states:
            callsign = s[1].strip() if s[1] else "알수없음"
            country = s[2] if s[2] else "미상"
            lon = s[5]
            lat = s[6]
            altitude = s[7] if s[7] is not None else 0
            velocity = s[9] if s[9] is not None else 0
            heading = s[10] if s[10] is not None else 0
            
            # 위도 경도가 정상적으로 있는 비행기만 수집합니다.
            if lon and lat:
                flight_list.append({
                    '콜사인': callsign,
                    '국가': country,
                    'lon': lon,
                    'lat': lat,
                    '기압고도': int(altitude),
                    '속도': int(velocity),
                    '방향': int(heading)
                })
                
        if not flight_list:
            return get_mock_data()
            
        df = pd.DataFrame(flight_list)
        
        # 3D 렌더링에 필요한 파생 필드들을 파이썬에서 안전하게 사전 가공합니다.
        df['속도_kmh'] = df['속도'] * 3.6
        df['fill_color'] = df['기압고도'].apply(lambda x: [50, max(0, min(255, int(150 + (x / 100)))), 255, 200])
        
        return df, False # False는 진짜 데이터임을 의미합니다.
        
    except Exception as e:
        # 인터넷 끊김이나 사이트 장애 시 가상 데이터로 안전하게 처리합니다.
        return get_mock_data()

# ---------------------------------------------------------
# 스트림릿 웹 화면 구성
# ---------------------------------------------------------
st.set_page_config(page_title="한반도 실시간 3D OpenSky 추적기", page_icon="✈️", layout="wide")

# 사이드바 - OpenSky 계정 및 프로젝트 가이드 정보 제공
with st.sidebar:
    st.image("https://images.unsplash.com/photo-1436491865332-7a61a109cc05?auto=format&fit=crop&w=300&q=80", caption="실시간 항공 관제 프로젝트")
    st.header("🔑 OpenSky API 인증 설정")
    st.write("아이디 없이도 호출이 가능하지만, 하루 요청 수가 매우 제한되어 있습니다
