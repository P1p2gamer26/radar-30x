from django.core.management.base import BaseCommand

from radar import label, student
from radar.collect import latest


class Command(BaseCommand):
    help = "Entrena el estudiante (Naive Bayes) con las etiquetas del profesor -> data/student.json"

    def handle(self, *args, **opts):
        self.stdout.write(str(student.run(latest()["signals"], label.cargar()["labels"])))
