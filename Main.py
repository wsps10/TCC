import json
import mysql.connector
import os
import requests
import re
from Crypto.Cipher import AES
import base64
from flask import Flask, redirect, request, session, make_response, jsonify
from flask_cors import CORS
from xml.etree import ElementTree
from goodreads import client
from rauth.service import OAuth1Service
from twython import Twython
from watson_developer_cloud import NaturalLanguageUnderstandingV1
from watson_developer_cloud.natural_language_understanding_v1 \
    import Features, EmotionOptions, SentimentOptions

app = Flask(__name__)
CORS(app)  # Esta linha de comando foi essencial para o funcionamento do front end
port = int(os.getenv("PORT", 8000))
app.secret_key = "super secret key"

KEY_SIZE = 16
KEY = b'thisisasamplepas'
IV = b'4c0e38884e2079cd'

# links de acesso a autenticação de usuário pela api do twitter
REQUEST_TOKEN_URL = 'https://api.twitter.com/oauth/request_token'
ACCESS_TOKEN_URL = 'https://api.twitter.com/oauth/access_token'
AUTHORIZATION_URL = 'https://api.twitter.com/oauth/authorize'
SIGNIN_URL = 'https://api.twitter.com/oauth/authenticate'

# Chaves de acesso de desenvolvedor do goodreads
APP_KEY = 'xxxxxxx'
APP_SECRET = 'xxxxxxx'

# links de acesso a autenticação de usuário pela api do goodreads
goodreads = OAuth1Service(
    consumer_key='xxxxxxx',
    consumer_secret='xxxxxxx',
    name='goodreads',
    request_token_url='https://www.goodreads.com/oauth/request_token',
    authorize_url='https://www.goodreads.com/oauth/authorize',
    access_token_url='https://www.goodreads.com/oauth/access_token',
    base_url='https://www.goodreads.com/'
    )

# Chaves de acesso de desenvolvedor do goodreads
CONSUMER_KEY = 'xxxxxxx'
CONSUMER_SECRET = 'xxxxxxx'

# Configurações GoodReads
gc = client.GoodreadsClient(CONSUMER_KEY, CONSUMER_SECRET)

# Configurações do banco de dados MYSQL
config = {
    'user': 'xxxxxxx',
    'password': 'xxxxxxx',
    'host': 'sl-us-south-1-portal.28.dblayer.com',
    'port': 61675,
    'database': 'PRD',
    'ssl_verify_cert': False,
    'ssl_ca': 'cert.pem'
}

natural_language_understanding = NaturalLanguageUnderstandingV1(
    username='xxxxxxx',
    password='xxxxxxx',
    version='2018-03-16'
)


# PKCS5 Padding
def pad_pkcs5(text):
    try:
        length = KEY_SIZE - (len(text.encode('utf8')) % KEY_SIZE)
        return text.encode('utf8') + bytes(length) * length
    except:
        print("Padding exception in pad_pkcs5()")


# Encryption using AES CBC (128-bits)
def encrypt(plaintext, passphrase, iv):
    aes = AES.new(passphrase, AES.MODE_CBC, iv)
    return base64.b64encode(aes.encrypt(pad_pkcs5(plaintext)))


def analizaLivro(texto):
    response = natural_language_understanding.analyze(
                text=texto,
                features=Features(
                    sentiment=SentimentOptions(),
                    emotion=EmotionOptions()))

    score = response['sentiment']['document']['score']
    label = response['sentiment']['document']['label']
    sadness = response['emotion']['document']['emotion']['sadness']
    joy = response['emotion']['document']['emotion']['joy']
    fear = response['emotion']['document']['emotion']['fear']
    disgust = response['emotion']['document']['emotion']['disgust']
    anger = response['emotion']['document']['emotion']['anger']

    return [score, label, sadness, anger, joy, fear, disgust]


def db_cadastro(id_usuario, funcao, plataforma, email, senha, id_goodreads):
    connect = mysql.connector.connect(**config)
    cur = connect.cursor()
    resultado = None
    validacao = None
    insercao = None
    consulta_id = None
    mensagem = ''
    id = ''

    if plataforma == 'app':
        validacao = "where email = '" + email + "'"
        insercao = "INSERT INTO usuario (email, senha) VALUES('" + email + "', '" + senha + "')"
        consulta_id = "where email = '" + email + "'"

    elif plataforma == 'twitter':
        validacao = "where TWITTER_TOKEN = '" + email + "' AND TWITTER_TOKEN_SECRET = '" + senha + "'"
        if funcao == 'inserir':
            insercao = "UPDATE usuario set TWITTER_TOKEN = '" + email + "', TWITTER_TOKEN_SECRET = '" + senha + "' WHERE id = "+id_usuario
        else:
            insercao = "INSERT INTO usuario (TWITTER_TOKEN, TWITTER_TOKEN_SECRET) VALUES('" + email + "', '" + senha + "')"
        consulta_id = "where TWITTER_TOKEN = '" + email + "' AND TWITTER_TOKEN_SECRET = '" + senha + "'"
        email = ''

    elif plataforma == 'goodreads':
        validacao = "where goodreads_token = '" + email + "' AND goodreads_token_secret = '" + senha + "'"
        if funcao == 'inserir':
            insercao = "UPDATE usuario set goodreads_token = '" + email + "', goodreads_token_secret = '" + senha + "', id_goodreads = '" + id_goodreads + "'  WHERE id = "+id_usuario
        else:
            insercao = "INSERT INTO usuario (goodreads_token, goodreads_token_secret, id_goodreads) VALUES('" + email + "', '" + senha + "', '" + id_goodreads + "')"
        consulta_id = "where goodreads_token = '" + email + "' AND goodreads_token_secret = '" + senha + "'"
        email = ''

    cur.execute("SELECT id FROM usuario " + validacao)
    for row in cur:
        resultado = row[0]

    if resultado is None:
        cur.execute(insercao)
        cur.execute("commit")
    status = 'Success'

    cur.execute("SELECT id FROM usuario " + consulta_id)
    for row in cur:
        id = row[0]

    connect.close()
    email = email.encode('utf-8')
    return '{"status":"' + status + '","email":"' + email + '","id":"' + str(id) + '"}'


