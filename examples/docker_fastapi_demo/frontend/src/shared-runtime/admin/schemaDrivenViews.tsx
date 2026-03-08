import { useEffect, useMemo, useState } from "react";

import {
  AutocompleteInput,
  BooleanField,
  BooleanInput,
  Create,
  Datagrid,
  DateField,
  DateInput,
  DeleteButton,
  Edit,
  EditButton,
  FunctionField,
  List,
  Loading,
  NumberField,
  NumberInput,
  ReferenceInput,
  ReferenceManyField,
  SearchInput,
  Show,
  SimpleForm,
  TextField,
  TextInput,
  TopToolbar,
  useDelete,
  useDataProvider,
  useNotify,
  useRecordContext,
  useRedirect,
  useResourceContext,
} from "react-admin";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Divider,
  Grid,
  Tab,
  Tabs,
  Typography,
} from "@mui/material";

import { useAdminSchema } from "./schemaContext";
import {
  buildResourceMeta,
  type ResourceAttributeMeta,
  type ResourceMeta,
  type ResourceRelationshipMeta,
  useResourceMeta,
} from "./resourceMetadata";

const datagridSx = {
  "& .RaDatagrid-headerCell": {
    fontWeight: 700,
  },
  "& .RaDatagrid-headerCell .MuiTypography-root": {
    fontWeight: 700,
  },
};

const DEFAULT_PAGE_SIZE = 25;

const iconOnlyActionSx = {
  lineHeight: 1,
  minWidth: "auto",
  px: 0.75,
  "& .MuiButton-endIcon": {
    m: 0,
  },
  "& .MuiButton-startIcon": {
    m: 0,
  },
};

type DisplayMode = "create" | "edit" | "list" | "show";

interface DisplayItem {
  attribute?: ResourceAttributeMeta;
  key: string;
  kind: "attribute" | "relationship";
  label: string;
  relationship?: ResourceRelationshipMeta;
}

export interface SchemaDrivenPageOptions {
  exclude?: readonly string[];
  include?: readonly string[];
}

function selectAttributes(
  attributes: ResourceAttributeMeta[],
  options: SchemaDrivenPageOptions | undefined,
): ResourceAttributeMeta[] {
  const includeSet = options?.include ? new Set(options.include) : null;
  const excludeSet = options?.exclude ? new Set(options.exclude) : null;

  let selected = attributes;

  if (includeSet) {
    selected = attributes.filter((attribute) => includeSet.has(attribute.name));
  }

  if (excludeSet) {
    selected = selected.filter((attribute) => !excludeSet.has(attribute.name));
  }

  return selected;
}

function isTruthyFlag(value: boolean | string | undefined): boolean {
  return value === true || value === "true";
}

function isHiddenSetting(
  hidden: boolean | string | undefined,
  mode: DisplayMode,
): boolean {
  if (isTruthyFlag(hidden)) {
    return true;
  }

  return typeof hidden === "string" && hidden.toLowerCase() === mode;
}

function isAttributeHidden(attribute: ResourceAttributeMeta, mode: DisplayMode): boolean {
  if (isHiddenSetting(attribute.hidden, mode)) {
    return true;
  }

  if (mode === "list" && attribute.hideList === true) {
    return true;
  }

  if (mode === "show" && attribute.hideShow === true) {
    return true;
  }

  if ((mode === "edit" || mode === "create") && attribute.hideEdit === true) {
    return true;
  }

  return false;
}

function isRelationshipHidden(
  relationship: ResourceRelationshipMeta,
  mode: DisplayMode,
): boolean {
  if (isHiddenSetting(relationship.hidden, mode)) {
    return true;
  }

  if (mode === "list" && relationship.hideList === true) {
    return true;
  }

  if (mode === "show" && relationship.hideShow === true) {
    return true;
  }

  if ((mode === "edit" || mode === "create") && relationship.hideEdit === true) {
    return true;
  }

  return false;
}

