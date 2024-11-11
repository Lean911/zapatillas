from flask import Flask, flash, render_template, request, redirect, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
import secrets

app = Flask(__name__)

# Asegúrate de que la secret_key esté definida antes de cualquier uso de la sesión
app.secret_key = secrets.token_hex(16)  # Genera una clave secreta única

# Configuración de la base de datos
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'tuZapatos',  
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

@app.route('/ver_carrito')
def ver_carrito():
    if 'user_id' not in session:  # Verifica si el usuario está logueado
        flash("Inicia sesión primero para ver tu carrito", 'error')
        return redirect(url_for('login'))  # Redirige al inicio de sesión si no está logueado
    
    # Lógica para mostrar el carrito
    if 'carrito' not in session or len(session['carrito']) == 0:
        flash("Tu carrito está vacío.", 'info')
        return redirect(url_for('index'))
    
    total = sum(item['precio'] * item['cantidad'] for item in session['carrito'])
    return render_template('carrito.html', carrito=session['carrito'], total=total)

# Registro de usuarios
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        is_admin = request.form.get('is_admin', 0)  # 0 para cliente común, 1 para admin

        try:
            conn = get_db_connection()
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

# Login de usuarios
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
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

# Dashboard de administración
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

# Buscar productos
@app.route('/buscar', methods=['GET'])
def buscar():
    # Obtener el término de búsqueda desde el formulario
    termino_busqueda = request.args.get('search', '')

    # Conectar a la base de datos
    conexion = get_db_connection()

    # Crear un cursor para ejecutar la consulta
    cursor = conexion.cursor()

    # Consulta SQL para buscar productos que coincidan con el término
    consulta = "SELECT * FROM productos WHERE nombre_producto LIKE %s"
    cursor.execute(consulta, (f"%{termino_busqueda}%",))

    # Obtener los resultados
    resultados = cursor.fetchall()

    # Cerrar la conexión
    cursor.close()
    conexion.close()

    # Renderizar el template con los resultados de búsqueda
    return render_template('resultados.html', resultados=resultados)

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

# Agregar producto a favoritos
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

# Eliminar producto del dashboard
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

# Ver favoritos
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

# Cerrar sesión
@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión exitosamente.')
    return redirect(url_for('login'))

# Página principal
@app.route('/')
def index():
    return render_template('index.html')

# Inicializar carrito
@app.before_request
def init_cart():
    if 'carrito' not in session:
        session['carrito'] = []

# Agregar al carrito
@app.route('/agregar_al_carrito/<int:producto_id>', methods=['POST'])
def agregar_al_carrito(producto_id):
    cantidad = int(request.form.get('cantidad', 1))

    if 'carrito' not in session:
        session['carrito'] = []

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM productos WHERE ID = %s", (producto_id,))
    producto = cursor.fetchone()
    cursor.close()
    conn.close()

    if producto:
        item = {
            'id': producto['ID'],
            'nombre': producto['Nombre'],
            'precio': producto['Precio'],
            'cantidad': cantidad
        }
        session['carrito'].append(item)
        flash(f"Producto {producto['Nombre']} agregado al carrito.")
    else:
        flash("Producto no encontrado.")

    return redirect(url_for('index'))

if __name__ == "__main__":
    app.run(debug=True)
