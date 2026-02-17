
with open("rosetta-api/static/js/app.js", "r") as f:
    lines = f.readlines()

# lines are 0-indexed
# want to remove lines 404-418 (1-based) -> indices 403-417
# range is exclusive at end
start_idx = 403
end_idx = 418

# Verify content before writing
content_to_remove = "".join(lines[start_idx:end_idx])
print("Removing content:")
print(content_to_remove)

if "System Limits" not in content_to_remove:
    print("ERROR: Safety check failed. Target content not found at expected lines.")
    exit(1)

new_lines = lines[:start_idx] + lines[end_idx:]

with open("rosetta-api/static/js/app.js", "w") as f:
    f.writelines(new_lines)

print("File updated successfully.")
