import { NavLink, Route, Routes } from "react-router-dom";
import EmployeesPage from "./pages/EmployeesPage";
import EmployeeDetailPage from "./pages/EmployeeDetailPage";
import AccessLogPage from "./pages/AccessLogPage";
import AlarmZonesPage from "./pages/AlarmZonesPage";
import "./App.css";

function App() {
  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">Access Control</div>
        <nav>
          <NavLink to="/" end>
            Nhân viên
          </NavLink>
          <NavLink to="/access-log">Nhật ký ra vào</NavLink>
          <NavLink to="/alarm-zones">Vùng báo động</NavLink>
        </nav>
      </aside>
      <main className="content">
        <Routes>
          <Route path="/" element={<EmployeesPage />} />
          <Route path="/employees/:id" element={<EmployeeDetailPage />} />
          <Route path="/access-log" element={<AccessLogPage />} />
          <Route path="/alarm-zones" element={<AlarmZonesPage />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
