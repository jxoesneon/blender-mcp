"""
High-fidelity Mock Blender Python Environment for Unit Testing.
"""

from __future__ import annotations

import contextlib
import math
import os
import sys
from typing import Any, Dict, List, Optional


class MockRNAProperty:
    def __init__(self, name: str, prop_type: str = "STRING", is_readonly: bool = False, enum_items=None, default=None):
        self.name = name
        self.identifier = name
        self.type = prop_type
        self.description = f"Mock property {name}"
        self.is_readonly = is_readonly
        self.is_array = isinstance(default, (list, tuple))
        self.array_length = len(default) if self.is_array else 0
        self.enum_items = [MockEnumItem(i, i) for i in enum_items] if enum_items else []
        self.hard_min = 0.0
        self.hard_max = 100.0
        self.subtype = "NONE"


class MockEnumItem:
    def __init__(self, identifier: str, name: str, description: str = ""):
        self.identifier = identifier
        self.name = name
        self.description = description


class MockRNAFunction:
    def __init__(self, name: str, description: str = ""):
        self.identifier = name
        self.description = description
        self.parameters = []


class MockRNAPropertiesContainer(dict):
    def __iter__(self):
        return iter(self.values())


class MockRNAType:
    def __init__(self, name: str, properties: Optional[Dict[str, MockRNAProperty]] = None):
        self.name = name
        self.description = f"RNA type for {name}"
        self.base = None
        props = properties or {
            "name": MockRNAProperty("name", "STRING"),
            "location": MockRNAProperty("location", "FLOAT", default=[0.0, 0.0, 0.0]),
            "rotation_euler": MockRNAProperty("rotation_euler", "FLOAT", default=[0.0, 0.0, 0.0]),
            "scale": MockRNAProperty("scale", "FLOAT", default=[1.0, 1.0, 1.0]),
            "use_preview_images": MockRNAProperty("use_preview_images", "BOOLEAN", default=False),
        }
        self.properties = MockRNAPropertiesContainer(props)
        self.functions = [MockRNAFunction("update", "Update data")]


class MockStruct:
    def __init__(self, name: str = "Struct"):
        self.name = name
        self.rna_type = MockRNAType(name)
        self.bl_rna = self.rna_type


class MockVector(list):
    def __init__(self, items=(0.0, 0.0, 0.0)):
        super().__init__([float(x) for x in items])
    @property
    def x(self): return self[0] if len(self) > 0 else 0.0
    @property
    def y(self): return self[1] if len(self) > 1 else 0.0
    @property
    def z(self): return self[2] if len(self) > 2 else 0.0
    def to_tuple(self): return tuple(self)


class MockEuler(list):
    def __init__(self, items=(0.0, 0.0, 0.0), order="XYZ"):
        super().__init__([float(x) for x in items])
        self.order = order


class MockQuaternion:
    def __init__(self, w=1.0, x=0.0, y=0.0, z=0.0):
        self.w = float(w)
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)


class MockMatrix(list):
    def __init__(self, rows=None):
        if rows is None:
            rows = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
        super().__init__(rows)
    def inverted(self):
        return MockMatrix(self)
    def identity(self):
        self[:] = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]


class MockColor(list):
    def __init__(self, items=(1.0, 1.0, 1.0)):
        super().__init__([float(x) for x in items])


class MockVolumeData(MockStruct):
    def __init__(self, name: str):
        super().__init__(name)