def db_login(plataforma, email, senha):
    connect = mysql.connector.connect(**config)
    cur = connect.cursor()
    validacao = None
    id = None

    if plataforma == 'app':
        validacao = "WHERE email = '" + email + "' AND senha = '"+senha+"'"
        mensagem = 'Password and e-mail does not match'

    elif plataforma == 'twitter':
        validacao = "WHERE TWITTER_TOKEN = '" + email + "' AND TWITTER_TOKEN_SECRET = '"+senha+"'"
        mensagem = 'Account not found'
        email = ''
    elif plataforma == 'goodreads':
        validacao = "WHERE goodreads_token = '" + email + "' AND goodreads_token_secret = '"+senha+"'"
        mensagem = 'Account not found'
        email = ''
    cur.execute("SELECT * FROM usuario "+validacao)

    for row in cur:
        id = row[0]

    if id is not None:
        status = 'Success'
    else:
        status = mensagem
        id = ''
    connect.close()
    email = email.encode('utf-8')
    return '{"status":"'+status+'","email":"'+email+'","id":"'+str(id)+'"}'


def db_busca_email(email):
    connect = mysql.connector.connect(**config)
    cur = connect.cursor()
    cur.execute("SELECT id, email FROM usuario WHERE email = '" + email + "'")
    resultado = None
    id = ''

    for row in cur:
        resultado = row[1]
        id = row[0]

    if resultado is not None:
        status = 'Success'
        email = email.encode('utf-8')
    else:
        status = 'Email not found'
        id = ''

    connect.close()
    return '{"status":"' + status + '","email":"' + email + '","id":"' + str(id) + '"}'


def db_busca_id(id):
    connect = mysql.connector.connect(**config)
    cur = connect.cursor()
    cur.execute("SELECT id, email, top1_emocao, top2_emocao FROM usuario WHERE id = " + id)
    email = ''
    top1_emocao = ''
    top2_emocao = ''

    for row in cur:
        id = row[0]
        email = row[1]
        top1_emocao = row[2]
        top2_emocao = row[3]

    print(str(email))
    print(str(id))
    print(str(top1_emocao))
    print(str(top2_emocao))
    if email is not None:
        email = email.encode('utf-8')
        status = 'Success'
    elif id is not None:
        status = 'Success'
        email = ''
    else:
        status = 'ID not found'
    if top1_emocao is None:
        top1_emocao = ''
    if top2_emocao is None:
        top2_emocao = ''

    connect.close()
    return '{"status":"' + status + '","email":"' + email + '","id":"' + str(id) + '"' \
           ',"top1_emocao":"' + top1_emocao + '","top2_emocao":"' + top2_emocao + '"}'


def db_busca_emocao(emocao, id, sinopse, analise_total):
    resultado_json = ''
    if sinopse == 'True':
        sinopse = 'AND sinopse IS NOT NULL'
    else:
        sinopse = ''
    if analise_total == 'True':
        analise_total = "AND plataforma = 'gutenberg'"
    else:
        analise_total = ''

    connect = mysql.connector.connect(**config)
    cur = connect.cursor()
    cur.execute("SELECT id_livro, autor, nome_livro, site, plataforma, img_capa, sinopse, data "
                "  FROM livro liv "
                "    WHERE (top1_emocao = '"+emocao+"' OR top2_emocao = '"+emocao+"') "+sinopse+" "+analise_total+""
                "    AND id_livro NOT IN (SELECT id_livro "
                "                            FROM lista_livro_usuario lista "
                "                              WHERE lista.plataforma = liv.plataforma"
                "                              AND lista.id_livro = liv.id_livro"
                "                              AND id_usuario = "+id+")"
                "       ORDER BY RAND()")

    for row in cur:
        id_livro = str(row[0])
        autor = row[1]
        nome_livro = row[2]
        site = row[3]
        plataforma = row[4].encode('utf-8')
        img_capa = row[5]
        sinopse = row[6]
        data = row[7]

        if autor is None:
            autor = ''
        else:
            autor = autor.encode('utf-8').replace('\n', ' ').replace('"', '')
        if site is None:
            site = ''
        else:
            site = site.encode('utf-8')
        if img_capa is None:
            img_capa = ''
        else:
            img_capa = img_capa.encode('utf-8')
        if sinopse is None:
            sinopse = ''
        else:
            sinopse = sinopse.encode('utf-8').replace('\n', ' ').replace('"', '')
        if data is None:
            data = ''
        else:
            data = str(data)

        if nome_livro is not '':
            nome_livro = nome_livro.encode('utf-8').replace('\n', ' ').replace('"', '')
            resultado_json = resultado_json + '{"id_livro":"' + id_livro + '","autor":"' + autor + '","nome_livro":"' + nome_livro + '"' \
                             ',"site":"' + site + '","plataforma":"' + plataforma + '","img_capa":"' + img_capa + '"' \
                             ',"sinopse":"' + sinopse + '","data":"' + data + '"},'

    if resultado_json is '':
        resultado_json = ']'

    connect.close()
    return '['+resultado_json[:-1]+']'


