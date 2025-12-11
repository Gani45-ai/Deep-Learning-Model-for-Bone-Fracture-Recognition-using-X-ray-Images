from flask import Flask, flash, redirect, render_template, request, session, url_for, jsonify
import mysql.connector, random, string, os
from werkzeug.utils import secure_filename
from predict import process_xray
from datetime import datetime, timedelta
from mistralai import Mistral

app = Flask(__name__)
app.secret_key = "Qazwsx@123"

# Configure upload settings
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Database connection
link = mysql.connector.connect(
    host = 'localhost',
    user = 'root',
    password = '',
    database = 'bonefracture'
)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        return redirect(url_for('enquiry'))

    if request.method == "GET":
        return render_template('login.html')

    else:
        cursor = link.cursor()
        try:
            email = request.form["email"]
            password = request.form["password"]
            cursor.execute("SELECT * FROM users WHERE email = %s AND password = %s", (email, password))
            user = cursor.fetchone()
            if user:
                session['user_id'] = user[0] # Store user ID
                session['user'] = user[3]
                session['username'] = user[2]
                return redirect(url_for('enquiry'))
            else:
                return render_template('login.html', error='Invalid email or password')

        except Exception as e:
            error = str(e)
            return render_template('login.html', error=error)
        finally:
            cursor.close()

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user' in session:
        return redirect(url_for('enquiry'))

    if request.method == "GET":
        return render_template('register.html')

    else:
        cursor = link.cursor()
        try:
            name = request.form["name"]
            email = request.form["email"]
            password = request.form["password"]
            phone = request.form["phone"]
            uid = 'uid_'+''.join(random.choices(string.ascii_letters + string.digits, k=10))

            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()

            if user:
                return render_template('register.html', exists='Email already exists')
            else:
                cursor.execute("INSERT INTO users (uid, name, email, password, phone) VALUES (%s, %s, %s, %s, %s)",
                             (uid, name, email, password, phone))
                link.commit()
                return render_template('register.html', success='Registration successful')

        except Exception as e:
            error = str(e)
            return render_template('register.html', error=error)
        finally:
            cursor.close()

@app.route('/doctor_register', methods=['GET', 'POST'])
def doctor_register():
    if 'doctor_user' in session:
        return redirect(url_for('doctor_appointments')) # Redirect to doctor appointments page

    if request.method == "GET":
        return render_template('doctor_register.html')

    else:
        cursor = link.cursor()
        try:
            name = request.form["name"]
            name = request.form["name"]
            email = request.form["email"]
            password = request.form["password"]
            phone = request.form["phone"]
            specialization = request.form["specialization"]
            uid = 'doc_uid_'+''.join(random.choices(string.ascii_letters + string.digits, k=10))

            cursor.execute("SELECT * FROM doctors WHERE email = %s", (email,))
            doctor = cursor.fetchone()

            if doctor:
                return render_template('doctor_register.html', exists='Email already exists')
            else:
                cursor.execute("INSERT INTO doctors (uid, name, email, password, phone, specialization) VALUES (%s, %s, %s, %s, %s, %s)",
                             (uid, name, email, password, phone, specialization))
                link.commit()
                return render_template('doctor_register.html', success='Registration successful')

        except Exception as e:
            error = str(e)
            return render_template('doctor_register.html', error=error)
        finally:
            cursor.close()

@app.route('/doctor_login', methods=['GET', 'POST'])
def doctor_login():
    if 'doctor_user' in session:
        return redirect(url_for('doctor_appointments')) # Redirect to doctor appointments page

    if request.method == "GET":
        return render_template('doctor_login.html')

    else:
        cursor = link.cursor()
        try:
            email = request.form["email"]
            password = request.form["password"]
            cursor.execute("SELECT * FROM doctors WHERE email = %s AND password = %s", (email, password))
            doctor = cursor.fetchone()
            if doctor:
                session['doctor_user_id'] = doctor[0] # Store doctor ID
                session['doctor_user'] = doctor[3]
                session['doctor_username'] = doctor[2]
                return redirect(url_for('doctor_appointments')) # Redirect to doctor appointments page
            else:
                return render_template('doctor_login.html', error='Invalid email or password')

        except Exception as e:
            error = str(e)
            return render_template('doctor_login.html', error=error)
        finally:
            cursor.close()