class MockCollectionDict(dict):
    def __iter__(self):
        return iter(self.values())

    def new(self, name: str, *args, **kwargs):
        col_type = getattr(self, "_col_type", "")
        if "objects" in col_type:
            data = args[0] if len(args) > 0 else kwargs.get("object_data")
            item = MockObject(name, data)
        elif "materials" in col_type:
            item = MockMaterial(name)
        elif "cameras" in col_type:
            item = MockCameraData(name)
        elif "lights" in col_type:
            item = MockLightData(name, kwargs.get("type", "POINT"))
        elif "armatures" in col_type:
            item = MockArmatureData(name)
        elif "scenes" in col_type:
            item = MockScene(name)
        elif "collections" in col_type:
            item = MockSceneCollection(name)
        elif "curves" in col_type:
            item = MockCurveData(name, kwargs.get("type", "CURVE"))
        elif "node_groups" in col_type:
            item = MockNodeTree(name)
        elif "volumes" in col_type:
            item = MockVolumeData(name)
        else:
            item = MockStruct(name)

        self[name] = item
        return item

    def remove(self, item, do_unlink=True):
        key = item.name if hasattr(item, "name") else item
        if key in self:
            del self[key]

    def load(self, filepath: str, check_existing: bool = True):
        img = MockImage(os.path.basename(filepath))
        self[img.name] = img
        return img


class MockImage(MockStruct):
    def __init__(self, name: str):
        super().__init__(name)
        self.filepath = name
        self.packed_file = None
        self.colorspace_settings = MockStruct("colorspace")
        self.colorspace_settings.name = "sRGB"
    def pack(self):
        self.packed_file = b"mock_packed_data"


class MockNodeSocket:
    def __init__(self, name: str, socket_type: str = "RGBA"):
        self.name = name
        self.identifier = name
        self.type = socket_type
        self.is_linked = False
        self.default_value = [1.0, 1.0, 1.0, 1.0] if socket_type == "RGBA" else (0.0 if socket_type == "FLOAT" else [0.0, 0.0, 0.0])


class MockNodeSocketDict(list):
    def __getitem__(self, key):
        if isinstance(key, str):
            for s in self:
                if s.name == key or s.identifier == key:
                    return s
            new_s = MockNodeSocket(key)
            self.append(new_s)
            return new_s
        return super().__getitem__(key)

    def get(self, key, default=None):
        if isinstance(key, str):
            for s in self:
                if s.name == key or s.identifier == key:
                    return s
        elif isinstance(key, int) and 0 <= key < len(self):
            return self[key]
        return default

    def __contains__(self, key):
        if isinstance(key, str):
            return any(s.name == key or s.identifier == key for s in self)
        return super().__contains__(key)


class MockNode:
    def __init__(self, name: str, node_type: str):
        self.name = name
        self.type = node_type
        self.bl_idname = node_type
        self.label = name
        self.location = MockVector([0.0, 0.0, 0.0])
        self.inputs = MockNodeSocketDict([
            MockNodeSocket("Color"), MockNodeSocket("Strength", "FLOAT"), MockNodeSocket("Base Color"),
            MockNodeSocket("Surface"), MockNodeSocket("Volume"), MockNodeSocket("Image"), MockNodeSocket("Vector"),
            MockNodeSocket("Density", "FLOAT"), MockNodeSocket("Anisotropy", "FLOAT"), MockNodeSocket("Location"),
            MockNodeSocket("Rotation"), MockNodeSocket("Scale")
        ])
        self.outputs = MockNodeSocketDict([
            MockNodeSocket("Color"), MockNodeSocket("Fac", "FLOAT"), MockNodeSocket("Background"),
            MockNodeSocket("Surface"), MockNodeSocket("Volume"), MockNodeSocket("Image"), MockNodeSocket("Vector"),
            MockNodeSocket("Generated"), MockNodeSocket("UV")
        ])
        self.image = None
        self.sky_type = "NISHITA"
        self.vector_type = "POINT"
        self.mute = False


class MockNodeLink:
    def __init__(self, from_sock, to_sock, from_node, to_node):
        self.from_socket = from_sock
        self.to_socket = to_sock
        self.from_node = from_node
        self.to_node = to_node
        self.is_valid = True


class MockNodeTree:
    def __init__(self, name: str = "NodeTree"):
        self.name = name
        self.nodes = MockNodesContainer()
        self.links = MockLinksContainer(self)

    def clear(self):
        self.nodes.clear()
        self.links.clear()


