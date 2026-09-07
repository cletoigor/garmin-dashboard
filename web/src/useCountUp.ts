import { useEffect, useRef, useState } from 'react'

/**
 * Anima um numero contando de 0 ate `value` usando requestAnimationFrame.
 * Respeita prefers-reduced-motion (mostra o valor final direto).
 */
export function useCountUp(value: number | null, durationMs = 900): number | null {
  const [display, setDisplay] = useState<number | null>(value)
  const frameRef = useRef<number | null>(null)

  useEffect(() => {
    if (value === null || Number.isNaN(value)) {
      setDisplay(value)
      return
    }

    const prefersReducedMotion =
      typeof window !== 'undefined' &&
      window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

    if (prefersReducedMotion) {
      setDisplay(value)
      return
    }

    const start = performance.now()
    const from = 0

    function tick(now: number) {
      const elapsed = now - start
      const progress = Math.min(1, elapsed / durationMs)
      const eased = 1 - (1 - progress) * (1 - progress)
      setDisplay(from + (value! - from) * eased)
      if (progress < 1) {
        frameRef.current = requestAnimationFrame(tick)
      } else {
        setDisplay(value)
      }
    }

    frameRef.current = requestAnimationFrame(tick)
    return () => {
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, durationMs])

  return display
}
