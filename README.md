# Где бензин — официальный skill для ИИ-агентов

[![Tests](https://github.com/tylnyi/Gde-Benzin-Skill/actions/workflows/test.yml/badge.svg)](https://github.com/tylnyi/Gde-Benzin-Skill/actions/workflows/test.yml)

Найдите заправку рядом, проверьте нужную марку топлива и откройте выбранную АЗС
на [карте «Где бензин»](https://gde-benzin.ru/?utm_source=github&utm_medium=referral&utm_campaign=official_skill).

**Официальный домен — `gde-benzin.ru`.** Этот репозиторий поддерживается автором
сервиса. Данные поступают из API нашего сервиса.

## Установка одной командой

```bash
npx skills add tylnyi/Gde-Benzin-Skill --skill gde-benzin
```

CLI предложит выбрать агента. Для конкретного агента:

```bash
npx skills add tylnyi/Gde-Benzin-Skill --skill gde-benzin -a codex
npx skills add tylnyi/Gde-Benzin-Skill --skill gde-benzin -a claude-code
npx skills add tylnyi/Gde-Benzin-Skill --skill gde-benzin -a cursor
```

Команды устанавливают skill в текущий проект; `-g` означает глобальную установку.
Сам клиент требует **Python 3.10+**, интернет и не требует API-ключа или Python-пакетов.
Для установщика `skills` нужен Node.js 22.20+; без Node.js используйте ручную установку.

### Без Node.js

```bash
git clone https://github.com/tylnyi/Gde-Benzin-Skill.git
cd gde-benzin-skill
python3 skills/gde-benzin/scripts/gde_benzin.py --help
```

Скопируйте **всю папку** `skills/gde-benzin`, включая `scripts` и `references`,
в каталог skills своего агента. Например, для проекта Claude Code:

```bash
mkdir -p .claude/skills
cp -R skills/gde-benzin .claude/skills/
```

Для другого агента, поддерживающего формат Agent Skills, выберите его каталог
навыков. Установка скилла не подключает API автоматически ко всем обычным чатам
ChatGPT: у агента должны быть доступ к установленному навыку, Python и сеть.

## Что спросить у агента

- «Найди АЗС с АИ-95 в радиусе 5 км от этих координат: 55.7539, 37.6208».
- «Где заправиться дизелем рядом с центром Твери? Покажи ссылки на карту».
- «Проверь наличие и цены на АЗС с ID 41134».

Марка топлива не подменяется другой. Если местоположение неоднозначно, агент
должен его уточнить. Поиск от центра города явно отличается от поиска по GPS.

## Запуск напрямую

```bash
# Координаты места; возможны несколько вариантов — выберите нужный
python3 skills/gde-benzin/scripts/gde_benzin.py locate "Тверь"

# Только станции с актуальным положительным сведением об АИ-95
python3 skills/gde-benzin/scripts/gde_benzin.py search \
  --lat 55.7539 --lon 37.6208 --radius-km 5 --fuel 95

# Дизель, структурированный ответ для приложения или агента
python3 skills/gde-benzin/scripts/gde_benzin.py search \
  --lat 56.85967 --lon 35.89524 --fuel ДТ --format json

# Без фильтра марки: ближайшие станции, в том числе с неизвестным наличием
python3 skills/gde-benzin/scripts/gde_benzin.py search \
  --lat 55.7539 --lon 37.6208 --limit 3

# Карточка одной АЗС
python3 skills/gde-benzin/scripts/gde_benzin.py station 41134
```

Радиус: 0,5–50 км. В ответе до 10 станций, по умолчанию 5. Расстояние считается
по прямой, не по дорожному маршруту. При обрезанной сервером выдаче клиент
попросит уменьшить радиус вместо вывода неполного результата под видом полного.

Наличие учитывается по выбранной марке, с её собственным сроком действия.
Строже ограничить возраст можно через `--max-status-age-hours` (по умолчанию 6).
Цена показывается при возрасте не более 24 часов; порог можно задать отдельно
через `--max-price-age-hours`. Цена не считается подтверждением наличия.
Нет подходящей отметки — не значит, что бензин закончился.

## Переходы на нашу карту

Каждая станция содержит готовый `map_url`, например:

```text
https://gde-benzin.ru/?utm_source=ai_agent&utm_medium=referral&utm_campaign=official_skill#station=41134
```

Ссылка открывает конкретную карточку на карте. Её нужно сохранять в ответе агента,
а не заменять одной ссылкой на сторонний навигатор. Параметры отмечают переход
из официального skill; запросы к API сами по себе не являются переходами на сайт.
Клиент не отправляет дополнительную телеметрию и не сохраняет геолокацию локально.

## Для разработчиков

- [Инструкция для агента](skills/gde-benzin/SKILL.md).
- [Публичный HTTP-контракт и формат ответа клиента](skills/gde-benzin/references/api.md).
- [Python-клиент без зависимостей](skills/gde-benzin/scripts/gde_benzin.py).
- [Проверки](tests/test_client.py): `python3 -m unittest discover -s tests -v`.
- [Проверка живого API](tests/live_smoke.py): `python3 tests/live_smoke.py`.

Обычные тесты полностью локальные; живую проверку запускают явно. GitHub Actions
проверяет локальные сценарии на нескольких версиях Python. Работа сети и установки
агента отдельно проверяется перед релизом.

Не используйте этот клиент для массового выгружания страны или бесконечного
опроса. Один поиск делает один bbox-запрос (два при пересечении 180-го меридиана);
повтор при временной ошибке ограничен. При 429 соблюдается `Retry-After`.
Для большого приложения согласуйте нагрузку с владельцем сервиса.

Код skill распространяется под MIT. Лицензия кода не устанавливает отдельные
условия использования данных API.

---

## English

Official **gde-benzin.ru** Agent Skill: find gas stations in Russia, query petrol
or diesel availability and prices, and link directly to each station on our map.
Install with `npx skills add tylnyi/Gde-Benzin-Skill --skill gde-benzin`.
The client needs Python 3.10+, uses only the standard library, and requires no
API key. It never substitutes another fuel grade automatically. Availability
and prices have separate freshness checks. Distances are straight-line distances.
An installed skill and network/tool access are required; this does not enable
the integration in every hosted AI chat automatically.
