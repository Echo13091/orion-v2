"use client";

import { apiFetch } from "../lib/api";
import { getBackendUrl } from "../lib/backend";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

const BACKEND_URL = getBackendUrl();

type StatusState = "good" | "bad" | "warn" | "neutral" | "active";

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

function formatMode(value?: string | null) {
  if (!value) return "—";

  return value
    .replace(/[_-]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatPercent(value?: number | null) {
  return Number.isFinite(value) ? `${Number(value).toFixed(0)}%` : "—";
}

function formatTemp(value?: number | null) {
  return Number.isFinite(value) ? `${Number(value).toFixed(1)}°F` : "—";
}

function formatTime(value?: number | null) {
  if (!Number.isFinite(value)) return "—";

  const timestamp = Number(value);
  const ms = timestamp > 1_000_000_000_000 ? timestamp : timestamp * 1000;

  return new Date(ms).toLocaleString();
}

function formatJson(value: unknown) {
  try {
    return JSON.stringify(value ?? {}, null, 2);
  } catch {
    return String(value);
  }
}

function stateClasses(state: StatusState) {
  if (state === "good") return "bg-emerald-500/10 text-emerald-300 ring-1 ring-emerald-500/30";
  if (state === "bad") return "bg-red-500/10 text-red-300 ring-1 ring-red-500/30";
  if (state === "warn") return "bg-amber-500/10 text-amber-300 ring-1 ring-amber-500/30";
  if (state === "active") return "bg-blue-500/10 text-blue-300 ring-1 ring-blue-500/30";
  return "bg-neutral-800 text-neutral-300 ring-1 ring-neutral-700";
}

function Card({
  label,
  value,
  sub,
  state = "neutral",
}: {
  label: string;
  value: string;
  sub?: string;
  state?: StatusState;
}) {
  return (
    <div className="rounded-2xl border border-neutral-800 bg-neutral-950 p-5 shadow-lg">
      <p className="text-xs uppercase tracking-[0.18em] text-neutral-500">
        {label}
      </p>
      <p
        className={[
          "mt-2 text-3xl font-semibold",
          state === "good" ? "text-emerald-200" : "",
          state === "bad" ? "text-red-200" : "",
          state === "warn" ? "text-amber-200" : "",
          state === "active" ? "text-blue-200" : "",
          state === "neutral" ? "text-white" : "",
        ].join(" ")}
      >
        {value}
      </p>
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
  value: unknown;
  state?: StatusState;
}) {
  return (
    <div className="rounded-2xl border border-neutral-800 bg-neutral-950 p-4">
      <p className="text-xs uppercase tracking-[0.18em] text-neutral-500">
        {label}
      </p>
      <p
        className={[
          "mt-2 break-words text-lg font-semibold",
          state === "good" ? "text-emerald-200" : "",
          state === "bad" ? "text-red-200" : "",
          state === "warn" ? "text-amber-200" : "",
          state === "active" ? "text-blue-200" : "",
          state === "neutral" ? "text-white" : "",
        ].join(" ")}
      >
        {displayValue(value)}
      </p>
    </div>
  );
}

export default function DecisionCenterPage() {
  const [system, setSystem] = useState<any>(null);
  const [controlResult, setControlResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
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
      setError(err instanceof Error ? err.message : "Unable to load decision center");
    }
  }

  useEffect(() => {
    loadSystem();
    const timer = setInterval(loadSystem, 3000);
    return () => clearInterval(timer);
  }, []);

  const decision = system?.last_decision || {};
  const result = decision?.result || {};
  const environment = system?.environment || {};
  const weather = system?.weather || {};
  const sprinkler = system?.sprinkler || {};
  const thermostat = system?.thermostat || {};

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
        detail: `A system fault is present: ${system.fault}`,
        action: "observe",
        state: "bad" as StatusState,
        canApply: false,
        applyLabel: "Review fault",
      };
    }

    const rainChance = Number(weather?.rain_chance ?? 0);

    if (rainChance >= 70 && sprinkler?.running) {
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
        detail: `Rain chance is ${formatPercent(rainChance)}. Orion can skip the next irrigation run.`,
        action: "delay_irrigation",
        state: "warn" as StatusState,
        canApply: true,
        applyLabel: "Accept recommendation",
      };
    }

    if (thermostat?.cooling) {
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
  }, [system, weather, sprinkler, thermostat]);

  const executionStatus = useMemo(() => {
    const nested = result?.result || {};
    const blocked = Boolean(result?.blocked);
    const executed = Boolean(result?.executed);
    const ok = result?.ok ?? nested?.ok;

    if (blocked) return { label: "Blocked", state: "warn" as StatusState };
    if (executed && ok !== false) return { label: "Executed", state: "good" as StatusState };
    if (ok === false) return { label: "Failed", state: "bad" as StatusState };
    if (decision?.requires_execution) return { label: "Waiting", state: "neutral" as StatusState };

    return { label: "Monitoring Only", state: "active" as StatusState };
  }, [decision, result]);

  async function postControl(path: string, body: Record<string, unknown> = {}) {
    setLoading(true);

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

      setControlResult({
        ok: res.ok,
        status: res.status,
        response: data,
      });

      await loadSystem();
    } catch (err) {
      setControlResult({
        ok: false,
        error: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setLoading(false);
    }
  }

  async function applyRecommendation() {
    if (!recommendation.canApply || loading) return;

    if (recommendation.action === "stop_sprinkler") {
      await postControl("/v1/control/sprinkler/stop", {
        source: "decision_center",
        reason: recommendation.detail,
      });
      return;
    }

    if (recommendation.action === "delay_irrigation") {
      await postControl("/v1/control/sprinkler/skip", {
        source: "decision_center",
        reason: recommendation.detail,
      });
      return;
    }

    await postControl("/v1/control/ai/execute", {
      action: recommendation.action,
      source: "decision_center",
      state: system,
    });
  }

  async function setAutomationMode(mode: "manual" | "auto") {
    await postControl("/v1/control/ai/mode", { mode });
  }

  const aiActive = String(system?.ai_status || "").toLowerCase() === "active";
  const automationMode = system?.automation_mode || "manual";

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
              Orion Decision Center
            </p>

            <h1 className="mt-2 text-4xl font-semibold tracking-tight text-white">
              Supervisory Decision Engine
            </h1>

            <p className="mt-2 max-w-3xl text-neutral-400">
              Dedicated decision page for recommendations, safety gating,
              manual approval, execution state, and raw decision traces.
            </p>
          </div>

          <div className={`rounded-full px-4 py-2 text-sm font-semibold ${stateClasses(aiActive ? "good" : "neutral")}`}>
            {aiActive ? "AI Active" : "AI Standby"}
          </div>
        </div>

        {error ? (
          <div className="mb-6 rounded-2xl border border-red-500/30 bg-red-500/10 p-4 text-red-200">
            {error}
          </div>
        ) : null}

        <div className="grid gap-4 md:grid-cols-4">
          <Card
            label="Recommendation"
            value={recommendation.title}
            state={recommendation.state}
            sub="Current suggested action"
          />
          <Card
            label="Execution"
            value={executionStatus.label}
            state={executionStatus.state}
            sub="Hardware execution state"
          />
          <Card
            label="Approval Mode"
            value={automationMode === "auto" ? "Safety Gated" : "Manual"}
            state={automationMode === "auto" ? "active" : "neutral"}
            sub="Automated monitoring, gated execution"
          />
          <Card
            label="Faults"
            value={system?.fault ? "Fault Present" : "No Faults"}
            state={system?.fault ? "bad" : "good"}
            sub="System safety state"
          />
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <section className="rounded-2xl border border-neutral-800 bg-neutral-950 p-5 shadow-lg">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold">Current Recommendation</h2>
                <p className="mt-1 text-sm text-neutral-500">
                  Operator-facing recommendation based on live system telemetry.
                </p>
              </div>

              <div className={`rounded-full px-3 py-1 text-xs font-semibold ${stateClasses(recommendation.state)}`}>
                {formatMode(recommendation.action)}
              </div>
            </div>

            <div className="mt-5 rounded-2xl border border-neutral-800 bg-neutral-900 p-5">
              <h3 className="text-2xl font-semibold text-white">
                {recommendation.title}
              </h3>
              <p className="mt-3 text-sm leading-6 text-neutral-300">
                {recommendation.detail}
              </p>
            </div>

            {decision?.reason ? (
              <div className="mt-4 rounded-2xl border border-neutral-800 bg-black p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-neutral-500">
                  Decision Trace
                </p>
                <p className="mt-2 text-sm leading-6 text-neutral-300">
                  {decision.reason}
                </p>
              </div>
            ) : null}

            <div className="mt-5 flex flex-wrap gap-3">
              {recommendation.canApply ? (
                <button
                  type="button"
                  disabled={loading}
                  onClick={applyRecommendation}
                  className="rounded-xl bg-emerald-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {loading ? "Applying..." : recommendation.applyLabel}
                </button>
              ) : null}

              <button
                type="button"
                disabled={loading}
                onClick={() => loadSystem()}
                className="rounded-xl border border-neutral-700 bg-neutral-900 px-5 py-3 text-sm font-semibold text-neutral-100 transition hover:bg-neutral-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Refresh state
              </button>
            </div>
          </section>

          <section className="rounded-2xl border border-neutral-800 bg-neutral-950 p-5 shadow-lg">
            <h2 className="text-xl font-semibold">Execution Control</h2>
            <p className="mt-1 text-sm text-neutral-500">
              Switch between manual approval and automated monitoring mode. Hardware actions remain safety-gated.
            </p>

            <div className="mt-5 grid grid-cols-2 gap-3">
              <button
                type="button"
                disabled={loading}
                onClick={() => setAutomationMode("manual")}
                className={[
                  "rounded-xl px-4 py-3 text-sm font-semibold transition disabled:opacity-60",
                  automationMode === "manual"
                    ? "bg-blue-600 text-white"
                    : "border border-neutral-700 bg-neutral-900 text-neutral-100 hover:bg-neutral-800",
                ].join(" ")}
              >
                Manual
              </button>

              <button
                type="button"
                disabled={loading}
                onClick={() => setAutomationMode("auto")}
                className={[
                  "rounded-xl px-4 py-3 text-sm font-semibold transition disabled:opacity-60",
                  automationMode === "auto"
                    ? "bg-blue-600 text-white"
                    : "border border-neutral-700 bg-neutral-900 text-neutral-100 hover:bg-neutral-800",
                ].join(" ")}
              >Auto Monitor</button>
            </div>

            <div className="mt-5 grid grid-cols-2 gap-3">
              <Field label="System Action" value={decision?.action === "observe" ? "Monitor / no hardware command" : decision?.action || "Monitor / no hardware command"} />
              <Field label="Decision Source" value={decision?.source || "rules"} />
              <Field label="Requires Execution" value={decision?.requires_execution} />
              <Field label="Decision Time" value={formatTime(decision?.time)} />
              <Field label="Rain Chance" value={formatPercent(weather?.rain_chance)} state={Number(weather?.rain_chance ?? 0) >= 70 ? "warn" : "neutral"} />
              <Field label="Irrigation" value={sprinkler?.running ? "Running" : "Idle"} state={sprinkler?.running ? "active" : "neutral"} />
            </div>
          </section>
        </div>

        <section className="mt-6 rounded-2xl border border-neutral-800 bg-neutral-950 p-5 shadow-lg">
          <h2 className="text-xl font-semibold">Safety Context</h2>
          <p className="mt-1 text-sm text-neutral-500">
            Safety gating, manual override, and environmental constraints.
          </p>

          <div className="mt-5 grid gap-3 md:grid-cols-4">
            <Field
              label="Auto Execute Allowed"
              value={environment?.safety?.auto_execute_allowed}
              state={environment?.safety?.auto_execute_allowed ? "good" : "warn"}
            />
            <Field
              label="Requires Approval"
              value={environment?.safety?.requires_user_approval}
              state={environment?.safety?.requires_user_approval ? "warn" : "good"}
            />
            <Field
              label="Manual Override"
              value={system?.manual_override_until ? "Active" : "Inactive"}
              state={system?.manual_override_until ? "warn" : "neutral"}
            />
            <Field
              label="AI Status"
              value={system?.ai_status || "unknown"}
              state={aiActive ? "good" : "neutral"}
            />
          </div>

          <div className="mt-4 rounded-xl border border-neutral-800 bg-neutral-900 p-4 text-sm leading-6 text-neutral-300">
            {environment?.safety?.reason ||
              "No safety reason is currently available."}
          </div>
        </section>

        <section className="mt-6 rounded-2xl border border-neutral-800 bg-neutral-950 p-5 shadow-lg">
          <h2 className="text-xl font-semibold">Command Result</h2>
          <p className="mt-1 text-sm text-neutral-500">
            Last operator action from this page.
          </p>

          <pre className="mt-4 max-h-72 overflow-auto rounded-xl bg-black p-4 text-xs leading-5 text-neutral-300">
            {formatJson(controlResult || { message: "Awaiting operator approval. No hardware command has been sent." })}
          </pre>
        </section>

        <section className="mt-6 rounded-2xl border border-neutral-800 bg-neutral-950 p-5 shadow-lg">
          <details>
            <summary className="cursor-pointer text-sm font-semibold text-neutral-300">
              Raw decision JSON
            </summary>
            <pre className="mt-4 max-h-96 overflow-auto rounded-xl bg-black p-4 text-xs leading-5 text-neutral-300">
              {formatJson({
                last_decision: decision,
                result,
                environment,
                fault_status: system?.fault_status,
              })}
            </pre>
          </details>
        </section>
      </div>
    </main>
  );
}