class MockNodesContainer(list):
    def new(self, type: str):
        n = MockNode(f"{type}_{len(self)}", type)
        self.append(n)
        return n
    def get(self, name, default=None):
        for n in self:
            if n.name == name:
                return n
        return default
    def remove(self, node):
        if node in self:
            super().remove(node)


class MockLinksContainer(list):
    def __init__(self, tree):
        super().__init__()
        self.tree = tree
    def new(self, out_sock, in_sock):
        from_node = next((n for n in self.tree.nodes if out_sock in n.outputs), MockNode("from", "Node"))
        to_node = next((n for n in self.tree.nodes if in_sock in n.inputs), MockNode("to", "Node"))
        link = MockNodeLink(out_sock, in_sock, from_node, to_node)
        self.append(link)
        out_sock.is_linked = True
        in_sock.is_linked = True
        return link
    def remove(self, link):
        if link in self:
            super().remove(link)


class MockMaterial(MockStruct):
    def __init__(self, name: str):
        super().__init__(name)
        self.use_nodes = True
        self.node_tree = MockNodeTree(f"{name}_Tree")
    def copy(self):
        mat = MockMaterial(f"{self.name}.001")
        return mat


class MockCameraData(MockStruct):
    def __init__(self, name: str):
        super().__init__(name)
        self.type = "PERSP"
        self.lens = 50.0
        self.ortho_scale = 6.0
        self.sensor_fit = "AUTO"
        self.sensor_width = 36.0
        self.sensor_height = 24.0
        self.clip_start = 0.1
        self.clip_end = 1000.0
        self.shift_x = 0.0
        self.shift_y = 0.0
        self.dof = MockStruct("dof")
        self.dof.use_dof = False
        self.dof.focus_object = None
        self.dof.focus_distance = 10.0
        self.dof.aperture_fstop = 2.8
        self.dof.aperture_blades = 0
        self.dof.aperture_rotation = 0.0
        self.dof.aperture_ratio = 1.0


class MockLightData(MockStruct):
    def __init__(self, name: str, light_type: str = "POINT"):
        super().__init__(name)
        self.type = light_type
        self.energy = 1000.0
        self.color = MockColor([1.0, 1.0, 1.0])
        self.shadow_soft_size = 0.25
        self.shape = "SQUARE"
        self.size = 1.0
        self.size_y = 1.0
        self.spot_size = math.radians(45.0)
        self.spot_blend = 0.15
        self.show_cone = False
        self.use_shadow = True
        self.light_linking = MockStruct("light_linking")
        self.light_linking.receiver_collection = None


class MockSceneCollection(MockStruct):
    def __init__(self, name: str):
        super().__init__(name)
        self.children = MockChildCollection()
        self.objects = MockChildObjects()
        self.hide_viewport = False
        self.hide_render = False
        self.hide_select = False
        self.color_tag = "NONE"


class MockChildCollection(list):
    def link(self, col):
        if col not in self: self.append(col)
    def unlink(self, col):
        if col in self: self.remove(col)


class MockChildObjects(list):
    def link(self, obj):
        if obj not in self: self.append(obj)
    def unlink(self, obj):
        if obj in self: self.remove(obj)


class MockModifier(MockStruct):
    def __init__(self, name: str, mod_type: str):
        super().__init__(name)
        self.name = name
        self.type = mod_type
        self.show_viewport = True
        self.show_render = True
        self.levels = 1
        self.render_levels = 2
        self.object = None
        self.node_group = None
        self.operation = "DIFFERENCE"
        self.fluid_type = "DOMAIN"
        self.domain_settings = MockStruct("domain")
        self.flow_settings = MockStruct("flow")
        self.settings = MockStruct("settings")


class MockModifierCollection(list):
    def new(self, name: str, type: str):
        m = MockModifier(name, type)
        self.append(m)
        return m
    def get(self, name, default=None):
        for m in self:
            if m.name == name: return m
        return default
    def remove(self, mod):
        if mod in self: super().remove(mod)


