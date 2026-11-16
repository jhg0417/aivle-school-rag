# KT AIVLE School — 4차 미니프로젝트 2일차 Streamlit

이 패키지는 1일차에 만든 `rag_pipeline()`을 Streamlit 챗봇에 연결한 것입니다.
PDF 업로드 후 자동 벡터화, 문서 변경 감지, 재임베딩 방지, 추천 질문, 대화 삭제,
답변 근거 PDF 페이지 확인을 지원합니다.

## 파일 구성

- `app.py`: Streamlit 웹 UI / 업로드 / Session State
- `rag_backend.py`: 기존 RAG 파이프라인 + `return_sources=True` 옵션
- `requirements.txt`: Streamlit Cloud와 로컬 실행용 라이브러리
- `.streamlit/config.toml`: 기본 UI와 최대 업로드 크기
- `.gitignore`: API 키, 업로드 PDF, Chroma DB 등 공개 방지

**팀 통합 백서 PDF와 API 키는 ZIP에 포함하지 않았습니다.** 실제 웹에서 PDF를 업로드하세요.

## 방법 A — 로컬 PC에서 먼저 테스트 (Windows)

1. 폴더에 압축을 해제합니다.
2. 터미널(명령 프롬프트, PowerShell, VS Code)을 이 폴더에서 엽니다.
3. Python 3.12를 권장합니다.
4. 의존성을 설치합니다.

   ```bash
   python -m pip install -r requirements.txt
   ```

5. 프로젝트 폴더에 `.streamlit/secrets.toml` 파일을 생성합니다.

   ```toml
   OPENAI_API_KEY = "여기에_본인의_API_키"
   ```

   해당 파일은 GitHub에 올리지 마세요.

6. 웹 서버 실행:

   ```bash
   python -m streamlit run app.py
   ```

7. 브라우저의 Streamlit 화면에서 `aivle_whitepaper_final.pdf` (팀 통합 백서)를 업로드합니다.
8. 추천 질문 또는 직접 입력으로 테스트합니다.

## 방법 B — Streamlit Community Cloud에 배포

1. GitHub에 새 저장소를 만들고 **app.py, rag_backend.py, requirements.txt, .streamlit/config.toml, .gitignore**를 업로드합니다. API 키와 백서 PDF는 올리지 않습니다.
2. https://share.streamlit.io 에 접속해 GitHub 저장소 연결 후 New app 생성.
3. Main file path는 `app.py`로 지정합니다.
4. Advanced settings에서 Python 3.12를 선택하고 Secrets에 다음 내용을 넣습니다.

   ```toml
   OPENAI_API_KEY = "여기에_본인의_API_키"
   ```

5. Deploy한 뒤 앱의 **왼쪽 PDF 업로드**를 이용합니다.

Cloud의 저장소는 재시작되면 사라질 수 있습니다. 같은 세션에서는 체인을 재사용하고,
문서가 같고 인덱스가 남아 있다면 재임베딩하지 않습니다. 새로운 세션·재배포·서버 재시작 시
업로드/인덱싱을 다시 해야 할 수 있습니다.

## 기존 Colab 코드와의 관계

- 기존 1일차 코드: `rag_chain = rag_pipeline(filepath)`, `rag_chain.invoke({"input":"..."})` → **문자열 답변**
- 웹 UI용 옵션: `rag_chain = rag_pipeline(filepath, return_sources=True)`, `.invoke({"input":"..."})` → **`{"answer": str, "sources": [...]}`**
- RAG 검색 설정은 기존과 동일하게 `MMR`, `k=6`, 청크 1,200/200, OpenAI 임베딩, Chroma입니다.

## 필수 검증 질문

1. `DX 트랙 1차 미니프로젝트에서는 어떤 과제를 수행하나요?` — **9기 후기 기준 공공주차장/불법주정차**
2. `에이블스쿨을 수료하면 취업이 보장되나요?` — **합격 보장은 아님**
3. `에이블스쿨이 취업에 어떤 도움이 되나요?` — **여러 후기 종합**
4. `11기 잡페어의 정확한 날짜와 참가 기업은?` — **미확인 답변**

검색 문단과 답변의 페이지 번호가 실제 백서의 근거와 일치하는지 확인하세요.

## 유의사항

- OpenAI API 사용료가 발생합니다.
- 백서에 외부 배포가 제한된 운영 자료가 섞여 있을 수 있습니다. 공개 배포 전에 공유 가능 여부를 확인하세요.
- 기본 버전은 **화면에 대화 내역을 보여주지만**, 이전 질문을 RAG 검색 질의에 자동으로 포함하지는 않습니다.
  즉, `그럼 그건?` 같은 이어지는 질문은 독립 질문으로 풀어쓰는 편이 정확합니다.
- 현재 업로드 파일은 앱 서버의 `.aivle_data` 아래에 저장되며, 공개 GitHub에는 추가되지 않습니다.
  공개 운영 전 접근 제어와 업로드 데이터 보존·삭제 정책을 검토하세요.
- PDF가 바뀌면 이전 대화 기록을 초기화하고 새 문서로 다시 벡터화합니다.
