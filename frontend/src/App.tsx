import { Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import AppLayout from '@/components/layout/AppLayout';
import LoginPage from '@/components/auth/LoginPage';
import RegisterPage from '@/components/auth/RegisterPage';
import Dashboard from '@/components/Dashboard';
import PropertyList from '@/components/PropertyList';
import PropertyMap from '@/components/map/PropertyMap';
import PlanReport from '@/components/reports/PlanReport';
import FieldApp from '@/components/field/FieldApp';
import SharedPlanView from '@/components/reports/SharedPlanView';

function ProtectedRoute() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <Outlet />;
}

export default function App() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/shared/:token" element={<SharedPlanView />} />

      {/* Protected routes */}
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/properties" element={<PropertyList />} />
          <Route path="/properties/:id" element={<PropertyMap />} />
          <Route path="/plans/:id" element={<PlanReport />} />
        </Route>
        <Route path="/field" element={<FieldApp />} />
      </Route>

      {/* Catch-all */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
