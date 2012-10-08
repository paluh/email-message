email-message
=============

Email message wrapper ripped from django.

It doesn't depend on any global smtp `connection` or settings - `send_message` function takes `connection` as parameter:

    >>> import email_message
    >>> c = email_message.get_connection('smpt.example.com', 587, username='spammer', password='spam', use_tsl=True)
    >>> m = email_message.EmailMultiAlternatives(subject='spam', body='spam spam spam', from_email='spammer@example.com', to=['recipient@example.com'],
    ...                                          alternatives=[('<html><body><ul><li>spam</li><li>spam</li></ul></body></html>', 'text/html')])
    >>> email_message.send_message(m, c)

For more details look into django documentation (and into `email_message.__all__` ;-)).
