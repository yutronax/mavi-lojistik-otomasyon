import os

file_path = 'text_gen_parser.py'
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# The redundant block starts after {rules_context} and before MESSAGE TO PARSE
start_idx = -1
end_idx = -1

for i, line in enumerate(lines):
    if '{rules_context}' in line:
        start_idx = i + 1
    if 'MESSAGE TO PARSE:' in line:
        end_idx = i
        break

if start_idx != -1 and end_idx != -1:
    # Delete everything between start_idx and end_idx
    # But keep one blank line
    del lines[start_idx:end_idx]
    lines.insert(start_idx, '\n')

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print(f"Cleaned up lines between {start_idx} and {end_idx}")
