import { createContext, useContext } from "react";
import type { ReactNode } from "react";

import {
  createDataProviderSync,
  loadAdminYamlFromUrl,
  normalizeAdminYaml,
} from "safrs-jsonapi-client";
import type { DataProvider, Schema } from "safrs-jsonapi-client";

import { createSearchEnabledDataProvider } from "./createSearchEnabledDataProvider";

const AdminSchemaContext = createContext<Schema | null>(null);

export interface AdminAppConfig {
  adminYamlUrl: string;
  apiRoot: string;
  title: string;
}

export function AdminSchemaProvider({
  children,
  schema,
}: {
  children: ReactNode;
  schema: Schema;
}) {
  return (
    <AdminSchemaContext.Provider value={schema}>
      {children}
    </AdminSchemaContext.Provider>
  );
}

export function useAdminSchema(): Schema {
  const schema = useContext(AdminSchemaContext);
  if (!schema) {
    throw new Error("Admin schema is not available.");
  }
  return schema;
}

export async function loadAdminBootstrap(config: AdminAppConfig): Promise<{
  dataProvider: DataProvider;
  schema: Schema;
}> {
  const rawYaml = await loadAdminYamlFromUrl(config.adminYamlUrl, fetch);
  const schema = normalizeAdminYaml(rawYaml);
  const baseProvider = createDataProviderSync({
    apiRoot: config.apiRoot,
    schema,
  });
  const dataProvider = createSearchEnabledDataProvider({
    apiRoot: config.apiRoot,
    baseProvider,
    fetch,
    schema,
  });

  return {
    dataProvider,
    schema,
  };
}
