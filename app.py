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

#MAIL SETTINGS

app.config['MAIL_SERVER'] = 'smtp.example.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your_email@example.com'
app.config['MAIL_PASSWORD'] = 'your_email_password'
mail = Mail(app)

#DATABASE SETTINGS

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://username:password@localhost/rht_tms'
app.config['SECRET_KEY'] = '11235813213455Ba!!!'

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

#BASE

app = Flask(__name__)

#@app.route('/')
#def index():
#        return render_template('base.html')

#    if __name__ == '__main__':
#            app.run(debug=True)


@app.route('/')
@login_required
def index():
    if current_user.role in ('admin', 'super_user'):
        return redirect(url_for('admin_main'))
    elif current_user.role == 'seller':
        return redirect(url_for('seller_main'))

    return redirect(url_for('login'))

#USER MODELS

class User(UserMixin, db.Model):
        id = db.Column(db.Integer, primary_key=True)
        username = db.Column(db.String(255), unique=True, nullable=False)
        email = db.Column(db.String(255), unique=True, nullable=False)                      
        password = db.Column(db.String(255), nullable=False)
        role = db.Column(db.String(255), nullable=False)

#LOGIN FUNCTION

@app.route('/login', methods=['GET', 'POST'])
def login():
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            user = User.query.filter_by(username=username).first()

        if user and user.password == password:
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials.')
            
    return render_template('login.html')

#CREATE USER

@app.route('/create_user', methods=['GET', 'POST'])
@login_required
def create_user():
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.')
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        new_user = User(username=username, email=email, password=password, role=role)
        db.session.add(new_user)
        db.session.commit()
        flash('User successfully created.')
        return redirect(url_for('index'))
    return render_template('create_user.html')

#EVENT CREATION

