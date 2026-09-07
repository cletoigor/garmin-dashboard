// Estilo compartilhado dos cards do app: borda sutil, sombra leve e um "lift" no
// hover (desativado quando o usuario prefere menos movimento).
export const CARD_CLASS =
  'border border-default-200/70 dark:border-default-100/10 transition-all duration-200 motion-safe:hover:-translate-y-0.5 hover:shadow-md'

// Variantes que deixam UM lado sem cor de borda definida, para compor com um
// acento (border-t-2/border-l-4 colorido) sem entrar em conflito de cascata:
// a utilidade "border-{color}" (shorthand, afeta os 4 lados) e a utilidade
// "border-t-{color}"/"border-l-{color}" (um lado so) setam a MESMA propriedade
// CSS para aquele lado, entao a que "ganha" depende da ordem interna do Tailwind
// — nao do texto do className. Evitamos isso nunca sobrepondo o mesmo lado.
export const CARD_CLASS_NO_TOP =
  'border-x border-b border-l-default-200/70 border-r-default-200/70 border-b-default-200/70 dark:border-l-default-100/10 dark:border-r-default-100/10 dark:border-b-default-100/10 transition-all duration-200 motion-safe:hover:-translate-y-0.5 hover:shadow-md'

export const CARD_CLASS_NO_LEFT =
  'border-y border-r border-t-default-200/70 border-b-default-200/70 border-r-default-200/70 dark:border-t-default-100/10 dark:border-b-default-100/10 dark:border-r-default-100/10 transition-all duration-200 motion-safe:hover:-translate-y-0.5 hover:shadow-md'

export type Accent = 'primary' | 'danger' | 'success' | 'warning'

// Acento semantico por metrica, reaproveitado entre StatsBar/HealthGrid/graficos:
// passos=azul (primary), FC/vermelho, Body Battery/verde, estresse/ambar.
export const ACCENT_TEXT: Record<Accent, string> = {
  primary: 'text-primary',
  danger: 'text-danger',
  success: 'text-success',
  warning: 'text-warning',
}

export const ACCENT_BORDER: Record<Accent, string> = {
  primary: 'border-t-primary',
  danger: 'border-t-danger',
  success: 'border-t-success',
  warning: 'border-t-warning',
}
