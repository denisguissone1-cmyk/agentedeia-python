import { useEffect, useState, type ReactNode } from "react"
import { Tag, SlidersHorizontal, KeyRound, Link2, Copy, type LucideIcon } from "lucide-react"
import { toast } from "sonner"
import { api, post, ApiError } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

type Dict = Record<string, string>

const NUM: { key: string; label: string; sufixo: string; desc: string }[] = [
  { key: "buffer_segundos", label: "Tempo para juntar mensagens", sufixo: "segundos", desc: "Espera mensagens seguidas e responde tudo junto" },
  { key: "bloqueio_humano_min", label: "Pausa quando um humano assume", sufixo: "minutos", desc: "Tempo calado depois que um atendente entra" },
  { key: "rate_limit_max", label: "Limite de mensagens por pessoa", sufixo: "mensagens", desc: "Proteção contra spam na mesma conversa" },
  { key: "rate_limit_janela", label: "Janela do limite", sufixo: "segundos", desc: "Período considerado para o limite acima" },
  { key: "historico_max", label: "Máximo de mensagens no histórico", sufixo: "mensagens", desc: "Quanto o agente lembra por conversa" },
  { key: "agent_timeout_seg", label: "Timeout do agente", sufixo: "segundos", desc: "Tempo máximo para responder" },
]

function CardHead({ icon: Icon, color, children }: { icon: LucideIcon; color: string; children: ReactNode }) {
  return (
    <CardHeader className="border-b">
      <CardTitle className="flex items-center gap-2.5 text-sm">
        <span className={`grid size-7 place-items-center rounded-md ${color}`}>
          <Icon className="size-4" />
        </span>
        {children}
      </CardTitle>
    </CardHeader>
  )
}

