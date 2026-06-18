import {
  Scale,
  Building2,
  ShieldCheck,
  Scissors,
  Sparkles,
  Smile,
  Activity,
  Boxes,
  UserPlus,
  Search,
  Calendar,
  CalendarCheck,
  CalendarX,
  MessageCircle,
  CheckCircle2,
  CalendarDays,
  Clock,
  AlertTriangle,
  type LucideIcon,
} from "lucide-react"

const niche: Record<string, LucideIcon> = {
  advogado: Scale,
  imobiliaria: Building2,
  corretor: ShieldCheck,
  barbearia: Scissors,
  estetica: Sparkles,
  odontologia: Smile,
  fisioterapia: Activity,
}

export const nicheIcon = (name: string): LucideIcon => niche[name] ?? Boxes

const tool: Record<string, LucideIcon> = {
  cadastrar: UserPlus,
  buscar_info: Search,
  consultar_agenda: Calendar,
  pre_marcacao: CalendarCheck,
  desmarcar: CalendarX,
}

export const toolIcon = (name: string): LucideIcon => tool[name] ?? Boxes

const evento: Record<string, LucideIcon> = {
  "e-blue": MessageCircle,
  "e-grn": CheckCircle2,
  "e-vio": CalendarDays,
  "e-amb": Clock,
  "e-red": AlertTriangle,
}

export const eventoIcon = (cor: string): LucideIcon => evento[cor] ?? MessageCircle

// classes de cor (texto/fundo) por categoria de evento
export const eventoCor: Record<string, string> = {
  "e-blue": "bg-blue-100 text-blue-600",
  "e-grn": "bg-emerald-100 text-emerald-600",
  "e-vio": "bg-violet-100 text-violet-600",
  "e-amb": "bg-amber-100 text-amber-600",
  "e-red": "bg-red-100 text-red-600",
}
