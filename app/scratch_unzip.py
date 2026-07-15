import zipfile
import os

zip_path = "/tmp/glpi_plugin_temp/customlogin.zip"
extract_path = "/tmp/glpi_plugin_temp"

with zipfile.ZipFile(zip_path, 'r') as zip_ref:
    zip_ref.extractall(extract_path)

print("Extracted files:", os.listdir(extract_path))
