import { Bot } from "lucide-react"
import { LoginForm } from "@/components/login-form"
import { Card, CardContent } from "@/components/ui/card"

export default function Login() {
  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-6 bg-muted p-6 md:p-10">
      <div className="flex w-full max-w-sm flex-col gap-6">
        <div className="flex items-center gap-2 self-center font-medium">
          <div className="flex size-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <Bot className="size-5" />
          </div>
          Painel do Agente
        </div>
        <Card>
          <CardContent className="py-6">
            <LoginForm />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
