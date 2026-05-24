"use client";

import { getBackendUrl } from "../lib/backend";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

const BACKEND_URL = getBackendUrl();

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

type SystemState = {
  weather?: WeatherState;
  environment?: any;
  sprinkler?: any;
  irrigation_schedule?: any;
};

function displayValue(value: unknown, fallback = "—") {
  if (value === null || value === undefined || value === "") return fallback;
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}

function formatTemp(value?: number | null) {
  return Number.isFinite(value) ? `${Number(value).toFixed(1)}°F` : "—";
}

function formatPercent(value?: number | null) {
  return Number.isFinite(value) ? `${Number(value).toFixed(0)}%` : "—";
}

function formatHumidity(value?: number | null) {
  return Number.isFinite(value) ? `${Number(value).toFixed(1)}%` : "—";
}

function formatWind(value?: number | null) {
  return Number.isFinite(value) ? `${Number(value).toFixed(1)} mph` : "—";
}

function formatPrecip(value?: number | null) {
  return Number.isFinite(value) ? `${Number(value).toFixed(2)} in` : "—";
}

function formatUpdated(value?: number | null) {
  if (!Number.isFinite(value)) return "Waiting for update";

  const timestamp = Number(value);
  const ms = timestamp > 1_000_000_000_000 ? timestamp : timestamp * 1000;
  const diff = Math.max(0, Date.now() - ms);

  if (diff < 5000) return "Just now";

  const seconds = Math.round(diff / 1000);
  if (seconds < 60) return `${seconds}s ago`;

  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.round(minutes / 60);
  return `${hours}h ago`;
}

function formatJson(value: unknown) {
  try {
    return JSON.stringify(value ?? {}, null, 2);
  } catch {
    return String(value);
  }
}

