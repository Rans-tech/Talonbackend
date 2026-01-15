#!/usr/bin/env python3
"""
Script to update app.py for 3-role system
This makes 3 changes:
1. Update get_pending_approvals() function
2. Delete assign_manager() function
3. Add export_expenses_csv() function
"""

import re

# Read the file
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

print("Starting app.py updates...")

# ============================================================================
# CHANGE 1: Update get_pending_approvals function
# ============================================================================
print("1. Updating get_pending_approvals()...")

old_function = r'''@app\.route\('/api/approvals/pending', methods=\['GET'\]\)
def get_pending_approvals\(\):
    """Get pending expense approvals for a manager or admin"""
    try:
        user_id = request\.args\.get\('user_id'\)
        organization_id = request\.args\.get\('organization_id'\)

        if not user_id or not organization_id:
            return jsonify\(\{'success': False, 'error': 'Missing required parameters'\}\), 400

        # Get user's role in organization
        member_response = db_client\.client\.table\('organization_members'\)\.select\('role, manager_id'\)\.eq\('user_id', user_id\)\.eq\('organization_id', organization_id\)\.single\(\)\.execute\(\)

        if not member_response\.data:
            return jsonify\(\{'success': False, 'error': 'User not found in organization'\}\), 404

        role = member_response\.data\['role'\]

        # Build query based on role
        if role in \['owner', 'admin'\]:
            # Admins see all pending submissions in org
            submissions_response = db_client\.client\.table\('expense_submissions'\)\.select\('\*, expenses\(\*\), profiles!submitted_by\(\*\)'\)\.eq\('organization_id', organization_id\)\.eq\('status', 'submitted'\)\.order\('submitted_at', desc=True\)\.execute\(\)
        else:
            # Managers see submissions from their direct reports
            submissions_response = db_client\.client\.table\('expense_submissions'\)\.select\('\*, expenses\(\*\), profiles!submitted_by\(\*\)'\)\.eq\('organization_id', organization_id\)\.eq\('status', 'submitted'\)\.execute\(\)

            # Filter for direct reports
            if submissions_response\.data:
                # Get team member IDs
                team_response = db_client\.client\.table\('organization_members'\)\.select\('user_id'\)\.eq\('manager_id', user_id\)\.eq\('organization_id', organization_id\)\.eq\('status', 'active'\)\.execute\(\)
                team_ids = \[member\['user_id'\] for member in team_response\.data\] if team_response\.data else \[\]

                # Filter submissions
                submissions_response\.data = \[s for s in submissions_response\.data if s\['submitted_by'\] in team_ids\]

        return jsonify\(\{
            'success': True,
            'submissions': submissions_response\.data if submissions_response\.data else \[\],
            'total': len\(submissions_response\.data\) if submissions_response\.data else 0
        \}\)

    except Exception as e:
        print\(f"Error fetching pending approvals: \{e\}"\)
        import traceback
        traceback\.print_exc\(\)
        return jsonify\(\{'success': False, 'error': str\(e\)\}\), 500'''

new_function = '''@app.route('/api/approvals/pending', methods=['GET'])
def get_pending_approvals():
    """Get pending expense approvals for an approver or admin"""
    try:
        user_id = request.args.get('user_id')
        organization_id = request.args.get('organization_id')

        if not user_id or not organization_id:
            return jsonify({'success': False, 'error': 'Missing required parameters'}), 400

        # Get user's role in organization
        member_response = db_client.client.table('organization_members')\\
            .select('role')\\
            .eq('user_id', user_id)\\
            .eq('organization_id', organization_id)\\
            .single()\\
            .execute()

        if not member_response.data:
            return jsonify({'success': False, 'error': 'User not found in organization'}), 404

        role = member_response.data['role']

        # Only admin, owner, and approver can see pending approvals
        if role not in ['owner', 'admin', 'approver']:
            return jsonify({'success': False, 'error': 'Insufficient permissions'}), 403

        # Admin/Approver see all pending submissions in org
        submissions_response = db_client.client.table('expense_submissions')\\
            .select('*, expenses(*), trips!trip_id(destination), profiles!submitted_by(id, email, full_name)')\\
            .eq('organization_id', organization_id)\\
            .eq('status', 'submitted')\\
            .order('submitted_at', desc=True)\\
            .execute()

        return jsonify({
            'success': True,
            'submissions': submissions_response.data if submissions_response.data else [],
            'total': len(submissions_response.data) if submissions_response.data else 0
        })

    except Exception as e:
        print(f"Error fetching pending approvals: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500'''

