from gutenberg.acquire import load_etext
from pyunpack import Archive
import os
import codecs
import sys
import shutil

i = 1
id_livro = 101
book_path = 'Textos/' + str(id_livro) + '.txt'

#Mover o arquivo para a pasta de Textos
src = str(id_livro)+"-chapters"
dst = "Textos/"


def filecount(dir_name):
    # return the number of files in directory dir_name
    try:
        return len([f for f in os.listdir(dir_name) if os.path.isfile(os.path.join(dir_name, f))])
    except Exception as e:
        return None


if __name__ == '__main__':
    text = load_etext(id_livro).replace('”', '"').replace('“', '"')

    with codecs.open('Textos/' + str(id_livro) + '.txt', 'w+', encoding='utf8') as f:
        f.write(text)
        f.close()

    pathname = os.path.dirname(sys.argv[0])
    fullpath = pathname + '/chapterize-master/chapterize'

    os.system('python "' + fullpath + '"/chapterize.py ' '"' + book_path + '"')

    #shutil.move(src, dst)

