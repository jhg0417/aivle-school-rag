"""KT AIVLE School 백서 학습 도우미 — 음성 대화 포함."""

import hashlib
import io
import html
import os
import re
import uuid
from pathlib import Path

import streamlit as st
from openai import OpenAI



st.set_page_config(
    page_title="AIVLE School | 백서 학습 도우미",
    page_icon="🎓",
    layout="wide",
)

st.markdown(
    """
    <style>
      .stApp {background: #f7fafb;}
      .block-container {max-width: 1120px; padding-top: 2.0rem; padding-bottom: 6rem;}
      [data-testid="stSidebar"] {background: linear-gradient(180deg,#e7f9f5,#f6fcfb);border-right:1px solid #d9ece8;}
      [data-testid="stSidebar"] .stButton button {border-radius: 12px; min-height: 40px;}
      [data-testid="stChatMessage"] {border:1px solid #e4efed;border-radius:16px;background:#ffffff;}
      div.stButton > button[kind="primary"] {background:#098f8b;border-color:#098f8b;color:#fff;}
      div.stButton > button[kind="primary"]:hover {background:#067873;border-color:#067873;}
      .aivle-hero {background:linear-gradient(115deg,#073d4b 0%,#0a8a8c 58%,#32c4af 100%);border-radius:24px;padding:26px 30px;color:white;box-shadow:0 14px 28px rgba(0,92,100,.12);margin-bottom:20px;}
      .aivle-eyebrow {font-size:11px;letter-spacing:1.6px;font-weight:750;opacity:.84;margin-bottom:17px;}
      .aivle-title {display:flex;align-items:center;gap:14px;flex-wrap:wrap;}
      .aivle-title h1 {font-size:29px;font-weight:850;color:white;margin:0;line-height:1.2;letter-spacing:-.04em;}
      .aivle-hero p {color:#e4fffb;margin:17px 0 0;font-size:14px;}
      .aivle-ghost {height:76px;width:76px;object-fit:contain;flex-shrink:0;filter:drop-shadow(0 2px 4px rgba(0,0,0,.15));}
      .aivle-stat {background:white;border:1px solid #e7eeee;padding:15px 18px;border-radius:17px;min-height:76px;box-shadow:0 3px 10px rgba(15,65,75,.03);}
      .aivle-stat small {display:block;font-size:11px;color:#6e9697;margin-bottom:6px;}
      .aivle-stat b {color:#253441;font-size:15px;}
      .sidebar-brand {font-size:27px;font-weight:850;letter-spacing:-1px;color:#18282d;}
      .sidebar-brand em {font-style:normal;color:#14a99f;}
      [data-testid="stChatInput"] {border-radius:15px;}
    </style>
    """,
    unsafe_allow_html=True,
)


# 이미지·캐릭터 소개는 KT AIVLE School 공식 캐릭터 페이지에서 확인된 자료 사용
# 인스타그램 자체의 게시물 이미지는 직접 수집/재게시하지 않음
DANNY_IMAGE = "https://aivle.kt.co.kr/tpl/011/img/micro/danny_full.jpg"
ZZANY_IMAGE = "https://aivle.kt.co.kr/tpl/011/img/micro/zzani_full.jpg"
CHARACTER_PAGE = "https://aivle.kt.co.kr/home/micro/main"
INSTAGRAM_URL = "https://www.instagram.com/aivlestory/"