# Try to replace using regex
if re.search(old_function, content, re.DOTALL):
    content = re.sub(old_function, new_function, content, flags=re.DOTALL)
    print("✓ Updated get_pending_approvals()")
else:
    print("⚠ Could not find exact match for get_pending_approvals() - trying simpler approach")
    # Simpler approach - find by function signature and replace entire function
    lines = content.split('\n')
    new_lines = []
    i = 0
    while i < len(lines):
        if "def get_pending_approvals():" in lines[i]:
            # Skip old function until we hit the next @app.route
            new_lines.append(new_function)
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('@app.route'):
                i += 1
            continue
        new_lines.append(lines[i])
        i += 1
    content = '\n'.join(new_lines)
    print("✓ Updated get_pending_approvals() using line-by-line approach")

# ============================================================================
# CHANGE 2: Delete assign_manager function
# ============================================================================
print("2. Deleting assign_manager()...")

# Find and remove the assign_manager function
lines = content.split('\n')
new_lines = []
i = 0
skip = False
while i < len(lines):
    line = lines[i]

    # Start skipping when we find assign_manager
    if "def assign_manager(organization_id, user_id):" in line:
        skip = True
        print("  Found assign_manager at line", i+1)

    # Stop skipping when we hit the next @app.route
    if skip and line.strip().startswith('@app.route'):
        skip = False
        print("  Deleted assign_manager function")

    if not skip:
        new_lines.append(line)

    i += 1

content = '\n'.join(new_lines)
print("✓ Deleted assign_manager()")

# ============================================================================
# CHANGE 3: Add CSV export function
# ============================================================================
print("3. Adding export_expenses_csv()...")

