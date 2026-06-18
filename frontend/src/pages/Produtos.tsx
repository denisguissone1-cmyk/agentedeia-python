import { useEffect, useRef, useState } from "react"
import { Plus, Trash2, ImagePlus, X, Pencil, Package } from "lucide-react"
import { toast } from "sonner"
import { api, post } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Switch } from "@/components/ui/switch"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
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

type Produto = {
  id: number
  nome: string
  preco: string
  descricao: string
  ativo: boolean
  fotos: number[]
}

const vazio = { id: 0, nome: "", preco: "", descricao: "", ativo: true }

export default function Produtos() {
  const [produtos, setProdutos] = useState<Produto[]>([])
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState<typeof vazio>(vazio)
  const [saving, setSaving] = useState(false)
  const fileRefs = useRef<Record<number, HTMLInputElement | null>>({})

  const carregar = () =>
    api<{ produtos: Produto[] }>("/produtos").then((d) => setProdutos(d.produtos))

  useEffect(() => {
    carregar().catch(() => toast.error("Falha ao carregar produtos"))
  }, [])

  const abrirNovo = () => {
    setForm(vazio)
    setOpen(true)
  }
  const abrirEdicao = (p: Produto) => {
    setForm({ id: p.id, nome: p.nome, preco: p.preco, descricao: p.descricao, ativo: p.ativo })
    setOpen(true)
  }

  const salvar = async () => {
    if (!form.nome.trim()) {
      toast.error("Informe o nome do produto")
      return
    }
    setSaving(true)
    try {
      const body = { nome: form.nome, preco: form.preco, descricao: form.descricao, ativo: form.ativo }
      if (form.id) await api(`/produtos/${form.id}`, { method: "PUT", body: JSON.stringify(body) })
      else await post("/produtos", body)
      setOpen(false)
      await carregar()
      toast.success(form.id ? "Produto atualizado" : "Produto cadastrado")
    } catch {
      toast.error("Falha ao salvar")
    } finally {
      setSaving(false)
    }
  }

  const toggle = async (p: Produto) => {
    setProdutos((ps) => ps.map((x) => (x.id === p.id ? { ...x, ativo: !x.ativo } : x)))
    try {
      await post(`/produtos/${p.id}/toggle`)
    } catch {
      toast.error("Falha ao alterar status")
      carregar()
    }
  }

  const excluir = async (p: Produto) => {
    try {
      await api(`/produtos/${p.id}`, { method: "DELETE" })
      await carregar()
      toast.success("Produto removido")
    } catch {
      toast.error("Falha ao remover")
    }
  }

  const upload = async (pid: number, files: FileList | null) => {
    if (!files || !files.length) return
    let ok = 0
    const falhas: string[] = []
    // Uma foto por requisição: resiliente a lotes grandes e mostra falhas individuais.
    for (const f of Array.from(files)) {
      const fd = new FormData()
      fd.append("fotos", f)
      try {
        const res = await fetch(`/api/produtos/${pid}/fotos`, {
          method: "POST",
          body: fd,
          credentials: "include",
        })
        if (res.status === 401) {
          toast.error("Sessão expirada — entre de novo")
          window.location.href = "/login"
          return
        }
        if (res.ok) {
          ok++
        } else {
          const d = (await res.json().catch(() => null)) as { detail?: string } | null
          falhas.push(`${f.name}: ${d?.detail || res.status}`)
        }
      } catch {
        falhas.push(`${f.name}: erro de rede`)
      }
    }
    await carregar()
    if (ok) toast.success(`${ok} foto(s) adicionada(s)`)
    if (falhas.length) toast.error(`Falha em ${falhas.length}: ${falhas[0]}`)
  }

  const removerFoto = async (fid: number) => {
    try {
      await api(`/produtos/fotos/${fid}`, { method: "DELETE" })
      await carregar()
    } catch {
      toast.error("Falha ao remover foto")
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold tracking-tight">Produtos</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Catálogo que o agente consulta e cujas fotos ele envia. Só os <b>ativos</b> aparecem para o cliente.
          </p>
        </div>
        <Button onClick={abrirNovo}>
          <Plus className="size-4" /> Adicionar produto
        </Button>
      </div>

      {produtos.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-14 text-center">
            <span className="grid size-12 place-items-center rounded-xl bg-muted text-muted-foreground">
              <Package className="size-6" />
            </span>
            <div className="text-sm text-muted-foreground">Nenhum produto cadastrado ainda.</div>
            <Button variant="outline" onClick={abrirNovo}>
              <Plus className="size-4" /> Cadastrar o primeiro
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {produtos.map((p) => (
            <Card key={p.id} className={p.ativo ? "" : "opacity-70"}>
              <CardContent className="space-y-3 p-5">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="truncate font-semibold">{p.nome}</h3>
                      {p.ativo ? (
                        <Badge className="bg-emerald-100 text-emerald-700 hover:bg-emerald-100">ativo</Badge>
                      ) : (
                        <Badge variant="secondary" className="text-muted-foreground">inativo</Badge>
                      )}
                    </div>
                    {p.preco && <div className="mt-0.5 text-sm font-medium text-primary">R$ {p.preco}</div>}
                  </div>
                  <Switch checked={p.ativo} onCheckedChange={() => toggle(p)} />
                </div>

                {p.descricao && (
                  <p className="line-clamp-3 text-sm leading-relaxed text-muted-foreground">{p.descricao}</p>
                )}

                <div className="flex flex-wrap gap-2">
                  {p.fotos.map((fid) => (
                    <div key={fid} className="group relative">
                      <img
                        src={`/media/foto/${fid}`}
                        alt=""
                        className="size-16 rounded-md border object-cover"
                      />
                      <button
                        onClick={() => removerFoto(fid)}
                        className="absolute -right-1.5 -top-1.5 grid size-5 place-items-center rounded-full bg-destructive text-white opacity-0 transition group-hover:opacity-100"
                        title="Remover foto"
                      >
                        <X className="size-3" />
                      </button>
                    </div>
                  ))}
                  <button
                    onClick={() => fileRefs.current[p.id]?.click()}
                    className="grid size-16 place-items-center rounded-md border border-dashed text-muted-foreground transition hover:border-primary hover:text-primary"
                    title="Adicionar fotos"
                  >
                    <ImagePlus className="size-5" />
                  </button>
                  <input
                    ref={(el) => {
                      fileRefs.current[p.id] = el
                    }}
                    type="file"
                    accept="image/*"
                    multiple
                    hidden
                    onChange={(e) => {
                      upload(p.id, e.target.files)
                      e.target.value = ""
                    }}
                  />
                </div>

                <div className="flex justify-end gap-2 pt-1">
                  <Button variant="outline" size="sm" onClick={() => abrirEdicao(p)}>
                    <Pencil className="size-3.5" /> Editar
                  </Button>
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button variant="outline" size="sm" className="text-destructive hover:text-destructive">
                        <Trash2 className="size-3.5" /> Excluir
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>Excluir "{p.nome}"?</AlertDialogTitle>
                        <AlertDialogDescription>
                          O produto e suas fotos serão removidos. Isso não tem volta.
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>Cancelar</AlertDialogCancel>
                        <AlertDialogAction
                          onClick={() => excluir(p)}
                          className="bg-destructive text-white hover:bg-destructive/90"
                        >
                          Excluir
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Dialog de cadastro/edição */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{form.id ? "Editar produto" : "Novo produto"}</DialogTitle>
            <DialogDescription>Preencha os dados. As fotos você adiciona no card depois de salvar.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="nome">Nome</Label>
              <Input
                id="nome"
                autoFocus
                placeholder="Ex.: iPhone 14 Pro 256GB"
                value={form.nome}
                onChange={(e) => setForm((f) => ({ ...f, nome: e.target.value }))}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="preco">Preço</Label>
              <Input
                id="preco"
                placeholder="Ex.: 4.500 ou 4500 à vista"
                value={form.preco}
                onChange={(e) => setForm((f) => ({ ...f, preco: e.target.value }))}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="descricao">Especificações</Label>
              <Textarea
                id="descricao"
                placeholder="Cor, capacidade, estado (novo/seminovo), garantia, observações…"
                className="min-h-[110px]"
                value={form.descricao}
                onChange={(e) => setForm((f) => ({ ...f, descricao: e.target.value }))}
              />
            </div>
            <div className="flex items-center justify-between rounded-lg border px-3 py-2.5">
              <div>
                <div className="text-sm font-medium">Produto ativo</div>
                <div className="text-xs text-muted-foreground">Visível para o agente e o cliente</div>
              </div>
              <Switch checked={form.ativo} onCheckedChange={(v) => setForm((f) => ({ ...f, ativo: v }))} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={salvar} disabled={saving}>
              {saving ? "Salvando…" : "Salvar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
