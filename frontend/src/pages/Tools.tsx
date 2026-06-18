import { useEffect, useState } from "react"
import { toast } from "sonner"
import { api, post } from "@/lib/api"
import { toolIcon } from "@/lib/icons"
import { cn } from "@/lib/utils"
import { Card, CardContent } from "@/components/ui/card"
import { Switch } from "@/components/ui/switch"

type Tool = { nome: string; descricao: string; ativa: boolean }

export default function Tools() {
  const [tools, setTools] = useState<Tool[]>([])

  useEffect(() => {
    api<{ tools: Tool[] }>("/tools").then((d) => setTools(d.tools)).catch(() => {})
  }, [])

  const toggle = async (nome: string) => {
    try {
      const r = await post<{ nome: string; ativa: boolean }>(`/tools/${nome}/toggle`)
      setTools((ts) => ts.map((t) => (t.nome === nome ? { ...t, ativa: r.ativa } : t)))
      toast.success(`Tool "${nome}" ${r.ativa ? "ativada" : "desativada"}`)
    } catch {
      toast.error("Não foi possível alterar a tool")
    }
  }

  return (
    <div className="space-y-1">
      <h2 className="text-base font-semibold tracking-tight">Ferramentas do agente</h2>
      <p className="pb-4 text-sm text-muted-foreground">
        As ações que o agente pode executar durante a conversa. Ligue/desligue à vontade.
      </p>
      <div className="grid gap-4 sm:grid-cols-2">
        {tools.map((t) => {
          const Icon = toolIcon(t.nome)
          return (
            <Card key={t.nome}>
              <CardContent className="p-5">
                <div className="flex items-start justify-between gap-3">
                  <span
                    className={cn(
                      "grid size-10 flex-none place-items-center rounded-lg border",
                      t.ativa ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
                    )}
                  >
                    <Icon className="size-5" />
                  </span>
                  <Switch checked={t.ativa} onCheckedChange={() => toggle(t.nome)} />
                </div>
                <div className="mt-3 font-mono text-sm font-semibold">{t.nome}</div>
                <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{t.descricao}</p>
              </CardContent>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
