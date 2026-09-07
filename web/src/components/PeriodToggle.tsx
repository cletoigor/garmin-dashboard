import { ButtonGroup, Button } from '@heroui/react'

const OPTIONS = [7, 15, 30] as const

export function PeriodToggle({
  value,
  onChange,
  disabled,
}: {
  value: number
  onChange: (days: number) => void
  disabled?: boolean
}) {
  return (
    <ButtonGroup size="sm" variant="flat">
      {OPTIONS.map((d) => (
        <Button
          key={d}
          color={value === d ? 'primary' : 'default'}
          isDisabled={disabled}
          onPress={() => onChange(d)}
        >
          {d} dias
        </Button>
      ))}
    </ButtonGroup>
  )
}
