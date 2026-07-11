import streamlit as st
import pandas as pd
import pydeck as pdk
import requests
from requests.auth import HTTPBasicAuth

# --- 1. 가상 데이터(Mock Data) 생성 함수 ---
# API 호출 실패, 네트워크 순간 끊김, 혹은 요청 제한 시 화면이 멈추지 않도록 제공되는 예비 항공 데이터입니다.
def get_mock_data():
    mock_flights = [
        ['KOREAN_AIR_01', 'South Korea', 126.45, 37.45, 10500, 250, 45],
        ['ASIANA_02', 'South Korea', 129.12, 35.17, 7200, 200, 90],
        ['JEJU_03', 'South Korea', 126.49, 33.50, 4500, 150, 10],
        ['JIN_AIR_04', 'South Korea', 127.42, 36.71, 8800, 220, 120]
    ]
    columns = ['callsign', 'country', 'lon', 'lat', 'altitude', 'velocity', 'heading']
    df = pd.DataFrame(mock_flights, columns=columns)
    
    # 3D 렌더링에 사용할 파생 변수들을 파이썬에서 미리 빌드합니다.
    df['velocity_kmh'] = df['velocity'] * 3.6
    # 고도에 따른 그라데이션 색상 (낮으면 청록색, 높으면 자홍색)
    df['fill_color'] = df['altitude'].apply(
        lambda x: [50, max(0, min(255, int(200 - (x / 80)))), max(100, min(255, int(100 + (x / 50)))), 200]
    )
    return df, True

# --- 2. OpenSky Network API 실시간 데이터 수집 함수 ---
@st.cache_data(ttl=12) # 12초 동안 데이터를 안전하게 캐싱하여 반복적인 API 난타 및 IP 차단을 예방합니다.
def get_real_flights_opensky(username="", password=""):
    url = "https://opensky-network.org/api/states/all"
    
    # 한반도 좌표 경계 박스 (남, 북, 서, 동)
    params = {
        "lamin": 33.0,  # 남위 경계
        "lamax": 39.0,  # 북위 경계
        "lomin": 124.0, # 서경 경계
        "lomax": 132.0  # 동경 경계
    }
    
    try:
        # 로그인 값이 입력되었다면 인증 헤더를 동봉하고, 없으면 비인증 세션으로 요청합니다.
        if username and password:
            response = requests.get(url, params=params, auth=HTTPBasicAuth(username, password), timeout=10)
        else:
            response = requests.get(url, params=params, timeout=10)
            
        # API 응답 상태 코드가 정상(200)이 아닌 경우 예비 데이터를 호출합니다.
        if response.status_code != 200:
            return get_mock_data()
            
        data = response.json()
        states = data.get("states", [])
        
        # 탐색 범위 내 비행 중인 항공기가 없을 경우
        if not states:
            return get_mock_data()
            
        flight_list = []
        for s in states:
            # 외부 API 호출 시 발생할 수 있는 데이터 누락(IndexError)을 선제 방지합니다.
            callsign = s[1].strip() if len(s) > 1 and s[1] else "알수없음"
            country = s[2] if len(s) > 2 and s[2] else "미상"
            lon = s[5] if len(s) > 5 else None
            lat = s[6] if len(s) > 6 else None
            altitude = s[7] if len(s) > 7 and s[7] is not None else 0
            velocity = s[9] if len(s) > 9 and s[9] is not None else 0
            heading = s[10] if len(s) > 10 and s[10] is not None else 0
            
            # 위도와 경도 좌표값이 실재하는 정보만 엄선합니다.
            if lon is not None and lat is not None:
                flight_list.append({
                    'callsign': callsign,
                    'country': country,
                    'lon': lon,
                    'lat': lat,
                    'altitude': int(altitude),
                    'velocity': int(velocity),
                    'heading': int(heading)
                })
                
        if not flight_list:
            return get_mock_data()
            
        df = pd.DataFrame(flight_list)
        
        # Pydeck 파싱에 문제를 주지 않도록 완벽한 데이터 가공을 마칩니다.
        df['velocity_kmh'] = df['velocity'] * 3.6
        df['fill_color'] = df['altitude'].apply(
            lambda x: [50, max(0, min(255, int(200 - (x / 80)))), max(100, min(255, int(100 + (x / 50)))), 200]
        )
        return df, False
        
    except Exception:
        # 어떠한 예외 오류가 터지더라도 메인 서버 화면이 꺼지지 않도록 가상 데이터를 자동 바인딩합니다.
        return get_mock_data()

# ---------------------------------------------------------
# 스트림릿 애플리케이션 시작 및 환경 정의
# ---------------------------------------------------------
st.set_page_config(page_title="한반도 실시간 3D OpenSky 관제소", page_icon="✈️", layout="wide")

