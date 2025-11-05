import sys

with open('app.py', 'r') as f:
    lines = f.readlines()

# Find the function and add OPTIONS check
for i, line in enumerate(lines):
    if 'def generate_trip_tasks(trip_id):' in line:
        # Insert OPTIONS check after the docstring
        docstring_end = i + 2
        lines.insert(docstring_end, '    # Handle OPTIONS preflight\n')
        lines.insert(docstring_end + 1, "    if request.method == 'OPTIONS':\n")
        lines.insert(docstring_end + 2, "        return '', 200\n")
        lines.insert(docstring_end + 3, '\n')
        break

with open('app.py', 'w') as f:
    f.writelines(lines)

print("Fixed CORS handling")
