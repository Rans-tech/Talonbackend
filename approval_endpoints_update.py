"""
APPROVAL ENDPOINTS UPDATE FOR 3-ROLE SYSTEM
============================================
These are the updated/new endpoints to replace the existing approval endpoints in app.py

CHANGES:
1. Updated get_pending_approvals() - Works with admin/approver/member (no manager hierarchy)
2. Removed assign_manager() - No longer needed
3. Added export_expenses_csv() - NEW CSV export functionality

TO APPLY:
Replace the corresponding functions in app.py with these updated versions
"""

# ============================================================================
# UPDATED: Get Pending Approvals (Simplified for 3 roles)
# ============================================================================
@app.route('/api/approvals/pending', methods=['GET'])
def get_pending_approvals():
    """Get pending expense approvals for an approver or admin"""
    try:
        user_id = request.args.get('user_id')
        organization_id = request.args.get('organization_id')

        if not user_id or not organization_id:
            return jsonify({'success': False, 'error': 'Missing required parameters'}), 400

        # Get user's role in organization
        member_response = db_client.client.table('organization_members')\
            .select('role')\
            .eq('user_id', user_id)\
            .eq('organization_id', organization_id)\
            .single()\
            .execute()

        if not member_response.data:
            return jsonify({'success': False, 'error': 'User not found in organization'}), 404

        role = member_response.data['role']

        # Only admin, owner, and approver can see pending approvals
        if role not in ['owner', 'admin', 'approver']:
            return jsonify({'success': False, 'error': 'Insufficient permissions'}), 403

        # Admin/Approver see all pending submissions in org
        submissions_response = db_client.client.table('expense_submissions')\
            .select('*, expenses(*), trips!trip_id(destination), profiles!submitted_by(id, email, full_name)')\
            .eq('organization_id', organization_id)\
            .eq('status', 'submitted')\
            .order('submitted_at', desc=True)\
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
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# REMOVED: Assign Manager Endpoint
# ============================================================================
# The endpoint at /api/organizations/<organization_id>/members/<user_id>/manager
# should be DELETED from app.py as we no longer use manager hierarchy


# ============================================================================
# NEW: CSV Export Endpoint
# ============================================================================
@app.route('/api/organizations/<organization_id>/expenses/export', methods=['GET'])
def export_expenses_csv(organization_id):
    """
    Export expenses to CSV for an organization
    Query params:
        - user_id: Required - User requesting the export
        - start_date: Optional - Filter by date range (YYYY-MM-DD)
        - end_date: Optional - Filter by date range (YYYY-MM-DD)
        - status: Optional - Filter by status (approved, submitted, rejected, all)
        - format: Optional - Export format (csv-standard, csv-quickbooks, xlsx)
    """
    try:
        import csv
        import io
        from datetime import datetime

        user_id = request.args.get('user_id')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        status_filter = request.args.get('status', 'approved')  # Default to approved only
        export_format = request.args.get('format', 'csv-standard')

        if not user_id:
            return jsonify({'success': False, 'error': 'Missing user_id'}), 400

        # Check user permissions (only admin/approver can export)
        member_response = db_client.client.table('organization_members')\
            .select('role')\
            .eq('user_id', user_id)\
            .eq('organization_id', organization_id)\
            .eq('status', 'active')\
            .single()\
            .execute()

        if not member_response.data:
            return jsonify({'success': False, 'error': 'User not found in organization'}), 404

        role = member_response.data['role']
        if role not in ['owner', 'admin', 'approver']:
            return jsonify({'success': False, 'error': 'Insufficient permissions'}), 403

        # Build query for expense submissions
        query = db_client.client.table('expense_submissions')\
            .select('''
                *,
                expenses(id, amount, category, merchant, notes, date),
                trips!trip_id(destination),
                profiles!submitted_by(id, email, full_name),
                approver:profiles!approver_id(id, email, full_name)
            ''')\
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
            fieldnames = [
                'Date', 'Vendor', 'Account', 'Amount', 'Memo', 'Customer:Job'
            ]
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
                    'Currency': 'USD',  # TODO: Make this dynamic
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


# ============================================================================
# INTEGRATION INSTRUCTIONS
# ============================================================================
"""
TO INTEGRATE INTO app.py:

1. Replace the get_pending_approvals() function (around line 1153-1198)
   with the updated version above

2. Delete the assign_manager() function (around line 1229-1258)
   It's no longer needed with the 3-role system

3. Add the new export_expenses_csv() function anywhere in the
   EXPENSE APPROVAL WORKFLOW ENDPOINTS section (after line 1308, before 1312)

4. Test the endpoints:
   - GET /api/approvals/pending?user_id=X&organization_id=Y
   - GET /api/organizations/{org_id}/expenses/export?user_id=X&status=approved
"""
