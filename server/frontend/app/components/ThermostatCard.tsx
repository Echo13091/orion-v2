"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type Thermostat = {
  id: string;
  name?: string;
  vendor?: string;
  model?: string;
  online?: boolean;
  status?: string;
  temperature?: number | null;
  humidity?: number | null;
  target_setpoint?: number | null;
  cool_setpoint?: number | null;
  heat_setpoint?: number | null;
  mode?: string;
  fan_mode?: string;
  equipment_state?: string;
  heating?: boolean;
  cooling?: boolean;
  fan_active?: boolean;
  last_update_age_seconds?: number | null;
  fault?: boolean;
  fault_code?: string;
  fault_message?: string;
};

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "";

function displayTemp(value?: number | null) {
  if (value === null || value === undefined) return "—";
  return `${Number(value).toFixed(1)}°F`;
}

function displayValue(value?: string | number | null) {
  if (value === null || value === undefined || value === "") return "—";
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

export default function ThermostatCard() {
  const [thermostat, setThermostat] = useState<Thermostat | null>(null);
  const [error, setError] = useState<string>("");

  async function loadThermostat() {
    try {
      const res = await fetch(`${BACKEND_URL}/v1/thermostats`, {
        cache: "no-store",
      });

      if (!res.ok) {
        throw new Error(`Backend returned ${res.status}`);
      }

      const data = await res.json();
      const first = data?.thermostats?.[0] || null;

      setThermostat(first);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load thermostat");
    }
  }

  useEffect(() => {
    loadThermostat();
    const timer = setInterval(loadThermostat, 5000);
    return () => clearInterval(timer);
  }, []);

  const id = thermostat?.id || "t6pro_living_room";
  const online = Boolean(thermostat?.online);
  const fault = Boolean(thermostat?.fault);
  const status = thermostat?.status || "offline";

  return (
    <section className="rounded-2xl border border-neutral-800 bg-neutral-950/80 p-5 shadow-lg">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-neutral-500">
            Thermostat
          </p>
          <h2 className="mt-1 text-xl font-semibold text-white">
            {thermostat?.name || "Honeywell T6 Pro"}
          </h2>
          <p className="mt-1 text-sm text-neutral-400">
            {thermostat?.vendor || "Honeywell Home / Resideo"} ·{" "}
            {thermostat?.model || "T6 Pro"}
          </p>
        </div>

        <span
          className={[
            "rounded-full px-3 py-1 text-xs font-medium",
            online && !fault
              ? "bg-emerald-500/10 text-emerald-300 ring-1 ring-emerald-500/30"
              : "bg-red-500/10 text-red-300 ring-1 ring-red-500/30",
          ].join(" ")}
        >
          {online && !fault ? "Online" : "Fault"}
        </span>
      </div>

      {error ? (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
          {error}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-xl bg-neutral-900 p-4">
              <p className="text-xs text-neutral-500">Room Temp</p>
              <p className="mt-1 text-2xl font-semibold text-white">
                {displayTemp(thermostat?.temperature)}
              </p>
            </div>

            <div className="rounded-xl bg-neutral-900 p-4">
              <p className="text-xs text-neutral-500">Target</p>
              <p className="mt-1 text-2xl font-semibold text-white">
                {displayTemp(
                  thermostat?.target_setpoint ??
                    thermostat?.cool_setpoint ??
                    thermostat?.heat_setpoint
                )}
              </p>
            </div>

            <div className="rounded-xl bg-neutral-900 p-4">
              <p className="text-xs text-neutral-500">Mode</p>
              <p className="mt-1 text-lg font-medium capitalize text-white">
                {displayValue(thermostat?.mode)}
              </p>
            </div>

            <div className="rounded-xl bg-neutral-900 p-4">
              <p className="text-xs text-neutral-500">Equipment</p>
              <p className="mt-1 text-lg font-medium capitalize text-white">
                {displayValue(thermostat?.equipment_state)}
              </p>
            </div>
          </div>

          <div className="mt-4 rounded-xl border border-neutral-800 bg-neutral-900/70 p-3">
            <div className="flex items-center justify-between text-sm">
              <span className="text-neutral-400">Status</span>
              <span className="capitalize text-neutral-100">{status}</span>
            </div>
            <div className="mt-2 flex items-center justify-between text-sm">
              <span className="text-neutral-400">Last update</span>
              <span className="text-neutral-100">
                {ageLabel(thermostat?.last_update_age_seconds)}
              </span>
            </div>
            {thermostat?.fault_message ? (
              <p className="mt-3 rounded-lg bg-red-500/10 p-2 text-xs text-red-200">
                {thermostat.fault_message}
              </p>
            ) : null}
          </div>
        </>
      )}

      <Link
        href={`/thermostats/${id}`}
        className="mt-4 inline-flex w-full items-center justify-center rounded-xl bg-white px-4 py-3 text-sm font-semibold text-black transition hover:bg-neutral-200"
      >
        View Thermostat
      </Link>
    </section>
  );
}
