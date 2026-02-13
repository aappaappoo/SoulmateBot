# import subprocess
# from datetime import datetime
# from pathlib import Path
#
# def screenshot_fullscreen(save_dir="./screenshots"):
#     save_dir = Path(save_dir)
#     save_dir.mkdir(parents=True, exist_ok=True)
#
#     filename = datetime.now().strftime("%Y%m%d_%H%M%S") + ".png"
#     save_path = save_dir / filename
#
#     subprocess.run(
#         ["screencapture", "-t", "jpg", "-x", str(save_path)],
#         check=True
#     )
#
#     return str(save_path)
#
# if __name__ == "__main__":
#     path = screenshot_fullscreen()
#     print("Saved screenshot to:", path)
