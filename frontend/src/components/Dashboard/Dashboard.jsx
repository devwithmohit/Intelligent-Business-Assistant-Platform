import React, { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  Grid,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Stack,
  Typography,
} from "@mui/material";
import { useNavigate } from "react-router-dom";

import api from "../../services/api";

const initialState = {
  summary: null,
  agents: [],
  conversations: [],
};

const kpiCards = (summary) => [
  {
    label: "Conversations",
    value: summary?.total_conversations ?? 0,
    helper: "Customer and agent discussions recorded",
  },
  {
    label: "Messages",
    value: summary?.total_messages ?? 0,
    helper: "Total turns processed across all chats",
  },
  {
    label: "Active Agents",
    value: summary?.agents_active ?? 0,
    helper: "Runtime agent records ready to respond",
  },
];

const Dashboard = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [data, setData] = useState(initialState);

  useEffect(() => {
    let active = true;

    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const [summaryRes, agentsRes, conversationsRes] = await Promise.all([
          api.get("/api/v1/analytics/summary"),
          api.get("/api/v1/analytics/agents"),
          api.get("/api/v1/chat/conversations?skip=0&limit=5"),
        ]);
        if (!active) {
          return;
        }
        setData({
          summary: summaryRes.data,
          agents: agentsRes.data ?? [],
          conversations: conversationsRes.data ?? [],
        });
      } catch (requestError) {
        if (!active) {
          return;
        }
        setError(
          requestError?.response?.data?.detail ||
            requestError?.message ||
            "Dashboard data could not be loaded.",
        );
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    load();
    return () => {
      active = false;
    };
  }, []);

  if (loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", py: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: { xs: 2, md: 3 } }}>
      <Stack
        direction={{ xs: "column", md: "row" }}
        spacing={2}
        justifyContent="space-between"
        alignItems={{ xs: "flex-start", md: "center" }}
        sx={{ mb: 3 }}
      >
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700 }}>
            Platform Dashboard
          </Typography>
          <Typography color="text.secondary">
            Monitor conversations, agent readiness, and the next actions across the workspace.
          </Typography>
        </Box>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
          <Button variant="contained" onClick={() => navigate("/chat")}>
            Open Chat
          </Button>
          <Button variant="outlined" onClick={() => navigate("/agents")}>
            Review Agents
          </Button>
          <Button variant="outlined" onClick={() => navigate("/settings")}>
            Configure Integrations
          </Button>
        </Stack>
      </Stack>

      {error ? <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert> : null}

      <Grid container spacing={2.5} sx={{ mb: 2 }}>
        {kpiCards(data.summary).map((card) => (
          <Grid item xs={12} md={4} key={card.label}>
            <Card sx={{ height: "100%" }}>
              <CardContent>
                <Typography color="text.secondary" variant="overline">
                  {card.label}
                </Typography>
                <Typography variant="h3" sx={{ fontWeight: 700, my: 1 }}>
                  {card.value}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {card.helper}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      <Grid container spacing={2.5}>
        <Grid item xs={12} md={7}>
          <Card sx={{ height: "100%" }}>
            <CardContent>
              <Stack
                direction="row"
                justifyContent="space-between"
                alignItems="center"
                sx={{ mb: 2 }}
              >
                <Typography variant="h6">Agent Activity</Typography>
                <Chip
                  label={`${data.agents.length} agent types`}
                  color="primary"
                  variant="outlined"
                />
              </Stack>
              {data.agents.length === 0 ? (
                <Typography color="text.secondary">
                  Agent metrics will appear here after the first successful runs.
                </Typography>
              ) : (
                <List disablePadding>
                  {data.agents.map((agent, index) => (
                    <React.Fragment key={agent.agent_type}>
                      <ListItem disableGutters sx={{ py: 1.25 }}>
                        <ListItemText
                          primary={agent.agent_type.replaceAll("_", " ")}
                          secondary={`${agent.runs} runs • ${(agent.success_rate * 100).toFixed(0)}% success`}
                        />
                        <Chip
                          label={`${agent.avg_latency_ms} ms avg`}
                          color={agent.success_rate >= 0.75 ? "success" : "warning"}
                          variant="outlined"
                        />
                      </ListItem>
                      {index < data.agents.length - 1 ? <Divider /> : null}
                    </React.Fragment>
                  ))}
                </List>
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={5}>
          <Card sx={{ height: "100%" }}>
            <CardContent>
              <Stack
                direction="row"
                justifyContent="space-between"
                alignItems="center"
                sx={{ mb: 2 }}
              >
                <Typography variant="h6">Recent Conversations</Typography>
                <Button size="small" onClick={() => navigate("/chat")}>
                  View all
                </Button>
              </Stack>
              {data.conversations.length === 0 ? (
                <Typography color="text.secondary">
                  Start a conversation to build your activity feed.
                </Typography>
              ) : (
                <List disablePadding>
                  {data.conversations.map((conversation, index) => (
                    <React.Fragment key={conversation.id}>
                      <ListItemButton
                        sx={{ px: 0, py: 1.25 }}
                        onClick={() => navigate("/chat")}
                      >
                        <ListItemText
                          primary={conversation.title || "Untitled conversation"}
                          secondary={conversation.agent_type.replaceAll("_", " ")}
                        />
                      </ListItemButton>
                      {index < data.conversations.length - 1 ? <Divider /> : null}
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

export default Dashboard;
