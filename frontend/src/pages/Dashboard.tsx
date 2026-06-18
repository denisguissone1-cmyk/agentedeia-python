import { useEffect, useState } from "react"
import { MessageCircle, Inbox, ListTodo, CalendarCheck, type LucideIcon } from "lucide-react"
import { api } from "@/lib/api"
import { eventoIcon, eventoCor } from "@/lib/icons"
import { cn } from "@/lib/utils"
import { ActivityChart } from "@/components/ActivityChart"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

type Ev = { texto: string; cor: string; quando?: string }
type Tool = { nome: string; descricao: string; ativa: boolean }
type Data = {
  stats: { conversas_ativas: number; msgs_hoje: number; fila_pendente: number; agendamentos: number }
  eventos: Ev[]
  tools: Tool[]
}

const CARDS: { key: keyof Data["stats"]; label: string; icon: LucideIcon; tag: string; hint: string }[] = [
  { key: "conversas_ativas", label: "Conversas ativas", icon: MessageCircle, tag: "agora", hint: "Contatos com conversa aberta" },
  { key: "msgs_hoje", label: "Mensagens atendidas", icon: Inbox, tag: "hoje", hint: "Total processado nas últimas 24h" },
  { key: "fila_pendente", label: "Fila pendente", icon: ListTodo, tag: "fila", hint: "Jobs aguardando o worker" },
  { key: "agendamentos", label: "Agendamentos", icon: CalendarCheck, tag: "hoje", hint: "Marcações criadas hoje" },
]

export default function Dashboard() {
  const [d, setD] = useState<Data | null>(null)
  useEffect(() => {
    api<Data>("/dashboard").then(setD).catch(() => {})
  }, [])

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {CARDS.map((c) => {
          const Icon = c.icon
          return (
            <Card key={c.key}>
              <CardHeader>
                <CardDescription>{c.label}</CardDescription>
                <CardTitle className="text-3xl font-semibold tabular-nums">
                  {d ? d.stats[c.key] : "—"}
                </CardTitle>
                <CardAction>
                  <Badge variant="outline" className="gap-1">
                    <Icon className="size-3.5" />
                    {c.tag}
                  </Badge>
                </CardAction>
              </CardHeader>
              <CardFooter>
                <span className="text-sm text-muted-foreground">{c.hint}</span>
              </CardFooter>
            </Card>
          )
        })}
      </div>

      <ActivityChart />

      <div className="grid gap-5 lg:grid-cols-[1.5fr_1fr]">
        <Card>
          <CardHeader className="border-b">
            <CardTitle className="text-sm">O que está acontecendo</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {!d || d.eventos.length === 0 ? (
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
          <CardHeader className="border-b">
            <CardTitle className="text-sm">Tools ativas</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {d?.tools.map((t) => (
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
