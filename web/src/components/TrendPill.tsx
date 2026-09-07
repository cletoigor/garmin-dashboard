import { Card, CardBody } from '@heroui/react'
import type { Trend } from '../api'
import { useCountUp } from '../useCountUp'
import { CARD_CLASS_NO_LEFT } from '../ui'

const ARROW: Record<Trend['direction'], string> = { up: '▲', down: '▼', flat: '▬' }

const SENTIMENT_CLASS: Record<Trend['sentiment'], string> = {
  positive: 'text-success',
  negative: 'text-danger',
  neutral: 'text-default-500',
}

// Borda esquerda colorida por sentimento, pra ler o card de relance sem precisar
// da seta/percentual.
const SENTIMENT_BORDER: Record<Trend['sentiment'], string> = {
  positive: 'border-l-success',
  negative: 'border-l-danger',
  neutral: 'border-l-default-300',
}

export function TrendPill({ trend }: { trend: Trend }) {
  const animated = useCountUp(trend.current)
  const display = animated === null ? '--' : animated.toFixed(1).replace(/\.0$/, '')

  return (
    <Card shadow="sm" className={`${CARD_CLASS_NO_LEFT} border-l-4 ${SENTIMENT_BORDER[trend.sentiment]}`}>
      <CardBody className="gap-1 py-3">
        <span className="text-xs uppercase tracking-wide text-default-500">{trend.label}</span>
        <span className="text-xl font-semibold tabular-nums">
          {display}
          {trend.unit ? <span className="ml-1 text-sm font-normal text-default-500">{trend.unit}</span> : null}
        </span>
        <span className={`text-sm font-medium ${SENTIMENT_CLASS[trend.sentiment]}`}>
          {ARROW[trend.direction]} {trend.change_pct}%
        </span>
        <span className="text-xs text-default-400">
          anterior: {trend.previous}
          {trend.unit ? ` ${trend.unit}` : ''}
        </span>
      </CardBody>
    </Card>
  )
}
