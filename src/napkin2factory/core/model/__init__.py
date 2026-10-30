"""Pydantic schemas for every file in a product repository (GRAND_PLAN §4.2)."""

from napkin2factory.core.model.assemblies import Assembly, Child, Exploded
from napkin2factory.core.model.base import Model, Quantity, UriField
from napkin2factory.core.model.decisions import Decision, DecisionsFile
from napkin2factory.core.model.docs import DocMeta
from napkin2factory.core.model.ecr import TRANSITIONS, Applied, Approval, Ecr, Edit
from napkin2factory.core.model.interfaces import (
    BoltPatternSpec,
    Frame,
    Interface,
    MatingFaceSpec,
)
from napkin2factory.core.model.manifest import Manifest, Operator, ProductInfo
from napkin2factory.core.model.parameters import Parameter, ParametersFile
from napkin2factory.core.model.parts import (
    Cost,
    KitGeometry,
    Material,
    ModuleGeometry,
    Part,
    Source,
)
from napkin2factory.core.model.requirements import (
    Requirement,
    RequirementsFile,
    Verify,
)
from napkin2factory.core.model.signoff import Signoff

__all__ = [
    "TRANSITIONS",
    "Applied",
    "Approval",
    "Assembly",
    "BoltPatternSpec",
    "Child",
    "Cost",
    "Decision",
    "DecisionsFile",
    "DocMeta",
    "Ecr",
    "Edit",
    "Exploded",
    "Frame",
    "Interface",
    "KitGeometry",
    "Manifest",
    "Material",
    "MatingFaceSpec",
    "Model",
    "ModuleGeometry",
    "Operator",
    "Parameter",
    "ParametersFile",
    "Part",
    "ProductInfo",
    "Quantity",
    "Requirement",
    "RequirementsFile",
    "Signoff",
    "Source",
    "UriField",
    "Verify",
]