MAX_UPLOAD_BYTES = 20 * 1024 * 1024
UPLOAD_ROOT = Path(__file__).resolve().parent / ".aivle_data"
# 추천 질문은 사용자 선택을 돕는 예시이며, 답은 업로드한 PDF에서만 검색합니다.
RECOMMENDED_QUESTIONS = {
    "📅 출결": [
        "에이블스쿨의 출석 인정 기준은 무엇인가요?",
        "지각이나 조퇴는 출결에 어떻게 반영되나요?",
        "결석이 발생하면 어떤 절차로 처리해야 하나요?",
        "병원 진료 등으로 수업에 참여하지 못하면 어떻게 하나요?",
        "수료를 위한 출결 조건은 무엇인가요?",
    ],
    "🎁 지원제도": [
        "에이블스쿨 교육생에게 제공되는 지원제도는 무엇인가요?",
        "교육비는 무료인가요? 별도 부담금이 있나요?",
        "훈련장려금이나 교육지원금은 어떤 조건으로 지급되나요?",
        "학습 장비나 교육 자료는 어떻게 지원받을 수 있나요?",
        "취업 지원에는 어떤 프로그램이 포함되어 있나요?",
    ],
    "🧩 프로젝트": [
        "1차 미니프로젝트에서는 무엇을 하나요?",
        "2차 미니프로젝트에서는 무엇을 하나요?",
        "미니프로젝트의 팀 구성과 역할 분담은 어떻게 진행되나요?",
        "빅프로젝트는 어떤 순서로 진행되나요?",
        "프로젝트 결과물과 발표는 어떻게 평가하나요?",
    ],
    "📚 학습전략": [
        "DX 트랙 교육과정을 효과적으로 공부하는 방법은 무엇인가요?",
        "Python과 데이터 분석 기초는 어떤 순서로 복습하면 좋나요?",
        "미니프로젝트를 준비할 때 우선 학습할 역량은 무엇인가요?",
        "팀 프로젝트에서 협업과 일정 관리를 잘하려면 어떻게 해야 하나요?",
        "에이블스쿨 학습 경험을 취업 포트폴리오로 정리하려면 어떻게 하나요?",
    ],
}


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



@st.cache_resource

def get_openai_client():
    """API 키가 설정된 후에 생성하며 Streamlit 재실행 간 재사용."""
    return OpenAI()


def transcribe_audio(uploaded_audio):
    """마이크 음성 → 한국어 텍스트(STT). 원본 음성 파일은 저장하지 않음."""
    audio_file = io.BytesIO(uploaded_audio.getvalue())
    audio_file.name = "question.wav"
    result = get_openai_client().audio.transcriptions.create(
        model="whisper-1", file=audio_file, language="ko"
    )
    return result.text.strip()


def synthesize_answer(answer):
    """AI 답변 텍스트 → MP3(TTS); PDF 근거 번호는 읽지 않음."""
    clean = re.sub(r"\[(?:검색자료|자료)\s*\d+[^]]*\]", "", answer)
    clean = re.sub(r"\(백서\s*\d+쪽\)", "", clean).strip()
    if not clean:
        return None
    result = get_openai_client().audio.speech.create(
        model="tts-1", voice="alloy", input=clean[:3500], response_format="mp3"
    )
    return result.content

# ============================================================
# RAG 백엔드: 별도 파일 없이 app.py에 통합
# ============================================================
from operator import itemgetter
from langchain_pymupdf4llm import PyMuPDF4LLMLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
import json

def format_docs(docs):
    """LLM에 전달하는 검색 문단에 원본 PDF 페이지 붙이기."""
    result = []
    for i, doc in enumerate(docs, 1):
        meta = doc.metadata or {}
        if isinstance(meta.get('page'), int):
            page = f"{meta['page'] + 1}쪽"  # 0부터 시작
        elif isinstance(meta.get('page_number'), int):
            page = f"{meta['page_number']}쪽"
        else:
            page = '페이지 확인 불가'
        result.append(f'[검색자료 {i} | 백서 {page}]\n{doc.page_content}')
    return '\n\n---\n\n'.join(result)


def project_round(question):
    """미니프로젝트 차수를 추출한다. '4차 미니프로젝트의 1일차'는 4차로 해석."""
    q = re.sub(r'\s+', '', question)
    # '1차 프로젝트'처럼 '미니'가 생략된 질문도 지원
    for pattern in (
        r'(?<!\d)(\d+)차미니프로젝트',
        r'미니프로젝트(\d+)차',
        r'(?<!\d)(\d+)차미프',
        r'(?<!\d)(\d+)차프로젝트',
    ):
        match = re.search(pattern, q)
        if match:
            return match.group(1)
    return None


def exact_project_docs(question, all_docs, limit=2):
    """차수가 명시된 경우 그 차수를 직접 다루는 FAQ 청크를 우선 확보."""
    number = project_round(question)
    if number is None:
        return []

    target = f'{number}차미니프로젝트'
    candidates = []
    for doc in all_docs:
        normalized = re.sub(r'\s+', '', doc.page_content)
        if target not in normalized:
            continue
        # Q011. 9기 DX 트랙 1차미니프로젝트에서는... 같은 직접 질문 우대.
        faq_headings = re.findall(r'Q\d{1,3}\.(.{0,130}?\?)', normalized)
        exact_faq = any(target in heading for heading in faq_headings)
        if exact_faq:
            score = 3
        elif '미니프로젝트' in normalized:
            score = 1
        else:
            score = 0
        candidates.append((score, doc))

    candidates.sort(key=lambda row: row[0], reverse=True)
    return [doc for _, doc in candidates[:limit]]


