import { NavLink, Route, Routes } from "react-router-dom";
import EmployeesPage from "./pages/EmployeesPage";
import EmployeeDetailPage from "./pages/EmployeeDetailPage";
import AccessLogPage from "./pages/AccessLogPage";
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
        </nav>
      </aside>
      <main className="content">
        <Routes>
          <Route path="/" element={<EmployeesPage />} />
          <Route path="/employees/:id" element={<EmployeeDetailPage />} />
          <Route path="/access-log" element={<AccessLogPage />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
