import React, { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  AppBar,
  Toolbar,
  IconButton,
  Typography,
  InputBase,
  Badge,
  Avatar,
  Menu,
  MenuItem,
  Divider,
  Box,
  useTheme,
  alpha,
  styled,
} from "@mui/material";
import MenuIcon from "@mui/icons-material/Menu";
import SearchIcon from "@mui/icons-material/Search";
import NotificationsIcon from "@mui/icons-material/Notifications";
import MoreVertIcon from "@mui/icons-material/MoreVert";
import useAuth from "../../hooks/useAuth";

interface TopbarProps {
  title?: string;
  onMenuClick?: () => void;
  onProfile?: () => void;
  onLogout?: () => void;
  notificationsCount?: number;
}

const Search = styled("div")(({ theme }) => ({
  position: "relative",
  borderRadius: theme.shape.borderRadius,
  backgroundColor: alpha(theme.palette.common.white, 0.06),
  "&:hover": { backgroundColor: alpha(theme.palette.common.white, 0.09) },
  marginRight: theme.spacing(2),
  marginLeft: 0,
  width: "100%",
  [theme.breakpoints.up("sm")]: { width: "auto" },
}));

const SearchIconWrapper = styled("div")(({ theme }) => ({
  padding: theme.spacing(0, 1),
  height: "100%",
  position: "absolute",
  pointerEvents: "none",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
}));

const StyledInputBase = styled(InputBase)(({ theme }) => ({
  color: "inherit",
  "& .MuiInputBase-input": {
    padding: theme.spacing(1, 1, 1, 0),
    paddingLeft: `calc(1em + ${theme.spacing(3)})`,
    transition: theme.transitions.create("width"),
    width: "12ch",
    [theme.breakpoints.up("md")]: { width: "20ch" },
  },
}));

const Topbar: React.FC<TopbarProps> = ({
  title = "Intelligent Business Assistant",
  onMenuClick,
  onProfile,
  onLogout,
  notificationsCount = 0,
}) => {
  const theme = useTheme();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  const [mobileAnchor, setMobileAnchor] = useState<HTMLElement | null>(null);

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

  const handleProfileOpen = (e: React.MouseEvent<HTMLElement>) => setAnchorEl(e.currentTarget);
  const handleProfileClose = () => setAnchorEl(null);

  const handleMobileOpen = (e: React.MouseEvent<HTMLElement>) => setMobileAnchor(e.currentTarget);
  const handleMobileClose = () => setMobileAnchor(null);

  const handleLogout = async () => {
    handleProfileClose();
    handleMobileClose();
    if (onLogout) {
      onLogout();
    } else {
      try {
        await logout();
      } finally {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        navigate("/login", { replace: true });
      }
    }
  };

  return (
    <AppBar position="fixed" sx={{ zIndex: (t) => t.zIndex.drawer + 1 }}>
      <Toolbar>
        <IconButton
          color="inherit"
          edge="start"
          onClick={onMenuClick}
          sx={{ mr: 2, display: { md: "none" } }}
          aria-label="open drawer"
          size="large"
        >
          <MenuIcon />
        </IconButton>

        <Typography variant="h6" noWrap component="div" sx={{ flexShrink: 0, fontWeight: 600 }}>
          {title}
        </Typography>

        <Box sx={{ flexGrow: 1 }} />

        <Search sx={{ display: { xs: "none", sm: "flex" }, mr: 1 }}>
          <SearchIconWrapper>
            <SearchIcon />
          </SearchIconWrapper>
          <StyledInputBase placeholder="Search…" inputProps={{ "aria-label": "search" }} />
        </Search>

        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <IconButton color="inherit" aria-label="notifications" size="large">
            <Badge badgeContent={notificationsCount} color="error">
              <NotificationsIcon />
            </Badge>
          </IconButton>

          <IconButton
            color="inherit"
            onClick={handleProfileOpen}
            aria-label="account"
            size="large"
            sx={{ ml: 0.5 }}
          >
            <Avatar sx={{ width: 34, height: 34, bgcolor: "secondary.main", fontSize: "0.85rem", fontWeight: 700 }}>
              {userInitials}
            </Avatar>
          </IconButton>

          <IconButton
            color="inherit"
            sx={{ display: { md: "none" } }}
            onClick={handleMobileOpen}
            aria-label="more"
            size="large"
          >
            <MoreVertIcon />
          </IconButton>
        </Box>

        {/* Profile menu */}
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
          <MenuItem
            onClick={() => {
              handleProfileClose();
              if (onProfile) onProfile();
              else navigate("/profile");
            }}
          >
            Profile
          </MenuItem>
          <MenuItem
            onClick={() => {
              handleProfileClose();
              navigate("/settings");
            }}
          >
            Settings
          </MenuItem>
          <Divider />
          <MenuItem onClick={handleLogout} sx={{ color: "error.main" }}>
            Logout
          </MenuItem>
        </Menu>

        {/* Mobile menu */}
        <Menu
          anchorEl={mobileAnchor}
          open={Boolean(mobileAnchor)}
          onClose={handleMobileClose}
          anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
          transformOrigin={{ vertical: "top", horizontal: "right" }}
        >
          <MenuItem>
            <IconButton color="inherit" aria-label="notifications" size="large">
              <Badge badgeContent={notificationsCount} color="error">
                <NotificationsIcon />
              </Badge>
            </IconButton>
            <Typography sx={{ ml: 1 }}>Notifications</Typography>
          </MenuItem>
          <MenuItem
            onClick={() => {
              handleMobileClose();
              if (onProfile) onProfile();
              else navigate("/profile");
            }}
          >
            <Typography>Account Profile</Typography>
          </MenuItem>
          <MenuItem onClick={handleLogout} sx={{ color: "error.main" }}>
            <Typography color="error">Logout</Typography>
          </MenuItem>
        </Menu>
      </Toolbar>
    </AppBar>
  );
};

export default Topbar;