def rag_pipeline(filepath, search_type='mmr', k=6, return_sources=False):
    """입력 {'input': 질문}; 기본 출력 str, return_sources=True면 답변+근거."""
    filepath = os.path.abspath(filepath)
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f'PDF 파일을 찾을 수 없습니다: {filepath}')
    if search_type not in ('mmr', 'similarity'):
        raise ValueError("search_type은 'mmr' 또는 'similarity'여야 합니다.")
    if not isinstance(k, int) or k <= 0:
        raise ValueError('k는 1 이상의 정수여야 합니다.')

    chunk_size, chunk_overlap = 1200, 200
    embed_model = 'text-embedding-3-small'
    db_dir = os.path.join(os.path.dirname(filepath), 'chroma_db')
    manifest_path = os.path.join(db_dir, 'aivle_index_info.json')
    os.makedirs(db_dir, exist_ok=True)

    embeddings = OpenAIEmbeddings(model=embed_model)
    vectorstore = Chroma(
        collection_name='aivle_docs',
        persist_directory=db_dir,
        embedding_function=embeddings,
    )

    with open(filepath, 'rb') as f:
        pdf_sha = hashlib.sha256(f.read()).hexdigest()
    signature = f'{pdf_sha}|{chunk_size}|{chunk_overlap}|{embed_model}|page-v1'
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            saved = json.load(f)
    except (OSError, json.JSONDecodeError):
        saved = {}

    existing_ids = vectorstore.get(include=[])['ids']
    reuse = (
        saved.get('signature') == signature
        and existing_ids
        and len(existing_ids) == saved.get('chunks')
    )

    if reuse:
        print(f'기존 Chroma DB 재사용: {len(existing_ids)}개 청크 (재임베딩 없음)')
    else:
        print('새 문서/설정 감지 → PDF 로딩, 분할, 임베딩 시작')
        docs = [d for d in PyMuPDF4LLMLoader(filepath, mode='page').load()
                if d.page_content.strip()]
        if not docs:
            raise ValueError('PDF에서 텍스트를 추출할 수 없습니다.')
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap,
            separators=['\n\n', '\n', ' ', ''],
        )
        chunks = splitter.split_documents(docs)
        if os.path.isfile(manifest_path):
            os.remove(manifest_path)  # 인덱싱 실패 시 정상 DB로 오인하지 않기
        vectorstore.reset_collection()
        for start in range(0, len(chunks), 100):
            vectorstore.add_documents(chunks[start:start + 100])
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump({'signature': signature, 'chunks': len(chunks)}, f)
        print(f'PDF {len(docs)}페이지 / {len(chunks)}청크 인덱싱 완료')

    # MMR 기본 검색 (특정 사실 질문에서는 차수 정확 매칭을 앞에 추가)
    count = len(vectorstore.get(include=[])['ids'])
    actual_k = min(k, count)
    if search_type == 'mmr':
        base_retriever = vectorstore.as_retriever(
            search_type='mmr',
            search_kwargs={
                'k': actual_k,
                'fetch_k': min(max(25, actual_k * 4), count),
                'lambda_mult': 0.45,
            },
        )
    else:
        base_retriever = vectorstore.as_retriever(
            search_type='similarity',
            search_kwargs={'k': actual_k},
        )

    # 이미 저장된 청크를 검색할 뿐, 임베딩 API를 다시 호출하지 않음
    db_data = vectorstore.get(include=['documents', 'metadatas'])
    all_docs = [
        Document(page_content=text, metadata=meta or {})
        for text, meta in zip(db_data['documents'], db_data['metadatas'])
    ]

    def improved_retrieve(question):
        exact_docs = exact_project_docs(question, all_docs, limit=2)
        semantic_docs = base_retriever.invoke(question)
        combined, seen = [], set()
        for doc in exact_docs + semantic_docs:
            identity = (doc.metadata.get('page'), doc.page_content)
            if identity not in seen:
                combined.append(doc)
                seen.add(identity)
            if len(combined) >= actual_k:
                break
        return combined

    retriever = RunnableLambda(improved_retrieve)

    prompt = ChatPromptTemplate.from_messages([
        ('system', '''당신은 KT AIVLE School 백서 기반 학습 도우미입니다.
반드시 아래 검색자료에 근거해 한국어로 답하세요.

규칙:
1. 자료에 없는 내용은 추측하지 말고 확인되지 않는다고 안내하세요.
2. 10기 당시의 모집·금액·일정·출결 규정을 현재 기준으로 단정하지 마세요.
3. 선배 경험은 해당 기수의 사례로 설명하고 모든 기수에 일반화하지 마세요.
4. 취업 연계와 채용 우대는 최종 합격 보장과 다릅니다.
5. 포괄적인 질문이면 여러 후기를 공통점과 차이점으로 종합하세요.
6. 추천은 가능하지만 공식 규정과 개인적인 권장 사항을 구분하세요.
7. '1차 미니프로젝트'는 첫 번째 프로젝트이고,
   '4차 미니프로젝트의 1일차'는 네 번째 프로젝트의 첫날입니다.
   프로젝트 차수와 교육 일차를 절대 혼동하지 마세요.
8. 질문한 차수에 해당하는 자료만 그 차수의 근거로 제시하세요.
   9기 후기만 있다면 '9기 후기 사례'라고 표시하세요.
9. 사용한 근거의 PDF 페이지를 '(백서 N쪽)' 형식으로 표기하세요.
   자료에 없는 쪽수를 만들지 마세요.

[검색자료]
{context}'''),
        ('human', '{question}'),
    ])

    llm = ChatOpenAI(model='gpt-4o-mini', temperature=0)
    rag_chain = (
        {'context': itemgetter('input') | retriever | format_docs,
         'question': itemgetter('input')}
        | prompt | llm | StrOutputParser()
    )

    # 검색 진단용: Colab에서 사용하던 인터페이스도 유지
    rag_pipeline.last_retriever = retriever
    rag_pipeline.last_vectorstore = vectorstore

    if return_sources:
        # 검색 근거를 먼저 확보한 후, 동일한 근거로 스트리밍 답변.
        answer_chain = prompt | llm | StrOutputParser()

        class SourceAwareRAG:
            def _prepare(self, payload):
                question = payload['input']
                docs = retriever.invoke(question)
                sources = []
                for doc in docs:
                    metadata = doc.metadata or {}
                    if isinstance(metadata.get('page'), int):
                        page = metadata['page'] + 1
                    elif isinstance(metadata.get('page_number'), int):
                        page = metadata['page_number']
                    else:
                        page = None
                    sources.append({
                        'page': page,
                        'excerpt': doc.page_content[:700],
                    })
                return question, docs, sources

            def invoke(self, payload):
                question, docs, sources = self._prepare(payload)
                answer = answer_chain.invoke({
                    'context': format_docs(docs),
                    'question': question,
                })
                return {'answer': answer, 'sources': sources}

            def stream(self, payload):
                question, docs, sources = self._prepare(payload)
                yield {'kind': 'sources', 'sources': sources}
                for text_chunk in answer_chain.stream({
                    'context': format_docs(docs),
                    'question': question,
                }):
                    if text_chunk:
                        yield {'kind': 'token', 'text': text_chunk}

        return SourceAwareRAG()

    return rag_chain


