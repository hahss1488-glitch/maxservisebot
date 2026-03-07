import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image

from ui.premium_renderer import render_dashboard_image_bytes, render_leaderboard_image_bytes

def main():
    out = Path('reports/previews')
    out.mkdir(parents=True, exist_ok=True)

    dashboard_payload = {
        'title': 'Дашборд',
        'decade_title': '1-я декада · 1–10 марта',
        'shift_status': 'Смена активна',
        'revenue_label': 'Выручка',
        'decade_earned': 30205,
        'decade_goal': 50000,
        'current_amount': '30 205 ₽',
        'target_amount': '50 000 ₽',
        'completion_percent': 0.60,
        'remaining_amount': '19 795 ₽',
        'shifts_left': '3',
        'per_shift_needed': '6 599 ₽',
        'decade_metrics': [
            ('Осталось до плана', '19 795 ₽', (244, 248, 255, 255)),
            ('Смен осталось', '3', (244, 248, 255, 255)),
            ('Нужно в смену', '6 599 ₽', (244, 248, 255, 255)),
        ],
        'shifts_done': '6',
        'cars_done': '95',
        'average_check': '317 ₽',
        'mini': ['Смен: 6', 'Машин: 95', 'Средний чек: 317 ₽'],
        'updated_at': '2026-03-07T17:30:00',
    }
    b = render_dashboard_image_bytes('closed', dashboard_payload)
    (out / 'dashboard_preview.png').write_bytes(b.getvalue())

    leaders = [
        {'telegram_id': 1, 'name': 'Александр Очень-Длинная Фамилия С Невероятным Хвостом', 'total_amount': 152340, 'total_hours': 122, 'avg_per_hour': 1249, 'run_rate': 1.14, 'shifts_count': 12},
        {'telegram_id': 2, 'name': 'Мария Лебедева', 'total_amount': 143100, 'total_hours': 153, 'avg_per_hour': 935, 'run_rate': 0.98, 'shifts_count': 14},
        {'telegram_id': 3, 'name': 'Илья', 'total_amount': 129870, 'total_hours': 118, 'avg_per_hour': 1100, 'run_rate': None, 'shifts_count': 11},
        {'telegram_id': 4, 'name': 'Владислав Нестандартное Имя Чтобы Проверить Fit', 'total_amount': 121500, 'total_hours': 144, 'avg_per_hour': 844, 'run_rate': 0.93, 'shifts_count': 13},
        {'telegram_id': 5, 'name': 'Алина', 'total_amount': 99700, 'total_hours': 90, 'avg_per_hour': 1108, 'run_rate': 1.21, 'shifts_count': 9},
        {'telegram_id': 6, 'name': 'Никита', 'total_amount': 85110, 'total_hours': 100, 'avg_per_hour': 851, 'run_rate': 0.87, 'shifts_count': 10},
    ]

    avatars = {1: Image.new('RGB', (128, 128), '#5E92FF'), 2: None, 3: Image.new('RGB', (128, 128), '#56D8CA')}
    l = render_leaderboard_image_bytes('1-я декада: 1–10 марта', leaders, top3_avatars=avatars)
    (out / 'leaderboard_preview.png').write_bytes(l.getvalue())

    print('saved previews to', out)


if __name__ == '__main__':
    main()