"""
Blender MCP Integration Engine Addon
Enterprise-grade Model Context Protocol server embedding into Blender 3.6 LTS, 4.x, and 5.x.
"""

bl_info = {
    "name": "Blender MCP Integration Engine",
    "author": "Jose Eduardo Rojas Jimenez (jxoesneon)",
    "version": (2, 0, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > BlenderMCP",
    "description": "Comprehensive Model Context Protocol integration for AI-driven 3D modeling and automation",
    "category": "Development",
}

import base64
import contextlib
import io
import json
import math
import os
import queue
import socket
import struct
import sys
import threading
import time
import traceback
from typing import Any, Dict, List, Optional, Tuple

import bpy
import idprop
import mathutils

# ---------------------------------------------------------------------------
# Global Socket Server State
# ---------------------------------------------------------------------------

_server_thread: Optional[threading.Thread] = None
_server_socket: Optional[socket.socket] = None
_is_running = False
_task_queue: queue.Queue = queue.Queue()
_server_status = "Stopped"
_connected_clients = 0

# ---------------------------------------------------------------------------
# Framing & Serialization Utilities
# ---------------------------------------------------------------------------

def encode_frame(payload: Any) -> bytes:
    data = json.dumps(payload).encode("utf-8")
    header = struct.pack(">I", len(data))
    return header + data


def read_exact(sock: socket.socket, num_bytes: int) -> bytes:
    chunks = []
    bytes_read = 0
    while bytes_read < num_bytes:
        chunk = sock.recv(min(num_bytes - bytes_read, 65536))
        if not chunk:
            raise ConnectionError("Socket closed while reading frame data.")
        chunks.append(chunk)
        bytes_read += len(chunk)
    return b"".join(chunks)


def read_frame(sock: socket.socket) -> Any:
    header = read_exact(sock, 4)
    frame_len = struct.unpack(">I", header)[0]
    payload_bytes = read_exact(sock, frame_len)
    return json.loads(payload_bytes.decode("utf-8"))


def serialize_bpy_value(val: Any, depth: int = 0, max_depth: int = 3) -> Any:
    if val is None or isinstance(val, (bool, int, str)):
        return val

    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return str(val)
        return val

    if isinstance(val, (list, tuple)):
        return [serialize_bpy_value(v, depth + 1, max_depth) for v in val]

    if isinstance(val, (set, frozenset)):
        return [serialize_bpy_value(v, depth + 1, max_depth) for v in sorted(val, key=str)]

    if isinstance(val, dict):
        return {str(k): serialize_bpy_value(v, depth + 1, max_depth) for k, v in val.items()}

    type_name = type(val).__name__
    if type_name in ("Vector", "Color") or hasattr(val, "to_tuple"):
        return list(val)

    if type_name == "Euler":
        return {"angles": list(val), "order": getattr(val, "order", "XYZ")}

    if type_name == "Quaternion":
        return {"w": float(val.w), "x": float(val.x), "y": float(val.y), "z": float(val.z)}

    if type_name == "Matrix":
        return [list(row) for row in val]

    if hasattr(val, "to_list"):
        return [serialize_bpy_value(v, depth + 1, max_depth) for v in val.to_list()]

    if hasattr(val, "to_dict"):
        return {str(k): serialize_bpy_value(v, depth + 1, max_depth) for k, v in val.to_dict().items()}

    if hasattr(val, "rna_type"):
        if depth >= max_depth:
            name = getattr(val, "name", "unnamed")
            return f"<{val.rna_type.name}: {name}>"
        res: dict[str, Any] = {"_rna_type": val.rna_type.name}
        if hasattr(val, "name"):
            res["name"] = val.name
        return res

    return str(val)


def kelvin_to_rgb(temperature_k: float) -> Tuple[float, float, float]:
    temp = max(1000.0, min(float(temperature_k), 12000.0)) / 100.0
    if temp <= 66.0:
        red = 255.0
    else:
        red = max(0.0, min(255.0, 329.698727446 * ((temp - 60.0) ** -0.1332047592)))

    if temp <= 66.0:
        green = max(0.0, min(255.0, 99.4708025861 * math.log(max(1.0, temp)) - 161.1195681661))
    else:
        green = max(0.0, min(255.0, 288.1221695283 * ((temp - 60.0) ** -0.0755148492)))

    if temp >= 66.0:
        blue = 255.0
    elif temp <= 19.0:
        blue = 0.0
    else:
        blue = max(0.0, min(255.0, 138.5177312231 * math.log(max(1.0, temp - 10.0)) - 305.0447927307))

    def to_linear(c: float) -> float:
        c_norm = c / 255.0
        if c_norm <= 0.04045:
            return max(0.0, min(1.0, c_norm / 12.92))
        return max(0.0, min(1.0, ((c_norm + 0.055) / 1.055) ** 2.4))

    return (to_linear(red), to_linear(green), to_linear(blue))


# ---------------------------------------------------------------------------
# Addon Handlers Registry Import & Integration
# ---------------------------------------------------------------------------

try:
    from blender_mcp.handlers import dispatch_blender_command
except ImportError:
    # If imported directly inside Blender without blender_mcp in pythonpath
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
    try:
        from blender_mcp.handlers import dispatch_blender_command
    except Exception:
        def dispatch_blender_command(action: str, params: Dict[str, Any]) -> Dict[str, Any]:
            return {"success": False, "error": "blender_mcp package not found in addon path"}


# ---------------------------------------------------------------------------
# Background Socket Server & Main Thread Timer Loop
# ---------------------------------------------------------------------------

def _main_thread_timer():
    """Processes pending client tasks on Blender's main UI thread."""
    global _is_running
    if not _is_running:
        return None

    while not _task_queue.empty():
        try:
            task = _task_queue.get_nowait()
            action = task["action"]
            params = task["params"]
            response_channel = task["response_channel"]

            # Execute command on main thread
            result = dispatch_blender_command(action, params)
            response_channel.put(result)
        except queue.Empty:
            break
        except Exception as e:
            if "response_channel" in locals():
                response_channel.put({
                    "success": False,
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                })

    return 0.01  # Poll every 10ms


def _client_handler(conn: socket.socket, addr: Tuple[str, int]):
    """Handles an individual client connection."""
    global _connected_clients
    _connected_clients += 1
    try:
        while _is_running:
            try:
                msg = read_frame(conn)
            except (ConnectionError, struct.error):
                break

            action = msg.get("action", "unknown")
            params = msg.get("params", {})

            # Submit task to main thread queue
            resp_q: queue.Queue = queue.Queue()
            _task_queue.put({
                "action": action,
                "params": params,
                "response_channel": resp_q,
            })

            # Wait for main thread execution
            try:
                resp = resp_q.get(timeout=60.0)
            except queue.Empty:
                resp = {"success": False, "error": "Task execution timed out on Blender main thread."}

            conn.sendall(encode_frame(resp))
    finally:
        conn.close()
        _connected_clients = max(0, _connected_clients - 1)


def _socket_listener_thread(host: str, port: int):
    """Background listener accepting TCP socket connections."""
    global _server_socket, _is_running, _server_status
    _server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        _server_socket.bind((host, port))
        _server_socket.listen(5)
        _server_status = f"Running on {host}:{port}"
        print(f"[BlenderMCP] Socket server started on {host}:{port}")

        while _is_running:
            try:
                conn, addr = _server_socket.accept()
                t = threading.Thread(target=_client_handler, args=(conn, addr), daemon=True)
                t.start()
            except socket.error:
                break
    except Exception as e:
        _server_status = f"Error: {str(e)}"
        print(f"[BlenderMCP] Server error: {e}")
    finally:
        if _server_socket:
            _server_socket.close()
        _server_status = "Stopped"


def start_mcp_server(host: str = "127.0.0.1", port: int = 9876):
    global _server_thread, _is_running
    if _is_running:
        return

    _is_running = True
    _server_thread = threading.Thread(target=_socket_listener_thread, args=(host, port), daemon=True)
    _server_thread.start()

    if not bpy.app.timers.is_registered(_main_thread_timer):
        bpy.app.timers.register(_main_thread_timer)


def stop_mcp_server():
    global _server_socket, _is_running, _server_status
    _is_running = False
    if _server_socket:
        try:
            _server_socket.close()
        except Exception:
            pass
    if bpy.app.timers.is_registered(_main_thread_timer):
        bpy.app.timers.unregister(_main_thread_timer)
    _server_status = "Stopped"
    print("[BlenderMCP] Socket server stopped.")


# ---------------------------------------------------------------------------
# UI Panels & Operator Properties
# ---------------------------------------------------------------------------

class BLENDERMCP_PG_properties(bpy.types.PropertyGroup):
    host: bpy.props.StringProperty(
        name="Host",
        default="127.0.0.1",
        description="IP address to bind the MCP server socket"
    )
    port: bpy.props.IntProperty(
        name="Port",
        default=9876,
        min=1024,
        max=65535,
        description="Port for MCP TCP socket"
    )
    auto_start: bpy.props.BoolProperty(
        name="Auto-start on launch",
        default=True,
        description="Automatically start the MCP server when Blender launches or a new file is loaded"
    )


class BLENDERMCP_OT_start_server(bpy.types.Operator):
    bl_idname = "blendermcp.start_server"
    bl_label = "Start MCP Server"
    bl_description = "Starts the background Model Context Protocol socket server"

    def execute(self, context):
        props = context.scene.blendermcp_props
        start_mcp_server(host=props.host, port=props.port)
        self.report({'INFO'}, f"Blender MCP Server started on {props.host}:{props.port}")
        return {'FINISHED'}


class BLENDERMCP_OT_stop_server(bpy.types.Operator):
    bl_idname = "blendermcp.stop_server"
    bl_label = "Stop MCP Server"
    bl_description = "Stops the background Model Context Protocol socket server"

    def execute(self, context):
        stop_mcp_server()
        self.report({'INFO'}, "Blender MCP Server stopped")
        return {'FINISHED'}


class VIEW3D_PT_blender_mcp_panel(bpy.types.Panel):
    bl_label = "Blender MCP Engine"
    bl_idname = "VIEW3D_PT_blender_mcp"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BlenderMCP'

    def draw(self, context):
        layout = self.layout
        props = context.scene.blendermcp_props

        box = layout.box()
        box.label(text="Server Configuration", icon='PREFERENCES')
        box.prop(props, "host")
        box.prop(props, "port")
        box.prop(props, "auto_start")

        row = layout.row(align=True)
        if not _is_running:
            row.operator("blendermcp.start_server", icon='PLAY', text="Start MCP Server")
        else:
            row.operator("blendermcp.stop_server", icon='PAUSE', text="Stop MCP Server")

        status_box = layout.box()
        status_box.label(text=f"Status: {_server_status}", icon='INFO')
        if _is_running:
            status_box.label(text=f"Active Clients: {_connected_clients}", icon='LINKED')


# ---------------------------------------------------------------------------
# Addon Registration Lifecycle
# ---------------------------------------------------------------------------

classes = (
    BLENDERMCP_PG_properties,
    BLENDERMCP_OT_start_server,
    BLENDERMCP_OT_stop_server,
    VIEW3D_PT_blender_mcp_panel,
)


# ---------------------------------------------------------------------------
# Persistent load handler — restarts the server when a new .blend is loaded
# ---------------------------------------------------------------------------

@bpy.app.handlers.persistent
def _on_load_post(dummy=None):
    """Restart the MCP server after a new .blend file is loaded.

    This handles the case where Blender is launched with a file argument
    (e.g. ``blender my_scene.blend``) — the file loads *after* register()
    runs, so any server started in register() would operate on the default
    scene.  By restarting here we ensure the server is bound to the actual
    scene data.
    """
    # Check the auto_start preference on the current scene
    props = getattr(bpy.context.scene, "blendermcp_props", None)
    auto = getattr(props, "auto_start", True) if props else True
    if not auto:
        return
    # If already running, restart to pick up the new file
    if _is_running:
        stop_mcp_server()
    host = os.environ.get("BLENDER_HOST", "127.0.0.1")
    port = int(os.environ.get("BLENDER_PORT", "9876"))
    # Defer slightly so the depsgraph is fully evaluated
    def _restart():
        start_mcp_server(host=host, port=port)
        print(f"[BlenderMCP] Server (re)started on {host}:{port} after file load")
        return None
    bpy.app.timers.register(_restart, first_interval=0.1)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.blendermcp_props = bpy.props.PointerProperty(type=BLENDERMCP_PG_properties)

    # Register the persistent load_post handler so the server restarts
    # whenever a new .blend file is loaded (including the initial file
    # passed on the command line).
    if _on_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load_post)

    # Auto-start socket server.
    # Priority:
    #   1. BLENDER_MCP_AUTOSTART env var (used by the launcher wrapper)
    #   2. auto_start preference (default True)
    env_autostart = os.environ.get("BLENDER_MCP_AUTOSTART", "").lower() in ("1", "true", "yes")
    if env_autostart:
        host = os.environ.get("BLENDER_HOST", "127.0.0.1")
        port = int(os.environ.get("BLENDER_PORT", "9876"))
        def _autostart():
            start_mcp_server(host=host, port=port)
            print(f"[BlenderMCP] Auto-started server on {host}:{port}")
            return None
        bpy.app.timers.register(_autostart, first_interval=0.5)
    else:
        # Default: auto-start via a deferred timer.
        # The load_post handler will also restart it after the initial
        # file loads, but starting here covers the case where Blender
        # opens with the default startup file (no file argument).
        def _autostart_default():
            props = getattr(bpy.context.scene, "blendermcp_props", None)
            auto = getattr(props, "auto_start", True) if props else True
            if auto and not _is_running:
                host = os.environ.get("BLENDER_HOST", "127.0.0.1")
                port = int(os.environ.get("BLENDER_PORT", "9876"))
                start_mcp_server(host=host, port=port)
                print(f"[BlenderMCP] Auto-started server on {host}:{port}")
            return None
        bpy.app.timers.register(_autostart_default, first_interval=1.0)


def unregister():
    stop_mcp_server()
    # Remove the persistent load_post handler
    if _on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load_post)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.blendermcp_props


if __name__ == "__main__":
    register()
