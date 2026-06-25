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

def save_result(data, filename=RESULT_FILE):#Secruity Note: This should be only modified to accept year_month parameter not by any other api.
    with open(filename, 'w') as f:
        json.dump(data, f)

def load_result():
    try:
        with open(RESULT_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        return {"result": "No result yet."}

SELLER_TYPES_FILE = "save_result/seller_types.json"

def load_seller_types():
    if os.path.exists(SELLER_TYPES_FILE):
        try:
            with open(SELLER_TYPES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_seller_types(data):
    try:
        with open(SELLER_TYPES_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except Exception:
        return False

MANUAL_INVOICES_FILE = "save_result/user_manual_invoices.json"

def load_manual_invoices():
    if os.path.exists(MANUAL_INVOICES_FILE):
        try:
            with open(MANUAL_INVOICES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_manual_invoices(data):
    try:
        with open(MANUAL_INVOICES_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except Exception:
        return False

def merge_manual_invoices(api_data, year_month):
    if not isinstance(api_data, dict):
        api_data = {"content": [], "total": 0}
    if "content" not in api_data:
        api_data["content"] = []
    
    manuals = load_manual_invoices()
    target_prefix = year_month.replace("_", "-")
    target_prefix_alt = year_month.replace("_", "/")
    
    matched_manuals = []
    for item in manuals:
        date_str = item.get("invoiceDate", "")
        if date_str.startswith(target_prefix) or date_str.startswith(target_prefix_alt):
            matched_manuals.append(item)
            
    combined_content = list(api_data["content"])
    combined_content.extend(matched_manuals)
    
    total = 0
    for item in combined_content:
        try:
            total += int(item.get("totalAmount", 0))
        except (ValueError, TypeError):
            try:
                total += int(float(item.get("totalAmount", 0)))
            except (ValueError, TypeError):
                pass
                
    return {
        "content": combined_content,
        "total": total
    }

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
    # Allow loading a specific month from local JSON
    month = request.args.get('month') or (request.json.get('month') if (request.is_json and request.json) else None)
    if month:
        filename = f"save_result/{month}_result.json"
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return jsonify(merge_manual_invoices(data, month))
            except Exception as e:
                return jsonify({"error": f"Failed to read file: {str(e)}"}), 500
        else:
            return jsonify({"error": f"Saved data for month {month} not found."}), 404

    # Default live API fetch logic
    today = datetime.today()
    today_str = today.strftime('%Y_%m')
    first_day_of_month = today.replace(day=1)
    first_day_of_last_month= (first_day_of_month - timedelta(days=1)).replace(day=1)

    result = get_data(first_day_of_month, today)
    if not result:
        # Fallback to local saved data for current month if API fails
        if os.path.exists(RESULT_FILE):
            try:
                with open(RESULT_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return jsonify(merge_manual_invoices(data, today_str))
            except Exception:
                pass
        return jsonify({"error": "Failed to retrieve data."}), 500

    all_items = result['content']
    total = result['total']
    save_result({"content": all_items, "total": total})

    # Also get last month's data
    result_last_month = get_data(first_day_of_last_month, first_day_of_month - timedelta(days=1))
    if result_last_month:
        all_items_last_month = result_last_month['content']
        total_last_month = result_last_month['total']
        print("Last month's total:", total_last_month)
        save_result({"content": all_items_last_month, "total": total_last_month}, filename=PREVIOUS_RESULT_FILE)       

    return jsonify(merge_manual_invoices({
        "content": all_items,
        "total": total
    }, today_str))


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
    today = datetime.today()
    today_str = today.strftime('%Y_%m')
    raw_res = load_result()
    if isinstance(raw_res, dict) and raw_res.get("result") == "No result yet.":
        merged = merge_manual_invoices({"content": [], "total": 0}, today_str)
        if merged["content"]:
            return jsonify(merged)
        return jsonify(raw_res)
    return jsonify(merge_manual_invoices(raw_res, today_str))

@app.route('/api/saved_months', methods=['GET'])
def api_saved_months():
    try:
        files = os.listdir("save_result")
        months = []
        for f in files:
            if f.endswith("_result.json"):
                parts = f.split("_result.json")
                if parts and len(parts[0]) == 7: # e.g. "2026_06"
                    months.append(parts[0])
        months.sort(reverse=True)
        return jsonify(months)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/seller_types', methods=['GET', 'POST', 'DELETE'])
def api_seller_types():
    if request.method == 'GET':
        return jsonify(load_seller_types())
    
    elif request.method == 'POST':
        data = request.get_json(silent=True) or {}
        seller_name = data.get('sellerName')
        seller_type = data.get('type')
        
        if not seller_name or not seller_type:
            return jsonify({"error": "sellerName and type are required"}), 400
        
        mappings = load_seller_types()
        mappings[seller_name] = seller_type
        if save_seller_types(mappings):
            return jsonify({"status": "success", "mappings": mappings})
        else:
            return jsonify({"error": "Failed to save mappings"}), 500
            
    elif request.method == 'DELETE':
        data = request.get_json(silent=True) or {}
        seller_name = data.get('sellerName')
        
        if not seller_name:
            return jsonify({"error": "sellerName is required"}), 400
            
        mappings = load_seller_types()
        if seller_name in mappings:
            del mappings[seller_name]
            if save_seller_types(mappings):
                return jsonify({"status": "success", "mappings": mappings})
            else:
                return jsonify({"error": "Failed to save mappings"}), 500
        else:
            return jsonify({"error": "Mapping not found"}), 404

@app.route('/api/user_save_result', methods=['POST'])
def user_save_result():
    data = request.get_json(silent=True) or {}
    amount = data.get('amount')
    type_ = data.get('type')
    date_ = data.get('date')
    seller_name = data.get('sellerName') or 'Manual Entry'

    if not amount:
        return jsonify({"error": "Amount is required"}), 400
    if not type_:
        return jsonify({"error": "Type is required"}), 400

    try:
        amount_val = int(amount)
        if amount_val < 0:
            return jsonify({"error": "Amount must be positive"}), 400
    except ValueError:
        return jsonify({"error": "Amount must be a number"}), 400

    if not date_:
        date_ = datetime.today().strftime('%Y-%m-%d')
    else:
        try:
            for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%Y-%m-%dT%H:%M:%S'):
                try:
                    parsed_dt = datetime.strptime(date_, fmt)
                    date_ = parsed_dt.strftime('%Y-%m-%d')
                    break
                except ValueError:
                    continue
            else:
                date_ = datetime.today().strftime('%Y-%m-%d')
        except Exception:
            date_ = datetime.today().strftime('%Y-%m-%d')

    import random
    suffix = ''.join(random.choices('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=4))
    invoice_number = f"MANUAL-{date_.replace('-', '')}-{suffix}"

    new_invoice = {
        "invoiceNumber": invoice_number,
        "invoiceDate": date_,
        "carrierName": "Manual",
        "sellerName": seller_name,
        "totalAmount": str(amount),
        "token": "",
        "type": type_
    }

    manuals = load_manual_invoices()
    manuals.append(new_invoice)
    if save_manual_invoices(manuals):
        return jsonify({"status": "success", "invoice": new_invoice})
    else:
        return jsonify({"error": "Failed to save manual invoice"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
