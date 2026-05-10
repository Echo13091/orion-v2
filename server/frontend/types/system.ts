export type Message = {
  role: "user" | "assistant";
  content: string;
};

export type Session = {
  id: string;
  title: string;
};

export type LastDecision = {
  action: string;
  reason?: string;
  params?: Record<string, unknown>;
  source?: string;
  requires_execution?: boolean;
  result?: unknown;
  time?: number;
};

export type SprinklerState = {
  online?: boolean;
  source?: string | null;
  running?: boolean;
  zone?: number | string | null;
  mode?: string | null;
  next_run?: string | null;
  error?: string;
  raw?: unknown;
};

export type ThermostatState = {
  online?: boolean;
  source?: string | null;
  temp?: number | null;
  humidity?: number | null;
  mode?: string | null;
  cooling?: boolean;
  heating?: boolean;
  fan?: boolean;
  error?: string;
  raw?: unknown;
};

export type WeatherState = {
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

export type IrrigationSchedule = {
  enabled?: boolean;
  days?: string[];
  start_time?: string | null;
  duration_minutes?: number | null;
  zones?: number[];
  skip_next_run?: boolean;
  skip_reason?: string | null;
  updated_at?: number | null;
  controller?: string;
  hardware_sync_required?: boolean;
  skip_if_rain_likely?: boolean;
  last_run_key?: string | null;
  active_run?: unknown;
  last_scheduler_event?: unknown;
  hardware_synced?: boolean;
  hardware_result?: unknown;
};

export type AutomationMode = "manual" | "auto";

export type SystemState = {
  mode: string;
  automation_mode?: AutomationMode;
  fault: string | null;
  cpu: number;
  memory: number;
  gpu?: number;
  ai_status: string;
  last_update: number;
  last_decision: LastDecision | null;
  last_execution?: unknown;
  manual_override_until?: number | null;
  manual_override_reason?: string | null;
  fault_status?: Record<string, unknown>;
  irrigation_schedule?: IrrigationSchedule;
  sprinkler?: SprinklerState;
  thermostat?: ThermostatState;
  weather?: WeatherState;
};

export type StatusState = "good" | "bad" | "warn" | "neutral" | "active";

export type RecommendationAction =
  | "observe"
  | "nothing"
  | "delay_irrigation"
  | "stop_sprinkler"
  | "set_thermostat";

export type OrionRecommendation = {
  title: string;
  detail: string;
  state: StatusState;
  action: RecommendationAction;
  params?: Record<string, unknown>;
  canApply: boolean;
  applyLabel?: string;
};
