import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "../context/AuthContext";
import ProtectedRoute from "../components/auth/ProtectedRoute";

import MainLayout from "../components/layout/MainLayout";
import Login from "../pages/Login";
import Signup from "../pages/signup";
import Dashboard from "../pages/Dashboard";
import Chat from "../pages/Chat";
import Analytics from "../pages/Analytics";
import AgentStatus from "../pages/AgentStatus";
import Settings from "../pages/Settings";
import Tasks from "../pages/Tasks";
import Integrations from "../pages/Integrations";
import Profile from "../pages/Profile";
import Help from "../pages/Help";

const AppRoutes: React.FC = () => {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public */}
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />

          {/* Protected app routes with MainLayout as shell */}
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<MainLayout />}>
              <Route index element={<Navigate to="dashboard" replace />} />
              <Route path="dashboard" element={<Dashboard />} />
              <Route path="chat" element={<Chat />} />
              <Route path="analytics" element={<Analytics />} />
              <Route path="agents" element={<AgentStatus />} />
              <Route path="tasks" element={<Tasks />} />
              <Route path="integrations" element={<Integrations />} />
              <Route path="profile" element={<Profile />} />
              <Route path="settings" element={<Settings />} />
              <Route path="help" element={<Help />} />
              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Route>
          </Route>

          {/* Fallback for any unmatched route */}
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
};

export default AppRoutes;
