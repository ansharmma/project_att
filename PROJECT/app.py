from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
import pandas as pd
from graphs import generate_graphs_and_stats
from analytics import AttendanceAnalytics
import json
import sqlite3
from functools import wraps
import logging
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
import calendar
from werkzeug.utils import secure_filename

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')  # Use environment variable in production
UPLOAD_FOLDER = "data"
STATIC_FOLDER = "static"
USERS_FILE = "data/users.json"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Create necessary directories if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(STATIC_FOLDER, exist_ok=True)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    logger.error(f"Page not found: {request.url}")
    return render_template('error.html', error="Page not found"), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Server error: {error}")
    return render_template('error.html', error="Internal server error"), 500

# User class for authentication
class User(UserMixin):
    def __init__(self, id, username, password_hash, role):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.role = role

# Load users from JSON file
def load_users():
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r') as f:
                users_data = json.load(f)
                return {user_id: User(user_id, data['username'], data['password_hash'], data['role']) 
                        for user_id, data in users_data.items()}
        return {}
    except Exception as e:
        logger.error(f"Error loading users: {e}")
        return {}

# Save users to JSON file
def save_users(users):
    try:
        users_data = {user_id: {'username': user.username, 'password_hash': user.password_hash, 'role': user.role} 
                      for user_id, user in users.items()}
        with open(USERS_FILE, 'w') as f:
            json.dump(users_data, f)
    except Exception as e:
        logger.error(f"Error saving users: {e}")
        flash("Error saving user data", "error")

# Initialize users
users = load_users()

# Create default admin if no users exist
if not users:
    try:
        admin = User('1', 'admin', generate_password_hash('admin123'), 'admin')
        users['1'] = admin
        save_users(users)
        logger.info("Default admin user created")
    except Exception as e:
        logger.error(f"Error creating default admin: {e}")

@login_manager.user_loader
def load_user(user_id):
    return users.get(user_id)