def db_recomendacao(emocao1, emocao2):
    resultado_json = ''

    connect = mysql.connector.connect(**config)
    cur = connect.cursor()
    cur.execute("SELECT id_livro, autor, nome_livro, site, plataforma, img_capa, sinopse, data"  
                "  FROM("
                "    SELECT id_livro, autor, nome_livro, site, plataforma, img_capa, sinopse, data" 
                "      FROM livro"
                "        WHERE top1_emocao = '{0}' AND top2_emocao = '{1}'" 
                "           ORDER BY RAND()) principal"
                " UNION "
                "SELECT id_livro, autor, nome_livro, site, plataforma, img_capa, sinopse, data" 
                "  FROM("
	            "    SELECT id_livro, autor, nome_livro, site, plataforma, img_capa, sinopse, data" 
                "      FROM livro"
                "        WHERE (top1_emocao = '{0}' OR top2_emocao = '{0}' )"
                "          ORDER BY RAND()) top1_emocao"
                " UNION "
                "SELECT id_livro, autor, nome_livro, site, plataforma, img_capa, sinopse, data" 
                "  FROM("
	            "    SELECT id_livro, autor, nome_livro, site, plataforma, img_capa, sinopse, data" 
                "      FROM livro"
                "        WHERE (top1_emocao = '{1}' OR top2_emocao = '{1}' )"
			    "          ORDER BY RAND()) top2_emocao".format(emocao1, emocao2))

    for row in cur:
        id_livro = str(row[0])
        autor = row[1]
        nome_livro = row[2]
        site = row[3]
        plataforma = row[4].encode('utf-8')
        img_capa = row[5]
        sinopse = row[6]
        data = row[7]

        if autor is None:
            autor = ''
        else:
            autor = autor.encode('utf-8').replace('\n', ' ').replace('"', '')
        if site is None:
            site = ''
        else:
            site = site.encode('utf-8')
        if img_capa is None:
            img_capa = ''
        else:
            img_capa = img_capa.encode('utf-8')
        if sinopse is None:
            sinopse = ''
        else:
            sinopse = sinopse.encode('utf-8').replace('\n', ' ').replace('"', '')
        if data is None:
            data = ''
        else:
            data = str(data)

        if nome_livro is not '':
            nome_livro = nome_livro.encode('utf-8')

            resultado_json = resultado_json + '{"id_livro":"' + id_livro + '","autor":"' + autor + '","nome_livro":"' + nome_livro + '"' \
                             ',"site":"' + site + '","plataforma":"' + plataforma + '","img_capa":"' + img_capa + '"' \
                             ',"sinopse":"' + sinopse + '","data":"' + data + '"},'

    if resultado_json is '':
        resultado_json = ']'

    connect.close()
    return '['+resultado_json[:-1]+']'


def busca_goodreads(id_usuario, titulo, autor, status):
    cleanr = re.compile('<.*?>')
    url = "https://www.goodreads.com/book/title.xml?key=95dRojHMRbZ6h9CthaPO2Q"
    titulo = titulo.replace(' ', '+')
    autor = autor.replace(' ', '+')
    url_titulo = "&title={}".format(titulo)
    url_autor = "&author={}".format(autor)
    url_final = url + url_titulo + url_autor
    print(url_final)

    response = requests.get(url_final)
    tree = ElementTree.fromstring(response.content)

    id_livro = tree[1][0].text
    print(id_livro)

    book = gc.book(id_livro)
    site_html = book.link
    img_capa = book.image_url
    img_capa_peq = book.small_image_url
    autor = str(book.authors).replace('[', '').replace(']', '').replace("'", "''")
    print(book, site_html, img_capa, img_capa_peq, autor)
    sinopse = book.description
    if sinopse is not None:
        try:
            sinopse = re.sub(cleanr, '', str(sinopse).replace("’", "'").replace("'", "''").replace('—', '-').encode('utf-8'))
            print(sinopse)

            data = book.publication_date
            if data[0] is None:
                mes = '01'
            else:
                mes = data[0]
            if data[1] is None:
                dia = '01'
            else:
                dia = data[1]
            if data[2]:
                data_final = "'"+data[2]+'-'+mes+'-'+dia+"'"
            else:
                data_final = "NULL"
            print(data_final)
            resultado = db_insere_livro(id_usuario, id_livro, autor, book, site_html, img_capa, img_capa_peq, data_final, sinopse, status)
            if resultado == 'Success':
                resultado = db_analisa_livro(id_livro, sinopse)
        except:
            resultado = 'No synthesis found, please choose another book'
    else:
        resultado = 'No synthesis found, please choose another book'

    resultado = '[{"status":"'+resultado+'"}]'
    return resultado


