"""
API REST - GUIA CAQUI
=====================
Versão otimizada para Render/Railway
Suporta variáveis de ambiente
"""

import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
from urllib.parse import quote

# ==========================================
# CONFIGURAÇÃO
# ==========================================
app = Flask(__name__)
CORS(app)  # Permitir requisições de qualquer origem

# Ler configurações de variáveis de ambiente
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'seu_usuario_mysql.mysql.db'),
    'user': os.getenv('DB_USER', 'seu_usuario'),
    'password': os.getenv('DB_PASSWORD', 'sua_senha'),
    'database': os.getenv('DB_NAME', 'guia_caqui_db'),
    'autocommit': True
}

# ==========================================
# FUNÇÕES AUXILIARES
# ==========================================
def conectar_banco():
    """Conecta ao banco de dados MySQL."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"Erro ao conectar: {err}")
        return None

def formatar_oferta(oferta):
    """Formata uma oferta para retorno JSON."""
    return {
        'id': oferta[0],
        'supermercado': oferta[1],
        'produto': oferta[2],
        'marca': oferta[3],
        'quantidade': oferta[4],
        'preco': float(oferta[5]) if oferta[5] else None,
        'preco_original': float(oferta[6]) if oferta[6] else None,
        'desconto': round(
            ((oferta[6] - oferta[5]) / oferta[6] * 100) 
            if oferta[6] and oferta[5] else 0, 
            2
        ),
        'data_extracao': str(oferta[7]) if oferta[7] else None
    }

# ==========================================
# ROTAS
# ==========================================

@app.route('/', methods=['GET'])
def index():
    """Rota raiz - informações da API."""
    return jsonify({
        'status': 'ok',
        'nome': 'API Guia Caqui',
        'versao': '1.0',
        'endpoints': {
            'GET /': 'Informações da API',
            'GET /saude': 'Status de saúde',
            'GET /buscar': 'Buscar ofertas',
            'GET /supermercados': 'Listar supermercados',
            'GET /top-precos': 'Top 20 melhores preços',
            'GET /com-desconto': 'Ofertas com desconto'
        }
    })

@app.route('/saude', methods=['GET'])
def saude():
    """Verifica a saúde da API e conexão com banco."""
    try:
        conn = conectar_banco()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM ofertas")
            total = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            
            return jsonify({
                'status': 'ok',
                'banco_dados': 'conectado',
                'total_ofertas': total
            })
        else:
            return jsonify({
                'status': 'erro',
                'banco_dados': 'desconectado'
            }), 500
            
    except Exception as e:
        return jsonify({
            'status': 'erro',
            'mensagem': str(e)
        }), 500

@app.route('/buscar', methods=['GET'])
def buscar():
    """
    Busca ofertas por termo.
    
    Parâmetros:
    - termo: palavra-chave (obrigatório)
    - limite: número de resultados (padrão: 50)
    - supermercado: filtrar por supermercado (opcional)
    
    Exemplo:
    GET /buscar?termo=arroz&limite=20
    """
    try:
        termo = request.args.get('termo', '').strip()
        limite = request.args.get('limite', 50, type=int)
        supermercado = request.args.get('supermercado', '').strip()
        
        # Validar entrada
        if not termo:
            return jsonify({
                'status': 'erro',
                'mensagem': 'Parâmetro "termo" é obrigatório'
            }), 400
        
        if limite > 500:
            limite = 500  # Limite máximo
        
        # Conectar ao banco
        conn = conectar_banco()
        if not conn:
            return jsonify({
                'status': 'erro',
                'mensagem': 'Erro ao conectar ao banco de dados'
            }), 500
        
        cursor = conn.cursor()
        
        # Construir query
        query = """
            SELECT id, supermercado, produto, marca, quantidade, preco, preco_original, data_extracao
            FROM ofertas
            WHERE (produto LIKE %s OR marca LIKE %s)
        """
        params = [f"%{termo}%", f"%{termo}%"]
        
        # Filtrar por supermercado se fornecido
        if supermercado:
            query += " AND supermercado = %s"
            params.append(supermercado)
        
        # Ordenar por preço e limitar
        query += " ORDER BY preco ASC LIMIT %s"
        params.append(limite)
        
        cursor.execute(query, params)
        resultados = cursor.fetchall()
        
        # Formatar resultados
        ofertas = [formatar_oferta(r) for r in resultados]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'status': 'ok',
            'termo': termo,
            'total': len(ofertas),
            'ofertas': ofertas
        })
        
    except Exception as e:
        return jsonify({
            'status': 'erro',
            'mensagem': str(e)
        }), 500

@app.route('/supermercados', methods=['GET'])
def listar_supermercados():
    """Lista todos os supermercados cadastrados."""
    try:
        conn = conectar_banco()
        if not conn:
            return jsonify({
                'status': 'erro',
                'mensagem': 'Erro ao conectar ao banco de dados'
            }), 500
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT supermercado, COUNT(*) as total_ofertas
            FROM ofertas
            GROUP BY supermercado
            ORDER BY supermercado
        """)
        
        resultados = cursor.fetchall()
        supermercados = [
            {
                'nome': r[0],
                'total_ofertas': r[1]
            }
            for r in resultados
        ]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'status': 'ok',
            'total': len(supermercados),
            'supermercados': supermercados
        })
        
    except Exception as e:
        return jsonify({
            'status': 'erro',
            'mensagem': str(e)
        }), 500

