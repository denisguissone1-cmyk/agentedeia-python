import { useEffect, useRef, useState } from "react"
import { api } from "@/lib/api"
import { eventoIcon, eventoCor } from "@/lib/icons"
import { cn } from "@/lib/utils"
import { Card, CardContent } from "@/components/ui/card"

type Ev = { texto: string; cor: string; quando?: string }

export default function Logs() {
  const [eventos, setEventos] = useState<Ev[]>([])
  const [vivo, setVivo] = useState(false)
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    api<{ eventos: Ev[] }>("/logs").then((d) => setEventos(d.eventos)).catch(() => {})

    const es = new EventSource("/api/logs/stream")
    esRef.current = es
    es.onopen = () => setVivo(true)
    es.onerror = () => setVivo(false)
    es.onmessage = (e) => {
      try {
        const ev = JSON.parse(e.data) as Ev
        setEventos((prev) => [ev, ...prev].slice(0, 80))
      } catch {
        /* ignora keep-alive */
      }
    }
    return () => es.close()
  }, [])

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-base font-semibold tracking-tight">Atividade ao vivo</h2>
        <p className="mt-1 text-sm text-muted-foreground">Tudo que o agente faz, em tempo real.</p>
      </div>
      <Card>
        <div className="flex items-center gap-2 border-b px-5 py-3 text-xs font-semibold">
          <span className={cn("size-2 rounded-full", vivo ? "animate-pulse bg-emerald-500" : "bg-muted-foreground/40")} />
          <span className={vivo ? "text-emerald-600" : "text-muted-foreground"}>
            {vivo ? "Ao vivo" : "Conectando…"}
          </span>
        </div>
        <CardContent className="max-h-[600px] overflow-auto p-0">
          {eventos.length === 0 ? (
            <div className="px-5 py-12 text-center text-sm text-muted-foreground">Sem atividade ainda</div>
          ) : (
            eventos.map((ev, i) => {
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
    </div>
  )
}
