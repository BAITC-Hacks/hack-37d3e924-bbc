"""Private stage process: offline model loading and no outbound Python sockets."""
import json
import os
from pathlib import Path
import socket
import sys
import time
try:
    import resource
except ImportError:  # pragma: no cover - exercised on Windows
    resource = None

OFFLINE_ENV = {'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','HF_HUB_DISABLE_TELEMETRY':'1',
               'PYANNOTE_METRICS_ENABLED':'0','DO_NOT_TRACK':'1','TOKENIZERS_PARALLELISM':'false'}

def deny_network(event,args):
    if event=='socket.getaddrinfo' or (event in ('socket.connect','socket.sendto') and args and
            getattr(args[0],'family',None) in (socket.AF_INET,socket.AF_INET6)):
        raise PermissionError('Network disabled in inference process')

def peak_rss_bytes():
    if resource is None:
        if sys.platform != 'win32':
            return None
        import ctypes
        from ctypes import wintypes
        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD),
                        ('PeakWorkingSetSize', ctypes.c_size_t), ('WorkingSetSize', ctypes.c_size_t),
                        ('QuotaPeakPagedPoolUsage', ctypes.c_size_t), ('QuotaPagedPoolUsage', ctypes.c_size_t),
                        ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t), ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                        ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t)]
        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        api = ctypes.WinDLL('psapi', use_last_error=True).GetProcessMemoryInfo
        api.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessMemoryCounters), wintypes.DWORD]
        api.restype = wintypes.BOOL
        if not api(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            return None
        return int(counters.PeakWorkingSetSize)
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(rss if sys.platform=='darwin' else rss*1024)

def main():
    os.environ.update(OFFLINE_ENV)
    os.umask(0o077)
    sys.addaudithook(deny_network)
    from .settings import Settings
    from .errors import PipelineError
    stage,folder=sys.argv[1],Path(sys.argv[2])
    request=json.loads((folder/'request.json').read_text(encoding='utf-8'))
    settings=Settings(**request['settings'])
    from .metrics import GpuSampler
    sampler=GpuSampler()
    started=time.monotonic()
    try:
        if stage=='preparing_audio':
            from .audio import prepare_audio
            result={'duration':prepare_audio(request['input']['audio_path'],folder/'audio.wav',settings.max_seconds)}
        elif stage=='transcribing':
            from .asr import transcribe
            result=transcribe(folder/'audio.wav',settings)
        elif stage=='diarizing':
            from .diarization import diarize
            result=diarize(folder/'audio.wav',settings)
        elif stage=='extracting_tasks':
            from .extraction import extract
            segments=json.loads((folder/'segments.json').read_text(encoding='utf-8'))
            result=extract(segments,request['input'],settings)
        else:
            raise PipelineError('PROCESSING_FAILED','Неизвестный этап обработки.')
        (folder/f'{stage}.json').write_text(json.dumps(result,ensure_ascii=False,allow_nan=False),encoding='utf-8')
        sampler.stop()
        torch=sys.modules.get('torch')
        cuda_peak = int(torch.cuda.max_memory_allocated()) if torch and torch.cuda.is_available() else None
        mlx=sys.modules.get('mlx.core')
        mlx_peak = int(mlx.get_peak_memory()) if mlx else None
        metrics={'stage':stage,'wall_seconds':round(time.monotonic()-started,3),
            'peak_rss_bytes':peak_rss_bytes(),
            'torch_peak_cuda_allocated_bytes':cuda_peak,'mlx_peak_allocated_bytes':mlx_peak,
            'sampled_process_gpu_peak_mib':sampler.peak_mib,
            'note':'RSS includes stage process; Torch counter excludes CTranslate2/ONNX allocations.'}
        (folder/f'{stage}.metrics.json').write_text(json.dumps(metrics),encoding='utf-8')
    except Exception as e:
        sampler.stop()
        if isinstance(e,PipelineError):
            code,message=e.code,e.message
        elif isinstance(e,MemoryError) or 'out of memory' in str(e).lower():
            code,message='RESOURCE_EXHAUSTED','Недостаточно памяти для локальной модели.'
        elif isinstance(e,(ImportError,FileNotFoundError)):
            code,message='MODEL_UNAVAILABLE','Не найдены локальные модели или зависимости.'
        else:
            code,message='PROCESSING_FAILED','Локальная модель не завершила обработку.'
        (folder/'error.json').write_text(json.dumps({'code':code,'message':message},ensure_ascii=False),encoding='utf-8')
        return 1
    return 0

if __name__=='__main__':
    sys.exit(main())
