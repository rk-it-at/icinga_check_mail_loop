#!/usr/bin/env python3
#
# -----------------------------------------------------------------------------
# Copyright (c) 2023 Martin Schobert, Pentagrid AG
#
# All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
#  ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
#  WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
#  ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
#  (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
#  LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
#  ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
#  SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
#  The views and conclusions contained in the software and documentation are those
#  of the authors and should not be interpreted as representing official policies,
#  either expressed or implied, of the project.
#
#  NON-MILITARY-USAGE CLAUSE
#  Redistribution and use in source and binary form for military use and
#  military research is not permitted. Infringement of these clauses may
#  result in publishing the source code of the utilizing applications and
#  libraries to the public. As this software is developed, tested and
#  reviewed by *international* volunteers, this clause shall not be refused
#  due to the matter of *national* security concerns.
# -----------------------------------------------------------------------------

import smtplib
import imaplib
import argparse
import uuid
import sys
import os
import ssl
import time
from email.mime.text import MIMEText
from enum import Enum
from typing import Optional


class MailFound(Enum):
	UNDEFINED = 0
	FOUND = 1
	FOUND_IN_SPAM = 2
	NOT_FOUND = 3


# global flags
debug_flag = False

# time to wait
delay = 10

# number of times to search for token
retries = 3


def debug(message: str) -> None:
	if debug_flag:
		print(message)


def email_create_message(mail_from: str, mail_to: str, _uuid: str) -> MIMEText:
	"""
	Create an E-mail.

	@param mail_from: The sender's E-mail address for the E-mail header.
	@param mail_to: The recipients E-mail address for the E-mail header.
	@param _uuid: Add this UUID as additional X-Icinga-Test-Id header.
	@return Function returns a MIMEText object.
	"""

	text = ("Dear Icinga Monitoring Plugin,\n\n"
			"I hope your overall health is at its best. Today I am writing you another e-mail. I'm afraid you will\n"
			"take note of this email, maybe read out one or two bon mot and delete this mail. Maybe this is the way\n"
			"of things and we cannot change anything. The main thing is that everything is fine. I will write to\n"
			"you again very soon.\n\n"
			"Greetings\n\n"
			"The sender\n")

	msg = MIMEText(text)

	msg["From"] = mail_from
	msg["To"] = mail_to
	msg["Subject"] = "Mail test"
	msg["X-Icinga-Test-Id"] = _uuid

	return msg


def smtp_connect(smtp_host: str, smtp_port: int, smtp_user: str, smtp_pass: str) -> smtplib.SMTP:
	"""
	Connect to an SMTPS server.

	@param smtp_host: The mail server host.
	@param smtp_port: The SMTP server port. Plaintext communication is not supported.
	@param smtp_user: The username for SMTP authentication.
	@param smtp_pass: The password for SMTP authentication.
	@return Function returns a smtplib.SMTP object that represents a server connection.
	"""

	if smtp_port == 587:
		server = smtplib.SMTP(smtp_host, smtp_port)
		server.starttls()
	else:
		server = smtplib.SMTP_SSL(smtp_host, smtp_port, context=ssl.create_default_context())

	debug(f"SMTP: Try to log in to {smtp_host} as: {smtp_user}")
	server.login(smtp_user, smtp_pass)
	debug(f"SMTP: Log in was successful.")

	return server


def imap_retrieve_mail(imap_host: str, imap_port: int, imap_user: str, imap_pass: str, imap_spambox: Optional[str],
					   expected_token: str, cleanup_flag: bool, search_body: bool) -> MailFound:
	"""
	Retrieve an e-mail from an IMAP account. Search the INBOX and the Spambox for a specific token value.
	Retry up to three times.

	@param imap_host: The mail server host.
	@param imap_port: The SMTP server port. STARTSSL or plaintext communication is not supported.
	@param imap_user: The username for SMTP authentication.
	@param imap_pass: The password for SMTP authentication.
	@param imap_spambox: The name of the spam mailbox, where the mail is also searched. Pass None to skip.
	@param expected_token: Lookup this token in a X-Icinga-Test-Id E-mail header.
	@param cleanup_flag: Remove mails from the IMAP account.
	@param search_body: Search token in email body instead of header.

	@return Function returns a MailFound status.
	"""

	# Establish IMAP connection
	server = imaplib.IMAP4_SSL(host=imap_host, port=imap_port, ssl_context=ssl.create_default_context())
	debug(f"IMAP: Try to log in to {imap_host} as: {imap_user}")
	server.login(imap_user, imap_pass)
	debug(f"IMAP: Log in was successful.")

	status = MailFound.NOT_FOUND

	# Check which mailboxes to lookup
	mailboxes = ["INBOX"]
	if imap_spambox:
		debug(f"IMAP: Will also check spambox \"{imap_spambox}\" as fallback.")
		mailboxes.append(imap_spambox)

	for i in range(0, retries):
		for mailbox in mailboxes:
			time.sleep(delay)
			status = imap_search_server(server, mailbox, expected_token, cleanup_flag, search_body)
			if status != MailFound.NOT_FOUND:
				server.logout()
				return status

	server.logout()
	return status


