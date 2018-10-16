from __future__ import unicode_literals

from email import charset as Charset, encoders as Encoders
from email.generator import Generator
from email.header import Header
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, getaddresses, formataddr, parseaddr
from io import BytesIO
import mimetypes
import os
import random
import socket
import smtplib
import time

__version__ = '1.0'


__all__ = ['get_connection', 'send_message', 'EmailMessage', 'EmailMultiAlternatives']


_dns = None
def get_dns():
    global _dns
    if _dns is None:
        _dns = socket.getfqdn()

# Don't BASE64-encode UTF-8 messages so that we avoid unwanted attention from
# some spam filters.
Charset.add_charset('utf-8', Charset.SHORTEST, None, 'utf-8')

# Default MIME type to use on attachments (if it is not explicitly given
# and cannot be guessed).
DEFAULT_ATTACHMENT_MIME_TYPE = 'application/octet-stream'

class BadHeaderError(ValueError):
    pass


# Copied from Python standard library, with the following modifications:
# * Used cached hostname for performance.
# * Added try/except to support lack of getpid() in Jython (#5496).
def make_msgid(idstring=None):
    """Returns a string suitable for RFC 2822 compliant Message-ID, e.g:

    <20020201195627.33539.96671@nightshade.la.mastaler.com>

    Optional idstring if given is a string used to strengthen the
    uniqueness of the message id.
    """
    timeval = time.time()
    utcdate = time.strftime('%Y%m%d%H%M%S', time.gmtime(timeval))
    try:
        pid = os.getpid()
    except AttributeError:
        # No getpid() in Jython, for example.
        pid = 1
    randint = random.randrange(100000)
    if idstring is None:
        idstring = ''
    else:
        idstring = '.' + idstring
    idhost = get_dns()
    msgid = '<%s.%s.%s%s@%s>' % (utcdate, pid, randint, idstring, idhost)
    return msgid


# Header names that contain structured address data (RFC #5322)
ADDRESS_HEADERS = set([
    'from',
    'sender',
    'reply-to',
    'to',
    'cc',
    'bcc',
    'resent-from',
    'resent-sender',
    'resent-to',
    'resent-cc',
    'resent-bcc',
])


def forbid_multi_line_headers(name, val, encoding='utf-8'):
    """Forbids multi-line headers, to prevent header injection."""
    if '\n' in val or '\r' in val:
        raise BadHeaderError("Header values can't contain newlines (got %r for header %r)" % (val, name))
    try:
        val = val.encode('ascii')
    except UnicodeEncodeError:
        if name.lower() in ADDRESS_HEADERS:
            val = ', '.join(sanitize_address(addr, encoding)
                for addr in getaddresses((val,)))
        else:
            val = str(Header(val, encoding))
    else:
        if name.lower() == 'subject':
            val = Header(val)
    return name.encode('utf-8'), val


def sanitize_address(addr, encoding):
    if isinstance(addr, basestring):
        addr = parseaddr(addr)
    nm, addr = addr
    nm = str(Header(nm, encoding))
    try:
        addr = addr.encode('ascii')
    except UnicodeEncodeError:  # IDN
        if '@' in addr:
            localpart, domain = addr.split('@', 1)
            localpart = str(Header(localpart, encoding))
            domain = domain.encode('idna')
            addr = '@'.join([localpart, domain])
        else:
            addr = str(Header(addr, encoding))
    return formataddr((nm, addr))


class SafeMIMEText(MIMEText):

    def __init__(self, text, subtype, charset):
        self.encoding = charset
        MIMEText.__init__(self, text, subtype, charset)

    def __setitem__(self, name, val):
        name, val = forbid_multi_line_headers(name, val, self.encoding)
        MIMEText.__setitem__(self, name, val)

    def as_string(self, unixfrom=False):
        """Return the entire formatted message as a string.
        Optional `unixfrom' when True, means include the Unix From_ envelope
        header.

        This overrides the default as_string() implementation to not mangle
        lines that begin with 'From '. See bug #13433 for details.
        """
        fp = BytesIO()
        g = Generator(fp, mangle_from_ = False)
        g.flatten(self, unixfrom=unixfrom)
        return fp.getvalue()


class SafeMIMEMultipart(MIMEMultipart):

    def __init__(self, _subtype='mixed', boundary=None, _subparts=None, encoding=None, **_params):
        self.encoding = encoding
        MIMEMultipart.__init__(self, _subtype, boundary, _subparts, **_params)

    def __setitem__(self, name, val):
        name, val = forbid_multi_line_headers(name, val, self.encoding)
        MIMEMultipart.__setitem__(self, name, val)

    def as_string(self, unixfrom=False):
        """Return the entire formatted message as a string.
        Optional `unixfrom' when True, means include the Unix From_ envelope
        header.

        This overrides the default as_string() implementation to not mangle
        lines that begin with 'From '. See bug #13433 for details.
        """
        fp = BytesIO()
        g = Generator(fp, mangle_from_ = False)
        g.flatten(self, unixfrom=unixfrom)
        return fp.getvalue()


