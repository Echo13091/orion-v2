"use client";

import { apiFetch } from "../lib/api";
import { getBackendUrl } from "../lib/backend";
import Link from "next/link";
import { useEffect, useState } from "react";

const BACKEND_URL = getBackendUrl();

type SystemState = {
  sprinkler?: any;
  irrigation_schedule?: any;
  irrigation_runtime?: any;
  environment?: any;
};

function value(v: any, fallback = "—") {
  if (v === null || v === undefined || v === "") return fallback;
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function formatJson(v: any) {
  try {
    return JSON.stringify(v ?? {}, null, 2);
  } catch {
    return String(v);
  }
}

function formatZone(value: any) {
  const zone = Number(value);
  return Number.isFinite(zone) && zone >= 1 ? String(zone) : "—";
}

function formatSeconds(value: any) {
  const seconds = Number(value);
  if (!Number.isFinite(seconds) || seconds <= 0) return "—";
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${minutes}m ${rest}s`;
}

function statusClass(state: "good" | "warn" | "bad" | "active" | "neutral") {
  if (state === "good") return "border-emerald-500/40 bg-emerald-500/10 text-emerald-200";
  if (state === "warn") return "border-yellow-500/50 bg-yellow-500/10 text-yellow-200";
  if (state === "bad") return "border-red-500/40 bg-red-500/10 text-red-200";
  if (state === "active") return "border-blue-500/40 bg-blue-500/10 text-blue-200";
  return "border-neutral-700 bg-neutral-950 text-neutral-300";
}

function Field({
  label,
  value: fieldValue,
  state = "neutral",
}: {
  label: string;
  value: any;
  state?: "good" | "warn" | "bad" | "active" | "neutral";
}) {
  return (
    <div className="rounded-2xl border border-neutral-800 bg-neutral-950 p-4">
      <p className="text-xs uppercase tracking-[0.18em] text-neutral-500">
        {label}
      </p>
      <p className={`mt-2 break-words text-lg font-semibold ${state === "neutral" ? "text-white" : statusClass(state).split(" ").at(-1)}`}>
        {value(fieldValue)}
      </p>
    </div>
  );
}

function Pill({
  label,
  state = "neutral",
}: {
  label: string;
  state?: "good" | "warn" | "bad" | "active" | "neutral";
}) {
  return (
    <span className={`w-fit rounded-full border px-3 py-1 text-xs font-semibold ${statusClass(state)}`}>
      {label}
    </span>
  );
}

function formatSprinklerRecommendation(input?: string | null) {
  if (!input) return "No recommendation";
  const normalized = String(input).trim().toLowerCase();
  const labels: Record<string, string> = {
    delay_irrigation: "Delay irrigation",
    skip_irrigation: "Skip irrigation",
    run_irrigation: "Run irrigation",
    normal: "Normal operation",
    none: "No recommendation",
  };
  return labels[normalized] ?? normalized.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function SprinklerPage() {
  const [system, setSystem] = useState<SystemState | null>(null);
  const [error, setError] = useState("");

  async function loadSystem() {
    try {
      const res = await apiFetch(`${BACKEND_URL}/v1/system/decision`, {
        cache: "no-store",
      });

      if (!res.ok) throw new Error(`Backend returned ${res.status}`);

      const data = await res.json();
      setSystem(data);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load irrigation controller");
    }
  }

  useEffect(() => {
    loadSystem();
    const timer = setInterval(loadSystem, 3000);
    return () => clearInterval(timer);
  }, []);

  const sprinkler = system?.sprinkler || {};
  const raw = sprinkler.raw || sprinkler;
  const rain = sprinkler.rain_sensor || raw.rain_sensor || {};
  const schedule = sprinkler.schedule || raw.schedule || system?.irrigation_schedule || {};
  const environment = system?.environment || {};
  const wifi = sprinkler.wifi || raw.wifi || {};

  const online = sprinkler.online !== false && raw.online !== false;
  const running = Boolean(sprinkler.running || raw.running);
  const fault = Boolean(sprinkler.fault || raw.fault || raw.fault_latched);
  const rainWet = Boolean(rain.wet);
  const rainBlocksSchedule = Boolean(rain.blocks_schedule ?? sprinkler.rain_inhibit);
  const rainInhibit = Boolean(sprinkler.rain_inhibit || (rainWet && rainBlocksSchedule));
  const scheduleStatus = sprinkler.schedule_status || schedule.status || sprinkler.next_run || "—";
  const activeZone = sprinkler.zone ?? sprinkler.active_zone ?? raw.active_zone ?? raw.zone;

  const status = !online
    ? "Offline"
    : fault
      ? "Fault"
      : running
        ? "Running"
        : rainInhibit
          ? "Rain Inhibit"
          : "Idle";

  const statusState = !online || fault
    ? "bad"
    : running
      ? "active"
      : rainInhibit
        ? "warn"
        : "good";

  const controllerName = sprinkler.display_name || "Standalone Irrigation Controller";
  const controllerType = sprinkler.controller_type || "standalone_esp32_irrigation";

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

            <p className="mt-6 text-xs uppercase tracking-[0.25em] text-cyan-400">
              Orion Standalone Irrigation Node
            </p>

            <h1 className="mt-2 text-4xl font-semibold tracking-tight text-white">
              {controllerName}
            </h1>

            <p className="mt-2 max-w-3xl text-neutral-400">
              Dedicated detail page for the ESP32 standalone irrigation controller,
              live zone state, local schedule status, rain switch inhibit, Wi-Fi,
              time sync, and Orion supervisory context.
            </p>
          </div>

          <Pill label={status} state={statusState as any} />
        </div>

        {error ? (
          <div className="mb-6 rounded-2xl border border-red-500/30 bg-red-500/10 p-4 text-red-200">
            {error}
          </div>
        ) : null}

        <div className="grid gap-4 md:grid-cols-4">
          <Field label="Controller" value={controllerType.replaceAll("_", " ")} state={online ? "good" : "bad"} />
          <Field label="Run State" value={status} state={statusState as any} />
          <Field label="Active Zone" value={running ? formatZone(activeZone) : "—"} state={running ? "active" : "neutral"} />
          <Field label="Rain Sensor" value={rain.enabled === false ? "Disabled" : rainWet ? "Wet" : "Dry"} state={rainWet ? "warn" : "good"} />
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_1fr]">
          <section className="rounded-2xl border border-neutral-800 bg-neutral-950 p-5 shadow-lg">
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
              <div>
                <h2 className="text-xl font-semibold">Standalone Controller State</h2>
                <p className="mt-1 text-sm text-neutral-500">
                  Live normalized telemetry from the ESP32 controller.
                </p>
              </div>
              <Pill label={online ? "Online" : "Offline"} state={online ? "good" : "bad"} />
            </div>

            <div className="mt-5 grid grid-cols-2 gap-3">
              <Field label="Online" value={online} state={online ? "good" : "bad"} />
              <Field label="Running" value={running} state={running ? "active" : "neutral"} />
              <Field label="Remaining" value={formatSeconds(sprinkler.remaining_seconds ?? raw.remaining_seconds)} />
              <Field label="Schedule Status" value={scheduleStatus} state={String(scheduleStatus).includes("rain") ? "warn" : "neutral"} />
              <Field label="Rain Inhibit" value={rainInhibit} state={rainInhibit ? "warn" : "good"} />
              <Field label="Rain Raw High" value={rain.raw_high} />
              <Field label="Time Source" value={sprinkler.time_sync_source || raw.time_sync_source} />
              <Field label="Wi-Fi" value={wifi.status || "—"} state={wifi.status === "connected" ? "good" : "neutral"} />
            </div>

            {(sprinkler.fault_message || raw.fault_message || raw.error) && (
              <div className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
                {sprinkler.fault_message || raw.fault_message || raw.error}
              </div>
            )}
          </section>

          <section className="rounded-2xl border border-neutral-800 bg-neutral-950 p-5 shadow-lg">
            <h2 className="text-xl font-semibold">Orion Supervisory Context</h2>
            <p className="mt-1 text-sm text-neutral-500">
              Weather and policy context affecting irrigation decisions.
            </p>

            <div className="mt-5 grid gap-3">
              <Field label="Recommendation" value={formatSprinklerRecommendation(environment.recommendation)} />
              <Field label="Confidence" value={environment.confidence} />
              <Field
                label="Rain Probability"
                value={
                  environment.inputs?.rain_probability !== undefined
                    ? `${Math.round(environment.inputs.rain_probability * 100)}%`
                    : "—"
                }
              />
              <Field
                label="Safety"
                value={environment.safety?.reason || "Manual approval required"}
                state={environment.safety?.requires_user_approval ? "warn" : "good"}
              />
            </div>

            <div className="mt-4 rounded-xl border border-neutral-800 bg-neutral-900 p-4 text-sm text-neutral-300">
              {environment.reason ||
                "No environmental recommendation is currently available."}
            </div>
          </section>
        </div>

        <section className="mt-6 rounded-2xl border border-neutral-800 bg-neutral-950 p-5 shadow-lg">
          <h2 className="text-xl font-semibold">Local Schedule / Hardware Inhibit</h2>
          <p className="mt-1 text-sm text-neutral-500">
            The ESP32 controller owns local schedule execution. Orion supervises and displays inhibit state.
          </p>

          <div className="mt-5 grid gap-3 md:grid-cols-4">
            <Field label="Enabled" value={schedule.enabled} state={schedule.enabled ? "good" : "neutral"} />
            <Field label="Start Minute" value={schedule.start_minute} />
            <Field label="Valid" value={schedule.valid} state={schedule.valid ? "good" : "warn"} />
            <Field label="Last Run" value={schedule.last_run_utc_epoch || "—"} />
          </div>

          {rainInhibit ? (
            <div className="mt-4 rounded-xl border border-yellow-500/20 bg-yellow-500/10 px-4 py-3 text-sm text-yellow-100">
              Rain switch is wet. Scheduled watering is currently inhibited by controller hardware policy.
            </div>
          ) : null}
        </section>

        <section className="mt-6 rounded-2xl border border-neutral-800 bg-neutral-950 p-5 shadow-lg">
          <details>
            <summary className="cursor-pointer text-sm font-semibold text-neutral-300">
              Raw standalone irrigation JSON
            </summary>
            <pre className="mt-4 max-h-96 overflow-auto rounded-xl bg-black p-4 text-xs leading-5 text-neutral-300">
              {formatJson(sprinkler)}
            </pre>
          </details>
        </section>
      </div>
    </main>
  );
}
