import React, { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Grid,
  List,
  ListItem,
  ListItemText,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { yupResolver } from "@hookform/resolvers/yup";
import { Controller, useForm } from "react-hook-form";
import * as yup from "yup";

import useAuth from "../../hooks/useAuth";
import api from "../../services/api";

const integrationSchema = yup.object({
  name: yup.string().required("Integration name is required"),
  type: yup.string().required("Integration type is required"),
  client_secrets_path: yup.string().required("Credential path is required"),
  enabled: yup.boolean().default(true),
});

const profileSchema = yup.object({
  name: yup.string().nullable(),
  email: yup.string().email("Enter a valid email").required("Email is required"),
  password: yup.string().min(8, "Password must be at least 8 characters").optional(),
});

const integrationTypes = [
  { value: "gmail", label: "Gmail" },
  { value: "slack", label: "Slack" },
  { value: "salesforce", label: "Salesforce" },
  { value: "hubspot", label: "HubSpot" },
];

const Settings = () => {
  const { user } = useAuth();
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [integrations, setIntegrations] = useState([]);

  const profileDefaults = useMemo(
    () => ({
      name: user?.name || "",
      email: user?.email || "",
      password: "",
    }),
    [user],
  );

  const integrationForm = useForm({
    resolver: yupResolver(integrationSchema),
    defaultValues: {
      name: "",
      type: "gmail",
      client_secrets_path: "",
      enabled: true,
    },
  });

  const profileForm = useForm({
    resolver: yupResolver(profileSchema),
    defaultValues: profileDefaults,
  });

  useEffect(() => {
    profileForm.reset(profileDefaults);
  }, [profileDefaults, profileForm]);

  useEffect(() => {
    let active = true;

    const loadIntegrations = async () => {
      try {
        const response = await api.get("/api/v1/integrations/");
        if (!active) {
          return;
        }
        const records = response.data ?? {};
        setIntegrations(Object.values(records));
      } catch (requestError) {
        if (active) {
          setError(
            requestError?.response?.data?.detail ||
              requestError?.message ||
              "Integration settings could not be loaded.",
          );
        }
      }
    };

    loadIntegrations();
    return () => {
      active = false;
    };
  }, []);

  const submitIntegration = integrationForm.handleSubmit(async (values) => {
    setError("");
    setSuccess("");
    try {
      const payload = {
        ...values,
        enabled: values.enabled,
      };
      await api.post("/api/v1/integrations/", payload);
      setSuccess("Integration settings saved.");
      integrationForm.reset({
        name: "",
        type: values.type,
        client_secrets_path: "",
        enabled: true,
      });
      const refresh = await api.get("/api/v1/integrations/");
      setIntegrations(Object.values(refresh.data ?? {}));
    } catch (requestError) {
      setError(
        requestError?.response?.data?.detail ||
          requestError?.message ||
          "Integration settings could not be saved.",
      );
    }
  });

  const submitProfile = profileForm.handleSubmit(async (values) => {
    setError("");
    setSuccess("");
    try {
      if (!user?.id) {
        throw new Error("User profile is unavailable.");
      }
      const payload = { ...values };
      if (!payload.password) {
        delete payload.password;
      }
      await api.patch(`/api/v1/users/${user.id}`, payload);
      setSuccess("Profile updated successfully.");
      profileForm.reset({ ...values, password: "" });
    } catch (requestError) {
      setError(
        requestError?.response?.data?.detail ||
          requestError?.message ||
          "Profile could not be updated.",
      );
    }
  });

  return (
    <Box sx={{ p: { xs: 2, md: 3 } }}>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>
        Settings
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        Manage your profile and configure external systems the agents depend on.
      </Typography>

      {error ? <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert> : null}
      {success ? <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert> : null}

      <Grid container spacing={2.5}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Profile Settings
              </Typography>
              <Stack
                component="form"
                spacing={2}
                onSubmit={submitProfile}
              >
                <Controller
                  name="name"
                  control={profileForm.control}
                  render={({ field, fieldState }) => (
                    <TextField
                      {...field}
                      label="Full Name"
                      error={!!fieldState.error}
                      helperText={fieldState.error?.message}
                      fullWidth
                    />
                  )}
                />
                <Controller
                  name="email"
                  control={profileForm.control}
                  render={({ field, fieldState }) => (
                    <TextField
                      {...field}
                      label="Email"
                      error={!!fieldState.error}
                      helperText={fieldState.error?.message}
                      fullWidth
                    />
                  )}
                />
                <Controller
                  name="password"
                  control={profileForm.control}
                  render={({ field, fieldState }) => (
                    <TextField
                      {...field}
                      type="password"
                      label="New Password"
                      error={!!fieldState.error}
                      helperText={fieldState.error?.message || "Leave blank to keep the current password."}
                      fullWidth
                    />
                  )}
                />
                <Button type="submit" variant="contained">
                  Save Profile
                </Button>
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card sx={{ mb: 2.5 }}>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Integration Config
              </Typography>
              <Stack
                component="form"
                spacing={2}
                onSubmit={submitIntegration}
              >
                <Controller
                  name="name"
                  control={integrationForm.control}
                  render={({ field, fieldState }) => (
                    <TextField
                      {...field}
                      label="Connection Name"
                      error={!!fieldState.error}
                      helperText={fieldState.error?.message}
                      fullWidth
                    />
                  )}
                />
                <Controller
                  name="type"
                  control={integrationForm.control}
                  render={({ field, fieldState }) => (
                    <TextField
                      {...field}
                      select
                      label="Provider"
                      error={!!fieldState.error}
                      helperText={fieldState.error?.message}
                      fullWidth
                    >
                      {integrationTypes.map((option) => (
                        <MenuItem key={option.value} value={option.value}>
                          {option.label}
                        </MenuItem>
                      ))}
                    </TextField>
                  )}
                />
                <Controller
                  name="client_secrets_path"
                  control={integrationForm.control}
                  render={({ field, fieldState }) => (
                    <TextField
                      {...field}
                      label="Credential Path"
                      placeholder="/secrets/gmail-client.json"
                      error={!!fieldState.error}
                      helperText={fieldState.error?.message}
                      fullWidth
                    />
                  )}
                />
                <Button type="submit" variant="contained">
                  Save Integration
                </Button>
              </Stack>
            </CardContent>
          </Card>

          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Connected Integrations
              </Typography>
              {integrations.length === 0 ? (
                <Typography color="text.secondary">
                  No saved integrations yet.
                </Typography>
              ) : (
                <List disablePadding>
                  {integrations.map((integration) => (
                    <ListItem key={integration.name} disableGutters>
                      <ListItemText
                        primary={integration.name}
                        secondary={`${integration.type || "custom"} integration`}
                      />
                    </ListItem>
                  ))}
                </List>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default Settings;
