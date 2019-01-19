# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2019-01-14 21:16
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0010_payment_refector'),
        ('braintreepayment', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='braintreelog',
            name='paymentmethod',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='invoices.InvoicePaymentMethod'),
        ),
        migrations.AddField(
            model_name='braintreetransaction',
            name='paymentmethod',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='invoices.InvoicePaymentMethod'),
        ),
        migrations.RunSQL(
            "UPDATE braintreepayment_braintreelog SET paymentmethod_id = (SELECT id FROM invoices_invoicepaymentmethod WHERE classname='postgresqleu.util.payment.braintree.Braintree') WHERE paymentmethod_id IS NULL",
        ),
        migrations.RunSQL(
            "UPDATE braintreepayment_braintreetransaction SET paymentmethod_id = (SELECT id FROM invoices_invoicepaymentmethod WHERE classname='postgresqleu.util.payment.braintree.Braintree') WHERE paymentmethod_id IS NULL",
        ),
        migrations.AlterField(
            model_name='braintreelog',
            name='paymentmethod',
            field=models.ForeignKey(blank=False, null=False, on_delete=django.db.models.deletion.CASCADE, to='invoices.InvoicePaymentMethod'),
        ),
        migrations.AlterField(
            model_name='braintreetransaction',
            name='paymentmethod',
            field=models.ForeignKey(blank=False, null=False, on_delete=django.db.models.deletion.CASCADE, to='invoices.InvoicePaymentMethod'),
        ),

    ]
