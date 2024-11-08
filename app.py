from flask import Flask, flash, render_template, request, redirect, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Configuración de la base de datos MySQL
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'tuZapatos',  # Asegúrate de usar tu nombre de base de datos
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

# Registro de usuarios
@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        is_admin = 1 if request.form.get('is_admin') else 0

        hashed_password = generate_password_hash(password)
        connection = get_db_connection()
        cursor = connection.cursor()
        sql = "INSERT INTO users (username, password, is_admin) VALUES (%s, %s, %s)"
        cursor.execute(sql, (username, hashed_password, is_admin))
        connection.commit()
        cursor.close()
        connection.close()
        return redirect('/login')
    return render_template('registro.html')

# Login de usuarios
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_admin'] = user['is_admin']
            return redirect('/dashboard') if user['is_admin'] else redirect('/dashboard')
        else:
            flash("Nombre de usuario o contraseña incorrectos", "danger")
        cursor.close()
        connection.close()
    return render_template('login.html')

# Panel de administración
@app.route('/admin')
def admin():
    if not session.get('is_admin'):
        return "Acceso denegado. Solo administradores."
    return render_template('admin.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if not session.get('is_admin'):
        return redirect('/login')
    
    if request.method == 'POST':
        # Obtener los datos del formulario
        nombre = request.form['nombre']
        descripcion = request.form['descripcion']
        precio = request.form['precio']
        stock = request.form['stock']
        # Comprobar si el producto es de temporada
        id_categoria = request.form['ID_Categoria'] if not request.form.get('esDeTemporada') else "5"  # 5 es la categoría de temporada
        id_marca = request.form['id_marca']
        imagen = request.form['imagen']
        es_de_temporada = request.form.get('esDeTemporada') == 'on'  # Verifica si el checkbox está marcado

        # Conectar a la base de datos
        conn = get_db_connection()
        cursor = conn.cursor()

        # SQL para insertar el producto
        query = '''
        INSERT INTO productos (Nombre, Descripcion, Precio, Stock, ID_Categoria, id_marca, Imagen, esDeTemporada)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        '''
        cursor.execute(query, (nombre, descripcion, precio, stock, id_categoria, id_marca, imagen, es_de_temporada))
        conn.commit()

        # Cerrar la conexión
        cursor.close()
        conn.close()

        return redirect(url_for('dashboard'))

    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    query = '''
    SELECT productos.*, categorias.Nombre AS Categoria
    FROM productos
    JOIN categorias ON productos.ID_Categoria = categorias.ID_Categoria
    '''
    cursor.execute(query)
    productos = cursor.fetchall()

    cursor.execute('SELECT * FROM categorias')
    categorias = cursor.fetchall()
    cursor.execute('SELECT * FROM marcas')
    marcas = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('dashboard.html', productos=productos, categorias=categorias, marcas=marcas)

# Productos por categoría
@app.route('/productos/<categoria>')
def productos_categoria(categoria):
    categorias_ids = {'Hombre': 1, 'Mujer': 2, 'Niño': 3, 'Niña': 4}
    if categoria not in categorias_ids:
        return "Categoría no encontrada."
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    query = "SELECT * FROM productos WHERE ID_Categoria = %s"
    cursor.execute(query, (categorias_ids[categoria],))
    productos = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template(f'{categoria}.html', productos=productos)

@app.route('/add_to_favorites/<int:producto_id>', methods=['POST'])
def add_to_favorites(producto_id):
    if 'user_id' not in session:
        flash("Por favor, inicia sesión para agregar a favoritos.", "warning")
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM favoritos WHERE user_id = %s AND producto_id = %s", (user_id, producto_id))
    favorito = cursor.fetchone()
    
    if not favorito:
        cursor.execute("INSERT INTO favoritos (user_id, producto_id) VALUES (%s, %s)", (user_id, producto_id))
        conn.commit()
        flash("Producto agregado a favoritos.", "success")
    else:
        flash("Este producto ya está en tus favoritos.", "info")
    
    cursor.close()
    conn.close()
    return redirect(url_for('productos_categoria', categoria='todos'))

@app.route('/eliminar_producto/<int:producto_id>', methods=['POST'])
def eliminar_producto(producto_id):
    if not session.get('is_admin'):
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM productos WHERE ID = %s', (producto_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Producto eliminado.", "success")
    return redirect(url_for('dashboard'))

@app.route('/favoritos')
def favoritos():
    if 'user_id' not in session:
        flash("Por favor, inicia sesión para ver tus favoritos.", "warning")
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    query = '''
    SELECT productos.* 
    FROM productos
    JOIN favoritos ON productos.ID = favoritos.producto_id
    WHERE favoritos.user_id = %s
    '''
    cursor.execute(query, (user_id,))
    favoritos = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template('favoritos.html', favoritos=favoritos)

# Inicializar el carrito
@app.before_request
def init_cart():
    if 'carrito' not in session:
        session['carrito'] = []

from flask import session

# Función para agregar al carrito
@app.route('/agregar_al_carrito/<int:producto_id>', methods=['POST'])
def agregar_al_carrito(producto_id):
    # Obtener la cantidad deseada del formulario o definir una cantidad por defecto
    cantidad = int(request.form.get('cantidad', 1))

    # Si no hay un carrito en la sesión, inicializarlo como una lista vacía
    if 'carrito' not in session:
        session['carrito'] = []

    # Conectar a la base de datos para obtener el producto y sus detalles
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM productos WHERE ID_Producto = %s", (producto_id,))
    producto = cursor.fetchone()
    cursor.close()
    conn.close()

    # Agregar el producto con sus detalles y cantidad al carrito
    if producto:
        item = {
            'id': producto['ID_Producto'],
            'nombre': producto['Nombre'],
            'descripcion': producto['Descripcion'],
            'precio': producto['Precio'],
            'cantidad': cantidad
        }
        session['carrito'].append(item)
        session.modified = True  # Asegura que los cambios en la sesión se guarden

    return redirect(url_for('ver_carrito'))

@app.route('/ver_carrito')
def ver_carrito():
    # Verificar el contenido del carrito
    print("Contenido del carrito:", session.get('carrito'))
    carrito = session.get('carrito', [])
    return render_template('carrito.html', carrito=carrito)

@app.route('/')
def index():
    # Crear una conexión a la base de datos
    connection = mysql.connector.connect(
        host='localhost',
        user='root',
        password='',
        database='tuZapatos'
    )
    cursor = connection.cursor()
    
    # Consulta para obtener productos de temporada
    cursor.execute("SELECT * FROM productos WHERE esDeTemporada = 1")
    temporada_productos = cursor.fetchall()
    
    # Imprimir los productos de temporada para depuración
    print(temporada_productos)  # Esto imprimirá la lista de productos
    
    connection.close()
    
    # Pasar los productos al template
    return render_template('index.html', temporada_productos=temporada_productos)

@app.route('/productos/hombre')
def productos_hombre():
    connection = mysql.connect()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM productos WHERE categoria = 'Hombre'")  # Ajusta la consulta según tu esquema
    productos_hombre = cursor.fetchall()
    connection.close()
    return render_template('hombre.html', productos=productos_hombre)




@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))
if __name__ == '__main__':
    app.run(debug=True)
