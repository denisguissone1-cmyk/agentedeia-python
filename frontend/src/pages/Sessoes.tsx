import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { MessageSquare, Eye, Search, Settings2, Check, X, FileText } from "lucide-react"
import { toast } from "sonner"
import { api, post } from "@/lib/api"
import { cn } from "@/lib/utils"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"

type Sessao = { numero: string; nome: string | null; mascara: string; status: string }
type Msg = { role: string; ag: boolean; texto: string; tipo?: string; audio_id?: number }
type Passo = { nome: string; status: string; detalhe: string; hora: string }
type Exec = { req_id: string; hora: string; status: string; resumo: string; passos: Passo[] }

const STATUS: Record<string, string> = {
  sucesso: "bg-emerald-100 text-emerald-700",
  falha: "bg-red-100 text-red-700",
  ignorada: "bg-muted text-muted-foreground",
  aguardando: "bg-amber-100 text-amber-700",
  andamento: "bg-blue-100 text-blue-700",
}

function iniciais(s: Sessao): string {
  const base = (s.nome || s.mascara || "?").trim()
  const p = base.split(/\s+/)
  return ((p[0]?.[0] ?? "") + (p[1]?.[0] ?? "")).toUpperCase() || "?"
}

function ExecSheet({ numero }: { numero: string }) {
  const [execs, setExecs] = useState<Exec[]>([])
  const onOpen = (o: boolean) => {
    if (o)
      api<{ execucoes: Exec[] }>(`/sessoes/${encodeURIComponent(numero)}/execucoes`)
        .then((d) => setExecs(d.execucoes))
        .catch(() => {})
  }
  return (
    <Sheet onOpenChange={onOpen}>
      <SheetTrigger asChild>
        <Button variant="outline" size="icon" title="Execuções desta conversa">
          <Settings2 className="size-4" />
        </Button>
      </SheetTrigger>
      <SheetContent className="w-full overflow-auto sm:max-w-md">
        <SheetHeader>
          <SheetTitle>Execuções desta conversa</SheetTitle>
          <SheetDescription>O que o agente fez em cada mensagem deste contato.</SheetDescription>
        </SheetHeader>
        <div className="space-y-3 px-4 pb-6">
          {execs.length === 0 ? (
            <div className="py-10 text-center text-sm text-muted-foreground">
              Nenhuma execução registrada para este contato.
            </div>
          ) : (
            execs.map((ex) => (
              <div key={ex.req_id} className="rounded-lg border p-3">
                <div className="flex items-center gap-2">
                  <Badge className={cn("font-medium hover:opacity-100", STATUS[ex.status] ?? "bg-muted")}>
                    {ex.status}
                  </Badge>
                  <span className="min-w-0 flex-1 truncate text-sm text-foreground/80">{ex.resumo}</span>
                  <span className="text-xs text-muted-foreground">{ex.hora}</span>
                </div>
                <ol className="ml-2 mt-3 space-y-2 border-l pl-4">
                  {ex.passos.map((p, i) => {
                    const erro = p.status === "erro"
                    return (
                      <li key={i} className="relative">
                        <span
                          className={cn(
                            "absolute -left-[1.4rem] grid size-5 place-items-center rounded-full text-white",
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
              </div>
            ))
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}

function AudioBubble({ m }: { m: Msg }) {
  const [verTexto, setVerTexto] = useState(false)
  return (
    <div className="max-w-[80%] rounded-2xl rounded-bl-sm border border-black/5 bg-white px-2.5 py-2 shadow-sm">
      <audio controls preload="none" src={`/media/audio/${m.audio_id}`} className="h-10 w-64 max-w-full" />
      {m.texto && (
        <>
          <button
            onClick={() => setVerTexto((v) => !v)}
            className="mt-1.5 flex items-center gap-1 text-xs font-medium text-emerald-700 hover:underline"
          >
            <FileText className="size-3.5" />
            {verTexto ? "Ocultar transcrição" : "Ver transcrição"}
          </button>
          {verTexto && (
            <div className="mt-1 whitespace-pre-wrap break-words border-t pt-1.5 text-sm leading-relaxed text-zinc-600">
              {m.texto}
            </div>
          )}
        </>
      )}
    </div>
  )
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
          <ExecSheet numero={numero} />
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
                {m.tipo === "audio" ? (
                  <AudioBubble m={m} />
                ) : (
                  <div
                    className={cn(
                      "max-w-[72%] whitespace-pre-wrap break-words rounded-2xl px-3 py-2 text-sm leading-relaxed text-zinc-800 shadow-sm",
                      m.ag ? "rounded-br-sm bg-[#d9fdd3]" : "rounded-bl-sm border border-black/5 bg-white"
                    )}
                  >
                    {m.texto}
                  </div>
                )}
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
  const [busca, setBusca] = useState("")

  useEffect(() => {
    api<{ sessoes: Sessao[]; erro: string }>("/sessoes")
      .then((d) => {
        setSessoes(d.sessoes)
        setErro(d.erro)
      })
      .catch(() => setErro("Falha ao carregar as conversas"))
  }, [])

  const ativo = numero ? decodeURIComponent(numero) : ""

  const filtradas = useMemo(() => {
    const q = busca.trim().toLowerCase()
    if (!q) return sessoes
    return sessoes.filter(
      (s) =>
        (s.nome || "").toLowerCase().includes(q) ||
        s.numero.toLowerCase().includes(q) ||
        s.mascara.toLowerCase().includes(q)
    )
  }, [sessoes, busca])

  return (
    <div className="flex h-[calc(100svh-7rem)] overflow-hidden rounded-xl border bg-background">
      {/* lista de conversas */}
      <div className="flex w-80 flex-none flex-col border-r">
        <div className="flex-none space-y-2.5 border-b p-3">
          <div className="text-sm font-semibold">Conversas</div>
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Buscar nome ou número…"
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              className="h-9 pl-8"
            />
          </div>
        </div>
        {erro && <p className="m-3 rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">{erro}</p>}
        <div className="flex-1 overflow-auto">
          {filtradas.length === 0 ? (
            <div className="px-4 py-10 text-center text-sm text-muted-foreground">
              {busca ? "Nada encontrado" : "Nenhuma conversa"}
            </div>
          ) : (
            filtradas.map((s) => (
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