# 사이드바 패널 구성
with st.sidebar:
    st.image("https://images.unsplash.com/photo-1436491865332-7a61a109cc05?auto=format&fit=crop&w=300&q=80", caption="고등학생 파이썬 실무 시각화 프로젝트")
    st.header("🔑 OpenSky API 계정 설정")
    
    # 삼중 따옴표 멀티라인으로 구문을 감싸 텍스트 줄바꿈 시의 구문 에러를 방지했습니다.
    st.info(
        """
        아이디 없이도 기본 실행이 가능하지만, 일일 무료 사용량 초과 시 조회가 막힐 수 있습니다.
        가급적 OpenSky Network 공식 홈페이지에서 무료 가입을 진행한 뒤 계정을 연동해 보세요!
        """
    )
    
    user_id = st.text_input("OpenSky ID", value="", placeholder="아이디 입력")
    user_pw = st.text_input("OpenSky Password", type="password", value="", placeholder="비밀번호 입력")
    
    st.divider()
    st.header("🎨 지도 스타일 및 필터")
    map_theme = st.selectbox(
        "베이스 레이어 테마",
        ["dark", "light", "satellite", "road"]
    )
    
    st.markdown("### 📡 관제 데이터 필터링")
    # 사용자가 직접 데이터를 조작하는 인터랙션 추가
    altitude_cutoff = st.slider("최소 비행 고도 필터 (m)", 0, 15000, 0, step=500)
    speed_cutoff = st.slider("최소 비행 속도 필터 (km/h)", 0, 1200, 0, step=50)

# 메인 웹 페이지 디자인
st.title("✈️ OpenSky API 기반 한반도 실시간 3D 비행기 관제 레이더")
st.markdown(
    """
    이 웹앱은 전 세계 항공 장비 전파 데이터를 수집해 무료 개방하는 공익적 프로젝트인 **OpenSky Network API**를 
    사용하여 한반도 영역의 위성 위치 전파를 추적하고, 이를 **3D 실시간 막대 데이터 기둥**으로 렌더링한 데이터 과학 예제 프로젝트입니다.
    """
)

# 실시간 데이터 새로고침 제어 버튼
if st.button("🔄 데이터 실시간 강제 업데이트", use_container_width=True):
    st.cache_data.clear()

with st.spinner("한반도 일대 항공 중계 서버 통신 중..."):
    raw_df, is_mock = get_real_flights_opensky(username=user_id, password=user_pw)

# 데이터 가공 및 필터 적용
if not raw_df.empty:
    # 사이드바 필터에 따라 Pandas 상에서 능동적으로 데이터를 분기해 줍니다.
    filtered_df = raw_df[
        (raw_df['altitude'] >= altitude_cutoff) & 
        (raw_df['velocity_kmh'] >= speed_cutoff)
    ]
    
    if is_mock:
        st.warning("⚠️ **OpenSky 무료 비인증 호출 한도 초과 또는 네트워크 순간 끊김으로 가상 데이터를 노출 중입니다.** (정상 관제를 원할 시 사이드바 계정 연동 권장)")
    else:
        st.success(f"📡 수신 성공! 현재 한반도 일대에서 수집된 비행기 {len(raw_df)}대 중 필터링 조건에 부합하는 {len(filtered_df)}대를 추적합니다.")

    # 실시간 통계 보드 디자인
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("추적 중인 항공기 수", f"{len(filtered_df)} 대")
    with col2:
        max_speed = filtered_df['velocity_kmh'].max() if not filtered_df.empty else 0
        st.metric("관제 내 최고 속도", f"{max_speed:.1f} km/h")
    with col3:
        avg_altitude = filtered_df['altitude'].mean() if not filtered_df.empty else 0
        st.metric("평균 운항 고도", f"{avg_altitude:.1f} m")
    with col4:
        foreign_count = len(filtered_df[filtered_df['country'] != 'South Korea']) if not filtered_df.empty else 0
        st.metric("외국 국적기 비율", f"{(foreign_count/len(filtered_df)*100 if len(filtered_df)>0 else 0):.1f} %")

    # Pydeck 3D 가상 레이어 매핑
    column_layer = pdk.Layer(
        "ColumnLayer",
        data=filtered_df,
        get_position=["lon", "lat"],
        get_elevation="altitude",
        elevation_scale=1.5,
        radius=2800,
        get_fill_color="fill_color", # 파이썬에서 사전에 정의된 RGBA 어레이를 직접 파싱하여 JS 에러를 막습니다.
        pickable=True,
        auto_highlight=True,
    )

    # 한반도 지리적 중앙 정렬 및 뷰포트 설정
    view_state = pdk.ViewState(
        latitude=36.0,
        longitude=127.5,
        zoom=5.8,
        pitch=52,  # 3D 기둥이 입체적으로 보이도록 비스듬히 기울임
        bearing=15
    )

    tooltip_layout = {
        "html": """
        <div style="font-family: 'sans-serif'; padding: 5px;">
            <b style="color: #4f83cc; font-size: 14px;">콜사인: {callsign}</b><br/>
            <b>등록 국가:</b> {country}<br/>
            <b>지상 고도:</b> {altitude} m<br/>
            <b>비행 속도:</b> {velocity_kmh:.1f} km/h ({velocity} m/s)
        </div>
        """,
        "style": {
            "backgroundColor": "#0d1117",
            "color": "white",
            "border": "1px solid #30363d",
            "borderRadius": "4px"
        }
    }

    # 3D 덱 생성
    st.pydeck_chart(pdk.Deck(
        map_style=map_theme,
        initial_view_state=view_state,
        layers=[column_layer],
        tooltip=tooltip_layout
    ))
    st.caption("🖱️ **3D 지도 시점 제어 가이드:** [오른쪽 마우스 드래그]로 입체 카메라 회전 / [왼쪽 마우스 드래그]로 수평 패닝 이동")

    # 원본 데이터 시각화 테이블 표 (친절한 한글 별칭 적용)
    st.subheader("📋 실시간 OpenSky 기지국 수집 로우(Raw) 데이터 테이블")
    
    # 분석 표용 한글 컬럼 변환 데이터프레임 빌드
    display_df = filtered_df.copy()
    display_df = display_df.rename(columns={
        'callsign': '콜사인(항공편명)',
        'country': '소속/출발국가',
        'lon': '경도(Longitude)',
        'lat': '위도(Latitude)',
        'altitude': '기압고도(m)',
        'velocity': '속도(m/s)',
        'velocity_kmh': '시속(km/h)',
        'heading': '비행방향각도'
    })
    st.dataframe(display_df.drop(columns=['fill_color'], errors='ignore'), use_container_width=True)

