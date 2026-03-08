import type { ReactElement } from "react";
import { Resource } from "react-admin";
import type { Schema } from "safrs-jsonapi-client";

import {
  SchemaDrivenCreate,
  SchemaDrivenEdit,
  SchemaDrivenList,
  SchemaDrivenShow,
  type SchemaDrivenPageOptions,
} from "./admin/schemaDrivenViews";
import { buildResourceMeta } from "./admin/resourceMetadata";

interface ResourceOverride {
  create?: SchemaDrivenPageOptions;
  edit?: SchemaDrivenPageOptions;
  list?: SchemaDrivenPageOptions;
  show?: SchemaDrivenPageOptions;
}

export interface ResourcePageSet {
  create: () => ReactElement;
  edit: () => ReactElement;
  list: () => ReactElement;
  show: () => ReactElement;
}

export type ResourcePageRegistry = Record<string, ResourcePageSet>;

export function makeSchemaDrivenPages(
  resourceName: string,
  override: ResourceOverride = {},
): ResourcePageSet {
  const ListPage = () => (
    <SchemaDrivenList options={override.list} resource={resourceName} />
  );
  const ShowPage = () => (
    <SchemaDrivenShow options={override.show} resource={resourceName} />
  );
  const EditPage = () => (
    <SchemaDrivenEdit options={override.edit} resource={resourceName} />
  );
  const CreatePage = () => (
    <SchemaDrivenCreate options={override.create} resource={resourceName} />
  );

  ListPage.displayName = `${resourceName}List`;
  ShowPage.displayName = `${resourceName}Show`;
  EditPage.displayName = `${resourceName}Edit`;
  CreatePage.displayName = `${resourceName}Create`;

  return {
    create: CreatePage,
    edit: EditPage,
    list: ListPage,
    show: ShowPage,
  };
}

export function buildResourceElements(
  schema: Schema,
  resourcePages?: ResourcePageRegistry,
): ReactElement[] {
  return Object.keys(schema.resources)
    .map((resourceName) => buildResourceMeta(schema, resourceName))
    .filter((resourceMeta) => resourceMeta.hidden !== true && resourceMeta.hidden !== "true")
    .flatMap((resourceMeta) => {
      const pages = resourcePages?.[resourceMeta.name] ?? makeSchemaDrivenPages(resourceMeta.name);

      if (!pages) {
        return [];
      }

      return [
        <Resource
          key={resourceMeta.name}
          create={pages.create}
          edit={pages.edit}
          list={pages.list}
          name={resourceMeta.name}
          options={{ label: resourceMeta.label }}
          show={pages.show}
        />,
      ];
    });
}
