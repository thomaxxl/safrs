import {
  buildListQuery,
  createHttpClient,
  getTotal,
  normalizeDocument,
  queryToSearchParams,
  synthesizeCompositeKeys,
} from "safrs-jsonapi-client";
import type {
  CreateHttpClientOptions,
  DataProvider,
  JsonApiDocument,
  LoggerLike,
  Schema,
  SearchCol,
} from "safrs-jsonapi-client";

import { resolveSearchColumns } from "./resourceMetadata";

function appendQuery(url: string, query: Record<string, string | number | boolean>): string {
  const queryString = queryToSearchParams(query).toString();
  return queryString ? `${url}?${queryString}` : url;
}

function trimTrailingSlashes(value: string): string {
  return value.replace(/\/+$/, "");
}

function applySearchTemplate(template: string | undefined, search: string): string {
  if (!template) {
    return `%${search}%`;
  }

  if (template.includes("{q}")) {
    return template.split("{q}").join(search);
  }

  if (template.includes("{}")) {
    return template.split("{}").join(search);
  }

  if (template.includes("%s")) {
    return template.split("%s").join(search);
  }

  return template;
}

function buildJsonApiSearchFilter(
  search: string,
  searchCols: SearchCol[],
): { or: Array<{ name: string; op: string; val: string }> } {
  return {
    or: searchCols.map((column) => ({
      name: column.name,
      op: column.op ?? "ilike",
      val: applySearchTemplate(column.val, search),
    })),
  };
}

function omitSearchFilter(filter: Record<string, unknown> | undefined): Record<string, unknown> | undefined {
  if (!filter || !("q" in filter)) {
    return filter;
  }

  const { q: _q, ...rest } = filter;
  return Object.keys(rest).length > 0 ? rest : undefined;
}

export function createSearchEnabledDataProvider({
  apiRoot,
  baseProvider,
  fetch: fetchImpl,
  logger = console,
  schema,
}: {
  apiRoot: string;
  baseProvider: DataProvider;
  fetch?: CreateHttpClientOptions["fetch"];
  logger?: LoggerLike;
  schema: Schema;
}): DataProvider {
  const resolvedFetch = fetchImpl
    ? (input: RequestInfo | URL, init?: RequestInit) => fetchImpl(input, init)
    : globalThis.fetch.bind(globalThis);
  const http = createHttpClient({
    fetch: resolvedFetch,
    logger,
  });
  const normalizedApiRoot = `${trimTrailingSlashes(apiRoot)}/`;

  return {
    ...baseProvider,

    async getList(resource, params = {}) {
      const searchValue = params.filter?.q;
      if (typeof searchValue !== "string" || !searchValue.trim()) {
        return baseProvider.getList(resource, omitSearchFilter(params.filter) === params.filter
          ? params
          : {
              ...params,
              filter: omitSearchFilter(params.filter),
            });
      }

      const searchCols = resolveSearchColumns(schema, resource);
      if (searchCols.length === 0) {
        return baseProvider.getList(resource, {
          ...params,
          filter: omitSearchFilter(params.filter),
        });
      }

      const query = buildListQuery(
        resource,
        {
          ...params,
          filter: omitSearchFilter(params.filter),
        },
        schema,
        {
          defaultPerPage: params.pagination?.perPage,
          delimiter: schema.delimiter,
          logger,
        },
      );

      query.filter = JSON.stringify(
        buildJsonApiSearchFilter(searchValue.trim(), searchCols),
      );

      const url = appendQuery(`${normalizedApiRoot}${resource}`, query);
      const { json } = await http.requestJson<JsonApiDocument>(url);

      const normalized = normalizeDocument(json, {
        delimiter: schema.delimiter,
        includeTomany: false,
        logger,
        resourceEndpoint: resource,
        schema,
      });

      return {
        data: normalized.records.map((record) =>
          synthesizeCompositeKeys(record, resource, schema, schema.delimiter),
        ),
        total: getTotal(json, { keys: ["count", "total"] }),
      };
    },
  };
}
