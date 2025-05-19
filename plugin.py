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
from urllib import request
from pathlib import Path
import urllib

from typing import Optional, Union, Any

import shutil

SESSION_NAME = "rustowl"
LSP_SERVER_VERSION = "0.3.3"
BASE_URL = "https://github.com/cordx56/rustowl/releases/download/v{version}/rustowl-{arch}-{platform}{ext}"

colors = {
    "lifetime": ["region.greenish", "#16c60c"],
    "imm_borrow": ["region.bluish", "#0078d7"],
    "mut_borrow": ["region.purplish", "#886ce4"],
    "move": ["region.orangish", "#f7630c"],
    "call": ["region.orangish", "#f7630c"],
    "outlive": ["region.redish", "#e81224"],
    "shared_mut": ["region.yellowish", "#ff2fff"]
}

DEBUG_LOG = False


def debug(*args, **kwargs):
    if (DEBUG_LOG):
        print("LSP-rustowl | ", end="")
        print(*args, **kwargs)

# Plugin setup:


def platform():
    if sublime.platform() == "windows":
        return "pc-windows-msvc"
    if sublime.platform() == "linux":
        return "unknown-linux-gnu"
    if sublime.platform() == "osx":
        return "apple-darwin"
    raise RuntimeError(f"platform {sublime.platform()} not found")


def arch() -> str:
    if sublime.arch() == "x32":
        raise RuntimeError("x32 isn't supported!")
    if sublime.arch() == "x64":
        return "x86_64"
    if sublime.arch() == "arm64":
        return "aarch64"


def ext() -> str:
    if sublime.platform() == "windows":
        return ".exe"
    return ""


class Rustowl(AbstractPlugin):

    @classmethod
    def name(cls) -> str:
        return SESSION_NAME

    @classmethod
    def basedir(cls) -> str:
        return os.path.join(cls.storage_path(), "LSP-rustowl")

    @classmethod
    def current_version(cls) -> Optional[str]:
        version_file = os.path.join(cls.basedir(), "version")
        if os.path.isfile(version_file):
            with open(version_file) as file:
                return file.read()
        return None

    @classmethod
    def needs_update_or_installation(cls):
        if get_setting(None, "rustowl.bin"):
            return False

        return LSP_SERVER_VERSION != cls.current_version()

    @classmethod
    def rustowl_bin(cls):
        defined = get_setting(None, "rustowl.bin")
        if defined:
            return defined

        return os.path.join(cls.basedir(), f"rustowl{ext()}")

    @classmethod
    def install_or_update(cls):
        print("LSP-rustowl | Installing rustowl binary...")

        if os.path.isdir(cls.basedir()):
            shutil.rmtree(cls.basedir())
        os.makedirs(cls.basedir(), exist_ok=True)

        file_url = BASE_URL.format(
            version=LSP_SERVER_VERSION,
            arch=arch(),
            platform=platform(),
            ext=ext()
        )

        print(f"LSP-rustowl | url: {file_url}")

        with urllib.request.urlopen(file_url) as fp:
            with open(cls.rustowl_bin(), "wb") as f:
                f.write(fp.read())

        with open(os.path.join(cls.basedir(), "version"), "w") as f:
            f.write(LSP_SERVER_VERSION)

        os.chmod(cls.rustowl_bin(), 0o744)

    @classmethod
    def additional_variables(cls):
        return {
            "rustowl_bin": cls.rustowl_bin()
        }


def plugin_loaded() -> None:
    register_plugin(Rustowl)


def plugin_unloaded() -> None:
    unregister_plugin(Rustowl)

# Plugin logic:


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

    if sublime.platform() == "windows":
        return urljoin("file:///", encoded_path.replace("|", ":"))
    else:
        return urljoin("file://", encoded_path)


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

        debug(f"sending request for {position}...")

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
        debug(f"result recived, status: {result['status']}")

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