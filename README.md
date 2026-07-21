# General Info

General Info checks `/var/lib/baypark-decision-queue/questions.sqlite3` every five
minutes. For recognized new questions it writes an answer and marks the row
answered so the existing dt-core email sender can send the reply.

It recognizes commands for help, Raspberry Pi status and uptime, reachability of
`192.168.5.215`, federal and Schedule A job searches, state job guidance for all
50 states, NOC and penetration-testing roadmaps through 2035, salary and
stability guidance, and Security+ study.

The sample incoming email format uses a Request-ID and a `Question:` field.

## USAJOBS

Live federal searches require `USAJOBS_EMAIL` and `USAJOBS_API_KEY` in
`/etc/general-info/general-info.env`. Never commit that file. Without credentials
the service returns official search links and setup guidance.

The service reports currently open postings. It cannot predict announcements
that have not been posted, and it does not claim any state is objectively
least-competitive for a person with a disability.

## GitHub

The installer initializes `/opt/general-info`, commits only public managed files,
and uses `git@github.com:we6jbo/gen-info.git`. A timer checks for public file
changes every 30 minutes. Configure an SSH deploy key for the `pi` user for
unattended pushes. Never commit a private key, token, database, logs, or email
credentials.

## License

GPL-3.0-only. Copyright © 2026 Jeremiah O'Neal.
