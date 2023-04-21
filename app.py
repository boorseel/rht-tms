from flask import Flask, render_template, request, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
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
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base, Session
from flask_migrate import Migrate

#Debuging
import sentry_sdk
sentry_sdk.init(
            dsn="https://e577e42812b045689b535c6a52337dc4@o4505041920065536.ingest.sentry.io/4505041925439488",
            traces_sample_rate=1.0
            )

#OS SETTINGS
os.chdir('/var/www/rht-tms')


def create_directory_if_not_exists(directory_path):
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)


def initialize_directories():
    required_directories = [
        'barcodes',
        'exports'
    ]
    for directory in required_directories:
        create_directory_if_not_exists(directory)

initialize_directories()

# MAIL SETTINGS
app = Flask(__name__)
app.config['MAIL_SERVER'] = 'smtp.example.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your_email@example.com'
app.config['MAIL_PASSWORD'] = 'your_email_password'
mail = Mail(app)

# DATABASE SETTINGS
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:11235813213455Ba!!!@localhost/rht_tms'
app.config['SECRET_KEY'] = '11235813213455Ba!!!'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Event model
class Event(db.Model):
    event_ID = db.Column(db.String(6), primary_key=True)
    event_Name = db.Column(db.String(255), nullable=False)
    event_Date = db.Column(db.Date, nullable=False)

# Ticket model
class Ticket(db.Model):
    __tablename__ = 'tickets'
    ticket_ID = db.Column(db.String, primary_key=True)
    event_ID = db.Column(db.Integer)

# User model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(255), nullable=False)

    @classmethod
    def get_by_id(cls, user_id):
        return db.session.query(cls).get(int(user_id))

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

# BASE
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
        print("User is already authenticated")
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()
        user = User.query.filter_by(username=username).first()
        if user:
            print(f"Expected password: {user.password}, provided password: {password}")
        if user and user.password == password:
            login_user(user)
            print("User logged in successfully")
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials.')
            print("Invalid credentials")
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
    if current_user.role == 'seller':
        return render_template('seller_main.html')



# Create user
@app.route('/create_user', methods=['GET', 'POST'])
@login_required
def create_user():
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.')
        return redirect(url_for('index'))  
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()
        role = request.form['role']
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
        event_Name = request.form['event_Name'] 
        event_Date = request.form['event_Date'] 
        event_Date_obj = datetime.strptime(event_Date, '%Y-%m-%d') 
        unique_hash = hashlib.sha1(f"{event_Name}{event_Date}".encode('utf-8')).hexdigest()[:6]
        new_event = Event(event_ID=unique_hash, event_Name=event_Name, event_Date=event_Date_obj) 
        db.session.add(new_event) 
        db.session.commit() 
        flash('Event successfully created.') 
   return render_template('create_event.html')   

# SEARCH EVENT 
@app.route('/search_events', methods=['GET', 'POST']) 
@login_required 
def search_events(): 
    events = Event.query.all() 
    filtered_events = events 
    if request.method == 'POST': 
        search_term = request.form['search_term']
        event_Date = request.form['event_Date']
        filtered_events = [event for event in events if (search_term.lower) in event.event_Name.lower()] and (event_Date == '' or event.event_Date == datetime.strptime(event_Date, '%Y-%m-%d'))
        return render_template('search_events.html', events=filtered_event)

@app.route('/generate_tickets', methods=['GET', 'POST'])
@login_required
def generate_tickets():
    if current_user.role not in ('admin', 'super_user'):
        flash('You do not have permission to access this page.')
        return redirect(url_for('index'))
    events = Event.query.all()
    if request.method == 'POST':
        print("Request method is POST")
        event_ID = None
        try:
            event_ID = request.form['event_ID']
        except KeyError:
            flash('Event ID not provided.', 'error')
            return redirect(url_for('index'))
        print(f"Event ID: {event_ID}")
        event = db.session.query(Event).filter_by(event_ID=event_ID).first()
        num_tickets = int(request.form.get('num_tickets', 0))
        print(f"Number of tickets to generate: {num_tickets}")
        if event is not None:
            ticket_ids = []
            print(f"Generating {num_tickets} tickets for event ID {event_ID}")
            flash('Event found.', 'info')
            print("Starting ticket generation...")

            # Initialize count variable
            count = 1

            for _ in range(num_tickets):
                # Generate ticket ID using event_ID and count
                ticket_id = f"{event_ID}{count:03d}"

                ticket = Ticket(ticket_ID=ticket_id, event_ID=event.event_ID)
                db.session.add(ticket)
                db.session.commit()
                print("Ticket committed to database:", ticket_id)
                # Generate barcode
                ean = barcode.get('ean13', ticket_id, writer=ImageWriter())
                filename = f"barcodes/{ticket_id}.png"
                ean.save(filename)
                ticket_ids.append(ticket_id)
                print("Generating barcode for ticket:", ticket_id)
                ean.save(filename)
                print("Barcode saved:", filename)

                # Increment count variable
                count += 1

            flash('Tickets generated successfully!')
            # Export ticket IDs to Excel
            print(f"{num_tickets} ticket IDs successfully generated for {event.event_Name}.")
            wb = Workbook()
            ws = wb.active
            ws.title = f"Tickets for {event.event_Name}"
            ws.append(['Ticket ID'])
            for ticket_id in ticket_ids:
                ws.append([ticket_id])
            wb.save(f"exports/tickets_{event.event_Name}.xlsx")
            flash(f"{num_tickets} ticket IDs successfully generated for {event.event_Name}.")
            return send_file(f"exports/tickets_{event.event_Name}.xlsx", as_attachment=True)
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
    ticket = None  # Initialize the 'ticket' variable with a default value
    student = None  # Initialize the 'student' variable with a default value

    if request.method == 'POST':
        ticket_id = request.form['ticket_id']
        student_id = request.form['student_id']

        ticket = Ticket.query.filter_by(ticket_ID=ticket_id).first()
        student = Student.query.filter_by(student_ID=student_id).first()

        if ticket and student:
            ticket.student_id = student.id
            db.session.commit()
            flash('Ticket successfully activated.')

            # Send email confirmation to the student
            event = Event.query.get(ticket.event_ID)  # Corrected the line to query Event
            msg = Message('Ticket Activation Confirmation',
                          sender='your_email@example.com',
                          recipients=[students.student_EMAIL])  
            msg.body = f"Dear {students.student_NAME} {students.student_SNAME},\n\nYour ticket for {event.event_Name} on {event.event_Date.strftime('%Y-%m-%d')} has been successfully activated. Please keep this email for your records.\n\nBest regards,\nRadio HighTECH"
            mail.send(msg)
        else:
            flash('Ticket or student not found. Please check the information and try again.')
            return render_template('activate_ticket.html')

    return render_template('activate_ticket.html', students=students)

     
