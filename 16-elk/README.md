# ELK: время события и время загрузки

ДЗ OTUS, занятие 16. Работа принята 31.10.2026. Доработка 22.11.2026 учитывает рекомендацию преподавателя о разделении времени события и загрузки.

## Поля времени

- timestamp: исходная строка даты из CSV, сохранена без изменений.
- parsed_timestamp: разобранная дата события. Формат источника dd/MMM/yyyy:HH:mm:ss, locale en. Часовой пояс в файле отсутствует, поэтому явно принят UTC.
- @timestamp: время получения строки Logstash. Оно не перезаписывается датой события. По разнице с parsed_timestamp можно увидеть задержку доставки.
- Суточный индекс weblogs-v3-yyyy.MM.dd определяется по parsed_timestamp через поле @metadata.event_index_date. Он не зависит от текущего дня загрузки.

HTTP-статус проверяется до преобразования в integer. Строка заголовка исключается, повреждённые CSV, даты, запросы и статусы попадают в weblogs-rejected-v3.

Созданы новые индексы v3 и новые ID объектов Kibana. Предыдущие индексы v2, их данные и подтверждения не удалялись. В dashboard.ndjson временное поле index pattern и ось графика заменены на parsed_timestamp. Диапазон дашборда: 01.11.2017-01.04.2018.

## Воспроизведение

```powershell
docker compose up -d elasticsearch kibana
docker compose --profile load run --rm --no-deps logstash
```

Logstash читает только clickstream.conf. Позиция чтения хранится в sincedb-v3 внутри named volume. Повторный запуск с тем же файлом не перечитывает его. Не удаляйте volume для обычного перезапуска.

В Kibana http://localhost:5601 откройте Stack Management, Saved Objects, Import и импортируйте dashboard.ndjson с зависимостями. Дашборд: OTUS - HTTP status by source event time, ID otus-http-dashboard-v3. Проверка:

```powershell
Invoke-RestMethod 'http://localhost:9200/weblogs-v3-*/_count'
Invoke-RestMethod 'http://localhost:9200/weblogs-rejected-v3/_count'
```

## Предыдущая проверка 17.10.2026

Источник: 16007 строк данных. В прежнем прогоне v2 получено 15789 корректных HTTP-запросов и 218 повреждённых строк. Статусы: 200=11330, 302=3498, 304=658, 404=251, 206=52. Период событий: 2017-11-07 23:59:19 UTC - 2018-03-02 15:47:46 UTC.

verification.json и dashboard.png относятся к проверке v2 от 17.10.2026. Новый протокол v3 сохраняется отдельно в verification-v3.json.

## Проверка доработки 22.11.2026

Реальный повторный прогон: 15789 корректных документов и 218 rejected, всего 16007. Ни одного документа без parsed_timestamp. У каждого суточного индекса дата совпадает с датой события. Время событий осталось 2017-11-07 - 2018-03-02, время загрузки в @timestamp: 22.11.2026. Исходные timestamp и request сохранены. Все проверки PASS, фактический ответ сохранён в verification-v3.json, журнал в load-results-2026-11-22.log.