def initialize_session():
    if "upload_session_id" not in st.session_state:
        st.session_state.upload_session_id = uuid.uuid4().hex
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "active_index" not in st.session_state:
        st.session_state.active_index = None
    if "document_digest" not in st.session_state:
        st.session_state.document_digest = None
    if "mascot" not in st.session_state:
        st.session_state.mascot = "다니 (DANNY)"
    if "last_voice_digest" not in st.session_state:
        st.session_state.last_voice_digest = None
    if "voice_reply_to_text" not in st.session_state:
        st.session_state.voice_reply_to_text = False


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

# 사용자 요청: 제목의 손바닥 이모지 대신 작은 다니 유령 이미지
# 이미지 로딩 실패 시 CSS 안에 대체 유령 이모지를 표시합니다.
st.markdown(
    f"""<section class="aivle-hero">
      <div class="aivle-eyebrow">KT AIVLE SCHOOL · STUDY ASSISTANT</div>
      <div class="aivle-title">
        <h1>AIVLE 백서에게 물어보세요</h1>
        <img class="aivle-ghost"
             src="https://raw.githubusercontent.com/jhg0417/aivle-school-rag/main/character.png"
             alt="AIVLE 캐릭터" />
      </div>
      <p>업로드한 AIVLE 백서를 바탕으로 궁금한 점을 설명해 드릴게요.</p>
    </section>""",
    unsafe_allow_html=True,
)

