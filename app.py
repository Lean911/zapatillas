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
    categorias_ids = {'Hombre': 1, 'Mujer': 2, 'Nino': 3, 'Niña': 4}
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


@app.route('/agregar_al_carrito/<int:producto_id>', methods=['POST'])
def agregar_al_carrito(producto_id):
    
    cantidad = int(request.form.get('cantidad', 1))

    
    if 'carrito' not in session:
        session['carrito'] = []

    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM productos WHERE ID_Producto = %s", (producto_id,))
    producto = cursor.fetchone()
    cursor.close()
    conn.close()

    
    if producto:
        item = {
            'id': producto['ID_Producto'],
            'nombre': producto['Nombre'],
            'descripcion': producto['Descripcion'],
            'precio': producto['Precio'],
            'cantidad': cantidad
        }
        session['carrito'].append(item)
        session.modified = True  

    return redirect(url_for('ver_carrito'))

@app.route('/ver_carrito')
def ver_carrito():
    
    print("Contenido del carrito:", session.get('carrito'))
    carrito = session.get('carrito', [])
    return render_template('carrito.html', carrito=carrito)

@app.route('/')
def index():
    
    connection = mysql.connector.connect(
        host='localhost',
        user='root',
        password='',
        database='tuzapatos'
    )
    cursor = connection.cursor()
    
    
    cursor.execute("SELECT * FROM productos WHERE esDeTemporada = 1")
    productos = cursor.fetchall()  
    
    
    temporada_productos = []
    for producto in productos:
        producto_dict = {
            'ID_Producto': producto[0],  
            'Nombre': producto[1],
            'Precio': producto[2],
            'Descripcion': producto[3],
            'Imagen': producto[7], 
        }
        temporada_productos.append(producto_dict)
    print(temporada_productos)  

    connection.close()
    return render_template('index.html', temporada_productos=temporada_productos)


@app.route('/hombre')
def categoria_hombre():
    # Crear una conexión a la base de datos
    connection = mysql.connector.connect(
        host='localhost',
        user='root',
        password='',
        database='tuzapatos'
    )
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM productos WHERE categoria = 'Hombre' AND esDeTemporada = 0")
    productos_hombre = cursor.fetchall()  
   
    productos_hombre_dict = []
    for producto in productos_hombre:
        producto_dict = {
            'ID_Producto': producto[0],
            'Nombre': producto[1],
            'Precio': producto[2],
            'Descripcion': producto[3],
            'Imagen': producto[4],
            'Temporada': producto[5],  
            'Categoria': producto[6],  
        }
        productos_hombre_dict.append(producto_dict)

    
    connection.close()

    # Pasar los productos al template
    return render_template('categoria_hombre.html', productos=productos_hombre_dict)

@app.route('/nino')
def categoria_nino():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM productos WHERE ID_Categoria = 3 AND esDeTemporada = 0")
    productos_nino = cursor.fetchall()
    
    # Debug: Imprimir productos para ver si están siendo seleccionados correctamente
    print("Productos Niño:", productos_nino)
    
    cursor.close()
    connection.close()
    
    return render_template('nino.html', productos=productos_nino)

@app.route('/nina')
def categoria_nina():
    # Conectar a la base de datos
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    # Ejecutar la consulta para obtener productos de la categoría "Niña"
    cursor.execute("SELECT * FROM productos WHERE ID_Categoria = 4 AND esDeTemporada = 0")  # ID_Categoria 4 representa "Niña"
    productos_nina = cursor.fetchall()
    
    # Depuración: imprimir los productos de la categoría "Niña"
    print("Productos Niña:", productos_nina)
    
    # Cerrar la conexión
    cursor.close()
    connection.close()
    
    # Renderizar el template de la categoría "Niña" con los productos
    return render_template('nina.html', productos=productos_nina)




@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))
if __name__ == '__main__':
    app.run(debug=True)
