#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
sys.path.append('.')
from funcs import check_project_duration

# Test the specific case
test_text = """
🆔BE-8636

Scala Developer

Месячная ставка(на руки) до: 168 400 RUB

О кандидате:

Грейд: Middle+ / Senior
Локация специалиста: РФ, Беларусь, Казахстан, Армения
Тайм-зона проекта: мск

О проекте:
Описание проекта: * некоммерческий банк РФ
Дата старта проекта: ASAP
Продолжительность проекта : 2 месяца


Оформление:
Тип занятости: удалёнка
Загрузка: фулл-тайм
"""

result = check_project_duration(test_text)
print(f'Result for full text with "Продолжительность проекта : 2 месяца": {result}')

# Test simpler cases
simple_tests = [
    'Продолжительность проекта: 2 месяца',
    'продолжительность проекта : 2 месяца',
    'Продолжительность проекта : 2 месяца',
    '2 месяца',
    'проект на 2 месяца',
    'срок: 1 месяц',
    'длительность: 2 мес'
]

print('\nTesting individual patterns:')
for test in simple_tests:
    result = check_project_duration(test)
    status = '✓' if result else '✗'
    print(f'{status} "{test}": {result}')
