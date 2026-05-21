"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "";

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

function tempStatusColor(ok: boolean) {
  return ok
    ? "bg-emerald-500/10 text-emerald-300 ring-1 ring-emerald-500/30"
    : "bg-red-500/10 text-red-300 ring-1 ring-red-500/30";
}

function formatJson(v: any) {
  try {
    return JSON.stringify(v ?? {}, null, 2);
  } catch {
    return String(v);
  }
}


function formatSprinklerRecommendation(value?: string | null) {
  if (!value) return "No recommendation";

  const normalized = String(value).trim().toLowerCase();

  const labels: Record<string, string> = {
    delay_irrigation: "Delay irrigation",
    skip_irrigation: "Skip irrigation",
    run_irrigation: "Run irrigation",
    normal: "Normal operation",
    none: "No recommendation",
  };

  return labels[normalized] ?? normalized.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatYesNo(value: unknown) {
  if (value === true) return "Yes";
  if (value === false) return "No";
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (["true", "yes", "online", "ok"].includes(normalized)) return "Yes";
    if (["false", "no", "offline", "fault"].includes(normalized)) return "No";
  }
  return String(value ?? "Unknown");
}

function Field({
  label,
  value: fieldValue,
}: {
  label: string;
  value: any;
}) {
  return (
    <div className="rounded-2xl border border-neutral-800 bg-neutral-950 p-4">
      <p className="text-xs uppercase tracking-[0.18em] text-neutral-500">
        {label}
      </p>
      <p className="mt-2 break-words text-lg font-semibold text-white">
        {value(fieldValue)}
      </p>
    </div>
  );
}

