"""Run with Blender --background --python this_file.py -- --manifest scene.json.

This runner has no CadQuery dependency: it consumes CadKit's millimetre scene
manifest and creates named objects, materials, studio cameras and an editable
exploded animation. The model is never redesigned inside Blender.
"""

from __future__ import annotations
import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path
import bpy
from mathutils import Vector


def look_at(obj, target):
    obj.rotation_euler = (
        (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()
    )


def material(name, color, kind):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1)
    shader.inputs["Metallic"].default_value = 0.8 if kind == "metal" else 0
    shader.inputs["Roughness"].default_value = (
        0.27 if kind == "metal" else 0.62 if kind == "rubber" else 0.38
    )
    return mat


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--render", type=Path)
    parser.add_argument("--animation", action="store_true")
    parser.add_argument("--samples", type=int, default=64)
    parser.add_argument("--width", type=int, default=1200)
    parser.add_argument("--height", type=int, default=1200)
    parser.add_argument("--camera", choices=("Overview", "Front", "Rear"), default="Overview")
    args = parser.parse_args(
        argv if argv is not None else sys.argv[sys.argv.index("--") + 1 :]
    )
    if not (1 <= args.samples <= 4096 and 16 <= args.width <= 8192 and 16 <= args.height <= 8192):
        parser.error("Samples must be 1–4096; dimensions must be 16–8192")
    spec = json.loads(args.manifest.read_text())
    if spec.get("schema_version") != 1 or spec.get("units") != "mm":
        raise ValueError("Expected CadKit scene schema 1 in millimetres")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1
    scene.render.engine = "CYCLES"
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x = args.width
    scene.render.resolution_y = args.height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.fps = 30
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (
        0.19,
        0.22,
        0.27,
        1,
    )
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = 0.10
    try:
        scene.view_settings.view_transform = "AgX"
    except TypeError:
        scene.view_settings.view_transform = "Standard"
    scene.view_settings.exposure = -1.45
    groups = {}
    materials = {}
    objects = []
    bounds = []
    for item in spec["components"]:
        path = (args.manifest.parent / item["file"]).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        bpy.ops.wm.stl_import(filepath=str(path), global_scale=0.001)
        obj = bpy.context.object
        obj.name = item["name"]
        obj.data.name = item["name"] + " mesh"
        group = item["group"]
        if group not in groups:
            groups[group] = bpy.data.collections.new(group)
            scene.collection.children.link(groups[group])
        for collection in list(obj.users_collection):
            collection.objects.unlink(obj)
        groups[group].objects.link(obj)
        key = (tuple(item["color"]), item["material"])
        if key not in materials:
            materials[key] = material(f'{item["material"]} {len(materials)+1}', *key)
        obj.data.materials.append(materials[key])
        obj["cadkit_part"] = item.get("part") or ""
        obj["cadkit_geometry"] = item["geometry"]
        for polygon in obj.data.polygons:
            polygon.use_smooth = False
        explosion = Vector(item.get("explosion_mm", (0, 0, 0))) * 0.001
        base = obj.location.copy()
        obj["explosion_mm"] = item.get("explosion_mm", (0, 0, 0))
        if args.animation:
            for frame, amount in ((1, 0), (30, 0), (120, 1), (165, 1), (255, 0)):
                obj.location = base + amount * explosion
                obj.keyframe_insert(data_path="location", frame=frame)
        else:
            obj.location = base + (
                explosion if spec.get("exploded") else Vector((0, 0, 0))
            )
        bpy.context.view_layer.update()
        # Frame both installed and exploded poses for animation without cropping.
        for corner in obj.bound_box:
            point = obj.matrix_world @ Vector(corner)
            bounds.append(point)
            if args.animation:
                bounds.append(point + explosion)
        objects.append(obj)
    scene.frame_start = 1
    scene.frame_end = 255
    scene.frame_set(120 if spec.get("exploded") and args.animation else 1)
    bpy.context.view_layer.update()
    if not bounds:
        raise ValueError("Scene has no components")
    lo = Vector(tuple(min(p[i] for p in bounds) for i in range(3)))
    hi = Vector(tuple(max(p[i] for p in bounds) for i in range(3)))
    center = (lo + hi) / 2
    size = max(hi - lo)
    span = max(size, 0.05)
    floor_mat = material("Studio floor", (0.08, 0.11, 0.14), "rubber")
    bpy.ops.mesh.primitive_plane_add(
        size=span * 200, location=(center.x, center.y, lo.z - 0.001)
    )
    bpy.context.object.name = "Studio floor"
    bpy.context.object.data.materials.append(floor_mat)
    for name, direction, power, width in [
        ("Key", (-1, -1.5, 2.5), 85, 1.5),
        ("Fill", (2, -0.5, 1), 45, 1.8),
        ("Rim", (0, 1.6, 2), 110, 1.2),
    ]:
        data = bpy.data.lights.new(name, "AREA")
        data.energy = power * span * span
        data.shape = "DISK"
        data.size = span * width
        light = bpy.data.objects.new(name, data)
        scene.collection.objects.link(light)
        light.location = center + Vector(direction) * span
        look_at(light, center)
    for name, direction in [
        ("Overview", (1.5, 2.5, 1.1)),
        ("Rear", (-1.5, -2.5, 1)),
        ("Front", (0, 3, 0.6)),
    ]:
        data = bpy.data.cameras.new(name)
        camera = bpy.data.objects.new(name, data)
        scene.collection.objects.link(camera)
        camera.location = center + Vector(direction) * span
        look_at(camera, center)
        data.type = "ORTHO"
        data.ortho_scale = span * 1.65 * max(args.width / args.height, args.height / args.width)
        data.clip_start = 0.001
        data.clip_end = 100
        if name == args.camera:
            scene.camera = camera
    args.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
    if args.render:
        args.render.parent.mkdir(parents=True, exist_ok=True)
        if args.animation:
            ffmpeg = shutil.which("ffmpeg")
            if not ffmpeg:
                raise RuntimeError(
                    "ffmpeg is required to encode an animation; the editable .blend is saved"
                )
            frames = args.render.parent / (args.render.stem + "-frames")
            frames.mkdir(exist_ok=True)
            scene.render.filepath = str(frames.resolve() / "frame_")
            bpy.ops.render.render(animation=True)
            subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-framerate",
                    "30",
                    "-i",
                    str(frames / "frame_%04d.png"),
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    str(args.render),
                ],
                check=True,
            )
        else:
            scene.render.filepath = str(args.render.resolve())
            bpy.ops.render.render(write_still=True)
    print(
        f"Saved {args.output}: {len(objects)} components, millimetres converted to metres"
    )


if __name__ == "__main__":
    main()
