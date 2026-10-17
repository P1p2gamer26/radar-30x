from django.core.management.base import BaseCommand

from radar.build import build


class Command(BaseCommand):
    help = "Arma data/radar.json desde el último snapshot"

    def handle(self, *args, **opts):
        r = build()
        for t in r["topics"][:10]:
            self.stdout.write(f"{t['rank']:>2} {t['decision']:<10} p={t['p']:.2f} {t['stage']:<9} x{t['growth']:<5} fit={t['exec_fit']:.2f} {t['name']}")
        self.stdout.write(str(r["totals"]))
