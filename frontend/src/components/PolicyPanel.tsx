import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { AccessPolicy } from "../api/types";

const WEEKDAYS: { code: string; label: string }[] = [
  { code: "mon", label: "T2" },
  { code: "tue", label: "T3" },
  { code: "wed", label: "T4" },
  { code: "thu", label: "T5" },
  { code: "fri", label: "T6" },
  { code: "sat", label: "T7" },
  { code: "sun", label: "CN" },
];

function dayLabels(codes: string[]): string {
  return WEEKDAYS.filter((w) => codes.includes(w.code))
    .map((w) => w.label)
    .join(", ");
}

const emptyForm = { allowed_days: [] as string[], allowed_time_start: "07:00", allowed_time_end: "19:00" };

export default function PolicyPanel({ employeeId }: { employeeId: string }) {
  const [policies, setPolicies] = useState<AccessPolicy[]>([]);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [submitting, setSubmitting] = useState(false);

  const load = () => {
    api.get<AccessPolicy[]>(`/employees/${employeeId}/policies`).then(setPolicies).catch((e) => setError(e.message));
  };

  useEffect(load, [employeeId]);

  const toggleDay = (code: string) => {
    setForm((f) =>
      f.allowed_days.includes(code)
        ? { ...f, allowed_days: f.allowed_days.filter((d) => d !== code) }
        : { ...f, allowed_days: [...f.allowed_days, code] }
    );
  };

  const startEdit = (policy: AccessPolicy) => {
    setEditingId(policy.id);
    setForm({
      allowed_days: policy.allowed_days,
      allowed_time_start: policy.allowed_time_start.slice(0, 5),
      allowed_time_end: policy.allowed_time_end.slice(0, 5),
    });
    setShowForm(true);
  };

  const startNew = () => {
    setEditingId(null);
    setForm(emptyForm);
    setShowForm(true);
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (form.allowed_days.length === 0) {
      setError("Chọn ít nhất 1 ngày trong tuần");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      if (editingId) {
        await api.patch(`/employees/${employeeId}/policies/${editingId}`, form);
      } else {
        await api.post(`/employees/${employeeId}/policies`, form);
      }
      setShowForm(false);
      setEditingId(null);
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  const toggleActive = async (policy: AccessPolicy) => {
    await api.patch(`/employees/${employeeId}/policies/${policy.id}`, { is_active: !policy.is_active });
    load();
  };

  return (
    <div className="card">
      <h2>Chính sách ra vào (access_policies)</h2>
      <table>
        <thead>
          <tr>
            <th>Ngày áp dụng</th>
            <th>Khung giờ</th>
            <th>Trạng thái</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {policies.map((p) => (
            <tr key={p.id}>
              <td>{dayLabels(p.allowed_days)}</td>
              <td>
                {p.allowed_time_start.slice(0, 5)} - {p.allowed_time_end.slice(0, 5)}
              </td>
              <td>
                <span className={`badge ${p.is_active ? "active" : "inactive"}`}>
                  {p.is_active ? "Đang bật" : "Đã tắt"}
                </span>
              </td>
              <td>
                <div className="row">
                  <button className="btn secondary" onClick={() => startEdit(p)}>
                    Sửa
                  </button>
                  <button className="btn secondary" onClick={() => toggleActive(p)}>
                    {p.is_active ? "Tắt" : "Bật"}
                  </button>
                </div>
              </td>
            </tr>
          ))}
          {policies.length === 0 && (
            <tr>
              <td colSpan={4} className="muted">
                Chưa có chính sách nào — nhân viên sẽ luôn bị "rejected" dù sinh trắc học khớp.
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {!showForm && (
        <button className="btn" style={{ marginTop: 12 }} onClick={startNew}>
          + Thêm chính sách
        </button>
      )}

      {showForm && (
        <form className="card" style={{ marginTop: 12, boxShadow: "none", border: "1px solid #eef0f3" }} onSubmit={submit}>
          <div className="field">
            <label>Ngày trong tuần</label>
            <div className="row">
              {WEEKDAYS.map((w) => (
                <label key={w.code} style={{ display: "flex", gap: 4, alignItems: "center", fontSize: 13 }}>
                  <input type="checkbox" checked={form.allowed_days.includes(w.code)} onChange={() => toggleDay(w.code)} />
                  {w.label}
                </label>
              ))}
            </div>
          </div>
          <div className="row">
            <div className="field">
              <label>Giờ bắt đầu</label>
              <input
                type="time"
                value={form.allowed_time_start}
                onChange={(e) => setForm({ ...form, allowed_time_start: e.target.value })}
              />
            </div>
            <div className="field">
              <label>Giờ kết thúc</label>
              <input
                type="time"
                value={form.allowed_time_end}
                onChange={(e) => setForm({ ...form, allowed_time_end: e.target.value })}
              />
            </div>
          </div>
          <div className="row">
            <button className="btn" disabled={submitting} type="submit">
              {submitting ? "Đang lưu..." : editingId ? "Cập nhật" : "Lưu"}
            </button>
            <button type="button" className="btn secondary" onClick={() => setShowForm(false)}>
              Huỷ
            </button>
          </div>
        </form>
      )}

      {error && <StatusErr text={error} />}
    </div>
  );
}

function StatusErr({ text }: { text: string }) {
  return <div className="status-line err">{text}</div>;
}
