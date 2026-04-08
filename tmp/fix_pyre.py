import re

filepath = "src/services/data_service.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Replace variables with += 1
content = re.sub(r"(\s+)([a-zA-Z_0-9]+)\s*\+=\s*1", r"\1\2 = \2 + 1", content)
# Replace variables with += other_var
content = re.sub(r"(\s+)([a-zA-Z_0-9]+)\s*\+=\s*([a-zA-Z_0-9\['\]]+)", r"\1\2 = \2 + \3", content)
# Fix log_data indexing
content = content.replace("log_data = log_data[-500:]", "log_data = list(log_data)[-500:]")

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
print("Fixes applied.")
