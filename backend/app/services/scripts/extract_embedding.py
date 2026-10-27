"""
Chay boi ai_env (venv rieng co DeepFace), khong phai venv/global cua backend.
In ra 1 dong JSON duy nhat tren stdout: {"embedding": [...]} hoac {"error": "..."}.
"""
import json
import sys

from deepface import DeepFace


def main():
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: extract_embedding.py <image_path>"}))
        sys.exit(1)

    image_path = sys.argv[1]
    try:
        result = DeepFace.represent(
            img_path=image_path,
            model_name="Facenet512",
            enforce_detection=True,
        )
        print(json.dumps({"embedding": result[0]["embedding"]}))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
