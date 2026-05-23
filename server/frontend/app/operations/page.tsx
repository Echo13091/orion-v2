"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

type OrionEvent = {
  id: string;
  timestamp: number;
  subsystem: string;
  node: string;
  severity: "info" | "warning" | "critical" | string;
  event_type: string;
  message: string;
  source: string;
  evidence?: Record<string, unknown>;
  repeat_count?: number;
  first_seen?: number;
  latest_seen?: number;
  latest_event_id?: string;
};

type CompactEvent = OrionEvent & {
  repeat_count: number;
  first_seen: number;
  latest_seen: number;
  repeated_events?: OrionEvent[];
};

type EventsResponse = {
  ok: boolean;
  count: number;
  active_fault_count: number;
  events: OrionEvent[];
};

type SystemResponse = {
  ok?: boolean;
  sprinkler?: {
    online?: boolean;
    running?: boolean;
    active?: boolean;
    zone?: number | string | null;
    active_zone?: number | string | null;
    mode?: string | null;
    status?: string | null;
    next_run?: string | null;
  };
  automation_mode?: string;
  ai_status?: string;
  fault?: unknown;
};

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:5001";

function formatTime(timestamp: number) {
  if (!timestamp) return "Unknown";

  return new Date(timestamp * 1000).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  });
}

function severityClass(severity: string) {
  if (severity === "critical") {
    return "border-red-500/50 bg-red-500/10 text-red-200";
  }

  if (severity === "warning") {
    return "border-yellow-500/50 bg-yellow-500/10 text-yellow-200";
  }

  return "border-emerald-500/40 bg-emerald-500/10 text-emerald-200";
}

function eventTypeLabel(value: string) {
  return value.replaceAll("_", " ");
}

function operationalImpact(event: OrionEvent) {
  if (event.subsystem === "vision" && event.event_type === "node_offline") {
    return "Impact: camera stream, snapshots, lawn condition, and visual rain evidence are unavailable. Orion continues operating with weather, sprinkler, thermostat, and event telemetry.";
  }

  if (event.subsystem === "vision" && event.event_type === "node_recovered") {
    return "Impact: camera telemetry recovered. Vision-based lawn and wet-surface evidence can resume after the next successful analysis cycle.";
  }

  if (event.event_type === "automation_policy_decision") {
    return "Impact: Orion evaluated policy context and updated the visible decision trail without directly bypassing hardware safety gates.";
  }

  if (event.event_type === "automation_action_recommended") {
    return "Impact: Orion generated an action recommendation. Hardware execution still requires the configured safety path and approval mode.";
  }

  if (event.event_type === "manual_zone_start") {
    return "Impact: a manual irrigation command was issued and recorded for audit visibility.";
  }

  if (event.event_type === "manual_stop") {
    return "Impact: a manual stop command was issued and recorded for audit visibility.";
  }

  if (event.event_type === "state_transition") {
    return "Impact: Orion detected a subsystem state change and preserved the transition evidence.";
  }

  if (event.severity === "critical") {
    return "Impact: critical subsystem condition detected. Operator review is required before relying on related automation.";
  }

  if (event.severity === "warning") {
    return "Impact: degraded or warning condition detected. Orion should continue using available trusted telemetry only.";
  }

  return "";
}

function compactEventKey(event: OrionEvent) {
  return [
    event.subsystem,
    event.node,
    event.severity,
    event.event_type,
    event.message,
    event.source,
  ].join("::");
}

function compactEvents(events: OrionEvent[]): CompactEvent[] {
  const compacted = new Map<string, CompactEvent>();

  for (const event of events) {
    const key = compactEventKey(event);
    const existing = compacted.get(key);

    if (!existing) {
      compacted.set(key, {
        ...event,
        repeat_count: 1,
        first_seen: event.timestamp,
        latest_seen: event.timestamp,
        repeated_events: [event],
      });
      continue;
    }

    existing.repeat_count += 1;
    existing.first_seen = Math.min(existing.first_seen, event.timestamp);
    existing.latest_seen = Math.max(existing.latest_seen, event.timestamp);
    existing.repeated_events = existing.repeated_events ?? [];
    existing.repeated_events.push(event);

    if (event.timestamp >= existing.timestamp) {
      existing.id = event.id;
      existing.timestamp = event.timestamp;
      existing.evidence = event.evidence;
    }
  }

  return Array.from(compacted.values()).sort(
    (a, b) => b.latest_seen - a.latest_seen,
  );
}

