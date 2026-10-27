"""
Threshold sweep + tinh FAR/FRR cho FaceNet512 (DeepFace) - chay boi ai_env (venv co DeepFace),
KHONG phai venv/global cua backend. Dung cho Ngay 3 cua ke hoach 8 ngay (17-27/10 sprint
Access Control), thay the threshold mac dinh 0.30 dang dung tam trong
backend/app/services/face_embedding.py bang nguong chon tu du lieu test thuc.

Cau truc dataset mong doi (tao thu muc nay roi bo anh vao, 1 thu muc = 1 nguoi):
    test_data/far_frr_dataset/
        nguoianh_01/   anh1.jpg  anh2.jpg  anh3.jpg ...
        nguoibinh_02/  anh1.jpg  anh2.jpg ...
        ...
    Ten thu muc chi dung de nhan dien trong ket qua, khong anh huong tinh toan.
    Can >=2 anh/nguoi de co "genuine pair" (cung 1 nguoi) va >=2 nguoi de co
    "impostor pair" (2 nguoi khac nhau) - thieu 1 trong 2 thi FRR hoac FAR se khong tinh duoc.

Dinh nghia (giong huong dan GVHD):
    FAR (False Acceptance Rate) = ti le cap "2 nguoi KHAC nhau" nhung bi he thong bao KHOP
                                   (distance <= threshold) - nguoi la duoc nhan la nguoi quen.
    FRR (False Rejection Rate)  = ti le cap "CUNG 1 nguoi" nhung bi he thong bao KHONG khop
                                   (distance > threshold) - nguoi quen bi tu choi oan.
    EER (Equal Error Rate)      = diem threshold ma FAR va FRR gan bang nhau nhat - thuong
                                   dung lam nguong de xuat thay cho so mac dinh 0.30.

Cach chay:
    cd "C:\\Users\\Admin\\Security and IOT"
    set PYTHONIOENCODING=utf-8 && ai_env\\Scripts\\python.exe test_data\\threshold_sweep.py test_data\\far_frr_dataset

Ket qua:
    - In ra console: so luong genuine/impostor pair, FAR/FRR tai threshold mac dinh 0.30,
      threshold de xuat (EER) va FAR/FRR tai do.
    - test_data/threshold_sweep_result.csv  - bang day du FAR/FRR tai moi threshold (dan vao
      bao cao duoc luon, khong can ve lai).
    - test_data/threshold_sweep_chart.jpg   - do thi FAR/FRR theo threshold (ve bang OpenCV,
      ai_env khong co matplotlib - giong demo_visual.py).
"""
import argparse
import csv
import sys
from itertools import combinations
from pathlib import Path

import cv2
import numpy as np
from deepface import DeepFace

MODEL_NAME = "Facenet512"
DEFAULT_THRESHOLD = 0.30  # phai khop FACENET512_THRESHOLD trong backend/app/services/face_embedding.py
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def cosine_distance(a: list[float], b: list[float]) -> float:
    # Cong thuc giong y app/services/face_embedding.py de ket qua nhat quan voi backend.
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    return 1 - dot / (norm_a * norm_b)


def load_embeddings(dataset_dir: Path) -> dict[str, list[list[float]]]:
    """Tra ve {ten_nguoi: [embedding1, embedding2, ...]}. Anh khong detect duoc mat se bi
    bo qua (in canh bao), khong lam dung chuong trinh."""
    embeddings_by_person: dict[str, list[list[float]]] = {}

    person_dirs = sorted(p for p in dataset_dir.iterdir() if p.is_dir())
    if not person_dirs:
        print(f"Khong tim thay thu muc nguoi nao trong {dataset_dir}")
        return embeddings_by_person

    for person_dir in person_dirs:
        image_paths = sorted(
            p for p in person_dir.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS
        )
        embeddings = []
        for image_path in image_paths:
            try:
                result = DeepFace.represent(
                    img_path=str(image_path), model_name=MODEL_NAME, enforce_detection=True
                )
                embeddings.append(result[0]["embedding"])
            except Exception as e:  # noqa: BLE001 - anh loi (khong co mat, mo...) thi bo qua, khong dung ca batch
                print(f"  [bo qua] {image_path.name}: khong trich duoc embedding ({e})")
        print(f"{person_dir.name}: {len(embeddings)}/{len(image_paths)} anh trich embedding thanh cong")
        if embeddings:
            embeddings_by_person[person_dir.name] = embeddings

    return embeddings_by_person


def build_pair_distances(embeddings_by_person: dict[str, list[list[float]]]) -> tuple[list[float], list[float]]:
    """Tra ve (genuine_distances, impostor_distances)."""
    genuine_distances = []
    for embeddings in embeddings_by_person.values():
        for a, b in combinations(embeddings, 2):
            genuine_distances.append(cosine_distance(a, b))

    impostor_distances = []
    people = list(embeddings_by_person.items())
    for (name_a, emb_a), (name_b, emb_b) in combinations(people, 2):
        for a in emb_a:
            for b in emb_b:
                impostor_distances.append(cosine_distance(a, b))

    return genuine_distances, impostor_distances


def far_frr_at(threshold: float, genuine: list[float], impostor: list[float]) -> tuple[float, float]:
    far = (sum(1 for d in impostor if d <= threshold) / len(impostor)) if impostor else float("nan")
    frr = (sum(1 for d in genuine if d > threshold) / len(genuine)) if genuine else float("nan")
    return far, frr


def sweep(genuine: list[float], impostor: list[float], step: float = 0.01) -> list[tuple[float, float, float]]:
    max_dist = max(genuine + impostor, default=1.0)
    thresholds = np.arange(0.0, max_dist + step, step)
    rows = []
    for t in thresholds:
        far, frr = far_frr_at(float(t), genuine, impostor)
        rows.append((float(t), far, frr))
    return rows