def livros_usuario_goodreads(id_goodreads):
    book_id = {}
    book_status = {}
    update_date = {}
    status = ''
    data_final = ''

    connect = mysql.connector.connect(**config)
    cur = connect.cursor()
    cur.execute("select id from usuario where id_goodreads = '" + id_goodreads + "'")
    for row in cur:
        id_usuario = str(row[0])
    connect.close()

    response = requests.get('https://www.goodreads.com/user/show/' + id_goodreads + '.xml?key=' + CONSUMER_KEY)

    tree = ElementTree.fromstring(response.content)
    x = 0
    for child in tree:
        for child2 in child:
            for child3 in child2:
                for child4 in child3:
                    for child5 in child4:
                        for child6 in child5:
                            for child7 in child6:
                                if child7.tag == 'book_id':
                                    book_id[x] = child7.text
                                if child7.tag == 'read_status':
                                    book_status[x] = child7.text
                                if child7.tag == 'updated_at':
                                    update_date[x] = child7.text
                                    x += 1

    for item in book_id:
        print(book_id[item])
        print(book_status[item])
        print(update_date[item])

        id_livro = book_id[item]
        book = gc.book(book_id[item])
        site_html = book.link.encode('utf-8')
        img_capa = book.image_url.encode('utf-8')
        img_capa_peq = book.small_image_url.encode('utf-8')
        try:
            autor = str(book.authors).replace('[', '').replace(']', '').replace("'", "''").encode('utf-8')
        except:
            autor = ''
        if book_status[item] == 'read':
            status = 'lido'
        elif book_status[item] == 'to-read':
            status = 'para_ler'
        elif book_status[item] == 'currently-reading':
            status = 'lendo'
        cleanr = re.compile('<.*?>')
        data = book.publication_date
        sinopse = book.description.encode('utf-8')
        sinopse = re.sub(cleanr, '', str(sinopse).replace("'", "''").replace('--', ' '))
        if data[0] is None:
            mes = '01'
        else:
            mes = data[0]
        if data[1] is None:
            dia = '01'
        else:
            dia = data[1]
        if data[2] is not None:
            data_final = data[2] + '-' + mes + '-' + dia

        teste = db_insere_livro(id_usuario, id_livro, autor, book, site_html, img_capa, img_capa_peq, data_final, sinopse, status)
        print(teste)
        if teste == 'Success':
            resultado = db_analisa_livro(id_livro, sinopse)


    return 'Success'


def db_insere_livro(id_usuario, id_livro, autor, book, site_html, img_capa, img_capa_peq, data_final, sinopse, status):
    connect = mysql.connector.connect(**config)
    cur = connect.cursor()
    print('entrou no insere_livro')
    print(id_livro)
    print(autor)
    print(book)
    print(sinopse)
    print(status)
    print(data_final)
    try:
        cur.execute("INSERT INTO livro (id_livro, autor, nome_livro, site, plataforma, img_capa, img_capa_peq, data, sinopse) "
                    "VALUES("+str(id_livro)+", '"+autor+"', '"+str(book).replace("'", "''")+"', "
                    "'"+site_html+"', 'goodreads', '"+img_capa+"', '"+img_capa_peq+"', '"+data_final+"', '"+sinopse+"')")
        cur.execute("commit")
        resultado = 'Success'
        print('inseriu livro')
    except:
        resultado = 'Book already inserted'

    if status != '':
        try:
            cur.execute("INSERT INTO lista_livro_usuario(id_livro, id_usuario, plataforma, status) "
                        "  VALUES(" + str(id_livro) + "," + str(id_usuario) + ",'goodreads', '" + status + "')")
            cur.execute("commit")
            connect.close()
            status = 'Book inserted successful'
            print('inseriu lista livro')
        except:
            cur.execute("UPDATE lista_livro_usuario"
                        "   SET STATUS = '" + status + "'"
                        "     WHERE ID_LIVRO = " + str(id_livro) + ""
                        "       AND ID_USUARIO = " + str(id_usuario) + ""
                        "       AND PLATAFORMA = 'goodreads'")
            cur.execute("commit")
    try:
        perfil = db_atualiza_perfil_usuario(id_usuario)
    except:
        erro = 'emocoes duplicadas'
    connect.close()
    return resultado


def db_analisa_livro(id_livro, sintese):
    connect = mysql.connector.connect(**config)
    cur = connect.cursor()

    resultado = analizaLivro(sintese)
    analise = [resultado[2], resultado[3], resultado[4], resultado[5], resultado[6]]
    ordenar = sorted(analise, reverse=True)

    top = ordenar[0]
    top2 = ordenar[1]
    top1_emocao = ''
    top2_emocao = ''

    if top == resultado[2]:
        top1_emocao = 'tristeza'
    elif top == resultado[3]:
        top1_emocao = 'raiva'
    elif top == resultado[4]:
        top1_emocao = 'felicidade'
    elif top == resultado[5]:
        top1_emocao = 'medo'
    elif top == resultado[6]:
        top1_emocao = 'desgosto'

    if top2 == resultado[2]:
        top2_emocao = 'tristeza'
    elif top2 == resultado[3]:
        top2_emocao = 'raiva'
    elif top2 == resultado[4]:
        top2_emocao = 'felicidade'
    elif top2 == resultado[5]:
        top2_emocao = 'medo'
    elif top2 == resultado[6]:
        top2_emocao = 'desgosto'

    cur.execute("INSERT INTO analise (id_livro, numero_capt, sentimento, resultado, tristeza, raiva, felicidade, "
                " medo, desgosto, top1_emocao, top2_emocao, plataforma) "
                "VALUES(" + str(id_livro) + ", 0, " + str(resultado[0]) + ","
                " '" + resultado[1] + "', " + str(resultado[2]) + ", " + str(resultado[3]) + ","
                " " + str(resultado[4]) + ", " + str(resultado[5]) + ", " + str(resultado[6]) + ","
                " '" + top1_emocao + "', '" + top2_emocao + "', 'goodreads')")

    cur.execute("UPDATE livro "
                "   SET top1_emocao = '{}', top2_emocao = '{}' "
                "       WHERE id_livro = {} AND plataforma = 'goodreads'".format(top1_emocao, top2_emocao, id_livro))

    cur.execute("commit")

    connect.close()
    return 'Book inserted successful'