function Card({
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

function Field({
  label,
  value,
}: {
  label: string;
  value: unknown;
}) {
  return (
    <div className="rounded-2xl border border-neutral-800 bg-neutral-950 p-4">
      <p className="text-xs uppercase tracking-[0.18em] text-neutral-500">
        {label}
      </p>
      <p className="mt-2 break-words text-lg font-semibold text-white">
        {displayValue(value)}
      </p>
    </div>
  );
}

export default function WeatherPage() {
  const [system, setSystem] = useState<SystemState | null>(null);
  const [error, setError] = useState("");

  async function loadSystem() {
    try {
      const res = await fetch(`${BACKEND_URL}/v1/system/decision`, {
        cache: "no-store",
      });

      if (!res.ok) throw new Error(`Backend returned ${res.status}`);

      const data = await res.json();
      setSystem(data);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load weather");
    }
  }

  useEffect(() => {
    loadSystem();
    const timer = setInterval(loadSystem, 3000);
    return () => clearInterval(timer);
  }, []);

  const weather = system?.weather || {};
  const environment = system?.environment || {};

  const rainChance = Number(weather.rain_chance ?? 0);

  const status = useMemo(() => {
    if (weather.online === false) return "Offline";
    if (rainChance >= 70) return "Rain likely";
    if (rainChance >= 40) return "Rain possible";
    return weather.condition || "Online";
  }, [weather.online, weather.condition, rainChance]);

  const statusClass =
    weather.online === false
      ? "bg-red-500/10 text-red-300 ring-1 ring-red-500/30"
      : rainChance >= 40
        ? "bg-amber-500/10 text-amber-300 ring-1 ring-amber-500/30"
        : "bg-emerald-500/10 text-emerald-300 ring-1 ring-emerald-500/30";

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
              Orion Weather Node
            </p>

            <h1 className="mt-2 text-4xl font-semibold tracking-tight text-white">
              Weather Intelligence
            </h1>

            <p className="mt-2 max-w-3xl text-neutral-400">
              Dedicated weather detail page for outdoor conditions, rain
              probability, forecast context, irrigation impact, and environmental
              decision support.
            </p>
          </div>

          <div className={`rounded-full px-4 py-2 text-sm font-semibold ${statusClass}`}>
            {status}
          </div>
        </div>

        {error ? (
          <div className="mb-6 rounded-2xl border border-red-500/30 bg-red-500/10 p-4 text-red-200">
            {error}
          </div>
        ) : null}

        <div className="grid gap-4 md:grid-cols-4">
          <Card
            label="Temperature"
            value={formatTemp(weather.temp)}
            sub={weather.location || "Outdoor reading"}
          />
          <Card
            label="Feels Like"
            value={formatTemp(weather.feels_like)}
            sub="Heat index / apparent temp"
          />
          <Card
            label="Rain Chance"
            value={formatPercent(weather.rain_chance)}
            sub={rainChance >= 70 ? "Irrigation delay likely" : "Monitoring"}
          />
          <Card
            label="Humidity"
            value={formatHumidity(weather.humidity)}
            sub="Outdoor humidity"
          />
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_1fr]">
          <section className="rounded-2xl border border-neutral-800 bg-neutral-950 p-5 shadow-lg">
            <h2 className="text-xl font-semibold">Current Conditions</h2>
            <p className="mt-1 text-sm text-neutral-500">
              Live weather data used by Orion automation logic.
            </p>

            <div className="mt-5 grid grid-cols-2 gap-3">
              <Field label="Online" value={weather.online !== false} />
              <Field label="Condition" value={weather.condition} />
              <Field label="Wind" value={formatWind(weather.wind_mph)} />
              <Field label="Precipitation" value={formatPrecip(weather.precip_in)} />
              <Field label="Updated" value={formatUpdated(weather.updated_at)} />
              <Field
                label="Cache Age"
                value={
                  Number.isFinite(weather.cache_age_seconds)
                    ? `${weather.cache_age_seconds}s`
                    : "—"
                }
              />
            </div>

            {weather.error ? (
              <div className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
                {weather.error}
              </div>
            ) : null}
          </section>

          <section className="rounded-2xl border border-neutral-800 bg-neutral-950 p-5 shadow-lg">
            <h2 className="text-xl font-semibold">Automation Impact</h2>
            <p className="mt-1 text-sm text-neutral-500">
              How weather affects irrigation and environmental decisions.
            </p>

            <div className="mt-5 grid gap-3">
              <Field label="Recommendation" value={environment.recommendation} />
              <Field label="Confidence" value={environment.confidence} />
              <Field
                label="Heat Stress"
                value={environment.inputs?.heat_stress}
              />
              <Field
                label="Lawn Analysis"
                value={
                  environment.inputs?.lawn_analysis_available === false
                    ? "Unavailable / low light"
                    : "Available"
                }
              />
            </div>

            <div className="mt-4 rounded-xl border border-neutral-800 bg-neutral-900 p-4 text-sm leading-6 text-neutral-300">
              {environment.reason ||
                "No environmental recommendation is currently available."}
            </div>
          </section>
        </div>

        <section className="mt-6 rounded-2xl border border-neutral-800 bg-neutral-950 p-5 shadow-lg">
          <h2 className="text-xl font-semibold">Today’s Forecast</h2>
          <p className="mt-1 text-sm text-neutral-500">
            Forecast context used for outdoor automation.
          </p>

          <div className="mt-5 grid gap-3 md:grid-cols-4">
            <Field label="Date" value={weather.forecast_today?.date} />
            <Field label="High" value={formatTemp(weather.forecast_today?.max_temp)} />
            <Field label="Low" value={formatTemp(weather.forecast_today?.min_temp)} />
            <Field
              label="Sunrise / Sunset"
              value={`${weather.forecast_today?.sunrise || "—"} / ${
                weather.forecast_today?.sunset || "—"
              }`}
            />
          </div>
        </section>

        <section className="mt-6 rounded-2xl border border-neutral-800 bg-neutral-950 p-5 shadow-lg">
          <details>
            <summary className="cursor-pointer text-sm font-semibold text-neutral-300">
              Raw weather JSON
            </summary>
            <pre className="mt-4 max-h-96 overflow-auto rounded-xl bg-black p-4 text-xs leading-5 text-neutral-300">
              {formatJson(weather)}
            </pre>
          </details>
        </section>
      </div>
    </main>
  );
}
