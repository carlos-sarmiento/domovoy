from __future__ import annotations

import asyncio
import importlib
import importlib.util
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from importlab import environment
from importlab.graph import ImportGraph
from watchdog.observers import Observer

from domovoy.core.configuration import get_main_config
from domovoy.core.dependency_tracking.file_watcher import ReloadPythonFileWatcher
from domovoy.core.engine.engine import AppEngine
from domovoy.core.errors import DomovoyAsyncError
from domovoy.core.logging import get_logger

from .deepreload import reload as deepreload

_logcore = get_logger(__name__)
_logcore_ignore_paths = get_logger(f"{__name__}.ignore")


@dataclass
class ModuleTrackingRecord:
    path: str
    module_name: str
    module: ModuleType | None
    imported_by: list[ModuleTrackingRecord]
    imports: list[ModuleTrackingRecord]
    is_app_file: bool = False

    def __repr__(self) -> str:
        return self.__str__()

    def __str__(self) -> str:
        return f"MTR({self.module_name})"


class DependencyTracker:
    __dependencies: dict[str, ModuleTrackingRecord]
    __current_event_loop: asyncio.AbstractEventLoop

    def __init__(self, app_path: str, app_registry: AppEngine) -> None:
        self.__dependencies = {}
        self.__app_path = app_path
        self.__app_package = Path(os.path.normpath(app_path)).name

        self.__app_registry = app_registry
        self.__current_event_loop = asyncio.get_running_loop()

    def start(self) -> None:
        _logcore.info(
            "Starting DependencyTracker for {app_path} with {app_registry}",
            app_path=self.__app_path,
            app_registry=self.__app_registry,
        )

        for root, _, files in os.walk(self.__app_path):
            for file in files:
                if file.endswith(f"{get_main_config().app_suffix}.py"):
                    path = f"{root}/{file}"
                    self.load_or_reload_filepath(path)

        _logcore.info(
            "Initializing FileWatcher for {app_path}",
            app_path=self.__app_path,
        )
        event_handler = ReloadPythonFileWatcher(self.__notify_file_changed)
        self.__observer = Observer()
        self.__observer.schedule(event_handler, self.__app_path, recursive=True)
        self.__observer.start()

    def stop(self) -> None:
        _logcore.info("Stopping Dependency Tracker")
        self.__observer.stop()
        self.__observer.join()

    async def process_file_changed(self, filepath: str, *, is_deletion: bool) -> None:
        if not is_deletion:
            _logcore.info(
                "File Changed: {filepath}",
                filepath=filepath,
            )
        else:
            _logcore.info(
                "File Deleted: {filepath}",
                filepath=filepath,
            )

        if filepath.endswith(".ignore.py"):
            _logcore.warning(
                "Ignoring {filepath} because it ends in .ignore.py",
                filepath=filepath,
            )
            return

        await self.unload_from_app_registry(filepath)

        if not is_deletion:
            self.load_or_reload_filepath(filepath)

    async def unload_from_app_registry(self, path: str) -> None:
        files_to_unload = self.__get_files_to_unload(path)

        _logcore.trace(
            "Calling App Registry to unload modules due to File change: {path} - {files_to_unload}",
            path=path,
            files_to_unload=files_to_unload,
        )
        await self.__app_registry.terminate_app_from_files(files_to_unload)

    def load_or_reload_filepath(self, path: str) -> None:
        _logcore.trace(
            "Preparing to (re)load: {path} with {app_path}",
            path=path,
            app_path=self.__app_path,
        )

        _logcore.trace("Building Import Graph for File")
        import_graph = ImportGraph.create(
            environment.Environment(
                environment.path_from_pythonpath(""),
                (sys.version_info.major, sys.version_info.minor),
            ),
            [path],
            trim=True,
        )

        _logcore.trace(
            "Detected Dependencies for {path}: {deps}",
            path=path,
            deps=import_graph.sorted_source_files(),
        )

        _logcore.trace("Filtering dependencies to tracked files only")
        for node, deps in import_graph.deps_list():
            current_module_path = import_graph.format(node)
            if not current_module_path.startswith(self.__app_path):
                _logcore_ignore_paths.trace(
                    "Ignoring path: {current_module_path}. It is outside apps director",
                    current_module_path=current_module_path,
                )
                continue

            _logcore.trace(
                "Should Import path: {current_module_path}",
                current_module_path=current_module_path,
            )

            current_mtr = self.__get_module_tracking_record(current_module_path)

            for imp in current_mtr.imports:
                _logcore.trace(
                    "Removing {imp} as being imported by {current_mtr}",
                    imp=imp,
                    current_mtr=current_mtr,
                )
                imp.imported_by.remove(current_mtr)

            current_mtr.imports = []

            final_deps: list[str] = [import_graph.format(x) for x in (deps or [])]
            final_deps = [x for x in final_deps if x.startswith(self.__app_path)]

            _logcore.trace("Identified dependencies: {final_deps}", final_deps=final_deps)

            if final_deps:
                for dep in final_deps:
                    dep_mtr = self.__get_module_tracking_record(dep)
                    dep_mtr.imported_by.append(current_mtr)
                    current_mtr.imports.append(dep_mtr)

        root = self.__get_module_tracking_record(path)

        nodes_to_load = self.__build_recursive_list_of_imports_from_node(root)
        nodes_to_reload = self.__build_recursive_list_of_importers_of_node(root)

        if _logcore.getEffectiveLevel() < logging.DEBUG:
            _logcore.trace(
                "Depdency Graph: {graph}",
                graph=self.render_dependency_graph(),
            )

        if not any(x[0].module_name.endswith(get_main_config().app_suffix) for x in nodes_to_load + nodes_to_reload):
            _logcore.warning(
                "The dependency tree does not include an _apps file. Not reloading any modules",
            )
            return

        nodes_to_load = self.__clean_and_rank(nodes_to_load)
        nodes_to_reload = self.__clean_and_rank(nodes_to_reload)

        if root.module is not None:
            nodes_to_load.remove(root)
        else:
            nodes_to_reload.remove(root)

        self.__load_nodes(nodes_to_load)
        self.__reload_nodes(nodes_to_reload)

    def render_dependency_graph(self) -> str:
        buffer = ""
        terminal_nodes = self.__get_terminal_nodes()
        for n in terminal_nodes:
            buffer += self.__render_graph(n, 0) + "\n"

        return buffer

    def __clean_and_rank(
        self,
        nodes: list[tuple[ModuleTrackingRecord, int]],
    ) -> list[ModuleTrackingRecord]:
        sorted_nodes = sorted(nodes, key=lambda x: x[1], reverse=True)

        s = []
        for n_tuple in sorted_nodes:
            if n_tuple[0] not in s:
                s.insert(0, n_tuple[0])

        return s

    def __render_graph(self, node: ModuleTrackingRecord, depth: int) -> str:
        prefix = " " * (depth * 2)

        if node.module_name.endswith(get_main_config().app_suffix):
            prefix += "* "

        buffer = prefix + node.path + "\n"

        for dependent in node.imported_by:
            buffer += self.__render_graph(dependent, depth + 1)

        return buffer

    def __get_terminal_nodes(self) -> list[ModuleTrackingRecord]:
        return [x for x in self.__dependencies.values() if not x.imports]

    def __build_recursive_list_of_imports_from_node(
        self,
        node: ModuleTrackingRecord,
        depth: int = 0,
    ) -> list[tuple[ModuleTrackingRecord, int]]:
        nodes = [(node, depth)]

        for imp in node.imports:
            importers = self.__build_recursive_list_of_imports_from_node(
                imp,
                depth=depth + 1,
            )
            _logcore.trace(
                "Dependencies of {node}: {importers}",
                node=node,
                importers=importers,
            )
            nodes = importers + nodes

        return nodes

    def __build_recursive_list_of_importers_of_node(
        self,
        node: ModuleTrackingRecord,
        depth: int = 0,
    ) -> list[tuple[ModuleTrackingRecord, int]]:
        nodes = [(node, depth)]

        for imp in node.imported_by:
            importers = self.__build_recursive_list_of_importers_of_node(
                imp,
                depth=depth + 1,
            )
            _logcore.trace(
                "Importers of {node}: {importers}",
                node=node,
                importers=importers,
            )
            nodes = nodes + importers

        return nodes

    def __load_nodes(self, nodes: list[ModuleTrackingRecord]) -> None:
        _logcore.trace("Attempting to Load Modules: {nodes}", nodes=nodes)

        try:
            importlib.invalidate_caches()
            for node in nodes:
                try:
                    if node.module is None:
                        _logcore.info(
                            "Loading Module: {module_name}",
                            module_name=node.module_name,
                        )
                        node.module = importlib.import_module(node.module_name)
                except SyntaxError as e:
                    _logcore.exception(
                        "Error while importing module {module_name} ({path})",
                        e,
                        module_name=node.module_name,
                        path=node.path,
                    )
                    return

        except Exception as e:
            _logcore.exception("Error while importing modules", e)

    def __reload_nodes(self, nodes: list[ModuleTrackingRecord]) -> None:
        _logcore.trace("Reloading Modules: {nodes}", nodes=nodes)

        try:
            importlib.invalidate_caches()
            for node in nodes:
                try:
                    if node.module is not None:
                        _logcore.info(
                            "Reloading Module: {module_name}",
                            module_name=node.module_name,
                        )

                        node.module = deepreload(
                            node.module,
                            [n.module_name for n in nodes],
                        )

                except SyntaxError as e:
                    _logcore.exception(
                        "Error while importing module {module_name} ({path})",
                        e,
                        module_name=node.module_name,
                        path=node.path,
                    )
                    return

        except Exception as e:
            _logcore.exception("Error while importing modules", e)

    def __get_module_tracking_record(self, module_fs_path: str) -> ModuleTrackingRecord:
        if module_fs_path not in self.__dependencies:
            is_app_file = False
            module_name = module_fs_path.removeprefix(self.__app_path)
            if module_name.endswith(f"{get_main_config().app_suffix}.py"):
                is_app_file = True
                module_name = (
                    module_name.removesuffix(f"{get_main_config().app_suffix}.py") + get_main_config().app_suffix
                )
            module_name = (
                self.__app_package + "." + (module_name.replace("/", ".").removeprefix(".").removesuffix(".py"))
            )

            self.__dependencies[module_fs_path] = ModuleTrackingRecord(
                path=module_fs_path,
                module_name=module_name,
                module=None,
                imported_by=[],
                imports=[],
                is_app_file=is_app_file,
            )

        return self.__dependencies[module_fs_path]

    def __get_files_to_unload(self, path: str) -> list[str]:
        _logcore.trace("Calculating files to unload for {path}", path=path)
        node: ModuleTrackingRecord = self.__get_module_tracking_record(path)
        nodes = self.__build_recursive_list_of_importers_of_node(node)
        files_to_unload = [x[0].path for x in nodes]
        _logcore.trace("Files to unload: {files}", files=files_to_unload)
        return files_to_unload

    def __notify_file_changed(self, filepath: str, *, is_deletion: bool) -> None:
        if self.__current_event_loop is None:
            raise DomovoyAsyncError(
                "Code is not running inside an AsyncIO Event Loop",
            )

        self.__current_event_loop.create_task(
            self.process_file_changed(filepath, is_deletion=is_deletion),
        )