# REFUND TICKETS    
@app.route('/refund_ticket', methods=['GET', 'POST']) 
@login_required 
def refund_ticket(): 
    if current_user.role not in ('admin', 'super_user', 'seller'): 
        flash('You do not have permission to access this page.') 
        return redirect(url_for('index'))

    ticket = None
    
    if request.method == 'POST': 
        ticket_id = request.form['ticket_id'] 
        ticket = Ticket.query.filter_by(ticket_ID=ticket_id).first()
        if ticket:
            event_ID = ticket.event_ID 
            active_tickets_table = f"active_tickets_{event_ID}" 
            refund_tickets_table = f"refund_tickets_{event_ID}" 

    if ticket:
        # Move ticket from active_tickets to refund_tickets
        db.engine.execute(f"INSERT INTO {refund_tickets_table} SELECT * FROM {active_tickets_table} WHERE ticket_ID = '{ticket_id}'")
        db.engine.execute(f"DELETE FROM {active_tickets_table} WHERE ticket_ID = '{ticket_id}'")
        db.session.commit()

        # Log the refund action
        log = ActivityLog(user_id=current_user.id, action='refund', ticket_id=ticket.id)
        db.session.add(log)
        db.session.commit()
        flash('Ticket successfully refunded.')
    else:
        flash('Ticket not found. Please check the information and try again.')
        return render_template('refund_ticket.html')

    return render_template('refund_ticket.html')

#ANALYTICS   
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
        
        #Calculate KPIs for the event 
        active_tickets_count = db.engine.execute(text(f"SELECT COUNT(*) FROM {active_tickets_table}")).scalar()
        refund_tickets_count = db.engine.execute(text(f"SELECT COUNT(*) FROM {refund_tickets_table}")).scalar()
        spent_tickets_count = db.engine.execute(text(f"SELECT COUNT(*) FROM {spent_tickets_table}")).scalar()   
        event_analytics.append({ 
            'event_Name': event.event_Name, 
            'event_Date': event.event_Date, 
            'active_tickets': active_tickets_count, 
            'refund_tickets': refund_tickets_count, 
            'spent_tickets': spent_tickets_count 
            })
        return render_template('analytics.html', event_analytics=event_analytics)   

#TICKET VALIDATION    
@app.route('/validate_ticket', methods=['GET', 'POST'])  
@login_required  
def validate_ticket():  
    student_data = None  
    if current_user.role not in ('admin', 'super_user', 'seller'):  
        flash('You do not have permission to access this page.')  
        return redirect(url_for('index'))  
    if request.method == 'POST':  
        ticket_id = request.form['ticket_id']  
        ticket = Ticket.query.filter_by(ticket_ID=ticket_id).first()  
        event_ID = ticket.event_ID  
        active_tickets_table = f"active_tickets_{event_ID}"  
        spent_tickets_table = f"spent_tickets_{event_ID}"  
        if ticket:  
            student_id = ticket.student_id  
            student_data = Students.query.filter_by(student_ID=student_id).first()  
              
            #Move tickets from active_tickets to spent_tickets  
            db.engine.execute(f"INSERT INTO {spent_tickets_table} SELECT * FROM {active_tickets_table} WHERE ticket_ID = '{ticket_id}'") 
            db.engine.execute(f"DELETE FROM {active_tickets_table} WHERE ticket_ID = '{ticket_id}'")  
            db.session.commit()    
              
            #Log the validation action  
            log = ActivityLog(user_id=current_user.id, action='validate', ticket_id=ticket.id)  
            db.session.add(log)  
            db.session.commit() 
            flash('Ticket successfully validated.')    
        else:  
            flash('Ticket not found. Please check the information and try again.')
            return render_template('validate_ticket.html', student_data=student_data)    

    return render_template('validate_ticket.html', student_data=student_data)

             
             
if __name__ == "__main__": 
    app.run(debug=True, host="0.0.0.0", port=5000)
    app.run(ssl_context="adhoc")
    initialize_directories()
    #Comment out after initial run.
    with app.app_context():
        db.create_all()
    
    migrate = Migrate(app, db)