def find_eer(rows: list[tuple[float, float, float]]) -> tuple[float, float, float]:
    """Diem threshold co |FAR-FRR| nho nhat trong cac dong co ca 2 gia tri hop le."""
    valid = [r for r in rows if not (np.isnan(r[1]) or np.isnan(r[2]))]
    if not valid:
        raise ValueError("Khong co du du lieu de tinh EER - can >=2 nguoi VA >=2 anh/nguoi")
    return min(valid, key=lambda r: abs(r[1] - r[2]))


def draw_chart(rows: list[tuple[float, float, float]], out_path: Path, eer_point: tuple[float, float, float]) -> None:
    W, H, MARGIN = 800, 500, 60
    canvas = np.full((H, W, 3), 255, dtype=np.uint8)

    valid = [r for r in rows if not (np.isnan(r[1]) or np.isnan(r[2]))]
    if not valid:
        cv2.imwrite(str(out_path), canvas)
        return

    max_t = max(r[0] for r in valid)

    def to_px(t: float, rate: float) -> tuple[int, int]:
        x = MARGIN + int((t / max_t) * (W - 2 * MARGIN)) if max_t > 0 else MARGIN
        y = H - MARGIN - int(rate * (H - 2 * MARGIN))
        return x, y

    cv2.line(canvas, (MARGIN, H - MARGIN), (W - MARGIN, H - MARGIN), (0, 0, 0), 2)  # truc X (threshold)
    cv2.line(canvas, (MARGIN, H - MARGIN), (MARGIN, MARGIN), (0, 0, 0), 2)  # truc Y (ti le)

    for i in range(1, len(valid)):
        cv2.line(canvas, to_px(valid[i - 1][0], valid[i - 1][1]), to_px(valid[i][0], valid[i][1]), (255, 0, 0), 2)  # FAR xanh
        cv2.line(canvas, to_px(valid[i - 1][0], valid[i - 1][2]), to_px(valid[i][0], valid[i][2]), (0, 0, 255), 2)  # FRR do

    ex, ey = to_px(eer_point[0], eer_point[1])
    cv2.circle(canvas, (ex, ey), 6, (0, 150, 0), -1)
    cv2.putText(canvas, f"EER~{eer_point[0]:.2f}", (ex + 8, ey), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 150, 0), 1)

    cv2.putText(canvas, "FAR (xanh)", (MARGIN, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
    cv2.putText(canvas, "FRR (do)", (MARGIN + 130, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
    cv2.putText(canvas, "threshold ->", (W - MARGIN - 90, H - MARGIN + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)

    cv2.imwrite(str(out_path), canvas)


def main() -> None:
    parser = argparse.ArgumentParser(description="Threshold sweep + FAR/FRR cho FaceNet512")
    parser.add_argument("dataset_dir", help="Thu muc chua 1 thu muc con/nguoi, moi thu muc nhieu anh")
    parser.add_argument("--out", default=None, help="File CSV ket qua (mac dinh: <dataset_dir>/../threshold_sweep_result.csv)")
    parser.add_argument("--chart", default=None, help="File anh do thi (mac dinh: <dataset_dir>/../threshold_sweep_chart.jpg)")
    parser.add_argument("--step", type=float, default=0.01, help="Buoc nhay threshold khi sweep (mac dinh 0.01)")
    args = parser.parse_args()

    dataset_dir = Path(args.dataset_dir)
    if not dataset_dir.is_dir():
        print(f"Khong tim thay thu muc dataset: {dataset_dir}")
        sys.exit(1)

    out_csv = Path(args.out) if args.out else dataset_dir.parent / "threshold_sweep_result.csv"
    out_chart = Path(args.chart) if args.chart else dataset_dir.parent / "threshold_sweep_chart.jpg"

    print(f"Dang trich embedding tu {dataset_dir} ...")
    embeddings_by_person = load_embeddings(dataset_dir)
    if len(embeddings_by_person) < 2:
        print("Can >=2 nguoi co it nhat 1 anh trich embedding thanh cong de tinh FAR. Dung lai.")
        sys.exit(1)

    genuine, impostor = build_pair_distances(embeddings_by_person)
    print(f"\nSo genuine pair (cung 1 nguoi): {len(genuine)}")
    print(f"So impostor pair (2 nguoi khac nhau): {len(impostor)}")
    if not genuine:
        print("CANH BAO: khong co genuine pair nao (moi nguoi chi co 1 anh) - FRR se la NaN, "
              "khong tinh duoc EER dang hoan chinh. Them it nhat 2 anh/nguoi.")

    far_default, frr_default = far_frr_at(DEFAULT_THRESHOLD, genuine, impostor)
    print(f"\nTai threshold mac dinh dang dung ({DEFAULT_THRESHOLD}): FAR={far_default:.4f}  FRR={frr_default:.4f}")

    rows = sweep(genuine, impostor, step=args.step)

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["threshold", "FAR", "FRR"])
        for t, far, frr in rows:
            writer.writerow([f"{t:.4f}", f"{far:.4f}" if not np.isnan(far) else "", f"{frr:.4f}" if not np.isnan(frr) else ""])
    print(f"Da luu bang day du: {out_csv}")

    try:
        eer_t, eer_far, eer_frr = find_eer(rows)
        print(f"\nThreshold de xuat (EER, |FAR-FRR| nho nhat): {eer_t:.4f}  (FAR={eer_far:.4f}, FRR={eer_frr:.4f})")
        draw_chart(rows, out_chart, (eer_t, eer_far, eer_frr))
        print(f"Da luu do thi: {out_chart}")
    except ValueError as e:
        print(f"\nKhong tinh duoc EER: {e}")


if __name__ == "__main__":
    main()
