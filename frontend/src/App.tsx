import { BrowserRouter, Route, Routes, Navigate, useLocation } from "react-router-dom";
import { DefaultProviders } from "./components/providers/default.tsx";
import LoginPage from "./pages/LoginPage.tsx";
import Index from "./pages/Index.tsx";
import NotFound from "./pages/NotFound.tsx";
import OnboardingPage from "./pages/OnboardingPage.tsx";
import AppLayout from "./pages/app/AppLayout.tsx";
import DashboardPage from "./pages/app/dashboard/page.tsx";
import BranchesPage from "./pages/app/branches/page.tsx";
import EmployeesPage from "./pages/app/employees/page.tsx";
import TemplatesPage from "./pages/app/templates/page.tsx";
import ChecklistsPage from "./pages/app/checklists/page.tsx";
import ReportsPage from "./pages/app/reports/page.tsx";
import IssuesPage from "./pages/app/issues/page.tsx";
import ShiftsPage from "./pages/app/shifts/page.tsx";
import StandardsPage from "./pages/app/standards/page.tsx";
import PhotosPage from "./pages/app/photos/page.tsx";
import SchedulesPage from "./pages/app/schedules/page.tsx";
import { useAuth } from "./context/auth-context.tsx";

function FullScreenLoader() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-current border-t-transparent opacity-60" />
    </div>
  );
}

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();
  // Wait for the silent refresh on page load; otherwise the user is briefly
  // redirected to /login and then bounced back once the session is restored.
  if (isLoading) return <FullScreenLoader />;
  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
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
            path="/onboarding"
            element={
              <RequireAuth>
                <OnboardingPage />
              </RequireAuth>
            }
          />
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
            <Route path="/app/schedules" element={<SchedulesPage />} />
            <Route path="/app/reports" element={<ReportsPage />} />
            <Route path="/app/issues" element={<IssuesPage />} />
            <Route path="/app/shifts" element={<ShiftsPage />} />
            <Route path="/app/standards" element={<StandardsPage />} />
            <Route path="/app/photos" element={<PhotosPage />} />
          </Route>
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </DefaultProviders>
  );
}
