import { Navigate } from "react-router-dom";
import { useAuth } from "@/context/auth-context.tsx";

export default function Index() {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <Navigate to="/app" replace /> : <Navigate to="/login" replace />;
}
