import { useState, type FormEvent } from "react"
import { useNavigate } from "react-router-dom"
import { post } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

export default function Login() {
  const [usuario, setUsuario] = useState("")
  const [senha, setSenha] = useState("")
  const [erro, setErro] = useState("")
  const [loading, setLoading] = useState(false)
  const nav = useNavigate()

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setErro("")
    setLoading(true)
    try {
      await post("/login", { usuario, senha })
      nav("/geral")
    } catch {
      setErro("Usuário ou senha inválidos")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="grid min-h-screen place-items-center bg-muted/30 p-6">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-3">
          <div className="grid size-12 place-items-center rounded-xl bg-primary text-xl font-bold text-primary-foreground shadow-lg shadow-primary/25">
            A
          </div>
          <div className="text-center">
            <div className="font-semibold">Painel do Agente</div>
            <div className="text-sm text-muted-foreground">Entre para gerenciar</div>
          </div>
        </div>

        <Card>
          <CardContent className="pt-6">
            <form onSubmit={submit} className="flex flex-col gap-4">
              {erro && (
                <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm font-medium text-destructive">
                  {erro}
                </p>
              )}
              <div className="grid gap-2">
                <Label htmlFor="usuario">Usuário</Label>
                <Input
                  id="usuario"
                  autoFocus
                  autoComplete="username"
                  value={usuario}
                  onChange={(e) => setUsuario(e.target.value)}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="senha">Senha</Label>
                <Input
                  id="senha"
                  type="password"
                  autoComplete="current-password"
                  value={senha}
                  onChange={(e) => setSenha(e.target.value)}
                />
              </div>
              <Button type="submit" className="mt-2 w-full" disabled={loading}>
                {loading ? "Entrando…" : "Entrar"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
