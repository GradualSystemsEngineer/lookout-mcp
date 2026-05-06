import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const ok = (body: unknown) =>
  Promise.resolve({
    json: () => Promise.resolve(body)
  } as Response);

describe("Lookout Explorer", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.includes("/api/health")) {
          return ok({
            status: "ok",
            service: "lookout-mcp",
            db_path: "lookout.sqlite3",
            fs_root: "var",
            log_level: "INFO"
          });
        }
        return ok({ items: [], row_count: 0, returned_row_count: 0, truncated: false, next_cursor: null, warnings: [] });
      })
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("marks the browser UI as optional evaluator support", async () => {
    render(<App />);

    expect(screen.getAllByText("Lookout Explorer")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Optional evaluator demo")[0]).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText(/lookout-mcp/)).toBeInTheDocument());
  });

  it("shows the shared error envelope when the adapter returns one", async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      json: () =>
        Promise.resolve({
          error: {
            code: "SOURCE_UNAVAILABLE",
            message: "Datasource source is offline.",
            details: { datasource_id: "ds_demo" }
          }
        })
    } as Response);

    render(<App />);

    await waitFor(() => expect(screen.getByText("SOURCE_UNAVAILABLE")).toBeInTheDocument());
    expect(screen.getByText("Datasource source is offline.")).toBeInTheDocument();
  });
});
