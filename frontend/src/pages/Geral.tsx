import { useEffect, useState } from "react"
import { Layers, RotateCcw } from "lucide-react"
import { toast } from "sonner"
import { api, post } from "@/lib/api"
import { nicheIcon, presetLabel } from "@/lib/icons"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Checkbox } from "@/components/ui/checkbox"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"

type PresetInfo = { id: string; nome_agente: string; nome_marca: string }
type GeralData = { presets: PresetInfo[]; preset_ativo: string; nome_agente: string; nome_marca: string }
type AtivarResp = { ok: boolean; preset_ativo: string; produtos_carregados: number; aviso: string | null }

const formVazio = { nome_agente: "", nome_marca: "", carregar_produtos: true }

export default function Geral() {
  const [data, setData] = useState<GeralData | null>(null)
  const [sel, setSel] = useState("")
  const [busy, setBusy] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [form, setForm] = useState(formVazio)

  const carregar = () =>
    api<GeralData>("/geral").then((d) => {
      setData(d)
      setSel(d.preset_ativo || "")
    })

  useEffect(() => {
    carregar().catch(() => toast.error("Falha ao carregar o painel"))
  }, [])

  const abrirModal = () => {
    const info = data?.presets.find((p) => p.id === sel)
    setForm({
      nome_agente: info?.nome_agente || "",
      nome_marca: info?.nome_marca || "",
      carregar_produtos: true,
    })
    setModalOpen(true)
  }

  const ativar = async () => {
    if (!form.nome_agente.trim() || !form.nome_marca.trim()) {
      toast.error("Preencha o nome do agente e o nome da marca")
      return
    }
    setBusy(true)
    try {
      const r = await post<AtivarResp>("/preset", {
        preset: sel,
        nome_agente: form.nome_agente.trim(),
        nome_marca: form.nome_marca.trim(),
        carregar_produtos: form.carregar_produtos,
      })
      setModalOpen(false)
      await carregar()
      window.dispatchEvent(new Event("marca-atualizada"))
      toast.success(`Base "${presetLabel(sel)}" ativada`, {
        description: r.produtos_carregados
          ? `${r.produtos_carregados} produto(s) de exemplo carregados. Revise o prompt e as tools.`
          : "Revise o prompt, as tools e a marca.",
      })
      if (r.aviso) toast.warning(r.aviso)
    } catch {
      toast.error("Não foi possível ativar a base")
    } finally {
      setBusy(false)
    }
  }

  const resetar = async () => {
    setBusy(true)
    try {
      const r = await post<{ apagadas: number }>("/reset")
      toast.success("Histórico zerado", {
        description: `${r.apagadas} mensagens apagadas. As conversas recomeçam do zero.`,
      })
    } catch {
      toast.error("Falha ao resetar o histórico")
    } finally {
      setBusy(false)
    }
  }

  if (!data) return <div className="text-sm text-muted-foreground">Carregando…</div>

  const podeAtivar = sel !== "" && sel !== data.preset_ativo

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h2 className="text-base font-semibold tracking-tight">Central de controle</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Escolha a base ativa do agente e gerencie as conversas. Só uma base fica ativa por vez, e
          o motor (código) é o mesmo para todas.
        </p>
      </div>

      {/* Base ativa */}
      <Card>
        <CardHeader className="border-b">
          <CardTitle className="flex items-center gap-2.5 text-sm">
            <span className="grid size-7 place-items-center rounded-md bg-violet-100 text-violet-600">
              <Layers className="size-4" />
            </span>
            Base ativa do agente
          </CardTitle>
        </CardHeader>
        <CardContent className="p-2">
          <RadioGroup value={sel} onValueChange={setSel} className="gap-1">
            {data.presets.map((p) => {
              const Icon = nicheIcon(p.id)
              const ativo = p.id === data.preset_ativo
              const checked = p.id === sel
              return (
                <Label
                  key={p.id}
                  htmlFor={`p-${p.id}`}
                  className={cn(
                    "flex cursor-pointer items-center gap-3 rounded-lg border border-transparent px-3.5 py-3 transition-colors hover:bg-muted",
                    checked && "border-primary/20 bg-primary/5"
                  )}
                >
                  <span
                    className={cn(
                      "grid size-9 flex-none place-items-center rounded-lg border bg-background text-muted-foreground transition-colors",
                      checked && "border-primary/20 text-primary"
                    )}
                  >
                    <Icon className="size-[18px]" />
                  </span>
                  <span className="flex-1">
                    <span className="block text-sm font-semibold">{presetLabel(p.id)}</span>
                    <span className="block text-xs text-muted-foreground">
                      {p.nome_agente} · {p.nome_marca}
                    </span>
                  </span>
                  {ativo && <Badge className="bg-emerald-100 text-emerald-700 hover:bg-emerald-100">ativa</Badge>}
                  <RadioGroupItem value={p.id} id={`p-${p.id}`} />
                </Label>
              )
            })}
          </RadioGroup>
          {!data.preset_ativo && (
            <p className="px-3.5 pb-1 pt-2 text-xs text-muted-foreground">
              Nenhuma base aplicada ainda — a config atual é personalizada.
            </p>
          )}
        </CardContent>
        <div className="flex justify-end border-t p-4">
          <Button disabled={!podeAtivar || busy} onClick={abrirModal}>
            Ativar base
          </Button>
        </div>
      </Card>

      {/* Modal de ativação: nome do agente/marca + catálogo de exemplo */}
      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Ativar a base "{presetLabel(sel)}"?</DialogTitle>
            <DialogDescription>
              Isso vai sobrescrever o prompt, as tools e a marca atuais do agente. Com o catálogo
              marcado, os produtos atuais serão apagados e substituídos pelos de exemplo.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="nome_agente">Nome do agente</Label>
              <Input
                id="nome_agente"
                autoFocus
                placeholder="Ex.: Clara"
                value={form.nome_agente}
                onChange={(e) => setForm((f) => ({ ...f, nome_agente: e.target.value }))}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="nome_marca">Nome da marca / empresa</Label>
              <Input
                id="nome_marca"
                placeholder="Ex.: Farmácia Vida"
                value={form.nome_marca}
                onChange={(e) => setForm((f) => ({ ...f, nome_marca: e.target.value }))}
              />
            </div>
            <label className="flex cursor-pointer items-start gap-2.5 rounded-lg border px-3 py-2.5">
              <Checkbox
                checked={form.carregar_produtos}
                onCheckedChange={(v) => setForm((f) => ({ ...f, carregar_produtos: v === true }))}
                className="mt-0.5"
              />
              <span>
                <span className="block text-sm font-medium">Carregar catálogo de exemplo</span>
                <span className="block text-xs text-muted-foreground">
                  Substitui os produtos atuais pelos ~10 itens de exemplo deste nicho
                </span>
              </span>
            </label>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setModalOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={ativar} disabled={busy}>
              Ativar base
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reset */}
      <Card className="border-destructive/30">
        <CardHeader className="border-b border-destructive/15">
          <CardTitle className="flex items-center gap-2.5 text-sm">
            <span className="grid size-7 place-items-center rounded-md bg-destructive/10 text-destructive">
              <RotateCcw className="size-4" />
            </span>
            Reset de conversas
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 pt-5">
          <p className="text-sm text-muted-foreground">
            Apaga o histórico de mensagens de todas as conversas (a memória do agente). Cada conversa
            recomeça do zero, como uma conversa nova. Os contatos cadastrados são mantidos.
          </p>
          <div className="flex justify-end">
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="destructive" disabled={busy}>
                  Zerar histórico de conversas
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Apagar o histórico de todas as conversas?</AlertDialogTitle>
                  <AlertDialogDescription>
                    Isso não tem volta. A memória de todas as conversas será apagada; os contatos são
                    mantidos.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancelar</AlertDialogCancel>
                  <AlertDialogAction
                    onClick={resetar}
                    className="bg-destructive text-white hover:bg-destructive/90"
                  >
                    Zerar histórico
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
