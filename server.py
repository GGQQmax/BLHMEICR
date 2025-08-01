from flask import Flask, render_template, jsonify
from flask import request
import json
import random
from api.AuthorizedModules import EInvoiceAuthenticator
import os
import dotenv
from datetime import datetime

app = Flask(__name__)

dotenv.load_dotenv()
api = EInvoiceAuthenticator(
            os.getenv("EINVOICE_USERNAME"),
            os.getenv("EINVOICE_PASSWORD")
        )

RESULT_FILE = 'result.json'

def save_result(data):
    with open(RESULT_FILE, 'w') as f:
        json.dump(data, f)

def load_result():
    try:
        with open(RESULT_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        return {"result": "No result yet."}

@app.route('/')
def index():
    return render_template('index.html', result=load_result())

@app.route('/run', methods=['POST'])
def run_script():
    today = datetime.today()
    first_day_of_month = today.replace(day=1)
    token = api.getSearchCarrierInvoiceListJWT(first_day_of_month, today)
    if not token:
        return jsonify({"error": "Failed to retrieve token."}), 500

    print("Token retrieved successfully:", token)

    all_items = []
    page = 0
    while True:
        data = api.searchCarrierInvoice(token, page=page, size=100)  # You must support page param in the API
        if 'content' not in data:
            break
        all_items.extend(data['content'])

        if data.get('last', True):  # When it's the last page
            break
        page += 1

    total = sum(int(item['totalAmount']) for item in all_items)
    save_result({"content": all_items, "total": total})

    return jsonify({
        "content": all_items,
        "total": total
    })


@app.route('/token_page')
def token_page():
    token = request.args.get('q')
    page = int(request.args.get('page', 0))

    if not token:
        return "Token missing", 400

    data = api.getCarrierInvoiceDetail(token,page)
    print("Data retrieved successfully:", data)
    if not data:
        return "No data found for the provided token", 404

    return render_template('token_result.html', token=token, data=data)

@app.route('/result', methods=['GET'])
def get_result():
    return jsonify(load_result())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
