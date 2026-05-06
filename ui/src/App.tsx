import { useEffect, useMemo, useState } from "react";
import {
  type ApiResult,
  type ArtifactList,
  type ArtifactResult,
  type Datasource,
  type DatasourceDetail,
  type DatasourceField,
  type ErrorEnvelope,
  type Page,
  type QueryResult,
  type View,
  type ViewDetail,
  type Warning,
  type Workbook,
  type WorkbookDetail,
  artifactUrl,
  isErrorEnvelope,
  postJson,
  request
} from "./api";

type Screen = "overview" | "datasources" | "workbooks" | "views" | "query" | "artifacts";

const screens: Array<{ id: Screen; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "datasources", label: "Datasources" },
  { id: "workbooks", label: "Workbooks" },
  { id: "views", label: "View Details" },
  { id: "query", label: "Query Runner" },
  { id: "artifacts", label: "Exports/Renders" }
];

const statusLabels: Record<string, string> = {
  available: "Available",
  cache_stale: "Cache stale",
  source_offline: "Source offline"
};

function useLoad<T>(loader: () => Promise<ApiResult<T>>, deps: unknown[]) {
  const [data, setData] = useState<ApiResult<T> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    loader()
      .then((result) => {
        if (active) {
          setData(result);
        }
      })
      .catch((error: Error) => {
        if (active) {
          setData({
            error: { code: "NETWORK_ERROR", message: error.message, details: {} }
          });
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, deps);

  return { data, loading, setData };
}

function App() {
  const [screen, setScreen] = useState<Screen>("overview");
  const [selectedDatasource, setSelectedDatasource] = useState<string>("");
  const [selectedWorkbook, setSelectedWorkbook] = useState<string>("");
  const [selectedView, setSelectedView] = useState<string>("");

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Lookout Explorer navigation">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            L
          </span>
          <div>
            <h1>Lookout Explorer</h1>
            <p>Optional evaluator demo</p>
          </div>
        </div>
        <nav>
          {screens.map((item) => (
            <button
              key={item.id}
              className={screen === item.id ? "nav-item active" : "nav-item"}
              type="button"
              onClick={() => setScreen(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </aside>
      <main className="workspace">
        {screen === "overview" && <Overview onOpen={setScreen} />}
        {screen === "datasources" && (
          <Datasources
            selectedId={selectedDatasource}
            onSelect={(id) => {
              setSelectedDatasource(id);
              setScreen("datasources");
            }}
          />
        )}
        {screen === "workbooks" && (
          <Workbooks
            selectedId={selectedWorkbook}
            onSelect={setSelectedWorkbook}
            onOpenView={(id) => {
              setSelectedView(id);
              setScreen("views");
            }}
          />
        )}
        {screen === "views" && (
          <Views
            selectedId={selectedView}
            onSelect={setSelectedView}
            onOpenArtifacts={() => setScreen("artifacts")}
          />
        )}
        {screen === "query" && <QueryRunner onOpenArtifacts={() => setScreen("artifacts")} />}
        {screen === "artifacts" && <Artifacts />}
      </main>
    </div>
  );
}

function Overview({ onOpen }: { onOpen: (screen: Screen) => void }) {
  const { data, loading } = useLoad<Record<string, unknown>>(() => request("/api/health"), []);
  const checks = [
    ["Transport", "MCP remains the primary interface"],
    ["Runtime", "Local SQLite and local generated files"],
    ["Adapter", "Dev-only HTTP bridge reusing domain services"],
    ["Scope", "No auth, no external services, no business logic fork"]
  ];

  return (
    <section className="screen">
      <ScreenHeader
        eyebrow="Optional demo"
        title="Offline BI workflows, inspectable in a browser"
        description="Lookout Explorer is a small local UI for evaluators. The technical spec and MCP tools remain the source of truth."
      />
      <div className="overview-grid">
        <div className="hero-panel">
          <h2>Start with the core MCP assignment, then use this UI to inspect seeded content.</h2>
          <p>
            Browse datasources, workbooks, saved views, bounded query previews, and generated
            render/export artifacts without connecting to Tableau or a warehouse.
          </p>
          <div className="button-row">
            <button type="button" onClick={() => onOpen("datasources")}>
              Browse datasources
            </button>
            <button type="button" className="secondary" onClick={() => onOpen("query")}>
              Run a query
            </button>
          </div>
        </div>
        <StatusPanel title="Adapter status" loading={loading} data={data} />
      </div>
      <div className="summary-grid">
        {checks.map(([label, value]) => (
          <article className="summary-item" key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </article>
        ))}
      </div>
      <div className="link-grid" aria-label="Demo sections">
        {screens.slice(1).map((item) => (
          <button key={item.id} type="button" onClick={() => onOpen(item.id)}>
            {item.label}
          </button>
        ))}
      </div>
    </section>
  );
}

function Datasources({ selectedId, onSelect }: { selectedId: string; onSelect: (id: string) => void }) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const path = `/api/datasources?query=${encodeURIComponent(query)}&status=${encodeURIComponent(status)}`;
  const { data, loading } = useLoad<Page<Datasource>>(() => request(path), [query, status]);
  const datasources = !isErrorEnvelope(data) && data ? data.items : [];
  const activeId = selectedId || datasources[0]?.id || "";

  return (
    <section className="screen">
      <ScreenHeader
        eyebrow="Discovery"
        title="Datasources"
        description="Search seeded datasources and inspect field metadata, status warnings, and allowed filters."
      />
      <div className="controls">
        <label>
          Search
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Revenue, support, pipeline" />
        </label>
        <label>
          Status
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">Any status</option>
            <option value="available">Available</option>
            <option value="cache_stale">Cache stale</option>
            <option value="source_offline">Source offline</option>
          </select>
        </label>
      </div>
      <Loadable loading={loading} data={data}>
        <div className="split">
          <ListPanel
            empty="No datasources match those filters."
            items={datasources}
            activeId={activeId}
            onSelect={onSelect}
            render={(item) => (
              <>
                <strong>{item.label}</strong>
                <span>{item.theme}</span>
                <StatusBadge status={item.status} />
              </>
            )}
          />
          {activeId ? <DatasourceDetails datasourceId={activeId} /> : <EmptyState message="Select a datasource to inspect fields." />}
        </div>
      </Loadable>
    </section>
  );
}

function DatasourceDetails({ datasourceId }: { datasourceId: string }) {
  const { data, loading } = useLoad<DatasourceDetail>(() => request(`/api/datasources/${datasourceId}`), [datasourceId]);

  return (
    <Loadable loading={loading} data={data}>
      {!isErrorEnvelope(data) && data && (
        <DetailPanel title={data.datasource.label} meta={`${data.datasource.row_count.toLocaleString()} rows`}>
          <Warnings warnings={data.warnings} />
          <p>{data.datasource.description}</p>
          <Table
            columns={["Field", "Type", "Role", "Allowed filters"]}
            rows={data.fields.map((field) => [
              field.label,
              field.data_type,
              field.semantic_role,
              field.allowed_operators.join(", ")
            ])}
          />
        </DetailPanel>
      )}
    </Loadable>
  );
}

function Workbooks({
  selectedId,
  onSelect,
  onOpenView
}: {
  selectedId: string;
  onSelect: (id: string) => void;
  onOpenView: (id: string) => void;
}) {
  const [query, setQuery] = useState("");
  const { data, loading } = useLoad<Page<Workbook>>(
    () => request(`/api/workbooks?query=${encodeURIComponent(query)}`),
    [query]
  );
  const workbooks = !isErrorEnvelope(data) && data ? data.items : [];
  const activeId = selectedId || workbooks[0]?.id || "";

  return (
    <section className="screen">
      <ScreenHeader
        eyebrow="Workbook inspection"
        title="Workbooks"
        description="Open workbook metadata and jump into contained views."
      />
      <div className="controls single">
        <label>
          Search
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Executive, pipeline, support" />
        </label>
      </div>
      <Loadable loading={loading} data={data}>
        <div className="split">
          <ListPanel
            empty="No workbooks match that search."
            items={workbooks}
            activeId={activeId}
            onSelect={onSelect}
            render={(item) => (
              <>
                <strong>{item.title}</strong>
                <span>{item.project}</span>
                <small>{item.owner}</small>
              </>
            )}
          />
          {activeId ? <WorkbookDetails workbookId={activeId} onOpenView={onOpenView} /> : <EmptyState message="Select a workbook." />}
        </div>
      </Loadable>
    </section>
  );
}

function WorkbookDetails({ workbookId, onOpenView }: { workbookId: string; onOpenView: (id: string) => void }) {
  const { data, loading } = useLoad<WorkbookDetail>(() => request(`/api/workbooks/${workbookId}`), [workbookId]);

  return (
    <Loadable loading={loading} data={data}>
      {!isErrorEnvelope(data) && data && (
        <DetailPanel title={data.workbook.title} meta={data.workbook.project}>
          <Warnings warnings={data.warnings} />
          <p>{data.workbook.description}</p>
          <div className="view-list">
            {data.views.map((view) => (
              <button key={view.id} type="button" onClick={() => onOpenView(view.id)}>
                <strong>{view.title}</strong>
                <span>{view.chart_type}</span>
              </button>
            ))}
          </div>
        </DetailPanel>
      )}
    </Loadable>
  );
}

function Views({
  selectedId,
  onSelect,
  onOpenArtifacts
}: {
  selectedId: string;
  onSelect: (id: string) => void;
  onOpenArtifacts: () => void;
}) {
  const [query, setQuery] = useState("");
  const { data, loading } = useLoad<Page<View>>(() => request(`/api/views?query=${encodeURIComponent(query)}`), [query]);
  const views = !isErrorEnvelope(data) && data ? data.items : [];
  const activeId = selectedId || views[0]?.id || "";

  return (
    <section className="screen">
      <ScreenHeader
        eyebrow="Saved analysis"
        title="View Details"
        description="Inspect saved query specs, run bounded previews, generate SVG renders, and export view data."
      />
      <div className="controls single">
        <label>
          Search
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Q1, growth, histogram" />
        </label>
      </div>
      <Loadable loading={loading} data={data}>
        <div className="split">
          <ListPanel
            empty="No views match that search."
            items={views}
            activeId={activeId}
            onSelect={onSelect}
            render={(item) => (
              <>
                <strong>{item.title}</strong>
                <span>{item.chart_type}</span>
                <small>{item.id}</small>
              </>
            )}
          />
          {activeId ? <ViewDetails viewId={activeId} onOpenArtifacts={onOpenArtifacts} /> : <EmptyState message="Select a view." />}
        </div>
      </Loadable>
    </section>
  );
}

function ViewDetails({ viewId, onOpenArtifacts }: { viewId: string; onOpenArtifacts: () => void }) {
  const { data, loading } = useLoad<ViewDetail>(() => request(`/api/views/${viewId}`), [viewId]);
  const view = !isErrorEnvelope(data) && data ? data.view : null;
  const viewWarnings = !isErrorEnvelope(data) && data ? data.warnings : [];
  const datasourceId = view?.datasource_id ?? "";
  const datasource = useLoad<DatasourceDetail>(
    () => (datasourceId ? request(`/api/datasources/${datasourceId}`) : Promise.resolve({ error: { code: "NO_SELECTION", message: "No datasource selected.", details: {} } })),
    [datasourceId]
  );
  const fields = !isErrorEnvelope(datasource.data) && datasource.data ? datasource.data.fields : [];

  return (
    <Loadable loading={loading} data={data}>
      {view && (
        <DetailPanel title={view.title} meta={`${view.chart_type} view`}>
          <Warnings warnings={viewWarnings} />
          <p>{view.description}</p>
          <div className="spec-grid">
            <JsonBlock title="Default filters" value={view.default_filters ?? {}} />
            <JsonBlock title="Saved query spec" value={view.query_spec ?? {}} />
          </div>
          <ViewActions viewId={viewId} fields={fields} onOpenArtifacts={onOpenArtifacts} />
        </DetailPanel>
      )}
    </Loadable>
  );
}

function ViewActions({
  viewId,
  fields,
  onOpenArtifacts
}: {
  viewId: string;
  fields: DatasourceField[];
  onOpenArtifacts: () => void;
}) {
  const filterable = fields.filter((field) => field.is_filterable);
  const [filterField, setFilterField] = useState("");
  const [filterValue, setFilterValue] = useState("");
  const [result, setResult] = useState<ApiResult<QueryResult | ArtifactResult> | null>(null);
  const [loading, setLoading] = useState(false);

  async function run(action: "data" | "render" | "export") {
    setLoading(true);
    const body =
      action === "data" && filterField && filterValue
        ? { preview_limit: 8, filter_overrides: [{ field: filterField, operator: "eq", value: filterValue }] }
        : action === "export"
          ? { format: "csv" }
          : {};
    setResult(await postJson(`/api/views/${viewId}/${action}`, body));
    setLoading(false);
  }

  return (
    <div className="action-panel">
      <div className="controls">
        <label>
          Filter field
          <select value={filterField} onChange={(event) => setFilterField(event.target.value)}>
            <option value="">No override</option>
            {filterable.map((field) => (
              <option key={field.id} value={field.name}>
                {field.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Filter value
          <input value={filterValue} onChange={(event) => setFilterValue(event.target.value)} placeholder="Exact value" />
        </label>
      </div>
      <div className="button-row">
        <button type="button" disabled={loading} onClick={() => run("data")}>
          Run view data
        </button>
        <button type="button" disabled={loading} className="secondary" onClick={() => run("render")}>
          Render SVG
        </button>
        <button type="button" disabled={loading} className="secondary" onClick={() => run("export")}>
          Export CSV
        </button>
        <button type="button" className="ghost" onClick={onOpenArtifacts}>
          Open artifacts
        </button>
      </div>
      {loading && <LoadingState label="Running view action" />}
      <ResultPanel result={result} />
    </div>
  );
}

function QueryRunner({ onOpenArtifacts }: { onOpenArtifacts: () => void }) {
  const { data, loading } = useLoad<Page<Datasource>>(() => request("/api/datasources"), []);
  const datasources = !isErrorEnvelope(data) && data ? data.items : [];
  const [datasourceId, setDatasourceId] = useState("");
  const activeDatasource = datasourceId || datasources.find((item) => item.status !== "source_offline")?.id || datasources[0]?.id || "";
  const detail = useLoad<DatasourceDetail>(
    () => (activeDatasource ? request(`/api/datasources/${activeDatasource}`) : Promise.resolve({ error: { code: "NO_SELECTION", message: "No datasource selected.", details: {} } })),
    [activeDatasource]
  );
  const fields = !isErrorEnvelope(detail.data) && detail.data ? detail.data.fields : [];
  const dimensions = fields.filter((field) => field.semantic_role === "dimension" || field.semantic_role === "temporal");
  const measures = fields.filter((field) => field.semantic_role === "measure");
  const [groupBy, setGroupBy] = useState("");
  const [metric, setMetric] = useState("");
  const [filterField, setFilterField] = useState("");
  const [filterValue, setFilterValue] = useState("");
  const [queryResult, setQueryResult] = useState<ApiResult<QueryResult> | null>(null);
  const [exportResult, setExportResult] = useState<ApiResult<ArtifactResult> | null>(null);
  const [running, setRunning] = useState(false);

  const selectedMetric = metric || measures[0]?.name || "";
  const selectedGroup = groupBy || dimensions[0]?.name || "";

  async function runQuery() {
    setRunning(true);
    const filters = filterField && filterValue ? [{ field: filterField, operator: "eq", value: filterValue }] : [];
    const result = await postJson<QueryResult>("/api/query", {
      datasource: activeDatasource,
      preview_limit: 8,
      query_spec: {
        operation: "aggregate",
        group_by: selectedGroup ? [selectedGroup] : [],
        metrics: selectedMetric ? [{ field: selectedMetric }] : [],
        filters,
        order_by: selectedMetric ? [{ field: selectedMetric, direction: "desc" }] : []
      }
    });
    setQueryResult(result);
    setExportResult(null);
    setRunning(false);
  }

  async function exportQuery() {
    if (!queryResult || isErrorEnvelope(queryResult) || !queryResult.query_result_id) {
      return;
    }
    setExportResult(await postJson(`/api/query-results/${queryResult.query_result_id}/export`, { format: "csv" }));
  }

  return (
    <section className="screen">
      <ScreenHeader
        eyebrow="Ad hoc analysis"
        title="Query Runner"
        description="Build a bounded structured query with field metadata from the selected datasource."
      />
      <Loadable loading={loading} data={data}>
        <div className="query-layout">
          <div className="builder">
            <label>
              Datasource
              <select value={activeDatasource} onChange={(event) => setDatasourceId(event.target.value)}>
                {datasources.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label} ({statusLabels[item.status]})
                  </option>
                ))}
              </select>
            </label>
            <label>
              Group by
              <select value={selectedGroup} onChange={(event) => setGroupBy(event.target.value)}>
                {dimensions.map((field) => (
                  <option key={field.id} value={field.name}>
                    {field.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Metric
              <select value={selectedMetric} onChange={(event) => setMetric(event.target.value)}>
                {measures.map((field) => (
                  <option key={field.id} value={field.name}>
                    {field.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Filter field
              <select value={filterField} onChange={(event) => setFilterField(event.target.value)}>
                <option value="">No filter</option>
                {fields.filter((field) => field.is_filterable).map((field) => (
                  <option key={field.id} value={field.name}>
                    {field.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Filter value
              <input value={filterValue} onChange={(event) => setFilterValue(event.target.value)} placeholder="Exact value" />
            </label>
            <div className="button-row">
              <button type="button" disabled={running || !activeDatasource} onClick={runQuery}>
                Run query
              </button>
              <button type="button" className="secondary" disabled={!queryResult || isErrorEnvelope(queryResult)} onClick={exportQuery}>
                Export result
              </button>
              <button type="button" className="ghost" onClick={onOpenArtifacts}>
                Open artifacts
              </button>
            </div>
          </div>
          <div>
            {detail.loading && <LoadingState label="Loading fields" />}
            <ResultPanel result={queryResult} />
            <ResultPanel result={exportResult} />
          </div>
        </div>
      </Loadable>
    </section>
  );
}

function Artifacts() {
  const { data, loading } = useLoad<ArtifactList>(() => request("/api/artifacts"), []);

  return (
    <section className="screen">
      <ScreenHeader
        eyebrow="Generated files"
        title="Exports/Renders"
        description="Inspect export and render metadata created under LOOKOUT_FS_ROOT."
      />
      <Loadable loading={loading} data={data}>
        {!isErrorEnvelope(data) && data && (
          <div className="artifact-grid">
            <ArtifactSection title="Renders" items={data.renders} media />
            <ArtifactSection title="Exports" items={data.exports} />
          </div>
        )}
      </Loadable>
    </section>
  );
}

function ArtifactSection({
  title,
  items,
  media = false
}: {
  title: string;
  items: Array<Record<string, unknown> & { id: string; artifact_path: string; status: string }>;
  media?: boolean;
}) {
  return (
    <section className="artifact-section">
      <h2>{title}</h2>
      {items.length === 0 ? (
        <EmptyState message={`No ${title.toLowerCase()} have been generated yet.`} />
      ) : (
        <div className="artifact-list">
          {items.map((item) => (
            <article key={item.id} className="artifact-card">
              <div>
                <strong>{String(item.view_title || item.workbook_title || item.datasource_label || item.id)}</strong>
                <code>{item.artifact_path}</code>
                <span>{item.status}</span>
              </div>
              {media && <img src={artifactUrl(item.artifact_path)} alt={`Render artifact ${item.id}`} />}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function ScreenHeader({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return (
    <header className="screen-header">
      <p>{eyebrow}</p>
      <h2>{title}</h2>
      <span>{description}</span>
    </header>
  );
}

function Loadable<T>({ loading, data, children }: { loading: boolean; data: ApiResult<T> | null; children: React.ReactNode }) {
  if (loading) {
    return <LoadingState label="Loading" />;
  }
  if (isErrorEnvelope(data)) {
    return <ErrorState error={data} />;
  }
  return <>{children}</>;
}

function LoadingState({ label }: { label: string }) {
  return (
    <div className="state loading" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      {label}
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return <div className="state empty">{message}</div>;
}

function ErrorState({ error }: { error: ErrorEnvelope }) {
  return (
    <div className="state error" role="alert">
      <strong>{error.error.code}</strong>
      <span>{error.error.message}</span>
      {Object.keys(error.error.details).length > 0 && <JsonBlock title="Details" value={error.error.details} />}
    </div>
  );
}

function StatusPanel<T>({ title, loading, data }: { title: string; loading: boolean; data: ApiResult<T> | null }) {
  return (
    <aside className="status-panel">
      <h2>{title}</h2>
      {loading && <LoadingState label="Checking adapter" />}
      {isErrorEnvelope(data) && <ErrorState error={data} />}
      {!loading && data && !isErrorEnvelope(data) && <JsonBlock title="Health" value={data} />}
    </aside>
  );
}

function StatusBadge({ status }: { status: string }) {
  return <span className={`status-badge ${status}`}>{statusLabels[status] ?? status}</span>;
}

function Warnings({ warnings }: { warnings: Warning[] }) {
  if (!warnings.length) {
    return null;
  }
  return (
    <div className="warnings" aria-label="Warnings">
      {warnings.map((warning) => (
        <span key={`${warning.code}-${warning.message}`}>{warning.code}</span>
      ))}
    </div>
  );
}

function ListPanel<T extends { id: string }>({
  items,
  activeId,
  onSelect,
  render,
  empty
}: {
  items: T[];
  activeId: string;
  onSelect: (id: string) => void;
  render: (item: T) => React.ReactNode;
  empty: string;
}) {
  if (items.length === 0) {
    return <EmptyState message={empty} />;
  }
  return (
    <div className="list-panel" aria-label="Results">
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          className={item.id === activeId ? "list-item active" : "list-item"}
          onClick={() => onSelect(item.id)}
        >
          {render(item)}
        </button>
      ))}
    </div>
  );
}

function DetailPanel({ title, meta, children }: { title: string; meta: string; children: React.ReactNode }) {
  return (
    <article className="detail-panel">
      <div className="detail-heading">
        <h2>{title}</h2>
        <span>{meta}</span>
      </div>
      {children}
    </article>
  );
}

function Table({ columns, rows }: { columns: string[]; rows: unknown[][] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {row.map((cell, cellIndex) => (
                <td key={`${index}-${cellIndex}`}>{String(cell ?? "")}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function JsonBlock({ title, value }: { title: string; value: unknown }) {
  return (
    <div className="json-block">
      <strong>{title}</strong>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </div>
  );
}

function ResultPanel({ result }: { result: ApiResult<QueryResult | ArtifactResult> | null }) {
  if (!result) {
    return null;
  }
  if (isErrorEnvelope(result)) {
    return <ErrorState error={result} />;
  }
  const artifact = "artifact_path" in result ? result : null;
  const query = "rows" in result ? result : null;

  return (
    <div className="result-panel" aria-live="polite">
      {artifact && (
        <div className="success-state">
          <strong>{artifact.status}</strong>
          <span>File path: {artifact.artifact_path}</span>
          {artifact.artifact_path.endsWith(".svg") && <img src={artifactUrl(artifact.artifact_path)} alt="Generated SVG render" />}
        </div>
      )}
      {query && (
        <>
          <div className="success-state">
            <strong>Query complete</strong>
            <span>
              {query.returned_row_count} of {query.row_count} rows
              {query.query_result_id ? `, result ${query.query_result_id}` : ""}
            </span>
          </div>
          <Warnings warnings={query.warnings} />
          <Table columns={resultColumns(query.rows)} rows={query.rows.map((row) => resultColumns(query.rows).map((column) => row[column]))} />
        </>
      )}
    </div>
  );
}

function resultColumns(rows: Record<string, unknown>[]): string[] {
  return Array.from(new Set(rows.flatMap((row) => Object.keys(row))));
}

export default App;