else:
    st.error("현재 기지국 통신 데이터프레임이 빈 상태입니다. 잠시 후 새로고침을 진행해 주세요.")

# --- 3. 튜터 코너 및 깜짝 퀴즈 피드백 영역 ---
st.divider()
tutor_col, quiz_col = st.columns([3, 2])

with tutor_col:
    st.markdown("### 🎓 [Tutor Corner] 튜터가 알려주는 데이터 설계 노트")
    st.markdown(
        """
        - **Pydeck의 JSON 파싱 원리**: Pydeck은 웹 페이지 내부에서 자바스크립트 엔진(`deck.gl`)으로 구동돼요. 만약 데이터 컬럼명에 한글이나 기호 `( )`가 들어가면, 자바스크립트는 이를 변수명이 아닌 '함수 호출식'으로 이해해서 에러를 뿜습니다! 
        - **Pandas 전처리(Pre-processing)의 필요성**: 따라서 데이터프레임의 모든 원본 키 값은 깔끔한 영문 알파벳 소문자(`altitude`, `velocity`)로 유지하고, 화면용 표를 띄울 때만 임시로 가공해서 전달하는 방식이 실무 데이터 과학의 베스트 프랙티스랍니다.
        - **속도 단위 변환 공식**: 항공 레이더 통신에서 초속(`m/s`) 단위를 도로의 차량 계기판 속도와 같은 시속(`km/h`)으로 바꾸기 위해선 **'속도 * 3.6'**이라는 연산을 거치게 됩니다.
        """
    )

with quiz_col:
    st.markdown("### 📝 튜터의 실시간 미니 퀴즈!")
    st.write("오늘 배운 내용으로 간단한 퀴즈를 풀어볼까요?")
    
    answer = st.radio(
        "Q. OpenSky API로 수집한 초속 250m/s로 날아가는 제트기는 시속 몇 km/h로 비행하고 있을까요?",
        ["1) 약 500 km/h", "2) 약 900 km/h", "3) 약 1200 km/h"]
    )
    
    if st.button("정답 확인하기", use_container_width=True):
        if "2)" in answer:
            st.success("🎉 정답입니다! 250 * 3.6 = 900 km/h 입니다. 엄청나게 빠른 속도군요!")
        else:
            st.error("앗, 다시 계산해 볼까요? 250m/s에 3.6을 곱해보세요!")
```
eof

### 📋 최종 실행 가이드
1. 깃허브 저장소 내의 **`app.py`** 파일을 열어, 이전에 적혀있던 모든 코드를 지우고 위 코드로 완전히 교체합니다.
2. 깃허브 저장소에 함께 올린 **`requirements.txt`**에 패키지들이 잘 배치되어 있는지 확인합니다:
   ```text
   streamlit>=1.32
   requests>=2.31
   pandas>=2.0
   numpy>=1.24
   pydeck
