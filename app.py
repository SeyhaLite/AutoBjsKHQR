# app.py
# This Flask application provides a web server with an API for your BJS bot.
# កម្មវិធី Flask នេះផ្តល់ម៉ាស៊ីនមេគេហទំព័រជាមួយនឹង API សម្រាប់ BJS bot របស់អ្នក។

from flask import Flask, request, jsonify, render_template_string
import requests
import qrcode
from io import BytesIO
import base64
import logging
import threading
import time
from datetime import datetime, timedelta
import json

app = Flask(__name__)

# --- Configuration ---
# IMPORTANT: Replace "YOUR_BAKONG_API_TOKEN" with your actual Bakong API token.
# សំខាន់: ជំនួស "YOUR_BAKONG_API_TOKEN" ដោយ Bakong API token ពិតប្រាកដរបស់អ្នក។
BAKONG_API_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7ImlkIjoiYjljMWE3MjE3ZWQ4NGRhIn0sImlhdCI6MTc1NDExNTUyOCwiZXhwIjoxNzYxODkxNTI4fQ.Ad-_Z_jUtsxiiEAY--bvtPMaiabVDYEc1C1ES-ctHaU"
BAKONG_CREATE_QR_URL = "https://api.bakong.nbc.gov.kh/v1/qr"
BAKONG_CHECK_STATUS_URL = "https://api.bakong.nbc.gov.kh/v1/transaction/status"

pending_payments = {}

logging.basicConfig(level=logging.INFO)

def create_qr_data_uri(qr_data):
    """
    Generates a QR code image as a base64 encoded data URI.
    បង្កើតរូបភាព QR code ជា base64 encoded data URI។
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffered.getvalue()).decode('utf-8')

def payment_status_checker():
    """
    Background thread to automatically check the status of pending payments.
    This runs every 6 seconds for a total of 3 minutes.
    """
    logging.info("Starting payment status checker thread...")
    while True:
        invoices_to_check = list(pending_payments.keys())
        
        for invoice_id in invoices_to_check:
            payment = pending_payments.get(invoice_id)
            if not payment:
                continue

            if datetime.now() > payment['expires_at']:
                logging.warning(f"Payment for invoice {invoice_id} expired. Removing.")
                del pending_payments[invoice_id]
                continue

            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {BAKONG_API_TOKEN}'
            }
            
            try:
                response = requests.get(
                    f"{BAKONG_CHECK_STATUS_URL}/{payment['transaction_id']}",
                    headers=headers
                )
                response.raise_for_status()
                result = response.json()

                if result.get('status') == 'completed':
                    logging.info(f"Payment successful for invoice {invoice_id}. Notifying bot...")
                    
                    bjs_webhook_url = payment['webhook_url']
                    webhook_data = {
                        'user_id': payment['user_id'],
                        'amount': payment['amount'],
                        'invoice_id': invoice_id
                    }
                    
                    try:
                        # Call the BJS webhook to notify the bot about the successful payment
                        requests.post(bjs_webhook_url, json=webhook_data)
                        logging.info(f"Webhook sent successfully for invoice {invoice_id}.")
                    except requests.exceptions.RequestException as e:
                        logging.error(f"Failed to send webhook for invoice {invoice_id}: {e}")
                    
                    del pending_payments[invoice_id]
                else:
                    logging.info(f"Payment for invoice {invoice_id} is still pending. Status: {result.get('status')}")
            
            except requests.exceptions.RequestException as e:
                logging.error(f"Error checking status for invoice {invoice_id}: {e}")
                
        time.sleep(6)

@app.route('/')
def home():
    """
    Endpoint for the web server's homepage with a smooth UI.
    Endpoint សម្រាប់ទំព័រដើមរបស់ web server ជាមួយនឹង UI រលូន។
    """
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Bakong KHQR Payments</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
            body {
                font-family: 'Inter', sans-serif;
            }
        </style>
    </head>
    <body class="bg-slate-900 text-slate-100 min-h-screen flex items-center justify-center p-4">
        <div class="bg-slate-800 rounded-2xl shadow-2xl p-8 w-full max-w-md border border-slate-700 text-center">
            <h1 class="text-3xl font-bold text-white mb-4">Bakong KHQR Payments</h1>
            <p class="text-lg text-slate-400 mb-6">
                This server handles payment requests for your Telegram Bot.
            </p>
            <p class="text-slate-400">
                To generate a payment QR code, please use the `/pay` command in your bot.
            </p>
            <a href="https://t.me/bots_business" class="mt-8 inline-block bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 px-6 rounded-xl shadow-lg transition-transform transform hover:scale-105">
                Go to the Bot
            </a>
        </div>
    </body>
    </html>
    """)

