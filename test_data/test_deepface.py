from deepface import DeepFace
import numpy as np

IMG_PATH = "ngocanh_01.jpg"

print("=== Test 1: Trich embedding khuon mat ===")
result = DeepFace.represent(
    img_path=IMG_PATH,
    model_name="Facenet512",
    enforce_detection=True,
)

print(f"So khuon mat phat hien duoc: {len(result)}")
embedding = result[0]["embedding"]
print(f"Do dai vector embedding: {len(embedding)} (ky vong 512)")
print(f"5 gia tri dau: {embedding[:5]}")

facial_area = result[0]["facial_area"]
print(f"Vi tri khuon mat trong anh: {facial_area}")

print()
print("=== Test 2: So khop anh voi chinh no (sanity check) ===")
verify_result = DeepFace.verify(
    img1_path=IMG_PATH,
    img2_path=IMG_PATH,
    model_name="Facenet512",
)
print(f"Verified (nen la True): {verify_result['verified']}")
print(f"Distance (nen gan 0): {verify_result['distance']:.6f}")
print(f"Threshold mac dinh cua model: {verify_result['threshold']}")

print()
print("=== KET LUAN ===")
print("DeepFace + FaceNet512 chay duoc tren Python 3.13 - KHONG co loi tuong thich.")
