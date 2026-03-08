import { useMemo } from "react";

import type {
  Schema,
  SchemaAttribute,
  SchemaRelationship,
  SearchCol,
} from "safrs-jsonapi-client";

import { useAdminSchema } from "./schemaContext";

type VisibilitySetting = boolean | string | undefined;

interface RawAttribute {
  hidden?: VisibilitySetting;
  hide_edit?: VisibilitySetting;
  hide_list?: VisibilitySetting;
  hide_show?: VisibilitySetting;
  hideEdit?: VisibilitySetting;
  hideList?: VisibilitySetting;
  hideShow?: VisibilitySetting;
  label?: string;
  name?: string;
  required?: boolean;
  search?: boolean | string;
  type?: string;
}

interface RawTabGroup {
  attributes?: Array<{ name?: string } | string>;
  composite_delimiter?: string;
  compositeDelimiter?: string;
  direction?: "toone" | "tomany";
  fks?: string[];
  hidden?: VisibilitySetting;
  hide_edit?: VisibilitySetting;
  hide_list?: VisibilitySetting;
  hide_show?: VisibilitySetting;
  hideEdit?: VisibilitySetting;
  hideList?: VisibilitySetting;
  hideShow?: VisibilitySetting;
  label?: string;
  name?: string;
  resource?: string;
}

interface RawResource {
  attributes?: Array<RawAttribute | string>;
  hidden?: VisibilitySetting;
  label?: string;
  max_list_columns?: number | string;
  maxListColumns?: number | string;
  tab_groups?: Array<RawTabGroup> | Record<string, RawTabGroup>;
  type?: string;
  user_key?: string;
}

interface RawAdminYaml {
  resources?: Record<string, RawResource>;
  settings?: {
    max_list_columns?: number | string;
  };
}

export interface ResourceRelationshipMeta extends SchemaRelationship {
  attributes?: string[];
  hidden?: VisibilitySetting;
  hideEdit?: boolean;
  hideList?: boolean;
  hideShow?: boolean;
  label: string;
}

export interface ResourceAttributeMeta extends SchemaAttribute {
  hidden?: VisibilitySetting;
  hideList?: boolean;
  hideShow?: boolean;
  isPrimaryKey: boolean;
  kind: "boolean" | "date" | "longText" | "number" | "text";
  label: string;
  relationship?: ResourceRelationshipMeta;
}

export interface ResourceMeta {
  attributes: ResourceAttributeMeta[];
  hidden?: VisibilitySetting;
  label: string;
  maxListColumns: number;
  name: string;
  relationships: ResourceRelationshipMeta[];
  searchColumns: Array<SearchCol & { label: string }>;
  userKey?: string;
}

