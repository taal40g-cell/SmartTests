import os
import ast

# ------------------------------
# Configuration
# ------------------------------
PROJECT_DIR = r"C:\Users\User\Desktop\SmartTests"
HELPERS_FILE = os.path.join(PROJECT_DIR, "helpers.py")

# ------------------------------
# Collect all Python files
# ------------------------------
py_files = []
for root, dirs, files in os.walk(PROJECT_DIR):
    for file in files:
        if file.endswith(".py"):
            py_files.append(os.path.join(root, file))

# ------------------------------
# Parse helpers.py for function names
# ------------------------------
with open(HELPERS_FILE, "r", encoding="utf-8") as f:
    helpers_tree = ast.parse(f.read(), filename=HELPERS_FILE)

helper_funcs = [node.name for node in ast.walk(helpers_tree) if isinstance(node, ast.FunctionDef)]

# ------------------------------
# Check usage in other files
# ------------------------------
unused_funcs = []

for func in helper_funcs:
    used = False
    for py_file in py_files:
        if py_file == HELPERS_FILE:
            continue
        with open(py_file, "r", encoding="utf-8") as f:
            if func in f.read():
                used = True
                break
    if not used:
        unused_funcs.append(func)

# ------------------------------
# Report
# ------------------------------
if unused_funcs:
    print("⚠️ Functions in helpers.py that are not used anywhere else:")
    for func in unused_funcs:
        print(f"- {func}")
else:
    print("✅ All helper functions are used somewhere.")
