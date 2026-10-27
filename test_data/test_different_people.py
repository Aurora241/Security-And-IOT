from deepface import DeepFace

IMG1 = "test_1.jpg"
IMG2 = "test_2.jpg"

print("=== Test: DeepFace phan biet 2 nguoi KHAC nhau ===")
result = DeepFace.verify(
    img1_path=IMG1,
    img2_path=IMG2,
    model_name="Facenet512",
)

print(f"Verified (ky vong False): {result['verified']}")
print(f"Distance (ky vong > threshold): {result['distance']:.6f}")
print(f"Threshold mac dinh cua model: {result['threshold']}")

print()
print("=== KET LUAN ===")
if not result["verified"] and result["distance"] > result["threshold"]:
    print("DUNG: DeepFace phan biet dung 2 nguoi khac nhau (khong nham lan).")
else:
    print("SAI: DeepFace nham 2 nguoi khac nhau la cung 1 nguoi - can kiem tra lai anh/threshold.")
