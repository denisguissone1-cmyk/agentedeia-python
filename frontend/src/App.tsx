import { useEffect, useState, type ReactNode } from "react"
import { Navigate, Route, Routes } from "react-router-dom"
import { api } from "@/lib/api"
import Layout from "@/components/Layout"
import Login from "@/pages/Login"
import Geral from "@/pages/Geral"

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
        <Route path="*" element={<Navigate to="/geral" replace />} />
      </Route>
    </Routes>
  )
}
