import json
from os import getlogin

def change_fz(size):
    path = f"C:\\Users\\{getlogin()}\\AppData\\Local\\Packages\\Microsoft.WindowsTerminal_8wekyb3d8bbwe\\LocalState\\settings.json"
    try:
        with open(path, 'r') as fr:
            data = json.load(fr)
        with open(path, 'w') as fw:
            data["profiles"]["defaults"]["font"]["size"] = size
            json.dump(data, fw, indent=4)
    except FileNotFoundError:
        raise FileNotFoundError("Error: The settings file was not found.")
