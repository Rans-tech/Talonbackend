from flask import Flask, request, jsonify
from flask_cors import CORS
from talon.agent import TalonAgent
from talon.monitoring import WeatherMonitor, PriceMonitor
from talon.document_parser import DocumentParser
from talon.database import db_client
import os
import base64
import stripe
import csv
import io
import uuid
import secrets
import resend
from dotenv import load_dotenv

load_dotenv()

# Initialize Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

# Initialize Resend
resend.api_key = os.getenv('RESEND_API_KEY')
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:5173')
FROM_EMAIL = os.getenv('FROM_EMAIL', 'noreply@travelraven.com')

app = Flask(__name__)
# Enable CORS for all origins (including localhost for development)
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": False
    }
})

# Initialize TALON agent
talon = TalonAgent()
weather_monitor = WeatherMonitor()
price_monitor = PriceMonitor()
document_parser = DocumentParser()

@app.route('/api/talon/status', methods=['GET'])
def get_talon_status():
    """Get current TALON status and metrics"""
    return jsonify({
        'status': 'active',
        'platforms_unified': 12,
        'disruptions_prevented': 2400,
        'active_monitoring': 12,
        'system_health': 97.4,
        'current_activity': talon.get_current_activity()
    })

@app.route('/api/talon/chat', methods=['POST'])
def talon_chat():
    """Handle chat requests to TALON"""
    data = request.json
    message = data.get('message', '')
    
    response = talon.process_message(message)
    return jsonify({'response': response})

@app.route('/api/monitoring/weather', methods=['GET'])
def get_weather_monitoring():
    """Get weather monitoring data"""
    location = request.args.get('location', 'Orlando, FL')
    return jsonify(weather_monitor.get_status(location))

@app.route('/api/monitoring/prices', methods=['GET'])
def get_price_monitoring():
    """Get price monitoring data"""
    return jsonify(price_monitor.get_status())

