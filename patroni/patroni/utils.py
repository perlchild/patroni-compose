import datetime
import os
import random
import re
import signal
import sys
import time

from patroni.exceptions import PatroniException

ignore_sigterm = False
interrupted_sleep = False
reap_children = False

_DATE_TIME_RE = re.compile(r'''^
(?P<year>\d{4})\-(?P<month>\d{2})\-(?P<day>\d{2})  # date
T
(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})\.(?P<microsecond>\d{6})  # time
\d*Z$''', re.X)


def parse_datetime(time_str):
    """
    >>> parse_datetime('2015-06-10T12:56:30.552539016Z')
    datetime.datetime(2015, 6, 10, 12, 56, 30, 552539)
    >>> parse_datetime('2015-06-10 12:56:30.552539016Z')
    """
    m = _DATE_TIME_RE.match(time_str)
    if not m:
        return None
    p = dict((n, int(m.group(n))) for n in 'year month day hour minute second microsecond'.split(' '))
    return datetime.datetime(**p)


def calculate_ttl(expiration):
    """
    >>> calculate_ttl(None)
    >>> calculate_ttl('2015-06-10 12:56:30.552539016Z')
    >>> calculate_ttl('2015-06-10T12:56:30.552539016Z') < 0
    True
    """
    if not expiration:
        return None
    expiration = parse_datetime(expiration)
    if not expiration:
        return None
    now = datetime.datetime.utcnow()
    return int((expiration - now).total_seconds())


def sigterm_handler(signo, stack_frame):
    global ignore_sigterm
    if not ignore_sigterm:
        ignore_sigterm = True
        sys.exit()


def sigchld_handler(signo, stack_frame):
    global interrupted_sleep, reap_children
    reap_children = interrupted_sleep = True


def sleep(interval):
    global interrupted_sleep
    current_time = time.time()
    end_time = current_time + interval
    while current_time < end_time:
        interrupted_sleep = False
        time.sleep(end_time - current_time)
        if not interrupted_sleep:  # we will ignore only sigchld
            break
        current_time = time.time()
    interrupted_sleep = False


def setup_signal_handlers():
    signal.signal(signal.SIGTERM, sigterm_handler)
    signal.signal(signal.SIGCHLD, sigchld_handler)


def reap_children():
    global reap_children
    if reap_children:
        try:
            while True:
                ret = os.waitpid(-1, os.WNOHANG)
                if ret == (0, 0):
                    break
        except OSError:
            pass
        finally:
            reap_children = False


class RetryFailedError(PatroniException):

    """Raised when retrying an operation ultimately failed, after retrying the maximum number of attempts."""


class Retry:

    """Helper for retrying a method in the face of retry-able exceptions"""

    def __init__(self, max_tries=1, delay=0.1, backoff=2, max_jitter=0.8, max_delay=3600,
                 sleep_func=sleep, deadline=None, retry_exceptions=PatroniException):
        """Create a :class:`Retry` instance for retrying function calls

        :param max_tries: How many times to retry the command. -1 means infinite tries.
        :param delay: Initial delay between retry attempts.
        :param backoff: Backoff multiplier between retry attempts. Defaults to 2 for exponential backoff.
        :param max_jitter: Additional max jitter period to wait between retry attempts to avoid slamming the server.
        :param max_delay: Maximum delay in seconds, regardless of other backoff settings. Defaults to one hour.
        :param retry_exceptions: single exception or tuple"""

        self.max_tries = max_tries
        self.delay = delay
        self.backoff = backoff
        self.max_jitter = int(max_jitter * 100)
        self.max_delay = float(max_delay)
        self._attempts = 0
        self._cur_delay = delay
        self.deadline = deadline
        self._cur_stoptime = None
        self.sleep_func = sleep_func
        self.retry_exceptions = retry_exceptions

    def reset(self):
        """Reset the attempt counter"""
        self._attempts = 0
        self._cur_delay = self.delay
        self._cur_stoptime = None

    def copy(self):
        """Return a clone of this retry manager"""
        return Retry(max_tries=self.max_tries, delay=self.delay, backoff=self.backoff,
                     max_jitter=self.max_jitter / 100.0, max_delay=self.max_delay, sleep_func=self.sleep_func,
                     deadline=self.deadline, retry_exceptions=self.retry_exceptions)

    def __call__(self, func, *args, **kwargs):
        """Call a function with arguments until it completes without throwing a `retry_exceptions`

        :param func: Function to call
        :param args: Positional arguments to call the function with
        :params kwargs: Keyword arguments to call the function with

        The function will be called until it doesn't throw one of the retryable exceptions"""
        self.reset()

        while True:
            try:
                if self.deadline is not None and self._cur_stoptime is None:
                    self._cur_stoptime = time.time() + self.deadline
                return func(*args, **kwargs)
            except self.retry_exceptions:
                # Note: max_tries == -1 means infinite tries.
                if self._attempts == self.max_tries:
                    raise RetryFailedError("Too many retry attempts")
                self._attempts += 1
                sleeptime = self._cur_delay + (random.randint(0, self.max_jitter) / 100.0)

                if self._cur_stoptime is not None and time.time() + sleeptime >= self._cur_stoptime:
                    raise RetryFailedError("Exceeded retry deadline")
                else:
                    self.sleep_func(sleeptime)
                self._cur_delay = min(self._cur_delay * self.backoff, self.max_delay)
