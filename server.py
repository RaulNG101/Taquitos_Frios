from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from werkzeug.utils import secure_filename
import os
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_aqui'  # Cambia esto por una clave segura en producción

# Configuración
DATABASE = 'database.db'
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Función para conectar a la base de datos
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# Inicializar DB
def init_db():
    with app.app_context():
        db = get_db()
        db.execute('''
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            descripcion TEXT,
            precio REAL NOT NULL,
            imagen TEXT,
            categoria TEXT NOT NULL,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        db.execute('''
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id INTEGER,
            cantidad INTEGER DEFAULT 1,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (producto_id) REFERENCES productos (id)
        )''')
        db.commit()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# =============================================
# RUTAS PRINCIPALES DEL POS
# =============================================

@app.route('/')
def index():
    db = get_db()
    categorias = db.execute('SELECT DISTINCT categoria FROM productos').fetchall()
    pedido_count = db.execute('SELECT SUM(cantidad) as count FROM pedidos').fetchone()['count'] or 0
    return render_template('index.html', 
                         categorias=[c['categoria'] for c in categorias],
                         pedido_count=pedido_count)

@app.route('/categoria/<categoria>')
def elementos(categoria):
    db = get_db()
    productos = db.execute('SELECT * FROM productos WHERE categoria = ?', (categoria,)).fetchall()
    return render_template('elementos.html', productos=productos, categoria=categoria)

@app.route('/agregar_al_pedido/<int:producto_id>')
def agregar_al_pedido(producto_id):
    db = get_db()
    producto = db.execute('SELECT * FROM productos WHERE id = ?', (producto_id,)).fetchone()
    
    # Verificar si ya existe en el pedido
    item = db.execute('SELECT * FROM pedidos WHERE producto_id = ? LIMIT 1', (producto_id,)).fetchone()
    
    if item:
        db.execute('UPDATE pedidos SET cantidad = cantidad + 1 WHERE id = ?', (item['id'],))
    else:
        db.execute('INSERT INTO pedidos (producto_id, cantidad) VALUES (?, 1)', (producto_id,))
    
    db.commit()
    flash(f'{producto["nombre"]} - ${producto["precio"]:.2f} añadido', 'added_product')
    return redirect(request.referrer or url_for('index'))

@app.route('/quitar_item/<int:producto_id>')
def quitar_item(producto_id):
    db = get_db()
    # Obtener el primer item del pedido para este producto
    item = db.execute('''
        SELECT id, cantidad FROM pedidos 
        WHERE producto_id = ? 
        LIMIT 1
    ''', (producto_id,)).fetchone()
    
    if item:
        if item['cantidad'] > 1:
            # Si hay más de 1, reducir cantidad
            db.execute('UPDATE pedidos SET cantidad = cantidad - 1 WHERE id = ?', (item['id'],))
        else:
            # Si solo hay 1, eliminar el registro
            db.execute('DELETE FROM pedidos WHERE id = ?', (item['id'],))
        
        db.commit()
        producto = db.execute('SELECT nombre, precio FROM productos WHERE id = ?', (producto_id,)).fetchone()
        flash(f'{producto["nombre"]} - ${producto["precio"]:.2f} removido', 'removed_product')
    
    return redirect(url_for('ver_pedido'))

@app.route('/ver_pedido')
def ver_pedido():
    db = get_db()
    pedido = db.execute('''
        SELECT p.id, p.nombre, p.precio, SUM(pd.cantidad) as cantidad 
        FROM pedidos pd
        JOIN productos p ON pd.producto_id = p.id
        GROUP BY p.id, p.nombre, p.precio
    ''').fetchall()
    
    total = sum(item['precio'] * item['cantidad'] for item in pedido)
    return render_template('pedido.html', pedido=pedido, total=total)

@app.route('/limpiar_pedido')
def limpiar_pedido():
    db = get_db()
    db.execute('DELETE FROM pedidos')
    db.commit()
    flash('Pedido limpiado correctamente', 'info')
    return redirect(url_for('ver_pedido'))

# =============================================
# RUTAS DE ADMINISTRACIÓN
# =============================================

@app.route('/admin/productos')
def admin_productos():
    db = get_db()
    productos = db.execute('SELECT * FROM productos ORDER BY fecha_creacion DESC').fetchall()
    return render_template('admin/productos.html', productos=productos)

@app.route('/admin/producto/nuevo', methods=['GET', 'POST'])
def nuevo_producto():
    if request.method == 'POST':
        nombre = request.form['nombre']
        descripcion = request.form['descripcion']
        precio = float(request.form['precio'])
        categoria = request.form['categoria'].lower()  # Convertir a minúsculas
        
        imagen = None
        if 'imagen' in request.files:
            file = request.files['imagen']
            if file and allowed_file(file.filename):
                filename = f"{datetime.now().timestamp()}_{secure_filename(file.filename)}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                imagen = filename
        
        db = get_db()
        db.execute('''
            INSERT INTO productos (nombre, descripcion, precio, imagen, categoria)
            VALUES (?, ?, ?, ?, ?)
        ''', (nombre, descripcion, precio, imagen, categoria))
        db.commit()
        
        flash('Producto creado exitosamente', 'success')
        return redirect(url_for('admin_productos'))
    
    return render_template('admin/nuevo_producto.html')

@app.route('/admin/producto/editar/<int:id>', methods=['GET', 'POST'])
def editar_producto(id):
    db = get_db()
    producto = db.execute('SELECT * FROM productos WHERE id = ?', (id,)).fetchone()
    
    if request.method == 'POST':
        nombre = request.form['nombre']
        descripcion = request.form['descripcion']
        precio = float(request.form['precio'])
        categoria = request.form['categoria'].lower()  # Convertir a minúsculas
        
        imagen = producto['imagen']
        if 'imagen' in request.files:
            file = request.files['imagen']
            if file and allowed_file(file.filename):
                if imagen:
                    try:
                        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], imagen))
                    except:
                        pass
                
                filename = f"{datetime.now().timestamp()}_{secure_filename(file.filename)}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                imagen = filename
        
        db.execute('''
            UPDATE productos 
            SET nombre=?, descripcion=?, precio=?, imagen=?, categoria=?
            WHERE id=?
        ''', (nombre, descripcion, precio, imagen, categoria, id))
        db.commit()
        
        flash('Producto actualizado exitosamente', 'success')
        return redirect(url_for('admin_productos'))
    
    return render_template('admin/editar_producto.html', producto=producto)

@app.route('/admin/producto/eliminar/<int:id>')
def eliminar_producto(id):
    db = get_db()
    producto = db.execute('SELECT * FROM productos WHERE id = ?', (id,)).fetchone()
    
    if producto['imagen']:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], producto['imagen']))
        except:
            pass
    
    db.execute('DELETE FROM productos WHERE id = ?', (id,))
    db.commit()
    
    flash('Producto eliminado exitosamente', 'info')
    return redirect(url_for('admin_productos'))

# Ruta para servir archivos subidos
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)