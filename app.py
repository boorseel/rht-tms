from flask import Flask, render_template, request, flash, redirect, url_for
from pyzbar.pyzbar import decode
from PIL import Image
from flask import send_file
import cv2
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import hashlib
import barcode
from barcode.writer import ImageWriter
from flask import send_file
from openpyxl import Workbook
import os
import random
import string
from flask_mail import Mail, Message
from sqlalchemy.sql import text
from sqlalchemy import Column, Integer, String, BigInteger
from sqlalchemy.orm import declarative_base, Session
from flask_migrate import Migrate
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

# Debugging
import sentry_sdk
from sentry_sdk import capture_exception

sentry_sdk.init(
    os.getenv("SENTRY_DSN"),
    traces_sample_rate=1.0
)

# Change working directory
try:
    os.chdir('/var/www/rht-tms')
except FileNotFoundError as e:
    capture_exception(e)

def create_directory_if_not_exists(directory_path):
    try:
        if not os.path.exists(directory_path):
            os.makedirs(directory_path)
    except OSError as e:
        capture_exception(e)

def initialize_directories():
    required_directories = [
        'barcodes',
        'exports'
    ]
    for directory in required_directories:
        create_directory_if_not_exists(directory)

initialize_directories()

# Initialize Flask app
app = Flask(__name__)

# MAIL SETTINGS
app.config['MAIL_SERVER'] = os.getenv("MAIL_SERVER")
app.config['MAIL_PORT'] = os.getenv("MAIL_PORT")
app.config['MAIL_USE_TLS'] = os.getenv("MAIL_USE_TLS")
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
mail = Mail(app)

# DATABASE SETTINGS
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URI")
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")

try:
    db = SQLAlchemy(app)
except SQLAlchemyError as e:
    capture_exception(e)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ActivityLog model
class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    action = db.Column(db.String(50), nullable=False)
    ticket_ID = db.Column(db.BigInteger, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, user_id, action, ticket_ID):
        self.user_id = user_id
        self.action = action
        self.ticket_ID = ticket_ID


# Event model
class Event(db.Model):
    event_ID = db.Column(db.String(6), primary_key=True)
    event_name = db.Column(db.String(255), nullable=False)
    event_date = db.Column(db.Date, nullable=False)


