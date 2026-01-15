# Backend Update Instructions for app.py

## Summary
You need to make **3 manual edits** to `app.py` for the 3-role system:

1. **Update** `get_pending_approvals()` function
2. **Delete** `assign_manager()` function
3. **Add** `export_expenses_csv()` function

---

## Edit 1: Update get_pending_approvals() (Line ~1153)

**Find this function:**
```python
@app.route('/api/approvals/pending', methods=['GET'])
def get_pending_approvals():
    """Get pending expense approvals for a manager or admin"""
```

**Replace the ENTIRE function** with the code from:
- File: `NEW_get_pending_approvals.py`
- Or copy from below

<details>
<summary>Click to expand replacement code</summary>

```python
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
```
</details>

---

## Edit 2: Delete assign_manager() (Line ~1229)

**Find and DELETE this ENTIRE function:**
```python
@app.route('/api/organizations/<organization_id>/members/<user_id>/manager', methods=['PUT'])
def assign_manager(organization_id, user_id):
    """Assign a manager to an employee (Admin only)"""
    # ... rest of function
```

**Delete from** `@app.route` **to the end of the function** (about 30 lines).

---

## Edit 3: Add CSV Export Function (After Line ~1308)

**Find this comment:**
```python
# ============================================================================
# END EXPENSE APPROVAL WORKFLOW ENDPOINTS
# ============================================================================
```

**Insert the NEW function BEFORE this comment** from:
- File: `NEW_csv_export.py`
- Or copy from below

<details>
<summary>Click to expand new function code</summary>

```python
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
```
</details>

---

## After Making Changes

1. **Save** `app.py`
2. **Test locally** (optional):
   ```bash
   python app.py
   ```
3. **Commit changes:**
   ```bash
   git add app.py
   git commit -m "Update approval workflow for 3-role system and add CSV export"
   git push
   ```
4. **Deploy to Railway** (will auto-deploy on push)

---

## Summary of Changes

✅ Updated `get_pending_approvals()` - Supports 'approver' role, removes manager hierarchy logic
✅ Deleted `assign_manager()` - No longer needed without manager hierarchy
✅ Added `export_expenses_csv()` - NEW endpoint for CSV export with QuickBooks support

**These changes align with the database migration you already ran successfully!**
