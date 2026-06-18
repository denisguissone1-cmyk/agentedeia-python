import { Bot, ShieldCheck, Zap, Layers } from "lucide-react"
import { LoginForm } from "@/components/login-form"

export default function Login() {
  return (
    <div className="grid min-h-svh lg:grid-cols-2">
      {/* coluna do formulário */}
      <div className="flex flex-col gap-4 p-6 md:p-10">
        <div className="flex justify-center gap-2 md:justify-start">
          <div className="flex items-center gap-2 font-medium">
            <div className="bg-primary text-primary-foreground flex size-6 items-center justify-center rounded-md">
              <Bot className="size-4" />
            </div>
            Painel do Agente
          </div>
        </div>
        <div className="flex flex-1 items-center justify-center">
          <div className="w-full max-w-xs">
            <LoginForm />
          </div>
        </div>
      </div>

      {/* painel lateral (substitui a imagem do login-02 por um gradiente da marca) */}
      <div className="relative hidden overflow-hidden bg-primary lg:block">
        <div className="absolute inset-0 bg-gradient-to-br from-primary to-indigo-700" />
        <div
          className="absolute inset-0 opacity-20"
          style={{
            backgroundImage:
              "radial-gradient(circle at 20% 20%, rgba(255,255,255,0.35) 0, transparent 40%), radial-gradient(circle at 80% 60%, rgba(255,255,255,0.25) 0, transparent 35%)",
          }}
        />
        <div className="absolute inset-0 flex flex-col justify-center gap-8 p-12 text-primary-foreground">
          <div>
            <h2 className="text-3xl font-semibold tracking-tight">Um motor, vários agentes.</h2>
            <p className="mt-3 max-w-sm text-sm text-primary-foreground/80">
              Gerencie prompt, ferramentas e a base ativa de cada nicho — tudo em um lugar.
            </p>
          </div>
          <ul className="flex flex-col gap-4 text-sm">
            <li className="flex items-center gap-3">
              <span className="grid size-9 place-items-center rounded-lg bg-white/15">
                <Layers className="size-4" />
              </span>
              Troque de base (advogado, fisioterapia…) num clique
            </li>
            <li className="flex items-center gap-3">
              <span className="grid size-9 place-items-center rounded-lg bg-white/15">
                <Zap className="size-4" />
              </span>
              Config ao vivo — muda na hora, sem restart
            </li>
            <li className="flex items-center gap-3">
              <span className="grid size-9 place-items-center rounded-lg bg-white/15">
                <ShieldCheck className="size-4" />
              </span>
              Handoff humano, rate limit e logs ao vivo
            </li>
          </ul>
        </div>
      </div>
    </div>
  )
}
