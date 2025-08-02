# This Python code is for an external server that handles KHQR generation and payment verification.
# This code is NOT meant to be run in BJS. It requires a server environment (e.g., a virtual machine).
# កូដ Python នេះគឺសម្រាប់ server ខាងក្រៅដែលគ្រប់គ្រងការបង្កើត KHQR និងការផ្ទៀងផ្ទាត់ការទូទាត់។
# កូដនេះមិនត្រូវបានរចនាឡើងដើម្បីដំណើរការនៅក្នុង BJS ទេ។ វាទាមទារបរិស្ថាន server (ឧទាហរណ៍ ម៉ាស៊ីននិម្មិត)។

import os
import requests
import qrcode
import base64
from flask import Flask, request, render_template_string
from bakong_khqr import KHQR # Make sure this library is installed.
import time
import threading

app = Flask(__name__)

# --- IMPORTANT ---
# REPLACE with your Bakong API Token provided in the user prompt.
# ជំនួសដោយ Bakong API Token ពិតប្រាកដរបស់អ្នកដែលបានផ្ដល់ក្នុងសំណើរបស់អ្នកប្រើប្រាស់។
API_TOKEN_BAKONG = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7ImlkIjoiYjljMWE3MjE3ZWQ4NGRhIn0sImlhdCI6MTc1NDExNTUyOCwiZXhwIjoxNzYxODkxNTI4fQ.Ad-_Z_jUtsxiiEAY--bvtPMaiabVDYEc1C1ES-ctHaU"
khqr_client = KHQR(API_TOKEN_BAKONG)
# ---

# A simple in-memory store for pending transactions. In a production app, use a database.
# កន្លែងរក្សាទុកបណ្ដោះអាសន្នសម្រាប់ប្រតិបត្តិការដែលកំពុងរង់ចាំ។ នៅក្នុងកម្មវិធីផលិតកម្ម សូមប្រើប្រាស់មូលដ្ឋានទិន្នន័យ។
pending_transactions = {}

# HTML template to display the QR code.
# គំរូ HTML ដើម្បីបង្ហាញ QR code។
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>KHQR Payment</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }
        .container { max-width: 400px; margin: auto; padding: 20px; border: 1px solid #ccc; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
        .qr-code { width: 100%; height: auto; }
        .status { margin-top: 20px; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <h2>Scan to Pay with KHQR</h2>
        <p>Invoice ID: <strong>{{ invoice_id }}</strong></p>
        <p>Amount: <strong>{{ amount }} USD</strong></p>
        <img class="qr-code" src="data:image/png;base64,{{ qr_code_b64 }}" alt="KHQR Code">
        <div id="status" class="status">Waiting for payment...</div>
    </div>

    <script>
        // Use JavaScript to poll the server for payment status.
        // ប្រើ JavaScript ដើម្បីសាកសួរ server សម្រាប់ស្ថានភាពទូទាត់។
        function checkPaymentStatus() {
            fetch(`/payment_status/{{ invoice_id }}`)
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'SUCCESS') {
                        document.getElementById('status').innerText = '✅ Payment successful! You can now return to the bot.';
                        // You can also hide the QR code and stop polling.
                    } else if (data.status === 'PENDING') {
                        document.getElementById('status').innerText = 'Waiting for payment...';
                        setTimeout(checkPaymentStatus, 3000); // Check again in 3 seconds.
                    } else {
                        document.getElementById('status').innerText = '❌ Payment failed or not found.';
                    }
                })
                .catch(error => {
                    console.error('Error checking payment status:', error);
                    document.getElementById('status').innerText = 'Error checking status.';
                });
        }
        window.onload = checkPaymentStatus;
    </script>
