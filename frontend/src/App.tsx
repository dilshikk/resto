import { BrowserRouter, Route, Routes, Navigate } from "react-router-dom";
import { DefaultProviders } from "./components/providers/default.tsx";
import LoginPage from "./pages/LoginPage.tsx";
import Index from "./pages/Index.tsx";
import NotFound from "./pages/NotFound.tsx";
import AppLayout from "./pages/app/AppLayout.tsx";
import DashboardPage from "./pages/app/dashboard/page.tsx";
import BranchesPage from "./pages/app/branches/page.tsx";
import EmployeesPage from "./pages/app/employees/page.tsx";
import TemplatesPage from "./pages/app/templates/page.tsx";
import ChecklistsPage from "./pages/app/checklists/page.tsx";
import ReportsPage from "./pages/app/reports/page.tsx";
import ComingSoon from "./pages/app/ComingSoon.tsx";
import { useAuth } from "./context/auth-context.tsx";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <DefaultProviders>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Index />} />
          <Route path="/login" element={<LoginPage />} />
          <Route
            element={
              <RequireAuth>
                <AppLayout />
              </RequireAuth>
            }
          >
            <Route path="/app" element={<DashboardPage />} />
            <Route path="/app/branches" element={<BranchesPage />} />
            <Route path="/app/employees" element={<EmployeesPage />} />
            <Route path="/app/checklists" element={<ChecklistsPage />} />
            <Route path="/app/templates" element={<TemplatesPage />} />
            <Route path="/app/reports" element={<ReportsPage />} />
            <Route path="/app/issues" element={<ComingSoon title="Проблемы" />} />
          </Route>
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </DefaultProviders>
  );
}
