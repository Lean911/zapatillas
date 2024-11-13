from flask import Flask, flash, jsonify, render_template, request, redirect, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
import secrets
import config
from mercadopago.config import RequestOptions


# SDK de Mercado Pago
import mercadopago
# Agrega credenciales



app = Flask(__name__)
app.config.from_object(config)
sdk = mercadopago.SDK(app.config['MERCADO_PAGO_ACCESS_TOKEN'])

# Crea un ítem en la preferencia
preference_data = {
    "items": [
        {
            "title": "Nike",
            "quantity": 1,
            "unit_price": 1.0,
            "currency_id": "ARS"
        }
    ]
}

preference_response = sdk.preference().create(preference_data)
preference = preference_response["response"]


# Asegúrate de que la secret_key esté definida antes de cualquier uso de la sesión
app.secret_key = secrets.token_hex(16)  # Genera una clave secreta única

# Configura las opciones de la solicitud
request_options = RequestOptions(access_token='MERCADO_PAGO_ACCESS_TOKEN')

@app.route('/pagar', methods=['POST'])
def pagar():
    if 'carrito' not in session or len(session['carrito']) == 0:
        flash("El carrito está vacío.", "error")
        return redirect(url_for('ver_carrito'))

    carrito = session['carrito']
    total = sum(float(item['precio']) * int(item['cantidad']) for item in carrito)

    metodo_pago = request.form.get('pago')
    if metodo_pago is None:
        flash("Por favor, selecciona un método de pago.", "error")
        return redirect(url_for('ver_carrito'))

    if metodo_pago == 'mercado_pago':
        preference_data = {
            "items": [
                {
                    "title": item['nombre'],
                    "quantity": int(item['cantidad']),
                    "unit_price": float(item['precio']),
                    "currency_id": "ARS"
                } for item in carrito
            ],
            "back_urls": {
                "success": url_for('pago_exitoso', _external=True),
                "failure": url_for('pago_fallido', _external=True),
                "pending": url_for('pago_pendiente', _external=True)
            },
            "auto_return": "approved"
        }
        try:
            preference_response = sdk.preference().create(preference_data)
            print("Respuesta completa de Mercado Pago:", preference_response)  # Log completo
            if preference_response["status"] == 201:
                init_point = preference_response["response"].get("init_point")
                if init_point:
                    return redirect(init_point)
                else:
                    flash("Error al generar el enlace de pago.", "error")
            else:
                print(f"Error en la respuesta de Mercado Pago: {preference_response}")
                flash("Error al crear la preferencia de pago.", "error")
        except Exception as e:
            print(f"Error al procesar el pago: {e}")
            flash(f"Ocurrió un error al procesar el pago: {e}", "error")
            
        
        return redirect(url_for('ver_carrito'))

    flash("Método de pago no válido.", "error")
    return redirect(url_for('checkout'))


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

    # Verifica si el carrito está vacío
    if 'carrito' not in session or len(session['carrito']) == 0:
        flash("Tu carrito está vacío.", 'info')
        return redirect(url_for('index'))

    # Define carrito desde la sesión y calcula el total
    carrito = session['carrito']
    total = sum(float(item['precio']) * int(item['cantidad']) for item in carrito)

    return render_template('carrito.html', carrito=carrito, total=total)



@app.route('/checkout', methods=['[GET]','POST'])
def checkout():
    carrito = session.get('carrito', [])
    if not carrito:
        return redirect(url_for('index'))

    preference_data = {
        "item": []
    }

    # Conexión a la base de datos para obtener los detalles de los productos
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    for product in carrito:
        product_id = product.get('id')

        try:
            product_id = int(product_id)  # Asegurarse de que sea un número entero
        except ValueError:
            print(f"Error: product_id no es un número válido: {product_id}")
            continue

        cursor.execute("SELECT nombre, precio FROM productos WHERE ID_Producto = %s", (product_id,))
        product_data = cursor.fetchone()

        if product_data:
            item = {
                "title": product_data['nombre'],
                "quantity": 1,
                "unit_price": float(product_data['precio'])
            }
            preference_data["item"].append(item)

    cursor.close()
    connection.close()

    # Crea la preferencia de pago con las opciones de solicitud
    preference_response = sdk.preference().create(preference_data)

    if preference_response['status'] == 200:
        preference = preference_response["response"]
        link_pago = preference["init_point"]
        return redirect(link_pago)
    else:
        return "Error al crear la preferencia de pago", 500
    


