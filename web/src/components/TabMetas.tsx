import { useState } from 'react'
import { Button, Card, CardBody, CardHeader, Chip, Input, Progress } from '@heroui/react'
import { saveGoals, type GoalProgress, type GoalTargets } from '../api'
import { CARD_CLASS } from '../ui'

interface Props {
  goals: GoalProgress[]
  streak: number
  onSaved: () => Promise<void>
}

function fmt(n: number): string {
  return n.toLocaleString('pt-BR')
}

export function TabMetas({ goals, streak, onSaved }: Props) {
  const [editing, setEditing] = useState(false)
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(goals.map((g) => [g.key, String(g.goal)])),
  )
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function startEdit() {
    setValues(Object.fromEntries(goals.map((g) => [g.key, String(g.goal)])))
    setError(null)
    setEditing(true)
  }

  async function handleSave() {
    setSaving(true)
    setError(null)
    const body: Partial<GoalTargets> = {}
    for (const g of goals) {
      const raw = values[g.key]
      const n = raw !== undefined ? parseFloat(raw) : NaN
      if (!Number.isNaN(n) && n > 0) {
        body[g.key as keyof GoalTargets] = n
      }
    }
    try {
      await saveGoals(body)
      await onSaved()
      setEditing(false)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <Card shadow="sm" className={CARD_CLASS}>
        <CardHeader className="flex items-center justify-between gap-3">
          <span className="font-semibold">🎯 Metas da semana</span>
          <div className="flex items-center gap-2">
            {streak > 0 && (
              <Chip color="warning" variant="flat" size="sm">
                🔥 {streak} {streak === 1 ? 'dia' : 'dias'} batendo a meta de passos
              </Chip>
            )}
            {!editing && (
              <Button size="sm" variant="flat" onPress={startEdit}>
                ⚙ Editar
              </Button>
            )}
          </div>
        </CardHeader>
        <CardBody className="gap-5">
          {!editing ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              {goals.map((g) => (
                <div key={g.key} className="flex flex-col gap-1.5">
                  <div className="flex items-baseline justify-between text-sm">
                    <span className="text-default-500">{g.label}</span>
                    <span className="font-semibold tabular-nums">
                      {fmt(g.value)}
                      {g.unit ? ` ${g.unit}` : ''}
                      <span className="ml-1 font-normal text-default-400">/ {fmt(g.goal)}</span>
                    </span>
                  </div>
                  <Progress
                    aria-label={g.label}
                    value={g.pct}
                    maxValue={100}
                    size="md"
                    radius="full"
                    color={g.pct >= 100 ? 'success' : 'primary'}
                  />
                </div>
              ))}
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                {goals.map((g) => (
                  <Input
                    key={g.key}
                    type="number"
                    min={0}
                    step="any"
                    label={g.unit ? `${g.label} (${g.unit})` : g.label}
                    value={values[g.key] ?? ''}
                    onValueChange={(v) => setValues((prev) => ({ ...prev, [g.key]: v }))}
                  />
                ))}
              </div>
              {error && <p className="text-sm text-danger">Erro ao salvar: {error}</p>}
              <div className="flex gap-2">
                <Button color="primary" isLoading={saving} onPress={handleSave}>
                  {saving ? 'Salvando...' : 'Salvar'}
                </Button>
                <Button variant="flat" isDisabled={saving} onPress={() => setEditing(false)}>
                  Cancelar
                </Button>
              </div>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