class EmailMessage(object):
    """
    A container for email information.
    """
    content_subtype = 'plain'
    mixed_subtype = 'mixed'
    encoding = None     # None => use settings default

    def __init__(self, subject='', body='', from_email=None, to=None, bcc=None,
                 attachments=None, headers=None, cc=None, encoding='utf-8'):
        self.subject = subject
        self.body = body
        self.from_email = from_email
        self.to = to or []
        self.bcc = bcc or []
        self.attachments = attachments or []
        self.extra_headers = headers or {}
        self.cc = cc or []
        self.encoding = encoding

    def message(self):
        msg = SafeMIMEText(self.body.encode(self.encoding),
                           self.content_subtype, self.encoding)
        msg = self._create_message(msg)
        msg['Subject'] = self.subject
        msg['From'] = self.extra_headers.get('From', self.from_email)
        msg['To'] = self.extra_headers.get('To', ', '.join(self.to))
        if self.cc:
            msg['Cc'] = ', '.join(self.cc)

        # Email header names are case-insensitive (RFC 2045), so we have to
        # accommodate that when doing comparisons.
        header_names = [key.lower() for key in self.extra_headers]
        if 'date' not in header_names:
            msg['Date'] = formatdate()
        if 'message-id' not in header_names:
            msg['Message-ID'] = make_msgid()
        for name, value in self.extra_headers.items():
            if name.lower() in ('from', 'to'):  # From and To are already handled
                continue
            msg[name] = value
        return msg

    def recipients(self):
        return self.to + self.cc + self.bcc

    def attach(self, filename=None, content=None, mimetype=None):
        """
        Attaches a file with the given filename and content. The filename can
        be omitted and the mimetype is guessed, if not provided.

        If the first parameter is a MIMEBase subclass it is inserted directly
        into the resulting message attachments.
        """
        if isinstance(filename, MIMEBase):
            assert content == mimetype == None
            self.attachments.append(filename)
        else:
            assert content is not None
            self.attachments.append((filename, content, mimetype))

    def attach_file(self, path, mimetype=None):
        """Attaches a file from the filesystem."""
        filename = os.path.basename(path)
        with open(path, 'rb') as f:
            content = f.read()
        self.attach(filename, content, mimetype)

    def _create_message(self, msg):
        return self._create_attachments(msg)

    def _create_attachments(self, msg):
        if self.attachments:
            body_msg = msg
            msg = SafeMIMEMultipart(_subtype=self.mixed_subtype, encoding=self.encoding)
            if self.body:
                msg.attach(body_msg)
            for attachment in self.attachments:
                if isinstance(attachment, MIMEBase):
                    msg.attach(attachment)
                else:
                    msg.attach(self._create_attachment(*attachment))
        return msg

    def _create_mime_attachment(self, content, mimetype):
        """
        Converts the content, mimetype pair into a MIME attachment object.
        """
        basetype, subtype = mimetype.split('/', 1)
        if basetype == 'text':
            attachment = SafeMIMEText(content.encode(self.encoding), subtype, self.encoding)
        else:
            # Encode non-text attachments with base64.
            attachment = MIMEBase(basetype, subtype)
            attachment.set_payload(content)
            Encoders.encode_base64(attachment)
        return attachment

    def _create_attachment(self, filename, content, mimetype=None):
        """
        Converts the filename, content, mimetype triple into a MIME attachment
        object.
        """
        if mimetype is None:
            mimetype, _ = mimetypes.guess_type(filename)
            if mimetype is None:
                mimetype = DEFAULT_ATTACHMENT_MIME_TYPE
        attachment = self._create_mime_attachment(content, mimetype)
        if filename:
            try:
                filename = filename.encode('ascii')
            except UnicodeEncodeError:
                filename = ('utf-8', '', filename.encode('utf-8'))
            attachment.add_header('Content-Disposition', 'attachment',
                                  filename=filename)
        return attachment


class EmailMultiAlternatives(EmailMessage):
    """
    A version of EmailMessage that makes it easy to send multipart/alternative
    messages. For example, including text and HTML versions of the text is
    made easier.
    """
    alternative_subtype = 'alternative'

    def __init__(self, *args, **kwargs):
        """
        Initialize a single email message (which can be sent to multiple
        recipients).

        All strings used to create the message can be unicode strings (or UTF-8
        bytestrings). The SafeMIMEText class will handle any necessary encoding
        conversions.
        """
        self.alternatives = kwargs.pop('alternatives', [])
        super(EmailMultiAlternatives, self).__init__(*args, **kwargs)

    def attach_alternative(self, content, mimetype):
        self.alternatives.append((content, mimetype))

    def _create_message(self, msg):
        return self._create_attachments(self._create_alternatives(msg))

    def _create_alternatives(self, msg):
        if self.alternatives:
            body_msg = msg
            msg = SafeMIMEMultipart(_subtype=self.alternative_subtype, encoding=self.encoding)
            if self.body:
                msg.attach(body_msg)
            for alternative in self.alternatives:
                msg.attach(self._create_mime_attachment(*alternative))
        return msg

PROTOCOL = namedtuple('Protocol', ['SSL', 'TLS', 'PLAIN'])('SSL', 'TLS', 'PLAIN')

def get_connection(host, port, username=None, password=None, protocol=PROTOCOL.PLAIN):
    if protocol == PROTOCOL.SSL:
        connection = smtplib.SMTP_SSL(host, port)
    else:
        connection = smtplib.SMTP(host, port, local_hostname=get_dns())
        if protocol == PROTOCOL.TLS:
            connection.ehlo()
            connection.starttls()
            connection.ehlo()

    if username and password:
        connection.login(username, password)
    return connection

def close_connection(connection):
    try:
        connection.quit()
    except socket.sslerror:
        # This happens when calling quit() on a TLS connection
        # sometimes.
        connection.close()

def send_message(email_message, connection):
    from_email = sanitize_address(email_message.from_email, email_message.encoding)
    recipients = [sanitize_address(addr, email_message.encoding)
                      for addr in email_message.recipients()]
    connection.sendmail(from_email, recipients,
            email_message.message().as_string())