@app.route('/eliminar_producto/<int:producto_id>', methods=['POST'])
def eliminar_producto_dashboard(producto_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM productos WHERE ID_Producto = %s", (producto_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Producto eliminado exitosamente.')
    return redirect(url_for('dashboard'))

@app.route('/success')
def success():
    return render_template('success.html')

@app.route('/failure')
def failure():
    return render_template('failure.html')

@app.route('/pending')
def pending():
    return render_template('pending.html')

def procesar_pago(publicacion):
    """
    Procesa el pago con Mercado Pago para una publicación dada.
    :param publicacion: Diccionario u objeto que contiene información del producto.
                        Debe incluir 'nombre', 'id', y 'valor'.
    """
    # Inicializar el SDK de Mercado Pago con tu token de acceso
    sdk = mercadopago.SDK("MERCADO_PAGO_ACCESS_TOKEN")

    # Crear los datos de la preferencia
    preference_data = {
        "items": [
            {
                "title": publicacion['nombre'],  # Asegúrate de que este atributo existe
                "quantity": 1,  # Cantidad fija en este ejemplo
                "currency_id": "ARS",  # Moneda en pesos argentinos
                "unit_price": float(publicacion['valor'])  # Precio del producto
            }
        ],
        "back_urls": {
            "success": f"http://127.0.0.1:5000/pago_exitoso/{publicacion['id']}",
            "failure": "http://127.0.0.1:5000/pago_fallido/",
            "pending": "http://127.0.0.1:5000/pago_pendiente/"
        },
        "auto_return": "approved",  # Auto-retorno cuando el pago es aprobado
    }

    try:
        # Crear la preferencia en Mercado Pago
        preference_response = sdk.preference().create(preference_data)
        preference = preference_response["response"]

        # Redirigir al usuario al init_point para completar el pago
        return redirect(preference["init_point"])
    except Exception as e:
        # Manejar errores y devolver una respuesta JSON con el mensaje de error
        print(f"Error al crear la preferencia de pago: {str(e)}")
        return jsonify({'error': 'No se pudo crear la preferencia de pago.'}), 500

@app.route('/pago_exitoso')
def pago_exitoso():
    # Aquí puedes procesar lo que sucede después de un pago exitoso (actualizar el estado del pedido, etc.)
    return render_template('pago_exitoso.html')

@app.route('/pago_fallido')
def pago_fallido():
    # Aquí puedes manejar el caso de pago fallido
    return render_template('pago_fallido.html')

@app.route('/pago_pendiente')
def pago_pendiente():
    # Aquí puedes manejar el caso de pago pendiente
    return render_template('pago_pendiente.html')






# Registro de usuarios
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        is_admin = request.form.get('is_admin', 0)

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username, password, is_admin) VALUES (%s, %s, %s)",
                           (username, password, is_admin))
            conn.commit()
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
    termino_busqueda = request.args.get('search', '')
    conexion = get_db_connection()
    cursor = conexion.cursor()
    consulta = "SELECT * FROM productos WHERE nombre_producto LIKE %s"
    cursor.execute(consulta, (f"%{termino_busqueda}%",))
    resultados = cursor.fetchall()
    cursor.close()
    conexion.close()
    return render_template('resultados.html', resultados=resultados)

# Productos por categoría
@app.route('/productos/<categoria>')
def productos_categoria(categoria):
    categorias_ids = {'hombre': 1, 'mujer': 2, 'niño': 3, 'niña': 4}
    id_categoria = categorias_ids.get(categoria.lower())
    
    if id_categoria:
        conexion = get_db_connection()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("SELECT * FROM productos WHERE ID_Categoria = %s", (id_categoria,))
        productos = cursor.fetchall()
        cursor.close()
        conexion.close()
        return render_template(f'{categoria}.html', productos=productos)
    else:
        return "Categoría no encontrada", 404

# Página principal
@app.route('/')
def index():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM productos WHERE esDeTemporada = 1")
    productos_temporada = cursor.fetchall()

    cursor.execute("SELECT * FROM productos WHERE esDeTemporada = 0")
    productos_otros = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('index.html', productos_temporada=productos_temporada, productos_otros=productos_otros)

# Ruta para agregar productos al carrito
# Ruta para agregar productos al carrito
@app.route('/agregar_al_carrito/<int:id>', methods=['POST'])
def agregar_al_carrito(id):
    # Conexión a la base de datos
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM productos WHERE ID_Producto = %s", (id,))
    producto = cursor.fetchone()
    cursor.close()
    conn.close()

    if not producto:
        return "Producto no encontrado", 404

    cantidad = int(request.form.get('cantidad', 1))
    
    # Asegurar que el carrito en la sesión esté inicializado
    if 'carrito' not in session:
        session['carrito'] = []

    # Crear el item con todos los detalles necesarios
    item = {
        'id': producto['ID_Producto'],
        'nombre': producto['Nombre'],
        'descripcion': producto['Descripcion'],
        'precio': producto['Precio'],
        'cantidad': cantidad
    }

    # Si quieres añadir "modelo" (por ejemplo si tienes un campo para ello en tu DB), asegúrate de agregarlo aquí
    item['modelo'] = producto.get('Modelo', 'Desconocido')  # Si no tienes 'Modelo', puedes asignar 'Desconocido' como valor predeterminado

    # Verificar si el producto ya está en el carrito
    for prod in session['carrito']:
        if prod['id'] == producto['ID_Producto']:
            prod['cantidad'] += cantidad  # Incrementar la cantidad si el producto ya está en el carrito
            break
    else:
        # Si no está en el carrito, añadir el nuevo producto
        session['carrito'].append(item)

    session.modified = True  # Indicar que la sesión se ha modificado
    return redirect(url_for('ver_carrito'))

# Logout
@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión correctamente.')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
