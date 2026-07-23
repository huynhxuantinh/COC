export type AppConfig = Record<string, any>;

export type BotStatus = {
  status: string;
  adb_ready: boolean;
  running: boolean;
  paused: boolean;
  active_devices: string[];
};

export type LogEntry = {
  id: number;
  message: string;
  created_at: string;
};

export type StatsPayload = {
  current_session: Record<string, number>;
  total: Record<string, number>;
  by_device: Record<string, unknown>;
};

export type SelectOption = {
  label: string;
  value: string;
};

export type OptionsPayload = {
  combos: string[];
  deploy_modes: SelectOption[];
  attack_edges: SelectOption[];
  attack_views: SelectOption[];
};

export type ScreenshotPayload = {
  image_base64: string;
  width: number;
  height: number;
};

export type ReferenceImageItem = {
  name: string;
  label: string;
  width: number;
  height: number;
};
