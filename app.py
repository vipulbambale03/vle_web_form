from flask import Flask, render_template, request, jsonify
import psycopg2
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection
def get_db_connection():
    return psycopg2.connect(
        host='dpg-d08r3hp5pdvs739q23i0-a.singapore-postgres.render.com',
        database='mh_web_app_funj',
        user='vipulbambale03',
        password='jLN4WPo1dLc54HCnReR8BI7uPf1uiDce',
        port='5432'
    )

app = Flask(__name__)

'''@app.route('/')
def index():
    return render_template('index.html')
'''
@app.route('/')
def index():
    return render_template('index.html')
    
@app.route('/debug_check')
def debug_check():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM divisions")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return f"Division count: {count}"
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/get_divisions', methods=['GET'])
def get_divisions():
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT id, name FROM divisions")
    divisions = [{'id': row[0], 'name': row[1]} for row in cursor.fetchall()]
    cursor.close()
    connection.close()
    return jsonify(divisions)

@app.route('/get_districts/<division_id>', methods=['GET'])
def get_districts(division_id):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT id, name FROM districts WHERE division_id = %s", (division_id,))
    districts = [{'id': row[0], 'name': row[1]} for row in cursor.fetchall()]
    cursor.close()
    connection.close()
    return jsonify(districts)

@app.route('/get_blocks/<district_id>', methods=['GET'])
def get_blocks(district_id):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT id, name FROM blocks WHERE district_id = %s", (district_id,))
    blocks = [{'id': row[0], 'name': row[1]} for row in cursor.fetchall()]
    cursor.close()
    connection.close()
    return jsonify(blocks)

@app.route('/get_grampanchayats/<block_id>', methods=['GET'])
def get_grampanchayats(block_id):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT lgd_code, name FROM grampanchayats WHERE block_id = %s", (block_id,))
    grampanchayats = [{'lgd_code': row[0], 'name': row[1]} for row in cursor.fetchall()]
    cursor.close()
    connection.close()
    return jsonify(grampanchayats)

def validate_pincode(pincode):
    """Validate that pincode is exactly 6 digits"""
    return pincode and pincode.isdigit() and len(pincode) == 6

