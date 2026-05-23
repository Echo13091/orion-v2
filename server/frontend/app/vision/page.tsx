"use client";

import Link from "next/link";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "";

const POLL_MS = Number(process.env.NEXT_PUBLIC_SYSTEM_POLL_MS ?? "3000");

type StatusState = "good" | "bad" | "warn" | "neutral" | "active";

type VisionStatus = {
  ok?: boolean;
  online?: boolean;
  degraded?: boolean;
  mode?: string;
  analysis_available?: boolean;
  message?: string;
  node_url?: string;
  vision_node_url?: string;
  vision_node_fallback_url?: string | null;
  vision_node_urls?: string[];
  configured_node_urls?: string[];
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
    lawn_analysis_available?: boolean;
    camera_rain_detected?: boolean;
    visual_wet_surface_evidence?: boolean;
    visual_evidence_detected?: boolean;
    visual_evidence_label?: string;
    camera_rain_confidence?: string;
    camera_wetness_score?: number;
    camera_motion_score?: number;
  };
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

function displayConfiguredEndpoint(value: unknown, label: string) {
  if (value === null || value === undefined || value === "") return "Not configured";
  return label;
}

function sanitizeDetail(value: unknown) {
  const raw = String(value || "").trim();

  if (!raw) return "No detail available";

  return raw
    .replace(/https?:\/\/[^\s"'<>]+/g, "[endpoint]")
    .replace(/\b(?:\d{1,3}\.){3}\d{1,3}\b/g, "[ip]");
}

function formatNumber(value: unknown, digits = 1) {
  const n = Number(value);
  return Number.isFinite(n) ? n.toFixed(digits) : "—";
}

function formatPercent(value: unknown, digits = 1) {
  const n = Number(value);
  return Number.isFinite(n) ? `${n.toFixed(digits)}%` : "—";
}

function formatRatioPercent(value: unknown) {
  const n = Number(value);
  return Number.isFinite(n) ? `${Math.round(n * 100)}%` : "—";
}

function formatTemp(value: unknown) {
  const n = Number(value);
  return Number.isFinite(n) ? `${n.toFixed(1)}°F` : "—";
}

function formatJson(value: unknown) {
  try {
    return JSON.stringify(value ?? {}, null, 2);
  } catch {
    return String(value);
  }
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

function isLawnAnalysisAvailable(grassCondition?: GrassCondition | null) {
  const condition = String(grassCondition?.condition || "").trim().toLowerCase();
  const validPercent = Number(grassCondition?.valid_percent ?? 0);

  if (condition === "unknown") return false;
  if (Number.isFinite(validPercent) && validPercent < 5) return false;

  return true;
}

function lawnConditionLabel(grassCondition?: GrassCondition | null) {
  if (!grassCondition) return "Waiting";
  if (!isLawnAnalysisAvailable(grassCondition)) return "Low Light";

  return formatMode(grassCondition.condition);
}

function lawnScoreLabel(grassCondition?: GrassCondition | null) {
  if (!grassCondition) return "--";
  if (!isLawnAnalysisAvailable(grassCondition)) return "Not Evaluated";

  return Number.isFinite(Number(grassCondition.score))
    ? `${Number(grassCondition.score).toFixed(0)} / 100`
    : "--";
}

function lawnState(grassCondition?: GrassCondition | null): StatusState {
  if (!grassCondition) return "neutral";
  if (!isLawnAnalysisAvailable(grassCondition)) return "neutral";

  return conditionState(grassCondition.condition);
}

function confidenceState(value?: string | null): StatusState {
  if (value === "high") return "good";
  if (value === "medium") return "warn";
  if (value === "low") return "neutral";
  return "neutral";
}

function stateClasses(state: StatusState) {
  if (state === "good") {
    return "bg-emerald-500/10 text-emerald-300 ring-1 ring-emerald-500/30";
  }

  if (state === "bad") {
    return "bg-red-500/10 text-red-300 ring-1 ring-red-500/30";
  }

  if (state === "warn") {
    return "bg-amber-500/10 text-amber-300 ring-1 ring-amber-500/30";
  }

  if (state === "active") {
    return "bg-blue-500/10 text-blue-300 ring-1 ring-blue-500/30";
  }

  return "bg-neutral-800 text-neutral-300 ring-1 ring-neutral-700";
}

function textStateClass(state: StatusState) {
  if (state === "good") return "text-emerald-200";
  if (state === "bad") return "text-red-200";
  if (state === "warn") return "text-amber-200";
  if (state === "active") return "text-blue-200";
  return "text-white";
}

function Button({
  children,
  onClick,
  disabled,
  variant = "primary",
  className = "",
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: "primary" | "success" | "danger" | "secondary" | "ghost";
  className?: string;
}) {
  const variantClass =
    variant === "success"
      ? "bg-emerald-600 text-white hover:bg-emerald-500"
      : variant === "danger"
        ? "bg-red-600 text-white hover:bg-red-500"
        : variant === "secondary"
          ? "border border-neutral-700 bg-neutral-900 text-neutral-100 hover:bg-neutral-800"
          : variant === "ghost"
            ? "text-neutral-300 hover:bg-neutral-900"
            : "bg-blue-600 text-white hover:bg-blue-500";

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={[
        "inline-flex items-center justify-center rounded-xl px-4 py-3 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50",
        variantClass,
        className,
      ].join(" ")}
    >
      {children}
    </button>
  );
}

function StatCard({
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
      <p className={`mt-2 text-3xl font-semibold ${textStateClass(state)}`}>
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
  value: ReactNode;
  state?: StatusState;
}) {
  return (
    <div className="rounded-2xl border border-neutral-800 bg-neutral-950 p-4">
      <p className="text-xs uppercase tracking-[0.18em] text-neutral-500">
        {label}
      </p>
      <p className={`mt-2 break-words text-lg font-semibold ${textStateClass(state)}`}>
        {value}
      </p>
    </div>
  );
}

function Section({
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
    <section className="rounded-2xl border border-neutral-800 bg-neutral-950 p-5 shadow-lg">
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold text-white">{title}</h2>
          {subtitle ? (
            <p className="mt-1 text-sm text-neutral-500">{subtitle}</p>
          ) : null}
        </div>

        {status ? (
          <span
            className={`rounded-full px-3 py-1 text-xs font-semibold ${stateClasses(
              statusState,
            )}`}
          >
            {status}
          </span>
        ) : null}
      </div>

      {children}
    </section>
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
  const weather = system?.weather || null;

  const visionOnline = Boolean(vision?.online);
  const visionStatus = !vision
    ? "Loading"
    : vision.online
      ? "Online"
      : vision.degraded
        ? "Degraded"
        : "Offline";
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
            ? "Stream Error"
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

  const loadVision = useCallback(async (): Promise<VisionStatus | null> => {
    try {
      const res = await fetch(`${BACKEND_URL}/v1/vision/status`, {
        cache: "no-store",
      });

      const data = await res.json().catch(() => null);

      if (!res.ok) {
        const offlineStatus: VisionStatus = {
          ok: false,
          online: false,
          degraded: Boolean(data?.degraded ?? true),
          mode: data?.mode || "vision_degraded",
          analysis_available: false,
          message:
            data?.message ||
            "Vision node unavailable. Orion is operating in degraded mode.",
          error: data?.error || "Vision node unavailable",
          detail: data?.detail,
          node_url: data?.node_url,
          vision_node_url: data?.vision_node_url,
          vision_node_fallback_url: data?.vision_node_fallback_url,
          vision_node_urls: data?.vision_node_urls,
          configured_node_urls: data?.configured_node_urls,
        };

        setVision(offlineStatus);
        return offlineStatus;
      }

      setVision(data);
      return data;
    } catch (err) {
      const offlineStatus: VisionStatus = {
        ok: false,
        online: false,
        degraded: true,
        mode: "vision_degraded",
        analysis_available: false,
        message: "Vision node unavailable. Orion is operating in degraded mode.",
        error: err instanceof Error ? err.message : String(err),
      };

      setVision(offlineStatus);
      return offlineStatus;
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
    const [, visionStatusResult] = await Promise.all([
      loadSystem(),
      loadVision(),
    ]);

    if (visionStatusResult?.online) {
      await Promise.all([
        loadGrassCondition(),
        loadRainDetection(),
      ]);
      return;
    }

    setGrassCondition((previous) => previous?.ok === false
      ? previous
      : {
          ok: false,
          condition: "unknown",
          error: "Vision analysis unavailable",
          detail:
            "Vision node is offline. Lawn condition is not being evaluated.",
        },
    );

    setRainDetection((previous) => previous?.ok === false
      ? previous
      : {
          ok: false,
          rain_detected: false,
          confidence: "unknown",
          error: "Vision rain detection unavailable",
          detail:
            "Vision node is offline. Rain/wet-surface evidence is unavailable.",
        },
    );
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

  function chooseRecorderOptions(): MediaRecorderOptions | undefined {
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
  }

  function saveRecording() {
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
  }

  function startRecording() {
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
  }

  function toggleRecording() {
    if (recording) {
      stopRecording(true);
      return;
    }

    startRecording();
  }

  async function startStream() {
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

      await new Promise<void>((resolve) => {
        if (pc.iceGatheringState === "complete") {
          resolve();
          return;
        }

        const checkState = () => {
          if (pc.iceGatheringState === "complete") {
            pc.removeEventListener("icegatheringstatechange", checkState);
            resolve();
          }
        };

        pc.addEventListener("icegatheringstatechange", checkState);

        window.setTimeout(() => {
          pc.removeEventListener("icegatheringstatechange", checkState);
          resolve();
        }, 3000);
      });

      const localDescription = pc.localDescription;

      if (!localDescription?.sdp || !localDescription.type) {
        throw new Error("Failed to create local WebRTC offer.");
      }

      const res = await fetch(`${BACKEND_URL}/v1/vision/offer`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          sdp: localDescription.sdp,
          type: localDescription.type,
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
  }

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

  function openSnapshot() {
    window.open(`${BACKEND_URL}/v1/vision/snapshot?t=${Date.now()}`, "_blank");
  }

  async function autofocusOnce() {
    await fetch(`${BACKEND_URL}/v1/vision/focus`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ mode: "auto_once" }),
    });

    await loadVision();
  }

  async function restartCamera() {
    const confirmed = window.confirm("Restart the vision node camera?");
    if (!confirmed) return;

    await fetch(`${BACKEND_URL}/v1/vision/restart-camera`, {
      method: "POST",
    });

    await loadVision();
  }

  const streamButtonLabel = !visionOnline
    ? "Vision Offline"
    : streamState === "connected"
      ? "Connected"
      : streamState === "connecting"
        ? "Connecting..."
        : streamState === "error"
          ? "Reconnect"
          : "Connect";

  const visionAnalysisAvailable =
    visionOnline &&
    rainDetection?.ok !== false &&
    environment?.inputs?.visual_evidence_detected !== undefined;

  const cameraRainDetected =
    visionAnalysisAvailable &&
    Boolean(
      environment?.inputs?.visual_evidence_detected ||
        environment?.inputs?.camera_rain_detected ||
        environment?.inputs?.visual_wet_surface_evidence ||
        rainDetection?.rain_detected,
    );

  const rainEvidenceLabel = !visionAnalysisAvailable
    ? "Unavailable"
    : cameraRainDetected
      ? "Wet Surface"
      : "Clear / Dry";

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
              Orion Vision Node
            </p>

            <h1 className="mt-2 text-4xl font-semibold tracking-tight text-white">
              Environmental Vision
            </h1>

            <p className="mt-2 max-w-3xl text-neutral-400">
              Dedicated vision page for live camera streaming, lawn condition,
              visual rain evidence, environmental decisions, and irrigation guidance.
            </p>
          </div>

          <div className={`rounded-full px-4 py-2 text-sm font-semibold ${stateClasses(visionState)}`}>
            {visionStatus}
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-4">
          <StatCard
            label="Decision"
            value={formatMode(environment?.recommendation)}
            state={recommendationState(environment?.recommendation)}
            sub="Environmental recommendation"
          />
          <StatCard
            label="Confidence"
            value={formatMode(environment?.confidence)}
            state={confidenceState(environment?.confidence)}
            sub="Decision certainty"
          />
          <StatCard
            label="Rain Probability"
            value={formatRatioPercent(environment?.inputs?.rain_probability)}
            state={Number(environment?.inputs?.rain_probability ?? 0) >= 0.7 ? "warn" : "neutral"}
            sub="Weather input"
          />
          <StatCard
            label="Visual Condition"
            value={rainEvidenceLabel}
            state={!visionAnalysisAvailable ? "neutral" : cameraRainDetected ? "warn" : "neutral"}
            sub={visionAnalysisAvailable ? "Camera evidence" : "Camera unavailable"}
          />
        </div>

        <section className="mt-6 rounded-2xl border border-neutral-800 bg-neutral-950 shadow-lg">
          <div className="flex items-start justify-between gap-4 border-b border-neutral-800 p-5">
            <div>
              <h2 className="text-xl font-semibold">Environmental Camera Feed</h2>
              <p className="mt-1 text-sm text-neutral-500">
                Pi Zero 2 W · IMX708 · WebRTC
              </p>
            </div>

            <span
              className={`rounded-full px-3 py-1 text-xs font-semibold ${stateClasses(
                streamPillState,
              )}`}
            >
              {streamLabel}
            </span>
          </div>

          <div className="relative bg-black">
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className="aspect-video w-full bg-black object-contain"
            />

            {!visionOnline ? (
              <div className="absolute inset-0 flex items-center justify-center bg-black/85 p-6 text-center">
                <div className="max-w-2xl rounded-2xl border border-amber-500/30 bg-amber-500/10 p-6 shadow-lg">
                  <p className="text-xs uppercase tracking-[0.2em] text-amber-300">
                    Vision Degraded Mode
                  </p>
                  <h3 className="mt-2 text-2xl font-semibold text-white">
                    Vision node offline
                  </h3>
                  <p className="mt-3 text-sm leading-6 text-amber-100/90">
                    Camera stream, snapshots, lawn analysis, and visual rain
                    evidence are unavailable. Orion is continuing with weather,
                    sprinkler, thermostat, and operations telemetry.
                  </p>

                  <div className="mt-4 grid gap-2 text-left text-xs text-neutral-300">
                    <p>
                      <span className="text-neutral-500">Primary:</span>{" "}
                      {displayConfiguredEndpoint(
                        vision?.vision_node_url || vision?.node_url,
                        "Local vision endpoint configured",
                      )}
                    </p>
                    <p>
                      <span className="text-neutral-500">Fallback:</span>{" "}
                      {displayConfiguredEndpoint(
                        vision?.vision_node_fallback_url,
                        "Private fallback endpoint configured",
                      )}
                    </p>
                    <p>
                      <span className="text-neutral-500">Detail:</span>{" "}
                      {sanitizeDetail(vision?.detail || vision?.error || vision?.message)}
                    </p>
                  </div>
                </div>
              </div>
            ) : null}
          </div>

          <div className="grid grid-cols-2 gap-3 border-t border-neutral-800 p-4 md:grid-cols-4">
            <Button
              onClick={startStream}
              disabled={
                !visionOnline ||
                streamState === "connecting" ||
                streamState === "connected"
              }
            >
              {streamButtonLabel}
            </Button>

            <Button
              onClick={stopStream}
              disabled={streamState === "idle"}
              variant="secondary"
            >
              Disconnect
            </Button>

            <Button
              onClick={toggleRecording}
              disabled={streamState !== "connected"}
              variant={recording ? "danger" : "success"}
            >
              {recording
                ? "Stop Recording"
                : streamState === "connected"
                  ? "Record Clip"
                  : "Recording Unavailable"}
            </Button>

            <Button
              onClick={openSnapshot}
              disabled={!visionOnline}
              variant="secondary"
            >
              {visionOnline ? "Snapshot" : "Snapshot Unavailable"}
            </Button>
          </div>

          {lastError ? (
            <div className="border-t border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
              {lastError}
            </div>
          ) : null}
        </section>

        <div className="mt-6 grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <Section
            title="Environmental Decision"
            subtitle="Weather, camera, lawn condition, and irrigation context"
            status={formatMode(environment?.confidence || "unknown")}
            statusState={confidenceState(environment?.confidence)}
          >
            <div className="grid grid-cols-2 gap-3">
              <Field
                label="Decision"
                value={formatMode(environment?.recommendation)}
                state={recommendationState(environment?.recommendation)}
              />
              <Field
                label="Lawn Need"
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
                label="Next Run"
                value={displayValue(environment?.irrigation?.next_irrigation)}
              />
              <Field
                label="Heat Stress"
                value={displayValue(environment?.inputs?.heat_stress)}
                state={environment?.inputs?.heat_stress ? "warn" : "neutral"}
              />
            </div>

            <div className="mt-4 rounded-xl border border-neutral-800 bg-neutral-900 p-4 text-sm leading-6 text-neutral-300">
              {environment?.reason || "No environmental decision available."}
            </div>

            <div className="mt-4 rounded-xl border border-neutral-800 bg-black p-4 text-xs leading-5 text-neutral-300">
              {environment?.safety?.reason ||
                "Environmental recommendations are advisory. Hardware actions remain gated behind operator approval."}
            </div>
          </Section>

          <Section
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
              <Field label="Resolution" value={vision?.resolution || "—"} />
              <Field
                label="Clients"
                value={vision?.streaming_clients ?? 0}
                state={Number(vision?.streaming_clients ?? 0) > 0 ? "active" : "neutral"}
              />
              <Field
                label="Focus"
                value={formatMode(vision?.focus_mode)}
                state={vision?.focus_mode ? "good" : "neutral"}
              />
              <Field label="Lens" value={formatNumber(vision?.lens_position, 2)} />
              <Field
                label="Last Frame"
                value={
                  Number.isFinite(Number(vision?.last_frame_age))
                    ? `${Number(vision?.last_frame_age).toFixed(2)}s ago`
                    : "—"
                }
                state={Number(vision?.last_frame_age ?? 999) <= 2 ? "good" : "warn"}
              />
              <Field
                label="Fault"
                value={
                  !visionOnline
                    ? "Node Unreachable"
                    : vision?.fault
                      ? vision?.fault_code || "Fault"
                      : "None"
                }
                state={!visionOnline || vision?.fault ? "bad" : "good"}
              />
            </div>

            {vision?.error ? (
              <div className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
                {vision.error}
                {vision.detail ? ` · ${vision.detail}` : ""}
              </div>
            ) : null}

            <div className="mt-4 flex flex-wrap gap-3">
              <Button onClick={refreshAll} variant="secondary">
                Refresh
              </Button>
              <Button onClick={autofocusOnce} disabled={!visionOnline} variant="secondary">
                {visionOnline ? "Autofocus" : "Focus Unavailable"}
              </Button>
              <Button onClick={restartCamera} disabled={!visionOnline} variant="ghost">
                {visionOnline ? "Restart Camera" : "Restart Unavailable"}
              </Button>
            </div>
          </Section>
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_1fr]">
          <Section
            title="Lawn Condition"
            subtitle="Camera-based grass color and dryness analysis"
            status={visionAnalysisAvailable ? formatMode(grassCondition?.condition || "waiting") : "Unavailable"}
            statusState={lawnState(grassCondition)}
          >
            <div className="grid grid-cols-2 gap-3">
              <Field
                label="Condition"
                value={lawnConditionLabel(grassCondition)}
                state={lawnState(grassCondition)}
              />
              <Field
                label="Score"
                value={
                  Number.isFinite(Number(grassCondition?.score))
                    ? `${Number(grassCondition?.score).toFixed(0)} / 100`
                    : "—"
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
              <Field label="Dryness" value={formatNumber(grassCondition?.dryness_index, 3)} />
              <Field label="Green" value={formatPercent(grassCondition?.green_percent, 1)} state="good" />
              <Field
                label="Dry Tones"
                value={formatPercent(grassCondition?.dry_percent, 1)}
                state={Number(grassCondition?.dry_percent ?? 0) >= 15 ? "warn" : "neutral"}
              />
              <Field label="Valid Area" value={formatPercent(grassCondition?.valid_percent, 1)} />
            </div>

            {grassCondition?.reason ? (
              <p className="mt-4 rounded-xl border border-neutral-800 bg-neutral-900 p-4 text-sm leading-6 text-neutral-300">
                {grassCondition.reason}
              </p>
            ) : null}

            {grassCondition?.error ? (
              <div className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
                {grassCondition.error}
                {grassCondition.detail ? ` · ${grassCondition.detail}` : ""}
              </div>
            ) : null}

            <Button
              onClick={loadGrassCondition}
              disabled={!visionOnline}
              variant="secondary"
              className="mt-4"
            >
              Analyze Lawn
            </Button>
          </Section>

          <Section
            title="Visual Condition"
            subtitle="Camera-assisted visual surface analysis"
            status={rainEvidenceLabel}
            statusState={cameraRainDetected ? "warn" : "neutral"}
          >
            <div className="grid grid-cols-2 gap-3">
              <Field
                label="Condition"
                value={rainEvidenceLabel}
                state={cameraRainDetected ? "warn" : "neutral"}
              />
              <Field
                label="Confidence"
                value={formatMode(rainDetection?.confidence || environment?.inputs?.camera_rain_confidence)}
                state={confidenceState(rainDetection?.confidence || environment?.inputs?.camera_rain_confidence)}
              />
              <Field
                label="Surface Score"
                value={formatNumber(rainDetection?.wetness_score ?? environment?.inputs?.camera_wetness_score, 3)}
              />
              <Field
                label="Motion"
                value={formatNumber(rainDetection?.motion_score ?? environment?.inputs?.camera_motion_score, 3)}
              />
              <Field label="Dark Area" value={formatPercent(rainDetection?.dark_percent, 1)} />
              <Field label="Reflection" value={formatPercent(rainDetection?.reflection_percent, 1)} />
            </div>

            {rainDetection?.reason ? (
              <p className="mt-4 rounded-xl border border-neutral-800 bg-neutral-900 p-4 text-sm leading-6 text-neutral-300">
                {rainDetection.reason}
              </p>
            ) : null}

            {rainDetection?.error ? (
              <div className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
                {rainDetection.error}
                {rainDetection.detail ? ` · ${rainDetection.detail}` : ""}
              </div>
            ) : null}

            <Button
              onClick={loadRainDetection}
              disabled={!visionOnline}
              variant="secondary"
              className="mt-4"
            >
              Analyze Rain
            </Button>
          </Section>
        </div>

        <Section
          title="Weather Context"
          subtitle={weather?.location || "Outdoor conditions used by the vision decision model"}
          status={Number(weather?.rain_chance ?? 0) >= 70 ? "Rain likely" : "Monitoring"}
          statusState={Number(weather?.rain_chance ?? 0) >= 70 ? "warn" : "good"}
        >
          <div className="grid gap-3 md:grid-cols-4">
            <Field label="Temperature" value={formatTemp(weather?.temp)} />
            <Field label="Feels Like" value={formatTemp(weather?.feels_like)} />
            <Field
              label="Rain Chance"
              value={Number.isFinite(Number(weather?.rain_chance)) ? `${Number(weather?.rain_chance).toFixed(0)}%` : "—"}
              state={Number(weather?.rain_chance ?? 0) >= 70 ? "warn" : "neutral"}
            />
            <Field label="Humidity" value={formatPercent(weather?.humidity, 1)} />
          </div>
        </Section>

        <section className="mt-6 rounded-2xl border border-neutral-800 bg-neutral-950 p-5 shadow-lg">
          <details>
            <summary className="cursor-pointer text-sm font-semibold text-neutral-300">
              Raw vision JSON
            </summary>
            <pre className="mt-4 max-h-96 overflow-auto rounded-xl bg-black p-4 text-xs leading-5 text-neutral-300">
              {formatJson({
                vision,
                grassCondition,
                rainDetection,
                environment,
              })}
            </pre>
          </details>
        </section>
      </div>
    </main>
  );
}
