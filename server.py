from flask import Flask, render_template, jsonify
from flask import request
import json
import random
from api.AuthorizedModules import EInvoiceAuthenticator
import os
import dotenv
from datetime import datetime, timedelta

app = Flask(__name__)

dotenv.load_dotenv()
api = EInvoiceAuthenticator(
            os.getenv("EINVOICE_USERNAME"),
            os.getenv("EINVOICE_PASSWORD")
        )

today = datetime.today()
RESULT_FILE = f"save_result/{today.strftime('%Y_%m')}_result.json"
PREVIOUS_RESULT_FILE = f"save_result/{(today.replace(day=1) - timedelta(days=1)).strftime('%Y_%m')}_result.json"

os.makedirs("save_result", exist_ok=True)

def save_result(data, filename=RESULT_FILE):
    with open(filename, 'w') as f:
        json.dump(data, f)

def load_result():
    try:
        with open(RESULT_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        return {"result": "No result yet."}

def get_data(frist_day, last_day):
    token = api.getSearchCarrierInvoiceListJWT(frist_day, last_day)
    if not token:
        return None

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
    return {"content": all_items, "total": total}


@app.route('/')
def index():
    return render_template('index.html', result=load_result())

@app.route('/run', methods=['POST'])
def run_script():
    today = datetime.today()
    first_day_of_month = today.replace(day=1)
    first_day_of_last_month= (first_day_of_month - timedelta(days=1)).replace(day=1)
    """
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
    """
    result = get_data(first_day_of_month, today)
    if not result:
        return jsonify({"error": "Failed to retrieve data."}), 500
    all_items = result['content']
    total = result['total']
    save_result({"content": all_items, "total": total})

    # Also get last month's data
    result_last_month = get_data(first_day_of_last_month, first_day_of_month - timedelta(days=1))
    if result_last_month:
        all_items_last_month = result_last_month['content']
        total_last_month = result_last_month['total']
        print( "Last month's total:", total_last_month)
        save_result({"content": all_items_last_month, "total": total_last_month}, filename=PREVIOUS_RESULT_FILE)       


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
