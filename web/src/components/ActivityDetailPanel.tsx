import { Tooltip } from '@heroui/react'
import type { ActivityDetail } from '../api'
import { fmtSecs, paceFromSpeed } from '../format'
import { ZONE_COLORS, ZONE_NAMES, ZONE_TIPS } from '../charts/chartTheme'

export function ActivityDetailPanel({ data }: { data: ActivityDetail }) {
  const zones = (data.hr_zones || []).filter((z) => z.secs > 0)
  const splits = data.splits || []
  const maxSecs = zones.length ? Math.max(...zones.map((z) => z.secs)) : 0

  if (!zones.length && !splits.length) {
    return <p className="py-3 text-xs text-default-400">Sem dados de zonas/splits para esta atividade.</p>
  }

  return (
    <div className="flex flex-col gap-4 py-3">
      {zones.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <span className="text-xs font-semibold uppercase tracking-wide text-default-400">
            Zonas de frequência cardíaca
          </span>
          {zones.map((z) => {
            const idx = z.zone - 1
            const w = maxSecs ? (z.secs / maxSecs) * 100 : 0
            return (
              <div key={z.zone} className="flex items-center gap-2 text-xs">
                <span className="flex w-16 items-center gap-1 font-medium">
                  {ZONE_NAMES[idx] || `Z${z.zone}`}
                  <span className="text-default-400">{z.low ?? ''}</span>
                </span>
                <Tooltip content={ZONE_TIPS[idx] || ''} className="max-w-64">
                  <span className="flex h-4 w-4 shrink-0 cursor-help items-center justify-center rounded-full border border-default-300 text-[10px] text-default-400">
                    ?
                  </span>
                </Tooltip>
                <span className="h-4 flex-1 overflow-hidden rounded bg-default-100">
                  <span
                    className="block h-full"
                    style={{ width: `${w}%`, backgroundColor: ZONE_COLORS[idx] || ZONE_COLORS[0] }}
                  />
                </span>
                <span className="w-14 text-right tabular-nums text-default-500">{fmtSecs(z.secs)}</span>
              </div>
            )
          })}
        </div>
      )}

      {splits.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-default-400">
                <th className="py-1 pr-3 font-medium">Km</th>
                <th className="py-1 pr-3 font-medium">Tempo</th>
                <th className="py-1 pr-3 font-medium">Pace</th>
                <th className="py-1 pr-3 font-medium">FC</th>
                <th className="py-1 pr-3 font-medium">Cad</th>
                <th className="py-1 pr-3 font-medium">Elev</th>
              </tr>
            </thead>
            <tbody>
              {splits.map((s, i) => (
                <tr key={i} className="border-t border-default-100">
                  <td className="py-1 pr-3 tabular-nums">{i + 1}</td>
                  <td className="py-1 pr-3 tabular-nums">{fmtSecs(s.duration_s)}</td>
                  <td className="py-1 pr-3 tabular-nums">{paceFromSpeed(s.speed)}</td>
                  <td className="py-1 pr-3 tabular-nums">{s.avg_hr ? Math.round(s.avg_hr) : '--'}</td>
                  <td className="py-1 pr-3 tabular-nums">{s.cadence || '--'}</td>
                  <td className="py-1 pr-3 tabular-nums">{s.elev_gain != null ? `${s.elev_gain}m` : '--'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
