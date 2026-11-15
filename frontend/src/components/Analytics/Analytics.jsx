import React, { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Card,
  CardContent,
  CircularProgress,
  Divider,
  Grid,
  LinearProgress,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";

import api from "../../services/api";

const Analytics = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [summary, setSummary] = useState(null);
  const [agents, setAgents] = useState([]);
  const [usage, setUsage] = useState([]);

  useEffect(() => {
    let active = true;

    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const [summaryRes, agentsRes, usageRes] = await Promise.all([
          api.get("/api/v1/analytics/summary"),
          api.get("/api/v1/analytics/agents"),
          api.get("/api/v1/analytics/usage"),
        ]);
        if (!active) {
          return;
        }
        setSummary(summaryRes.data);
        setAgents(agentsRes.data ?? []);
        setUsage(usageRes.data ?? []);
      } catch (requestError) {
        if (!active) {
          return;
        }
        setError(
          requestError?.response?.data?.detail ||
            requestError?.message ||
            "Analytics data could not be loaded.",
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

  const peakUsage = useMemo(() => {
    if (usage.length === 0) {
      return 1;
    }
    return Math.max(...usage.map((entry) => Math.max(entry.conversations, entry.messages)), 1);
  }, [usage]);

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
        Analytics
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        Review platform usage, response quality, and agent operating performance.
      </Typography>

      {error ? <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert> : null}

      <Grid container spacing={2.5} sx={{ mb: 2.5 }}>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" variant="overline">
                Total Conversations
              </Typography>
              <Typography variant="h3" sx={{ fontWeight: 700 }}>
                {summary?.total_conversations ?? 0}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" variant="overline">
                Total Messages
              </Typography>
              <Typography variant="h3" sx={{ fontWeight: 700 }}>
                {summary?.total_messages ?? 0}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" variant="overline">
                Agents Active
              </Typography>
              <Typography variant="h3" sx={{ fontWeight: 700 }}>
                {summary?.agents_active ?? 0}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Grid container spacing={2.5}>
        <Grid item xs={12} md={6}>
          <Card sx={{ height: "100%" }}>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Agent Performance
              </Typography>
              {agents.length === 0 ? (
                <Typography color="text.secondary">
                  Performance data will appear after agents have handled requests.
                </Typography>
              ) : (
                <Stack spacing={2}>
                  {agents.map((agent) => (
                    <Box key={agent.agent_type}>
                      <Stack
                        direction="row"
                        justifyContent="space-between"
                        alignItems="center"
                        sx={{ mb: 0.75 }}
                      >
                        <Typography sx={{ textTransform: "capitalize" }}>
                          {agent.agent_type.replaceAll("_", " ")}
                        </Typography>
                        <Typography color="text.secondary" variant="body2">
                          {agent.runs} runs
                        </Typography>
                      </Stack>
                      <LinearProgress
                        variant="determinate"
                        value={Math.max(0, Math.min(100, agent.success_rate * 100))}
                        sx={{ height: 10, borderRadius: 999 }}
                      />
                      <Stack
                        direction="row"
                        justifyContent="space-between"
                        sx={{ mt: 0.75 }}
                      >
                        <Typography variant="body2" color="text.secondary">
                          {(agent.success_rate * 100).toFixed(0)}% success
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {agent.avg_latency_ms} ms avg latency
                        </Typography>
                      </Stack>
                    </Box>
                  ))}
                </Stack>
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card sx={{ height: "100%" }}>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Usage Over Time
              </Typography>
              {usage.length === 0 ? (
                <Typography color="text.secondary">
                  Usage history will populate after conversation traffic starts flowing.
                </Typography>
              ) : (
                <Stack spacing={2}>
                  {usage.map((entry, index) => (
                    <React.Fragment key={entry.date}>
                      <Box>
                        <Stack
                          direction="row"
                          justifyContent="space-between"
                          alignItems="center"
                          sx={{ mb: 0.75 }}
                        >
                          <Typography>{entry.date}</Typography>
                          <Typography color="text.secondary" variant="body2">
                            {entry.conversations} conversations • {entry.messages} messages
                          </Typography>
                        </Stack>
                        <Box sx={{ display: "flex", gap: 1, alignItems: "center" }}>
                          <Box sx={{ flex: 1 }}>
                            <LinearProgress
                              color="primary"
                              variant="determinate"
                              value={(entry.conversations / peakUsage) * 100}
                              sx={{ height: 8, borderRadius: 999, mb: 0.75 }}
                            />
                            <LinearProgress
                              color="secondary"
                              variant="determinate"
                              value={(entry.messages / peakUsage) * 100}
                              sx={{ height: 8, borderRadius: 999 }}
                            />
                          </Box>
                        </Box>
                      </Box>
                      {index < usage.length - 1 ? <Divider /> : null}
                    </React.Fragment>
                  ))}
                </Stack>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Card sx={{ mt: 2.5 }}>
        <CardContent>
          <Typography variant="h6" sx={{ mb: 2 }}>
            Metrics Table
          </Typography>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Agent Type</TableCell>
                <TableCell align="right">Runs</TableCell>
                <TableCell align="right">Success Rate</TableCell>
                <TableCell align="right">Avg Latency</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {agents.map((agent) => (
                <TableRow key={agent.agent_type}>
                  <TableCell sx={{ textTransform: "capitalize" }}>
                    {agent.agent_type.replaceAll("_", " ")}
                  </TableCell>
                  <TableCell align="right">{agent.runs}</TableCell>
                  <TableCell align="right">
                    {(agent.success_rate * 100).toFixed(0)}%
                  </TableCell>
                  <TableCell align="right">{agent.avg_latency_ms} ms</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </Box>
  );
};

export default Analytics;
