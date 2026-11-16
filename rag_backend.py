"""KT AIVLE School 백서 RAG — 프로젝트 차수 검색 보강 버전.

Colab 설치 셀 (이 파일 실행 전):
%pip install -q -U langchain-pymupdf4llm langchain-text-splitters langchain-openai langchain-chroma langchain-core

사용 예:
    rag_chain = rag_pipeline(path + 'AIVLE School 백서.pdf')
    print(rag_chain.invoke({'input': 'DX 트랙 1차 미니프로젝트에서는 어떤 과제를 수행하나요?'}))
"""

import hashlib
import json
import os
import re
from operator import itemgetter

from langchain_pymupdf4llm import PyMuPDF4LLMLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda


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
        # 웹 화면에서는 검색을 한 번만 수행하고, 같은 문단으로 답변과 출처를 만든다.
        answer_chain = prompt | llm | StrOutputParser()

        def run_with_sources(payload):
            question = payload['input']
            docs = retriever.invoke(question)
            answer = answer_chain.invoke({
                'context': format_docs(docs),
                'question': question,
            })
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
            return {'answer': answer, 'sources': sources}

        return RunnableLambda(run_with_sources)

    return rag_chain
