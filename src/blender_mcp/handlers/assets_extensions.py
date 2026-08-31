"""
Asset marking, catalogs, and Blender 5.x extension package management handler.
"""

from __future__ import annotations

import os
from typing import Any, Dict
from blender_mcp.handlers.base import BaseHandler


class AssetsExtensionsHandler(BaseHandler):
    """Manages Blender asset libraries, catalogs, and 5.x extension packages."""

    # ------------------------------------------------------------------
    # Asset & catalog management
    # ------------------------------------------------------------------
    _ASSET_COLLECTIONS = ("objects", "materials", "collections", "node_groups", "worlds", "scenes")

    @classmethod
    def _resolve_data_collection(cls, bpy: Any, asset_type: str) -> Any:
        attr_map = {
            "OBJECT": "objects",
            "MATERIAL": "materials",
            "COLLECTION": "collections",
            "NODE_TREE": "node_groups",
            "WORLD": "worlds",
            "SCENE": "scenes",
        }
        attr = attr_map.get(asset_type.upper())
        if not attr:
            raise ValueError(f"Unknown asset_type: '{asset_type}'")
        return getattr(bpy.data, attr)

    @classmethod
    def _find_catalog_uuid(cls, bpy: Any, catalog_name: str) -> str:
        asset_cats = bpy.context.preferences.asset_libraries
        for lib in asset_cats:
            cat_path = os.path.join(lib.path, "blender_assets.cats.txt") if hasattr(lib, "path") else None
            if cat_path and os.path.exists(cat_path):
                with open(cat_path, "r") as fh:
                    for line in fh:
                        line = line.strip()
                        if line and not line.startswith("#") and ":" in line:
                            parts = line.split(":", 2)
                            if len(parts) >= 3 and parts[2].strip() == catalog_name:
                                return parts[0].strip()
        return None

    @classmethod
    def manage_assets(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        action = params["action"]
        asset_type = params.get("asset_type", "OBJECT")
        asset_name = params.get("asset_name")
        catalog_name = params.get("catalog_name")
        catalog_uuid = params.get("catalog_uuid")
        library_name = params.get("library_name")

        if action == "mark":
            if not asset_name:
                raise ValueError("asset_name is required for 'mark'.")
            coll = cls._resolve_data_collection(bpy, asset_type)
            item = coll.get(asset_name)
            if not item:
                raise ValueError(f"{asset_type} '{asset_name}' not found.")
            if not hasattr(item, "asset_mark"):
                raise ValueError(f"{asset_type} '{asset_name}' does not support asset marking.")
            item.asset_mark()
            return {"status": "success", "action": "mark", "asset_type": asset_type, "asset_name": asset_name}

        if action == "clear":
            if not asset_name:
                raise ValueError("asset_name is required for 'clear'.")
            coll = cls._resolve_data_collection(bpy, asset_type)
            item = coll.get(asset_name)
            if not item:
                raise ValueError(f"{asset_type} '{asset_name}' not found.")
            if hasattr(item, "asset_clear"):
                item.asset_clear()
            return {"status": "success", "action": "clear", "asset_type": asset_type, "asset_name": asset_name}

        if action == "list":
            assets = []
            for attr in cls._ASSET_COLLECTIONS:
                coll = getattr(bpy.data, attr, None)
                if not coll:
                    continue
                for item in coll:
                    if hasattr(item, "asset_data") and item.asset_data:
                        ad = item.asset_data
                        assets.append({
                            "name": item.name,
                            "type": attr,
                            "catalog_id": getattr(ad, "catalog_id", ""),
                            "tags": [t.name for t in getattr(ad, "tags", [])] if hasattr(ad, "tags") else [],
                            "description": getattr(ad, "description", ""),
                        })
            return {"status": "success", "action": "list", "library_name": library_name, "assets": assets}

        if action == "set_catalog":
            if not asset_name:
                raise ValueError("asset_name is required for 'set_catalog'.")
            coll = cls._resolve_data_collection(bpy, asset_type)
            item = coll.get(asset_name)
            if not item:
                raise ValueError(f"{asset_type} '{asset_name}' not found.")
            if not (hasattr(item, "asset_data") and item.asset_data):
                raise ValueError(f"{asset_type} '{asset_name}' is not marked as an asset.")
            if catalog_uuid:
                item.asset_data.catalog_id = catalog_uuid
            elif catalog_name:
                uuid = cls._find_catalog_uuid(bpy, catalog_name)
                if not uuid:
                    raise ValueError(f"Catalog '{catalog_name}' not found.")
                item.asset_data.catalog_id = uuid
            else:
                raise ValueError("Either catalog_uuid or catalog_name is required for 'set_catalog'.")
            return {"status": "success", "action": "set_catalog", "asset_type": asset_type, "asset_name": asset_name, "catalog_id": item.asset_data.catalog_id}

        if action == "create_catalog":
            if not catalog_name:
                raise ValueError("catalog_name is required for 'create_catalog'.")
            if hasattr(bpy.ops.asset, "catalog_new"):
                bpy.ops.asset.catalog_new(catalog_name=catalog_name)
            else:
                raise RuntimeError("bpy.ops.asset.catalog_new is not available in this Blender version.")
            return {"status": "success", "action": "create_catalog", "catalog_name": catalog_name}

        if action == "list_catalogs":
            catalogs = []
            asset_libs = bpy.context.preferences.asset_libraries
            for lib in asset_libs:
                lib_path = getattr(lib, "path", "") if hasattr(lib, "path") else ""
                cat_path = os.path.join(lib_path, "blender_assets.cats.txt") if lib_path else ""
                entries = []
                if cat_path and os.path.exists(cat_path):
                    with open(cat_path, "r") as fh:
                        for line in fh:
                            line = line.strip()
                            if line and not line.startswith("#") and ":" in line:
                                parts = line.split(":", 2)
                                if len(parts) >= 3:
                                    entries.append({"uuid": parts[0].strip(), "path": parts[1].strip(), "name": parts[2].strip()})
                catalogs.append({"library": lib.name, "path": lib_path, "catalogs": entries})
            return {"status": "success", "action": "list_catalogs", "libraries": catalogs}

        if action == "save_catalogs":
            if hasattr(bpy.ops.asset, "catalogs_save"):
                bpy.ops.asset.catalogs_save()
            else:
                raise RuntimeError("bpy.ops.asset.catalogs_save is not available in this Blender version.")
            return {"status": "success", "action": "save_catalogs"}

        raise ValueError(f"Unknown asset action: '{action}'")

    # ------------------------------------------------------------------
    # Extension package management (Blender 5.x)
    # ------------------------------------------------------------------
    @classmethod
    def manage_extensions(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        action = params["action"]
        package_name = params.get("package_name")
        filepath = params.get("filepath")
        repo_name = params.get("repo_name")

        ext_ops = getattr(bpy.ops, "extensions", None)

        if action == "list":
            repos = []
            prefs_repos = bpy.context.preferences.extensions.repos
            for repo in prefs_repos:
                packages = []
                if hasattr(repo, "modules"):
                    for mod in repo.modules:
                        packages.append({
                            "name": mod.name,
                            "installed": getattr(mod, "installed", False),
                            "enabled": getattr(mod, "enabled", False),
                            "version": getattr(mod, "version", ""),
                        })
                repos.append({
                    "name": repo.name,
                    "module": getattr(repo, "module", ""),
                    "enabled": getattr(repo, "enabled", False),
                    "packages": packages,
                })
            return {"status": "success", "action": "list", "repositories": repos}

        if action == "install":
            if not filepath:
                raise ValueError("filepath is required for 'install'.")
            if not os.path.exists(filepath):
                raise FileNotFoundError(f"Extension package not found at '{filepath}'")
            if not ext_ops or not hasattr(ext_ops, "package_install_files"):
                raise RuntimeError("Extension install operator not available (requires Blender 5.x).")
            kwargs = {"filepath": filepath}
            if repo_name:
                kwargs["repo"] = repo_name
            ext_ops.package_install_files(**kwargs)
            return {"status": "success", "action": "install", "filepath": filepath, "repo_name": repo_name}

        if action == "uninstall":
            if not package_name:
                raise ValueError("package_name is required for 'uninstall'.")
            if not ext_ops or not hasattr(ext_ops, "package_uninstall"):
                raise RuntimeError("Extension uninstall operator not available (requires Blender 5.x).")
            ext_ops.package_uninstall(package=package_name)
            return {"status": "success", "action": "uninstall", "package_name": package_name}

        if action == "enable":
            if not package_name:
                raise ValueError("package_name is required for 'enable'.")
            prefs_repos = bpy.context.preferences.extensions.repos
            for repo in prefs_repos:
                if hasattr(repo, "modules"):
                    mod = repo.modules.get(package_name)
                    if mod is not None:
                        mod.enabled = True
                        return {"status": "success", "action": "enable", "package_name": package_name, "repo": repo.name}
            raise ValueError(f"Extension package '{package_name}' not found in any repository.")

        if action == "disable":
            if not package_name:
                raise ValueError("package_name is required for 'disable'.")
            prefs_repos = bpy.context.preferences.extensions.repos
            for repo in prefs_repos:
                if hasattr(repo, "modules"):
                    mod = repo.modules.get(package_name)
                    if mod is not None:
                        mod.enabled = False
                        return {"status": "success", "action": "disable", "package_name": package_name, "repo": repo.name}
            raise ValueError(f"Extension package '{package_name}' not found in any repository.")

        if action == "refresh":
            if not ext_ops or not hasattr(ext_ops, "repo_refresh_all"):
                raise RuntimeError("Extension refresh operator not available (requires Blender 5.x).")
            ext_ops.repo_refresh_all()
            return {"status": "success", "action": "refresh"}

        if action == "sync":
            if not ext_ops or not hasattr(ext_ops, "repo_sync_all"):
                raise RuntimeError("Extension sync operator not available (requires Blender 5.x).")
            ext_ops.repo_sync_all()
            return {"status": "success", "action": "sync"}

        raise ValueError(f"Unknown extension action: '{action}'")