class MockConstraint(MockStruct):
    def __init__(self, name: str, c_type: str):
        super().__init__(name)
        self.type = c_type
        self.influence = 1.0
        self.target = None
        self.subtarget = None


class MockConstraintCollection(list):
    def new(self, type: str):
        c = MockConstraint(f"{type}_{len(self)}", type)
        self.append(c)
        return c
    def get(self, name, default=None):
        for c in self:
            if c.name == name: return c
        return default
    def remove(self, c):
        if c in self: super().remove(c)


class MockMesh(MockStruct):
    def __init__(self, name: str):
        super().__init__(name)
        self.vertices = [MockStruct(f"v_{i}") for i in range(8)]
        for v in self.vertices:
            v.co = MockVector([0, 0, 0])
        self.edges = [MockStruct(f"e_{i}") for i in range(12)]
        self.polygons = [MockStruct(f"f_{i}") for i in range(6)]
        for p in self.polygons:
            p.use_smooth = False
            p.material_index = 0
        self.materials = MockMaterialList()
    def update(self):
        pass


class MockMaterialList(list):
    def append(self, mat):
        super().append(mat)


class MockCurveData(MockStruct):
    def __init__(self, name: str, c_type: str = "CURVE"):
        super().__init__(name)
        self.dimensions = "3D"
        self.bevel_depth = 0.0
        self.extrude = 0.0
        self.body = "Text"
        self.size = 1.0
        self.splines = MockSplineCollection()


class MockSplinePoint:
    def __init__(self):
        self.co = MockVector([0, 0, 0])
        self.handle_left = MockVector([0, 0, 0])
        self.handle_right = MockVector([0, 0, 0])


class MockSplinePointsList(list):
    def add(self, count):
        for _ in range(count):
            self.append(MockSplinePoint())


class MockSpline:
    def __init__(self, spline_type: str = "BEZIER"):
        self.type = spline_type
        self.use_cyclic_u = False
        self.bezier_points = MockSplinePointsList([MockSplinePoint()])
        self.points = MockSplinePointsList([MockSplinePoint()])


class MockSplineCollection(list):
    def new(self, type: str = "BEZIER"):
        s = MockSpline(type)
        self.append(s)
        return s


class MockArmatureData(MockStruct):
    def __init__(self, name: str):
        super().__init__(name)
        self.edit_bones = MockEditBoneCollection()
        self.bones = {}


class MockEditBone(MockStruct):
    def __init__(self, name: str):
        super().__init__(name)
        self.head = MockVector([0, 0, 0])
        self.tail = MockVector([0, 0, 1])
        self.roll = 0.0
        self.use_deform = True
        self.parent = None
        self.use_connect = False


class MockEditBoneCollection(dict):
    def new(self, name: str):
        b = MockEditBone(name)
        self[name] = b
        return b


class MockObject(MockStruct):
    def __init__(self, name: str, object_data: Any = None):
        super().__init__(name)
        self.data = object_data or MockMesh(f"{name}_Mesh")
        if isinstance(self.data, MockCameraData):
            self.type = "CAMERA"
        elif isinstance(self.data, MockLightData):
            self.type = "LIGHT"
        elif isinstance(self.data, MockArmatureData):
            self.type = "ARMATURE"
        elif isinstance(self.data, MockCurveData):
            self.type = "CURVE"
        else:
            self.type = "MESH"

        self.location = MockVector([0.0, 0.0, 0.0])
        self.rotation_euler = MockEuler([0.0, 0.0, 0.0])
        self.scale = MockVector([1.0, 1.0, 1.0])
        self.delta_location = MockVector([0.0, 0.0, 0.0])
        self.delta_rotation_euler = MockEuler([0.0, 0.0, 0.0])
        self.delta_scale = MockVector([1.0, 1.0, 1.0])
        self.parent = None
        self.matrix_world = MockMatrix()
        self.matrix_parent_inverse = MockMatrix()
        self.children_recursive = []
        self.users_collection = []
        self.modifiers = MockModifierCollection()
        self.constraints = MockConstraintCollection()
        self.material_slots = [MockStruct("slot_0")]
        self.particle_systems = MockParticleSystemsCollection()
        self.animation_data = MockAnimationData()
        self.mode = "OBJECT"
        self.rigid_body = None
        self.field = None
        self.pose = MockPose()

        # Register in global bpy.data if bpy is installed
        if "bpy" in sys.modules and hasattr(sys.modules["bpy"], "data"):
            sys.modules["bpy"].data.objects[name] = self

    def select_set(self, state: bool):
        pass

    def keyframe_insert(self, data_path: str, frame: float = 1.0, index: int = -1, group: str = None):
        return True

    def keyframe_delete(self, data_path: str, frame: float = 1.0, index: int = -1):
        return True

    def driver_add(self, data_path: str, index: int = -1):
        fc = MockFCurve(data_path, index)
        return fc

    def driver_remove(self, data_path: str, index: int = -1):
        return True

    def animation_data_create(self):
        return self.animation_data


