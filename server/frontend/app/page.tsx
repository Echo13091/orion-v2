"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

type Message = {
  role: "user" | "assistant";
  content: string;
};

type Session = {
  id: string;
  title: string;
};

type LastDecision = {
  action: string;
  reason?: string;
  params?: Record<string, unknown>;
  source?: string;
  requires_execution?: boolean;
  result?: unknown;
  time?: number;
};

type SprinklerState = {
  online?: boolean;
  source?: string | null;
  running?: boolean;
  zone?: number | string | null;
  mode?: string | null;
  next_run?: unknown;
  error?: string;
  raw?: unknown;
};

type ThermostatState = {
  online?: boolean;
  source?: string | null;
  temp?: number | null;
  humidity?: number | null;
  mode?: string | null;
  cooling?: boolean;
  heating?: boolean;
  fan?: boolean;
  error?: string;
  raw?: unknown;
};

type WeatherState = {
  online?: boolean;
  location?: string | null;
  temp?: number | null;
  feels_like?: number | null;
  humidity?: number | null;
  condition?: string | null;
  rain_chance?: number | null;
  wind_mph?: number | null;
  precip_in?: number | null;
  source?: string | null;
  updated_at?: number | null;
  cache_age_seconds?: number | null;
  forecast_today?: {
    date?: string | null;
    max_temp?: number | null;
    min_temp?: number | null;
    sunrise?: string | null;
    sunset?: string | null;
  } | null;
  error?: string | null;
};


type IrrigationSchedule = {
  enabled?: boolean;
  days?: string[];
  start_time?: string | null;
  duration_minutes?: number | null;
  zones?: number[];
  skip_next_run?: boolean;
  skip_reason?: string | null;
  updated_at?: number | null;
  controller?: string;
  hardware_sync_required?: boolean;
  skip_if_rain_likely?: boolean;
  last_run_key?: string | null;
  active_run?: unknown;
  last_scheduler_event?: unknown;
  hardware_synced?: boolean;
  hardware_result?: unknown;
};

type SystemState = {
  mode: string;
  automation_mode?: AutomationMode;
  fault: string | null;
  cpu: number;
  memory: number;
  gpu?: number;
  ai_status: string;
  last_update: number;
  last_decision: LastDecision | null;
  last_execution?: unknown;
  manual_override_until?: number | null;
  manual_override_reason?: string | null;
  fault_status?: Record<string, unknown>;
  irrigation_schedule?: IrrigationSchedule;
  sprinkler?: SprinklerState;
  thermostat?: ThermostatState;
  weather?: WeatherState;
};

type StatusState = "good" | "bad" | "warn" | "neutral" | "active";

type AutomationMode = "manual" | "auto";

type RecommendationAction =
  | "observe"
  | "nothing"
  | "delay_irrigation"
  | "stop_sprinkler"
  | "set_thermostat";

type OrionRecommendation = {
  title: string;
  detail: string;
  state: StatusState;
  action: RecommendationAction;
  params?: Record<string, unknown>;
  canApply: boolean;
  applyLabel?: string;
};

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:5001";

const SYSTEM_POLL_MS = Number(process.env.NEXT_PUBLIC_SYSTEM_POLL_MS ?? "3000");

function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
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


function formatMetricValue(value: unknown): ReactNode {
  if (value === null || value === undefined || value === "") {
    return "—";
  }

  if (
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean"
  ) {
    return String(value);
  }

  if (Array.isArray(value)) {
    return value.length ? `${value.length} item(s)` : "—";
  }

  if (typeof value === "object") {
    const data = value as Record<string, unknown>;

    if ("day" in data && "time" in data && "zone" in data) {
      return `${String(data.day)} ${String(data.time)} · Zone ${String(data.zone)}`;
    }

    return JSON.stringify(data);
  }

  return String(value);
}

function percent(value?: number) {
  return Number.isFinite(value) ? `${Number(value).toFixed(1)}%` : "--";
}

function yesNo(value?: boolean) {
  if (value === undefined) return "--";
  return value ? "Yes" : "No";
}

function onOff(value?: boolean) {
  if (value === undefined) return "--";
  return value ? "On" : "Off";
}

function onlineState(value?: boolean): "good" | "bad" | "neutral" {
  if (value === undefined) return "neutral";
  return value ? "good" : "bad";
}

function activeState(value?: boolean): "good" | "neutral" {
  return value ? "good" : "neutral";
}

function formatTemp(value?: number | null) {
  return Number.isFinite(value) ? `${Number(value).toFixed(1)}°F` : "--";
}

function formatHumidity(value?: number | null) {
  return Number.isFinite(value) ? `${Number(value).toFixed(1)}%` : "--";
}

function formatRain(value?: number | null) {
  return Number.isFinite(value) ? `${Number(value).toFixed(0)}%` : "--";
}

function formatWind(value?: number | null) {
  return Number.isFinite(value) ? `${Number(value).toFixed(1)} mph` : "--";
}

function formatPrecip(value?: number | null) {
  return Number.isFinite(value) ? `${Number(value).toFixed(2)} in` : "--";
}

function formatScheduleSummary(schedule?: IrrigationSchedule | null) {
  if (!schedule) return "No schedule";
  if (schedule.enabled === false) return "Schedule off";

  const time = schedule.start_time || "--";
  const minutes = Number.isFinite(schedule.duration_minutes)
    ? `${Number(schedule.duration_minutes)} min`
    : "--";
  const zones = Array.isArray(schedule.zones) && schedule.zones.length > 0
    ? `Z${schedule.zones.join(",")}`
    : "All zones";

  if (schedule.skip_next_run) return `Skip next · ${time}`;
  return `${time} · ${minutes} · ${zones}`;
}

function formatScheduleController(schedule?: IrrigationSchedule | null) {
  if (!schedule) return "--";
  if (schedule.controller === "sprinkler" || schedule.hardware_synced) return "Sprinkler controlled";
  if (schedule.controller === "orion" || schedule.hardware_sync_required === false) return "Orion controlled";
  return "Hardware controlled";
}