@app.route('/submit_form', methods=['POST'])
def submit_form():
    try:
        form_data = request.form
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get employee type
        vle_type = form_data['employeeType']

        grampanchayats = request.form.getlist('grampanchayats')
        print(f"GP Type: {gp_type}, Grampanchayats: {grampanchayats}")
        
        # Get selected grampanchayats
        grampanchayat_ids = request.form.getlist('grampanchayat') if vle_type == 'cluster' else [form_data['grampanchayat']]
        
        # Validate grampanchayat selection
        if vle_type == 'cluster' and len(grampanchayat_ids) < 2:
            return jsonify({
                'success': False,
                'message': 'Please select at least 2 grampanchayats for cluster type'
            }), 400
        elif vle_type == 'individual' and len(grampanchayat_ids) != 1:
            return jsonify({
                'success': False,
                'message': 'Please select exactly 1 grampanchayat for individual type'
            }), 400

        # Validate pincodes
        if not validate_pincode(form_data['permPincode']):
            return jsonify({
                'success': False,
                'message': 'Invalid permanent address pincode (must be 6 digits)'
            }), 400
            
        if (not form_data.get('sameCurrentAddress') and 
            form_data.get('currPincode') and 
            not validate_pincode(form_data['currPincode'])):
            return jsonify({
                'success': False,
                'message': 'Invalid current address pincode (must be 6 digits)'
            }), 400

        # Validate CIBIL score
        cibil_score = form_data.get('cibilScore', '')
        if not cibil_score.isdigit() or not (300 <= int(cibil_score) <= 900):
            return jsonify({
                'success': False,
                'message': 'Invalid CIBIL score (must be 300-900)'
            }), 400

        # Process addresses
        perm_address = ", ".join(filter(None, [
            form_data['permAddressLine1'],
            form_data.get('permAddressLine2'),
            f"{form_data['permCity']} - {form_data['permPincode']}"
        ]))
        
        same_current_address = 'sameCurrentAddress' in form_data
        if same_current_address:
            curr_address = perm_address
        else:
            curr_address = ", ".join(filter(None, [
                form_data.get('currAddressLine1', ''),
                form_data.get('currAddressLine2', ''),
                f"{form_data.get('currCity', '')} - {form_data.get('currPincode', '')}" 
                if form_data.get('currCity') else None
            ])) or None

        # Get grampanchayat details
        cursor.execute("SELECT lgd_code, name FROM grampanchayats WHERE lgd_code = ANY(%s)", (grampanchayat_ids,))
        gp_results = cursor.fetchall()
        
        if len(gp_results) != len(grampanchayat_ids):
            return jsonify({
                'success': False,
                'message': 'One or more selected grampanchayats not found'
            }), 400
        
        grampanchayat_names = [gp[1] for gp in gp_results]
        lgd_codes = [str(gp[0]) for gp in gp_results]

        # Get division name
        cursor.execute("SELECT name FROM divisions WHERE id = %s", (form_data['division'],))
        division_result = cursor.fetchone()
        if not division_result:
            return jsonify({'success': False, 'message': 'Division not found'}), 400
        division_name = division_result[0]
        
        # Get district name
        cursor.execute("SELECT name FROM districts WHERE id = %s", (form_data['district'],))
        district_result = cursor.fetchone()
        if not district_result:
            return jsonify({'success': False, 'message': 'District not found'}), 400
        district_name = district_result[0]
        
        # Get block name
        cursor.execute("SELECT name FROM blocks WHERE id = %s", (form_data['block'],))
        block_result = cursor.fetchone()
        if not block_result:
            return jsonify({'success': False, 'message': 'Block not found'}), 400
        block_name = block_result[0]

        # Handle checkbox values
        same_whatsapp = 'sameWhatsapp' in form_data
        
        # Prepare data for database
        data = {
            'vle_type': vle_type,
            'csc_id': form_data['cscId'],
            'division': division_name,
            'district': district_name,
            'block': block_name,
            'grampanchayat': ', '.join(grampanchayat_names),
            'lgd_code': ', '.join(lgd_codes),
            
            # Personal Details
            'first_name': form_data['firstName'],
            'father_name': form_data['fatherName'],
            'mother_name': form_data['motherName'],
            'surname': form_data['surname'],
            'dob': form_data['dob'],
            'blood_group': form_data.get('blood_group', ''),
            'gender': form_data['gender'],
            'marital_status': form_data['maritalStatus'],
            'spouse_name': form_data.get('spouseName', ''),
            'num_children': int(form_data.get('numChildren', 0)) if form_data.get('numChildren') else None,
            'anniversary_date': form_data.get('anniversary_date', None),
            'religion': form_data['religion'] if form_data['religion'] != 'Other' else form_data.get('otherReligion', ''),
            'category': form_data['category'] if form_data['category'] != 'Other' else form_data.get('otherCategory', ''),
            'caste': form_data.get('caste', ''),
            'education': form_data['education'] if form_data['education'] != 'Other' else form_data.get('otherEducation', ''),
            'institute_name': form_data['instituteName'],
            'cibil_score': int(cibil_score),

            # Contact Details
            'contact_number': form_data['contactNumber'],
            'whatsapp_number': form_data['contactNumber'] if same_whatsapp else form_data.get('whatsappNumber', ''),
            'email': form_data['email'],
            
            # Address Details
            'permanent_address': perm_address,
            'current_address': curr_address,
            
            # Identification Details
            'pan_number': form_data.get('panNumber', ''),
            'aadhar_number': form_data.get('aadharNumber', ''),
            
            # Bank Details
            'bank_name': form_data['bankName'] if form_data.get('bankName') != 'Other' else form_data.get('otherBank', ''),
            'ifsc_code': form_data.get('ifsc', ''),
            'account_number': form_data.get('accountNumber', ''),
            'branch_name': form_data.get('branchName', '')
        }

        # Insert data
        query = """
        INSERT INTO vle_details (
            vle_type, csc_id, division, district, block, grampanchayat, lgd_code,
            first_name, father_name, mother_name, surname, dob, blood_group, gender,
            marital_status, spouse_name, num_children, anniversary_date, religion,
            category, caste, education, institute_name, contact_number, whatsapp_number,
            email, permanent_address, current_address, pan_number, aadhar_number,
            bank_name, ifsc_code, account_number, branch_name, cibil_score
        ) VALUES (
            %(vle_type)s, %(csc_id)s, %(division)s, %(district)s, %(block)s, %(grampanchayat)s, %(lgd_code)s,
            %(first_name)s, %(father_name)s, %(mother_name)s, %(surname)s, %(dob)s, %(blood_group)s, %(gender)s,
            %(marital_status)s, %(spouse_name)s, %(num_children)s, %(anniversary_date)s, %(religion)s,
            %(category)s, %(caste)s, %(education)s, %(institute_name)s, %(contact_number)s, %(whatsapp_number)s,
            %(email)s, %(permanent_address)s, %(current_address)s, %(pan_number)s, %(aadhar_number)s,
            %(bank_name)s, %(ifsc_code)s, %(account_number)s, %(branch_name)s, %(cibil_score)s
        )
        """
        
        cursor.execute(query, data)
        connection.commit()
        
        return jsonify({'success': True, 'message': 'Form submitted successfully!'})
    
    except psycopg2.Error as err:
        return jsonify({'success': False, 'message': f'Database error: {str(err)}'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'An error occurred: {str(e)}'}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'connection' in locals(): connection.close()

@app.route('/search_record', methods=['GET'])
def search_record():
    try:
        search_term = request.args.get('term')
        if not search_term:
            return jsonify({'success': False, 'message': 'Search term is required'})
            
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # First try exact matches
        cursor.execute("""
            SELECT v.*, 
                   TO_CHAR(v.dob, 'YYYY-MM-DD') as dob_formatted,
                   TO_CHAR(v.anniversary_date, 'YYYY-MM-DD') as anniversary_date_formatted
            FROM vle_details v
            WHERE TRIM(v.csc_id) = %s 
               OR TRIM(v.aadhar_number) = %s 
               OR TRIM(v.contact_number) = %s
            LIMIT 1
        """, (search_term, search_term, search_term))
        
        record = cursor.fetchone()
        
        if not record:
            return jsonify({'success': False, 'message': 'Record not found'})
        
        # Get column names
        colnames = [desc[0] for desc in cursor.description]
        record_dict = dict(zip(colnames, record))
        
        # Get location information
        location_ids = {}
        grampanchayat_details = []
        lgd_codes = record_dict['lgd_code'].split(', ') if record_dict['lgd_code'] else []
        
        if lgd_codes:
            if record_dict['vle_type'] == 'individual' and len(lgd_codes) == 1:
                # For individual, get single GP location
                cursor.execute("""
                    SELECT g.lgd_code, g.block_id, b.district_id, d.division_id as division_id
                    FROM grampanchayats g
                    JOIN blocks b ON g.block_id = b.id
                    JOIN districts d ON b.district_id = d.id
                    WHERE g.lgd_code = %s
                """, (lgd_codes[0],))
                gp_location = cursor.fetchone()
                
                if gp_location:
                    location_ids = {
                        'division_id': gp_location[3],
                        'district_id': gp_location[2],
                        'block_id': gp_location[1],
                        'grampanchayat_id': lgd_codes[0]
                    }
            
            elif record_dict['vle_type'] == 'cluster' and len(lgd_codes) > 1:
                # For cluster, get all GP details
                cursor.execute("""
                    SELECT g.lgd_code, g.name, g.block_id, 
                           b.district_id, d.division_id as division_id
                    FROM grampanchayats g
                    JOIN blocks b ON g.block_id = b.id
                    JOIN districts d ON b.district_id = d.id
                    WHERE g.lgd_code = ANY(%s)
                """, (lgd_codes,))
                grampanchayat_details = cursor.fetchall()
                
                if grampanchayat_details:
                    # Verify all GPs are from same block
                    block_ids = set(gp[2] for gp in grampanchayat_details)
                    if len(block_ids) == 1:
                        gp = grampanchayat_details[0]
                        location_ids = {
                            'division_id': gp[4],
                            'district_id': gp[3],
                            'block_id': gp[2],
                            'grampanchayat_ids': [gp[0] for gp in grampanchayat_details]
                        }

        response = {
            'success': True, 
            'record': record_dict,
            'location_ids': location_ids,
            'grampanchayat_details': grampanchayat_details
        }
        
        return jsonify(response)
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'connection' in locals(): connection.close()

@app.route('/update_record', methods=['POST'])
def update_record():
    try:
        form_data = request.form
        csc_id = form_data['cscId']
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get employee type
        vle_type = form_data['employeeType']
        
        # Get selected grampanchayats
        grampanchayat_ids = request.form.getlist('grampanchayat') if vle_type == 'cluster' else [form_data['grampanchayat']]
        
        # Validate grampanchayat selection
        if vle_type == 'cluster' and len(grampanchayat_ids) < 2:
            return jsonify({
                'success': False,
                'message': 'Please select at least 2 grampanchayats for cluster type'
            }), 400
        elif vle_type == 'individual' and len(grampanchayat_ids) != 1:
            return jsonify({
                'success': False,
                'message': 'Please select exactly 1 grampanchayat for individual type'
            }), 400

        # Validate pincodes
        if not validate_pincode(form_data['permPincode']):
            return jsonify({
                'success': False,
                'message': 'Invalid permanent address pincode (must be 6 digits)'
            }), 400
            
        if (not form_data.get('sameCurrentAddress') and 
            form_data.get('currPincode') and 
            not validate_pincode(form_data['currPincode'])):
            return jsonify({
                'success': False,
                'message': 'Invalid current address pincode (must be 6 digits)'
            }), 400

        # Validate CIBIL score
        cibil_score = form_data.get('cibilScore', '')
        if not cibil_score.isdigit() or not (300 <= int(cibil_score) <= 900):
            return jsonify({
                'success': False,
                'message': 'Invalid CIBIL score (must be 300-900)'
            }), 400

        # Process addresses
        perm_address = ", ".join(filter(None, [
            form_data['permAddressLine1'],
            form_data.get('permAddressLine2'),
            f"{form_data['permCity']} - {form_data['permPincode']}"
        ]))
        
        same_current_address = 'sameCurrentAddress' in form_data
        if same_current_address:
            curr_address = perm_address
        else:
            curr_address = ", ".join(filter(None, [
                form_data.get('currAddressLine1', ''),
                form_data.get('currAddressLine2', ''),
                f"{form_data.get('currCity', '')} - {form_data.get('currPincode', '')}" 
                if form_data.get('currCity') else None
            ])) or None

        # Get grampanchayat details
        cursor.execute("SELECT lgd_code, name FROM grampanchayats WHERE lgd_code = ANY(%s)", (grampanchayat_ids,))
        gp_results = cursor.fetchall()
        
        if len(gp_results) != len(grampanchayat_ids):
            return jsonify({
                'success': False,
                'message': 'One or more selected grampanchayats not found'
            }), 400
        
        grampanchayat_names = [gp[1] for gp in gp_results]
        lgd_codes = [str(gp[0]) for gp in gp_results]

        # Get location names
        cursor.execute("SELECT name FROM divisions WHERE id = %s", (form_data['division'],))
        division_name = cursor.fetchone()[0]
        
        cursor.execute("SELECT name FROM districts WHERE id = %s", (form_data['district'],))
        district_name = cursor.fetchone()[0]
        
        cursor.execute("SELECT name FROM blocks WHERE id = %s", (form_data['block'],))
        block_name = cursor.fetchone()[0]

        # Handle checkbox values
        same_whatsapp = 'sameWhatsapp' in form_data
        
        # Prepare update data
        data = {
            'csc_id': csc_id,
            'vle_type': vle_type,
            'division': division_name,
            'district': district_name,
            'block': block_name,
            'grampanchayat': ', '.join(grampanchayat_names),
            'lgd_code': ', '.join(lgd_codes),
            
            # Personal Details
            'first_name': form_data['firstName'],
            'father_name': form_data['fatherName'],
            'mother_name': form_data['motherName'],
            'surname': form_data['surname'],
            'dob': form_data['dob'],
            'blood_group': form_data.get('blood_group', ''),
            'gender': form_data['gender'],
            'marital_status': form_data['maritalStatus'],
            'spouse_name': form_data.get('spouseName', ''),
            'num_children': int(form_data.get('numChildren', 0)) if form_data.get('numChildren') else None,
            'anniversary_date': form_data.get('anniversary_date', None),
            'religion': form_data['religion'] if form_data['religion'] != 'Other' else form_data.get('otherReligion', ''),
            'category': form_data['category'] if form_data['category'] != 'Other' else form_data.get('otherCategory', ''),
            'caste': form_data.get('caste', ''),
            'education': form_data['education'] if form_data['education'] != 'Other' else form_data.get('otherEducation', ''),
            'institute_name': form_data['instituteName'],
            'cibil_score': int(cibil_score),

            # Contact Details
            'contact_number': form_data['contactNumber'],
            'whatsapp_number': form_data['contactNumber'] if same_whatsapp else form_data.get('whatsappNumber', ''),
            'email': form_data['email'],
            
            # Address Details
            'permanent_address': perm_address,
            'current_address': curr_address,
            
            # Identification Details
            'pan_number': form_data.get('panNumber', ''),
            'aadhar_number': form_data.get('aadharNumber', ''),
            
            # Bank Details
            'bank_name': form_data['bankName'] if form_data.get('bankName') != 'Other' else form_data.get('otherBank', ''),
            'ifsc_code': form_data.get('ifsc', ''),
            'account_number': form_data.get('accountNumber', ''),
            'branch_name': form_data.get('branchName', '')
        }

        # Update query
        query = """
        UPDATE vle_details SET
            vle_type = %(vle_type)s,
            division = %(division)s,
            district = %(district)s,
            block = %(block)s,
            grampanchayat = %(grampanchayat)s,
            lgd_code = %(lgd_code)s,
            first_name = %(first_name)s,
            father_name = %(father_name)s,
            mother_name = %(mother_name)s,
            surname = %(surname)s,
            dob = %(dob)s,
            blood_group = %(blood_group)s,
            gender = %(gender)s,
            marital_status = %(marital_status)s,
            spouse_name = %(spouse_name)s,
            num_children = %(num_children)s,
            anniversary_date = %(anniversary_date)s,
            religion = %(religion)s,
            category = %(category)s,
            caste = %(caste)s,
            education = %(education)s,
            institute_name = %(institute_name)s,
            contact_number = %(contact_number)s,
            whatsapp_number = %(whatsapp_number)s,
            email = %(email)s,
            permanent_address = %(permanent_address)s,
            current_address = %(current_address)s,
            pan_number = %(pan_number)s,
            aadhar_number = %(aadhar_number)s,
            bank_name = %(bank_name)s,
            ifsc_code = %(ifsc_code)s,
            account_number = %(account_number)s,
            branch_name = %(branch_name)s,
            cibil_score = %(cibil_score)s
        WHERE csc_id = %(csc_id)s
        """
        
        cursor.execute(query, data)
        connection.commit()
        
        return jsonify({'success': True, 'message': 'Record updated successfully!'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'connection' in locals(): connection.close()

# This line ensures the app object is accessible by Gunicorn
application = app

app = Flask(__name__)
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
