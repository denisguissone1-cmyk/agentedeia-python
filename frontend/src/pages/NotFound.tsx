import { Link } from "react-router-dom"
import { Compass, ArrowLeft } from "lucide-react"
import { Button } from "@/components/ui/button"

export default function NotFound() {
  return (
    <div className="grid min-h-[60vh] place-items-center">
      <div className="flex max-w-md flex-col items-center gap-4 px-4 text-center">
        <span className="grid size-16 flex-none place-items-center rounded-2xl bg-muted text-muted-foreground">
          <Compass className="size-8" />
        </span>
        <div className="text-5xl font-bold tracking-tight">404</div>
        <h1 className="text-lg font-semibold">Página não encontrada</h1>
        <p className="text-sm text-muted-foreground">
          O endereço que você abriu não existe (ou foi removido). Volte ao painel para continuar.
        </p>
        <Button asChild className="mt-1 w-full sm:w-auto">
          <Link to="/geral">
            <ArrowLeft className="size-4" /> Voltar ao painel
          </Link>
        </Button>
      </div>
    </div>
  )
}
