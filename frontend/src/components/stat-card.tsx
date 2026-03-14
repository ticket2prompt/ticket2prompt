import { Card, CardContent } from "@/components/ui/card"
import type { ReactNode } from "react"

export function StatCard({ icon, label, value, index = 0 }: { icon: ReactNode; label: string; value: string | number; index?: number }) {
  return (
    <Card className={`animate-float-in stagger-${index + 1}`}>
      <CardContent className="flex items-center gap-4 p-5">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
          {icon}
        </div>
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="text-2xl font-semibold tracking-tight">{value}</p>
        </div>
      </CardContent>
    </Card>
  )
}
