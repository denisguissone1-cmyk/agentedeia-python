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
  type LucideIcon,
} from "lucide-react"
import { api, post } from "@/lib/api"
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

type NavItem = { to: string; label: string; icon: LucideIcon }

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
  const nav = useNavigate()
  const loc = useLocation()

  useEffect(() => {
    api<{ nome_agente: string; nome_marca: string }>("/marca").then(setMarca).catch(() => {})
  }, [])

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
        </header>
        <div className="flex-1 overflow-auto p-4 md:p-6">
          <Outlet />
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
