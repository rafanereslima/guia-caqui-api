"""
API REST - GUIA CAQUI
=====================
Versão otimizada para Render/Railway
Suporta variáveis de ambiente
Filtro por data: hoje, ontem, ou nenhuma oferta
"""

import os
import json
from datetime import datetime, timedelta
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
        'desconto': float(round(
            ((oferta[6] - oferta[5]) / oferta[6] * 100) 
            if oferta[6] and oferta[5] else 0, 
            2
        )),
        'data_extracao': str(oferta[7]) if oferta[7] else None
    }

def obter_data_hoje():
    """Retorna a data de hoje em formato YYYY-MM-DD."""
    return datetime.now().strftime('%Y-%m-%d')

def obter_data_ontem():
    """Retorna a data de ontem em formato YYYY-MM-DD."""
    ontem = datetime.now() - timedelta(days=1)
    return ontem.strftime('%Y-%m-%d')

# ==========================================
# ROTAS
# ==========================================

@app.route('/', methods=['GET'])
def index():
    """Rota raiz - informações da API."""
    return jsonify({
        'status': 'ok',
        'nome': 'API Guia Caqui',
        'versao': '2.0',
        'endpoints': {
            'GET /': 'Informações da API',
            'GET /saude': 'Status de saúde',
            'GET /buscar': 'Buscar ofertas (hoje ou ontem)',
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
                'total_ofertas': total,
                'data_hoje': obter_data_hoje()
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
    Busca ofertas por termo com filtro de data.
    
    Lógica:
    1. Retorna ofertas do dia atual
    2. Se nenhuma do dia atual, retorna do dia anterior
    3. Se nenhuma em ambos, retorna erro
    
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
        
        # Datas para filtro
        data_hoje = obter_data_hoje()
        data_ontem = obter_data_ontem()
        
        # Construir query base
        query_base = """
            SELECT id, supermercado, produto, marca, quantidade, preco, preco_original, data_extracao
            FROM ofertas
            WHERE (produto LIKE %s OR marca LIKE %s)
        """
        params_base = [f"%{termo}%", f"%{termo}%"]
        
        # Adicionar filtro de supermercado se fornecido
        if supermercado:
            query_base += " AND supermercado = %s"
            params_base.append(supermercado)
        
        # ========================================
        # PASSO 1: Tentar buscar ofertas de HOJE
        # ========================================
        query_hoje = query_base + f"""
            AND DATE(data_extracao) = '{data_hoje}'
            ORDER BY preco ASC LIMIT %s
        """
        params_hoje = params_base + [limite]
        
        cursor.execute(query_hoje, params_hoje)
        resultados_hoje = cursor.fetchall()
        
        # Se encontrou ofertas de hoje, retornar
        if resultados_hoje:
            ofertas = [formatar_oferta(r) for r in resultados_hoje]
            cursor.close()
            conn.close()
            
            return jsonify({
                'status': 'ok',
                'termo': termo,
                'total': len(ofertas),
                'periodo': f'Hoje ({data_hoje})',
                'ofertas': ofertas
            })
        
        # ========================================
        # PASSO 2: Se não encontrou hoje, tentar ONTEM
        # ========================================
        query_ontem = query_base + f"""
            AND DATE(data_extracao) = '{data_ontem}'
            ORDER BY preco ASC LIMIT %s
        """
        params_ontem = params_base + [limite]
        
        cursor.execute(query_ontem, params_ontem)
        resultados_ontem = cursor.fetchall()
        
        # Se encontrou ofertas de ontem, retornar
        if resultados_ontem:
            ofertas = [formatar_oferta(r) for r in resultados_ontem]
            cursor.close()
            conn.close()
            
            return jsonify({
                'status': 'ok',
                'termo': termo,
                'total': len(ofertas),
                'periodo': f'Ontem ({data_ontem})',
                'ofertas': ofertas
            })
        
        # ========================================
        # PASSO 3: Se não encontrou em nenhum dia
        # ========================================
        cursor.close()
        conn.close()
        
        return jsonify({
            'status': 'ok',
            'termo': termo,
            'total': 0,
            'periodo': 'Nenhuma',
            'mensagem': f'Não foi possível encontrar ofertas para "{termo}" nos últimos 2 dias.',
            'ofertas': []
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
    """Retorna os 20 melhores preços de hoje ou ontem."""
    try:
        conn = conectar_banco()
        if not conn:
            return jsonify({
                'status': 'erro',
                'mensagem': 'Erro ao conectar ao banco de dados'
            }), 500
        
        cursor = conn.cursor()
        
        data_hoje = obter_data_hoje()
        data_ontem = obter_data_ontem()
        
        # Tentar buscar de hoje
        cursor.execute(f"""
            SELECT id, supermercado, produto, marca, quantidade, preco, preco_original, data_extracao
            FROM ofertas
            WHERE preco IS NOT NULL AND DATE(data_extracao) = '{data_hoje}'
            ORDER BY preco ASC
            LIMIT 20
        """)
        
        resultados = cursor.fetchall()
        periodo = f'Hoje ({data_hoje})'
        
        # Se não encontrou hoje, buscar ontem
        if not resultados:
            cursor.execute(f"""
                SELECT id, supermercado, produto, marca, quantidade, preco, preco_original, data_extracao
                FROM ofertas
                WHERE preco IS NOT NULL AND DATE(data_extracao) = '{data_ontem}'
                ORDER BY preco ASC
                LIMIT 20
            """)
            resultados = cursor.fetchall()
            periodo = f'Ontem ({data_ontem})'
        
        ofertas = [formatar_oferta(r) for r in resultados]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'status': 'ok',
            'total': len(ofertas),
            'periodo': periodo,
            'ofertas': ofertas
        })
        
    except Exception as e:
        return jsonify({
            'status': 'erro',
            'mensagem': str(e)
        }), 500

@app.route('/com-desconto', methods=['GET'])
def com_desconto():
    """Retorna ofertas com desconto de hoje ou ontem."""
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
        
        data_hoje = obter_data_hoje()
        data_ontem = obter_data_ontem()
        
        # Tentar buscar de hoje
        cursor.execute(f"""
            SELECT id, supermercado, produto, marca, quantidade, preco, preco_original, data_extracao
            FROM ofertas
            WHERE preco_original > preco AND preco IS NOT NULL AND DATE(data_extracao) = '{data_hoje}'
            ORDER BY (preco_original - preco) DESC
            LIMIT {limite}
        """)
        
        resultados = cursor.fetchall()
        periodo = f'Hoje ({data_hoje})'
        
        # Se não encontrou hoje, buscar ontem
        if not resultados:
            cursor.execute(f"""
                SELECT id, supermercado, produto, marca, quantidade, preco, preco_original, data_extracao
                FROM ofertas
                WHERE preco_original > preco AND preco IS NOT NULL AND DATE(data_extracao) = '{data_ontem}'
                ORDER BY (preco_original - preco) DESC
                LIMIT {limite}
            """)
            resultados = cursor.fetchall()
            periodo = f'Ontem ({data_ontem})'
        
        ofertas = [formatar_oferta(r) for r in resultados]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'status': 'ok',
            'total': len(ofertas),
            'periodo': periodo,
            'ofertas': ofertas
        })
        
    except Exception as e:
        return jsonify({
            'status': 'erro',
            'mensagem': str(e)
        }), 500

@app.route('/estatisticas', methods=['GET'])
def estatisticas():
    """Retorna estatísticas gerais de hoje ou ontem."""
    try:
        conn = conectar_banco()
        if not conn:
            return jsonify({
                'status': 'erro',
                'mensagem': 'Erro ao conectar ao banco de dados'
            }), 500
        
        cursor = conn.cursor()
        
        data_hoje = obter_data_hoje()
        data_ontem = obter_data_ontem()
        
        # Total de ofertas de hoje
        cursor.execute(f"SELECT COUNT(*) FROM ofertas WHERE DATE(data_extracao) = '{data_hoje}'")
        total_hoje = cursor.fetchone()[0]
        
        # Se não tem hoje, pega de ontem
        if total_hoje == 0:
            cursor.execute(f"SELECT COUNT(*) FROM ofertas WHERE DATE(data_extracao) = '{data_ontem}'")
            total_ofertas = cursor.fetchone()[0]
            periodo = f'Ontem ({data_ontem})'
        else:
            total_ofertas = total_hoje
            periodo = f'Hoje ({data_hoje})'
        
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
            'periodo': periodo,
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
