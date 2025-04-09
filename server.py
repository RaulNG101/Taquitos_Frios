from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_aqui'  # Necesaria para usar sesiones

# Datos de ejemplo (puedes reemplazar con una base de datos)
productos = {
    'hamburguesas': [
        {'id': 1, 'nombre': 'Big Mac', 'precio': 99},
        {'id': 2, 'nombre': 'Cuarto de Libra', 'precio': 89},
    ],
    'bebidas': [
        {'id': 3, 'nombre': 'Coca-Cola', 'precio': 35},
        {'id': 4, 'nombre': 'Fanta', 'precio': 35},
    ]
}

@app.route('/')
def index():
    # Inicializa el pedido en la sesión si no existe
    if 'pedido' not in session:
        session['pedido'] = []
    return render_template('index.html', categorias=productos.keys())

@app.route('/elementos/<categoria>')
def elementos(categoria):
    if categoria not in productos:
        return redirect(url_for('index'))
    return render_template('elementos.html', 
                         productos=productos[categoria],
                         categoria=categoria)

@app.route('/agregar_al_pedido', methods=['POST'])
def agregar_al_pedido():
    if request.method == 'POST':
        producto_id = int(request.form['producto_id'])
        # Busca el producto en todas las categorías
        producto = None
        for categoria in productos.values():
            for p in categoria:
                if p['id'] == producto_id:
                    producto = p.copy()
                    break
            if producto:
                break
        
        if producto:
            if 'pedido' not in session:
                session['pedido'] = []
            session['pedido'].append(producto)
            session.modified = True
    
    return redirect(url_for('ver_pedido'))

@app.route('/pedido')
def ver_pedido():
    total = sum(item['precio'] for item in session.get('pedido', []))
    return render_template('pedido.html', 
                         pedido=session.get('pedido', []),
                         total=total)

@app.route('/limpiar_pedido')
def limpiar_pedido():
    session.pop('pedido', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)