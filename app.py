"""KT AIVLE School 백서 학습 도우미 — 음성 대화 포함."""

import base64
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
      /* 우측 고정 공식 링크: 스크롤해도 같은 위치에 유지 */
      .aivle-quick-links {position:fixed;right:18px;top:148px;width:184px;z-index:990;
        background:rgba(255,255,255,.97);border:1px solid #d5eae7;border-radius:17px;
        box-shadow:0 8px 24px rgba(15,65,75,.12);padding:14px 12px;box-sizing:border-box;}
      .aivle-quick-links-title {font-size:13px;font-weight:800;color:#176965;margin:0 4px 10px;}
      .aivle-quick-link {display:block;padding:11px 9px;margin-top:7px;border:1px solid #dbece9;
        border-radius:11px;background:#f5fcfa;text-align:center;text-decoration:none!important;
        color:#204a49!important;font-size:13px;font-weight:700;line-height:1.4;}
      .aivle-quick-link:hover {background:#dff5ef;border-color:#8ad4c5;color:#086a64!important;}
      .aivle-mobile-links {display:none;}
      @media (min-width:1320px) {
        /* 본문과 우측 고정 메뉴가 겹치지 않도록 공간 확보 */
        .block-container {padding-right:225px!important;}
      }
      @media (max-width:1319px) {
        .aivle-quick-links {display:none;}
        .aivle-mobile-links {display:block;position:fixed;right:12px;bottom:105px;z-index:990;
          width:194px;background:rgba(255,255,255,.97);border:1px solid #d5eae7;
          border-radius:13px;box-shadow:0 6px 18px rgba(15,65,75,.14);padding:8px;box-sizing:border-box;}
        .aivle-mobile-links summary {cursor:pointer;font-size:13px;font-weight:750;color:#176965;
          padding:6px;list-style-position:inside;}
        .aivle-mobile-links .aivle-quick-link {font-size:12px;padding:8px 6px;}
      }
    </style>
    """,
    unsafe_allow_html=True,
)


# 우측 고정 메뉴에서 연결할 공식 채널
CHARACTER_PAGE = "https://aivle.kt.co.kr/home/micro/main"
INSTAGRAM_URL = "https://www.instagram.com/aivlestory/"
OFFICIAL_SITE_URL = "https://aivle.kt.co.kr/home/main/indexMain"


MAX_UPLOAD_BYTES = 20 * 1024 * 1024
UPLOAD_ROOT = Path(__file__).resolve().parent / ".aivle_data"
# 추천 질문은 사용자 선택을 돕는 예시이며, 답은 업로드한 PDF에서만 검색합니다.
RECOMMENDED_QUESTIONS = {
    '📅 출결': [
        '출석은 어떻게 체크하고 결석 기준은 뭔가요?',
        '수료하려면 출석률이 얼마나 되어야 하나요?',
        '학교 수업이나 취업 면접 때문에 빠지면 공결되나요?',
        '공결이 가능한 대표적인 사유에는 무엇이 있나요?',
        '결석이나 출결 누락이 발생했는데 어디에 문의하나요?',
    ],
    '🎁 지원제도': [
        '에이블스쿨 교육생에게는 어떤 지원과 혜택이 있나요?',
        '수강료는 무료인가요? 자비부담금이 있나요?',
        '훈련장려금은 누구나 자동으로 받나요?',
        '노트북이나 유료 프로그램을 지원받나요?',
        '에이블스쿨 취업지원 프로그램에는 무엇이 있나요?',
    ],
    '🧩 프로젝트': [
        '9기와 10기 DX 트랙 1차 미니프로젝트에서는 무엇을 했나요?',
        '9기와 10기 DX 트랙 2차 미니프로젝트에서는 무엇을 했나요?',
        '9기와 10기 DX 트랙 3차 미니프로젝트에서는 무엇을 했나요?',
        '9기와 10기 DX 트랙 4차 미니프로젝트는 무엇이었나요?',
        '빅프로젝트는 몇 주 동안 어떤 순서로 하나요?',
    ],
    '📚 학습전략': [
        '실습 코드를 따라 쳤는데 다음 날 혼자 작성이 안 됩니다. 어떻게 복습하나요?',
        '수업 복습은 매일 얼마나 해야 하나요?',
        '수업을 따라가기 벅찰 때는 어떻게 공부하나요?',
        '코딩테스트를 준비하려면 어디부터 공부해야 하나요?',
        '스터디를 만들려면 몇 명이 적당하고 어떤 활동을 하나요?',
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

# 우측 고정 외부 링크. 화면이 좁으면 우측 하단에 접히는 메뉴로 표시.
st.markdown(
    f"""
    <nav class="aivle-quick-links" aria-label="AIVLE 공식 사이트 바로가기">
      <div class="aivle-quick-links-title">🔗 공식 바로가기</div>
      <a class="aivle-quick-link" href="{html.escape(INSTAGRAM_URL, quote=True)}" target="_blank" rel="noopener noreferrer">📸 공식 인스타그램</a>
      <a class="aivle-quick-link" href="{html.escape(CHARACTER_PAGE, quote=True)}" target="_blank" rel="noopener noreferrer">👻 공식 캐릭터 소개</a>
      <a class="aivle-quick-link" href="{html.escape(OFFICIAL_SITE_URL, quote=True)}" target="_blank" rel="noopener noreferrer">🌐 공식 사이트</a>
    </nav>
    <details class="aivle-mobile-links">
      <summary>🔗 공식 바로가기</summary>
      <a class="aivle-quick-link" href="{html.escape(INSTAGRAM_URL, quote=True)}" target="_blank" rel="noopener noreferrer">📸 공식 인스타그램</a>
      <a class="aivle-quick-link" href="{html.escape(CHARACTER_PAGE, quote=True)}" target="_blank" rel="noopener noreferrer">👻 공식 캐릭터 소개</a>
      <a class="aivle-quick-link" href="{html.escape(OFFICIAL_SITE_URL, quote=True)}" target="_blank" rel="noopener noreferrer">🌐 공식 사이트</a>
    </details>
    """,
    unsafe_allow_html=True,
)

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


# 업로드한 AIVLE 공식 로고를 앱 파일에 내장해 외부 이미지 경로 없이 표시합니다.
_SIDEBAR_LOGO_PNG = base64.b64decode(
    "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"
)

# 사이드바: 상단 AIVLE 로고와 네 개의 접이식 메뉴만 표시합니다.
with st.sidebar:
    st.image(_SIDEBAR_LOGO_PNG, width=200)
    st.caption("AIVLE School 학습 도우미")
    st.divider()
    with st.expander("💡 추천 질문", expanded=False):
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

    with st.expander("🎧 음성 설정", expanded=False):
        st.toggle(
            "텍스트 질문에도 음성 답변",
            key="voice_reply_to_text",
            help="켜면 직접 입력하거나 추천 질문을 눌러도 음성 파일이 생성됩니다. 음성 질문은 항상 음성 답변을 생성합니다.",
        )

    with st.expander("🔎 검색 설정", expanded=False):
        search_type = st.selectbox("검색 방식", ["mmr", "similarity"], index=0)
        k = st.slider("검색 문단 수", min_value=3, max_value=10, value=6)

    with st.expander("🗑️ 대화 관리", expanded=False):
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
            st.download_button(
                "📥 대화 내역 TXT 다운로드",
                data=transcript.encode("utf-8-sig"),
                file_name="aivle_chat.txt",
                mime="text/plain",
                use_container_width=True,
            )
        st.caption("대화 기록은 현재 브라우저 세션에만 보관됩니다.")

# PDF 업로드는 사이드바 대신 본문 '백서 준비' 영역에 배치합니다.
st.subheader("📄 백서 준비")
uploaded = st.file_uploader(
    "최종 팀 통합 백서 PDF 업로드",
    type=["pdf"],
    help="PDF를 선택하면 해당 문서로 검색 인덱스를 준비합니다.",
    key="manual_pdf_upload",
)
st.caption("🔒 PDF 파일은 GitHub에 업로드하지 않습니다.")

if not configure_api_key():
    st.error("OpenAI API 키가 없습니다. Streamlit Secrets에 OPENAI_API_KEY를 등록하세요.")
    st.stop()

if uploaded is None:
    st.info("위에서 **최종 팀 통합 백서 PDF**를 업로드하면 질문을 시작할 수 있어요.")
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

