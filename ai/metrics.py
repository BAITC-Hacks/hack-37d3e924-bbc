"""Sample per-process NVIDIA memory; works for Torch, CTranslate2, and ONNX."""
import os
import shutil
import subprocess
import threading

class GpuSampler:
    def __init__(self):
        self.peak_mib=None
        self.stop_event=threading.Event()
        self.thread=None
        if shutil.which('nvidia-smi'):
            self.thread=threading.Thread(target=self._run,daemon=True)
            self.thread.start()

    def _run(self):
        while not self.stop_event.is_set():
            try:
                p=subprocess.run(['nvidia-smi','--query-compute-apps=pid,used_gpu_memory',
                    '--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=2,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                values=[]
                if p.returncode==0:
                    for row in p.stdout.splitlines():
                        fields=row.split(',')
                        if len(fields)==2 and int(fields[0].strip())==os.getpid():
                            values.append(float(fields[1].strip()))
                if values:
                    self.peak_mib=max(self.peak_mib or 0,sum(values))
            except (OSError,ValueError,subprocess.TimeoutExpired):
                pass
            self.stop_event.wait(.25)

    def stop(self):
        self.stop_event.set()
        if self.thread:self.thread.join(timeout=3)
