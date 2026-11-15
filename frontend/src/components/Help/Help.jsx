import React, { useState } from "react";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  Grid,
  InputAdornment,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import SearchIcon from "@mui/icons-material/Search";
import HelpOutlineIcon from "@mui/icons-material/HelpOutline";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import SecurityIcon from "@mui/icons-material/Security";
import IntegrationInstructionsIcon from "@mui/icons-material/IntegrationInstructions";
import ChatIcon from "@mui/icons-material/Chat";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import CodeIcon from "@mui/icons-material/Code";

const FAQ_ITEMS = [
  {
    category: "Agents & Workflows",
    question: "How do autonomous agents execute tasks in the platform?",
    answer:
      "The platform features specialized autonomous agents: Customer Service, Sales Research, Content Creation, Data Analysis, and Project Management. When you submit a task or chat request, the orchestration engine passes context to the designated agent, which uses tools and vector embeddings to fulfill the objective.",
  },
  {
    category: "Security & Tenancy",
    question: "How does the platform enforce multi-tenant data isolation?",
    answer:
      "Every workflow, task, chat session, and integration connection is strictly bound to your tenant user_id in PostgreSQL. The backend API routers enforce ownership checks on every request, ensuring that no cross-tenant read or modification can occur.",
  },
  {
    category: "Security & Tenancy",
    question: "How are external integration API keys and tokens kept secure?",
    answer:
      "All sensitive integration payloads (Slack bot tokens, HubSpot API keys, Salesforce passwords) are encrypted at rest using Fernet symmetric cryptography with keys derived from the application SECRET_KEY. API responses automatically redact secrets to prevent credential leaks.",
  },
  {
    category: "Chat & WebSockets",
    question: "How does the real-time WebSocket chat authenticate?",
    answer:
      "The WebSocket connection at /api/ws/chat/{conversation_id} does not expose tokens in URL query strings. Instead, it completes an in-band authentication handshake immediately upon socket opening, validating the user's JWT securely.",
  },
  {
    category: "Integrations",
    question: "Do I need to upload files or client secrets from my computer?",
    answer:
      "No. The Integrations interface allows you to configure connections directly in your browser using API keys, OAuth tokens, and webhooks without needing client-side filesystem paths.",
  },
  {
    category: "Agents & Workflows",
    question: "What happens if a background task or agent execution fails?",
    answer:
      "Task statuses transition to 'cancelled' or display error details. You can review task logs, edit input parameters, and restart the execution directly from the Task Queue interface.",
  },
];

const GUIDES = [
  {
    icon: <AutoAwesomeIcon color="primary" />,
    title: "Agent Capabilities",
    desc: "Discover how customer service, research, and analysis agents work collaboratively.",
    tag: "Core",
  },
  {
    icon: <IntegrationInstructionsIcon color="secondary" />,
    title: "Tool Integrations",
    desc: "Learn how to connect Slack, HubSpot, Gmail, and custom webhooks securely.",
    tag: "Connectivity",
  },
  {
    icon: <ChatIcon color="info" />,
    title: "Live Chat Collaboration",
    desc: "Interact with agents in real-time with full conversational context and streaming.",
    tag: "Interface",
  },
  {
    icon: <SecurityIcon color="success" />,
    title: "Security & Governance",
    desc: "Review token handling, role-based controls, Fernet encryption, and tenant boundaries.",
    tag: "Security",
  },
];

