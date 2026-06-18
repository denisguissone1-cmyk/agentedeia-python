import { useCallback, useEffect, useRef, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { MessageSquare, Eye } from "lucide-react"
import { toast } from "sonner"
import { api, post } from "@/lib/api"
import { cn } from "@/lib/utils"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"

type Sessao = { numero: string; nome: string | null; mascara: string; status: string }
type Msg = { role: string; ag: boolean; texto: string }

function iniciais(s: Sessao): string {
  const base = (s.nome || s.mascara || "?").trim()
  const partes = base.split(/\s+/)
  return ((partes[0]?.[0] ?? "") + (partes[1]?.[0] ?? "")).toUpperCase() || "?"
}

function ChatView({ numero }: { numero: string }) {
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
    <div className="flex h-full flex-1 flex-col">
      <div className="flex flex-none items-center gap-3 border-b bg-background px-4 py-2.5">
        <span className="font-mono text-sm font-semibold">{numero.split("@")[0]}</span>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
          <Eye className="size-3.5" /> somente leitura
        </span>
        <div className="ml-auto flex gap-2">
          <Button variant="outline" size="sm" disabled={busy} onClick={() => acao("pausar")}>
            Pausar bot
          </Button>
          <Button size="sm" disabled={busy} onClick={() => acao("despausar")}>
            Despausar
          </Button>
        </div>
      </div>
      <div className="flex-1 overflow-auto p-4" style={{ backgroundColor: "#efeae2" }}>
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
                    "max-w-[72%] whitespace-pre-wrap break-words rounded-2xl px-3 py-2 text-sm leading-relaxed text-zinc-800 shadow-sm",
                    m.ag ? "rounded-br-sm bg-[#d9fdd3]" : "rounded-bl-sm border border-black/5 bg-white"
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

export default function Sessoes() {
  const { numero } = useParams()
  const nav = useNavigate()
  const [sessoes, setSessoes] = useState<Sessao[]>([])
  const [erro, setErro] = useState("")

  useEffect(() => {
    api<{ sessoes: Sessao[]; erro: string }>("/sessoes")
      .then((d) => {
        setSessoes(d.sessoes)
        setErro(d.erro)
      })
      .catch(() => setErro("Falha ao carregar as sessões"))
  }, [])

  const ativo = numero ? decodeURIComponent(numero) : ""

  return (
    <div className="flex h-[calc(100svh-7rem)] overflow-hidden rounded-xl border bg-background">
      {/* lista de conversas */}
      <div className="flex w-80 flex-none flex-col border-r">
        <div className="flex-none border-b px-4 py-3 text-sm font-semibold">Conversas</div>
        {erro && <p className="m-3 rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">{erro}</p>}
        <div className="flex-1 overflow-auto">
          {sessoes.length === 0 ? (
            <div className="px-4 py-10 text-center text-sm text-muted-foreground">Nenhuma conversa</div>
          ) : (
            sessoes.map((s) => (
              <button
                key={s.numero}
                onClick={() => nav(`/sessoes/${encodeURIComponent(s.numero)}`)}
                className={cn(
                  "flex w-full items-center gap-3 border-b px-3 py-3 text-left transition-colors hover:bg-muted",
                  ativo === s.numero && "bg-muted"
                )}
              >
                <Avatar className="size-10 flex-none">
                  <AvatarFallback className="bg-primary/10 text-xs font-semibold text-primary">
                    {iniciais(s)}
                  </AvatarFallback>
                </Avatar>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-semibold">{s.nome || s.mascara}</div>
                  <div className="truncate font-mono text-xs text-muted-foreground">{s.mascara}</div>
                </div>
                <span
                  className={cn(
                    "size-2 flex-none rounded-full",
                    s.status === "ativo" ? "bg-emerald-500" : "bg-muted-foreground/40"
                  )}
                  title={s.status === "ativo" ? "ativo" : "pausado"}
                />
              </button>
            ))
          )}
        </div>
      </div>

      {/* conversa */}
      {ativo ? (
        <ChatView key={ativo} numero={ativo} />
      ) : (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 text-muted-foreground">
          <span className="grid size-14 place-items-center rounded-2xl bg-muted">
            <MessageSquare className="size-7" />
          </span>
          <div className="text-sm">Selecione uma conversa para ver as mensagens</div>
        </div>
      )}
    </div>
  )
}