class MockPose:
    def __init__(self):
        self.bones = MockPoseBoneDict()


class MockPoseBone(MockStruct):
    def __init__(self, name: str):
        super().__init__(name)
        self.location = MockVector([0, 0, 0])
        self.rotation_euler = MockEuler([0, 0, 0])
        self.scale = MockVector([1, 1, 1])
        self.constraints = MockConstraintCollection()
    def keyframe_insert(self, data_path: str, frame: float = 1.0, group: str = None):
        return True


class MockPoseBoneDict(dict):
    def get(self, name, default=None):
        if name not in self:
            self[name] = MockPoseBone(name)
        return self[name]


class MockParticleSystem(MockStruct):
    def __init__(self, name: str):
        super().__init__(name)
        self.settings = MockStruct("ParticleSettings")
        self.settings.type = "EMITTER"


class MockParticleSystemsCollection(list):
    def __init__(self):
        super().__init__()
        self.active = None
    def get(self, name, default=None):
        for ps in self:
            if ps.name == name: return ps
        return default


class MockKeyframePoint:
    def __init__(self, frame=1.0, val=0.0):
        self.co = MockVector([frame, val, 0.0])
        self.interpolation = "BEZIER"
        self.easing = "AUTO"
        self.handle_left_type = "AUTO"
        self.handle_right_type = "AUTO"
        self.handle_left = MockVector([frame - 1, val, 0.0])
        self.handle_right = MockVector([frame + 1, val, 0.0])


class MockFCurve:
    def __init__(self, data_path: str, array_index: int = 0):
        self.data_path = data_path
        self.array_index = array_index
        self.keyframe_points = [MockKeyframePoint(1.0, 0.0), MockKeyframePoint(10.0, 5.0)]
        self.driver = MockDriver()
    def update(self):
        pass


class MockDriver:
    def __init__(self):
        self.expression = "1.0"


class MockAction(MockStruct):
    def __init__(self, name: str = "Action"):
        super().__init__(name)
        self.fcurves = [MockFCurve("location", 0), MockFCurve("location", 1), MockFCurve("location", 2)]
        self.frame_range = (1.0, 250.0)


class MockNLAStrip(MockStruct):
    def __init__(self, name: str, start: int = 1):
        super().__init__(name)
        self.frame_start = float(start)
        self.frame_end = float(start + 50)


class MockNLATrack(MockStruct):
    def __init__(self, name: str = "NlaTrack"):
        super().__init__(name)
        self.strips = MockNLAStrips()


class MockNLAStrips(list):
    def new(self, name: str, start: int, action: Any):
        s = MockNLAStrip(name, start)
        self.append(s)
        return s
    def get(self, name, default=None):
        for s in self:
            if s.name == name: return s
        return default


