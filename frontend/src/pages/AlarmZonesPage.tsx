import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { AlarmZone } from "../api/types";

const emptySchedule = { start: "20:00", end: "07:00" };

export default function AlarmZonesPage() {
  const [zones, setZones] = useState<AlarmZone[]>([]);
  const [error, setError] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState(emptySchedule);
  const [submitting, setSubmitting] = useState(false);

  const load = () => {
    api.get<AlarmZone[]>("/alarm/zones").then(setZones).catch((e) => setError(e.message));
  };

  useEffect(load, []);

  const startEdit = (zone: AlarmZone) => {
    setEditingId(zone.id);
    setForm({
      start: (zone.active_schedule?.start ?? emptySchedule.start).slice(0, 5),
      end: (zone.active_schedule?.end ?? emptySchedule.end).slice(0, 5),
    });
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingId) return;
    setSubmitting(true);
    setError("");
    try {
      await api.patch(`/alarm/zones/${editingId}`, { active_schedule: form });
      setEditingId(null);
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  const toggleArmed = async (zone: AlarmZone) => {
    setError("");
    try {
      await api.patch(`/alarm/zones/${zone.id}`, { is_armed: !zone.is_armed });
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div className="card">
      <h2>Vùng báo động (alarm_zones)</h2>
      <table>
        <thead>
          <tr>
            <th>Tên vùng</th>
            <th>Khung giờ cấm</th>
            <th>Trạng thái</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {zones.map((z) => (
            <tr key={z.id}>
              <td>{z.name}</td>
              <td>
                {z.active_schedule ? `${z.active_schedule.start.slice(0, 5)} - ${z.active_schedule.end.slice(0, 5)}` : "—"}
              </td>
              <td>
                <span className={`badge ${z.is_armed ? "active" : "inactive"}`}>
                  {z.is_armed ? "Đang armed" : "Đã tắt"}
                </span>
              </td>
              <td>
                <div className="row">
                  <button className="btn secondary" onClick={() => startEdit(z)}>
                    Sửa khung giờ
                  </button>
                  <button className="btn secondary" onClick={() => toggleArmed(z)}>
                    {z.is_armed ? "Tắt" : "Bật"}
                  </button>
                </div>
              </td>
            </tr>
          ))}
          {zones.length === 0 && (
            <tr>
              <td colSpan={4} className="muted">
                Chưa có alarm_zone nào.
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {editingId && (
        <form className="card" style={{ marginTop: 12, boxShadow: "none", border: "1px solid #eef0f3" }} onSubmit={submit}>
          <div className="row">
            <div className="field">
              <label>Giờ bắt đầu cấm</label>
              <input type="time" value={form.start} onChange={(e) => setForm({ ...form, start: e.target.value })} />
            </div>
            <div className="field">
              <label>Giờ kết thúc cấm</label>
              <input type="time" value={form.end} onChange={(e) => setForm({ ...form, end: e.target.value })} />
            </div>
          </div>
          <p className="muted" style={{ fontSize: 13 }}>
            Khung giờ được phép vắt qua nửa đêm (vd 20:00 → 07:00).
          </p>
          <div className="row">
            <button className="btn" disabled={submitting} type="submit">
              {submitting ? "Đang lưu..." : "Cập nhật"}
            </button>
            <button type="button" className="btn secondary" onClick={() => setEditingId(null)}>
              Huỷ
            </button>
          </div>
        </form>
      )}

      {error && <div className="status-line err">{error}</div>}
    </div>
  );
}
