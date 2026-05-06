CREATE TABLE IF NOT EXISTS datasources (
    id TEXT PRIMARY KEY
        CHECK (length(id) = 15 AND id GLOB 'ds_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]'),
    name TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    description TEXT NOT NULL,
    theme TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('available', 'cache_stale', 'source_offline')),
    connection_type TEXT NOT NULL,
    tags TEXT NOT NULL CHECK (json_valid(tags)),
    default_filters TEXT NOT NULL CHECK (json_valid(default_filters)),
    row_count INTEGER NOT NULL CHECK (row_count >= 0),
    cache_updated_at TEXT,
    source_updated_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS datasource_fields (
    id TEXT PRIMARY KEY
        CHECK (length(id) = 16 AND id GLOB 'fld_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]'),
    datasource_id TEXT NOT NULL REFERENCES datasources(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    label TEXT NOT NULL,
    data_type TEXT NOT NULL CHECK (data_type IN ('string', 'integer', 'decimal', 'date', 'datetime', 'boolean')),
    semantic_role TEXT NOT NULL CHECK (semantic_role IN ('identifier', 'dimension', 'measure', 'temporal')),
    description TEXT NOT NULL,
    default_aggregation TEXT CHECK (default_aggregation IN ('sum', 'avg', 'min', 'max', 'count', 'count_distinct')),
    is_filterable INTEGER NOT NULL CHECK (is_filterable IN (0, 1)),
    is_sortable INTEGER NOT NULL CHECK (is_sortable IN (0, 1)),
    allowed_operators TEXT NOT NULL CHECK (json_valid(allowed_operators)),
    ordinal INTEGER NOT NULL CHECK (ordinal > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (datasource_id, name),
    UNIQUE (datasource_id, ordinal)
);

CREATE TABLE IF NOT EXISTS workbooks (
    id TEXT PRIMARY KEY
        CHECK (length(id) = 15 AND id GLOB 'wb_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]'),
    name TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    project TEXT NOT NULL,
    owner TEXT NOT NULL,
    tags TEXT NOT NULL CHECK (json_valid(tags)),
    default_filters TEXT NOT NULL CHECK (json_valid(default_filters)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS views (
    id TEXT PRIMARY KEY
        CHECK (length(id) = 17 AND id GLOB 'view_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]'),
    workbook_id TEXT NOT NULL REFERENCES workbooks(id) ON DELETE CASCADE,
    datasource_id TEXT NOT NULL REFERENCES datasources(id) ON DELETE RESTRICT,
    name TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    chart_type TEXT NOT NULL CHECK (chart_type IN ('bar', 'pie', 'treemap', 'line', 'histogram')),
    chart_config TEXT NOT NULL CHECK (json_valid(chart_config)),
    query_spec TEXT NOT NULL CHECK (json_valid(query_spec)),
    default_filters TEXT NOT NULL CHECK (json_valid(default_filters)),
    visual_config TEXT NOT NULL CHECK (json_valid(visual_config)),
    position INTEGER NOT NULL CHECK (position > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (workbook_id, name),
    UNIQUE (workbook_id, position)
);

CREATE TABLE IF NOT EXISTS query_results (
    id TEXT PRIMARY KEY
        CHECK (length(id) = 16 AND id GLOB 'run_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]'),
    datasource_id TEXT NOT NULL REFERENCES datasources(id) ON DELETE RESTRICT,
    view_id TEXT REFERENCES views(id) ON DELETE SET NULL,
    query_spec TEXT NOT NULL CHECK (json_valid(query_spec)),
    row_count INTEGER NOT NULL CHECK (row_count >= 0),
    preview_rows TEXT NOT NULL CHECK (json_valid(preview_rows)),
    status TEXT NOT NULL CHECK (status IN ('completed', 'failed')),
    warnings TEXT NOT NULL CHECK (json_valid(warnings)),
    executed_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS exports (
    id TEXT PRIMARY KEY
        CHECK (length(id) = 16 AND id GLOB 'exp_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]'),
    query_result_id TEXT REFERENCES query_results(id) ON DELETE SET NULL,
    view_id TEXT REFERENCES views(id) ON DELETE SET NULL,
    format TEXT NOT NULL CHECK (format IN ('csv', 'json')),
    artifact_path TEXT NOT NULL,
    row_count INTEGER NOT NULL CHECK (row_count >= 0),
    status TEXT NOT NULL CHECK (status IN ('ready', 'failed')),
    metadata TEXT NOT NULL CHECK (json_valid(metadata)),
    created_at TEXT NOT NULL,
    CHECK (query_result_id IS NOT NULL OR view_id IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS renders (
    id TEXT PRIMARY KEY
        CHECK (length(id) = 16 AND id GLOB 'rnd_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]'),
    workbook_id TEXT REFERENCES workbooks(id) ON DELETE SET NULL,
    view_id TEXT REFERENCES views(id) ON DELETE SET NULL,
    chart_type TEXT CHECK (chart_type IN ('bar', 'pie', 'treemap', 'line', 'histogram')),
    artifact_path TEXT NOT NULL,
    width INTEGER NOT NULL CHECK (width > 0),
    height INTEGER NOT NULL CHECK (height > 0),
    status TEXT NOT NULL CHECK (status IN ('ready', 'failed')),
    warnings TEXT NOT NULL CHECK (json_valid(warnings)),
    visual_config TEXT NOT NULL CHECK (json_valid(visual_config)),
    created_at TEXT NOT NULL,
    CHECK (workbook_id IS NOT NULL OR view_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_datasources_status_theme ON datasources(status, theme);
CREATE INDEX IF NOT EXISTS idx_datasources_label ON datasources(label);
CREATE INDEX IF NOT EXISTS idx_datasource_fields_datasource ON datasource_fields(datasource_id, ordinal);
CREATE INDEX IF NOT EXISTS idx_datasource_fields_filterable ON datasource_fields(datasource_id, is_filterable);
CREATE INDEX IF NOT EXISTS idx_datasource_fields_sortable ON datasource_fields(datasource_id, is_sortable);
CREATE INDEX IF NOT EXISTS idx_datasource_fields_type_role ON datasource_fields(data_type, semantic_role);
CREATE INDEX IF NOT EXISTS idx_workbooks_project_title ON workbooks(project, title);
CREATE INDEX IF NOT EXISTS idx_views_workbook_position ON views(workbook_id, position);
CREATE INDEX IF NOT EXISTS idx_views_datasource_chart ON views(datasource_id, chart_type);
CREATE INDEX IF NOT EXISTS idx_views_title ON views(title);
CREATE INDEX IF NOT EXISTS idx_query_results_datasource_time ON query_results(datasource_id, executed_at);
CREATE INDEX IF NOT EXISTS idx_query_results_view ON query_results(view_id);
CREATE INDEX IF NOT EXISTS idx_exports_query_result ON exports(query_result_id);
CREATE INDEX IF NOT EXISTS idx_exports_view ON exports(view_id);
CREATE INDEX IF NOT EXISTS idx_renders_workbook ON renders(workbook_id);
CREATE INDEX IF NOT EXISTS idx_renders_view ON renders(view_id);
