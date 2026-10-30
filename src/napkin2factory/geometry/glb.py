"""In-house GLB writer (decision D13).

Every part URI gets exactly one mesh and one material, both named with the URI;
every occurrence is a node named ``part://<id>#<n>`` carrying a transform and
referencing that shared mesh.  build123d's ``export_gltf`` neither names materials
nor shares meshes between instances, which is why this exists.

three.js's GLTFLoader sanitizes node names (it strips ``/``, ``:`` and ``.``), so the
URI is also written to each node's and mesh's ``extras`` (``n2f_uri``, ``n2f_node``),
which the loader exposes untouched as ``userData``.  The viewer keys on that.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Sequence

import numpy as np
import pygltflib
from numpy.typing import NDArray


@dataclass
class GlbMesh:
    """A triangulated part: one mesh and one material per part URI."""

    uri: str
    vertices: NDArray[np.float32]
    triangles: NDArray[np.uint32]
    color: tuple[float, float, float]


@dataclass
class GlbInstance:
    """One occurrence of a part in an assembly, as a named node."""

    name: str
    mesh_uri: str
    translation: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)  # quaternion xyzw
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0)
    parent: str | None = None  # name of a parent node (sub-assembly), if any


@dataclass
class GlbGroup:
    """A named grouping node (an assembly or sub-assembly) with its own transform."""

    name: str
    translation: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)
    parent: str | None = None


def _pad4(b: bytes, fill: bytes = b"\x00") -> bytes:
    return b + fill * ((4 - len(b) % 4) % 4)


def write_glb(
    meshes: Sequence[GlbMesh],
    instances: Sequence[GlbInstance],
    groups: Sequence[GlbGroup] = (),
    scene_name: str = "n2f",
) -> bytes:
    """Serialize meshes and instances into GLB bytes.

    Args:
        meshes: one per part URI.
        instances: nodes referencing meshes by URI; ``parent`` may name a group.
        groups: optional grouping nodes; a group's ``parent`` may name another group.
        scene_name: name of the single scene.
    """
    gltf = pygltflib.GLTF2(asset=pygltflib.Asset(generator="napkin2factory", version="2.0"))
    blob = bytearray()
    mesh_index: dict[str, int] = {}
    for m in meshes:
        verts = np.ascontiguousarray(m.vertices, dtype=np.float32)
        idx = np.ascontiguousarray(m.triangles.reshape(-1), dtype=np.uint32)
        normals = _vertex_normals(verts, m.triangles)
        v_off = len(blob)
        blob.extend(_pad4(verts.tobytes()))
        n_off = len(blob)
        blob.extend(_pad4(normals.tobytes()))
        i_off = len(blob)
        blob.extend(_pad4(idx.tobytes()))
        bv_base = len(gltf.bufferViews)
        gltf.bufferViews.extend(
            [
                pygltflib.BufferView(
                    buffer=0,
                    byteOffset=v_off,
                    byteLength=verts.nbytes,
                    target=pygltflib.ARRAY_BUFFER,
                ),
                pygltflib.BufferView(
                    buffer=0,
                    byteOffset=n_off,
                    byteLength=normals.nbytes,
                    target=pygltflib.ARRAY_BUFFER,
                ),
                pygltflib.BufferView(
                    buffer=0,
                    byteOffset=i_off,
                    byteLength=idx.nbytes,
                    target=pygltflib.ELEMENT_ARRAY_BUFFER,
                ),
            ]
        )
        acc_base = len(gltf.accessors)
        gltf.accessors.extend(
            [
                pygltflib.Accessor(
                    bufferView=bv_base,
                    componentType=pygltflib.FLOAT,
                    count=len(verts),
                    type=pygltflib.VEC3,
                    max=verts.max(axis=0).tolist(),
                    min=verts.min(axis=0).tolist(),
                ),
                pygltflib.Accessor(
                    bufferView=bv_base + 1,
                    componentType=pygltflib.FLOAT,
                    count=len(normals),
                    type=pygltflib.VEC3,
                ),
                pygltflib.Accessor(
                    bufferView=bv_base + 2,
                    componentType=pygltflib.UNSIGNED_INT,
                    count=len(idx),
                    type=pygltflib.SCALAR,
                ),
            ]
        )
        gltf.materials.append(
            pygltflib.Material(
                name=m.uri,
                pbrMetallicRoughness=pygltflib.PbrMetallicRoughness(
                    baseColorFactor=[*m.color, 1.0], metallicFactor=0.1, roughnessFactor=0.7
                ),
                doubleSided=True,
            )
        )
        gltf.meshes.append(
            pygltflib.Mesh(
                name=m.uri,
                extras={"n2f_uri": m.uri},
                primitives=[
                    pygltflib.Primitive(
                        attributes=pygltflib.Attributes(POSITION=acc_base, NORMAL=acc_base + 1),
                        indices=acc_base + 2,
                        material=len(gltf.materials) - 1,
                    )
                ],
            )
        )
        mesh_index[m.uri] = len(gltf.meshes) - 1

    node_index: dict[str, int] = {}
    for g in groups:
        gltf.nodes.append(
            pygltflib.Node(
                name=g.name,
                translation=list(g.translation),
                rotation=list(g.rotation),
                extras={"n2f_uri": g.name.split("#")[0], "n2f_node": g.name, "n2f_kind": "group"},
            )
        )
        node_index[g.name] = len(gltf.nodes) - 1
    for inst in instances:
        if inst.mesh_uri not in mesh_index:
            raise KeyError(f"instance {inst.name!r} references unknown mesh {inst.mesh_uri!r}")
        gltf.nodes.append(
            pygltflib.Node(
                name=inst.name,
                mesh=mesh_index[inst.mesh_uri],
                translation=list(inst.translation),
                rotation=list(inst.rotation),
                scale=list(inst.scale),
                extras={"n2f_uri": inst.mesh_uri, "n2f_node": inst.name, "n2f_kind": "instance"},
            )
        )
        node_index[inst.name] = len(gltf.nodes) - 1
    roots: list[int] = []
    for obj in [*groups, *instances]:
        i = node_index[obj.name]
        if obj.parent is None:
            roots.append(i)
        else:
            gltf.nodes[node_index[obj.parent]].children.append(i)
    gltf.scenes.append(pygltflib.Scene(name=scene_name, nodes=roots))
    gltf.scene = 0
    gltf.buffers.append(pygltflib.Buffer(byteLength=len(blob)))
    gltf.set_binary_blob(bytes(blob))
    data: bytes = b"".join(gltf.save_to_bytes())
    return data


def _vertex_normals(verts: NDArray[np.float32], tris: NDArray[np.uint32]) -> NDArray[np.float32]:
    """Area-weighted vertex normals, so flat faces stay flat after GLTF smoothing."""
    v = verts.astype(np.float64)
    t = tris.astype(np.int64)
    fn = np.cross(v[t[:, 1]] - v[t[:, 0]], v[t[:, 2]] - v[t[:, 0]])
    n = np.zeros_like(v)
    for k in range(3):
        np.add.at(n, t[:, k], fn)
    lens = np.linalg.norm(n, axis=1, keepdims=True)
    lens[lens == 0] = 1.0
    return (n / lens).astype(np.float32)


def read_glb_summary(data: bytes) -> dict[str, object]:
    """Return node names, mesh names, and material names (for tests and validate_outputs)."""
    import struct as _struct

    assert data[:4] == b"glTF"
    length = _struct.unpack_from("<I", data, 8)[0]
    assert length == len(data)
    g = pygltflib.GLTF2.load_from_bytes(data)
    return {
        "nodes": [n.name for n in g.nodes],
        "meshes": [m.name for m in g.meshes],
        "materials": [m.name for m in g.materials],
        "node_mesh": {
            n.name: (g.meshes[n.mesh].name if n.mesh is not None else None) for n in g.nodes
        },
    }


__all__ = ["GlbGroup", "GlbInstance", "GlbMesh", "read_glb_summary", "write_glb", "struct"]
