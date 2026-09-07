import { Card, CardBody, CardHeader, Progress } from '@heroui/react'
import type { AppState } from '../api'
import { CARD_CLASS } from '../ui'

interface HealthMetric {
  label: string
  icon: string
  raw: number | null | undefined
  decimals?: number
  unit?: string
}

function HealthGrid({ state }: { state: AppState }) {
  const s = state.snapshot
  const metrics: HealthMetric[] = [
    { label: 'Sono', icon: '🌙', raw: s.sleep_hours, decimals: 1, unit: 'h' },
    { label: 'VFC (HRV)', icon: '💓', raw: s.avg_hrv, unit: ' ms' },
    { label: 'SpO2', icon: '🫁', raw: s.avg_spo2, unit: '%' },
    { label: 'Min. Ativos', icon: '⏱️', raw: s.active_minutes, unit: ' min' },
    { label: 'Calorias', icon: '🔥', raw: s.calories, unit: ' kcal' },
    { label: 'Andares', icon: '🏢', raw: s.floors },
    { label: 'FC Repouso', icon: '❤️', raw: s.resting_hr, unit: ' bpm' },
    { label: 'Distancia', icon: '📍', raw: s.distance_km, decimals: 1, unit: ' km' },
  ]

  // Oculta celulas sem dado (null/undefined) para nao poluir a grade com "--".
  const available = metrics.filter((m) => m.raw !== null && m.raw !== undefined)

  if (available.length === 0) return null

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {available.map((m) => (
        <Card key={m.label} shadow="sm" className={CARD_CLASS}>
          <CardBody className="gap-1 py-3 text-center">
            <span className="text-base leading-none opacity-70" aria-hidden="true">
              {m.icon}
            </span>
            <span className="text-lg font-semibold tabular-nums">
              {(m.raw as number).toFixed(m.decimals ?? 0)}
              {m.unit ?? ''}
            </span>
            <span className="text-xs text-default-500">{m.label}</span>
          </CardBody>
        </Card>
      ))}
    </div>
  )
}

function SleepBreakdown({ state }: { state: AppState }) {
  const s = state.snapshot
  const segments = [
    { label: 'Profundo', minutes: s.deep_sleep_min ?? 0, color: 'bg-indigo-500' },
    { label: 'REM', minutes: s.rem_sleep_min ?? 0, color: 'bg-purple-400' },
    { label: 'Leve', minutes: s.light_sleep_min ?? 0, color: 'bg-sky-400' },
    { label: 'Acordado', minutes: s.awake_min ?? 0, color: 'bg-default-300' },
  ]
  const total = segments.reduce((acc, seg) => acc + seg.minutes, 0)

  // Sem nenhum dado de sono para o dia exibido: nao renderiza o card (pedido explicito).
  if (total === 0 && !s.sleep_hours) return null

  return (
    <Card shadow="sm" className={CARD_CLASS}>
      <CardHeader className="gap-2 font-semibold">
        <span aria-hidden="true">🌙</span> Composição do sono
      </CardHeader>
      <CardBody className="gap-3">
        <div className="flex h-4 w-full overflow-hidden rounded-full bg-default-100">
          {segments.map((seg) =>
            seg.minutes > 0 ? (
              <div
                key={seg.label}
                className={seg.color}
                style={{ width: `${(seg.minutes / total) * 100}%` }}
                title={`${seg.label}: ${seg.minutes} min`}
              />
            ) : null,
          )}
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-default-500">
          {segments.map((seg) => (
            <span key={seg.label} className="flex items-center gap-1.5">
              <span className={`h-2 w-2 rounded-full ${seg.color}`} />
              {seg.label}: {seg.minutes} min
            </span>
          ))}
        </div>
      </CardBody>
    </Card>
  )
}

function GoalsProgress({ state }: { state: AppState }) {
  return (
    <Card shadow="sm" className={CARD_CLASS}>
      <CardHeader className="gap-2 font-semibold">
        <span aria-hidden="true">🎯</span> Progresso das metas
      </CardHeader>
      <CardBody className="gap-5">
        {state.goals.map((g) => (
          <div key={g.key} className="flex flex-col gap-1.5">
            <div className="flex justify-between text-sm">
              <span>{g.label}</span>
              <span className="text-default-500">
                {g.value.toLocaleString('pt-BR')}
                {g.unit} / {g.goal.toLocaleString('pt-BR')}
                {g.unit}
              </span>
            </div>
            <Progress
              aria-label={g.label}
              value={g.pct}
              maxValue={100}
              size="md"
              radius="full"
              color={g.pct >= 100 ? 'success' : 'primary'}
            />
          </div>
        ))}
      </CardBody>
    </Card>
  )
}

export function TabHoje({ state }: { state: AppState }) {
  return (
    <div className="flex flex-col gap-5">
      <Card shadow="sm" className={CARD_CLASS}>
        <CardBody>
          <p className="text-base leading-relaxed">{state.daily_summary}</p>
          {state.snapshot_is_fallback && (
            <p className="mt-2 text-xs text-warning">
              Exibindo o ultimo dia com dados completos ({state.snapshot.date}).
            </p>
          )}
        </CardBody>
      </Card>

      <HealthGrid state={state} />
      <SleepBreakdown state={state} />
      <GoalsProgress state={state} />
    </div>
  )
}
