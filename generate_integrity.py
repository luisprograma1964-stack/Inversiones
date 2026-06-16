import os, hashlib, json
import logging_config

logger = logging_config.get_logger(__name__)

root = r"C:/Users/luis/Desktop/Inversiones"
manifest = {}
for dirpath, _, filenames in os.walk(root):
    for fname in filenames:
        # skip the manifest itself to avoid recursion
        if fname == "integrity_manifest.json":
            continue
        fpath = os.path.join(dirpath, fname)
        # compute relative path using forward slashes
        rel_path = os.path.relpath(fpath, root).replace(os.sep, "/")
        with open(fpath, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        manifest[rel_path] = file_hash

output = {"files": manifest}
out_path = os.path.join(root, "integrity_manifest.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)
logger.info(f"Integrity manifest written to {out_path}")
