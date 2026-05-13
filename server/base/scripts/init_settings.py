from base.models import Setting
from django.core.exceptions import ValidationError


def run():
    default_values = {
        'A': 'N',  # App Maintenance
        'B': 'N',  # Cock-Fight Maintenance
        'C': 'N',  # Lottery Maintenance
        'D': 'N',  # Cricket Maintenance

        'E': 'https://t.me/example',  # Whatsapp Number

        'F': 'https://t.me/example',  # Telegram
        'G': 'https://youtube.com/example',
        'H': 'https://facebook.com/example',
        'I': 'https://instagram.com/example',

        'J': '100',    # Min Deposit
        'K': '299',    # Subscription
        'L': '50',     # Min Balance to Watch
        # 'M': '2',      # Free Withdrawals
        # 'N': '5',      # Withdrawal Commission %

        'O': 'Welcome to our platform, Play More Win More!',  # Promotion Text

        'P': 'https://testme.com/example.mp4',  # Price Pool Video Link
        'Q': 'https://testme.com/example.mp4',  # Price Pool Video Link

        'R': '0.85',
        'S': '0.85',
        'T': '10.00',
        'U': '0.75',
        'V': '0.75',
        'W': '9.00',
        'X': "EMPTY"
    }

    created = 0
    for code, _ in Setting.CATEGORY_CHOICES:
        if not Setting.objects.filter(action=code).exists():
            setting = Setting(
                action=code, actionValue=default_values.get(code, ''))
            try:
                setting.full_clean()
                setting.save()
                created += 1
            except ValidationError as e:
                print(f"Validation error for {code}: {e}")

    if created:
        print(f"{created} setting(s) created.")
    else:
        print("All settings already exist.")
