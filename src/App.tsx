import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import { AuthProvider } from "./context/AuthContext";
import { ProtectedRoute } from "./components/layout/ProtectedRoute";
import { Shell } from "./components/layout/Shell";

import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import Contracts from "./pages/Contracts";
import ContractOverview from "./pages/ContractOverview";
import UploadContract from "./pages/UploadContract";
import Obligations from "./pages/Obligations";
import RiskMonitor from "./pages/RiskMonitor";
import Compare from "./pages/Compare";
import Analyst from "./pages/Analyst";
import Audit from "./pages/Audit";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public Auth Routes */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          {/* Protected Application Workspace */}
          <Route
            element={
              <ProtectedRoute>
                <Shell />
              </ProtectedRoute>
            }
          >
            {/* Dashboard */}
            <Route path="/" element={<Dashboard />} />
            <Route path="/dashboard" element={<Dashboard />} />

            {/* Contracts */}
            <Route path="/contracts" element={<Contracts />} />
            <Route path="/contracts/upload" element={<UploadContract />} />
            <Route path="/contracts/:id" element={<ContractOverview />} />

            {/* Modules */}
            <Route path="/obligations" element={<Obligations />} />
            <Route path="/risks" element={<RiskMonitor />} />
            <Route path="/compare" element={<Compare />} />
            <Route path="/analyst" element={<Analyst />} />
            <Route path="/audit" element={<Audit />} />
          </Route>

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
