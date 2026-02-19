# -*- coding: utf-8 -*-

from typing import Any, Dict, List, Literal, Optional, Tuple, Type, cast

from pydantic import Field, create_model
from sqlalchemy.orm.interfaces import MANYTOONE, MANYTOMANY, ONETOMANY

from .from_sqlalchemy import create_attributes_model
from .jsonapi_primitives import (
    JsonApiErrorDocument,
    JsonApiVersion,
    PermissiveModel,
    RelationshipToMany,
    RelationshipToOne,
    ResourceIdentifierBase,
)


def _resolve_relationships(Model: Type[Any]) -> Dict[str, Any]:
    rels = getattr(Model, "_s_relationships", None)
    mapper = getattr(Model, "__mapper__", None)
    mapper_rels = {rel.key: rel for rel in mapper.relationships} if mapper is not None else {}
    if not isinstance(rels, dict):
        return mapper_rels

    resolved: Dict[str, Any] = {}
    for rel_name, rel in rels.items():
        candidate = rel
        if not hasattr(candidate, "mapper"):
            candidate = getattr(rel, "relationship", None)
        if candidate is None or not hasattr(candidate, "mapper"):
            candidate = mapper_rels.get(rel_name)
        if candidate is not None and hasattr(candidate, "mapper"):
            resolved[rel_name] = candidate
    return resolved


