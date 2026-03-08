import { startTransition, useEffect, useState } from "react";
import { Admin } from "react-admin";

import type { DataProvider, Schema } from "safrs-jsonapi-client";

import {
  AdminSchemaProvider,
  type AdminAppConfig,
  loadAdminBootstrap,
} from "./admin/schemaContext";
import {
  buildResourceElements,
  type ResourcePageRegistry,
} from "./resourceRegistry";

interface BootstrapState {
  dataProvider: DataProvider;
  schema: Schema;
}

export function SchemaDrivenAdminApp({
  appConfig,
  resourcePages,
}: {
  appConfig: AdminAppConfig;
  resourcePages?: ResourcePageRegistry;
}) {
  const [bootstrap, setBootstrap] = useState<BootstrapState | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    startTransition(() => {
      loadAdminBootstrap(appConfig)
        .then((next) => {
          if (mounted) {
            setBootstrap(next);
          }
        })
        .catch((err: unknown) => {
          if (mounted) {
            setError(err instanceof Error ? err.message : String(err));
          }
        });
    });

    return () => {
      mounted = false;
    };
  }, [appConfig]);

  if (error) {
    return (
      <main style={{ fontFamily: "sans-serif", padding: 24 }}>
        <h1>{appConfig.title}</h1>
        <p>Failed to initialize the schema or data provider.</p>
        <pre>{error}</pre>
      </main>
    );
  }

  if (!bootstrap) {
    return (
      <main style={{ fontFamily: "sans-serif", padding: 24 }}>
        <h1>{appConfig.title}</h1>
        <p>Loading `admin.yaml` and wiring `safrs-jsonapi-client`...</p>
      </main>
    );
  }

  return (
    <AdminSchemaProvider schema={bootstrap.schema}>
      <Admin
        dataProvider={bootstrap.dataProvider as any}
        disableTelemetry
        title={appConfig.title}
      >
        {buildResourceElements(bootstrap.schema, resourcePages)}
      </Admin>
    </AdminSchemaProvider>
  );
}