class MockNLATracks(list):
    def new(self):
        t = MockNLATrack(f"NlaTrack_{len(self)}")
        self.append(t)
        return t
    def get(self, name, default=None):
        for t in self:
            if t.name == name: return t
        return default


class MockAnimationData:
    def __init__(self):
        self.action = MockAction("DefaultAction")
        self.nla_tracks = MockNLATracks()


class MockScene(MockStruct):
    def __init__(self, name: str = "Scene"):
        super().__init__(name)
        self.unit_settings = MockStruct("unit_settings")
        self.unit_settings.system = "METRIC"
        self.unit_settings.scale_length = 1.0
        self.unit_settings.length_unit = "METERS"
        self.unit_settings.rotation_unit = "DEGREES"
        self.gravity = MockVector([0.0, 0.0, -9.81])
        self.use_gravity = True
        self.camera = None
        self.world = MockWorld("World")
        self.collection = MockSceneCollection("MasterCollection")
        self.cursor = MockStruct("cursor")
        self.cursor.location = MockVector([0, 0, 0])
        self.cursor.rotation_euler = MockEuler([0, 0, 0])
        self.render = MockRenderSettings()
        self.display_settings = MockStruct("display")
        self.display_settings.display_device = "sRGB"
        self.view_settings = MockStruct("view")
        self.view_settings.view_transform = "AgX"
        self.view_settings.look = "None"
        self.view_settings.exposure = 0.0
        self.view_settings.gamma = 1.0
        self.use_nodes = True
        self.node_tree = MockNodeTree("CompositorTree")
        self.frame_start = 1
        self.frame_end = 250
        self.frame_current = 1
        self.cycles = MockStruct("cycles")
        self.cycles.samples = 128
        self.cycles.preview_samples = 32
        self.cycles.use_adaptive_sampling = True
        self.cycles.adaptive_threshold = 0.01

    def frame_set(self, frame: int):
        self.frame_current = frame

    def copy(self):
        return MockScene(f"{self.name}.001")


class MockRenderSettings:
    def __init__(self):
        self.engine = "CYCLES"
        self.resolution_x = 1920
        self.resolution_y = 1080
        self.resolution_percentage = 100
        self.fps = 24
        self.fps_base = 1.0
        self.filepath = "/tmp/render"
        self.image_settings = MockStruct("image_settings")
        self.image_settings.file_format = "PNG"
        self.image_settings.color_mode = "RGBA"


class MockWorld(MockStruct):
    def __init__(self, name: str = "World"):
        super().__init__(name)
        self.use_nodes = True
        self.node_tree = MockNodeTree(f"{name}_Tree")
        self.color = MockColor([0.05, 0.05, 0.05])


class MockPreferences:
    def __init__(self):
        self.system = MockStruct("system")
        self.view = MockStruct("view")
        self.filepaths = MockStruct("filepaths")
        self.keymap = MockStruct("keymap")
        self.experimental = MockStruct("experimental")


class MockData:
    def __init__(self):
        self.objects = MockCollectionDict()
        self.objects._col_type = "objects"
        self.scenes = MockCollectionDict()
        self.scenes._col_type = "scenes"
        self.materials = MockCollectionDict()
        self.materials._col_type = "materials"
        self.worlds = MockCollectionDict()
        self.worlds._col_type = "worlds"
        self.collections = MockCollectionDict()
        self.collections._col_type = "collections"
        self.cameras = MockCollectionDict()
        self.cameras._col_type = "cameras"
        self.lights = MockCollectionDict()
        self.lights._col_type = "lights"
        self.armatures = MockCollectionDict()
        self.armatures._col_type = "armatures"
        self.curves = MockCollectionDict()
        self.curves._col_type = "curves"
        self.volumes = MockCollectionDict()
        self.volumes._col_type = "volumes"
        self.node_groups = MockCollectionDict()
        self.node_groups._col_type = "node_groups"
        self.actions = MockCollectionDict()
        self.actions._col_type = "actions"
        self.images = MockCollectionDict()
        self.images._col_type = "images"
        self.workspaces = MockCollectionDict()
        self.workspaces._col_type = "workspaces"

        # Initialize Default Scene, Cube, World, Collection
        self.scenes["Scene"] = MockScene("Scene")
        self.worlds["World"] = self.scenes["Scene"].world
        self.collections["Collection"] = self.scenes["Scene"].collection
        cube = MockObject("Cube")
        self.objects["Cube"] = cube
        self.scenes["Scene"].collection.objects.link(cube)


