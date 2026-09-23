"""Read-only hardware/software inventory. Does not inspect credentials or meeting files."""
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path

def command(args):
    try:
        p=subprocess.run(args,capture_output=True,text=True,timeout=15)
        return p.stdout.strip() if p.returncode==0 else None
    except (OSError,subprocess.TimeoutExpired):return None

def probe():
    packages={}
    for name in ('torch','torchaudio','torchcodec','faster-whisper','ctranslate2','pyannote.audio',
                 'transformers','bitsandbytes','mlx-lm','sherpa-onnx','jsonschema'):
        try:packages[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:packages[name]=None
    usage=shutil.disk_usage(Path.cwd())
    ram=None
    if platform.system()=='Darwin':
        ram=command(['sysctl','-n','hw.memsize'])
        ram=int(ram) if ram else None
    elif Path('/proc/meminfo').exists():
        for line in Path('/proc/meminfo').read_text().splitlines():
            if line.startswith('MemTotal:'):ram=int(line.split()[1])*1024
    gpu=command(['nvidia-smi','--query-gpu=index,name,memory.total,driver_version','--format=csv,noheader,nounits'])
    return {'os':platform.system(),'os_release':platform.release(),'architecture':platform.machine(),
        'python':platform.python_version(),'cpu_count':os.cpu_count(),'ram_bytes':ram,
        'disk_total_bytes':usage.total,'disk_free_bytes':usage.free,'gpu_inventory_csv':gpu,
        'cuda_compiler':command(['nvcc','--version']),'packages':packages,
        'billing':{'provider':'Brev','balance':None,'hourly_rate':None,'storage_rate':None,
                   'status':'Account inspection deferred by user; inventory does not prove availability or budget.'}}

if __name__=='__main__':print(json.dumps(probe(),indent=2))
