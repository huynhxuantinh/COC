import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { getConfig, getOptions, saveConfig } from "../services/configApi";
import { apiErrorMessage } from "../services/http";
import type { AppConfig, OptionsPayload } from "../services/types";

function cloneConfig(config: AppConfig): AppConfig {
  return JSON.parse(JSON.stringify(config));
}

export function setConfigPath(config: AppConfig, path: string[], value: unknown): AppConfig {
  const next = cloneConfig(config);
  let cursor: any = next;
  for (let index = 0; index < path.length - 1; index += 1) {
    if (!cursor[path[index]] || typeof cursor[path[index]] !== "object") {
      cursor[path[index]] = {};
    }
    cursor = cursor[path[index]];
  }
  cursor[path[path.length - 1]] = value;
  return next;
}

export function numberValue(value: string): number {
  const normalized = value.replace(/[,\s]/g, "").trim();
  return Number.parseInt(normalized || "0", 10);
}

function configSignature(config: AppConfig | null): string {
  return config ? JSON.stringify(config) : "";
}

type ConfigEditorContextValue = {
  config: AppConfig | null;
  options: OptionsPayload | null;
  loading: boolean;
  saving: boolean;
  error: string;
  savedMessage: string;
  isDirty: boolean;
  updatePath: (path: string[], value: unknown) => void;
  save: () => Promise<void>;
  reload: () => Promise<void>;
};

const ConfigEditorContext = createContext<ConfigEditorContextValue | null>(null);

export function ConfigEditorProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [options, setOptions] = useState<OptionsPayload | null>(null);
  const [savedSignature, setSavedSignature] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [savedMessage, setSavedMessage] = useState("");
  const isDirty = Boolean(config) && configSignature(config) !== savedSignature;

  const load = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      const [configPayload, optionsPayload] = await Promise.all([getConfig(), getOptions()]);
      setConfig(configPayload);
      setSavedSignature(configSignature(configPayload));
      setOptions(optionsPayload);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const updatePath = useCallback((path: string[], value: unknown) => {
    setSavedMessage("");
    setConfig((current) => (current ? setConfigPath(current, path, value) : current));
  }, []);

  const save = useCallback(async () => {
    if (!config) {
      return;
    }
    setError("");
    setSavedMessage("");
    setSaving(true);
    try {
      const saved = await saveConfig(config);
      setConfig(saved);
      setSavedSignature(configSignature(saved));
      setSavedMessage("Đã lưu cấu hình. Cần quét ADB lại trước khi chạy.");
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }, [config]);

  useEffect(() => {
    if (!isDirty) {
      return;
    }
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [isDirty]);

  const value = useMemo(
    () => ({ config, options, loading, saving, error, savedMessage, isDirty, updatePath, save, reload: load }),
    [config, options, loading, saving, error, savedMessage, isDirty, updatePath, save, load],
  );

  return <ConfigEditorContext.Provider value={value}>{children}</ConfigEditorContext.Provider>;
}

export function useConfigEditor() {
  const context = useContext(ConfigEditorContext);
  if (!context) {
    throw new Error("useConfigEditor must be used within ConfigEditorProvider");
  }
  return context;
}
