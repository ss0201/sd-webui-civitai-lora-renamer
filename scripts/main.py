import glob
import json
from pathlib import Path
from datetime import datetime
import re

import gradio as gr
from send2trash import send2trash

from modules import script_callbacks, shared

INFO_EXTENSION = "civitai.info"
INVALID_PATH_CHARACTERS = r'<>:"/\|?*& '
ESCAPED_INVALID_PATH_CHARACTERS = re.escape(INVALID_PATH_CHARACTERS)


def on_ui_tabs():
    with gr.Blocks(analytics_enabled=False) as ui_component:
        rename_button = gr.Button(value="Rename", variant="primary")
        rename_log_md = gr.Markdown(value="Renaming takes a while, please be patient.")

        rename_button.click(scan_and_rename_files, inputs=[], outputs=rename_log_md)

        return [(ui_component, "Lora Renamer", "civitai_lora_renamer")]


def on_ui_settings():
    section = ("civitai_lora_renamer", "CivitAI Lora Renamer")

    shared.opts.add_option(
        "clr_use_send2trash",
        shared.OptionInfo(
            True,
            "Use send2trash",
            gr.Checkbox,
            {"interactive": True},
            section=section,
        ).info("Use send2trash instead of permanently deleting files."),
    )


class FileEntry:
    def __init__(
        self,
        updated_at: datetime,
        model_name: str,
        version: str,
        base_name: str,
        info_path: Path,
    ):
        self.updated_at = updated_at
        self.model_name = model_name
        self.version = version
        self.base_name = base_name
        self.info_path = info_path

    @property
    def base_path(self) -> Path:
        return self.info_path.parent


def scan_and_rename_files() -> str:
    directory = Path(shared.cmd_opts.lora_dir)
    if not directory.exists():
        return f"Directory {directory} does not exist"

    id_to_file_entries: dict[str, list[FileEntry]] = {}
    for info_path in directory.rglob(f"*.{INFO_EXTENSION}"):
        base_name = info_path.name[: -len(INFO_EXTENSION) - 1]

        try:
            with open(info_path, "r", encoding="utf-8") as file:
                data = json.load(file)
        except (json.JSONDecodeError, UnicodeDecodeError):
            print(
                f'CivitAI Lora Renamer: Skipping "{info_path.name}" as it is not a valid JSON file'
            )
            continue

        model_name = data.get("model", {}).get("name")
        version = data.get("name")
        id = data.get("id")
        updated_at_str = data.get("updatedAt")
        if updated_at_str:
            try:
                updated_at = datetime.fromisoformat(
                    updated_at_str.replace("Z", "+00:00")
                )
            except ValueError:
                updated_at = datetime.min
        else:
            updated_at = datetime.min

        if not model_name or not version or not id:
            print(
                f'CivitAI Lora Renamer: Skipping "{info_path.name}" as it lacks model name, version, or id'
            )
            continue

        file_entry = FileEntry(
            updated_at=updated_at,
            model_name=model_name,
            version=version,
            base_name=base_name,
            info_path=info_path,
        )

        id_to_file_entries.setdefault(id, []).append(file_entry)

    for id, entries in id_to_file_entries.items():
        if len(entries) > 1:
            entries_sorted = sorted(entries, key=lambda x: x.updated_at, reverse=True)
            keep_entry = entries_sorted[0]
            duplicate_entries = entries_sorted[1:]

            for entry in duplicate_entries:
                delete_duplicate_files(
                    entry.base_path, entry.base_name, id, keep_entry.info_path
                )

            entries = [keep_entry]

        for entry in entries:
            new_info_filename = get_new_filename(
                entry.model_name, entry.version, INFO_EXTENSION
            )
            new_info_path = entry.base_path / new_info_filename

            if new_info_path != entry.info_path:
                use_id = new_info_path.exists()
                rename_relevant_files(
                    entry.base_path,
                    entry.base_name,
                    entry.model_name,
                    entry.version,
                    use_id,
                    id,
                )

    print("CivitAI Lora Renamer: Done")
    return "Done"


def delete_duplicate_files(
    base_path: Path, base_name: str, id: str, other_civitai_info_path: Path
):
    for file in base_path.glob(f"{glob.escape(base_name)}.*"):
        if shared.opts.clr_use_send2trash:
            send2trash(str(file))
        else:
            file.unlink()
        print(
            f"CivitAI Lora Renamer: "
            f'Deleted "{file.name}" as "{other_civitai_info_path}" '
            f"(id: {id}) already exists"
        )


def rename_relevant_files(
    base_path: Path,
    base_name: str,
    model_name: str,
    version: str,
    use_id: bool,
    id: str,
):
    for file in base_path.glob(f"{glob.escape(base_name)}.*"):
        extension = file.name[len(base_name) + 1 :]
        new_filename = get_new_filename(
            model_name, version, extension, id if use_id else ""
        )
        new_filepath = base_path / new_filename
        if file.name == new_filename:
            continue
        if new_filepath.exists():
            print(
                f"CivitAI Lora Renamer: "
                f'Skipping "{file.name}" as "{new_filename}" already exists'
            )
        else:
            file.rename(new_filepath)
            print(f"CivitAI Lora Renamer: {file.name} -> {new_filename}")


def get_new_filename(
    model_name: str, version: str, extension: str, id: str = ""
) -> str:
    sanitized_model_name = sanitize_string(model_name)
    sanitized_version = sanitize_string(version)
    id_part = f"_{id}" if id else ""
    return f"{sanitized_model_name}{id_part}__{sanitized_version}.{extension}"


def sanitize_string(value: str) -> str:
    sanitized = value.strip()
    sanitized = re.sub(f"[{ESCAPED_INVALID_PATH_CHARACTERS}]+", "_", sanitized)
    max_length = 255
    return sanitized[:max_length]


script_callbacks.on_ui_tabs(on_ui_tabs)
script_callbacks.on_ui_settings(on_ui_settings)
