import click
import logging
import re
import os
import mysql.connector
from nltk.tokenize import word_tokenize
from nltk.tokenize import sent_tokenize
from nltk.corpus import stopwords
from string import punctuation
from nltk.probability import FreqDist
from collections import defaultdict
from heapq import nlargest
from gutenberg.acquire import load_etext
from watson_developer_cloud import NaturalLanguageUnderstandingV1
from watson_developer_cloud.natural_language_understanding_v1 \
    import Features, EmotionOptions, SentimentOptions

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
    anger = response['emotion']['document']['emotion']['anger']
    joy = response['emotion']['document']['emotion']['joy']
    fear = response['emotion']['document']['emotion']['fear']
    disgust = response['emotion']['document']['emotion']['disgust']

    return [score, label, sadness, anger, joy, fear, disgust]


@click.option('--nochapters', is_flag=True, default=False, help="Don't actually split the book into chapters. Just extract the inner text.")
@click.option('--stats', is_flag=True, default=False, help="Don't actually split the book into chapters. Just return statistics about the chapters.")
@click.option('--verbose', is_flag=True, help='Get extra information about what\'s happening behind the scenes.')
@click.option('--debug', is_flag=True, help='Turn on debugging messages.')
@click.version_option('0.1')
def cli(book, nochapters, stats, verbose, debug, gut):
    """ This tool breaks up a plain text book into chapters.
    It works especially well with Project Gutenberg plain text ebooks.
    This may also be used to strip metatextual text (tables of contents,
    headings, Project Gutenberg licenses) from a book, to prepare it
    for text analysis. Just use the --nochapters option.
    """

    if verbose:
        logging.basicConfig(level=logging.INFO)

    if debug:
        logging.basicConfig(level=logging.DEBUG)

    logging.info('Now attempting to break the file %s into chapters.' % book)

    bookObj = Book(book, nochapters, stats, gut)


