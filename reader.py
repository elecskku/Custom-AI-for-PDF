import streamlit as st
import fitz  # PyMuPDF
from openai import OpenAI

# 페이지 설정
st.set_page_config(page_title="유재우 Custom AI", page_icon="📄", layout="wide")

# 세션 상태 초기화
if "page_num" not in st.session_state:
    st.session_state.page_num = 0
if "processed_data" not in st.session_state:
    st.session_state.processed_data = {}
if "full_text" not in st.session_state:
    st.session_state.full_text = ""
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- CSS 스타일 (너비 조절 및 구분선) ---
st.markdown(
    """
    <style>
    section[data-testid="stSidebar"] { width: 200px !important; min-width: 200px !important; }
    [data-testid="column"] { border-right: 2px solid #000000 !important; padding: 0 15px !important; }
    [data-testid="column"]:last-child { border-right: none !important; }
    .stMarkdown { word-break: keep-all; }
    /* 채팅창 영역 스타일 */
    .chat-container { border: 1px solid #ddd; padding: 10px; border-radius: 5px; background: #f9f9f9; height: 300px; overflow-y: auto; }
    </style>
    """,
    unsafe_allow_html=True
)

# --- 사이드바 설정 ---
with st.sidebar:
    st.title("⚙️ 설정")
    api_key = st.text_input("OpenAI API Key", type="password", placeholder="sk-...")
    selected_model = st.selectbox("모델 선택", ["gpt-4o", "gpt-4o-mini"], index=0)
    uploaded_file = st.file_uploader("PDF 업로드", type=["pdf"])
    
    st.divider()
    st.subheader("📏 영역 너비 조절")
    w_left = st.slider("번역 영역", 0.5, 4.0, 2.0, 0.1)
    w_mid = st.slider("원본 영역", 0.5, 4.0, 1.4, 0.1)
    w_right = st.slider("요약/챗봇 영역", 0.5, 4.0, 1.2, 0.1)

st.title("유재우 Custom AI")

if uploaded_file and api_key:
    try:
        client = OpenAI(api_key=api_key)
        pdf_data = uploaded_file.getvalue()
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        total_pages = len(doc)

        # 전체 텍스트 추출 (챗봇 학습용)
        if not st.session_state.full_text:
            all_text = ""
            for p in doc:
                all_text += p.get_text()
            st.session_state.full_text = all_text

        # 페이지 이동 컨트롤
        col_nav1, col_nav2, col_nav3 = st.columns([1, 1, 1])
        with col_nav1:
            if st.button("이전 페이지") and st.session_state.page_num > 0:
                st.session_state.page_num -= 1
        with col_nav2:
            st.write(f"페이지: {st.session_state.page_num + 1} / {total_pages}")
        with col_nav3:
            if st.button("다음 페이지") and st.session_state.page_num < total_pages - 1:
                st.session_state.page_num += 1

        # 화면 3단 구성
        col_left, col_mid, col_right = st.columns([w_left, w_mid, w_right])
        
        current_idx = st.session_state.page_num
        page = doc.load_page(current_idx)
        page_text = page.get_text()
        
        # 1. 중앙: 원본 PDF
        with col_mid:
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
            st.image(pix.tobytes("png"), use_container_width=True)

        # 2. 왼쪽: 번역 (AI 처리)
        if current_idx not in st.session_state.processed_data:
            with st.spinner("분석 중..."):
                t_res = client.chat.completions.create(
                    model=selected_model,
                    messages=[{"role": "system", "content": "전문 번역가입니다. 이 페이지를 한국어로 번역하세요."},
                              {"role": "user", "content": page_text}]
                )
                s_res = client.chat.completions.create(
                    model=selected_model,
                    messages=[{"role": "system", "content": "이 페이지의 핵심을 한국어로 요약하세요."},
                              {"role": "user", "content": page_text}]
                )
                st.session_state.processed_data[current_idx] = {
                    "trans": t_res.choices[0].message.content,
                    "sum": s_res.choices[0].message.content
                }

        with col_left:
            st.subheader("한국어 번역")
            st.write(st.session_state.processed_data[current_idx]["trans"])

        # 3. 오른쪽: 요약 및 챗봇 (질문에 답하는 전용 모델)
        with col_right:
            st.subheader("요약 및 핵심")
            st.write(st.session_state.processed_data[current_idx]["sum"])
            
            st.divider()
            st.subheader("💬 PDF 전용 챗봇")
            
            # 채팅 기록 표시
            for chat in st.session_state.chat_history:
                with st.chat_message(chat["role"]):
                    st.markdown(chat["content"])

            # 채팅 입력창
            if prompt := st.chat_input("이 문서에 대해 궁금한 점을 물어보세요!"):
                st.session_state.chat_history.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)

                with st.chat_message("assistant"):
                    # PDF 전체 내용을 컨텍스트로 주입
                    response = client.chat.completions.create(
                        model=selected_model,
                        messages=[
                            {"role": "system", "content": f"당신은 제공된 PDF 문서의 전문가입니다. 아래의 문서 내용을 바탕으로 답변하세요. 문서에 없는 내용은 모른다고 하세요.\n\n[문서 내용]\n{st.session_state.full_text[:15000]}"}, # 토큰 제한을 고려해 앞부분 위주 제공
                            *st.session_state.chat_history
                        ]
                    )
                    answer = response.choices[0].message.content
                    st.markdown(answer)
                    st.session_state.chat_history.append({"role": "assistant", "content": answer})

    except Exception as e:
        st.error(f"오류: {str(e)}")
elif not api_key:
    st.warning("API 키를 입력하세요.")
else:
    st.info("PDF를 업로드하세요.")