# Find the line with "# END EXPENSE APPROVAL WORKFLOW ENDPOINTS"
csv_export_function = '''
@app.route('/api/organizations/<organization_id>/expenses/export', methods=['GET'])
def export_expenses_csv(organization_id):
    """Export expenses to CSV for an organization"""
    try:
        import csv
        import io
        from datetime import datetime

        user_id = request.args.get('user_id')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        status_filter = request.args.get('status', 'approved')
        export_format = request.args.get('format', 'csv-standard')

        if not user_id:
            return jsonify({'success': False, 'error': 'Missing user_id'}), 400

        # Check user permissions (only admin/approver can export)
        member_response = db_client.client.table('organization_members')\\
            .select('role')\\
            .eq('user_id', user_id)\\
            .eq('organization_id', organization_id)\\
            .eq('status', 'active')\\
            .single()\\
            .execute()

        if not member_response.data:
            return jsonify({'success': False, 'error': 'User not found in organization'}), 404

        role = member_response.data['role']
        if role not in ['owner', 'admin', 'approver']:
            return jsonify({'success': False, 'error': 'Insufficient permissions'}), 403

        # Build query for expense submissions
        query = db_client.client.table('expense_submissions')\\
            .select(\'\'\'
                *,
                expenses(id, amount, category, merchant, notes, date),
                trips!trip_id(destination),
                profiles!submitted_by(id, email, full_name),
                approver:profiles!approver_id(id, email, full_name)
            \'\'\')\\
            .eq('organization_id', organization_id)

        # Apply status filter
        if status_filter and status_filter != 'all':
            query = query.eq('status', status_filter)

        # Apply date filters
        if start_date:
            query = query.gte('submitted_at', start_date)
        if end_date:
            query = query.lte('submitted_at', end_date)

        # Execute query
        submissions_response = query.order('submitted_at', desc=False).execute()

        if not submissions_response.data:
            return jsonify({'success': False, 'error': 'No expenses found'}), 404

        # Generate CSV
        output = io.StringIO()

        if export_format == 'csv-quickbooks':
            # QuickBooks format
            fieldnames = ['Date', 'Vendor', 'Account', 'Amount', 'Memo', 'Customer:Job']
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()

            for submission in submissions_response.data:
                expense = submission.get('expenses', {})
                submitter = submission.get('profiles', {})
                trip = submission.get('trips', {})

                writer.writerow({
                    'Date': expense.get('date', '')[:10] if expense.get('date') else '',
                    'Vendor': expense.get('merchant', 'Unknown'),
                    'Account': expense.get('category', 'Travel'),
                    'Amount': submission.get('approved_amount', submission.get('submitted_amount', 0)),
                    'Memo': expense.get('notes', ''),
                    'Customer:Job': trip.get('destination', '')
                })
        else:
            # Standard CSV format
            fieldnames = [
                'Employee Name', 'Employee Email', 'Trip Destination',
                'Expense Date', 'Category', 'Merchant', 'Amount', 'Currency',
                'Status', 'Approved By', 'Approved Date', 'Notes', 'Submission ID'
            ]
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()

            for submission in submissions_response.data:
                expense = submission.get('expenses', {})
                submitter = submission.get('profiles', {})
                approver = submission.get('approver', {})
                trip = submission.get('trips', {})

                writer.writerow({
                    'Employee Name': submitter.get('full_name', 'Unknown'),
                    'Employee Email': submitter.get('email', ''),
                    'Trip Destination': trip.get('destination', ''),
                    'Expense Date': expense.get('date', '')[:10] if expense.get('date') else '',
                    'Category': expense.get('category', ''),
                    'Merchant': expense.get('merchant', ''),
                    'Amount': submission.get('approved_amount', submission.get('submitted_amount', 0)),
                    'Currency': 'USD',
                    'Status': submission.get('status', '').title(),
                    'Approved By': approver.get('full_name', '') if approver else '',
                    'Approved Date': submission.get('approved_at', '')[:10] if submission.get('approved_at') else '',
                    'Notes': expense.get('notes', ''),
                    'Submission ID': submission.get('id', '')
                })

        # Prepare response
        output.seek(0)
        csv_content = output.getvalue()

        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'expenses_{status_filter}_{timestamp}.csv'

        return jsonify({
            'success': True,
            'csv_content': csv_content,
            'filename': filename,
            'total_expenses': len(submissions_response.data),
            'total_amount': sum([
                float(s.get('approved_amount', s.get('submitted_amount', 0)))
                for s in submissions_response.data
            ])
        })

    except Exception as e:
        print(f"Error exporting expenses: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

'''

# Insert before the END comment
end_marker = "# ============================================================================\n# END EXPENSE APPROVAL WORKFLOW ENDPOINTS\n# ============================================================================"
if end_marker in content:
    content = content.replace(end_marker, csv_export_function + "\n" + end_marker)
    print("✓ Added export_expenses_csv() before END marker")
else:
    # Try alternate marker
    end_marker = "# END EXPENSE APPROVAL WORKFLOW ENDPOINTS"
    if end_marker in content:
        content = content.replace(end_marker, csv_export_function + "\n" + end_marker)
        print("✓ Added export_expenses_csv() before END marker")
    else:
        print("⚠ Could not find END marker - appending to end of file")
        content += "\n" + csv_export_function

# Write back
with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("\n✅ All backend updates complete!")
print("\nSummary:")
print("  1. ✓ Updated get_pending_approvals() for 3-role system")
print("  2. ✓ Deleted assign_manager() function")
print("  3. ✓ Added export_expenses_csv() endpoint")
print("\nYou can now commit and deploy to Railway!")