function buildDisplayItems(
  resourceMeta: ResourceMeta,
  mode: "list" | "show",
  options: SchemaDrivenPageOptions | undefined,
): DisplayItem[] {
  const selected = selectAttributes(resourceMeta.attributes, options).filter(
    (attribute) => !isAttributeHidden(attribute, mode),
  );
  const renderedRelationships = new Set<string>();
  const items: DisplayItem[] = [];

  for (const attribute of selected) {
    if (
      attribute.relationship
      && attribute.relationship.direction === "toone"
      && !isRelationshipHidden(attribute.relationship, mode)
    ) {
      if (renderedRelationships.has(attribute.relationship.name)) {
        continue;
      }

      renderedRelationships.add(attribute.relationship.name);
      items.push({
        key: `relationship:${attribute.relationship.name}`,
        kind: "relationship",
        label: attribute.relationship.label,
        relationship: attribute.relationship,
      });
      continue;
    }

    items.push({
      attribute,
      key: `attribute:${attribute.name}`,
      kind: "attribute",
      label: attribute.label,
    });
  }

  return items;
}

function buildFormAttributes(
  resourceMeta: ResourceMeta,
  mode: "create" | "edit",
  options: SchemaDrivenPageOptions | undefined,
): ResourceAttributeMeta[] {
  return selectAttributes(resourceMeta.attributes, options).filter((attribute) => {
    if (isAttributeHidden(attribute, mode)) {
      return false;
    }

    if (mode === "edit" && attribute.isPrimaryKey) {
      return false;
    }

    return true;
  });
}

function getRecordRelationValue(
  record: Record<string, unknown>,
  relationshipName: string,
): Record<string, unknown> | undefined {
  const direct = record[relationshipName];
  if (direct && typeof direct === "object" && !Array.isArray(direct)) {
    return direct as Record<string, unknown>;
  }

  const alias = record[`rel_${relationshipName}`];
  if (alias && typeof alias === "object" && !Array.isArray(alias)) {
    return alias as Record<string, unknown>;
  }

  return undefined;
}

function formatScalarValue(value: unknown, kind: ResourceAttributeMeta["kind"]): string {
  if (value === undefined || value === null || value === "") {
    return "-";
  }

  if (kind === "boolean") {
    return value ? "Yes" : "No";
  }

  if (Array.isArray(value)) {
    return value.join(", ");
  }

  return String(value);
}

function getRelatedRecordLabel(
  record: Record<string, unknown>,
  relationship: ResourceRelationshipMeta,
  targetMeta: ResourceMeta,
): string {
  const related = getRecordRelationValue(record, relationship.name);
  if (related) {
    const labelField = targetMeta.userKey ?? "name";
    const preferred = related[labelField] ?? related.name ?? related.id;
    if (preferred !== undefined && preferred !== null && preferred !== "") {
      return String(preferred);
    }
  }

  const fallback = relationship.fks
    .map((fk) => record[fk])
    .filter((value) => value !== undefined && value !== null && value !== "")
    .map((value) => String(value));

  return fallback.length > 0 ? fallback.join(" / ") : "-";
}

function renderListField(
  item: DisplayItem,
  resourceMeta: ResourceMeta,
  schema: ReturnType<typeof useAdminSchema>,
) {
  if (item.kind === "relationship" && item.relationship) {
    const targetMeta = buildResourceMeta(schema, item.relationship.targetResource);

    return (
      <FunctionField
        key={item.key}
        label={item.label}
        render={(record: Record<string, unknown>) =>
          getRelatedRecordLabel(record, item.relationship!, targetMeta)}
      />
    );
  }

  const attribute = item.attribute!;

  if (attribute.kind === "number") {
    return <NumberField key={item.key} label={item.label} source={attribute.name} />;
  }

  if (attribute.kind === "boolean") {
    return <BooleanField key={item.key} label={item.label} source={attribute.name} />;
  }

  if (attribute.kind === "date") {
    return <DateField key={item.key} label={item.label} source={attribute.name} />;
  }

  return <TextField key={item.key} label={item.label} source={attribute.name} />;
}

function renderInput(
  attribute: ResourceAttributeMeta,
  schema: ReturnType<typeof useAdminSchema>,
) {
  if (
    attribute.relationship
    && attribute.relationship.direction === "toone"
    && attribute.relationship.fks.length === 1
    && attribute.relationship.fks[0] === attribute.name
  ) {
    const targetMeta = buildResourceMeta(schema, attribute.relationship.targetResource);
    const optionText = targetMeta.userKey ?? "id";

    return (
      <ReferenceInput
        key={attribute.name}
        label={attribute.relationship.label}
        reference={attribute.relationship.targetResource}
        source={attribute.name}
      >
        <AutocompleteInput
          fullWidth
          label={attribute.relationship.label}
          optionText={optionText}
        />
      </ReferenceInput>
    );
  }

  const commonProps = {
    label: attribute.label,
    required: attribute.required,
    source: attribute.name,
  };

  if (attribute.kind === "number") {
    return <NumberInput key={attribute.name} {...commonProps} />;
  }

  if (attribute.kind === "boolean") {
    return <BooleanInput key={attribute.name} {...commonProps} />;
  }

  if (attribute.kind === "date") {
    return <DateInput key={attribute.name} {...commonProps} />;
  }

  if (attribute.kind === "longText") {
    return <TextInput key={attribute.name} {...commonProps} minRows={5} multiline />;
  }

  return <TextInput key={attribute.name} {...commonProps} />;
}

