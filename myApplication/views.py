import requests
from django.conf import settings
from django.shortcuts import render, redirect
from django.http import JsonResponse
from .utils import get_pesapal_token
from django.core.mail import send_mail
from django.contrib import messages

# views.py
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.conf import settings
import requests
import uuid
from urllib.parse import urlencode
import hashlib
import hmac
import base64
from datetime import datetime
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import xml.etree.ElementTree as ET


def home(request):
    return render(request, 'home.html')

def payment_success(request):
    return render(request, "payment_success.html")


def initiate_payment(request):
    if request.method == "POST":
        amount = request.POST.get('amount')
        email = request.POST.get('email')

        if not amount or not email:
            return render(request, 'error.html', {'message': 'Please provide both amount and email.'})

        order_id = str(uuid.uuid4())
        request.session['order_id'] = order_id
        request.session['amount'] = amount
        request.session['email'] = email

        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        try:
            # Step 1: Get a bearer token
            auth_url = f"{settings.PESAPAL_API_URL}/api/Auth/RequestToken"
            auth_payload = {
                "consumer_key": settings.PESAPAL_CONSUMER_KEY,
                "consumer_secret": settings.PESAPAL_CONSUMER_SECRET
            }
            auth_response = requests.post(auth_url, json=auth_payload, headers=headers)
            # print(f"Auth Response Status: {auth_response.status_code}")
            # print(f"Auth Response Headers: {auth_response.headers}")
            # print(f"Auth Response Text: {auth_response.text}")

            if auth_response.status_code != 200:
                return render(request, 'error.html', {'message': f'Failed to authenticate with Pesapal: {auth_response.text}'})

            token_data = auth_response.json()
            if token_data.get('status') != '200':
                return render(request, 'error.html', {'message': f'Authentication error: {token_data.get("error", "Unknown error")}'})

            access_token = token_data.get('token')
            if not access_token:
                return render(request, 'error.html', {'message': 'No access token received from Pesapal.'})

            # Step 2: Register the IPN URL to get notification_id
            ipn_url = f"{settings.PESAPAL_API_URL}/api/URLSetup/RegisterIPN"
            ipn_payload = {
                "url": settings.PESAPAL_IPN_URL,
                "ipn_notification_type": "POST"
            }
            headers['Authorization'] = f'Bearer {access_token}'
            ipn_response = requests.post(ipn_url, json=ipn_payload, headers=headers)
            # print(f"IPN Registration Status: {ipn_response.status_code}")
            # print(f"IPN Registration Headers: {ipn_response.headers}")
            # print(f"IPN Registration Text: {ipn_response.text}")

            if ipn_response.status_code != 200:
                return render(request, 'error.html', {'message': f'Failed to register IPN URL: {ipn_response.text}'})

            ipn_data = ipn_response.json()
            if ipn_data.get('status') != '200':
                return render(request, 'error.html', {'message': f'IPN registration error: {ipn_data.get("error", "Unknown error")}'})

            notification_id = ipn_data.get('ipn_id')
            if not notification_id:
                return render(request, 'error.html', {'message': 'No notification ID received from Pesapal.'})

            # Step 3: Submit the order with the notification_id
            order_url = f"{settings.PESAPAL_API_URL}/api/Transactions/SubmitOrderRequest"
            order_payload = {
                "id": order_id,
                "currency": "KES",
                "amount": float(amount),
                "description": "Donation to Organization",
                "callback_url": settings.PESAPAL_CALLBACK_URL,
                "notification_id": notification_id,  # Use the obtained ID
                "email_address": email,
                "billing_address": {
                    "email_address": email
                }
            }
            order_response = requests.post(order_url, json=order_payload, headers=headers)
            # print(f"Order Response Status: {order_response.status_code}")
            # print(f"Order Response Headers: {order_response.headers}")
            # print(f"Order Response Text: {order_response.text}")

            if order_response.status_code == 200:
                order_data = order_response.json()
                if order_data.get('status') != '200':
                    return render(request, 'error.html', {'message': f'Order submission error: {order_data.get("error", "Unknown error")}'})

                redirect_url = order_data.get('redirect_url')
                if not redirect_url or not redirect_url.startswith('http'):
                    return render(request, 'error.html', {'message': 'Invalid redirect URL from Pesapal.'})
                return redirect(redirect_url)
            else:
                return render(request, 'error.html', {'message': f'Error initiating payment: Status {order_response.status_code} - {order_response.text}'})

        except requests.exceptions.RequestException as e:
            return render(request, 'error.html', {'message': f'Error initiating payment: {str(e)}'})

    return render(request, 'donation_form.html')

