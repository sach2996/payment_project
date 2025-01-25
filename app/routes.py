from flask import request, jsonify
from app import app, mongo, fs
from app.services import normalize_csv_and_store, allowed_file
from bson.objectid import ObjectId
import os
from werkzeug.utils import secure_filename
from app.db import get_collection, get_fs
from app.models import Payment
from flask import Response, jsonify
from bson import ObjectId
import gridfs
from datetime import date, datetime


collection = get_collection()
fs = get_fs()

# Route to upload CSV and process it
@app.route('/upload_csv', methods=['POST'])
def upload_csv():
    try:
        file = request.files['file']
        file_path = f"./uploads/{file.filename}"
        file.save(file_path)
        
        # Normalize CSV data and store in MongoDB
        normalize_csv_and_store(file_path)
        
        return jsonify({"message": "CSV file processed and data saved to MongoDB successfully."}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route to get all payments with filtering, paging, and search
@app.route('/payments', methods=['GET'])
def get_payments():
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        search_query = request.args.get('search', '')
        filter_status = request.args.get('status', None)

        # Ensure valid status values
        valid_statuses = ['pending', 'due_now', 'completed', 'overdue']
        if filter_status and filter_status not in valid_statuses:
            return jsonify({'error': 'Invalid status value. Allowed values: pending, due_now, completed, overdue'}), 400

        query = {}

        # Search filter for payee's first name
        if search_query:
            query['payee_first_name'] = {'$regex': search_query, '$options': 'i'}

        # Status filter
        if filter_status:
            query['payee_payment_status'] = filter_status

        skip = (page - 1) * limit

        # Adding sorting based on the due date (optional, but helpful)
        payments_cursor = collection.find(query).skip(skip).limit(limit).sort('payee_due_date', 1)
        payments = []

        for doc in payments_cursor:
            try:
                due_amount = float(doc.get('due_amount', 0))  # Default to 0 if not found
                discount_percent = float(doc.get('discount_percent', 0))  # Default to 0 if not found
                tax_percent = float(doc.get('tax_percent', 0))  # Default to 0 if not found

                # Calculate discount and tax amounts
                discount_amount = (discount_percent / 100) * due_amount
                tax_amount = (tax_percent / 100) * due_amount

                # Calculate total_due
                total_due = due_amount - discount_amount + tax_amount

                # Check if payee_due_date is today or in the past
                try:
                    due_date = datetime.strptime(doc['payee_due_date'], '%Y-%m-%d')  # Assuming date format is YYYY-MM-DD
                    if due_date.date() < date.today():
                        doc['payee_payment_status'] = 'overdue'
                    elif due_date.date() == date.today():
                        doc['payee_payment_status'] = 'due_now'
                except (ValueError, KeyError):
                    pass 

                payments.append({
                    '_id': str(doc['_id']),
                    'payee_first_name': doc['payee_first_name'],
                    'payee_last_name': doc['payee_last_name'],
                    'payee_payment_status': doc['payee_payment_status'],
                    'payee_due_date': doc['payee_due_date'],
                    'total_due': round(total_due, 2),
                    'evidence_file_id': doc.get('evidence_file_id', ''),
                })
            except ValueError as e:
                return jsonify({'error': f'Invalid numeric value in payment record: {str(e)}'}), 400

        # Total number of payments matching the query
        total_payments = collection.count_documents(query)

        return jsonify({
            'payments': payments,
            'pagination': {
                'current_page': page,
                'total_pages': (total_payments // limit) + (1 if total_payments % limit else 0),
                'total_records': total_payments
            }
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500
@app.route('/payments/<payment_id>', methods=['GET'])
def get_payment_by_id(payment_id):
    try:
        # Convert the payment_id to an ObjectId
        payment = collection.find_one({'_id': ObjectId(payment_id)})

        # If payment is not found, return a 404 error
        if not payment:
            return jsonify({'error': 'Payment not found'}), 404

        try:
            # Convert values to float to ensure proper arithmetic operations
            due_amount = float(payment['due_amount'])
            discount_percent = float(payment.get('discount_percent', 0))  # Default to 0 if not found
            tax_percent = float(payment.get('tax_percent', 0))  # Default to 0 if not found

            # Calculate discount and tax amounts
            discount_amount = (discount_percent / 100) * due_amount
            tax_amount = (tax_percent / 100) * due_amount

            # Calculate total_due
            total_due = due_amount - discount_amount + tax_amount
        except ValueError as e:
            return jsonify({'error': f'Invalid numeric value: {str(e)}'}), 400

        # Return the payment details with all its attributes
        payment_data = {
            '_id': str(payment['_id']),
            'payee_first_name': payment['payee_first_name'],
            'payee_last_name': payment['payee_last_name'],
            'payee_payment_status': payment['payee_payment_status'],
            'payee_added_date_utc': payment.get('payee_added_date_utc'),
            'payee_due_date': payment['payee_due_date'],
            'payee_address_line_1': payment['payee_address_line_1'],
            'payee_address_line_2': payment.get('payee_address_line_2'),
            'payee_city': payment['payee_city'],
            'payee_country': payment['payee_country'],
            'payee_province_or_state': payment.get('payee_province_or_state'),
            'payee_postal_code': payment['payee_postal_code'],
            'payee_phone_number': payment['payee_phone_number'],
            'payee_email': payment['payee_email'],
            'currency': payment['currency'],
            'discount_percent': payment.get('discount_percent'),
            'tax_percent': payment.get('tax_percent'),
            'due_amount': payment['due_amount'],
            'total_due': total_due,
            'evidence_file_id': payment.get('evidence_file_id',''),
        }

        return jsonify({'payment': payment_data}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Route to create a new payment
@app.route('/payments', methods=['POST'])
def create_payment():
    try:
        data = request.get_json()
        print(data)
        # Validate data using Pydantic model
        try:
            payment = Payment(**data)  # Validate with Pydantic model
        except Exception as e:
            return jsonify({'error': str(e)}), 400

        # Insert the new payment data into MongoDB
        result = collection.insert_one(payment.dict())

        # Return the ID of the newly created payment
        return jsonify({'message': 'Payment created successfully', 'id': str(result.inserted_id)}), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/payments/<payment_id>', methods=['PATCH'])
def update_payment(payment_id):
    try:
        collection = get_collection()  # Get the correct collection
        fs = get_fs()  # Ensure fs is an instance of GridFS

        # Extract form data instead of JSON
        payee_due_date = request.form.get('payee_due_date')
        due_amount = request.form.get('due_amount')
        payee_payment_status = request.form.get('payee_payment_status')

        # Validate the presence of editable fields
        update_data = {}

        if payee_due_date:
            update_data['payee_due_date'] = payee_due_date

        if due_amount:
            update_data['due_amount'] = float(due_amount)  # Ensure correct data type

        if payee_payment_status:
            update_data['payee_payment_status'] = payee_payment_status

        # Handle file upload if status is "completed"
        if payee_payment_status == 'completed':
            if 'evidence_file' not in request.files:
                return jsonify({'error': 'Evidence file is required when marking payment as completed'}), 400

            file = request.files['evidence_file']

            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_data = file.read()

                # Correctly use GridFS to store the file
                file_id = fs.put(file_data, filename=filename)

                update_data['evidence_file_id'] = str(file_id)
            else:
                return jsonify({'error': 'Invalid file type. Only PDF, PNG, JPG allowed'}), 400

        if not update_data:
            return jsonify({'error': 'No valid fields to update'}), 400

        # Perform the update with the provided data
        result = collection.update_one(
            {'_id': ObjectId(payment_id)},
            {'$set': update_data}
        )

        if result.modified_count == 1:
            return jsonify({'message': 'Payment updated successfully', 'id': str(payment_id)}), 200
        else:
            return jsonify({'error': 'Payment not found'}), 404

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/payments/<payment_id>', methods=['DELETE'])
def delete_payment(payment_id):
    try:
        collection = get_collection()  # Get collection within the function
        fs = get_fs()  # Get fs instance within the function

        # Ensure that you are using the correct method on the collection
        result = collection.delete_one({'_id': ObjectId(payment_id)})

        # Check if the deletion was successful
        if result.deleted_count == 1:
            return jsonify({'message': 'Payment deleted successfully'}), 200
        else:
            return jsonify({'message': 'Payment not found'}), 404

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/payments/<payment_id>/upload_evidence', methods=['PUT'])
def upload_evidence(payment_id):
    # Retrieve the payment document
    payment = collection.find_one({'_id': ObjectId(payment_id)})

    if not payment:
        return jsonify({'error': 'Payment not found'}), 404

    # Check if payment status is "completed"
    if payment['payee_payment_status'] == 'completed':
        return jsonify({'error': 'Evidence already uploaded for this payment.'}), 400

    # Ensure that a file is provided in the request
    if 'evidence_file' not in request.files:
        return jsonify({'error': 'No evidence file provided'}), 400

    file = request.files['evidence_file']

    # Validate file type
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Allowed types are PDF, PNG, JPG, JPEG.'}), 400

    # Store the file in MongoDB using GridFS
    filename = secure_filename(file.filename)
    file_data = file.read()
    file_id = fs.put(file_data, filename=filename)

    # Update payment status to "completed" and store file ID in payment document
    result = collection.update_one(
        {'_id': ObjectId(payment_id)},
        {'$set': {
            'payee_payment_status': 'completed',
            'evidence_file_id': file_id
        }}
    )

    if result.modified_count == 1:
        return jsonify({
            'message': 'Payment status updated to "completed" and evidence file uploaded successfully',
            'evidence_file_id': str(file_id)
        }), 200
    else:
        return jsonify({'error': 'Failed to update payment status'}), 500


# Route to download evidence file

from flask import send_file, jsonify
from bson import ObjectId
import gridfs
import io

@app.route('/payments/<payment_id>/download_evidence', methods=['GET'])
def download_file(payment_id):
    payment = collection.find_one({'_id': ObjectId(payment_id)})
    
    if payment and 'evidence_file_id' in payment:
        file_id = payment['evidence_file_id']
        file = fs.get(ObjectId(file_id))

        # Convert the file to a readable stream
        file_data = io.BytesIO(file.read())
        
        # Use send_file to return the file properly
        return send_file(
            file_data,
            as_attachment=True,
            download_name=file.filename,  # Flask 2.x uses download_name instead of attachment_filename
            mimetype=file.content_type
        )

    return jsonify({'error': 'Evidence file not found'}), 404