function OverviewGrid({
  items,
  resourceMeta,
}: {
  items: DisplayItem[];
  resourceMeta: ResourceMeta;
}) {
  const schema = useAdminSchema();
  const record = useRecordContext();

  if (!record) {
    return <Loading />;
  }

  return (
    <Box>
      <Typography sx={{ mb: 4 }} variant="h4">
        {resourceMeta.label}{" "}
        <Box component="span" sx={{ color: "text.secondary", fontStyle: "italic" }}>
          #{String(record.id ?? "")}
        </Box>
      </Typography>
      <Grid container spacing={3}>
        {items.map((item) => {
          let value = "-";

          if (item.kind === "relationship" && item.relationship) {
            const targetMeta = buildResourceMeta(schema, item.relationship.targetResource);
            value = getRelatedRecordLabel(
              record as Record<string, unknown>,
              item.relationship,
              targetMeta,
            );
          } else if (item.attribute) {
            value = formatScalarValue(
              (record as Record<string, unknown>)[item.attribute.name],
              item.attribute.kind,
            );
          }

          return (
            <Grid item key={item.key} md={3} sm={6} xs={12}>
              <Typography
                color="text.secondary"
                sx={{ fontWeight: 700, mb: 0.5 }}
                variant="body2"
              >
                {item.label}
              </Typography>
              <Typography variant="body1">{value}</Typography>
            </Grid>
          );
        })}
      </Grid>
    </Box>
  );
}

function buildRelationshipTarget(
  relationship: ResourceRelationshipMeta,
  delimiter: string,
): string {
  return relationship.fks.length === 1
    ? relationship.fks[0]
    : relationship.fks.join(relationship.compositeDelimiter ?? delimiter);
}

function isBackReferenceItem(
  item: DisplayItem,
  relationship: ResourceRelationshipMeta,
  parentResource: string,
): boolean {
  if (item.kind === "attribute" && item.attribute) {
    return relationship.fks.includes(item.attribute.name);
  }

  if (item.kind === "relationship" && item.relationship) {
    return (
      item.relationship.targetResource === parentResource
      && item.relationship.fks.some((fk) => relationship.fks.includes(fk))
    );
  }

  return false;
}

function ManyRelationshipTab({
  parentResource,
  relationship,
}: {
  parentResource: string;
  relationship: ResourceRelationshipMeta;
}) {
  const schema = useAdminSchema();
  const targetMeta = useMemo(
    () => buildResourceMeta(schema, relationship.targetResource),
    [relationship.targetResource, schema],
  );
  const items = useMemo(
    () =>
      buildDisplayItems(targetMeta, "list", undefined)
        .filter((item) => !isBackReferenceItem(item, relationship, parentResource))
        .slice(0, targetMeta.maxListColumns),
    [parentResource, relationship, targetMeta],
  );
  const target = buildRelationshipTarget(relationship, schema.delimiter);
  const sortField = targetMeta.userKey ?? targetMeta.attributes[0]?.name ?? "id";

  return (
    <ReferenceManyField
      perPage={DEFAULT_PAGE_SIZE}
      reference={relationship.targetResource}
      sort={{ field: sortField, order: "ASC" }}
      target={target}
    >
      <Datagrid bulkActionButtons={false} rowClick="show" sx={datagridSx}>
        {items.map((item) => renderListField(item, targetMeta, schema))}
        <FunctionField
          label=""
          render={(record: Record<string, unknown>) => (
            <ListRowActions record={record} resource={targetMeta.name} />
          )}
        />
      </Datagrid>
    </ReferenceManyField>
  );
}

