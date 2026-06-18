import { useState, type ComponentProps, type FormEvent } from "react"
import { useNavigate } from "react-router-dom"
import { post } from "@/lib/api"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"

export function LoginForm({ className, ...props }: ComponentProps<"form">) {
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
    <form className={cn("flex flex-col gap-6", className)} {...props} onSubmit={submit}>
      <FieldGroup>
        <div className="flex flex-col items-center gap-1 text-center">
          <h1 className="text-2xl font-bold">Entrar no painel</h1>
          <p className="text-sm text-balance text-muted-foreground">
            Acesse para gerenciar o agente
          </p>
        </div>
        {erro && (
          <p className="rounded-md bg-destructive/10 px-3 py-2 text-center text-sm font-medium text-destructive">
            {erro}
          </p>
        )}
        <Field>
          <FieldLabel htmlFor="usuario">Usuário</FieldLabel>
          <Input
            id="usuario"
            autoFocus
            autoComplete="username"
            value={usuario}
            onChange={(e) => setUsuario(e.target.value)}
            className="bg-background"
            required
          />
        </Field>
        <Field>
          <FieldLabel htmlFor="senha">Senha</FieldLabel>
          <Input
            id="senha"
            type="password"
            autoComplete="current-password"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            className="bg-background"
            required
          />
        </Field>
        <Field>
          <Button type="submit" disabled={loading}>
            {loading ? "Entrando…" : "Entrar"}
          </Button>
        </Field>
      </FieldGroup>
    </form>
  )
}