@app.route('/api/documents/parse', methods=['POST'])
def parse_document():
    """Parse uploaded travel document and create trip elements"""
    try:
        data = request.json

        # Extract required fields
        file_content = data.get('file_content')  # Base64 encoded
        file_type = data.get('file_type')
        trip_id = data.get('trip_id')
        document_id = data.get('document_id')  # Optional: if you want to link back

        if not file_content or not file_type or not trip_id:
            return jsonify({
                'success': False,
                'error': 'Missing required fields: file_content, file_type, trip_id'
            }), 400

        # Verify trip exists
        print(f"Looking for trip_id: {trip_id}")
        trip = db_client.get_trip(trip_id)
        print(f"Trip found: {trip}")
        if not trip:
            return jsonify({
                'success': False,
                'error': f'Trip not found with id: {trip_id}'
            }), 404

        # Parse the document
        parse_result = document_parser.parse_travel_document(file_content, file_type)

        if not parse_result['success']:
            return jsonify(parse_result), 500

        parsed_data = parse_result['data']
        created_elements = []

        # Create trip elements from parsed data
        if 'elements' in parsed_data:
            for element_data in parsed_data['elements']:
                try:
                    # Validate and clean the element data
                    validated_element = document_parser.validate_element_data(element_data)

                    # Create the trip element in the database
                    created_element = db_client.create_trip_element(trip_id, validated_element)

                    if created_element:
                        created_elements.append(created_element)

                        # Link document to element if document_id provided
                        if document_id and len(created_elements) == 1:  # Link to first element
                            db_client.update_trip_document(document_id, created_element['id'])
                except Exception as e:
                    print(f"Error creating element: {e}")
                    continue

        return jsonify({
            'success': True,
            'message': f'Successfully created {len(created_elements)} trip element(s)',
            'elements': created_elements,
            'metadata': parsed_data.get('metadata', {}),
            'document_type': parsed_data.get('document_type')
        })

    except Exception as e:
        print(f"Error in parse_document: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/documents/parse-text', methods=['POST'])
def parse_text():
    """Parse pasted email/text confirmation and create trip elements"""
    try:
        data = request.json

        # Extract required fields
        text_content = data.get('text_content')
        trip_id = data.get('trip_id')
        document_id = data.get('document_id')  # Optional: if you want to link back

        if not text_content or not trip_id:
            return jsonify({
                'success': False,
                'error': 'Missing required fields: text_content, trip_id'
            }), 400

        # Verify trip exists
        print(f"Looking for trip_id: {trip_id}")
        trip = db_client.get_trip(trip_id)
        print(f"Trip found: {trip}")
        if not trip:
            return jsonify({
                'success': False,
                'error': f'Trip not found with id: {trip_id}'
            }), 404

        # Parse the text
        parse_result = document_parser.parse_travel_text(text_content)

        if not parse_result['success']:
            return jsonify(parse_result), 500

        parsed_data = parse_result['data']
        created_elements = []
        duplicate_count = 0

        # Get existing elements to check which are new
        existing_response = db_client.client.table('trip_elements').select("id").eq('trip_id', trip_id).execute()
        existing_ids = {elem['id'] for elem in (existing_response.data or [])}

        # Create trip elements from parsed data
        if 'elements' in parsed_data:
            for element_data in parsed_data['elements']:
                try:
                    # Validate and clean the element data
                    validated_element = document_parser.validate_element_data(element_data)

                    # Create the trip element in the database (will return existing if duplicate)
                    created_element = db_client.create_trip_element(trip_id, validated_element)

                    if created_element:
                        # Check if this is a new element or existing duplicate
                        if created_element['id'] in existing_ids:
                            duplicate_count += 1
                        else:
                            created_elements.append(created_element)

                        # Link document to element if document_id provided
                        if document_id and len(created_elements) == 1:  # Link to first element
                            db_client.update_trip_document(document_id, created_element['id'])
                except Exception as e:
                    print(f"Error creating element: {e}")
                    continue

        # Build message
        message_parts = []
        if created_elements:
            message_parts.append(f'Created {len(created_elements)} new element(s)')
        if duplicate_count:
            message_parts.append(f'{duplicate_count} duplicate(s) skipped')
        message = ', '.join(message_parts) if message_parts else 'No new elements created'

        return jsonify({
            'success': True,
            'message': message,
            'elements': created_elements,
            'duplicates_skipped': duplicate_count,
            'metadata': parsed_data.get('metadata', {}),
            'document_type': parsed_data.get('document_type')
        })

    except Exception as e:
        print(f"Error in parse_text: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/stripe/webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events"""
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError as e:
        # Invalid payload
        print(f"Invalid payload: {e}")
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        print(f"Invalid signature: {e}")
        return jsonify({'error': 'Invalid signature'}), 400

    # Handle the event
    event_type = event['type']
    print(f"Processing event: {event_type}")

    if event_type == 'checkout.session.completed':
        session = event['data']['object']

        # Extract metadata
        user_id = session.get('client_reference_id')
        tier = session['metadata'].get('tier')
        billing_cycle = session['metadata'].get('billingCycle')

        if user_id and tier:
            # Update user's subscription in Supabase
            try:
                db_client.client.table('profiles').update({
                    'subscription_tier': tier,
                    'stripe_customer_id': session.get('customer'),
                    'stripe_subscription_id': session.get('subscription'),
                    'subscription_status': 'active',
                    'subscription_started_at': 'now()',
                }).eq('id', user_id).execute()

                print(f"Successfully activated {tier} subscription for user {user_id}")
            except Exception as e:
                print(f"Error updating subscription: {e}")

    elif event_type == 'customer.subscription.updated':
        subscription = event['data']['object']
        customer_id = subscription['customer']

        # Find user by Stripe customer ID
        try:
            result = db_client.client.table('profiles').select('id').eq('stripe_customer_id', customer_id).limit(1).execute()
            if result.data:
                user_id = result.data[0]['id']
                status = subscription['status']

                db_client.client.table('profiles').update({
                    'subscription_status': status,
                }).eq('id', user_id).execute()

                print(f"Updated subscription status to {status} for user {user_id}")
        except Exception as e:
            print(f"Error updating subscription status: {e}")

    elif event_type == 'customer.subscription.deleted':
        subscription = event['data']['object']
        customer_id = subscription['customer']

        # Find user by Stripe customer ID and downgrade to free
        try:
            result = db_client.client.table('profiles').select('id').eq('stripe_customer_id', customer_id).limit(1).execute()
            if result.data:
                user_id = result.data[0]['id']

                db_client.client.table('profiles').update({
                    'subscription_tier': 'free',
                    'subscription_status': 'canceled',
                }).eq('id', user_id).execute()

                print(f"Downgraded user {user_id} to free tier")
        except Exception as e:
            print(f"Error downgrading to free tier: {e}")

    return jsonify({'received': True}), 200

@app.route('/api/stripe/create-checkout-session', methods=['POST'])
def create_checkout_session():
    """Create a Stripe checkout session for subscription"""
    try:
        data = request.json

        # Extract required fields
        tier = data.get('tier')
        billing_cycle = data.get('billingCycle')
        user_id = data.get('userId')
        user_email = data.get('userEmail')
        quantity = data.get('quantity', 1)

        if not all([tier, billing_cycle, user_id, user_email]):
            return jsonify({
                'error': 'Missing required fields'
            }), 400

        # Price IDs mapping (from your frontend config)
        STRIPE_PRICE_IDS = {
            'pro_single': {
                'monthly': 'price_1SPSaM6e7MGhkeXuJUBfzRO4',
                'annually': 'price_1SPSaw6e7MGhkeXu3hYTq2Sl',
            },
            'family': {
                'monthly': 'price_1SPSbX6e7MGhkeXuyj9bzT6S',
                'annually': 'price_1SPSbw6e7MGhkeXuiI46XS1N',
            },
            'enterprise': {
                'monthly': 'price_1SPSg06e7MGhkeXuHjzYy0q5',
                'annually': 'price_1SPSgj6e7MGhkeXuMbo6bhzp',
            },
        }

        price_id = STRIPE_PRICE_IDS.get(tier, {}).get(billing_cycle)

        if not price_id:
            return jsonify({
                'error': f'Invalid tier or billing cycle: {tier} {billing_cycle}'
            }), 400

        # Get origin from request headers
        origin = request.headers.get('Origin', 'http://localhost:5173')

        # Create Stripe Checkout Session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': quantity,
            }],
            mode='subscription',
            success_url=f'{origin}/?checkout=success&session_id={{CHECKOUT_SESSION_ID}}',
            cancel_url=f'{origin}/pricing?checkout=canceled',
            customer_email=user_email,
            client_reference_id=user_id,
            metadata={
                'userId': user_id,
                'tier': tier,
                'billingCycle': billing_cycle,
                **({"seats": str(quantity)} if tier == 'enterprise' else {})
            },
            allow_promotion_codes=True,
            billing_address_collection='auto',
        )

        return jsonify({
            'sessionId': checkout_session.id,
            'url': checkout_session.url
        })

    except Exception as e:
        print(f"Error creating checkout session: {e}")
        return jsonify({
            'error': str(e)
        }), 500

