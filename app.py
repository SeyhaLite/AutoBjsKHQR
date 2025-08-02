from flask import Flask, render_template_string, request, jsonify
import qrcode
from qrcode.image.pil import PilImage
import base64
import io
import sqlite3
import time
import os

app = Flask(__name__)

# ==============================================================================
# Database Setup
# Use a simple SQLite database for this example.
# ==============================================================================
def init_db():
    conn = sqlite3.connect('payments.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id TEXT PRIMARY KEY,
            qr_data TEXT NOT NULL,
            status TEXT NOT NULL,
            expiry_timestamp INTEGER NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# Initialize the database when the application starts
init_db()

# ==============================================================================
# HTML Template String
# This is the single page the application will render.
# ==============================================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>QR Code Payment</title>
    <!-- Tailwind CSS for a modern and clean UI -->
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap');
        body {
            font-family: 'Inter', sans-serif;
            background-color: #f3f4f6;
        }
    </style>
</head>
<body class="flex items-center justify-center min-h-screen p-4">
    <div class="bg-white rounded-3xl shadow-2xl p-8 max-w-sm w-full text-center">
        <h1 class="text-3xl font-bold text-gray-800 mb-2">Scan to Pay</h1>
        <p class="text-gray-500 mb-6">Your payment QR code will expire in:</p>
        <div id="timer" class="text-5xl font-bold text-red-500 mb-8">3:00</div>
        
        <div class="p-4 bg-gray-100 rounded-2xl mb-8">
            <img id="qr-code" src="data:image/png;base64,{{ qr_code_base64 }}" 
                 alt="QR Code" class="w-full h-auto rounded-xl shadow-lg">
        </div>
        
        <div id="status-display" class="bg-yellow-100 text-yellow-800 font-medium px-4 py-3 rounded-xl">
            ⏳ Waiting for payment...
        </div>
    </div>

    <script>
        const transactionId = "{{ transaction_id }}";
        const expiryTimestamp = parseInt("{{ expiry_timestamp }}", 10);
        let timerInterval;

        function updateTimer() {
            const now = Math.floor(Date.now() / 1000);
            const timeLeft = expiryTimestamp - now;
            const timerElement = document.getElementById('timer');

            if (timeLeft <= 0) {
                clearInterval(timerInterval);
                timerElement.textContent = 'Expired';
                document.getElementById('status-display').className = 'bg-red-100 text-red-800 font-medium px-4 py-3 rounded-xl';
                document.getElementById('status-display').textContent = '❌ QR code expired.';
                return;
            }

            const minutes = Math.floor(timeLeft / 60);
            const seconds = timeLeft % 60;
            timerElement.textContent = `${minutes}:${seconds < 10 ? '0' : ''}${seconds}`;
        }

        function checkPaymentStatus() {
            fetch(`/check_status/${transactionId}`)
                .then(response => response.json())
                .then(data => {
                    const statusDisplay = document.getElementById('status-display');
                    if (data.status === 'completed') {
                        clearInterval(timerInterval);
                        statusDisplay.className = 'bg-green-100 text-green-800 font-medium px-4 py-3 rounded-xl';
                        statusDisplay.textContent = '✅ Payment completed! Thank you.';
                        document.getElementById('timer').textContent = '0:00';
                    } else if (data.status === 'expired') {
                        clearInterval(timerInterval);
                        statusDisplay.className = 'bg-red-100 text-red-800 font-medium px-4 py-3 rounded-xl';
                        statusDisplay.textContent = '❌ QR code expired.';
                    } else {
                        statusDisplay.className = 'bg-yellow-100 text-yellow-800 font-medium px-4 py-3 rounded-xl';
                        statusDisplay.textContent = '⏳ Waiting for payment...';
                    }
                })
                .catch(error => {
                    console.error('Error checking status:', error);
                });
        }

        // Run on page load
        updateTimer();
        timerInterval = setInterval(updateTimer, 1000);
        
        // Auto-check payment status every 5 seconds
        setInterval(checkPaymentStatus, 5000);
    </script>
</body>
</html>
"""

# ==============================================================================
# Routes
# ==============================================================================
@app.route('/')
def qr_code_page():
    qr_data = request.args.get('qr_data')
    if not qr_data:
        return "Error: `qr_data` parameter is missing.", 400
    
    # Generate a unique ID for this transaction
    transaction_id = str(int(time.time() * 1000))
    
    # Store transaction data in the database (3-minute expiration)
    expiry_timestamp = int(time.time()) + 180
    conn = sqlite3.connect('payments.db')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO transactions (transaction_id, qr_data, status, expiry_timestamp) VALUES (?, ?, ?, ?)",
        (transaction_id, qr_data, "pending", expiry_timestamp)
    )
    conn.commit()
    conn.close()

    # Generate QR code image as a Base64 string
    img_buffer = io.BytesIO()
    qr_img = qrcode.make(qr_data, image_factory=PilImage)
    qr_img.save(img_buffer, format="PNG")
    qr_code_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')

    return render_template_string(HTML_TEMPLATE, 
                                  qr_code_base64=qr_code_base64,
                                  transaction_id=transaction_id,
                                  expiry_timestamp=expiry_timestamp)

@app.route('/check_status/<transaction_id>')
def check_status(transaction_id):
    conn = sqlite3.connect('payments.db')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT status, expiry_timestamp FROM transactions WHERE transaction_id = ?",
        (transaction_id,)
    )
    result = cursor.fetchone()
    conn.close()

    if not result:
        return jsonify({"status": "not_found"}), 404

    status, expiry_timestamp = result
    now = int(time.time())
    
    if now > expiry_timestamp and status == "pending":
        return jsonify({"status": "expired"})
    
    return jsonify({"status": status})

@app.route('/simulate_payment/<transaction_id>')
def simulate_payment(transaction_id):
    conn = sqlite3.connect('payments.db')
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE transactions SET status = 'completed' WHERE transaction_id = ?",
        (transaction_id,)
    )
    conn.commit()
    conn.close()
    return f"Transaction {transaction_id} marked as **completed** for testing."

# ==============================================================================
# Main Entry Point
# ==============================================================================
if __name__ == '__main__':
    # Use Gunicorn for production on Render
    # For local testing, app.run() is fine.
    # On Render, the `gunicorn app:app` command will be used.
    # The `os.environ.get('PORT')` is important for Render deployment.
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