function buildRelatedId(
  record: Record<string, unknown>,
  relationship: ResourceRelationshipMeta,
  schema: ReturnType<typeof useAdminSchema>,
): string | undefined {
  const values = relationship.fks
    .map((fk) => record[fk])
    .filter((value) => value !== undefined && value !== null && value !== "")
    .map((value) => String(value));

  if (values.length !== relationship.fks.length) {
    return undefined;
  }

  if (values.length === 1) {
    return values[0];
  }

  return values.join(relationship.compositeDelimiter ?? schema.delimiter);
}

function ListRowActions({
  record,
  resource,
}: {
  record: Record<string, unknown>;
  resource: string;
}) {
  return (
    <Box sx={{ display: "flex", gap: 0.5, whiteSpace: "nowrap" }}>
      <EditButton
        aria-label="Edit"
        label=""
        record={record as any}
        resource={resource}
        sx={iconOnlyActionSx}
      />
      <DeleteButton
        aria-label="Delete"
        color="primary"
        label=""
        mutationMode="pessimistic"
        record={record as any}
        redirect={false}
        resource={resource}
        sx={iconOnlyActionSx}
      />
    </Box>
  );
}

function RelatedRecordSummary({
  data,
  resource,
}: {
  data: Record<string, unknown>;
  resource: string;
}) {
  const schema = useAdminSchema();
  const resourceMeta = useMemo(() => buildResourceMeta(schema, resource), [resource, schema]);
  const items = useMemo(
    () => buildDisplayItems(resourceMeta, "show", undefined).slice(0, resourceMeta.maxListColumns),
    [resourceMeta],
  );

  return (
    <Box sx={{ pt: 2 }}>
      <Grid container spacing={3}>
        {items.map((item) => {
          let value = "-";

          if (item.kind === "relationship" && item.relationship) {
            const targetMeta = buildResourceMeta(schema, item.relationship.targetResource);
            value = getRelatedRecordLabel(data, item.relationship, targetMeta);
          } else if (item.attribute) {
            value = formatScalarValue(data[item.attribute.name], item.attribute.kind);
          }

          return (
            <Grid item key={item.key} md={3} sm={6} xs={12}>
              <Typography
                color="text.secondary"
                sx={{ fontWeight: 700, mb: 0.5 }}
                variant="body2"
              >
                {item.label}
              </Typography>
              <Typography variant="body1">{value}</Typography>
            </Grid>
          );
        })}
      </Grid>
    </Box>
  );
}

