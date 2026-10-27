"""
Trich embedding khuon mat bang cach goi sang ai_env (venv rieng co DeepFace) qua subprocess,
thay vi cai DeepFace/TensorFlow thang vao moi truong chay backend - tranh xung dot dependency
da tung gap voi firebase-admin/httpx (xem memory du an).
"""
import json
import os
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
AI_ENV_PYTHON = ROOT_DIR / "ai_env" / "Scripts" / "python.exe"
EXTRACT_SCRIPT = Path(__file__).resolve().parent / "scripts" / "extract_embedding.py"


FACENET512_THRESHOLD = 0.30  # nguong mac dinh DeepFace dung cho Facenet512 + cosine distance


class FaceEmbeddingError(Exception):
    pass


def cosine_distance(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    return 1 - dot / (norm_a * norm_b)


def extract_embedding(image_path: str) -> list[float]:
    if not AI_ENV_PYTHON.exists():
        raise FaceEmbeddingError(f"Khong tim thay ai_env tai {AI_ENV_PYTHON}")

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    result = subprocess.run(
        [str(AI_ENV_PYTHON), str(EXTRACT_SCRIPT), image_path],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=60,
    )

    # DeepFace/TensorFlow in canh bao ra stdout/stderr, JSON ket qua luon la dong cuoi cung.
    output_lines = [line for line in result.stdout.strip().splitlines() if line.strip()]
    if not output_lines:
        raise FaceEmbeddingError(f"Khong co output tu AI service. stderr: {result.stderr[-500:]}")

    try:
        data = json.loads(output_lines[-1])
    except json.JSONDecodeError:
        raise FaceEmbeddingError(f"Output khong phai JSON hop le: {output_lines[-1][:300]}")

    if "error" in data:
        raise FaceEmbeddingError(data["error"])

    return data["embedding"]
