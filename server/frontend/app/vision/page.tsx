"use client";

import Link from "next/link";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://192.168.7.230:5001";

const POLL_MS = Number(process.env.NEXT_PUBLIC_SYSTEM_POLL_MS ?? "3000");

type StatusState = "good" | "bad" | "warn" | "neutral" | "active";

type VisionStatus = {
  ok?: boolean;
  online?: boolean;
  node_url?: string;
  node_id?: string;
  node_name?: string;
  camera_online?: boolean;
  streaming_clients?: number;
  recording?: boolean;
  fps?: number | null;
  resolution?: string | null;
  focus_mode?: string | null;
  focus_state?: string | null;
  lens_position?: number | null;
  uptime_seconds?: number | null;
  last_frame_age?: number | null;
  fault?: boolean;
  fault_code?: string;
  fault_message?: string;
  error?: string;
  detail?: string;
};

type GrassCondition = {
  ok?: boolean;
  condition?: string;
  score?: number;
  dryness_index?: number;
  green_percent?: number;
  dry_percent?: number;
  dark_percent?: number;
  valid_percent?: number;
  reason?: string;
  time?: string;
  error?: string;
  detail?: string;
};

type RainDetection = {
  ok?: boolean;
  rain_detected?: boolean;
  confidence?: string;
  wetness_score?: number;
  motion_score?: number;
  dark_percent?: number;
  low_saturation_percent?: number;
  reflection_percent?: number;
  smoothness_score?: number;
  reason?: string;
  time?: string;
  error?: string;
  detail?: string;
};

type EnvironmentState = {
  recommendation?: string;
  confidence?: string;
  reason?: string;
  inputs?: {
    grass_score?: number;
    dryness_index?: number;
    rain_probability?: number;
    temperature_f?: number | null;
    feels_like_f?: number | null;
    humidity?: number | null;
    lawn_need_score?: number;
    lawn_need_level?: string;
    heat_stress?: boolean;
    extreme_heat?: boolean;
    low_humidity?: boolean;
    camera_rain_detected?: boolean;
    camera_rain_confidence?: string;
    camera_wetness_score?: number;
    camera_motion_score?: number;
  };
  rain_detection?: RainDetection;
  irrigation?: {
    online?: boolean;
    running?: boolean;
    zone?: string | number | null;
    next_irrigation?: unknown;
    last_irrigation?: unknown;
  };
  safety?: {
    auto_execute_allowed?: boolean;
    requires_user_approval?: boolean;
    reason?: string;
  };
};

type SystemState = {
  weather?: {
    online?: boolean;
    temp?: number | null;
    feels_like?: number | null;
    humidity?: number | null;
    rain_chance?: number | null;
    condition?: string | null;
    location?: string | null;
  };
  grass_condition?: GrassCondition | null;
  rain_detection?: RainDetection | null;
  environment?: EnvironmentState | null;
};

type StreamState =
  | "idle"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "error";

function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
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

function formatNumber(value: unknown, digits = 1) {
  const n = Number(value);
  return Number.isFinite(n) ? n.toFixed(digits) : "--";
}

function formatPercent(value: unknown, digits = 1) {
  const n = Number(value);
  return Number.isFinite(n) ? `${n.toFixed(digits)}%` : "--";
}

function formatRatioPercent(value: unknown) {
  const n = Number(value);
  return Number.isFinite(n) ? `${Math.round(n * 100)}%` : "--";
}

function formatTemp(value: unknown) {
  const n = Number(value);
  return Number.isFinite(n) ? `${n.toFixed(1)}°F` : "--";
}

function statusFromOnline(value?: boolean): StatusState {
  if (value === undefined) return "neutral";
  return value ? "good" : "bad";
}

function conditionState(value?: string | null): StatusState {
  if (value === "healthy") return "good";
  if (value === "fair") return "warn";
  if (value === "stressed" || value === "poor") return "bad";
  return "neutral";
}

