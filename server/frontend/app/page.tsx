"use client";

import { apiFetch } from "./lib/api";
import { getBackendUrl } from "./lib/backend";
import Link from "next/link";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

type StatusState = "good" | "bad" | "warn" | "neutral" | "active";
type AutomationMode = "manual" | "auto";

type Message = {
  role: "user" | "assistant";
  content: string;
};

type Session = {
  id: string;
  title: string;
};

const BACKEND_URL = getBackendUrl();

const SYSTEM_POLL_MS = Number(process.env.NEXT_PUBLIC_SYSTEM_POLL_MS ?? "3000");

function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

function displayValue(value: unknown, fallback = "—") {
  if (value === null || value === undefined || value === "") return fallback;
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value);
}

function formatJson(value: unknown, fallback = "No data") {
  if (value === null || value === undefined || value === "") return fallback;
  if (typeof value === "string") return value;

  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function formatMode(value?: string | null) {
  if (!value) return "—";

  return value
    .replace(/[_-]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatTemp(value: unknown) {
  const n = Number(value);
  return Number.isFinite(n) ? `${n.toFixed(1)}°F` : "—";
}

function formatPercent(value: unknown, digits = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? `${n.toFixed(digits)}%` : "—";
}

function formatUpdated(value?: number | null) {
  if (!Number.isFinite(value)) return "Waiting for data";

  const timestamp = Number(value);
  const ms = timestamp > 1_000_000_000_000 ? timestamp : timestamp * 1000;
  const diff = Math.max(0, Date.now() - ms);

  if (diff < 5000) return "Updated now";

  const seconds = Math.round(diff / 1000);
  if (seconds < 60) return `Updated ${seconds}s ago`;

  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `Updated ${minutes}m ago`;

  const hours = Math.round(minutes / 60);
  return `Updated ${hours}h ago`;
}

function formatSessionTitle(session: Session) {
  const title = session.title?.trim() || "Untitled chat";

  if (/^\d+(\s*x\s*)?\d+$/.test(title)) {
    return `Conversation ${session.id.slice(0, 8)}`;
  }

  return title;
}

function stateClasses(state: StatusState) {
  if (state === "good") {
    return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
  }

  if (state === "bad") {
    return "border-red-500/30 bg-red-500/10 text-red-300";
  }

  if (state === "warn") {
    return "border-amber-500/30 bg-amber-500/10 text-amber-300";
  }

  if (state === "active") {
    return "border-blue-500/30 bg-blue-500/10 text-blue-300";
  }

  return "border-neutral-700 bg-neutral-900 text-neutral-300";
}

function textStateClass(state: StatusState) {
  if (state === "good") return "text-emerald-200";
  if (state === "bad") return "text-red-200";
  if (state === "warn") return "text-amber-200";
  if (state === "active") return "text-blue-200";
  return "text-white";
}

function dotClass(state: StatusState) {
  if (state === "good") return "bg-emerald-300";
  if (state === "bad") return "bg-red-300";
  if (state === "warn") return "bg-amber-300";
  if (state === "active") return "bg-blue-300";
  return "bg-neutral-500";
}

function Pill({
  label,
  state = "neutral",
}: {
  label: string;
  state?: StatusState;
}) {
  return (
    <span
      className={cx(
        "inline-flex shrink-0 items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold",
        stateClasses(state),
      )}
    >
      <span className={cx("h-2 w-2 rounded-full", dotClass(state))} />
      {label}
    </span>
  );
}

function Button({
  children,
  onClick,
  disabled,
  variant = "primary",
  className,
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: "primary" | "success" | "danger" | "secondary" | "ghost";
  className?: string;
}) {
  const variantClass =
    variant === "success"
      ? "bg-emerald-600 text-white hover:bg-emerald-500"
      : variant === "danger"
        ? "bg-red-600 text-white hover:bg-red-500"
        : variant === "secondary"
          ? "border border-neutral-700 bg-neutral-900 text-neutral-100 hover:bg-neutral-800"
          : variant === "ghost"
            ? "text-neutral-300 hover:bg-neutral-900"
            : "bg-blue-600 text-white hover:bg-blue-500";

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cx(
        "inline-flex items-center justify-center rounded-xl px-4 py-3 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50",
        variantClass,
        className,
      )}
    >
      {children}
    </button>
  );
}

function MetricCard({
  label,
  value,
  sub,
  state = "neutral",
}: {
  label: string;
  value: ReactNode;
  sub?: string;
  state?: StatusState;
}) {
  return (
    <div className="rounded-2xl border border-neutral-800 bg-neutral-950 p-5 shadow-lg">
      <p className="text-xs uppercase tracking-[0.18em] text-neutral-500">
        {label}
      </p>
      <div className={cx("mt-2 text-3xl font-semibold", textStateClass(state))}>
        {value}
      </div>
      {sub ? <p className="mt-1 text-sm text-neutral-400">{sub}</p> : null}
    </div>
  );
}

function Field({
  label,
  value,
  state = "neutral",
}: {
  label: string;
  value: ReactNode;
  state?: StatusState;
}) {
  return (
    <div className="rounded-2xl border border-neutral-800 bg-neutral-950 p-4">
      <p className="text-xs uppercase tracking-[0.18em] text-neutral-500">
        {label}
      </p>
      <div className={cx("mt-2 break-words text-lg font-semibold", textStateClass(state))}>
        {value}
      </div>
    </div>
  );
}

function Section({
  title,
  subtitle,
  right,
  children,
}: {
  title: string;
  subtitle?: string;
  right?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-neutral-800 bg-neutral-950 p-5 shadow-lg">
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold text-white">{title}</h2>
          {subtitle ? <p className="mt-1 text-sm text-neutral-500">{subtitle}</p> : null}
        </div>
        {right}
      </div>
      {children}
    </section>
  );
}

function SubsystemCard({
  icon,
  title,
  subtitle,
  href,
  status,
  statusState,
  primary,
  fields,
}: {
  icon: string;
  title: string;
  subtitle: string;
  href: string;
  status: string;
  statusState: StatusState;
  primary: ReactNode;
  fields: Array<{
    label: string;
    value: ReactNode;
    state?: StatusState;
  }>;
}) {
  return (
    <section className="rounded-2xl border border-neutral-800 bg-neutral-950 p-5 shadow-lg">
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-neutral-800 bg-black text-xl">
            {icon}
          </div>
          <div className="min-w-0">
            <h2 className="truncate text-lg font-semibold text-white">{title}</h2>
            <p className="mt-1 line-clamp-2 text-sm text-neutral-500">{subtitle}</p>
          </div>
        </div>

        <Pill label={status} state={statusState} />
      </div>

      <div className="mt-5">
        <p className="text-xs uppercase tracking-[0.18em] text-neutral-500">
          Current State
        </p>
        <div className="mt-2 text-3xl font-semibold text-white">{primary}</div>
      </div>

      <div className="mt-5 grid grid-cols-2 gap-3">
        {fields.map((field) => (
          <Field
            key={field.label}
            label={field.label}
            value={field.value}
            state={field.state}
          />
        ))}
      </div>

      <Link
        href={href}
        className="mt-5 inline-flex h-11 w-full items-center justify-center rounded-xl border border-neutral-700 bg-neutral-900 px-4 text-sm font-semibold text-neutral-100 transition hover:bg-neutral-800"
      >
        Open {title}
      </Link>
    </section>
  );
}

function EmptyChatState({
  onSuggestion,
}: {
  onSuggestion: (value: string) => void;
}) {
  const suggestions = [
    "Check home system health",
    "Explain current weather state",
    "Why is irrigation delayed?",
    "Set sprinkler schedule weekdays at 6am for 10 minutes all zones",
    "Set thermostat to 72",
  ];

  return (
    <div className="rounded-2xl border border-neutral-800 bg-black p-6 text-center">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl border border-blue-500/30 bg-blue-500/10 text-2xl">
        🤖
      </div>
      <h3 className="mt-4 text-lg font-semibold text-white">
        Orion is monitoring your system
      </h3>
      <p className="mt-2 text-sm leading-6 text-neutral-400">
        Ask about live telemetry, inspect a device, or let Orion explain the current recommendation.
      </p>

      <div className="mt-4 flex flex-wrap justify-center gap-2">
        {suggestions.map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            onClick={() => onSuggestion(suggestion)}
            className="rounded-full border border-neutral-700 bg-neutral-950 px-3 py-1.5 text-xs font-medium text-neutral-300 transition hover:bg-neutral-900 hover:text-white"
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  );
}

function extractStreamPayload(payload: string) {
  if (payload.length === 0) return "\n";

  try {
    const parsed = JSON.parse(payload);

    if (typeof parsed === "string") return parsed;

    if (parsed && typeof parsed === "object") {
      const obj = parsed as Record<string, unknown>;

      const simpleKeys = [
        "content",
        "delta",
        "token",
        "text",
        "response",
        "message",
      ];

      for (const key of simpleKeys) {
        if (typeof obj[key] === "string") {
          return obj[key] as string;
        }
      }

      const choices = obj.choices;

      if (Array.isArray(choices) && choices.length > 0) {
        const first = choices[0];

        if (first && typeof first === "object") {
          const choice = first as Record<string, unknown>;

          if (typeof choice.text === "string") return choice.text;

          const delta = choice.delta;

          if (delta && typeof delta === "object") {
            const deltaObj = delta as Record<string, unknown>;

            if (typeof deltaObj.content === "string") {
              return deltaObj.content;
            }
          }
        }
      }

      return JSON.stringify(parsed);
    }

    return String(parsed);
  } catch {
    return payload;
  }
}

export default function Home() {
  const [system, setSystem] = useState<any>(null);
  const [vision, setVision] = useState<any>(null);
  const [cameras, setCameras] = useState<any>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [abortController, setAbortController] =
    useState<AbortController | null>(null);
  const [controlLoading, setControlLoading] = useState(false);
  const [controlResult, setControlResult] = useState<unknown>(null);
  const [automationMode, setAutomationMode] = useState<AutomationMode>("manual");

  const messageEndRef = useRef<HTMLDivElement | null>(null);

  const loadSystem = useCallback(async () => {
    try {
      const res = await apiFetch(`${BACKEND_URL}/v1/system`, {
        cache: "no-store",
      });

      if (!res.ok) return;

      const data = await res.json();
      setSystem(data);

      if (data?.automation_mode === "auto" || data?.automation_mode === "manual") {
        setAutomationMode(data.automation_mode);
      }
    } catch {}
  }, []);

  const loadVision = useCallback(async () => {
    try {
      const res = await apiFetch(`${BACKEND_URL}/v1/vision/status`, {
        cache: "no-store",
      });

      const data = await res.json().catch(() => null);

      if (!res.ok) {
        setVision({
          online: false,
          error: data?.error || "Vision node unavailable",
        });
        return;
      }

      setVision(data);
    } catch (err) {
      setVision({
        online: false,
        error: err instanceof Error ? err.message : String(err),
      });
    }
  }, []);

  const loadCameras = useCallback(async () => {
    try {
      const res = await apiFetch(`${BACKEND_URL}/v1/cameras`, {
        cache: "no-store",
      });

      const data = await res.json().catch(() => null);

      if (!res.ok) {
        setCameras({
          system: "cameras",
          summary: { total: 0, online: 0, unknown: 0, external_cloud: 0 },
          devices: [],
          error: data?.error || "Camera subsystem unavailable",
        });
        return;
      }

      setCameras(data);
    } catch (err) {
      setCameras({
        system: "cameras",
        summary: { total: 0, online: 0, unknown: 0, external_cloud: 0 },
        devices: [],
        error: err instanceof Error ? err.message : String(err),
      });
    }
  }, []);

  const loadSessions = useCallback(async () => {
    try {
      const res = await apiFetch(`${BACKEND_URL}/v1/sessions`);
      if (!res.ok) return;

      const data = await res.json();
      setSessions(data.sessions || []);
    } catch {}
  }, []);

  useEffect(() => {
    loadSystem();
    loadVision();
    loadCameras();
    loadSessions();

    const timer = window.setInterval(() => {
      loadSystem();
      loadVision();
      loadCameras();
    }, Number.isFinite(SYSTEM_POLL_MS) ? SYSTEM_POLL_MS : 3000);

    return () => window.clearInterval(timer);
  }, [loadSystem, loadVision, loadCameras, loadSessions]);

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const weather = system?.weather || {};
  const thermostat = system?.thermostat || {};
  const thermostatRaw = thermostat?.raw || {};
  const sprinkler = system?.sprinkler || {};
  const sprinklerRaw = sprinkler?.raw || {};
  const environment = system?.environment || {};
  const decision = system?.last_decision || {};
  const cameraSummary = cameras?.summary || {};
  const cameraDevices = Array.isArray(cameras?.devices) ? cameras.devices : [];
  const primaryCamera = cameraDevices[0] || {};

  const cameraStatus =
    cameraDevices.length === 0
      ? "Unavailable"
      : cameraSummary.online > 0
        ? "Online"
        : cameraSummary.unknown > 0
          ? "Unknown"
          : "Offline";

  const cameraState: StatusState =
    cameraDevices.length === 0
      ? "bad"
      : cameraSummary.online > 0
        ? "good"
        : cameraSummary.unknown > 0
          ? "warn"
          : "bad";

  const cameraPrimary =
    primaryCamera?.integration_type === "external_cloud"
      ? "External Cloud"
      : formatMode(primaryCamera?.integration_type || "Camera Device");

  const rainChance = Number(weather?.rain_chance ?? 0);
  const aiActive = String(system?.ai_status || "").toLowerCase() === "active";

  const hvacCooling = Boolean(thermostat?.cooling || thermostatRaw?.cooling);
  const hvacHeating = Boolean(thermostat?.heating || thermostatRaw?.heating);
  const hvacFan = Boolean(
    thermostat?.fan ||
      thermostat?.fan_active ||
      thermostatRaw?.fan ||
      thermostatRaw?.fan_on ||
      thermostatRaw?.fan_active,
  );

  const hvacOnline =
    thermostat?.online !== false &&
    thermostatRaw?.online !== false &&
    thermostatRaw?.node_online !== false;

  const coolStage = Number(
    thermostatRaw?.cool_stage ?? thermostatRaw?.node_cool_stage ?? (hvacCooling ? 1 : 0),
  );

  const hvacStatus = !hvacOnline
    ? "Offline"
    : hvacCooling
      ? "Cooling"
      : hvacHeating
        ? "Heating"
        : hvacFan
          ? "Fan"
          : "Online";

  const hvacState: StatusState =
    !hvacOnline ? "bad" : hvacCooling || hvacHeating || hvacFan ? "active" : "good";

  const hvacStage = hvacCooling
    ? coolStage >= 2
      ? "Stage 2 Active"
      : "Stage 1 Active"
    : hvacHeating
      ? "Heating Active"
      : "Standby";

  const sprinklerRunning = Boolean(sprinkler?.running || sprinklerRaw?.running);
  const sprinklerOnline =
    sprinkler?.online !== false &&
    sprinklerRaw?.online !== false &&
    sprinklerRaw?.node_online !== false &&
    sprinklerRaw?.controller_online !== false;

  const rainSensor = sprinkler?.rain_sensor || sprinklerRaw?.rain_sensor || {};
  const rainWet = Boolean(rainSensor?.wet);
  const rainInhibit = Boolean(
    sprinkler?.rain_inhibit || (rainWet && rainSensor?.blocks_schedule),
  );

  const sprinklerStatus = !sprinklerOnline
    ? "Offline"
    : sprinklerRunning
      ? "Running"
      : rainInhibit
        ? "Rain Inhibit"
        : "Idle";

  const sprinklerState: StatusState = !sprinklerOnline
    ? "bad"
    : sprinklerRunning
      ? "active"
      : rainInhibit
        ? "warn"
        : "good";

  const activeZone =
    sprinkler?.zone ??
    sprinkler?.active_zone ??
    sprinklerRaw?.active_zone ??
    sprinklerRaw?.current_zone;

  const nextRun =
    sprinkler?.next_run ??
    sprinklerRaw?.next_run ??
    system?.irrigation_schedule?.next_run ??
    "No scheduled run";

  const weatherStatus = weather?.online === false
    ? "Offline"
    : rainChance >= 70
      ? "Rain likely"
      : rainChance >= 40
        ? "Rain possible"
        : weather?.condition || "Online";

  const weatherState: StatusState = weather?.online === false
    ? "bad"
    : rainChance >= 40
      ? "warn"
      : "good";

  const visionStatus = !vision
    ? "Unknown"
    : vision?.online
      ? "Online"
      : "Offline";

  const visionState: StatusState = !vision
    ? "neutral"
    : vision?.fault
      ? "bad"
      : vision?.online
        ? "good"
        : "bad";

  const systemHealthState: StatusState = !system
    ? "neutral"
    : system?.fault
      ? "bad"
      : "good";

  const recommendation = useMemo(() => {
    if (!system) {
      return {
        title: "Waiting for telemetry",
        detail: "Orion is waiting for live system state.",
        action: "observe",
        state: "neutral" as StatusState,
        canApply: false,
        applyLabel: "Apply",
      };
    }

    if (system.fault) {
      return {
        title: "Investigate fault",
        detail: `A system fault is present: ${system.fault}. Review logs before automation.`,
        action: "observe",
        state: "bad" as StatusState,
        canApply: false,
        applyLabel: "Review",
      };
    }

    if (rainChance >= 70 && sprinklerRunning) {
      return {
        title: "Stop irrigation",
        detail: `Rain chance is ${formatPercent(rainChance)} while irrigation is running.`,
        action: "stop_sprinkler",
        state: "warn" as StatusState,
        canApply: true,
        applyLabel: "Stop sprinkler",
      };
    }

    if (rainChance >= 70) {
      return {
        title: "Delay irrigation",
        detail: `Rain probability is ${formatPercent(rainChance)}. Orion recommends skipping the next scheduled irrigation cycle. No sprinkler output is active.`,
        action: "delay_irrigation",
        state: "warn" as StatusState,
        canApply: true,
        applyLabel: "Apply delay",
      };
    }

    if (hvacCooling) {
      return {
        title: "Monitor cooling",
        detail: `HVAC is cooling at ${formatTemp(thermostat?.temp ?? thermostat?.temperature)}.`,
        action: "observe",
        state: "active" as StatusState,
        canApply: false,
        applyLabel: "Observe",
      };
    }

    return {
      title: "Monitor system",
      detail: "No immediate hardware action is required.",
      action: "observe",
      state: "good" as StatusState,
      canApply: false,
      applyLabel: "Observe",
    };
  }, [system, rainChance, sprinklerRunning, hvacCooling, thermostat]);

  async function postControl(path: string, body: Record<string, unknown> = {}) {
    setControlLoading(true);

    try {
      const res = await apiFetch(`${BACKEND_URL}${path}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });

      const text = await res.text();

      let data: unknown;
      try {
        data = JSON.parse(text);
      } catch {
        data = text;
      }

      const result = {
        ok: res.ok,
        status: res.status,
        response: data,
      };

      setControlResult(result);
      await loadSystem();
      return result;
    } catch (err) {
      const result = {
        ok: false,
        error: err instanceof Error ? err.message : String(err),
      };

      setControlResult(result);
      return result;
    } finally {
      setControlLoading(false);
    }
  }

  async function applyRecommendation() {
    if (!recommendation.canApply || controlLoading) return;

    if (recommendation.action === "stop_sprinkler") {
      await postControl("/v1/control/sprinkler/stop", {
        source: "main_dashboard",
        reason: recommendation.detail,
      });
      return;
    }

    if (recommendation.action === "delay_irrigation") {
      await postControl("/v1/control/sprinkler/skip", {
        source: "main_dashboard",
        reason: recommendation.detail,
      });
      return;
    }

    await postControl("/v1/control/ai/execute", {
      action: recommendation.action,
      source: "main_dashboard",
      state: system,
    });
  }

  async function setAutomationModeAction(mode: AutomationMode) {
    setAutomationMode(mode);

    await postControl("/v1/control/ai/mode", {
      mode,
    });
  }

  function askSuggestion(value: string) {
    setInput(value);
  }

  function stopGeneration() {
    abortController?.abort();
    setAbortController(null);
    setLoading(false);
  }

  function newChat() {
    abortController?.abort();
    setAbortController(null);
    setLoading(false);
    setMessages([]);
    setSessionId(null);
  }

  async function loadChat(id: string) {
    abortController?.abort();
    setAbortController(null);
    setLoading(false);
    setSessionId(id);

    try {
      const res = await apiFetch(`${BACKEND_URL}/v1/session/${id}`);
      if (!res.ok) return;

      const data = await res.json();
      setMessages((data.messages || []) as Message[]);
    } catch {
      setMessages([
        {
          role: "assistant",
          content: "Error: failed to load this chat.",
        },
      ]);
    }
  }

  async function renameChat(id: string) {
    const title = window.prompt("Rename chat:");
    if (!title?.trim()) return;

    await apiFetch(`${BACKEND_URL}/v1/session/${id}/rename`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ title: title.trim() }),
    });

    await loadSessions();
  }

  async function deleteChat(id: string) {
    const confirmed = window.confirm("Delete this chat?");
    if (!confirmed) return;

    await apiFetch(`${BACKEND_URL}/v1/session/${id}`, {
      method: "DELETE",
    });

    if (sessionId === id) {
      setMessages([]);
      setSessionId(null);
    }

    await loadSessions();
  }

  function appendAssistantReply(reply: string) {
    setMessages((prev) => {
      const updated = [...prev];

      if (updated.length > 0) {
        updated[updated.length - 1] = {
          ...updated[updated.length - 1],
          content: reply,
        };
      }

      return updated;
    });
  }

  async function sendMessage() {
    if (!input.trim() || loading) return;

    const userText = input.trim();

    const newMessages: Message[] = [
      ...messages,
      {
        role: "user",
        content: userText,
      },
    ];

    setMessages(newMessages);
    setInput("");
    setLoading(true);

    const controller = new AbortController();
    setAbortController(controller);

    try {
      const res = await apiFetch(`${BACKEND_URL}/v1/chat/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        signal: controller.signal,
        body: JSON.stringify({
          messages: newMessages,
          session_id: sessionId,
        }),
      });

      const returnedSessionId = res.headers.get("X-Session-ID");
      const isNewSession = !sessionId;

      if (returnedSessionId) {
        setSessionId(returnedSessionId);
      }

      if (!res.ok || !res.body) {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: "Error: failed to contact backend.",
          },
        ]);
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();

      let reply = "";
      let buffer = "";

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "",
        },
      ]);

      function processEvent(event: string) {
        const normalizedEvent = event.replace(/\r\n/g, "\n").trimEnd();

        const dataLines = normalizedEvent
          .split("\n")
          .filter((line) => line.startsWith("data:"));

        if (dataLines.length === 0) return;

        const payload = dataLines
          .map((line) => line.replace(/^data:\s?/, ""))
          .join("\n");

        if (payload === "[DONE]") return;

        reply += extractStreamPayload(payload);
        appendAssistantReply(reply);
      }

      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        const events = buffer.split("\n\n");
        buffer = events.pop() || "";

        for (const event of events) {
          processEvent(event);
        }
      }

      if (buffer.trim()) {
        processEvent(buffer);
      }

      if (returnedSessionId && isNewSession) {
        const sessionRes = await apiFetch(
          `${BACKEND_URL}/v1/session/${returnedSessionId}`,
        );

        if (sessionRes.ok) {
          const sessionData = await sessionRes.json();
          setMessages((sessionData.messages || []) as Message[]);
        }
      }
    } catch (err) {
      const aborted =
        controller.signal.aborted ||
        (err instanceof DOMException && err.name === "AbortError");

      if (!aborted) {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: "Error: failed to contact backend.",
          },
        ]);
      }
    } finally {
      setAbortController(null);
      setLoading(false);
      await loadSessions();
      await loadSystem();
    }
  }

  const updatedLabel = formatUpdated(system?.last_update);

  return (
    <main className="min-h-screen bg-black px-6 py-8 text-white">
      <div className="mx-auto max-w-7xl">
        <header className="mb-8 flex flex-col justify-between gap-5 md:flex-row md:items-start">
          <div>
            <p className="text-xs uppercase tracking-[0.25em] text-neutral-500">
              Orion Control Platform
            </p>
            <h1 className="mt-2 text-5xl font-semibold tracking-tight text-white">
              Home Operations Dashboard
            </h1>
            <p className="mt-3 max-w-3xl text-neutral-400">
              Central command overview for distributed edge automation, live
              telemetry, supervisory decisions, environmental intelligence, and
              subsystem health.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Pill label={aiActive ? "AI Active" : "AI Standby"} state={aiActive ? "good" : "neutral"} />
            <Pill
              label={automationMode === "auto" ? "Auto execute" : "Manual approval"}
              state={automationMode === "auto" ? "active" : "neutral"}
            />
            <Pill
              label={system?.fault ? "Fault" : system ? "Healthy" : "Loading"}
              state={systemHealthState}
            />
          </div>
        </header>

        <nav className="mb-6 grid gap-3 md:grid-cols-2 lg:grid-cols-6">
          {[
            ["/decision-center", "Decision Center"],
            ["/operations", "Operations"],
            ["/vision", "Vision"],
            ["/weather", "Weather"],
            ["/sprinkler", "Irrigation"],
            ["/thermostat", "Thermostat"],
          ].map(([href, label]) => (
            <Link
              key={href}
              href={href}
              className="inline-flex h-11 items-center justify-center rounded-xl border border-neutral-800 bg-neutral-950 px-4 text-sm font-semibold text-neutral-200 transition hover:bg-neutral-900 hover:text-white"
            >
              {label}
            </Link>
          ))}
        </nav>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
          <MetricCard
            label="Supervisor"
            value={system ? "Online" : "Waiting"}
            state={system ? "good" : "neutral"}
            sub={updatedLabel}
          />
          <MetricCard
            label="HVAC"
            value={hvacStatus}
            state={hvacState}
            sub={hvacStage}
          />
          <MetricCard
            label="Irrigation"
            value={sprinklerStatus}
            state={sprinklerState}
            sub={sprinklerRunning ? `Zone ${displayValue(activeZone)}` : rainInhibit ? "Rain inhibit active" : "No active zone"}
          />
          <MetricCard
            label="Weather"
            value={weatherStatus}
            state={weatherState}
            sub={`${formatTemp(weather?.temp)} · ${formatPercent(rainChance)} rain`}
          />
          <MetricCard
            label="Vision"
            value={visionStatus}
            state={visionState}
            sub={vision?.resolution || "Environmental camera"}
          />
          <MetricCard
            label="Faults"
            value={system?.fault ? "Fault" : "None"}
            state={system?.fault ? "bad" : system ? "good" : "neutral"}
            sub="System safety state"
          />
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-[1.05fr_0.95fr]">
          <Section
            title="Current Recommendation"
            subtitle="Operator-facing supervisory decision based on live state"
            right={<Pill label={recommendation.title} state={recommendation.state} />}
          >
            <div className="rounded-2xl border border-neutral-800 bg-neutral-900 p-5">
              <h2 className={cx("text-3xl font-semibold", textStateClass(recommendation.state))}>
                {recommendation.title}
              </h2>
              <p className="mt-3 text-sm leading-6 text-neutral-300">
                {recommendation.detail}
              </p>

              {decision?.reason ? (
                <div className="mt-4 rounded-xl border border-neutral-800 bg-black p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-neutral-500">
                    Decision Trace
                  </p>
                  <p className="mt-2 text-sm leading-6 text-neutral-300">
                    {decision.reason}
                  </p>
                </div>
              ) : null}
            </div>

            <div className="mt-5 flex flex-wrap gap-3">
              {recommendation.canApply ? (
                <Button
                  onClick={applyRecommendation}
                  disabled={controlLoading}
                  variant={
                    recommendation.action === "stop_sprinkler"
                      ? "danger"
                      : "success"
                  }
                >
                  {controlLoading ? "Applying..." : recommendation.action === "delay_irrigation" ? "Skip next irrigation" : recommendation.applyLabel}
                </Button>
              ) : null}

              <Link
                href="/decision-center"
                className="inline-flex items-center justify-center rounded-xl border border-neutral-700 bg-neutral-900 px-4 py-3 text-sm font-semibold text-neutral-100 transition hover:bg-neutral-800"
              >
                Open Decision Center
              </Link>

              <Button
                onClick={() =>
                  askSuggestion(
                    "Explain the current home automation recommendation using only the live system state.",
                  )
                }
                variant="secondary"
              >
                Explain
              </Button>
            </div>
          </Section>

          <Section
            title="Execution Control"
            subtitle="Hardware actions require operator approval"
            right={<Pill label={automationMode === "auto" ? "Auto" : "Manual"} state={automationMode === "auto" ? "active" : "neutral"} />}
          >
            <div className="grid grid-cols-2 gap-3">
              <Button
                onClick={() => setAutomationModeAction("manual")}
                disabled={controlLoading}
                variant={automationMode === "manual" ? "primary" : "secondary"}
              >
                Manual
              </Button>
              <Button
                onClick={() => setAutomationModeAction("auto")}
                disabled={controlLoading}
                variant={automationMode === "auto" ? "primary" : "secondary"}
              >
                Auto
              </Button>
            </div>

            <div className="mt-5 grid grid-cols-2 gap-3">
              <Field label="Decision" value={formatMode(decision?.action || "observe")} state="active" />
              <Field label="Source" value={decision?.source || "rules"} />
              <Field label="Requires Execution" value={decision?.requires_execution} />
              <Field
                label="Safety"
                value={environment?.safety?.reason || "Monitoring system"}
                state={environment?.safety?.requires_user_approval ? "warn" : "good"}
              />
            </div>

            <details className="mt-5 rounded-2xl border border-neutral-800 bg-black p-4">
              <summary className="cursor-pointer text-sm font-semibold text-neutral-300">
                Last command result
              </summary>
              <pre className="mt-4 max-h-60 overflow-auto text-xs leading-5 text-neutral-300">
                {formatJson(controlResult || { message: "No command sent yet." })}
              </pre>
            </details>
          </Section>
        </div>

        <section className="mt-6">
          <div className="mb-4 flex items-end justify-between gap-4">
            <div>
              <h2 className="text-2xl font-semibold text-white">
                Subsystem Overview
              </h2>
              <p className="mt-1 text-sm text-neutral-500">
                Each card links to a dedicated engineering detail page.
              </p>
            </div>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <SubsystemCard
              icon="🤖"
              title="Decision Center"
              subtitle="Recommendations, safety gating, automation mode, and execution trace"
              href="/decision-center"
              status={aiActive ? "AI Active" : "Standby"}
              statusState={aiActive ? "good" : "neutral"}
              primary={recommendation.title}
              fields={[
                {
                  label: "Action",
                  value: formatMode(decision?.action || recommendation.action),
                  state: "active",
                },
                {
                  label: "Automation",
                  value: automationMode === "auto" ? "Monitor Only" : "Manual Approval",
                  state: automationMode === "auto" ? "active" : "neutral",
                },
                {
                  label: "Approval",
                  value: environment?.safety?.requires_user_approval ? "Required" : "Not required",
                  state: environment?.safety?.requires_user_approval ? "warn" : "good",
                },
                {
                  label: "Faults",
                  value: system?.fault ? "Present" : "None",
                  state: system?.fault ? "bad" : "good",
                },
              ]}
            />

            <SubsystemCard
              icon="🛰️"
              title="Operations Console"
              subtitle="System events, active faults, node health, automation policies, and evidence history"
              href="/operations"
              status="Live"
              statusState="active"
              primary="Event Memory"
              fields={[
                {
                  label: "Timeline",
                  value: "Enabled",
                  state: "good",
                },
                {
                  label: "Faults",
                  value: "Tracked",
                  state: "active",
                },
                {
                  label: "Policies",
                  value: "Visible",
                  state: "active",
                },
                {
                  label: "Evidence",
                  value: "Logged",
                  state: "good",
                },
              ]}
            />

            <SubsystemCard
              icon="📷"
              title="Vision"
              subtitle="Camera stream, surface condition, visual rain evidence, and environmental context"
              href="/vision"
              status={visionStatus}
              statusState={visionState}
              primary={vision?.camera_online ? "Camera Online" : "Camera Offline"}
              fields={[
                {
                  label: "Camera",
                  value: vision?.camera_online ? "Online" : "Offline",
                  state: vision?.camera_online ? "good" : "bad",
                },
                {
                  label: "FPS",
                  value: displayValue(vision?.fps),
                  state: Number(vision?.fps ?? 0) > 0 ? "active" : "neutral",
                },
                {
                  label: "Surface Moisture",
                  value: (environment?.inputs?.visual_evidence_detected || environment?.inputs?.camera_rain_detected || environment?.inputs?.visual_wet_surface_evidence)
                    ? "Wet surface"
                    : "Not confirmed",
                  state: (environment?.inputs?.visual_evidence_detected || environment?.inputs?.camera_rain_detected || environment?.inputs?.visual_wet_surface_evidence) ? "warn" : "neutral",
                },
                {
                  label: "Confidence",
                  value: formatMode(environment?.confidence),
                  state: environment?.confidence === "high" ? "good" : "neutral",
                },
              ]}
            />

            <SubsystemCard
              icon="🌦️"
              title="Weather"
              subtitle="Outdoor conditions, forecast context, rain probability, and irrigation impact"
              href="/weather"
              status={weatherStatus}
              statusState={weatherState}
              primary={formatTemp(weather?.temp)}
              fields={[
                {
                  label: "Rain",
                  value: formatPercent(rainChance),
                  state: rainChance >= 70 ? "warn" : "neutral",
                },
                {
                  label: "Feels",
                  value: formatTemp(weather?.feels_like),
                },
                {
                  label: "Humidity",
                  value: formatPercent(weather?.humidity, 1),
                },
                {
                  label: "Wind",
                  value: Number.isFinite(Number(weather?.wind_mph))
                    ? `${Number(weather.wind_mph).toFixed(1)} mph`
                    : "—",
                },
              ]}
            />

            <SubsystemCard
              icon="💧"
              title="Standalone Irrigation"
              subtitle="ESP32 standalone irrigation controller, local schedule, rain switch, and hardware inhibit state"
              href="/sprinkler"
              status={sprinklerStatus}
              statusState={sprinklerState}
              primary={
                sprinklerRunning
                  ? `Zone ${displayValue(activeZone)}`
                  : rainInhibit
                    ? "Rain Inhibit"
                    : "Idle"
              }
              fields={[
                {
                  label: "Online",
                  value: sprinklerOnline ? "Yes" : "No",
                  state: sprinklerOnline ? "good" : "bad",
                },
                {
                  label: "Rain Sensor",
                  value: rainWet ? "Wet" : "Dry",
                  state: rainWet ? "warn" : "good",
                },
                {
                  label: "Schedule",
                  value: displayValue(sprinkler?.schedule_status || nextRun),
                  state: rainInhibit ? "warn" : "neutral",
                },
                {
                  label: "Controller",
                  value: sprinkler?.display_name || "Standalone ESP32",
                  state: "good",
                },
              ]}
            />

            <SubsystemCard
              icon="🌡️"
              title="Thermostat"
              subtitle="HVAC equipment state, indoor temperature, humidity, setpoint, and fan"
              href="/thermostat"
              status={hvacStatus}
              statusState={hvacState}
              primary={formatTemp(thermostat?.temp ?? thermostat?.temperature)}
              fields={[
                {
                  label: "Target",
                  value: formatTemp(thermostatRaw?.setpoint ?? thermostat?.setpoint),
                },
                {
                  label: "Humidity",
                  value: formatPercent(thermostat?.humidity, 1),
                },
                {
                  label: "Fan",
                  value: hvacFan ? "Running" : "Idle",
                  state: hvacFan ? "active" : "neutral",
                },
                {
                  label: "Stage",
                  value: hvacStage,
                  state: hvacState,
                },
              ]}
            />
          </div>
        </section>

        <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_420px]">
          <Section
            title="Assistant"
            subtitle="Ask Orion about live system state"
            right={<Button onClick={newChat} variant="secondary">New chat</Button>}
          >
            <div className="max-h-[520px] min-h-[360px] space-y-5 overflow-y-auto rounded-2xl border border-neutral-800 bg-black p-5">
              {messages.length === 0 ? (
                <EmptyChatState onSuggestion={askSuggestion} />
              ) : null}

              {messages.map((message, index) => (
                <div
                  key={`${message.role}-${index}`}
                  className={cx(
                    "flex",
                    message.role === "user" ? "justify-end" : "justify-start",
                  )}
                >
                  <div
                    className={cx(
                      "max-w-[min(760px,90%)] rounded-2xl px-4 py-3 text-sm leading-7 shadow-sm",
                      message.role === "user"
                        ? "bg-blue-600 text-white"
                        : "border border-neutral-800 bg-neutral-950 text-neutral-100",
                    )}
                  >
                    <div className="whitespace-pre-wrap break-words">
                      {message.content}
                    </div>
                  </div>
                </div>
              ))}

              {loading ? (
                <div className="flex justify-start">
                  <div className="rounded-2xl border border-neutral-800 bg-neutral-950 px-4 py-3 text-sm text-neutral-400">
                    Thinking…
                  </div>
                </div>
              ) : null}

              <div ref={messageEndRef} />
            </div>

            <div className="mt-4 flex gap-2 rounded-2xl border border-neutral-800 bg-black p-2">
              <input
                className="min-h-11 flex-1 rounded-xl bg-transparent px-3 text-sm text-white outline-none placeholder:text-neutral-500"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder="Ask Orion…"
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    if (loading) {
                      stopGeneration();
                    } else {
                      sendMessage();
                    }
                  }
                }}
              />

              <Button
                onClick={loading ? stopGeneration : sendMessage}
                disabled={!loading && !input.trim()}
                variant={loading ? "danger" : "primary"}
                className="min-w-[84px]"
              >
                {loading ? "Stop" : "Send"}
              </Button>
            </div>
          </Section>

          <Section title="Saved Chats" subtitle="Continue a conversation">
            <div className="max-h-[560px] space-y-3 overflow-y-auto">
              {sessions.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-neutral-700 bg-black p-5 text-sm text-neutral-400">
                  No saved chats yet.
                </div>
              ) : null}

              {sessions.map((session) => (
                <div
                  key={session.id}
                  className={cx(
                    "rounded-2xl border p-4 transition",
                    sessionId === session.id
                      ? "border-blue-400/50 bg-blue-500/10"
                      : "border-neutral-800 bg-black hover:bg-neutral-950",
                  )}
                >
                  <button
                    type="button"
                    onClick={() => loadChat(session.id)}
                    className="block w-full truncate text-left text-sm font-semibold text-white"
                    title={session.title}
                  >
                    {formatSessionTitle(session)}
                  </button>

                  <div className="mt-3 flex gap-3 text-xs">
                    <button
                      type="button"
                      onClick={() => renameChat(session.id)}
                      className="text-neutral-400 transition hover:text-white"
                    >
                      Rename
                    </button>

                    <button
                      type="button"
                      onClick={() => deleteChat(session.id)}
                      className="text-red-300 transition hover:text-red-200"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </Section>
        </div>

        <section className="mt-6 rounded-2xl border border-neutral-800 bg-neutral-950 p-5 shadow-lg">
          <details>
            <summary className="cursor-pointer text-sm font-semibold text-neutral-300">
              Raw system snapshot
            </summary>
            <pre className="mt-4 max-h-96 overflow-auto rounded-xl bg-black p-4 text-xs leading-5 text-neutral-300">
              {formatJson({
                system_health: {
                  ai_status: system?.ai_status,
                  automation_mode: system?.automation_mode,
                  fault: system?.fault,
                  last_update: system?.last_update,
                },
                last_decision: system?.last_decision,
                control_result: controlResult,
              })}
            </pre>
          </details>
        </section>
      </div>
    </main>
  );
}
