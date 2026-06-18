import { useEffect, useState } from "react"
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom"
import {
  SlidersHorizontal,
  LayoutGrid,
  Wrench,
  AlignLeft,
  MessageSquare,
  ScrollText,
  ClipboardCheck,
  Settings,
  LogOut,
  type LucideIcon,
} from "lucide-react"
import { api, post } from "@/lib/api"
import { cn } from "@/lib/utils"

type NavItem = { to: string; label: string; icon: LucideIcon; enabled: boolean }

const NAV: NavItem[] = [
  { to: "/geral", label: "Painel Geral", icon: SlidersHorizontal, enabled: true },
  { to: "/dashboard", label: "Dashboard", icon: LayoutGrid, enabled: false },
  { to: "/tools", label: "Tools", icon: Wrench, enabled: false },
  { to: "/prompt", label: "Prompt", icon: AlignLeft, enabled: false },
  { to: "/sessoes", label: "Sessões", icon: MessageSquare, enabled: false },
  { to: "/logs", label: "Logs", icon: ScrollText, enabled: false },
  { to: "/execucoes", label: "Execuções", icon: ClipboardCheck, enabled: false },
  { to: "/config", label: "Configurações", icon: Settings, enabled: false },
]

export default function Layout() {
  const [marca, setMarca] = useState({ nome_agente: "Agente", nome_marca: "Agente IA" })
  const nav = useNavigate()
  const loc = useLocation()

  useEffect(() => {
    api<{ nome_agente: string; nome_marca: string }>("/marca")
      .then(setMarca)
      .catch(() => {})
  }, [])

  const logout = async () => {
    await post("/logout").catch(() => {})
    nav("/login")
  }

  const titulo = NAV.find((n) => loc.pathname.startsWith(n.to))?.label ?? "Painel"
  const inicial = (marca.nome_marca[0] || "A").toUpperCase()

  return (
    <div className="flex h-screen overflow-hidden bg-muted/30">
      {/* sidebar */}
      <aside className="flex w-64 flex-none flex-col border-r bg-background px-3 py-4">
        <div className="flex items-center gap-3 px-2 py-1">
          <div className="grid size-9 place-items-center rounded-lg bg-primary text-sm font-bold text-primary-foreground">
            {inicial}
          </div>
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold leading-tight">{marca.nome_marca}</div>
            <div className="truncate text-xs text-muted-foreground">{marca.nome_agente}</div>
          </div>
        </div>

        <div className="mt-3 flex items-center gap-2 rounded-lg bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-600">
          <span className="size-2 animate-pulse rounded-full bg-emerald-500" />
          {marca.nome_agente} atendendo
        </div>

        <nav className="mt-5 flex flex-col gap-0.5">
          {NAV.map((item) => {
            const Icon = item.icon
            if (!item.enabled)
              return (
                <span
                  key={item.to}
                  className="flex cursor-not-allowed items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground/50"
                  title="Em breve"
                >
                  <Icon className="size-[18px]" />
                  {item.label}
                  <span className="ml-auto text-[10px] font-semibold uppercase tracking-wide">
                    em breve
                  </span>
                </span>
              )
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  )
                }
              >
                <Icon className="size-[18px]" />
                {item.label}
              </NavLink>
            )
          })}
        </nav>

        <div className="mt-auto flex items-center gap-3 border-t pt-3">
          <div className="grid size-8 place-items-center rounded-full bg-muted text-xs font-semibold text-muted-foreground">
            AD
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-xs font-semibold">admin</div>
            <div className="text-[11px] text-muted-foreground">Administrador</div>
          </div>
          <button
            onClick={logout}
            className="text-muted-foreground transition-colors hover:text-foreground"
            title="Sair"
          >
            <LogOut className="size-4" />
          </button>
        </div>
      </aside>

      {/* main */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex flex-none items-center border-b bg-background/80 px-7 py-4 backdrop-blur">
          <h1 className="text-lg font-semibold tracking-tight">{titulo}</h1>
        </header>
        <main className="flex-1 overflow-auto px-7 py-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