</body>
</html>
"""

def verify_and_notify(user_id, invoice_id, amount, webhook_url):
    """
    This function continuously checks the payment status.
    In a real app, you would use a proper webhook from the payment gateway instead of polling.
    មុខងារនេះពិនិត្យមើលស្ថានភាពទូទាត់ជាបន្តបន្ទាប់។
    នៅក្នុងកម្មវិធីពិតប្រាកដ អ្នកនឹងប្រើ webhook ពីច្រកទូទាត់ប្រាក់ជំនួសឱ្យការសាកសួរ។
    """
    max_checks = 20 # Check for about 1 minute (20 * 3 seconds)
    for _ in range(max_checks):
        try:
            # Simulate checking the payment status. Replace this with your actual verification logic.
            # ក្លែងធ្វើការពិនិត្យស្ថានភាពទូទាត់។ ជំនួសនេះដោយតក្កវិជ្ជាផ្ទៀងផ្ទាត់ពិតប្រាកដរបស់អ្នក។
            # Example using a hypothetical verification API:
            # verification_response = khqr_client.verify_transaction(invoice_id)
            # if verification_response['status'] == 'SUCCESS':
            
            # For this example, we'll just check our pending_transactions store.
            if pending_transactions.get(invoice_id, {}).get('status') == 'SUCCESS':
                print(f"Payment successful for invoice {invoice_id}. Notifying BJS bot.")
                # Send webhook to the BJS bot.
                # ផ្ញើ webhook ទៅកាន់ Bot BJS។
                payload = {
                    'user_id': user_id,
                    'amount': amount,
                    'invoice_id': invoice_id
                }
                requests.post(webhook_url, json=payload)
                break
        except Exception as e:
            print(f"Error during verification or webhook call: {e}")
        time.sleep(3) # Wait 3 seconds before checking again.

@app.route('/generate_qr', methods=['GET'])
def generate_qr():
    user_id = request.args.get('user_id')
    amount_str = request.args.get('amount')
    invoice_id = request.args.get('invoice_id')
    webhook_url = request.args.get('webhook_url')

    if not all([user_id, amount_str, invoice_id, webhook_url]):
        return "Missing required parameters.", 400

    try:
        amount = float(amount_str)
    except ValueError:
        return "Invalid amount format.", 400

    # In a real app, generate the QR code using your KHQR client.
    # នៅក្នុងកម្មវិធីពិតប្រាកដ សូមបង្កើត QR code ដោយប្រើ client KHQR របស់អ្នក។
    # qr_string = khqr_client.generate_qr(amount, invoice_id)
    qr_string = f"This is a placeholder for KHQR code data for invoice {invoice_id} and amount {amount}."

    # Create a QR code image from the string.
    # បង្កើតរូបភាព QR code ពី string ។
    img = qrcode.make(qr_string)
    img_byte_arr = img.save(f"qr_{invoice_id}.png") # Save to a file to show it works.
    
    # Encode the QR code image to a base64 string for display in HTML.
    # បម្លែងរូបភាព QR code ទៅជា base64 string សម្រាប់បង្ហាញក្នុង HTML។
    from io import BytesIO
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    qr_code_b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

    # Store transaction details for status checking (in a real app, use a DB).
    # រក្សាទុកព័ត៌មានលម្អិតនៃប្រតិបត្តិការសម្រាប់ការពិនិត្យស្ថានភាព (នៅក្នុងកម្មវិធីពិតប្រាកដ សូមប្រើ DB)។
    pending_transactions[invoice_id] = {
        'user_id': user_id,
        'amount': amount,
        'status': 'PENDING'
    }

    # Start a background thread to check for payment completion and notify the BJS bot.
    # ចាប់ផ្តើម thread ផ្ទៃខាងក្រោយដើម្បីពិនិត្យមើលការទូទាត់ដែលបានបញ្ចប់ និងជូនដំណឹងដល់ Bot BJS។
    thread = threading.Thread(target=verify_and_notify, args=(user_id, invoice_id, amount, webhook_url))
    thread.daemon = True
    thread.start()

    # Render the QR code page.
    # បង្ហាញទំព័រ QR code។
    return render_template_string(HTML_TEMPLATE,
                                  qr_code_b64=qr_code_b64,
                                  invoice_id=invoice_id,
                                  amount=amount)

@app.route('/payment_status/<invoice_id>')
def payment_status(invoice_id):
    """
    This endpoint is polled by the HTML page to get the payment status.
    Endpoint នេះត្រូវបានសាកសួរដោយទំព័រ HTML ដើម្បីទទួលបានស្ថានភាពទូទាត់។
    """
    transaction = pending_transactions.get(invoice_id)
    if transaction:
        return {'status': transaction['status']}
    return {'status': 'NOT_FOUND'}

@app.route('/simulate_payment_success/<invoice_id>')
def simulate_payment_success(invoice_id):
    """
    A temporary endpoint to manually simulate a successful payment for testing.
    Endpoint បណ្តោះអាសន្នដើម្បីក្លែងធ្វើការទូទាត់ជោគជ័យដោយដៃសម្រាប់ការសាកល្បង។
    """
    if invoice_id in pending_transactions:
        pending_transactions[invoice_id]['status'] = 'SUCCESS'
        return {'message': 'Payment status updated to SUCCESS.'}
    return {'message': 'Invoice not found.'}, 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