class SchemaRegistry:
    def __init__(self, document_relationships: bool = True, max_union_included_types: int = 0) -> None:
        self.document_relationships = document_relationships
        self.max_union_included_types = max_union_included_types
        self._cache: Dict[Tuple[str, Type[Any]], Type[PermissiveModel]] = {}

    def _cached(self, kind: str, Model: Type[Any]) -> Optional[Type[PermissiveModel]]:
        return self._cache.get((kind, Model))

    def _store(self, kind: str, Model: Type[Any], schema: Type[PermissiveModel]) -> Type[PermissiveModel]:
        self._cache[(kind, Model)] = schema
        return schema

    def attributes(self, Model: Type[Any]) -> Type[PermissiveModel]:
        cached = self._cached("attributes", Model)
        if cached is not None:
            return cached
        model_name = f"{Model._s_type}Attributes"
        schema = create_attributes_model(Model, model_name)
        return self._store("attributes", Model, schema)

    def resource_identifier(self, Model: Type[Any]) -> Type[PermissiveModel]:
        cached = self._cached("identifier", Model)
        if cached is not None:
            return cached
        model_type = str(Model._s_type)
        model_name = f"{model_type}ResourceIdentifier"
        schema = create_model(
            model_name,
            __base__=ResourceIdentifierBase,
            type=(Literal[model_type], Field(default=model_type)),
            id=(str, ...),
        )
        return self._store("identifier", Model, cast(Type[PermissiveModel], schema))

    def relationships_container(self, Model: Type[Any]) -> Optional[Type[PermissiveModel]]:
        if not self.document_relationships:
            return None
        cached = self._cached("relationships", Model)
        if cached is not None:
            return cached

        rels = _resolve_relationships(Model)
        if not rels:
            return None

        fields: Dict[str, Tuple[Any, Any]] = {}
        model_type = str(Model._s_type)
        for rel_name, rel in rels.items():
            target_model = rel.mapper.class_
            if not hasattr(target_model, "_s_type"):
                continue
            identifier = self.resource_identifier(target_model)
            identifier_type: Any = identifier
            rel_schema: Type[PermissiveModel]
            if rel.direction == MANYTOONE:
                rel_schema = cast(
                    Type[PermissiveModel],
                    create_model(
                        f"{model_type}_{rel_name}RelationshipToOne",
                        __base__=RelationshipToOne,
                        data=(Optional[identifier_type], None),
                    ),
                )
            elif rel.direction in (ONETOMANY, MANYTOMANY):
                rel_schema = cast(
                    Type[PermissiveModel],
                    create_model(
                        f"{model_type}_{rel_name}RelationshipToMany",
                        __base__=RelationshipToMany,
                        data=(list[identifier_type], Field(default_factory=list)),
                    ),
                )
            else:
                rel_schema = cast(
                    Type[PermissiveModel],
                    create_model(
                        f"{model_type}_{rel_name}Relationship",
                        __base__=RelationshipToMany,
                    ),
                )
            fields[rel_name] = (Optional[rel_schema], None)

        if not fields:
            return None

        schema = cast(
            Type[PermissiveModel],
            create_model(
                f"{model_type}Relationships",
                __base__=PermissiveModel,
                **cast(Any, fields),
            ),
        )
        return self._store("relationships", Model, cast(Type[PermissiveModel], schema))

    def resource(self, Model: Type[Any]) -> Type[PermissiveModel]:
        cached = self._cached("resource", Model)
        if cached is not None:
            return cached
        model_type = str(Model._s_type)
        fields: Dict[str, Tuple[Any, Any]] = {
            "type": (Literal[model_type], Field(default=model_type)),
            "id": (str, ...),
            "attributes": (self.attributes(Model), ...),
        }
        relationships = self.relationships_container(Model)
        if relationships is not None:
            relationships_type: Any = relationships
            fields["relationships"] = (Optional[relationships_type], None)
        schema = cast(
            Type[PermissiveModel],
            create_model(
                f"{model_type}Resource",
                __base__=PermissiveModel,
                **cast(Any, fields),
            ),
        )
        return self._store("resource", Model, cast(Type[PermissiveModel], schema))

    def _document_model(self, kind: str, Model: Type[Any], is_collection: bool) -> Type[PermissiveModel]:
        cached = self._cached(kind, Model)
        if cached is not None:
            return cached
        resource = self.resource(Model)
        resource_type: Any = resource
        data_type: Any = list[resource_type] if is_collection else resource_type
        model_type = str(Model._s_type)
        schema = cast(
            Type[PermissiveModel],
            create_model(
                f"{model_type}{'DocumentCollection' if is_collection else 'DocumentSingle'}",
                __base__=PermissiveModel,
                jsonapi=(Optional[JsonApiVersion], None),
                data=(data_type, ...),
                included=(Optional[List[Dict[str, Any]]], None),
                meta=(Optional[Dict[str, Any]], None),
                links=(Optional[Dict[str, Any]], None),
            ),
        )
        return self._store(kind, Model, cast(Type[PermissiveModel], schema))

    def document_single(self, Model: Type[Any]) -> Type[PermissiveModel]:
        return self._document_model("doc_single", Model, is_collection=False)

    def document_collection(self, Model: Type[Any]) -> Type[PermissiveModel]:
        return self._document_model("doc_collection", Model, is_collection=True)

    def _document_request_model(self, kind: str, Model: Type[Any]) -> Type[PermissiveModel]:
        cached = self._cached(kind, Model)
        if cached is not None:
            return cached
        model_type = str(Model._s_type)
        fields: Dict[str, Tuple[Any, Any]] = {
            "type": (Literal[model_type], Field(default=model_type)),
            "id": (Optional[str], None),
            "attributes": (Optional[self.attributes(Model)], None),
        }
        relationships = self.relationships_container(Model)
        if relationships is not None:
            relationships_type: Any = relationships
            fields["relationships"] = (Optional[relationships_type], None)
        resource_schema = cast(
            Type[PermissiveModel],
            create_model(
                f"{model_type}{'CreateResource' if kind == 'doc_create' else 'PatchResource'}",
                __base__=PermissiveModel,
                **cast(Any, fields),
            ),
        )
        resource_schema_type: Any = resource_schema
        document_schema = cast(
            Type[PermissiveModel],
            create_model(
                f"{model_type}{'DocumentCreate' if kind == 'doc_create' else 'DocumentPatch'}",
                __base__=PermissiveModel,
                jsonapi=(Optional[JsonApiVersion], None),
                data=(resource_schema_type, ...),
                meta=(Optional[Dict[str, Any]], None),
            ),
        )
        return self._store(kind, Model, cast(Type[PermissiveModel], document_schema))

    def document_create(self, Model: Type[Any]) -> Type[PermissiveModel]:
        return self._document_request_model("doc_create", Model)

    def document_patch(self, Model: Type[Any]) -> Type[PermissiveModel]:
        return self._document_request_model("doc_patch", Model)

    def error_document(self) -> Type[PermissiveModel]:
        return cast(Type[PermissiveModel], JsonApiErrorDocument)

    def relationship_document_to_one(self, TargetModel: Type[Any]) -> Type[PermissiveModel]:
        cached = self._cached("rel_doc_to_one", TargetModel)
        if cached is not None:
            return cached
        identifier = self.resource_identifier(TargetModel)
        identifier_type: Any = identifier
        model_type = str(TargetModel._s_type)
        schema = create_model(
            f"{model_type}RelationshipDocumentToOne",
            __base__=PermissiveModel,
            jsonapi=(Optional[JsonApiVersion], None),
            data=(Optional[identifier_type], None),
            links=(Optional[Dict[str, Any]], None),
            meta=(Optional[Dict[str, Any]], None),
        )
        return self._store("rel_doc_to_one", TargetModel, cast(Type[PermissiveModel], schema))

    def relationship_document_to_many(self, TargetModel: Type[Any]) -> Type[PermissiveModel]:
        cached = self._cached("rel_doc_to_many", TargetModel)
        if cached is not None:
            return cached
        identifier = self.resource_identifier(TargetModel)
        identifier_type: Any = identifier
        model_type = str(TargetModel._s_type)
        schema = create_model(
            f"{model_type}RelationshipDocumentToMany",
            __base__=PermissiveModel,
            jsonapi=(Optional[JsonApiVersion], None),
            data=(list[identifier_type], Field(default_factory=list)),
            links=(Optional[Dict[str, Any]], None),
            meta=(Optional[Dict[str, Any]], None),
        )
        return self._store("rel_doc_to_many", TargetModel, cast(Type[PermissiveModel], schema))
