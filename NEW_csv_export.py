# ADD this function to app.py after line 1308
# (before the "# END EXPENSE APPROVAL WORKFLOW ENDPOINTS" comment)

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
