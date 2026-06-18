import { useCallback, useEffect, useRef, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { ArrowLeft, Eye } from "lucide-react"
import { toast } from "sonner"
import { api, post } from "@/lib/api"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

type Msg = { role: string; ag: boolean; texto: string }

export default function Conversa() {
  const { numero = "" } = useParams()
  const [mensagens, setMensagens] = useState<Msg[]>([])
  const [busy, setBusy] = useState(false)
  const fimRef = useRef<HTMLDivElement | null>(null)

  const carregar = useCallback(() => {
    api<{ mensagens: Msg[] }>(`/sessoes/${encodeURIComponent(numero)}`)
      .then((d) => setMensagens(d.mensagens))
      .catch(() => {})
  }, [numero])

  useEffect(() => {
    carregar()
  }, [carregar])

  useEffect(() => {
    fimRef.current?.scrollIntoView({ block: "end" })
  }, [mensagens])

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
    <div className="mx-auto flex h-[calc(100svh-7rem)] max-w-2xl flex-col">
      {/* topo */}
      <div className="flex flex-wrap items-center gap-3 pb-3">
        <Button asChild variant="outline" size="sm">
          <Link to="/sessoes">
            <ArrowLeft className="size-3.5" /> Sessões
          </Link>
        </Button>
        <h2 className="flex-1 font-mono text-sm font-semibold">{numero.split("@")[0]}</h2>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 text-xs text-muted-foreground">
          <Eye className="size-3.5" /> somente leitura
        </span>
        <Button variant="outline" size="sm" disabled={busy} onClick={() => acao("pausar")}>
          Pausar bot
        </Button>
        <Button size="sm" disabled={busy} onClick={() => acao("despausar")}>
          Despausar
        </Button>
      </div>

      {/* janela de chat estilo WhatsApp */}
      <div
        className="flex-1 overflow-auto rounded-xl border p-4"
        style={{ backgroundColor: "#efeae2" }}
      >
        {mensagens.length === 0 ? (
          <div className="grid h-full place-items-center text-sm text-muted-foreground">
            Nenhuma mensagem ainda
          </div>
        ) : (
          <div className="flex flex-col gap-1.5">
            {mensagens.map((m, i) => (
              <div key={i} className={cn("flex", m.ag ? "justify-end" : "justify-start")}>
                <div
                  className={cn(
                    "max-w-[78%] whitespace-pre-wrap break-words rounded-2xl px-3 py-2 text-sm leading-relaxed text-zinc-800 shadow-sm",
                    m.ag
                      ? "rounded-br-sm bg-[#d9fdd3]"
                      : "rounded-bl-sm border border-black/5 bg-white"
                  )}
                >
                  {m.texto}
                </div>
              </div>
            ))}
            <div ref={fimRef} />
          </div>
        )}
      </div>
    </div>
  )
}
