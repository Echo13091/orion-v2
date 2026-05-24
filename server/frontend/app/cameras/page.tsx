"use client";

import { apiFetch } from "../lib/api";
import { getBackendUrl } from "../lib/backend";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

const BACKEND_URL = getBackendUrl();

type StatusState = "good" | "bad" | "warn" | "neutral" | "active";

function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
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

function displayValue(value: unknown, fallback = "—") {
  if (value === null || value === undefined || value === "") return fallback;
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}

function stateClasses(state: StatusState) {
  if (state === "good") return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
  if (state === "bad") return "border-red-500/30 bg-red-500/10 text-red-300";
  if (state === "warn") return "border-amber-500/30 bg-amber-500/10 text-amber-300";
  if (state === "active") return "border-blue-500/30 bg-blue-500/10 text-blue-300";
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

function Pill({ label, state = "neutral" }: { label: string; state?: StatusState }) {
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

function Field({
  label,
  value,
  state = "neutral",
}: {
  label: string;
  value: React.ReactNode;
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
  right?: React.ReactNode;
  children: React.ReactNode;
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

export default function CamerasPage() {
  const [cameras, setCameras] = useState<any>(null);

  const loadCameras = useCallback(async () => {
    try {
      const res = await apiFetch(`${BACKEND_URL}/v1/cameras`, {
        cache: "no-store",
      });

      const data = await res.json().catch(() => null);
      setCameras(data);
    } catch (err) {
      setCameras({
        error: err instanceof Error ? err.message : String(err),
        summary: { total: 0, external_cloud: 0, native_streams: 0 },
        devices: [],
      });
    }
  }, []);

  useEffect(() => {
    const initialTimer = window.setTimeout(loadCameras, 0);
    const intervalTimer = window.setInterval(loadCameras, 5000);

    return () => {
      window.clearTimeout(initialTimer);
      window.clearInterval(intervalTimer);
    };
  }, [loadCameras]);

  const devices = Array.isArray(cameras?.devices) ? cameras.devices : [];
  const primary = devices[0] || {};
  const status = primary?.health ? formatMode(primary.health) : "Unknown";

  const statusState: StatusState =
    primary?.health === "online"
      ? "good"
      : primary?.health === "offline"
        ? "bad"
        : "warn";

  return (
    <main className="min-h-screen bg-black px-6 py-8 text-neutral-100">
      <div className="mx-auto max-w-5xl">
        <Link
          href="/"
          className="text-sm font-medium text-neutral-500 transition hover:text-neutral-200"
        >
          ← Back to Orion Dashboard
        </Link>

        <header className="mt-8 flex items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-neutral-600">
              Orion External Devices
            </p>
            <h1 className="mt-2 text-4xl font-bold text-white">
              External Cameras
            </h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-neutral-400">
              Supervised cloud-managed cameras, vendor-app video access, and mixed-vendor device visibility.
            </p>
          </div>

          <Pill label={status} state={statusState} />
        </header>

        <section className="mt-8 grid gap-4 md:grid-cols-4">
          <Field label="Total Cameras" value={displayValue(cameras?.summary?.total, "0")} />
          <Field label="External Cloud" value={displayValue(cameras?.summary?.external_cloud, "0")} state="warn" />
          <Field label="Native Streams" value={displayValue(cameras?.summary?.native_streams, "0")} />
          <Field label="Local Access" value={primary?.local_access ? "Available" : "Not exposed"} state={primary?.local_access ? "good" : "warn"} />
        </section>

        <div className="mt-6 grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <Section
            title={primary?.name || "No camera configured"}
            subtitle={`${primary?.vendor || "Unknown vendor"} · ${primary?.model || "Unknown model"}`}
            right={<Pill label={formatMode(primary?.integration_type || "external_cloud")} state="warn" />}
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="IP Address" value={displayValue(primary?.ip)} />
              <Field label="MAC Address" value={displayValue(primary?.mac_address)} />
              <Field label="Managed By" value={displayValue(primary?.managed_by)} state="active" />
              <Field label="Location" value={displayValue(primary?.location)} />
              <Field label="Video Access" value={primary?.stream_access ? "Local Stream" : "Vendor App"} state={primary?.stream_access ? "active" : "neutral"} />
              <Field label="PTZ Control" value={formatMode(primary?.ptz_control || "vendor_app")} />
              <Field label="RTSP" value={primary?.capabilities?.rtsp ? "Available" : "Not available"} state={primary?.capabilities?.rtsp ? "good" : "neutral"} />
              <Field label="ONVIF" value={primary?.capabilities?.onvif ? "Available" : "Not available"} state={primary?.capabilities?.onvif ? "good" : "neutral"} />
            </div>

            <div className="mt-5 rounded-2xl border border-neutral-800 bg-black p-4">
              <p className="text-xs uppercase tracking-[0.18em] text-neutral-500">
                Orion Role
              </p>
              <p className="mt-2 text-lg font-semibold text-white">
                {primary?.orion_role || "Supervised external camera"}
              </p>
              <p className="mt-2 text-sm leading-6 text-neutral-400">
                {primary?.message || primary?.notes || "This camera is tracked as an external vendor-managed device."}
              </p>
            </div>
          </Section>

          <Section
            title="Integration Limits"
            subtitle="Known capability boundaries for this camera"
          >
            <div className="space-y-3">
              <Field label="Local HTTP UI" value={primary?.capabilities?.http_ui ? "Available" : "Not available"} />
              <Field label="Local Stream" value={primary?.capabilities?.local_stream ? "Available" : "Not available"} />
              <Field label="Motion Alerts" value={primary?.capabilities?.vendor_app_motion_alerts ? "ANRAN App" : "Unknown"} state="active" />
              <Field label="Playback" value={primary?.capabilities?.vendor_app_playback ? "ANRAN App" : "Unknown"} state="active" />
            </div>

            <div className="mt-5 rounded-2xl border border-amber-500/20 bg-amber-500/10 p-4 text-sm leading-6 text-amber-100">
              This camera is intentionally shown as an external cloud device. Orion supervises its metadata and integration status, while live video, PTZ, motion events, and playback remain inside the ANRAN app.
            </div>
          </Section>
        </div>

        <details className="mt-6 rounded-2xl border border-neutral-800 bg-neutral-950 p-4">
          <summary className="cursor-pointer text-sm font-semibold text-neutral-300">
            Raw camera JSON
          </summary>
          <pre className="mt-4 max-h-[420px] overflow-auto rounded-xl bg-black p-4 text-xs text-neutral-300">
            {JSON.stringify(cameras, null, 2)}
          </pre>
        </details>
      </div>
    </main>
  );
}
