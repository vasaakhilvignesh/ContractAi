import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import { Shell } from "./components/layout/Shell";

import Dashboard from "./pages/Dashboard";
import Contracts from "./pages/Contracts";
import ContractOverview from "./pages/ContractOverview";
import UploadContract from "./pages/UploadContract";
import Obligations from "./pages/Obligations";
import RiskMonitor from "./pages/RiskMonitor";
import Compare from "./pages/Compare";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>

        {/* Main application layout */}
        <Route element={<Shell />}>

          {/* Dashboard */}
          <Route path="/" element={<Dashboard />} />
          <Route path="/dashboard" element={<Dashboard />} />

          {/* Contracts */}
          <Route path="/contracts" element={<Contracts />} />
          <Route
            path="/contracts/upload"
            element={<UploadContract />}
          />
          <Route
            path="/contracts/:id"
            element={<ContractOverview />}
          />

          {/* Other modules */}
          <Route path="/obligations" element={<Obligations />} />
          <Route path="/risks" element={<RiskMonitor />} />
          <Route path="/compare" element={<Compare />} />

        </Route>

        {/* Unknown URL → Dashboard */}
        <Route path="*" element={<Navigate to="/" replace />} />

      </Routes>
    </BrowserRouter>
  );
}