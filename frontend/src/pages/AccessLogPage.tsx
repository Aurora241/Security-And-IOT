import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { AccessLogRow } from "../api/types";

export default function AccessLogPage() {
  const [logs, setLogs] = useState<AccessLogRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = () => {
    setLoading(true);
    api
      .get<AccessLogRow[]>("/access-logs")
      .then(setLogs)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  return (
    <div>
      <div className="page-header">
        <h1>Nhật ký ra vào</h1>
        <button className="btn secondary" onClick={load}>
          Làm mới
        </button>
      </div>

      {error && <div className="status-line err">{error}</div>}

      {loading ? (
        <p className="muted">Đang tải...</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Thời gian</th>
              <th>Nhân viên</th>
              <th>Phương thức</th>
              <th>Độ tin cậy</th>
              <th>Kết quả</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log) => (
              <tr key={log.id}>
                <td>{new Date(log.timestamp).toLocaleString("vi-VN")}</td>
                <td>{log.employees ? `${log.employees.code} - ${log.employees.full_name}` : "(không xác định)"}</td>
                <td>{log.method === "face" ? "Khuôn mặt" : "Vân tay"}</td>
                <td>{log.confidence ?? "-"}</td>
                <td>
                  <span className={`badge ${log.result}`}>{log.result.toUpperCase()}</span>
                </td>
              </tr>
            ))}
            {logs.length === 0 && (
              <tr>
                <td colSpan={5} className="muted">
                  Chưa có nhật ký nào.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}
