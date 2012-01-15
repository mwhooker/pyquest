class Counter(object):

    def __init__(self):
        self.count = 0

    def inc(self):
        self.count += 1

    def flush(self):
        tmp = self.count
        self.count = 0
        return tmp
