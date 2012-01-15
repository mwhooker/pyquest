class GameLoop(object):

    def __init__(self, target_tps):

        self.target_tps = 60
        self.scheduler = scheduler(time.time, time.sleep)

    def repeat(self, f, n=1, until=None):
        """repeat f every n ticks."""

        def _run():
            f()
            if not callable(until) or not until():
                self.repeat(f, n, until)

        self.schedule(_run, n)

    def schedule(self, f, n=1):
        return self.scheduler.enter(n / self.target_tps, 1, f, ())

    def cancel(self, event):
        self.scheduler.cancel(event)

    def run(self):
        self.scheduler.run()