function SingleRelationshipTab({
  relationship,
}: {
  relationship: ResourceRelationshipMeta;
}) {
  const dataProvider = useDataProvider();
  const record = useRecordContext();
  const schema = useAdminSchema();
  const [related, setRelated] = useState<Record<string, unknown> | null>(() => {
    if (!record) {
      return null;
    }

    return (
      getRecordRelationValue(record as Record<string, unknown>, relationship.name) ?? null
    );
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const relatedId = useMemo(
    () =>
      record
        ? buildRelatedId(record as Record<string, unknown>, relationship, schema)
        : undefined,
    [record, relationship, schema],
  );

  useEffect(() => {
    if (!record) {
      return;
    }

    const embedded = getRecordRelationValue(
      record as Record<string, unknown>,
      relationship.name,
    );
    if (embedded) {
      setRelated(embedded);
      setLoading(false);
      setError(null);
      return;
    }

    if (!relatedId) {
      setRelated(null);
      setLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    dataProvider
      .getOne(relationship.targetResource, { id: relatedId })
      .then(({ data }) => {
        if (!cancelled) {
          setRelated(data as Record<string, unknown>);
          setLoading(false);
        }
      })
      .catch((nextError: unknown) => {
        if (!cancelled) {
          setError(nextError instanceof Error ? nextError.message : String(nextError));
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [dataProvider, record, relatedId, relationship]);

  if (loading) {
    return <Loading />;
  }

  if (error) {
    return (
      <Typography color="error" sx={{ pt: 2 }}>
        {error}
      </Typography>
    );
  }

  if (!related) {
    return (
      <Typography color="text.secondary" sx={{ pt: 2 }}>
        No related record.
      </Typography>
    );
  }

  return <RelatedRecordSummary data={related} resource={relationship.targetResource} />;
}

function buildSearchPlaceholder(searchLabels: string[]): string {
  if (searchLabels.length === 0) {
    return "Search";
  }

  if (searchLabels.length === 1) {
    return `Search ${searchLabels[0]}`;
  }

  if (searchLabels.length === 2) {
    return `Search ${searchLabels[0]} or ${searchLabels[1]}`;
  }

  return `Search ${searchLabels.slice(0, 3).join(", ")}`;
}

function getRelationshipPriority(
  relationship: ResourceRelationshipMeta,
  parentResource: string,
): number {
  if (relationship.direction === "tomany" && relationship.targetResource !== parentResource) {
    return 0;
  }

  if (relationship.direction === "toone" && relationship.targetResource !== parentResource) {
    return 1;
  }

  if (relationship.direction === "tomany") {
    return 2;
  }

  return 3;
}

function getDefaultRelationshipTabIndex(
  relationships: ResourceRelationshipMeta[],
  parentResource: string,
): number {
  if (relationships.length === 0) {
    return 0;
  }

  let bestIndex = 0;
  let bestPriority = Number.POSITIVE_INFINITY;

  relationships.forEach((relationship, index) => {
    const priority = getRelationshipPriority(relationship, parentResource);
    if (priority < bestPriority) {
      bestPriority = priority;
      bestIndex = index;
    }
  });

  return bestIndex;
}

function TabPanel({
  children,
  index,
  value,
}: {
  children: React.ReactNode;
  index: number;
  value: number;
}) {
  return (
    <Box hidden={value !== index} sx={{ pt: 3 }}>
      {value === index ? children : null}
    </Box>
  );
}

function ShowContent({
  options,
  resource,
}: {
  options?: SchemaDrivenPageOptions;
  resource: string;
}) {
  const resourceMeta = useResourceMeta(resource);
  const overviewItems = useMemo(
    () => buildDisplayItems(resourceMeta, "show", options),
    [options, resourceMeta],
  );
  const relationships = useMemo(
    () => resourceMeta.relationships.filter((relationship) => !isRelationshipHidden(relationship, "show")),
    [resourceMeta.relationships],
  );
  const preferredTabIndex = useMemo(
    () => getDefaultRelationshipTabIndex(relationships, resource),
    [relationships, resource],
  );
  const [tabIndex, setTabIndex] = useState(preferredTabIndex);

  useEffect(() => {
    setTabIndex(preferredTabIndex);
  }, [preferredTabIndex, resource]);

  return (
    <Box>
      <OverviewGrid items={overviewItems} resourceMeta={resourceMeta} />
      {relationships.length > 0 ? (
        <>
          <Divider sx={{ my: 4 }} />
          <Tabs
            allowScrollButtonsMobile
            onChange={(_event, nextIndex) => setTabIndex(nextIndex)}
            scrollButtons="auto"
            value={tabIndex}
            variant="scrollable"
          >
            {relationships.map((relationship) => (
              <Tab key={relationship.name} label={relationship.label} />
            ))}
          </Tabs>
          {relationships.map((relationship, index) => (
            <TabPanel index={index} key={relationship.name} value={tabIndex}>
              {relationship.direction === "tomany" ? (
                <ManyRelationshipTab
                  parentResource={resource}
                  relationship={relationship}
                />
              ) : (
                <SingleRelationshipTab relationship={relationship} />
              )}
            </TabPanel>
          ))}
        </>
      ) : null}
    </Box>
  );
}

function SchemaDrivenShowDeleteButton({
  onDeleteStart,
  onDeleteError,
}: {
  onDeleteError: () => void;
  onDeleteStart: () => void;
}) {
  const notify = useNotify();
  const record = useRecordContext();
  const redirect = useRedirect();
  const resource = useResourceContext();
  const [open, setOpen] = useState(false);
  const [deleteOne, { isPending }] = useDelete();

  if (!record || !resource) {
    return null;
  }

  const handleClose = () => {
    if (!isPending) {
      setOpen(false);
    }
  };

  const handleConfirmDelete = () => {
    onDeleteStart();
    deleteOne(
      resource,
      {
        id: record.id,
        previousData: record as any,
      },
      {
        mutationMode: "pessimistic",
        onError: (error: unknown) => {
          const message =
            typeof error === "string"
              ? error
              : error instanceof Error
                ? error.message
                : "ra.notification.http_error";

          notify(message, {
            type: "error",
            messageArgs: {
              _: typeof error === "string"
                ? error
                : error instanceof Error
                  ? error.message
                  : undefined,
            },
          });
          onDeleteError();
          setOpen(false);
        },
        onSuccess: () => {
          notify("ra.notification.deleted", {
            type: "info",
            messageArgs: { smart_count: 1 },
          });
          redirect("list", resource);
        },
      },
    );
  };

  return (
    <>
      <Button
        color="primary"
        onClick={() => setOpen(true)}
        startIcon={<DeleteOutlineIcon />}
      >
        DELETE
      </Button>
      <Dialog onClose={handleClose} open={open}>
        <DialogTitle>Delete record?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            {`This will permanently delete ${resource} ${String(record.id)}.`}
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button disabled={isPending} onClick={handleClose}>
            CANCEL
          </Button>
          <Button
            color="primary"
            disabled={isPending}
            onClick={handleConfirmDelete}
            startIcon={<DeleteOutlineIcon />}
          >
            DELETE
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

function SchemaDrivenShowActions({
  onDeleteError,
  onDeleteStart,
}: {
  onDeleteError: () => void;
  onDeleteStart: () => void;
}) {
  const record = useRecordContext();

  if (!record) {
    return null;
  }

  return (
    <TopToolbar>
      <EditButton label="EDIT" />
      <SchemaDrivenShowDeleteButton
        onDeleteError={onDeleteError}
        onDeleteStart={onDeleteStart}
      />
    </TopToolbar>
  );
}

export function SchemaDrivenList({
  options,
  resource,
}: {
  options?: SchemaDrivenPageOptions;
  resource: string;
}) {
  const schema = useAdminSchema();
  const resourceMeta = useResourceMeta(resource);
  const items = useMemo(
    () => buildDisplayItems(resourceMeta, "list", options).slice(0, resourceMeta.maxListColumns),
    [options, resourceMeta],
  );
  const sortField = resourceMeta.userKey ?? resourceMeta.attributes[0]?.name ?? "id";
  const filters = useMemo(() => {
    if (resourceMeta.searchColumns.length === 0) {
      return undefined;
    }

    return [
      <SearchInput
        alwaysOn
        key={`${resource}-search`}
        placeholder={buildSearchPlaceholder(
          resourceMeta.searchColumns.map((column) => column.label),
        )}
        source="q"
      />,
    ];
  }, [resource, resourceMeta.searchColumns]);

  return (
    <List
      filters={filters}
      perPage={DEFAULT_PAGE_SIZE}
      resource={resource}
      sort={{ field: sortField, order: "ASC" }}
    >
      <Datagrid bulkActionButtons={false} rowClick="show" sx={datagridSx}>
        {items.map((item) => renderListField(item, resourceMeta, schema))}
        <FunctionField
          label=""
          render={(record: Record<string, unknown>) => (
            <ListRowActions record={record} resource={resourceMeta.name} />
          )}
        />
      </Datagrid>
    </List>
  );
}

export function SchemaDrivenShow({
  options,
  resource,
}: {
  options?: SchemaDrivenPageOptions;
  resource: string;
}) {
  const [isDeleting, setIsDeleting] = useState(false);

  return (
    <Show
      actions={
        <SchemaDrivenShowActions
          onDeleteError={() => setIsDeleting(false)}
          onDeleteStart={() => setIsDeleting(true)}
        />
      }
      queryOptions={{ enabled: !isDeleting }}
      resource={resource}
    >
      <ShowContent options={options} resource={resource} />
    </Show>
  );
}

export function SchemaDrivenEdit({
  options,
  resource,
}: {
  options?: SchemaDrivenPageOptions;
  resource: string;
}) {
  const schema = useAdminSchema();
  const resourceMeta = useResourceMeta(resource);
  const attributes = useMemo(
    () => buildFormAttributes(resourceMeta, "edit", options),
    [options, resourceMeta],
  );

  return (
    <Edit mutationMode="pessimistic" resource={resource}>
      <SimpleForm>{attributes.map((attribute) => renderInput(attribute, schema))}</SimpleForm>
    </Edit>
  );
}

export function SchemaDrivenCreate({
  options,
  resource,
}: {
  options?: SchemaDrivenPageOptions;
  resource: string;
}) {
  const schema = useAdminSchema();
  const resourceMeta = useResourceMeta(resource);
  const attributes = useMemo(
    () => buildFormAttributes(resourceMeta, "create", options),
    [options, resourceMeta],
  );

  return (
    <Create resource={resource}>
      <SimpleForm>{attributes.map((attribute) => renderInput(attribute, schema))}</SimpleForm>
    </Create>
  );
}