def db_inserir_livro_usuario(id_livro, id_usuario, plataforma, status, origem):
    print(id_usuario, id_livro, plataforma, status)
    token = ''
    token_secret = ''
    connect = mysql.connector.connect(**config)
    cur = connect.cursor()

    try:
        cur.execute("INSERT INTO lista_livro_usuario(id_livro, id_usuario, plataforma, status) "
                    "  VALUES("+str(id_livro)+","+str(id_usuario)+",'"+plataforma+"', '"+status+"')")
        cur.execute("commit")
        status = 'Book inserted successful'
    except:
        cur.execute("UPDATE lista_livro_usuario"
                    "   SET STATUS = '"+status+"'"
                    "     WHERE ID_LIVRO = "+str(id_livro)+""
                    "       AND ID_USUARIO = "+str(id_usuario)+""
                    "       AND PLATAFORMA = '"+plataforma+"'")
        cur.execute("commit")
        status = 'Book updated successful'

    try:
        perfil = db_atualiza_perfil_usuario(id_usuario)
    except:
        erro = 'emocoes duplicadas'
    resultado = '{"status":"' + status + '"}'

    if plataforma == 'goodreads' and origem != 'goodreads':
        cur.execute("select goodreads_token, goodreads_token_secret from usuario where id = "+id_usuario)
        for row in cur:
            token = str(row[0])
        connect.close()
        print('token '+str(token))
        if str(token) != 'None':
            print(str(token))
            return connect_goodreads()
    else:
        connect.close()
    return resultado


def db_lista_livro_usuario(id_usuario):
    resultado_json = ''
    connect = mysql.connector.connect(**config)
    cur = connect.cursor()

    cur.execute("SELECT liv.id_livro, autor, nome_livro, site, lista.plataforma, img_capa, sinopse, data, lista.status "
                "  FROM lista_livro_usuario lista LEFT JOIN livro liv "
                "  ON lista.id_livro = liv.id_livro "
                "    WHERE STATUS <> 'cancelado' AND lista.id_usuario = "+id_usuario)
    for row in cur:
        id_livro = str(row[0])
        autor = row[1]
        nome_livro = row[2]
        site = row[3]
        plataforma = row[4].encode('utf-8')
        img_capa = row[5]
        sinopse = row[6]
        data = row[7]
        status = row[8]

        if autor is None:
            autor = ''
        else:
            autor = autor.encode('utf-8').replace('\n', ' ').replace('"', '')
        if site is None:
            site = ''
        else:
            site = site.encode('utf-8')
        if img_capa is None:
            img_capa = ''
        else:
            img_capa = img_capa.encode('utf-8')
        if sinopse is None:
            sinopse = ''
        else:
            sinopse = sinopse.encode('utf-8').replace('\n', ' ').replace('"', '')
        if data is None:
            data = ''
        else:
            data = str(data)
        if sinopse is None:
            status = ''
        else:
            status = status.encode('utf-8').replace('\n', ' ').replace('"', '')

        if nome_livro is not '':
            nome_livro = nome_livro.encode('utf-8')

            resultado_json = resultado_json + '{"id_livro":"' + id_livro + '","autor":"' + autor + '","nome_livro":"' + nome_livro + '"' \
                             ',"site":"' + site + '","plataforma":"' + plataforma + '","img_capa":"' + img_capa + '"' \
                             ',"sinopse":"' + sinopse + '","data":"' + data + '","status":"' + status + '"},'

    if resultado_json is '':
        resultado_json = ']'

    connect.close()
    return '['+resultado_json[:-1]+']'


