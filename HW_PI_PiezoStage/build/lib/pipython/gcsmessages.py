#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Process messages between GCSCommands and an interface."""

from logging import debug, error
from threading import Lock, Thread
import sys
from time import time
from pipython import gcserror
from pipython.gcserror import GCSError  # prevents cyclic import


def endofanswer(answer):
    """Return True if answer is complete in terms of GCS.
    @param answer : Answer to check as string.
    @return : True if last character is "\n" with no preceeding space.
    """
    return ' ' != answer[-2:-1] and '\n' == answer[-1:]


class GCSMessages(object):
    """Provide a GCS communication layer."""

    def __init__(self, interface):
        """Provide a GCS communication layer.
        @param interface : Instance of an object from pipython.interfaces.
        """
        debug('create an instance of GCSComm(interface=%s)', str(interface))
        self.__lock = Lock()
        self.__interface = interface
        self.__errcheck = True
        self.__embederr = False
        self.__timeout = 7000  # milliseconds
        self.__databuffer = {'size': 0, 'index': 0, 'data': [], 'error': None}

    def __str__(self):
        return 'GCSMessages(interface=%s)' % str(self.__interface)

    @property
    def connectionid(self):
        """Get ID of current connection as integer."""
        return self.__interface.connectionid

    @property
    def errcheck(self):
        """Get current error check setting, i.e. if the devices error state is always queried."""
        return self.__errcheck

    @errcheck.setter
    def errcheck(self, value):
        """Set error check property.
        @param value : True means that after each command the error is queried.
        """
        self.__errcheck = bool(value)
        debug('GCSMessages.errcheck set to %s', self.__errcheck)

    @property
    def embederr(self):
        """Get current embed error setting, i.e. if "ERR?" is embedded into a set command."""
        return self.__embederr

    @embederr.setter
    def embederr(self, value):
        """Set embed error property.
        @param value : True means that "ERR?" is embedded into a set command.
        """
        self.__embederr = bool(value)
        debug('GCSMessages.embederr set to %s', self.__embederr)

    @property
    def timeout(self):
        """Get current timeout setting in milliseconds."""
        return self.__timeout

    @timeout.setter
    def timeout(self, value):
        """Set timeout.
        @param value : Timeout in milliseconds as integer.
        """
        self.__timeout = int(value)
        debug('GCSMessages.timeout set to %d milliseconds', self.__timeout)

    @property
    def bufstate(self):
        """False if no buffered data is available. True if buffered data is ready to use.
        Float value 0..1 indicates read progress. To wait, use "while bufstate is not True".
        """
        if self.__databuffer['error']:
            raise self.__databuffer['error']  # Raising NoneType pylint: disable=E0702
        if not self.__databuffer['size']:
            bufstate = False
        elif self.__databuffer['size'] is True:
            bufstate = True
        else:
            bufstate = float(self.__databuffer['index']) / float(self.__databuffer['size'])
        return bufstate

    @property
    def bufdata(self):
        """Get buffered data as 2-dimensional list of float values."""
        debug('GCSMessages.bufdata: %d datasets', self.__databuffer['index'])
        return self.__databuffer['data']

    @property
    def locked(self):
        """Return True if instance is locked, i.e. is communicating with the device."""
        debug('GCSMessages.locked: %s', self.__lock.locked())
        return self.__lock.locked()

    def send(self, tosend):
        """Send 'tosend' to device and check for error.
        @param tosend : String to send to device, with or without trailing linefeed.
        """
        if self.__embederr and self.__errcheck:
            if len(tosend) > 1 and not tosend.endswith('\n'):
                tosend += '\n'
            tosend += 'ERR?\n'
        with self.__lock:
            self.__send(tosend)
            self.__checkerror(senderr=not self.__embederr)

    def read(self, tosend, gcsdata=0):
        """Send 'tosend' to device, read answer and check for error.
        @param tosend : String to send to device.
        @param gcsdata : Number of lines, if != 0 then GCS data will be read in background task.
        @return : Device answer as string.
        """
        gcsdata = None if gcsdata < 0 else gcsdata
        stopon = None
        if 0 != gcsdata:
            stopon = '# END_HEADER'
            self.__databuffer['data'] = []
            self.__databuffer['index'] = 0
            self.__databuffer['error'] = None
        with self.__lock:
            while self.__interface.answersize:
                self.__interface.getanswer(self.__interface.answersize)  # empty buffer
            self.__send(tosend)
            answer = self.__read(stopon)
            if 0 != gcsdata:
                splitpos = answer.upper().find(stopon)
                if splitpos < 0:
                    self.__send('ERR?\n')
                    err = int(self.__read(stopon=None).strip())
                    err = err or gcserror.E_1004_PI_UNEXPECTED_RESPONSE
                    raise GCSError(err, answer)
                stopon += ' \n'
                splitpos += len(stopon)
                strbuf = answer[splitpos:]
                answer = answer[:splitpos]
                self.__databuffer['size'] = gcsdata
                if stopon in answer.upper():  # "# END HEADER\n" will not start reading GCS data
                    self.__readgcsdata(strbuf)
            else:
                self.__checkerror()
        return answer

    def __send(self, tosend):
        """Send 'tosend' to device.
        @param tosend : String to send to device, with or without trailing linefeed.
        """
        if len(tosend) > 1 and not tosend.endswith('\n'):
            tosend += '\n'
        self.__interface.send(tosend)

    def __read(self, stopon):
        """Read answer from device until this ends with linefeed with no preceeding space.
        @param stopon: Addditional uppercase string that stops reading, too.
        @return : Received data as string.
        """
        timeout = time() + self.__timeout / 1000.
        chunks = []
        while True:
            if time() > timeout:
                raise GCSError(gcserror.E_7_COM_TIMEOUT)
            if self.__interface.answersize:
                timeout = time() + self.__timeout / 1000.
                received = self.__interface.getanswer(self.__interface.answersize)
                chunks.append(received)
                if endofanswer(chunks[-1]):
                    break
                if stopon and stopon in chunks[-1].upper():
                    break
        try:
            answer = ''.join(chunks)
        except TypeError:
            answer = b''.join(chunks)
        return answer

    def __readgcsdata(self, strbuf):
        """Start a background task to read out GCS data and save it in the instance.
        @param strbuf : String of already readout answer.
        """
        if not endofanswer(strbuf):
            strbuf += self.__read(stopon=' \n')
        numcolumns = len(strbuf.split('\n')[0].split())
        self.__databuffer['data'] = [[] for _ in range(numcolumns)]
        debug('GCSMessages: start background task to query GCS data')
        thread = Thread(target=self.__fillbuffer, args=(strbuf,))
        thread.start()

    def __fillbuffer(self, answer):
        """Read answers and save them as float values into the data buffer.
        An answerline with invalid data (non-number, missing column) will be skipped and error flag is set.
        @param answer : String of already readout answer.
        """
        numcolumns = len(self.__databuffer['data'])
        with self.__lock:
            while True:
                lines = answer.splitlines(True)  # keep line endings
                answer = ''
                for line in lines:
                    if '\n' not in line:
                        answer = line
                        break
                    try:
                        values = [float(x) for x in line.split()]
                        assert numcolumns == len(values)
                    except (AssertionError, ValueError):
                        exc = GCSError(gcserror.E_1004_PI_UNEXPECTED_RESPONSE, line)
                        self.__databuffer['error'] = exc
                        error('GCSMessages: GCSError: %s', exc)
                    else:
                        for i in range(numcolumns):
                            self.__databuffer['data'][i].append(values[i])
                    self.__databuffer['index'] += 1
                    if self.__endofdata(line):
                        debug('GCSMessages: end background task to query GCS data')
                        self.__databuffer['error'] = self.__checkerror(doraise=False)
                        self.__databuffer['size'] = True
                        return
                try:
                    answer += self.__read(stopon=' \n')
                except:  # No exception type(s) specified pylint: disable=W0702
                    exc = GCSError(gcserror.E_1090_PI_GCS_DATA_READ_ERROR, sys.exc_info()[1])
                    self.__databuffer['error'] = exc
                    error('GCSMessages: end background task with GCSError: %s', exc)
                    self.__databuffer['size'] = True
                    return

    def __endofdata(self, line):
        """Verify 'line' and return True if 'line' is last line of device answer.
        @param line : One answer line of device with trailing line feed character.
        @return : True if 'line' is last line of device answer.
        """
        if endofanswer(line) and self.__databuffer['index'] < self.__databuffer['size']:
            msg = '%s expected, %d received' % (self.__databuffer['size'], self.__databuffer['index'])
            exc = GCSError(gcserror.E_1088_PI_TOO_FEW_GCS_DATA, msg)
            self.__databuffer['error'] = exc
            error('GCSMessages: GCSError: %s', exc)
        if self.__databuffer['size'] and self.__databuffer['index'] > self.__databuffer['size']:
            msg = '%s expected, %d received' % (self.__databuffer['size'], self.__databuffer['index'])
            exc = GCSError(gcserror.E_1089_PI_TOO_MANY_GCS_DATA, msg)
            self.__databuffer['error'] = exc
            error('GCSMessages: GCSError: %s', exc)
        return endofanswer(line)

    def __checkerror(self, senderr=True, doraise=True):
        """Query error from device and raise GCSError exception.
        @param senderr : If True send "ERR?\n" to the device.
        @param doraise : If True an error is raised, else the GCS error number is returned.
        @return : If doraise is False the GCS exception if an error occured else None.
        """
        if not self.__errcheck:
            return 0
        if senderr:
            self.__send('ERR?\n')
        answer = self.__read(stopon=None)
        exc = None
        try:
            err = int(answer)
        except ValueError:
            exc = GCSError(gcserror.E_1004_PI_UNEXPECTED_RESPONSE, answer)
        else:
            if err:
                exc = GCSError(err)
        if exc and doraise:
            raise exc  # Raising NoneType while only classes or instances are allowed pylint: disable=E0702
        return exc
