import { Card, CardBody } from '@heroui/react'
import type { DailySnapshot } from '../api'
import { useCountUp } from '../useCountUp'
import { ACCENT_BORDER, ACCENT_TEXT, CARD_CLASS_NO_TOP, type Accent } from '../ui'

interface StatDef {
  label: string
  value: number | null
  unit: string
  icon: string
  accent: Accent
}

function Stat({ label, value, unit, icon, accent }: StatDef) {
  const animated = useCountUp(value)
  const display =
    animated === null ? '--' : Number.isInteger(value) ? Math.round(animated).toLocaleString('pt-BR') : animated.toFixed(1)

  return (
    <Card shadow="sm" className={`${CARD_CLASS_NO_TOP} border-t-2 ${ACCENT_BORDER[accent]}`}>
      <CardBody className="gap-1 py-4 text-center">
        <span className="text-lg leading-none opacity-70" aria-hidden="true">
          {icon}
        </span>
        <span className={`text-2xl font-semibold tabular-nums ${ACCENT_TEXT[accent]}`}>
          {display}
          {value !== null && unit ? <span className="ml-1 text-base font-normal text-default-500">{unit}</span> : null}
        </span>
        <span className="text-sm text-default-500">{label}</span>
      </CardBody>
    </Card>
  )
}

export function StatsBar({ snapshot }: { snapshot: DailySnapshot }) {
  const stats: StatDef[] = [
    { label: 'Passos', value: snapshot.steps, unit: '', icon: '👣', accent: 'primary' },
    { label: 'FC Repouso', value: snapshot.resting_hr, unit: 'bpm', icon: '❤️', accent: 'danger' },
    { label: 'Body Battery', value: snapshot.bb_high, unit: '', icon: '🔋', accent: 'success' },
    { label: 'Estresse', value: snapshot.avg_stress, unit: '', icon: '🧠', accent: 'warning' },
  ]

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {stats.map((s) => (
        <Stat key={s.label} {...s} />
      ))}
    </div>
  )
}
