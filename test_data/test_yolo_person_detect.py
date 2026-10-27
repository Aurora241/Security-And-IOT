"""
Sanity-check YOLOv8 (model pretrained COCO) phat hien duoc class "person", truoc khi
tich hop vao backend module Alarm - mo phong dung cach test_deepface.py da validate
DeepFace truoc khi tich hop vao Access Control.

COCO class "person" co index = 0 (thu tu chuan trong COCO 80-class).

2 che do:
- Mac dinh (khong co arg): chay tren anh mau co san trong test_data/ (headless, khong
  can webcam/man hinh - de tu dong xac nhan ket qua).
- "webcam": mo webcam laptop, ve box truc tiep (phim 'q' de thoat) - chay thu cong.

Chay anh mau:  yolo_env\\Scripts\\python.exe test_data\\test_yolo_person_detect.py
Chay webcam:   yolo_env\\Scripts\\python.exe test_data\\test_yolo_person_detect.py webcam
"""
import sys
from pathlib import Path

from ultralytics import YOLO
import cv2

SCRIPT_DIR = Path(__file__).parent

MODEL_NAME = "yolov8n.pt"  # ban nano - nhe, nhanh, du de sanity-check tren laptop
PERSON_CLASS_ID = 0
CONF_THRESHOLD = 0.5
SAMPLE_IMAGES = ["test_1.jpg", "test_2.jpg", "ngocanh_01.jpg"]


def draw_detections(frame, result):
    for box in result.boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        conf = float(box.conf[0])
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 200, 0), 2)
        cv2.putText(frame, f"person {conf:.2f}", (x1, max(0, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 0), 2)
    return frame


def run_on_sample_images(model):
    print("\n=== SANITY CHECK: phat hien 'person' tren anh mau (headless) ===")
    any_detected = False
    for name in SAMPLE_IMAGES:
        img_path = SCRIPT_DIR / name
        results = model.predict(str(img_path), conf=CONF_THRESHOLD, classes=[PERSON_CLASS_ID], verbose=False)
        result = results[0]
        n = len(result.boxes)
        print(f"{name}: phat hien {n} nguoi"
              + (f" (confidence cao nhat = {float(result.boxes.conf.max()):.3f})" if n else ""))
        if n:
            any_detected = True
            out_path = SCRIPT_DIR / f"yolo_demo_{name}"
            annotated = draw_detections(result.orig_img.copy(), result)
            cv2.imwrite(str(out_path), annotated)
            print(f"  -> da luu anh ket qua: {out_path}")

    print("\n=== KET LUAN ===")
    if any_detected:
        print("YOLOv8 pretrained phat hien duoc 'person' tren anh mau - san sang thiet ke module Alarm.")
    else:
        print("KHONG phat hien duoc 'person' tren bat ky anh mau nao - kiem tra lai anh/nguong confidence.")


def run_on_webcam(model):
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    if not cap.isOpened():
        raise SystemExit("Khong mo duoc webcam. Kiem tra lai camera/driver.")

    print("\n=== SANITY CHECK: phat hien 'person' qua webcam ===")
    print("Nhan 'q' de thoat")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        results = model.predict(frame, conf=CONF_THRESHOLD, classes=[PERSON_CLASS_ID], verbose=False)
        result = results[0]
        draw_detections(frame, result)

        cv2.putText(frame, f"So nguoi phat hien: {len(result.boxes)}", (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.imshow("YOLOv8 Sanity Check - Person Detection", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


def main():
    print("=== Dang tai model YOLOv8 pretrained (COCO) ===")
    model = YOLO(MODEL_NAME)
    print(f"Model da tai xong. So class COCO: {len(model.names)}")
    print(f"Class 0 = '{model.names[0]}' (ky vong 'person')")

    if len(sys.argv) > 1 and sys.argv[1] == "webcam":
        run_on_webcam(model)
    else:
        run_on_sample_images(model)


if __name__ == "__main__":
    main()
