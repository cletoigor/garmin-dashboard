import { useEffect, useState } from 'react'
import { Tab, Tabs, Spinner } from '@heroui/react'
import { getState, type AppState } from './api'
import { Header } from './components/Header'
import { StatsBar } from './components/StatsBar'
import { TabHoje } from './components/TabHoje'
import { TabTendencias } from './components/TabTendencias'
import { TabTreino } from './components/TabTreino'
import { TabMetas } from './components/TabMetas'
import { TabCondicionamento } from './components/TabCondicionamento'

export default function App() {
  const [state, setState] = useState<AppState | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getState()
      .then(setState)
      .catch((err: Error) => setError(err.message))
  }, [])

  async function refreshState() {
    const fresh = await getState()
    setState(fresh)
  }

  if (error) {
    return (
      <div className="flex min-h-svh items-center justify-center p-6 text-center text-danger">
        Erro ao carregar dados do dashboard: {error}
      </div>
    )
  }

  if (!state) {
    return (
      <div className="flex min-h-svh items-center justify-center">
        <Spinner label="Carregando dados do Garmin..." />
      </div>
    )
  }

  return (
    <div className="app-shell min-h-svh text-foreground">
      <Header sync={state.sync} />
      <main className="mx-auto flex max-w-5xl flex-col gap-7 px-4 py-8">
        <StatsBar snapshot={state.snapshot} />

        <Tabs aria-label="Secoes do dashboard" color="primary" variant="underlined" size="lg">
          <Tab
            key="hoje"
            title={
              <span className="flex items-center gap-1.5">
                <span aria-hidden="true">📅</span> Hoje
              </span>
            }
          >
            <TabHoje state={state} />
          </Tab>
          <Tab
            key="tendencias"
            title={
              <span className="flex items-center gap-1.5">
                <span aria-hidden="true">📈</span> Tendencias
              </span>
            }
          >
            <TabTendencias initialDailyData={state.daily_data} initialTrends={state.trends} />
          </Tab>
          <Tab
            key="treino"
            title={
              <span className="flex items-center gap-1.5">
                <span aria-hidden="true">🏃</span> Treino
              </span>
            }
          >
            <TabTreino initialReport={state.report} />
          </Tab>
          <Tab
            key="metas"
            title={
              <span className="flex items-center gap-1.5">
                <span aria-hidden="true">🎯</span> Metas
              </span>
            }
          >
            <TabMetas goals={state.goals} streak={state.streak} onSaved={refreshState} />
          </Tab>
          <Tab
            key="condicionamento"
            title={
              <span className="flex items-center gap-1.5">
                <span aria-hidden="true">🔥</span> Condicionamento
              </span>
            }
          >
            <TabCondicionamento fitness={state.fitness} />
          </Tab>
        </Tabs>
      </main>
    </div>
  )
}
