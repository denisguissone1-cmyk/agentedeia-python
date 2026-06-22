import { useEffect, useState } from "react"
import { Check, X } from "lucide-react"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"

type Passo = { nome: string; status: string; detalhe: string; hora: string }
type Exec = {
  req_id: string
  numero: string
  hora: string
  status: string
  resumo: string
  passos: Passo[]
}

const STATUS: Record<string, string> = {
  sucesso: "bg-emerald-100 text-emerald-700",
  falha: "bg-red-100 text-red-700",
  ignorada: "bg-muted text-muted-foreground",
  aguardando: "bg-amber-100 text-amber-700",
  andamento: "bg-blue-100 text-blue-700",
}

export default function Execucoes() {
  const [execs, setExecs] = useState<Exec[]>([])
  useEffect(() => {
    api<{ execucoes: Exec[] }>("/execucoes").then((d) => setExecs(d.execucoes)).catch(() => {})
  }, [])

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-base font-semibold tracking-tight">Execuções</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Cada mensagem processada e exatamente onde parou ou falhou.
        </p>
      </div>
      <Card className="p-2">
        {execs.length === 0 ? (
          <div className="px-5 py-12 text-center text-sm text-muted-foreground">Nenhuma execução ainda</div>
        ) : (
          <Accordion type="single" collapsible>
            {execs.map((ex) => (
              <AccordionItem key={ex.req_id} value={ex.req_id} className="border-b last:border-0">
                <AccordionTrigger className="px-3 hover:no-underline">
                  <div className="flex flex-1 flex-wrap items-center gap-x-3 gap-y-1 pr-3 text-left">
                    <Badge className={cn("font-medium hover:opacity-100", STATUS[ex.status] ?? "bg-muted")}>
                      {ex.status}
                    </Badge>
                    <span className="font-mono text-xs text-muted-foreground">{ex.numero}</span>
                    <span className="ml-auto text-xs text-muted-foreground sm:order-last sm:ml-0">{ex.hora}</span>
                    <span className="order-last w-full min-w-0 truncate text-sm text-foreground/80 sm:order-none sm:w-auto sm:flex-1">
                      {ex.resumo}
                    </span>
                  </div>
                </AccordionTrigger>
                <AccordionContent>
                  <ol className="ml-3 space-y-0 border-l pl-4">
                    {ex.passos.map((p, i) => {
                      const erro = p.status === "erro"
                      return (
                        <li key={i} className="relative py-2">
                          <span
                            className={cn(
                              "absolute -left-[1.45rem] grid size-5 place-items-center rounded-full text-white",
                              erro ? "bg-red-500" : "bg-emerald-500"
                            )}
                          >
                            {erro ? <X className="size-3" /> : <Check className="size-3" />}
                          </span>
                          <div className="flex items-baseline gap-2">
                            <span className="text-sm font-medium">{p.nome}</span>
                            <span className="text-xs text-muted-foreground">{p.hora}</span>
                          </div>
                          {p.detalhe && <div className="text-xs text-muted-foreground">{p.detalhe}</div>}
                        </li>
                      )
                    })}
                  </ol>
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        )}
      </Card>
    </div>
  )
}
