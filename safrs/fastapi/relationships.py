# -*- coding: utf-8 -*-

from typing import Any, Dict, Iterator, Optional, Tuple, Type


def resolve_relationships(Model: Type[Any]) -> Dict[str, Any]:
    rels = getattr(Model, "_s_relationships", None)
    if isinstance(rels, dict):
        return rels
    mapper = getattr(Model, "__mapper__", None)
    if mapper is None:
        return {}
    return {rel.key: rel for rel in mapper.relationships}


def relationship_property(rel: Any) -> Optional[Any]:
    candidate = rel
    if not hasattr(candidate, "mapper"):
        candidate = getattr(rel, "relationship", None)
    if candidate is None or not hasattr(candidate, "mapper"):
        return None
    return candidate


def relationship_is_exposed(Model: Type[Any], rel_name: str, rel_prop: Any) -> bool:
    expose = getattr(rel_prop, "expose", None)
    if expose is False:
        return False

    try:
        mapper = getattr(Model, "__mapper__", None)
        mapped = mapper.relationships.get(rel_name) if mapper is not None else None
        if getattr(mapped, "expose", None) is False:
            return False
    except Exception:
        pass

    try:
        inst = getattr(Model, rel_name, None)
        if inst is not None and getattr(inst, "expose", None) is False:
            return False
        mapped_inst = getattr(inst, "property", None)
        if mapped_inst is not None and getattr(mapped_inst, "expose", None) is False:
            return False
    except Exception:
        pass

    return True


def iter_exposed_relationship_properties(Model: Type[Any]) -> Iterator[Tuple[str, Any]]:
    raw_rels = resolve_relationships(Model)
    mapper = getattr(Model, "__mapper__", None)
    mapper_rels: Dict[str, Any] = {}
    if mapper is not None:
        mapper_rels = {rel.key: rel for rel in mapper.relationships}

    for rel_name, rel in raw_rels.items():
        rel_prop = relationship_property(rel)
        if rel_prop is None:
            rel_prop = relationship_property(mapper_rels.get(rel_name))
        if rel_prop is None:
            continue
        if not relationship_is_exposed(Model, rel_name, rel_prop):
            continue
        yield rel_name, rel_prop
