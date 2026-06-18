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
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
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

type GeralData = { presets: string[]; preset_ativo: string }

export default function Geral() {
  const [data, setData] = useState<GeralData | null>(null)
  const [sel, setSel] = useState("")
  const [busy, setBusy] = useState(false)

  const carregar = () =>
    api<GeralData>("/geral").then((d) => {
      setData(d)
      setSel(d.preset_ativo || "")
    })

  useEffect(() => {
    carregar().catch(() => toast.error("Falha ao carregar o painel"))
  }, [])

  const ativar = async () => {
    setBusy(true)
    try {
      await post("/preset", { preset: sel })
      await carregar()
      toast.success(`Base "${sel}" ativada`, { description: "Revise o prompt, as tools e a marca." })
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
              const Icon = nicheIcon(p)
              const ativo = p === data.preset_ativo
              const checked = p === sel
              return (
                <Label
                  key={p}
                  htmlFor={`p-${p}`}
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
                  <span className="flex-1 text-sm font-semibold">{presetLabel(p)}</span>
                  {ativo && <Badge className="bg-emerald-100 text-emerald-700 hover:bg-emerald-100">ativa</Badge>}
                  <RadioGroupItem value={p} id={`p-${p}`} />
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
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button disabled={!podeAtivar || busy}>Ativar base</Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Ativar a base "{sel}"?</AlertDialogTitle>
                <AlertDialogDescription>
                  Isso vai sobrescrever o prompt, as tools e a marca atuais do agente.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancelar</AlertDialogCancel>
                <AlertDialogAction onClick={ativar}>Ativar base</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </Card>

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
