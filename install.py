import launch


def install(package):
    if not launch.is_installed(package):
        launch.run_pip(
            f"install {package}", "requirements for SD WebUI CivitAI Lora Renamer"
        )


install("Send2Trash")
