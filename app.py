
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
