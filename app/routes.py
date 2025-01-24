from flask import request, jsonify
from app import app, mongo, fs
from app.services import normalize_csv_and_store, allowed_file
from bson.objectid import ObjectId
import os
from werkzeug.utils import secure_filename
from app.db import get_collection, get_fs
from app.models import Payment


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

        query = {}

        if search_query:
            query['payee_first_name'] = {'$regex': search_query, '$options': 'i'}

        if filter_status:
            query['payee_payment_status'] = filter_status

        skip = (page - 1) * limit

        payments_cursor = collection.find(query).skip(skip).limit(limit)
        payments = []

        for doc in payments_cursor:
            payments.append({
                '_id': str(doc['_id']),
                'payee_first_name': doc['payee_first_name'],
                'payee_last_name': doc['payee_last_name'],
                'payee_payment_status': doc['payee_payment_status'],
                'payee_due_date': doc['payee_due_date'],
                'total_due': doc.get('total_due', 0)
            })

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


# Route to create a new payment
@app.route('/payments', methods=['POST'])
def create_payment():
    try:
        data = request.get_json()

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


@app.route('/payments/<payment_id>', methods=['PUT'])
def update_payment(payment_id):
    data = request.get_json()

    collection = get_collection()  # Get collection within the function
    fs = get_fs()  # Get fs instance within the function

    # Check if the payment status is "completed" and if a file is uploaded
    if data.get('payee_payment_status') == 'completed':
        # Check if file is present in the request
        if 'evidence_file' not in request.files:
            return jsonify({'error': 'Evidence file is required when marking payment as completed'}), 400

        file = request.files['evidence_file']

        # Validate file type
        if file and allowed_file(file.filename):
            # Store the file in MongoDB using GridFS
            filename = secure_filename(file.filename)
            file_data = file.read()
            file_id = fs.put(file_data, filename=filename)

            # Update the payment status and save the file ID in the payment record
            result = collection.update_one(
                {'_id': ObjectId(payment_id)},
                {'$set': {
                    'payee_payment_status': 'completed',
                    'evidence_file_id': file_id
                }}
            )

            if result.modified_count == 1:
                return jsonify({'message': 'Payment status updated to completed and evidence file uploaded successfully'}), 200
            else:
                return jsonify({'error': 'Payment not found'}), 404
        else:
            return jsonify({'error': 'Invalid file type. Only PDF, PNG, JPG allowed'}), 400

    # Handle other status updates (without evidence file)
    result = collection.update_one(
        {'_id': ObjectId(payment_id)},
        {'$set': {'payee_payment_status': data['payee_payment_status']}}
    )

    if result.modified_count == 1:
        return jsonify({'message': 'Payment status updated successfully'}), 200
    else:
        return jsonify({'error': 'Payment not found'}), 404

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
@app.route('/payments/<payment_id>/download_evidence', methods=['GET'])
def download_file(payment_id):
    # Retrieve the payment document from MongoDB
    payment = collection.find_one({'_id': ObjectId(payment_id)})

    if payment and 'evidence_file_id' in payment:
        file_id = payment['evidence_file_id']
        file = fs.get(file_id)

        return file, 200  # This will send the file content back as a download

    return jsonify({'error': 'Evidence file not found'}), 404

