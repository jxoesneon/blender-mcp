# Blender MCP Integration Engine 🚀

[![CI Test Suite](https://github.com/jxoesneon/blender-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/jxoesneon/blender-mcp/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](https://github.com/jxoesneon/blender-mcp)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Blender MCP** is an enterprise-grade, comprehensive Model Context Protocol (MCP) server and addon providing full human-equivalent control over Blender 3D (3.6 LTS, 4.x, and 5.x) for autonomous AI agents (Claude Code, Cursor, Windsurf, Gemini CLI).

---

## 🌟 Key Architecture & Capabilities

1. **Dynamic Reflection & Universal Operator Dispatcher**:
   - Arbitrary Blender RNA introspection (`inspect_bpy_path`, `get_rna_schema`).
   - Universal operator execution (`bpy.ops.*`) with dynamic keyword argument and context override injection.
   - Isolated Python scripting sandbox with automatic transactional undo rollback.
2. **Scene, World, Viewport & Photometric Lighting**:
   - Multi-scene management, units, gravity vectors, and active cameras.
   - Dynamic world lighting (HDRI environments, Nishita atmospheric physical sky, volumetric scatter/absorption).
   - Real-world photometric light control (Kelvin color temperature conversion, Area/Spot/Sun/Point lights, light linking).
   - Viewport workspaces, shading modes (Wireframe, Solid, Material, Rendered), clipping planes, and 3D cursor.
3. **Objects, Hierarchy, Collections & Matrix Transforms**:
   - Robust object lifecycle (creation, duplicate, parent/unparent, parent inverse matrix calculation).
   - Scene collection hierarchies and view layer exclusion flags.
   - Transform manipulation across Global, Local, and Parent spaces with Euler/Quaternion support.
   - Bone and object constraints (Track To, IK, Copy Transforms, Damped Track).
4. **Mesh Geometry, BMesh & Geometry Nodes**:
   - Parametric primitive generation (Cube, UV/Ico Sphere, Cylinder, Cone, Torus, Grid, Monkey, etc.).
   - High-precision BMesh modeling (extrusions, insets, bevels, loop bridging, dissolutions, booleans).
   - Splines (Bezier, NURBS, Path), 3D extruded typography, OpenVDB volumes, and procedural Geometry Nodes graphs.
5. **Materials, Shader Nodes, Textures & UV Unwrapping**:
   - Principled BSDF shader network generation.
   - Shader node lifecycle and socket link manipulation.
   - Procedural texture synthesis (Voronoi, Noise, Musgrave, Wave, Brick, Checker) and image asset assignment.
   - UV unwrapping algorithms (Smart UV Project, Lightmap Pack, Cube/Sphere/Cylinder projection).
6. **Universal Modifiers Stack, Physics & Simulations**:
   - Modifiers stack configuration (Subdivision Surface, Mirror, Solidify, Bevel, Boolean, Array, etc.).
   - Physics simulation engines (Rigid Body dynamics, Cloth presets, Mantaflow Fluid/Smoke, Collision, Force Fields).
   - Particle systems (Emitter, Hair dynamics, velocity, and physics settings).
7. **Animation Timeline, F-Curves, Drivers & Armatures**:
   - Playhead, frame ranges, framerate configuration.
   - Keyframe insertions/deletions across any data path with Bezier interpolation and tangent handle adjustments.
   - Mathematical expression drivers and Non-Linear Animation (NLA) multi-track actions.
   - Armature rigging, bone hierarchy creation, and pose bone transform manipulation.
8. **Render Engines, Color Management & Compositor**:
   - Render engine setup (Cycles GPU/CPU adaptive sampling, EEVEE-Next, Workbench).
   - OCIO color management (AgX, Filmic, Standard, exposure, gamma, contrast looks).
   - View Layer pass configuration (Z-depth, Normals, Mist, Cryptomatte, AO) and post-processing Compositor node graphs.
   - High-resolution still rendering, multi-frame animation output, and instant OpenGL viewport captures with base64 streaming.
9. **Preferences, Addons & Universal I/O**:
   - User preferences inspection and modification.
   - Addon lifecycle management (check status, enable, disable, install).
   - Asset pack/unpack routines and relative/absolute path normalization.
   - Universal file formats (FBX, GLTF/GLB, OBJ, USD, Alembic, STL, PLY, BVH, DAE).

---

## 📦 Installation & Setup

### 1. Install the Blender Addon
1. Download or copy `addon.py` into your Blender addons directory or install via **Edit > Preferences > Add-ons > Install**.
2. Enable **Blender MCP Integration Engine**.
3. In the 3D Viewport sidebar (`N`-panel), navigate to **BlenderMCP** and click **Start MCP Server** (defaults to `127.0.0.1:9876`).

### 2. Configure Your AI Host

Add `blender-mcp` to your MCP configuration (e.g. `claude_desktop_config.json`, Windsurf, or Gemini CLI):

```json
{
  "mcpServers": {
    "blender": {
      "command": "python",
      "args": ["-m", "blender_mcp.server"],
      "env": {
        "BLENDER_HOST": "127.0.0.1",
        "BLENDER_PORT": "9876"
      }
    }
  }
}
```

---

## 🧪 Testing & Validation

Run the test suite with exact line-by-line coverage measurement:

```bash
python tests/run_tests_with_coverage.py
```

---

## 📄 License
MIT License. Created and maintained by [Jose Eduardo Rojas Jimenez (jxoesneon)](https://github.com/jxoesneon).
