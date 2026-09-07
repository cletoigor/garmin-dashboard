import { useEffect, useRef, useState } from 'react'
import { Card, CardBody, CardHeader, Spinner } from '@heroui/react'
import { getReport, type TrainingReport } from '../api'
import { PeriodToggle } from './PeriodToggle'
import { ActivityRow } from './ActivityRow'
import { CARD_CLASS } from '../ui'

interface Props {
  initialReport: TrainingReport
}

function fmtNum(n: number | undefined | null): string {
  return (n || 0).toLocaleString('pt-BR')
}

export function TabTreino({ initialReport }: Props) {
  const [period, setPeriod] = useState(7)
  const [report, setReport] = useState<TrainingReport>(initialReport)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const reqSeq = useRef(0)

  useEffect(() => {
    const seq = ++reqSeq.current
    setLoading(true)
    setError(null)
    getReport(period)
      .then((data) => {
        if (seq !== reqSeq.current) return
        setReport(data.report)
      })
      .catch((err: Error) => {
        if (seq !== reqSeq.current) return
        setError(err.message)
      })
      .finally(() => {
        if (seq === reqSeq.current) setLoading(false)
      })
  }, [period])

  const s = report.summary || {}

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="text-sm text-default-500">
          ultimos {period} dias
        </span>
        <PeriodToggle value={period} onChange={setPeriod} disabled={loading} />
      </div>

      {error && <p className="text-sm text-danger">Erro ao carregar dados: {error}</p>}

      <div
        className="grid grid-cols-2 gap-3 transition-opacity duration-300 sm:grid-cols-4"
        style={{ opacity: loading ? 0.4 : 1 }}
      >
        <Card shadow="sm" className={CARD_CLASS}>
          <CardBody className="items-center gap-1 py-4 text-center">
            <span className="text-lg leading-none opacity-70" aria-hidden="true">🏃</span>
            <span className="text-2xl font-semibold text-primary tabular-nums">{s.total_activities || 0}</span>
            <span className="text-xs text-default-500">Atividades</span>
          </CardBody>
        </Card>
        <Card shadow="sm" className={CARD_CLASS}>
          <CardBody className="items-center gap-1 py-4 text-center">
            <span className="text-lg leading-none opacity-70" aria-hidden="true">📍</span>
            <span className="text-2xl font-semibold text-success tabular-nums">{s.total_km || 0}</span>
            <span className="text-xs text-default-500">Km totais</span>
          </CardBody>
        </Card>
        <Card shadow="sm" className={CARD_CLASS}>
          <CardBody className="items-center gap-1 py-4 text-center">
            <span className="text-lg leading-none opacity-70" aria-hidden="true">⏱️</span>
            <span className="text-2xl font-semibold tabular-nums">{s.total_hours || 0}</span>
            <span className="text-xs text-default-500">Horas</span>
          </CardBody>
        </Card>
        <Card shadow="sm" className={CARD_CLASS}>
          <CardBody className="items-center gap-1 py-4 text-center">
            <span className="text-lg leading-none opacity-70" aria-hidden="true">🔥</span>
            <span className="text-2xl font-semibold text-warning tabular-nums">{fmtNum(s.total_calories)}</span>
            <span className="text-xs text-default-500">Calorias</span>
          </CardBody>
        </Card>
      </div>

      {report.by_type && report.by_type.length > 0 && (
        <Card shadow="sm" className={CARD_CLASS}>
          <CardHeader className="gap-2 font-semibold">
            <span aria-hidden="true">📊</span> Por tipo de atividade
          </CardHeader>
          <CardBody>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-default-400">
                    <th className="py-1 pr-3 font-medium">Tipo</th>
                    <th className="py-1 pr-3 font-medium">Qtd</th>
                    <th className="py-1 pr-3 font-medium">Distância</th>
                    <th className="py-1 pr-3 font-medium">FC média</th>
                    <th className="py-1 pr-3 font-medium">Duração</th>
                  </tr>
                </thead>
                <tbody>
                  {report.by_type.map((t) => (
                    <tr key={t.type} className="border-t border-default-100">
                      <td className="py-2 pr-3 font-medium">{t.label}</td>
                      <td className="py-2 pr-3 tabular-nums">{t.count}x</td>
                      <td className="py-2 pr-3 tabular-nums">{t.distance_km} km</td>
                      <td className="py-2 pr-3 tabular-nums">{t.avg_hr || '--'} bpm</td>
                      <td className="py-2 pr-3 tabular-nums">{t.duration_min} min</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardBody>
        </Card>
      )}

      {report.recent && report.recent.length > 0 && (
        <Card shadow="sm" className={CARD_CLASS}>
          <CardHeader className="flex-col items-start gap-0.5">
            <span className="font-semibold">🏃 Atividades recentes</span>
            <span className="text-xs font-normal text-default-400">clique para ver zonas de FC e splits</span>
          </CardHeader>
          <CardBody>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-default-400">
                    <th className="py-1 pr-3 font-medium">Data</th>
                    <th className="py-1 pr-3 font-medium">Nome</th>
                    <th className="py-1 pr-3 font-medium">Dist</th>
                    <th className="py-1 pr-3 font-medium">Duração</th>
                    <th className="py-1 pr-3 font-medium">FC méd</th>
                    <th className="py-1 pr-3 font-medium">Cal</th>
                    <th className="py-1 pr-3 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {report.recent.map((a) => (
                    <ActivityRow key={a.id ?? `${a.date}-${a.name}`} activity={a} />
                  ))}
                </tbody>
              </table>
            </div>
          </CardBody>
        </Card>
      )}

      {loading && (
        <div className="flex justify-center py-2">
          <Spinner size="sm" label="Carregando..." />
        </div>
      )}
    </div>
  )
}
