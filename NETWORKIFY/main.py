from flask import Flask, jsonify, render_template, request
from werkzeug.security import generate_password_hash, check_password_hash
from Models.models import Users

app = Flask(__name__, template_folder='templates', static_folder= 'static')
app.config()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login_page():
    return render_template('login.html')

app.route('/register')
def register():
    return render_template('register.html')

app.route('/login', methods = ['POST'])
def login():
    data = request.get_json()
    if not data.get('username') or data.get('password'):
        return jsonify({
            'success': False,
            'message': 'No login credentials Provided'
        }), 400
    username = data['username']
    password = data['password']
    users = Users.query.filter_by(username = username).first()
    if not users:
        return jsonify({
            'success': False,
            'message': 'Wrong username or user does not exist'
        }), 404
    if not check_password_hash(users.password, password):
        return jsonify({
            'success': False,
            'message': 'Incorrect password'
        }), 401
    
app.route('/register', methods = ['POST'])
def register():
    data = request.get_json()