const Help = () => {
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState(false);

  const handleAccordionChange = (panel) => (event, isExpanded) => {
    setExpanded(isExpanded ? panel : false);
  };

  const filteredFaqs = FAQ_ITEMS.filter((item) => {
    if (!search.trim()) return true;
    const term = search.toLowerCase();
    return (
      item.question.toLowerCase().includes(term) ||
      item.answer.toLowerCase().includes(term) ||
      item.category.toLowerCase().includes(term)
    );
  });

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
            Help & Documentation
          </Typography>
          <Typography color="text.secondary">
            Everything you need to configure agents, integrate tools, and monitor business automations.
          </Typography>
        </Box>
      </Stack>

      {/* Search Header Banner */}
      <Card
        sx={{
          mb: 4,
          p: { xs: 2, sm: 3 },
          background: "linear-gradient(135deg, rgba(25, 118, 210, 0.08) 0%, rgba(156, 39, 176, 0.08) 100%)",
          border: "1px solid",
          borderColor: "divider",
        }}
      >
        <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>
          How can we help you today?
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Search guides, FAQs, and architecture questions across the platform.
        </Typography>
        <TextField
          fullWidth
          placeholder="Search documentation, topics, or FAQs (e.g., 'Slack', 'encryption', 'websocket')..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon color="action" />
              </InputAdornment>
            ),
          }}
          sx={{ bgcolor: "background.paper", borderRadius: 1 }}
        />
      </Card>

      {/* Guide Cards */}
      <Typography variant="h6" sx={{ fontWeight: 700, mb: 2 }}>
        Platform Guides
      </Typography>
      <Grid container spacing={2.5} sx={{ mb: 4 }}>
        {GUIDES.map((guide, idx) => (
          <Grid item xs={12} sm={6} md={3} key={idx}>
            <Card
              variant="outlined"
              sx={{
                height: "100%",
                display: "flex",
                flexDirection: "column",
                borderRadius: 2,
                transition: "all 0.2s",
                "&:hover": { borderColor: "primary.main", transform: "translateY(-2px)", boxShadow: 2 },
              }}
            >
              <CardContent sx={{ flexGrow: 1, p: 2.5 }}>
                <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
                  <Box
                    sx={{
                      p: 1,
                      borderRadius: 1.5,
                      bgcolor: "action.hover",
                      display: "flex",
                    }}
                  >
                    {guide.icon}
                  </Box>
                  <Chip label={guide.tag} size="small" variant="outlined" sx={{ fontSize: "0.7rem" }} />
                </Stack>
                <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 0.5 }}>
                  {guide.title}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {guide.desc}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {/* FAQ Accordion Section */}
      <Typography variant="h6" sx={{ fontWeight: 700, mb: 2 }}>
        Frequently Asked Questions ({filteredFaqs.length})
      </Typography>

      {filteredFaqs.length === 0 ? (
        <Card variant="outlined" sx={{ py: 6, textAlign: "center" }}>
          <HelpOutlineIcon sx={{ fontSize: 40, color: "text.disabled", mb: 1 }} />
          <Typography variant="h6" color="text.secondary">
            No matching questions found
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Try adjusting your search terms to explore platform guides.
          </Typography>
        </Card>
      ) : (
        <Stack spacing={1.5} sx={{ mb: 4 }}>
          {filteredFaqs.map((faq, index) => {
            const panelId = `panel-${index}`;
            return (
              <Accordion
                key={index}
                expanded={expanded === panelId}
                onChange={handleAccordionChange(panelId)}
                variant="outlined"
                sx={{ borderRadius: "8px !important", overflow: "hidden" }}
              >
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Stack direction="row" spacing={1.5} alignItems="center">
                    <Chip
                      label={faq.category}
                      size="small"
                      color="primary"
                      variant="outlined"
                      sx={{ height: 22, fontSize: "0.7rem", fontWeight: 600 }}
                    />
                    <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                      {faq.question}
                    </Typography>
                  </Stack>
                </AccordionSummary>
                <AccordionDetails sx={{ pt: 0, pb: 2 }}>
                  <Divider sx={{ mb: 1.5 }} />
                  <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.7 }}>
                    {faq.answer}
                  </Typography>
                </AccordionDetails>
              </Accordion>
            );
          })}
        </Stack>
      )}

      {/* System Health & Architectural Guarantees */}
      <Card variant="outlined" sx={{ p: 2.5, bgcolor: "background.paper", borderRadius: 2 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 2 }}>
          System Architecture Status
        </Typography>
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6} md={3}>
            <Stack direction="row" spacing={1} alignItems="center">
              <CheckCircleIcon color="success" fontSize="small" />
              <Box>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  FastAPI Core
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Strict Tenancy & CORS
                </Typography>
              </Box>
            </Stack>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Stack direction="row" spacing={1} alignItems="center">
              <CheckCircleIcon color="success" fontSize="small" />
              <Box>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  Fernet Cryptography
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Credential Encryption Active
                </Typography>
              </Box>
            </Stack>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Stack direction="row" spacing={1} alignItems="center">
              <CheckCircleIcon color="success" fontSize="small" />
              <Box>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  WebSocket Handshake
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  In-Band Auth Secured
                </Typography>
              </Box>
            </Stack>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Stack direction="row" spacing={1} alignItems="center">
              <CheckCircleIcon color="success" fontSize="small" />
              <Box>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  PostgreSQL & Alembic
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Multi-Tenant Schema Up-to-Date
                </Typography>
              </Box>
            </Stack>
          </Grid>
        </Grid>
      </Card>
    </Box>
  );
};

export default Help;
