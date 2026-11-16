"""KT AIVLE School 백서 학습 도우미 — 미니프로젝트 4차 2일차."""

import hashlib
import os
import uuid
from pathlib import Path

import streamlit as st

from rag_backend import rag_pipeline


st.set_page_config(
    page_title="AIVLE School | 백서 학습 도우미",
    page_icon="🎓",
    layout="wide",
)

st.markdown(
    """
    <style>
      .block-container {max-width: 960px; padding-top: 2rem;}
      h1 {letter-spacing: -0.035em;}
      [data-testid="stChatMessage"] {border-radius: 14px;}
    </style>
    """,
    unsafe_allow_html=True,
)

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
UPLOAD_ROOT = Path(__file__).resolve().parent / ".aivle_data"
EXAMPLES = [
    "DX 트랙 1차 미니프로젝트에서는 어떤 과제를 수행하나요?",
    "에이블스쿨을 수료하면 취업이 보장되나요?",
    "에이블스쿨이 취업에 어떤 도움이 되나요?",
]


def configure_api_key():
    """Streamlit Cloud Secret 또는 로컬 환경변수로 API 키 설정."""
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        try:
            key = str(st.secrets.get("OPENAI_API_KEY", "")).strip()
        except (FileNotFoundError, KeyError):
            key = ""
    if key:
        os.environ["OPENAI_API_KEY"] = key
    return bool(key)


def initialize_session():
    if "upload_session_id" not in st.session_state:
        st.session_state.upload_session_id = uuid.uuid4().hex
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "active_index" not in st.session_state:
        st.session_state.active_index = None
    if "document_digest" not in st.session_state:
        st.session_state.document_digest = None


def save_uploaded_pdf(content: bytes, digest: str):
    """업로드 파일을 확장자 .pdf인 실제 경로로 저장 (RAG 함수 인자용)."""
    folder = UPLOAD_ROOT / st.session_state.upload_session_id / digest
    folder.mkdir(parents=True, exist_ok=True)
    filepath = folder / "AIVLE School 백서.pdf"
    if not filepath.exists():
        filepath.write_bytes(content)
    return filepath


def show_sources(sources):
    if not sources:
        return
    with st.expander(f"검색된 백서 근거 {len(sources)}개 보기"):
        st.caption("이 문단들이 답변 생성 시 전달된 자료입니다. 실제 답변과 일치하는지 확인할 수 있어요.")
        for idx, source in enumerate(sources, 1):
            page = source.get("page")
            label = f"PDF {page}쪽" if page is not None else "쪽수 미확인"
            st.markdown(f"**{idx}. {label}**")
            st.text(source.get("excerpt", ""))


initialize_session()

st.title("🎓 AIVLE School 학습 도우미")
st.caption("팀 통합 백서 기반 RAG · 강의/프로젝트/취업 관련 질문에 문서 근거로 답변합니다")

with st.sidebar:
    st.header("📄 백서 등록")
    uploaded = st.file_uploader(
        "AIVLE School 백서 PDF",
        type=["pdf"],
        help="팀 통합 백서 PDF를 선택하세요. 업로드 후 자동으로 검색 인덱스를 준비합니다.",
    )
    st.divider()
    st.subheader("검색 설정")
    search_type = st.selectbox("검색 방식", ["mmr", "similarity"], index=0)
    k = st.slider("검색 문단 수 (k)", min_value=3, max_value=10, value=6)
    st.caption("기본값: MMR, k=6. 특정 프로젝트 차수는 정확한 FAQ 검색을 우선합니다.")
    st.divider()
    if st.button("🗑️ 대화 삭제", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    st.caption("교육 운영·금액·날짜는 기수별 공지를 우선합니다.")

if not configure_api_key():
    st.error("OpenAI API 키가 없습니다. Streamlit Secrets에 OPENAI_API_KEY를 등록하세요.")
    st.stop()

if uploaded is None:
    st.info("왼쪽에서 **최종 팀 통합 백서 PDF**를 업로드하면 질문을 시작할 수 있어요.")
    st.markdown("**사용 순서:** PDF 업로드 → 인덱싱 완료 → 추천 질문 클릭 또는 직접 질문")
    st.stop()

pdf_bytes = uploaded.getvalue()
if len(pdf_bytes) > MAX_UPLOAD_BYTES:
    st.error("현재 데모는 20MB 이하 PDF만 지원합니다.")
    st.stop()
if not pdf_bytes.startswith(b"%PDF-"):
    st.error("PDF 형식의 파일이 아닙니다. 올바른 PDF를 선택해 주세요.")
    st.stop()

pdf_digest = hashlib.sha256(pdf_bytes).hexdigest()
if st.session_state.document_digest != pdf_digest:
    # 문서가 바뀌면 이전 문서의 질문 이력을 보여주지 않는다.
    st.session_state.messages = []
    st.session_state.document_digest = pdf_digest
    st.session_state.active_index = None

index_identity = (pdf_digest, search_type, k)
if st.session_state.active_index != index_identity:
    filepath = save_uploaded_pdf(pdf_bytes, pdf_digest)
    try:
        with st.spinner("백서 검색 인덱스를 준비하고 있습니다. 처음 업로드할 때만 임베딩합니다."):
            chain = rag_pipeline(
                str(filepath),
                search_type=search_type,
                k=k,
                return_sources=True,
            )
        st.session_state.rag_chain = chain
        st.session_state.active_index = index_identity
    except Exception as exc:
        st.error("PDF 처리 또는 임베딩에 실패했습니다. API 키/잔액, 패키지, PDF 형식을 확인해 주세요.")
        st.caption(f"오류 유형: {type(exc).__name__}")
        st.stop()

st.success(f"백서 준비 완료: {uploaded.name} · {len(pdf_bytes) / 1024 / 1024:.1f}MB")

st.markdown("**추천 질문**")
cols = st.columns(3)
for i, example in enumerate(EXAMPLES):
    if cols[i].button(example, use_container_width=True, key=f"example_{i}"):
        st.session_state.pending_question = example

st.divider()
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            show_sources(message.get("sources", []))

typed_question = st.chat_input("에이블스쿨에 대해 궁금한 점을 질문하세요")
pending_question = st.session_state.pop("pending_question", None)
question = typed_question or pending_question

if question and question.strip():
    question = question.strip()
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        try:
            with st.spinner("백서에서 근거를 검색하고 답변을 작성하는 중..."):
                result = st.session_state.rag_chain.invoke({"input": question})
            answer, sources = result["answer"], result["sources"]
            st.markdown(answer)
            show_sources(sources)
            st.session_state.messages.append(
                {"role": "assistant", "content": answer, "sources": sources}
            )
        except Exception as exc:
            st.error("답변 생성에 실패했습니다. API 호출 제한이나 연결 상태를 확인해 주세요.")
            st.caption(f"오류 유형: {type(exc).__name__}")

st.caption("이 챗봇은 백서의 검색 결과를 활용합니다. 출력된 페이지와 실제 PDF를 대조해 확인하세요.")