@app.route('/top-precos', methods=['GET'])
def top_precos():
    """Retorna os 20 melhores preços."""
    try:
        conn = conectar_banco()
        if not conn:
            return jsonify({
                'status': 'erro',
                'mensagem': 'Erro ao conectar ao banco de dados'
            }), 500
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, supermercado, produto, marca, quantidade, preco, preco_original, data_extracao
            FROM ofertas
            WHERE preco IS NOT NULL
            ORDER BY preco ASC
            LIMIT 20
        """)
        
        resultados = cursor.fetchall()
        ofertas = [formatar_oferta(r) for r in resultados]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'status': 'ok',
            'total': len(ofertas),
            'ofertas': ofertas
        })
        
    except Exception as e:
        return jsonify({
            'status': 'erro',
            'mensagem': str(e)
        }), 500

@app.route('/com-desconto', methods=['GET'])
def com_desconto():
    """Retorna ofertas com desconto."""
    try:
        limite = request.args.get('limite', 50, type=int)
        
        if limite > 500:
            limite = 500
        
        conn = conectar_banco()
        if not conn:
            return jsonify({
                'status': 'erro',
                'mensagem': 'Erro ao conectar ao banco de dados'
            }), 500
        
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT id, supermercado, produto, marca, quantidade, preco, preco_original, data_extracao
            FROM ofertas
            WHERE preco_original > preco AND preco IS NOT NULL
            ORDER BY (preco_original - preco) DESC
            LIMIT {limite}
        """)
        
        resultados = cursor.fetchall()
        ofertas = [formatar_oferta(r) for r in resultados]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'status': 'ok',
            'total': len(ofertas),
            'ofertas': ofertas
        })
        
    except Exception as e:
        return jsonify({
            'status': 'erro',
            'mensagem': str(e)
        }), 500

@app.route('/estatisticas', methods=['GET'])
def estatisticas():
    """Retorna estatísticas gerais."""
    try:
        conn = conectar_banco()
        if not conn:
            return jsonify({
                'status': 'erro',
                'mensagem': 'Erro ao conectar ao banco de dados'
            }), 500
        
        cursor = conn.cursor()
        
        # Total de ofertas
        cursor.execute("SELECT COUNT(*) FROM ofertas")
        total_ofertas = cursor.fetchone()[0]
        
        # Total de supermercados
        cursor.execute("SELECT COUNT(DISTINCT supermercado) FROM ofertas")
        total_supermercados = cursor.fetchone()[0]
        
        # Preço médio
        cursor.execute("SELECT AVG(preco) FROM ofertas WHERE preco IS NOT NULL")
        preco_medio = cursor.fetchone()[0]
        
        # Maior desconto
        cursor.execute("""
            SELECT MAX((preco_original - preco) / preco_original * 100)
            FROM ofertas
            WHERE preco_original > preco AND preco IS NOT NULL
        """)
        maior_desconto = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'status': 'ok',
            'total_ofertas': total_ofertas,
            'total_supermercados': total_supermercados,
            'preco_medio': round(float(preco_medio), 2) if preco_medio else 0,
            'maior_desconto': round(float(maior_desconto), 2) if maior_desconto else 0
        })
        
    except Exception as e:
        return jsonify({
            'status': 'erro',
            'mensagem': str(e)
        }), 500

# ==========================================
# TRATAMENTO DE ERROS
# ==========================================

@app.errorhandler(404)
def nao_encontrado(error):
    return jsonify({
        'status': 'erro',
        'mensagem': 'Rota não encontrada'
    }), 404

@app.errorhandler(500)
def erro_interno(error):
    return jsonify({
        'status': 'erro',
        'mensagem': 'Erro interno do servidor'
    }), 500

# ==========================================
# EXECUÇÃO
# ==========================================

if __name__ == '__main__':
    # Obter porta da variável de ambiente (importante para Render)
    port = int(os.getenv('PORT', 5000))
    
    # Executar em produção
    app.run(
        host='0.0.0.0',  # Ouvir em todas as interfaces
        port=port,
        debug=False  # Desabilitar debug em produção
    )
