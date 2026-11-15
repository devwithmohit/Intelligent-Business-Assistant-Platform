import React, { useEffect, useMemo, useRef, useState } from "react";
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
  ListItemButton,
  ListItemText,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from "@mui/material";

import api from "../../services/api";

const agentOptions = [
  { value: "customer_service", label: "Customer Service" },
  { value: "sales_research", label: "Sales Research" },
  { value: "content_creation", label: "Content Creation" },
  { value: "data_analysis", label: "Data Analysis" },
  { value: "project_management", label: "Project Management" },
];

const buildWebSocketUrl = (conversationId) => {
  const baseUrl = api.defaults.baseURL || window.location.origin;
  const wsBase = baseUrl.replace(/^http/, "ws");
  return `${wsBase}/api/ws/chat/${conversationId}`;
};

const Chat = () => {
  const websocketRef = useRef(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [conversations, setConversations] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [message, setMessage] = useState("");
  const [agentType, setAgentType] = useState("customer_service");
  const [connectionState, setConnectionState] = useState("offline");

  const sortedConversations = useMemo(
    () => [...conversations].sort((left, right) => right.id - left.id),
    [conversations],
  );

  const refreshConversations = async () => {
    const response = await api.get("/api/v1/chat/conversations?skip=0&limit=50");
    setConversations(response.data ?? []);
  };

  const loadConversation = async (id) => {
    const response = await api.get(`/api/v1/chat/conversations/${id}`);
    const detail = response.data;
    setConversationId(detail.conversation.id);
    setMessages(detail.messages ?? []);
    setAgentType(detail.conversation.agent_type);
  };

  useEffect(() => {
    let active = true;

    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const response = await api.get("/api/v1/chat/conversations?skip=0&limit=50");
        if (!active) {
          return;
        }
        const nextConversations = response.data ?? [];
        setConversations(nextConversations);
        if (nextConversations.length > 0) {
          const firstConversation = nextConversations[0];
          await loadConversation(firstConversation.id);
        }
      } catch (requestError) {
        if (active) {
          setError(
            requestError?.response?.data?.detail ||
              requestError?.message ||
              "Chat history could not be loaded.",
          );
        }
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

  useEffect(() => {
    if (!conversationId) {
      setConnectionState("offline");
      if (websocketRef.current) {
        websocketRef.current.close();
        websocketRef.current = null;
      }
      return undefined;
    }

    const socket = new WebSocket(buildWebSocketUrl(conversationId));
    websocketRef.current = socket;
    setConnectionState("connecting");

    socket.onopen = () => {
      const token = localStorage.getItem("access_token");
      if (!token) {
        setConnectionState("offline");
        setError("Authentication required for live chat.");
        socket.close();
        return;
      }
      // Send secure in-band authentication frame immediately upon connection establishment
      socket.send(JSON.stringify({ type: "auth", token }));
    };

    socket.onmessage = (event) => {
      // Handle control frames (e.g. handshake confirmation)
      try {
        const payload = JSON.parse(event.data);
        if (
          payload?.type === "auth_success" ||
          payload?.status === "authenticated"
        ) {
          setConnectionState("live");
          return;
        }
        if (payload?.type === "pong") {
          return;
        }
      } catch {
        // Not a JSON control message; display as assistant reply
      }

      setMessages((current) => [
        ...current,
        {
          id: `assistant-${Date.now()}`,
          conversation_id: conversationId,
          role: "assistant",
          content: event.data,
          created_at: new Date().toISOString(),
        },
      ]);
      setSending(false);
      refreshConversations().catch(() => {});
    };

    socket.onerror = () => {
      setConnectionState("degraded");
    };

    socket.onclose = () => {
      setConnectionState("offline");
    };

    return () => {
      socket.close();
    };
  }, [conversationId]);

  const handleSend = async () => {
    const trimmed = message.trim();
    if (!trimmed || sending) {
      return;
    }

    setError("");
    setSending(true);

    const optimisticUserMessage = {
      id: `user-${Date.now()}`,
      conversation_id: conversationId ?? 0,
      role: "user",
      content: trimmed,
      created_at: new Date().toISOString(),
    };

    try {
      if (
        conversationId &&
        websocketRef.current &&
        websocketRef.current.readyState === WebSocket.OPEN
      ) {
        setMessages((current) => [...current, optimisticUserMessage]);
        websocketRef.current.send(trimmed);
        setMessage("");
        return;
      }

      const response = await api.post("/api/v1/chat/", {
        message: trimmed,
        agent_type: agentType,
        conversation_id: conversationId ?? undefined,
        context: {},
      });
      const data = response.data;
      setMessage("");
      await refreshConversations();
      await loadConversation(data.conversation_id);
    } catch (requestError) {
      setError(
        requestError?.response?.data?.detail ||
          requestError?.message ||
          "Message could not be sent.",
      );
    } finally {
      setSending(false);
    }
  };

  const startNewConversation = () => {
    setConversationId(null);
    setMessages([]);
    setMessage("");
    setError("");
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
      <Stack
        direction={{ xs: "column", md: "row" }}
        justifyContent="space-between"
        alignItems={{ xs: "flex-start", md: "center" }}
        spacing={1.5}
        sx={{ mb: 3 }}
      >
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700 }}>
            Agent Chat
          </Typography>
          <Typography color="text.secondary">
            Choose an agent, keep the thread context, and continue live conversations over WebSocket.
          </Typography>
        </Box>
        <Stack direction="row" spacing={1.5}>
          <Chip
            label={`Socket: ${connectionState}`}
            color={connectionState === "live" ? "success" : "default"}
            variant="outlined"
          />
          <Button variant="contained" onClick={startNewConversation}>
            New Conversation
          </Button>
        </Stack>
      </Stack>

      {error ? <Alert severity="error" sx={{ mb: 2.5 }}>{error}</Alert> : null}

      <Grid container spacing={2.5}>
        <Grid item xs={12} md={4}>
          <Card sx={{ height: "100%" }}>
            <CardContent>
              <Stack
                direction="row"
                justifyContent="space-between"
                alignItems="center"
                sx={{ mb: 2 }}
              >
                <Typography variant="h6">Conversations</Typography>
                <Chip label={`${sortedConversations.length}`} variant="outlined" />
              </Stack>
              {sortedConversations.length === 0 ? (
                <Typography color="text.secondary">
                  No conversation history yet. Start a new thread to begin.
                </Typography>
              ) : (
                <List disablePadding>
                  {sortedConversations.map((conversation) => (
                    <ListItemButton
                      key={conversation.id}
                      selected={conversation.id === conversationId}
                      onClick={() => loadConversation(conversation.id)}
                      sx={{ borderRadius: 2, mb: 0.5 }}
                    >
                      <ListItemText
                        primary={conversation.title || "Untitled conversation"}
                        secondary={conversation.agent_type.replaceAll("_", " ")}
                      />
                    </ListItemButton>
                  ))}
                </List>
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={8}>
          <Card>
            <CardContent>
              <Stack spacing={2}>
                <TextField
                  select
                  label="Agent"
                  value={agentType}
                  onChange={(event) => setAgentType(event.target.value)}
                  helperText="Existing conversations lock to their original agent type."
                  disabled={Boolean(conversationId)}
                >
                  {agentOptions.map((option) => (
                    <MenuItem key={option.value} value={option.value}>
                      {option.label}
                    </MenuItem>
                  ))}
                </TextField>

                <Box
                  sx={{
                    minHeight: 420,
                    maxHeight: 420,
                    overflowY: "auto",
                    borderRadius: 3,
                    border: "1px solid",
                    borderColor: "divider",
                    p: 2,
                    bgcolor: "background.default",
                  }}
                >
                  {messages.length === 0 ? (
                    <Box sx={{ py: 8, textAlign: "center" }}>
                      <Typography variant="h6" sx={{ mb: 1 }}>
                        Start the conversation
                      </Typography>
                      <Typography color="text.secondary">
                        Send the first message and the selected agent will respond here.
                      </Typography>
                    </Box>
                  ) : (
                    <Stack spacing={1.5}>
                      {messages.map((entry) => (
                        <Box
                          key={entry.id}
                          sx={{
                            alignSelf:
                              entry.role === "user" ? "flex-end" : "flex-start",
                            maxWidth: "85%",
                            px: 2,
                            py: 1.5,
                            borderRadius: 3,
                            bgcolor:
                              entry.role === "user"
                                ? "primary.main"
                                : "grey.100",
                            color:
                              entry.role === "user"
                                ? "primary.contrastText"
                                : "text.primary",
                          }}
                        >
                          <Typography
                            variant="caption"
                            sx={{ opacity: 0.8, display: "block", mb: 0.5 }}
                          >
                            {entry.role}
                          </Typography>
                          <Typography sx={{ whiteSpace: "pre-wrap" }}>
                            {entry.content}
                          </Typography>
                        </Box>
                      ))}
                    </Stack>
                  )}
                </Box>

                <Divider />

                <Stack spacing={1.5}>
                  <TextField
                    label="Message"
                    multiline
                    minRows={4}
                    value={message}
                    onChange={(event) => setMessage(event.target.value)}
                    placeholder="Ask the agent to help with research, content, support, analytics, or planning."
                  />
                  <Stack
                    direction={{ xs: "column", sm: "row" }}
                    justifyContent="space-between"
                    alignItems={{ xs: "stretch", sm: "center" }}
                    spacing={1.5}
                  >
                    <Typography color="text.secondary" variant="body2">
                      Conversation responses stream live when a socket is active.
                    </Typography>
                    <Button
                      variant="contained"
                      onClick={handleSend}
                      disabled={sending || !message.trim()}
                    >
                      {sending ? "Sending..." : "Send Message"}
                    </Button>
                  </Stack>
                </Stack>
              </Stack>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default Chat;
