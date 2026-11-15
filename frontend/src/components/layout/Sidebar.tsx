import React, { useMemo } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import {
  Drawer,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Box,
  Typography,
  Divider,
  Avatar,
  useTheme,
} from "@mui/material";
import DashboardIcon from "@mui/icons-material/Dashboard";
import ChatIcon from "@mui/icons-material/Chat";
import AnalyticsIcon from "@mui/icons-material/Analytics";
import StorageIcon from "@mui/icons-material/Storage";
import InventoryIcon from "@mui/icons-material/Inventory";
import IntegrationInstructionsIcon from "@mui/icons-material/IntegrationInstructions";
import SettingsIcon from "@mui/icons-material/Settings";
import HelpOutlineIcon from "@mui/icons-material/HelpOutline";
import LogoutIcon from "@mui/icons-material/Logout";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import useAuth from "../../hooks/useAuth";

const drawerWidth = 260;

type NavItem = {
  key: string;
  label: string;
  icon: React.ReactNode;
  path: string;
};

const navItems: NavItem[] = [
  {
    key: "dashboard",
    label: "Dashboard",
    icon: <DashboardIcon />,
    path: "/dashboard",
  },
  { key: "chat", label: "Chat", icon: <ChatIcon />, path: "/chat" },
  {
    key: "agents",
    label: "Agent Status",
    icon: <AnalyticsIcon />,
    path: "/agents",
  },
  {
    key: "analytics",
    label: "Analytics",
    icon: <StorageIcon />,
    path: "/analytics",
  },
  {
    key: "tasks",
    label: "Task Queue",
    icon: <InventoryIcon />,
    path: "/tasks",
  },
  {
    key: "integrations",
    label: "Integrations",
    icon: <IntegrationInstructionsIcon />,
    path: "/integrations",
  },
  {
    key: "settings",
    label: "Settings",
    icon: <SettingsIcon />,
    path: "/settings",
  },
  { key: "help", label: "Help", icon: <HelpOutlineIcon />, path: "/help" },
];

type SidebarProps = {
  onNavigate?: (path: string) => void;
  mobileOpen?: boolean;
  onClose?: () => void;
};

const Sidebar: React.FC<SidebarProps> = ({
  onNavigate,
  mobileOpen = false,
  onClose,
}) => {
  const theme = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();

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

  const handleClick = (path: string) => {
    if (onNavigate) onNavigate(path);
    else navigate(path);
    if (onClose) onClose();
  };

  const handleLogout = async () => {
    if (onClose) onClose();
    try {
      await logout();
    } finally {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      navigate("/login", { replace: true });
    }
  };

  const drawerContent = (
    <Box sx={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <Toolbar>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
          <Box
            sx={{
              width: 34,
              height: 34,
              borderRadius: 2,
              bgcolor: "primary.main",
              color: "primary.contrastText",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: 2,
            }}
          >
            <AutoAwesomeIcon fontSize="small" />
          </Box>
          <Box>
            <Typography variant="subtitle1" sx={{ fontWeight: 700, lineHeight: 1.2 }} noWrap>
              IBA Platform
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: "block", fontSize: "0.7rem" }}>
              Intelligent Assistant
            </Typography>
          </Box>
        </Box>
      </Toolbar>

      <Divider />

      <List sx={{ flexGrow: 1, py: 1 }}>
        {navItems.map((item) => {
          const selected = location.pathname === item.path;
          return (
            <ListItemButton
              key={item.key}
              selected={selected}
              onClick={() => handleClick(item.path)}
              aria-label={item.label}
              sx={{
                mx: 1,
                mb: 0.5,
                borderRadius: 1.5,
                "&.Mui-selected": {
                  backgroundColor: theme.palette.action.selected,
                  fontWeight: 600,
                },
              }}
            >
              <ListItemIcon sx={{ minWidth: 40, color: selected ? "primary.main" : "inherit" }}>
                {item.icon}
              </ListItemIcon>
              <ListItemText
                primary={item.label}
                primaryTypographyProps={{
                  variant: "body2",
                  fontWeight: selected ? 600 : 400,
                }}
              />
            </ListItemButton>
          );
        })}
      </List>

      <Divider />

      <Box sx={{ p: 2 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, mb: 1 }}>
          <Avatar sx={{ width: 34, height: 34, bgcolor: "secondary.main", fontSize: "0.85rem", fontWeight: 700 }}>
            {userInitials}
          </Avatar>
          <Box sx={{ overflow: "hidden", flexGrow: 1 }}>
            <Typography variant="body2" sx={{ fontWeight: 600 }} noWrap>
              {user?.name || "User Account"}
            </Typography>
            <Typography variant="caption" color="text.secondary" noWrap display="block">
              {user?.email || ""}
            </Typography>
          </Box>
        </Box>
        <ListItemButton
          onClick={handleLogout}
          sx={{
            borderRadius: 1.5,
            color: "error.main",
            py: 0.75,
            "&:hover": { bgcolor: "action.hover" },
          }}
        >
          <ListItemIcon sx={{ color: "error.main", minWidth: 36 }}>
            <LogoutIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Log Out" primaryTypographyProps={{ variant: "body2", fontWeight: 600 }} />
        </ListItemButton>
      </Box>
    </Box>
  );

  return (
    <Box
      component="nav"
      aria-label="main navigation"
      sx={{ width: { md: drawerWidth }, flexShrink: { md: 0 } }}
    >
      {/* Mobile temporary drawer */}
      <Drawer
        variant="temporary"
        open={mobileOpen}
        onClose={onClose}
        ModalProps={{ keepMounted: true }}
        sx={{
          display: { xs: "block", md: "none" },
          "& .MuiDrawer-paper": { width: drawerWidth, boxSizing: "border-box" },
        }}
      >
        {drawerContent}
      </Drawer>

      {/* Desktop permanent drawer */}
      <Drawer
        variant="permanent"
        sx={{
          display: { xs: "none", md: "block" },
          "& .MuiDrawer-paper": { width: drawerWidth, boxSizing: "border-box" },
        }}
        open
      >
        {drawerContent}
      </Drawer>
    </Box>
  );
};

export default Sidebar;
