import { useCallback, useState } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { Feedback } from "./components/Feedback";
import { ConfigEditorProvider } from "./hooks/useConfigEditor";
import { usePolling } from "./hooks/usePolling";
import { SpellCoordinatesPage, TroopCoordinatesPage } from "./pages/CoordinatesPage";
import { ComboPage } from "./pages/ComboPage";
import { DashboardPage } from "./pages/DashboardPage";
import { FarmPage } from "./pages/FarmPage";
import { SettingsPage } from "./pages/SettingsPage";
import { SlotDetectionPage } from "./pages/SlotDetectionPage";
import { SurrenderPage } from "./pages/SurrenderPage";
import { WallUpgradePage } from "./pages/WallUpgradePage";
import { BuilderCoordinatesPage } from "./pages/BuilderCoordinatesPage";
import { BuilderStrategyPage } from "./pages/BuilderStrategyPage";
import { BuilderWallUpgradePage } from "./pages/BuilderWallUpgradePage";
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
                    <Feedback tone="error" className="mb-5">Không kết nối được backend: {backendError}</Feedback>
                  )}
                  <DashboardPage status={status} refreshStatus={refreshStatus} />
                </>
              }
            />
            <Route path="/farm" element={<FarmPage />} />
            <Route path="/combos" element={<ComboPage />} />
            <Route path="/coordinates" element={<TroopCoordinatesPage />} />
            <Route path="/coordinates/troops" element={<TroopCoordinatesPage />} />
            <Route path="/coordinates/spells" element={<SpellCoordinatesPage />} />
            <Route path="/slots" element={<SlotDetectionPage />} />
            <Route path="/surrender" element={<SurrenderPage />} />
            <Route path="/wall-upgrade" element={<WallUpgradePage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/builder/strategy" element={<BuilderStrategyPage />} />
            <Route path="/builder/coordinates" element={<BuilderCoordinatesPage />} />
            <Route path="/builder/wall-upgrade" element={<BuilderWallUpgradePage />} />
            <Route path="*" element={<Feedback tone="warning">Trang bạn mở không tồn tại.</Feedback>} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ConfigEditorProvider>
  );
}
