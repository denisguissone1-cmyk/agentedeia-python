import { useEffect, useState } from "react"
import { toast } from "sonner"
import { api, post, ApiError } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"

type Data = { system_prompt: string; tools_descricao: Record<string, string> }

export default function Prompt() {
  const [sp, setSp] = useState("")
  const [td, setTd] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api<Data>("/prompt").then((d) => {
      setSp(d.system_prompt)
      setTd(d.tools_descricao)
    }).catch(() => {})
  }, [])

  const salvar = async () => {
    setSaving(true)
    try {
      await post("/prompt", { system_prompt: sp, tools_descricao: td })
      toast.success("Alterações salvas — valem na hora")
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Falha ao salvar")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold tracking-tight">Personalidade &amp; instruções</h2>
          <p className="mt-1 text-sm text-muted-foreground">Quem o agente é e quando usa cada ferramenta.</p>
        </div>
        <Button onClick={salvar} disabled={saving}>
          {saving ? "Salvando…" : "Salvar"}
        </Button>
      </div>

      <Card>
        <CardContent className="pt-6">
          <label className="mb-2 block text-sm font-semibold">System prompt principal</label>
          <Textarea
            value={sp}
            onChange={(e) => setSp(e.target.value)}
            className="min-h-[340px] font-mono text-xs leading-relaxed"
          />
        </CardContent>
      </Card>

      <Card>
        <CardContent className="py-2">
          <Accordion type="single" collapsible>
            {Object.entries(td).map(([nome, desc]) => (
              <AccordionItem key={nome} value={nome}>
                <AccordionTrigger className="font-mono text-sm">{nome}</AccordionTrigger>
                <AccordionContent>
                  <Textarea
                    value={desc}
                    onChange={(e) => setTd((p) => ({ ...p, [nome]: e.target.value }))}
                    className="min-h-[110px] text-sm"
                  />
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </CardContent>
      </Card>
    </div>
  )
}