@csrf_exempt
def payment_callback(request):
    if request.method == "GET":
        # Extract query parameters (Pesapal API v3 uses OrderTrackingId and OrderMerchantReference)
        order_id = request.GET.get('OrderMerchantReference')
        tracking_id = request.GET.get('OrderTrackingId')

        # Log the received parameters for debugging
        # print(f"Callback Parameters: OrderMerchantReference={order_id}, OrderTrackingId={tracking_id}")

        # Verify the order ID matches the one in the session
        session_order_id = request.session.get('order_id')
        # print(f"Session Order ID: {session_order_id}")

        if not order_id or order_id != session_order_id:
            return render(request, 'error.html', {'message': 'Invalid transaction reference.'})
        
        amount = request.session.get('amount')
        email = request.session.get('email')

        # Step 1: Get a bearer token (same as in initiate_payment)
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        auth_url = f"{settings.PESAPAL_API_URL}/api/Auth/RequestToken"
        auth_payload = {
            "consumer_key": settings.PESAPAL_CONSUMER_KEY,
            "consumer_secret": settings.PESAPAL_CONSUMER_SECRET
        }
        auth_response = requests.post(auth_url, json=auth_payload, headers=headers)
        # print(f"Auth Response: {auth_response.status_code} - {auth_response.text}")

        if auth_response.status_code != 200:
            return render(request, 'error.html', {'message': 'Failed to authenticate with Pesapal to check transaction status'})

        token_data = auth_response.json()
        access_token = token_data.get('token')
        if not access_token:
            return render(request, 'error.html', {'message': 'No access token received from Pesapal'})

        # Step 2: Query transaction status
        status_url = f"{settings.PESAPAL_API_URL}/api/Transactions/GetTransactionStatus"
        status_params = {
            "orderTrackingId": tracking_id
        }
        headers['Authorization'] = f'Bearer {access_token}'
        status_response = requests.get(status_url, params=status_params, headers=headers)
        # print(f"Transaction Status Response: {status_response.status_code} - {status_response.text}")

        if status_response.status_code == 200:
            status_data = status_response.json()
            transaction_status = status_data.get('payment_status_description', 'UNKNOWN')  # e.g., "COMPLETED", "FAILED", "PENDING"
        else:
            transaction_status = "UNKNOWN"

        # Display confirmation to the user
        context = {
            'message': 'Thank you for your donation!',
            'order_id': order_id,
            'tracking_id': tracking_id,
            'transaction_status': transaction_status,
            'amount':amount,
            'email':email,
        }
        return render(request, 'thank_you.html', context)

    return JsonResponse({'status': 'Invalid request'})


@csrf_exempt
def ipn_callback(request):
    if request.method == "GET":
        # Pesapal API v3 sends IPN notifications via GET with query parameters
        notification_type = request.GET.get('notification_type')
        order_id = request.GET.get('order_merchant_reference')
        tracking_id = request.GET.get('order_tracking_id')

        # print(f"IPN Parameters: notification_type={notification_type}, order_merchant_reference={order_id}, order_tracking_id={tracking_id}")

        if notification_type == 'CHANGE' and order_id and tracking_id:
            # Step 1: Get a bearer token
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            auth_url = f"{settings.PESAPAL_API_URL}/api/Auth/RequestToken"
            auth_payload = {
                "consumer_key": settings.PESAPAL_CONSUMER_KEY,
                "consumer_secret": settings.PESAPAL_CONSUMER_SECRET
            }
            auth_response = requests.post(auth_url, json=auth_payload, headers=headers)
            # print(f"IPN Auth Response: {auth_response.status_code} - {auth_response.text}")

            if auth_response.status_code != 200:
                return HttpResponse('error')

            token_data = auth_response.json()
            access_token = token_data.get('token')
            if not access_token:
                return HttpResponse('error')

            # Step 2: Query transaction status
            status_url = f"{settings.PESAPAL_API_URL}/api/Transactions/GetTransactionStatus"
            status_params = {
                "orderTrackingId": tracking_id
            }
            headers['Authorization'] = f'Bearer {access_token}'
            status_response = requests.get(status_url, params=status_params, headers=headers)
            # print(f"IPN Transaction Status Response: {status_response.status_code} - {status_response.text}")

            if status_response.status_code == 200:
                status_data = status_response.json()
                transaction_status = status_data.get('status')  # e.g., "COMPLETED", "FAILED", "PENDING"
                # print(f"IPN Update: Order {order_id}, Status: {transaction_status}")
                # Update your database with the transaction status
                # Example: donation = Donation.objects.get(order_id=order_id); donation.status = transaction_status; donation.save()
                return HttpResponse('success')
            return HttpResponse('error')

    return HttpResponse('invalid')



def contact_form(request):
    if request.method == 'POST':
        # print("POST received")
        name = request.POST.get('name')
        email = request.POST.get('email')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        email_content = f"From: {name} <{email}>\nSubject: {subject}\n\nMessage:\n{message}"
        try:
            send_mail(
                subject=subject,
                message=email_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.CONTACT_EMAIL],
                fail_silently=False,
            )
            messages.success(request, 'Email sent successfully!')
            return redirect('home')  # Redirect to home.html
            # print("Email sent")
            # return render(request, 'home.html', {'sent': True})
        except Exception as e:
            messages.error(request, f'Failed to send email: {e}')
            return redirect('contact')  # Redirect back with error
            # print(f"Email error: {e}")
            # return render(request, 'home.html', {'error': True})
    # print("GET received")
    return render(request, 'base.html')
