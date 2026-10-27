"""
Script giam sat lien tuc cho module Alarm - kien truc da chot khac voi DeepFace
(face_embedding.py goi ai_env qua subprocess MOI LAN 1 anh): o day can real-time, khong
the load lai model YOLO moi frame, nen chay 1 TIEN TRINH RIENG lien tuc bang yolo_env, giu
model + webcam luon mo, tu GOI API backend khi da xac nhan xam nhap - khong dua tung frame
tho qua API.

Trach nhiem chia doi ro:
- Script nay (client, yolo_env): chi lo phat hien NGUOI + debounce (>=3 frame lien tiep).
- Backend (/api/v1/alarm/detections): lo enforcement (dung gio/zone armed) + chong spam
  (cooldown 60s) + ghi alarm_events/snapshots + bat coi MQTT + ghi alarm_notifications.
  Script KHONG tu lam cooldown - goi API moi frame con nguoi sau khi debounce dat, backend
  se tu tra "ignored_cooldown" neu qua gan event truoc, khong ton hai gi (API nhe, khong co
  side effect khi bi cooldown).

CAMERA_ID phai dung dung UUID cua ban ghi "Webcam Laptop" da seed trong bang `cameras`
(Supabase) - neu seed lai camera moi, nho doi lai gia tri nay.

Chay: yolo_env\\Scripts\\python.exe test_data\\alarm_monitor.py
Phim tat: 'q' = thoat
"""
import base64
import time

import cv2
import requests
from ultralytics import YOLO

MODEL_NAME = "yolov8n.pt"
PERSON_CLASS_ID = 0
CONF_THRESHOLD = 0.5
DEBOUNCE_FRAMES = 3  # can >=3 frame lien tiep deu thay nguoi moi goi API bao xam nhap

BACKEND_URL = "http://localhost:8001/api/v1/alarm/detections"
CAMERA_ID = "173888ec-b468-45a6-8482-58f0f7ae0be6"  # id thuc cua camera "Webcam Laptop" trong Supabase


def encode_snapshot(frame) -> str:
    ok, buf = cv2.imencode(".jpg", frame)
    if not ok:
        return ""
    return base64.b64encode(buf.tobytes()).decode("ascii")


def report_detection(camera_id: str, confidence: float, box: list[int], frame) -> dict:
    payload = {
        "camera_id": camera_id,
        "confidence": confidence,
        "bounding_box": {"x1": box[0], "y1": box[1], "x2": box[2], "y2": box[3]},
        "snapshot_base64": encode_snapshot(frame),
    }
    try:
        resp = requests.post(BACKEND_URL, json=payload, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        print(f"[CANH BAO] Khong goi duoc backend ({BACKEND_URL}): {exc}")
        return {"status": "api_error", "event_id": None}


def main():
    print("=== Dang tai model YOLOv8 ===")
    model = YOLO(MODEL_NAME)

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    if not cap.isOpened():
        raise SystemExit("Khong mo duoc webcam. Kiem tra lai camera/driver.")

    print(f"=== Giam sat Alarm dang chay - bao ve {BACKEND_URL} ===")
    print("Nhan 'q' de thoat")

    consecutive_person_frames = 0
    last_status = ""

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        results = model.predict(frame, conf=CONF_THRESHOLD, classes=[PERSON_CLASS_ID], verbose=False)
        result = results[0]
        has_person = len(result.boxes) > 0

        if has_person:
            consecutive_person_frames += 1
            box = result.boxes[0]
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            conf = float(box.conf[0])
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 165, 255), 2)
        else:
            consecutive_person_frames = 0

        if consecutive_person_frames >= DEBOUNCE_FRAMES:
            report = report_detection(CAMERA_ID, conf, [x1, y1, x2, y2], frame)
            last_status = report["status"]
            if last_status == "intrusion":
                print(f"[XAM NHAP] alarm_event_id={report['event_id']}")

        color = {"intrusion": (0, 0, 200), "ignored_cooldown": (0, 165, 255)}.get(last_status, (200, 200, 200))
        cv2.putText(frame, f"Nguoi lien tiep: {consecutive_person_frames}/{DEBOUNCE_FRAMES} | status: {last_status}",
                    (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        cv2.imshow("Alarm Monitor - YOLOv8", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
