"""
Demo truc quan chuc nang nhan dien khuon mat (Access Control) qua webcam.
Buoc 1: Dang ky (enrollment) - chup 1 anh, trich embedding lam "nguoi duoc cap quyen".
Buoc 2: Nhan dien (verify) thoi gian thuc - so khop tung frame webcam voi embedding da dang ky.
Viec nhan dien chay o thread rieng (khong chan luong hien thi camera) de tranh giat/lag.

Chay: ai_env\\Scripts\\python.exe test_data\\webcam_demo.py
Phim tat: 'e' = chup dang ky, 'q' = thoat (o ca 2 buoc)
"""
import threading
import time

import cv2
import numpy as np
from deepface import DeepFace

MODEL = "Facenet512"
DETECTOR = "opencv"
THRESHOLD = 0.30  # nguong mac dinh DeepFace dung cho Facenet512 + cosine
PROCESS_WIDTH = 320  # resize nho lai truoc khi dua vao AI de tang toc nhan dien


def get_embedding(img):
    try:
        reps = DeepFace.represent(
            img, model_name=MODEL, detector_backend=DETECTOR, enforce_detection=True
        )
        return reps[0]["embedding"], reps[0]["facial_area"]
    except Exception:
        return None, None


def cosine_distance(a, b):
    a, b = np.array(a), np.array(b)
    return 1 - np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


class RecognitionWorker(threading.Thread):
    """Chay nhan dien o nen, luon lay frame moi nhat, khong lam nghen camera."""

    def __init__(self, enrolled_embedding):
        super().__init__(daemon=True)
        self.enrolled_embedding = enrolled_embedding
        self.lock = threading.Lock()
        self.latest_frame = None
        self.label = "Dang nhan dien..."
        self.color = (200, 200, 200)
        self.area = None
        self.scale = 1.0
        self.running = True

    def submit_frame(self, frame):
        with self.lock:
            self.latest_frame = frame

    def get_result(self):
        with self.lock:
            return self.label, self.color, self.area, self.scale

    def run(self):
        while self.running:
            with self.lock:
                frame = self.latest_frame
                self.latest_frame = None
            if frame is None:
                time.sleep(0.01)
                continue

            h, w = frame.shape[:2]
            scale = PROCESS_WIDTH / w
            small = cv2.resize(frame, (PROCESS_WIDTH, int(h * scale)))

            emb, area = get_embedding(small)
            if emb is None:
                label, color, area_out = "Khong phat hien khuon mat", (0, 165, 255), None
            else:
                dist = cosine_distance(self.enrolled_embedding, emb)
                if dist <= THRESHOLD:
                    label = f"MO CUA - Da nhan dien (dist={dist:.3f})"
                    color = (0, 200, 0)
                else:
                    label = f"TU CHOI - Khong khop (dist={dist:.3f})"
                    color = (0, 0, 200)
                area_out = area

            with self.lock:
                self.label, self.color, self.area, self.scale = label, color, area_out, scale

    def stop(self):
        self.running = False


def main():
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    if not cap.isOpened():
        raise SystemExit("Khong mo duoc webcam. Kiem tra lai camera/driver.")

    print("=== BUOC 1: DANG KY (ENROLLMENT) ===")
    print("Nhin thang vao camera, nhan 'e' de chup anh dang ky, 'q' de huy")

    enrolled_embedding = None
    while enrolled_embedding is None:
        ret, frame = cap.read()
        if not ret:
            break
        display = frame.copy()
        cv2.putText(display, "Nhan 'e' de dang ky khuon mat, 'q' de thoat",
                    (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.imshow("Access Control Demo - Enrollment", display)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            cap.release()
            cv2.destroyAllWindows()
            raise SystemExit("Da huy demo.")
        if key == ord('e'):
            emb, _ = get_embedding(frame)
            if emb is None:
                print("Khong phat hien khuon mat trong anh, thu lai.")
                continue
            enrolled_embedding = emb
            print("Da dang ky thanh cong khuon mat.")

    cv2.destroyWindow("Access Control Demo - Enrollment")

    print("\n=== BUOC 2: NHAN DIEN (VERIFY) THOI GIAN THUC ===")
    print("Nhan 'q' de thoat")

    worker = RecognitionWorker(enrolled_embedding)
    worker.start()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        worker.submit_frame(frame.copy())
        label, color, area, scale = worker.get_result()

        if area is not None:
            x = int(area["x"] / scale)
            y = int(area["y"] / scale)
            w = int(area["w"] / scale)
            h = int(area["h"] / scale)
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 3)

        cv2.putText(frame, label, (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        cv2.putText(frame, f"Threshold = {THRESHOLD}", (20, frame.shape[0] - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        cv2.imshow("Access Control Demo - Verification", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    worker.stop()
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
