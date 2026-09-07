import { useState } from 'react'
import { Spinner } from '@heroui/react'
import { getActivity, type ActivityDetail, type ActivitySummary } from '../api'
import { ActivityDetailPanel } from './ActivityDetailPanel'

const activityCache = new Map<number, ActivityDetail>()

export function ActivityRow({ activity }: { activity: ActivitySummary }) {
  const [expanded, setExpanded] = useState(false)
  const [detail, setDetail] = useState<ActivityDetail | null>(activityCache.get(activity.id) ?? null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleToggle() {
    if (!activity.id) return
    if (expanded) {
      setExpanded(false)
      return
    }
    setExpanded(true)
    if (activityCache.has(activity.id)) {
      setDetail(activityCache.get(activity.id)!)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const data = await getActivity(activity.id)
      activityCache.set(activity.id, data)
      setDetail(data)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const clickable = Boolean(activity.id)

  return (
    <>
      <tr
        className={`border-t border-default-100 ${clickable ? 'cursor-pointer hover:bg-default-50' : ''}`}
        onClick={clickable ? handleToggle : undefined}
      >
        <td className="py-2 pr-3 text-default-500">{activity.date.slice(5)}</td>
        <td className="py-2 pr-3 font-medium">{activity.name || activity.type}</td>
        <td className="py-2 pr-3 tabular-nums">{activity.distance_km} km</td>
        <td className="py-2 pr-3 tabular-nums">{Math.round(activity.duration_min)} min</td>
        <td className="py-2 pr-3 tabular-nums">{activity.avg_hr || '--'} bpm</td>
        <td className="py-2 pr-3 tabular-nums">{activity.calories || '--'}</td>
        <td className="py-2 pr-3 text-right text-default-400">{clickable ? (expanded ? '▲' : '▼') : ''}</td>
      </tr>
      {expanded && (
        <tr className="border-t border-default-100">
          <td colSpan={7} className="px-2">
            {loading && (
              <div className="flex items-center gap-2 py-3 text-xs text-default-400">
                <Spinner size="sm" /> Carregando detalhe...
              </div>
            )}
            {error && <p className="py-3 text-xs text-danger">Erro ao carregar detalhe: {error}</p>}
            {detail && !loading && <ActivityDetailPanel data={detail} />}
          </td>
        </tr>
      )}
    </>
  )
}
