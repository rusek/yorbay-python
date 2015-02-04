import codecs


class Loader(object):
    def load_source(self, path):
        raise NotImplementedError


class FsLoader(Loader):
    def load_source(self, path):
        with codecs.open(path, encoding='UTF-8') as f:
            return f.read()


default_loader = FsLoader()
