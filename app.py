from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import mysql.connector
from mysql.connector import IntegrityError
from datetime import date

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Connect to MySQL database
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='saanushobha@123',
            database='library_db',
            port=3307
        )
        return conn
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")
        return None

# Create necessary tables
def init_db():
    conn = get_db_connection()
    if conn is None:
        print("Failed to connect to database during initialization")
        return
        
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            password VARCHAR(100) NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS books (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            author VARCHAR(255),
            year INT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS borrow (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_name VARCHAR(100),
            book_title VARCHAR(255),
            borrow_date DATE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS returns (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_name VARCHAR(100),
            book_title VARCHAR(255),
            return_date DATE
        )
    ''')
    conn.commit()
    conn.close()
    print("Database initialized successfully")

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        if conn is None:
            flash('Database connection error')
            return redirect(url_for('login'))
            
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users WHERE username = %s AND password = %s', (username, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['username'] = username
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        if conn is None:
            flash('Database connection error')
            return redirect(url_for('signup'))
            
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO users (username, password) VALUES (%s, %s)', (username, password))
            conn.commit()
            flash('Signup successful. Please login.')
            return redirect(url_for('login'))
        except IntegrityError:
            flash('Username already exists')
            return redirect(url_for('signup'))
        finally:
            conn.close()

    return render_template('signup.html')

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', username=session['username'])

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('You have been logged out.')
    return redirect(url_for('home'))

@app.route('/gallery')
def gallery():
    return render_template('gallery.html')

@app.route('/add_view_books', methods=['GET', 'POST'])
def add_view_books():
    conn = get_db_connection()
    if conn is None:
        flash('Database connection error')
        return redirect(url_for('dashboard'))
        
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        title = request.form['title']
        author = request.form['author']
        year = request.form['year']
        
        try:
            cursor.execute("INSERT INTO books (title, author, year) VALUES (%s, %s, %s)", 
                          (title, author, year))
            conn.commit()
            flash('Book added successfully!')
        except Exception as e:
            conn.rollback()
            flash(f'Error adding book: {str(e)}')
            print(f"Database error: {str(e)}")

    try:
        cursor.execute("SELECT * FROM books")
        books = cursor.fetchall()
    except Exception as e:
        books = []
        flash(f'Error retrieving books: {str(e)}')
        print(f"Database error: {str(e)}")
    
    conn.close()
    return render_template('add_view_books.html', books=books)

@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('q', '')
    conn = get_db_connection()
    if conn is None:
        flash('Database connection error')
        return redirect(url_for('dashboard'))
        
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM books WHERE title LIKE %s OR author LIKE %s", 
                  (f'%{query}%', f'%{query}%'))
    books = cursor.fetchall()
    conn.close()
    return render_template('search_results.html', books=books, query=query)

@app.route('/delete_book/<int:book_id>', methods=['POST'])
def delete_book(book_id):
    conn = get_db_connection()
    if conn is None:
        flash('Database connection error')
        return redirect(url_for('add_view_books'))

    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM books WHERE id = %s", (book_id,))
        conn.commit()
        flash('Book deleted successfully!')
    except Exception as e:
        conn.rollback()
        flash(f'Error deleting book: {str(e)}')
    finally:
        conn.close()

    return redirect(url_for('add_view_books'))


@app.route('/borrow_return', methods=['GET', 'POST'])
def borrow_return():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        action = request.form.get('action')
        user = request.form['user']
        book = request.form['book']
        date_value = request.form.get('date') or date.today().isoformat()

        conn = get_db_connection()
        if conn is None:
            flash('Database connection error')
            return redirect(url_for('borrow_return'))
            
        cursor = conn.cursor()
        try:
            if action == 'borrow':
                # Check if the book is already borrowed by someone else
                cursor.execute('''
                    SELECT * FROM borrow WHERE book_title = %s AND 
                    NOT EXISTS (SELECT * FROM returns WHERE returns.book_title = borrow.book_title AND returns.user_name = borrow.user_name)
                ''', (book,))
                if cursor.fetchone():
                    flash('This book is already borrowed by someone else!')
                else:
                    cursor.execute('INSERT INTO borrow (user_name, book_title, borrow_date) VALUES (%s, %s, %s)', 
                                 (user, book, date_value))
                    flash('Book borrowed successfully!')
            elif action == 'return':
                # Check if the user actually borrowed this book
                cursor.execute('''
                    SELECT * FROM borrow WHERE user_name = %s AND book_title = %s AND
                    NOT EXISTS (SELECT * FROM returns WHERE returns.book_title = borrow.book_title AND returns.user_name = borrow.user_name)
                ''', (user, book))
                if cursor.fetchone():
                    cursor.execute('INSERT INTO returns (user_name, book_title, return_date) VALUES (%s, %s, %s)', 
                                 (user, book, date_value))
                    flash('Book returned successfully!')
                else:
                    flash('You cannot return a book you have not borrowed!')
            conn.commit()
        except Exception as e:
            conn.rollback()
            flash(f'Error: {str(e)}')
        finally:
            conn.close()
        
        return redirect(url_for('borrow_return'))

    # Get data for the template
    conn = get_db_connection()
    today = date.today().isoformat()
    
    books = []
    borrowed_books = []
    borrow_history = []
    return_history = []
    
    if conn:
        cursor = conn.cursor(dictionary=True)
        
        # Get all books
        cursor.execute("SELECT title FROM books")
        books = [book['title'] for book in cursor.fetchall()]
        
        # Get books borrowed by the current user that haven't been returned
        cursor.execute('''
            SELECT book_title FROM borrow 
            WHERE user_name = %s AND 
            NOT EXISTS (
                SELECT * FROM returns 
                WHERE returns.book_title = borrow.book_title 
                AND returns.user_name = borrow.user_name
            )
        ''', (session['username'],))
        borrowed_books = [book['book_title'] for book in cursor.fetchall()]
        
        # Get borrow history for the current user
        cursor.execute('''
            SELECT b.book_title, b.borrow_date, 
                CASE WHEN r.return_date IS NOT NULL THEN 1 ELSE 0 END as returned
            FROM borrow b
            LEFT JOIN returns r ON b.book_title = r.book_title AND b.user_name = r.user_name
            WHERE b.user_name = %s
            ORDER BY b.borrow_date DESC
        ''', (session['username'],))
        borrow_history = cursor.fetchall()
        
        # Get return history for the current user
        cursor.execute('''
            SELECT book_title, return_date
            FROM returns
            WHERE user_name = %s
            ORDER BY return_date DESC
        ''', (session['username'],))
        return_history = cursor.fetchall()
        
        conn.close()

    return render_template(
        'borrow_return.html', 
        books=books,
        borrowed_books=borrowed_books,
        borrow_history=borrow_history,
        return_history=return_history,
        username=session['username'],
        today=today
    )

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)