def db_atualiza_perfil_usuario(id_usuario):
    qtde = {}
    x = 0
    connect = mysql.connector.connect(**config)
    cur = connect.cursor()

    cur.execute("SELECT id_usuario, top1_emocao, COUNT(1) AS qtde "
                "  FROM lista_livro_usuario lista"
                "    LEFT JOIN livro liv ON liv.id_livro = lista.id_livro "
                "      WHERE STATUS <> 'cancelado' AND id_usuario = " + id_usuario + " "
                "        GROUP BY id_usuario, top1_emocao")
    for row in cur:
        id_usuario = str(row[0])
        qtde[x] = str(row[2])
        x += 1

    ordenar = sorted(qtde.values(), reverse=True)
    top = str(ordenar[0])

    cur.execute("UPDATE usuario"
                "	SET  top1_emocao = ("
                "	SELECT top1_emocao FROM("
                "		SELECT id_usuario, top1_emocao, COUNT(1) AS qtde"
                "			FROM lista_livro_usuario lista"
                "				LEFT JOIN livro liv ON liv.id_livro = lista.id_livro"
                "                  WHERE id_usuario = " + id_usuario + ""
                "					GROUP BY id_usuario, top1_emocao "
                "					   HAVING count(1) = " + top + ""
                "        ) "
                "           result ) WHERE id = " + id_usuario + "")

    cur.execute("SELECT id_usuario, top2_emocao, COUNT(1) AS qtde "
                "  FROM lista_livro_usuario lista"
                "    LEFT JOIN livro liv ON liv.id_livro = lista.id_livro "
                "      WHERE STATUS <> 'cancelado' AND id_usuario = " + id_usuario + " "
                "        GROUP BY id_usuario, top2_emocao")
    x = 0
    for row in cur:
        id_usuario = str(row[0])
        qtde[x] = str(row[2])
        x += 1

    ordenar = sorted(qtde.values(), reverse=True)
    top = str(ordenar[0])
    cur.execute("UPDATE usuario"
                "	SET  top2_emocao = ("
                "	SELECT top2_emocao FROM("
                "		SELECT id_usuario, top2_emocao, COUNT(1) AS qtde"
                "			FROM lista_livro_usuario lista"
                "				LEFT JOIN livro liv ON liv.id_livro = lista.id_livro"
                "                  WHERE id_usuario = " + id_usuario + ""
                "					GROUP BY id_usuario, top2_emocao "
                "					   HAVING count(1) = " + top + ""
                "        ) "
                "           result ) WHERE id = " + id_usuario + "")

    cur.execute("commit")
    connect.close()
    print('atualizou perfil usuario')
    return 'Sucesso'


@app.route("/")
def paginicial():
    return '<br/>URLs disponiveis:' \
           '<br/>/cadastro/?email=&senha=' \
           '<br/>/login/?email=&senha=' \
           '<br/>/busca_email/?email=' \
           '<br/>/recomendacao_id_usuario/?id=' \
           '<br/>/recomendacao_emocao/?emocao=&id_usuario=&sinopse=&analise_total=' \
           '<br/>/recomendacao_aleatorio/?id_usuario=' \
           '<br/>/add_livro_base/?id_usuario=&status=&titulo=&autor=' \
           '<br/>/add_livro_usuario/?id_usuario=&id_livro=&plataforma=&status=(lendo/lido/para_ler)' \
           '<br/>/lista_livro_usuario/?id_usuario=' \
           '<br/>/twitter/?id_usuario=&funcao=(cadastrar/login/tweet)&tweet=&id_livro=&plataforma=' \
           '<br/>/goodreads/?id_usuario=&funcao=(cadastrar/login)&id_livro='


@app.route("/cadastro/", methods=['GET'])
def cadastro():
    email = request.args.get('email', None)
    senha = request.args.get('senha', None)
    resultado = db_cadastro('', 'cadastrar', 'app', email, senha)
    return str(resultado)


@app.route("/login/", methods=['GET'])
def login():
    email = request.args.get('email', None)
    senha = request.args.get('senha', None)
    resultado = db_login('app', email, senha)
    return str(resultado)


@app.route("/busca_email/", methods=['GET'])
def busca_email():
    email = request.args.get('email', None)
    resultado = db_busca_email(email)
    return str(resultado)


@app.route("/recomendacao_id_usuario/", methods=['GET'])
def recomendacao_id():
    id = request.args.get('id', None)
    resultado = db_busca_id(id)
    j = json.loads(resultado)
    if j['status'] == 'Success':
        resultado = db_recomendacao(j['top1_emocao'], j['top2_emocao'])
    return resultado


@app.route("/recomendacao_emocao/", methods=['GET'])
def recomendacao_emocao():
    emocao = request.args.get('emocao', None)
    id = request.args.get('id_usuario', None)
    sinopse = request.args.get('sinopse', None)
    analise_total = request.args.get('analise_total', None)
    resultado = db_busca_emocao(emocao, id, sinopse, analise_total)
    return resultado


@app.route("/recomendacao_aleatorio/", methods=['GET'])
def recomendacao_aleatorio():
    resultado_json = ''
    id_usuario = request.args.get('id_usuario', None)

    connect = mysql.connector.connect(**config)
    cur = connect.cursor()
    cur.execute("select top1_emocao, top2_emocao from usuario where id = "+id_usuario)
    for row in cur:
        emocao1 = str(row[0])
        emocao2 = str(row[1])
    print(id_usuario)
    print(emocao1)
    print(emocao2)
    cur.execute("SELECT id_livro, autor, nome_livro, site, plataforma, img_capa, sinopse, data "
                "   FROM livro "
                "      WHERE id_livro not in (select id_livro "
                "                               from lista_livro_usuario "
                "                                 where id_usuario = "+id_usuario+""
                "                               UNION"
                "                             SELECT id_livro" 
	            "                               FROM livro"
   	            "                                 WHERE ( top1_emocao = '{0}' AND top2_emocao = '{1}' )" 
                "                                 OR top1_emocao = '{0}' OR top2_emocao = '{0}' "
                "                             )"
                "         ORDER BY RAND()".format(emocao1, emocao2))

    for row in cur:
        id_livro = str(row[0])
        autor = row[1]
        nome_livro = row[2]
        site = row[3]
        plataforma = row[4].encode('utf-8')
        img_capa = row[5]
        sinopse = row[6]
        data = row[7]

        if autor is None:
            autor = ''
        else:
            autor = autor.encode('utf-8').replace('\n', ' ').replace('"', '')
        if site is None:
            site = ''
        else:
            site = site.encode('utf-8')
        if img_capa is None:
            img_capa = ''
        else:
            img_capa = img_capa.encode('utf-8')
        if sinopse is None:
            sinopse = ''
        else:
            sinopse = sinopse.encode('utf-8').replace('\n', ' ').replace('"', '')
        if data is None:
            data = ''
        else:
            data = str(data)

        if nome_livro is not '':
            nome_livro = nome_livro.encode('utf-8')
            resultado_json = resultado_json + '{"id_livro":"' + id_livro + '","autor":"' + autor + '","nome_livro":"' + nome_livro + '"' \
                             ',"site":"' + site + '","plataforma":"' + plataforma + '","img_capa":"' + img_capa + '"' \
                             ',"sinopse":"' + sinopse + '","data":"' + data + '"},'

    if resultado_json is '':
        resultado_json = ']'

    connect.close()
    resultado_json_final = '[' + resultado_json[:-1] + ']'
    return resultado_json_final


