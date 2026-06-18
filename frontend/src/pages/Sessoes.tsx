import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { ArrowRight } from "lucide-react"
import { api } from "@/lib/api"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

type Sessao = { numero: string; nome: string | null; mascara: string; status: string }

export default function Sessoes() {
  const [sessoes, setSessoes] = useState<Sessao[]>([])
  const [erro, setErro] = useState("")

  useEffect(() => {
    api<{ sessoes: Sessao[]; erro: string }>("/sessoes")
      .then((d) => {
        setSessoes(d.sessoes)
        setErro(d.erro)
      })
      .catch(() => setErro("Falha ao carregar as sessões"))
  }, [])

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-base font-semibold tracking-tight">Sessões</h2>
        <p className="mt-1 text-sm text-muted-foreground">Conversas e contatos do agente.</p>
      </div>
      {erro && (
        <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm font-medium text-destructive">{erro}</p>
      )}
      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Número</TableHead>
              <TableHead>Nome</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Ação</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sessoes.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} className="py-10 text-center text-muted-foreground">
                  Nenhuma conversa ainda
                </TableCell>
              </TableRow>
            ) : (
              sessoes.map((s) => (
                <TableRow key={s.numero}>
                  <TableCell className="font-mono">{s.mascara}</TableCell>
                  <TableCell className="font-medium text-foreground">{s.nome || "—"}</TableCell>
                  <TableCell>
                    {s.status === "ativo" ? (
                      <Badge className="bg-emerald-100 text-emerald-700 hover:bg-emerald-100">ativo</Badge>
                    ) : (
                      <Badge variant="secondary" className="text-muted-foreground">pausado</Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button asChild variant="outline" size="sm">
                      <Link to={`/sessoes/${encodeURIComponent(s.numero)}`}>
                        Abrir <ArrowRight className="size-3.5" />
                      </Link>
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Card>
    </div>
  )
}
