import { BrowserRouter, Route, Routes } from "react-router-dom";
import { DefaultProviders } from "./components/providers/default.tsx";
import AuthCallback from "./pages/auth/Callback.tsx";
import Index from "./pages/Index.tsx";
import NotFound from "./pages/NotFound.tsx";
import AppLayout from "./pages/app/AppLayout.tsx";
import DashboardPage from "./pages/app/dashboard/page.tsx";
import BranchesPage from "./pages/app/branches/page.tsx";
import EmployeesPage from "./pages/app/employees/page.tsx";
import ComingSoon from "./pages/app/ComingSoon.tsx";

export default function App() {
  return (
    <DefaultProviders>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Index />} />
          <Route path="/auth/callback" element={<AuthCallback />} />
          {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
          <Route element={<AppLayout />}>
            <Route path="/app" element={<DashboardPage />} />
            <Route path="/app/branches" element={<BranchesPage />} />
            <Route path="/app/employees" element={<EmployeesPage />} />
            <Route
              path="/app/checklists"
              element={<ComingSoon title="Чек-листы" />}
            />
            <Route
              path="/app/issues"
              element={<ComingSoon title="Проблемы" />}
            />
            <Route
              path="/app/templates"
              element={<ComingSoon title="Шаблоны" />}
            />
            <Route
              path="/app/reports"
              element={<ComingSoon title="Аналитика" />}
            />
          </Route>
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </DefaultProviders>
  );
}