function humanizeIdentifier(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function normalizeLabel(label: string | undefined, fallbackName: string): string {
  const cleaned = label?.trim().replace(/\*+$/, "").trim();
  return cleaned && cleaned.length > 0
    ? cleaned
    : humanizeIdentifier(fallbackName);
}

function isPrimaryKeyName(resource: string, attributeName: string): boolean {
  const lowered = attributeName.toLowerCase();
  return lowered === "id" || lowered === `${resource.toLowerCase()}id`;
}

function inferFieldKind(attribute: SchemaAttribute): ResourceAttributeMeta["kind"] {
  const rawType = attribute.type?.toUpperCase();
  const loweredName = attribute.name.toLowerCase();

  if (rawType?.includes("BOOL")) {
    return "boolean";
  }

  if (
    rawType?.includes("DATE")
    || rawType?.includes("TIME")
    || loweredName.endsWith("date")
    || loweredName.endsWith("at")
  ) {
    return "date";
  }

  if (
    rawType?.includes("DECIMAL")
    || rawType?.includes("INT")
    || rawType?.includes("NUMERIC")
    || rawType?.includes("DOUBLE")
    || rawType?.includes("FLOAT")
    || rawType?.includes("REAL")
  ) {
    return "number";
  }

  if (
    loweredName.includes("description")
    || loweredName.includes("notes")
  ) {
    return "longText";
  }

  return "text";
}

function getRawAdminYaml(schema: Schema): RawAdminYaml {
  return (schema.raw ?? {}) as RawAdminYaml;
}

function getRawResource(schema: Schema, resource: string): RawResource | undefined {
  return getRawAdminYaml(schema).resources?.[resource];
}

function normalizeBoolean(value: VisibilitySetting): boolean | undefined {
  if (value === true || value === "true") {
    return true;
  }

  if (value === false || value === "false") {
    return false;
  }

  return undefined;
}

function firstDefined<T>(...values: Array<T | undefined>): T | undefined {
  return values.find((value) => value !== undefined);
}

function normalizeNumber(value: number | string | undefined, fallback: number): number {
  if (value === undefined) {
    return fallback;
  }

  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function normalizeNames(input: Array<{ name?: string } | string> | undefined): string[] {
  const names: string[] = [];

  for (const item of input ?? []) {
    if (typeof item === "string") {
      names.push(item);
      continue;
    }

    if (item?.name) {
      names.push(item.name);
    }
  }

  return names;
}

function buildRawAttributeMap(rawResource: RawResource | undefined): Map<string, RawAttribute> {
  const map = new Map<string, RawAttribute>();

  for (const attribute of rawResource?.attributes ?? []) {
    if (typeof attribute === "string") {
      map.set(attribute, { name: attribute });
      continue;
    }

    if (attribute?.name) {
      map.set(attribute.name, attribute);
    }
  }

  return map;
}

function buildRawRelationshipMap(rawResource: RawResource | undefined): Map<string, RawTabGroup> {
  const map = new Map<string, RawTabGroup>();
  const tabGroups = rawResource?.tab_groups;

  if (!tabGroups) {
    return map;
  }

  if (Array.isArray(tabGroups)) {
    for (const tabGroup of tabGroups) {
      if (tabGroup?.name) {
        map.set(tabGroup.name, tabGroup);
      }
    }
    return map;
  }

  for (const [name, tabGroup] of Object.entries(tabGroups)) {
    map.set(name, { ...tabGroup, name: tabGroup.name ?? name });
  }

  return map;
}

function isSearchEnabled(value: boolean | string | undefined): boolean {
  return value === true || value === "true";
}

export function resolveSearchColumns(schema: Schema, resource: string): SearchCol[] {
  const schemaResource = schema.resources[resource];
  if (!schemaResource) {
    return [];
  }

  if (schemaResource.searchCols.length > 0) {
    return schemaResource.searchCols;
  }

  const rawResource = getRawResource(schema, resource);
  const rawAttributeMap = buildRawAttributeMap(rawResource);
  const fromRaw = schemaResource.attributeConfigs
    .filter((attribute) => isSearchEnabled(rawAttributeMap.get(attribute.name)?.search))
    .map((attribute) => ({ name: attribute.name }));

  return fromRaw;
}

export function buildResourceMeta(schema: Schema, resource: string): ResourceMeta {
  const schemaResource = schema.resources[resource];
  if (!schemaResource) {
    throw new Error(`Unknown resource '${resource}'.`);
  }

  const rawAdminYaml = getRawAdminYaml(schema);
  const rawResource = getRawResource(schema, resource);
  const rawAttributeMap = buildRawAttributeMap(rawResource);
  const rawRelationshipMap = buildRawRelationshipMap(rawResource);

  const relationships = schemaResource.relationships.map((relationship) => {
    const rawRelationship = rawRelationshipMap.get(relationship.name);

    return {
      ...relationship,
      attributes: normalizeNames(rawRelationship?.attributes),
      hidden: rawRelationship?.hidden,
      hideEdit: firstDefined(
        normalizeBoolean(rawRelationship?.hideEdit),
        normalizeBoolean(rawRelationship?.hide_edit),
      ),
      hideList: firstDefined(
        relationship.hideList,
        normalizeBoolean(rawRelationship?.hideList),
        normalizeBoolean(rawRelationship?.hide_list),
      ),
      hideShow: firstDefined(
        relationship.hideShow,
        normalizeBoolean(rawRelationship?.hideShow),
        normalizeBoolean(rawRelationship?.hide_show),
      ),
      label: normalizeLabel(rawRelationship?.label, relationship.name),
    } satisfies ResourceRelationshipMeta;
  });

  const relationshipByName = new Map(
    relationships.map((relationship) => [relationship.name, relationship]),
  );

  const maxListColumns = normalizeNumber(
    firstDefined(rawResource?.max_list_columns, rawResource?.maxListColumns),
    normalizeNumber(rawAdminYaml.settings?.max_list_columns, 8),
  );
  const searchColumns = resolveSearchColumns(schema, resource).map((column) => ({
    ...column,
    label: normalizeLabel(rawAttributeMap.get(column.name)?.label, column.name),
  }));

  return {
    attributes: schemaResource.attributeConfigs.map((attribute) => {
      const rawAttribute = rawAttributeMap.get(attribute.name);
      const relationship = schema.fkToRelationship[resource]?.[attribute.name];
      const relationshipMeta = relationship
        ? relationshipByName.get(relationship.name)
        : undefined;

      return {
        ...attribute,
        hidden: rawAttribute?.hidden,
        hideEdit: firstDefined(
          attribute.hideEdit,
          normalizeBoolean(rawAttribute?.hideEdit),
          normalizeBoolean(rawAttribute?.hide_edit),
        ),
        hideList: firstDefined(
          normalizeBoolean(rawAttribute?.hideList),
          normalizeBoolean(rawAttribute?.hide_list),
        ),
        hideShow: firstDefined(
          normalizeBoolean(rawAttribute?.hideShow),
          normalizeBoolean(rawAttribute?.hide_show),
        ),
        isPrimaryKey: isPrimaryKeyName(resource, attribute.name),
        kind: inferFieldKind(attribute),
        label: normalizeLabel(
          rawAttribute?.label,
          relationshipMeta?.label ?? attribute.name,
        ),
        relationship: relationshipMeta,
      };
    }),
    hidden: rawResource?.hidden,
    label: normalizeLabel(rawResource?.label, resource),
    maxListColumns,
    name: resource,
    relationships,
    searchColumns,
    userKey: schemaResource.userKey ?? rawResource?.user_key,
  };
}

export function useResourceMeta(resource: string): ResourceMeta {
  const schema = useAdminSchema();

  return useMemo(() => buildResourceMeta(schema, resource), [resource, schema]);
}

export function useResourceMetas(): ResourceMeta[] {
  const schema = useAdminSchema();

  return useMemo(
    () => Object.keys(schema.resources).map((resource) => buildResourceMeta(schema, resource)),
    [schema],
  );
}
