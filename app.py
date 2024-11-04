from flask import Flask, flash, render_template, request, redirect, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Cambia esto por una clave secreta

# Configuración de la base de datos MySQL
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root',  # Cambia esto por tu contraseña
    'database': 'tuZapatos',
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

# Ruta para registrar usuarios
@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        is_admin = 1 if request.form.get('is_admin') else 0  # Si es admin, obtiene 1, si no, 0

        hashed_password = generate_password_hash(password)  # Usar el hash por defecto para la contraseña

        # Conexión a la base de datos y guardado del nuevo usuario
        connection = get_db_connection()
        cursor = connection.cursor()

        sql = "INSERT INTO users (userName, password, is_admin) VALUES (%s, %s, %s)"
        cursor.execute(sql, (username, hashed_password, is_admin))
        connection.commit()

        cursor.close()
        connection.close()

        return redirect('/login')  # Redirige a la página de login después del registro
    return render_template('registro.html')

# Ruta para el login de usuarios
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Aquí obtienes el cursor y la conexión a la base de datos
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)

        # Consulta para obtener el usuario
        cursor.execute("SELECT * FROM users WHERE userName = %s", (username,))
        user = cursor.fetchone()  # Obtén un solo usuario

        # Verifica si se encontró el usuario
        if user and check_password_hash(user['password'], password):  # Cambia user[1] por user['password']
            session['user_id'] = user['id']  # Cambia user[0] por user['id'] según la columna de ID
            session['username'] = user['username']  # Cambia user['userName'] por user['username']
            session['is_admin'] = user['is_admin']  # user['is_admin']

            if user['is_admin']:  # Si el usuario es admin
                return redirect('/dashboard')  # Redirige al dashboard para administración
            else:
                return redirect('/user-dashboard')  # Redirige al dashboard de usuario regular
        else:
            flash("Nombre de usuario o contraseña incorrectos", "danger")  # Maneja el error de inicio de sesión

        # Cierra el cursor y la conexión
        cursor.close()
        connection.close()

    return render_template('login.html')


# Ruta para el panel de administración
@app.route('/admin')
def admin():
    if not session.get('is_admin'):
        return "Acceso denegado. Solo administradores."
    return render_template('admin.html')

# Ruta para el dashboard de usuarios y para agregar productos
@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if not session.get('is_admin'):  # Solo permite el acceso a admin
        return redirect('/login')  # Redirige al login si no es admin
    
    if request.method == 'POST':
        # Obtener datos del formulario
        nombre = request.form['nombre']
        descripcion = request.form['descripcion']
        precio = request.form['precio']
        stock = request.form['stock']
        id_categoria = request.form['ID_Categoria']
        id_marca = request.form['id_marca']
        imagen = request.form['imagen']

        # Conectar a la base de datos y agregar el producto
        conn = get_db_connection()
        cursor = conn.cursor()

        # Consulta para insertar el nuevo producto
        query = '''
        INSERT INTO productos (Nombre, Descripcion, Precio, Stock, ID_Categoria, id_marca, Imagen)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        '''
        cursor.execute(query, (nombre, descripcion, precio, stock, id_categoria, id_marca, imagen))
        conn.commit()  # Guardar los cambios

        cursor.close()
        conn.close()

        return redirect(url_for('dashboard'))

    # Obtener los productos existentes para mostrarlos
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Obtener productos
    cursor.execute('SELECT * FROM productos')
    productos = cursor.fetchall()

    # Obtener categorías
    cursor.execute('SELECT * FROM categorias')
    categorias = cursor.fetchall()

    # Obtener marcas
    cursor.execute('SELECT * FROM marcas')
    marcas = cursor.fetchall()

    # Cerrar cursor y conexión
    cursor.close()
    conn.close()

    return render_template('dashboard.html', productos=productos, categorias=categorias, marcas=marcas)

# Rutas para productos por categoría (Hombre, Mujer, Niño, Niña)
@app.route('/productos/hombre')
def productos_hombre():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = "SELECT * FROM productos WHERE ID_Categoria = %s"
    cursor.execute(query, (1,))  # ID 1 es 'hombre'

    productos = cursor.fetchall()  # Lee todos los resultados aquí

    cursor.close()  # Luego puedes cerrar el cursor
    conn.close()  # Cerrar la conexión después de leer los resultados

    return render_template('hombre.html', productos=productos)

@app.route('/productos/mujer')
def productos_mujer():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = "SELECT * FROM productos WHERE ID_Categoria = %s"
    cursor.execute(query, (2,))  # ID 2 es 'mujer'

    productos = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('mujer.html', productos=productos)

@app.route('/productos/nino')
def productos_nino():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = "SELECT * FROM productos WHERE ID_Categoria = %s"
    cursor.execute(query, (3,))  # ID 3 es 'niño'

    productos = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('nino.html', productos=productos)

@app.route('/productos/nina')
def productos_nina():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = "SELECT * FROM productos WHERE ID_Categoria = %s"
    cursor.execute(query, (4,))  # ID 4 es 'niña'

    productos = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('niña.html', productos=productos)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
