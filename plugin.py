import sublime
import sublime_plugin

import os

from sublime_plugin import EventListener
from sublime import Region


import LSP
from LSP.plugin.core.views import position, position_to_offset, point_to_offset, offset_to_point
from LSP.plugin import AbstractPlugin
from LSP.plugin import Request
from LSP.plugin import register_plugin, unregister_plugin
from LSP.plugin.core.sessions import Session

from urllib.parse import urljoin, quote
from pathlib import Path

from typing import Optional, Union, Any

SESSION_NAME = "rustowl"

colors = {
    "lifetime": ["region.greenish", "#16c60c"],
    "imm_borrow": ["region.bluish", "#0078d7"],
    "mut_borrow": ["region.purplish", "#886ce4"],
    "move": ["region.orangish", "#f7630c"],
    "call": ["region.orangish", "#f7630c"],
    "outlive": ["region.redish", "#e81224"],
    "shared_mut": ["region.yellowish", "#ff2fff"]
}


def is_windows():
    return sublime.platform == "windows"


def get_setting(view: Optional[sublime.View], key: str, default: Optional[Union[str, bool]] = None) -> Any:
    if view:
        settings = view.settings()
        if settings.has(key):
            return settings.get(key)
    settings = sublime.load_settings('LSP-rustowl.sublime-settings').get("settings", {})
    return settings.get(key, default)


class Listener(sublime_plugin.EventListener):
    def on_selection_modified(self, view: sublime.View):
        if get_setting(view, "rustowl.hover_type") == "cursor" and len(view.sel()) > 0:
            self.request_analyze(view, position(view, view.sel()[0].a))

    def on_hover(self, view, point, hover_zone):
        if get_setting(view, "rustowl.hover_type") == "mouse":
            self.request_analyze(view, position(view, point))

    def request_analyze(self, view: sublime.View, position: int):
        session = get_session(view)
        if (session is None):
            return

        for type in colors.keys():
            view.erase_regions("rustowl-"+type)

        session.send_request(
            Request(
                "rustowl/cursor",
                {
                    "position": position,
                    "document": {
                        "uri": path_to_uri(view.file_name())
                    }
                }
            ),
            lambda x: self.on_result(view, x),
            lambda x: print(x)
        )

    def on_result(self, view: sublime.View, result):
        # Status update
        view.set_status("rustowl-status", "rustowl status: " + result["status"])

        regions = {k: [] for k in colors.keys()}
        hovers = {k: [] for k in colors.keys()}

        annotations_to_show_setting = get_setting(view, "rustowl.show_annotations")
        annotations_to_show = list(map(lambda x: x.strip(), annotations_to_show_setting.split(",")))

        for decoration in result["decorations"]:
            if (decoration["overlapped"]):
                continue

            regions[decoration["type"]].append(Region(
                position_to_offset(decoration["range"]["start"], view),
                position_to_offset(decoration["range"]["end"], view)
            ))

            if (decoration["type"] in annotations_to_show):
                hovers[decoration["type"]].append(decoration["hover_text"])

        for type in colors.keys():
            view.add_regions(
                "rustowl-" + type, 
                regions=regions[type],
                annotations=hovers[type],
                scope=colors[type][0],
                annotation_color=colors[type][1],
                flags=sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE | sublime.DRAW_SOLID_UNDERLINE
            )


class Rustowl(AbstractPlugin):

    @classmethod
    def name(cls) -> str:
        return SESSION_NAME

    @classmethod
    def rustowl_exec(cls):
        path = get_setting(None, "rustowl.bin")
        if path and os.path.isfile(path):
            return path

        cargo = os.path.expanduser("~\\AppData\\Roaming\\cargo\\bin" if is_windows() else "~/.cargo/bin")
        path = os.path.join(cargo, "rustowl" + (".exe" if is_windows else ""))
        return path

    @classmethod
    def additional_variables(cls):
        return {
            "rustowl_exec": Rustowl.rustowl_exec()
        }


def plugin_loaded() -> None:
    register_plugin(Rustowl)


def plugin_unloaded() -> None:
    unregister_plugin(Rustowl)


def _session_by_name(view, name: str):
    target = name
    listener = _get_listener(view)
    if listener:
        for sv in listener.session_views_async():
            if sv.session.config.name == target:
                return sv.session
    return None


def _get_listener(view: sublime.View):
    return LSP.plugin.core.registry.windows.listener_for_view(view)


def get_session(view) -> Session:
    return _session_by_name(view, SESSION_NAME)


def path_to_uri(file_path: str) -> str:
    path = Path(file_path).resolve().absolute().as_posix()

    encoded_path = quote(path, safe="/%")

    if is_windows():
        return urljoin("file:///", encoded_path.replace("|", ":"))
    else:
        return urljoin("file://", encoded_path)




