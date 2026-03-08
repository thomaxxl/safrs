export const appConfig = {
  adminYamlUrl:
    import.meta.env.VITE_ADMIN_YAML_URL
    ?? "http://127.0.0.1:5656/ui/admin/admin.yaml",
  apiRoot: import.meta.env.VITE_API_ROOT ?? "http://127.0.0.1:5656/api",
  title: "Northwind Admin",
} as const;