@app.route('/enquiry', methods=['GET', 'POST'])
def enquiry():
    if 'user' not in session:
        return redirect(url_for('login'))

    if request.method == "GET":
        return render_template('enquiry.html')

    if 'file' not in request.files:
        return render_template('enquiry.html', error='No file uploaded')

    file = request.files['file']
    if file.filename == '':
        return render_template('enquiry.html', error='No file selected')

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        file.save(filepath)

        try:
            processed_image, grayscale_image, thresholded_image, binary_image, result = process_xray(filepath)
            if processed_image:
                return render_template('enquiry.html',
                                     original_image=filepath,
                                     grayscale_image=grayscale_image,
                                     thresholded_image=thresholded_image,
                                     binary_image=binary_image,
                                     processed_image=processed_image,
                                     result=result)
            else:
                return render_template('enquiry.html', error='Error processing image')
        except Exception as e:
            return render_template('enquiry.html', error=str(e))

    return render_template('enquiry.html', error='Invalid file type')

@app.route('/doctors')
def doctors():
    if 'user' not in session:
        return redirect(url_for('login'))

    cursor = link.cursor()
    try:
        # Fetch all doctors
        cursor.execute("SELECT * FROM doctors")
        doctors_list = cursor.fetchall()

        # Fetch user's appointments with doctor names
        user_id = session['user_id']
        cursor.execute("""
            SELECT a.*, d.name
            FROM appointments a
            JOIN doctors d ON a.doctor_id = d.id
            WHERE a.user_id = %s
        """, (user_id,))
        user_appointments = cursor.fetchall()

        return render_template('doctors.html', doctors=doctors_list, user_appointments=user_appointments)

    except Exception as e:
        error = str(e)
        return render_template('doctors.html', error=error)
    finally:
        cursor.close()

@app.route('/book_appointment', methods=['POST'])
def book_appointment():
    if 'user' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        doctor_id = request.form['doctor_id']
        appointment_date = request.form['appointment_date']
        appointment_time = request.form['appointment_time']
        user_id = session['user_id']

        cursor = link.cursor()
        try:
            # Combine date and time for easier comparison
            appointment_datetime = datetime.strptime(f"{appointment_date} {appointment_time}", "%Y-%m-%d %H:%M")
            time_before = appointment_datetime - timedelta(minutes=29)
            time_after = appointment_datetime + timedelta(minutes=29)

            # Check for existing appointments within the 30-minute window
            cursor.execute(
                """
                SELECT COUNT(*) FROM appointments
                WHERE doctor_id = %s
                AND appointment_date = %s
                AND appointment_time BETWEEN %s AND %s
                """,
                (doctor_id, appointment_date, time_before.strftime("%H:%M:%S"), time_after.strftime("%H:%M:%S"))
            )
            existing_appointments_count = cursor.fetchone()[0]

            if existing_appointments_count > 0:
                flash('There is already an appointment scheduled within 30 minutes of this time.', 'danger')
                return redirect(url_for('doctors'))

            # If no conflicting appointments, insert the new appointment
            cursor.execute(
                "INSERT INTO appointments (user_id, doctor_id, appointment_date, appointment_time) VALUES (%s, %s, %s, %s)",
                (user_id, doctor_id, appointment_date, appointment_time)
            )
            link.commit()
            flash('Appointment booked successfully!', 'success')
            return redirect(url_for('doctors'))

        except Exception as e:
            link.rollback()
            flash(f'Error booking appointment: {str(e)}', 'danger')
            return redirect(url_for('doctors'))
        finally:
            cursor.close()

@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('username', None)
    session.pop('user_id', None) # Also remove user_id from session
    return redirect(url_for('index'))

@app.route('/doctor_logout')
def doctor_logout():
    session.pop('doctor_user', None)
    session.pop('doctor_username', None)
    session.pop('doctor_user_id', None) # Also remove doctor_user_id from session
    return redirect(url_for('index'))