function EvidenceBlock({ evidence }: { evidence?: Record<string, unknown> }) {
  if (!evidence || Object.keys(evidence).length === 0) {
    return <span className="text-zinc-500">No evidence attached</span>;
  }

  return (
    <pre className="max-h-40 overflow-auto rounded-xl border border-zinc-800 bg-black/40 p-3 text-xs text-zinc-300">
      {JSON.stringify(evidence, null, 2)}
    </pre>
  );
}

export default function OperationsPage() {
  const [data, setData] = useState<EventsResponse | null>(null);
  const [systemData, setSystemData] = useState<SystemResponse | null>(null);
  const [error, setError] = useState<string>("");
  const [selectedSubsystem, setSelectedSubsystem] = useState<string>("all");
  const [selectedSeverity, setSelectedSeverity] = useState<string>("all");
  const [selectedEventType, setSelectedEventType] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");

  async function loadEvents() {
    try {
      setError("");

      const response = await fetch(`${BACKEND_URL}/v1/events?limit=100&compact=true`, {
        cache: "no-store",
      });

      if (!response.ok) {
        throw new Error(`Backend returned ${response.status}`);
      }

      const payload = (await response.json()) as EventsResponse;
      setData(payload);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Unknown operations console error";

      setError(message);
    }
  }

  async function loadSystemState() {
    try {
      const response = await fetch(`${BACKEND_URL}/v1/system`, {
        cache: "no-store",
      });

      if (!response.ok) {
        return;
      }

      const payload = (await response.json()) as SystemResponse;
      setSystemData(payload);
    } catch {
      // Keep Operations usable even if system snapshot polling fails.
    }
  }

  useEffect(() => {
    loadEvents();
    loadSystemState();

    const timer = window.setInterval(() => {
      loadEvents();
      loadSystemState();
    }, 5000);

    return () => window.clearInterval(timer);
  }, []);

  const events = data?.events ?? [];
  const sprinkler = systemData?.sprinkler ?? {};
  const sprinklerRunning = Boolean(
    sprinkler.running || sprinkler.active || sprinkler.status === "running",
  );
  const sprinklerZone = sprinkler.zone ?? sprinkler.active_zone ?? "—";
  const sprinklerMode = sprinkler.mode ?? (sprinklerRunning ? "manual" : "idle");

  const subsystems = useMemo(() => {
    return Array.from(new Set(events.map((event) => event.subsystem))).sort();
  }, [events]);

  const eventTypes = useMemo(() => {
    return Array.from(new Set(events.map((event) => event.event_type))).sort();
  }, [events]);

  const filteredEvents = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();

    return events.filter((event) => {
      const subsystemMatch =
        selectedSubsystem === "all" || event.subsystem === selectedSubsystem;

      const severityMatch =
        selectedSeverity === "all" || event.severity === selectedSeverity;

      const eventTypeMatch =
        selectedEventType === "all" || event.event_type === selectedEventType;

      const searchableText = [
        event.message,
        event.subsystem,
        event.node,
        event.severity,
        event.event_type,
        event.source,
        JSON.stringify(event.evidence ?? {}),
      ]
        .join(" ")
        .toLowerCase();

      const searchMatch = !query || searchableText.includes(query);

      return subsystemMatch && severityMatch && eventTypeMatch && searchMatch;
    });
  }, [
    events,
    selectedSubsystem,
    selectedSeverity,
    selectedEventType,
    searchQuery,
  ]);

  const compactedFilteredEvents = useMemo(() => {
    return compactEvents(filteredEvents);
  }, [filteredEvents]);

  const activeFaults = useMemo(() => {
    const faultEvents = events.filter((event) => {
      return (
        event.severity === "warning" ||
        event.severity === "critical" ||
        event.event_type === "fault" ||
        event.event_type === "node_offline" ||
        event.event_type === "policy_block"
      );
    });

    const latestByFaultKey = new Map<string, OrionEvent>();

    for (const event of faultEvents) {
      const key = `${event.subsystem}:${event.node}:${event.event_type}`;
      const existing = latestByFaultKey.get(key);

      if (!existing || event.timestamp > existing.timestamp) {
        latestByFaultKey.set(key, event);
      }
    }

    return Array.from(latestByFaultKey.values()).sort(
      (a, b) => b.timestamp - a.timestamp,
    );
  }, [events]);

  const nodeHealth = useMemo(() => {
    const latestByNode = new Map<string, OrionEvent>();

    for (const event of events) {
      const existing = latestByNode.get(event.node);

      if (!existing || event.timestamp > existing.timestamp) {
        latestByNode.set(event.node, event);
      }
    }

    return Array.from(latestByNode.values()).sort((a, b) =>
      a.node.localeCompare(b.node),
    );
  }, [events]);

  const policyEvents = useMemo(() => {
    return events.filter((event) => {
      return (
        event.event_type.includes("policy") ||
        event.source.includes("policy") ||
        event.event_type.includes("safety")
      );
    });
  }, [events]);

  const transitionEvents = useMemo(() => {
    return events.filter((event) => event.event_type === "state_transition");
  }, [events]);

  function applyQuickFilter(kind: "all" | "faults" | "vision" | "automation" | "manual" | "transitions") {
    setSearchQuery("");
    setSelectedSubsystem("all");
    setSelectedSeverity("all");
    setSelectedEventType("all");

    if (kind === "faults") {
      setSelectedSeverity("warning");
      return;
    }

    if (kind === "vision") {
      setSelectedSubsystem("vision");
      return;
    }

    if (kind === "automation") {
      setSelectedSubsystem("automation");
      return;
    }

    if (kind === "manual") {
      setSearchQuery("manual");
      return;
    }

    if (kind === "transitions") {
      setSelectedEventType("state_transition");
    }
  }

  return (
    <main className="min-h-screen bg-zinc-950 px-6 py-8 text-zinc-100">
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <header className="flex flex-col gap-2">
          <Link
            href="/"
            className="mb-2 inline-flex w-fit items-center text-sm text-zinc-400 transition hover:text-zinc-100"
          >
            ← Back to Orion Dashboard
          </Link>

          <p className="text-sm uppercase tracking-[0.25em] text-cyan-400">
            Orion V2
          </p>

          <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div>
              <h1 className="text-3xl font-semibold">Operations Console</h1>
              <p className="mt-2 max-w-3xl text-sm text-zinc-400">
                Supervisory view of system events, active faults, automation
                policies, node health, and command evidence.
              </p>
            </div>

            <button
              onClick={loadEvents}
              className="rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-2 text-sm text-zinc-200 hover:bg-zinc-800"
            >
              Refresh
            </button>
          </div>
        </header>

        {error ? (
          <section className="rounded-2xl border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-200">
            Operations backend unavailable: {error}
          </section>
        ) : null}

        <section className="grid gap-4 md:grid-cols-4">
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-5">
            <p className="text-sm text-zinc-400">Total Events</p>
            <p className="mt-2 text-3xl font-semibold">{data?.count ?? 0}</p>
          </div>

          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-5">
            <p className="text-sm text-zinc-400">Active Faults / Blocks</p>
            <p className="mt-2 text-3xl font-semibold">
              {activeFaults.length}
            </p>
          </div>

          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-5">
            <p className="text-sm text-zinc-400">Nodes Seen</p>
            <p className="mt-2 text-3xl font-semibold">{nodeHealth.length}</p>
          </div>

          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-5">
            <p className="text-sm text-zinc-400">Policy Events</p>
            <p className="mt-2 text-3xl font-semibold">
              {policyEvents.length}
            </p>
          </div>
        </section>

        <section className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-5">
          <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
            <div>
              <h2 className="text-lg font-semibold">Degraded Subsystems</h2>
              <p className="mt-1 text-sm text-zinc-400">
                Current warning/critical conditions with operational impact and fallback context.
              </p>
            </div>

            <span
              className={`w-fit rounded-full border px-3 py-1 text-xs font-medium ${
                activeFaults.length
                  ? "border-yellow-500/50 bg-yellow-500/10 text-yellow-200"
                  : "border-emerald-500/40 bg-emerald-500/10 text-emerald-200"
              }`}
            >
              {activeFaults.length ? "Review Required" : "No Degraded Subsystems"}
            </span>
          </div>

          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            {activeFaults.length === 0 ? (
              <div className="rounded-xl border border-zinc-800 bg-black/20 p-4 text-sm text-zinc-400">
                No warning, critical, offline-node, or policy-block events are currently active.
              </div>
            ) : (
              activeFaults.slice(0, 4).map((event) => (
                <article
                  key={event.id}
                  className="rounded-xl border border-zinc-800 bg-black/20 p-4"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`rounded-full border px-2.5 py-1 text-xs ${severityClass(
                          event.severity,
                        )}`}
                      >
                        {event.severity}
                      </span>

                      <span className="rounded-full border border-zinc-700 bg-zinc-950 px-2.5 py-1 text-xs text-zinc-300">
                        {event.subsystem}
                      </span>

                      <span className="rounded-full border border-zinc-700 bg-zinc-950 px-2.5 py-1 text-xs text-zinc-300">
                        {eventTypeLabel(event.event_type)}
                      </span>
                    </div>

                    <span className="text-xs text-zinc-500">
                      {formatTime(event.timestamp)}
                    </span>
                  </div>

                  <h3 className="mt-3 text-sm font-semibold text-zinc-100">
                    {event.message}
                  </h3>

                  <p className="mt-1 text-xs text-zinc-500">
                    Node: {event.node} · Source: {event.source}
                  </p>

                  {operationalImpact(event) ? (
                    <p className="mt-3 rounded-lg border border-yellow-500/20 bg-yellow-500/5 p-3 text-xs leading-5 text-yellow-100/90">
                      {operationalImpact(event)}
                    </p>
                  ) : null}
                </article>
              ))
            )}
          </div>
        </section>

        <section className="grid gap-4 lg:grid-cols-3">
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-5 lg:col-span-2">
            <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <h2 className="text-lg font-semibold">Event Timeline</h2>
                <p className="text-sm text-zinc-400">
                  Recent operational events across Orion subsystems.
                </p>
              </div>

              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => applyQuickFilter("all")}
                  className="rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-300 hover:bg-zinc-900"
                >
                  All
                </button>

                <button
                  onClick={() => applyQuickFilter("faults")}
                  className="rounded-xl border border-yellow-500/40 bg-yellow-500/10 px-3 py-2 text-sm text-yellow-200 hover:bg-yellow-500/20"
                >
                  Faults
                </button>

                <button
                  onClick={() => applyQuickFilter("vision")}
                  className="rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-300 hover:bg-zinc-900"
                >
                  Vision
                </button>

                <button
                  onClick={() => applyQuickFilter("automation")}
                  className="rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-300 hover:bg-zinc-900"
                >
                  Automation
                </button>

                <button
                  onClick={() => applyQuickFilter("manual")}
                  className="rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-300 hover:bg-zinc-900"
                >
                  Manual
                </button>

                <button
                  onClick={() => applyQuickFilter("transitions")}
                  className="rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-300 hover:bg-zinc-900"
                >
                  Transitions
                </button>

                <input
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  placeholder="Search events..."
                  className="min-w-48 rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-600"
                />

                <select
                  value={selectedSubsystem}
                  onChange={(event) => setSelectedSubsystem(event.target.value)}
                  className="rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-200"
                >
                  <option value="all">All subsystems</option>
                  {subsystems.map((subsystem) => (
                    <option key={subsystem} value={subsystem}>
                      {subsystem}
                    </option>
                  ))}
                </select>

                <select
                  value={selectedSeverity}
                  onChange={(event) => setSelectedSeverity(event.target.value)}
                  className="rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-200"
                >
                  <option value="all">All severities</option>
                  <option value="info">Info</option>
                  <option value="warning">Warning</option>
                  <option value="critical">Critical</option>
                </select>

                <select
                  value={selectedEventType}
                  onChange={(event) => setSelectedEventType(event.target.value)}
                  className="rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-200"
                >
                  <option value="all">All event types</option>
                  {eventTypes.map((eventType) => (
                    <option key={eventType} value={eventType}>
                      {eventTypeLabel(eventType)}
                    </option>
                  ))}
                </select>

                {(selectedSubsystem !== "all" ||
                  selectedSeverity !== "all" ||
                  selectedEventType !== "all" ||
                  searchQuery.trim()) && (
                  <button
                    onClick={() => {
                      setSelectedSubsystem("all");
                      setSelectedSeverity("all");
                      setSelectedEventType("all");
                      setSearchQuery("");
                    }}
                    className="rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-300 hover:bg-zinc-900"
                  >
                    Clear
                  </button>
                )}
              </div>
            </div>

            <div className="flex flex-col gap-3">
              {compactedFilteredEvents.length === 0 ? (
                <div className="rounded-xl border border-zinc-800 bg-black/20 p-4 text-sm text-zinc-500">
                  No events found.
                </div>
              ) : (
                compactedFilteredEvents.map((event) => (
                  <article
                    key={`${event.id}:${event.repeat_count}`}
                    className="rounded-2xl border border-zinc-800 bg-black/20 p-4"
                  >
                    <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <span
                            className={`rounded-full border px-2.5 py-1 text-xs ${severityClass(
                              event.severity,
                            )}`}
                          >
                            {event.severity}
                          </span>

                          <span className="rounded-full border border-zinc-700 bg-zinc-900 px-2.5 py-1 text-xs text-zinc-300">
                            {event.subsystem}
                          </span>

                          <span className="rounded-full border border-zinc-700 bg-zinc-900 px-2.5 py-1 text-xs text-zinc-300">
                            {eventTypeLabel(event.event_type)}
                          </span>

                          {event.repeat_count > 1 ? (
                            <span className="rounded-full border border-cyan-500/40 bg-cyan-500/10 px-2.5 py-1 text-xs text-cyan-200">
                              repeated ×{event.repeat_count}
                            </span>
                          ) : null}
                        </div>

                        <h3 className="mt-3 font-medium text-zinc-100">
                          {event.message}
                        </h3>

                        <p className="mt-1 text-sm text-zinc-400">
                          Node: {event.node} · Source: {event.source}
                        </p>

                        {event.repeat_count > 1 ? (
                          <p className="mt-2 text-xs text-zinc-500">
                            First seen: {formatTime(event.first_seen)} · Latest:{" "}
                            {formatTime(event.latest_seen)}
                          </p>
                        ) : null}

                        {operationalImpact(event) ? (
                          <p className="mt-3 rounded-lg border border-zinc-700 bg-zinc-950/70 p-3 text-xs leading-5 text-zinc-300">
                            {operationalImpact(event)}
                          </p>
                        ) : null}
                      </div>

                      <p className="shrink-0 text-sm text-zinc-500">
                        {formatTime(event.latest_seen)}
                      </p>
                    </div>

                    <details className="mt-4">
                      <summary className="cursor-pointer text-xs font-medium text-zinc-400 hover:text-zinc-200">
                        Latest evidence
                        {event.repeat_count > 1
                          ? ` · ${event.repeat_count} matching events compacted`
                          : ""}
                      </summary>

                      <div className="mt-3">
                        <EvidenceBlock evidence={event.evidence} />
                      </div>
                    </details>
                  </article>
                ))
              )}
            </div>
          </div>

          <aside className="flex flex-col gap-4">
            <section className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-5">
              <h2 className="text-lg font-semibold">Current Runtime State</h2>
              <p className="mt-1 text-sm text-zinc-400">
                Live subsystem state from Orion's normalized system snapshot.
              </p>

              <div className="mt-4 rounded-xl border border-zinc-800 bg-black/20 p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-medium text-zinc-100">
                    Irrigation
                  </p>

                  <span
                    className={`rounded-full border px-2 py-0.5 text-xs ${
                      sprinklerRunning
                        ? "border-cyan-500/50 bg-cyan-500/10 text-cyan-200"
                        : "border-zinc-700 bg-zinc-900 text-zinc-300"
                    }`}
                  >
                    {sprinklerRunning ? "Running" : "Idle"}
                  </span>
                </div>

                <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                  <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-2">
                    <p className="text-zinc-500">Zone</p>
                    <p className="mt-1 text-zinc-200">{sprinklerZone}</p>
                  </div>

                  <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-2">
                    <p className="text-zinc-500">Mode</p>
                    <p className="mt-1 text-zinc-200">{sprinklerMode}</p>
                  </div>
                </div>

                <p className="mt-3 text-xs text-zinc-500">
                  Automation mode: {systemData?.automation_mode ?? "unknown"}
                </p>
              </div>
            </section>

            <section className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-5">
              <h2 className="text-lg font-semibold">Active Faults</h2>
              <p className="mt-1 text-sm text-zinc-400">
                Warnings, critical faults, offline nodes, and blocked policies.
              </p>

              <div className="mt-4 flex flex-col gap-3">
                {activeFaults.length === 0 ? (
                  <p className="rounded-xl border border-zinc-800 bg-black/20 p-3 text-sm text-zinc-500">
                    No active faults detected.
                  </p>
                ) : (
                  activeFaults.slice(0, 6).map((event) => (
                    <div
                      key={event.id}
                      className="rounded-xl border border-zinc-800 bg-black/20 p-3"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span
                          className={`rounded-full border px-2 py-0.5 text-xs ${severityClass(
                            event.severity,
                          )}`}
                        >
                          {event.severity}
                        </span>
                        <span className="text-xs text-zinc-500">
                          {event.subsystem}
                        </span>
                      </div>

                      <p className="mt-2 text-sm text-zinc-200">
                        {event.message}
                      </p>

                      {operationalImpact(event) ? (
                        <p className="mt-2 text-xs leading-5 text-zinc-400">
                          {operationalImpact(event)}
                        </p>
                      ) : null}
                    </div>
                  ))
                )}
              </div>
            </section>

            <section className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-5">
              <h2 className="text-lg font-semibold">Node Health</h2>
              <p className="mt-1 text-sm text-zinc-400">
                Latest event observed per node.
              </p>

              <div className="mt-4 flex flex-col gap-3">
                {nodeHealth.length === 0 ? (
                  <p className="rounded-xl border border-zinc-800 bg-black/20 p-3 text-sm text-zinc-500">
                    No node events yet.
                  </p>
                ) : (
                  nodeHealth.map((event) => (
                    <div
                      key={event.node}
                      className="rounded-xl border border-zinc-800 bg-black/20 p-3"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-sm font-medium text-zinc-100">
                          {event.node}
                        </p>

                        <span
                          className={`rounded-full border px-2 py-0.5 text-xs ${severityClass(
                            event.severity,
                          )}`}
                        >
                          {event.severity}
                        </span>
                      </div>

                      <p className="mt-1 text-xs text-zinc-500">
                        Last seen: {formatTime(event.timestamp)}
                      </p>
                    </div>
                  ))
                )}
              </div>
            </section>

            <section className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-5">
              <h2 className="text-lg font-semibold">State Transitions</h2>
              <p className="mt-1 text-sm text-zinc-400">
                Recent subsystem state changes and execution transitions.
              </p>

              <div className="mt-4 flex flex-col gap-3">
                {transitionEvents.length === 0 ? (
                  <p className="rounded-xl border border-zinc-800 bg-black/20 p-3 text-sm text-zinc-500">
                    No state transitions yet.
                  </p>
                ) : (
                  transitionEvents.slice(0, 6).map((event) => {
                    const fromState =
                      typeof event.evidence?.from_state === "string"
                        ? event.evidence.from_state
                        : "unknown";

                    const toState =
                      typeof event.evidence?.to_state === "string"
                        ? event.evidence.to_state
                        : "unknown";

                    return (
                      <div
                        key={event.id}
                        className="rounded-xl border border-zinc-800 bg-black/20 p-3"
                      >
                        <p className="text-sm font-medium text-zinc-100">
                          {event.subsystem}
                        </p>
                        <p className="mt-1 text-sm text-zinc-300">
                          {fromState} → {toState}
                        </p>
                        <p className="mt-1 text-xs text-zinc-500">
                          {event.message}
                        </p>
                      </div>
                    );
                  })
                )}
              </div>
            </section>

            <section className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-5">
              <h2 className="text-lg font-semibold">Automation Policies</h2>
              <p className="mt-1 text-sm text-zinc-400">
                Safety, weather, and control-policy decisions.
              </p>

              <div className="mt-4 flex flex-col gap-3">
                {policyEvents.length === 0 ? (
                  <p className="rounded-xl border border-zinc-800 bg-black/20 p-3 text-sm text-zinc-500">
                    No policy events yet.
                  </p>
                ) : (
                  policyEvents.slice(0, 6).map((event) => (
                    <div
                      key={event.id}
                      className="rounded-xl border border-zinc-800 bg-black/20 p-3"
                    >
                      <p className="text-sm text-zinc-200">{event.message}</p>
                      <p className="mt-1 text-xs text-zinc-500">
                        {eventTypeLabel(event.event_type)} · {event.subsystem}
                      </p>
                    </div>
                  ))
                )}
              </div>
            </section>
          </aside>
        </section>
      </div>
    </main>
  );
}
