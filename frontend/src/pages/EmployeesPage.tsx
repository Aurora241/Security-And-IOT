import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Employee } from "../api/types";

export default function EmployeesPage() {
  const navigate = useNavigate();
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ code: "", full_name: "", department: "", position: "" });
  const [submitting, setSubmitting] = useState(false);

  const loadEmployees = () => {
    setLoading(true);
    api
      .get<Employee[]>("/employees")
      .then(setEmployees)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(loadEmployees, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await api.post("/employees", {
        code: form.code,
        full_name: form.full_name,
        department: form.department || null,
        position: form.position || null,
      });
      setForm({ code: "", full_name: "", department: "", position: "" });
      setShowForm(false);
      loadEmployees();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Loi khong xac dinh");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <h1>Nhân viên</h1>
        <button className="btn" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Đóng" : "+ Thêm nhân viên"}
        </button>
      </div>

      {showForm && (
        <form className="card" onSubmit={handleSubmit}>
          <h2>Thêm nhân viên mới</h2>
          <div className="row">
            <div className="field">
              <label>Mã nhân viên</label>
              <input required value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />
            </div>
            <div className="field">
              <label>Họ tên</label>
              <input
                required
                value={form.full_name}
                onChange={(e) => setForm({ ...form, full_name: e.target.value })}
              />
            </div>
            <div className="field">
              <label>Phòng ban</label>
              <input
                value={form.department}
                onChange={(e) => setForm({ ...form, department: e.target.value })}
              />
            </div>
            <div className="field">
              <label>Vị trí</label>
              <input value={form.position} onChange={(e) => setForm({ ...form, position: e.target.value })} />
            </div>
          </div>
          <button className="btn" disabled={submitting} type="submit">
            {submitting ? "Đang lưu..." : "Lưu"}
          </button>
        </form>
      )}

      {error && <div className="status-line err">{error}</div>}

      {loading ? (
        <p className="muted">Đang tải...</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Mã NV</th>
              <th>Họ tên</th>
              <th>Phòng ban</th>
              <th>Vị trí</th>
              <th>Trạng thái</th>
            </tr>
          </thead>
          <tbody>
            {employees.map((emp) => (
              <tr key={emp.id} className="clickable" onClick={() => navigate(`/employees/${emp.id}`)}>
                <td>{emp.code}</td>
                <td>{emp.full_name}</td>
                <td>{emp.department ?? "-"}</td>
                <td>{emp.position ?? "-"}</td>
                <td>
                  <span className={`badge ${emp.status === "active" ? "active" : "inactive"}`}>{emp.status}</span>
                </td>
              </tr>
            ))}
            {employees.length === 0 && (
              <tr>
                <td colSpan={5} className="muted">
                  Chưa có nhân viên nào.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}