@app.route('/chatbot', methods=['POST'])
def chatbot():
    if 'user' not in session and 'doctor_user' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user_message = request.json.get('message')
    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    api_key = "WTuMOibXWmpTqjvscYHSaaCOjjXCakkJ" # Replace with secure storage method
    model = "mistral-large-latest"

    try:
        client = Mistral(api_key=api_key)
        messages = [
            {"role": "system", "content": "You are a medical chatbot specializing in bones. Provide information and answer questions related to bone health, fractures, and related medical topics. Do not answer questions outside of this domain."},
            {"role": "user", "content": user_message}
        ]
        chat_response = client.chat.complete(model=model, messages=messages)
        bot_response = chat_response.choices[0].message.content
        return jsonify({"response": bot_response})
    except Exception as e:
        print(f"Error in chatbot API call: {e}") # Add detailed logging
        # Check for specific Mistral API errors if possible
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
             print(f"Mistral API response error: {e.response.text}")
             return jsonify({"error": f"Mistral API error: {e.response.text}"}), 500
        elif isinstance(e, Exception): # Catch other potential exceptions
             return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500
        else:
             return jsonify({"error": "Could not get response from chatbot API."}), 500

@app.route('/doctor_appointments')
def doctor_appointments():
    if 'doctor_user_id' not in session:
        return redirect(url_for('doctor_login'))

    doctor_id = session['doctor_user_id']
    cursor = link.cursor()
    try:
        # Fetch appointments for the logged-in doctor with user names
        cursor.execute("""
            SELECT a.*, u.name
            FROM appointments a
            JOIN users u ON a.user_id = u.id
            WHERE a.doctor_id = %s
            ORDER BY a.appointment_date, a.appointment_time
        """, (doctor_id,))
        doctor_appointments_list = cursor.fetchall()

        return render_template('doctor_appointments.html', doctor_appointments=doctor_appointments_list)

    except Exception as e:
        error = str(e)
        return render_template('doctor_appointments.html', error=error)
    finally:
        cursor.close()

@app.route('/update_appointment_status/<int:appointment_id>', methods=['POST'])
def update_appointment_status(appointment_id):
    if 'doctor_user_id' not in session:
        return redirect(url_for('doctor_login'))

    if request.method == 'POST':
        status = request.form.get('status')
        doctor_id = session['doctor_user_id']

        if status in ['accepted', 'rejected']:
            cursor = link.cursor()
            try:
                # Ensure the appointment belongs to the logged-in doctor
                cursor.execute("SELECT doctor_id FROM appointments WHERE id = %s", (appointment_id,))
                appointment = cursor.fetchone()

                if appointment and appointment[0] == doctor_id:
                    cursor.execute(
                        "UPDATE appointments SET status = %s WHERE id = %s",
                        (status, appointment_id)
                    )
                    link.commit()
                    flash(f'Appointment {status} successfully!', 'success')
                else:
                    flash('Appointment not found or does not belong to you.', 'danger')

            except Exception as e:
                link.rollback()
                flash(f'Error updating appointment status: {str(e)}', 'danger')
            finally:
                cursor.close()
        else:
            flash('Invalid status provided.', 'danger')

        return redirect(url_for('doctor_appointments'))
#####VGG19########################
# Load and preprocess image
def load_image(image_path):
    image = Image.open(image_path).convert('RGB')
    image_tensor = preprocess(image).unsqueeze(0)  # Add batch dimension
    return image_tensor

# Visualize a feature map
def save_feature_map(feature_tensor, layer_name):
    # Take first channel only for visualization
    feature = feature_tensor[0][0].cpu().detach().numpy()
    feature -= feature.min()
    feature /= feature.max()
    feature = np.uint8(feature * 255)
    img = Image.fromarray(feature)
    img.save(os.path.join(output_dir, f"{layer_name}.png"))


def get_activation(name):
    def hook(model, input, output):
        feature_maps[name] = output
        save_feature_map(output, name)
        print(f"[INFO] Captured features from layer: {name}, shape: {output.shape}")
    return hook


if __name__ == '__main__':
    app.run(debug=True)
