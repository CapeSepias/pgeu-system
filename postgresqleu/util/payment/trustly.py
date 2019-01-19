from django.conf import settings
from django import forms
from django.core.exceptions import ValidationError

from postgresqleu.invoices.models import Invoice
from postgresqleu.invoices.backendforms import BackendInvoicePaymentMethodForm
from postgresqleu.accounting.util import get_account_choices
from postgresqleu.util.forms import CharToArrayField

from postgresqleu.trustlypayment.models import TrustlyTransaction, TrustlyLog

from postgresqleu.trustlypayment.util import Trustly
from postgresqleu.trustlypayment.api import TrustlyException

from . import BasePayment

import collections
from Crypto.PublicKey import RSA


def validate_pem_public_key(value):
    try:
        k = RSA.importKey(value)
        if k.has_private():
            raise ValidationError("This should be a public key, but contains a private key")
    except ValidationError:
        raise
    except Exception as e:
        raise ValidationError("Could not validate public key: {}".format(e))


def validate_pem_private_key(value):
    try:
        k = RSA.importKey(value)
        if not k.has_private():
            raise ValidationError("This should be a private key, but doesn't contain one")
    except ValidationError:
        raise
    except Exception as e:
        raise ValidationError("Could not validate private key: {}".format(e))


def validate_country_list(value):
    if len(value) == 0:
        raise ValidationError("At least one country must be specified")
    dupes = [c for c, num in collections.Counter(value).items() if num > 1]
    if dupes:
        if len(dupes) == 1:
            raise ValidationError("Country {} specified more than once!".format(dupes[0]))
        else:
            raise ValidationError("Countries {} specified more than once!".format(", ".join(dupes)))


class BackendTrustlyPaymentForm(BackendInvoicePaymentMethodForm):
    test = forms.BooleanField(required=False)
    user = forms.CharField(required=True)
    password = forms.CharField(required=True, widget=forms.widgets.PasswordInput(render_value=True))
    hold_notifications = forms.BooleanField(required=False)

    notification_receiver = forms.EmailField(required=True)
    countries = CharToArrayField(required=True, validators=[validate_country_list, ],
                                 label="Available countries",
                                 help_text="Comma separate list of countries available in")

    public_key = forms.CharField(required=True, widget=forms.widgets.Textarea, validators=[validate_pem_public_key, ])
    private_key = forms.CharField(required=True, widget=forms.widgets.Textarea, validators=[validate_pem_private_key, ])

    accounting_income = forms.ChoiceField(required=True, choices=get_account_choices,
                                          label="Income account")

    config_fields = ['user', 'test', 'password', 'hold_notifications',
                     'notification_receiver', 'countries',
                     'public_key', 'private_key',
                     'accounting_income', ]
    config_fieldsets = [
        {
            'id': 'trustly',
            'legend': 'Trustly',
            'fields': ['user', 'test', 'password', 'hold_notifications', ],
        },
        {
            'id': 'integration',
            'legend': 'Integration',
            'fields': ['notification_receiver', 'countries', ],
        },
        {
            'id': 'keys',
            'legend': 'Keys',
            'fields': ['public_key', 'private_key', ],
        },
        {
            'id': 'accounting',
            'legend': 'Accounting',
            'fields': ['accounting_income', ],
        }
    ]


class TrustlyPayment(BasePayment):
    backend_form_class = BackendTrustlyPaymentForm

    @property
    def description(self):
        return """
Pay directly using online banking. Currently supported with most banks in {0}.
""".format(', '.join(self.config('countries')))

    def get_apibase(self):
        return self.config('test') and 'https://test.trustly.com/api/1' or 'https://api.trustly.com/api/1'

    def build_payment_url(self, invoicestr, invoiceamount, invoiceid, returnurl=None):
        i = Invoice.objects.get(pk=invoiceid)
        return '/invoices/trustlypay/{0}/{1}/{2}/'.format(self.id, invoiceid, i.recipient_secret)

    def payment_fees(self, invoice):
        # For now, we always get our Trustly transactions for free...
        return 0

    def autorefund(self, refund):
        try:
            trans = TrustlyTransaction.objects.get(invoiceid=refund.invoice.id)
        except TrustlyTransaction.DoesNotExist:
            raise Exception("Transaction matching invoice not found")

        t = Trustly(self)
        try:
            t.refund(trans.orderid, refund.fullamount)
        except TrustlyException as e:
            TrustlyLog(message='Refund API failed: {0}'.format(e), error=True).save()
            return False

        # Will raise exception if something goes wrong
        refund.payment_reference = trans.orderid

        return True

    def used_method_details(self, invoice):
        # Bank transfers don't need any extra information
        return "Trustly"
