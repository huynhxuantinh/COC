import { useCallback, useState } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { ConfigEditorProvider } from "./hooks/useConfigEditor";
import { usePolling } from "./hooks/usePolling";
import { CoordinatesPage } from "./pages/CoordinatesPage";
import { DashboardPage } from "./pages/DashboardPage";
import { FarmPage } from "./pages/FarmPage";
import { SettingsPage } from "./pages/SettingsPage";
import { SurrenderPage } from "./pages/SurrenderPage";
import { getBotStatus } from "./services/botApi";
import { apiErrorMessage } from "./services/http";
import type { BotStatus } from "./services/types";

export function App() {
  const [status, setStatus] = useState<BotStatus | null>(null);
  const [backendError, setBackendError] = useState("");

  const refreshStatus = useCallback(async () => {
    try {
      setStatus(await getBotStatus());
      setBackendError("");
    } catch (err) {
      setBackendError(apiErrorMessage(err));
    }
  }, []);

  usePolling(refreshStatus, 1500);

  return (
    <ConfigEditorProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell status={status} />}>
            <Route
              path="/"
              element={
                <>
                  {backendError && (
                    <div className="mb-5 rounded-2xl border border-danger/30 bg-danger/10 p-4 text-sm text-rose-200">
                      Không kết nối được backend: {backendError}
                    </div>
                  )}
                  <DashboardPage status={status} refreshStatus={refreshStatus} />
                </>
              }
            />
            <Route path="/farm" element={<FarmPage />} />
            <Route path="/coordinates" element={<CoordinatesPage />} />
            <Route path="/surrender" element={<SurrenderPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ConfigEditorProvider>
  );
}
