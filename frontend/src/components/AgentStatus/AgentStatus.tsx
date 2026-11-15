import React, { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  Grid,
  List,
  ListItemButton,
  ListItemText,
  Stack,
  Typography,
} from "@mui/material";

import api from "../../services/api";

type AgentInfo = {
  type: string;
  name: string;
  status: string;
  last_run_at?: string | null;
};

type AgentRunLog = {
  agent_id: string;
  agent_type: string;
  timestamp: number;
  payload: Record<string, unknown>;
  success: boolean;
  output?: string | null;
  error?: string | null;
  duration_ms: number;
};

const statusColor = (status: string) => {
  if (status === "running") {
    return "warning";
  }
  if (status === "error") {
    return "error";
  }
  return "success";
};

const AgentStatus = () => {
  const [loading, setLoading] = useState(true);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [error, setError] = useState("");
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string>("");
  const [history, setHistory] = useState<AgentRunLog[]>([]);

  useEffect(() => {
    let active = true;

    const loadAgents = async () => {
      setLoading(true);
      setError("");
      try {
        const response = await api.get("/api/v1/agents/");
        if (!active) {
          return;
        }
        const nextAgents = response.data ?? [];
        setAgents(nextAgents);
        if (nextAgents.length > 0) {
          setSelectedAgent((current) => current || nextAgents[0].type);
        }
      } catch (requestError: any) {
        if (!active) {
          return;
        }
        setError(
          requestError?.response?.data?.detail ||
            requestError?.message ||
            "Agent status could not be loaded.",
        );
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    loadAgents();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;

    const loadHistory = async () => {
      if (!selectedAgent) {
        setHistory([]);
        return;
      }
      setHistoryLoading(true);
      try {
        const response = await api.get(
          `/api/v1/agents/${selectedAgent}/history?skip=0&limit=10`,
        );
        if (active) {
          setHistory(response.data ?? []);
        }
      } catch (requestError: any) {
        if (active) {
          setError(
            requestError?.response?.data?.detail ||
              requestError?.message ||
              "Agent history could not be loaded.",
          );
        }
      } finally {
        if (active) {
          setHistoryLoading(false);
        }
      }
    };

    loadHistory();
    return () => {
      active = false;
    };
  }, [selectedAgent]);

  if (loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", py: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: { xs: 2, md: 3 } }}>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>
        Agent Status
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        Inspect each agent type, confirm availability, and review recent run output.
      </Typography>

      {error ? <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert> : null}

      <Grid container spacing={2.5}>
        <Grid item xs={12} md={5}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Agent Cards
              </Typography>
              <Stack spacing={1.5}>
                {agents.map((agent) => (
                  <Card
                    key={agent.type}
                    variant={selectedAgent === agent.type ? "elevation" : "outlined"}
                    sx={{ borderRadius: 3 }}
                  >
                    <ListItemButton onClick={() => setSelectedAgent(agent.type)}>
                      <ListItemText
                        primary={agent.name}
                        secondary={agent.type.replaceAll("_", " ")}
                      />
                      <Chip
                        label={agent.status}
                        color={statusColor(agent.status)}
                        size="small"
                      />
                    </ListItemButton>
                  </Card>
                ))}
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={7}>
          <Card>
            <CardContent>
              <Stack
                direction="row"
                justifyContent="space-between"
                alignItems="center"
                sx={{ mb: 2 }}
              >
                <Typography variant="h6">
                  {selectedAgent
                    ? `${selectedAgent.replaceAll("_", " ")} history`
                    : "Run history"}
                </Typography>
                {selectedAgent ? (
                  <Chip
                    label={`${history.length} records`}
                    variant="outlined"
                    color="primary"
                  />
                ) : null}
              </Stack>

              {historyLoading ? (
                <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
                  <CircularProgress size={28} />
                </Box>
              ) : history.length === 0 ? (
                <Typography color="text.secondary">
                  No runs recorded yet for the selected agent.
                </Typography>
              ) : (
                <List disablePadding>
                  {history.map((entry, index) => (
                    <React.Fragment key={`${entry.agent_id}-${entry.timestamp}`}>
                      <Box sx={{ py: 1.5 }}>
                        <Stack
                          direction="row"
                          justifyContent="space-between"
                          alignItems="center"
                          sx={{ mb: 0.75 }}
                        >
                          <Typography sx={{ fontWeight: 600 }}>
                            {new Date(entry.timestamp * 1000).toLocaleString()}
                          </Typography>
                          <Chip
                            label={entry.success ? "Success" : "Error"}
                            color={entry.success ? "success" : "error"}
                            size="small"
                          />
                        </Stack>
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 0.75 }}>
                          Duration: {entry.duration_ms} ms
                        </Typography>
                        <Typography variant="body2">
                          {entry.output || entry.error || "No textual output returned."}
                        </Typography>
                      </Box>
                      {index < history.length - 1 ? <Divider /> : null}
                    </React.Fragment>
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

export default AgentStatus;
