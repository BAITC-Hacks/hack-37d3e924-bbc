"""Create a labeled two-voice smoke recording using installed macOS voices.
The recording is synthetic, not meeting-quality or speaker-identity ground truth.
"""

import argparse
import json
import platform
import subprocess
from pathlib import Path

RU = "Айжан, подготовь отчёт к завтрашнему дню. Нам нужны точные цифры расходов. Это поручение нужно выполнить завтра."
KK = "Жақсы, мен есепті ертең дайындаймын. Марсель, кестені жаңартшы. Мерзімі әзірге белгісіз. Бюджет бойынша ұсыныс дайындаңыз."

INTRA = "Ерлан, подготовьте отчёт жұмаға дейін. Алия, бюджет бойынша ұсыныс дайындаңыз."


def main():
    p = argparse.ArgumentParser()
    p.add_argument("directory", type=Path)
    args = p.parse_args()
    if platform.system() != "Darwin":
        p.error("Requires macOS with Aru and Milena voices installed")
    import numpy as np
    import soundfile as sf

    from .audio import prepare_audio

    folder = args.directory.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    for name, voice, text in [
        ("ru", "Milena (Russian (Russia))", RU),
        ("kk", "Aru", KK),
        ("intra", "Aru", INTRA),
    ]:
        subprocess.run(
            ["say", "-v", voice, "-o", str(folder / (name + ".aiff")), text], check=True
        )
        prepare_audio(folder / (name + ".aiff"), folder / (name + ".wav"))
    parts = []
    reference_turns = []
    at = 0
    for name in ["ru", "kk", "ru", "kk"]:
        samples, sr = sf.read(folder / (name + ".wav"), dtype="float32")
        parts.append(samples)
        reference_turns.append(
            {"start": at, "end": at + len(samples) / sr, "speaker_id": name}
        )
        at += len(samples) / sr
        parts.append(np.zeros(16000, dtype="float32"))
        at += 1
    audio = folder / "mixed-two-speakers.wav"
    sf.write(audio, np.concatenate(parts), 16000)
    request = json.loads(
        (Path(__file__).parent / "fixtures/input.json").read_text(encoding="utf-8")
    )
    request.update(meeting_id="synthetic-mixed-two-speakers", audio_path=str(audio))
    (folder / "input.json").write_text(
        json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (folder / "asr-manifest.json").write_text(
        json.dumps(
            [
                {
                    "id": "ru-synthetic",
                    "audio_path": str(folder / "ru.wav"),
                    "reference": RU,
                },
                {
                    "id": "mixed-two-synthetic",
                    "audio_path": str(audio),
                    "reference": " ".join([RU, KK, RU, KK]),
                },
                {
                    "id": "mixed-intra-synthetic",
                    "audio_path": str(folder / "intra.wav"),
                    "reference": INTRA,
                },
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (folder / "reference-turns.json").write_text(
        json.dumps(reference_turns, indent=2), encoding="utf-8"
    )
    print(
        "SYNTHETIC demo created. Turn envelopes include pauses; do not treat as hand-labeled DER reference."
    )


if __name__ == "__main__":
    main()
