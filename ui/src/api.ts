export type ErrorEnvelope = {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
  };
};

export type Warning = {
  code: string;
  message: string;
  details: Record<string, unknown>;
};

export type Page<T> = {
  items: T[];
  row_count: number;
  returned_row_count: number;
  truncated: boolean;
  next_cursor: string | null;
  warnings: Warning[];
};

export type Datasource = {
  id: string;
  label: string;
  status: "available" | "cache_stale" | "source_offline";
  theme: string;
  row_count: number;
  tags: string[];
};

export type DatasourceField = {
  id: string;
  name: string;
  label: string;
  data_type: string;
  semantic_role: string;
  default_aggregation: string | null;
  is_filterable: boolean;
  is_sortable: boolean;
  allowed_operators: string[];
};

export type DatasourceDetail = {
  datasource: Datasource & {
    description?: string;
    connection_type?: string;
    default_filters?: Record<string, unknown>;
  };
  fields: DatasourceField[];
  warnings: Warning[];
};

export type Workbook = {
  id: string;
  title: string;
  project: string;
  owner: string;
  tags: string[];
};

export type View = {
  id: string;
  title: string;
  workbook_id: string;
  datasource_id: string;
  chart_type: string;
  position: number;
};

export type WorkbookDetail = {
  workbook: Workbook & {
    description?: string;
    default_filters?: Record<string, unknown>;
  };
  views: View[];
  warnings: Warning[];
};

export type ViewDetail = {
  view: View & {
    description: string;
    workbook_title?: string;
    datasource_label?: string;
    datasource_status?: string;
    chart_config: Record<string, unknown>;
    query_spec?: Record<string, unknown>;
    default_filters?: Record<string, unknown>;
    visual_config?: Record<string, unknown>;
  };
  warnings: Warning[];
};

export type QueryResult = {
  query_result_id?: string;
  rows: Record<string, unknown>[];
  row_count: number;
  returned_row_count: number;
  truncated: boolean;
  next_cursor: string | null;
  warnings: Warning[];
};

export type ArtifactResult = {
  export_id?: string;
  render_id?: string;
  artifact_path: string;
  format?: string;
  row_count?: number;
  width?: number;
  height?: number;
  status: string;
  warnings: Warning[];
};

export type ArtifactList = {
  exports: Array<Record<string, unknown> & { id: string; artifact_path: string; status: string }>;
  renders: Array<Record<string, unknown> & { id: string; artifact_path: string; status: string }>;
  warnings: Warning[];
};

export type ApiResult<T> = T | ErrorEnvelope;

const API_BASE = import.meta.env.VITE_LOOKOUT_API_BASE ?? "http://127.0.0.1:8765";

export function isErrorEnvelope<T>(value: ApiResult<T> | null): value is ErrorEnvelope {
  return Boolean(value && typeof value === "object" && "error" in value);
}

export function artifactUrl(path: string): string {
  return `${API_BASE}/api/files?path=${encodeURIComponent(path)}`;
}

export async function request<T>(path: string, init?: RequestInit): Promise<ApiResult<T>> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });
  return (await response.json()) as ApiResult<T>;
}

export function postJson<T>(path: string, body: unknown): Promise<ApiResult<T>> {
  return request<T>(path, {
    method: "POST",
    body: JSON.stringify(body)
  });
}