class Book():
    def __init__(self, filename, nochapters, stats, gut):
        self.gut = gut
        self.filename = filename
        self.nochapters = nochapters
        self.contents = self.getContents()
        self.lines = self.getLines()
        self.headings = self.getHeadings()
        # Alias for historical reasons. FIXME
        self.headingLocations = self.headings
        self.ignoreTOC()
        logging.info('Heading locations: %s' % self.headingLocations)
        headingsPlain = [self.lines[loc] for loc in self.headingLocations]
        logging.info('Headings: %s' % headingsPlain)
        self.chapters = self.getTextBetweenHeadings()
        # logging.info('Chapters: %s' % self.chapters)
        self.numChapters = len(self.chapters)

        if stats:
            self.getStats()
        else:
            self.writeChapters()

    def getContents(self):
        """
        Reads the book into memory.
        """
        contents = load_etext(self.gut).replace('”', '"').replace('“', '"')
        return contents

    def getLines(self):
        """
        Breaks the book into lines.
        """
        return self.contents.split('\n')

    def getHeadings(self):

        # Form 1: Chapter I, Chapter 1, Chapter the First, CHAPTER 1
        # Ways of enumerating chapters, e.g.
        arabicNumerals = '\d+'
        romanNumerals = '(?=[MDCLXVI])M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})'
        numberWordsByTens = ['twenty', 'thirty', 'forty', 'fifty', 'sixty',
                              'seventy', 'eighty', 'ninety']
        numberWords = ['one', 'two', 'three', 'four', 'five', 'six',
                       'seven', 'eight', 'nine', 'ten', 'eleven',
                       'twelve', 'thirteen', 'fourteen', 'fifteen',
                       'sixteen', 'seventeen', 'eighteen', 'nineteen'] + numberWordsByTens
        numberWordsPat = '(' + '|'.join(numberWords) + ')'
        ordinalNumberWordsByTens = ['twentieth', 'thirtieth', 'fortieth', 'fiftieth',
                                    'sixtieth', 'seventieth', 'eightieth', 'ninetieth'] + \
                                    numberWordsByTens
        ordinalNumberWords = ['first', 'second', 'third', 'fourth', 'fifth', 'sixth',
                              'seventh', 'eighth', 'ninth', 'twelfth', 'last'] + \
                             [numberWord + 'th' for numberWord in numberWords] + ordinalNumberWordsByTens
        ordinalsPat = '(the )?(' + '|'.join(ordinalNumberWords) + ')'
        enumeratorsList = [arabicNumerals, romanNumerals, numberWordsPat, ordinalsPat]
        enumerators = '(' + '|'.join(enumeratorsList) + ')'
        form1 = 'chapter ' + enumerators

        # Form 2: II. The Mail
        enumerators = romanNumerals
        separators = '(\. | )'
        titleCase = '[A-Z][a-z]'
        form2 = enumerators + separators + titleCase

        # Form 3: II. THE OPEN ROAD
        enumerators = romanNumerals
        separators = '(\. )'
        titleCase = '[A-Z][A-Z]'
        form3 = enumerators + separators + titleCase

        # Form 4: a number on its own, e.g. 8, VIII
        arabicNumerals = '^\d+\.?$'
        romanNumerals = '(?=[MDCLXVI])M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})\.?$'
        enumeratorsList = [arabicNumerals, romanNumerals]
        enumerators = '(' + '|'.join(enumeratorsList) + ')'
        form4 = enumerators

        pat = re.compile(form1, re.IGNORECASE)
        # This one is case-sensitive.
        pat2 = re.compile('(%s|%s|%s)' % (form2, form3, form4))

        # TODO: can't use .index() since not all lines are unique.

        headings = []
        for i, line in enumerate(self.lines):
            if pat.match(line) is not None:
                headings.append(i)
            if pat2.match(line) is not None:
                headings.append(i)

        if len(headings) < 3:
            #logging.info('Headings: %s' % headings)
            #logging.error("Detected fewer than three chapters. This probably means there's something wrong with chapter detection for this book.")
            raise ValueError('Falha ao identificar os capitulos')

        self.endLocation = self.getEndLocation()

        # Treat the end location as a heading.
        headings.append(self.endLocation)

        return headings

    def ignoreTOC(self):
        """
        Filters headings out that are too close together,
        since they probably belong to a table of contents.
        """
        pairs = zip(self.headingLocations, self.headingLocations[1:])
        toBeDeleted = []
        for pair in pairs:
            delta = pair[1] - pair[0]
            if delta < 4:
                if pair[0] not in toBeDeleted:
                    toBeDeleted.append(pair[0])
                if pair[1] not in toBeDeleted:
                    toBeDeleted.append(pair[1])
        logging.debug('TOC locations to be deleted: %s' % toBeDeleted)
        for badLoc in toBeDeleted:
            index = self.headingLocations.index(badLoc)
            del self.headingLocations[index]

    def getEndLocation(self):
        """
        Tries to find where the book ends.
        """
        ends = ["End of the Project Gutenberg EBook",
                "End of Project Gutenberg's",
                "\*\*\*END OF THE PROJECT GUTENBERG EBOOK",
                "\*\*\* END OF THIS PROJECT GUTENBERG EBOOK"]
        joined = '|'.join(ends)
        pat = re.compile(joined, re.IGNORECASE)
        endLocation = None
        for line in self.lines:
            if pat.match(line) is not None:
                endLocation = self.lines.index(line)
                self.endLine = self.lines[endLocation]
                break

        if endLocation is None: # Can't find the ending.
            logging.info("Can't find an ending line. Assuming that the book ends at the end of the text.")
            endLocation = len(self.lines)-1 # The end
            self.endLine = 'None'

        logging.info('End line: %s at line %s' % (self.endLine, endLocation))
        return endLocation

    def getTextBetweenHeadings(self):
        chapters = []
        lastHeading = len(self.headingLocations) - 1
        for i, headingLocation in enumerate(self.headingLocations):
            if i is not lastHeading:
                nextHeadingLocation = self.headingLocations[i+1]
                chapters.append(self.lines[headingLocation+1:nextHeadingLocation])
        return chapters

    def zeroPad(self, numbers):
        """
        Takes a list of ints and zero-pads them, returning
        them as a list of strings.
        """
        maxNum = max(numbers)
        maxDigits = len(str(maxNum))
        numberStrs = [str(number).zfill(maxDigits) for number in numbers]
        return numberStrs

    def getStats(self):
        """
        Returns statistics about the chapters, like their length.
        """
        # TODO: Check to see if there's a log file. If not, make one.
        # Write headings to file.
        numChapters = self.numChapters
        averageChapterLength = sum([len(chapter) for chapter in self.chapters])/numChapters
        headings = ['Filename', 'Average chapter length', 'Number of chapters']
        stats = ['"' + self.filename + '"', averageChapterLength, numChapters]
        stats = [str(val) for val in stats]
        headings = ','.join(headings) + '\n'
        statsLog = ','.join(stats) + '\n'
        logging.info('Log headings: %s' % headings)
        logging.info('Log stats: %s' % statsLog)

        if not os.path.exists('log.txt'):
            logging.info('Log file does not exist. Creating it.')
            with open('log.txt', 'w') as f:
                f.write(headings)
                f.close()

        with open('log.txt', 'a') as f:
            f.write(statsLog)
            f.close()

    def writeChapters(self):
        chapterNums = self.zeroPad(range(1, len(self.chapters)+1))
        logging.debug('Writing chapter headings: %s' % chapterNums)
        basename = os.path.basename(self.filename)
        noExt = os.path.splitext(basename)[0]

        if self.nochapters:
            # Join together all the chapters and lines.
            text = ""
            for chapter in self.chapters:
                # Stitch together the lines.
                chapter = '\n'.join(chapter)
                # Stitch together the chapters.
                text += chapter + '\n'
            ext = '-extracted.txt'
            path = noExt + ext
            with open(path, 'w') as f:
                f.write(text)
        else:
            logging.info('Filename: %s' % noExt)
            for num, chapter in zip(chapterNums, self.chapters):

                logging.debug(chapter)
                chapter = '\n'.join(chapter)
                capitulo[int(num)] = chapter


