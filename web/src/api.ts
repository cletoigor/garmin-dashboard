// Tipos e helpers de fetch para a API do backend Flask (Garmin dashboard).

export interface DailySnapshot {
  date: string
  steps: number | null
  calories: number | null
  resting_hr: number | null
  avg_stress: number | null
  max_stress: number | null
  bb_high: number | null
  bb_low: number | null
  active_minutes: number | null
  floors: number | null
  distance_km: number | null
  sleep_hours: number | null
  deep_sleep_min: number | null
  rem_sleep_min: number | null
  light_sleep_min: number | null
  awake_min: number | null
  avg_spo2: number | null
  avg_hrv: number | null
  sleep_score: number | null
  hr_min: number | null
  hr_max: number | null
  avg_respiration: number | null
  sleep_respiration: number | null
}

export type TrendDirection = 'up' | 'down' | 'flat'
export type TrendSentiment = 'positive' | 'negative' | 'neutral'

export interface Trend {
  label: string
  current: number
  previous: number
  change_pct: number
  direction: TrendDirection
  sentiment: TrendSentiment
  unit: string
}

export type Trends = Record<string, Trend>

export interface GoalProgress {
  key: 'steps_day' | 'km_week' | 'active_min_week'
  label: string
  value: number
  goal: number
  unit: string
  pct: number
  color: string
}

export interface GoalTargets {
  steps_day: number
  km_week: number
  active_min_week: number
}

export interface FitnessPredictions {
  '5k': number | null
  '10k': number | null
  half: number | null
  marathon: number | null
}

export interface Fitness {
  vo2max: number | null
  vo2max_date: string | null
  predictions: FitnessPredictions
  fitness_age: number | null
}

export interface SyncStatus {
  ts: number | null
  ok: boolean | null
  age_hours: number | null
  message: string
  level: 'ok' | 'stale' | 'fail' | 'unknown'
  source?: string
}

export interface ActivitySummary {
  id: number
  name: string
  type: string
  date: string
  datetime: string
  duration_min: number
  distance_km: number
  avg_hr: number | null
  max_hr: number | null
  calories: number | null
  avg_speed: number | null
  elevation_gain: number | null
  vo2max: number | null
}

export interface ActivityTypeStat {
  type: string
  label: string
  count: number
  distance_km: number
  avg_hr: number | null
  duration_min: number
}

export interface TrainingReport {
  summary: {
    total_activities?: number
    total_km?: number
    total_hours?: number
    total_calories?: number
  }
  by_type: ActivityTypeStat[]
  insights: Record<string, Array<{ text: string; sentiment: string }>>
  recent: ActivitySummary[]
}

export interface ReportResponse {
  report: TrainingReport
  trends: Trends
  daily: DailySnapshot[]
  days: number
}

export interface HrZone {
  zone: number
  secs: number
  low: number | null
}

export interface ActivitySplit {
  distance_km: number
  duration_s: number
  speed: number | null
  avg_hr: number | null
  cadence: number | null
  elev_gain: number | null
}

export interface ActivityDetail {
  hr_zones: HrZone[]
  splits: ActivitySplit[]
}

export interface AppState {
  snapshot: DailySnapshot
  snapshot_is_fallback: boolean
  today_date: string
  trends: Trends
  report: TrainingReport
  daily_data: DailySnapshot[]
  daily_summary: string
  fitness: Fitness
  goals: GoalProgress[]
  streak: number
  sync: SyncStatus
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init)
  if (!res.ok) {
    throw new Error(`Falha ao chamar ${url}: ${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

export function getState(): Promise<AppState> {
  return fetchJson<AppState>('/api/state')
}

export function getReport(days: number): Promise<ReportResponse> {
  return fetchJson<ReportResponse>(`/api/report?days=${days}`)
}

export function getActivity(id: number): Promise<ActivityDetail> {
  return fetchJson<ActivityDetail>(`/api/activity/${id}`)
}

export function getGoals(): Promise<GoalTargets> {
  return fetchJson<GoalTargets>('/api/goals')
}

export function saveGoals(body: Partial<GoalTargets>): Promise<{ ok: boolean; goals: GoalTargets }> {
  return fetchJson('/api/goals', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function refresh(): Promise<unknown> {
  return fetchJson('/refresh', { method: 'POST' })
}

export function shutdown(): Promise<unknown> {
  return fetchJson('/shutdown', { method: 'POST' })
}
