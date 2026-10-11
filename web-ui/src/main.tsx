import { StrictMode } from "react"
import { createRoot } from "react-dom/client"

import App from "@/App"
import "@/index.css"
import { AppQueryClientProvider } from "@/providers/query-client-provider"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppQueryClientProvider>
      <App />
    </AppQueryClientProvider>
  </StrictMode>,
)