ALLOWED_EXTENSIONS = {"csv"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_csv(filepath):
    try:
        df = pd.read_csv(filepath)
        
        # Check for required columns
        if 'Name' not in df.columns:
            return False, "CSV file must contain a 'Name' column"
        if len(df.columns) < 2:
            return False, "CSV file must contain at least one date column"
            
        # Validate date columns
        date_columns = df.columns[1:]
        for col in date_columns:
            try:
                datetime.strptime(col, '%Y-%m-%d')
            except ValueError:
                return False, f"Invalid date format in column '{col}'. Expected format: YYYY-MM-DD"
                
        # Validate attendance values
        for col in date_columns:
            invalid_values = df[col].apply(lambda x: str(x).upper() not in ['P', 'A', ''])
            if invalid_values.any():
                return False, f"Invalid attendance values in column '{col}'. Only 'P' (Present) and 'A' (Absent) are allowed."
                
        return True, None
    except Exception as e:
        logger.error(f"Error validating CSV: {e}")
        return False, f"Error reading CSV file: {str(e)}"

def init_db():
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      username TEXT UNIQUE NOT NULL,
                      password TEXT NOT NULL,
                      role TEXT NOT NULL)''')
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        try:
            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            c.execute('SELECT * FROM users WHERE username = ?', (username,))
            user = c.fetchone()
            conn.close()
            
            if user and check_password_hash(user[2], password):
                session['user_id'] = user[0]
                session['username'] = user[1]
                session['role'] = user[3]
                flash('Login successful!', 'success')
                logger.info(f"User {username} logged in successfully")
                return redirect(url_for('index'))
            else:
                flash('Invalid username or password', 'error')
                logger.warning(f"Failed login attempt for user {username}")
        except Exception as e:
            logger.error(f"Error during login: {e}")
            flash('An error occurred during login', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        role = request.form['role']
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return redirect(url_for('register'))
        
        try:
            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            
            c.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
                     (username, generate_password_hash(password), role))
            conn.commit()
            flash('Registration successful! Please login.', 'success')
            logger.info(f"New user registered: {username}")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists', 'error')
            logger.warning(f"Registration attempt with existing username: {username}")
        except Exception as e:
            logger.error(f"Error during registration: {e}")
            flash('An error occurred during registration', 'error')
        finally:
            conn.close()
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    logger.info(f"User {session.get('username', 'unknown')} logged out")
    return redirect(url_for('login'))

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first', 'error')
            logger.warning(f"Unauthorized access attempt to {request.url}")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    theme = session.get('theme', 'light')  # Default to light
    stats = None
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], "attendance.csv")
    
    # Check if data is already loaded
    if request.args.get('data') == 'loaded' and os.path.exists(filepath):
        try:
            stats = generate_graphs_and_stats(filepath)
            if stats is None:
                flash("Error: Could not load attendance data", "error")
                logger.error("Failed to load attendance data")
                return redirect(url_for("index"))
        except Exception as e:
            flash(f"Error loading data: {str(e)}", "error")
            logger.error(f"Error loading attendance data: {e}")
            return redirect(url_for("index"))
    
    if request.method == "POST":
        if "file" not in request.files:
            flash("No file part", "error")
            return redirect(request.url)

        file = request.files["file"]
        if file.filename == "":
            flash("No file selected", "error")
            return redirect(request.url)

        if file and allowed_file(file.filename):
            # Save the file with a secure filename
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], "attendance.csv")
            file.save(filepath)

            # Validate CSV format
            is_valid, error_message = validate_csv(filepath)
            if not is_valid:
                flash(error_message, "error")
                logger.error(f"Invalid CSV file: {error_message}")
                # Remove the invalid file
                if os.path.exists(filepath):
                    os.remove(filepath)
                return redirect(request.url)

            try:
                stats = generate_graphs_and_stats(filepath)
                if stats is None:
                    flash("Error: Could not process attendance data", "error")
                    logger.error("Failed to process attendance data")
                    return redirect(request.url)
                flash("CSV uploaded and graphs updated successfully!", "success")
                logger.info("Attendance data processed successfully")
            except Exception as e:
                flash(f"Error processing file: {str(e)}", "error")
                logger.error(f"Error processing attendance file: {e}")
                return redirect(request.url)
        else:
            flash("Only CSV files are allowed.", "error")
            logger.warning(f"Invalid file type attempted: {file.filename}")

    return render_template("index.html", stats=stats, theme=theme)

@app.route("/dashboard")
@login_required
def dashboard():
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], "attendance.csv")
    if not os.path.exists(filepath):
        flash("Please upload attendance data first", "error")
        logger.warning("Dashboard accessed without attendance data")
        return redirect(url_for("index"))
    
    try:
        analytics = AttendanceAnalytics(filepath)
        analytics.generate_enhanced_graphs()
        stats = analytics.get_summary_statistics()
        
        # Add enhancement data
        enhancements = {
            'monthly_trend': {
                'title': 'Monthly Attendance Trend',
                'description': 'Shows the attendance rate trends over different months, helping identify seasonal patterns and overall attendance trajectory.',
                'image': 'monthly_attendance_trend.png',
                'data': {
                    'headers': ['Month', 'Attendance Rate (%)'],
                    'rows': [[month, f"{rate:.1f}"] for month, rate in stats.monthly_stats.items()]
                }
            },
            'day_pattern': {
                'title': 'Attendance by Day of Week',
                'description': 'Analyzes attendance patterns across different days of the week, helping identify which days have better attendance rates.',
                'image': 'day_wise_attendance.png',
                'data': {
                    'headers': ['Day', 'Attendance Rate (%)'],
                    'rows': [[day, f"{rate:.1f}"] for day, rate in stats.day_patterns.items()]
                }
            },
            'heatmap': {
                'title': 'Student Attendance Heatmap',
                'description': 'A comprehensive view of attendance patterns for all students across all dates, with color coding to quickly identify attendance trends.',
                'image': 'attendance_heatmap.png',
                'data': None
            }
        }
        
        logger.info("Dashboard generated successfully")
        return render_template("dashboard.html", stats=stats, enhancements=enhancements)
    except Exception as e:
        flash(f"Error generating dashboard: {str(e)}", "error")
        logger.error(f"Error generating dashboard: {e}")
        return redirect(url_for("index"))

@app.route("/enhancement/<enhancement_type>")
@login_required
def enhancement_details(enhancement_type):
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], "attendance.csv")
    if not os.path.exists(filepath):
        flash("Please upload attendance data first", "error")
        logger.warning("Enhancement details accessed without attendance data")
        return redirect(url_for("index"))
    
    try:
        analytics = AttendanceAnalytics(filepath)
        stats = analytics.get_summary_statistics()
        
        # Get enhancement data
        enhancements = {
            'monthly_trend': {
                'title': 'Monthly Attendance Trend',
                'description': 'Shows the attendance rate trends over different months, helping identify seasonal patterns and overall attendance trajectory.',
                'image': 'monthly_attendance_trend.png',
                'data': {
                    'headers': ['Month', 'Attendance Rate (%)'],
                    'rows': [[month, f"{rate:.1f}"] for month, rate in stats.monthly_stats.items()]
                }
            },
            'day_pattern': {
                'title': 'Attendance by Day of Week',
                'description': 'Analyzes attendance patterns across different days of the week, helping identify which days have better attendance rates.',
                'image': 'day_wise_attendance.png',
                'data': {
                    'headers': ['Day', 'Attendance Rate (%)'],
                    'rows': [[day, f"{rate:.1f}"] for day, rate in stats.day_patterns.items()]
                }
            },
            'heatmap': {
                'title': 'Student Attendance Heatmap',
                'description': 'A comprehensive view of attendance patterns for all students across all dates, with color coding to quickly identify attendance trends.',
                'image': 'attendance_heatmap.png',
                'data': None
            }
        }
        
        if enhancement_type not in enhancements:
            flash("Invalid enhancement type", "error")
            logger.warning(f"Invalid enhancement type requested: {enhancement_type}")
            return redirect(url_for("dashboard"))
            
        enhancement = enhancements[enhancement_type]
        logger.info(f"Enhancement details generated for {enhancement_type}")
        return render_template("enhancement_details.html", 
                             enhancement_title=enhancement['title'],
                             enhancement_description=enhancement['description'],
                             enhancement_image=enhancement['image'],
                             enhancement_data=enhancement['data'])
    except Exception as e:
        flash(f"Error generating enhancement details: {str(e)}", "error")
        logger.error(f"Error generating enhancement details: {e}")
        return redirect(url_for("dashboard"))

@app.route("/student/<student_name>")
@login_required
def student(student_name):
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], "attendance.csv")
    if not os.path.exists(filepath):
        flash("Please upload attendance data first", "error")
        logger.warning("Student portal accessed without attendance data")
        return redirect(url_for("index"))
    
    try:
        analytics = AttendanceAnalytics(filepath)
        student_data = analytics.get_student_data(student_name)
        if student_data is None:
            flash(f"Student {student_name} not found", "error")
            logger.warning(f"Student not found: {student_name}")
            return redirect(url_for("index"))
        logger.info(f"Student data generated for {student_name}")
        return render_template("student.html", student_data=student_data)
    except Exception as e:
        flash(f"Error generating student portal: {str(e)}", "error")
        logger.error(f"Error generating student portal: {e}")
        return redirect(url_for("index"))

@app.route("/leave", methods=["GET", "POST"])
@login_required
def leave():
    if request.method == "POST":
        action = request.form.get("action")
        
        if action in ["approve", "reject"]:
            # Handle leave request approval/rejection
            student_name = request.form.get("student_name")
            leave_date = request.form.get("leave_date")
            
            leave_file = os.path.join(app.config["UPLOAD_FOLDER"], "leaves.json")
            if os.path.exists(leave_file):
                try:
                    with open(leave_file, 'r') as f:
                        leaves = json.load(f)
                    
                    if student_name in leaves:
                        for leave in leaves[student_name]:
                            if leave["date"] == leave_date:
                                leave["status"] = "approved" if action == "approve" else "rejected"
                                break
                        
                        with open(leave_file, 'w') as f:
                            json.dump(leaves, f)
                        
                        flash(f"Leave request has been {action}d", "success")
                        logger.info(f"Leave request {action}d for {student_name} on {leave_date}")
                except Exception as e:
                    flash(f"Error processing leave request: {str(e)}", "error")
                    logger.error(f"Error processing leave request: {e}")
            return redirect(url_for("leave"))
        
        # Handle new leave request submission
        student_name = request.form.get("student_name")
        leave_date = request.form.get("leave_date")
        leave_type = request.form.get("leave_type")
        reason = request.form.get("reason")
        
        try:
            # Save leave request
            leave_file = os.path.join(app.config["UPLOAD_FOLDER"], "leaves.json")
            leaves = {}
            
            if os.path.exists(leave_file):
                with open(leave_file, 'r') as f:
                    leaves = json.load(f)
            
            if student_name not in leaves:
                leaves[student_name] = []
            
            leaves[student_name].append({
                "date": leave_date,
                "type": leave_type,
                "reason": reason,
                "status": "pending"
            })
            
            with open(leave_file, 'w') as f:
                json.dump(leaves, f)
            
            flash(f"Leave request submitted for {student_name}", "success")
            logger.info(f"New leave request submitted for {student_name}")
        except Exception as e:
            flash(f"Error submitting leave request: {str(e)}", "error")
            logger.error(f"Error submitting leave request: {e}")
        return redirect(url_for("leave"))
    
    # Get existing leaves
    leave_file = os.path.join(app.config["UPLOAD_FOLDER"], "leaves.json")
    leaves = {}
    
    try:
        if os.path.exists(leave_file):
            with open(leave_file, 'r') as f:
                leaves = json.load(f)
    except Exception as e:
        flash(f"Error loading leave requests: {str(e)}", "error")
        logger.error(f"Error loading leave requests: {e}")
    
    return render_template("leave.html", leaves=leaves)

@app.route("/leave/export/pdf")
@login_required
def export_leave_pdf():
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        import io
        
        # Get leave data
        leave_file = os.path.join(app.config["UPLOAD_FOLDER"], "leaves.json")
        leaves = {}
        
        if os.path.exists(leave_file):
            with open(leave_file, 'r') as f:
                leaves = json.load(f)
        
        # Create PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []
        
        # Add title
        styles = getSampleStyleSheet()
        elements.append(Paragraph("Leave Report", styles["Title"]))
        elements.append(Spacer(1, 12))
        
        # Add summary
        total_requests = sum(len(student_leaves) for student_leaves in leaves.values())
        pending_requests = sum(1 for student_leaves in leaves.values() 
                             for leave in student_leaves if leave["status"] == "pending")
        approved_requests = sum(1 for student_leaves in leaves.values() 
                              for leave in student_leaves if leave["status"] == "approved")
        rejected_requests = sum(1 for student_leaves in leaves.values() 
                              for leave in student_leaves if leave["status"] == "rejected")
        
        elements.append(Paragraph(f"Total Leave Requests: {total_requests}", styles["Normal"]))
        elements.append(Paragraph(f"Pending Requests: {pending_requests}", styles["Normal"]))
        elements.append(Paragraph(f"Approved Requests: {approved_requests}", styles["Normal"]))
        elements.append(Paragraph(f"Rejected Requests: {rejected_requests}", styles["Normal"]))
        elements.append(Spacer(1, 12))
        
        # Add leave requests table
        elements.append(Paragraph("Leave Requests", styles["Heading2"]))
        elements.append(Spacer(1, 12))
        
        # Create table data
        data = [["Student", "Date", "Type", "Status", "Reason"]]
        for student, student_leaves in leaves.items():
            for leave in student_leaves:
                data.append([
                    student,
                    leave["date"],
                    leave["type"].title(),
                    leave["status"].title(),
                    leave["reason"]
                ])
        
        # Create table
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), (0.8, 0.8, 0.8)),
            ('TEXTCOLOR', (0, 0), (-1, 0), (0, 0, 0)),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), (0.9, 0.9, 0.9)),
            ('TEXTCOLOR', (0, 1), (-1, -1), (0, 0, 0)),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, (0, 0, 0)),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(table)
        
        # Build PDF
        doc.build(elements)
        
        # Get the value of the BytesIO buffer
        pdf = buffer.getvalue()
        buffer.close()
        
        logger.info("Leave report PDF generated successfully")
        return send_file(
            io.BytesIO(pdf),
            mimetype='application/pdf',
            as_attachment=True,
            download_name='leave_report.pdf'
        )
    except Exception as e:
        flash(f"Error generating PDF: {str(e)}", "error")
        logger.error(f"Error generating leave report PDF: {e}")
        return redirect(url_for("leave"))

def get_calendar_data(attendance_data):
    """Generate calendar data from attendance records"""
    calendar_data = {}
    
    # Get unique dates from attendance data
    dates = pd.to_datetime(attendance_data.columns[1:]).unique()
    
    for date in dates:
        # Count present students for each date
        present_count = attendance_data.iloc[:, attendance_data.columns.get_loc(date)].sum()
        total_students = len(attendance_data)
        attendance_percentage = (present_count / total_students) * 100
        
        calendar_data[date.strftime('%Y-%m-%d')] = {
            'attendance_percentage': round(attendance_percentage, 1),
            'present_count': int(present_count),
            'total_students': total_students
        }
    
    return calendar_data

def get_previous_month(year, month):
    if month == 1:
        return year - 1, 12
    return year, month - 1

def get_next_month(year, month):
    if month == 12:
        return year + 1, 1
    return year, month + 1

@app.route('/calendar')
@login_required
def calendar_view():
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], "attendance.csv")
    if not os.path.exists(filepath):
        flash('Please upload attendance data first', 'error')
        return redirect(url_for('index'))
    
    try:
        # Get year and month from query parameters or use current date
        year = int(request.args.get('year', datetime.now().year))
        month = int(request.args.get('month', datetime.now().month))
        
        # Get navigation parameters
        prev_year, prev_month = get_previous_month(year, month)
        next_year, next_month = get_next_month(year, month)
        
        # Read the attendance data
        attendance_data = pd.read_csv(filepath)
        
        # Convert date columns to datetime
        date_columns = attendance_data.columns[1:]  # Skip the 'Name' column
        
        # Calculate calendar data
        calendar_data = {}
        for date_col in date_columns:
            try:
                # Parse the date from the column name
                date = datetime.strptime(date_col, '%Y-%m-%d')
                
                # Format the date string to match the template's expected format
                date_str = date.strftime('%Y-%m-%d')
                
                # Calculate attendance statistics
                present_count = attendance_data[date_col].sum()
                total_students = len(attendance_data)
                attendance_percentage = (present_count / total_students) * 100
                
                calendar_data[date_str] = {
                    'attendance_percentage': round(attendance_percentage, 1),
                    'present_count': int(present_count),
                    'total_students': total_students
                }
            except Exception as e:
                logger.error(f"Error processing date {date_col}: {str(e)}")
                continue
        
        # Get calendar for the specified month
        cal = calendar.monthcalendar(year, month)
        
        # Get month name
        month_name = calendar.month_name[month]
        
        # Get today's date for highlighting
        today = datetime.now()
        
        return render_template('calendar.html',
                             cal=cal,
                             year=year,
                             month=month,
                             month_name=month_name,
                             today=today,
                             calendar_data=calendar_data,
                             prev_year=prev_year,
                             prev_month=prev_month,
                             next_year=next_year,
                             next_month=next_month)
                             
    except Exception as e:
        logger.error(f"Error in calendar view: {str(e)}")
        flash('Error loading calendar data', 'error')
        return redirect(url_for('index'))

@app.route('/set_theme/<theme>')
def set_theme(theme):
    if theme in ['light', 'dark']:
        session['theme'] = theme
    return redirect(request.referrer or url_for('index'))

def generate_graphs_and_stats(filepath):
    try:
        df = pd.read_csv(filepath)
        df.set_index('Name', inplace=True)
        
        # Convert attendance values to numeric (1 for Present, 0 for Absent)
        df = df.applymap(lambda x: 1 if str(x).upper() == 'P' else (0 if str(x).upper() == 'A' else None))
        
        # Calculate statistics
        total_days = len(df.columns)
        present_days = df.sum(axis=1)
        absent_days = total_days - present_days
        attendance_percentage = (present_days / total_days * 100).round(2)
        
        # Create attendance summary
        attendance_summary = pd.DataFrame({
            'Present Days': present_days,
            'Absent Days': absent_days,
            'Attendance %': attendance_percentage
        })
        
        # Generate graphs
        plt.figure(figsize=(12, 6))
        attendance_percentage.plot(kind='bar')
        plt.title('Attendance Percentage by Student')
        plt.xlabel('Student')
        plt.ylabel('Attendance Percentage')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig('static/attendance_graph.png')
        plt.close()
        
        # Generate heatmap
        plt.figure(figsize=(15, 8))
        sns.heatmap(df, cmap='RdYlGn', cbar_kws={'label': 'Attendance'})
        plt.title('Attendance Heatmap')
        plt.xlabel('Date')
        plt.ylabel('Student')
        plt.tight_layout()
        plt.savefig('static/attendance_heatmap.png')
        plt.close()
        
        return {
            'summary': attendance_summary.to_html(classes='table table-striped'),
            'graph_path': 'static/attendance_graph.png',
            'heatmap_path': 'static/attendance_heatmap.png'
        }
    except Exception as e:
        logger.error(f"Error generating graphs and stats: {e}")
        return None

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