@app.route('/create_event', methods=['GET', 'POST'])
@login_required
def create_event():
    if current_user.role not in ('admin', 'super_user'):
        flash('You do not have permission to access this page.')
        return redirect(url_for('index')
    if request.method == 'POST':
        event_name = request.form['event_name']
        event_date = request.form['event_date']
        event_date_obj = datetime.strptime(event_date, '%Y-%m-%d')
        unique_hash = hashlib.sha1(f"{event_name}{event_date}".encode('utf-8')).hexdigest()[:10]
        new_event = Event(event_ID=unique_hash, event_name=event_name, event_date=event_date_obj)
        db.session.add(new_event)
        db.session.commit()
        flash('Event successfully created.') 
    return render_template('create_event.html')

#SEARCH EVEN

@app.route('/search_events', methods=['GET', 'POST'])
@login_required
def search_events():
    events = Event.query.all()
    filtered_events = events

    if request.method == 'POST':
        search_term = request.form['search_term']
        event_date = request.form['event_date']
        filtered_events = [event for event in events if (search_term.lower() in event.event_name.lower()) and (event_date == '' or event.event_date == datetime.strptime(event_date, '%Y-%m-%d'))]
        
    return render_template('search_events.html', events=filtered_events)
             
#GENERATE TICKET ID

@app.route('/generate_tickets', methods=['GET', 'POST'])
@login_required
def generate_tickets():
    if current_user.role not in ('admin', 'super_user'):
        flash('You do not have permission to access this page.')
        return redirect(url_for('index'))

    events = Event.query.all()

    if request.method == 'POST':
        event_id = request.form['event_id']
        num_tickets = int(request.form['num_tickets'])
        event = Event.query.filter_by(event_ID=event_id).first()
        ticket_ids = []

    for _ in range(num_tickets):
        ticket_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        ticket = Ticket(ticket_ID=ticket_id, event_id=event.id)
        db.session.add(ticket)
        db.session.commit()
        
        # Generate barcode
        ean = barcode.get('ean13', ticket_id, writer=ImageWriter())
        filename = f"barcodes/{ticket_id}.png"
        ean.save(filename)

        ticket_ids.append(ticket_id)

    # Export ticket IDs to Excel
    wb = Workbook()
    ws = wb.active
    ws.title = f"Tickets for {event.event_name}"
    ws.append(['Ticket ID'])

    for ticket_id in ticket_ids:
        ws.append([ticket_id])

    wb.save(f"exports/tickets_{event.event_name}.xlsx")

    flash(f"{num_tickets} ticket IDs successfully generated for {event.event_name}.")
    return send_file(f"exports/tickets_{event.event_name}.xlsx", as_attachment=True)

return render_template('generate_tickets.html', events=events)

#ACTIVATE TICKET

@app.route('/activate_ticket', methods=['GET', 'POST'])
@login_required
def activate_ticket():
    if current_user.role not in ('admin', 'super_user', 'seller'):
        flash('You do not have permission to access this page.')
        return redirect(url_for('index'))
   
   students = Student.query.all()
   
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
        event = Event.query.get(ticket.event_id)
        msg = Message('Ticket Activation Confirmation',
                sender='your_email@example.com',
                recipients=[student.student_EMAIL])
        msg.body = f"Dear {student.student_NAME} {student.student_SNAME},Your ticket for {event.event_name} on {event.event_date.strftime('%Y-%m-%d')} has been successfully activated. Please keep this email for your records.Best regards, The Radio HighTECH Student Association"
        mail.send(msg)
    else:
        flash('Ticket or student not found. Please check the information and try again.')
        return render_template('activate_ticket.html')

return render_template('activate_ticket.html', students=students)

#REFUND TICKETS

@app.route('/refund_ticket', methods=['GET', 'POST'])
@login_required
def refund_ticket():
    if current_user.role not in ('admin', 'super_user', 'seller'):
        flash('You do not have permission to access this page.')
        return redirect(url_for('index'))

    if request.method == 'POST':
        ticket_id = request.form['ticket_id']
        ticket = Ticket.query.filter_by(ticket_ID=ticket_id).first()
        event_id = ticket.event_id
        active_tickets_table = f"active_tickets_{event_id}"
        refund_tickets_table = f"refund_tickets_{event_id}"

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
        event_id = event.event_ID
        active_tickets_table = f"active_tickets_{event_id}"
        refund_tickets_table = f"refund_tickets_{event_id}"
        spent_tickets_table = f"spent_tickets_{event_id}"

        # Calculate KPIs for the event
        active_tickets_count = db.engine.execute(text(f"SELECT COUNT(*) FROM {active_tickets_table}")).scalar()
        refund_tickets_count = db.engine.execute(text(f"SELECT COUNT(*) FROM {refund_tickets_table}")).scalar()
        spent_tickets_count = db.engine.execute(text(f"SELECT COUNT(*) FROM {spent_tickets_table}")).scalar()

        event_analytics.append({
            'event_name': event.event_name,
            'event_date': event.event_date,
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
        event_id = ticket.event_id
        active_tickets_table = f"active_tickets_{event_id}"
        spent_tickets_table = f"spent_tickets_{event_id}"
        
        if ticket:
            student_id = ticket.student_id
            student_data = Student.query.filter_by(student_ID=student_id).first()

            # Move ticket from active_tickets to spent_tickets
            db.engine.execute(f"INSERT INTO {spent_tickets_table} SELECT * FROM {active_tickets_table} WHERE ticket_ID = '{ticket_id}'")
            db.engine.execute(f"DELETE FROM {active_tickets_table} WHERE ticket_ID = '{ticket_id}'")
            db.session.commit()

            # Log the validation action
            log = ActivityLog(user_id=current_user.id, action='validate', ticket_id=ticket.id)
            db.session.add(log)
            db.session.commit()
            
            flash('Ticket successfully validated.')

        else:
            flash('Ticket not found. Please check the information and try again.')

    return render_template('validate_ticket.html', student_data=student_data)

#
