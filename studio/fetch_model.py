"""Download and verify the speech-to-text model once.
Run with:  python -m studio.fetch_model"""
import hashlib
import tarfile
import urllib.request

from . import config

URL = f"https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/{config.ASR_MODEL_NAME}.tar.bz2"
EXPECTED_SHA256 = {
    "sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8":
        "6fc4426b54aa549a0019b8a75b8dea59164e71790a37ac56a045ad57f915f714",
}


def main():
    if (config.ASR_MODEL_DIR / "tokens.txt").exists():
        print("Speech model already present.")
        return
    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = config.MODELS_DIR / "parakeet.tar.bz2"
    expected = EXPECTED_SHA256.get(config.ASR_MODEL_NAME)
    if not expected:
        raise RuntimeError(f"No trusted checksum is configured for ASR model {config.ASR_MODEL_NAME!r}.")
    print("Downloading the speech model (480 MB to 1.1 GB)...")
    digest = hashlib.sha256()
    with urllib.request.urlopen(URL, timeout=60) as response, tmp.open("wb") as out:
        while chunk := response.read(1024 * 1024):
            digest.update(chunk)
            out.write(chunk)
    if digest.hexdigest() != expected:
        tmp.unlink(missing_ok=True)
        raise RuntimeError("Downloaded speech model failed SHA-256 verification.")
    with tarfile.open(tmp, "r:bz2") as t:
        for m in t.getmembers():  # only plain files and folders that stay inside the models folder
            if (m.isfile() or m.isdir()) and not m.name.startswith(("/", "..")) and ".." not in m.name.split("/"):
                t.extract(m, config.MODELS_DIR)
    tmp.unlink()
    print("Speech model ready.")


if __name__ == "__main__":
    main()