function recommendationState(value?: string | null): StatusState {
  if (value === "no_irrigation_needed") return "good";
  if (value === "delay_irrigation") return "warn";
  if (value === "monitor_lawn") return "warn";
  if (value === "consider_irrigation") return "bad";
  if (value === "run_short_irrigation") return "bad";
  if (value === "stop_or_delay_irrigation") return "bad";
  return "neutral";
}

function confidenceState(value?: string | null): StatusState {
  if (value === "high") return "good";
  if (value === "medium") return "warn";
  if (value === "low") return "neutral";
  return "neutral";
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
        "overflow-hidden rounded-2xl border border-slate-800/80 bg-slate-900/75 shadow-xl shadow-black/10 ring-1 ring-white/[0.03] backdrop-blur",
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

function Field({
  label,
  value,
  state = "neutral",
}: {
  label: string;
  value: ReactNode;
  state?: StatusState;
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
          state === "neutral" && "text-white",
        )}
      >
        {value}
      </div>
    </div>
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

function DetailCard({
  title,
  subtitle,
  status,
  statusState = "neutral",
  children,
}: {
  title: string;
  subtitle?: string;
  status?: string;
  statusState?: StatusState;
  children: ReactNode;
}) {
  return (
    <Panel>
      <PanelHeader
        title={title}
        subtitle={subtitle}
        right={status ? <StatusPill label={status} state={statusState} /> : null}
      />
      <div className="p-5">{children}</div>
    </Panel>
  );
}

export default function VisionPage() {
  const [system, setSystem] = useState<SystemState | null>(null);
  const [vision, setVision] = useState<VisionStatus | null>(null);
  const [grassCondition, setGrassCondition] = useState<GrassCondition | null>(
    null,
  );
  const [rainDetection, setRainDetection] = useState<RainDetection | null>(null);

  const [streamState, setStreamState] = useState<StreamState>("idle");
  const [recording, setRecording] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const pcRef = useRef<RTCPeerConnection | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const recordedChunksRef = useRef<Blob[]>([]);
  const saveRecordingRef = useRef(true);
  const autoConnectAttemptedRef = useRef(false);

  const environment = system?.environment || null;

  const visionOnline = Boolean(vision?.online);
  const visionStatus = !vision ? "Loading" : vision.online ? "Online" : "Offline";
  const visionState: StatusState = !vision
    ? "neutral"
    : vision.fault
      ? "bad"
      : vision.online
        ? "good"
        : "bad";

  const streamLabel =
    streamState === "connected"
      ? "Connected"
      : streamState === "connecting"
        ? "Connecting"
        : streamState === "reconnecting"
          ? "Reconnecting"
          : streamState === "error"
            ? "Stream error"
            : "Idle";

  const streamPillState: StatusState =
    streamState === "connected"
      ? "active"
      : streamState === "connecting" || streamState === "reconnecting"
        ? "warn"
        : streamState === "error"
          ? "bad"
          : "neutral";

  const loadSystem = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/v1/system`, {
        cache: "no-store",
      });

      if (!res.ok) return;

      const data = await res.json();

      setSystem(data);

      if (data?.grass_condition) {
        setGrassCondition(data.grass_condition);
      }

      if (data?.rain_detection) {
        setRainDetection(data.rain_detection);
      }
    } catch (err) {
      setLastError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  const loadVision = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/v1/vision/status`, {
        cache: "no-store",
      });

      const data = await res.json().catch(() => null);

      if (!res.ok) {
        setVision({
          ok: false,
          online: false,
          error: data?.error || "Vision node unavailable",
          detail: data?.detail,
        });
        return;
      }

      setVision(data);
    } catch (err) {
      setVision({
        ok: false,
        online: false,
        error: err instanceof Error ? err.message : String(err),
      });
    }
  }, []);

  const loadGrassCondition = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/v1/vision/grass-condition`, {
        cache: "no-store",
      });

      const data = await res.json().catch(() => null);

      if (!res.ok) {
        setGrassCondition({
          ok: false,
          error: data?.error || "Grass condition unavailable",
          detail: data?.detail,
        });
        return;
      }

      setGrassCondition(data);
    } catch (err) {
      setGrassCondition({
        ok: false,
        error: err instanceof Error ? err.message : String(err),
      });
    }
  }, []);

  const loadRainDetection = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/v1/vision/rain-detection`, {
        cache: "no-store",
      });

      const data = await res.json().catch(() => null);

      if (!res.ok) {
        setRainDetection({
          ok: false,
          error: data?.error || "Rain detection unavailable",
          detail: data?.detail,
        });
        return;
      }

      setRainDetection(data);
    } catch (err) {
      setRainDetection({
        ok: false,
        error: err instanceof Error ? err.message : String(err),
      });
    }
  }, []);

  const refreshAll = useCallback(async () => {
    await Promise.all([
      loadSystem(),
      loadVision(),
      loadGrassCondition(),
      loadRainDetection(),
    ]);
  }, [loadSystem, loadVision, loadGrassCondition, loadRainDetection]);

  const stopRecording = useCallback((save = true) => {
    const recorder = recorderRef.current;

    if (!recorder) {
      setRecording(false);
      return;
    }

    saveRecordingRef.current = save;

    try {
      if (recorder.state !== "inactive") {
        recorder.stop();
      }
    } catch {
      recorderRef.current = null;
      setRecording(false);
    }
  }, []);

  const stopStream = useCallback(() => {
    stopRecording(true);

    const pc = pcRef.current;

    if (pc) {
      pc.ontrack = null;
      pc.onconnectionstatechange = null;
      pc.oniceconnectionstatechange = null;
      pc.close();
      pcRef.current = null;
    }

    if (videoRef.current) {
      videoRef.current.pause();
      videoRef.current.srcObject = null;
      videoRef.current.removeAttribute("src");
      videoRef.current.load();
    }

    setStreamState("idle");
  }, [stopRecording]);

  const chooseRecorderOptions = (): MediaRecorderOptions | undefined => {
    const candidates = [
      "video/webm;codecs=vp9",
      "video/webm;codecs=vp8",
      "video/webm",
    ];

    for (const mimeType of candidates) {
      if (
        typeof MediaRecorder !== "undefined" &&
        MediaRecorder.isTypeSupported(mimeType)
      ) {
        return {
          mimeType,
          videoBitsPerSecond: 8_000_000,
        };
      }
    }

    return undefined;
  };

  const saveRecording = () => {
    const chunks = recordedChunksRef.current;

    if (!chunks.length) return;

    const recorder = recorderRef.current;
    const mimeType = recorder?.mimeType || "video/webm";

    const blob = new Blob(chunks, { type: mimeType });
    const url = URL.createObjectURL(blob);
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");

    const link = document.createElement("a");
    link.href = url;
    link.download = `orion-vision-recording-${timestamp}.webm`;

    document.body.appendChild(link);
    link.click();

    window.setTimeout(() => {
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    }, 0);
  };

  const startRecording = () => {
    if (recording) return;

    const stream = videoRef.current?.srcObject;

    if (!(stream instanceof MediaStream)) {
      setLastError("No active vision stream to record.");
      return;
    }

    try {
      const options = chooseRecorderOptions();
      const recorder = options
        ? new MediaRecorder(stream, options)
        : new MediaRecorder(stream);

      recorderRef.current = recorder;
      recordedChunksRef.current = [];
      saveRecordingRef.current = true;

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          recordedChunksRef.current.push(event.data);
        }
      };

      recorder.onstop = () => {
        if (saveRecordingRef.current) {
          saveRecording();
        }

        recorderRef.current = null;
        setRecording(false);
      };

      recorder.start(1000);
      setRecording(true);
    } catch (err) {
      setLastError(err instanceof Error ? err.message : String(err));
      setRecording(false);
    }
  };

  const toggleRecording = () => {
    if (recording) {
      stopRecording(true);
      return;
    }

    startRecording();
  };

  const startStream = async () => {
    if (pcRef.current || streamState === "connecting") return;

    setLastError(null);
    setStreamState("connecting");

    try {
      const pc = new RTCPeerConnection({ iceServers: [] });
      pcRef.current = pc;

      pc.ontrack = (event) => {
        const [stream] = event.streams;

        if (stream && videoRef.current) {
          videoRef.current.srcObject = stream;
        }

        setStreamState("connected");
      };

      pc.onconnectionstatechange = () => {
        if (pc.connectionState === "connected") {
          setStreamState("connected");
          return;
        }

        if (pc.connectionState === "disconnected") {
          setStreamState("reconnecting");
          return;
        }

        if (pc.connectionState === "failed" || pc.connectionState === "closed") {
          setStreamState("error");
        }
      };

      pc.oniceconnectionstatechange = () => {
        if (
          pc.iceConnectionState === "connected" ||
          pc.iceConnectionState === "completed"
        ) {
          setStreamState("connected");
          return;
        }

        if (pc.iceConnectionState === "disconnected") {
          setStreamState("reconnecting");
          return;
        }

        if (
          pc.iceConnectionState === "failed" ||
          pc.iceConnectionState === "closed"
        ) {
          setStreamState("error");
        }
      };

      const offer = await pc.createOffer({
        offerToReceiveAudio: false,
        offerToReceiveVideo: true,
      });

      await pc.setLocalDescription(offer);

      const res = await fetch(`${BACKEND_URL}/v1/vision/offer`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          sdp: offer.sdp,
          type: offer.type,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.error || "Failed to negotiate vision stream");
      }

      const answer = await res.json();

      await pc.setRemoteDescription(answer);
      await loadVision();
    } catch (err) {
      setLastError(err instanceof Error ? err.message : String(err));
      stopStream();
      setStreamState("error");
    }
  };

  useEffect(() => {
    refreshAll();

    const interval = window.setInterval(refreshAll, POLL_MS);

    return () => window.clearInterval(interval);
  }, [refreshAll]);

  useEffect(() => {
    const handlePageHide = () => stopStream();

    const handleVisibilityChange = () => {
      if (document.visibilityState === "hidden") {
        stopStream();
      }
    };

    window.addEventListener("pagehide", handlePageHide);
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      window.removeEventListener("pagehide", handlePageHide);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      stopStream();
    };
  }, [stopStream]);

  useEffect(() => {
    if (!visionOnline) return;
    if (autoConnectAttemptedRef.current) return;
    if (pcRef.current) return;
    if (streamState !== "idle" && streamState !== "error") return;

    autoConnectAttemptedRef.current = true;
    startStream();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visionOnline, streamState]);

  const openSnapshot = () => {
    window.open(`${BACKEND_URL}/v1/vision/snapshot?t=${Date.now()}`, "_blank");
  };

  const autofocusOnce = async () => {
    await fetch(`${BACKEND_URL}/v1/vision/focus`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ mode: "auto_once" }),
    });

    await loadVision();
  };

  const restartCamera = async () => {
    const confirmed = window.confirm("Restart the vision node camera?");
    if (!confirmed) return;

    await fetch(`${BACKEND_URL}/v1/vision/restart-camera`, {
      method: "POST",
    });

    await loadVision();
  };

  const streamButtonLabel =
    streamState === "connected"
      ? "Connected"
      : streamState === "connecting"
        ? "Connecting..."
        : streamState === "error"
          ? "Reconnect"
          : "Connect";

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

      <header className="relative z-20 border-b border-slate-800/80 bg-slate-950/95 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[1600px] items-center justify-between gap-4 px-5 py-3.5">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-xl shadow-lg shadow-blue-950/30">
              📷
            </div>

            <div className="min-w-0">
              <h1 className="truncate text-lg font-semibold tracking-tight text-white">
                Orion Vision Node
              </h1>
              <p className="truncate text-xs text-slate-400">
                Environmental vision, lawn telemetry, rain evidence, and irrigation guidance
              </p>
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            <StatusPill label={visionStatus} state={visionState} />
            <Link
              href="/"
              className="inline-flex h-10 items-center justify-center rounded-xl border border-slate-700/80 bg-slate-800/80 px-4 text-sm font-semibold text-slate-100 transition hover:bg-slate-700"
            >
              Back to Dashboard
            </Link>
          </div>
        </div>
      </header>

      <main className="relative mx-auto grid max-w-[1500px] grid-cols-1 gap-5 px-5 py-5 xl:grid-cols-[minmax(0,1.45fr)_minmax(380px,0.85fr)]">
        <section className="space-y-4">
          <Panel>
            <PanelHeader
              title="Environmental Camera Feed"
              subtitle="Pi Zero 2 W · IMX708 · WebRTC"
              right={<StatusPill label={streamLabel} state={streamPillState} />}
            />

            <div className="bg-black">
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className="aspect-video w-full bg-black object-contain"
              />
            </div>

            <div className="grid grid-cols-2 gap-2 border-t border-slate-800/80 p-4 sm:grid-cols-4">
              <Button
                onClick={startStream}
                disabled={
                  !visionOnline ||
                  streamState === "connecting" ||
                  streamState === "connected"
                }
                className="h-9 w-full"
              >
                {streamButtonLabel}
              </Button>

              <Button
                onClick={stopStream}
                disabled={streamState === "idle"}
                variant="secondary"
                className="h-9 w-full"
              >
                Disconnect
              </Button>

              <Button
                onClick={toggleRecording}
                disabled={streamState !== "connected"}
                variant={recording ? "danger" : "success"}
                className="h-9 w-full"
              >
                {recording ? "Stop" : "Record Clip"}
              </Button>

              <Button
                onClick={openSnapshot}
                disabled={!visionOnline}
                variant="secondary"
                className="h-9 w-full"
              >
                Snapshot
              </Button>
            </div>

            {lastError && (
              <div className="border-t border-red-400/15 bg-red-500/10 p-4 text-sm text-red-200">
                {lastError}
              </div>
            )}
          </Panel>

          <DetailCard
            title="Environmental Decision"
            subtitle="Weather, camera, lawn condition, and irrigation context"
            status={formatMode(environment?.confidence || "Unknown")}
            statusState={confidenceState(environment?.confidence)}
          >
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
              <Field
                label="Decision"
                value={formatMode(environment?.recommendation)}
                state={recommendationState(environment?.recommendation)}
              />
              <Field
                label="Confidence"
                value={formatMode(environment?.confidence)}
                state={confidenceState(environment?.confidence)}
              />
              <Field
                label="Rain Probability"
                value={formatRatioPercent(environment?.inputs?.rain_probability)}
                state={
                  Number(environment?.inputs?.rain_probability ?? 0) >= 0.7
                    ? "warn"
                    : "neutral"
                }
              />
              <Field
                label="Rain Evidence"
                value={environment?.inputs?.camera_rain_detected ? "Detected" : "Not Confirmed"}
                state={environment?.inputs?.camera_rain_detected ? "warn" : "neutral"}
              />
              <Field
                label="Lawn Watering Need"
                value={formatMode(environment?.inputs?.lawn_need_level)}
                state={
                  environment?.inputs?.lawn_need_level === "high"
                    ? "bad"
                    : environment?.inputs?.lawn_need_level === "moderate"
                      ? "warn"
                      : "neutral"
                }
              />
              <Field
                label="Next Scheduled Run"
                value={String(environment?.irrigation?.next_irrigation || "--")}
              />
            </div>

            <p className="mt-4 rounded-xl border border-slate-800/70 bg-slate-950/35 p-3 text-sm leading-6 text-slate-300">
              {environment?.reason || "No environmental decision available."}
            </p>

            {environment?.safety && (
              <div className="mt-3 rounded-xl border border-slate-700/70 bg-slate-950/35 p-3 text-xs leading-5 text-slate-300">
                {environment.safety.reason ||
                  "Environmental decisions are advisory and require operator approval before hardware action."}
              </div>
            )}
          </DetailCard>
        </section>

        <aside className="space-y-4">
          <DetailCard
            title="Vision Node Health"
            subtitle={vision?.node_name || "Camera service, stream health, focus state, and telemetry"}
            status={visionStatus}
            statusState={visionState}
          >
            <div className="grid grid-cols-2 gap-3">
              <Field
                label="Camera"
                value={vision?.camera_online ? "Online" : "Offline"}
                state={statusFromOnline(vision?.camera_online)}
              />
              <Field
                label="FPS"
                value={formatNumber(vision?.fps, 1)}
                state={
                  Number(vision?.fps ?? 0) >= 20
                    ? "good"
                    : Number(vision?.fps ?? 0) > 0
                      ? "warn"
                      : "neutral"
                }
              />
              <Field label="Resolution" value={vision?.resolution || "--"} />
              <Field
                label="Clients"
                value={vision?.streaming_clients ?? 0}
                state={
                  Number(vision?.streaming_clients ?? 0) > 0
                    ? "active"
                    : "neutral"
                }
              />
              <Field
                label="Focus"
                value={formatMode(vision?.focus_mode)}
                state={vision?.focus_mode ? "good" : "neutral"}
              />
              <Field
                label="Lens"
                value={formatNumber(vision?.lens_position, 2)}
              />
              <Field
                label="Last Frame"
                value={
                  Number.isFinite(Number(vision?.last_frame_age))
                    ? `${Number(vision?.last_frame_age).toFixed(2)}s ago`
                    : "--"
                }
                state={
                  Number(vision?.last_frame_age ?? 999) <= 2 ? "good" : "warn"
                }
              />
              <Field
                label="Fault"
                value={vision?.fault ? vision?.fault_code || "Fault" : "None"}
                state={vision?.fault ? "bad" : "good"}
              />
            </div>

            {vision?.error && (
              <div className="mt-4 rounded-xl border border-red-400/15 bg-red-500/10 p-3 text-xs leading-5 text-red-200">
                {vision.error}
                {vision.detail ? ` · ${vision.detail}` : ""}
              </div>
            )}

            <div className="mt-4 flex flex-wrap gap-2">
              <Button onClick={refreshAll} variant="secondary" className="h-9">
                Refresh
              </Button>
              <Button
                onClick={autofocusOnce}
                disabled={!visionOnline}
                variant="secondary"
                className="h-9"
              >
                Autofocus
              </Button>
              <Button
                onClick={restartCamera}
                disabled={!visionOnline}
                variant="ghost"
                className="h-9"
              >
                Restart camera
              </Button>
            </div>
          </DetailCard>

          <DetailCard
            title="Lawn Condition"
            subtitle="Camera-based grass color and dryness analysis"
            status={formatMode(grassCondition?.condition || "Waiting")}
            statusState={conditionState(grassCondition?.condition)}
          >
            <div className="grid grid-cols-2 gap-3">
              <Field
                label="Condition"
                value={formatMode(grassCondition?.condition)}
                state={conditionState(grassCondition?.condition)}
              />
              <Field
                label="Score"
                value={
                  Number.isFinite(Number(grassCondition?.score))
                    ? `${Number(grassCondition?.score).toFixed(0)} / 100`
                    : "--"
                }
                state={
                  Number(grassCondition?.score ?? 0) >= 65
                    ? "good"
                    : Number(grassCondition?.score ?? 0) >= 45
                      ? "warn"
                      : Number(grassCondition?.score ?? 0) > 0
                        ? "bad"
                        : "neutral"
                }
              />
              <Field
                label="Dryness"
                value={formatNumber(grassCondition?.dryness_index, 3)}
              />
              <Field
                label="Green"
                value={formatPercent(grassCondition?.green_percent, 1)}
                state="good"
              />
              <Field
                label="Dry Tones"
                value={formatPercent(grassCondition?.dry_percent, 1)}
                state={
                  Number(grassCondition?.dry_percent ?? 0) >= 15
                    ? "warn"
                    : "neutral"
                }
              />
              <Field
                label="Valid Area"
                value={formatPercent(grassCondition?.valid_percent, 1)}
              />
            </div>

            {grassCondition?.reason && (
              <p className="mt-3 text-xs leading-5 text-slate-400">
                {grassCondition.reason}
              </p>
            )}

            {grassCondition?.error && (
              <div className="mt-3 rounded-xl border border-red-400/15 bg-red-500/10 p-3 text-xs leading-5 text-red-200">
                {grassCondition.error}
                {grassCondition.detail ? ` · ${grassCondition.detail}` : ""}
              </div>
            )}

            <Button
              onClick={loadGrassCondition}
              disabled={!visionOnline}
              variant="secondary"
              className="mt-4 h-9"
            >
              Analyze Lawn
            </Button>
          </DetailCard>

          <DetailCard
            title="Rain Evidence"
            subtitle="Camera-assisted rain and wet-surface detection"
            status={
              rainDetection?.rain_detected
                ? "Detected"
                : rainDetection
                  ? "Not Confirmed"
                  : "Waiting"
            }
            statusState={
              rainDetection?.rain_detected
                ? "warn"
                : rainDetection
                  ? "neutral"
                  : "neutral"
            }
          >
            <div className="grid grid-cols-2 gap-3">
              <Field
                label="Rain"
                value={rainDetection?.rain_detected ? "Detected" : "Not Confirmed"}
                state={rainDetection?.rain_detected ? "warn" : "neutral"}
              />
              <Field
                label="Confidence"
                value={formatMode(rainDetection?.confidence)}
                state={confidenceState(rainDetection?.confidence)}
              />
              <Field
                label="Wetness"
                value={formatNumber(rainDetection?.wetness_score, 3)}
                state={
                  Number(rainDetection?.wetness_score ?? 0) >= 0.32
                    ? "warn"
                    : "neutral"
                }
              />
              <Field
                label="Motion"
                value={formatNumber(rainDetection?.motion_score, 3)}
              />
              <Field
                label="Dark Area"
                value={formatPercent(rainDetection?.dark_percent, 1)}
              />
              <Field
                label="Reflection"
                value={formatPercent(rainDetection?.reflection_percent, 1)}
              />
            </div>

            {rainDetection?.reason && (
              <p className="mt-3 text-xs leading-5 text-slate-400">
                {rainDetection.reason}
              </p>
            )}

            {rainDetection?.error && (
              <div className="mt-3 rounded-xl border border-red-400/15 bg-red-500/10 p-3 text-xs leading-5 text-red-200">
                {rainDetection.error}
                {rainDetection.detail ? ` · ${rainDetection.detail}` : ""}
              </div>
            )}

            <Button
              onClick={loadRainDetection}
              disabled={!visionOnline}
              variant="secondary"
              className="mt-4 h-9"
            >
              Analyze Rain
            </Button>
          </DetailCard>

          <DetailCard
            title="Weather Conditions"
            subtitle={system?.weather?.location || "Local weather and irrigation context"}
            status={
              Number(system?.weather?.rain_chance ?? 0) >= 70
                ? "Rain likely"
                : system?.weather?.condition || "Weather"
            }
            statusState={
              Number(system?.weather?.rain_chance ?? 0) >= 70 ? "warn" : "good"
            }
          >
            <div className="grid grid-cols-2 gap-3">
              <Field label="Temp" value={formatTemp(system?.weather?.temp)} />
              <Field
                label="Feels Like"
                value={formatTemp(system?.weather?.feels_like)}
              />
              <Field
                label="Rain"
                value={
                  Number.isFinite(Number(system?.weather?.rain_chance))
                    ? `${Number(system?.weather?.rain_chance).toFixed(0)}%`
                    : "--"
                }
                state={
                  Number(system?.weather?.rain_chance ?? 0) >= 70
                    ? "warn"
                    : "neutral"
                }
              />
              <Field
                label="Humidity"
                value={formatPercent(system?.weather?.humidity, 1)}
              />
            </div>
          </DetailCard>
        </aside>
      </main>
    </div>
  );
}
