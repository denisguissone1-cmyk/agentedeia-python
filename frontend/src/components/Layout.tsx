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
  Package,
  LogOut,
  ChevronsUpDown,
  Bell,
  type LucideIcon,
} from "lucide-react"
import { api, post } from "@/lib/api"
import { notifIcone, notifCor } from "@/lib/icons"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarRail,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Separator } from "@/components/ui/separator"
import { Button } from "@/components/ui/button"

type NavItem = { to: string; label: string; icon: LucideIcon }
type Notif = { id: string; titulo: string; texto: string; tipo: string; numero: string | null; quando: string }

const NAV: NavItem[] = [
  { to: "/geral", label: "Painel Geral", icon: SlidersHorizontal },
  { to: "/dashboard", label: "Dashboard", icon: LayoutGrid },
  { to: "/tools", label: "Tools", icon: Wrench },
  { to: "/produtos", label: "Produtos", icon: Package },
  { to: "/prompt", label: "Prompt", icon: AlignLeft },
  { to: "/sessoes", label: "Conversas", icon: MessageSquare },
  { to: "/logs", label: "Logs", icon: ScrollText },
  { to: "/execucoes", label: "Execuções", icon: ClipboardCheck },
  { to: "/config", label: "Configurações", icon: Settings },
]

export default function Layout() {
  const [marca, setMarca] = useState({ nome_agente: "Agente", nome_marca: "Agente IA" })
  const [notifs, setNotifs] = useState<Notif[]>([])
  const [naoLidas, setNaoLidas] = useState(0)
  const nav = useNavigate()
  const loc = useLocation()

  useEffect(() => {
    const carregarMarca = () =>
      api<{ nome_agente: string; nome_marca: string }>("/marca").then(setMarca).catch(() => {})
    carregarMarca()
    window.addEventListener("marca-atualizada", carregarMarca)
    return () => window.removeEventListener("marca-atualizada", carregarMarca)
  }, [])

  useEffect(() => {
    const carregarNotifs = () =>
      api<{ notificacoes: Notif[]; nao_lidas: number }>("/notificacoes")
        .then((d) => {
          setNotifs(d.notificacoes)
          setNaoLidas(d.nao_lidas)
        })
        .catch(() => {})
    carregarNotifs()

    const es = new EventSource("/api/logs/stream")
    es.onmessage = (ev) => {
      try {
        const dados = JSON.parse(ev.data)
        if (dados?.filtro === "notificacao") carregarNotifs()
      } catch {
        // ignora linhas que não são JSON (ex.: comentário de keep-alive)
      }
    }
    return () => es.close()
  }, [])

  const abrirNotificacoes = (open: boolean) => {
    if (open && naoLidas > 0) {
      setNaoLidas(0)
      post("/notificacoes/lidas").catch(() => {})
    }
  }

  const logout = async () => {
    await post("/logout").catch(() => {})
    nav("/login")
  }

  const atual = NAV.find((n) => loc.pathname.startsWith(n.to))
  const inicial = (marca.nome_marca[0] || "A").toUpperCase()

  return (
    <SidebarProvider>
      <Sidebar collapsible="icon">
        <SidebarHeader>
          <div className="flex items-center gap-2.5 px-1.5 py-1.5">
            <div className="grid size-8 flex-none place-items-center rounded-lg bg-primary text-sm font-bold text-primary-foreground">
              {inicial}
            </div>
            <div className="min-w-0 group-data-[collapsible=icon]:hidden">
              <div className="truncate text-sm font-semibold leading-tight">{marca.nome_marca}</div>
              <div className="truncate text-xs text-muted-foreground">{marca.nome_agente}</div>
            </div>
          </div>
        </SidebarHeader>

        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupContent>
              <SidebarMenu>
                {NAV.map((item) => {
                  const Icon = item.icon
                  const active = loc.pathname.startsWith(item.to)
                  return (
                    <SidebarMenuItem key={item.to}>
                      <SidebarMenuButton asChild isActive={active} tooltip={item.label}>
                        <NavLink to={item.to}>
                          <Icon />
                          <span>{item.label}</span>
                        </NavLink>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  )
                })}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>

        <SidebarFooter>
          <SidebarMenu>
            <SidebarMenuItem>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <SidebarMenuButton size="lg" className="data-[state=open]:bg-sidebar-accent">
                    <Avatar className="size-8 rounded-lg">
                      <AvatarFallback className="rounded-lg">AD</AvatarFallback>
                    </Avatar>
                    <div className="grid flex-1 text-left text-sm leading-tight">
                      <span className="truncate font-semibold">admin</span>
                      <span className="truncate text-xs text-muted-foreground">Administrador</span>
                    </div>
                    <ChevronsUpDown className="ml-auto size-4" />
                  </SidebarMenuButton>
                </DropdownMenuTrigger>
                <DropdownMenuContent side="top" align="end" className="w-(--radix-dropdown-menu-trigger-width) min-w-56">
                  <DropdownMenuLabel className="text-xs text-muted-foreground">Conta</DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={logout}>
                    <LogOut className="size-4" /> Sair
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarFooter>
        <SidebarRail />
      </Sidebar>

      <SidebarInset>
        <header className="flex h-14 shrink-0 items-center gap-2 border-b">
          <div className="flex items-center gap-2 px-4">
            <SidebarTrigger className="-ml-1" />
            <Separator orientation="vertical" className="mr-2 data-[orientation=vertical]:h-4" />
            <Breadcrumb>
              <BreadcrumbList>
                <BreadcrumbItem className="hidden md:block">{marca.nome_agente}</BreadcrumbItem>
                <BreadcrumbSeparator className="hidden md:block" />
                <BreadcrumbItem>
                  <BreadcrumbPage>{atual?.label ?? "Painel"}</BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </div>

          <div className="ml-auto flex items-center px-4">
            <DropdownMenu onOpenChange={abrirNotificacoes}>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="relative">
                  <Bell className="size-4" />
                  {naoLidas > 0 && (
                    <span className="absolute right-1 top-1 grid size-4 place-items-center rounded-full bg-destructive text-[10px] font-bold leading-none text-white">
                      {naoLidas > 9 ? "9+" : naoLidas}
                    </span>
                  )}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-80">
                <DropdownMenuLabel className="text-xs text-muted-foreground">Notificações</DropdownMenuLabel>
                <DropdownMenuSeparator />
                {notifs.length === 0 && (
                  <div className="px-2 py-4 text-center text-sm text-muted-foreground">
                    Sem notificações
                  </div>
                )}
                {notifs.slice(0, 10).map((n) => {
                  const Icon = notifIcone(n.tipo)
                  return (
                    <DropdownMenuItem
                      key={n.id}
                      className="items-start gap-2.5 whitespace-normal"
                      onClick={() => n.numero && nav("/sessoes")}
                    >
                      <span className={`grid size-7 flex-none place-items-center rounded-md ${notifCor(n.tipo)}`}>
                        <Icon className="size-3.5" />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="flex items-center justify-between gap-2">
                          <span className="truncate text-sm font-medium">{n.titulo}</span>
                          <span className="flex-none text-xs text-muted-foreground">{n.quando}</span>
                        </span>
                        <span className="line-clamp-2 block text-xs text-muted-foreground">{n.texto}</span>
                      </span>
                    </DropdownMenuItem>
                  )
                })}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>
        <div className="flex-1 overflow-auto p-4 md:p-6">
          <Outlet />
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
