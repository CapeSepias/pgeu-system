#!/usr/bin/env python
#
# Expire waitlist offers that have expired, so others can get the
# seats.
#
# Copyright (C) 2015, PostgreSQL Europe
#

import os
import sys
from datetime import datetime

# Set up to run in django environment
from django.core.management import setup_environ
sys.path.append(os.path.join(os.path.abspath(os.path.dirname(sys.argv[0])), '../../postgresqleu'))
import settings
setup_environ(settings)

from django.db import transaction, connection
from django.template import Context
from django.template.loader import get_template

from postgresqleu.mailqueue.util import send_simple_mail

from postgresqleu.confreg.models import RegistrationWaitlistEntry, RegistrationWaitlistHistory

if __name__ == "__main__":
	with transaction.commit_on_success():
		# Any entries that actually have an invoice will be canceled by the invoice
		# system, as the expiry time of the invoice is set synchronized. In this
		# run, we only care about offers that have not been picked up at all.
		wlentries = RegistrationWaitlistEntry.objects.filter(registration__payconfirmedat__isnull=True, registration__invoice__isnull=True, offerexpires__lt=datetime.now())

		template = get_template('confreg/mail/waitlist_expired.txt')

		for w in wlentries:
			reg = w.registration

			# Create a history entry so we know exactly when it happened
			RegistrationWaitlistHistory(waitlist=w,
										text="Offer expired at {0}".format(w.offerexpires)).save()

			# Notify conference organizers
			send_simple_mail(reg.conference.contactaddr,
							 reg.conference.contactaddr,
								 'Waitlist expired',
								 u'User {0} {1} <{2}> did not complete the registration before the waitlist offer expired.'.format(reg.firstname, reg.lastname, reg.email),
								 sendername=reg.conference.conferencename)

			# Also send an email to the user
			send_simple_mail(reg.conference.contactaddr,
							 reg.email,
							 'Your waitlist offer for {0}'.format(reg.conference.conferencename),
							 template.render(Context({
								 'conference': reg.conference,
								 'reg': reg,
								 'offerexpires': w.offerexpires,
								 'SITEBASE': settings.SITEBASE_SSL,
								 })),
							 sendername = reg.conference.conferencename,
							 receivername = "{0} {1}".format(reg.firstname, reg.lastname),
							 )

			# Now actually expire the offer
			w.offeredon = None
			w.offerexpires = None
			w.save()

	connection.close()