left, center, right = st.columns(3)
with left:
    st.markdown('<div class="aivle-stat"><small>답변 방식</small><b>업로드한 PDF 기반 RAG</b></div>', unsafe_allow_html=True)
with center:
    st.markdown('<div class="aivle-stat"><small>지원 기능</small><b>텍스트 · 음성 질문/답변</b></div>', unsafe_allow_html=True)
with right:
    st.markdown(f'<div class="aivle-stat"><small>대화 기록</small><b>{sum(m["role"]=="user" for m in st.session_state.messages)}개 질문</b></div>', unsafe_allow_html=True)


# 문서 업로드는 필수이며, 서버 파일이나 Drive에서 자동으로 불러오지 않는다.
with st.sidebar:
    st.markdown('<div class="sidebar-brand"><em>✳</em> AIVLE</div>', unsafe_allow_html=True)
    st.caption("AIVLE School 학습 도우미")
    st.divider()
    st.subheader("📎 PDF 자료 추가 · 필수")
    uploaded = st.file_uploader(
        "질문에 사용할 AIVLE School PDF를 직접 선택하세요",
        type=["pdf"],
        help="수동으로 PDF를 선택해야 RAG가 시작됩니다. 자동 업로드는 하지 않습니다.",
        key="manual_pdf_upload",
    )
    st.caption("🔒 PDF 파일은 GitHub에 업로드하지 않습니다.")
    st.divider()

    # 캐릭터는 눌렀을 때만 표시하고, 너비를 제한합니다.
    with st.expander("👻 AIVLE 캐릭터 보기", expanded=False):
        mascot = st.radio(
            "캐릭터 선택",
            ["다니 (DANNY)", "짜니 (ZZANY)"],
            key="mascot",
            horizontal=True,
        )
        image_url = DANNY_IMAGE if mascot.startswith("다니") else ZZANY_IMAGE
        st.image(image_url, width=145, caption=mascot)
        st.link_button("📸 공식 인스타그램", INSTAGRAM_URL, use_container_width=True)
        st.link_button("👻 공식 캐릭터 소개", CHARACTER_PAGE, use_container_width=True)
    st.divider()

    st.subheader("🔎 검색 설정")
    search_type = st.selectbox("검색 방식", ["mmr", "similarity"], index=0)
    k = st.slider("검색 문단 수", min_value=3, max_value=10, value=6)

    st.divider()
    st.subheader("🎧 음성 답변 설정")
    st.toggle(
        "텍스트 질문에도 음성 답변",
        key="voice_reply_to_text",
        help="켜면 직접 입력하거나 추천 질문을 눌러도 음성 파일이 생성됩니다. 음성 질문은 항상 음성 답변을 생성합니다.",
    )
    # '추천 질문 메뉴'를 열고 주제를 고르면 해당 질문 5개를 표시합니다.
    with st.expander("💡 추천 질문 메뉴", expanded=False):
        selected_topic = st.selectbox(
            "질문 주제 선택",
            options=list(RECOMMENDED_QUESTIONS.keys()),
            key="recommended_topic",
        )
        for index, example in enumerate(RECOMMENDED_QUESTIONS[selected_topic]):
            if st.button(
                example,
                key=f"sidebar_example_{selected_topic}_{index}",
                use_container_width=True,
            ):
                st.session_state.pending_question = example
                st.rerun()
    st.divider()
    st.subheader("🗑️ 대화 관리")
    if st.button("마지막 질문·답변 삭제", use_container_width=True):
        messages = st.session_state.messages
        if messages:
            if messages[-1]["role"] == "assistant":
                messages.pop()
            if messages and messages[-1]["role"] == "user":
                messages.pop()
        st.session_state.pop("pending_question", None)
        st.rerun()
    if st.button("전체 대화 삭제", type="secondary", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pop("pending_question", None)
        st.rerun()

    if st.session_state.messages:
        transcript = "\n\n".join(
            ("사용자" if m["role"] == "user" else "AI 도우미")
            + ":\n" + m["content"]
            for m in st.session_state.messages
        )
        st.download_button("📥 대화 내역 TXT 다운로드",
                           data=transcript.encode("utf-8-sig"),
                           file_name="aivle_chat.txt", mime="text/plain",
                           use_container_width=True)
    st.caption("대화 기록은 현재 브라우저 세션에만 보관됩니다.")


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

# 캐릭터는 사이드바에서 선택했을 때만 표시하므로 메인 영역에서는 제외합니다.

st.divider()
st.caption("🎤 음성으로 질문하면 인식된 질문과 답변이 모두 채팅에 기록되고, 답변은 MP3 플레이어로 들을 수 있어요.")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "user" and message.get("input_type") == "voice":
            st.caption("🎙️ 음성 질문 · 음성 인식 결과")
        if message["role"] == "assistant" and message.get("reply_type") == "voice":
            st.caption("🔊 AI 음성 답변 · 텍스트와 함께 표시")
        st.markdown(message["content"])
        if message["role"] == "assistant":
            if message.get("audio_bytes"):
                st.audio(message["audio_bytes"], format="audio/mp3")
            show_sources(message.get("sources", []))

# 음성 입력은 PDF가 업로드되고 인덱싱된 이후에만 노출됩니다.
with st.expander("🎙️ 음성으로 질문하기", expanded=False):
    recorded = st.audio_input("질문을 말한 뒤 녹음을 완료하세요", key="voice_question_audio")
    if recorded is not None:
        if st.button("🎤 음성 질문 전송", type="primary", key="send_voice"):
            digest = hashlib.sha256(recorded.getvalue()).hexdigest()
            if digest == st.session_state.last_voice_digest:
                st.info("이미 보낸 녹음입니다. 새로 녹음해 주세요.")
            else:
                try:
                    with st.spinner("음성을 글자로 변환하는 중..."):
                        transcript = transcribe_audio(recorded)
                    if not transcript:
                        st.warning("음성을 인식하지 못했습니다. 다시 녹음해 주세요.")
                    else:
                        st.session_state.pending_question = transcript
                        st.session_state.pending_input_type = "voice"
                        st.session_state.last_voice_digest = digest
                        st.rerun()
                except Exception as exc:
                    st.error("음성 인식에 실패했습니다. 마이크 권한과 API 설정을 확인해 주세요.")
                    st.caption(f"오류 유형: {type(exc).__name__}")

# 추천 질문 클릭 시에도 텍스트 질문과 동일하게 처리됩니다.
typed_question = st.chat_input("예: 출결 인정 기준은 어떻게 되나요?")
pending_question = st.session_state.pop("pending_question", None)
question = typed_question or pending_question
input_type = "text" if typed_question else st.session_state.pop("pending_input_type", "text")

if question and question.strip():
    question = question.strip()
    st.session_state.messages.append({
        "role": "user", "content": question, "input_type": input_type,
    })
    with st.chat_message("user"):
        if input_type == "voice":
            st.caption("🎙️ 음성 질문 · 음성 인식 결과")
        st.markdown(question)
    with st.chat_message("assistant"):
        try:
            source_holder = {}

            def stream_rag_reply():
                for event in st.session_state.rag_chain.stream({"input": question}):
                    if event["kind"] == "sources":
                        source_holder["sources"] = event["sources"]
                    elif event["kind"] == "token":
                        yield event["text"]

            answer = st.write_stream(stream_rag_reply())
            sources = source_holder.get("sources", [])
            voice_reply = input_type == "voice" or st.session_state.voice_reply_to_text
            if voice_reply:
                st.caption("🔊 AI 음성 답변 · 텍스트와 함께 표시")
            st.markdown(answer)
            audio_bytes = None
            if voice_reply:
                try:
                    with st.spinner("AI 답변 음성을 생성하는 중..."):
                        audio_bytes = synthesize_answer(answer)
                    if audio_bytes:
                        st.audio(audio_bytes, format="audio/mp3")
                except Exception as speech_exc:
                    st.warning("텍스트 답변은 생성되었지만 음성 생성에는 실패했습니다.")
                    st.caption(f"음성 오류 유형: {type(speech_exc).__name__}")
            show_sources(sources)
            st.session_state.messages.append({
                "role": "assistant",
                "content": answer,
                "sources": sources,
                "audio_bytes": audio_bytes,
                "reply_type": "voice" if voice_reply else "text",
            })
        except Exception as exc:
            st.error("답변 생성에 실패했습니다. API 호출 제한이나 연결 상태를 확인해 주세요.")
            st.caption(f"오류 유형: {type(exc).__name__}")

st.caption("이 챗봇은 업로드한 PDF에서 검색한 내용을 근거로 답합니다. 음성은 OpenAI STT/TTS API를 통해 처리됩니다.")
