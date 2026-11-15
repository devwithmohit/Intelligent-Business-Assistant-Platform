import React, { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Grid,
  IconButton,
  InputAdornment,
  MenuItem,
  Stack,
  Switch,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import RefreshIcon from "@mui/icons-material/Refresh";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import EditIcon from "@mui/icons-material/Edit";
import LockOutlinedIcon from "@mui/icons-material/LockOutlined";
import VisibilityIcon from "@mui/icons-material/Visibility";
import VisibilityOffIcon from "@mui/icons-material/VisibilityOff";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import SecurityIcon from "@mui/icons-material/Security";
import HubIcon from "@mui/icons-material/Hub";
import EmailIcon from "@mui/icons-material/Email";
import ChatBubbleOutlineIcon from "@mui/icons-material/ChatBubbleOutline";
import BusinessIcon from "@mui/icons-material/Business";
import CloudQueueIcon from "@mui/icons-material/CloudQueue";

import api from "../../services/api";

const PROVIDER_METADATA = {
  slack: {
    label: "Slack",
    category: "Messaging",
    color: "#4A154B",
    icon: <ChatBubbleOutlineIcon />,
    description: "Post notifications, listen to channels, and let agents reply in Slack threads.",
  },
  gmail: {
    label: "Gmail",
    category: "Email & Calendar",
    color: "#EA4335",
    icon: <EmailIcon />,
    description: "Read, summarize, and draft email replies with Google Workspace.",
  },
  hubspot: {
    label: "HubSpot",
    category: "CRM & Marketing",
    color: "#FF7A59",
    icon: <HubIcon />,
    description: "Sync contacts, manage pipeline deals, and log agent interactions.",
  },
  salesforce: {
    label: "Salesforce",
    category: "Enterprise CRM",
    color: "#00A1E0",
    icon: <BusinessIcon />,
    description: "Query enterprise accounts, leads, and custom CRM records.",
  },
  teams: {
    label: "Microsoft Teams",
    category: "Messaging",
    color: "#6264A7",
    icon: <ChatBubbleOutlineIcon />,
    description: "Trigger alerts and automate updates across Microsoft Teams channels.",
  },
  generic: {
    label: "Custom / Generic API",
    category: "Webhooks & APIs",
    color: "#1976D2",
    icon: <CloudQueueIcon />,
    description: "Connect any external REST endpoint or webhook service via API keys.",
  },
};

const Integrations = () => {
  const [integrations, setIntegrations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingName, setEditingName] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [showSecret, setShowSecret] = useState(false);

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [integrationToDelete, setIntegrationToDelete] = useState(null);

  const [formData, setFormData] = useState({
    name: "",
    type: "slack",
    enabled: true,
    // Provider specific fields
    token: "",
    default_channel: "",
    api_key: "",
    client_id: "",
    client_secret: "",
    username: "",
    password: "",
    security_token: "",
    domain: "login",
    webhook_url: "",
  });

  const fetchIntegrations = async () => {
    setLoading(true);
    setError("");
    try {
      const response = await api.get("/api/v1/integrations/");
      const records = response.data ?? {};
      setIntegrations(Object.values(records));
    } catch (err) {
      setError(
        err?.response?.data?.detail ||
          err?.message ||
          "Could not load integrations."
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIntegrations();
  }, []);

  const handleOpenAdd = (presetType = "slack") => {
    setEditingName(null);
    setShowSecret(false);
    setFormData({
      name: "",
      type: presetType,
      enabled: true,
      token: "",
      default_channel: "",
      api_key: "",
      client_id: "",
      client_secret: "",
      username: "",
      password: "",
      security_token: "",
      domain: "login",
      webhook_url: "",
    });
    setDialogOpen(true);
  };

  const handleOpenEdit = (integration) => {
    setEditingName(integration.name);
    setShowSecret(false);
    setFormData({
      name: integration.name || "",
      type: integration.type || "generic",
      enabled: integration.enabled !== false,
      token: integration.token || "",
      default_channel: integration.default_channel || "",
      api_key: integration.api_key || "",
      client_id: integration.client_id || "",
      client_secret: integration.client_secret || "",
      username: integration.username || "",
      password: integration.password || "",
      security_token: integration.security_token || "",
      domain: integration.domain || "login",
      webhook_url: integration.webhook_url || "",
    });
    setDialogOpen(true);
  };

  const handleSaveIntegration = async (e) => {
    e.preventDefault();
    if (!formData.name.trim()) return;

    setSubmitting(true);
    setError("");
    setSuccess("");

    // Assemble payload tailored to provider type without requiring client filesystem paths
    const payload = {
      name: formData.name.trim(),
      type: formData.type,
      enabled: formData.enabled,
    };

    if (formData.type === "slack") {
      if (formData.token) payload.token = formData.token.trim();
      if (formData.default_channel) payload.default_channel = formData.default_channel.trim();
    } else if (formData.type === "gmail") {
      if (formData.client_id) payload.client_id = formData.client_id.trim();
      if (formData.client_secret) payload.client_secret = formData.client_secret.trim();
      if (formData.token) payload.access_token = formData.token.trim();
      if (formData.api_key) payload.api_key = formData.api_key.trim();
    } else if (formData.type === "hubspot") {
      if (formData.api_key) payload.api_key = formData.api_key.trim();
      if (formData.token) payload.access_token = formData.token.trim();
    } else if (formData.type === "salesforce") {
      if (formData.username) payload.username = formData.username.trim();
      if (formData.password) payload.password = formData.password.trim();
      if (formData.security_token) payload.security_token = formData.security_token.trim();
      if (formData.domain) payload.domain = formData.domain.trim();
    } else if (formData.type === "teams") {
      if (formData.webhook_url) payload.webhook_url = formData.webhook_url.trim();
      if (formData.token) payload.access_token = formData.token.trim();
      if (formData.default_channel) payload.default_channel_id = formData.default_channel.trim();
    } else {
      if (formData.api_key) payload.api_key = formData.api_key.trim();
      if (formData.token) payload.token = formData.token.trim();
      if (formData.webhook_url) payload.webhook_url = formData.webhook_url.trim();
    }

    try {
      if (editingName) {
        await api.put(`/api/v1/integrations/${editingName}`, payload);
        setSuccess(`Integration "${payload.name}" updated successfully.`);
      } else {
        await api.post("/api/v1/integrations/", payload);
        setSuccess(`Integration "${payload.name}" registered and encrypted successfully.`);
      }
      setDialogOpen(false);
      await fetchIntegrations();
    } catch (err) {
      setError(
        err?.response?.data?.detail ||
          err?.message ||
          "Failed to save integration. Please check inputs."
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleEnabled = async (integration) => {
    const updatedStatus = !integration.enabled;
    try {
      await api.put(`/api/v1/integrations/${integration.name}`, {
        ...integration,
        enabled: updatedStatus,
      });
      setIntegrations((prev) =>
        prev.map((item) =>
          item.name === integration.name ? { ...item, enabled: updatedStatus } : item
        )
      );
      setSuccess(`Integration "${integration.name}" is now ${updatedStatus ? "active" : "disabled"}.`);
    } catch (err) {
      setError(
        err?.response?.data?.detail ||
          err?.message ||
          "Could not update status."
      );
    }
  };

  const handleDeleteIntegration = async () => {
    if (!integrationToDelete) return;
    try {
      await api.delete(`/api/v1/integrations/${integrationToDelete.name}`);
      setIntegrations((prev) => prev.filter((i) => i.name !== integrationToDelete.name));
      setSuccess(`Integration "${integrationToDelete.name}" was successfully removed.`);
      setDeleteDialogOpen(false);
    } catch (err) {
      setError(
        err?.response?.data?.detail ||
          err?.message ||
          "Failed to delete integration."
      );
    }
  };

  return (
    <Box sx={{ p: { xs: 2, md: 3 } }}>
      {/* Page Header */}
      <Stack
        direction={{ xs: "column", sm: "row" }}
        justifyContent="space-between"
        alignItems={{ xs: "flex-start", sm: "center" }}
        spacing={2}
        sx={{ mb: 3 }}
      >
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700 }}>
            Integrations
          </Typography>
          <Typography color="text.secondary">
            Connect enterprise tools and messaging services directly to your AI agents.
          </Typography>
        </Box>
        <Stack direction="row" spacing={1.5}>
          <Tooltip title="Refresh integrations">
            <IconButton onClick={fetchIntegrations} color="primary">
              <RefreshIcon />
            </IconButton>
          </Tooltip>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => handleOpenAdd("slack")}
            sx={{ fontWeight: 600 }}
          >
            Connect Integration
          </Button>
        </Stack>
      </Stack>

      {/* Security Alert Banner */}
      <Alert
        icon={<SecurityIcon fontSize="inherit" />}
        severity="info"
        sx={{ mb: 3, alignItems: "center" }}
      >
        <strong>Zero-Exposure Credential Storage:</strong> All credentials (API keys, bot tokens, and client secrets) are encrypted on disk via Fernet symmetric encryption and strictly scoped to your tenant account.
      </Alert>

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

      {/* Popular Providers Quick-Connect Shelf */}
      <Typography variant="h6" sx={{ fontWeight: 700, mb: 1.5 }}>
        Supported Services
      </Typography>
      <Grid container spacing={2} sx={{ mb: 4 }}>
        {Object.entries(PROVIDER_METADATA).map(([key, provider]) => (
          <Grid item xs={12} sm={6} md={4} key={key}>
            <Card
              variant="outlined"
              sx={{
                height: "100%",
                display: "flex",
                flexDirection: "column",
                transition: "border-color 0.2s, box-shadow 0.2s",
                "&:hover": { borderColor: "primary.main", boxShadow: 1 },
              }}
            >
              <CardContent sx={{ flexGrow: 1, p: 2 }}>
                <Stack direction="row" alignItems="center" spacing={1.5} sx={{ mb: 1 }}>
                  <Box
                    sx={{
                      p: 1,
                      borderRadius: 1.5,
                      bgcolor: "action.hover",
                      color: provider.color,
                      display: "flex",
                    }}
                  >
                    {provider.icon}
                  </Box>
                  <Box>
                    <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                      {provider.label}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {provider.category}
                    </Typography>
                  </Box>
                </Stack>
                <Typography variant="body2" color="text.secondary" sx={{ minHeight: 40, mb: 1.5 }}>
                  {provider.description}
                </Typography>
                <Button
                  size="small"
                  variant="outlined"
                  fullWidth
                  onClick={() => handleOpenAdd(key)}
                  sx={{ textTransform: "none", fontWeight: 600 }}
                >
                  Configure {provider.label}
                </Button>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {/* Active Integrations Section */}
      <Typography variant="h6" sx={{ fontWeight: 700, mb: 1.5 }}>
        Configured Connections ({integrations.length})
      </Typography>

      {loading ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 8 }}>
          <CircularProgress />
        </Box>
      ) : integrations.length === 0 ? (
        <Card variant="outlined" sx={{ py: 6, textAlign: "center", bgcolor: "background.paper" }}>
          <LockOutlinedIcon sx={{ fontSize: 44, color: "text.disabled", mb: 1 }} />
          <Typography variant="h6" color="text.secondary">
            No integrations connected yet
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Choose a provider above to securely link tools to your assistant platform.
          </Typography>
          <Button variant="contained" startIcon={<AddIcon />} onClick={() => handleOpenAdd("slack")}>
            Connect Now
          </Button>
        </Card>
      ) : (
        <Grid container spacing={2}>
          {integrations.map((integration) => {
            const provider = PROVIDER_METADATA[integration.type?.toLowerCase()] || PROVIDER_METADATA.generic;
            return (
              <Grid item xs={12} md={6} key={integration.name}>
                <Card
                  variant="outlined"
                  sx={{
                    borderRadius: 2,
                    borderLeft: "5px solid",
                    borderColor: integration.enabled ? "success.main" : "text.disabled",
                  }}
                >
                  <CardHeader
                    avatar={
                      <Box
                        sx={{
                          p: 1,
                          borderRadius: 1.5,
                          bgcolor: "action.hover",
                          color: provider.color,
                          display: "flex",
                        }}
                      >
                        {provider.icon}
                      </Box>
                    }
                    action={
                      <Stack direction="row" spacing={0.5} alignItems="center">
                        <Tooltip title={integration.enabled ? "Disable Integration" : "Enable Integration"}>
                          <Switch
                            checked={Boolean(integration.enabled)}
                            onChange={() => handleToggleEnabled(integration)}
                            color="success"
                            size="small"
                          />
                        </Tooltip>
                        <Tooltip title="Edit Connection">
                          <IconButton size="small" onClick={() => handleOpenEdit(integration)}>
                            <EditIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Delete Integration">
                          <IconButton
                            size="small"
                            color="error"
                            onClick={() => {
                              setIntegrationToDelete(integration);
                              setDeleteDialogOpen(true);
                            }}
                          >
                            <DeleteOutlineIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </Stack>
                    }
                    title={
                      <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                        {integration.name}
                      </Typography>
                    }
                    subheader={
                      <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 0.25 }}>
                        <Chip
                          label={provider.label}
                          size="small"
                          variant="outlined"
                          sx={{ height: 20, fontSize: "0.7rem", fontWeight: 600 }}
                        />
                        <Chip
                          label={integration.enabled ? "Active" : "Disabled"}
                          size="small"
                          color={integration.enabled ? "success" : "default"}
                          sx={{ height: 20, fontSize: "0.7rem" }}
                        />
                      </Stack>
                    }
                  />
                  <Divider />
                  <CardContent sx={{ py: 1.5 }}>
                    <Stack spacing={0.75}>
                      {integration.default_channel ? (
                        <Box sx={{ display: "flex", justifyContent: "space-between" }}>
                          <Typography variant="caption" color="text.secondary">
                            Channel:
                          </Typography>
                          <Typography variant="caption" sx={{ fontWeight: 600 }}>
                            {integration.default_channel}
                          </Typography>
                        </Box>
                      ) : null}

                      {integration.username ? (
                        <Box sx={{ display: "flex", justifyContent: "space-between" }}>
                          <Typography variant="caption" color="text.secondary">
                            User:
                          </Typography>
                          <Typography variant="caption" sx={{ fontWeight: 600 }}>
                            {integration.username}
                          </Typography>
                        </Box>
                      ) : null}

                      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <Typography variant="caption" color="text.secondary">
                          Encrypted Credential:
                        </Typography>
                        <Chip
                          label="******** (Redacted)"
                          size="small"
                          variant="outlined"
                          icon={<LockOutlinedIcon style={{ fontSize: 13 }} />}
                          sx={{ height: 22, fontSize: "0.72rem" }}
                        />
                      </Box>
                    </Stack>
                  </CardContent>
                </Card>
              </Grid>
            );
          })}
        </Grid>
      )}

      {/* Add / Edit Integration Modal */}
      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <form onSubmit={handleSaveIntegration}>
          <DialogTitle sx={{ fontWeight: 700 }}>
            {editingName ? `Edit ${editingName}` : "Connect New Integration"}
          </DialogTitle>
          <Divider />
          <DialogContent>
            <Stack spacing={2.5} sx={{ mt: 1 }}>
              <TextField
                select
                label="Integration Type / Provider"
                value={formData.type}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, type: e.target.value }))
                }
                disabled={Boolean(editingName)}
                fullWidth
              >
                {Object.entries(PROVIDER_METADATA).map(([key, provider]) => (
                  <MenuItem key={key} value={key}>
                    {provider.label} ({provider.category})
                  </MenuItem>
                ))}
              </TextField>

              <TextField
                required
                label="Connection Name"
                placeholder="e.g., Slack Ops Channel, Production HubSpot"
                value={formData.name}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, name: e.target.value }))
                }
                disabled={Boolean(editingName)}
                helperText="A unique identifier for agents to reference this connection."
                fullWidth
              />

              {/* Dynamic Credentials Form Fields based on Provider */}
              {formData.type === "slack" ? (
                <>
                  <TextField
                    required={!editingName}
                    label="Bot User OAuth Token"
                    placeholder="xoxb-xxxxxxxxxxxx"
                    type={showSecret ? "text" : "password"}
                    value={formData.token}
                    onChange={(e) =>
                      setFormData((prev) => ({ ...prev, token: e.target.value }))
                    }
                    helperText={editingName ? "Leave blank to keep existing encrypted token." : "Found in Slack App OAuth & Permissions."}
                    InputProps={{
                      endAdornment: (
                        <InputAdornment position="end">
                          <IconButton onClick={() => setShowSecret((s) => !s)} edge="end">
                            {showSecret ? <VisibilityOffIcon /> : <VisibilityIcon />}
                          </IconButton>
                        </InputAdornment>
                      ),
                    }}
                    fullWidth
                  />
                  <TextField
                    label="Default Channel"
                    placeholder="#general or C0123456789"
                    value={formData.default_channel}
                    onChange={(e) =>
                      setFormData((prev) => ({ ...prev, default_channel: e.target.value }))
                    }
                    fullWidth
                  />
                </>
              ) : null}

              {formData.type === "gmail" ? (
                <>
                  <TextField
                    label="Client ID / OAuth Client"
                    placeholder="xxxxxxxxxxxx.apps.googleusercontent.com"
                    value={formData.client_id}
                    onChange={(e) =>
                      setFormData((prev) => ({ ...prev, client_id: e.target.value }))
                    }
                    fullWidth
                  />
                  <TextField
                    required={!editingName}
                    label="Client Secret / API Key"
                    type={showSecret ? "text" : "password"}
                    value={formData.client_secret}
                    onChange={(e) =>
                      setFormData((prev) => ({ ...prev, client_secret: e.target.value }))
                    }
                    helperText={editingName ? "Leave blank to keep existing encrypted secret." : "Securely encrypted on disk."}
                    InputProps={{
                      endAdornment: (
                        <InputAdornment position="end">
                          <IconButton onClick={() => setShowSecret((s) => !s)} edge="end">
                            {showSecret ? <VisibilityOffIcon /> : <VisibilityIcon />}
                          </IconButton>
                        </InputAdornment>
                      ),
                    }}
                    fullWidth
                  />
                </>
              ) : null}

              {formData.type === "hubspot" ? (
                <TextField
                  required={!editingName}
                  label="HubSpot Private App Access Token or API Key"
                  placeholder="pat-na1-xxxxxxxx-xxxx"
                  type={showSecret ? "text" : "password"}
                  value={formData.api_key}
                  onChange={(e) =>
                    setFormData((prev) => ({ ...prev, api_key: e.target.value }))
                  }
                  helperText={editingName ? "Leave blank to keep existing encrypted key." : "From HubSpot Settings > Integrations > Private Apps."}
                  InputProps={{
                    endAdornment: (
                      <InputAdornment position="end">
                        <IconButton onClick={() => setShowSecret((s) => !s)} edge="end">
                          {showSecret ? <VisibilityOffIcon /> : <VisibilityIcon />}
                        </IconButton>
                      </InputAdornment>
                    ),
                  }}
                  fullWidth
                />
              ) : null}

              {formData.type === "salesforce" ? (
                <>
                  <TextField
                    label="Username / Service Account"
                    placeholder="agent-integration@yourorg.com"
                    value={formData.username}
                    onChange={(e) =>
                      setFormData((prev) => ({ ...prev, username: e.target.value }))
                    }
                    fullWidth
                  />
                  <TextField
                    required={!editingName}
                    label="Password"
                    type={showSecret ? "text" : "password"}
                    value={formData.password}
                    onChange={(e) =>
                      setFormData((prev) => ({ ...prev, password: e.target.value }))
                    }
                    InputProps={{
                      endAdornment: (
                        <InputAdornment position="end">
                          <IconButton onClick={() => setShowSecret((s) => !s)} edge="end">
                            {showSecret ? <VisibilityOffIcon /> : <VisibilityIcon />}
                          </IconButton>
                        </InputAdornment>
                      ),
                    }}
                    fullWidth
                  />
                  <TextField
                    label="Security Token"
                    type="password"
                    placeholder="Salesforce security token (if required)"
                    value={formData.security_token}
                    onChange={(e) =>
                      setFormData((prev) => ({ ...prev, security_token: e.target.value }))
                    }
                    fullWidth
                  />
                </>
              ) : null}

              {formData.type === "teams" || formData.type === "generic" ? (
                <>
                  <TextField
                    label="Webhook or API URL"
                    placeholder="https://outlook.office.com/webhook/..."
                    value={formData.webhook_url}
                    onChange={(e) =>
                      setFormData((prev) => ({ ...prev, webhook_url: e.target.value }))
                    }
                    fullWidth
                  />
                  <TextField
                    label="API Key / Bearer Token"
                    type={showSecret ? "text" : "password"}
                    value={formData.token}
                    onChange={(e) =>
                      setFormData((prev) => ({ ...prev, token: e.target.value }))
                    }
                    InputProps={{
                      endAdornment: (
                        <InputAdornment position="end">
                          <IconButton onClick={() => setShowSecret((s) => !s)} edge="end">
                            {showSecret ? <VisibilityOffIcon /> : <VisibilityIcon />}
                          </IconButton>
                        </InputAdornment>
                      ),
                    }}
                    fullWidth
                  />
                </>
              ) : null}

              <Stack direction="row" alignItems="center" spacing={1}>
                <Switch
                  checked={formData.enabled}
                  onChange={(e) =>
                    setFormData((prev) => ({ ...prev, enabled: e.target.checked }))
                  }
                  color="success"
                />
                <Typography variant="body2">
                  Enable integration immediately upon saving
                </Typography>
              </Stack>
            </Stack>
          </DialogContent>
          <DialogActions sx={{ px: 3, pb: 2 }}>
            <Button onClick={() => setDialogOpen(false)} disabled={submitting}>
              Cancel
            </Button>
            <Button
              type="submit"
              variant="contained"
              disabled={submitting}
              startIcon={submitting ? <CircularProgress size={16} /> : <LockOutlinedIcon />}
            >
              {editingName ? "Save Changes" : "Encrypt & Connect"}
            </Button>
          </DialogActions>
        </form>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
        maxWidth="xs"
      >
        <DialogTitle sx={{ fontWeight: 700 }}>Disconnect Integration</DialogTitle>
        <DialogContent>
          <Typography variant="body2">
            Are you sure you want to disconnect and delete "
            <strong>{integrationToDelete?.name}</strong>"? All stored encrypted keys will be permanently erased.
          </Typography>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleDeleteIntegration} color="error" variant="contained">
            Disconnect
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Integrations;
