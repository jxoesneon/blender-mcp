"""
Universal Dynamic Reflection, Operator Dispatcher, Property Access, and Script Execution Handler.
"""

from __future__ import annotations

import contextlib
import io
import math
import sys
import traceback
from typing import Any, Dict, List, Optional
from blender_mcp.exceptions import BlenderExecutionError
from blender_mcp.handlers.base import BaseHandler
from blender_mcp.utils.serialization import serialize_bpy_value


class ReflectionHandler(BaseHandler):
    """Executes dynamic RNA path introspection, operator execution, and isolated scripts."""

    @classmethod
    def inspect_bpy_path(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        """Dynamically introspects any arbitrary Blender Python or RNA data path."""
        bpy = cls.get_bpy()
        path = params["path"].strip()

        eval_globals = {
            "bpy": bpy,
            "C": bpy.context,
            "D": bpy.data,
        }

        try:
            val = eval(path, eval_globals)
        except Exception as e:
            raise BlenderExecutionError(f"Failed to evaluate path '{path}': {str(e)}") from e

        type_name = type(val).__name__
        serialized_val = serialize_bpy_value(val)

        rna_props: Dict[str, Any] = {}
        if hasattr(val, "rna_type"):
            for prop in val.rna_type.properties:
                if prop.identifier != "rna_type":
                    try:
                        p_val = getattr(val, prop.identifier)
                        rna_props[prop.identifier] = {
                            "type": prop.type,
                            "description": prop.description,
                            "is_readonly": prop.is_readonly,
                            "value": serialize_bpy_value(p_val),
                        }
                    except Exception:
                        pass

        methods = []
        if hasattr(val, "rna_type"):
            methods = [f.identifier for f in val.rna_type.functions]
        else:
            methods = [attr for attr in dir(val) if callable(getattr(val, attr, None)) and not attr.startswith("_")]

        return {
            "path": path,
            "type_name": type_name,
            "value": serialized_val,
            "rna_properties": rna_props,
            "methods": methods[:50],
        }

    @classmethod
    def get_rna_schema(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        """Queries RNA struct definitions dynamically for any Blender type."""
        bpy = cls.get_bpy()
        type_name = params["rna_type_name"].strip()

        rna_struct = getattr(bpy.types, type_name, None)
        if not rna_struct or not hasattr(rna_struct, "bl_rna"):
            raise ValueError(f"Blender RNA type '{type_name}' not found in bpy.types.")

        bl_rna = rna_struct.bl_rna
        properties = {}
        for prop in bl_rna.properties:
            properties[prop.identifier] = {
                "name": prop.name,
                "type": prop.type,
                "description": prop.description,
                "is_readonly": prop.is_readonly,
                "is_array": getattr(prop, "is_array", False),
                "array_length": getattr(prop, "array_length", 0),
                "enum_items": [
                    {"identifier": item.identifier, "name": item.name, "description": item.description}
                    for item in getattr(prop, "enum_items", [])
                ],
                "min": getattr(prop, "hard_min", None),
                "max": getattr(prop, "hard_max", None),
                "subtype": getattr(prop, "subtype", "NONE"),
            }

        functions = {}
        for func in bl_rna.functions:
            functions[func.identifier] = {
                "description": func.description,
                "parameters": [
                    {"identifier": p.identifier, "type": p.type, "is_output": getattr(p, "is_output", False)}
                    for p in func.parameters
                ],
            }

        return {
            "type_name": type_name,
            "description": bl_rna.description,
            "base": bl_rna.base.name if getattr(bl_rna, "base", None) else None,
            "properties": properties,
            "functions": functions,
        }

    @classmethod
    def execute_operator(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        """Executes ANY arbitrary Blender operator with kwargs and context overrides."""
        bpy = cls.get_bpy()
        op_str = params["operator"].strip()
        exec_ctx = params.get("execution_context", "EXEC_DEFAULT")
        kwargs = params.get("kwargs", {})
        context_override = params.get("context_override", {})

        if op_str.startswith("bpy.ops."):
            op_str = op_str[len("bpy.ops."):]

        parts = op_str.split(".")
        if len(parts) != 2:
            raise ValueError(f"Invalid operator string '{op_str}'. Expected format: 'category.operator_name'")

        category, op_name = parts[0], parts[1]
        cat_obj = getattr(bpy.ops, category, None)
        if not cat_obj:
            raise AttributeError(f"Operator category 'bpy.ops.{category}' does not exist.")

        op_func = getattr(cat_obj, op_name, None)
        if not op_func:
            raise AttributeError(f"Operator 'bpy.ops.{category}.{op_name}' does not exist.")

        override_kwargs = {}
        if context_override:
            if "active_object" in context_override and isinstance(context_override["active_object"], str):
                override_kwargs["active_object"] = cls.get_object(context_override["active_object"])
            if "selected_objects" in context_override and isinstance(context_override["selected_objects"], list):
                override_kwargs["selected_objects"] = [cls.get_object(n) for n in context_override["selected_objects"]]
            if "area_type" in context_override:
                target_type = context_override["area_type"]
                for window in bpy.context.window_manager.windows:
                    screen = window.screen
                    for area in screen.areas:
                        if area.type == target_type:
                            override_kwargs["window"] = window
                            override_kwargs["screen"] = screen
                            override_kwargs["area"] = area
                            override_kwargs["region"] = next(
                                (r for r in area.regions if getattr(r, "type", "WINDOW") == context_override.get("region_type", "WINDOW")),
                                area.regions[0] if area.regions else None
                            )
                            break

        if override_kwargs and hasattr(bpy.context, "temp_override"):
            with bpy.context.temp_override(**override_kwargs):
                res = op_func(exec_ctx, **kwargs)
        else:
            res = op_func(exec_ctx, **kwargs)

        return {
            "operator": f"bpy.ops.{category}.{op_name}",
            "execution_context": exec_ctx,
            "result": list(res) if isinstance(res, set) else str(res),
        }

    @classmethod
    def get_property(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        """Gets the value of any RNA data path."""
        bpy = cls.get_bpy()
        path = params["path"].strip()
        eval_globals = {"bpy": bpy, "C": bpy.context, "D": bpy.data}

        try:
            val = eval(path, eval_globals)
            return {"path": path, "value": serialize_bpy_value(val)}
        except Exception as e:
            raise BlenderExecutionError(f"Failed to get property at path '{path}': {str(e)}") from e

    @classmethod
    def set_property(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        """Sets the value of any RNA data path with type coercion."""
        bpy = cls.get_bpy()
        path = params["path"].strip()
        new_val = params["value"]
        eval_globals = {"bpy": bpy, "C": bpy.context, "D": bpy.data}

        if "." in path or "[" in path:
            if path.endswith("]"):
                target_expr, index_expr = path.rsplit("[", 1)
                idx = eval(index_expr[:-1], eval_globals)
                target = eval(target_expr, eval_globals)
                target[idx] = new_val
            else:
                target_expr, prop_name = path.rsplit(".", 1)
                target = eval(target_expr, eval_globals)
                setattr(target, prop_name, new_val)
        else:
            raise ValueError(f"Invalid path for set_property: '{path}'")

        return {"path": path, "set_value": serialize_bpy_value(new_val)}

    @classmethod
    def eval_expression(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluates a single-line Python expression within Blender's global namespace."""
        bpy = cls.get_bpy()
        expr = params["expression"].strip()
        eval_globals = {"bpy": bpy, "C": bpy.context, "D": bpy.data, "math": math}

        try:
            res = eval(expr, eval_globals)
            return {"expression": expr, "result": serialize_bpy_value(res)}
        except Exception as e:
            raise BlenderExecutionError(f"Expression evaluation failed: {str(e)}") from e

    @classmethod
    def exec_script(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        """Executes an arbitrary multi-line Python script within Blender with stdout capture and undo rollback."""
        bpy = cls.get_bpy()
        script = params["script"]
        use_rollback = params.get("use_transaction_rollback", True)

        exec_globals = {
            "bpy": bpy,
            "C": bpy.context,
            "D": bpy.data,
            "math": math,
        }

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        if use_rollback and hasattr(bpy.ops.ed, "undo_push"):
            bpy.ops.ed.undo_push(message="MCP Exec Script")

        success = True
        err_msg = None
        tb_str = None

        with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
            try:
                exec(script, exec_globals)
            except Exception as e:
                success = False
                err_msg = str(e)
                tb_str = traceback.format_exc()
                if use_rollback and hasattr(bpy.ops.ed, "undo"):
                    bpy.ops.ed.undo()

        return {
            "success": success,
            "stdout": stdout_capture.getvalue(),
            "stderr": stderr_capture.getvalue(),
            "error": err_msg,
            "traceback": tb_str,
            "rolled_back": not success and use_rollback,
        }
