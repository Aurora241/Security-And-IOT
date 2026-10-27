import cv2
from deepface import DeepFace

IMG1 = "test_1.jpg"
IMG2 = "test_2.jpg"
OUT = "demo_result.jpg"

TARGET_H = 480

result = DeepFace.verify(
    img1_path=IMG1,
    img2_path=IMG2,
    model_name="Facenet512",
)

verified = result["verified"]
distance = result["distance"]
threshold = result["threshold"]
area1 = result["facial_areas"]["img1"]
area2 = result["facial_areas"]["img2"]

BOX_COLOR = (0, 200, 0) if not verified else (0, 0, 200)


def prep(img_path, area):
    img = cv2.imread(img_path)
    x, y, w, h = area["x"], area["y"], area["w"], area["h"]
    cv2.rectangle(img, (x, y), (x + w, y + h), BOX_COLOR, 4)
    scale = TARGET_H / img.shape[0]
    img = cv2.resize(img, (int(img.shape[1] * scale), TARGET_H))
    return img


img1 = prep(IMG1, area1)
img2 = prep(IMG2, area2)

import numpy as np

gap = 40
banner_h = 140
w_total = img1.shape[1] + gap + img2.shape[1]
canvas = np.full((TARGET_H + banner_h, w_total, 3), 255, dtype=np.uint8)
canvas[banner_h:, : img1.shape[1]] = img1
canvas[banner_h:, img1.shape[1] + gap :] = img2

verdict_text = "TRUNG KHOP (verified=True)" if verified else "KHAC NGUOI (verified=False)"
verdict_color = (0, 0, 200) if verified else (0, 150, 0)

cv2.putText(canvas, "DeepFace Facenet512 - Face Verification Demo", (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
cv2.putText(canvas, f"Distance = {distance:.4f}   Threshold = {threshold}", (20, 75),
            cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 0), 2)
cv2.putText(canvas, verdict_text, (20, 115),
            cv2.FONT_HERSHEY_SIMPLEX, 0.9, verdict_color, 2)

cv2.imwrite(OUT, canvas)
print(f"Da luu anh demo: {OUT}")
print(f"Verified: {verified} | Distance: {distance:.4f} | Threshold: {threshold}")