export default function SprinklerPage() {
  const [system, setSystem] = useState<SystemState | null>(null);
  const [error, setError] = useState("");

  async function loadSystem() {
    try {
      const res = await fetch(`${BACKEND_URL}/v1/system`, {
        cache: "no-store",
      });

      if (!res.ok) throw new Error(`Backend returned ${res.status}`);

      const data = await res.json();
      setSystem(data);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load sprinkler");
    }
  }

  useEffect(() => {
    loadSystem();
    const timer = setInterval(loadSystem, 3000);
    return () => clearInterval(timer);
  }, []);

  const sprinkler = system?.sprinkler || {};
  const raw = sprinkler.raw || sprinkler;
  const schedule = system?.irrigation_schedule || {};
  const environment = system?.environment || {};

  const online = sprinkler.online !== false && raw.online !== false;
  const running = Boolean(sprinkler.running || raw.running);
  const fault = Boolean(sprinkler.fault || raw.fault);

  const status = !online
    ? "Offline"
    : fault
      ? "Fault"
      : running
        ? "Running"
        : "Idle";

  const activeZone =
    sprinkler.zone ??
    sprinkler.active_zone ??
    raw.zone ??
    raw.active_zone ??
    raw.current_zone ??
    null;

  const nextRun =
    sprinkler.next_run ??
    raw.next_run ??
    schedule.next_run ??
    "No scheduled run";

  const relayZones = Array.isArray(raw.relay_zones)
    ? raw.relay_zones
    : Array.isArray(raw.zones)
      ? raw.zones
      : [];

  const activeRelays = relayZones.filter(Boolean).length;

  const timeline = Array.isArray(raw.timeline)
    ? raw.timeline
    : Array.isArray(schedule.timeline)
      ? schedule.timeline
      : [];

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
              Orion Sprinkler Node
            </p>

            <h1 className="mt-2 text-4xl font-semibold tracking-tight text-white">
              Irrigation Controller
            </h1>

            <p className="mt-2 max-w-3xl text-neutral-400">
              Dedicated irrigation detail page for controller state, zone timeline,
              relay feedback, schedule sync, weather-aware recommendations, and
              fault visibility.
            </p>
          </div>

          <div
            className={[
              "rounded-full px-4 py-2 text-sm font-semibold",
              tempStatusColor(online && !fault),
            ].join(" ")}
          >
            {status}
          </div>
        </div>

        {error ? (
          <div className="mb-6 rounded-2xl border border-red-500/30 bg-red-500/10 p-4 text-red-200">
            {error}
          </div>
        ) : null}

        <div className="grid gap-4 md:grid-cols-4">
          <Field label="Status" value={status} />
          <Field label="Active Zone" value={running ? activeZone : "None"} />
          <Field label="Next Run" value={nextRun} />
          <Field label="Relays Active" value={`${activeRelays} / 8 active`} />
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_1fr]">
          <section className="rounded-2xl border border-neutral-800 bg-neutral-950 p-5 shadow-lg">
            <h2 className="text-xl font-semibold">Controller State</h2>
            <p className="mt-1 text-sm text-neutral-500">
              Live normalized sprinkler controller telemetry.
            </p>

            <div className="mt-5 grid grid-cols-2 gap-3">
              <Field label="Online" value={online} />
              <Field label="Running" value={running} />
              <Field label="Mode" value={sprinkler.mode || raw.mode} />
              <Field label="Health" value={sprinkler.health || raw.health} />
              <Field label="Heartbeat" value={raw.heartbeat || raw.last_heartbeat_msg_age} />
              <Field label="Controller" value={schedule.controller || "sprinkler"} />
              <Field label="Next Cycle Skipped" value={schedule.skip_next_run} />
              <Field label="Rain Forecast Skip" value={schedule.skip_if_rain_likely} />
            </div>

            {(sprinkler.error || raw.fault_message) && (
              <div className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
                {sprinkler.error || raw.fault_message}
              </div>
            )}
          </section>

          <section className="rounded-2xl border border-neutral-800 bg-neutral-950 p-5 shadow-lg">
            <h2 className="text-xl font-semibold">Weather-Aware Decision</h2>
            <p className="mt-1 text-sm text-neutral-500">
              Orion environmental recommendation affecting irrigation.
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
              />
            </div>

            <div className="mt-4 rounded-xl border border-neutral-800 bg-neutral-900 p-4 text-sm text-neutral-300">
              {environment.reason ||
                "No environmental recommendation is currently available."}
            </div>
          </section>
        </div>

        <section className="mt-6 rounded-2xl border border-neutral-800 bg-neutral-950 p-5 shadow-lg">
          
          <div className="mb-4 rounded-xl border border-yellow-500/20 bg-yellow-500/10 px-4 py-3 text-sm text-yellow-100">
            Next scheduled cycle is currently held because rain probability is high.
          </div>
<h2 className="text-xl font-semibold">Upcoming Zone Timeline</h2>
          <p className="mt-1 text-sm text-neutral-500">
            Preview of the next irrigation cycle. Held cycles remain visible for operator review.
          </p>

          {timeline.length === 0 ? (
            <p className="mt-4 rounded-xl border border-neutral-800 bg-neutral-900 p-4 text-sm text-neutral-400">
              No timeline available.
            </p>
          ) : (
            <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {timeline.slice(0, 8).map((item: any, index: number) => (
                <div
                  key={`${item.zone}-${item.time}-${index}`}
                  className="rounded-xl border border-neutral-800 bg-neutral-900 p-4"
                >
                  <p className="text-xs uppercase tracking-[0.18em] text-neutral-500">
                    {item.time || item.start_label || "—"}
                  </p>
                  <p className="mt-2 text-lg font-semibold text-white">
                    Zone {value(item.zone, String(index + 1))}
                  </p>
                  <p className="mt-1 text-sm text-neutral-400">
                    {value(item.duration_minutes ?? item.duration)} min
                    {item.end_label ? ` · ends ${item.end_label}` : ""}
                  </p>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="mt-6 rounded-2xl border border-neutral-800 bg-neutral-950 p-5 shadow-lg">
          <details>
            <summary className="cursor-pointer text-sm font-semibold text-neutral-300">
              Raw sprinkler JSON
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