@app.route('/generate_qr', methods=['GET'])
def generate_qr():
    """
    Endpoint to generate a KHQR code for payment.
    Endpoint សម្រាប់បង្កើត KHQR code សម្រាប់ការទូទាត់។
    """
    try:
        user_id = request.args.get('user_id')
        amount = float(request.args.get('amount'))
        invoice_id = request.args.get('invoice_id')
        webhook_url = request.args.get('webhook_url')

        if not all([user_id, amount, invoice_id, webhook_url]):
            return "Missing parameters", 400

        payload = {
            "merchant": { "name": "My Bot Business" },
            "transaction_amount": amount,
            "currency": "USD",
            "type": "pay"
        }

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {BAKONG_API_TOKEN}'
        }

        response = requests.post(BAKONG_CREATE_QR_URL, headers=headers, json=payload)
        response.raise_for_status()
        
        bakong_data = response.json()
        qr_code_data = bakong_data['qr_code']
        transaction_id = bakong_data['transaction_id']

        expires_at = datetime.now() + timedelta(minutes=3)
        pending_payments[invoice_id] = {
            'user_id': user_id,
            'amount': amount,
            'webhook_url': webhook_url,
            'transaction_id': transaction_id,
            'expires_at': expires_at
        }
        
        logging.info(f"Generated QR for user {user_id}, invoice {invoice_id}.")
        
        qr_data_uri = create_qr_data_uri(qr_code_data)
        
        # HTML for QR code page, same as before for consistency and good UX
        # HTML សម្រាប់ទំព័រ QR code, ដូចមុនសម្រាប់ភាពស្របគ្នា និង UX ល្អ
        html_content = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>QR Code Payment</title>
            <script src="https://cdn.tailwindcss.com"></script>
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
                body {
                    font-family: 'Inter', sans-serif;
                }
            </style>
        </head>
        <body class="bg-slate-900 text-slate-100 min-h-screen flex items-center justify-center p-4">
            <div class="bg-slate-800 rounded-2xl shadow-2xl p-8 w-full max-w-sm border border-slate-700">
                <h1 class="text-2xl font-bold text-center text-white mb-2">Scan to Pay</h1>
                <p class="text-center text-slate-400 mb-6">Amount: <span class="font-extrabold text-white">${{ amount }}</span> USD</p>
                
                <div class="flex justify-center mb-6">
                    <img src="{{ qr_data_uri }}" alt="QR Code" class="w-56 h-56 p-4 bg-white rounded-xl shadow-inner transition-transform transform hover:scale-105">
                </div>
                
                <div class="text-center text-slate-400 font-medium mb-4">
                    <p>Expires in: <span id="countdown" class="text-red-400 font-bold"></span></p>
                </div>

                <div class="flex flex-col space-y-2">
                    <button id="copy-button" class="bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 px-4 rounded-xl shadow-lg transition-transform transform hover:scale-105 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-opacity-50">
                        Copy Payment Link
                    </button>
                    <p id="copy-message" class="text-emerald-400 text-sm text-center font-medium hidden transition-opacity opacity-0">Link copied to clipboard!</p>
                </div>

                <textarea id="qr-data-text" class="absolute left-[-9999px]"></textarea>
            </div>

            <script>
                const expiresAt = new Date("{{ expires_at }}");
                const countdownEl = document.getElementById('countdown');
                const copyButton = document.getElementById('copy-button');
                const copyMessage = document.getElementById('copy-message');
                const qrDataText = document.getElementById('qr-data-text');

                // Set the QR data into the textarea for copying
                qrDataText.value = "{{ qr_code_data }}";

                function updateCountdown() {
                    const now = new Date();
                    const timeLeft = expiresAt - now;
                    if (timeLeft <= 0) {
                        countdownEl.textContent = "Expired!";
                        clearInterval(countdownInterval);
                        return;
                    }
                    const minutes = Math.floor((timeLeft % (1000 * 60 * 60)) / (1000 * 60));
                    const seconds = Math.floor((timeLeft % (1000 * 60)) / 1000);
                    countdownEl.textContent = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
                }
                const countdownInterval = setInterval(updateCountdown, 1000);
                updateCountdown();
                
                copyButton.addEventListener('click', () => {
                    qrDataText.select();
                    qrDataText.setSelectionRange(0, 99999); // For mobile devices
                    document.execCommand('copy');
                    
                    copyMessage.classList.remove('hidden');
                    copyMessage.classList.add('opacity-100');
                    setTimeout(() => {
                        copyMessage.classList.remove('opacity-100');
                        copyMessage.classList.add('opacity-0');
                        setTimeout(() => copyMessage.classList.add('hidden'), 500);
                    }, 2000);
                });
            </script>
        </body>
        </html>
        """
        
        return render_template_string(html_content, 
            amount=amount, 
            qr_data_uri=qr_data_uri,
            qr_code_data=qr_code_data, 
            expires_at=expires_at.isoformat()
        )

    except requests.exceptions.RequestException as e:
        logging.error(f"Bakong API request failed: {e}")
        return jsonify({"error": "Failed to generate QR code. Please try again."}), 500
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return jsonify({"error": "An unexpected error occurred."}), 500

payment_checker_thread = threading.Thread(target=payment_status_checker, daemon=True)
payment_checker_thread.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)