@app.route("/add_livro_base/", methods=['GET'])
def add_livro_base():
    id_usuario = request.args.get('id_usuario', None)
    titulo = request.args.get('titulo', None)
    autor = request.args.get('autor', None)
    status = request.args.get('status', None)
    resultado = busca_goodreads(id_usuario, titulo, autor, status)
    return str(resultado)


@app.route("/add_livro_usuario/", methods=['GET'])
def add_livro_usuario():
    id_livro = request.args.get('id_livro', None)
    id_usuario = request.args.get('id_usuario', None)
    plataforma = request.args.get('plataforma', None)
    status = request.args.get('status', None)
    print(id_usuario, id_livro, plataforma, status)
    resultado = db_inserir_livro_usuario(id_livro, id_usuario, plataforma, status, 'app')
    return resultado


@app.route("/lista_livro_usuario/", methods=['GET'])
def lista_livro_usuario():
    id_usuario = request.args.get('id_usuario', None)
    resultado = db_lista_livro_usuario(id_usuario)
    return resultado


@app.route('/twitter/', methods=['GET'])
def connect_twitter():
    id_usuario = request.args.get('id_usuario', None)
    id_livro = request.args.get('id_livro', None)
    plataforma = request.args.get('plataforma', None)
    funcao = request.args.get('funcao', None)
    texto = request.args.get('texto', None)
    OAUTH_TOKEN = None
    OAUTH_TOKEN_SECRET = None

    url = str(request.base_url).split('/')
    callback = 'https://' + str(url[2]) + '/tweet/oauth'
    twitter = Twython(APP_KEY, APP_SECRET)
    auth = twitter.get_authentication_tokens(callback_url=callback)
    redirect_url = auth['auth_url']

    if funcao == 'tweet':
        connect = mysql.connector.connect(**config)
        cur = connect.cursor()
        cur.execute("SELECT TWITTER_TOKEN, TWITTER_TOKEN_SECRET FROM usuario WHERE id = " + id_usuario)
        for row in cur:
            OAUTH_TOKEN = row[0]
            OAUTH_TOKEN_SECRET = row[1]
        if OAUTH_TOKEN and OAUTH_TOKEN_SECRET is not None:
            twitter = Twython(APP_KEY, APP_SECRET,
                              str(OAUTH_TOKEN), str(OAUTH_TOKEN_SECRET))
            twitter.update_status(status=texto)
            # A VARIAVEL RESULTADO DEVERA SER ARMAZENADA NO BANCO
            resultado = analizaLivro(texto)
            cur.execute("insert into usuario_tweet (id_usuario, id_livro, plataforma, tweet, sentimento) "
                        "values({0},{1},'{2}','{3}','{4}')".format(id_usuario, id_livro, plataforma, texto, resultado[1]))
            cur.execute("commit")
            resultado = '{"status":"Success"}'
        else:
            session['id_usuario'] = id_usuario
            session['funcao'] = funcao
            session['texto'] = texto
            session['token'] = auth['oauth_token']
            session['token_secret'] = auth['oauth_token_secret']
            resultado = redirect(redirect_url)

    else:
        session['id_usuario'] = id_usuario
        session['funcao'] = funcao
        session['texto'] = texto
        session['token'] = auth['oauth_token']
        session['token_secret'] = auth['oauth_token_secret']
        session.permanent = True
        resultado = redirect(redirect_url)
    return resultado


@app.route('/tweet/oauth/', methods=['GET'])
def twitter_autenticacao():
    resultado = None
    id = ''

    verifier = request.args.get('oauth_verifier', None)
    token_oauth = session.get('token', None)
    token_secret_oauth = session.get('token_secret', None)

    twitter = Twython(APP_KEY, APP_SECRET,
                      token_oauth, token_secret_oauth)

    final_step = twitter.get_authorized_tokens(verifier)

    OAUTH_TOKEN = str(final_step['oauth_token'])
    OAUTH_TOKEN_SECRET = str(final_step['oauth_token_secret'])

    if session.get('funcao', None) == 'cadastrar':
        resultado = db_cadastro('', 'cadastrar', 'twitter', OAUTH_TOKEN, OAUTH_TOKEN_SECRET, '')
    elif session.get('funcao', None) == 'login':
        resultado = db_login('twitter', OAUTH_TOKEN, OAUTH_TOKEN_SECRET)
    elif session.get('funcao', None) == 'tweet':
        resultado = db_cadastro(str(session.get('id_usuario', None)), 'inserir', 'twitter', OAUTH_TOKEN, OAUTH_TOKEN_SECRET, '')

    j = json.loads(resultado)
    if j['status'] == 'Success':
        id = str(j['id'])
    return redirect('http://kanoon.mybluemix.net/?id='+str(id))


