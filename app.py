from flask import Flask, request, jsonify
from flask_cors import CORS
from talon.agent import TalonAgent
from talon.monitoring import WeatherMonitor, PriceMonitor
from talon.document_parser import DocumentParser
from talon.database import db_client
from talon.insights_detector import InsightsDetector
from talon.pattern_matcher import PatternMatcher
from talon.insights_learning import InsightsLearning
from talon.insights_ai import InsightsAI
from datetime import datetime
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
        user_id = data.get('user_id')  # Required for expense creation
        user_id = data.get('user_id')  # Required for expense creation

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

                        # Create linked expense if element has price
                        if user_id and validated_element.get('price'):
                            db_client.create_expense_from_element(trip_id, user_id, validated_element, created_element['id'])

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
        user_id = data.get('user_id')  # Required for expense creation

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

                            # Create linked expense if element has price (only for new elements)
                            if user_id and validated_element.get('price'):
                                db_client.create_expense_from_element(trip_id, user_id, validated_element, created_element['id'])

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
        expenses = response.data

        # Refresh signed URLs for receipts (in case they expired or are old public URLs)
        for expense in expenses:
            if expense.get('receipt_image_url'):
                try:
                    # Extract the file path from the URL
                    # URL format: https://.../storage/v1/object/sign/expense-receipts/path/to/file.jpg?token=...
                    # OR: https://.../storage/v1/object/public/expense-receipts/path/to/file.jpg
                    url = expense['receipt_image_url']
                    if '/expense-receipts/' in url:
                        # Extract path after bucket name
                        path_start = url.find('/expense-receipts/') + len('/expense-receipts/')
                        path_end = url.find('?') if '?' in url else len(url)
                        file_path = url[path_start:path_end]

                        # Generate fresh signed URL (1 year expiration)
                        signed_url_response = db_client.client.storage.from_('expense-receipts').create_signed_url(file_path, 31536000)
                        signed_url = signed_url_response.get('signedURL') if isinstance(signed_url_response, dict) else signed_url_response
                        expense['receipt_image_url'] = signed_url
                except Exception as url_error:
                    print(f"Error refreshing signed URL for expense {expense.get('id')}: {url_error}")
                    # Keep the old URL if refresh fails
                    pass

        return jsonify({'success': True, 'expenses': expenses})
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

        # Get signed URL for RLS-protected bucket (expires in 1 year = 31536000 seconds)
        signed_url_response = db_client.client.storage.from_('expense-receipts').create_signed_url(unique_filename, 31536000)

        # Extract the signed URL from response
        signed_url = signed_url_response.get('signedURL') if isinstance(signed_url_response, dict) else signed_url_response

        # Update expense with receipt URL
        update_response = db_client.client.table('expenses').update({'receipt_image_url': signed_url}).eq('id', expense_id).execute()
        if update_response.data:
            print(f"Receipt uploaded successfully: {signed_url}")
            return jsonify({'success': True, 'receipt_url': signed_url, 'expense': update_response.data[0]})
        return jsonify({'success': False, 'error': 'Failed to update expense with receipt URL'}), 500
    except Exception as e:
        print(f"Error uploading receipt: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================================
# EXPENSE APPROVAL WORKFLOW ENDPOINTS
# ============================================================================

@app.route('/api/expenses/<expense_id>/submit', methods=['POST'])
def submit_expense_for_approval(expense_id):
    """Submit an expense for approval"""
    try:
        data = request.json
        user_id = data.get('user_id')
        organization_id = data.get('organization_id')
        trip_id = data.get('trip_id')
        submission_notes = data.get('notes', '')

        if not user_id or not organization_id or not trip_id:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        # Get expense details
        expense_response = db_client.client.table('expenses').select('*').eq('id', expense_id).single().execute()
        if not expense_response.data:
            return jsonify({'success': False, 'error': 'Expense not found'}), 404

        expense = expense_response.data

        # Check if already submitted
        existing_submission = db_client.client.table('expense_submissions').select('*').eq('expense_id', expense_id).execute()
        if existing_submission.data and len(existing_submission.data) > 0:
            return jsonify({'success': False, 'error': 'Expense already submitted'}), 400

        # Get organization settings
        settings_response = db_client.client.table('expense_approval_settings').select('*').eq('organization_id', organization_id).single().execute()
        settings = settings_response.data if settings_response.data else {}

        # Determine if auto-approval applies
        auto_approve_threshold = settings.get('auto_approve_below_amount', 0)
        status = 'approved' if expense['amount'] < auto_approve_threshold else 'submitted'

        # Create submission
        submission_data = {
            'expense_id': expense_id,
            'trip_id': trip_id,
            'organization_id': organization_id,
            'submitted_by': user_id,
            'submitted_amount': expense['amount'],
            'submission_notes': submission_notes,
            'status': status
        }

        if status == 'approved':
            submission_data['approved_amount'] = expense['amount']
            submission_data['approver_id'] = user_id
            submission_data['approved_at'] = 'now()'
            submission_data['approval_notes'] = 'Auto-approved'

        submission_response = db_client.client.table('expense_submissions').insert(submission_data).execute()

        if submission_response.data:
            return jsonify({
                'success': True,
                'submission': submission_response.data[0],
                'auto_approved': status == 'approved'
            })

        return jsonify({'success': False, 'error': 'Failed to create submission'}), 500

    except Exception as e:
        print(f"Error submitting expense: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/submissions/<submission_id>/approve', methods=['POST'])
def approve_expense(submission_id):
    """Approve an expense submission (Manager/Admin)"""
    try:
        data = request.json
        approver_id = data.get('approver_id')
        approved_amount = data.get('approved_amount')
        approval_notes = data.get('notes', '')

        if not approver_id:
            return jsonify({'success': False, 'error': 'Missing approver_id'}), 400

        # Get submission
        submission_response = db_client.client.table('expense_submissions').select('*').eq('id', submission_id).single().execute()
        if not submission_response.data:
            return jsonify({'success': False, 'error': 'Submission not found'}), 404

        submission = submission_response.data

        # Verify submission is in submitted status
        if submission['status'] != 'submitted':
            return jsonify({'success': False, 'error': f'Cannot approve submission with status: {submission["status"]}'}), 400

        # Use submitted amount if approved amount not provided
        if approved_amount is None:
            approved_amount = submission['submitted_amount']

        # Update submission
        update_data = {
            'status': 'approved',
            'approver_id': approver_id,
            'approved_at': 'now()',
            'approved_amount': approved_amount,
            'approval_notes': approval_notes
        }

        update_response = db_client.client.table('expense_submissions').update(update_data).eq('id', submission_id).execute()

        if update_response.data:
            return jsonify({'success': True, 'submission': update_response.data[0]})

        return jsonify({'success': False, 'error': 'Failed to approve submission'}), 500

    except Exception as e:
        print(f"Error approving expense: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/submissions/<submission_id>/reject', methods=['POST'])
def reject_expense(submission_id):
    """Reject an expense submission (Manager/Admin)"""
    try:
        data = request.json
        approver_id = data.get('approver_id')
        rejection_reason = data.get('reason', '')

        if not approver_id:
            return jsonify({'success': False, 'error': 'Missing approver_id'}), 400

        if not rejection_reason:
            return jsonify({'success': False, 'error': 'Rejection reason is required'}), 400

        # Get submission
        submission_response = db_client.client.table('expense_submissions').select('*').eq('id', submission_id).single().execute()
        if not submission_response.data:
            return jsonify({'success': False, 'error': 'Submission not found'}), 404

        submission = submission_response.data

        # Verify submission is in submitted status
        if submission['status'] != 'submitted':
            return jsonify({'success': False, 'error': f'Cannot reject submission with status: {submission["status"]}'}), 400

        # Update submission
        update_data = {
            'status': 'rejected',
            'approver_id': approver_id,
            'approved_at': 'now()',
            'rejection_reason': rejection_reason
        }

        update_response = db_client.client.table('expense_submissions').update(update_data).eq('id', submission_id).execute()

        if update_response.data:
            return jsonify({'success': True, 'submission': update_response.data[0]})

        return jsonify({'success': False, 'error': 'Failed to reject submission'}), 500

    except Exception as e:
        print(f"Error rejecting expense: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/submissions/<submission_id>/reimburse', methods=['POST'])
def reimburse_expense(submission_id):
    """Mark expense as reimbursed (Admin only)"""
    try:
        data = request.json
        reimbursed_by = data.get('reimbursed_by')
        reimbursement_method = data.get('method', 'bank_transfer')
        reimbursement_reference = data.get('reference', '')

        if not reimbursed_by:
            return jsonify({'success': False, 'error': 'Missing reimbursed_by'}), 400

        # Get submission
        submission_response = db_client.client.table('expense_submissions').select('*').eq('id', submission_id).single().execute()
        if not submission_response.data:
            return jsonify({'success': False, 'error': 'Submission not found'}), 404

        submission = submission_response.data

        # Verify submission is approved
        if submission['status'] != 'approved':
            return jsonify({'success': False, 'error': 'Can only reimburse approved expenses'}), 400

        # Update submission
        update_data = {
            'status': 'reimbursed',
            'reimbursed_by': reimbursed_by,
            'reimbursed_at': 'now()',
            'reimbursement_method': reimbursement_method,
            'reimbursement_reference': reimbursement_reference
        }

        update_response = db_client.client.table('expense_submissions').update(update_data).eq('id', submission_id).execute()

        if update_response.data:
            return jsonify({'success': True, 'submission': update_response.data[0]})

        return jsonify({'success': False, 'error': 'Failed to mark as reimbursed'}), 500

    except Exception as e:
        print(f"Error marking expense as reimbursed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/approvals/pending', methods=['GET'])
def get_pending_approvals():
    """Get pending expense approvals for a manager or admin"""
    try:
        user_id = request.args.get('user_id')
        organization_id = request.args.get('organization_id')

        if not user_id or not organization_id:
            return jsonify({'success': False, 'error': 'Missing required parameters'}), 400

        # Get user's role in organization
        member_response = db_client.client.table('organization_members').select('role, manager_id').eq('user_id', user_id).eq('organization_id', organization_id).single().execute()

        if not member_response.data:
            return jsonify({'success': False, 'error': 'User not found in organization'}), 404

        role = member_response.data['role']

        # Build query based on role
        if role in ['owner', 'admin']:
            # Admins see all pending submissions in org
            submissions_response = db_client.client.table('expense_submissions').select('*, expenses(*), profiles!submitted_by(*)').eq('organization_id', organization_id).eq('status', 'submitted').order('submitted_at', desc=True).execute()
        else:
            # Managers see submissions from their direct reports
            submissions_response = db_client.client.table('expense_submissions').select('*, expenses(*), profiles!submitted_by(*)').eq('organization_id', organization_id).eq('status', 'submitted').execute()

            # Filter for direct reports
            if submissions_response.data:
                # Get team member IDs
                team_response = db_client.client.table('organization_members').select('user_id').eq('manager_id', user_id).eq('organization_id', organization_id).eq('status', 'active').execute()
                team_ids = [member['user_id'] for member in team_response.data] if team_response.data else []

                # Filter submissions
                submissions_response.data = [s for s in submissions_response.data if s['submitted_by'] in team_ids]

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

@app.route('/api/submissions/my-history', methods=['GET'])
def get_my_submission_history():
    """Get submission history for the current user"""
    try:
        user_id = request.args.get('user_id')
        organization_id = request.args.get('organization_id')

        if not user_id:
            return jsonify({'success': False, 'error': 'Missing user_id'}), 400

        # Build query
        query = db_client.client.table('expense_submissions').select('*, expenses(*), profiles!approver_id(*)').eq('submitted_by', user_id).order('submitted_at', desc=True)

        if organization_id:
            query = query.eq('organization_id', organization_id)

        submissions_response = query.execute()

        return jsonify({
            'success': True,
            'submissions': submissions_response.data if submissions_response.data else []
        })

    except Exception as e:
        print(f"Error fetching submission history: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/organizations/<organization_id>/approval-settings', methods=['GET'])
def get_approval_settings(organization_id):
    """Get approval settings for an organization"""
    try:
        settings_response = db_client.client.table('expense_approval_settings').select('*').eq('organization_id', organization_id).single().execute()

        if settings_response.data:
            return jsonify({'success': True, 'settings': settings_response.data})

        return jsonify({'success': False, 'error': 'Settings not found'}), 404

    except Exception as e:
        print(f"Error fetching approval settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/organizations/<organization_id>/approval-settings', methods=['PUT'])
def update_approval_settings(organization_id):
    """Update approval settings for an organization (Admin only)"""
    try:
        data = request.json

        # Build update data
        update_data = {}
        allowed_fields = [
            'require_approval', 'auto_approve_below_amount', 'require_admin_approval_above',
            'require_receipt', 'require_receipt_above_amount', 'max_expense_age_days',
            'notify_manager_on_submission', 'notify_submitter_on_decision'
        ]

        for field in allowed_fields:
            if field in data:
                update_data[field] = data[field]

        if not update_data:
            return jsonify({'success': False, 'error': 'No update data provided'}), 400

        # Update settings
        update_response = db_client.client.table('expense_approval_settings').update(update_data).eq('organization_id', organization_id).execute()

        if update_response.data:
            return jsonify({'success': True, 'settings': update_response.data[0]})

        return jsonify({'success': False, 'error': 'Failed to update settings'}), 500

    except Exception as e:
        print(f"Error updating approval settings: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================================
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
# END EXPENSE APPROVAL WORKFLOW ENDPOINTS
# ============================================================================

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


# TALON Insights Endpoint
# @route: POST /api/trips/:id/insights
@app.route('/api/trips/<trip_id>/insights', methods=['POST', 'OPTIONS'])
def get_trip_insights(trip_id):
    """
    Generate TALON Insights for a trip.
    Returns actionable intelligence in 3 priority tiers:
    - action_required: Critical issues that WILL cause problems
    - recommendations: Optimizations to improve the trip
    - good_to_know: Helpful context (usually empty)
    """
    # Handle OPTIONS preflight
    if request.method == 'OPTIONS':
        return '', 200

    try:
        # Get trip details
        trip_response = db_client.client.table('trips').select('*').eq('id', trip_id).single().execute()
        if not trip_response.data:
            return jsonify({'success': False, 'error': 'Trip not found'}), 404

        trip = trip_response.data

        # Get all trip elements
        elements_response = db_client.client.table('trip_elements').select('*').eq('trip_id', trip_id).execute()
        elements = elements_response.data if elements_response.data else []

        # Check if we have cached insights (1 hour cache)
        cache_key = f"insights_{trip_id}"
        # TODO: Implement Redis caching for production
        # For now, generate fresh insights each time

        # Run rule-based detection
        detector = InsightsDetector(trip, elements)
        base_insights = detector.analyze()

        # Enhance with AI recommendations
        ai = InsightsAI()
        enhanced_insights = ai.analyze_itinerary(trip, elements, base_insights)

        # Add metadata
        result = {
            'success': True,
            'trip_id': trip_id,
            'generated_at': datetime.now().isoformat(),
            'insights': enhanced_insights,
            'counts': {
                'action_required': len(enhanced_insights.get('action_required', [])),
                'recommendations': len(enhanced_insights.get('recommendations', [])),
                'good_to_know': len(enhanced_insights.get('good_to_know', []))
            }
        }

        return jsonify(result)

    except Exception as e:
        print(f"Error generating insights: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# Auto-Update Trip Dates from Timeline
# @route: POST /api/trips/:trip_id/auto-update-dates
@app.route('/api/trips/<trip_id>/auto-update-dates', methods=['POST', 'OPTIONS'])
def auto_update_trip_dates(trip_id):
    """Auto-detect and update trip dates from timeline elements"""
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        # Verify authentication
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({'success': False, 'error': 'No authorization header'}), 401
        
        # Get all trip elements with dates
        elements_response = db_client.client.table('trip_elements').select('start_datetime').eq('trip_id', trip_id).not_('start_datetime', 'is', 'null').execute()
        
        if not elements_response.data or len(elements_response.data) == 0:
            return jsonify({'success': False, 'error': 'No timeline elements with dates found'}), 400
        
        # Find earliest and latest dates
        from datetime import datetime
        dates = [datetime.fromisoformat(el['start_datetime'].replace('Z', '+00:00')) for el in elements_response.data]
        earliest = min(dates)
        latest = max(dates)
        
        start_date = earliest.strftime('%Y-%m-%d')
        end_date = latest.strftime('%Y-%m-%d')
        
        print(f"[AUTO-UPDATE] Trip {trip_id}: {start_date} to {end_date}")
        
        # Update using service role to bypass RLS
        from supabase import create_client
        service_client = create_client(
            os.getenv('SUPABASE_URL'),
            os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        )
        
        update_response = service_client.table('trips').update({
            'start_date': start_date,
            'end_date': end_date
        }).eq('id', trip_id).execute()
        
        if update_response.data:
            return jsonify({
                'success': True,
                'trip': update_response.data[0],
                'start_date': start_date,
                'end_date': end_date
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to update trip'}), 500
            
    except Exception as e:
        print(f"[AUTO-UPDATE] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# Trip Summary for Shared Trips
# @route: GET /api/trips/shared/:token/summary
@app.route('/api/trips/shared/<share_token>/summary', methods=['GET', 'OPTIONS'])
def get_shared_trip_summary(share_token):
    """Generate AI trip summary for shared trips"""
    if request.method == 'OPTIONS':
        return '', 200

    try:
        print(f"[SUMMARY] Starting for token: {share_token[:10]}...")
        
        # Get share
        share_response = db_client.client.table('trip_shares').select('*').eq('share_token', share_token).eq('is_active', True).single().execute()
        if not share_response.data:
            return jsonify({'success': False, 'error': 'Share not found'}), 404

        trip_id = share_response.data['trip_id']
        
        # Get trip
        trip_response = db_client.client.table('trips').select('*').eq('id', trip_id).single().execute()
        if not trip_response.data:
            return jsonify({'success': False, 'error': 'Trip not found'}), 404


        trip = trip_response.data
        print(f"[SUMMARY] Trip: {trip.get('name')}, Owner: {trip.get('user_id')}")
        
        # Get elements
        elements_response = db_client.client.table('trip_elements').select('*').eq('trip_id', trip_id).execute()
        elements = elements_response.data or []
        
        # Get trip owner name FIRST
        travelers = []
        try:
            owner_id = trip.get('user_id')
            print(f"[SUMMARY] Looking up owner: {owner_id}")
            if owner_id:
                # Try to get profile with full_name or email
                owner_response = db_client.client.table('profiles').select('full_name, email').eq('id', owner_id).single().execute()
                print(f"[SUMMARY] Profile response: {owner_response.data}")
                
                if owner_response.data:
                    owner_name = owner_response.data.get('full_name')
                    if not owner_name or owner_name.strip() == '':
                        # Fallback to email username
                        email = owner_response.data.get('email', '')
                        if email:
                            owner_name = email.split('@')[0].title()
                    
                    if owner_name and owner_name.strip():
                        travelers.append(owner_name)
                        print(f"[SUMMARY] Added owner: {owner_name}")
                    else:
                        print(f"[SUMMARY] No owner name found")
                else:
                    print(f"[SUMMARY] No profile data for owner")
        except Exception as e:
            print(f"[SUMMARY] Owner error: {e}")
            import traceback
            traceback.print_exc()
        
        # Get other participants
        try:
            participants_response = db_client.client.table('trip_participants').select('participant_name, is_trip_owner').eq('trip_id', trip_id).execute()
            for p in (participants_response.data or []):
                # Skip owner - already added from profiles lookup above
                if p.get('is_trip_owner'):
                    continue
                if p.get('participant_name'):
                    travelers.append(p['participant_name'])
            print(f"[SUMMARY] All travelers: {travelers}")
        except Exception as e:
            print(f"[SUMMARY] Participants error: {e}")

        # Get destination - smart detection
        destination = trip.get('destination')
        if not destination or destination == 'None' or destination.strip() == '':
            trip_name = trip.get('name', '')
            if 'San Diego' in trip_name:
                destination = 'San Diego'
            elif 'Orlando' in trip_name:
                destination = 'Orlando'
            elif 'Disney' in trip_name:
                destination = 'Orlando'
            else:
                for e in elements:
                    if e.get('type') in ['hotel', 'flight'] and e.get('location'):
                        loc = e['location']
                        if ',' in loc:
                            parts = loc.split(',')
                            destination = parts[-2].strip() if len(parts) > 1 else parts[0].strip()
                            break
        
        if not destination or destination == 'None' or destination.strip() == '':
            destination = 'an exciting destination'
        
        print(f"[SUMMARY] Destination: {destination}")

        # Duration
        # Duration and travel dates
        from datetime import datetime
        duration_days = 7
        travel_month = None
        start_date = None
        end_date = None
        try:
            if trip.get('start_date') and trip.get('end_date'):
                s = str(trip['start_date']).split('T')[0]
                e = str(trip['end_date']).split('T')[0]
                start_date = datetime.strptime(s, '%Y-%m-%d')
                end_date = datetime.strptime(e, '%Y-%m-%d')
                duration_days = (end_date - start_date).days + 1
                travel_month = start_date.month
        except Exception as de:
            print(f"[SUMMARY] Date error: {de}")

        # Detect holidays in trip dates
        holidays = []
        if start_date and end_date:
            year = start_date.year
            holiday_dates = {
                'New Year\'s Eve': datetime(year, 12, 31),
                'New Year\'s Day': datetime(year, 1, 1),
                'Christmas': datetime(year, 12, 25),
                'Thanksgiving': datetime(year, 11, 28),
                'Fourth of July': datetime(year, 7, 4),
            }
            for holiday_name, holiday_date in holiday_dates.items():
                if start_date <= holiday_date <= end_date:
                    holidays.append(holiday_name)
            # Check next year for NYE trips
            if start_date.month == 12:
                if start_date <= datetime(year, 12, 31) <= end_date:
                    if 'New Year\'s Eve' not in holidays:
                        holidays.append('New Year\'s Eve')
                next_year_start = datetime(year + 1, 1, 1)
                if next_year_start <= end_date:
                    if 'New Year\'s Day' not in holidays:
                        holidays.append('New Year\'s Day')

        # Categorize elements - extract more detail
        activities = [el['title'] for el in elements if el.get('type') == 'activity' and el.get('title')][:4]
        dining = [el['title'] for el in elements if el.get('type') == 'dining' and el.get('title')][:3]
        hotels = [el['title'] for el in elements if el.get('type') == 'hotel' and el.get('title')][:2]

        # Count days with events to detect downtime
        days_with_events = set()
        for el in elements:
            if el.get('start_datetime'):
                try:
                    el_date = datetime.strptime(str(el['start_datetime']).split('T')[0], '%Y-%m-%d')
                    days_with_events.add(el_date.date())
                except:
                    pass

        busy_days = len(days_with_events)
        free_days = max(0, duration_days - busy_days)
        has_downtime = free_days >= 2 or (duration_days >= 5 and busy_days < duration_days * 0.7)

        print(f"[SUMMARY] Hotels: {hotels}, Activities: {activities}, Dining: {dining}")
        print(f"[SUMMARY] Holidays: {holidays}, Downtime: {has_downtime} ({free_days} free days)")

        # Build enhanced prompt
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

        traveler_str = ', '.join(travelers) if travelers else 'travelers'
        activity_str = ', '.join(activities) if activities else None
        dining_str = ', '.join(dining) if dining else None
        hotel_str = ', '.join(hotels) if hotels else None
        holiday_str = ' and '.join(holidays) if holidays else None

        # Build context
        context_parts = []
        context_parts.append(f"Travelers: {traveler_str}")
        context_parts.append(f"Destination: {destination}")
        context_parts.append(f"Duration: {duration_days} days")
        if start_date and end_date:
            context_parts.append(f"Trip dates: {start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}")
        if hotel_str:
            context_parts.append(f"Hotels: {hotel_str}")
        if activity_str:
            context_parts.append(f"Activities: {activity_str}")
        if dining_str:
            context_parts.append(f"Dining: {dining_str}")
        if holiday_str:
            context_parts.append(f"Holidays during trip: {holiday_str}")
        if has_downtime:
            context_parts.append(f"Note: Trip includes {free_days}+ days of unstructured relaxation time")

        context = '\n'.join(context_parts)

        prompt = f"""Write an engaging, evocative 3-4 sentence trip summary for sharing with friends/family.

TRIP DETAILS:
{context}

REQUIREMENTS:
1. Start with travelers' names (use nicknames if apparent, like "Roxy" for Scarlett)
2. Include weather context for the destination and travel month (e.g., "mild sunny days in the mid-60s" for San Diego in winter, "warm tropical breezes" for Hawaii)
3. If notable hotels exist, mention them by name (e.g., "luxurious stay at the legendary Hotel del Coronado")
4. Highlight balance of adventure AND relaxation/downtime if applicable
5. Use sensory, inviting language (sparkling beaches, ocean breezes, festive vibes)
6. If holidays fall during the trip, weave them in naturally (e.g., "ring in the New Year...")
7. End with an exciting hook

TONE: Warm, playful, inviting - like a friend sharing their upcoming adventure.
Keep it concise but vivid - 3-4 sentences max."""

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a talented travel writer who creates warm, vivid trip summaries. You know weather patterns for popular destinations and craft engaging narratives that make readers wish they were coming along."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=250
        )

        summary = response.choices[0].message.content.strip()
        print(f"[SUMMARY] Success: {summary[:100]}...")

        return jsonify({
            'success': True,
            'summary': summary,
            'trip_name': trip.get('name'),
            'destination': trip.get('destination'),
            'duration_days': duration_days,
            'travelers': travelers,
            'hotels': hotels,
            'holidays': holidays
        })

    except Exception as e:
        print(f"[SUMMARY] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500
# Learning Loop API Endpoints

# @route: POST /api/insights/feedback
@app.route('/api/insights/feedback', methods=['POST', 'OPTIONS'])
def submit_insight_feedback():
    """
    Record user feedback on an insight.
    Enables the self-learning loop.
    """
    if request.method == 'OPTIONS':
        return '', 200

    try:
        from talon.insights_learning import InsightsLearning

        data = request.json
        user_id = data.get('user_id')  # TODO: Get from auth session
        trip_id = data.get('trip_id')
        insight_id = data.get('insight_id')
        insight_type = data.get('insight_type')
        insight_category = data.get('insight_category')
        action_taken = data.get('action_taken')  # 'dismissed', 'acted', 'rated'

        # Optional feedback fields
        helpful = data.get('helpful')
        accurate = data.get('accurate')
        rating = data.get('rating')
        user_comment = data.get('comment')
        action_details = data.get('action_details', {})

        # Trip context for learning
        trip_context = data.get('trip_context', {})

        if not all([user_id, trip_id, insight_id, insight_type, insight_category, action_taken]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields'
            }), 400

        # Record feedback
        learning = InsightsLearning()
        feedback = learning.record_feedback(
            user_id=user_id,
            trip_id=trip_id,
            insight_id=insight_id,
            insight_type=insight_type,
            insight_category=insight_category,
            action_taken=action_taken,
            action_details=action_details,
            helpful=helpful,
            accurate=accurate,
            rating=rating,
            user_comment=user_comment,
            trip_context=trip_context
        )

        return jsonify({
            'success': True,
            'feedback_id': feedback.get('id'),
            'message': 'Feedback recorded - thank you for helping TALON learn!'
        })

    except Exception as e:
        print(f"Error recording feedback: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# @route: GET /api/insights/patterns
@app.route('/api/insights/patterns', methods=['GET'])
def get_insight_patterns():
    """
    Get learned patterns and performance metrics.
    Shows which insights are most/least helpful.
    """
    try:
        category = request.args.get('category')

        # Get patterns from database
        query = db_client.client.table('insights_patterns').select('*')
        if category:
            query = query.eq('insight_category', category)

        response = query.order('confidence_score', desc=True).execute()
        patterns = response.data if response.data else []

        return jsonify({
            'success': True,
            'patterns': patterns,
            'count': len(patterns)
        })

    except Exception as e:
        print(f"Error fetching patterns: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# @route: POST /api/insights/analyze-patterns
@app.route('/api/insights/analyze-patterns', methods=['POST', 'OPTIONS'])
def trigger_pattern_analysis():
    """
    Manually trigger pattern analysis.
    Useful for testing or scheduled jobs.
    """
    if request.method == 'OPTIONS':
        return '', 200

    try:
        from talon.insights_learning import InsightsLearning

        data = request.json or {}
        category = data.get('category')  # Optional: analyze specific category

        learning = InsightsLearning()
        results = learning.analyze_patterns(category)

        return jsonify({
            'success': True,
            'analyzed_categories': len(results),
            'results': results
        })

    except Exception as e:
        print(f"Error analyzing patterns: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# @route: GET /api/kb/learnings
@app.route('/api/kb/learnings', methods=['GET'])
def get_kb_learnings():
    """
    Get pending learnings to be reviewed and added to Knowledge Base.
    """
    try:
        from talon.insights_learning import InsightsLearning

        status = request.args.get('status', 'pending')

        query = db_client.client.table('kb_learnings').select('*')
        if status:
            query = query.eq('status', status)

        response = query.order('confidence_score', desc=True).execute()
        learnings = response.data if response.data else []

        return jsonify({
            'success': True,
            'learnings': learnings,
            'count': len(learnings)
        })

    except Exception as e:
        print(f"Error fetching KB learnings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# @route: POST /api/kb/update
@app.route('/api/kb/update', methods=['POST', 'OPTIONS'])
def update_knowledge_base():
    """
    Apply approved learnings to TALON_KNOWLEDGE_BASE.md.
    Creates backup before updating.
    """
    if request.method == 'OPTIONS':
        return '', 200

    try:
        from talon.kb_updater import KnowledgeBaseUpdater

        data = request.json or {}
        dry_run = data.get('dry_run', False)

        updater = KnowledgeBaseUpdater()
        result = updater.update_kb_with_learnings(dry_run=dry_run)

        return jsonify({
            'success': True,
            'applied': result.get('applied', 0),
            'learnings': result.get('learnings', []),
            'dry_run': dry_run,
            'message': f"Applied {result.get('applied', 0)} learnings to Knowledge Base" if not dry_run else "Dry run completed (no changes made)"
        })

    except Exception as e:
        print(f"Error updating KB: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# @route: GET /api/kb/learning-report
@app.route('/api/kb/learning-report', methods=['GET'])
def get_learning_report():
    """
    Generate a summary report of all approved learnings.
    Returns markdown format.
    """
    try:
        from talon.kb_updater import KnowledgeBaseUpdater

        updater = KnowledgeBaseUpdater()
        report = updater.generate_learning_summary_report()

        return jsonify({
            'success': True,
            'report': report,
            'format': 'markdown'
        })

    except Exception as e:
        print(f"Error generating report: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