# Ticket model
class Ticket(db.Model):
    __tablename__ = 'tickets'
    ticket_ID = db.Column(db.String, primary_key=True)
    event_ID = db.Column(db.String, db.ForeignKey('event.event_ID'), nullable=False)
    student_ID = db.Column(db.String, db.ForeignKey('students.student_ID'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="inactive")


# User model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(255), nullable=False)

    @classmethod
    def get_by_id(cls, user_id):
        return cls.query.get(int(user_id))


# Student model
class Students(db.Model):
    cli_ID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_ID = db.Column(db.String(255), nullable=False, unique=True)
    student_NAME = db.Column(db.String(255), nullable=False)
    student_SNAME = db.Column(db.String(255), nullable=False)
    student_GSM = db.Column(db.String(255))
    student_EMAIL = db.Column(db.String(255), nullable=False, unique=True)
    student_DEP = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f"<Students {self.student_ID} - {self.student_NAME} {self.student_SNAME}>"

# Initialize all the tables after defining the models
with app.app_context():
    db.create_all()
# User loader
@login_manager.user_loader
def load_user(user_id):
    return User.get_by_id(user_id)

# Log out
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have successfully logged out.')
    return redirect(url_for('login'))

# Base
@app.route('/')
@login_required
def index():
    if current_user.role in ('admin', 'super_user'):
        return redirect(url_for('admin_main'))
    elif current_user.role == 'seller':
        return redirect(url_for('seller_main'))
    return redirect(url_for('login'))

# Login function
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()
        user = User.query.filter_by(username=username).first()
        if user and user.password == password:
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials.')
            return render_template('login.html')
    else:
        return render_template('login.html')

# Admin main landing
@app.route('/admin_main')
@login_required
def admin_main():
    if current_user.role not in ('admin', 'super_user'):
        flash('You do not have permission to access this page.')
        return redirect(url_for('index'))
    return render_template('admin_main.html')

# Seller main landing
@app.route('/seller_main')
@login_required
def seller_main():
    if current_user.role != 'seller':
        flash('You do not have permission to access this page.')
        return redirect(url_for('index'))
    return render_template('seller_main.html')
# Create user
@app.route('/create_user', methods=['GET', 'POST'])
@login_required
def create_user():
    if current_user.role != 'super_user':
        flash('You do not have permission to access this page.')
        return redirect(url_for('index'))  
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()
        role = request.form['role']
        if User.query.filter_by(username=username).first() or User.query.filter_by(email=email).first():
            flash('Username or Email already exists.')
            return render_template('create_user.html')
        new_user = User(username=username, email=email, password=password, role=role)
        db.session.add(new_user)
        db.session.commit()
        flash('User successfully created.')
        return redirect(url_for('index'))
    return render_template('create_user.html')

# EVENT CREATION
@app.route('/create_event', methods=['GET', 'POST'])
@login_required
def create_event():
    if current_user.role not in ('admin', 'super_user'):
        flash('You do not have permission to access this page.')
        return redirect(url_for('index'))
    if request.method == 'POST':
        event_name = request.form['event_name']
        event_date = request.form['event_date']
        event_date_obj = datetime.strptime(event_date, '%Y-%m-%d').date()
        unique_hash = hashlib.sha1(f"{event_name}{event_date}".encode('utf-8')).hexdigest()[:6]
        event_ID_int = int(unique_hash, 16)  # Convert unique_hash to integer
        if Event.query.filter_by(event_ID=event_ID_int).first():
            flash('Event ID already exists. Please try again.')
            return render_template('create_event.html')
        new_event = Event(event_ID=event_ID_int, event_name=event_name, event_date=event_date_obj)
        db.session.add(new_event)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash('Event ID already exists. Please try again.')
            return render_template('create_event.html')
        flash('Event successfully created.')
        # Create spent_tickets table for the new event
        create_ticket_table("spent_tickets_", event_ID_int)
        # Create active_tickets table for the new event
        create_ticket_table("active_tickets_", event_ID_int)
        # Create refund_tickets table for the new event
        create_ticket_table("refund_tickets_", event_ID_int)
        return redirect(url_for('index'))
    return render_template('create_event.html')

# Helper function to create ticket tables
def create_ticket_table(prefix, event_ID_int):
    table_name = f"{prefix}{event_ID_int}"
    create_table_sql = text(f"""
    CREATE TABLE {table_name} (
        ticket_ID BIGINT PRIMARY KEY,
        event_ID char(10) NOT NULL,
        student_ID VARCHAR(255) NOT NULL,
        FOREIGN KEY (event_ID) REFERENCES event(event_ID),
        FOREIGN KEY (student_ID) REFERENCES students(student_ID)
        );
    """)
    db.session.execute(create_table_sql)
    db.session.commit()
# SEARCH EVENT
@app.route('/search_events', methods=['GET', 'POST'])
@login_required
def search_events():
    events = Event.query.all()
    filtered_events = events
    if request.method == 'POST':
        search_term = request.form['search_term']
        event_date = request.form['event_date']
        if event_date:
            event_date = datetime.strptime(event_date, '%Y-%m-%d').date()
        filtered_events = [event for event in events if (search_term.lower() in event.event_name.lower()) and (event_date == '' or event.event_date == event_date)]
    return render_template('search_event.html', events=filtered_events)

# GENERATE TICKET
@app.route('/generate_tickets', methods=['GET', 'POST'])
@login_required
def generate_tickets():
    if current_user.role not in ('admin', 'super_user'):
        flash('You do not have permission to access this page.')
        return redirect(url_for('index'))
    events = Event.query.all()
    if request.method == 'POST':
        event_ID = request.form.get('event_ID')
        if event_ID is None:
            flash('Event ID not provided.', 'error')
            return redirect(url_for('index'))
        event = Event.query.filter_by(event_ID=event_ID).first()
        num_tickets = int(request.form.get('num_tickets', 0))
        if event is not None:
            ticket_IDs = []
            count = 1
            for _ in range(num_tickets):
                unique_number = f"{count:06}"
                ticket_ID = f"{event_ID}{unique_number}"
                ticket = Ticket(ticket_ID=ticket_ID, event_ID=event.event_ID)
                db.session.add(ticket)
                db.session.commit()
                # Generate barcode
                ean = barcode.get('ean13', ticket_ID, writer=ImageWriter())
                filename = f"barcodes/{ticket_ID}.png"
                ean.save(filename)
                ticket_IDs.append(ticket_ID)
                count += 1
            flash('Tickets generated successfully!')
            # Export ticket IDs to Excel
            wb = Workbook()
            ws = wb.active
            ws.title = f"Tickets for {event.event_name}"
            ws.append(['Ticket ID'])
            for ticket_ID in ticket_IDs:
                ws.append([ticket_ID])
            wb.save(f"exports/tickets_{event.event_name}.xlsx")
            flash(f"{num_tickets} ticket IDs successfully generated for {event.event_name}.")
            return send_file(f"exports/tickets_{event.event_name}.xlsx", as_attachment=True)
        else:
            flash("Event not found", "error")
            return redirect(url_for('index'))
    return render_template('generate_tickets.html', events=events)
# ACTIVATE TICKET
@app.route('/activate_ticket', methods=['GET', 'POST'])
@login_required
def activate_ticket():
    if current_user.role not in ('admin', 'super_user', 'seller'):
        flash('You do not have permission to access this page.')
        return redirect(url_for('index'))
    students = Students.query.all()
    if request.method == 'POST':
        ticket_ID = request.form.get('ticket_ID')
        if not ticket_ID:
            barcode_image = request.files.get('barcode_image')
            if barcode_image:
                image = Image.open(barcode_image)
                cv_image = np.array(image)
                decoded_objects = decode(cv_image)
                if decoded_objects:
                    ticket_ID = decoded_objects[0].data.decode("utf-8")
                else:
                    flash("No barcode found in the uploaded image.", "error")
                    return render_template('activate_ticket.html', students=students)
        student_ID = request.form.get('student_ID')
        ticket = Ticket.query.filter_by(ticket_ID=ticket_ID).first()
        student = Students.query.filter_by(student_ID=student_ID).first()
        if ticket and student:
            ticket.student_ID = student.student_ID
            db.session.commit()
            flash('Ticket successfully activated.')
            # Send email confirmation to the student
            event = Event.query.get(ticket.event_ID)
            msg = Message('Ticket Activation Confirmation',
                sender='your_email@example.com',
                recipients=[student.student_EMAIL])
            msg.body = f"Dear {student.student_NAME} {student.student_SNAME},\n\nYour ticket for {event.event_name} on {event.event_date.strftime('%Y-%m-%d')} has been successfully activated. Please keep this email for your records.\n\nBest regards,\nRadio HighTECH"
            mail.send(msg)
        else:
            flash('Ticket or student not found. Please check the information and try again.')
    return render_template('activate_ticket.html', students=students)

# REFUND TICKETS
@app.route('/refund_ticket', methods=['GET', 'POST']) 
@login_required 
def refund_ticket(): 
    if current_user.role not in ('admin', 'super_user', 'seller'): 
        flash('You do not have permission to access this page.') 
        return redirect(url_for('index'))
    if request.method == 'POST': 
        ticket_ID = request.form.get('ticket_ID', None)
        ticket = Ticket.query.filter_by(ticket_ID=ticket_ID).first()
        if ticket:
            event_ID = ticket.event_ID 
            active_tickets_table = f"active_tickets_{event_ID}" 
            refund_tickets_table = f"refund_tickets_{event_ID}" 
            # Move ticket from active_tickets to refund_tickets
            db.engine.execute(f"INSERT INTO {refund_tickets_table} SELECT * FROM {active_tickets_table} WHERE ticket_ID = :ticket_ID", {'ticket_ID': ticket_ID})
            db.engine.execute(f"DELETE FROM {active_tickets_table} WHERE ticket_ID = :ticket_ID", {'ticket_ID': ticket_ID})
            db.session.commit()
            # Log the refund action
            log = ActivityLog(user_id=current_user.id, action='refund', ticket_ID=ticket.ID)
            db.session.add(log)
            db.session.commit()
            flash('Ticket successfully refunded.')
        else:
            flash('Ticket not found. Please check the information and try again.')
    return render_template('refund_ticket.html')
# ANALYTICS
@app.route('/analytics')
@login_required
def analytics():
    if current_user.role not in ('admin', 'super_user'):
        flash('You do not have permission to access this page.')
        return redirect(url_for('index'))

    events = Event.query.all()
    event_analytics = []

    for event in events:
        event_ID = event.event_ID
        active_tickets_table = f"active_tickets_{event_ID}"
        refund_tickets_table = f"refund_tickets_{event_ID}"
        spent_tickets_table = f"spent_tickets_{event_ID}"

        # Calculate KPIs for the event
        with db.engine.connect() as connection:
            active_tickets_count = connection.execute(text(f"SELECT COUNT(*) FROM {active_tickets_table}")).scalar()
            refund_tickets_count = connection.execute(text(f"SELECT COUNT(*) FROM {refund_tickets_table}")).scalar()
            spent_tickets_count = connection.execute(text(f"SELECT COUNT(*) FROM {spent_tickets_table}")).scalar()

        event_analytics.append({
            'event_name': event.event_name,
            'event_date': event.event_date,
            'active_tickets': active_tickets_count,
            'refund_tickets': refund_tickets_count,
            'spent_tickets': spent_tickets_count
        })

    return render_template('analytics.html', event_analytics=event_analytics)

# Validate Ticket
@app.route('/validate_ticket', methods=['GET', 'POST'])
@login_required
def validate_ticket():
    student_data = None
    if current_user.role not in ('admin', 'super_user', 'seller'):
        flash('You do not have permission to access this page.')
        return redirect(url_for('index'))
    if request.method == 'POST':
        ticket_ID = request.form.get('ticket_ID')
        ticket = Ticket.query.filter_by(ticket_ID=ticket_ID).first()
        if ticket:
            event_ID = ticket.event_ID
            active_tickets_table = f"active_tickets_{event_ID}"
            spent_tickets_table = f"spent_tickets_{event_ID}"
            student_data = Students.query.filter_by(student_ID=ticket.student_ID).first()

            # Move tickets from active_tickets to spent_tickets
            with db.engine.connect() as connection:
                connection.execute(text(f"INSERT INTO {spent_tickets_table} SELECT * FROM {active_tickets_table} WHERE ticket_ID = :ticket_ID"), {'ticket_ID': ticket_ID})
                connection.execute(text(f"DELETE FROM {active_tickets_table} WHERE ticket_ID = :ticket_ID"), {'ticket_ID': ticket_ID})
                db.session.commit()

            # Log the validation action
            log = ActivityLog(user_id=current_user.id, action='validate', ticket_ID=ticket.ticket_ID)
            db.session.add(log)
            db.session.commit()
            flash('Ticket successfully validated.')
        else:
            flash('Ticket not found. Please check the information and try again.')

    return render_template('validate_ticket.html', student_data=student_data)

#Main
if __name__ == "__main__":
    initialize_directories()

    # Only create the database if it doesn't exist.
    if not os.path.isfile('./app.db'):
        with app.app_context():
            db.create_all()

    migrate = Migrate(app, db)

    app.run(debug=True, host="0.0.0.0", port=5000)
