from flask import Flask, flash, render_template, request, redirect, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
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
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        is_admin = request.form.get('is_admin', 0)  # 0 para cliente común, 1 para admin

        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username, password, is_admin) VALUES (%s, %s, %s)",
                           (username, password, is_admin))
            conn.commit()  # Guardar cambios en la base de datos
            cursor.close()
            conn.close()

            flash('Registro exitoso. Ahora puedes iniciar sesión.')
            return redirect(url_for('login'))
        except mysql.connector.Error as err:
            print(f"Error al insertar en la base de datos: {err}")
            flash('Error al registrar el usuario. Intenta nuevamente.')
            return redirect(url_for('register'))
    
    return render_template('registro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['is_admin'] = user['is_admin']
            session['username'] = user['username']
            flash('Has iniciado sesión exitosamente.')
            return redirect(url_for('index'))
        else:
            flash('Usuario o contraseña incorrecta.')
            return redirect(url_for('login'))
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
        id_categoria = request.form['ID_Categoria'] if not request.form.get('esDeTemporada') else "5"
        id_marca = request.form['id_marca']
        imagen = request.form['imagen']
        es_de_temporada = request.form.get('esDeTemporada') == 'on'
        talle = request.form['talle']
        
        conn = get_db_connection()
        cursor = conn.cursor()

        query_producto = '''
        INSERT INTO productos (Nombre, Descripcion, Precio, Stock, ID_Categoria, id_marca, Imagen, esDeTemporada)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        '''
        cursor.execute(query_producto, (nombre, descripcion, precio, stock, id_categoria, id_marca, imagen, es_de_temporada))
        conn.commit()

        id_producto = cursor.lastrowid

        query_talle = '''
        INSERT INTO talles (ID_Producto, Talle) VALUES (%s, %s)
        '''
        cursor.execute(query_talle, (id_producto, talle))
        conn.commit()

        cursor.close()
        conn.close()

        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    query_productos = '''
    SELECT productos.*, categorias.Nombre AS Categoria
    FROM productos
    JOIN categorias ON productos.ID_Categoria = categorias.ID_Categoria
    '''
    cursor.execute(query_productos)
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
    return redirect(url_for('productos_categoria', categoria='Hombre'))

@app.route('/eliminar_producto_dashboard/<int:producto_id>', methods=['POST'])
def eliminar_producto_from_dashboard(producto_id):
    if not session.get('is_admin'):
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM talles WHERE ID_Producto = %s", (producto_id,))
    conn.commit()
    cursor.execute("DELETE FROM productos WHERE ID_Producto = %s", (producto_id,))
    conn.commit()

    cursor.close()
    conn.close()
    flash("Producto eliminado correctamente")
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

@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión exitosamente.')
    return redirect(url_for('login'))

@app.route('/')
def index():
    return render_template('index.html')

@app.before_request
def init_cart():
    if 'carrito' not in session:
        session['carrito'] = []

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

@app.route('/carrito')
def ver_carrito():
    carrito = [
        {'nombre': 'Producto 1', 'descripcion': 'Descripción 1', 'precio': 19.99, 'cantidad': 2},
        {'nombre': 'Producto 2', 'descripcion': 'Descripción 2', 'precio': 29.99, 'cantidad': 1}
    ]
    
    # Calcular el total
    total = sum(float(item['precio']) * int(item['cantidad']) for item in carrito)
    
    # Renderizar el template 'carrito.html'
    return render_template('carrito.html', carrito=carrito, total=total)


@app.route('/eliminar_del_carrito/<int:producto_id>', methods=['POST'])
def eliminar_del_carrito(producto_id):
    carrito = session.get('carrito', [])
    session['carrito'] = [item for item in carrito if item['id'] != producto_id]
    return redirect(url_for('ver_carrito'))


if __name__ == '__main__':
    app.run(debug=True)
