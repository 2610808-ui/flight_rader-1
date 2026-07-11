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
    
    # 여러 줄 텍스트가 들어가더라도 줄바꿈 문자열 오류(SyntaxError)가 발생하지 않도록 삼중 따옴표(""")를 사용합니다.
    st.write(
        """
        아이디 없이도 호출이 가능하지만, 하루 요청 수가 매우 제한되어 있습니다. 
        [OpenSky Network](https://opensky-network.org/)에 무료 회원가입 후 
        아래에 계정을 입력하면 보다 안정적으로 작동합니다!
        """
    )
    
    user_id = st.text_input("OpenSky 아이디", value="", placeholder="ID 입력")
    user_pw = st.text_input("OpenSky 비밀번호", type="password", value="", placeholder="비밀번호 입력")
    
    st.divider()
    st.markdown("### 🗺️ 한반도 탐색 위경도 범위")
    st.code("북위: 33.0°N ~ 39.0°N\n동경: 124.0°E ~ 132.0°E")

# 메인 헤더
st.title("✈️ OpenSky API 기반 한반도 실시간 3D 비행기 추적기")
st.markdown("""
이 앱은 전 세계 항공기 감시망 데이터를 무료로 개방하는 **OpenSky Network API**를 이용하여 한반도 주변의 비행기 위치를 수집하고 3D 지도로 시각화한 프로젝트입니다.  
고등학생 파이썬 데이터 다루기 실전 예제 수업을 위해 튜터가 재구성한 템플릿입니다!
""")

# 데이터 새로고침 및 수집
if st.button("🔄 데이터 실시간 업데이트", use_container_width=True):
    st.cache_data.clear()

with st.spinner("OpenSky 기지국 서버 탐색 중..."):
    flights_df, is_mock = get_real_flights_opensky(username=user_id, password=user_pw)

# 데이터가 존재한다면 시각화 수행
if not flights_df.empty:
    if is_mock:
        st.warning("⚠️ **OpenSky 비회원 요청 제한에 도달했거나 네트워크 오류가 발생했습니다.** 화면 기능 확인을 위한 테스트 가상 데이터(4대)를 표시합니다. (안정적인 관제를 원하시면 사이드바에 OpenSky 계정을 입력해 주세요)")
    else:
        st.success(f"📡 관제 성공! 현재 한반도 탐색 범위 내에서 실시간 감지된 비행기 **{len(flights_df)}대**를 화면에 시각화합니다!")

    # 3D pydeck 레이어 설정
    # 기압고도에 따라 막대기둥의 높이(Elevation)와 색상을 다르게 표현합니다.
    column_layer = pdk.Layer(
        "ColumnLayer",
        data=flights_df,
        get_position=["lon", "lat"],
        get_elevation="기압고도",
        elevation_scale=1.5,       # 고도 표현의 입체감을 높이기 위해 스케일 조절
        radius=3000,               # 기둥 두께 설정
        get_fill_color="fill_color", # 파이썬 Pandas에서 미리 안전하게 만든 컬럼을 그대로 전달합니다.
        pickable=True,
        auto_highlight=True,
    )

    # 3D 지도의 첫 시작 시점 (한반도 중앙부 배치)
    view_state = pdk.ViewState(
        latitude=36.0,
        longitude=127.5,
        zoom=6.0,
        pitch=50,                  # 카메라가 지도를 비스듬히 바라보는 각도 (3D 표현 필수)
        bearing=15                 # 지도가 살짝 회전된 각도
    )

    # 지도 툴팁 디자인 (마우스를 기둥에 올렸을 때 나타나는 팝업 메시지)
    tooltip = {
        "html": "<b>콜사인:</b> {콜사인} <br/>"
                "<b>출발국가:</b> {국가} <br/>"
                "<b>실시간 고도:</b> {기압고도} m <br/>"
                "<b>지속도:</b> {속도} m/s (약 {속도_kmh:.1f} km/h)",
        "style": {"backgroundColor": "#0c1020", "color": "white", "font-family": "sans-serif", "border": "1px solid #4f83cc"}
    }

    # Pydeck 3D 맵 렌더링
    st.pydeck_chart(pdk.Deck(
        map_style="mapbox://styles/mapbox/dark-v11",
        initial_view_state=view_state,
        layers=[column_layer],
        tooltip=tooltip
    ))

    st.caption("🖱️ **지도 조작 팁:** 마우스 오른쪽 클릭 상태에서 드래그 = 지도 3D 입체 각도 변경 | 마우스 왼쪽 클릭 상태에서 드래그 = 지도 평면 이동")

    # 수집한 데이터 원본 표(Table)로 확인
    st.subheader("📋 실시간 OpenSky 비행기 원본 데이터 테이블")
    st.dataframe(flights_df, use_container_width=True)

else:
    st.error("데이터 수집 과정에 예기치 못한 치명적 에러가 발생했습니다.")

# --- 3. 튜터 코너 (고등학생을 위한 API & Pydeck 시각화 해설) ---
st.divider()
with st.expander("🎓 [Tutor Corner] 튜터가 설명해 주는 OpenSky API 분석 가이드"):
    st.markdown("""
    ### 1. OpenSky API는 무엇인가요?
    전 세계 자원봉사자들이 ADS-B 기지국 장비를 활용해 수집하는 실시간 항공 네트워크입니다. 비행기에서 1초마다 공중으로 쏘는 고도, 위도, 경도 전파를 수집하여 오픈 API로 무료 제공하고 있습니다.
    
    ### 2. 우리가 보낸 HTTP Request(요청) 뜯어보기
    API 호출 시 사용된 주요 파라미터는 `lamin, lamax, lomin, lomax`로 한반도 직사각형 모양 영역을 자르는 경계선 좌표(Bounding Box)입니다.
    - `lamin` (latitude minimum): 탐지 구역의 가장 아래 위도 (33도)
    - `lomin` (longitude minimum): 탐지 구역의 가장 왼쪽 경도 (124도)
    
    ### 3. OpenSky API의 데이터 배열 구조
    OpenSky는 딕셔너리(`{"states": [...]}`) 안에 속성 정보들이 이름이 아닌 **순서(인덱스)**로 정렬된 리스트를 반환합니다. 파이썬 리스트 슬라이싱 연습하기에 매우 좋은 데이터입니다!
    * `s[1]`: 비행기 콜사인 (Callsign)
    * `s[2]`: 등록 국가 (Origin Country)
    * `s[5] / s[6]`: 경도(lon) 및 위도(lat)
    * `s[7]`: 고도 (미터 단위)
    * `s[9]`: 속도 (m/s 단위)
    
    ### 4. 이전 프로젝트(FlightRadar24)와 다른 점은 무엇일까요?
    - **정보량:** FlightRadar24는 출발 공항(ICN) 및 도착 공항(LAX) 정보를 기본 제공하지만, OpenSky의 공용 States API는 항공기가 우주에서 전파하는 물리적 신호(위치, 고도, 속도) 중심이기 때문에 경로 정보가 직접 표시되지 않습니다. (각 API마다 수집 및 제공 구조가 달라요!)
    - **가입 여부:** FlightRadar24는 코랩 등 공용 서버 IP를 봇으로 철저히 격리 차단하지만, OpenSky는 로그인 정보 입력 세션을 직접 만들 수 있어서 학교 실습이나 개인 프로젝트 웹앱으로 개발하기에 훨씬 친화적입니다!
    """)
