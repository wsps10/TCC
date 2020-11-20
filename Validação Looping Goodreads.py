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

    return [score, label, sadness, joy, fear, disgust, anger]


gc = client.GoodreadsClient('XXXXXX', 'XXXXXX')

if __name__ == '__main__':
    id_livro = 3
    book = gc.book(id_livro)
    sintese = book.description
    resultado = analizaLivro(sintese)

print(book)
print(sintese)

print('Score: {}\nLabel: {}\nSadness: {}\nJoy: {}\nFear: {}\nDisgust: {}\nAnger: {}'.format(resultado[0], resultado[1],
                                                                                            resultado[2], resultado[3], resultado[4],
                                                                                            resultado[5], resultado[6]))
