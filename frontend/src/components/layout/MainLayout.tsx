import React, { useState, Suspense, useMemo } from "react";
import { Outlet, useNavigate } from "react-router-dom";
import {
  Box,
  AppBar,
  Toolbar,
  Typography,
  IconButton,
  CssBaseline,
  Avatar,
  Menu,
  MenuItem,
  Divider,
  CircularProgress,
  useTheme,
  Theme,
} from "@mui/material";
import MenuIcon from "@mui/icons-material/Menu";
import Sidebar from "./Sidebar";
import useAuth from "../../hooks/useAuth";

const drawerWidth = 260;

const MainLayout: React.FC = () => {
  const theme = useTheme() as Theme;
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);

  const handleDrawerToggle = () => setMobileOpen((v) => !v);

  const handleNavigate = (path: string) => {
    if (!path) return;
    navigate(path);
    setMobileOpen(false);
  };

  const handleProfileOpen = (e: React.MouseEvent<HTMLElement>) =>
    setAnchorEl(e.currentTarget);
  const handleProfileClose = () => setAnchorEl(null);

  const userInitials = useMemo(() => {
    if (user?.name) {
      const parts = user.name.trim().split(/\s+/);
      if (parts.length >= 2) {
        return (parts[0][0] + parts[1][0]).toUpperCase();
      }
      return user.name.slice(0, 2).toUpperCase();
    }
    if (user?.email) {
      return user.email.slice(0, 2).toUpperCase();
    }
    return "U";
  }, [user]);

  const handleLogout = async () => {
    handleProfileClose();
    try {
      await logout();
    } finally {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      navigate("/login", { replace: true });
    }
  };

  return (
    <Box sx={{ display: "flex" }}>
      <CssBaseline />

      <AppBar
        position="fixed"
        sx={{ zIndex: (themeVar) => themeVar.zIndex.drawer + 1 }}
      >
        <Toolbar>
          <IconButton
            color="inherit"
            edge="start"
            onClick={handleDrawerToggle}
            sx={{ mr: 2, display: { md: "none" } }}
            aria-label="open drawer"
            size="large"
          >
            <MenuIcon />
          </IconButton>

          <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1, fontWeight: 600 }}>
            Intelligent Business Assistant
          </Typography>

          <IconButton
            color="inherit"
            onClick={handleProfileOpen}
            size="small"
            aria-label="profile"
          >
            <Avatar sx={{ width: 34, height: 34, bgcolor: "secondary.main", fontSize: "0.85rem", fontWeight: 700 }}>
              {userInitials}
            </Avatar>
          </IconButton>

          <Menu
            anchorEl={anchorEl}
            open={Boolean(anchorEl)}
            onClose={handleProfileClose}
            anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
            transformOrigin={{ vertical: "top", horizontal: "right" }}
          >
            <Box sx={{ px: 2, py: 1 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 600 }} noWrap>
                {user?.name || "User Account"}
              </Typography>
              <Typography variant="caption" color="text.secondary" noWrap display="block">
                {user?.email || ""}
              </Typography>
            </Box>
            <Divider />
            <MenuItem onClick={() => { handleProfileClose(); navigate("/profile"); }}>
              Profile
            </MenuItem>
            <MenuItem onClick={() => { handleProfileClose(); navigate("/settings"); }}>
              Settings
            </MenuItem>
            <Divider />
            <MenuItem onClick={handleLogout} sx={{ color: "error.main" }}>
              Logout
            </MenuItem>
          </Menu>
        </Toolbar>
      </AppBar>

      {/* Sidebar: passes navigation and mobile state */}
      <Sidebar
        mobileOpen={mobileOpen}
        onClose={() => setMobileOpen(false)}
        onNavigate={handleNavigate}
      />

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          width: { xs: "100%", md: `calc(100% - ${drawerWidth}px)` },
          ml: { md: `${drawerWidth}px` },
        }}
      >
        <Toolbar /> {/* spacing for fixed AppBar */}

        <Suspense
          fallback={
            <Box sx={{ display: "flex", justifyContent: "center", p: 4 }}>
              <CircularProgress />
            </Box>
          }
        >
          {/* Route children will render here */}
          <Outlet />
        </Suspense>
      </Box>
    </Box>
  );
};
export default MainLayout;