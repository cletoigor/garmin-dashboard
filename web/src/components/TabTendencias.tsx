import { useEffect, useMemo, useRef, useState } from 'react'
import { Line, Bar } from 'react-chartjs-2'
import { Card, CardBody, CardHeader, Spinner } from '@heroui/react'
import { getReport, type DailySnapshot, type Trends } from '../api'
import { useTheme } from '../theme'
import { lineChartOptions, sleepChartOptions } from '../charts/chartTheme'
import { fmtDayMonth } from '../format'
import { PeriodToggle } from './PeriodToggle'
import { TrendPill } from './TrendPill'
import { CARD_CLASS } from '../ui'

const CHART_ICONS: Record<string, string> = {
  steps: '👣',
  hr: '❤️',
  bb: '🔋',
  stress: '🧠',
}

// Reproduz o filtro da versao vanilla: valores nulos/zerados viram gap no grafico.
function toGapped(values: Array<number | null | undefined>): Array<number | null> {
  return values.map((v) => (v === null || v === undefined || v <= 0 ? null : v))
}

interface Props {
  initialDailyData: DailySnapshot[]
  initialTrends: Trends
}

export function TabTendencias({ initialDailyData, initialTrends }: Props) {
  const { theme } = useTheme()
  const [period, setPeriod] = useState(7)
  const [dailyData, setDailyData] = useState<DailySnapshot[]>(initialDailyData.slice(0, 7))
  const [trends, setTrends] = useState<Trends>(initialTrends)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const reqSeq = useRef(0)

  useEffect(() => {
    const seq = ++reqSeq.current
    setLoading(true)
    setError(null)
    getReport(period)
      .then((data) => {
        if (seq !== reqSeq.current) return // resposta antiga descartada
        setDailyData(data.daily)
        setTrends(data.trends)
      })
      .catch((err: Error) => {
        if (seq !== reqSeq.current) return
        setError(err.message)
      })
      .finally(() => {
        if (seq === reqSeq.current) setLoading(false)
      })
  }, [period])

  const chronological = useMemo(() => [...dailyData].reverse(), [dailyData])
  const labels = useMemo(() => chronological.map((d) => fmtDayMonth(d.date)), [chronological])

  const stepsData = useMemo(() => toGapped(chronological.map((d) => d.steps)), [chronological])
  const hrData = useMemo(() => toGapped(chronological.map((d) => d.resting_hr)), [chronological])
  const bbData = useMemo(() => toGapped(chronological.map((d) => d.bb_high)), [chronological])
  const stressData = useMemo(() => toGapped(chronological.map((d) => d.avg_stress)), [chronological])

  const lineCharts = useMemo(
    () => [
      {
        key: 'steps',
        title: 'Passos',
        color: 'rgb(88,166,255)',
        data: stepsData,
        opts: { suggestedMin: 0, unit: 'passos' },
      },
      {
        key: 'hr',
        title: 'FC Repouso',
        color: 'rgb(248,81,73)',
        data: hrData,
        opts: { suggestedMin: 40, suggestedMax: 80, unit: 'bpm' },
      },
      {
        key: 'bb',
        title: 'Body Battery',
        color: 'rgb(63,185,80)',
        data: bbData,
        opts: { suggestedMin: 0, suggestedMax: 100, unit: '' },
      },
      {
        key: 'stress',
        title: 'Estresse',
        color: 'rgb(210,153,34)',
        data: stressData,
        opts: { suggestedMin: 0, suggestedMax: 100, unit: '' },
      },
    ],
    [stepsData, hrData, bbData, stressData],
  )

  const sleepData = useMemo(
    () => ({
      labels,
      datasets: [
        {
          label: 'Profundo',
          data: chronological.map((d) => d.deep_sleep_min || 0),
          backgroundColor: 'rgba(79,70,229,0.85)',
          borderRadius: 2,
        },
        {
          label: 'REM',
          data: chronological.map((d) => d.rem_sleep_min || 0),
          backgroundColor: 'rgba(217,70,239,0.85)',
          borderRadius: 2,
        },
        {
          label: 'Leve',
          data: chronological.map((d) => d.light_sleep_min || 0),
          backgroundColor: 'rgba(34,211,238,0.85)',
          borderRadius: 2,
        },
        {
          label: 'Acordado',
          data: chronological.map((d) => d.awake_min || 0),
          backgroundColor: 'rgba(248,113,113,0.85)',
          borderRadius: 2,
        },
      ],
    }),
    [chronological, labels],
  )

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="text-sm text-default-500">
          ultimos {period} dias vs {period} anteriores
        </span>
        <PeriodToggle value={period} onChange={setPeriod} disabled={loading} />
      </div>

      {error && <p className="text-sm text-danger">Erro ao carregar dados: {error}</p>}

      <div
        className="grid grid-cols-2 gap-3 transition-opacity duration-300 sm:grid-cols-5"
        style={{ opacity: loading ? 0.4 : 1 }}
      >
        {Object.entries(trends).map(([key, t]) => (
          <TrendPill key={key} trend={t} />
        ))}
      </div>

      <div
        className="grid grid-cols-1 gap-4 transition-opacity duration-300 md:grid-cols-2"
        style={{ opacity: loading ? 0.35 : 1 }}
      >
        {lineCharts.map((c) => (
          <Card key={c.key} shadow="sm" className={CARD_CLASS}>
            <CardHeader className="gap-2 font-semibold">
              <span aria-hidden="true">{CHART_ICONS[c.key]}</span> {c.title}
            </CardHeader>
            <CardBody style={{ height: 220 }}>
              <Line
                data={{
                  labels,
                  datasets: [
                    {
                      label: c.title,
                      data: c.data,
                      borderColor: c.color,
                      backgroundColor: c.color.replace('rgb', 'rgba').replace(')', ',0.08)'),
                      fill: true,
                      tension: 0.3,
                      pointRadius: 4,
                      pointHoverRadius: 6,
                      pointBackgroundColor: c.color,
                      pointBorderColor: theme === 'dark' ? '#1a1f27' : '#ffffff',
                      pointBorderWidth: 2,
                      spanGaps: true,
                    },
                  ],
                }}
                options={lineChartOptions(theme, c.title, c.opts)}
              />
            </CardBody>
          </Card>
        ))}

        <Card shadow="sm" className={`${CARD_CLASS} md:col-span-2`}>
          <CardHeader className="gap-2 font-semibold">
            <span aria-hidden="true">🌙</span> Composição do sono
          </CardHeader>
          <CardBody style={{ height: 240 }}>
            <Bar data={sleepData} options={sleepChartOptions(theme)} />
          </CardBody>
        </Card>
      </div>

      {loading && (
        <div className="flex justify-center py-2">
          <Spinner size="sm" label="Carregando..." />
        </div>
      )}
    </div>
  )
}