class MockContext:
    def __init__(self):
        self._scene = MockScene("Scene")
        self.view_layer = MockViewLayer()
        self.screen = MockScreen()
        self.window = MockWindow()
        self.window_manager = MockWindowManager()
        self.preferences = MockPreferences()
        self.blend_data = None

    @property
    def scene(self):
        return self._scene
    @scene.setter
    def scene(self, val):
        self._scene = val

    @property
    def active_object(self):
        return self.view_layer.objects.active

    @property
    def selected_objects(self):
        return self.view_layer.objects.selected

    @contextlib.contextmanager
    def temp_override(self, **kwargs):
        yield


class MockViewLayer:
    def __init__(self):
        self.objects = MockActiveObjects()


class MockActiveObjects:
    def __init__(self):
        self.active = MockObject("ActiveObject")
        self.selected = [self.active]


class MockRegion(MockStruct):
    def __init__(self, r_type="WINDOW"):
        super().__init__(r_type)
        self.type = r_type


class MockArea:
    def __init__(self, area_type="VIEW_3D"):
        self.type = area_type
        self.spaces = MockSpaces()
        self.regions = [MockRegion("WINDOW")]


class MockSpace:
    def __init__(self):
        self.shading = MockStruct("shading")
        self.shading.type = "SOLID"
        self.overlay = MockStruct("overlay")
        self.overlay.show_overlays = True
        self.clip_start = 0.1
        self.clip_end = 1000.0
        self.lens = 50.0
        self.lock_object = None
        self.lock_cursor = False


class MockSpaces(list):
    def __init__(self):
        super().__init__([MockSpace()])
        self.active = self[0]


class MockScreen:
    def __init__(self):
        self.areas = [MockArea("VIEW_3D"), MockArea("PROPERTIES")]


class MockWindow:
    def __init__(self):
        self.screen = MockScreen()
        self.workspace = MockStruct("Workspace")
        self.scene = MockScene("Scene")


class MockWindowManager:
    def __init__(self):
        self.windows = [MockWindow()]


class MockOpsCategory:
    def __getattr__(self, name):
        def mock_op(*args, **kwargs):
            return {"FINISHED"}
        return mock_op


class MockOps:
    def __init__(self):
        self.mesh = MockOpsCategory()
        self.curve = MockOpsCategory()
        self.object = MockOpsCategory()
        self.preferences = MockOpsCategory()
        self.file = MockOpsCategory()
        self.render = MockOpsCategory()
        self.uv = MockOpsCategory()
        self.rigidbody = MockOpsCategory()
        self.ptcache = MockOpsCategory()
        self.ed = MockOpsCategory()
        self.wm = MockOpsCategory()
        self.import_scene = MockOpsCategory()
        self.export_scene = MockOpsCategory()
        self.import_mesh = MockOpsCategory()
        self.export_mesh = MockOpsCategory()
        self.import_anim = MockOpsCategory()
        self.export_anim = MockOpsCategory()
        self.import_curve = MockOpsCategory()
        self.blendermcp = MockOpsCategory()


class MockTypes:
    def __init__(self):
        self.Object = MockStruct("Object")
        self.Material = MockStruct("Material")
        self.Scene = MockStruct("Scene")
        self.Mesh = MockStruct("Mesh")
        self.Camera = MockStruct("Camera")
        self.Light = MockStruct("Light")
        self.Armature = MockStruct("Armature")
        self.PropertyGroup = object
        self.Operator = object
        self.Panel = object
        self.bpy_struct = MockStruct
        self.bpy_prop_array = list