export default function Config() {
  const [c, setC] = useState<Dict>({})
  const [t, setT] = useState<Dict>({})
  const [webhookUrl, setWebhookUrl] = useState("")
  const [modelos, setModelos] = useState<string[]>([])

  const setCField = (k: string, v: string) => setC((p) => ({ ...p, [k]: v }))
  const setTField = (k: string, v: string) => setT((p) => ({ ...p, [k]: v }))

  useEffect(() => {
    api<{ c: Record<string, unknown>; t: Dict; webhook_url: string }>("/config").then((d) => {
      const cc: Dict = {}
      for (const k of [...NUM.map((n) => n.key), "nome_agente", "nome_marca"]) cc[k] = String(d.c[k] ?? "")
      setC(cc)
      setT(d.t)
      setWebhookUrl(d.webhook_url)
    }).catch(() => {})
    api<string[]>("/modelos").then(setModelos).catch(() => setModelos([]))
  }, [])

  const salvarConfig = async () => {
    try {
      await post("/config", c)
      toast.success("Configurações salvas")
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Falha ao salvar")
    }
  }
  const salvarTokens = async () => {
    try {
      await post("/tokens", t)
      toast.success("Tokens salvos e clientes recarregados")
    } catch {
      toast.error("Falha ao salvar tokens")
    }
  }
  const salvarWebhook = async (registrar: boolean) => {
    try {
      const r = await post<{ ok: boolean; msg: string }>("/webhook", {
        webhook_base_url: t.webhook_base_url ?? "",
        webhook_token: t.webhook_token ?? "",
        registrar,
      })
      r.ok ? toast.success(r.msg) : toast.error(r.msg)
    } catch {
      toast.error("Falha no webhook")
    }
  }

  const modelosCom = (v: string) => (v && !modelos.includes(v) ? [v, ...modelos] : modelos)

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-base font-semibold tracking-tight">Configurações</h2>
        <p className="mt-1 text-sm text-muted-foreground">Comportamento do atendimento e chaves de acesso.</p>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        {/* Identidade + comportamento */}
        <Card className="self-start">
          <CardHead icon={Tag} color="bg-primary/10 text-primary">Identidade</CardHead>
          <CardContent className="space-y-4 pt-5">
            <div className="grid gap-2">
              <Label>Nome do agente</Label>
              <Input value={c.nome_agente ?? ""} onChange={(e) => setCField("nome_agente", e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>Nome da marca / empresa</Label>
              <Input value={c.nome_marca ?? ""} onChange={(e) => setCField("nome_marca", e.target.value)} />
            </div>
          </CardContent>
          <CardHead icon={SlidersHorizontal} color="bg-primary/10 text-primary">Comportamento</CardHead>
          <CardContent className="space-y-4 pt-5">
            {NUM.map((f) => (
              <div key={f.key} className="grid gap-1.5">
                <Label>{f.label}</Label>
                <p className="text-xs text-muted-foreground">{f.desc}</p>
                <div className="flex items-center gap-2">
                  <Input
                    type="number"
                    className="w-28"
                    value={c[f.key] ?? ""}
                    onChange={(e) => setCField(f.key, e.target.value)}
                  />
                  <span className="text-xs text-muted-foreground">{f.sufixo}</span>
                </div>
              </div>
            ))}
            <div className="flex justify-end">
              <Button onClick={salvarConfig}>Salvar</Button>
            </div>
          </CardContent>
        </Card>

        {/* Tokens */}
        <Card className="self-start">
          <CardHead icon={KeyRound} color="bg-emerald-100 text-emerald-600">Tokens &amp; integrações</CardHead>
          <CardContent className="space-y-4 pt-5">
            {[
              ["uazapi_url", "WhatsApp (UAZAPI) — URL", "text"],
              ["uazapi_token", "WhatsApp (UAZAPI) — Token", "password"],
              ["openai_api_key", "OpenAI", "password"],
              ["google_api_key", "Google Gemini — API Key", "password"],
            ].map(([k, label, type]) => (
              <div key={k} className="grid gap-2">
                <Label>{label}</Label>
                <Input
                  type={type}
                  autoComplete="off"
                  value={t[k] ?? ""}
                  onChange={(e) => setTField(k, e.target.value)}
                />
              </div>
            ))}
            <div className="grid gap-2">
              <Label>Modelo principal</Label>
              <Select value={t.gemini_model ?? ""} onValueChange={(v) => setTField("gemini_model", v)}>
                <SelectTrigger><SelectValue placeholder="Selecione" /></SelectTrigger>
                <SelectContent>
                  {modelosCom(t.gemini_model ?? "").map((m) => (
                    <SelectItem key={m} value={m}>{m}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label>Modelo de fallback</Label>
              <Select
                value={t.gemini_model_fallback || "__none__"}
                onValueChange={(v) => setTField("gemini_model_fallback", v === "__none__" ? "" : v)}
              >
                <SelectTrigger><SelectValue placeholder="— sem fallback —" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">— sem fallback —</SelectItem>
                  {modelosCom(t.gemini_model_fallback ?? "").map((m) => (
                    <SelectItem key={m} value={m}>{m}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {[
              ["supabase_url", "Supabase — URL", "text"],
              ["supabase_key", "Supabase — Key", "password"],
            ].map(([k, label, type]) => (
              <div key={k} className="grid gap-2">
                <Label>{label}</Label>
                <Input type={type} autoComplete="off" value={t[k] ?? ""} onChange={(e) => setTField(k, e.target.value)} />
              </div>
            ))}
            <div className="flex justify-end">
              <Button onClick={salvarTokens}>Salvar e recarregar</Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Webhook */}
      <Card>
        <CardHead icon={Link2} color="bg-violet-100 text-violet-600">Webhook de entrada</CardHead>
        <CardContent className="space-y-4 pt-5">
          <div className="grid gap-2">
            <Label>URL do webhook</Label>
            <p className="text-xs text-muted-foreground">Cole esta URL na sua instância UAZAPI.</p>
            <div className="flex items-center gap-2">
              <Input readOnly value={webhookUrl} className="font-mono text-xs" />
              <Button
                variant="outline"
                size="icon"
                onClick={() => {
                  navigator.clipboard.writeText(webhookUrl)
                  toast.success("URL copiada")
                }}
              >
                <Copy className="size-4" />
              </Button>
            </div>
          </div>
          <div className="grid gap-2">
            <Label>Endereço público do app (base URL)</Label>
            <Input
              placeholder="https://meu-dominio.com"
              value={t.webhook_base_url ?? ""}
              onChange={(e) => setTField("webhook_base_url", e.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <Label>Token de segurança do webhook</Label>
            <Input
              type="password"
              autoComplete="off"
              value={t.webhook_token ?? ""}
              onChange={(e) => setTField("webhook_token", e.target.value)}
            />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => salvarWebhook(false)}>Salvar</Button>
            <Button onClick={() => salvarWebhook(true)}>Registrar na UAZAPI</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
