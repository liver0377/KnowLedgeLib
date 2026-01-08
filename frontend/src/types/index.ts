// src/types/index.ts
export type KBDoc = {
  file_id: string;
  name: string;
  type: "pdf";
  dept_key: string;
  size_bytes?: number;
  updated_at?: string;
  can_view?: boolean;
  can_edit?: boolean;
};

export type KBFilesResponse = {
  items: KBDoc[];
  next_cursor: number | null;
};

export type UploadFileResponse = {
  ok: boolean;
  file_id: string;
  name: string;
  dept_key: string;
  size_bytes: number;
  message: string;
};

export type ToolCall = {
  id: string;
  name: string;
  args: any;
};

export type ChatMsg = {
  type: "human" | "ai" | "tool" | "custom";
  content: any;
  run_id?: string;
  tool_calls?: ToolCall[];
  tool_call_id?: string;
  custom_data?: any;
};

export type UiMessage = {
  id: string;
  role: "human" | "ai" | "tool" | "custom";
  content: string;
  runId?: string;
  toolCalls?: ToolCall[];
  toolResults?: Record<string, any>;
  _forceUpdate?: number;
};
