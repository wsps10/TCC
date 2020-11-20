from gutenberg.acquire import set_metadata_cache
from gutenberg.acquire.metadata import SqliteMetadataCache
from gutenberg.query import get_metadata
import re
import mysql.connector

config = {
    'user': 'XXXXXX',
    'password': 'XXXXXX',
    'host': 'sl-us-south-1-portal.28.dblayer.com',
    'port': XXXXXX,
    'database': 'XXXXXX',

    # Create SSL connection with the self-signed certificate
    'ssl_verify_cert': False,
    'ssl_ca': 'cert.pem'
}

connect = mysql.connector.connect(**config)
cur = connect.cursor()

cache = SqliteMetadataCache('C:/Users/William/Documents/Arquivos UNIP/Sétimo Semestre/TCC/Cache Gutenberg/cache.sqlite')
set_metadata_cache(cache)

livros_banco = {}
x = 0
cur.execute("SELECT id_livro FROM livro where plataforma = 'gutenberg'")
for row in cur:
    livros_banco[x] = row[0]
    x += 1

id_livro = 490

while id_livro < 1000:
    y = 0
    proximo_id = False
    while y < len(livros_banco) and proximo_id is not True:
        if id_livro == livros_banco[y]:
            proximo_id = True
        else:
            y += 1

    if proximo_id is not True:
        autor = list(get_metadata('author', id_livro))
        site = list(get_metadata('formaturi', id_livro))
        nome_livro = list(get_metadata('title', id_livro))

        x = 0
        sair = False

        while x < len(site):
            if re.search('htm', site[x]) and sair == False:
                site_html = site[x]
                sair = True
            x += 1

        if len(nome_livro) is not 0:
            try:
                cur.execute("INSERT INTO livro (id_livro, autor, nome_livro, site, plataforma)"
                            "VALUES(" + str(id_livro) + ", '" + autor[0].replace("'", "''") + "',"
                            " '" + nome_livro[0].replace("'", "''") + "',  '" + site_html + "', 'gutenberg')")
            except IndexError:
                cur.execute("INSERT INTO livro (id_livro, nome_livro, site, plataforma) "
                            "VALUES(" + str(id_livro) + ", '" + nome_livro[0].replace("'", "''") + "',  "
                            "'" + site_html + "', 'gutenberg')")
            cur.execute("commit")
            print(str(id_livro) + '< == Livro Inserido')

            livros_banco = {}
            x = 0
            cur.execute("SELECT id_gut FROM livro")
            for row in cur:
                livros_banco[x] = row[0]
                x += 1
        else:
            print(id_livro)
    id_livro += 1
connect.close()

#if str(titulo) != 'frozenset()':
#    try:
#        found = re.search("'(.+?)'", str(titulo)).group(1)
#        print('{} - {}'.format(10, found))
#    except:
#        found = re.search('"(.+?)"', str(titulo)).group(1)
#        print('{} - {}'.format(10, found))

