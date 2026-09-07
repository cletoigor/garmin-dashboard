// Formatadores usados nos graficos e tabelas de treino (portados da versao vanilla).

export function fmtSecs(s: number | null | undefined): string {
  if (!s) return '--'
  const total = Math.round(s)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const sec = total % 60
  return h
    ? `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
    : `${m}:${String(sec).padStart(2, '0')}`
}

export function paceFromSpeed(speed: number | null | undefined): string {
  if (!speed || speed <= 0) return '--'
  const spk = 1000 / speed
  const m = Math.floor(spk / 60)
  const s = Math.round(spk % 60)
  return `${m}:${String(s).padStart(2, '0')}/km`
}

/** dd/mm a partir de uma data ISO (YYYY-MM-DD). */
export function fmtDayMonth(isoDate: string): string {
  const parts = isoDate.split('-')
  return `${parts[2]}/${parts[1]}`
}
