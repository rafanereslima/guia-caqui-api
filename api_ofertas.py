"""
API REST - Guia Caqui
Intermediário seguro entre o Frontend e o Banco de Dados MySQL
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
import os

app = Flask(__name__)
# Habilita CORS para permitir requisições do frontend
CORS(app)

# Configuração do banco de dados
DB_CONFIG = {
    'host': '69.6.249.178',
    'user': 'raf12059_admin',
    'password': 'Bam900624@',
    'database': 'raf12059_guia_caqui_db'
}

def get_db_connection():
    """Cria e retorna uma conexão com o banco de dados"""
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except Exception as e:
        print(f"Erro de conexão: {e}")
        return None

@app.route('/api/status', methods=['GET'])
def status():
    """Endpoint simples para verificar se a API está online"""
    return jsonify({"status": "online", "message": "API Guia Caqui funcionando!"})

@app.route('/api/ofertas/buscar', methods=['GET'])
def buscar_ofertas():
    """
    Endpoint principal de busca.
    Exemplo de uso: /api/ofertas/buscar?q=arroz&limit=20
    """
    # Pega o termo de busca da URL (query parameter 'q')
    termo_busca = request.args.get('q', '').strip()
    
    # Pega o limite de resultados (padrão 20)
    try:
        limite = int(request.args.get('limit', 20))
        if limite > 100: limite = 100  # Proteção contra abusos
    except ValueError:
        limite = 20
        
    if not termo_busca:
        return jsonify({
            "success": False, 
            "message": "O termo de busca (q) é obrigatório."
        }), 400
        
    conn = get_db_connection()
    if not conn:
        return jsonify({
            "success": False, 
            "message": "Erro ao conectar ao banco de dados."
        }), 500
        
    try:
        cursor = conn.cursor(dictionary=True) # Retorna resultados como dicionários
        
        # Query segura usando parâmetros (%s) para evitar SQL Injection
        query = """
            SELECT 
                id, 
                supermercado, 
                produto, 
                marca, 
                quantidade, 
                preco, 
                preco_original,
                DATE_FORMAT(data_extracao, '%d/%m/%Y %H:%i') as data_formatada
            FROM ofertas
            WHERE produto LIKE %s OR marca LIKE %s
            ORDER BY preco ASC
            LIMIT %s
        """
        
        # Adiciona % ao redor do termo para busca parcial (LIKE)
        termo_like = f"%{termo_busca}%"
        
        cursor.execute(query, (termo_like, termo_like, limite))
        resultados = cursor.fetchall()
        
        # Formatar os dados para o frontend
        ofertas_formatadas = []
        for row in resultados:
            # Calcular desconto se houver preço original
            desconto_pct = 0
            if row['preco_original'] and row['preco_original'] > row['preco']:
                desconto_pct = round(((row['preco_original'] - row['preco']) / row['preco_original']) * 100, 1)
                
            ofertas_formatadas.append({
                "id": row['id'],
                "supermercado": row['supermercado'],
                "produto": row['produto'],
                "marca": row['marca'] if row['marca'] else "",
                "quantidade": row['quantidade'] if row['quantidade'] else "",
                "preco": float(row['preco']),
                "preco_formatado": f"R$ {row['preco']:.2f}".replace('.', ','),
                "preco_original": float(row['preco_original']) if row['preco_original'] else None,
                "desconto_pct": desconto_pct,
                "data_atualizacao": row['data_formatada']
            })
            
        return jsonify({
            "success": True,
            "termo_buscado": termo_busca,
            "total_encontrado": len(ofertas_formatadas),
            "resultados": ofertas_formatadas
        })
        
    except Exception as e:
        return jsonify({
            "success": False, 
            "message": f"Erro ao realizar a busca: {str(e)}"
        }), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

@app.route('/api/ofertas/destaques', methods=['GET'])
def ofertas_destaque():
    """Retorna as melhores ofertas (maior desconto)"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "message": "Erro de conexão"}), 500
        
    try:
        cursor = conn.cursor(dictionary=True)
        
        query = """
            SELECT 
                id, supermercado, produto, marca, preco, preco_original,
                ROUND(((preco_original - preco) / preco_original) * 100, 1) as desconto_pct
            FROM ofertas
            WHERE preco_original IS NOT NULL AND preco_original > preco
            ORDER BY desconto_pct DESC
            LIMIT 10
        """
        
        cursor.execute(query)
        resultados = cursor.fetchall()
        
        # Formatar (similar ao endpoint de busca)
        ofertas = []
        for row in resultados:
            ofertas.append({
                "id": row['id'],
                "supermercado": row['supermercado'],
                "produto": row['produto'],
                "preco": float(row['preco']),
                "preco_formatado": f"R$ {row['preco']:.2f}".replace('.', ','),
                "preco_original": float(row['preco_original']),
                "desconto_pct": float(row['desconto_pct'])
            })
            
        return jsonify({
            "success": True,
            "resultados": ofertas
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

if __name__ == '__main__':
    # Em produção, use um servidor WSGI como Gunicorn
    # Para desenvolvimento local:
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