def imap_search_server(server: imaplib.IMAP4, mailbox: str, expected_token: str, cleanup_flag: bool, search_body: bool) -> MailFound:
	"""
	Lookup token on IMAP server.

	@param server: An imaplib.IMAP4 object that represents the sever connection.
	@param mailbox: Name of the mailbox, such as INBOX or Junk.
	@param expected_token: Lookup this token in a X-Icinga-Test-Id E-mail header.
	@param cleanup_flag: Remove mails from the IMAP account.
	@param search_body: Search token in email body instead of header.
	@return Function returns a MailFound status.
	"""

	class Email:
		def __init__(self, _data):
			self.data = _data.decode()
			self.header = "\r\n\r\n".join(self.data.split("\r\n\r\n")[0:1])
			self.body = "\r\n\r\n".join(self.data.split("\r\n\r\n")[2:])

	token_found = MailFound.NOT_FOUND
	token = ""

	debug(f"IMAP: Check mail in mailbox {mailbox}.")
	server.select(mailbox)

	typ, data = server.search(None, 'ALL')
	for num in data[0].split():

		num_str = num.decode('utf-8')

		typ, data = server.fetch(num, '(RFC822)')
		debug(f"IMAP: [{mailbox}]:{num_str} Check mail {num_str}.")
		email = Email(data[0][1])
		if not search_body:
			for line in email.header.splitlines():

				if line.startswith("X-Icinga-Test-Id"):
					token = line.split("X-Icinga-Test-Id: ")[1].strip()
					debug(f"IMAP: [{mailbox}]:{num_str} A token was found: {token}")
		else:
			for line in email.body.splitlines():

				if line.startswith("X-Icinga-Test-Id"):
					token = line.split("X-Icinga-Test-Id: ")[1].strip()
					debug(f"IMAP: [{mailbox}]:{num_str} A token was found: {token}")

		if token == expected_token:
			debug(f"IMAP: [{mailbox}]:{num_str} Expected token {token} found in {mailbox}.")
			if mailbox == "INBOX":
				token_found = MailFound.FOUND
				if cleanup_flag:
					debug(f"IMAP: [{mailbox}]:{num_str} Mark mail {num_str} as deleted.")
					server.store(num, '+FLAGS', '\\Deleted')
			else:
				token_found = MailFound.FOUND_IN_SPAM
				if cleanup_flag:
					debug(f"IMAP: [{mailbox}]:{num_str} Mark mail {num_str} as deleted.")
					server.store(num, '+FLAGS', '\\Deleted')
			break
		else:
			debug(f"IMAP: [{mailbox}]:{num_str} Expected token was not found in this e-mail.")

	if cleanup_flag:
		server.expunge()
	server.close()

	return token_found


def main():
	global debug_flag, delay, retries

	parser = argparse.ArgumentParser(description='Check SMTP to IMAPS health status.')

	parser.add_argument('--debug', action='store_true', help="Enable verbose output.")

	parser.add_argument('--mail-from', metavar='MAIL_FROM', help='Mail: Use this sender address.', required=True)
	parser.add_argument('--mail-to', metavar='MAIL_TO', help='Mail: Use this recipient address.', required=True)

	parser.add_argument('--smtp-host', metavar='SMTP_HOST', help='SMTP: Hostname of the SMTP server.', required=True)
	parser.add_argument('--smtp-port', metavar='SMTP_PORT',
						help='SMTP: Deliver mail via this port. STARTSSL or plaintext communication is not supported.',
						type=int, default=465)
	parser.add_argument('--smtp-user', metavar='SMTP_USER', help='SMTP: User name for login.', required=True)
	parser.add_argument('--smtp-pass', metavar='SMTP_PASS',
						help='SMTP: Passwort for login. Alternatively, set environment variable SMTP_PASS.',
						default=os.getenv("SMTP_PASS"))

	parser.add_argument('--imap-host', metavar='IMAP_HOST', help='IMAP: Hostname of the SMTP server.', required=True)
	parser.add_argument('--imap-port', metavar='IMAP_PORT', help='IMAP: Deliver mail via this port.', type=int,
						default=993)
	parser.add_argument('--imap-user', metavar='IMAP_USER', help='IMAP: User name for login.', required=True)
	parser.add_argument('--imap-pass', metavar='IMAP_PASS',
						help='IMAP: Passwort for login. Alternatively, set environment variable IMAP_PASS.',
						default=os.getenv("IMAP_PASS"))
	parser.add_argument('--imap-spam', metavar='IMAP_SPAM', help='IMAP: Name of the spam box.')
	parser.add_argument('--imap-body', action='store_true', help='IMAP: Search token in body instead of header.')
	parser.add_argument('--imap-cleanup', action='store_true', help="Delete processed mails on the IMAP account.")

	parser.add_argument('--delay', metavar='SECONDS', help=f"Delay between sending and retrieving (default {delay} s).",
						type=int, default=delay)
	parser.add_argument('--retries', metavar='RETRIES', help=f"Token search attempts (default {retries}).",
						type=int, default=retries)
	args = parser.parse_args()

	debug_flag = args.debug
	delay = args.delay
	retries = args.retries
	
	_uuid = str(uuid.uuid4())
	email = email_create_message(args.mail_from, args.mail_to, _uuid)
	smtp_server = smtp_connect(args.smtp_host, args.smtp_port, args.smtp_user, args.smtp_pass)
	smtp_server.sendmail(args.mail_from, args.mail_to, email.as_string())
	debug(f"SMTP: Mail sent with ID {_uuid}.")

	status = imap_retrieve_mail(args.imap_host, args.imap_port, args.imap_user, args.imap_pass, args.imap_spam, _uuid,
								args.imap_cleanup, args.imap_body)

	if status == MailFound.FOUND:
		print("OK")
		return 0
	elif status == MailFound.FOUND_IN_SPAM:
		debug("WARNING - Message found in Spam folder")
		return 1
	elif status == MailFound.NOT_FOUND:
		print("ERROR - Message not found")
		return 2
	else:
		print("UNDEFINED - Undefined state")
		return 3


if __name__ == "__main__":
	sys.exit(main())
