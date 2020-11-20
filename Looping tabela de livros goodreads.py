import mysql.connector
from goodreads import client
gc = client.GoodreadsClient('XXXXXX', 'XXXXXX')

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

id_livro = 300

connect = mysql.connector.connect(**config)
cur = connect.cursor()

livros_banco = {}
x = 0
cur.execute("SELECT id_livro FROM livro where plataforma = 'goodreads'")
for row in cur:
    livros_banco[x] = row[0]
    x += 1

while id_livro < 320:
    y = 0
    proximo_id = False
    while y < len(livros_banco) and proximo_id is not True:
        if id_livro == livros_banco[y]:
            proximo_id = True
        else:
            y += 1

    if proximo_id is not True:
        book = gc.book(id_livro)
        site_html = book.link
        img_capa = book.image_url
        img_capa_peq = book.small_image_url
        autor = str(book.authors).replace('[', '').replace(']', '').replace("'", "''")

        cur.execute("INSERT INTO livro (id_livro, autor, nome_livro, site, plataforma, img_capa, img_capa_peq) "
                    "VALUES(" + str(id_livro) + ", '" + autor + "', '" + str(book).replace("'", "''") + "', "
                    "'" + site_html + "', 'goodreads', '" + img_capa + "', '" + img_capa_peq + "')")
        cur.execute("commit")

        print(str(id_livro) + '< == Livro Inserido')

        sair = False
    else:
        print(id_livro)
    id_livro += 1

connect.close()
