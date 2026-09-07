import { Card, CardBody } from '@heroui/react'

export function ComingSoon({ title }: { title: string }) {
  return (
    <Card shadow="sm">
      <CardBody className="items-center gap-2 py-12 text-center">
        <span className="text-3xl">🚧</span>
        <p className="text-default-500">{title} — Em breve</p>
      </CardBody>
    </Card>
  )
}
