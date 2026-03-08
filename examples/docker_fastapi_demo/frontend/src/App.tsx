import { SchemaDrivenAdminApp } from "./shared-runtime/SchemaDrivenAdminApp";

import { appConfig } from "./config";

export default function App() {
  return <SchemaDrivenAdminApp appConfig={appConfig} />;
}
