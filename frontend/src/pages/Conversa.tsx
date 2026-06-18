import { useCallback, useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { ArrowLeft } from "lucide-react"
import { toast } from "sonner"
import { api, post } from "@/lib/api"
import { cn } from "@/lib/utils"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

type Msg = { role: string; ag: boolean; texto: string }

export default function Conversa() {
  const { numero = "" } = useParams()
  const [mensagens, setMensagens] = useState<Msg[]>([])
  const [busy, setBusy] = useState(false)

  const carregar = useCallback(() => {
    api<{ mensagens: Msg[] }>(`/sessoes/${encodeURIComponent(numero)}`)
      .then((d) => setMensagens(d.mensagens))
      .catch(() => {})
  }, [numero])

  useEffect(() => {
    carregar()
  }, [carregar])

  const acao = async (qual: "pausar" | "despausar") => {
    setBusy(true)
    try {
      await post(`/sessoes/${encodeURIComponent(numero)}/${qual}`)
      toast.success(qual === "pausar" ? "Bot pausado nesta conversa" : "Bot reativado")
    } catch {
      toast.error("Falha na ação")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Button asChild variant="outline" size="sm">
          <Link to="/sessoes">
            <ArrowLeft className="size-3.5" /> Sessões
          </Link>
        </Button>
        <h2 className="flex-1 font-mono text-sm font-semibold">{numero.split("@")[0]}</h2>
        <Button variant="outline" size="sm" disabled={busy} onClick={() => acao("pausar")}>
          Pausar bot
        </Button>
        <Button size="sm" disabled={busy} onClick={() => acao("despausar")}>
          Despausar
        </Button>
      </div>

      <Card>
        <CardContent className="p-0">
          {mensagens.length === 0 ? (
            <div className="px-5 py-12 text-center text-sm text-muted-foreground">Nenhuma mensagem ainda</div>
          ) : (
            mensagens.map((m, i) => (
              <div key={i} className="flex gap-4 border-b px-5 py-3.5 last:border-0">
                <span
                  className={cn(
                    "w-20 flex-none pt-0.5 text-xs font-semibold",
                    m.ag ? "text-primary" : "text-muted-foreground"
                  )}
                >
                  {m.role}
                </span>
                <span className="whitespace-pre-wrap break-words text-sm leading-relaxed text-foreground/80">
                  {m.texto}
                </span>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  )
}
