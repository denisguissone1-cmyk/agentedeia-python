import { useEffect, useState } from "react"
import { MessageCircle, Inbox, ListTodo, CalendarCheck, type LucideIcon } from "lucide-react"
import { api } from "@/lib/api"
import { eventoIcon, eventoCor } from "@/lib/icons"
import { cn } from "@/lib/utils"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

type Ev = { texto: string; cor: string; quando?: string }
type Tool = { nome: string; descricao: string; ativa: boolean }
type Data = {
  stats: { conversas_ativas: number; msgs_hoje: number; fila_pendente: number; agendamentos: number }
  eventos: Ev[]
  tools: Tool[]
}

const STATS: { key: keyof Data["stats"]; label: string; icon: LucideIcon; color: string }[] = [
  { key: "conversas_ativas", label: "Conversas ativas", icon: MessageCircle, color: "bg-blue-100 text-blue-600" },
  { key: "msgs_hoje", label: "Mensagens hoje", icon: Inbox, color: "bg-violet-100 text-violet-600" },
  { key: "fila_pendente", label: "Fila pendente", icon: ListTodo, color: "bg-amber-100 text-amber-600" },
  { key: "agendamentos", label: "Agendamentos hoje", icon: CalendarCheck, color: "bg-emerald-100 text-emerald-600" },
]

export default function Dashboard() {
  const [d, setD] = useState<Data | null>(null)
  useEffect(() => {
    api<Data>("/dashboard").then(setD).catch(() => {})
  }, [])
  if (!d) return <div className="text-sm text-muted-foreground">Carregando…</div>

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {STATS.map((s) => {
          const Icon = s.icon
          return (
            <Card key={s.key}>
              <CardContent className="p-5">
                <span className={cn("grid size-9 place-items-center rounded-lg", s.color)}>
                  <Icon className="size-[18px]" />
                </span>
                <div className="mt-4 text-3xl font-bold tracking-tight">{d.stats[s.key]}</div>
                <div className="mt-0.5 text-sm text-muted-foreground">{s.label}</div>
              </CardContent>
            </Card>
          )
        })}
      </div>

      <div className="grid gap-5 lg:grid-cols-[1.5fr_1fr]">
        <Card>
          <CardContent className="p-0">
            <div className="border-b px-5 py-4 text-sm font-semibold">O que está acontecendo</div>
            {d.eventos.length === 0 ? (
              <div className="px-5 py-10 text-center text-sm text-muted-foreground">Sem atividade ainda</div>
            ) : (
              d.eventos.map((ev, i) => {
                const Icon = eventoIcon(ev.cor)
                return (
                  <div key={i} className="flex items-start gap-3 border-b px-5 py-3 last:border-0">
                    <span className={cn("grid size-8 flex-none place-items-center rounded-lg", eventoCor[ev.cor] ?? "bg-muted")}>
                      <Icon className="size-4" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="text-sm text-foreground/80">{ev.texto}</div>
                      {ev.quando && <div className="mt-0.5 text-xs text-muted-foreground">{ev.quando}</div>}
                    </div>
                  </div>
                )
              })
            )}
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-0">
            <div className="border-b px-5 py-4 text-sm font-semibold">Tools ativas</div>
            {d.tools.map((t) => (
              <div key={t.nome} className="flex items-center justify-between border-b px-5 py-3 last:border-0">
                <span className="font-mono text-sm">{t.nome}</span>
                {t.ativa ? (
                  <Badge className="bg-emerald-100 text-emerald-700 hover:bg-emerald-100">ativa</Badge>
                ) : (
                  <Badge variant="secondary" className="text-muted-foreground">off</Badge>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
