import { useEffect, useState } from "react"
import { Area, AreaChart, CartesianGrid, XAxis } from "recharts"
import { api } from "@/lib/api"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

type Ponto = { data: string; mensagens: number; agendamentos: number }

const config = {
  mensagens: { label: "Mensagens", color: "var(--primary)" },
  agendamentos: { label: "Agendamentos", color: "#12A150" },
} satisfies ChartConfig

const fmtDia = (d: string) => {
  const [, m, dd] = d.split("-")
  return `${dd}/${m}`
}

export function ActivityChart() {
  const [dias, setDias] = useState(30)
  const [custom, setCustom] = useState("")
  const [serie, setSerie] = useState<Ponto[]>([])

  useEffect(() => {
    api<{ serie: Ponto[] }>(`/metricas?dias=${dias}`)
      .then((d) => setSerie(d.serie))
      .catch(() => {})
  }, [dias])

  const aplicarCustom = () => {
    const n = parseInt(custom, 10)
    if (!Number.isNaN(n) && n >= 1 && n <= 365) setDias(n)
  }

  const total = serie.reduce((s, p) => s + p.mensagens + p.agendamentos, 0)

  return (
    <Card>
      <CardHeader>
        <CardTitle>Atividade do agente</CardTitle>
        <CardDescription>
          Mensagens atendidas e agendamentos por dia — últimos {dias} dias
          {total === 0 && " (sem dados ainda; popula conforme as conversas acontecem)"}
        </CardDescription>
        <CardAction className="col-start-1 row-span-1 row-start-3 mt-3 flex flex-wrap items-center gap-2 justify-self-start sm:col-start-2 sm:row-span-2 sm:row-start-1 sm:mt-0 sm:justify-self-end">
          <ToggleGroup
            type="single"
            value={[7, 30, 90].includes(dias) ? String(dias) : ""}
            onValueChange={(v) => v && setDias(Number(v))}
            variant="outline"
            size="sm"
          >
            <ToggleGroupItem value="7">7 dias</ToggleGroupItem>
            <ToggleGroupItem value="30">30 dias</ToggleGroupItem>
            <ToggleGroupItem value="90">90 dias</ToggleGroupItem>
          </ToggleGroup>
          <div className="flex items-center gap-1.5">
            <Label htmlFor="custom" className="text-xs text-muted-foreground">
              Personalizado
            </Label>
            <Input
              id="custom"
              type="number"
              min={1}
              max={365}
              placeholder="dias"
              value={custom}
              onChange={(e) => setCustom(e.target.value)}
              onBlur={aplicarCustom}
              onKeyDown={(e) => e.key === "Enter" && aplicarCustom()}
              className="h-8 w-20"
            />
          </div>
        </CardAction>
      </CardHeader>
      <CardContent>
        <ChartContainer config={config} className="h-[260px] w-full">
          <AreaChart data={serie} margin={{ left: 4, right: 8 }}>
            <defs>
              <linearGradient id="fillMsg" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--color-mensagens)" stopOpacity={0.7} />
                <stop offset="95%" stopColor="var(--color-mensagens)" stopOpacity={0.08} />
              </linearGradient>
              <linearGradient id="fillAg" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--color-agendamentos)" stopOpacity={0.7} />
                <stop offset="95%" stopColor="var(--color-agendamentos)" stopOpacity={0.08} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="data"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              minTickGap={24}
              tickFormatter={fmtDia}
            />
            <ChartTooltip content={<ChartTooltipContent labelFormatter={(l) => fmtDia(String(l))} />} />
            <Area
              dataKey="mensagens"
              type="natural"
              fill="url(#fillMsg)"
              stroke="var(--color-mensagens)"
              stackId="a"
            />
            <Area
              dataKey="agendamentos"
              type="natural"
              fill="url(#fillAg)"
              stroke="var(--color-agendamentos)"
              stackId="a"
            />
            <ChartLegend content={<ChartLegendContent />} />
          </AreaChart>
        </ChartContainer>
      </CardContent>
    </Card>
  )
}
