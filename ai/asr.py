"""Explicit interchangeable local ASR implementations; no fallback."""
from pathlib import Path
from .audio import windows, owned_words, deduplicate_words

def ctc_words(logits, token_map, offset, duration):
    ids = logits.argmax(-1).tolist()
    blank, step = max(token_map)+1, duration/max(len(ids),1)
    words, chars, start, end, previous = [], [], None, 0, None
    def flush():
        nonlocal chars, start
        if chars:
            words.append({'text': ''.join(chars), 'start': offset+start, 'end': offset+end})
        chars, start = [], None
    for i, token in enumerate(ids):
        if token == previous:
            if chars and token != blank:
                end = (i+1)*step
            continue
        previous = token
        if token == blank:
            continue
        symbol = token_map.get(token, '')
        if symbol in ('|','_',' '):
            flush()
        elif symbol and symbol != '[UNK]':
            if start is None:
                start = i*step
            chars.append(symbol)
            end = (i+1)*step
    flush()
    return words

def ctc_token_map(asr_path):
    tokens = {}
    for line in (Path(asr_path)/'tokens.lst').read_text(encoding='utf-8').splitlines():
        if line.strip():
            symbol, index = line.split('\t')
            tokens[int(index)] = symbol
    return tokens

def transcribe(audio_path, settings):
    import soundfile as sf
    words = []
    with sf.SoundFile(str(audio_path)) as audio:
        duration, sr = len(audio)/audio.samplerate, audio.samplerate
        if settings.asr == 'whisper':
            from faster_whisper import WhisperModel
            model = WhisperModel(settings.asr_path, device=settings.device, compute_type=settings.compute_type,
                cpu_threads=settings.threads, local_files_only=True, num_workers=1)
            for a,b,left,right in windows(duration):
                audio.seek(int(left*sr))
                clip = audio.read(int((right-left)*sr), dtype='float32')
                segments, _ = model.transcribe(clip, language=settings.language, task='transcribe',
                    beam_size=5, word_timestamps=True, condition_on_previous_text=False,
                    vad_filter=True, vad_parameters={'min_silence_duration_ms':500})
                decoded = [{'text': w.word, 'start': left+w.start, 'end': min(duration,left+w.end)}
                    for s in segments for w in (s.words or [])]
                words.extend(owned_words(decoded,a,b))
        else:
            import torch
            torch.set_num_threads(settings.threads)
            model = torch.jit.load(str(Path(settings.asr_path)/'model.pt'), map_location=settings.device).eval()
            tokens = ctc_token_map(settings.asr_path)
            for a,b,left,right in windows(duration, core=12, context=.8):
                audio.seek(int(left*sr))
                clip = audio.read(int((right-left)*sr), dtype='float32')
                with torch.inference_mode():
                    outputs = model(torch.from_numpy(clip).unsqueeze(0).to(settings.device))
                    logits = outputs[0] if isinstance(outputs,(tuple,list)) else outputs
                    if logits.ndim == 3:
                        logits = logits[0]
                    decoded = ctc_words(logits.cpu(),tokens,left,len(clip)/sr)
                words.extend(owned_words(decoded,a,b))
    return deduplicate_words(words)
