import glob
import json
from pathlib import Path

import gradio as gr
from send2trash import send2trash

from modules import script_callbacks, shared

INFO_EXTENSION = "civitai.info"
INVALID_PATH_CHARACTERS = r'<>:"/\|?*& '


def on_ui_tabs():
    with gr.Blocks(analytics_enabled=False) as ui_component:
        rename_button = gr.Button(value="Rename", variant="primary")
        rename_log_md = gr.Markdown(value="Renaming takes a while, please be patient.")

        rename_button.click(scan_and_rename_files, inputs=[], outputs=rename_log_md)

        return [(ui_component, "Lora Renamer", "civitai_lora_renamer")]


def on_ui_settings():
    section = ("civitai_lora_renamer", "CivitAI Lora Renamer")

    shared.opts.add_option(
        "clr_delete_duplicate_files",
        shared.OptionInfo(
            False,
            "Delete duplicate files",
            gr.Checkbox,
            {"interactive": True},
            section=section,
        ).info("Delete duplicate files with the same model id."),
    )

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


def scan_and_rename_files() -> str:
    directory = Path(shared.cmd_opts.lora_dir)
    if not directory.exists():
        return f"Directory {directory} does not exist"

    for path in directory.rglob(f"*.{INFO_EXTENSION}"):
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)

        model_name = data.get("model", {}).get("name")
        version = data.get("name")
        id = data.get("id")

        if not model_name or not version:
            print(
                f"CivitAI Lora Renamer: "
                f'Skipping "{path.name}" as it does not contain model name or version'
            )
            continue

        base_name = path.name[: -len(INFO_EXTENSION) - 1]
        base_path = path.parent

        civitai_info_path = base_path / get_new_filename(
            model_name, version, INFO_EXTENSION
        )
        use_id = False

        if civitai_info_path == path:
            continue

        if civitai_info_path.exists():
            with open(civitai_info_path, "r", encoding="utf-8") as file:
                existing_data = json.load(file)
            if existing_data.get("id") == id:
                if shared.opts.clr_delete_duplicate_files:
                    delete_duplicate_files(base_path, base_name, id, civitai_info_path)
                else:
                    print(
                        f"CivitAI Lora Renamer: "
                        f'Skipping "{path.name}" as "{civitai_info_path} '
                        f"(id: {id}) already exists"
                    )
                continue
            else:
                use_id = True

        rename_relevant_files(base_path, base_name, model_name, version, use_id, id)

    print("CivitAI Lora Renamer: Done")
    return "Done"


def delete_duplicate_files(
    base_path: Path, base_name: str, id: str, civitai_info_path: Path
):
    for file in base_path.glob(f"{glob.escape(base_name)}.*"):
        if shared.opts.clr_use_send2trash:
            send2trash(str(file))
        else:
            file.unlink()
        print(
            f"CivitAI Lora Renamer: "
            f'Deleted "{file.name}" as "{civitai_info_path}" '
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
    for char in INVALID_PATH_CHARACTERS:
        sanitized = sanitized.replace(char, "_")
    return sanitized


script_callbacks.on_ui_tabs(on_ui_tabs)
script_callbacks.on_ui_settings(on_ui_settings)
