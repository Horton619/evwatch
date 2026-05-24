"""Email digest composition + send.

Renders ``templates/email.html.j2`` with the tagged listings from the current
run. Skips entirely if nothing to report. POSTs to Resend via
``RESEND_API_KEY``. Includes the weekly trends section on Mondays only.
Subject patterns per SPEC §5.5.
"""
