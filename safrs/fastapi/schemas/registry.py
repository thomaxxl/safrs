# -*- coding: utf-8 -*-

from typing import Any, Dict, List, Literal, Optional, Tuple, Type, Union, cast

from pydantic import Field, create_model
from sqlalchemy.orm.interfaces import MANYTOONE, MANYTOMANY, ONETOMANY

from ..relationships import iter_exposed_relationship_properties
from .from_sqlalchemy import create_attributes_model
from .jsonapi_primitives import (
    JsonApiErrorDocument,
    JsonApiLinks,
    JsonApiMeta,
    JsonApiVersion,
    PermissiveModel,
    RelationshipLinks,
    RelationshipToMany,
    RelationshipToOne,
    ResourceIdentifierBase,
)


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

    @staticmethod
    def _generic_included_field() -> Tuple[Any, Any]:
        return (Optional[List[Dict[str, Any]]], None)

    def _included_models(self, Model: Type[Any]) -> List[Type[Any]]:
        included_models: List[Type[Any]] = []
        seen: set[Type[Any]] = set()
        for _rel_name, rel in iter_exposed_relationship_properties(Model):
            target_model = rel.mapper.class_
            if not hasattr(target_model, "_s_type") or target_model in seen:
                continue
            seen.add(target_model)
            included_models.append(target_model)
        return included_models

    def _included_field(self, Model: Type[Any]) -> Tuple[Any, Any]:
        if self.max_union_included_types <= 0:
            return self._generic_included_field()

        included_models = self._included_models(Model)
        if not included_models or len(included_models) > self.max_union_included_types:
            return self._generic_included_field()

        included_types = [self.resource(target_model) for target_model in included_models]
        item_type: Any = included_types[0]
        if len(included_types) > 1:
            item_type = Union[tuple(included_types)]
        return (Optional[list[item_type]], None)

    def attributes(self, Model: Type[Any]) -> Type[PermissiveModel]:
        cached = self._cached("attributes", Model)
        if cached is not None:
            return cached
        model_name = f"{Model._s_type}Attributes"
        schema = create_attributes_model(Model, model_name)
        return self._store("attributes", Model, schema)

    def request_attributes(self, Model: Type[Any]) -> Type[PermissiveModel]:
        cached = self._cached("request_attributes", Model)
        if cached is not None:
            return cached
        model_name = f"{Model._s_type}RequestAttributes"
        schema = create_attributes_model(Model, model_name, writable_only=True)
        return self._store("request_attributes", Model, schema)

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

    def _relationships_container(self, kind: str, Model: Type[Any], *, request_only: bool) -> Optional[Type[PermissiveModel]]:
        if not self.document_relationships:
            return None
        cached = self._cached(kind, Model)
        if cached is not None:
            return cached

        rels = dict(iter_exposed_relationship_properties(Model))
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
                rel_base = PermissiveModel if request_only else RelationshipToOne
                rel_name_suffix = "RequestRelationshipToOne" if request_only else "RelationshipToOne"
                rel_schema = cast(
                    Type[PermissiveModel],
                    create_model(
                        f"{model_type}_{rel_name}{rel_name_suffix}",
                        __base__=rel_base,
                        data=(Optional[identifier_type], None),
                    ),
                )
            elif rel.direction in (ONETOMANY, MANYTOMANY):
                rel_base = PermissiveModel if request_only else RelationshipToMany
                rel_name_suffix = "RequestRelationshipToMany" if request_only else "RelationshipToMany"
                rel_schema = cast(
                    Type[PermissiveModel],
                    create_model(
                        f"{model_type}_{rel_name}{rel_name_suffix}",
                        __base__=rel_base,
                        data=(list[identifier_type], Field(default_factory=list)),
                    ),
                )
            else:
                rel_base = PermissiveModel if request_only else RelationshipToMany
                rel_name_suffix = "RequestRelationship" if request_only else "Relationship"
                rel_schema = cast(
                    Type[PermissiveModel],
                    create_model(
                        f"{model_type}_{rel_name}{rel_name_suffix}",
                        __base__=rel_base,
                    ),
                )
            fields[rel_name] = (Optional[rel_schema], None)

        if not fields:
            return None

        schema = cast(
            Type[PermissiveModel],
            create_model(
                f"{model_type}{'RequestRelationships' if request_only else 'Relationships'}",
                __base__=PermissiveModel,
                **cast(Any, fields),
            ),
        )
        return self._store(kind, Model, cast(Type[PermissiveModel], schema))

    def relationships_container(self, Model: Type[Any]) -> Optional[Type[PermissiveModel]]:
        return self._relationships_container("relationships", Model, request_only=False)

    def request_relationships_container(self, Model: Type[Any]) -> Optional[Type[PermissiveModel]]:
        return self._relationships_container("request_relationships", Model, request_only=True)

    def resource(self, Model: Type[Any]) -> Type[PermissiveModel]:
        cached = self._cached("resource", Model)
        if cached is not None:
            return cached
        model_type = str(Model._s_type)
        fields: Dict[str, Tuple[Any, Any]] = {
            "type": (Literal[model_type], Field(default=model_type)),
            "id": (str, ...),
            "attributes": (self.attributes(Model), ...),
            "links": (Optional[JsonApiLinks], None),
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
                included=self._included_field(Model),
                meta=(Optional[JsonApiMeta], None),
                links=(Optional[JsonApiLinks], None),
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
        if kind == "doc_patch":
            id_field: Tuple[Any, Any] = (str, ...)
        elif bool(getattr(Model, "allow_client_generated_ids", False)):
            id_field = (str, ...)
        else:
            id_field = (Optional[str], None)
        fields: Dict[str, Tuple[Any, Any]] = {
            "type": (Literal[model_type], Field(default=model_type)),
            "id": id_field,
            "attributes": (Optional[self.request_attributes(Model)], None),
        }
        relationships = self.request_relationships_container(Model)
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
                meta=(Optional[JsonApiMeta], None),
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
            links=(Optional[RelationshipLinks], None),
            meta=(Optional[JsonApiMeta], None),
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
            links=(Optional[RelationshipLinks], None),
            meta=(Optional[JsonApiMeta], None),
        )
        return self._store("rel_doc_to_many", TargetModel, cast(Type[PermissiveModel], schema))
