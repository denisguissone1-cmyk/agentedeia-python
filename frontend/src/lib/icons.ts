import {
  Scale,
  Building2,
  ShieldCheck,
  Scissors,
  Sparkles,
  Smile,
  Activity,
  Boxes,
  type LucideIcon,
} from "lucide-react"

const map: Record<string, LucideIcon> = {
  advogado: Scale,
  imobiliaria: Building2,
  corretor: ShieldCheck,
  barbearia: Scissors,
  estetica: Sparkles,
  odontologia: Smile,
  fisioterapia: Activity,
}

export const nicheIcon = (name: string): LucideIcon => map[name] ?? Boxes
