export async function readFile(): Promise<never> {
  throw new Error(
    "The browser build cannot read files from disk. Use loadAdminYamlFromUrl() instead.",
  );
}
