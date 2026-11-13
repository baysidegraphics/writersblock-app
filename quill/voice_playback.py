"""Project-scoped optional Quill audio controls. No editorial operations."""
def render(st,state,synthesize):
    from .wbs_quill_streamlit_ui import VOICE_ENABLED_KEY,VOICE_GENDER_KEY,LAST_RESPONSE_KEY,LAST_SPOKEN_KEY,VOICE_ERROR_KEY
    # Retain complete audio through normal reruns. Voice is optional and
    # scoped by the same Quill project/revision reset as the response.
    if bool(state.get(VOICE_ENABLED_KEY, False)):
        latest_quill_text = str(state.get(LAST_RESPONSE_KEY) or "").strip()
        if latest_quill_text:
            import hashlib
            gender=str(state.get(VOICE_GENDER_KEY,"Male") or "Male")
            signature=hashlib.sha256((gender+"\0"+latest_quill_text).encode()).hexdigest()
            replay=bool(state.pop("_wbs_quill_voice_replay",False))
            if st.button("Replay complete response",key="_wbs_quill_replay_response"):
                replay=True
            changed=signature!=state.get(LAST_SPOKEN_KEY)
            if changed or replay:
                state[LAST_SPOKEN_KEY]=signature
                try:
                    cache=state.get("_wbs_quill_voice_audio") or {}
                    if cache.get("signature")!=signature:
                        cache={"signature":signature,"data":synthesize(latest_quill_text,gender)}
                    if not cache.get("data"):raise RuntimeError("No audio was generated.")
                    state["_wbs_quill_voice_audio"]=cache
                    state[VOICE_ERROR_KEY]=""
                except Exception:
                    state.pop("_wbs_quill_voice_audio",None)
                    state[VOICE_ERROR_KEY]="Local speech is unavailable. Text remains available; use Replay to try again."
            cache=state.get("_wbs_quill_voice_audio") or {}
            if cache.get("signature")==signature and cache.get("data"):
                if changed or replay:
                    state['_wbs_quill_voice_player_generation']=int(state.get('_wbs_quill_voice_player_generation',0))+1
                # A new container key remounts the ended media element for replay;
                # audio bytes remain cached, with no new synthesis or provider call.
                with st.container(key='_wbs_quill_voice_player_'+str(state.get('_wbs_quill_voice_player_generation',0))):
                    # Inline cached WAV bytes to avoid a separate Cloud media request.
                    import base64
                    audio_uri="data:audio/wav;base64,"+base64.b64encode(cache["data"]).decode("ascii")
                    st.audio(audio_uri,format="audio/wav",autoplay=changed or replay)

        voice_error=str(state.get(VOICE_ERROR_KEY) or "")
        if voice_error:st.caption("Quill voice: "+voice_error)
