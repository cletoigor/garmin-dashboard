import { useEffect, useState } from 'react'
import {
  Navbar,
  NavbarBrand,
  NavbarContent,
  NavbarItem,
  Button,
  Chip,
} from '@heroui/react'
import type { SyncStatus } from '../api'
import { refresh, shutdown } from '../api'
import { useTheme } from '../theme'

const LEVEL_COLOR: Record<SyncStatus['level'], 'success' | 'warning' | 'danger' | 'default'> = {
  ok: 'success',
  stale: 'warning',
  fail: 'danger',
  unknown: 'default',
}

const LEVEL_LABEL: Record<SyncStatus['level'], string> = {
  ok: 'Sincronizado',
  stale: 'Dados desatualizados',
  fail: 'Falha na sincronizacao',
  unknown: 'Status desconhecido',
}

export function Header({ sync }: { sync: SyncStatus }) {
  const { theme, toggleTheme } = useTheme()
  const [now, setNow] = useState(() => new Date())
  const [syncing, setSyncing] = useState(false)

  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(id)
  }, [])

  async function handleRefresh() {
    setSyncing(true)
    try {
      await refresh()
      window.location.reload()
    } catch {
      setSyncing(false)
    }
  }

  async function handleShutdown() {
    if (!window.confirm('Encerrar o servidor do dashboard?')) return
    try {
      await shutdown()
    } catch {
      // servidor pode encerrar antes de responder
    }
  }

  return (
    <Navbar isBordered maxWidth="full" position="static">
      <NavbarBrand className="gap-2.5">
        <span className="text-xl leading-none" aria-hidden="true">
          ⌚
        </span>
        <span className="text-lg font-semibold">Garmin Dashboard</span>
        <Chip size="sm" color={LEVEL_COLOR[sync.level]} variant="flat">
          {LEVEL_LABEL[sync.level]}
        </Chip>
      </NavbarBrand>
      <NavbarContent justify="end" className="gap-4">
        <NavbarItem className="hidden text-sm text-default-500 sm:block">
          {now.toLocaleString('pt-BR')}
        </NavbarItem>
        <NavbarItem>
          <Button
            size="sm"
            color="primary"
            variant="flat"
            isLoading={syncing}
            onPress={handleRefresh}
          >
            Sincronizar
          </Button>
        </NavbarItem>
        <NavbarItem>
          <Button size="sm" variant="light" isIconOnly onPress={toggleTheme} aria-label="Alternar tema">
            {theme === 'dark' ? '☀️' : '🌙'}
          </Button>
        </NavbarItem>
        <NavbarItem>
          <Button size="sm" color="danger" variant="flat" onPress={handleShutdown}>
            Encerrar
          </Button>
        </NavbarItem>
      </NavbarContent>
    </Navbar>
  )
}