function formatMode(value?: string | null) {
  if (!value) return "--";

  return value
    .replace(/[_-]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatAutomationState(value?: string | null) {
  const formatted = formatMode(value);

  if (formatted === "Idle" || formatted === "Monitoring") return "Autonomous Monitoring";
  if (formatted === "--") return "Waiting";

  return formatted;
}

function formatZone(value?: number | string | null) {
  if (value === null || value === undefined) return "No active zone";

  const text = String(value).trim();
  if (!text || text === "--" || text.toLowerCase() === "none") {
    return "No active zone";
  }

  return text.toLowerCase().startsWith("zone") ? text : `Zone ${text}`;
}

function formatLastUpdated(value?: number) {
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

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function optionalBool(value: unknown): boolean | undefined {
  return typeof value === "boolean" ? value : undefined;
}

function optionalString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

function getExecutionSummary(system?: SystemState | null): {
  status: string;
  action: string;
  safety: string;
  state: "good" | "bad" | "neutral" | "warn" | "active";
} {
  const decision = system?.last_decision;
  const result = isRecord(decision?.result) ? decision.result : null;
  const nestedResult = isRecord(result?.result) ? result.result : null;

  const ok = optionalBool(result?.ok) ?? optionalBool(nestedResult?.ok);
  const blocked = optionalBool(result?.blocked) ?? false;
  const executed = optionalBool(result?.executed) ?? false;

  const action = formatMode(
    optionalString(result?.action) || decision?.action || "observe",
  );

  const status = optionalString(result?.status);
  const safety =
    optionalString(result?.safety_reason) ||
    optionalString(result?.message) ||
    optionalString(result?.reason) ||
    optionalString(nestedResult?.message) ||
    optionalString(nestedResult?.action) ||
    (decision?.requires_execution ? "Awaiting safe execution" : "No hardware action needed");

  if (status === "already_applied") {
    return {
      status: "Already applied",
      action,
      safety,
      state: "good",
    };
  }

  if (status === "holding") {
    return {
      status: "Standing by",
      action,
      safety: safety || "No repeat hardware action needed.",
      state: "neutral",
    };
  }

  if (blocked) {
    return {
      status: "Blocked",
      action,
      safety,
      state: "warn",
    };
  }

  if (executed && ok !== false) {
    return {
      status: "Executed",
      action,
      safety,
      state: "good",
    };
  }

  if (ok === false) {
    return {
      status: "Failed",
      action,
      safety,
      state: "bad",
    };
  }

  if (decision?.requires_execution) {
    return {
      status: "Waiting",
      action,
      safety,
      state: "neutral",
    };
  }

  return {
    status: "Autonomous Monitoring",
    action,
    safety,
    state: "active",
  };
}

function getManualOverrideSummary(system?: SystemState | null) {
  const until = Number(system?.manual_override_until ?? 0);
  const remainingMs = until > 1_000_000_000_000 ? until - Date.now() : until * 1000 - Date.now();
  const remaining = Math.max(0, Math.ceil(remainingMs / 1000));

  if (!until || remaining <= 0) {
    return { active: false, label: "No manual lock", detail: "Autonomy is allowed when safety rules permit." };
  }

  const minutes = Math.floor(remaining / 60);
  const seconds = remaining % 60;
  const label = minutes > 0 ? `${minutes}m ${seconds}s left` : `${seconds}s left`;

  return {
    active: true,
    label,
    detail: system?.manual_override_reason || "Manual user control active",
  };
}

type TimelineStatus = "completed" | "active" | "upcoming";

type TimelineEntry = {
  label: string;
  zone?: number | null;
  time: string;
  endTime?: string;
  duration: string;
  durationSeconds: number;
  active?: boolean;
  status: TimelineStatus;
  progress: number;
};

type CycleSummary = {
  running: boolean;
  activeIndex: number;
  activeLabel: string;
  activeEta: string;
  activeProgress: number | null;
  cycleEta: string;
  remainingLabel: string;
};

function coerceNumber(value: unknown, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function parseDurationSeconds(value: unknown) {
  const minutes = coerceNumber(value, 0);
  return Math.max(0, Math.round(minutes * 60));
}

function formatDurationSeconds(value: number) {
  const seconds = Math.max(0, Math.round(value));
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;

  if (mins <= 0) return `${secs}s`;
  if (secs === 0) return `${mins}m`;
  return `${mins}m ${String(secs).padStart(2, "0")}s`;
}

function parseClockToday(value?: string | null) {
  if (!value) return null;

  const parts = String(value).trim().split(":").map((part) => Number(part));
  if (parts.length < 2 || parts.some((part) => !Number.isFinite(part))) return null;

  const [hours, minutes, seconds = 0] = parts;
  const date = new Date();
  date.setHours(hours, minutes, seconds, 0);
  return date;
}

function formatClock(date?: Date | null) {
  if (!date || Number.isNaN(date.getTime())) return "--";
  return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function addSeconds(date: Date | null, seconds: number) {
  if (!date) return null;
  return new Date(date.getTime() + Math.max(0, seconds) * 1000);
}

function timelineZoneLabel(value: unknown) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "Zone --";

  // Sprinkler controller now returns display zone numbers 1-8.
  return `Zone ${n}`;
}

function timelineZoneNumber(value: unknown) {
  const n = Number(value);
  if (!Number.isFinite(n)) return null;

  // Sprinkler controller now returns display zone numbers 1-8.
  return n;
}

function getIrrigationTimeline(system?: SystemState | null): TimelineEntry[] {
  const raw = system?.sprinkler?.raw;
  const currentZone = coerceNumber(system?.sprinkler?.zone, -1);
  const running = Boolean(system?.sprinkler?.running);
  const entries: TimelineEntry[] = [];

  if (isRecord(raw) && Array.isArray(raw.computed_schedule)) {
    for (const item of raw.computed_schedule.slice(0, 8)) {
      if (!isRecord(item)) continue;

      const zone = timelineZoneNumber(item.zone);
      const durationSeconds = parseDurationSeconds(item.duration);
      const start = parseClockToday(String(item.time || ""));
      const isActive = running && zone !== null && zone === currentZone;

      entries.push({
        label: timelineZoneLabel(item.zone),
        zone,
        time: String(item.time || "--"),
        endTime: formatClock(addSeconds(start, durationSeconds)),
        duration: `${item.duration ?? "--"} min`,
        durationSeconds,
        active: isActive,
        status: isActive ? "active" : "upcoming",
        progress: 0,
      });
    }
  }

  if (entries.length === 0) {
    const schedule = system?.irrigation_schedule;
    const zones = Array.isArray(schedule?.zones) ? schedule?.zones || [] : [];
    const time = schedule?.start_time || "--";
    const durationMinutes = Number.isFinite(schedule?.duration_minutes)
      ? Number(schedule?.duration_minutes)
      : 0;
    const durationSeconds = parseDurationSeconds(durationMinutes);
    const start = parseClockToday(time);

    for (const zone of zones.slice(0, 8)) {
      const zoneNumber = Number(zone);
      const isActive = running && zoneNumber === currentZone;
      entries.push({
        label: `Zone ${zone}`,
        zone: zoneNumber,
        time,
        endTime: formatClock(addSeconds(start, durationSeconds)),
        duration: durationMinutes ? `${durationMinutes} min` : "--",
        durationSeconds,
        active: isActive,
        status: isActive ? "active" : "upcoming",
        progress: 0,
      });
    }
  }

  const activeIndex = entries.findIndex((entry) => entry.active);
  const rawRemaining = isRecord(raw) ? raw.remaining : undefined;
  const remainingSeconds = coerceNumber(rawRemaining, 0);

  return entries.map((entry, index) => {
    let status: TimelineStatus = "upcoming";
    let progress = 0;

    if (activeIndex >= 0) {
      if (index < activeIndex) {
        status = "completed";
        progress = 100;
      } else if (index === activeIndex) {
        status = "active";
        const duration = Math.max(1, entry.durationSeconds);
        progress = Math.max(0, Math.min(100, ((duration - remainingSeconds) / duration) * 100));
      }
    }

    return {
      ...entry,
      active: status === "active",
      status,
      progress,
    };
  });
}

function getIrrigationCycleSummary(
  system?: SystemState | null,
  entries: TimelineEntry[] = [],
): CycleSummary {
  const running = Boolean(system?.sprinkler?.running);
  const raw = system?.sprinkler?.raw;
  const activeIndex = entries.findIndex((entry) => entry.active);
  const activeEntry = activeIndex >= 0 ? entries[activeIndex] : null;
  const remainingSeconds = isRecord(raw) ? coerceNumber(raw.remaining, 0) : 0;
  const progress = activeEntry?.progress ?? null;

  if (!running) {
    return {
      running: false,
      activeIndex: -1,
      activeLabel: "No active zone",
      activeEta: "No active run",
      activeProgress: null,
      cycleEta: "No active cycle",
      remainingLabel: "--",
    };
  }

  const futureEntries = activeIndex >= 0 ? entries.slice(activeIndex + 1) : [];
  const futureSeconds = futureEntries.reduce((total, entry) => total + entry.durationSeconds, 0);
  const transitionSeconds = futureEntries.length > 0 ? futureEntries.length * 6 : 0;
  const totalRemainingSeconds = Math.max(0, remainingSeconds + futureSeconds + transitionSeconds);
  const completeAt = new Date(Date.now() + totalRemainingSeconds * 1000);

  return {
    running: true,
    activeIndex,
    activeLabel: activeEntry?.label || formatZone(system?.sprinkler?.zone),
    activeEta: `${formatDurationSeconds(remainingSeconds)} left`,
    activeProgress: progress,
    cycleEta: `Ends ~${formatClock(completeAt)}`,
    remainingLabel: formatDurationSeconds(totalRemainingSeconds),
  };
}

function displaySessionTitle(session: Session) {
  const title = session.title?.trim() || "Untitled chat";

  if (/^\d+(\s*x\s*)?\d+$/.test(title)) {
    return `Conversation ${session.id.slice(0, 8)}`;
  }

  return title;
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

          if (typeof choice.text === "string") {
            return choice.text;
          }

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

function StatusDot({ state = "neutral" }: { state?: StatusState }) {
  return (
    <span
      className={cx(
        "h-2 w-2 shrink-0 rounded-full",
        state === "good" && "bg-emerald-300",
        state === "bad" && "bg-red-300",
        state === "warn" && "bg-amber-300",
        state === "active" && "bg-blue-300",
        state === "neutral" && "bg-slate-500",
      )}
    />
  );
}

function StatusPill({
  label,
  state = "neutral",
}: {
  label: string;
  state?: StatusState;
}) {
  return (
    <span
      className={cx(
        "inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold",
        state === "good" &&
          "border-emerald-400/20 bg-emerald-400/10 text-emerald-200",
        state === "bad" && "border-red-400/20 bg-red-400/10 text-red-200",
        state === "warn" && "border-amber-400/20 bg-amber-400/10 text-amber-200",
        state === "active" && "border-blue-400/20 bg-blue-400/10 text-blue-200",
        state === "neutral" &&
          "border-slate-700/70 bg-slate-800/60 text-slate-300",
      )}
    >
      <StatusDot state={state} />
      {label}
    </span>
  );
}

function Panel({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cx(
        "overflow-hidden rounded-2xl border border-slate-800/80 bg-slate-900/70 shadow-xl shadow-black/10 ring-1 ring-white/[0.03] backdrop-blur",
        className,
      )}
    >
      {children}
    </section>
  );
}

function PanelHeader({
  title,
  subtitle,
  right,
}: {
  title: string;
  subtitle?: string;
  right?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-slate-800/80 px-5 py-4">
      <div className="min-w-0">
        <h2 className="truncate text-sm font-semibold tracking-tight text-slate-100">
          {title}
        </h2>
        {subtitle && <p className="mt-1 text-xs text-slate-400">{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}

function MetricTile({
  label,
  value,
  state,
}: {
  label: string;
  value: ReactNode;
  state?: "good" | "bad" | "neutral" | "warn" | "active";
}) {
  return (
    <div className="min-w-0 rounded-xl border border-slate-800/70 bg-slate-950/35 p-3">
      <div className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
        {label}
      </div>
      <div
        className={cx(
          "mt-1 whitespace-normal break-words text-base font-semibold tracking-tight",
          state === "good" && "text-emerald-200",
          state === "bad" && "text-red-200",
          state === "warn" && "text-amber-200",
          state === "active" && "text-blue-200",
          (!state || state === "neutral") && "text-white",
        )}
      >
        {value}
      </div>
    </div>
  );
}

function CollapsibleCard({
  icon,
  title,
  subtitle,
  status,
  statusState,
  primaryLabel,
  primaryValue,
  metrics = [],
  metricsWide = false,
  children,
  defaultOpen = false,
  className,
}: {
  icon: string;
  title: string;
  subtitle?: string;
  status: string;
  statusState: StatusState;
  primaryLabel?: string;
  primaryValue: ReactNode;
  metrics?: Array<{
    label: string;
    value: ReactNode;
    state?: "good" | "bad" | "neutral" | "warn" | "active";
  }>;
  metricsWide?: boolean;
  children?: ReactNode;
  defaultOpen?: boolean;
  className?: string;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <details
      open={isOpen}
      onToggle={(event) => setIsOpen(event.currentTarget.open)}
      className={cx(
        "group overflow-hidden rounded-2xl border border-slate-800/80 bg-slate-900/70 shadow-xl shadow-black/10 ring-1 ring-white/[0.03] backdrop-blur",
        className,
      )}
    >
      <summary className="cursor-pointer list-none p-5 outline-none transition hover:bg-slate-800/25 [&::-webkit-details-marker]:hidden">
        <div className="flex items-start justify-between gap-4">
          <div className="flex min-w-0 items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-950/55 text-lg ring-1 ring-slate-700/60">
              {icon}
            </div>
            <div className="min-w-0">
              <h2 className="truncate text-base font-semibold tracking-tight text-white">
                {title}
              </h2>
              {subtitle && (
                <p className="mt-1 truncate text-xs text-slate-400">{subtitle}</p>
              )}
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-3">
            <StatusPill label={status} state={statusState} />
            <span className="text-sm text-slate-500 transition group-open:rotate-180">
              ▾
            </span>
          </div>
        </div>

        <div className="mt-5 flex items-end justify-between gap-4">
          <div className="min-w-0">
            {primaryLabel && (
              <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                {primaryLabel}
              </div>
            )}
            <div className="mt-1 truncate text-3xl font-semibold tracking-tight text-white">
              {primaryValue}
            </div>
          </div>
        </div>

        {metrics.length > 0 && (
          <div
            className={cx(
              "mt-4 grid grid-cols-2 gap-3",
              metricsWide && "lg:grid-cols-4",
            )}
          >
            {metrics.map((metric) => (
              <div key={metric.label}>
                <MetricTile
                  label={metric.label}
                  value={formatMetricValue(metric.value)}
                  state={metric.state}
                />
              </div>
            ))}
          </div>
        )}
      </summary>

      {children && (
        <div className="border-t border-slate-800/80 p-5">{children}</div>
      )}
    </details>
  );
}

function Field({
  label,
  value,
  state,
}: {
  label: string;
  value: unknown;
  state?: "good" | "bad" | "neutral" | "warn" | "active";
}) {
  return (
    <div className="min-w-0 rounded-xl border border-slate-800/70 bg-slate-950/35 p-3">
      <div className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
        {label}
      </div>
      <div
        className={cx(
          "mt-1 whitespace-normal break-words text-base font-semibold tracking-tight",
          state === "good" && "text-emerald-200",
          state === "bad" && "text-red-200",
          state === "warn" && "text-amber-200",
          state === "active" && "text-blue-200",
          (!state || state === "neutral") && "text-white",
        )}
      >
        {formatMetricValue(value)}
      </div>
    </div>
  );
}

function ProgressStat({
  label,
  value,
  state = "neutral",
}: {
  label: string;
  value?: number;
  state?: StatusState;
}) {
  const safeValue = Number.isFinite(value)
    ? Math.max(0, Math.min(100, Number(value)))
    : 0;

  return (
    <div className="rounded-xl border border-slate-800/70 bg-slate-950/35 p-3">
      <div className="mb-2 flex items-center justify-between gap-3">
        <span className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
          {label}
        </span>
        <span
          className={cx(
            "text-sm font-semibold",
            state === "good" && "text-emerald-200",
            state === "bad" && "text-red-200",
            state === "warn" && "text-amber-200",
            state === "active" && "text-blue-200",
            state === "neutral" && "text-white",
          )}
        >
          {percent(value)}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-800/90">
        <div
          className={cx(
            "h-full rounded-full transition-all duration-500",
            state === "bad" && "bg-red-400",
            state === "warn" && "bg-amber-400",
            state === "good" && "bg-emerald-400",
            state === "active" && "bg-blue-400",
            state === "neutral" && "bg-blue-400",
          )}
          style={{ width: `${safeValue}%` }}
        />
      </div>
    </div>
  );
}

function TextInput({
  value,
  onChange,
  placeholder,
  onEnter,
  type = "text",
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  onEnter?: () => void;
  type?: string;
}) {
  return (
    <input
      type={type}
      className="h-10 w-full rounded-xl border border-slate-700/80 bg-slate-950/70 px-3.5 text-sm text-white outline-none transition placeholder:text-slate-500 hover:border-slate-600 focus:border-blue-400 focus:ring-4 focus:ring-blue-500/10"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      onKeyDown={(e) => {
        if (e.key === "Enter") onEnter?.();
      }}
    />
  );
}

function SelectInput({
  value,
  onChange,
  children,
}: {
  value: string;
  onChange: (value: string) => void;
  children: ReactNode;
}) {
  return (
    <select
      className="h-10 w-full rounded-xl border border-slate-700/80 bg-slate-950/70 px-3.5 text-sm text-white outline-none transition hover:border-slate-600 focus:border-blue-400 focus:ring-4 focus:ring-blue-500/10"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      {children}
    </select>
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
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cx(
        "inline-flex h-10 items-center justify-center rounded-xl px-4 text-sm font-semibold transition focus:outline-none focus:ring-4 disabled:cursor-not-allowed disabled:opacity-50",
        variant === "primary" &&
          "bg-blue-600 text-white shadow-lg shadow-blue-950/25 hover:bg-blue-500 focus:ring-blue-500/20",
        variant === "success" &&
          "bg-emerald-600 text-white shadow-lg shadow-emerald-950/20 hover:bg-emerald-500 focus:ring-emerald-500/20",
        variant === "danger" &&
          "bg-red-600 text-white shadow-lg shadow-red-950/20 hover:bg-red-500 focus:ring-red-500/20",
        variant === "secondary" &&
          "border border-slate-700/80 bg-slate-800/80 text-slate-100 hover:bg-slate-700 focus:ring-slate-500/20",
        variant === "ghost" &&
          "text-slate-300 hover:bg-slate-800/80 focus:ring-slate-500/20",
        className,
      )}
    >
      {children}
    </button>
  );
}

function Label({ children }: { children: ReactNode }) {
  return (
    <label className="mb-1.5 block text-xs font-medium text-slate-400">
      {children}
    </label>
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
    <div className="flex h-full min-h-[220px] items-center justify-center p-4">
      <div className="max-w-md rounded-2xl border border-slate-800/80 bg-slate-950/35 p-6 text-center shadow-2xl shadow-black/10">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-blue-600/15 text-2xl ring-1 ring-blue-400/20">
          🤖
        </div>
        <h3 className="mt-4 text-lg font-semibold tracking-tight text-white">
          Orion is monitoring your system
        </h3>
        <p className="mt-2 text-sm leading-6 text-slate-400">
          Ask about the live home state, inspect a device, or let Orion explain the current recommendation.
        </p>

        <div className="mt-4 flex flex-wrap justify-center gap-2">
          {suggestions.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => onSuggestion(suggestion)}
              className="rounded-full border border-slate-700/80 bg-slate-900/80 px-3 py-1.5 text-xs font-medium text-slate-300 transition hover:border-slate-600 hover:bg-slate-800 hover:text-white"
            >
              {suggestion}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(false);
  const [abortController, setAbortController] =
    useState<AbortController | null>(null);

  const [system, setSystem] = useState<SystemState | null>(null);

  const [controlLoading, setControlLoading] = useState(false);
  const [controlResult, setControlResult] = useState<unknown>(null);

  const [sprinklerZone, setSprinklerZone] = useState("1");
  const [sprinklerMinutes, setSprinklerMinutes] = useState("1");

  const [thermostatSetpoint, setThermostatSetpoint] = useState("72");
  const [thermostatMode, setThermostatMode] = useState("auto");
  const [fanMode, setFanMode] = useState("auto");

  const [automationMode, setAutomationMode] = useState<AutomationMode>("manual");
  const [autoExecutionLoading, setAutoExecutionLoading] = useState(false);

  const messageEndRef = useRef<HTMLDivElement | null>(null);

  const decisionResultText = useMemo(() => {
    return formatJson(system?.last_decision?.result, "No recent result");
  }, [system?.last_decision?.result]);

  const controlResultText = useMemo(() => {
    return formatJson(controlResult, "No command sent yet");
  }, [controlResult]);

  const executionSummary = useMemo(() => {
    return getExecutionSummary(system);
  }, [system]);

  const manualOverride = useMemo(() => {
    return getManualOverrideSummary(system);
  }, [system]);

  const irrigationTimeline = useMemo(() => {
    return getIrrigationTimeline(system);
  }, [system]);

  const cycleSummary = useMemo(() => {
    return getIrrigationCycleSummary(system, irrigationTimeline);
  }, [system, irrigationTimeline]);

  const lastUpdatedLabel = useMemo(() => {
    return formatLastUpdated(system?.last_update);
  }, [system?.last_update]);

  const weatherUpdatedLabel = useMemo(() => {
    return formatLastUpdated(system?.weather?.updated_at ?? undefined);
  }, [system?.weather?.updated_at]);

  const aiActive = system?.ai_status?.toLowerCase() === "active";

  const sprinklerStatus = useMemo(() => {
    if (!system?.sprinkler) return "Unknown";
    if (system.sprinkler.online === false) return "Offline";
    if (system.sprinkler.running) return "Running";
    return "Online";
  }, [system?.sprinkler]);

  const thermostatStatus = useMemo(() => {
    if (!system?.thermostat) return "Unknown";
    if (system.thermostat.online === false) return "Offline";
    if (system.thermostat.cooling) return "Cooling";
    if (system.thermostat.heating) return "Heating";
    if (system.thermostat.fan) return "Fan";
    return "Online";
  }, [system?.thermostat]);

  const weatherStatus = useMemo(() => {
    if (!system?.weather) return "Unknown";
    if (system.weather.online === false) return "Offline";

    const rainChance = Number(system.weather.rain_chance ?? 0);

    if (rainChance >= 70) return "Rain likely";
    if (rainChance >= 40) return "Rain possible";

    return system.weather.condition || "Online";
  }, [system?.weather]);

  const sprinklerPillState: StatusState =
    sprinklerStatus === "Running"
      ? "active"
      : sprinklerStatus === "Online"
        ? "good"
        : sprinklerStatus === "Offline"
          ? "bad"
          : "neutral";

  const thermostatPillState: StatusState =
    thermostatStatus === "Cooling" ||
    thermostatStatus === "Heating" ||
    thermostatStatus === "Fan"
      ? "active"
      : thermostatStatus === "Online"
        ? "good"
        : thermostatStatus === "Offline"
          ? "bad"
          : "neutral";

  const weatherPillState: StatusState =
    weatherStatus === "Rain likely"
      ? "warn"
      : weatherStatus === "Rain possible"
        ? "warn"
        : weatherStatus === "Offline"
          ? "bad"
          : weatherStatus === "Unknown"
            ? "neutral"
            : "good";

  const systemHealthState: StatusState = !system
    ? "neutral"
    : system.fault
      ? "bad"
      : "good";

  const orionRecommendation = useMemo<OrionRecommendation>(() => {
    if (!system) {
      return {
        title: "Waiting for telemetry",
        detail: "Orion is waiting for the backend to return live system state.",
        state: "neutral",
        action: "observe",
        canApply: false,
      };
    }

    if (system.fault) {
      return {
        title: "Investigate fault",
        detail: `A system fault is present: ${system.fault}. Review logs before running automation.`,
        state: "bad",
        action: "observe",
        canApply: false,
      };
    }

    const rainChance = Number(system.weather?.rain_chance ?? 0);

    if (rainChance >= 70 && system.sprinkler?.running) {
      return {
        title: "Stop irrigation",
        detail: `Rain chance is ${formatRain(rainChance)} while the sprinkler is running. Orion can stop watering now.`,
        state: "warn",
        action: "stop_sprinkler",
        canApply: true,
        applyLabel: "Stop sprinkler",
      };
    }

    if (rainChance >= 70) {
      return {
        title: "Delay irrigation",
        detail: `Rain chance is ${formatRain(rainChance)}. Orion can skip the next irrigation run and save the schedule state.`,
        state: "warn",
        action: "delay_irrigation",
        canApply: true,
        applyLabel: "Apply delay",
      };
    }

    if (system.thermostat?.cooling) {
      return {
        title: "Monitor cooling",
        detail: `Thermostat is cooling at ${formatTemp(system.thermostat.temp)} with ${formatHumidity(system.thermostat.humidity)} humidity. No automatic HVAC change is needed.`,
        state: "active",
        action: "observe",
        canApply: false,
      };
    }

    return {
      title: "Monitor system",
      detail: "No immediate action needed. Devices are stable and automation can keep observing.",
      state: "good",
      action: "observe",
      canApply: false,
    };
  }, [system]);

  const loadSessions = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/v1/sessions`);
      if (!res.ok) return;

      const data = await res.json();
      setSessions(data.sessions || []);
    } catch {}
  }, []);

  const loadSystem = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/v1/system`);
      if (!res.ok) return;

      const data = await res.json();
      setSystem(data);

      if (data?.automation_mode === "auto" || data?.automation_mode === "manual") {
        setAutomationMode(data.automation_mode);
      }
    } catch {}
  }, []);

  const loadAutomationMode = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/v1/control/ai/mode`);
      if (!res.ok) return;

      const data = await res.json();
      if (data.mode === "auto" || data.mode === "manual") {
        setAutomationMode(data.mode);
      }
    } catch {}
  }, []);

  useEffect(() => {
    loadSessions();
    loadSystem();
    loadAutomationMode();

    const interval = window.setInterval(loadSystem, Number.isFinite(SYSTEM_POLL_MS) ? SYSTEM_POLL_MS : 3000);

    return () => window.clearInterval(interval);
  }, [loadSessions, loadSystem, loadAutomationMode]);

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const stopGeneration = () => {
    abortController?.abort();
    setAbortController(null);
    setLoading(false);
  };

  const newChat = () => {
    abortController?.abort();
    setAbortController(null);
    setLoading(false);
    setMessages([]);
    setSessionId(null);
  };

  const loadChat = async (id: string) => {
    abortController?.abort();
    setAbortController(null);
    setLoading(false);
    setSessionId(id);

    try {
      const res = await fetch(`${BACKEND_URL}/v1/session/${id}`);
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
  };

  const postControl = useCallback(
    async (
      path: string,
      body: Record<string, unknown> = {},
    ) => {
      setControlLoading(true);

      try {
        const res = await fetch(`${BACKEND_URL}${path}`, {
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

        if (!res.ok) {
          data = {
            ok: false,
            status: res.status,
            response: data,
          };
        }

        setControlResult(data);
        await loadSystem();
        return data;
      } catch (err) {
        const errorResult = {
          ok: false,
          error: err instanceof Error ? err.message : String(err),
        };

        setControlResult(errorResult);
        return errorResult;
      } finally {
        setControlLoading(false);
      }
    },
    [loadSystem],
  );

  const setAutomationModeAction = async (mode: AutomationMode) => {
    setAutomationMode(mode);

    try {
      const res = await fetch(`${BACKEND_URL}/v1/control/ai/mode`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ mode }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        setControlResult(data || { ok: false, error: "Failed to update AI mode." });
      }
    } catch (err) {
      setControlResult({
        ok: false,
        error: err instanceof Error ? err.message : String(err),
      });
    }
  };

  const executeRecommendedAction = useCallback(
    async (source: "manual" | "auto" = "manual") => {
      if (!system || !orionRecommendation.canApply || controlLoading) return null;

      if (source === "auto") {
        setAutoExecutionLoading(true);
      }

      try {
        // Recommendations now execute through the same real control endpoints
        // that the assistant/manual controls use. This avoids the old bug where
        // recommendations only logged a decision but did not touch the device.
        if (orionRecommendation.action === "stop_sprinkler") {
          return await postControl("/v1/control/sprinkler/stop", {
            source: "recommendation",
            reason: orionRecommendation.detail,
          });
        }

        if (orionRecommendation.action === "delay_irrigation") {
          return await postControl("/v1/control/sprinkler/skip", {
            source: "recommendation",
            reason: orionRecommendation.detail,
          });
        }

        return await postControl("/v1/control/ai/execute", {
          action: orionRecommendation.action,
          params: orionRecommendation.params || {},
          source,
          state: system,
        });
      } finally {
        if (source === "auto") {
          setAutoExecutionLoading(false);
        }
      }
    },
    [controlLoading, orionRecommendation, postControl, system],
  );

  // Auto execution is handled by the backend AI loop after you switch Orion to Auto mode.
  // The frontend only provides the mode toggle and manual Apply button.

  const runSprinklerZone = async () => {
    if (controlLoading) return;

    const zone = Number(sprinklerZone);
    const minutes = Number(sprinklerMinutes);

    if (!Number.isFinite(zone) || !Number.isFinite(minutes)) {
      setControlResult({
        ok: false,
        error: "Zone and minutes must be numbers.",
      });
      return;
    }

    if (zone <= 0 || minutes <= 0) {
      setControlResult({
        ok: false,
        error: "Zone and minutes must be greater than zero.",
      });
      return;
    }

    const confirmed = window.confirm(
      `Run sprinkler zone ${zone} for ${minutes} minute(s)?`,
    );

    if (!confirmed) return;

    await postControl("/v1/control/sprinkler/zone", {
      zone,
      minutes,
    });
  };

  const stopSprinkler = async () => {
    if (controlLoading) return;

    const confirmed = window.confirm("Force sprinkler off?");
    if (!confirmed) return;

    await postControl("/v1/control/sprinkler/stop");
  };

  const runSprinklerProgramNow = async () => {
    if (controlLoading) return;

    const confirmed = window.confirm("Run sprinkler program now?");
    if (!confirmed) return;

    await postControl("/v1/control/sprinkler/program-now");
  };

  const setThermostatTemp = async () => {
    if (controlLoading) return;

    const temp = Number(thermostatSetpoint);

    if (!Number.isFinite(temp)) {
      setControlResult({
        ok: false,
        error: "Setpoint must be a number.",
      });
      return;
    }

    await postControl("/v1/control/thermostat/setpoint", {
      temp,
    });
  };

  const setThermostatModeAction = async () => {
    if (controlLoading) return;

    await postControl("/v1/control/thermostat/mode", {
      mode: thermostatMode,
    });
  };

  const setFanModeAction = async () => {
    if (controlLoading) return;

    await postControl("/v1/control/thermostat/fan", {
      mode: fanMode,
    });
  };

  const appendAssistantReply = (reply: string) => {
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
  };

  const sendMessage = async () => {
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
      const res = await fetch(`${BACKEND_URL}/v1/chat/stream`, {
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

      const processEvent = (event: string) => {
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
      };

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
        const sessionRes = await fetch(
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
  };

  const renameChat = async (id: string) => {
    const title = window.prompt("Rename chat:");
    if (!title?.trim()) return;

    await fetch(`${BACKEND_URL}/v1/session/${id}/rename`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ title: title.trim() }),
    });

    await loadSessions();
  };

  const deleteChat = async (id: string) => {
    const confirmed = window.confirm("Delete this chat?");
    if (!confirmed) return;

    await fetch(`${BACKEND_URL}/v1/session/${id}`, {
      method: "DELETE",
    });

    if (sessionId === id) {
      setMessages([]);
      setSessionId(null);
    }

    await loadSessions();
  };

  const askSuggestion = (value: string) => {
    setInput(value);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <style>{`
        html { color-scheme: dark; }
        * { scrollbar-width: thin; scrollbar-color: rgba(100, 116, 139, 0.42) transparent; }
        *::-webkit-scrollbar { width: 8px; height: 8px; }
        *::-webkit-scrollbar-track { background: transparent; }
        *::-webkit-scrollbar-thumb { background: rgba(100, 116, 139, 0.35); border-radius: 999px; border: 2px solid transparent; background-clip: padding-box; }
        *::-webkit-scrollbar-thumb:hover { background: rgba(148, 163, 184, 0.55); background-clip: padding-box; }
      `}</style>

      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(37,99,235,0.14),_transparent_32%),radial-gradient(circle_at_top_right,_rgba(14,165,233,0.08),_transparent_30%),linear-gradient(180deg,_rgba(15,23,42,0.22),_transparent_42%)]" />

      <header className="sticky top-0 z-20 border-b border-slate-800/80 bg-slate-950/90 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[1800px] items-center justify-between gap-4 px-5 py-3.5">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-xl shadow-lg shadow-blue-950/30">
              🤖
            </div>

            <div className="min-w-0">
              <h1 className="truncate text-lg font-semibold tracking-tight text-white">
                Orion
              </h1>
              <p className="truncate text-xs text-slate-400">
                Home assistant, live device state, weather, and automation
              </p>
            </div>
          </div>

          <div className="hidden items-center gap-2 md:flex">
            <StatusPill
              label={system?.ai_status ? `AI ${formatMode(system.ai_status)}` : "AI --"}
              state={aiActive ? "good" : "neutral"}
            />

            <StatusPill
              label={automationMode === "auto" ? "Auto execute" : "Manual apply"}
              state={automationMode === "auto" ? "active" : "neutral"}
            />

            <StatusPill label={weatherStatus} state={weatherPillState} />

            <StatusPill
              label={!system ? "Loading" : system.fault ? "Fault" : "Healthy"}
              state={systemHealthState}
            />
          </div>
        </div>
      </header>

      <main className="relative mx-auto grid max-w-[1800px] grid-cols-1 gap-4 px-5 py-4 xl:h-[calc(100vh-69px)] xl:min-h-0 xl:grid-cols-[minmax(0,1fr)_420px] xl:overflow-hidden">
        <section className="min-h-0 space-y-4 xl:overflow-y-auto xl:pr-1">
          <CollapsibleCard
            icon="🤖"
            title="Orion AI"
            subtitle={lastUpdatedLabel}
            status={!system ? "Loading" : system.fault ? "Fault" : aiActive ? "Autonomous Monitoring" : formatMode(system.ai_status)}
            statusState={system?.fault ? "bad" : aiActive ? "good" : "neutral"}
            primaryLabel="Automation state"
            primaryValue={formatAutomationState(system?.mode)}
            defaultOpen
            metricsWide
            metrics={[
              {
                label: "AI",
                value: formatMode(system?.ai_status),
                state: aiActive ? "good" : "neutral",
              },
              {
                label: "Fault",
                value: system?.fault ? "Yes" : "No",
                state: system?.fault ? "bad" : "good",
              },
              {
                label: "CPU",
                value: percent(system?.cpu),
              },
              {
                label: "Memory",
                value: percent(system?.memory),
              },
            ]}
          >
            <div className="grid gap-4 xl:grid-cols-2">
              <div className="rounded-2xl border border-slate-800/80 bg-slate-950/35 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                      Last decision
                    </div>
                    <div className="mt-2 text-lg font-semibold tracking-tight text-white">
                      {system?.last_decision?.action ? formatMode(system.last_decision.action) : "Autonomous Monitoring"}
                    </div>
                  </div>

                  <StatusPill
                    label={system?.last_decision?.time ? formatLastUpdated(system?.last_decision?.time) : "No action yet"}
                    state={system?.last_decision?.action ? "active" : "neutral"}
                  />
                </div>

                <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-6 text-slate-400">
                  {system?.last_decision?.reason ||
                    "No automation decision has been recorded yet. Orion is observing live device state."}
                </p>
              </div>

              <div className="rounded-2xl border border-slate-800/80 bg-slate-950/35 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                      Recommendation
                    </div>
                    <div className="mt-2 text-lg font-semibold tracking-tight text-white">
                      {orionRecommendation.title}
                    </div>
                  </div>

                  <StatusPill label="AI hint" state={orionRecommendation.state} />
                </div>

                <p className="mt-3 text-sm leading-6 text-slate-400">
                  {orionRecommendation.detail}
                </p>

                <div className="mt-4 flex flex-wrap gap-2">
                  {orionRecommendation.canApply && (
                    <Button
                      onClick={() => executeRecommendedAction("manual")}
                      disabled={controlLoading || autoExecutionLoading}
                      variant={orionRecommendation.action === "stop_sprinkler" ? "danger" : "success"}
                      className="h-9"
                    >
                      {orionRecommendation.applyLabel || "Apply"}
                    </Button>
                  )}

                  <Button
                    onClick={() => askSuggestion("Explain the current home automation recommendation using only the live system state.")}
                    variant="secondary"
                    className="h-9"
                  >
                    Explain
                  </Button>

                  <Button
                    onClick={() => askSuggestion("What should Orion do next for the home system?")}
                    variant="ghost"
                    className="h-9"
                  >
                    Ask Orion
                  </Button>
                </div>

                <div className="mt-4 rounded-xl border border-slate-800/70 bg-slate-950/35 p-3">
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <div>
                      <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                        Execution mode
                      </div>
                      <p className="mt-1 text-xs leading-5 text-slate-400">
                        Manual requires Apply. Auto can run safe irrigation actions when the recommendation changes.
                      </p>
                    </div>
                    <StatusPill
                      label={automationMode === "auto" ? "Auto" : "Manual"}
                      state={automationMode === "auto" ? "active" : "neutral"}
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <Button
                      onClick={() => setAutomationModeAction("manual")}
                      variant={automationMode === "manual" ? "primary" : "secondary"}
                      className="h-9 w-full"
                    >
                      Manual
                    </Button>
                    <Button
                      onClick={() => setAutomationModeAction("auto")}
                      variant={automationMode === "auto" ? "primary" : "secondary"}
                      className="h-9 w-full"
                    >
                      Auto
                    </Button>
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-4 grid gap-3 md:grid-cols-4">
              <Field
                label="Execution"
                value={executionSummary.status}
                state={executionSummary.state}
              />
              <Field
                label="Action"
                value={executionSummary.action}
              />
              <Field
                label="Safety"
                value={executionSummary.safety}
                state={executionSummary.state}
              />
              <Field
                label="Manual override"
                value={manualOverride.active ? manualOverride.label : "Inactive"}
                state={manualOverride.active ? "warn" : "neutral"}
              />
            </div>

            <div className="mt-4 rounded-2xl border border-slate-800/80 bg-slate-950/25 p-4">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold text-slate-100">System load</div>
                  <div className="mt-1 text-xs text-slate-400">Live resource usage from the backend</div>
                </div>
                <StatusPill label={lastUpdatedLabel} state="neutral" />
              </div>

              <div className="grid gap-3 md:grid-cols-3">
                <ProgressStat
                  label="CPU"
                  value={system?.cpu}
                  state={Number(system?.cpu ?? 0) >= 80 ? "bad" : Number(system?.cpu ?? 0) >= 60 ? "warn" : "neutral"}
                />
                <ProgressStat
                  label="Memory"
                  value={system?.memory}
                  state={Number(system?.memory ?? 0) >= 80 ? "bad" : Number(system?.memory ?? 0) >= 60 ? "warn" : "neutral"}
                />
                <ProgressStat
                  label="GPU"
                  value={system?.gpu}
                  state={Number(system?.gpu ?? 0) >= 80 ? "bad" : Number(system?.gpu ?? 0) >= 60 ? "warn" : "neutral"}
                />
              </div>
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              <StatusPill label={`Weather: ${weatherStatus}`} state={weatherPillState} />
              <StatusPill label={`Sprinkler: ${sprinklerStatus}`} state={sprinklerPillState} />
              <StatusPill label={`Thermostat: ${thermostatStatus}`} state={thermostatPillState} />
            </div>

            <details className="mt-4 rounded-2xl border border-slate-800/80 bg-slate-950/30">
              <summary className="cursor-pointer list-none px-3 py-2.5 text-xs font-medium text-slate-400 transition hover:text-slate-100 [&::-webkit-details-marker]:hidden">
                Advanced / Debug
              </summary>
              <div className="grid gap-3 border-t border-slate-800/80 p-3 lg:grid-cols-2">
                <div>
                  <div className="mb-2 text-xs font-medium text-slate-400">
                    Command response
                  </div>
                  <pre className="max-h-72 overflow-auto rounded-xl bg-slate-950/50 p-3 text-xs leading-5 text-slate-300">
                    {controlResultText}
                  </pre>
                </div>
                <div>
                  <div className="mb-2 text-xs font-medium text-slate-400">
                    Decision result
                  </div>
                  <pre className="max-h-72 overflow-auto rounded-xl bg-slate-950/50 p-3 text-xs leading-5 text-slate-300">
                    {decisionResultText}
                  </pre>
                </div>
              </div>
            </details>
          </CollapsibleCard>

          <div className="grid grid-cols-1 gap-4 2xl:grid-cols-3">
            <CollapsibleCard
              icon="🌦️"
              title="Weather"
              subtitle={system?.weather?.location || "Outdoor conditions"}
              status={weatherStatus}
              statusState={weatherPillState}
              primaryLabel="Current weather"
              primaryValue={formatTemp(system?.weather?.temp)}
              metrics={[
                {
                  label: "Rain",
                  value: formatRain(system?.weather?.rain_chance),
                  state: Number(system?.weather?.rain_chance ?? 0) >= 70 ? "warn" : "neutral",
                },
                {
                  label: "Feels",
                  value: formatTemp(system?.weather?.feels_like),
                },
                {
                  label: "Humidity",
                  value: formatHumidity(system?.weather?.humidity),
                },
                {
                  label: "Wind",
                  value: formatWind(system?.weather?.wind_mph),
                },
              ]}
            >
              <div className="grid grid-cols-2 gap-3">
                <Field label="Condition" value={system?.weather?.condition || "--"} />
                <Field label="Precip" value={formatPrecip(system?.weather?.precip_in)} />
                <Field label="High" value={formatTemp(system?.weather?.forecast_today?.max_temp)} />
                <Field label="Low" value={formatTemp(system?.weather?.forecast_today?.min_temp)} />
                <Field label="Updated" value={weatherUpdatedLabel} />
                <Field label="Source" value={system?.weather?.source || "--"} />
              </div>

              {system?.weather?.error && (
                <div className="mt-4 rounded-2xl border border-red-400/15 bg-red-500/10 p-3 text-xs leading-5 text-red-200">
                  {system.weather.error}
                </div>
              )}
            </CollapsibleCard>

            <CollapsibleCard
              icon="💧"
              title="Sprinkler"
              subtitle="Irrigation status and manual controls"
              status={sprinklerStatus}
              statusState={sprinklerPillState}
              primaryLabel="Current state"
              primaryValue={sprinklerStatus}
              metrics={[
                {
                  label: "Mode",
                  value: formatMode(system?.sprinkler?.mode),
                },
                {
                  label: "Zone",
                  value: formatZone(system?.sprinkler?.zone),
                },
                {
                  label: "Schedule",
                  value: system?.sprinkler?.next_run || formatScheduleSummary(system?.irrigation_schedule),
                },
                {
                  label: "Online",
                  value: yesNo(system?.sprinkler?.online),
                  state: onlineState(system?.sprinkler?.online),
                },
              ]}
            >
              <div className="space-y-4">
                {system?.sprinkler?.running && (
                  <div className="rounded-2xl border border-blue-400/20 bg-blue-500/10 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="text-sm font-semibold text-blue-100">
                          Sprinkler is running
                        </div>
                        <div className="mt-1 text-xs text-blue-200/80">
                          {cycleSummary.activeLabel} is currently active
                          {cycleSummary.activeEta ? ` · ${cycleSummary.activeEta}` : ""}
                          {cycleSummary.cycleEta && cycleSummary.cycleEta !== "No active cycle"
                            ? ` · ${cycleSummary.cycleEta}`
                            : ""}
                        </div>
                        {cycleSummary.activeProgress !== null && (
                          <div className="mt-3">
                            <div className="mb-1 flex items-center justify-between text-[11px] font-medium text-blue-100/80">
                              <span>Current zone progress</span>
                              <span>{Math.round(cycleSummary.activeProgress)}%</span>
                            </div>
                            <div className="h-2 overflow-hidden rounded-full bg-blue-950/80">
                              <div
                                className="h-full rounded-full bg-blue-300 transition-all duration-700"
                                style={{ width: `${cycleSummary.activeProgress}%` }}
                              />
                            </div>
                          </div>
                        )}
                      </div>
                      <Button
                        onClick={stopSprinkler}
                        disabled={controlLoading}
                        variant="danger"
                        className="shrink-0"
                      >
                        Stop now
                      </Button>
                    </div>
                  </div>
                )}

                {system?.sprinkler?.error && (
                  <div className="rounded-2xl border border-red-400/15 bg-red-500/10 p-3 text-xs leading-5 text-red-200">
                    {system.sprinkler.error}
                  </div>
                )}

                {irrigationTimeline.length > 0 && (
                  <div className="rounded-2xl border border-slate-800/80 bg-slate-950/25 p-4">
                    <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="text-sm font-semibold text-slate-100">Upcoming zone timeline</div>
                        <div className="mt-1 text-xs text-slate-400">
                          {cycleSummary.running
                            ? `${cycleSummary.activeLabel} active · ${cycleSummary.remainingLabel} remaining`
                            : "Next scheduled run preview"}
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {cycleSummary.running && (
                          <StatusPill label={cycleSummary.cycleEta} state="active" />
                        )}
                        <StatusPill label={formatScheduleController(system?.irrigation_schedule)} state="active" />
                      </div>
                    </div>

                    <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                      {irrigationTimeline.map((item, index) => (
                        <div
                          key={`${item.label}-${item.time}-${index}`}
                          className={cx(
                            "rounded-xl border p-3 transition",
                            item.status === "active" && "border-blue-300/60 bg-blue-500/15 shadow-lg shadow-blue-950/20",
                            item.status === "completed" && "border-emerald-400/25 bg-emerald-500/10",
                            item.status === "upcoming" && "border-slate-800/70 bg-slate-950/35",
                          )}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <div className="text-[11px] font-medium uppercase tracking-wide text-slate-500">
                              {item.time}
                            </div>
                            <div
                              className={cx(
                                "rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                                item.status === "active" && "bg-blue-400/15 text-blue-200",
                                item.status === "completed" && "bg-emerald-400/10 text-emerald-200",
                                item.status === "upcoming" && "bg-slate-800/70 text-slate-400",
                              )}
                            >
                              {item.status === "active"
                                ? "Active"
                                : item.status === "completed"
                                  ? "Done"
                                  : "Next"}
                            </div>
                          </div>
                          <div className="mt-1 text-sm font-semibold text-white">{item.label}</div>
                          <div className="mt-1 text-xs text-slate-400">
                            {item.duration}
                            {item.endTime && item.endTime !== "--" ? ` · ends ${item.endTime}` : ""}
                          </div>
                          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-800/80">
                            <div
                              className={cx(
                                "h-full rounded-full transition-all duration-700",
                                item.status === "active" && "bg-blue-300",
                                item.status === "completed" && "bg-emerald-300",
                                item.status === "upcoming" && "bg-slate-700",
                              )}
                              style={{ width: `${item.progress}%` }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="rounded-2xl border border-slate-800/80 bg-slate-950/25 p-4">
                  <div className="mb-3 text-sm font-semibold text-slate-100">
                    Run a zone
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <Label>Zone</Label>
                      <TextInput
                        value={sprinklerZone}
                        onChange={setSprinklerZone}
                        placeholder="1"
                        type="number"
                      />
                    </div>

                    <div>
                      <Label>Minutes</Label>
                      <TextInput
                        value={sprinklerMinutes}
                        onChange={setSprinklerMinutes}
                        placeholder="1"
                        type="number"
                      />
                    </div>
                  </div>

                  <Button
                    onClick={runSprinklerZone}
                    disabled={controlLoading}
                    variant="success"
                    className="mt-3 w-full"
                  >
                    Run zone
                  </Button>
                </div>

                <details className="rounded-2xl border border-slate-800/80 bg-slate-950/30">
                  <summary className="cursor-pointer list-none px-3 py-2.5 text-xs font-medium text-slate-400 transition hover:text-slate-100 [&::-webkit-details-marker]:hidden">
                    More sprinkler actions and technical details
                  </summary>
                  <div className="space-y-3 border-t border-slate-800/80 p-3">
                    <div className="grid gap-3 sm:grid-cols-2">
                      <Button
                        onClick={runSprinklerProgramNow}
                        disabled={controlLoading}
                        variant="secondary"
                        className="w-full"
                      >
                        Start irrigation cycle
                      </Button>

                      {!system?.sprinkler?.running && (
                        <Button
                          onClick={stopSprinkler}
                          disabled={controlLoading}
                          variant="danger"
                          className="w-full"
                        >
                          Force stop
                        </Button>
                      )}
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <Field label="Next run" value={formatMetricValue(system?.sprinkler?.next_run) || "No schedule"} />
                      <Field label="Schedule" value={formatScheduleSummary(system?.irrigation_schedule)} />
                      <Field label="Controller" value={formatScheduleController(system?.irrigation_schedule)} state="good" />
                      <Field label="Skip next" value={yesNo(system?.irrigation_schedule?.skip_next_run)} state={system?.irrigation_schedule?.skip_next_run ? "warn" : "neutral"} />
                      <Field label="Source" value={system?.sprinkler?.source || "--"} />
                    </div>

                    <pre className="max-h-56 overflow-auto rounded-xl bg-slate-950/50 p-3 text-xs leading-5 text-slate-300">
                      {formatJson(system?.sprinkler?.raw ?? system?.sprinkler, "No sprinkler data")}
                    </pre>
                  </div>
                </details>
              </div>
            </CollapsibleCard>

            <CollapsibleCard
              icon="🌡️"
              title="Thermostat"
              subtitle="Temperature, HVAC mode, and fan control"
              status={thermostatStatus}
              statusState={thermostatPillState}
              primaryLabel="Current temperature"
              primaryValue={formatTemp(system?.thermostat?.temp)}
              metrics={[
                {
                  label: "Status",
                  value: thermostatStatus,
                  state: thermostatPillState,
                },
                {
                  label: "Humidity",
                  value: formatHumidity(system?.thermostat?.humidity),
                },
                {
                  label: "Mode",
                  value: formatMode(system?.thermostat?.mode),
                },
                {
                  label: "Fan",
                  value: onOff(system?.thermostat?.fan),
                  state: system?.thermostat?.fan ? "active" : "neutral",
                },
              ]}
            >
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Online" value={yesNo(system?.thermostat?.online)} state={onlineState(system?.thermostat?.online)} />
                  <Field label="Cooling" value={onOff(system?.thermostat?.cooling)} state={activeState(system?.thermostat?.cooling)} />
                  <Field label="Heating" value={onOff(system?.thermostat?.heating)} state={activeState(system?.thermostat?.heating)} />
                  <Field label="Source" value={system?.thermostat?.source || "--"} />
                </div>

                {system?.thermostat?.error && (
                  <div className="rounded-2xl border border-red-400/15 bg-red-500/10 p-3 text-xs leading-5 text-red-200">
                    {system.thermostat.error}
                  </div>
                )}

                <div className="rounded-2xl border border-slate-800/80 bg-slate-950/25 p-4">
                  <div className="mb-3 text-sm font-semibold text-slate-100">
                    Set temperature
                  </div>
                  <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_140px]">
                    <TextInput
                      value={thermostatSetpoint}
                      onChange={setThermostatSetpoint}
                      placeholder="72"
                      type="number"
                    />

                    <Button
                      onClick={setThermostatTemp}
                      disabled={controlLoading}
                      className="w-full"
                    >
                      Set temp
                    </Button>
                  </div>
                </div>

                <details className="rounded-2xl border border-slate-800/80 bg-slate-950/30">
                  <summary className="cursor-pointer list-none px-3 py-2.5 text-xs font-medium text-slate-400 transition hover:text-slate-100 [&::-webkit-details-marker]:hidden">
                    HVAC, fan, and technical details
                  </summary>
                  <div className="space-y-3 border-t border-slate-800/80 p-3">
                    <div className="grid gap-3 sm:grid-cols-2">
                      <div>
                        <Label>HVAC Mode</Label>
                        <SelectInput value={thermostatMode} onChange={setThermostatMode}>
                          <option value="auto">Auto</option>
                          <option value="cool">Cool</option>
                          <option value="heat">Heat</option>
                          <option value="off">Off</option>
                        </SelectInput>
                        <Button
                          onClick={setThermostatModeAction}
                          disabled={controlLoading}
                          variant="secondary"
                          className="mt-2 w-full"
                        >
                          Apply mode
                        </Button>
                      </div>

                      <div>
                        <Label>Fan Mode</Label>
                        <SelectInput value={fanMode} onChange={setFanMode}>
                          <option value="auto">Auto</option>
                          <option value="on">On</option>
                          <option value="off">Off</option>
                        </SelectInput>
                        <Button
                          onClick={setFanModeAction}
                          disabled={controlLoading}
                          variant="secondary"
                          className="mt-2 w-full"
                        >
                          Apply fan
                        </Button>
                      </div>
                    </div>

                    <pre className="max-h-56 overflow-auto rounded-xl bg-slate-950/50 p-3 text-xs leading-5 text-slate-300">
                      {formatJson(system?.thermostat?.raw ?? system?.thermostat, "No thermostat data")}
                    </pre>
                  </div>
                </details>
              </div>
            </CollapsibleCard>
          </div>
        </section>

        <aside className="flex min-h-0 flex-col gap-4">
          <Panel className="flex min-h-[640px] flex-col xl:min-h-0 xl:flex-1">
            <div className="flex items-center justify-between gap-3 border-b border-slate-800/80 px-5 py-4">
              <div className="min-w-0">
                <h2 className="truncate text-sm font-semibold tracking-tight text-slate-100">
                  Assistant
                </h2>
                <p className="mt-1 truncate text-xs text-slate-400">
                  Chat with Orion
                </p>
              </div>

              <Button onClick={newChat} variant="secondary">
                New chat
              </Button>
            </div>

            <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-5 py-6">
              {messages.length === 0 && (
                <EmptyChatState onSuggestion={askSuggestion} />
              )}

              {messages.map((msg, i) => (
                <div
                  key={`${msg.role}-${i}`}
                  className={cx(
                    "flex",
                    msg.role === "user" ? "justify-end" : "justify-start",
                  )}
                >
                  <div
                    className={cx(
                      "max-w-[min(760px,90%)] rounded-2xl px-4 py-3 text-sm leading-7 shadow-sm",
                      msg.role === "user"
                        ? "bg-blue-600 text-white shadow-blue-950/20"
                        : "border border-slate-800/80 bg-slate-950/45 text-slate-100",
                    )}
                  >
                    <div className="whitespace-pre-wrap break-words">
                      {msg.content}
                    </div>
                  </div>
                </div>
              ))}

              {loading && (
                <div className="flex justify-start">
                  <div className="rounded-2xl border border-slate-800/80 bg-slate-950/45 px-4 py-3 text-sm text-slate-400">
                    Thinking…
                  </div>
                </div>
              )}

              <div ref={messageEndRef} />
            </div>

            <div className="border-t border-slate-800/80 bg-slate-950/35 p-4">
              <div className="flex gap-2 rounded-2xl border border-slate-800/80 bg-slate-950/55 p-2 shadow-inner shadow-black/10 focus-within:border-blue-400/80 focus-within:ring-4 focus-within:ring-blue-500/10">
                <input
                  className="min-h-10 flex-1 rounded-xl bg-transparent px-3 text-sm text-white outline-none placeholder:text-slate-500"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask Orion…"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
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
                  className="min-w-[80px]"
                >
                  {loading ? "Stop" : "Send"}
                </Button>
              </div>
            </div>
          </Panel>

          <Panel className="xl:max-h-64">
            <PanelHeader title="Saved Chats" subtitle="Continue a conversation" />

            <div className="max-h-48 space-y-2 overflow-y-auto p-5">
              {sessions.length === 0 && (
                <div className="rounded-2xl border border-dashed border-slate-700/80 bg-slate-950/30 p-4 text-sm text-slate-400">
                  No saved chats yet.
                </div>
              )}

              {sessions.map((s) => {
                const title = displaySessionTitle(s);

                return (
                  <div
                    key={s.id}
                    className={cx(
                      "group rounded-2xl border p-3.5 transition",
                      sessionId === s.id
                        ? "border-blue-400/50 bg-blue-500/10"
                        : "border-slate-800/80 bg-slate-950/30 hover:border-slate-700 hover:bg-slate-900/70",
                    )}
                  >
                    <button
                      type="button"
                      onClick={() => loadChat(s.id)}
                      className="block w-full truncate text-left text-sm font-semibold text-slate-100"
                      title={s.title}
                    >
                      {title}
                    </button>

                    <div className="mt-3 flex gap-3 text-xs">
                      <button
                        type="button"
                        onClick={() => renameChat(s.id)}
                        className="text-slate-400 transition hover:text-slate-100"
                      >
                        Rename
                      </button>

                      <button
                        type="button"
                        onClick={() => deleteChat(s.id)}
                        className="text-red-300 transition hover:text-red-200"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </Panel>
        </aside>
      </main>
    </div>
  );
}