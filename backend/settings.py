import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    database: Path
    mode: str = 'real'
    max_upload: int = 100 * 1024 * 1024

    @classmethod
    def from_env(cls):
        data = Path(os.environ.get('DATA_DIR', '.local/app')).resolve()
        mode = os.environ.get('PIPELINE_MODE', 'real')
        if mode not in {'real', 'fixture'}:
            raise ValueError('PIPELINE_MODE must be real or fixture')
        return cls(data, Path(os.environ.get('DATABASE_PATH', str(data / 'meetings.sqlite3'))).resolve(),
                   mode, int(os.environ.get('MAX_UPLOAD_BYTES', 100 * 1024 * 1024)))

    @property
    def audio_dir(self):
        return self.data_dir / 'audio'
