import { appConfig } from "../config";

export {
  AdminSchemaProvider,
  useAdminSchema,
} from "../shared-runtime/admin/schemaContext";
import {
  loadAdminBootstrap as loadSharedAdminBootstrap,
} from "../shared-runtime/admin/schemaContext";

export function loadAdminBootstrap() {
  return loadSharedAdminBootstrap(appConfig);
}
