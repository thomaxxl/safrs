# -*- coding: utf-8 -*-

from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class PermissiveModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class JsonApiVersion(PermissiveModel):
    version: str = "1.0"


class JsonApiLinks(PermissiveModel):
    pass


class JsonApiMeta(PermissiveModel):
    pass


class JsonApiErrorLinks(PermissiveModel):
    about: Optional[str] = None


class JsonApiErrorSource(PermissiveModel):
    pointer: Optional[str] = None
    parameter: Optional[str] = None
    header: Optional[str] = None


class JsonApiErrorObject(PermissiveModel):
    id: Optional[str] = None
    links: Optional[JsonApiErrorLinks] = None
    status: Optional[str] = None
    source: Optional[JsonApiErrorSource] = None
    title: Optional[str] = None
    detail: Optional[str] = None
    code: Optional[str] = None
    meta: Optional[JsonApiMeta] = None


class JsonApiErrorDocument(PermissiveModel):
    jsonapi: Optional[JsonApiVersion] = None
    errors: List[JsonApiErrorObject] = Field(default_factory=list)


class ResourceIdentifierBase(PermissiveModel):
    type: str
    id: str


class RelationshipLinks(PermissiveModel):
    self_: Optional[str] = Field(default=None, alias="self")
    related: Optional[str] = None

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class RelationshipToOne(PermissiveModel):
    data: Optional[Any] = None
    links: Optional[RelationshipLinks] = None
    meta: Optional[JsonApiMeta] = None


class RelationshipToMany(PermissiveModel):
    data: List[Any] = Field(default_factory=list)
    links: Optional[RelationshipLinks] = None
    meta: Optional[JsonApiMeta] = None
