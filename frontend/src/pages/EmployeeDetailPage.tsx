import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, DEVICE_ID } from "../api/client";
import type { AccessCredential, Employee } from "../api/types";
import PolicyPanel from "../components/PolicyPanel";

type StatusCls = "ok" | "err" | "wait";

function StatusLine({ text, cls }: { text: string; cls: StatusCls }) {
  if (!text) return null;
  return <div className={`status-line ${cls}`}>{text}</div>;
}

function captureFrame(video: HTMLVideoElement): string {
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext("2d")!.drawImage(video, 0, 0);
  return canvas.toDataURL("image/jpeg", 0.9);
}

function FaceEnrollCard({ employeeId, onEnrolled }: { employeeId: string; onEnrolled: () => void }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [camOn, setCamOn] = useState(false);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<{ text: string; cls: StatusCls }>({ text: "", cls: "wait" });

  const startCam = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      if (videoRef.current) videoRef.current.srcObject = stream;
      setCamOn(true);
    } catch (e) {
      setStatus({ text: "Không mở được camera: " + (e as Error).message, cls: "err" });
    }
  };

  const captureAndEnroll = async () => {
    if (!videoRef.current) return;
    setBusy(true);
    setStatus({ text: "Đang trích embedding và lưu, chờ vài giây...", cls: "wait" });
    try {
      const imageBase64 = captureFrame(videoRef.current);
      const data = await api.post<{ id: string }>(`/employees/${employeeId}/credentials/face`, {
        employee_id: employeeId,
        image_base64: imageBase64,
      });
      setStatus({ text: `Đăng ký thành công! Credential ID: ${data.id}`, cls: "ok" });
      onEnrolled();
    } catch (e) {
      setStatus({ text: "Lỗi: " + (e as Error).message, cls: "err" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card">
      <h2>Đăng ký khuôn mặt</h2>
      <video ref={videoRef} autoPlay playsInline muted />
      <div className="row" style={{ marginTop: 8 }}>
        <button className="btn secondary" onClick={startCam}>
          Bật camera
        </button>
        <button className="btn" disabled={!camOn || busy} onClick={captureAndEnroll}>
          Chụp & đăng ký
        </button>
      </div>
      <StatusLine {...status} />
    </div>
  );
}

function FaceVerifyCard({ employeeId }: { employeeId: string }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [camOn, setCamOn] = useState(false);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<{ text: string; cls: StatusCls }>({ text: "", cls: "wait" });

  const startCam = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      if (videoRef.current) videoRef.current.srcObject = stream;
      setCamOn(true);
    } catch (e) {
      setStatus({ text: "Không mở được camera: " + (e as Error).message, cls: "err" });
    }
  };

  const captureAndVerify = async () => {
    if (!videoRef.current) return;
    setBusy(true);
    setStatus({ text: "Đang so sánh với dữ liệu đã đăng ký...", cls: "wait" });
    try {
      const imageBase64 = captureFrame(videoRef.current);
      const data = await api.post<{ verified: boolean; distance: number; threshold: number; result: string }>(
        `/employees/${employeeId}/credentials/face/verify`,
        { employee_id: employeeId, image_base64: imageBase64 }
      );
      const matchText = data.verified ? "KHỚP" : "KHÔNG KHỚP";
      setStatus({
        text: `${matchText} (distance=${data.distance.toFixed(4)}, ngưỡng=${data.threshold}) -> kết quả: ${data.result.toUpperCase()}`,
        cls: data.result === "accepted" ? "ok" : "err",
      });
    } catch (e) {
      setStatus({ text: "Lỗi: " + (e as Error).message, cls: "err" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card">
      <h2>Test xác thực khuôn mặt</h2>
      <video ref={videoRef} autoPlay playsInline muted />
      <div className="row" style={{ marginTop: 8 }}>
        <button className="btn secondary" onClick={startCam}>
          Bật camera
        </button>
        <button className="btn" disabled={!camOn || busy} onClick={captureAndVerify}>
          Chụp & xác thực
        </button>
      </div>
      <StatusLine {...status} />
    </div>
  );
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function FingerprintEnrollCard({
  employeeId,
  employeeCode,
  onEnrolled,
}: {
  employeeId: string;
  employeeCode: string;
  onEnrolled: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<{ text: string; cls: StatusCls }>({ text: "", cls: "wait" });

  const run = async () => {
    setBusy(true);
    try {
      setStatus({ text: "Đang lấy slot ID và gửi lệnh xuống ESP32...", cls: "wait" });
      const slotRes = await api.get<{ slot_id: number }>(`/devices/${DEVICE_ID}/next-slot`);
      const slotId = slotRes.slot_id;

      const before = await api.get<AccessCredential[]>(`/employees/${employeeId}/credentials`);
      const beforeIds = new Set(before.filter((c) => c.type === "fingerprint" && c.is_active).map((c) => c.id));

      await api.post(`/devices/${DEVICE_ID}/enroll-fingerprint`, { employee_code: employeeCode, slot_id: slotId });

      setStatus({
        text: `Đã gửi lệnh (slot #${slotId}) - đặt ngón tay lên cảm biến AS608 2 lần khi ESP32 yêu cầu... (tối đa 60s)`,
        cls: "wait",
      });

      const start = Date.now();
      let lastStep = "";
      while (Date.now() - start < 60000) {
        await sleep(700);
        try {
          const progress = await api.get<{ step: string; message: string }>(`/devices/${DEVICE_ID}/enroll-progress`);
          if (progress.step && progress.step !== lastStep) {
            lastStep = progress.step;
            if (progress.step === "error") {
              setStatus({ text: `[${slotId}] ${progress.message}`, cls: "err" });
              setBusy(false);
              return;
            }
            setStatus({ text: `[${slotId}] ${progress.message}`, cls: "wait" });
          }
        } catch {
          // bo qua loi tam thoi khi poll tien trinh
        }

        const list = await api.get<AccessCredential[]>(`/employees/${employeeId}/credentials`);
        const found = list.find((c) => c.type === "fingerprint" && c.is_active && !beforeIds.has(c.id));
        if (found) {
          setStatus({ text: `Đăng ký vân tay thành công! Credential ID: ${found.id}`, cls: "ok" });
          onEnrolled();
          setBusy(false);
          return;
        }
      }
      setStatus({ text: "Hết thời gian chờ (60s) - kiểm tra lại ESP32/MQTT/backend.", cls: "err" });
    } catch (e) {
      setStatus({ text: "Lỗi: " + (e as Error).message, cls: "err" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card">
      <h2>Đăng ký vân tay (qua ESP32)</h2>
      <p className="muted">
        Bấm nút, ESP32 sẽ tự động bắt đầu quét - chỉ cần đặt ngón tay lên cảm biến AS608 2 lần khi được yêu cầu.
      </p>
      <button className="btn" disabled={busy} onClick={run}>
        Bắt đầu đăng ký vân tay
      </button>
      <StatusLine {...status} />
    </div>
  );
}

function FingerprintVerifyCard({ employeeId, employeeCode }: { employeeId: string; employeeCode: string }) {
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<{ text: string; cls: StatusCls }>({ text: "", cls: "wait" });

  const run = async () => {
    setBusy(true);
    try {
      setStatus({ text: "Đang gửi lệnh xác thực xuống ESP32...", cls: "wait" });
      await api.post(`/devices/${DEVICE_ID}/verify-fingerprint`, { employee_code: employeeCode, employee_id: employeeId });
      setStatus({ text: "Đã gửi lệnh - đặt ngón tay lên cảm biến AS608... (tối đa 30s)", cls: "wait" });

      const start = Date.now();
      while (Date.now() - start < 30000) {
        await sleep(700);
        const result = await api.get<{ matched?: boolean; found_id?: number; confidence?: number; result?: string }>(
          `/devices/${DEVICE_ID}/verify-result`
        );
        if (result.matched !== undefined) {
          const resultTag = result.result ? ` -> kết quả: ${result.result.toUpperCase()}` : "";
          if (result.matched) {
            setStatus({
              text: `KHỚP! (độ tin cậy=${result.confidence})${resultTag}`,
              cls: result.result === "accepted" ? "ok" : "err",
            });
          } else {
            setStatus({ text: `KHÔNG KHỚP (ID tìm thấy: ${result.found_id ?? "không tìm thấy"})${resultTag}`, cls: "err" });
          }
          setBusy(false);
          return;
        }
      }
      setStatus({ text: "Hết thời gian chờ (30s) - kiểm tra lại ESP32/MQTT/backend.", cls: "err" });
    } catch (e) {
      setStatus({ text: "Lỗi: " + (e as Error).message, cls: "err" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card">
      <h2>Test xác thực vân tay</h2>
      <p className="muted">Bấm nút, đặt ngón tay lên cảm biến AS608 khi được yêu cầu.</p>
      <button className="btn" disabled={busy} onClick={run}>
        Bắt đầu xác thực vân tay
      </button>
      <StatusLine {...status} />
    </div>
  );
}

export default function EmployeeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [employee, setEmployee] = useState<Employee | null>(null);
  const [credentials, setCredentials] = useState<AccessCredential[]>([]);
  const [error, setError] = useState("");

  const load = () => {
    if (!id) return;
    api.get<Employee>(`/employees/${id}`).then(setEmployee).catch((e) => setError(e.message));
    api.get<AccessCredential[]>(`/employees/${id}/credentials`).then(setCredentials).catch(() => {});
  };

  useEffect(load, [id]);

  const revoke = async (credentialId: string) => {
    if (!id) return;
    await api.patch(`/employees/${id}/credentials/${credentialId}/revoke`);
    load();
  };

  if (error) return <div className="status-line err">{error}</div>;
  if (!employee || !id) return <p className="muted">Đang tải...</p>;

  const activeFace = credentials.find((c) => c.type === "face" && c.is_active);
  const activeFingerprint = credentials.find((c) => c.type === "fingerprint" && c.is_active);

  return (
    <div>
      <div className="page-header">
        <h1>
          {employee.code} — {employee.full_name}
        </h1>
        <button className="btn secondary" onClick={() => navigate("/")}>
          ← Danh sách nhân viên
        </button>
      </div>

      <div className="card">
        <h2>Credential đang active</h2>
        <table>
          <thead>
            <tr>
              <th>Loại</th>
              <th>Ngày đăng ký</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {credentials.filter((c) => c.is_active).map((c) => (
              <tr key={c.id}>
                <td>{c.type === "face" ? "Khuôn mặt" : "Vân tay"}</td>
                <td>{new Date(c.enrolled_at).toLocaleString("vi-VN")}</td>
                <td>
                  <button className="btn danger" onClick={() => revoke(c.id)}>
                    Thu hồi
                  </button>
                </td>
              </tr>
            ))}
            {credentials.filter((c) => c.is_active).length === 0 && (
              <tr>
                <td colSpan={3} className="muted">
                  Chưa có credential nào active.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <PolicyPanel employeeId={id} />

      <div className="row" style={{ alignItems: "stretch" }}>
        {!activeFace && <FaceEnrollCard employeeId={id} onEnrolled={load} />}
        {activeFace && <FaceVerifyCard employeeId={id} />}
        {!activeFingerprint && (
          <FingerprintEnrollCard employeeId={id} employeeCode={employee.code} onEnrolled={load} />
        )}
        {activeFingerprint && <FingerprintVerifyCard employeeId={id} employeeCode={employee.code} />}
      </div>
    </div>
  );
}
