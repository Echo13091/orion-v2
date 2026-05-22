"use client";

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
};

type EventsResponse = {
  ok: boolean;
  count: number;
  active_fault_count: number;
  events: OrionEvent[];
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
  const [error, setError] = useState<string>("");
  const [selectedSubsystem, setSelectedSubsystem] = useState<string>("all");
  const [selectedSeverity, setSelectedSeverity] = useState<string>("all");

  async function loadEvents() {
    try {
      setError("");

      const response = await fetch(`${BACKEND_URL}/v1/events?limit=100`, {
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

  useEffect(() => {
    loadEvents();

    const timer = window.setInterval(loadEvents, 5000);

    return () => window.clearInterval(timer);
  }, []);

  const events = data?.events ?? [];

  const subsystems = useMemo(() => {
    return Array.from(new Set(events.map((event) => event.subsystem))).sort();
  }, [events]);

  const filteredEvents = useMemo(() => {
    return events.filter((event) => {
      const subsystemMatch =
        selectedSubsystem === "all" || event.subsystem === selectedSubsystem;

      const severityMatch =
        selectedSeverity === "all" || event.severity === selectedSeverity;

      return subsystemMatch && severityMatch;
    });
  }, [events, selectedSubsystem, selectedSeverity]);

  const activeFaults = useMemo(() => {
    return events.filter((event) => {
      return (
        event.severity === "warning" ||
        event.severity === "critical" ||
        event.event_type === "fault" ||
        event.event_type === "node_offline" ||
        event.event_type === "policy_block"
      );
    });
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

  return (
    <main className="min-h-screen bg-zinc-950 px-6 py-8 text-zinc-100">
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <header className="flex flex-col gap-2">
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
              </div>
            </div>

            <div className="flex flex-col gap-3">
              {filteredEvents.length === 0 ? (
                <div className="rounded-xl border border-zinc-800 bg-black/20 p-4 text-sm text-zinc-500">
                  No events found.
                </div>
              ) : (
                filteredEvents.map((event) => (
                  <article
                    key={event.id}
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
                        </div>

                        <h3 className="mt-3 font-medium text-zinc-100">
                          {event.message}
                        </h3>

                        <p className="mt-1 text-sm text-zinc-400">
                          Node: {event.node} · Source: {event.source}
                        </p>
                      </div>

                      <p className="shrink-0 text-sm text-zinc-500">
                        {formatTime(event.timestamp)}
                      </p>
                    </div>

                    <div className="mt-4">
                      <EvidenceBlock evidence={event.evidence} />
                    </div>
                  </article>
                ))
              )}
            </div>
          </div>

          <aside className="flex flex-col gap-4">
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
