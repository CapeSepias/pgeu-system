from django.conf import settings
from django import forms

from urllib.parse import urlencode

import re

from postgresqleu.paypal.models import TransactionInfo
from postgresqleu.paypal.util import PaypalAPI
from postgresqleu.invoices.backendforms import BackendInvoicePaymentMethodForm
from postgresqleu.accounting.util import get_account_choices

from . import BasePayment


class BackendPaypalForm(BackendInvoicePaymentMethodForm):
    sandbox = forms.BooleanField(required=False, help_text="Use testing sandbox")
    email = forms.EmailField(required=True, label="Paypal account email")
    apiuser = forms.CharField(required=True, label="API user",
                              help_text="Settings -> My Selling Tools -> API access -> Manage NVP API Credentials")
    apipassword = forms.CharField(required=True, label="API user password", widget=forms.widgets.PasswordInput(render_value=True),
                                  help_text="Settings -> My Selling Tools -> API access -> Manage NVP API Credentials")
    pdt_token = forms.CharField(required=True, label="PDT token", widget=forms.widgets.PasswordInput(render_value=True),
                                help_text="Settings -> My Selling Tools -> Website preferences -> Payment data transfer")
    signature = forms.CharField(required=True, label="API User signature", widget=forms.widgets.PasswordInput(render_value=True),
                                help_text="Settings -> My Selling Tools -> API access -> Manage NVP API Credentials")

    donation_text = forms.CharField(required=True,
                                    help_text="Payments with this text will be auto-matched as donations")
    report_receiver = forms.EmailField(required=True)
    accounting_income = forms.ChoiceField(required=True, choices=get_account_choices,
                                          label="Income account")
    accounting_fee = forms.ChoiceField(required=True, choices=get_account_choices,
                                       label="Fee account")
    accounting_transfer = forms.ChoiceField(required=True, choices=get_account_choices,
                                            label="Transfer account",
                                            help_text="Account that transfers from paypal are made to")

    config_fields = ['sandbox', 'email', 'apiuser', 'apipassword', 'pdt_token',
                     'signature', 'donation_text', 'report_receiver',
                     'accounting_income', 'accounting_fee', 'accounting_transfer']
    config_fieldsets = [
        {
            'id': 'paypal',
            'legend': 'Paypal',
            'fields': ['email', 'sandbox', 'apiuser', 'apipassword', 'signature',
                       'pdt_token'],
        },
        {
            'id': 'integration',
            'legend': 'Integration',
            'fields': ['report_receiver', 'donation_text', ],
        },
        {
            'id': 'accounting',
            'legend': 'Accounting',
            'fields': ['accounting_income', 'accounting_fee', 'accounting_transfer'],
        }
    ]


class Paypal(BasePayment):
    backend_form_class = BackendPaypalForm
    description = """
Pay using Paypal. You can use this both
to pay from your Paypal balance if you have a Paypal account, or you can
use it to pay with any credit card supported by Paypal (Visa, Mastercard, American Express).
In most countries, you do not need a Paypal account if you choose to pay
with credit card. However, we do recommend using the payment method called
"Credit card" instead of Paypal if you are paying with a credit card, as it has
lower fees.
"""

    PAYPAL_COMMON = {
        'lc': 'GB',
        'currency_code': settings.CURRENCY_ABBREV,
        'button_subtype': 'services',
        'no_note': '1',
        'no_shipping': '1',
        'bn': 'PP-BuyNowBF:btn_buynowCC_LG.gif-NonHosted',
        'charset': 'utf-8',
        }

    def get_baseurl(self):
        if self.config('sandbox'):
            return 'https://www.sandbox.paypal.com/cgi-bin/webscr'
        return 'https://www.paypal.com/cgi-bin/webscr'

    def build_payment_url(self, invoicestr, invoiceamount, invoiceid, returnurl=None):
        param = self.PAYPAL_COMMON
        param.update({
            'business': self.config('email'),
            'cmd': '_xclick',
            'item_name': invoicestr.encode('utf-8'),
            'amount': '%.2f' % invoiceamount,
            'invoice': invoiceid,
            'return': '%s/p/paypal_return/%s/' % (settings.SITEBASE, self.id),
            })
        if returnurl:
            # If the user cancels, send back to specific URL, instead of
            # the invoice url.
            param['cancel_return'] = returnurl
        return "%s?%s" % (
            self.get_baseurl(),
            urlencode(param))

    _re_paypal = re.compile('^Paypal id ([A-Z0-9]+), ')

    def _find_invoice_transaction(self, invoice):
        m = self._re_paypal.match(invoice.paymentdetails)
        if m:
            try:
                return (TransactionInfo.objects.get(paypaltransid=m.groups(1)[0]), None)
            except TransactionInfo.DoesNotExist:
                return (None, "not found")
        else:
            return (None, "unknown format")

    def payment_fees(self, invoice):
        (trans, reason) = self._find_invoice_transaction(invoice)
        if not trans:
            return reason

        return trans.fee

    def autorefund(self, refund):
        (trans, reason) = self._find_invoice_transaction(refund.invoice)
        if not trans:
            raise Exception(reason)

        api = PaypalAPI(self)
        refund.payment_reference = api.refund_transaction(
            trans.paypaltransid,
            refund.fullamount,
            refund.fullamount == refund.invoice.total_amount,
            '{0} refund {1}'.format(settings.ORG_SHORTNAME, refund.id),
        )
        # At this point, we succeeded. Anything that failed will bubble
        # up as an exception.
        return True

    def used_method_details(self, invoice):
        # Bank transfers don't need any extra information
        return "PayPal"