@app.route('/goodreads/', methods=['GET'])
def connect_goodreads():
    id_usuario = request.args.get('id_usuario', None)
    id_livro = request.args.get('id_livro', None)
    funcao = request.args.get('funcao', None)
    status = request.args.get('status', None)

    request_token, request_token_secret = goodreads.get_request_token(header_auth=True)
    authorize_url = goodreads.get_authorize_url(request_token)

    session['request_token'] = request_token
    session['request_token_secret'] = request_token_secret
    session['id_usuario'] = id_usuario
    session['funcao'] = funcao
    session['id_livro'] = id_livro
    session['status'] = status

    return redirect(authorize_url)


@app.route('/goodreads/oauth/', methods=['GET'])
def goodreads_autenticacao():
    resultado = None
    id_goodreads = None
    auth = goodreads.get_auth_session(session.get('request_token', None), session.get('request_token_secret', None))

    if session.get('funcao', None) == 'cadastrar':
        response2 = auth.get('https://www.goodreads.com/api/auth_user')
        tree = ElementTree.fromstring(response2.content)
        for child in tree:
            id_goodreads = child.attrib.get("id", None)
        print('id_goodreads'+str(id_goodreads))

        resultado = db_cadastro('', 'cadastrar', 'goodreads', auth.access_token, auth.access_token_secret, id_goodreads)
        resultado2 = livros_usuario_goodreads(id_goodreads)
    elif session.get('funcao', None) == 'login':
        resultado = db_login('goodreads', auth.access_token, auth.access_token_secret)
    elif session.get('funcao', None) == 'livro':
        status = session.get('status', None)
        if status == 'lendo':
            status = 'currently-reading'
        elif status == 'lido':
            status = 'read'
        elif status == 'para_ler':
            status = 'to-read'
        print('status '+status)
        data = {'name': status, 'book_id': session.get('id_livro', None)}
        response = auth.post('https://www.goodreads.com/shelf/add_to_shelf.xml', data)
        if response.status_code == 201:
            resultado = '{"status":"Success","id":"'+session.get('request_token', None)+'"}'

    j = json.loads(resultado)
    if j['status'] == 'Success':
        id = str(j['id'])
    return redirect('http://kanoon.mybluemix.net/?id=' + str(id))


@app.route('/acesso_rede_social/', methods=['GET'])
def acesso_rede_social():
    resultado = '{"status": "Fail", "id":""}'
    print('1'+str(request.cookies))
    print(str(session.get('id_usuario', None)))
    print('2'+str(request.cookies))
    if 'kanoon' in request.cookies:
        resultado = '{"status":"Success", "id":"'+str(request.cookies.get('kanoon'))+'"}'
    print(resultado)
    return resultado


@app.route('/canhoto/')
def canhoto():
    connect = mysql.connector.connect(**config)
    cur = connect.cursor()
    cur.execute("delete from lista_livro_usuario where id_usuario = (select id from usuario where goodreads_token = 'aacFq7dlV5Rp11Ss9hSag')")
    cur.execute("delete from usuario where goodreads_token = 'aacFq7dlV5Rp11Ss9hSag'")
    cur.execute("delete from usuario where twitter_token is not null")
    cur.execute("commit")
    connect.close()
    return 'Success'


@app.route('/cookie/')
def cookie():
    id = '2'
    res = make_response(redirect("https://kanoon.mybluemix.net/"), jsonify(message='Chain created'))
    res.set_cookie('kanoon', id, max_age=60 * 10, domain='kanoon.mybluemix.net')
    return res


@app.route('/cookie2/')
def cookie2():
    id = '2'
    res = make_response(redirect("https://kanoon.mybluemix.net/"), jsonify(message='Chain created'))
    return res


@app.route('/criptografia/', methods=['POST'])
def criptografia():
    plaintext = request.form['texto']

    if len(plaintext) < 16:
        plaintext = plaintext + 'b'*(16 - len(plaintext))

    encrypted = encrypt(plaintext, KEY, IV)
    texto = str(encrypted)
    texto = texto[2:len(texto)-1]
    lista_texto = list(texto)

    x = 0
    marc = ''
    while x < len(lista_texto):
        if lista_texto[x] == '/':
            marc = marc + ',' + str(x)
        x += 1
    texto_trat = str(texto).replace('/', 'a')

    key = str(KEY)
    key = key[2:len(key)-1]

    iv = str(IV)
    iv = iv[2:len(iv) - 1]

    resultado = '{"IV":"'+iv+'", "KEY":"'+key+'", "ID":"'+str(texto)+'", "ID Tratado":"'+str(texto_trat)+'", "MARC":"'+str(marc[1:])+'"}'
    return resultado


@app.route('/keys')
def keys():
    key = str(KEY)
    key = key[2:len(key) - 1]

    iv = str(IV)
    iv = iv[2:len(iv) - 1]
    resultado = '{"iv":"'+iv+'", "key":"'+key+'"}'
    return resultado


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port)
