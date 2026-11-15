import React, { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Avatar,
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Chip,
  CircularProgress,
  Divider,
  Grid,
  IconButton,
  InputAdornment,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import PersonIcon from "@mui/icons-material/Person";
import LockResetIcon from "@mui/icons-material/LockReset";
import SecurityIcon from "@mui/icons-material/Security";
import ShieldIcon from "@mui/icons-material/Shield";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import VisibilityIcon from "@mui/icons-material/Visibility";
import VisibilityOffIcon from "@mui/icons-material/VisibilityOff";

import useAuth from "../../hooks/useAuth";
import api from "../../services/api";

const Profile = () => {
  const { user } = useAuth();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // Edit profile form state
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [savingProfile, setSavingProfile] = useState(false);

  // Password update state
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [savingPassword, setSavingPassword] = useState(false);

  const fetchProfile = async () => {
    setLoading(true);
    setError("");
    try {
      const response = await api.get("/api/v1/auth/me");
      const data = response.data;
      setProfile(data);
      setName(data.name || "");
      setEmail(data.email || "");
    } catch (err) {
      setError(
        err?.response?.data?.detail ||
          err?.message ||
          "Could not load account details."
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfile();
  }, []);

  const userInitials = useMemo(() => {
    const displayName = name || profile?.name || user?.name;
    if (displayName) {
      const parts = displayName.trim().split(/\s+/);
      if (parts.length >= 2) {
        return (parts[0][0] + parts[1][0]).toUpperCase();
      }
      return displayName.slice(0, 2).toUpperCase();
    }
    const displayEmail = email || profile?.email || user?.email;
    if (displayEmail) {
      return displayEmail.slice(0, 2).toUpperCase();
    }
    return "U";
  }, [name, profile, user, email]);

  const handleUpdateProfile = async (e) => {
    e.preventDefault();
    if (!profile?.id) return;

    setSavingProfile(true);
    setError("");
    setSuccess("");

    try {
      const response = await api.patch(`/api/v1/users/${profile.id}`, {
        name: name.trim(),
        email: email.trim(),
      });
      setProfile(response.data);
      setSuccess("Profile information updated successfully.");
    } catch (err) {
      setError(
        err?.response?.data?.detail ||
          err?.message ||
          "Failed to update profile."
      );
    } finally {
      setSavingProfile(false);
    }
  };

  const handleUpdatePassword = async (e) => {
    e.preventDefault();
    if (!profile?.id) return;

    if (!newPassword || newPassword.length < 8) {
      setError("New password must be at least 8 characters long.");
      return;
    }

    if (newPassword !== confirmPassword) {
      setError("New password and confirmation do not match.");
      return;
    }

    setSavingPassword(true);
    setError("");
    setSuccess("");

    try {
      await api.patch(`/api/v1/users/${profile.id}`, {
        password: newPassword,
      });
      setSuccess("Password updated successfully.");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setError(
        err?.response?.data?.detail ||
          err?.message ||
          "Failed to update password."
      );
    } finally {
      setSavingPassword(false);
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", py: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: { xs: 2, md: 3 } }}>
      {/* Page Header */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>
          User Profile
        </Typography>
        <Typography color="text.secondary">
          Manage your account information, security credentials, and workspace settings.
        </Typography>
      </Box>

      {error ? (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError("")}>
          {error}
        </Alert>
      ) : null}
      {success ? (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess("")}>
          {success}
        </Alert>
      ) : null}

      <Grid container spacing={3}>
        {/* User Identity Card */}
        <Grid item xs={12} md={4}>
          <Card sx={{ height: "100%", textAlign: "center", p: 3 }}>
            <Avatar
              sx={{
                width: 80,
                height: 80,
                mx: "auto",
                mb: 2,
                bgcolor: "primary.main",
                fontSize: "2rem",
                fontWeight: 700,
                boxShadow: 3,
              }}
            >
              {userInitials}
            </Avatar>
            <Typography variant="h6" sx={{ fontWeight: 700 }}>
              {profile?.name || "Unnamed User"}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {profile?.email}
            </Typography>

            <Stack direction="row" spacing={1} justifyContent="center" sx={{ mb: 3 }}>
              <Chip
                label={profile?.is_admin ? "Administrator" : "Standard User"}
                color={profile?.is_admin ? "primary" : "default"}
                size="small"
                sx={{ fontWeight: 600 }}
              />
              <Chip
                icon={<CheckCircleIcon style={{ fontSize: 14 }} />}
                label={profile?.is_active !== false ? "Active" : "Inactive"}
                color="success"
                size="small"
                variant="outlined"
              />
            </Stack>

            <Divider sx={{ mb: 2 }} />

            <Box sx={{ textAlign: "left" }}>
              <Typography variant="caption" color="text.secondary" display="block">
                User ID / Tenant ID:
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 600, mb: 1.5 }}>
                #{profile?.id ?? "N/A"}
              </Typography>

              <Typography variant="caption" color="text.secondary" display="block">
                Member Since:
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                {profile?.created_at
                  ? new Date(profile.created_at).toLocaleDateString(undefined, {
                      year: "numeric",
                      month: "long",
                      day: "numeric",
                    })
                  : "N/A"}
              </Typography>
            </Box>
          </Card>
        </Grid>

        {/* Profile Edit & Security Forms */}
        <Grid item xs={12} md={8}>
          <Stack spacing={3}>
            {/* General Info */}
            <Card>
              <CardHeader
                avatar={<PersonIcon color="primary" />}
                title={<Typography variant="h6" sx={{ fontWeight: 700 }}>Personal Information</Typography>}
                subheader="Update your name and primary email address"
              />
              <Divider />
              <CardContent>
                <Box component="form" onSubmit={handleUpdateProfile}>
                  <Stack spacing={2.5}>
                    <TextField
                      label="Full Name"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="Jane Doe"
                      fullWidth
                    />
                    <TextField
                      required
                      type="email"
                      label="Email Address"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="jane@company.com"
                      fullWidth
                    />
                    <Box sx={{ display: "flex", justifyContent: "flex-end" }}>
                      <Button
                        type="submit"
                        variant="contained"
                        disabled={savingProfile}
                        startIcon={savingProfile ? <CircularProgress size={16} /> : null}
                      >
                        Save Profile
                      </Button>
                    </Box>
                  </Stack>
                </Box>
              </CardContent>
            </Card>

            {/* Change Password */}
            <Card>
              <CardHeader
                avatar={<LockResetIcon color="primary" />}
                title={<Typography variant="h6" sx={{ fontWeight: 700 }}>Change Password</Typography>}
                subheader="Ensure your account is protected with a strong password (minimum 8 characters)"
              />
              <Divider />
              <CardContent>
                <Box component="form" onSubmit={handleUpdatePassword}>
                  <Stack spacing={2.5}>
                    <TextField
                      label="New Password"
                      type={showPassword ? "text" : "password"}
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      placeholder="Enter new password (at least 8 characters)"
                      InputProps={{
                        endAdornment: (
                          <InputAdornment position="end">
                            <IconButton onClick={() => setShowPassword((s) => !s)} edge="end">
                              {showPassword ? <VisibilityOffIcon /> : <VisibilityIcon />}
                            </IconButton>
                          </InputAdornment>
                        ),
                      }}
                      fullWidth
                    />
                    <TextField
                      label="Confirm New Password"
                      type={showPassword ? "text" : "password"}
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="Re-type new password"
                      fullWidth
                    />
                    <Box sx={{ display: "flex", justifyContent: "flex-end" }}>
                      <Button
                        type="submit"
                        variant="outlined"
                        disabled={savingPassword || !newPassword}
                        startIcon={savingPassword ? <CircularProgress size={16} /> : null}
                      >
                        Update Password
                      </Button>
                    </Box>
                  </Stack>
                </Box>
              </CardContent>
            </Card>

            {/* Security & Tenancy Info */}
            <Card sx={{ bgcolor: "background.default", border: "1px dashed", borderColor: "divider" }}>
              <CardContent>
                <Stack direction="row" spacing={1.5} alignItems="flex-start">
                  <ShieldIcon color="primary" sx={{ mt: 0.5 }} />
                  <Box>
                    <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                      Tenant Data Isolation & Encryption
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Your business workflows, integration keys, tasks, and agent chat sessions are securely bound to Tenant #{profile?.id}. Third-party credentials are encrypted at rest with industry-standard Fernet cryptography.
                    </Typography>
                  </Box>
                </Stack>
              </CardContent>
            </Card>
          </Stack>
        </Grid>
      </Grid>
    </Box>
  );
};

export default Profile;
