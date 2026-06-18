import { useEffect, useState, type ReactNode } from "react"
import { Navigate, Route, Routes } from "react-router-dom"
import { api } from "@/lib/api"
import Layout from "@/components/Layout"
import Login from "@/pages/Login"
import Geral from "@/pages/Geral"
import Dashboard from "@/pages/Dashboard"
import Tools from "@/pages/Tools"
import Produtos from "@/pages/Produtos"
import Prompt from "@/pages/Prompt"
import Sessoes from "@/pages/Sessoes"
import Conversa from "@/pages/Conversa"
import Logs from "@/pages/Logs"
import Execucoes from "@/pages/Execucoes"
import Config from "@/pages/Config"

function Guard({ children }: { children: ReactNode }) {
  const [state, setState] = useState<"loading" | "ok" | "no">("loading")
  useEffect(() => {
    api("/me")
      .then(() => setState("ok"))
      .catch(() => setState("no"))
  }, [])
  if (state === "loading")
    return (
      <div className="grid min-h-screen place-items-center text-sm text-muted-foreground">
        Carregando…
      </div>
    )
  if (state === "no") return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <Guard>
            <Layout />
          </Guard>
        }
      >
        <Route path="/geral" element={<Geral />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/tools" element={<Tools />} />
        <Route path="/produtos" element={<Produtos />} />
        <Route path="/prompt" element={<Prompt />} />
        <Route path="/sessoes" element={<Sessoes />} />
        <Route path="/sessoes/:numero" element={<Conversa />} />
        <Route path="/logs" element={<Logs />} />
        <Route path="/execucoes" element={<Execucoes />} />
        <Route path="/config" element={<Config />} />
        <Route path="*" element={<Navigate to="/geral" replace />} />
      </Route>
    </Routes>
  )
}
