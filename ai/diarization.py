"""Diarize the entire bounded recording, so cluster IDs survive ASR chunk boundaries."""
from pathlib import Path

def diarize(audio_path, settings):
    import soundfile as sf
    audio, sr = sf.read(str(audio_path), dtype='float32')
    if settings.diarizer == 'community1':
        import torch
        from pyannote.audio import Pipeline
        pipeline = Pipeline.from_pretrained(settings.diarization_path)
        pipeline.to(torch.device(settings.device))
        kwargs = {'num_speakers':settings.num_speakers} if settings.num_speakers else {}
        output = pipeline({'waveform':torch.from_numpy(audio).unsqueeze(0), 'sample_rate':sr}, **kwargs)
        turns = [{'start':float(t.start), 'end':float(t.end), 'speaker_id':str(s)}
            for t, s in output.exclusive_speaker_diarization]
        # Standard output still used to report overlapping speech.
        regular = [(t.start,t.end,str(s)) for t,s in output.speaker_diarization]
        overlap = any(a[2] != b[2] and min(a[1],b[1]) > max(a[0],b[0])
                      for i,a in enumerate(regular) for b in regular[i+1:] if b[0] < a[1])
    else:
        import sherpa_onnx as so
        root = Path(settings.diarization_path)
        cfg = so.OfflineSpeakerDiarizationConfig(
            segmentation=so.OfflineSpeakerSegmentationModelConfig(
                pyannote=so.OfflineSpeakerSegmentationPyannoteModelConfig(model=str(root/'segmentation.onnx')),
                num_threads=settings.threads),
            embedding=so.SpeakerEmbeddingExtractorConfig(model=str(root/'embedding.onnx'),num_threads=settings.threads),
            clustering=so.FastClusteringConfig(num_clusters=settings.num_speakers or -1,threshold=.5),
            min_duration_on=.25,min_duration_off=.4)
        if not cfg.validate():
            from .errors import PipelineError
            raise PipelineError('MODEL_UNAVAILABLE','Модели диаризации недоступны.')
        pipeline = so.OfflineSpeakerDiarization(cfg)
        turns = [{'start':float(t.start),'end':float(t.end),'speaker_id':f'SPEAKER_{t.speaker:02d}'}
            for t in pipeline.process(audio).sort_by_start_time()]
        overlap = any(a['speaker_id'] != b['speaker_id'] and min(a['end'],b['end']) > max(a['start'],b['start'])
                      for i,a in enumerate(turns) for b in turns[i+1:] if b['start'] < a['end'])
    return {'turns':sorted(turns,key=lambda t:t['start']), 'overlap':overlap}
