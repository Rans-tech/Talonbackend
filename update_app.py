#!/usr/bin/env python3
"""Script to update app.py for 3-role system"""

# Read the current app.py
with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and update the get_pending_approvals function
in_get_pending = False
updated_lines = []
skip_until_return = False
i = 0

while i < len(lines):
    line = lines[i]

    # Detect start of get_pending_approvals
    if 'def get_pending_approvals():' in line:
        in_get_pending = True

    # Update the manager_id select statement
    if in_get_pending and "select('role, manager_id')" in line:
        updated_lines.append(line.replace("select('role, manager_id')", "select('role')"))
        i += 1
        continue

    # Replace the role-based logic section
    if in_get_pending and "# Build query based on role" in line:
        # Skip the old logic and insert new logic
        updated_lines.append("        # Only admin, owner, and approver can see pending approvals\n")
        updated_lines.append("        if role not in ['owner', 'admin', 'approver']:\n")
        updated_lines.append("            return jsonify({'success': False, 'error': 'Insufficient permissions'}), 403\n")
        updated_lines.append("\n")
        updated_lines.append("        # Admin/Approver see all pending submissions in org\n")
        updated_lines.append("        submissions_response = db_client.client.table('expense_submissions')\\\n")
        updated_lines.append("            .select('*, expenses(*), trips!trip_id(destination), profiles!submitted_by(id, email, full_name)')\\\n")
        updated_lines.append("            .eq('organization_id', organization_id)\\\n")
        updated_lines.append("            .eq('status', 'submitted')\\\n")
        updated_lines.append("            .order('submitted_at', desc=True)\\\n")
        updated_lines.append("            .execute()\n")

        # Skip all the old if/else logic until we hit the return statement
        i += 1
        while i < len(lines) and 'return jsonify({' not in lines[i]:
            i += 1
        continue

    updated_lines.append(line)
    i += 1

# Write the updated content
with open('app.py', 'w', encoding='utf-8') as f:
    f.writelines(updated_lines)

print("✅ Updated get_pending_approvals endpoint")
print("✅ Removed manager_id dependency")
print("✅ Added 'approver' role support")