class MockProps:
    @staticmethod
    def StringProperty(**kwargs): return kwargs.get("default", "")
    @staticmethod
    def IntProperty(**kwargs): return kwargs.get("default", 0)
    @staticmethod
    def FloatProperty(**kwargs): return kwargs.get("default", 0.0)
    @staticmethod
    def BoolProperty(**kwargs): return kwargs.get("default", False)
    @staticmethod
    def PointerProperty(**kwargs): return None
    @staticmethod
    def EnumProperty(**kwargs): return kwargs.get("default", "")
    @staticmethod
    def CollectionProperty(**kwargs): return []


class MockPath:
    @staticmethod
    def abspath(path: str): return os.path.abspath(path)


class MockUtils:
    @staticmethod
    def register_class(cls): pass
    @staticmethod
    def unregister_class(cls): pass


class MockAppTimers:
    def __init__(self):
        self._registered = []
    def register(self, func):
        if func not in self._registered: self._registered.append(func)
    def unregister(self, func):
        if func in self._registered: self._registered.remove(func)
    def is_registered(self, func):
        return func in self._registered


class MockApp:
    def __init__(self):
        self.timers = MockAppTimers()
        self.version = (4, 2, 0)


class MockBMeshModule:
    class types:
        class BMVert: pass
        class BMEdge: pass
        class BMFace: pass

    class ops:
        @staticmethod
        def extrude_face_region(bm, geom):
            return {"geom": [MockBMeshModule.types.BMVert()]}
        @staticmethod
        def translate(bm, vec, verts): pass
        @staticmethod
        def inset_individual(bm, faces, thickness=0.0, depth=0.0): pass
        @staticmethod
        def bevel(bm, geom, offset=0.0, segments=1, profile=0.5, affect="EDGES"): pass
        @staticmethod
        def subdivide_edges(bm, edges, cuts=1): pass
        @staticmethod
        def remove_doubles(bm, verts, dist=0.0001): pass
        @staticmethod
        def collapse(bm, edges): pass
        @staticmethod
        def recalc_face_normals(bm, faces, invert_faces=False): pass
        @staticmethod
        def delete(bm, geom, context="FACES"): pass

    def new(self):
        return MockBMeshInstance()


class MockBMeshInstance:
    def __init__(self):
        self.verts = MockBMeshSeq([MockBMeshModule.types.BMVert() for _ in range(8)])
        self.edges = MockBMeshSeq([MockBMeshModule.types.BMEdge() for _ in range(12)])
        self.faces = MockBMeshSeq([MockBMeshModule.types.BMFace() for _ in range(6)])
    def from_mesh(self, mesh): pass
    def to_mesh(self, mesh): pass
    def free(self): pass


class MockBMeshSeq(list):
    def ensure_lookup_table(self): pass


class MockMathutilsModule:
    Vector = MockVector
    Euler = MockEuler
    Quaternion = MockQuaternion
    Matrix = MockMatrix
    Color = MockColor


class MockIDPropModule:
    class types:
        class IDPropertyArray(list):
            def to_list(self): return list(self)
        class IDPropertyGroup(dict):
            def to_dict(self): return dict(self)


class MockAddonUtilsModule:
    @staticmethod
    def check(mod_name: str):
        return True, True


class MockBPY:
    def __init__(self):
        self.data = MockData()
        self.context = MockContext()
        self.ops = MockOps()
        self.types = MockTypes()
        self.props = MockProps()
        self.path = MockPath()
        self.utils = MockUtils()
        self.app = MockApp()


def install_mocks():
    mock_bpy = MockBPY()
    sys.modules["bpy"] = mock_bpy
    sys.modules["bmesh"] = MockBMeshModule()
    sys.modules["mathutils"] = MockMathutilsModule()
    sys.modules["idprop"] = MockIDPropModule()
    sys.modules["addon_utils"] = MockAddonUtilsModule()
    return mock_bpy
