import glob
import json
from pathlib import Path

import gradio as gr

from modules import script_callbacks, shared

INFO_EXTENSION = "civitai.info"
INVALID_PATH_CHARACTERS = r'<>:"/\|?*'


def on_ui_tabs():
    with gr.Blocks(analytics_enabled=False) as ui_component:
        rename_button = gr.Button(value="Rename", variant="primary")
        rename_log_md = gr.Markdown(value="Renaming takes a while, please be patient.")

        rename_button.click(rename_files, inputs=[], outputs=rename_log_md)

        return [(ui_component, "Lora Renamer", "civitai_lora_renamer")]


def rename_files() -> str:
    directory = Path(shared.cmd_opts.lora_dir)
    if not directory.exists():
        return f"Directory {directory} does not exist"

    for path in directory.rglob(f"*.{INFO_EXTENSION}"):
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)

        model_name = data.get("model", {}).get("name")
        version = data.get("name")

        if not model_name or not version:
            print(
                "CivitAI Lora Renamer: "
                f'Skipping "{path.name}" as it does not contain model name or version'
            )
            continue

        for char in INVALID_PATH_CHARACTERS:
            model_name = model_name.replace(char, "")
            version = version.replace(char, "")

        base_name = path.name[: -len(INFO_EXTENSION) - 1]
        base_path = path.parent

        for file in base_path.glob(f"{glob.escape(base_name)}.*"):
            extension = file.name[len(base_name) + 1 :]
            new_filename = f"{model_name} - {version}.{extension}"
            if file.name == new_filename:
                continue
            if Path(base_path / new_filename).exists():
                print(
                    "CivitAI Lora Renamer: "
                    f'Skipping "{file.name}" as "{new_filename}" already exists'
                )
            else:
                file.rename(base_path / new_filename)
                print(f"CivitAI Lora Renamer: {file.name} -> {new_filename}")

    print("CivitAI Lora Renamer: Done")
    return "Done"


script_callbacks.on_ui_tabs(on_ui_tabs)