@app.route('/api/organizations/<organization_id>/invitations/bulk', methods=['POST'])
def bulk_invite_members(organization_id):
    """Parse CSV and create pre-invitations for organization members"""
    try:
        data = request.json
        csv_content = data.get('csv_content')
        invited_by_id = data.get('invited_by_id')

        if not csv_content or not invited_by_id:
            return jsonify({
                'success': False,
                'error': 'Missing required fields: csv_content, invited_by_id'
            }), 400

        # Verify organization exists and get details
        org_response = db_client.client.table('organizations').select('id, name, logo_url').eq('id', organization_id).execute()
        if not org_response.data:
            return jsonify({
                'success': False,
                'error': f'Organization not found: {organization_id}'
            }), 404

        organization = org_response.data[0]

        # Parse CSV
        csv_file = io.StringIO(csv_content)
        csv_reader = csv.DictReader(csv_file)

        invitations = []
        errors = []

        for row_num, row in enumerate(csv_reader, start=2):
            try:
                # Extract and validate fields (case-insensitive)
                name = row.get('name') or row.get('Name') or row.get('NAME')
                email = row.get('email') or row.get('Email') or row.get('EMAIL')
                role = (row.get('role') or row.get('Role') or row.get('ROLE') or 'member').lower()

                if not name or not email:
                    errors.append(f"Row {row_num}: Missing name or email")
                    continue

                # Validate role
                if role not in ['owner', 'admin', 'member', 'viewer']:
                    role = 'member'

                # Generate unique invitation token
                invitation_token = secrets.token_urlsafe(32)

                # Store email separately for lookup and resending
                invitations.append({
                    'organization_id': organization_id,
                    'invited_name': name.strip(),
                    'invited_email': email.strip().lower(),  # Store email for resending
                    'role': role,
                    'status': 'invited',
                    'invitation_token': invitation_token,
                    'invitation_sent_at': 'now()',
                    'invited_at': 'now()',
                    '_email': email.strip().lower()  # Temporary field for sending initial email
                })

            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
                continue

        if not invitations:
            return jsonify({
                'success': False,
                'error': 'No valid invitations found in CSV',
                'errors': errors
            }), 400

        # Create invitation batch record
        batch_response = db_client.client.table('invitation_batches').insert({
            'organization_id': organization_id,
            'uploaded_by': invited_by_id,
            'file_name': data.get('file_name', 'bulk_upload.csv'),
            'total_invites': len(invitations),
            'status': 'processing'
        }).execute()

        batch_id = batch_response.data[0]['id'] if batch_response.data else None

        # Insert invitations (with pre-created profiles for tracking)
        successful = 0
        failed = 0
        created_invitations = []

        for invitation in invitations:
            try:
                # Extract email for lookup (don't insert it into DB)
                email = invitation.pop('_email')

                # Check if email already has a profile
                profile_check = db_client.client.table('profiles').select('id').eq('email', email).execute()

                if profile_check.data:
                    # User exists - create standard invitation
                    user_id = profile_check.data[0]['id']
                    invitation['user_id'] = user_id
                    invitation['status'] = 'pending'  # Change to pending since user exists

                # Insert invitation (email field removed)
                result = db_client.client.table('organization_members').insert(invitation).execute()

                if result.data:
                    invite_url = f"{FRONTEND_URL}/signup?token={invitation['invitation_token']}"

                    created_invitations.append({
                        **result.data[0],
                        'email': email,  # Include email in response for display
                        'invite_url': invite_url
                    })
                    successful += 1

                    # Send invitation email
                    try:
                        resend.Emails.send({
                            "from": FROM_EMAIL,
                            "to": email,
                            "subject": f"You're invited to join {organization['name']} on Travel Raven",
                            "html": f"""
                            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                                <h2 style="color: #0a1128;">You're invited to Travel Raven!</h2>
                                <p>Hello {invitation['invited_name']},</p>
                                <p>You've been invited to join <strong>{organization['name']}</strong>'s travel management platform on Travel Raven.</p>
                                <p>As a <strong>{invitation['role']}</strong>, you'll be able to collaborate with your team to manage travel bookings and itineraries.</p>
                                <div style="margin: 30px 0;">
                                    <a href="{invite_url}" style="background-color: #14b8a6; color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; display: inline-block;">
                                        Accept Invitation & Sign Up
                                    </a>
                                </div>
                                <p style="color: #666; font-size: 14px;">
                                    Or copy this link into your browser:<br>
                                    <a href="{invite_url}">{invite_url}</a>
                                </p>
                                <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                                <p style="color: #999; font-size: 12px;">
                                    This invitation was sent to {email}. If you didn't expect this email, you can safely ignore it.
                                </p>
                            </div>
                            """
                        })
                    except Exception as email_error:
                        print(f"Failed to send email to {email}: {email_error}")
                        # Don't fail the whole invitation if email fails
                else:
                    failed += 1

            except Exception as e:
                print(f"Error creating invitation for {email}: {e}")
                failed += 1
                errors.append(f"{email}: {str(e)}")

        # Update batch status
        if batch_id:
            db_client.client.table('invitation_batches').update({
                'successful_invites': successful,
                'failed_invites': failed,
                'status': 'completed',
                'completed_at': 'now()'
            }).eq('id', batch_id).execute()

        return jsonify({
            'success': True,
            'message': f'Created {successful} invitation(s), {failed} failed',
            'invitations': created_invitations,
            'batch_id': batch_id,
            'successful_count': successful,
            'failed_count': failed,
            'errors': errors
        })

    except Exception as e:
        print(f"Error in bulk_invite_members: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/organizations/<organization_id>/invitations/<member_id>/resend', methods=['POST'])
def resend_invitation(organization_id, member_id):
    """Resend invitation email to a member"""
    try:
        # Get the invitation
        member_response = db_client.client.table('organization_members').select('*').eq('id', member_id).eq('organization_id', organization_id).single().execute()

        if not member_response.data:
            return jsonify({
                'success': False,
                'error': 'Invitation not found'
            }), 404

        member = member_response.data

        # Only resend for invited status
        if member['status'] != 'invited':
            return jsonify({
                'success': False,
                'error': 'Can only resend invitations for members with invited status'
            }), 400

        # Get organization details
        org_response = db_client.client.table('organizations').select('id, name').eq('id', organization_id).single().execute()
        if not org_response.data:
            return jsonify({
                'success': False,
                'error': 'Organization not found'
            }), 404

        organization = org_response.data

        # Get email from invited_email field
        email = member.get('invited_email')

        if not email:
            return jsonify({
                'success': False,
                'error': 'Cannot resend: email address not found'
            }), 400

        # Construct the invite URL
        invite_url = f"{FRONTEND_URL}/signup?token={member['invitation_token']}"

        # Send invitation email
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": email,
            "subject": f"Reminder: You're invited to join {organization['name']} on Travel Raven",
            "html": f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #0a1128;">Reminder: You're invited to Travel Raven!</h2>
                <p>Hello {member['invited_name']},</p>
                <p>This is a reminder that you've been invited to join <strong>{organization['name']}</strong>'s travel management platform on Travel Raven.</p>
                <p>As a <strong>{member['role']}</strong>, you'll be able to collaborate with your team to manage travel bookings and itineraries.</p>
                <div style="margin: 30px 0;">
                    <a href="{invite_url}" style="background-color: #14b8a6; color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; display: inline-block;">
                        Accept Invitation & Sign Up
                    </a>
                </div>
                <p style="color: #666; font-size: 14px;">
                    Or copy this link into your browser:<br>
                    <a href="{invite_url}">{invite_url}</a>
                </p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                <p style="color: #999; font-size: 12px;">
                    This invitation was sent to {email}. If you didn't expect this email, you can safely ignore it.
                </p>
            </div>
            """
        })

        # Update invitation_sent_at timestamp
        db_client.client.table('organization_members').update({
            'invitation_sent_at': 'now()'
        }).eq('id', member_id).execute()

        return jsonify({
            'success': True,
            'message': 'Invitation email resent successfully'
        })

    except Exception as e:
        print(f"Error resending invitation: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/invitations/validate/<token>', methods=['GET'])
def validate_invitation_token(token):
    """Validate an invitation token and return invitation details"""
    try:
        # Look up invitation by token
        response = db_client.client.table('organization_members').select('''
            *,
            organization:organizations(id, name, logo_url)
        ''').eq('invitation_token', token).eq('status', 'invited').execute()

        if not response.data:
            return jsonify({
                'success': False,
                'error': 'Invalid or expired invitation token'
            }), 404

        invitation = response.data[0]

        return jsonify({
            'success': True,
            'invitation': {
                'id': invitation['id'],
                'invited_name': invitation['invited_name'],
                'role': invitation['role'],
                'organization': invitation['organization']
            }
        })

    except Exception as e:
        print(f"Error validating invitation token: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/invitations/accept', methods=['POST'])
def accept_invitation():
    """Accept an invitation after user signs up"""
    try:
        data = request.json
        token = data.get('token')
        user_id = data.get('user_id')

        if not token or not user_id:
            return jsonify({
                'success': False,
                'error': 'Missing required fields: token, user_id'
            }), 400

        # Find invitation
        invitation_response = db_client.client.table('organization_members').select('*').eq('invitation_token', token).eq('status', 'invited').execute()

        if not invitation_response.data:
            return jsonify({
                'success': False,
                'error': 'Invalid or already accepted invitation'
            }), 404

        invitation = invitation_response.data[0]

        # Update invitation with user_id and mark as active
        update_response = db_client.client.table('organization_members').update({
            'user_id': user_id,
            'status': 'active',
            'accepted_at': 'now()',
            'invitation_token': None  # Clear token after acceptance
        }).eq('id', invitation['id']).execute()

        if update_response.data:
            # Increment organization's seat count
            org_id = invitation['organization_id']
            org_response = db_client.client.table('organizations').select('current_seats_used').eq('id', org_id).single().execute()

            if org_response.data:
                current_seats = org_response.data.get('current_seats_used', 0)
                db_client.client.table('organizations').update({
                    'current_seats_used': current_seats + 1
                }).eq('id', org_id).execute()

            return jsonify({
                'success': True,
                'message': 'Invitation accepted successfully',
                'organization_id': invitation['organization_id']
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to accept invitation'
            }), 500

    except Exception as e:
        print(f"Error accepting invitation: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

# ============================================================================
# EXPENSE TRACKING ENDPOINTS
# ============================================================================

@app.route('/api/trips/<trip_id>/expenses', methods=['GET'])
def get_trip_expenses(trip_id):
    """Get all expenses for a trip"""
    try:
        response = db_client.client.table('expenses').select('*').eq('trip_id', trip_id).order('expense_date', desc=True).execute()
        return jsonify({'success': True, 'expenses': response.data})
    except Exception as e:
        print(f"Error fetching expenses: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/trips/<trip_id>/expenses', methods=['POST'])
def create_expense(trip_id):
    """Create a new expense for a trip"""
    try:
        data = request.json
        if not data.get('amount') or not data.get('category') or not data.get('expense_date') or not data.get('user_id'):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        expense_data = {
            'trip_id': trip_id,
            'user_id': data['user_id'],
            'amount': float(data['amount']),
            'category': data['category'],
            'description': data.get('description', ''),
            'expense_date': data['expense_date'],
            'notes': data.get('notes', ''),
            'receipt_image_url': data.get('receipt_image_url', None)
        }
        response = db_client.client.table('expenses').insert(expense_data).execute()
        if response.data:
            return jsonify({'success': True, 'expense': response.data[0]})
        return jsonify({'success': False, 'error': 'Failed to create expense'}), 500
    except Exception as e:
        print(f"Error creating expense: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/expenses/<expense_id>', methods=['PUT'])
def update_expense(expense_id):
    """Update an existing expense"""
    try:
        data = request.json
        update_data = {}
        if 'amount' in data:
            update_data['amount'] = float(data['amount'])
        if 'category' in data:
            update_data['category'] = data['category']
        if 'description' in data:
            update_data['description'] = data['description']
        if 'expense_date' in data:
            update_data['expense_date'] = data['expense_date']
        if 'notes' in data:
            update_data['notes'] = data['notes']
        if 'receipt_image_url' in data:
            update_data['receipt_image_url'] = data['receipt_image_url']

        response = db_client.client.table('expenses').update(update_data).eq('id', expense_id).execute()
        if response.data:
            return jsonify({'success': True, 'expense': response.data[0]})
        return jsonify({'success': False, 'error': 'Failed to update expense'}), 500
    except Exception as e:
        print(f"Error updating expense: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/expenses/<expense_id>', methods=['DELETE'])
def delete_expense(expense_id):
    """Delete an expense"""
    try:
        expense_response = db_client.client.table('expenses').select('receipt_image_url').eq('id', expense_id).single().execute()
        if expense_response.data and expense_response.data.get('receipt_image_url'):
            receipt_url = expense_response.data['receipt_image_url']
            if 'expense-receipts/' in receipt_url:
                file_path = receipt_url.split('expense-receipts/')[1]
                try:
                    db_client.client.storage.from_('expense-receipts').remove([file_path])
                except Exception as storage_error:
                    print(f"Warning: Failed to delete receipt image: {storage_error}")

        db_client.client.table('expenses').delete().eq('id', expense_id).execute()
        return jsonify({'success': True, 'message': 'Expense deleted successfully'})
    except Exception as e:
        print(f"Error deleting expense: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/expenses/<expense_id>/receipt', methods=['POST'])
def upload_receipt(expense_id):
    """Upload receipt image for an expense"""
    try:
        data = request.json
        if not data.get('user_id') or not data.get('file_data') or not data.get('file_name'):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        user_id = data['user_id']
        file_data = data['file_data']
        file_name = data['file_name']

        try:
            if ',' in file_data:
                file_data = file_data.split(',')[1]
            image_bytes = base64.b64decode(file_data)
        except Exception as decode_error:
            return jsonify({'success': False, 'error': f'Invalid base64 image data: {str(decode_error)}'}), 400

        file_extension = file_name.split('.')[-1] if '.' in file_name else 'jpg'
        unique_filename = f"{user_id}/{expense_id}_{uuid.uuid4().hex[:8]}.{file_extension}"

        # Upload to Supabase Storage with error checking
        try:
            upload_response = db_client.client.storage.from_('expense-receipts').upload(
                unique_filename,
                image_bytes,
                {'content-type': f'image/{file_extension}', 'upsert': 'false'}
            )

            # Check if upload failed
            if hasattr(upload_response, 'error') and upload_response.error:
                error_msg = upload_response.error.message if hasattr(upload_response.error, 'message') else str(upload_response.error)
                print(f"Storage upload error: {error_msg}")
                return jsonify({'success': False, 'error': f'Storage upload failed: {error_msg}'}), 500

        except Exception as storage_error:
            print(f"Exception during storage upload: {str(storage_error)}")
            return jsonify({'success': False, 'error': f'Storage exception: {str(storage_error)}'}), 500

        # Get public URL only after successful upload
        public_url = db_client.client.storage.from_('expense-receipts').get_public_url(unique_filename)

        # Update expense with receipt URL
        update_response = db_client.client.table('expenses').update({'receipt_image_url': public_url}).eq('id', expense_id).execute()
        if update_response.data:
            print(f"Receipt uploaded successfully: {public_url}")
            return jsonify({'success': True, 'receipt_url': public_url, 'expense': update_response.data[0]})
        return jsonify({'success': False, 'error': 'Failed to update expense with receipt URL'}), 500
    except Exception as e:
        print(f"Error uploading receipt: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/receipts/parse', methods=['POST'])
def parse_receipt():
    """Parse receipt image and extract expense data"""
    try:
        data = request.json
        
        if not data.get('file_content') or not data.get('file_type'):
            return jsonify({
                'success': False,
                'error': 'Missing required fields: file_content, file_type'
            }), 400
        
        file_content = data['file_content']
        file_type = data['file_type']
        
        # Parse the receipt using AI
        result = document_parser.parse_receipt(file_content, file_type)
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error parsing receipt: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================================================
# TASK GENERATION ENDPOINTS
# ============================================================================

@app.route('/api/trips/<trip_id>/generate-tasks', methods=['POST', 'OPTIONS'])
def generate_trip_tasks(trip_id):
    # Handle OPTIONS preflight
    if request.method == 'OPTIONS':
        return '', 200

    """Generate smart tasks for a trip using AI based on trip elements"""
    try:
        data = request.json
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'success': False, 'error': 'user_id required'}), 400
        
        # Fetch trip elements from database
        trip_response = db_client.client.table('trip_elements').select('*').eq('trip_id', trip_id).execute()
        
        if not trip_response.data or len(trip_response.data) == 0:
            return jsonify({
                'success': False,
                'error': 'No trip elements found. Add flights, hotels, or activities first.'
            }), 400
        
        trip_elements = trip_response.data
        
        # Generate tasks using AI
        result = document_parser.generate_smart_tasks(trip_elements)
        
        if not result.get('success'):
            return jsonify(result), 500
        
        # Insert tasks into database
        tasks_to_insert = []
        for task in result.get('tasks', []):
            task_data = {
                'trip_id': trip_id,
                'title': task['title'],
                'description': task.get('description', ''),
                'status': 'pending',
                'priority': task.get('priority', 'medium'),
                'due_date': task.get('due_date')
            }
            tasks_to_insert.append(task_data)
        
        if tasks_to_insert:
            insert_response = db_client.client.table('trip_tasks').insert(tasks_to_insert).execute()
            
            return jsonify({
                'success': True,
                'message': f'Generated {len(tasks_to_insert)} tasks',
                'tasks': insert_response.data
            })
        
        return jsonify({
            'success': False,
            'error': 'No tasks generated'
        }), 500
        
    except Exception as e:
        print(f"Error generating tasks: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tasks/<task_id>', methods=['DELETE', 'OPTIONS'])
def delete_task(task_id):
    """Delete a single task"""
    # Handle OPTIONS preflight
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        # Delete the task
        response = db_client.client.table('trip_tasks').delete().eq('id', task_id).execute()
        
        return jsonify({
            'success': True,
            'message': 'Task deleted successfully'
        })
        
    except Exception as e:
        print(f"Error deleting task: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/trips/<trip_id>/tasks', methods=['DELETE', 'OPTIONS'])
def clear_trip_tasks(trip_id):
    """Clear all tasks for a trip"""
    # Handle OPTIONS preflight
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        # Delete all tasks for this trip
        response = db_client.client.table('trip_tasks').delete().eq('trip_id', trip_id).execute()
        
        return jsonify({
            'success': True,
            'message': 'All tasks cleared successfully'
        })
        
    except Exception as e:
        print(f"Error clearing tasks: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
