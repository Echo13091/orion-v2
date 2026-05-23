"use client";

import { getBackendUrl } from "../../lib/backend";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

type Thermostat = {
  id: string;
  name?: string;
  type?: string;
  vendor?: string;
  model?: string;
  source?: string;
  online?: boolean;
  status?: string;
  temperature?: number | null;
  humidity?: number | null;
  cool_setpoint?: number | null;
  heat_setpoint?: number | null;
  target_setpoint?: number | null;
  mode?: string;
  fan_mode?: string;
  equipment_state?: string;
  heating?: boolean;
  cooling?: boolean;
  fan_active?: boolean;
  hold?: string | null;
  battery?: number | null;
  last_update?: number | null;
  last_update_age_seconds?: number | null;
  fault?: boolean;
  fault_code?: string;
  fault_message?: string;
  supervisory_control_enabled?: boolean;
  last_command?: {
    timestamp?: number;
    action?: string;
    setpoint?: number;
    mode?: string;
    source?: string;
    reason?: string;
    executed?: boolean;
    execution_status?: string;
    message?: string;
  } | null;
};

type EventRecord = {
  timestamp: number;
  thermostat_id: string;
  event: string;
  severity: string;
  message: string;
  details?: Record<string, unknown>;
};

const BACKEND_URL = getBackendUrl();

function displayTemp(value?: number | null) {
  if (value === null || value === undefined) return "—";
  return `${Number(value).toFixed(1)}°F`;
}

function displayPercent(value?: number | null) {
  if (value === null || value === undefined) return "—";
  return `${Number(value).toFixed(0)}%`;
}

function displayValue(value?: string | number | boolean | null) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}

function ageLabel(seconds?: number | null) {
  if (seconds === null || seconds === undefined) return "Never";
  if (seconds < 5) return "Just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}

function formatTime(epoch?: number | null) {
  if (!epoch) return "—";
  return new Date(epoch * 1000).toLocaleString();
}

function StatCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="rounded-2xl border border-neutral-800 bg-neutral-950 p-5 shadow-lg">
      <p className="text-xs uppercase tracking-[0.18em] text-neutral-500">
        {label}
      </p>
      <p className="mt-2 text-3xl font-semibold text-white">{value}</p>
      {sub ? <p className="mt-1 text-sm text-neutral-400">{sub}</p> : null}
    </div>
  );
}

function DetailRow({
  label,
  value,
}: {
  label: string;
  value: string | number | boolean | null | undefined;
}) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-neutral-800 py-3 last:border-b-0">
      <span className="text-sm text-neutral-400">{label}</span>
      <span className="text-right text-sm font-medium text-neutral-100">
        {displayValue(value)}
      </span>
    </div>
  );
}

