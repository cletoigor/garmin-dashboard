import type { Theme } from '../theme'

// Paletas espelhando as variaveis --text/--muted/--surface/--border do app legado
// (dark/light), usadas para colorir eixos, grid e tooltip dos graficos Chart.js.
const PALETTES: Record<Theme, { text: string; muted: string; surface: string; border: string }> = {
  dark: {
    text: '#e4e8ee',
    muted: '#98a3b3',
    surface: '#1a1f27',
    border: '#343d4a',
  },
  light: {
    text: '#1b2430',
    muted: '#5e6b7a',
    surface: '#ffffff',
    border: '#d3dae3',
  },
}

function withAlpha(hex: string, alpha: number): string {
  const m = hex.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i)
  if (!m) return hex
  let h = m[1]
  if (h.length === 3) h = h.split('').map((c) => c + c).join('')
  const r = parseInt(h.slice(0, 2), 16)
  const g = parseInt(h.slice(2, 4), 16)
  const b = parseInt(h.slice(4, 6), 16)
  return `rgba(${r},${g},${b},${alpha})`
}

export function getChartPalette(theme: Theme) {
  const p = PALETTES[theme]
  return { ...p, grid: withAlpha(p.muted, 0.15) }
}

interface LineChartOpts {
  suggestedMin?: number
  suggestedMax?: number
  unit?: string
}

/** Opcoes base compartilhadas por todos os graficos (linha e barra), theme-aware. */
export function chartDefaults(theme: Theme) {
  const { text, muted, surface, border, grid } = getChartPalette(theme)
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { intersect: false, mode: 'index' as const },
    animation: { duration: 900, easing: 'easeOutQuart' as const },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: surface,
        borderColor: border,
        borderWidth: 1,
        titleColor: text,
        bodyColor: text,
        padding: 10,
        cornerRadius: 6,
      },
    },
    scales: {
      x: { ticks: { color: muted, font: { size: 10 } }, grid: { color: grid } },
      y: { ticks: { color: muted, font: { size: 10 } }, grid: { color: grid } },
    },
  }
}

export function lineChartOptions(theme: Theme, label: string, opts: LineChartOpts = {}) {
  const base = chartDefaults(theme) as any
  if (opts.suggestedMin !== undefined) base.scales.y.suggestedMin = opts.suggestedMin
  if (opts.suggestedMax !== undefined) base.scales.y.suggestedMax = opts.suggestedMax
  base.plugins.tooltip.callbacks = {
    label: (ctx: any) => {
      const v = ctx.parsed.y
      if (v === null || v === undefined) return `${label}: sem dados`
      const suffix = opts.unit ? ` ${opts.unit}` : ''
      return `${label}: ${Number(v).toLocaleString('pt-BR')}${suffix}`
    },
  }
  return base
}

export function sleepChartOptions(theme: Theme) {
  const base = chartDefaults(theme) as any
  base.scales.x.stacked = true
  base.scales.y.stacked = true
  base.scales.y.suggestedMax = 540
  base.scales.y.ticks.callback = (v: number) => `${Math.floor(v / 60)}h`
  base.plugins.tooltip.callbacks = {
    label: (ctx: any) => {
      const v = ctx.parsed.y
      if (v === null || v === 0) return null
      const h = Math.floor(v / 60)
      const m = v % 60
      return `${ctx.dataset.label}: ${h > 0 ? h + 'h ' : ''}${m}min`
    },
    footer: (items: any[]) => {
      const total = items.reduce((s, i) => s + (i.parsed.y || 0), 0)
      const h = Math.floor(total / 60)
      const m = total % 60
      return `Total: ${h}h ${m}min`
    },
  }
  return base
}

export const ZONE_COLORS = ['#60a5fa', '#34d399', '#fbbf24', '#fb923c', '#f87171']
export const ZONE_NAMES = ['Z1', 'Z2', 'Z3', 'Z4', 'Z5']
export const ZONE_TIPS = [
  'Recuperação ativa — intensidade muito leve, ajuda o corpo a se recuperar entre treinos.',
  'Base aeróbica — ritmo leve e sustentável, melhora a resistência usando gordura como combustível principal.',
  'Aeróbico moderado — intensidade moderada, melhora a eficiência cardiovascular.',
  'Limiar anaeróbico — intensidade alta, o corpo passa a acumular lactato; melhora a tolerância ao esforço intenso.',
  'Esforço máximo — intensidade próxima do limite, usada em picos curtos de velocidade ou potência.',
]
