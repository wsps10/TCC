import mysql.connector
from goodreads import client
from watson_developer_cloud import NaturalLanguageUnderstandingV1
from watson_developer_cloud.natural_language_understanding_v1 \
    import Features, EmotionOptions, SentimentOptions

natural_language_understanding = NaturalLanguageUnderstandingV1(
    username='XXXXXX',
    password='XXXXXX',
    version='2018-03-16'
)


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


connect = mysql.connector.connect(**config)
cur = connect.cursor()


if __name__ == '__main__':
    id_livro = {}
    x = 0
    cur.execute("SELECT id_livro FROM livro where plataforma = 'goodreads'")
    for row in cur:
        id_livro[x] = row[0]
        x += 1

    y = 0

    while y < len(id_livro):
    #while y < 3:
        book = gc.book(id_livro[y])
        sintese = book.description
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
                    "VALUES(" + str(id_livro[y]) + ", 0, " + str(resultado[0]) + ","
                    " '" + resultado[1] + "', " + str(resultado[2]) + ", " + str(resultado[3]) + ","
                    " " + str(resultado[4]) + ", " + str(resultado[5]) + ", " + str(resultado[6]) + ","
                    " '" + top1_emocao + "', '" + top2_emocao + "', 'goodreads')")
        cur.execute("commit")
        print('{} <== Livro Inserido !'.format(id_livro[y]))

        y += 1
connect.close()