export default function ThermostatDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const thermostatId = params.id;

  const [thermostat, setThermostat] = useState<Thermostat | null>(null);
  const [events, setEvents] = useState<EventRecord[]>([]);
  const [error, setError] = useState("");
  const [setpoint, setSetpoint] = useState("73");
  const [mode, setMode] = useState("cool");
  const [commandStatus, setCommandStatus] = useState("");

  const activeState = useMemo(() => {
    if (thermostat?.cooling) return "Cooling";
    if (thermostat?.heating) return "Heating";
    if (thermostat?.fan_active) return "Fan Only";
    return "Idle";
  }, [thermostat]);

  async function loadThermostat() {
    try {
      const res = await fetch(`${BACKEND_URL}/v1/thermostats/${thermostatId}`, {
        cache: "no-store",
      });

      if (!res.ok) {
        throw new Error(`Backend returned ${res.status}`);
      }

      const data = await res.json();
      setThermostat(data.thermostat);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load thermostat");
    }
  }

  async function loadEvents() {
    try {
      const res = await fetch(`${BACKEND_URL}/v1/thermostats/events?limit=20`, {
        cache: "no-store",
      });

      if (!res.ok) return;

      const data = await res.json();
      setEvents(data.events || []);
    } catch {
      // Do not block page rendering on events.
    }
  }

  async function sendSetpointRequest() {
    setCommandStatus("Sending command request...");

    try {
      const res = await fetch(
        `${BACKEND_URL}/v1/thermostats/${thermostatId}/setpoint`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            setpoint: Number(setpoint),
            mode,
            source: "orion_dashboard",
            reason: "Manual request from Orion thermostat detail page",
          }),
        }
      );

      const data = await res.json();

      if (!res.ok || !data.ok) {
        throw new Error(data.message || data.error || "Command rejected");
      }

      setCommandStatus(
        data.command?.message ||
          "Command recorded. Real thermostat write integration pending."
      );

      await loadThermostat();
      await loadEvents();
    } catch (err) {
      setCommandStatus(
        err instanceof Error ? err.message : "Unable to send command request"
      );
    }
  }

  useEffect(() => {
    loadThermostat();
    loadEvents();

    const timer = setInterval(() => {
      loadThermostat();
      loadEvents();
    }, 5000);

    return () => clearInterval(timer);
  }, [thermostatId]);

  const online = Boolean(thermostat?.online);
  const fault = Boolean(thermostat?.fault);

  return (
    <main className="min-h-screen bg-black px-6 py-8 text-white">
      <div className="mx-auto max-w-6xl">
        <div className="mb-6 flex flex-col justify-between gap-4 md:flex-row md:items-end">
          <div>
            <Link
              href="/"
              className="text-sm font-medium text-neutral-400 hover:text-white"
            >
              ← Back to Orion Dashboard
            </Link>

            <p className="mt-6 text-xs uppercase tracking-[0.25em] text-neutral-500">
              Orion Thermostat Node
            </p>

            <h1 className="mt-2 text-4xl font-semibold tracking-tight text-white">
              {thermostat?.name || "Living Room Thermostat"}
            </h1>

            <p className="mt-2 max-w-3xl text-neutral-400">
              Supervisory HVAC telemetry and command logging for Orion thermostat
              nodes. Orion monitors equipment state, faults, setpoints, and
              operator commands across the current RPi4 / ESP32 HVAC controller
              and future Honeywell T6 Pro integration.
            </p>
          </div>

          <div
            className={[
              "rounded-full px-4 py-2 text-sm font-semibold",
              online && !fault
                ? "bg-emerald-500/10 text-emerald-300 ring-1 ring-emerald-500/30"
                : "bg-red-500/10 text-red-300 ring-1 ring-red-500/30",
            ].join(" ")}
          >
            {online && !fault ? "Online" : "Fault / Offline"}
          </div>
        </div>

        {error ? (
          <div className="mb-6 rounded-2xl border border-red-500/30 bg-red-500/10 p-4 text-red-200">
            {error}
          </div>
        ) : null}

        <div className="grid gap-4 md:grid-cols-4">
          <StatCard
            label="Room Temp"
            value={displayTemp(thermostat?.temperature)}
            sub="Live thermostat reading"
          />
          <StatCard
            label="Target"
            value={displayTemp(
              thermostat?.target_setpoint ??
                thermostat?.cool_setpoint ??
                thermostat?.heat_setpoint
            )}
            sub="Current control target"
          />
          <StatCard
            label="Humidity"
            value={displayPercent(thermostat?.humidity)}
            sub="Indoor humidity"
          />
          <StatCard
            label="Equipment"
            value={activeState}
            sub={`Mode: ${displayValue(thermostat?.mode)}`}
          />
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <section className="rounded-2xl border border-neutral-800 bg-neutral-950 p-5 shadow-lg">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="text-xl font-semibold">Thermostat State</h2>
                <p className="text-sm text-neutral-500">
                  Normalized Orion device model
                </p>
              </div>
              <span className="rounded-full bg-neutral-900 px-3 py-1 text-xs text-neutral-300">
                {displayValue(thermostat?.source)}
              </span>
            </div>

            <DetailRow label="Device ID" value={thermostat?.id} />
            <DetailRow label="Vendor" value={thermostat?.vendor} />
            <DetailRow label="Model" value={thermostat?.model} />
            <DetailRow label="Status" value={thermostat?.status} />
            <DetailRow label="Mode" value={thermostat?.mode} />
            <DetailRow label="Fan Mode" value={thermostat?.fan_mode} />
            <DetailRow label="Equipment State" value={thermostat?.equipment_state} />
            <DetailRow label="Cooling Active" value={thermostat?.cooling} />
            <DetailRow label="Heating Active" value={thermostat?.heating} />
            <DetailRow label="Fan Active" value={thermostat?.fan_active} />
            <DetailRow label="Cool Setpoint" value={displayTemp(thermostat?.cool_setpoint)} />
            <DetailRow label="Heat Setpoint" value={displayTemp(thermostat?.heat_setpoint)} />
            <DetailRow label="Last Update" value={ageLabel(thermostat?.last_update_age_seconds)} />
            <DetailRow label="Fault Code" value={thermostat?.fault_code || "None"} />

            {thermostat?.fault_message ? (
              <div className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
                {thermostat.fault_message}
              </div>
            ) : null}
          </section>

          <section className="rounded-2xl border border-neutral-800 bg-neutral-950 p-5 shadow-lg">
            <div>
              <h2 className="text-xl font-semibold">Setpoint Command</h2>
              <p className="mt-1 text-sm text-neutral-500">
                Safe command logging is active. Orion records operator setpoint
                requests before live thermostat write integration is enabled.
              </p>
            </div>

            <div className="mt-5 grid gap-4">
              <label className="grid gap-2">
                <span className="text-sm text-neutral-400">Target Setpoint</span>
                <input
                  value={setpoint}
                  onChange={(event) => setSetpoint(event.target.value)}
                  type="number"
                  min="50"
                  max="90"
                  className="rounded-xl border border-neutral-700 bg-black px-4 py-3 text-white outline-none focus:border-white"
                />
              </label>

              <label className="grid gap-2">
                <span className="text-sm text-neutral-400">Mode</span>
                <select
                  value={mode}
                  onChange={(event) => setMode(event.target.value)}
                  className="rounded-xl border border-neutral-700 bg-black px-4 py-3 text-white outline-none focus:border-white"
                >
                  <option value="cool">Cool</option>
                  <option value="heat">Heat</option>
                  <option value="auto">Auto</option>
                  <option value="off">Off</option>
                </select>
              </label>

              <button
                onClick={sendSetpointRequest}
                className="rounded-xl bg-white px-4 py-3 font-semibold text-black transition hover:bg-neutral-200"
              >
                Send Setpoint Request
              </button>

              {commandStatus ? (
                <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-3 text-sm text-neutral-200">
                  {commandStatus}
                </div>
              ) : null}

              {thermostat?.last_command ? (
                <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-4">
                  <p className="text-sm font-semibold text-white">
                    Last Command
                  </p>
                  <p className="mt-2 text-sm text-neutral-400">
                    {thermostat.last_command.action} ·{" "}
                    {displayTemp(thermostat.last_command.setpoint)} ·{" "}
                    {thermostat.last_command.execution_status}
                  </p>
                  <p className="mt-2 text-xs text-neutral-500">
                    {thermostat.last_command.reason}
                  </p>
                </div>
              ) : null}
            </div>
          </section>
        </div>

        <section className="mt-6 rounded-2xl border border-neutral-800 bg-neutral-950 p-5 shadow-lg">
          <div className="mb-4">
            <h2 className="text-xl font-semibold">Thermostat Events</h2>
            <p className="text-sm text-neutral-500">
              Operational timeline for telemetry changes, faults, and command
              requests.
            </p>
          </div>

          {events.length === 0 ? (
            <p className="rounded-xl border border-neutral-800 bg-neutral-900 p-4 text-sm text-neutral-400">
              No thermostat events recorded yet.
            </p>
          ) : (
            <div className="space-y-3">
              {events.map((event, index) => (
                <div
                  key={`${event.timestamp}-${index}`}
                  className="rounded-xl border border-neutral-800 bg-neutral-900 p-4"
                >
                  <div className="flex flex-col justify-between gap-2 md:flex-row md:items-center">
                    <div>
                      <p className="font-medium text-white">{event.event}</p>
                      <p className="text-sm text-neutral-400">{event.message}</p>
                    </div>
                    <div className="text-left text-xs text-neutral-500 md:text-right">
                      <p>{event.severity}</p>
                      <p>{formatTime(event.timestamp)}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
