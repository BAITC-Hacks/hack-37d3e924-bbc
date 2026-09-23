"""Local decoding and bounded ASR windows; timestamps always use source seconds."""
import math
import subprocess
from pathlib import Path
from .errors import PipelineError

def prepare_audio(source, destination, max_seconds=3600, allowed_formats=None):
    import imageio_ffmpeg
    import soundfile as sf
    path = Path(source)
    if not path.is_file():
        raise PipelineError('INVALID_AUDIO', 'Аудиофайл недоступен worker-процессу.')
    # Reject URLs and network protocols, including those inside input playlists.
    proc = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-v', 'error', '-nostdin', '-y',
        '-protocol_whitelist', 'file,pipe',
        *(['-format_whitelist', ','.join(allowed_formats)] if allowed_formats else []),
        '-i', str(path.resolve()), '-vn', '-t', str(max_seconds+1),
        '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(destination)], capture_output=True, timeout=180)
    if proc.returncode:
        raise PipelineError('INVALID_AUDIO', 'Не удалось декодировать аудио.')
    duration = sf.info(str(destination)).duration
    if not .5 <= duration <= max_seconds:
        raise PipelineError('INVALID_AUDIO', 'Длительность аудио вне настроенного диапазона.')
    return duration

def windows(duration, core=24.0, context=2.0):
    """Disjoint ownership intervals plus acoustic context on both sides."""
    for index in range(math.ceil(duration / core)):
        start, end = index*core, min(duration, (index+1)*core)
        yield start, end, max(0, start-context), min(duration, end+context)

def owned_words(words, core_start, core_end):
    return [w for w in words if core_start <= (w['start']+w['end'])/2 < core_end and w['end'] > w['start']]

def deduplicate_words(words):
    result = []
    for word in sorted(words, key=lambda w: (w['start'], w['end'])):
        if result:
            prev = result[-1]
            overlap = max(0, min(prev['end'],word['end'])-max(prev['start'],word['start']))
            shortest = min(prev['end']-prev['start'],word['end']-word['start'])
            if word['text'].strip().casefold() == prev['text'].strip().casefold() and shortest > 0 and overlap/shortest > .5:
                continue
        result.append(word)
    return result

def align(words, turns):
    segments, uncertain = [], False
    for word in deduplicate_words(words):
        candidates = [(max(0, min(word['end'],t['end'])-max(word['start'],t['start'])),t['speaker_id']) for t in turns]
        scores = {}
        for score, speaker in candidates:
            scores[speaker] = scores.get(speaker, 0) + score
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        speaker = ranked[0][0] if ranked and ranked[0][1] > 0 else 'SPEAKER_UNKNOWN'
        uncertain |= speaker == 'SPEAKER_UNKNOWN' or len([v for v in scores.values() if v > 0]) > 1
        text = word['text'].strip()
        if not text:
            continue
        if segments and segments[-1]['speaker_id'] == speaker and word['start']-segments[-1]['end'] < .8 and word['end']-segments[-1]['start'] < 20:
            segments[-1]['text'] += ' ' + text
            segments[-1]['end'] = max(segments[-1]['end'], word['end'])
        else:
            segments.append({'id': f's{len(segments)+1}', 'speaker_id': speaker,
                'start': word['start'], 'end': word['end'], 'text': text})
    return segments, uncertain