if __name__ == '__main__':
    stopwords = set(stopwords.words('english') + list(punctuation))
    capitulo = {}

    id_livro = {}
    x = 0
    cur.execute("SELECT id_livro FROM livro where plataforma = 'gutenberg'")
    for row in cur:
        id_livro[x] = row[0]
        x += 1

    y = 0

    while y < len(id_livro):
    #while y <= 8:
        quantidade_sentencas = 4
        try:
            cli('', '', '', '', '', id_livro[y])
        except ValueError:
            capitulo[1] = load_etext(id_livro[y]).replace('”', '"').replace('“', '"')
            quantidade_sentencas = 8

        x = 1
        while x <= len(capitulo):
            sentencas = None
            palavras = None
            palavras_sem_stopwords = None
            frequencia = None
            palavra = None
            idx_sentencas_importantes = None

            sentencas = sent_tokenize(capitulo[x])
            palavras = word_tokenize(capitulo[x].lower())
            palavras_sem_stopwords = [palavra for palavra in palavras if palavra not in stopwords]
            frequencia = FreqDist(palavras_sem_stopwords)
            sentencas_importantes = defaultdict(int)

            for i, sentenca in enumerate(sentencas):
                for palavra in word_tokenize(sentenca.lower()):
                    if palavra in frequencia:
                        sentencas_importantes[i] += frequencia[palavra]

            idx_sentencas_importantes = nlargest(quantidade_sentencas, sentencas_importantes, sentencas_importantes.get)

            capitulo_nltk = ''
            for i in sorted(idx_sentencas_importantes):
                capitulo_nltk = capitulo_nltk + sentencas[i]

            resultado = analizaLivro(capitulo_nltk)
            analise = [resultado[2], resultado[3], resultado[4], resultado[5],resultado[6]]
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

            cur.execute("INSERT INTO analise (id_livro, numero_capt, sentimento, resultado, tristeza, raiva"
                        ", felicidade, medo, desgosto, top1_emocao, top2_emocao, plataforma) "                       
                        "VALUES(" + str(id_livro[y]) + ", " + str(x) + ", " + str(resultado[0]) + ","
                        " '" + resultado[1] + "', " + str(resultado[2]) + ", " + str(resultado[3]) + ","
                        " " + str(resultado[4]) + ", " + str(resultado[5]) + ", " + str(resultado[6]) + ","
                        " '" + top1_emocao + "', '" + top2_emocao + "', 'gutenberg')")
            cur.execute("commit")
            print('Livro {}  - Capitulo {} <=== Inserido'.format(id_livro[y], x))
            x += 1

        y += 1
connect.close()

