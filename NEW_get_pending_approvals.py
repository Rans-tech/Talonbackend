# REPLACE the get_pending_approvals function in app.py (around line 1153)
# with this code:

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
