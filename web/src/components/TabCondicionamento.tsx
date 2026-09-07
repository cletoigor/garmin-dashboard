import { Card, CardBody, CardHeader, Tooltip } from '@heroui/react'
import type { Fitness } from '../api'
import { fmtSecs } from '../format'
import { CARD_CLASS } from '../ui'

const PREDICTIONS: Array<{ key: keyof Fitness['predictions']; label: string }> = [
  { key: '5k', label: '5K' },
  { key: '10k', label: '10K' },
  { key: 'half', label: '21K (Meia)' },
  { key: 'marathon', label: '42K (Maratona)' },
]

export function TabCondicionamento({ fitness }: { fitness: Fitness }) {
  const hasData = Boolean(fitness.vo2max) || Object.values(fitness.predictions || {}).some(Boolean)

  if (!hasData) {
    return (
      <Card shadow="sm" className={CARD_CLASS}>
        <CardBody className="py-10 text-center italic text-default-400">
          Ainda sem dados de condicionamento suficientes.
        </CardBody>
      </Card>
    )
  }

  return (
    <Card shadow="sm" className={CARD_CLASS}>
      <CardHeader className="gap-2 font-semibold">
        <span aria-hidden="true">🔥</span> Condicionamento &amp; previsões de corrida
      </CardHeader>
      <CardBody>
        <div className="flex flex-col gap-6 sm:flex-row sm:items-center">
          {fitness.vo2max && (
            <div className="flex flex-col items-center gap-1 rounded-xl border border-primary/20 bg-primary/5 px-8 py-6 text-center">
              <span className="text-4xl font-bold tabular-nums text-primary">{fitness.vo2max}</span>
              <span className="flex items-center gap-1 text-sm text-default-500">
                VO₂max
                <Tooltip
                  content="Capacidade aeróbica estimada: quanto maior, mais eficiente seu corpo usa oxigênio ao se exercitar."
                  className="max-w-64"
                >
                  <span className="flex h-4 w-4 cursor-help items-center justify-center rounded-full border border-default-300 text-[10px] text-default-400">
                    ?
                  </span>
                </Tooltip>
              </span>
              {fitness.vo2max_date && <span className="text-xs text-default-400">{fitness.vo2max_date}</span>}
              {fitness.fitness_age != null && (
                <span className="mt-1 text-xs text-default-400">Idade de condicionamento: {fitness.fitness_age}</span>
              )}
            </div>
          )}

          <div className="grid flex-1 grid-cols-2 gap-3 sm:grid-cols-4">
            {PREDICTIONS.map((p) => (
              <div
                key={p.key}
                className="flex flex-col items-center gap-1 rounded-xl border border-default-200/70 bg-default-50 px-3 py-4 text-center dark:border-default-100/10"
              >
                <span className="text-xs uppercase tracking-wide text-default-500">{p.label}</span>
                <span className="text-lg font-semibold tabular-nums">{fmtSecs(fitness.predictions?.[p.key])}</span>
              </div>
            ))}
          </div>
        </div>
      </CardBody>
    </Card>
  )
}
